#!/usr/bin/env python3
"""Gate and measure candidate VST2 stereo WAV artifacts against native references.

Input JSON schema is documented in docs/qa-v4/ASR10_VST2_ACCEPTANCE_V1.md.
No gain normalization or correlation-based auto-alignment is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from fractions import Fraction
from pathlib import Path

REQUIRED = ("effect_slot", "effect_name", "variation", "display_value", "raw_code",
            "input_sha256", "processing_rate_hz", "wav_sample_rate_hz", "startup_complete",
            "firmware_events_expected", "firmware_events_applied", "startup_complete_frame",
            "initial_state_sha256", "checkpoint_sha256", "program_sha256", "firmware_schedule_sha256",
            "serial_routing", "parameter_index", "host_parameter_value", "parameter_application_frame",
            "active_registers", "register_trace_sha256", "frame_zero", "known_latency_frames",
            "binary_sha256", "source_commit", "vst_callbacks")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_stereo_wav(path: Path) -> tuple[int, list[tuple[float, float]]]:
    blob = path.read_bytes()
    if blob[:4] != b"RIFF" or blob[8:12] != b"WAVE":
        raise ValueError(f"{path}: expected RIFF/WAVE")
    fmt = data = None
    pos = 12
    while pos + 8 <= len(blob):
        ident = blob[pos:pos + 4]
        size = struct.unpack_from("<I", blob, pos + 4)[0]
        start = pos + 8
        if start + size > len(blob):
            raise ValueError(f"{path}: truncated WAV chunk")
        if ident == b"fmt ": fmt = blob[start:start + size]
        if ident == b"data": data = blob[start:start + size]
        pos = start + size + (size & 1)
    if fmt is None or data is None or len(fmt) < 16:
        raise ValueError(f"{path}: missing fmt/data WAV chunks")
    subtype, channels, rate, _, align_bytes, bits = struct.unpack_from("<HHIIHH", fmt)
    if channels != 2 or subtype not in (1, 3):
        raise ValueError(f"{path}: expected uncompressed stereo PCM or IEEE float WAV")
    if len(data) % align_bytes:
        raise ValueError(f"{path}: malformed data chunk")
    width = bits // 8
    raw = data
    out = []
    if width == 2:
        vals = struct.unpack("<" + "h" * (len(raw) // 2), raw)
        out = [(vals[i] / 32768.0, vals[i + 1] / 32768.0) for i in range(0, len(vals), 2)]
    elif width == 3:
        vals = []
        for i in range(0, len(raw), 3):
            v = int.from_bytes(raw[i:i + 3], "little", signed=False)
            vals.append((v - (1 << 24) if v & (1 << 23) else v) / float(1 << 23))
        out = [(vals[i], vals[i + 1]) for i in range(0, len(vals), 2)]
    elif width == 4:
        if subtype == 3:
            vals = struct.unpack("<" + "f" * (len(raw) // 4), raw)
            out = [(float(vals[i]), float(vals[i + 1])) for i in range(0, len(vals), 2)]
        else:
            vals = struct.unpack("<" + "i" * (len(raw) // 4), raw)
            out = [(vals[i] / float(1 << 31), vals[i + 1] / float(1 << 31)) for i in range(0, len(vals), 2)]
    else:
        raise ValueError(f"{path}: supported PCM widths are 16/24/32-bit and float32")
    if not out or not all(math.isfinite(v) for pair in out for v in pair):
        raise ValueError(f"{path}: empty or non-finite audio")
    return rate, out


def verify_evidence(meta: dict, label: str) -> None:
    missing = [k for k in REQUIRED if k not in meta]
    if missing:
        raise ValueError(f"{label}: missing required evidence: {', '.join(missing)}")
    for key in ("input_sha256", "register_trace_sha256", "binary_sha256"):
        if not isinstance(meta[key], str) or len(meta[key]) != 64:
            raise ValueError(f"{label}: {key} must be a SHA-256 hex digest")
    for key in ("initial_state_sha256", "checkpoint_sha256", "program_sha256", "firmware_schedule_sha256"):
        if not isinstance(meta[key], str) or len(meta[key]) != 64:
            raise ValueError(f"{label}: {key} must be a SHA-256 hex digest")
    if not isinstance(meta["active_registers"], dict) or not meta["active_registers"]:
        raise ValueError(f"{label}: active DSP register snapshot is missing")
    if not isinstance(meta["firmware_events_expected"], int) or meta["firmware_events_expected"] < 1:
        raise ValueError(f"{label}: expected firmware event count is invalid")
    if meta["firmware_events_applied"] != meta["firmware_events_expected"]:
        raise ValueError(f"{label}: startup schedule application count is incomplete")
    if meta["effect_slot"] == 1 and meta["firmware_events_expected"] != 213:
        raise ValueError(f"{label}: HALL package must retain its 213-event startup schedule")
    if not meta["startup_complete"]:
        raise ValueError(f"{label}: startup is not complete")
    if meta["parameter_application_frame"] < meta["startup_complete_frame"]:
        raise ValueError(f"{label}: normal comparison edit precedes startup completion")
    if meta["frame_zero"] not in ("input_frame_0", "declared_latency_aligned"):
        raise ValueError(f"{label}: unsupported/ambiguous frame-zero mapping")
    expected_callbacks = {"open", "set_sample_rate", "set_block_size", "mains_on", "set_parameter", "process_replacing", "get_chunk", "set_chunk", "mains_off", "close"}
    got_callbacks = set(meta["vst_callbacks"])
    if not expected_callbacks.issubset(got_callbacks):
        raise ValueError(f"{label}: missing VST callback evidence: {sorted(expected_callbacks - got_callbacks)}")


def resample(samples: list[tuple[float, float]], src: int, dst: int) -> list[tuple[float, float]]:
    try:
        from scipy.signal import resample_poly
    except ImportError as e:
        raise ValueError("sample-rate mismatch requires scipy for explicit polyphase conversion") from e
    ratio = Fraction(dst, src)
    left = resample_poly([x[0] for x in samples], ratio.numerator, ratio.denominator)
    right = resample_poly([x[1] for x in samples], ratio.numerator, ratio.denominator)
    return list(zip(map(float, left), map(float, right)))


def align(samples: list[tuple[float, float]], latency: int, origin: int) -> list[tuple[float, float]]:
    # Both offsets must be declared by the producing host/test harness. This
    # aligns to input frame zero without estimating a shift from audio content.
    start = max(0, latency + origin)
    return samples[start:]


def summarize(x: list[tuple[float, float]], rate: int) -> dict:
    n = len(x)
    if n == 0:
        raise ValueError("no overlapping aligned samples")
    flat = [v for pair in x for v in pair]
    rms = math.sqrt(sum(v * v for v in flat) / len(flat))
    peak = max(abs(v) for v in flat)
    l = [p[0] for p in x]; r = [p[1] for p in x]
    dot = sum(a * b for a, b in zip(l, r))
    den = math.sqrt(sum(a*a for a in l) * sum(b*b for b in r))
    envelope = []
    hop = max(1, round(0.1 * rate))
    for start in range(0, n, hop):
        block = x[start:start + hop]
        energy = sum(a*a + b*b for a,b in block) / (2 * len(block))
        envelope.append({"start_frame": start, "rms": math.sqrt(energy), "energy": energy})
    return {"frames": n, "stereo_rms": rms, "peak": peak,
            "stereo_correlation_uncentered": dot / den if den else None,
            "tail_envelope_100ms": envelope}


def difference(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> dict:
    n = min(len(a), len(b))
    if n == 0:
        raise ValueError("A/B overlap is empty")
    d = [(a[i][0]-b[i][0], a[i][1]-b[i][1]) for i in range(n)]
    return {"frames": n, "difference_rms": math.sqrt(sum(x*x+y*y for x,y in d)/(2*n)),
            "difference_peak": max(max(abs(x),abs(y)) for x,y in d)}


def load_run(base: Path, row: dict, label: str, permit_rate_conversion: bool) -> tuple[dict, list[tuple[float,float]], int]:
    meta = row["evidence"]
    verify_evidence(meta, label)
    wav = (base / row["wav"]).resolve(strict=True)
    if sha(wav) != row.get("wav_sha256"):
        raise ValueError(f"{label}: WAV hash mismatch")
    rate, samples = read_stereo_wav(wav)
    if rate != meta["wav_sample_rate_hz"]:
        raise ValueError(f"{label}: WAV header rate disagrees with evidence")
    samples = align(samples, int(meta["known_latency_frames"]), int(meta.get("alignment_origin_frames", 0)))
    return meta, samples, rate, False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", type=Path, help="JSON pair manifest")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--allow-rate-conversion", action="store_true")
    args = ap.parse_args()
    bundle = json.loads(args.manifest.read_text())
    if bundle.get("schema") != "asr10-vst2-audio-pair-v1":
        raise SystemExit("unsupported pair manifest schema")
    report = {"schema": "asr10-vst2-audio-comparison-v1", "pairs": []}
    for pair in bundle["pairs"]:
        runs = {}
        for name in ("reference_a", "reference_b", "candidate_a", "candidate_b"):
            runs[name] = load_run(args.manifest.parent, pair[name], pair["pair_id"] + "/" + name, args.allow_rate_conversion)
        rate = runs["reference_a"][2]
        if any(v[2] != rate for v in runs.values()):
            if not args.allow_rate_conversion:
                raise ValueError(f"{pair['pair_id']}: WAV sample rates differ; explicit --allow-rate-conversion required")
            for key, (meta, samples, src_rate, _) in list(runs.items()):
                if src_rate != rate:
                    runs[key] = (meta, resample(samples, src_rate, rate), rate, True)
        for side in ("a", "b"):
            ref = runs[f"reference_{side}"][0]
            can = runs[f"candidate_{side}"][0]
            for key in ("effect_slot", "effect_name", "variation", "display_value", "raw_code", "input_sha256"):
                if ref[key] != can[key]:
                    raise ValueError(f"{pair['pair_id']}/{side}: reference/candidate evidence mismatch for {key}")
            for key in ("checkpoint_sha256", "program_sha256", "firmware_schedule_sha256", "initial_state_sha256", "serial_routing"):
                if ref[key] != can[key]:
                    raise ValueError(f"{pair['pair_id']}/{side}: initialization evidence mismatch for {key}")
            if ref["active_registers"] != can["active_registers"]:
                raise ValueError(f"{pair['pair_id']}/{side}: active DSP register contents differ")
        if runs["reference_a"][0]["raw_code"] == runs["reference_b"][0]["raw_code"]:
            raise ValueError(f"{pair['pair_id']}: A/B raw codes must differ")
        for prefix in ("reference", "candidate"):
            if runs[f"{prefix}_a"][0]["input_sha256"] != runs[f"{prefix}_b"][0]["input_sha256"]:
                raise ValueError(f"{pair['pair_id']}: {prefix} A/B input hashes differ")
        # Do not infer a shift. Candidate and reference frame-zero provenance
        # must declare the alignment method. Truncation is overlap-only.
        ref_a, ref_b = runs["reference_a"][1], runs["reference_b"][1]
        can_a, can_b = runs["candidate_a"][1], runs["candidate_b"][1]
        report["pairs"].append({
            "pair_id": pair["pair_id"], "sample_rate_hz": rate,
            "reference_a": summarize(ref_a, rate), "reference_b": summarize(ref_b, rate),
            "candidate_a": summarize(can_a, rate), "candidate_b": summarize(can_b, rate),
            "reference_a_minus_b": difference(ref_a, ref_b),
            "candidate_a_minus_b": difference(can_a, can_b),
            "candidate_vs_reference_a": difference(can_a, ref_a),
            "candidate_vs_reference_b": difference(can_b, ref_b),
            "parameter_application_frames": {k: runs[k][0]["parameter_application_frame"] for k in runs},
            "firmware_events_applied": {k: runs[k][0]["firmware_events_applied"] for k in runs},
            "active_registers": {k: runs[k][0]["active_registers"] for k in runs},
            "rate_conversion_performed": {k: runs[k][3] for k in runs},
            "wav_sample_rates_hz": {k: runs[k][0]["wav_sample_rate_hz"] for k in runs},
            "processing_rates_hz": {k: runs[k][0]["processing_rate_hz"] for k in runs},
            "processing_clock_match": len({float(runs[k][0]["processing_rate_hz"]) for k in runs}) == 1,
            "alignment": "declared input frame zero; known latency removed; no audio-derived auto-shift; no gain normalization",
        })
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: {len(report['pairs'])} pair(s); wrote {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(2)
