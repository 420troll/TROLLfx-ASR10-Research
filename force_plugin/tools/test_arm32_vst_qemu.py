#!/usr/bin/env python3
"""Exercise a packaged ARMv7 VST binary under QEMU with trusted factory assets."""
from __future__ import annotations
import argparse, hashlib, json, math, os, random, struct, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def run(args, *, env=None):
    p = subprocess.run([str(x) for x in args], text=True, capture_output=True, env=env)
    if p.returncode:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(map(str,args))}\n{p.stdout}\n{p.stderr}")
    return p.stdout.strip()

def make_stimulus(path: Path, frames=8192, seed=0x5510A551):
    rng = random.Random(seed)
    with path.open("wb") as f:
        for i in range(frames):
            nl, nr = rng.uniform(-0.015, 0.015), rng.uniform(-0.015, 0.015)
            left = 0.18 * math.sin(2 * math.pi * 330 * i / 48000) + nl
            right = 0.17 * math.sin(2 * math.pi * 277 * i / 48000 + 0.31) + nr
            f.write(struct.pack("<ff", left, right))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm32-plugin", type=Path, required=True)
    ap.add_argument("--collection", type=Path, required=True)
    ap.add_argument("--sdk", type=Path, required=True)
    ap.add_argument("--qemu-arm", type=Path, required=True)
    ap.add_argument("--sysroot", type=Path, default=Path("/usr/arm-linux-gnueabihf"))
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--zig-python", default=sys.executable)
    ap.add_argument("--zig-pythonpath", default=os.environ.get("PYTHONPATH", ""))
    a = ap.parse_args()
    plugin = a.arm32_plugin.resolve(strict=True)
    collection = a.collection.resolve(strict=True)
    sdk = a.sdk.resolve(strict=True)
    qemu = a.qemu_arm.resolve(strict=True)
    sysroot = a.sysroot.resolve(strict=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="trollfx-arm32-qemu-") as tmp:
        work = Path(tmp); assets = work / "FactoryAssets"; renders = work / "renders"
        renders.mkdir(); stimulus = work / "input-stimulus.f32"
        prep = json.loads(run([sys.executable, ROOT / "force_plugin/tools/prepare_force_assets.py", collection, assets]))
        make_stimulus(stimulus)
        harness = work / "vst-binary-test"
        env = os.environ.copy()
        if a.zig_pythonpath:
            env["PYTHONPATH"] = a.zig_pythonpath
        env["TROLLFX_ARM_QEMU_NO_STATIC_EXIT"] = "1"
        run([a.zig_python, "-m", "ziglang", "c++", "-target", "arm-linux-gnueabihf.2.31",
             "-mcpu=cortex_a17", "-std=c++17", "-O2", "-DTROLLFX_ARM_QEMU_NO_STATIC_EXIT",
             "-I", sdk / "framework", "-rdynamic", ROOT / "tests/force_vst_binary_audio_test.cpp",
             "-ldl", "-pthread", "-o", harness], env=env)
        output = run([qemu, "-cpu", "max", "-L", sysroot, harness, plugin, assets, stimulus, renders])
        lines = output.splitlines()
        slot_lines = [line for line in lines if line.startswith("SLOT ")]
        if len(slot_lines) != 50 or not any(line.startswith("BINARY_PASS ") for line in lines):
            raise RuntimeError("ARMv7 VST binary did not pass all 50-slot assertions")
        slots = []; output_hash = hashlib.sha256()
        for line in slot_lines:
            fields = line.split(); slot = int(fields[1]); values = {}
            for item in fields[3:]:
                key, value = item.split("=", 1)
                values[key] = float(value) if key in ("rms_l", "rms_r", "peak") else int(value)
            render = renders / f"slot-{slot:02}.f32"
            raw = render.read_bytes()
            for (sample,) in struct.iter_unpack("<f", raw):
                if not math.isfinite(sample):
                    raise RuntimeError(f"non-finite ARMv7 output at slot {slot}")
            output_hash.update(bytes((slot,))); output_hash.update(raw)
            slots.append({"slot": slot, "frames": values["frames"], "rms_left": values["rms_l"],
                "rms_right": values["rms_r"], "peak": values["peak"],
                "switch_completion_frames": values["transition_frames"], "finite_stereo": True})
        qemu_version = run([qemu, "--version"]).splitlines()[0]
        report = {"schema": "trollfx-arm32-vst-qemu-validation-v1", "status": "PASS",
            "target": "ARMv7 hard-float VST2", "execution_environment": "QEMU user-mode emulation; not Force hardware validation",
            "qemu_version": qemu_version, "cpu_model": "max", "sysroot": str(sysroot),
            "plugin_sha256": sha(plugin), "input_sha256": sha(stimulus),
            "trusted_package_index_sha256": sha(assets / "provider-index.tsv"),
            "output_renders_sha256": output_hash.hexdigest(), "accepted_packages": prep["eligible_slots"],
            "processed_slots": len(slots), "frames_per_slot": 8192, "callback_allocations": 0,
            "binary_assertions": ["VSTPluginMain entry", "stereo finite output", "all 50 validated packages",
                "19 verified parameter points", "Hall/Room effect-dependent EDIT routing", "dynamic formatted labels",
                "effect-specific state isolation", "effect switching", "wet/dry and gain", "bypass", "host chunk state roundtrip"],
            "aggregate_result": "BINARY_PASS", "slots": slots}
    a.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "slots": len(report["slots"]), "plugin_sha256": report["plugin_sha256"],
        "report": str(a.report)}, indent=2))

if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"test_arm32_vst_qemu: ERROR: {exc}", file=sys.stderr); raise SystemExit(2)
