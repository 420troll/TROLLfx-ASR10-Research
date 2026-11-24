#!/usr/bin/env python3
"""Capture two fresh OS 3.53 effect RUN references for a replay profile.

OS ROMs, disk image, snapshots, logs, WAVs, serial samples, and maps stay in the
private output directory. Selector values are traversed in ascending order,
because a direct value from a fresh boot is not reliable evidence of effect
identity.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
import capture_asr10_rom_effects as capture
from factory_replay_profiles import PROFILES
from replay_factory_from_boundary import event_fingerprint, read_run


def run_boot(cli: Path, roms: Path, disk: Path, root: Path, boot: str,
             profile_name: str, frame: int) -> dict:
    profile = PROFILES[profile_name]
    directory = root / f"boot-{boot}"
    directory.mkdir(parents=False, exist_ok=False)
    (directory / "snapshots").mkdir()
    args = ["--panel-log", "--trace-esp-io", "--wav", str(directory / "render.wav"),
            "--button", "15:7:1", "--button", "15.2:7:0"]
    t = 16.0
    for raw in range(8, int(profile["selector_raw_last"]) + 1):
        args += ["--analog-at", f"{t:.3f}:5:{raw}"]
        t += 0.15
    env = capture.emulator_env()
    count = 32768
    env.update({"ESP_PIPELOG": "1", "ESP_HOSTLOG": "1", "ESP_FRAMELOG": str(count),
                "ESP_FRAMELOG_START_FRAME": str(frame), "ESP_RUN_SNAPSHOT_FRAME": str(frame),
                "ESP_RUN_SNAPSHOT_DIR": str(directory / "snapshots"),
                "ASR_HOST_PCM_TRACE": str(directory / "host-output-map.csv"),
                "ASR_HOST_PCM_START_FRAME": str(frame), "ASR_HOST_PCM_FRAMES": str(count)})
    capture.run(cli, roms, disk, t + 1.0, args, env, directory / "session.log")
    return read_run(directory, frame, count, profile)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("profile", choices=sorted(PROFILES))
    p.add_argument("--roms", required=True, type=Path)
    p.add_argument("--disk", required=True, type=Path)
    p.add_argument("--run-frame", required=True, type=int)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--cli", type=Path)
    a = p.parse_args()
    out = a.out.expanduser().resolve()
    if out == ROOT or ROOT in out.parents:
        p.error("capture output must remain outside the checkout")
    roms = a.roms.resolve(strict=True); disk = a.disk.resolve(strict=True)
    if a.cli:
        cli = a.cli.resolve(strict=True)
    else:
        subprocess.run(["sh", str(ROOT / "tools/build_research_cli.sh")], cwd=ROOT, check=True)
        cli = ROOT / "build/research-cli/asr10-cli"
    out.mkdir(parents=True, exist_ok=False)
    a_bundle = run_boot(cli, roms, disk, out, "a", a.profile, a.run_frame)
    b_bundle = run_boot(cli, roms, disk, out, "b", a.profile, a.run_frame)
    if a_bundle["snapshot"].read_bytes() != b_bundle["snapshot"].read_bytes():
        raise SystemExit("fresh OS boot RUN checkpoints differ")
    if event_fingerprint(a_bundle) != event_fingerprint(b_bundle):
        raise SystemExit("fresh OS boot startup/load events differ")
    if a_bundle["updates"] != b_bundle["updates"]:
        raise SystemExit("fresh OS boot post-RUN firmware events differ")
    if a_bundle["inputs"] != b_bundle["inputs"] or a_bundle["outputs"] != b_bundle["outputs"]:
        raise SystemExit("fresh OS boot DSP serial traces differ")
    if a_bundle["host_wav"].read_bytes() != b_bundle["host_wav"].read_bytes():
        raise SystemExit("fresh OS boot host WAV references differ")
    print(f"validated two {PROFILES[a.profile]['effect_id']} RUN captures at frame {a.run_frame}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
