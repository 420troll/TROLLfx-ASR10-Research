#!/usr/bin/env python3
"""Enumerate and privately capture effects selected by the ASR-10 OS 3.53 UI.

ROM images, captures, host logs, WAVs, and manifests are local research data.
This tool refuses to place them inside the Git checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import struct
import wave
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLI = ROOT / "build/research-cli/asr10-cli"
DISPLAY_RE = re.compile(r"^\[\s*([0-9.]+)s\] \|FX=(.*?)\|$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def private_dir(path: Path) -> Path:
    p = path.expanduser().resolve()
    root = ROOT.resolve()
    if p == root or root in p.parents:
        raise ValueError("private output must stay outside the Git repository")
    return p


def atomic_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def parse_display_log(log: str, start: float, interval: float, raw_values: list[int]) -> dict:
    """Associate each DATA ENTRY value with the last repaint of the OS display."""
    states: list[str | None] = [None] * len(raw_values)
    last_time = None
    for line in log.splitlines():
        m = DISPLAY_RE.match(line)
        if not m:
            continue
        t = float(m.group(1))
        last_time = t
        idx = math.floor((t - start + 1e-7) / interval)
        if 0 <= idx < len(states):
            states[idx] = m.group(2).strip()
    visible = None
    for i, state in enumerate(states):
        if state is not None:
            visible = state
        elif visible is not None:
            states[i] = visible

    by_id: dict[int, dict] = {}
    variants: dict[int, dict[str, list[int]]] = {}
    for slot_index, state in enumerate(states):
        if not state:
            continue
        m = re.match(r"ROM-(\d{1,3})\s+(.*)$", state)
        if not m:
            continue
        effect_id, name = int(m.group(1)), m.group(2).strip()
        if effect_id < 1 or not name:
            continue
        variants.setdefault(effect_id, {}).setdefault(name, []).append(slot_index)
        by_id.setdefault(effect_id, {"id": effect_id})
    entries = []
    for effect_id in sorted(by_id):
        names = variants[effect_id]
        # Panel character refreshes can expose short-lived partial labels. Keep
        # the most persistent full display string and preserve alternatives.
        primary = max(names, key=lambda name: (len(names[name]), names[name][-1]))
        indices = names[primary]
        selected = [raw_values[i] for i in indices]
        entries.append({"id": effect_id, "name": primary, "select_raw": selected[len(selected)//2],
                        "raw_values": selected,
                        "display_variants": sorted(n for n in names if n != primary)})
    return {"entries": entries, "display_slots": sum(x is not None for x in states),
            "unobserved_raw_values": [raw_values[i] for i,x in enumerate(states) if x is None],
            "last_display_time": last_time}


def run(cli: Path, rom_dir: Path, os_image: Path, seconds: float, extra: list[str], env: dict, log: Path) -> None:
    cmd = [str(cli), "--roms", str(rom_dir), "--disk", str(os_image), "--seconds", f"{seconds:g}", *extra]
    with log.open("w", encoding="utf-8", errors="replace") as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, check=True)


def resolve_inputs(args):
    cli = Path(args.cli).expanduser().resolve()
    rom_dir = Path(args.rom_dir).expanduser().resolve()
    os_image = Path(args.os_image).expanduser().resolve()
    out = private_dir(Path(args.output))
    if not cli.is_file() or not os.access(cli, os.X_OK):
        raise ValueError(f"native emulator CLI is not executable: {cli}")
    for name in ("asr-648c-lo-1.5b.bin", "asr-65e0-hi-1.5b.bin"):
        if not (rom_dir / name).is_file():
            raise ValueError(f"missing private ROM: {name}")
    if not os_image.is_file() or os_image.stat().st_size != 1_638_400:
        raise ValueError("OS image must exist and be exactly 1,638,400 bytes")
    out.mkdir(parents=True, exist_ok=True)
    return cli, rom_dir, os_image, out


def emulator_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(ASR_ROUTE="-1,-1,1,-1,0", ASR_TEST_SINE="440:0.25", ESP_HOSTLOG="1")
    return env


def enumerate_effects(args) -> int:
    cli, rom_dir, os_image, out = resolve_inputs(args)
    raw_values = list(range(args.raw_first, args.raw_last + 1, args.raw_step))
    if raw_values[-1] != args.raw_last:
        raw_values.append(args.raw_last)
    start, interval = args.start, args.interval
    cmd = ["--panel-log", "--button", "15:7:1", "--button", "15.2:7:0"]
    t = start
    for value in raw_values:
        cmd += ["--analog-at", f"{t:.3f}:5:{value}"]
        t += interval
    logfile = out / "enumeration.log"
    run(cli, rom_dir, os_image, t + args.tail, cmd, emulator_env(), logfile)
    parsed = parse_display_log(logfile.read_text(errors="replace"), start, interval, raw_values)
    entries = parsed["entries"]
    report = {"schema": "asr10-os-rom-effect-inventory-v1", "os_sha256": sha256(os_image),
              "boot_rom_sha256": {p.name: sha256(p) for p in sorted(rom_dir.glob("asr-*-1.5b.bin"))},
              "selection_control": "OS FX Select screen; analog channel AN_DATA (5)",
              "raw_range": [args.raw_first, args.raw_last], "raw_step": args.raw_step,
              "interval_seconds": interval, "entries": entries, "observed_count": len(entries),
              "contiguous_ids_from_1": bool(entries) and [x["id"] for x in entries] == list(range(1, max(x["id"] for x in entries)+1)),
              "display_slots_observed": parsed["display_slots"],
              "unobserved_raw_values": parsed["unobserved_raw_values"],
              "enumeration_log_sha256": sha256(logfile)}
    path = out / "inventory.json"
    atomic_json(path, report)
    print(json.dumps({"inventory": str(path), "count": len(entries), "ids": [x["id"] for x in entries],
                      "contiguous_from_1": report["contiguous_ids_from_1"], "log": str(logfile)}, indent=2))
    return 0


def audio_metrics(path: Path) -> dict:
    with wave.open(str(path), "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (44100, 2, 2):
            raise ValueError("expected 44.1 kHz stereo PCM16 render")
        raw = w.readframes(w.getnframes())
    samples = struct.unpack("<%dh" % (len(raw)//2), raw)
    peak = max(map(abs, samples), default=0)
    rms = math.sqrt(sum(v*v for v in samples)/len(samples)) if samples else 0.0
    return {"frames": len(samples)//2, "peak_pcm16": peak, "rms_pcm16": round(rms, 4), "nonzero": peak > 0}


def capture_is_valid(entry: dict, directory: Path) -> bool:
    if entry.get("status") != "captured":
        return False
    for key in ("log", "esp", "wav", "summary"):
        p = directory / entry.get(key, "")
        if not p.is_file() or sha256(p) != entry.get("hashes", {}).get(key):
            return False
    try:
        snap = json.loads((directory / entry["summary"]).read_text())
        return snap["program"]["active_words_through_first_END"] is not None and not snap["runtime"]["control"]["halted"]
    except (OSError, ValueError, KeyError, TypeError):
        return False


def host_event_summary(log: Path, start_time: float | None = None, end_time: float | None = None) -> dict:
    counts = {"gpr": 0, "instruction": 0, "combined": 0, "ram": 0}
    gpr_indices: set[int] = set()
    instruction_indices: set[int] = set()
    ram_lines = 0
    for line in log.read_text(errors="replace").splitlines():
        m = re.match(r"ESPHOST (gpr|instr|both|ram)\b", line)
        if not m:
            continue
        tm = re.search(r"\bt=([0-9.]+)", line)
        event_time = float(tm.group(1)) if tm else None
        if event_time is not None and start_time is not None and event_time < start_time:
            continue
        if event_time is not None and end_time is not None and event_time > end_time:
            continue
        kind = m.group(1)
        if kind == "gpr":
            counts["gpr"] += 1
        elif kind == "instr":
            counts["instruction"] += 1
        elif kind == "both":
            counts["combined"] += 1
        elif kind == "ram":
            counts["ram"] += 1
            ram_lines += 1
        if kind in ("gpr", "instr", "both"):
            ix = re.search(r"ESPHOST (?:gpr|instr|both) ([0-9a-fA-F]{2}) <-", line)
            if ix:
                index = int(ix.group(1), 16)
                if kind in ("gpr", "both"):
                    gpr_indices.add(index)
                if kind in ("instr", "both"):
                    instruction_indices.add(index)
    return {"event_counts": counts, "unique_gpr_commit_indices": len(gpr_indices),
            "unique_instruction_commit_indices": len(instruction_indices),
            "gpr_initialization_evidence": counts["gpr"] + counts["combined"],
            "time_window_seconds": [start_time, end_time],
            "raw_ordered_transactions_retained": True}


def summarize_status(inventory: dict, manifest: dict) -> dict:
    discovered = sorted(int(e["id"]) for e in inventory["entries"])
    captured = sorted(int(k) for k,v in manifest["effects"].items() if v.get("status") == "captured")
    failed = sorted(int(k) for k,v in manifest["effects"].items() if v.get("status") == "failed")
    return {"schema": "asr10-rom-effect-status-v1", "discovered": discovered,
            "captured": captured, "failed": failed,
            "untested": sorted(set(discovered)-set(captured)-set(failed)),
            "counts": {"discovered": len(discovered), "captured": len(captured),
                       "failed": len(failed), "untested": len(set(discovered)-set(captured)-set(failed))}}


def capture(args) -> int:
    cli, rom_dir, os_image, out = resolve_inputs(args)
    if not args.hall_only:
        raise ValueError("isolated analog values are state-dependent; use capture-sweep for ROM IDs")
    inventory = json.loads(Path(args.inventory).expanduser().resolve().read_text())
    os_hash = sha256(os_image)
    if inventory.get("os_sha256") != os_hash:
        raise ValueError("inventory was generated from a different OS image")
    manifest_path = out / "manifest.json"
    manifest = {"schema": "asr10-rom-effect-capture-v1", "os_sha256": os_hash,
                "boot_rom_sha256": inventory.get("boot_rom_sha256", {}), "effects": {}}
    if manifest_path.exists():
        prior = json.loads(manifest_path.read_text())
        if prior.get("os_sha256") != os_hash or prior.get("boot_rom_sha256") != manifest["boot_rom_sha256"]:
            raise ValueError("output manifest belongs to different firmware; use a separate output root")
        manifest = prior
    results = []
    if not args.skip_hall_reference:
        hall_dir = out / "HALL-REFERENCE"
        hall_dir.mkdir(parents=True, exist_ok=True)
        old_hall = manifest.get("hall_reference", {})
        if not capture_is_valid(old_hall, hall_dir):
            hlog, hesp = hall_dir/"host.log", hall_dir/"state.esp"
            hwav, hsummary = hall_dir/"render.wav", hall_dir/"summary.json"
            hall = {"display_name": "INST HALL REVERB", "status": "running", "directory": hall_dir.name}
            manifest["hall_reference"] = hall
            atomic_json(manifest_path, manifest)
            try:
                run(cli, rom_dir, os_image, args.seconds,
                    ["--panel-log", "--button", "15:7:1", "--button", "15.2:7:0",
                     "--esp-list", "--esp-dump", str(hesp), "--wav", str(hwav)], emulator_env(), hlog)
                text = hlog.read_text(errors="replace")
                if "HALL REVERB" not in text or "FX=INST" not in text:
                    raise RuntimeError("built-in HALL REVERB display was not verified")
                summary_result = subprocess.run([sys.executable, str(ROOT/"tools/esp_capture.py"), str(hesp)],
                                                check=True, capture_output=True, text=True)
                hsummary.write_text(summary_result.stdout, encoding="utf-8")
                snap = json.loads(hsummary.read_text())
                audio = audio_metrics(hwav)
                if snap["runtime"]["control"]["halted"] or snap["program"]["active_words_through_first_END"] is None or not audio["nonzero"]:
                    raise RuntimeError("HALL reference capture/render failed basic validation")
                hall.update({"status": "captured", "log": hlog.name, "esp": hesp.name,
                             "wav": hwav.name, "summary": hsummary.name,
                             "active_instructions_through_first_END": snap["program"]["active_words_through_first_END"],
                             "audio": audio, "host_events": host_event_summary(hlog),
                             "memory_configuration": snap["runtime"]["memory_configuration"],
                             "delay_configuration": snap["runtime"]["delay_configuration"],
                             "signal_configuration": snap["runtime"]["signal_configuration"],
                             "hashes": {"log": sha256(hlog), "esp": sha256(hesp), "wav": sha256(hwav),
                                        "summary": sha256(hsummary)}})
                atomic_json(manifest_path, manifest)
                results.append({"id": "INST-HALL", "status": "captured", "instructions": hall["active_instructions_through_first_END"]})
            except Exception as exc:
                hall.update({"status": "failed", "failure": f"{type(exc).__name__}: {exc}"})
                atomic_json(manifest_path, manifest)
                results.append({"id": "INST-HALL", "status": "failed", "failure": str(exc)})
                if args.stop_on_error:
                    return 1
        else:
            results.append({"id": "INST-HALL", "status": "captured", "resumed": True})
    status = summarize_status(inventory, manifest)
    atomic_json(out/"status.json", status)
    print(json.dumps({"results": results, "status": status, "manifest": str(manifest_path)}, indent=2))
    return 1 if any(r["status"] == "failed" for r in results) else 0


def active_program_matches_host(log: Path, esp: Path, snap: dict, at_time: float | None = None) -> dict:
    raw = esp.read_bytes()
    if raw[:8] != b"ES5510C\0":
        return {"verified": False, "reason": "invalid snapshot magic"}
    nins = struct.unpack_from("<I", raw, 16)[0]
    words = [raw[44+i*6:44+(i+1)*6].hex() for i in range(nins)]
    active = snap["program"]["active_words_through_first_END"]
    last: dict[int,str] = {}
    rx = re.compile(r"ESPHOST (?:instr|both) ([0-9a-fA-F]{2}) <- ([0-9a-fA-F]{12})(?:.*? t=([0-9.]+))?$")
    for line in log.read_text(errors="replace").splitlines():
        m = rx.search(line)
        if m:
            if at_time is not None and m.group(3) is not None and float(m.group(3)) > at_time + 1e-6:
                continue
            last[int(m.group(1), 16)] = m.group(2).lower()
    missing = [i for i in range(active) if i not in last]
    mismatch = [i for i in range(active) if i in last and last[i] != words[i]]
    return {"verified": not missing and not mismatch, "active_instruction_count": active,
            "host_committed_indices": len(last), "missing_active_indices": missing,
            "mismatched_active_indices": mismatch}


def extract_wav_segment(source: Path, destination: Path, start_s: float, seconds: float) -> dict:
    with wave.open(str(source), "rb") as inp:
        rate, channels, width = inp.getframerate(), inp.getnchannels(), inp.getsampwidth()
        start = max(0, int(round(start_s * rate)))
        count = max(0, int(round(seconds * rate)))
        if channels != 2 or width != 2 or rate != 44100:
            raise ValueError("sweep render must be 44.1 kHz stereo PCM16")
        inp.setpos(min(start, inp.getnframes()))
        data = inp.readframes(min(count, max(0, inp.getnframes()-start)))
    with wave.open(str(destination), "wb") as outwav:
        outwav.setnchannels(2); outwav.setsampwidth(2); outwav.setframerate(44100); outwav.writeframes(data)
    return audio_metrics(destination)


def capture_sweep(args) -> int:
    """Capture all programs during one OS effect-selector sweep.

    The OS selection control is stateful: absolute knob values can land on a
    different ID after a fresh boot than during an ascending scan. Snapshots at
    stable, observed display IDs avoid assuming an isolated value-to-ID map.
    """
    cli, rom_dir, os_image, out = resolve_inputs(args)
    inventory = json.loads(Path(args.inventory).expanduser().resolve().read_text())
    if inventory.get("os_sha256") != sha256(os_image):
        raise ValueError("inventory was generated from a different OS image")
    manifest_path = out/"manifest.json"
    manifest = {"schema": "asr10-rom-effect-capture-v1", "os_sha256": sha256(os_image),
                "boot_rom_sha256": inventory.get("boot_rom_sha256", {}), "effects": {}}
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if previous.get("os_sha256") != manifest["os_sha256"] or previous.get("boot_rom_sha256") != manifest["boot_rom_sha256"]:
            raise ValueError("output manifest belongs to different firmware")
        manifest = previous
    if not capture_is_valid(manifest.get("hall_reference", {}), out/"HALL-REFERENCE"):
        hall_args = argparse.Namespace(cli=args.cli, rom_dir=args.rom_dir, os_image=args.os_image,
                                       output=args.output, inventory=args.inventory, seconds=22.0,
                                       skip_hall_reference=False, stop_on_error=True, hall_only=True)
        if capture(hall_args) != 0:
            return 1
        manifest = json.loads(manifest_path.read_text())
    # A run is resumable: the native CLI never overwrites existing snapshots,
    # while already-valid per-ID records are skipped during post-processing.
    snap_dir = out/"snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    # Preserve damaged remnants from an interrupted write, but let the CLI
    # recreate that ID's snapshot on this resume.
    for candidate in snap_dir.glob("ROM-*.esp"):
        match = re.fullmatch(r"ROM-(\d{2,3})\.esp", candidate.name)
        if match:
            effect_id = int(match.group(1))
            old_record = manifest["effects"].get(str(effect_id), {})
            old_dir = out/old_record.get("directory", "") if old_record else Path("/")
            if not old_record or not capture_is_valid(old_record, old_dir):
                archived = candidate.with_name(candidate.name + ".previous")
                index = 1
                while archived.exists():
                    archived = candidate.with_name(candidate.name + f".previous-{index}")
                    index += 1
                candidate.rename(archived)
                continue
        check = subprocess.run([sys.executable, str(ROOT/"tools/esp_capture.py"), str(candidate)],
                               capture_output=True, text=True)
        if check.returncode:
            damaged = candidate.with_name(candidate.name + ".incomplete")
            suffix = 1
            while damaged.exists():
                damaged = candidate.with_name(candidate.name + f".incomplete-{suffix}")
                suffix += 1
            candidate.rename(damaged)
    raw_values = list(range(args.raw_first, args.raw_last+1, args.raw_step))
    if not raw_values or raw_values[-1] != args.raw_last:
        raw_values.append(args.raw_last)
    t = args.start
    command = ["--panel-log", "--button", "15:7:1", "--button", "15.2:7:0",
               "--esp-snapshot-rom-dir", str(snap_dir), "--wav", str(out/"selector-sweep.wav")]
    for raw_value in raw_values:
        command += ["--analog-at", f"{t:.3f}:5:{raw_value}"]
        t += args.interval
    logfile = out/"selector-sweep.log"
    run(cli, rom_dir, os_image, t+args.tail, command, emulator_env(), logfile)
    captures = {}
    for line in logfile.read_text(errors="replace").splitlines():
        m = re.match(r'ESP_ROM_CAPTURE(?:_EXISTS)? id=(\d+) time=([0-9.]+)(?: display=(.*?))? path=(.*)$', line)
        if m:
            captures[int(m.group(1))] = {"time": float(m.group(2)), "display": m.group(3) or "", "path": Path(m.group(4))}
    listed = {int(e["id"]): e for e in inventory["entries"]}
    ordered = sorted(captures.items(), key=lambda kv: kv[1]["time"])
    full_wav = out/"selector-sweep.wav"
    for pos, (effect_id, capture_info) in enumerate(ordered):
        item = listed.get(effect_id)
        if not item:
            continue
        label = re.sub(r"[^A-Za-z0-9]+", "-", item["name"]).strip("-")[:36] or "unnamed"
        directory = out/f"ROM-{effect_id:02d}-{label}"
        directory.mkdir(exist_ok=True)
        record = manifest["effects"].get(str(effect_id), {})
        if capture_is_valid(record, directory):
            continue
        record.update({"id": effect_id, "display_name": item["name"], "status": "running",
                       "directory": directory.name, "selected_as": capture_info["display"],
                       "snapshot_time_seconds": capture_info["time"]})
        manifest["effects"][str(effect_id)] = record
        atomic_json(manifest_path, manifest)
        try:
            if item["name"] not in capture_info["display"]:
                raise RuntimeError("stable OS display label differs from the enumerated label")
            source_snapshot = capture_info["path"]
            if not source_snapshot.is_file():
                raise RuntimeError("stable ROM selection snapshot is missing")
            esp = directory/"state.esp"
            if esp.exists() and not capture_is_valid(record, directory):
                archived = esp.with_name(esp.name + ".previous")
                index = 1
                while archived.exists():
                    archived = esp.with_name(esp.name + f".previous-{index}")
                    index += 1
                esp.rename(archived)
            if not esp.exists():
                shutil.copy2(source_snapshot, esp)
            summary_result = subprocess.run([sys.executable, str(ROOT/"tools/esp_capture.py"), str(esp)],
                                            check=True, capture_output=True, text=True)
            summary = directory/"summary.json"
            summary.write_text(summary_result.stdout, encoding="utf-8")
            snap = json.loads(summary.read_text())
            active = snap["program"]["active_words_through_first_END"]
            if active is None or snap["runtime"]["control"]["halted"]:
                raise RuntimeError("snapshot lacks an END position or DSP was halted")
            hostlog = directory/"host.log"
            shutil.copy2(logfile, hostlog)
            host_match = active_program_matches_host(hostlog, esp, snap, capture_info["time"])
            if not host_match["verified"]:
                raise RuntimeError("active snapshot instructions do not match the last observed host commits")
            start_audio = capture_info["time"] + args.audio_offset
            wav = directory/"render.wav"
            next_time = ordered[pos+1][1]["time"] if pos+1 < len(ordered) else None
            available = (next_time - start_audio - 0.05) if next_time is not None else args.audio_seconds
            audio_duration = min(args.audio_seconds, available)
            if audio_duration <= 0.05:
                raise RuntimeError("too little stable audio remains before the next effect selection")
            audio = extract_wav_segment(full_wav, wav, start_audio, audio_duration)
            prior_time = ordered[pos-1][1]["time"] if pos else args.start
            event_window = host_event_summary(hostlog, prior_time, capture_info["time"])
            record.update({"status": "captured", "esp": esp.name, "log": hostlog.name,
                           "wav": wav.name, "summary": summary.name,
                           "active_instructions_through_first_END": active,
                           "end_indices": snap["program"]["END_indices"],
                           "active_program_sha256": snap["program"]["active_program_sha256"],
                           "registers": snap["registers"], "memory_configuration": snap["runtime"]["memory_configuration"],
                           "special_registers": snap["runtime"]["special_registers"],
                           "delay_configuration": snap["runtime"]["delay_configuration"],
                           "signal_configuration": snap["runtime"]["signal_configuration"],
                           "host_program_match": host_match, "host_events": event_window,
                           "audio": audio,
                           "hashes": {"esp": sha256(esp), "log": sha256(hostlog), "wav": sha256(wav), "summary": sha256(summary)}})
            atomic_json(manifest_path, manifest)
        except Exception as exc:
            record.update({"status": "failed", "failure": f"{type(exc).__name__}: {exc}"})
            atomic_json(manifest_path, manifest)
    status = summarize_status(inventory, manifest)
    status["observed_capture_events"] = sorted(captures)
    status["missing_capture_events"] = sorted(set(listed)-set(captures))
    status["hall_reference"] = manifest.get("hall_reference", {}).get("status", "not-run")
    atomic_json(out/"status.json", status)
    print(json.dumps({"status": status, "manifest": str(manifest_path),
                      "full_sweep_log": str(logfile), "full_sweep_wav": str(full_wav)}, indent=2))
    return 1 if status["failed"] or status["untested"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("enumerate", "capture", "capture-sweep"):
        q = sub.add_parser(name)
        q.add_argument("--cli", default=str(DEFAULT_CLI))
        q.add_argument("--rom-dir", required=True)
        q.add_argument("--os-image", required=True)
        q.add_argument("--output", required=True, help="private path outside Git")
    e = sub.choices["enumerate"]
    e.add_argument("--start", type=float, default=16.0)
    e.add_argument("--raw-first", type=int, default=8)
    e.add_argument("--raw-last", type=int, default=1023)
    e.add_argument("--raw-step", type=int, default=1)
    e.add_argument("--interval", type=float, default=0.15)
    e.add_argument("--tail", type=float, default=1.0)
    c = sub.choices["capture"]
    c.add_argument("--inventory", required=True)
    c.add_argument("--seconds", type=float, default=22.0)
    c.add_argument("--skip-hall-reference", action="store_true")
    c.add_argument("--hall-only", action="store_true")
    s = sub.choices["capture-sweep"]
    s.add_argument("--inventory", required=True)
    s.add_argument("--start", type=float, default=16.0)
    s.add_argument("--raw-first", type=int, default=8)
    s.add_argument("--raw-last", type=int, default=1023)
    s.add_argument("--raw-step", type=int, default=1)
    s.add_argument("--interval", type=float, default=0.15)
    s.add_argument("--tail", type=float, default=1.0)
    s.add_argument("--audio-offset", type=float, default=0.12)
    s.add_argument("--audio-seconds", type=float, default=0.5)
    c.add_argument("--stop-on-error", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "enumerate":
            return enumerate_effects(args)
        if args.command == "capture":
            return capture(args)
        return capture_sweep(args)
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
