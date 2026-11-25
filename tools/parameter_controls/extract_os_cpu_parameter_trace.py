#!/usr/bin/env python3
"""Extract bounded OS CPU/ES5510 write evidence from a private monitor log.

The input may contain proprietary emulator telemetry. Write the JSON output to
private storage; this tool intentionally emits parsed rows rather than copying
the raw log into the repository.
"""
import argparse
import json
import re
from pathlib import Path

CALL = re.compile(r"^ESPCALL cycles=(\d+) frame=(\d+) pc=([0-9a-f]+) sp=([0-9a-f]+) gpr=([0-9a-f]{2}) regs=([0-9a-f:]+)(.*)$", re.I)
HOST = re.compile(r"^ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-f]+)(?: caller=([0-9a-f]+))? gpr ([0-9a-f]{2}) <- ([0-9a-f]{6})", re.I)
LCD = re.compile(r'^PANELLCD cycles=(\d+) frame=(\d+) lcd="(.{22})" underline="(.{22})" cursor="(.{22})"')
TRACE_BEGIN = re.compile(r'^ESPTRACE_BEGIN cycles=(\d+) frame=(\d+) gpr=([0-9a-f]{2}) value_before=([0-9a-f]{6}) a6=([0-9a-f]+)', re.I)
TRACE_INSN = re.compile(r'^ESPINS cycles=(\d+) pc=([0-9a-f]+) d=([0-9a-f:]+) a=([0-9a-f:]+)', re.I)
TRACE_MEM = re.compile(r'^ESPMEM cycles=(\d+) pc=([0-9a-f]+) address=([0-9a-f]+) size=(\d+) before=([0-9a-f]+) after=([0-9a-f]+)', re.I)
TRACE_END = re.compile(r'^ESPTRACE_END cycles=(\d+) instruction_count=(\d+) memory_write_count=(\d+)', re.I)


def parse_log(text):
    calls = []
    writes = []
    displays = []
    parameter_windows = []
    active_window = None
    for line in text.splitlines():
        if m := TRACE_BEGIN.match(line):
            active_window = {"cycles": int(m[1]), "frame": int(m[2]), "gpr": int(m[3], 16),
                             "value_before": "0x" + m[4], "a6": "0x" + m[5],
                             "instructions": [], "memory_writes": []}
            parameter_windows.append(active_window)
        elif m := TRACE_INSN.match(line):
            if active_window is not None:
                active_window["instructions"].append({
                    "cycles": int(m[1]), "pc": "0x" + m[2],
                    "data_registers": ["0x" + x for x in m[3].split(":")],
                    "address_registers": ["0x" + x for x in m[4].split(":")],
                })
        elif m := TRACE_MEM.match(line):
            if active_window is not None:
                active_window["memory_writes"].append({
                    "cycles": int(m[1]), "pc": "0x" + m[2], "address": "0x" + m[3],
                    "size": int(m[4]), "before": "0x" + m[5], "after": "0x" + m[6],
                })
        elif m := TRACE_END.match(line):
            if active_window is not None:
                active_window["trace_window_end_cycles"] = int(m[1])
                active_window["reported_instruction_count"] = int(m[2])
                active_window["reported_memory_write_count"] = int(m[3])
                active_window = None
        elif m := CALL.match(line):
            regs = [int(x, 16) for x in m[6].split(":")]
            a2mem = re.search(r"\ba2mem=([0-9a-f:]+)", m[7], re.I)
            a6mem = re.search(r"\ba6mem=([0-9a-f:]+)", m[7], re.I)
            calls.append({
                "cycles": int(m[1]), "frame": int(m[2]), "cpu_pc": "0x" + m[3],
                "stack_pointer": "0x" + m[4], "gpr": int(m[5], 16),
                "a2": regs[10], "a3": regs[11], "a6": regs[14],
                "a2_memory_window_hex": None if not a2mem else a2mem[1].replace(":", ""),
                "a6_memory_window_hex": None if not a6mem else a6mem[1].replace(":", ""),
            })
        elif m := HOST.match(line):
            writes.append({"event": int(m[1]), "cycles": int(m[2]), "frame": int(m[3]),
                           "writer_pc": "0x" + m[4],
                           "caller_pc": None if not m[5] else "0x" + m[5],
                           "gpr": int(m[6], 16), "value": "0x" + m[7]})
        elif m := LCD.match(line):
            displays.append({"cycles": int(m[1]), "frame": int(m[2]), "lcd": m[3],
                             "underline": m[4], "cursor": m[5]})

    # The CPU instrumentation executes immediately before the host transfer.
    # Pair only equal GPRs in a narrow cycle window; do not infer unmatched rows.
    for write in writes:
        matches = [c for c in calls if c["gpr"] == write["gpr"] and
                   0 <= write["cycles"] - c["cycles"] <= 10000]
        if matches:
            call = min(matches, key=lambda c: write["cycles"] - c["cycles"])
            write["cpu_trace"] = call
        else:
            write["cpu_trace"] = None
    # The latest preceding live LCD snapshot is useful context but can lag an
    # editor value update by a display-refresh cycle. Keep chronology explicit.
    for window in parameter_windows:
        before = [x for x in displays if x["cycles"] <= window["cycles"]]
        after = [x for x in displays if window["cycles"] < x["cycles"] <= window["cycles"] + 100000]
        window["lcd_snapshot_before"] = before[-1] if before else None
        window["lcd_snapshot_after"] = after[0] if after else None
    return {"schema": "asr10-os-cpu-parameter-trace-v1",
            "summary": {"lcd_events": len(displays), "host_gpr_writes": len(writes),
                        "cpu_snapshots": len(calls),
                        "writes_with_cpu_snapshot": sum(w["cpu_trace"] is not None for w in writes),
                        "parameter_cpu_windows": len(parameter_windows),
                        "parameter_cpu_instructions": sum(len(x["instructions"]) for x in parameter_windows),
                        "parameter_memory_writes": sum(len(x["memory_writes"]) for x in parameter_windows)},
            "lcd_events": displays, "writes": writes,
            "parameter_cpu_windows": parameter_windows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, type=Path, help="private emulator log")
    ap.add_argument("--output", required=True, type=Path, help="private JSON output path")
    args = ap.parse_args()
    result = parse_log(args.input.read_text(errors="replace"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
