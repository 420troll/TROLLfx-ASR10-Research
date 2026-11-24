#!/usr/bin/env python3
"""Produce a redacted clipping summary from the native playback harness report."""
import argparse
import json
import struct
import wave
from pathlib import Path

THRESHOLD = 32767.0 / 32768.0

def pcm_reference(path: Path) -> dict:
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
            raise ValueError(f"reference is not uncompressed PCM16: {path.name}")
        raw = wav.readframes(wav.getnframes())
        samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
        return {"rate_hz": wav.getframerate(), "channels": wav.getnchannels(),
                "frames": wav.getnframes(), "peak_pcm16": max(map(abs, samples), default=0),
                "near_full_scale_samples": sum(abs(x) >= 32767 for x in samples),
                "full_scale_samples": sum(abs(x) == 32767 or abs(x) == 32768 for x in samples)}

def summarize(report: dict, collection_root: Path | None = None) -> dict:
    effects = []
    for effect in sorted(report["effects"], key=lambda x: x["slot"]):
        stimuli = []
        for item in effect["stimuli"]:
            over = int(item.get("float_overrange_samples", 0))
            clamped = int(item.get("wav_clamped_samples", over))
            if over != clamped:
                raise ValueError("WAV clamp count does not agree with pre-conversion float overrange")
            stimuli.append({"kind": item["kind"], "frames": int(item["frames"]),
                "peak_float": float(item["peak"]), "finite_samples": int(item["finite_samples"]),
                "near_full_scale_pcm16_threshold_samples": int(item.get("near_full_scale_pcm16_threshold_samples", 0)),
                "float_overrange_samples": over, "wav_clamped_samples": clamped})
        effects.append({"slot": int(effect["slot"]), "name": effect["name"], "stimuli": stimuli})
    totals = {key: sum(s[key] for e in effects for s in e["stimuli"])
              for key in ("near_full_scale_pcm16_threshold_samples", "float_overrange_samples", "wav_clamped_samples")}
    result = {"schema": "trollfx-audio-quality-clipping-summary-v1", "host_rate_hz": report["host_rate_hz"],
        "threshold_definition": f"abs(float_output) >= {THRESHOLD:.12f}; this is near-full-scale, not itself clipping",
        "float_overrange_definition": "abs(float_output) > 1.0 before PCM16 WAV conversion",
        "wav_clamped_definition": "number of float samples clipped to [-1,+1] by the WAV converter",
        "effects": effects, "totals": totals}
    if collection_root:
        refs = {}
        for slot in (31, 37):
            matches = list((collection_root / "packages").glob(f"ROM-{slot:02d}-*/selector-audio.wav"))
            if len(matches) != 1:
                raise ValueError(f"expected one emulator reference WAV for slot {slot}")
            refs[str(slot)] = pcm_reference(matches[0])
        result["original_os_emulator_selector_audio"] = refs
        result["reference_comparison_note"] = "These captured selector WAVs use their capture-session audio; they are not matched to the generated harness stimuli."
    return result

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", type=Path, help="native-audio-results.json from the playback harness")
    ap.add_argument("output", type=Path)
    ap.add_argument("--collection-root", type=Path, help="private imported package collection for emulator selector WAV stats")
    args = ap.parse_args()
    doc = json.loads(args.report.read_text())
    summary = summarize(doc, args.collection_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "effects": len(summary["effects"]), "totals": summary["totals"]}, indent=2))

if __name__ == "__main__":
    main()
