"""Merge directly observed OS-to-GPR points into the public effect catalog."""
import json
import argparse
from pathlib import Path


def apply_verified_mappings(catalog, mapping_path):
    mapping = json.loads(Path(mapping_path).read_text())
    by_slot = {item["slot"]: item["parameters"] for item in mapping["effects"]}
    for effect in catalog["effects"]:
        definitions = by_slot.get(effect["slot"], [])
        if not definitions:
            effect["verified_runtime_parameters"] = []
            effect["verified_runtime_parameter_count"] = 0
            effect["verified_display_point_count"] = 0
            effect["runtime_parameter_status"] = "no direct OS-to-GPR mapping verified"
            continue
        converted = []
        for definition in definitions:
            points = []
            for observed in definition["points"]:
                writes = [{"gpr": f"0x{gpr:02X}", "raw24": raw.upper().replace("0X", "0x")}
                          for gpr, raw in observed["writes"]]
                point = {"display_value": observed["value"], "display_text": observed["text"],
                         "ordered_writes": writes}
                if len(writes) == 1:
                    point["gpr"] = writes[0]["gpr"]
                    point["raw24"] = writes[0]["raw24"]
                points.append(point)
            converted.append({
                "id": definition["id"],
                "display_name": definition["ui_label"],
                "manual_label": definition.get("manual_label", definition["ui_label"]),
                "display_order": definition["live_display_order"],
                "units": definition["units"],
                "display_format": definition["display_format"],
                "verified_display_points": points,
                "factory_default": None,
                "conversion": "Only the listed observed display points are supported; no interpolation or extended values.",
                "trace_evidence": mapping["evidence"] + " Repeated/no-edit baselines used to exclude unrelated recurring GPR writes.",
                "runtime_status": "Functional through FactoryRuntime.setParameter using atomic ordered writes; transient OS write cadence is not emulated.",
            })
        effect["verified_runtime_parameters"] = converted
        effect["verified_runtime_parameter_count"] = len(converted)
        effect["verified_display_point_count"] = sum(len(p["verified_display_points"]) for p in converted)
        effect["runtime_parameter_status"] = f"{len(converted)} controls have direct two-point OS mapping evidence; other controls remain unavailable"
    catalog.setdefault("catalog_evidence", {})["live_register_mappings"] = mapping["evidence"]
    catalog["catalog_evidence"]["curve_policy"] = mapping["curve_policy"]
    catalog["verified_control_count"] = sum(len(v) for v in by_slot.values())
    catalog["verified_display_point_count"] = sum(len(p["points"]) for values in by_slot.values() for p in values)
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--mapping", type=Path, default=Path(__file__).resolve().parents[2] / "docs/ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text())
    args.catalog.write_text(json.dumps(apply_verified_mappings(catalog, args.mapping), indent=2) + "\n")
