#!/usr/bin/env python3
"""Compare two private OS 3.53 HALL decay sweeps; emit aggregate results only."""
import argparse
import hashlib
import json
from pathlib import Path

from audit_hall_decay_raw_domain import (
    derived_registers, derived_registers_unbounded, lcd_value,
    parameter_group_records, parse_os_table, read_sweep,
)


def run_summary(path, table_path, pid_path):
    document, directions, order_failures = read_sweep(path)
    table = parse_os_table(table_path)
    buckets = {}
    for raw, display in enumerate(table):
        buckets.setdefault(display, []).append(raw)
    checks = {"transition_cases": 0, "clamped_coefficients_match": 0,
              "unclamped_coefficients_match": 0, "gpr5b_full_formula_match": 0,
              "gpr6e_raw_match": 0}
    for direction in ("up", "down"):
        for display, group in directions[direction].items():
            raw = (group[0x6E] >> 16) & 0x7F
            checks["gpr6e_raw_match"] += group[0x6E] == raw << 16
            checks["gpr5b_full_formula_match"] += group[0x5B] == ((min(8, 127-raw) << 16) | raw)
            if 1 <= display <= 98:
                checks["transition_cases"] += 1
                expected = derived_registers(raw)
                checks["clamped_coefficients_match"] += all(group[r] == expected[r] for r in (3,4,5))
                old = derived_registers_unbounded(raw)
                checks["unclamped_coefficients_match"] += all(group[r] == old[r] for r in (3,4,5))
    pids = [s.strip() for s in pid_path.read_text().splitlines() if s.strip()]
    return {
        "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "cli_pid": pids[0] if pids else None,
        "sweep_complete": bool(document.get("sweep_complete")),
        "display_values_seen": len(set(directions["up"]) | set(directions["down"])),
        "directional_snapshot_counts": {name: len(directions[name]) for name in ("up", "down")},
        "write_order_failures": order_failures,
        "checks": checks,
    }, directions, buckets


def ordered_event_groups(path):
    import json
    document = json.loads(path.read_text(encoding="utf-8"))
    groups = {"up": {}, "down": {}}
    for step in document.get("steps", []):
        if not step.get("complete"):
            continue
        display = lcd_value(step.get("to_display", ""))
        direction = step.get("direction")
        if display is None or direction not in groups:
            continue
        records = parameter_group_records(step)
        if records is None:
            continue
        groups[direction][display] = [
            (record["gpr"].lower(), int(record["value24"], 16),
             int(record["cycles"]), int(record["frame"]))
            for record in records
        ]
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep-a", type=Path, required=True)
    parser.add_argument("--pid-a", type=Path, required=True)
    parser.add_argument("--sweep-b", type=Path, required=True)
    parser.add_argument("--pid-b", type=Path, required=True)
    parser.add_argument("--table-dump", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    a, directions_a, buckets_a = run_summary(args.sweep_a, args.table_dump, args.pid_a)
    b, directions_b, buckets_b = run_summary(args.sweep_b, args.table_dump, args.pid_b)
    events_a = ordered_event_groups(args.sweep_a)
    events_b = ordered_event_groups(args.sweep_b)
    payload_a = json.loads(args.sweep_a.read_text(encoding="utf-8"))
    payload_b = json.loads(args.sweep_b.read_text(encoding="utf-8"))
    same = {}
    for direction in ("up", "down"):
        shared = sorted(set(directions_a[direction]) & set(directions_b[direction]))
        differing = [display for display in shared
                     if directions_a[direction][display] != directions_b[direction][display]]
        event_differing = [display for display in shared
                           if events_a[direction].get(display) != events_b[direction].get(display)]
        same[direction] = {"shared_display_count": len(shared),
                           "identical_full_register_groups": len(shared)-len(differing),
                           "different_displays": differing,
                           "identical_ordered_value_cycle_frame_groups": len(shared)-len(event_differing),
                           "event_timing_different_displays": event_differing}

    route_differences = [display for display in range(1, 99)
                         if display in directions_a["up"] and display in directions_a["down"]
                         and directions_a["up"][display][0x6E] != directions_a["down"][display][0x6E]]
    old_mismatch_raw = []
    old_match_count = 0
    for direction in ("up", "down"):
        for display in range(1, 99):
            group = directions_a[direction].get(display)
            if group is None:
                continue
            raw = (group[0x6E] >> 16) & 0x7F
            expected = derived_registers_unbounded(raw)
            if not all(group[r] == expected[r] for r in (3,4,5)):
                old_mismatch_raw.append(raw)
            else:
                old_match_count += 1

    duplicate_pairs = [{"display": display, "raw_codes": codes}
                       for display, codes in sorted(buckets_a.items()) if len(codes) == 2]
    route_mismatches = []
    for display, raw_codes in buckets_a.items():
        for direction, expected_raw in (("up", raw_codes[0]), ("down", raw_codes[-1])):
            group = directions_a[direction].get(display)
            if group is None:
                continue
            observed_raw = (group[0x6E] >> 16) & 0x7F
            if observed_raw != expected_raw:
                route_mismatches.append({"display": display, "direction": direction,
                                         "expected_raw": expected_raw, "observed_raw": observed_raw})
    result = {
        "schema": "trollfx-hall-decay-independent-qa-v1",
        "evidence_basis": "original OS 3.53 emulator sweeps and independently parsed OS table",
        "runs": [a, b],
        "cross_run": {"full_write_groups_equal": all(
                          not same[d]["different_displays"] and not same[d]["event_timing_different_displays"]
                          for d in same),
                      "full_event_arrays_equal": payload_a.get("events") == payload_b.get("events"),
                      "full_step_arrays_equal": payload_a.get("steps") == payload_b.get("steps"),
                      "by_direction": same,
                      "table_decode_equal": buckets_a == buckets_b},
        "independent_boot_evidence": {
            "distinct_cli_pids": bool(a["cli_pid"] and b["cli_pid"] and a["cli_pid"] != b["cli_pid"]),
            "run_a_cli_pid": a["cli_pid"], "run_b_cli_pid": b["cli_pid"],
            "both_complete": a["sweep_complete"] and b["sweep_complete"],
        },
        "raw_display": {"raw_codes": 128, "display_values": len(buckets_a),
                        "duplicate_bucket_count": len(duplicate_pairs),
                        "all_observed_routes_match_os_table": not route_mismatches,
                        "route_mismatch_count": len(route_mismatches),
                        "duplicate_pairs": duplicate_pairs,
                        "direction_dependent_interior_displays": route_differences},
        "old_102_196_reconciliation": {
            "interior_cases": len(old_mismatch_raw) + old_match_count,
            "unclamped_helper_matches": old_match_count,
            "unclamped_helper_mismatches": len(old_mismatch_raw),
            "mismatch_raw_codes_outside_12_76": sum(r < 12 or r > 76 for r in old_mismatch_raw),
            "mismatch_raw_below_12": sum(r < 12 for r in old_mismatch_raw),
            "mismatch_raw_above_76": sum(r > 76 for r in old_mismatch_raw),
            "mismatch_raw_codes_inside_12_76": sum(12 <= r <= 76 for r in old_mismatch_raw),
            "all_clamped_formula_cases_match": all(
                run["checks"]["clamped_coefficients_match"] == 196 for run in (a, b)),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cross_run": result["cross_run"],
                      "raw_display": {k: v for k,v in result["raw_display"].items()
                                      if k != "duplicate_pairs"},
                      "old_102_196_reconciliation": result["old_102_196_reconciliation"]}, indent=2))


if __name__ == "__main__":
    main()
