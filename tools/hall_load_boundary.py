#!/usr/bin/env python3
"""Summarize private OpenASR traces without exporting factory payload bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECT_RE = re.compile(r"ESP_ROM_SELECT id=(\d+) time=([0-9.]+) cycles=(\d+) frame=(\d+) dsp_rate_hz=([0-9.]+) otto_clock_hz=([0-9.]+) active_voices=(\d+) host_output_rate_hz=([0-9.]+) display=(.*)$")
PHASE_RE = re.compile(r"ESPPHASE kind=([a-z0-9_]+)\s+(.*)$")
FRAME_RE = re.compile(r"ESPPFRAME kind=(input|output) index=(\d+) frame=(\d+) cycles=(\d+) host_pc=([0-9a-fA-F]+) serial=([0-9a-fA-F]+) lanes=([0-9a-fA-F,]+)")
HOST_RE = re.compile(r"ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-fA-F]+) (gpr|instr|both|ram) ([0-9a-fA-F]+) <- ([0-9a-fA-F]+)(?: / ([0-9a-fA-F]+))?")


def fields(text: str) -> dict[str, str]:
    return dict(re.findall(r"([a-z_]+)=([^\s]+)", text))


def summarize(path: Path) -> dict:
    lines = path.read_text(errors="replace").splitlines()
    selections: list[dict] = []
    phases: list[dict] = []
    frames: list[dict] = []
    host: list[dict] = []
    for line_number, line in enumerate(lines, 1):
        m = SELECT_RE.search(line)
        if m:
            selections.append({"log_sequence": line_number, "id": int(m.group(1)), "time_s": float(m.group(2)),
                               "cpu_cycles": int(m.group(3)), "esp_frame": int(m.group(4)),
                               "esp_rate_hz": float(m.group(5)), "otto_clock_hz": float(m.group(6)),
                               "active_voices": int(m.group(7)), "host_output_rate_hz": float(m.group(8)),
                               "display": m.group(9).strip()})
        m = PHASE_RE.search(line)
        if m:
            phases.append({"log_sequence": line_number, "kind": m.group(1), **fields(m.group(2))})
        m = FRAME_RE.search(line)
        if m:
            lane_data = bytes.fromhex(m.group(7).replace(",", ""))
            frames.append({"log_sequence": line_number, "kind": m.group(1), "index": int(m.group(2)), "frame": int(m.group(3)), "cycles": int(m.group(4)),
                           "host_serial": int(m.group(6), 16), "lane_count": len(lane_data) // 2,
                           "serial_lane_state_sha256": hashlib.sha256(lane_data).hexdigest()})
        m = HOST_RE.search(line)
        if m:
            item = {"log_sequence": line_number, "event": int(m.group(1)), "cycles": int(m.group(2)), "frame": int(m.group(3)),
                    "kind": m.group(5), "address": int(m.group(6), 16),
                    "value": int(m.group(7), 16), "second_value": int(m.group(8), 16) if m.group(8) else None}
            host.append(item)

    transactions = []
    for run in (p for p in phases if p["kind"] == "run_start"):
        run_frame = int(run["frame"])
        run_cycle = int(run["cycles"])
        starts = [p for p in phases if p["kind"] == "instruction_upload_start" and
                  int(p["cycles"]) <= run_cycle and int(p["frame"]) <= run_frame]
        upload_start = starts[-1] if starts else None
        halts = [p for p in phases if p["kind"] == "halt" and
                 int(p.get("cycles", -1)) <= run_cycle and int(p.get("frame", -1)) <= run_frame]
        halt = halts[-1] if halts else None
        transaction_start = halt or upload_start
        summaries = [p for p in phases if p["kind"] == "program_upload_summary" and
                     int(p["frame"]) == run_frame]
        summary = summaries[-1] if summaries else None
        if transaction_start:
            start_cycle = int(transaction_start["cycles"])
            events = [e for e in host if start_cycle <= e["cycles"] <= run_cycle]
        else:
            events = []
        instr_records = []
        gpr_records = []
        for e in events:
            if e["kind"] in ("instr", "both"):
                instr_records.append(f"{e['address']:02x}:{e['value']:012x}")
            if e["kind"] in ("gpr", "both"):
                gpr_records.append(f"{e['address']:02x}:{e['value']:06x}" if e["kind"] == "gpr"
                                   else f"{e['address']:02x}:{e['second_value']:06x}")
        near_frames = [f for f in frames if run_frame <= f["frame"] < run_frame + 4096]
        prev_sel = [s for s in selections if s["cpu_cycles"] <= run_cycle]
        run_pos = phases.index(run)
        start_pos = phases.index(halt) if halt else phases.index(upload_start) if upload_start else run_pos
        prior_halts = [i for i, p in enumerate(phases[:start_pos + 1])
                       if p["kind"] == "pa4_halt_assert"]
        if not prior_halts:
            prior_halts = [i for i, p in enumerate(phases[:start_pos + 1]) if p["kind"] == "halt"]
        lower = prior_halts[-1] if prior_halts else max(0, start_pos - 8)
        lifecycle = [{k: v for k, v in p.items() if k != "word"} for p in phases[lower:run_pos + 2]
                     if p["kind"] in ("pa4_halt_assert", "halt", "host_halt_pipeline_reset", "host_dram_clear",
                                       "host_dram_clear_ignored", "instruction_upload_start", "program_upload_summary",
                                       "pa4_run_release", "serial_config", "run_start", "first_instruction")]
        tx = {"run_frame": run_frame, "run_cpu_cycles": run_cycle,
              "transaction_halt_frame": int(halt["frame"]) if halt else None,
              "transaction_halt_cpu_cycles": int(halt["cycles"]) if halt else None,
              "instruction_upload_start_frame": int(upload_start["frame"]) if upload_start else None,
              "instruction_upload_start_cpu_cycles": int(upload_start["cycles"]) if upload_start else None,
              "selection": prev_sel[-1] if prev_sel else None,
              "upload": {k: int(summary[k]) for k in
                         ("commits", "unique_addresses", "first_end", "gpr_commits") if summary and k in summary},
              "host_records_in_window": len(events),
              "instruction_records": len(instr_records), "gpr_records": len(gpr_records),
              "instruction_state_sha256": hashlib.sha256("\n".join(instr_records).encode()).hexdigest(),
              "gpr_state_sha256": hashlib.sha256("\n".join(gpr_records).encode()).hexdigest(),
              "lifecycle": lifecycle,
              "serial_frame_checkpoints": near_frames}
        transactions.append(tx)

    return {"schema": "trollfx-asr10-hall-load-boundary-redacted-v1",
            "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "selection_count": len(selections), "selections": selections,
            "transaction_count": len(transactions), "transactions": transactions,
            "phase_event_counts": {kind: sum(p["kind"] == kind for p in phases)
                                   for kind in sorted({p["kind"] for p in phases})},
            "raw_payloads_included": False}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("trace", type=Path)
    ap.add_argument("--output", type=Path, help="redacted report; must be outside Git checkout")
    args = ap.parse_args()
    report = summarize(args.trace)
    if args.output:
        out = args.output.expanduser().resolve()
        if out == ROOT or ROOT in out.parents:
            ap.error("reports must be written outside the repository")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
