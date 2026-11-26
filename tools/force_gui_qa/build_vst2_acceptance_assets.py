#!/usr/bin/env python3
"""Build conservative VST2 acceptance and parameter-evidence artifacts."""
from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "docs/qa-v4/ASR10_FACTORY_PARAMETER_SPEC_AUDIT_V1.json"
REGISTRY = ROOT / "docs/qa-v4/source/ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json"
RECON = ROOT / "docs/qa-v4/ASR10_PARAMETER_RECONCILIATION_V2.json"
OUT = ROOT / "docs/qa-v4"

MOD_LABELS = {"MOD SRC1", "MOD SRC2", "DST1", "DST2", "MIN1", "MIN2", "MAX1", "MAX2"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(value: str) -> str:
    value = value.upper()
    value = re.sub(r"\([^)]*\)", " ", value)
    return re.sub(r"[^A-Z0-9]+", "", value)


def classify_manual(effect: dict, param: dict, deferred: bool) -> tuple[str, str]:
    if deferred:
        return "MISSING_ORIGINAL_OS_CAPTURE", "The included OS inventory marks this effect deferred."
    ident = param["id"].lower()
    label = param["manual_label"].upper()
    mappings = effect.get("known_manual_heading_normalizations", [])
    for mapping in mappings:
        if param["id"] not in mapping.get("source_descriptor_ids", []):
            continue
        relation = mapping.get("relationship", "")
        if "COMPOSITE" in relation or "EXPANDS" in relation:
            return "COMPOSITE_FIELD", relation
        return "NAMING_ABBREVIATION_MISMATCH", relation
    if "MOD" in ident or "MOD " in label or label.startswith(("DST", "MIN ", "MAX ")):
        return "MODULATION_FIELD", "Descriptor name indicates a modulation control; no OS mapping is asserted."
    if any(token in ident for token in ("variation", "var_")):
        return "VARIATION_SPECIFIC_FIELD", "Descriptor identity indicates variation scope; OS linkage is unresolved."
    return "UNRESOLVED", "No direct OS label association or explicit normalization is published."


def classify_os(effect: dict, field: dict) -> tuple[str, str]:
    label = field.get("label", "")
    if label.strip().upper() == "VAR":
        return "VARIATION_SPECIFIC_FIELD", "OS field is the effect Variation selector."
    if label.strip().upper() in MOD_LABELS:
        return "MODULATION_FIELD", "OS label is an observed modulation assignment field."
    selected = field.get("selected_subfield_observations", [])
    if selected:
        return "COMPOSITE_FIELD", "OS cursor observations expose selected subfields under a composite heading."
    label_n = norm(label)
    exact = [p["id"] for p in effect["parameters"] if norm(p.get("manual_label", "")) == label_n and label_n]
    if exact:
        return "EXACT_MATCH", "Exact normalized label only; semantic identity is still pending because this row is in the unlinked set."
    return "UNRESOLVED", "OS field is observed but has no published manual-catalog linkage."


def main() -> None:
    audit = json.loads(AUDIT.read_text())
    reg = json.loads(REGISTRY.read_text())
    rec = json.loads(RECON.read_text())
    reg_effects = {e["slot"]: e for e in reg["effects"]}
    manual_rows, deferred_rows, os_rows = [], [], []

    for effect in audit["effects"]:
        slot = effect["slot"]
        deferred = effect["os_scan_status"] == "deferred"
        for p in effect["parameters"]:
            if p["os_association_status"] == "DOCUMENTED_NOT_LABEL_MATCHED_REVIEW":
                classification, rationale = classify_manual(effect, p, False)
                row = {
                    "effect_slot": slot, "effect_name": effect["manual_effect_name"],
                    "parameter_id": p["id"], "manual_label": p["manual_label"],
                    "manual_range": p["manual_range_text"], "manual_pdf_page": p["manual_pdf_page"],
                    "manual_source": p["manual_source"], "published_os_status": p["os_association_status"],
                    "classification": classification, "classification_rationale": rationale,
                    "dsp_mapping_status": p["dsp_mapping_status"], "dsp_verified": p["dsp_verified"],
                    "os_observed_labels": p["os_observed_labels"],
                    "association_claimed": False,
                }
                manual_rows.append(row)
            elif deferred and p["os_association_status"] == "OS_INVENTORY_DEFERRED":
                classification, rationale = classify_manual(effect, p, True)
                deferred_rows.append({
                    "effect_slot": slot, "effect_name": effect["manual_effect_name"],
                    "parameter_id": p["id"], "manual_label": p["manual_label"],
                    "manual_range": p["manual_range_text"], "manual_pdf_page": p["manual_pdf_page"],
                    "classification": classification, "classification_rationale": rationale,
                    "association_claimed": False,
                })

        extra_counts = collections.Counter(effect["os_extra_field_labels"])
        fields_by_label: dict[str, list[dict]] = collections.defaultdict(list)
        for f in effect["os_observed_fields"]:
            fields_by_label[f["label"]].append(f)
        for label, count in extra_counts.items():
            candidates = fields_by_label.get(label, [])
            for occurrence in range(count):
                field = candidates[occurrence] if occurrence < len(candidates) else {"label": label, "values": [], "selected_subfield_observations": [], "observation_count": 0}
                classification, rationale = classify_os(effect, field)
                os_rows.append({
                    "effect_slot": slot, "effect_name": effect["manual_effect_name"],
                    "os_label": label, "occurrence": occurrence + 1,
                    "values": field.get("values", []), "selected_subfield_observations": field.get("selected_subfield_observations", []),
                    "observation_count": field.get("observation_count", 0),
                    "classification": classification, "classification_rationale": rationale,
                    "published_status": "OS_OBSERVED_NOT_DIRECTLY_IN_MANUAL_CATALOG",
                    "manual_parameter_candidates": [p["id"] for p in effect["parameters"] if norm(p.get("manual_label", "")) == norm(label) and norm(label)],
                    "association_claimed": False,
                })

    # Transparent ranking heuristic: composite cursor evidence first, then
    # variation/modulation fields, then larger observation counts; slot/label
    # provide stable tie-breaking. This ranks investigation value, not function.
    os_ranked = sorted(os_rows, key=lambda r: (
        0 if r["classification"] == "COMPOSITE_FIELD" else
        1 if r["classification"] in ("VARIATION_SPECIFIC_FIELD", "MODULATION_FIELD") else
        2 if r["classification"] == "UNRESOLVED" else 3,
        -len(r["selected_subfield_observations"]), -len(r["values"]), -r["observation_count"],
        r["effect_slot"], r["os_label"], r["occurrence"],
    ))
    top10 = [{"rank": i + 1, **row, "priority_basis": "Published OS field has composite selection, variation/modulation semantics, or repeated observations; this is a research-priority heuristic only."}
             for i, row in enumerate(os_ranked[:10])]
    manual_counts = collections.Counter(x["classification"] for x in manual_rows)
    os_counts = collections.Counter(x["classification"] for x in os_rows)
    out = {
        "schema": "asr10-parameter-evidence-mismatch-inventory-v1",
        "evidence": {
            "manual_os_audit": {"file": "ASR10_FACTORY_PARAMETER_SPEC_AUDIT_V1.json", "sha256": digest(AUDIT), "manual_pdf_sha256": audit["evidence"]["manual"][audit["evidence"]["manual"].find("SHA-256 ") + 8:audit["evidence"]["manual"].find("; PDF")], "source_commit": "ASR10 manual-to-OS audit as published at QA baseline 6115232"},
            "parameter_registry": {"file": "source/ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json", "sha256": digest(REGISTRY), "source_commit": reg.get("sources", {})},
            "reconciliation_summary": {"file": "ASR10_PARAMETER_RECONCILIATION_V2.json", "sha256": digest(RECON), "manual_unmatched_count": rec["os_inventory"]["manual_entries_unmatched_for_review"], "os_unlinked_association_count": rec["os_inventory"]["os_associations_not_linked_to_catalog_rows"]},
            "limitation": "The raw original OS inventory is not in Git. This derives records only from the published normalized audit. A label-only candidate is never promoted to a semantic mapping.",
        },
        "classification_policy": {
            "exact_match": "normalized label identity is evidence of a label match only; source OS row remains unlinked pending semantic confirmation",
            "composite_field": "explicit cursor-selected subfield evidence or a published normalization says one manual heading expands to multiple fields",
            "naming_abbreviation_mismatch": "published manual-heading normalization identifies a shared/consolidated OS field",
            "variation_specific_field": "explicit VAR field or descriptor identity; no effect-specific control mapping inferred",
            "modulation_field": "recognized manual/OS modulation descriptor; destination restrictions remain unverified unless separately evidenced",
            "missing_original_os_capture": "the published inventory marks the effect scan deferred or the manual descriptor has no associated field in the published observations; this does not prove the original OS lacks the control",
            "unresolved": "published evidence does not establish a reliable relation",
        },
        "counts": {
            "manual_rows_unmatched": len(manual_rows), "manual_unmatched_classifications": dict(sorted(manual_counts.items())),
            "deferred_manual_rows_additional": len(deferred_rows), "os_unlinked_associations": len(os_rows),
            "os_unlinked_classifications": dict(sorted(os_counts.items())),
            "all_manual_parameter_descriptors": 594,
            "os_field_associations_total": 1040,
            "os_field_observations_total": 5484,
        },
        "manual_unmatched_rows": manual_rows,
        "deferred_manual_rows": deferred_rows,
        "os_unlinked_fields": os_rows,
        "top_ten_future_research_fields": top10,
        "ranking_note": "Top ten uses the documented heuristic in priority_basis. It ranks evidence-rich ambiguities, not likely DSP importance or truth.",
    }
    (OUT / "ASR10_PARAMETER_EVIDENCE_MISMATCH_INVENTORY_V1.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")

    gates = {
        "schema": "asr10-vst2-independent-release-gates-v1",
        "candidate": {"codex1_runtime_commit": "1984744", "codex2_audio_lab_commit": "6a9317f", "vst2_candidate_commit": None, "candidate_status": "BLOCKED_NO_PUBLISHED_VST2_INTEGRATION_CANDIDATE", "baseline_vst_test_source_commit": "611523252079ff579060b539effa7e304877fcd7"},
        "gates": [
            {"gate": "Original-OS register equivalence", "status": "PASS", "coverage": "Previously validated HALL DECAY TIME mapped register subset only", "evidence": "Published HALL 40/41 and full-range OS register audits; this is parameter-specific and not whole-plugin audio equivalence."},
            {"gate": "Standalone native audio", "status": "PASS", "coverage": "HALL standalone extreme-range test matrix only", "evidence": "HALL standalone extreme-range renders and comparisons in ASR10_HALL_EXTREME_RANGE_AUDIO_QA_V1.json; package/firmware evidence in its provenance."},
            {"gate": "Native desktop VST2 audio", "status": "FAIL", "evidence": "The QA-baseline VST2 binary rendered all 50 slots and passed state chunk round-trip before the callback harness failed: NaN setParameter remained non-finite. Separate NaN processReplacing input also generated non-finite output. Codex 2's future candidate is separately BLOCKED because no candidate was published."},
            {"gate": "Full-range HALL control", "status": "BLOCKED", "evidence": "Current published plugin interface exposes HALL/ROM-02 bus selectors only; no full-range HALL decay parameter route in plugin source. Candidate callback/register/audio trace required."},
            {"gate": "ARMv7 binary build", "status": "PASS", "evidence": "QA-baseline source commit 6115232 built ARMv7 hard-float with SDK Zig 0.17.1 and passed SDK validation; this does not transfer to a future Codex 2 binary."},
            {"gate": "Physical Akai Force operation", "status": "NOT TESTED", "evidence": "No physical test for this candidate; prior V1/V3 observations do not transfer to a new binary."},
            {"gate": "Exact original-hardware audio equivalence", "status": "NOT TESTED", "evidence": "No same-state VST output against exact OS reference with candidate-bound provenance."},
        ],
        "scope_note": "PASS on a research/runtime gate does not imply integrated plugin acceptance or Force release readiness.",
    }
    (OUT / "ASR10_VST2_INDEPENDENT_RELEASE_GATES_V1.json").write_text(json.dumps(gates, indent=2) + "\n")
    print(json.dumps({"manual_unmatched": len(manual_rows), "manual_unmatched_classes": manual_counts,
                      "deferred_manual": len(deferred_rows), "os_unlinked": len(os_rows),
                      "os_unlinked_classes": os_counts, "top_ten": [x["effect_slot"] for x in top10]}, default=dict, indent=2))


if __name__ == "__main__":
    main()
