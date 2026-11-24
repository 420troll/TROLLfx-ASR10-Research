#!/usr/bin/env python3
"""Validate a private stable-selector sweep and make one private package per ROM slot.

The public catalog deliberately contains identities, observed lengths/rates and
shared-program relationships only. Captures, transaction values, hashes and
audio are written only beneath the required external private-results root.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import wave
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import esp_capture
import capture_asr10_rom_effects as capture

STATE = re.compile(r"^ESP_ROM_STATE id=(\d+) time=([0-9.]+) frame=(\d+) dsp_rate_hz=([0-9.]+) cycles=(\d+)")
PHASE = re.compile(r"^ESPPHASE kind=([a-z0-9_]+) frame=(\d+) cycles=(\d+)")
HOST = re.compile(r"^ESPHOST .*?cycles=(\d+) frame=(\d+) pc=([0-9a-fA-F]+) (gpr|instr|both|ram)\b")
INSN = re.compile(r"^ESPHOST .*?(?:instr|both) ([0-9a-fA-F]{2}) <- ([0-9a-fA-F]{12}).*?t=([0-9.]+)")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def external(path: Path) -> Path:
    p = path.expanduser().resolve()
    if p == ROOT or ROOT in p.parents:
        raise ValueError("private package output must remain outside the Git checkout")
    return p


def parse_sweep(log_path: Path):
    states, phases, host = [], [], []
    with log_path.open(errors="replace") as stream:
        for line in stream:
            m = STATE.match(line)
            if m:
                states.append({"id": int(m[1]), "time": float(m[2]), "frame": int(m[3]),
                               "rate": float(m[4]), "cycles": int(m[5])})
            m = PHASE.match(line)
            if m:
                phases.append({"kind": m[1], "frame": int(m[2]), "cycles": int(m[3])})
            m = HOST.match(line)
            if m:
                host.append((int(m[1]), int(m[2]), m[3], m[4], line.rstrip("\n")))
    return states, phases, host


def last_complete_run(phases: list[dict], through_cycles: int) -> tuple[int, dict]:
    before = [p for p in phases if p["cycles"] <= through_cycles]
    resets = [i for i, p in enumerate(before) if p["kind"] == "host_halt_pipeline_reset"]
    required_after_reset = ["host_halt_pipeline_reset", "host_dram_clear", "instruction_upload_start",
                            "pa4_run_release", "program_upload_summary", "run_start", "first_instruction"]
    for reset_at in reversed(resets):
        pa4_halts = [i for i, p in enumerate(before[:reset_at]) if p["kind"] == "pa4_halt_assert"]
        cpu_halts = [i for i, p in enumerate(before[:reset_at]) if p["kind"] == "halt"]
        if not pa4_halts or not cpu_halts:
            continue
        pa4_halt_at, cpu_halt_at = pa4_halts[-1], cpu_halts[-1]
        if pa4_halt_at >= cpu_halt_at:
            continue
        tail = before[reset_at:]
        selected = [before[pa4_halt_at], before[cpu_halt_at]]
        pos = 0
        for kind in required_after_reset:
            found = next((i for i in range(pos, len(tail)) if tail[i]["kind"] == kind), None)
            if found is None:
                break
            selected.append(tail[found]); pos = found + 1
        if len(selected) == 2 + len(required_after_reset):
            return selected[0]["cycles"], {"events": selected, "ordered": True}
    raise ValueError("no complete PA4 HALT/CPU HALT/pipeline reset/DRAM clear/upload/PA4 RUN/RUN/first-instruction sequence precedes snapshot")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True, help="private selector sweep directory")
    p.add_argument("--inventory", type=Path, required=True, help="validated private OS selector inventory")
    p.add_argument("--output", type=Path, required=True, help="new external private package directory")
    p.add_argument("--catalog", type=Path, required=True, help="public redacted JSON catalog path in checkout")
    a = p.parse_args()
    source = a.source.expanduser().resolve(strict=True)
    inventory_path = a.inventory.expanduser().resolve(strict=True)
    output = external(a.output)
    catalog_path = a.catalog.expanduser().resolve()
    inventory = json.loads(inventory_path.read_text())
    entries = {int(x["id"]): x for x in inventory.get("entries", [])}
    states, phases, host = parse_sweep(source / "selector-sweep.log")
    if sorted(entries) != list(range(1, 51)) or sorted(s["id"] for s in states) != list(range(1, 51)):
        raise ValueError("selector inventory and captured display markers must each contain IDs 1..50 exactly once")
    if digest(source / "selector-sweep.wav") == "":
        raise ValueError("missing full sweep WAV")
    if output.exists() and any(output.iterdir()):
        raise ValueError("private output must be a new or empty directory; refusing to overwrite")
    output.mkdir(parents=True, exist_ok=True)
    packages = output / "packages"
    packages.mkdir()

    # Correlate host instruction commits to each display-bound snapshot in one
    # pass over the ordered log instead of rescanning a large trace 50 times.
    commits: dict[int, str] = {}
    host_by_cycle = defaultdict(list)
    for cycles, frame, pc, kind, line in host:
        host_by_cycle[cycles].append(line)
    states_by_time = sorted(states, key=lambda s: s["time"])
    commit_snapshots = {}
    state_index = 0
    with (source / "selector-sweep.log").open(errors="replace") as stream:
        for line in stream:
            tm = re.search(r"\bt=([0-9.]+)", line)
            event_time = float(tm[1]) if tm else None
            while (event_time is not None and state_index < len(states_by_time) and
                   states_by_time[state_index]["time"] < event_time - 1e-6):
                commit_snapshots[states_by_time[state_index]["id"]] = dict(commits)
                state_index += 1
            m = INSN.match(line)
            if m:
                commits[int(m[1], 16)] = m[2].lower()
    while state_index < len(states_by_time):
        commit_snapshots[states_by_time[state_index]["id"]] = dict(commits)
        state_index += 1

    # The selector sweep's PCM is a shared file. Each slot gets its own short
    # private WAV cut, preserving the already observed host-output rate.
    previous_cycles = 0
    report, families = [], defaultdict(list)
    state_map = {s["id"]: s for s in states}
    for effect_id in range(1, 51):
        observed = state_map[effect_id]
        name = entries[effect_id]["name"]
        label = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")[:36] or "unnamed"
        folder = packages / f"ROM-{effect_id:02d}-{label}"
        folder.mkdir()
        snapshot = source / "snapshots" / f"ROM-{effect_id:02d}.esp"
        if not snapshot.is_file():
            raise ValueError(f"ROM-{effect_id:02d}: missing captured state")
        state = esp_capture.read_capture(snapshot)
        active = state["program"]["active_words_through_first_END"]
        if active is None or state["runtime"]["control"]["halted"] or state["runtime"]["control"]["pc"] != 0:
            raise ValueError(f"ROM-{effect_id:02d}: not a running PC-zero snapshot")
        if state["runtime"]["dram_words"] != 1 << 20 or state["registers"]["gpr_count"] != 192 or state["registers"]["special_count"] != 22:
            raise ValueError(f"ROM-{effect_id:02d}: incomplete live DSP state sections")
        if state["runtime"]["control"]["host_serial"] != 0x48:
            raise ValueError(f"ROM-{effect_id:02d}: captured serial mode does not match stereo factory route")
        matched = commit_snapshots.get(effect_id, {})
        raw = snapshot.read_bytes()
        program = [raw[44 + i * 6:50 + i * 6].hex() for i in range(active)]
        if any(matched.get(i) != program[i] for i in range(active)):
            raise ValueError(f"ROM-{effect_id:02d}: active instruction words do not match selector-time host commits")
        start_cycle, run_evidence = last_complete_run(phases, observed["cycles"])
        if start_cycle < previous_cycles:
            # A repeated reset may be emitted before a stable display marker;
            # retain the exact run block, but never claim a chronological
            # per-effect boundary earlier than the prior selected checkpoint.
            start_cycle = previous_cycles
        event_path = folder / "firmware-events.log"
        event_count = 0
        with event_path.open("w", encoding="utf-8") as out_events:
            for cycles, _, _, kind, line in host:
                if start_cycle <= cycles <= observed["cycles"]:
                    out_events.write(line + "\n"); event_count += 1
        if event_count == 0:
            raise ValueError(f"ROM-{effect_id:02d}: no post-reset host firmware transactions")
        checkpoint = folder / "run-checkpoint.esp"
        shutil.copy2(snapshot, checkpoint)
        render = folder / "selector-audio.wav"
        audio = capture.extract_wav_segment(source / "selector-sweep.wav", render,
                                            observed["time"] + 0.12, 0.5)
        if not audio["nonzero"]:
            raise ValueError(f"ROM-{effect_id:02d}: short selector audio render is silent")
        route = {"host_serial": state["runtime"]["control"]["host_serial"],
                 "configured_input_ports": [2], "configured_output_ports": [1],
                 "route_source": "ASR_ROUTE=-1,-1,1,-1,0 in the batch capture runner"}
        package = {
            "schema": "asr10-private-rom-effect-package-v1", "effect_id": effect_id,
            "display_name": name, "status": "validated",
            "capture_kind": "OS-selected RUN-state snapshot; pipeline-reset/upload/RUN sequence logged before capture",
            "checkpoint": checkpoint.name, "firmware_events": event_path.name, "audio_render": render.name,
            "active_program_words": active, "active_program_sha256": state["program"]["active_program_sha256"],
            "sample_rate_hz": observed["rate"], "host_output_rate_hz": 44100,
            "run_frame": observed["frame"], "snapshot_time_seconds": observed["time"],
            "pipeline_reset_acknowledged": True, "run_boundary_phase_evidence": run_evidence,
            "host_commit_match": {"verified": True, "active_words": active},
            "registers": state["registers"], "memory_configuration": state["runtime"]["memory_configuration"],
            "special_registers": state["runtime"]["special_registers"],
            "delay_configuration": state["runtime"]["delay_configuration"],
            "signal_configuration": state["runtime"]["signal_configuration"],
            "serial_route": route, "dram": {"words": state["runtime"]["dram_words"],
                "sha256": state["runtime"]["dram_sha256"], "nonzero_words": state["runtime"]["dram_nonzero_words"]},
            "firmware_transaction_count": event_count, "audio": audio,
            "files": {f.name: digest(f) for f in (checkpoint, event_path, render)},
        }
        (folder / "package.json").write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
        families[state["program"]["active_program_sha256"]].append(effect_id)
        report.append({"id": effect_id, "display_name": name, "status": "validated",
                       "directory": str(folder.relative_to(output)), "active_words": active,
                       "active_program_sha256": state["program"]["active_program_sha256"],
                       "sample_rate_hz": observed["rate"], "run_frame": observed["frame"],
                       "firmware_events": event_count, "audio_nonzero": audio["nonzero"]})
        previous_cycles = observed["cycles"]

    group_ids = {sha: members for sha, members in families.items()}
    for item in report:
        members = group_ids[item["active_program_sha256"]]
        item["shared_program_ids"] = members if len(members) > 1 else []
    (output / "collection-manifest.json").write_text(json.dumps({
        "schema": "asr10-private-rom-effect-collection-v1", "os_sha256": inventory["os_sha256"],
        "source_sweep_sha256": digest(source / "selector-sweep.log"),
        "slots": report, "counts": {"discovered": 50, "validated": 50, "failed": 0},
        "distinct_programs": len(families), "shared_program_groups": [v for v in group_ids.values() if len(v) > 1],
    }, indent=2, sort_keys=True) + "\n")
    shared_groups = []
    for members in group_ids.values():
        if len(members) < 2:
            continue
        group_packages = []
        for member in members:
            package_path = next(packages.glob(f"ROM-{member:02d}-*/package.json"))
            group_packages.append(json.loads(package_path.read_text()))
        shared_groups.append({"effect_ids": members, "same_active_instruction_image": True,
                              "distinct_gpr_states": len({x["registers"]["gpr_sha256"] for x in group_packages}) > 1,
                              "distinct_special_register_states": len({x["registers"]["special_sha256"] for x in group_packages}) > 1})
    catalog = {"schema": "asr10-rom-effect-catalog-v1", "effect_slots": 50,
               "identity_source": "OS 3.53 FX Select display", "capture_status": "validated emulator RUN-state snapshot",
               "distinct_programs_observed": len(families),
               "shared_program_groups": shared_groups,
               "effects": [{"id": x["id"], "display_name": x["display_name"],
                            "active_program_words": x["active_words"], "observed_dsp_rate_hz": x["sample_rate_hz"],
                            "shared_program_ids": x["shared_program_ids"], "capture_status": x["status"]}
                           for x in report]}
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"private_collection": str(output), "validated": 50, "failed": 0,
                      "distinct_programs": len(families), "catalog": str(catalog_path)}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"package_rom_effect_collection: {exc}", file=sys.stderr)
        raise SystemExit(2)
