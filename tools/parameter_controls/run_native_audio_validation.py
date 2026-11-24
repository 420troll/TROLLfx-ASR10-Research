#!/usr/bin/env python3
"""Render paired native-runtime WAVs for every verified V2 control point."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audit", type=Path, required=True, help="trusted private production-provider audit")
    ap.add_argument("--mappings", type=Path, default=ROOT / "docs/ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json")
    ap.add_argument("--output", type=Path, required=True, help="private output directory outside Git")
    ap.add_argument("--binary", type=Path, required=True)
    args = ap.parse_args()
    audit = json.loads(args.audit.resolve(strict=True).read_text())
    packages = {x["slot"]: x for x in audit["slots"]}
    mappings = json.loads(args.mappings.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    binary = args.binary.resolve()
    subprocess.run(["c++", "-std=c++17", "-O2", "-I" + str(ROOT / "include"), "-I" + str(ROOT / "src"),
                    str(ROOT / "tools/audio_validation/factory_parameter_audio_compare.cpp"),
                    str(ROOT / "src/es5510_factory_runtime.cpp"), str(ROOT / "src/es5510.cpp"),
                    "-o", str(binary)], cwd=ROOT, check=True)
    results = []
    for effect in mappings["effects"]:
        row = packages.get(effect["slot"])
        if not row or not row.get("registry_eligible") or not row.get("capture_state_valid"):
            raise SystemExit(f"slot {effect['slot']} is not registry eligible in the trusted audit")
        d = row["descriptor"]
        if not row.get("checkpoint_is_at_run_boundary"):
            raise SystemExit(f"slot {effect['slot']} checkpoint is not at the RUN boundary")
        checkpoint = Path(d["run_checkpoint_path"]).resolve(strict=True)
        schedule = Path(d["firmware_event_schedule_path"]).resolve(strict=True)
        if sha256(checkpoint) != d["run_checkpoint_sha256"]:
            raise SystemExit(f"slot {effect['slot']} checkpoint hash mismatch")
        if sha256(schedule) != d["firmware_event_schedule_sha256"]:
            raise SystemExit(f"slot {effect['slot']} firmware schedule hash mismatch")
        for parameter in effect["parameters"]:
            a, b = parameter["points"]
            prefix = args.output / f"slot-{effect['slot']:02d}-{parameter['id']}"
            command = [str(binary), str(effect["slot"]), d["factory_name"], str(d["active_program_words"]),
                       d["program_sha256"], str(checkpoint), d["run_checkpoint_sha256"],
                       str(d["factory_reference_rate_hz"]), str(schedule), parameter["id"],
                       str(a["value"]), str(b["value"]), str(prefix)]
            result = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
            line = result.stdout.strip()
            print(line)
            results.append({"slot": effect["slot"], "factory_name": d["factory_name"],
                            "parameter_id": parameter["id"], "point_a": a["text"], "point_b": b["text"],
                            "render_prefix": str(prefix), "result": line})
    result_path = args.output / "native-audio-validation.json"
    result_path.write_text(json.dumps({"schema": "trollfx-asr10-parameter-audio-validation-v1",
                                       "engine": "native ES5510, experimental 48 kHz", "results": results}, indent=2) + "\n")
    print(f"validated_controls={len(results)} report={result_path}")


if __name__ == "__main__":
    main()
