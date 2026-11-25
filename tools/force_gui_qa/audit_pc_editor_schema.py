#!/usr/bin/env python3
"""Independent schema checks for the published full-parameter PC editor."""
import argparse
import json
from pathlib import Path


EXPECTED = {
    14: ("DECAY TIME", "0.20 to 100.0 sec."),
    15: ("DECAY TIME", "0.20 to 150.0 sec."),
    16: ("DECAY TIME", "0.70 to 250.0 sec."),
    17: ("DECAY TIME", "0.2 to 100.0 sec."),
    18: ("DECAY TIME", "0.4 to 140.0 sec."),
}
EXTRA_EXPECTED = {
    18: ("PREDELAY TIME", "0 to 430 ms"),
}


def audit(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    findings = []
    if len(data.get("effects", [])) != 50:
        findings.append("expected 50 numbered ROM effects")
    seen = set()
    for effect in data.get("effects", []):
        slot = effect["slot"]
        for parameter in effect.get("parameters", []):
            identity = (slot, parameter["id"])
            if identity in seen:
                findings.append(f"duplicate identity {identity}")
            seen.add(identity)
        if slot in EXPECTED:
            expected_name, expected_range = EXPECTED[slot]
            matches = [p for p in effect["parameters"]
                       if p.get("manual", {}).get("display_name", "").startswith(expected_name)]
            if len(matches) != 1:
                findings.append(f"ROM-{slot:02d}: expected one {expected_name}, found {len(matches)}")
            elif matches[0]["manual"].get("documented_range") != expected_range:
                findings.append(
                    f"ROM-{slot:02d} {expected_name}: schema range "
                    f"{matches[0]['manual'].get('documented_range')!r}; manual range {expected_range!r}")
        if slot in EXTRA_EXPECTED:
            expected_name, expected_range = EXTRA_EXPECTED[slot]
            matches = [p for p in effect["parameters"]
                       if p.get("manual", {}).get("display_name", "").startswith(expected_name)]
            if len(matches) != 1:
                findings.append(f"ROM-{slot:02d}: expected one {expected_name}, found {len(matches)}")
            elif matches[0]["manual"].get("documented_range") != expected_range:
                findings.append(
                    f"ROM-{slot:02d} {expected_name}: schema range "
                    f"{matches[0]['manual'].get('documented_range')!r}; manual range {expected_range!r}")
    return {
        "schema": "trollfx-asr10-pc-editor-independent-schema-audit-v1",
        "effect_count": len(data.get("effects", [])),
        "catalog_descriptor_count": sum(len(e.get("parameters", [])) for e in data.get("effects", [])),
        "editor_control_claim": data.get("coverage", {}).get("editable_controls_including_manual_subparameters"),
        "unique_effect_parameter_identities": len(seen),
        "findings": findings,
        "result": "FAIL" if findings else "PASS",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("schema", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.schema)
    serialized = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    raise SystemExit(1 if result["result"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
