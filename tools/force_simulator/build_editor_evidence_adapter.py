"""Build the PC editor's read-only crosswalk from Codex 3's QA artifacts.

This is an adapter, not a second parameter authority: the source matrix keeps
the manual/OS/DSP layers separate and is versioned independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation-matrix", required=True, type=Path)
    ap.add_argument("--spec-audit", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    validation = json.loads(args.validation_matrix.read_text())
    audit = json.loads(args.spec_audit.read_text())
    qa_by_slot = {int(e["slot"]): e for e in validation["effects"]}
    audit_by_slot = {int(e["slot"]): e for e in audit["effects"]}

    effects = []
    for slot in sorted(qa_by_slot):
        qa = qa_by_slot[slot]
        source = audit_by_slot[slot]
        audited = {p["id"]: p for p in source["parameters"]}
        parameters = []
        for row in qa["parameters"]:
            p = audited.get(row["original_parameter_id"], {})
            parameters.append({
                "id": row["original_parameter_id"],
                "name": row["original_parameter_name"],
                "classification": row["classification"],
                "manual": {
                    "range": row.get("documented_range"),
                    "type": row.get("documented_type"),
                    "units": row.get("units"),
                    "choices": row.get("enumerated_choices"),
                    "step": row.get("full_range_step_size"),
                    "source": p.get("manual_source"),
                    "pdf_page": p.get("manual_pdf_page"),
                },
                "original_os": {
                    "association_status": p.get("os_association_status", "UNKNOWN"),
                    "observed": p.get("os_observed", False),
                    "labels": p.get("os_observed_labels", []),
                    "values_by_variation": p.get("os_observed_values_across_variations", []),
                },
                "dsp": {
                    "classification": row.get("classification", "UNKNOWN"),
                    "mapping": row.get("register_mapping", {}),
                    "vst_mappings": row.get("current_vst_mapping", []),
                    "full_range_implemented": row.get("full_documented_range_implemented", False),
                    "audio_status": row.get("audio_behavior_validation", "NOT_VALIDATED"),
                },
            })
        extras = []
        for extra in qa.get("additional_recovered_controls", []):
            candidate_labels = [extra.get("control_label", "")]
            aliases = {
                "REVERB MIX BUS1": ["REVERB MIX BUS1"],
                "REVERB MIX BUS2": ["REVERB MIX BUS2"],
            }
            candidate_labels.extend(aliases.get(extra.get("control_label", ""), []))
            fields = [f for f in source.get("os_observed_fields", []) if f.get("label") in candidate_labels]
            points = extra.get("verified_points", [])
            addresses = sorted({w.get("gpr") for p in points for w in p.get("ordered_writes", []) if w.get("gpr")})
            extras.append({**extra,
                "original_os": {"association_status": "OS_OBSERVED_LABEL_MATCH" if fields else "UNKNOWN",
                    "observed": bool(fields), "labels": [f["label"] for f in fields], "fields": fields},
                "dsp_evidence": {"classification": extra.get("classification", "UNKNOWN"),
                    "mapping": {"register_addresses": addresses, "observed_setting_points": points},
                    "vst_mappings": extra.get("current_vst_mapping", []),
                    "full_range_implemented": extra.get("full_documented_range_implemented", False),
                    "audio_status": "NOT_VALIDATED"},
            })
        effects.append({
            "slot": slot,
            "effect_id": qa["effect_id"],
            "name": qa["factory_effect_name"],
            "os_scan_status": source.get("os_scan_status", "UNKNOWN"),
            "variations": source.get("manual_variations", {}),
            "modulation": source.get("modulation_policy", {}),
            "os_observed_fields": source.get("os_observed_fields", []),
            "normalizations": source.get("known_manual_heading_normalizations", []),
            "parameters": parameters,
            "additional_recovered_controls": extras,
        })

    bundle = {
        "schema": "trollfx-asr10-pc-editor-evidence-adapter-v1",
        "provenance": {
            "adapter_role": "Read-only crosswalk to independent parameter validation evidence; not a DSP write allowlist.",
            "validation_matrix_schema": validation.get("schema"),
            "validation_matrix_sha256": digest(args.validation_matrix),
            "validation_matrix_inventory_commit": validation.get("provenance", {}).get("inventory_commit"),
            "validation_matrix_registry_commit": (
                validation.get("provenance", {}).get("dsp_registry_commit")
                or audit.get("evidence", {}).get("dsp_registry_commit")
            ),
            "spec_audit_schema": audit.get("schema"),
            "spec_audit_sha256": digest(args.spec_audit),
            "spec_audit_inventory_commit": audit.get("evidence", {}).get("os_lcd_inventory_commit"),
            "spec_audit_registry_commit": audit.get("evidence", {}).get("dsp_registry_commit"),
        },
        "coverage": {
            "effects": len(effects),
            "manual_descriptors": validation.get("summary", {}).get("original_parameters"),
            "additional_recovered_controls": validation.get("summary", {}).get("additional_recovered_controls"),
            "os_field_associations": audit.get("coverage", {}).get("os_field_label_associations"),
            "os_field_observations": audit.get("coverage", {}).get("os_field_observations"),
            "dsp_classification": validation.get("summary", {}).get("classification", {}),
            "full_range_implemented": validation.get("summary", {}).get("full_range_implemented", 0),
        },
        "effects": effects,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {args.output}; {len(effects)} effects; "
          f"{sum(len(e['parameters']) for e in effects)} manual identities")


if __name__ == "__main__":
    main()
