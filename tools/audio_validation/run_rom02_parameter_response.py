#!/usr/bin/env python3
"""Validate private ROM-02 evidence, then run the repeatable parameter response matrix."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def run(args):
    p = subprocess.run([str(x) for x in args], cwd=ROOT, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError("command failed: " + " ".join(map(str, args)) + "\n" + p.stdout + p.stderr)
    return p

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--reference-root", type=Path, required=True)
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True, help="redacted JSON output outside the checkout")
    args = ap.parse_args()
    output = args.output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("quality results must remain outside the Git checkout")
    validation = run([sys.executable, ROOT / "tools/audio_validation/validate_factory_runtime_package.py",
        "--effect", "rom02", "--manifest", args.manifest.resolve(strict=True),
        "--checkpoint", args.checkpoint.resolve(strict=True), "--reference-root", args.reference_root.resolve(strict=True),
        "--events", args.events.resolve(strict=True)])
    receipt = json.loads(validation.stdout)
    if receipt.get("valid") is not True or receipt.get("two_boot_checkpoint_match") is not True:
        raise ValueError("strict ROM-02 two-boot validator did not accept the package")
    with tempfile.TemporaryDirectory(prefix="trollfx-rom02-quality-") as td:
        binary = Path(td) / "rom02_parameter_response"
        run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
             "-I", ROOT / "include", "-I", ROOT / "src", ROOT / "tests/audio_quality/rom02_parameter_response.cpp",
             ROOT / "src/es5510.cpp", ROOT / "src/es5510_factory_runtime.cpp", "-o", binary])
        result = run([binary, args.checkpoint.resolve(strict=True), args.events.resolve(strict=True),
                      str(receipt["run_frame"])])
    report = json.loads(result.stdout)
    report["validated_reference"] = {k: receipt[k] for k in ("active_program_words", "run_frame", "processing_rate_hz",
        "factory_reference_rate_hz", "serial_route", "two_boot_checkpoint_match")}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "comparisons": len(report["comparisons"]),
        "rom02_validation": "PASS", "BUS1_nonzero": sum(x["different_samples"] > 0 for x in report["comparisons"] if x["control"] == "BUS1"),
        "BUS2_nonzero": sum(x["different_samples"] > 0 for x in report["comparisons"] if x["control"] == "BUS2")}, indent=2))

if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"run_rom02_parameter_response: {exc}", file=sys.stderr)
        raise SystemExit(2)
