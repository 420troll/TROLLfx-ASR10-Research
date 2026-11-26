"""Path-free importer and analyzer for explicit HALL audio comparison artifacts.

The importer never opens factory packages or invokes a DSP runtime. Its input is
an exported comparison bundle containing two rendered PCM WAVs and evidence
metadata from a runner that already performed the renders.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import re
import struct
import wave

SCHEMA = "trollfx-asr10-hall-audio-artifacts-v1"
SOURCES = {"standalone_experimental_runtime", "actual_vst_audio", "original_os_reference", "ui_fixture"}
PROVENANCE = {"validated_factory_checkpoint", "user_reference", "not_established", "synthetic_fixture"}
DSP_STATES = {"applied", "partial", "no_write", "unknown"}
RUNTIME_STATES = {"ready", "initialized", "not_ready", "unknown"}
FIRMWARE_STATES = {"initialized", "not_initialized", "unknown"}
STIMULI = {"impulse", "sine_sweep", "noise", "sustained_tones", "user_wav", "other"}
MAX_WAV_BYTES = 32 * 1024 * 1024
MAX_FRAMES = 2_000_000


def _integer(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{label} must be an integer from {low} to {high}")
    return value


def _decode_wav(encoded):
    if not isinstance(encoded, str) or len(encoded) > (MAX_WAV_BYTES * 4 // 3 + 16):
        raise ValueError("WAV payload is missing or too large")
    try:
        raw = base64.b64decode(encoded, validate=True)
        with wave.open(io.BytesIO(raw), "rb") as wf:
            channels, rate, frames = wf.getnchannels(), wf.getframerate(), wf.getnframes()
            width, comp = wf.getsampwidth(), wf.getcomptype()
            data = wf.readframes(frames)
    except Exception as exc:
        raise ValueError(f"invalid PCM WAV: {exc}") from exc
    if len(raw) > MAX_WAV_BYTES or channels != 2 or comp != "NONE" or width not in (2, 3, 4):
        raise ValueError("WAV must be uncompressed stereo 16-, 24- or 32-bit PCM")
    if rate < 8000 or rate > 192000 or frames < 1 or frames > MAX_FRAMES:
        raise ValueError("WAV sample rate or duration is outside supported bounds")
    samples = []
    if width == 2:
        samples = [v[0] / 32768.0 for v in struct.iter_unpack("<h", data)]
    elif width == 3:
        for i in range(0, len(data), 3):
            v = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16)
            if v & 0x800000:
                v -= 1 << 24
            samples.append(v / 8388608.0)
    else:
        samples = [v[0] / 2147483648.0 for v in struct.iter_unpack("<i", data)]
    if len(samples) != frames * 2 or not all(math.isfinite(x) for x in samples):
        raise ValueError("WAV sample data is incomplete or non-finite")
    return raw, rate, frames, samples


def _wav_bytes(samples, rate):
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        data = bytearray()
        for x in samples:
            x = max(-1.0, min(32767 / 32768.0, x if math.isfinite(x) else 0.0))
            q = round(x * 32768)
            data.extend(struct.pack("<h", max(-32768, min(32767, q))))
        wf.writeframes(data)
    return out.getvalue()


def _metrics(samples):
    left, right = samples[0::2], samples[1::2]
    def channel(xs):
        return {"rms": math.sqrt(sum(x * x for x in xs) / max(1, len(xs))),
                "peak": max((abs(x) for x in xs), default=0.0)}
    return {"left": channel(left), "right": channel(right), "stereo": channel(samples)}


def _waveform(samples, limit=640):
    frames = len(samples) // 2
    bins = min(limit, frames)
    result = {"left": [], "right": []}
    for b in range(bins):
        start, end = b * frames // bins, max(b * frames // bins + 1, (b + 1) * frames // bins)
        for ch, key in ((0, "left"), (1, "right")):
            values = samples[start * 2 + ch:end * 2:2]
            result[key].append([min(values), max(values)])
    return result


def _envelope(samples, rate, window_ms=20):
    window = max(1, round(rate * window_ms / 1000))
    frames = len(samples) // 2
    points = []
    for start in range(0, frames, window):
        end = min(frames, start + window)
        chunk = samples[start * 2:end * 2]
        points.append([start / rate, math.sqrt(sum(x * x for x in chunk) / max(1, len(chunk)))])
    return points


def _safe_render(render, label):
    allowed = {"display_value", "raw_code", "raw_code_basis", "wav_base64", "dsp_status", "runtime_status", "firmware_status",
               "processing_rate_hz", "package_provenance", "provenance_id", "source_commit", "register_updates"}
    if not isinstance(render, dict) or set(render) - allowed:
        raise ValueError(f"{label} render has unsupported metadata fields")
    display = _integer(render.get("display_value"), f"{label} display value", 0, 99)
    raw = render.get("raw_code")
    if raw is not None:
        raw = _integer(raw, f"{label} raw code", 0, 127)
    basis = render.get("raw_code_basis", "not_reported")
    if basis not in {"runtime_state", "original_os_observation", "not_reported"}:
        raise ValueError(f"{label} raw-code basis is invalid")
    if raw is None and basis != "not_reported":
        raise ValueError(f"{label} raw-code basis claims evidence but raw code is absent")
    if raw is not None and basis == "not_reported":
        raise ValueError(f"{label} raw code requires an evidence basis")
    status = render.get("dsp_status", "unknown")
    if status not in DSP_STATES:
        raise ValueError(f"{label} DSP status is invalid")
    runtime_status = render.get("runtime_status", "unknown")
    if runtime_status not in RUNTIME_STATES:
        raise ValueError(f"{label} runtime status is invalid")
    firmware_status = render.get("firmware_status", "unknown")
    if firmware_status not in FIRMWARE_STATES:
        raise ValueError(f"{label} firmware initialization status is invalid")
    rate = render.get("processing_rate_hz")
    if rate is not None and (isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 8000 <= rate <= 192000):
        raise ValueError(f"{label} processing rate is invalid")
    provenance = render.get("package_provenance", "not_established")
    if provenance not in PROVENANCE:
        raise ValueError(f"{label} package provenance is invalid")
    provenance_id = render.get("provenance_id")
    if provenance_id is not None and (not isinstance(provenance_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", provenance_id)):
        raise ValueError(f"{label} provenance id must be a path-free identifier")
    source_commit = render.get("source_commit")
    if source_commit is not None and (not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-fA-F]{7,40}", source_commit)):
        raise ValueError(f"{label} source commit must be a Git commit id")
    writes = render.get("register_updates", [])
    if not isinstance(writes, list) or len(writes) > 256:
        raise ValueError(f"{label} register update list is invalid")
    safe_writes = []
    for row in writes:
        if not isinstance(row, dict) or set(row) != {"frame", "register"}:
            raise ValueError("register update accepts only frame/register; omit values and paths")
        frame = _integer(row["frame"], "register update frame", 0, MAX_FRAMES)
        register = row["register"]
        if not isinstance(register, str) or not re.fullmatch(r"0x[0-9a-fA-F]{1,2}", register):
            raise ValueError("register update must identify a GPR address such as 0x6E")
        safe_writes.append({"frame": frame, "register": register.upper()})
    raw_wav, sample_rate, frames, samples = _decode_wav(render.get("wav_base64"))
    return {"display_value": display, "raw_code": raw, "raw_code_basis": basis,
            "dsp_status": status, "runtime_status": runtime_status, "firmware_status": firmware_status,
            "processing_rate_hz": rate, "package_provenance": provenance,
            "provenance_id": provenance_id, "source_commit": source_commit,
            "register_updates": sorted(safe_writes, key=lambda x: x["frame"]),
            "sample_rate_hz": sample_rate, "frames": frames, "duration_seconds": frames / sample_rate,
            "wav_sha256": hashlib.sha256(raw_wav).hexdigest(), "wav_base64": base64.b64encode(raw_wav).decode(),
            "metrics": _metrics(samples), "waveform": _waveform(samples),
            "envelope": _envelope(samples, sample_rate), "_samples": samples}


def analyze_bundle(bundle):
    if not isinstance(bundle, dict) or set(bundle) != {"schema", "source", "effect_slot", "effect_name", "variation", "cases"}:
        raise ValueError("bundle fields must match the documented path-free schema")
    if bundle["schema"] != SCHEMA:
        raise ValueError(f"unsupported audio artifact schema; expected {SCHEMA}")
    source = bundle["source"]
    if source not in SOURCES:
        raise ValueError("audio source must identify standalone runtime, actual VST, original OS, or UI fixture")
    if bundle["effect_slot"] != 1 or bundle["effect_name"] != "HALL REVERB":
        raise ValueError("AUDIO LAB accepts HALL REVERB (factory slot 1) only")
    variation = bundle["variation"]
    if variation is not None:
        variation = _integer(variation, "variation", 1, 4)
    cases = bundle["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
        raise ValueError("bundle must contain 1 to 32 comparison cases")
    clean_cases = []
    seen = set()
    for row in cases:
        if not isinstance(row, dict) or set(row) != {"case_id", "stimulus", "a", "b"}:
            raise ValueError("each case must contain only case_id, stimulus, a and b")
        ident = row["case_id"]
        if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", ident) or ident in seen:
            raise ValueError("case_id must be unique and contain only letters, digits, _ or -")
        seen.add(ident)
        stimulus = row["stimulus"]
        if stimulus not in STIMULI:
            raise ValueError("unknown test stimulus")
        a, b = _safe_render(row["a"], "A"), _safe_render(row["b"], "B")
        if a["sample_rate_hz"] != b["sample_rate_hz"] or a["frames"] != b["frames"]:
            raise ValueError("A and B WAVs must have identical sample rate and frame count")
        rate = a["sample_rate_hz"]
        diff = [x - y for x, y in zip(a["_samples"], b["_samples"])]
        delta = _metrics(diff)["stereo"]
        diff_wav = _wav_bytes(diff, rate)
        clean_cases.append({"case_id": ident, "stimulus": stimulus, "a": {k: v for k, v in a.items() if k != "_samples"},
            "b": {k: v for k, v in b.items() if k != "_samples"}, "difference": {
                "rms": delta["rms"], "peak": delta["peak"], "wav_base64": base64.b64encode(diff_wav).decode(),
                "waveform": _waveform(diff)}})
    safe_report = {"schema": "trollfx-asr10-hall-audio-measurement-v1", "source": source,
        "effect_slot": 1, "effect_name": "HALL REVERB", "variation": variation,
        "cases": [{"case_id": c["case_id"], "display_values": [c["a"]["display_value"], c["b"]["display_value"]],
            "stimulus": c["stimulus"],
            "raw_codes": [c["a"]["raw_code"], c["b"]["raw_code"]],
            "raw_code_bases": [c["a"]["raw_code_basis"], c["b"]["raw_code_basis"]],
            "sample_rate_hz": c["a"]["sample_rate_hz"], "frames": c["a"]["frames"],
            "duration_seconds": c["a"]["duration_seconds"],
            "processing_rates_hz": [c["a"]["processing_rate_hz"], c["b"]["processing_rate_hz"]],
            "package_provenance": [c["a"]["package_provenance"], c["b"]["package_provenance"]],
            "provenance_ids": [c["a"]["provenance_id"], c["b"]["provenance_id"]],
            "source_commits": [c["a"]["source_commit"], c["b"]["source_commit"]],
            "dsp_status": [c["a"]["dsp_status"], c["b"]["dsp_status"]],
            "runtime_status": [c["a"]["runtime_status"], c["b"]["runtime_status"]],
            "firmware_status": [c["a"]["firmware_status"], c["b"]["firmware_status"]],
            "wav_sha256": [c["a"]["wav_sha256"], c["b"]["wav_sha256"]],
            "register_update_count": [len(c["a"]["register_updates"]), len(c["b"]["register_updates"])],
            "register_updates": [c["a"]["register_updates"], c["b"]["register_updates"]],
            "rms": [c["a"]["metrics"]["stereo"]["rms"], c["b"]["metrics"]["stereo"]["rms"]],
            "peak": [c["a"]["metrics"]["stereo"]["peak"], c["b"]["metrics"]["stereo"]["peak"]],
            "difference_rms": c["difference"]["rms"], "difference_peak": c["difference"]["peak"]}
            for c in clean_cases]}
    return {"schema": SCHEMA, "source": source, "effect_slot": 1, "effect_name": "HALL REVERB",
        "variation": variation, "cases": clean_cases, "measurement_report": safe_report}
