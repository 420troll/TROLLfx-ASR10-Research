#!/usr/bin/env python3
"""Join manual-derived catalog rows to the existing OS LCD inventory.

The OS inventory is intentionally read from a user-local path; raw captures are
not copied into the repository. Output contains normalized labels/value
observations and association status, not full LCD frames or DSP trace windows.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/qa-v4/source"
OUTPUT = ROOT / "docs/qa-v4/ASR10_FACTORY_PARAMETER_SPEC_AUDIT_V1.json"
MANUAL_PAGES = {
    1: 99, 2: 99, 3: 99, 4: 100, 5: 100, 6: 100, 7: 101, 8: 102, 9: 102,
    10: 103, 11: 104, 12: 105, 13: 106, 14: 107, 15: 107, 16: 107,
    17: 109, 18: 109, 19: 111, 20: 112, 21: 113, 22: 116, 23: 116,
    24: 116, 25: 118, 26: 119, 27: 121, 28: 122, 29: 122, 30: 124,
    31: 126, 32: 126, 33: 127, 34: 129, 35: 131, 36: 133, 37: 134,
    38: 136, 39: 137, 40: 139, 41: 140, 42: 141, 43: 144, 44: 145,
    45: 147, 46: 148, 47: 150, 48: 152, 49: 152, 50: 153,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", type=Path, default=Path(
        "/home/gamer/worktrees/asr10-full-factory-parameter-recovery/docs/"
        "ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json"))
    ap.add_argument("--output", type=Path, default=OUTPUT)
    a = ap.parse_args()
    catalog = json.loads((SOURCE / "ASR10_FACTORY_PARAMETER_CATALOG_V1.json").read_text())
    registry = json.loads((SOURCE / "ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json").read_text())
    inv = json.loads(a.inventory.read_text())
    by_slot = {e["slot"]: e for e in inv["entries"]}
    reg_by_slot = {e["slot"]: e for e in registry["effects"]}
    status_counts = collections.Counter()
    unique_extra_labels = set()
    rows = []
    for effect in catalog["effects"]:
        slot = effect["slot"]
        os_effect = by_slot.get(slot, {})
        reg_effect = reg_by_slot.get(slot, {})
        comparison = {p["id"]: p for p in os_effect.get("manual_comparison", [])}
        reg_params = {p["id"]: p for p in reg_effect.get("parameters", [])}
        params = []
        for p in effect["parameters"]:
            cmp = comparison.get(p["id"])
            reg = reg_params.get(p["id"], {})
            association = cmp["status"] if cmp else (
                "OS_INVENTORY_DEFERRED" if os_effect.get("status") == "deferred"
                else "NO_DIRECT_ASSOCIATION_ROW")
            status_counts[association] += 1
            params.append({
                "id": p["id"], "manual_label": p["display_name"],
                "manual_range_text": p.get("documented_range"),
                "units": p.get("units"), "manual_source": "Musician's Manual §6",
                "documented_display_type": p.get("display_type"),
                "display_format": p.get("display_format"),
                "display_domain_note": p.get("display_domain"),
                "documented_numeric_domain": reg.get("documented_numeric_domain"),
                "documented_step": reg.get("documented_step"),
                "step_confidence": reg.get("step_confidence", "not established"),
                "documented_choices": reg.get("discrete_choices", []),
                "os_numeric_domain": reg.get("observed_os_numeric_domain"),
                "os_observed_values_across_variations": reg.get("os_observed_values_across_factory_variations", []),
                "manual_pdf_page": MANUAL_PAGES[slot],
                "manual_catalog_claim": "DOCUMENTED; see cautions in audit report",
                "os_association_status": association,
                "os_observed_labels": cmp.get("observed_labels", []) if cmp else [],
                "os_observed": bool(cmp and cmp.get("observed_labels")),
                "dsp_mapping_status": reg.get("dsp_mapping_status", "UNKNOWN"),
                "dsp_verified": bool(reg.get("runtime_ready", False)),
                "audio_status": reg.get("audio_status", "not verified"),
                "catalog_evidence_note": p.get("evidence"),
            })
        observed_fields = []
        for f in os_effect.get("os_observed_fields", []):
            observations = f.get("observations", [])
            values = []
            seen = set()
            for o in observations:
                value = o.get("displayed_value")
                variation = o.get("variation")
                key = (variation, value)
                if key not in seen:
                    values.append({"variation": variation, "value": value,
                                   "ordinal": o.get("ordinal")})
                    seen.add(key)
            selected = []
            for o in observations:
                for s in o.get("selected_fields", []):
                    item = {"selected_label": s.get("field_label"),
                            "selected_value": s.get("selected_text"),
                            "cursor_span": s.get("cursor_span"),
                            "variation": o.get("variation"),
                            "ordinal": o.get("ordinal")}
                    if item not in selected:
                        selected.append(item)
            observed_fields.append({"label": f.get("label"), "values": values,
                                    "selected_subfield_observations": selected,
                                    "observation_count": len(observations)})
        extras = os_effect.get("os_observed_not_directly_in_manual_catalog", [])
        unique_extra_labels.update(extras)
        variation_labels = []
        for f in os_effect.get("os_observed_fields", []):
            if f.get("label", "").strip().upper() == "VAR":
                for o in f.get("observations", []):
                    v = o.get("displayed_value")
                    if v and v not in variation_labels:
                        variation_labels.append(v)
        rows.append({
            "slot": slot, "effect_id": effect["id"],
            "manual_effect_name": effect["factory_name"],
            "os_effect_name": os_effect.get("factory_name"),
            "effect_name_match": bool(os_effect and effect["factory_name"].upper().replace(" ", "") ==
                                      os_effect["factory_name"].upper().replace(" ", "")),
            "manual_page": MANUAL_PAGES[slot],
            "manual_descriptor_count": len(params),
            "os_scan_status": os_effect.get("status", "NO_LCD_INVENTORY_ENTRY"),
            "os_variation_labels": variation_labels,
            "manual_variation_policy": "VAR selects one of four individually editable variation buffers; each variation may define two modulation sources, destinations and min/max ranges (Musician's Manual §6 intro).",
            "manual_variations": {"count": 4, "os_variation_labels_observed": variation_labels,
                                  "per_variation_state": "four separate edit buffers per manual; exact state behavior not inferred as DSP mapping"},
            "modulation_policy": {
                "manual_fields": ["MOD SRC 1", "DST 1", "MIN 1", "MAX 1", "MOD SRC 2", "DST 2", "MIN 2", "MAX 2"],
                "source_choices_documented": ["WHEEL", "PBEND", "PRESS", "PEDAL", "XCTRL", "KBD", "VEL", "KEYDN", "SUSTN", "FSW-L", "PATCH", "OFF"],
                "destination_choices": "effect/variation dependent; must be enumerated from OS evidence, not guessed",
                "observed_field_presence": [x["label"] for x in observed_fields if x["label"] in
                                             {"MOD SRC1", "MOD SRC2", "DST1", "DST2", "MIN1", "MIN2", "MAX1", "MAX2"}],
                "availability_condition": "not exhaustively established; absence in scan is not proof of unsupported",
            },
            "parameters": params,
            "known_manual_heading_normalizations": _normalizations(slot, effect),
            "os_observed_fields": observed_fields,
            "os_extra_field_labels": extras,
            "os_extra_unique_label_count": len(set(extras)),
            "lcd_stop_count": os_effect.get("lcd_stop_count"),
        })
    out = {
        "schema": "asr10-factory-parameter-spec-audit-v1",
        "evidence": {
            "manual": "ASR-10 Musician's Manual, Sections 5 and 6; local user copy SHA-256 e8ab5100904caf91fe355065ed9646aff197761b0663a7d452dc98af1f9a29dc; PDF page numbers refer to that copy",
            "manual_source_url": "https://datassette.s3.us-west-004.backblazeb2.com/manuais/ensoniq_eq_musicians_manual.pdf",
            "manual_catalog_commit": "e29cb8aa507abe10e2117cba374ee0c61d2a90f4",
            "os_lcd_inventory_commit": "f1a9f0f524835de8c85bf66012e4a1e29a6df24b",
            "os_lcd_inventory_sha256": sha256(a.inventory),
            "os_inventory_raw_file_in_git": False,
            "os_inventory_policy": "Normalized label/value observations only; raw captures, ROMs, firmware and private DSP traces excluded.",
            "dsp_registry_commit": "7d38ec2bc3369ecd16f9e284ba85ccfd6fe46b55",
        },
        "interpretation": {
            "manual_described": "catalog descriptor; may be a grouped heading or effect-specific range row, not necessarily a unique LCD control",
            "os_observed": "field appears in captured OS inventory; does not establish DSP function",
            "dsp_verified": "only registry runtime-ready evidence; must be kept separate from documentation and LCD presence",
            "counts_warning": "594 catalog descriptors are not a validated count of unique editable controls.",
        },
        "coverage": {
            "effects": len(rows),
            "catalog_manual_descriptors": sum(len(x["parameters"]) for x in rows),
            "os_field_label_associations": sum(len(x["os_observed_fields"]) for x in rows),
            "os_field_observations": sum(sum(f["observation_count"] for f in x["os_observed_fields"]) for x in rows),
            "manual_rows_exact_alias_or_expansion": sum(status_counts[s] for s in ("OS_OBSERVED_LABEL_MATCH", "OS_OBSERVED_LABEL_ALIAS_OR_EXPANSION")),
            "manual_rows_review_unmatched": status_counts["DOCUMENTED_NOT_LABEL_MATCHED_REVIEW"],
            "os_unlisted_field_associations": sum(len(x["os_extra_field_labels"]) for x in rows),
            "os_unlisted_unique_labels": len(unique_extra_labels),
            "dsp_verified_rows": sum(bool(p["dsp_verified"]) for x in rows for p in x["parameters"]),
            "slot_2_lcd_status": by_slot.get(2, {}).get("status", "NO_ENTRY"),
            "status_counts": dict(status_counts),
        },
        "effects": rows,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(out["coverage"], indent=2))


def _normalizations(slot: int, effect: dict) -> list[dict]:
    """Preserve source descriptor IDs while stating manual grouping explicitly."""
    if slot in (14, 15, 16):
        room_range = {14: "0.20 to 100.0 sec.", 15: "0.20 to 150.0 sec.",
                      16: "0.70 to 250.0 sec."}[slot]
        return [{"canonical_control_id": "decay_time", "canonical_label": "DECAY TIME",
                 "source_descriptor_ids": ["decay_time_small_room_1", "large_room_1", "hall_reverb2_1"],
                 "effect_specific_range": room_range, "units": "seconds",
                 "relationship": "ONE_CONTROL_WITH_ALGORITHM_SPECIFIC_RANGE",
                 "os_field_label": "DECAY TIME", "os_field_evidence": "single captured LCD row per effect; distinct displayed values",
                 "ui_correction": "show one DECAY TIME control and the slot-specific range; do not show three decay controls"},
                {"canonical_control_id": "position_balance", "canonical_label": "POSITN BAL {1|2|3}",
                 "source_descriptor_ids": ["positn_bal_1_to_3_1"], "effect_specific_range": "-99 to +99",
                 "relationship": "ONE_COMPOSITE_LCD_HEADING_WITH_THREE_INDEPENDENTLY_SELECTED_VALUES",
                 "os_field_label": "POSITN BAL", "os_selected_value_count": 3,
                 "ui_correction": "expose 1/2/3 as distinct controls or an explicit indexed editor; do not collapse the three values"}]
    if slot in (17, 18):
        small = slot == 17
        decay_range = "0.2 to 100.0 sec." if small else "0.4 to 140.0 sec."
        predelay_range = "0 to 500 ms" if small else "0 to 430 ms"
        return [
            {"canonical_control_id": "decay_time", "canonical_label": "DECAY TIME",
             "source_descriptor_ids": ["decay_time_small_plate_1", "large_plate_1"],
             "effect_specific_range": decay_range, "units": "seconds",
             "relationship": "ONE_CONTROL_WITH_ALGORITHM_SPECIFIC_RANGE",
             "os_field_label": "DECAY TIME", "ui_correction": "one DECAY TIME control per effect"},
            {"canonical_control_id": "predelay_time", "canonical_label": "PREDELAY TIME",
             "source_descriptor_ids": ["predelay_time_small_plate_1", "large_plate_2"],
             "effect_specific_range": predelay_range, "units": "milliseconds",
             "relationship": "ONE_CONTROL_WITH_ALGORITHM_SPECIFIC_RANGE",
             "os_field_label": "PREDELAY TIME", "ui_correction": "one PREDELAY TIME control; do not label its Large Plate range row as a second control"},
            {"canonical_control_id": "early_reflection_level", "canonical_label": "ER LEV {1..4}",
             "source_descriptor_ids": ["er_lev_1_to_4_1"], "effect_specific_range": "-99 to +99",
             "relationship": "ONE_COMPOSITE_LCD_HEADING_WITH_FOUR_INDEPENDENTLY_SELECTED_VALUES",
             "os_field_label": "ER LEV", "os_selected_value_count": 4,
             "ui_correction": "expose four signed values; retain the independent cursor-selected subfield"},
        ]
    if slot in (4, 5):
        delay_range = "0 to 2000 ms" if slot == 4 else "0 to 1300 ms"
        return [{"canonical_control_id": "bus_delay_mix", "canonical_label": "BUS{1|2} DELAY MIX",
                 "source_descriptor_ids": ["bus1_and_2_delay_mix_1"], "effect_specific_range": "0 to 99",
                 "relationship": "ONE_HEADING_EXPANDS_TO_TWO_BUS_CONTROLS",
                 "os_field_labels": ["BUS1 DELAY MIX", "BUS2 DELAY MIX"]},
                {"canonical_control_id": "bus_feedback", "canonical_label": "BUS{1|2} FEEDBACK",
                 "source_descriptor_ids": ["bus1_and_2_feedback_1"], "effect_specific_range": "0 to 99",
                 "relationship": "ONE_HEADING_EXPANDS_TO_TWO_BUS_CONTROLS",
                 "os_field_labels": ["BUS1 FEEDBACK", "BUS2 FEEDBACK"]},
                {"canonical_control_id": "bus_delay_time_lr", "canonical_label": "BUS{1|2} TIME {L|R}",
                 "source_descriptor_ids": ["delay_time_1"], "effect_specific_ranges": {"BUS1": delay_range, "BUS2": "0 to 150 ms"},
                 "units": "milliseconds", "relationship": "ONE_HEADING_EXPANDS_TO_BUS_AND_CHANNEL_CONTROLS",
                 "os_field_labels": ["BS1 TIME L", "BS1 TIME R", "BS2 TIME L", "BS2 TIME R"],
                 "ui_correction": "show four controls with distinct BUS1/BUS2 ranges; left/right are independent"}]
    if slot == 9:
        return [{"canonical_control_id": "dist_gain_in_out", "canonical_label": "DIST GAIN IN / DIST GAIN OUT",
                 "source_descriptor_ids": ["dist_gain_in_out_in_and_out_1"], "effect_specific_range": "0 to 99",
                 "relationship": "ONE_HEADING_EXPANDS_TO_TWO_CONTROLS",
                 "os_field_labels": ["DIST GAIN IN", "DIST GAIN OUT"]}]
    if slot in (17, 18, 21):
        return [{"canonical_control_id": "early_reflection_level", "canonical_label": "ER LEV {1..4}",
                 "source_descriptor_ids": ["er_lev_1_to_4_1"], "effect_specific_range": "-99 to +99",
                 "relationship": "ONE_COMPOSITE_LCD_HEADING_WITH_FOUR_INDEPENDENTLY_SELECTED_VALUES",
                 "os_field_label": "ER LEV", "os_selected_value_count": 4,
                 "ui_correction": "expose four signed values; retain the independent cursor-selected subfield"}]
    if slot in (22, 23, 24):
        return [{"canonical_control_id": "envelope_level", "canonical_label": "ENV LEV {1..9}",
                 "source_descriptor_ids": ["env_lev_1_to_9_1"], "effect_specific_range": "0 to 99",
                 "relationship": "MANUAL_NINE_LEVEL_GROUP_VS_OS_FIVE_VALUE_DISPLAY_UNRESOLVED",
                 "os_field_label": "ENV LEV", "os_selected_value_count_per_observation": 5,
                 "ui_correction": "do not present nine independent controls until remaining four OS fields are located; retain five observed values and mark correspondence unresolved"}]
    return []


if __name__ == "__main__":
    main()
