#!/usr/bin/env python3
"""Merge manual inventory, V4 OS observations, and exact V2/V3/V5 write points."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RANGE_EVIDENCE_PATH = ROOT / "docs/ASR10_FACTORY_PARAMETER_RANGE_RECOVERY_V1.json"


def numeric_range(text: str | None):
    if not text:
        return None
    match = re.fullmatch(r"\s*([+-]?\d+)\s+to\s+([+-]?\d+)\s*", text, re.I)
    if not match:
        return None
    return {"minimum": int(match.group(1)), "maximum": int(match.group(2)), "step": 1}


def merge_maps() -> dict[tuple[int, str], dict]:
    merged = {}
    v2 = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json").read_text())
    for effect in v2["effects"]:
        for item in effect["parameters"]:
            dst = merged.setdefault((effect["slot"], item["id"]), {"id": item["id"], "display_name": item["ui_label"],
                "display_order": item["live_display_order"], "units": item["units"], "points": [], "sources": []})
            dst["points"].extend({"value": p["value"], "text": p["text"], "ordered_writes": [
                {"gpr": f"0x{g:02X}", "value24": v} for g, v in p["writes"]]} for p in item["points"])
            dst["sources"].append("V2")
    v3 = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_RECOVERY_V03.json").read_text())
    for item in v3["new_verified_controls"]:
        dst = merged.setdefault((item["slot"], item["parameter_id"]), {"id": item["parameter_id"],
            "display_name": item["display_name"], "display_order": item["display_order"],
            "units": item["units"], "points": [], "sources": []})
        dst["points"].extend({"value": p["value"], "text": p["text"], "ordered_writes": [
            {"gpr": f"0x{g:02X}", "value24": value} for g, value in p["writes"]]} for p in item["points"])
        dst["sources"].append("V3")
    v5 = json.loads((ROOT / "docs/ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05.json").read_text())
    for item in v5["controls"]:
        dst = merged.setdefault((item["slot"], item["parameter_id"]), {"id": item["parameter_id"],
            "display_name": item["display_name"], "display_order": item["editor_order"],
            "units": item.get("units"), "points": [], "sources": []})
        dst["points"].extend({"value": p["value"], "text": p["text"], "ordered_writes": p["ordered_writes"]}
                             for p in item["verified_points"])
        dst["sources"].append("V5")
    for value in merged.values():
        unique = {}
        for point in value["points"]:
            key = (point["value"], tuple((w["gpr"], w["value24"]) for w in point["ordered_writes"]))
            unique[key] = point
        value["points"] = sorted(unique.values(), key=lambda p: (p["value"], p["text"]))
        value["sources"] = sorted(set(value["sources"]))
    return merged


def build_registry() -> dict:
    catalog = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json").read_text())
    inventory = json.loads((ROOT / "docs/ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json").read_text())
    inv_by_slot = {e["slot"]: e for e in inventory["entries"]}
    maps = merge_maps()
    range_evidence = []
    if RANGE_EVIDENCE_PATH.exists():
        range_evidence = json.loads(RANGE_EVIDENCE_PATH.read_text()).get("completed_scans", [])
    effects = []
    for effect in catalog["effects"]:
        slot = effect["slot"]
        observed = inv_by_slot.get(slot, {})
        fields_by_name = {f["label"].upper(): f for f in observed.get("os_observed_fields", [])}
        parameters = []
        for manual in effect["parameters"]:
            field = fields_by_name.get(manual["display_name"].upper())
            observations = [] if field is None else field.get("observations", [])
            values = list(dict.fromkeys(o.get("displayed_value", "") for o in observations))
            mapping = maps.get((slot, manual["id"]))
            if mapping is None:
                mapping = next((m for (s, _), m in maps.items()
                                if s == slot and m["display_name"].upper() == manual["display_name"].upper()), None)
            points = [] if mapping is None else mapping["points"]
            range_text = manual.get("documented_range")
            numeric = numeric_range(range_text)
            is_var = manual["id"] == "effect_variation" or manual["display_name"].upper() == "VAR"
            aliases = {manual["display_name"].upper()}
            comparison = next((x for x in observed.get("manual_comparison", [])
                               if x.get("id") == manual["id"]), None)
            aliases.update(v.upper() for v in (comparison or {}).get("observed_labels", []))
            range_scan = next((x for x in range_evidence if x["slot"] == slot and
                               x["parameter_label"].upper() in aliases), None)
            actual_domain = (range_scan.get("observed_domain") if range_scan and
                             range_scan.get("ui_range_status") == "OS_RANGE_VERIFIED" else None)
            parameters.append({
                "id": manual["id"], "display_name": manual["display_name"],
                "editor_order": manual["display_order"], "units": manual.get("units"),
                "display_type": manual.get("display_type"), "documented_range": range_text,
                "documented_numeric_domain": numeric,
                "observed_os_numeric_domain": actual_domain,
                "documented_step": numeric["step"] if numeric else None,
                "step_confidence": ("OS_RANGE_VERIFIED" if actual_domain else
                                    "manual describes integer display steps; increment sweep not complete" if numeric else "unknown"),
                "discrete_choices": values if is_var else [],
                "os_observed_values_across_factory_variations": values,
                "os_observed_field": field is not None,
                "ui_range_status": ("OS_RANGE_VERIFIED" if actual_domain else "DOCUMENTED_ONLY" if numeric else ("OS_OBSERVED_CHOICES" if is_var and values else "UNKNOWN")),
                "ui_range_confidence": "OS 3.53 full endpoint sweep with exact return to baseline" if actual_domain else "manual-derived; endpoints not swept" if numeric else "no numeric range established",
                "normalized_ui_mapping": ({"kind": "linear_display_normalization", "minimum": (actual_domain or numeric)["minimum"],
                    "maximum": (actual_domain or numeric)["maximum"], "formula": "display = min + round(normalized * (max - min))",
                    "scope": "UI-only coordinate mapping; makes no claim about DSP coefficient scaling"} if numeric else None),
                "dsp_mapping_status": "EXACT_POINTS_ONLY" if points else "UNKNOWN",
                "dsp_mapping_confidence": "repeated OS 3.53 register evidence" if points else "no verified parameter-to-register evidence",
                "supported_values": points,
                "mapping_sources": [] if mapping is None else mapping["sources"],
                "runtime_ready": bool(points),
                "audio_status": "see V5 per-control audio evidence" if "V5" in ([] if mapping is None else mapping["sources"]) else "not independently confirmed for every point",
                "default_value": manual.get("default"),
                "range_scan_evidence": range_scan,
                "evidence": manual.get("evidence")
            })
        effects.append({"slot": slot, "factory_name": effect["factory_name"],
                        "ui_inventory_status": observed.get("status", "deferred"),
                        "parameter_count": len(parameters), "parameters": parameters})
    count = sum(e["parameter_count"] for e in effects)
    mapped = sum(p["runtime_ready"] for e in effects for p in e["parameters"])
    return {"schema": "trollfx-asr10-full-factory-parameter-registry-v1",
            "policy": "No DSP interpolation: only listed verified display points can be scheduled. Numeric UI normalization is display-domain only.",
            "sources": {"manual_catalog": "ASR10_FACTORY_PARAMETER_CATALOG_V1.json",
                        "os_inventory": "ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json",
                        "register_mappings": ["ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json",
                                               "ASR10_FACTORY_PARAMETER_RECOVERY_V03.json",
                                               "ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05.json"]},
            "coverage": {"factory_effects": len(effects), "parameter_entries": count,
                         "register_mapped_controls": mapped, "controls_with_full_value_curve": 0,
                         "note": "The exact point maps are partial; a control is not full-range DSP-ready unless all original values are evidenced."},
            "effects": effects}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json")
    args = parser.parse_args()
    result = build_registry()
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), **result["coverage"]}, indent=2))
