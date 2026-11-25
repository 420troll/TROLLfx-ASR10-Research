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


def parse_log(text):
    calls = []
    writes = []
    displays = []
    for line in text.splitlines():
        if m := CALL.match(line):
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
    return {"schema": "asr10-os-cpu-parameter-trace-v1",
            "summary": {"lcd_events": len(displays), "host_gpr_writes": len(writes),
                        "cpu_snapshots": len(calls),
                        "writes_with_cpu_snapshot": sum(w["cpu_trace"] is not None for w in writes)},
            "lcd_events": displays, "writes": writes}


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
