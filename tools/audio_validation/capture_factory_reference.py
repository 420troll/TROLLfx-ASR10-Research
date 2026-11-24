#!/usr/bin/env python3
"""Capture two fresh OS 3.53 effect RUN references for a replay profile.

OS ROMs, disk image, snapshots, logs, WAVs, serial samples, and maps stay in the
private output directory. Selector values are traversed in ascending order,
because a direct value from a fresh boot is not reliable evidence of effect
identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
from factory_replay_profiles import PROFILES
from replay_factory_from_boundary import (correlate_source_efe, event_fingerprint,
                                          read_run, write_manifest)
from reference_provenance import (SCHEMA, artifact_inventory, compiler_facts,
                                  describe_file, environment_facts, sha256_file,
                                  source_fingerprint, verify_provenance, write_json)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def stable_hash(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


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
    # Remove inherited emulator debug switches before applying this capture's
    # explicit settings. Other process environment is preserved and recorded
    # only through the selected platform/compiler facts.
    env = {k: v for k, v in os.environ.items() if not (k.startswith("ASR_") or k.startswith("ESP_"))}
    count = 32768
    env.update({"ASR_ROUTE": "-1,-1,1,-1,0", "ASR_TEST_SINE": "440:0.25",
                "ESP_PIPELOG": "1", "ESP_HOSTLOG": "1", "ESP_FRAMELOG": str(count),
                "ESP_FRAMELOG_START_FRAME": str(frame), "ESP_RUN_SNAPSHOT_FRAME": str(frame),
                "ESP_RUN_SNAPSHOT_DIR": str(directory / "snapshots"),
                "ASR_HOST_PCM_TRACE": str(directory / "host-output-map.csv"),
                "ASR_HOST_PCM_START_FRAME": str(frame), "ASR_HOST_PCM_FRAMES": str(count)})
    command = [str(cli), "--roms", str(roms), "--disk", str(disk), "--seconds", f"{t + 1.0:g}", *args]
    started = now_utc()
    with (directory / "session.log").open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
        pid = process.pid
        returncode = process.wait()
    ended = now_utc()
    receipt = {"label": boot, "pid": pid, "started_utc": started, "ended_utc": ended,
               "returncode": returncode, "cwd": str(ROOT), "argv": command,
               "controlled_environment": {k: env[k] for k in sorted(env)
                                          if k.startswith("ASR_") or k.startswith("ESP_")}}
    if returncode:
        raise subprocess.CalledProcessError(returncode, command)
    bundle = read_run(directory, frame, count, profile)
    bundle["process_receipt"] = receipt
    return bundle


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("profile", choices=sorted(PROFILES))
    p.add_argument("--roms", required=True, type=Path)
    p.add_argument("--disk", required=True, type=Path)
    p.add_argument("--run-frame", required=True, type=int)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--cli", type=Path)
    p.add_argument("--efe-object", type=Path,
                   help="private EFE source object; required for ROM profiles with a correlated program")
    a = p.parse_args()
    out = a.out.expanduser().resolve()
    if out == ROOT or ROOT in out.parents:
        p.error("capture output must remain outside the checkout")
    roms = a.roms.resolve(strict=True); disk = a.disk.resolve(strict=True)
    profile = PROFILES[a.profile]
    efe = a.efe_object.expanduser().resolve(strict=True) if a.efe_object else None
    if profile.get("program_sha256") and not efe:
        p.error("this profile requires --efe-object to establish source-to-program correlation")
    rom_files = [roms / "asr-648c-lo-1.5b.bin", roms / "asr-65e0-hi-1.5b.bin"]
    if any(not item.is_file() for item in rom_files):
        p.error("--roms must contain the private ASR-10 low/high 1.5b ROM pair")
    source = source_fingerprint(ROOT)
    build = {"mode": "provided-executable", "command": None, "returncode": None}
    if a.cli:
        cli = a.cli.resolve(strict=True)
    else:
        build_command = ["bash", str(ROOT / "tools/build_research_cli.sh")]
        build_started = now_utc()
        proc = subprocess.run(build_command, cwd=ROOT, check=True, capture_output=True, text=True)
        build = {"mode": "built-from-recorded-worktree", "command": build_command,
                 "cwd": str(ROOT), "started_utc": build_started, "ended_utc": now_utc(),
                 "returncode": proc.returncode,
                 "stdout_sha256": hashlib.sha256(proc.stdout.encode()).hexdigest(),
                 "stderr_sha256": hashlib.sha256(proc.stderr.encode()).hexdigest()}
        cli = ROOT / "build/research-cli/asr10-cli"
    cli = cli.resolve(strict=True)
    if not os.access(cli, os.X_OK):
        p.error("--cli must be executable")
    if not build.get("started_utc"):
        build["started_utc"] = build["ended_utc"] = None
    cli_record = describe_file(cli)
    if build["mode"] == "built-from-recorded-worktree":
        build["executable_sha256"] = cli_record["sha256"]
        build["source_working_tree_sha256"] = source["working_tree_sha256"]
    compiler = compiler_facts() if build["mode"] == "built-from-recorded-worktree" else None
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
    source_correlation = None
    b_source_correlation = None
    if efe:
        source_correlation = correlate_source_efe(a_bundle, profile, efe)
        b_source_correlation = correlate_source_efe(b_bundle, profile, efe)
        if b_source_correlation != source_correlation:
            raise SystemExit("fresh OS boot source correlations differ")
        a_bundle["source_correlation"] = source_correlation
    manifest_path = write_manifest(a_bundle, a.profile, out / "replay-manifest")
    validation = {
        "two_boots_identical": True,
        "snapshots_equal": True,
        "startup_events_equal": event_fingerprint(a_bundle) == event_fingerprint(b_bundle),
        "post_run_events_equal": a_bundle["updates"] == b_bundle["updates"],
        "serial_inputs_equal": a_bundle["inputs"] == b_bundle["inputs"],
        "serial_outputs_equal": a_bundle["outputs"] == b_bundle["outputs"],
        "host_wavs_equal": a_bundle["host_wav"].read_bytes() == b_bundle["host_wav"].read_bytes(),
        "source_correlations_equal": not efe or b_source_correlation == source_correlation,
    }
    input_records = {"emulator_cli": cli_record, "os_disk": describe_file(disk),
                     "boot_roms": [describe_file(item) for item in rom_files],
                     "efe_source": describe_file(efe) if efe else None}
    boot_records = []
    for label, bundle in (("a", a_bundle), ("b", b_bundle)):
        directory = out / f"boot-{label}"
        boot_records.append({**bundle["process_receipt"],
                             "run_frame": bundle["run_frame"],
                             "checkpoint_sha256": bundle["capture"]["file_sha256"],
                             "startup_event_sha256": event_fingerprint(bundle),
                             "post_run_event_sha256": stable_hash(bundle["updates"]),
                             "serial_input_sha256": stable_hash(bundle["inputs"]),
                             "serial_output_sha256": stable_hash(bundle["outputs"]),
                             "artifacts": artifact_inventory(directory)})
    provenance_path = out / "provenance.json"
    provenance = {
        "schema": SCHEMA, "created_utc": now_utc(), "output_root": str(out),
        "profile": a.profile, "effect_id": profile["effect_id"], "effect_name": profile["effect_name"],
        "run_frame": a.run_frame, "dsp_frames": 32768,
        "source": source, "build": build, "compiler": compiler,
        "environment": environment_facts(), "inputs": input_records,
        "asset_roots": {"rom_directory": str(roms)},
        "efe_source_correlation": source_correlation,
        "boots": boot_records, "manifest": str(manifest_path),
        "validation": validation,
    }
    provenance["output_artifacts"] = artifact_inventory(out, exclude={"provenance.json"})
    write_json(provenance_path, provenance)
    verification = verify_provenance(provenance_path)
    if not verification["valid"]:
        raise SystemExit("provenance verification failed: " + "; ".join(verification["errors"]))
    print(f"validated two {PROFILES[a.profile]['effect_id']} RUN captures at frame {a.run_frame}")
    print(f"verified private provenance receipt: {provenance_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
