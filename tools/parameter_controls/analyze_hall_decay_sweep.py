#!/usr/bin/env python3
"""Validate private OS 3.53 HALL decay sweep evidence without exporting it.

The input sweep JSON contains proprietary emulator observations. The output is
an aggregate report only; select a private output path when preserving it.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hall_decay_coefficient_model import coefficient_registers

DUPLICATE_CODES = (2, 6, 11, 16, 20, 25, 29, 34, 38, 43, 47, 52, 57, 61,
                   66, 70, 75, 80, 84, 89, 93, 98, 102, 107, 111, 116, 121, 125)


def display(raw):
    return raw - sum(code <= raw for code in DUPLICATE_CODES)


def parse_value(text):
    match = re.search(r"DECAY TIME=(\d+)", text or "")
    return None if not match else int(match.group(1))


def analyze(document):
    paths = {"ascending": {}, "descending": {}}
    coefficient_mismatches = []
    for step in document.get("steps", []):
        if not step.get("complete") or not step.get("register_snapshot_after"):
            continue
        value = parse_value(step.get("to_display"))
        if value is None or not 0 <= value <= 99:
            continue
        direction = step.get("direction")
        if direction not in ("up", "down"):
            direction = "up" if step.get("segment") in ("to_max", "restore") else "down"
        direction = "ascending" if direction == "up" else "descending"
        value_hex = step["register_snapshot_after"].get("0x6e")
        if value_hex is not None:
            raw = int(value_hex, 16) >> 16
            paths[direction][value] = raw
            expected = coefficient_registers(raw)
            snapshot = step["register_snapshot_after"]
            for gpr, expected_value in expected.items():
                actual = snapshot.get(f"0x{gpr:02x}")
                if actual is None or int(actual, 16) != expected_value:
                    coefficient_mismatches.append({"direction": direction,
                        "display_value": value, "raw": raw, "gpr": f"0x{gpr:02x}",
                        "actual": actual, "expected": f"0x{expected_value:06x}"})

    missing = {name: sorted(set(range(100)) - set(points)) for name, points in paths.items()}
    mismatches = []
    for value in range(100):
        up, down = paths["ascending"].get(value), paths["descending"].get(value)
        if up is not None and down is not None and up != down:
            mismatches.append({"display_value": value, "ascending_raw": up, "descending_raw": down})
    invalid = []
    for name, points in paths.items():
        for value, raw in points.items():
            if raw > 127 or display(raw) != value:
                invalid.append({"path": name, "display_value": value, "raw": raw})
    expected_values = [value for value in range(100)
                       if any(display(code) == value and display(code - 1) == value
                              for code in DUPLICATE_CODES)]
    observed_values = [row["display_value"] for row in mismatches]
    mismatch_shapes_valid = all(row["descending_raw"] - row["ascending_raw"] == 1
                                for row in mismatches)
    observed_union = set(paths["ascending"]) | set(paths["descending"])
    return {
        "schema": "asr10-hall-decay-sweep-validation-v1",
        "effect": "ROM-01 HALL REVERB",
        "variation": document.get("variation"),
        "sweep_complete_flag": document.get("sweep_complete", False),
        "ascending_values_observed": len(paths["ascending"]),
        "descending_values_observed": len(paths["descending"]),
        "missing_ascending_values": missing["ascending"],
        "missing_descending_values": missing["descending"],
        "invalid_raw_to_display_pairs": invalid,
        "direction_mismatch_count": len(mismatches),
        "direction_mismatch_values": observed_values,
        "direction_mismatches_are_one_code": mismatch_shapes_valid,
        "matches_os_lookup_duplicate_buckets": observed_values == expected_values,
        "coefficient_formula_mismatch_count": len(coefficient_mismatches),
        "coefficient_formula_mismatches": coefficient_mismatches[:20],
        "all_values_observed": observed_union == set(range(100)),
        "interior_values_observed_in_both_directions": all(
            value in paths["ascending"] and value in paths["descending"] for value in range(1, 99)),
        "endpoints_observed_at_least_once": 0 in observed_union and 99 in observed_union,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="private sweep JSON")
    parser.add_argument("--output", type=Path, help="optional aggregate JSON destination")
    args = parser.parse_args()
    result = analyze(json.loads(args.input.read_text()))
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
