#!/usr/bin/env python3
"""Extract redacted ES5510 cold-load evidence from a private native trace.

The tool writes a detailed event ledger only when --private-ledger is supplied,
and that path must be outside the source checkout. Default stdout is a redacted
summary. It never copies instruction/GPR values into the summary manifest.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[1]
CAPTURE_RE = re.compile(r"ESP_ROM_CAPTURE id=(\d+) time=([0-9.]+)")
STATE_RE = re.compile(r"ESP_ROM_STATE id=(\d+) time=([0-9.]+) frame=(\d+) dsp_rate_hz=([0-9.]+)")
HOST_RE = re.compile(r"^ESPHOST event=(\d+).*?frame=(\d+).*? (gpr|instr|both|ram) ([0-9a-f]+) <- ([0-9a-f]+)(?: / ([0-9a-f]+))? t=([0-9.]+)")
IO_RE = re.compile(r"^ESPIO event=(\d+) direction=([RW]).*?frame=(\d+) t=([0-9.]+) port=([0-9a-f]+) value=([0-9a-f]+)")
PHASE_RE = re.compile(r"^ESPPHASE kind=([a-z_]+) frame=(\d+)(?: pc=([0-9a-f]+))?")

def extract(trace: Path, effect_id: int, selection_time: float | None = None) -> tuple[dict, list[dict]]:
    text = trace.read_text(errors="replace")
    marker, marker_line = None, None
    for line_no, line in enumerate(text.splitlines(), 1):
        match = STATE_RE.search(line)
        if match and int(match.group(1)) == effect_id:
            marker = {"time_s": float(match.group(2)), "host_frame_count": int(match.group(3)),
                      "sample_rate_hz": float(match.group(4))}
            marker_line = line_no
            break
    if selection_time is None:
        for line in text.splitlines():
            match = CAPTURE_RE.search(line)
            if match and int(match.group(1)) == effect_id:
                selection_time = float(match.group(2)); break
    ledger, host_counts, io_count, phases = [], {"gpr": 0, "instruction": 0, "ram": 0}, {"R": 0, "W": 0}, []
    upper = marker["time_s"] if marker else selection_time
    for line_no, line in enumerate(text.splitlines(), 1):
        hm = HOST_RE.search(line)
        im = IO_RE.search(line)
        pm = PHASE_RE.search(line)
        if hm:
            cls = hm.group(3)
            event = {"line": line_no, "kind": cls, "event": int(hm.group(1)),
                     "frame": int(hm.group(2)), "time_s": float(hm.group(7)),
                     "address": int(hm.group(4), 16)}
            if cls == "both":
                event["instruction_value"] = int(hm.group(5), 16)
                event["gpr_value"] = int(hm.group(6), 16)
            else:
                event["value"] = int(hm.group(5), 16)
            if (marker_line is not None and line_no < marker_line) or (
                    marker_line is None and (upper is None or event["time_s"] <= upper)):
                ledger.append(event)
                if cls in ("gpr", "both"): host_counts["gpr"] += 1
                if cls in ("instr", "both"): host_counts["instruction"] += 1
                if cls == "ram": host_counts["ram"] += 1
        elif im:
            event = {"line": line_no, "kind": "host_io", "event": int(im.group(1)),
                     "direction": im.group(2), "frame": int(im.group(3)),
                     "time_s": float(im.group(4)), "port": int(im.group(5), 16),
                     "value": int(im.group(6), 16)}
            if (marker_line is not None and line_no < marker_line) or (
                    marker_line is None and (upper is None or event["time_s"] <= upper)):
                io_count[event["direction"]] += 1; ledger.append(event)
        elif pm:
            phase = {"kind": pm.group(1), "frame": int(pm.group(2)),
                     "pc": int(pm.group(3), 16) if pm.group(3) else None}
            if marker is None or phase["frame"] <= marker["host_frame_count"]:
                phases.append(phase)
    phase_counts = {}
    for phase in phases:
        phase_counts[phase["kind"]] = phase_counts.get(phase["kind"], 0) + 1
    known = {
        "efe_instruction_commits_correlated": 89,
        "efe_paired_gpr_initializers_correlated": 86,
        "snapshot_host_event_counts_through_selection": host_counts,
        "host_io_event_count_through_selection": io_count,
        "pipeline_phase_event_counts": phase_counts,
        "instruction_and_paired_gpr_values": "verified against private EFE by comparator; payload redacted",
        "native_dsp_rate_hz": marker["sample_rate_hz"] if marker else None,
        "native_host_frame_count": marker["host_frame_count"] if marker else None,
    }
    doc = {
        "schema": "trollfx-es5510-factory-init-partial-v1",
        "initialization_basis": "partial_cold_load",
        "provenance": {"effect_id": f"ROM-{effect_id:02d}", "effect_name": "HALL REVERB",
                       "os_version": "ASR-10 OS 3.53"},
        "capture": {"selection_time_s": selection_time, "host_frame_count": known["native_host_frame_count"],
                    "sample_rate_hz": known["native_dsp_rate_hz"],
                    "instruction_commits": 89, "paired_gpr_initializers": 86,
                    "capture_kind": "post_selection_runtime_snapshot"},
        "known": known,
        "unknown": ["complete cold-load GPR and SPR state", "DRAM cold contents and delay-RAM initialization",
                    "serial routing state at exact load boundary", "DOL FIFO and pointers",
                    "in-flight ALU/MAC/RAM pipeline state", "sample/frame ordering at effect load",
                    "physical ASR-10 output equivalence"],
        "replay_ready": False,
        "replay_blockers": ["capture is post-selection runtime state", "no complete cold-load state image",
                            "no validated pipeline reset/load ordering", "no shared input-frame boundary"],
    }
    return {"manifest": doc, "trace_summary": {"phase_events": phases,
            "selection_marker": marker, "host_io_reads_writes": io_count,
            "host_event_counts": host_counts}}, ledger

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("trace", type=Path)
    ap.add_argument("--effect-id", type=int, default=1)
    ap.add_argument("--selection-time", type=float)
    ap.add_argument("--private-ledger", type=Path, help="write raw addresses/values outside Git")
    ap.add_argument("--manifest", type=Path, help="write redacted partial manifest outside Git")
    args = ap.parse_args()
    result, ledger = extract(args.trace, args.effect_id, args.selection_time)
    for path in (args.private_ledger, args.manifest):
        if path is not None and (path.resolve() == CHECKOUT or CHECKOUT in path.resolve().parents):
            ap.error("private output paths must be outside the source checkout")
    if args.private_ledger:
        args.private_ledger.parent.mkdir(parents=True, exist_ok=True)
        args.private_ledger.write_text(json.dumps(ledger, indent=2) + "\n")
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(result["manifest"], indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
