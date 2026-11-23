"""Read-only adapters for the hall-boundary, factory audio, and divergence artifacts.

Adapters copy observations and metadata only. They never load or alter emulator state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical_to_replay(trace: dict, *, input_sha256: str, initial_state_sha256: str,
                        firmware_events_sha256: str, alignment: str,
                        dsp_rate_hz: float = 29761.89453125, host_rate_hz: int = 44100) -> dict:
    """Adapt divergence-schema serial input/output events to the replay contract."""
    samples = {}
    for e in trace.get("events", []):
        if e.get("event_type") not in ("serial_input", "serial_output"):
            continue
        index = e.get("sample_index", e.get("frame"))
        if not isinstance(index, int) or index < 0:
            raise ValueError("serial events need a nonnegative sample_index or frame")
        item = samples.setdefault(index, {"index": index})
        channel = str(e.get("channel", "")).lower()
        side = "left" if channel in ("0", "left", "l") else "right" if channel in ("1", "right", "r") else None
        if side is None:
            raise ValueError(f"unsupported serial channel: {channel}")
        field = "input_" + side if e["event_type"] == "serial_input" else side
        item[field] = int(e["value"])
    output = []
    for i in sorted(samples):
        s = samples[i]
        if "left" in s and "right" in s:
            output.append({"index": i, "left": s["left"], "right": s["right"]})
    if output and [s["index"] for s in output] != list(range(len(output))):
        raise ValueError("serial output event indices must be contiguous from zero")
    meta = {"input_sha256": input_sha256, "initial_state_sha256": initial_state_sha256,
            "firmware_events_sha256": firmware_events_sha256, "alignment": alignment}
    return {"schema": "trollfx-es5510-hall-replay-v1", "replay": meta,
            "dsp_rate_hz": dsp_rate_hz, "host_rate_hz": host_rate_hz,
            "dsp_serial_samples": output,
            "adapter": {"source_schema": trace.get("schema"), "source_trace_id": trace.get("trace_id"),
                        "sample_values_included": True}}


def hall_load_fingerprint(report: dict) -> str:
    """Fingerprint ordered lifecycle + transaction identity from hall-boundary summary."""
    rows = []
    for tx in report.get("transactions", []):
        rows.append({"run_frame": tx.get("run_frame"), "upload": tx.get("upload"),
                     "instruction_state_sha256": tx.get("instruction_state_sha256"),
                     "gpr_state_sha256": tx.get("gpr_state_sha256"),
                     "lifecycle": tx.get("lifecycle")})
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def audio_lab_summary(summary: dict) -> dict:
    """Read-only adapter for factory-audio-lab summary; labels diagnostic coverage."""
    cases = {}
    for stimulus, variants in summary.get("summaries", {}).items():
        for algorithm, metrics in variants.items():
            cases[f"{stimulus}/{algorithm}"] = {
                "frames": metrics.get("frames"),
                "bit_exact": metrics.get("bit_exact"),
                "first_divergent_frame": metrics.get("first_divergent_frame"),
                "max_abs_deviation": metrics.get("max_abs_deviation"),
                "rms_deviation": metrics.get("rms_deviation"),
                "best_alignment_lag_frames": metrics.get("best_alignment_lag_frames")}
    return {"source": "factory-audio-lab-summary", "sample_rate_hz": summary.get("sample_rate_hz"),
            "frames_per_stimulus": summary.get("frames_per_stimulus"),
            "comparison": summary.get("comparison"), "cases": cases,
            "factory_hall_evidence": False}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())
