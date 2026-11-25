#!/usr/bin/env python3
"""Recompute route-dependent HALL DECAY register evidence from private trace JSON."""
import argparse
import hashlib
import json
import re
import collections
from pathlib import Path

ORDER = ["0x6e", "0x5b", "0x03", "0x04", "0x05"]


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def helper_registers(raw):
    """Independent implementation of the documented 68000 coefficient arithmetic."""
    d2 = raw << 8
    product = signed16(d2) * signed16(-d2)
    d5 = ((product + 0x3FFFFFFF) & 0xFFFFFFFF)
    if d5 & 0x80000000:
        d5 -= 0x100000000
    g03 = (d2 << 8) & 0xFFFFFF
    return {0x03: g03, 0x04: (-g03) & 0xFFFFFF, 0x05: (d5 >> 7) & 0xFFFFFF}


def last_parameter_group(step):
    writes = step.get("register_writes", [])
    found = []
    for i in range(len(writes) - len(ORDER) + 1):
        group = writes[i:i + len(ORDER)]
        if [w.get("gpr", "").lower() for w in group] == ORDER:
            found.append({int(w["gpr"], 16): int(w["value24"], 16) for w in group})
    return found[-1] if found else None


def last_parameter_records(step):
    writes = step.get("register_writes", [])
    found = []
    for i in range(len(writes) - len(ORDER) + 1):
        group = writes[i:i + len(ORDER)]
        if [w.get("gpr", "").lower() for w in group] == ORDER:
            found.append(group)
    return found[-1] if found else None


def shown_value(text):
    match = re.search(r"=(\d+)\s*$", text)
    return int(match.group(1)) if match else None


def measured_registers(raw):
    """Independent formula inferred from original-OS write groups, not imported."""
    q = max(12, min(76, raw))
    x = q << 8
    g03 = (x << 8) & 0xFFFFFF
    # Signed 16-bit multiply and signed 32-bit accumulation match the observed
    # 68000 operation width; this is evaluated independently of Codex 1's code.
    def s16(v):
        v &= 0xFFFF
        return v - 0x10000 if v & 0x8000 else v
    product = s16(x) * s16(-x)
    acc = (product + 0x3FFFFFFF) & 0xFFFFFFFF
    if acc & 0x80000000:
        acc -= 0x100000000
    tag = min(8, 127 - raw)
    return {0x6E: raw << 16, 0x5B: (tag << 16) | raw,
            0x03: g03, 0x04: (-g03) & 0xFFFFFF,
            0x05: (acc >> 7) & 0xFFFFFF}


def transition_matrix(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_display = collections.defaultdict(set)
    rows = []
    formula_mismatches = []
    for step in payload.get("steps", []):
        records = last_parameter_records(step)
        before = shown_value(step.get("from_display", ""))
        after = shown_value(step.get("to_display", ""))
        if records is None or before is None or after is None:
            continue
        raw = int(records[0]["value24"], 16) >> 16
        observed = {int(w["gpr"], 16): int(w["value24"], 16) for w in records}
        expected = measured_registers(raw)
        mismatch = [f"0x{k:02x}" for k in expected if observed[k] != expected[k]]
        if mismatch:
            formula_mismatches.append({"segment": step.get("segment"), "step": step.get("step"),
                                       "raw": raw, "registers": mismatch})
        direction = step.get("direction") or (
            "up" if step.get("segment") in ("to_max", "restore") else
            "down" if step.get("segment") in ("to_origin", "to_min") else "unknown")
        raw_display[raw].add(after)
        rows.append({
            "segment": step.get("segment"), "step": int(step.get("step", 0)),
            "direction": direction, "display_before": before, "display_after": after,
            "raw_after": raw,
            "ordered_writes": [{"gpr": w["gpr"].lower(),
                                "value24": w["value24"].lower(),
                                "cycles": int(w["cycles"]), "dsp_frame": int(w["frame"])}
                               for w in records],
            "formula_mismatch_registers": mismatch,
        })
    inverse = collections.defaultdict(list)
    for raw, displays in raw_display.items():
        for display in displays:
            inverse[display].append(raw)
    raw_rows = [{"raw_code": raw, "display_value": next(iter(values))}
                for raw, values in sorted(raw_display.items()) if len(values) == 1]
    duplicate_buckets = [{"display_value": d, "raw_codes": sorted(codes)}
                         for d, codes in sorted(inverse.items()) if len(codes) > 1]
    display_by_raw = {row["raw_code"]: row["display_value"] for row in raw_rows}
    for bucket in duplicate_buckets:
        for raw in bucket["raw_codes"]:
            display_by_raw[raw] = bucket["display_value"]
    transition_mismatches = []
    segments = collections.defaultdict(list)
    for row in rows:
        segments[row["segment"]].append(row)
    for segment, segment_rows in segments.items():
        segment_rows.sort(key=lambda r: r["step"])
        first = segment_rows[0]
        direction = 1 if first["direction"] == "up" else -1
        possible_starts = [raw for raw, display in display_by_raw.items()
                           if display == first["display_before"]]
        candidates = []
        for raw in possible_starts:
            adjacent = raw + direction
            if 0 <= adjacent <= 127 and display_by_raw[adjacent] == display_by_raw[raw]:
                adjacent += direction
            if adjacent == first["raw_after"]:
                candidates.append(raw)
        if not candidates:
            transition_mismatches.append({"segment": segment, "step": first["step"],
                                          "reason": "no start raw state yields captured first transition"})
            continue
        current = first["raw_after"]
        checked = [first]
        for row in segment_rows[1:]:
            adjacent = current + direction
            if (0 <= adjacent <= 127 and display_by_raw[adjacent] == display_by_raw[current]):
                adjacent += direction
            if adjacent != row["raw_after"]:
                transition_mismatches.append({"segment": segment, "step": row["step"],
                                              "raw_before": current, "expected_raw": adjacent,
                                              "observed_raw": row["raw_after"]})
            current = row["raw_after"]
            checked.append(row)
    return {
        "schema": "trollfx-asr10-hall-decay-os-transition-matrix-v1",
        "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "transition_count": len(rows), "raw_code_count": len(raw_rows),
        "display_value_count": len(inverse), "duplicate_display_bucket_count": len(duplicate_buckets),
        "raw_to_display": raw_rows, "duplicate_buckets": duplicate_buckets,
        "transitions": rows, "register_formula_mismatch_count": len(formula_mismatches),
        "register_formula_mismatches": formula_mismatches,
        "os_step_transition_mismatch_count": len(transition_mismatches),
        "os_step_transition_mismatches": transition_mismatches,
    }


def summarize(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_direction = {"up": {}, "down": {}}
    for step in payload.get("steps", []):
        target = shown_value(step.get("to_display", ""))
        group = last_parameter_group(step)
        if target is None or group is None:
            continue
        direction = step.get("direction") or (
            "up" if step.get("segment") in ("to_max", "restore") else
            "down" if step.get("segment") in ("to_origin", "to_min") else None)
        if direction in by_direction:
            by_direction[direction][target] = group
    shared = sorted(set(by_direction["up"]) & set(by_direction["down"]) & set(range(1, 99)))
    differing = [v for v in shared if by_direction["up"][v][0x6E] != by_direction["down"][v][0x6E]]
    helper_total = helper_matches = 0
    helper_mismatch_raw_domains = collections.Counter()
    for direction in ("up", "down"):
        for value in shared:
            group = by_direction[direction][value]
            raw = (group[0x6E] >> 16) & 0x7F
            expected = helper_registers(raw)
            helper_total += 1
            matched = all(group[k] == expected[k] for k in (0x03, 0x04, 0x05))
            helper_matches += matched
            if not matched:
                helper_mismatch_raw_domains["raw_below_12" if raw < 12 else "raw_above_76"] += 1
    initial = payload.get("events", [{}])[0]
    log_path = Path(payload["raw_log"]) if payload.get("raw_log") else None
    raw_log_hash = hashlib.sha256(log_path.read_bytes()).hexdigest() if log_path and log_path.exists() else None
    first_line = log_path.open("rb").readline(500).decode("utf-8", errors="replace") if log_path and log_path.exists() else ""
    startup = re.search(r"cycles=(\d+) frame=(\d+)", first_line)
    return {
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "step_count": len(payload.get("steps", [])),
        "shared_interior_display_values": len(shared),
        "gpr6e_direction_difference_count": len(differing),
        "gpr6e_direction_difference_values": differing,
        "first_lcd_event_cycles": initial.get("cycles"),
        "first_lcd_event_frame": initial.get("frame"),
        "full_log_sha256": raw_log_hash,
        "full_log_start_cycles": int(startup.group(1)) if startup else None,
        "full_log_start_frame": int(startup.group(2)) if startup else None,
        "helper_03_04_05_match_count": helper_matches,
        "helper_03_04_05_total_directional_cases": helper_total,
        "unclamped_helper_mismatch_raw_domains": dict(helper_mismatch_raw_domains),
        "register_order": ORDER,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace", type=Path, help="private Codex 1 step-level HALL range JSON")
    ap.add_argument("--compare", type=Path, action="append", default=[],
                    help="additional private summaries to compare boot/start metadata")
    ap.add_argument("--process-id", action="append", default=[],
                    help="caller-recorded emulator CLI PID, ordered primary then --compare traces")
    ap.add_argument("--output", type=Path)
    ap.add_argument("--matrix-output", type=Path,
                    help="write the primary trace's redacted raw/display/GPR transition matrix")
    args = ap.parse_args()
    result = {"schema": "trollfx-asr10-hall-decay-independent-trace-audit-v1",
              "primary": summarize(args.trace),
              "comparisons": [summarize(p) for p in args.compare]}
    primary_matrix = transition_matrix(args.trace)
    result["cross_run_transition_comparisons"] = []
    for other_path in args.compare:
        other_matrix = transition_matrix(other_path)
        fields = ("segment", "step", "direction", "display_before", "display_after",
                  "raw_after", "ordered_writes")
        exact = (primary_matrix["raw_to_display"] == other_matrix["raw_to_display"] and
                 primary_matrix["duplicate_buckets"] == other_matrix["duplicate_buckets"] and
                 len(primary_matrix["transitions"]) == len(other_matrix["transitions"]) and
                 all(all(a[k] == b[k] for k in fields)
                     for a, b in zip(primary_matrix["transitions"], other_matrix["transitions"])))
        result["cross_run_transition_comparisons"].append({
            "other_trace_sha256": other_matrix["trace_sha256"],
            "exact_raw_display_register_order_and_cycle_match": exact,
            "primary_transition_count": primary_matrix["transition_count"],
            "other_transition_count": other_matrix["transition_count"],
        })
    starts = {(r.get("first_lcd_event_cycles"), r.get("first_lcd_event_frame"))
              for r in [result["primary"], *result["comparisons"]]}
    result["independent_boot_evidence"] = (
        "INCONCLUSIVE_NO_UNIQUE_PROCESS_OR_BOOT_ID" if len(starts) <= 1 else
        "DISTINCT_START_COORDINATES_BUT_STILL_REQUIRES_PROCESS_PROVENANCE")
    run_logs = [r.get("full_log_sha256") for r in [result["primary"], *result["comparisons"]]
                if r.get("full_log_sha256")]
    full_startup_logs = all(r.get("full_log_start_cycles", 10**9) < 100000 and
                            r.get("full_log_start_frame", 10**9) < 200 for r in
                            [result["primary"], *result["comparisons"]])
    if len(run_logs) >= 2 and len(set(run_logs)) == len(run_logs) and full_startup_logs:
        result["independent_boot_evidence"] = "REPEATED_ACROSS_DISTINCT_FULL_STARTUP_LOGS_PROCESS_IDS_NOT_RECORDED"
    if args.process_id:
        expected_runs = 1 + len(args.compare)
        if len(args.process_id) != expected_runs:
            ap.error(f"provide exactly {expected_runs} --process-id values, in trace order")
        result["caller_recorded_process_ids"] = args.process_id
        result["independent_boot_evidence"] = (
            "PASS_DISTINCT_PROCESS_IDS_AND_IDENTICAL_FULL_TRANSITION_TRACES"
            if len(set(args.process_id)) == expected_runs and
               result["cross_run_transition_comparisons"] and
               all(c["exact_raw_display_register_order_and_cycle_match"]
                   for c in result["cross_run_transition_comparisons"])
            else "FAIL_OR_INCOMPLETE_PROCESS_PROVENANCE_OR_TRANSITION_MATCH")
    if args.matrix_output:
        args.matrix_output.write_text(json.dumps(primary_matrix, indent=2) + "\n",
                                      encoding="utf-8")
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
