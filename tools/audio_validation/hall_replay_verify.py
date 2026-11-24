#!/usr/bin/env python3
"""Independent, read-only HALL replay comparison for redacted private traces.

Input JSON contains replay metadata and ordered DSP serial samples. Host WAVs are
compared separately: host frame n maps to DSP frame floor(n * dsp_rate / host_rate).
No resampling, phase search, or automatic alignment is performed.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import wave
from pathlib import Path

DSP_RATE = 29761.89453125
HOST_RATE = 44100
WINDOWS = (256, 4096, 32768)
FIELDS = ("input_sha256", "initial_state_sha256", "firmware_events_sha256", "alignment")


def host_frame_to_dsp_frame(host_frame: int) -> int:
    if host_frame < 0:
        raise ValueError("host frame must be nonnegative")
    return math.floor(host_frame * DSP_RATE / HOST_RATE)


def load_trace(path: Path) -> dict:
    trace = json.loads(path.read_text())
    if trace.get("schema") != "trollfx-es5510-hall-replay-v1":
        raise ValueError(f"{path}: unsupported replay trace schema")
    for key in FIELDS:
        if not trace.get("replay", {}).get(key):
            raise ValueError(f"{path}: replay.{key} is required")
    if not math.isclose(float(trace.get("dsp_rate_hz", 0)), DSP_RATE, abs_tol=1e-8):
        raise ValueError(f"{path}: expected observed HALL DSP rate {DSP_RATE} Hz")
    if int(trace.get("host_rate_hz", 0)) != HOST_RATE:
        raise ValueError(f"{path}: expected 44100 Hz host rate")
    samples = trace.get("dsp_serial_samples")
    if not isinstance(samples, list):
        raise ValueError(f"{path}: dsp_serial_samples must be an ordered list")
    for i, s in enumerate(samples):
        if s.get("index") != i or not isinstance(s.get("left"), int) or not isinstance(s.get("right"), int):
            raise ValueError(f"{path}: DSP samples must have contiguous indices and integer stereo values")
    return trace


def compare_samples(a: list[dict], b: list[dict], limit: int | None = None) -> dict:
    n = min(len(a), len(b), limit if limit is not None else max(len(a), len(b)))
    first = None
    max_abs = 0
    sum_sq = 0
    mismatches = 0
    for i in range(n):
        diffs = (a[i]["left"] - b[i]["left"], a[i]["right"] - b[i]["right"])
        if diffs != (0, 0):
            mismatches += 1
            if first is None:
                first = {"index": i, "left": a[i], "right": b[i], "delta": list(diffs)}
        max_abs = max(max_abs, *(abs(d) for d in diffs))
        sum_sq += sum(d * d for d in diffs)
    complete = len(a) >= n and len(b) >= n
    return {"compared_frames": n, "left_available": len(a), "right_available": len(b),
            "lengths_equal": len(a) == len(b) if limit is None else None,
            "samples_equal": complete and first is None and len(a) == len(b) if limit is None else complete and first is None,
            "mismatching_frames": mismatches, "first_difference": first,
            "max_absolute_difference": max_abs,
            "rms_difference": math.sqrt(sum_sq / (2*n)) if n else None}


def load_wav(path: Path) -> tuple[int, list[dict]]:
    with wave.open(str(path), "rb") as w:
        channels, width, rate, count = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if channels != 2 or width not in (2, 3, 4):
            raise ValueError(f"{path}: expected stereo PCM16/24/32 WAV")
        raw = w.readframes(count)
    if width == 2:
        vals = struct.unpack("<" + "h" * (len(raw)//2), raw)
    elif width == 4:
        vals = struct.unpack("<" + "i" * (len(raw)//4), raw)
    else:
        vals = []
        for i in range(0, len(raw), 3):
            v = int.from_bytes(raw[i:i+3], "little", signed=False)
            vals.append(v - (1 << 24) if v & (1 << 23) else v)
    return rate, [{"left": vals[i], "right": vals[i+1]} for i in range(0, len(vals), 2)]


def compare_wavs(a: Path, b: Path) -> dict:
    ar, aa = load_wav(a); br, bb = load_wav(b)
    if ar != HOST_RATE or br != HOST_RATE:
        raise ValueError("host-output comparison requires both WAVs at 44100 Hz")
    return compare_samples(aa, bb)


def verify(left_path: Path, right_path: Path, left_wav: Path | None = None, right_wav: Path | None = None) -> dict:
    a, b = load_trace(left_path), load_trace(right_path)
    gates = {key: {"left": a["replay"][key], "right": b["replay"][key],
                   "equal": a["replay"][key] == b["replay"][key]} for key in FIELDS}
    eligible = all(x["equal"] for x in gates.values())
    result = {"schema": "trollfx-es5510-hall-replay-report-v1", "replay_eligible": eligible,
              "gates": gates, "comparison_suppressed": not eligible,
              "clock_domains": {"dsp_rate_hz": DSP_RATE, "host_rate_hz": HOST_RATE,
                  "host_to_dsp_frame": "floor(host_frame * 29761.89453125 / 44100); domains are reported separately"},
              "factory_windows": {str(n): compare_samples(a["dsp_serial_samples"], b["dsp_serial_samples"], n)
                                   if eligible and len(a["dsp_serial_samples"]) >= n and len(b["dsp_serial_samples"]) >= n
                                   else {"status": "not_run", "reason": "identical replay gates and adequate private reference samples required"}
                                   for n in WINDOWS}}
    if left_wav and right_wav:
        result["host_wav"] = compare_wavs(left_wav, right_wav) if eligible else {"status": "not_run", "reason": "replay gates differ"}
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("left", type=Path); p.add_argument("right", type=Path)
    p.add_argument("--left-wav", type=Path); p.add_argument("--right-wav", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if bool(args.left_wav) != bool(args.right_wav):
        p.error("--left-wav and --right-wav must be supplied together")
    result = verify(args.left, args.right, args.left_wav, args.right_wav)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
