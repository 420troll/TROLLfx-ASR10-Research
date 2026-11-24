#!/usr/bin/env python3
"""Validate and replay a captured factory-effect RUN boundary.

All state payloads, OS traces, generated engine traces, and audio remain in the
caller-selected private output directory. Profiles carry counts and clock
metadata only; engines are loaded from the observed RUN checkpoint.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import re
import struct
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
import esp_capture
from factory_replay_profiles import PROFILES

PHASE = re.compile(r"ESPPHASE kind=([a-z0-9_]+)\s+(.*)$")
FRAME = re.compile(r"ESPPFRAME kind=(input|output) index=(\d+) frame=(\d+) cycles=(\d+) host_pc=([0-9a-fA-F]+) serial=([0-9a-fA-F]+) lanes=([0-9a-fA-F,]+)")
HOST = re.compile(r"ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-fA-F]+) (gpr|instr|both|ram) ([0-9a-fA-F]+) <- ([0-9a-fA-F]+)(?: / ([0-9a-fA-F]+))?")
WINDOWS = (256, 4096, 32768)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def fields(text: str) -> dict[str, str]:
    return dict(re.findall(r"([a-z_]+)=([^\s]+)", text))


def signed16(v: str) -> int:
    n = int(v, 16) & 0xffff
    return n - 0x10000 if n & 0x8000 else n


def validate_instruction_aliases(words: list[int], aliases: dict) -> None:
    for alias, source in aliases.items():
        if words[int(alias)] != words[int(source)]:
            raise ValueError("instruction alias does not match the independently correlated source address")


def assign_event_boundary(event_seq: int, inputs: list[dict], outputs: list[dict]) -> int:
    input_seq = [x["seq"] for x in inputs]
    output_seq = [x["seq"] for x in outputs]
    j = bisect.bisect_right(input_seq, event_seq)
    k = bisect.bisect_left(output_seq, event_seq) - 1
    if j >= len(inputs) or k < 0 or outputs[k]["frame"] + 1 != inputs[j]["frame"]:
        raise ValueError("post-RUN firmware write is not bounded by adjacent serial frames")
    if not outputs[k]["seq"] < event_seq < inputs[j]["seq"]:
        raise ValueError("post-RUN firmware event order is ambiguous")
    return inputs[j]["frame"]


def read_run(directory: Path, frame0: int, frame_count: int, profile: dict) -> dict:
    log = directory / "session.log"
    snapshot = directory / "snapshots" / f"run-frame-{frame0}.esp"
    if not log.is_file() or not snapshot.is_file():
        raise ValueError(f"{directory.name}: missing RUN log or checkpoint")
    phases, events, frames, displays = [], [], [], []
    with log.open(errors="replace") as f:
        for line_no, line in enumerate(f, 1):
            if "|FX=ROM-" in line:
                displays.append((line_no, line))
            m = PHASE.search(line)
            if m:
                item = fields(m.group(2)); item.update(kind=m.group(1), seq=line_no)
                phases.append(item)
            m = HOST.search(line)
            if m:
                eid, cycles, dspframe, pc, kind, address, value, second = m.groups()
                events.append({"seq": line_no, "event_id": int(eid), "cycles": int(cycles),
                               "frame": int(dspframe), "pc": pc.lower(), "kind": kind,
                               "address": int(address, 16), "value": int(value, 16),
                               "second": int(second, 16) if second else None,
                               "time": float(re.search(r"\bt=([0-9.]+)", line).group(1))
                                       if re.search(r"\bt=([0-9.]+)", line) else None})
            m = FRAME.search(line)
            if m and frame0 <= int(m.group(3)) < frame0 + frame_count:
                kind, index, dspframe, cycles, pc, serial, lanes = m.groups()
                raw = lanes.split(",")
                if len(raw) != 8:
                    raise ValueError("serial frame did not have eight lanes")
                frames.append({"seq": line_no, "kind": kind, "index": int(index),
                               "frame": int(dspframe), "cycles": int(cycles),
                               "pc": pc.lower(), "serial": serial.lower(),
                               "lanes": [signed16(x) for x in raw]})

    run = [x for x in phases if x["kind"] == "run_start" and int(x.get("frame", -1)) == frame0]
    snap = [x for x in phases if x["kind"] == "run_snapshot" and int(x.get("frame", -1)) == frame0]
    first = [x for x in phases if x["kind"] == "first_instruction" and int(x.get("frame", -1)) == frame0]
    summary = [x for x in phases if x["kind"] == "program_upload_summary" and int(x.get("frame", -1)) == frame0]
    if any(len(x) != 1 for x in (run, snap, first, summary)):
        raise ValueError("RUN, checkpoint, upload summary, or first instruction is not unique")
    run, snap, first, summary = run[0], snap[0], first[0], summary[0]
    expected_display = f'{profile["effect_id"]} {profile["effect_name"]}'
    if not any(seq < run["seq"] and expected_display in re.sub(r"\s+", " ", line) for seq, line in displays):
        raise ValueError("OS display did not confirm the configured factory effect before RUN")
    if not (run["seq"] < snap["seq"] < first["seq"]):
        raise ValueError("RUN snapshot/first-instruction order is invalid")
    if int(first.get("pc", "-1"), 16) != 0:
        raise ValueError("first instruction is not at PC 0")

    before = [x for x in phases if x["seq"] < run["seq"]]
    halt = [x for x in before if x["kind"] == "pa4_halt_assert"]
    reset = [x for x in before if x["kind"] == "host_halt_pipeline_reset"]
    clear = [x for x in before if x["kind"] == "host_dram_clear"]
    upload = [x for x in before if x["kind"] == "instruction_upload_start"]
    release = [x for x in before if x["kind"] == "pa4_run_release"]
    if not all((halt, reset, clear, upload, release)):
        raise ValueError("HALT/reset/DRAM-clear/upload/RUN evidence is incomplete")
    halt, reset, clear, upload, release = halt[-1], reset[-1], clear[-1], upload[-1], release[-1]
    if not (halt["seq"] < reset["seq"] < clear["seq"] < upload["seq"] < release["seq"] < run["seq"]):
        raise ValueError("HALT/reset/clear/upload/RUN ordering does not match observed lifecycle")
    for key, expected in (("commits", profile["instruction_commits"]),
                          ("unique_addresses", profile["unique_instruction_addresses"]),
                          ("first_end", profile["end_word"]),
                          ("gpr_commits", profile["register_commits"])):
        if int(summary.get(key, -1)) != expected:
            raise ValueError(f"loader {key} count does not match effect profile")

    tx_events = [x for x in events if halt["seq"] < x["seq"] < run["seq"]]
    tx_instr = [x for x in tx_events if x["kind"] in ("instr", "both")]
    tx_register = sum(x["kind"] in ("gpr", "both") for x in tx_events)
    if len(tx_instr) != profile["instruction_commits"] or tx_register != profile["register_commits"]:
        raise ValueError("ordered transaction records disagree with upload summary")
    image = [0] * 160
    for e in tx_instr:
        image[e["address"]] = e["value"]
    cap = esp_capture.read_capture(snapshot)
    raw = snapshot.read_bytes()
    active = int(profile["active_words"])
    if cap["program"]["active_words_through_first_END"] != active:
        raise ValueError("checkpoint active program length differs from effect profile")
    checkpoint_words = [int.from_bytes(raw[44 + i * 6:44 + (i + 1) * 6], "big") for i in range(active)]
    if image[:active] != checkpoint_words:
        raise ValueError("ordered halted instruction writes do not recreate RUN program")
    validate_instruction_aliases(checkpoint_words, profile.get("instruction_aliases", {}))
    program = raw[44:44 + active * 6]
    program_hash = sha(program)
    if profile.get("program_sha256") and program_hash != profile["program_sha256"]:
        raise ValueError("active program digest does not match independently correlated effect")

    by_kind = {kind: [x for x in frames if x["kind"] == kind] for kind in ("input", "output")}
    want = list(range(frame0, frame0 + frame_count))
    if any([x["frame"] for x in by_kind[k]] != want for k in by_kind):
        raise ValueError("serial traces are incomplete or out of order")
    clock_lines = []
    with log.open(errors="replace") as f:
        for line in f:
            if f"ESPAUDIO kind=clock frame={frame0} " in line:
                clock_lines.append(fields(line.split("ESPAUDIO kind=clock", 1)[1]))
    if len(clock_lines) != 1:
        raise ValueError("clock metadata is not unique at RUN")
    clock = clock_lines[0]
    if float(clock["dsp_rate_hz"]) != profile["dsp_rate_hz"] or int(float(clock["host_output_rate_hz"])) != profile["host_rate_hz"]:
        raise ValueError("DSP or host clock differs from effect profile")
    if clock["serial_route"] != profile["serial_route"]:
        raise ValueError("serial route differs from effect profile")
    if int(run["host_serial"], 16) != profile["host_serial"]:
        raise ValueError("RUN host serial differs from effect profile")
    if cap["runtime"]["control"]["halted"] or cap["runtime"]["control"]["pc"] != 0:
        raise ValueError("checkpoint is not a running PC-zero boundary")
    if cap["runtime"]["dram_nonzero_words"] != 0:
        raise ValueError("checkpoint is not immediately after the verified DRAM clear")
    if cap["runtime"]["memory_configuration"]["memshift"] != 8:
        raise ValueError("checkpoint memory configuration is not the observed 256-byte mode")
    first_input = by_kind["input"][0]
    if cap["runtime"]["serial_samples"] != first_input["lanes"]:
        raise ValueError("checkpoint serial latches do not equal first input frame")
    if cap["runtime"]["memory_configuration"]["memshift"] != int(run["memshift"]):
        raise ValueError("RUN and snapshot memory modes disagree")

    wav_path = directory / "render.wav"
    map_path = directory / "host-output-map.csv"
    if not wav_path.is_file() or not map_path.is_file():
        raise ValueError("host WAV or source-position mapping is missing")
    with wave.open(str(wav_path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (2, 2, profile["host_rate_hz"]):
            raise ValueError("host WAV is not stereo PCM16 at the configured host rate")
        wav_frames = w.getnframes()
        wav_pcm = w.readframes(wav_frames)
    mapped = list(csv.DictReader(map_path.open(newline="")))
    if not mapped:
        raise ValueError("host source-position mapping is empty")
    for row in mapped:
        idx = int(row["host_frame_index"])
        if not 0 <= idx < wav_frames:
            raise ValueError("host source-position map refers outside the WAV")
        left, right = struct.unpack_from("<hh", wav_pcm, idx * 4)
        if (left, right) != (int(row["left_pcm16"]), int(row["right_pcm16"])):
            raise ValueError("host map PCM values disagree with the rendered OS WAV")

    # A host GPR write must be ordered between output frame k and input frame k+1.
    updates = []
    output_by_seq = sorted(by_kind["output"], key=lambda x: x["seq"])
    for e in events:
        if e["kind"] != "gpr" or not run["seq"] < e["seq"] < output_by_seq[-1]["seq"]:
            continue
        updates.append({**e, "boundary_frame": assign_event_boundary(e["seq"], by_kind["input"], by_kind["output"])})
    if len(updates) != profile["post_run_gpr_events"]:
        raise ValueError("post-RUN firmware event count differs from effect profile")
    return {"snapshot": snapshot, "capture": cap, "raw": raw, "program": program,
            "phases": phases, "events": events, "transaction_events": tx_events,
            "inputs": by_kind["input"], "outputs": by_kind["output"],
            "updates": updates, "clock": clock,
            "host_wav": wav_path, "host_map": map_path, "host_mapped_frames": len(mapped),
            "lifecycle": {"halt": halt, "reset": reset, "clear": clear,
                          "upload": upload, "release": release,
                          "run": run, "snapshot": snap, "first_instruction": first},
            "run_frame": frame0}


def event_fingerprint(bundle: dict) -> str:
    start = bundle["lifecycle"]["halt"]["seq"]
    end = bundle["lifecycle"]["first_instruction"]["seq"]
    log = bundle["snapshot"].parents[1] / "session.log"
    selected = []
    with log.open(errors="replace") as f:
        for line_no, line in enumerate(f, 1):
            if start <= line_no <= end and ("ESPPHASE " in line or "ESPHOST " in line or "ESPIO " in line):
                # Snapshot filenames vary by boot directory; the checkpoint digest is gated separately.
                selected.append(re.sub(r"path=[^\s]+", "path=<checkpoint>", line.rstrip("\n")))
    return sha(("\n".join(selected) + "\n").encode())


def correlate_source_efe(bundle: dict, profile: dict, efe_object: Path) -> dict:
    times = [e["time"] for e in bundle["transaction_events"]
             if e["seq"] < bundle["lifecycle"]["run"]["seq"] and e["time"] is not None]
    if not times:
        raise ValueError("load transaction has no timestamped source-correlation cutoff")
    cutoff = max(times)
    log = bundle["snapshot"].parents[1] / "session.log"
    tool = ROOT / "tools/compare_asr10_effect_capture.py"
    proc = subprocess.run([sys.executable, str(tool), str(efe_object.resolve(strict=True)),
                           str(bundle["snapshot"]), str(log), "--expected-name", profile["effect_name"],
                           "--at-time", f"{cutoff:.6f}"], capture_output=True, text=True)
    if proc.returncode:
        raise ValueError("source EFE comparison failed; payload values withheld")
    result = json.loads(proc.stdout)
    offsets = result.get("source_offsets", {})
    if (result.get("capture_active_instructions") != profile["active_words"] or
            result.get("capture_program_sha256") != profile["program_sha256"] or
            result.get("host_instruction_commits_exact_match") != profile["active_words"] or
            offsets.get("paired_records_count") != profile["source_paired_gprs"] or
            offsets.get("instruction_only_count") != profile["source_instruction_only"] or
            offsets.get("source_instruction_alias_count") != profile["source_aliases"] or
            offsets.get("host_instruction_only_commits") != (profile["source_instruction_only"] + profile["source_aliases"]) or
            not result.get("host_commit_gpr_bytes_match_source_for_paired_records") or
            not result.get("source_instruction_locations_resolved_by_layout")):
        raise ValueError("source EFE layout/counts do not match the effect-specific profile")
    return {"effect_name": result["effect_name"], "active_instruction_matches": result["host_instruction_commits_exact_match"],
            "paired_gpr_initializers": offsets["paired_records_count"],
            "instruction_only_source_records": offsets["instruction_only_count"],
            "source_aliases": offsets["source_instruction_alias_count"],
            "host_instruction_only_commits": offsets["host_instruction_only_commits"],
            "program_sha256": result["capture_program_sha256"], "cutoff_time_s": cutoff,
            "source_pair_values_match": True}


def write_manifest(bundle: dict, profile_name: str, out: Path) -> Path:
    raw = bundle["raw"]
    off = 44
    program = raw[off:off + len(bundle["program"])]; off += 160 * 6
    gpr = raw[off:off + 192 * 3]; off += 192 * 3
    spr = raw[off:off + 22 * 3]; off += 22 * 3
    state = raw[off:off + 74]; dram = raw[off + 74:]
    out.mkdir(parents=True, exist_ok=True)
    payloads = {"program.bin": program, "gpr.bin": gpr, "special-registers.bin": spr}
    for name, data in payloads.items():
        (out / name).write_bytes(data)
    profile = PROFILES[profile_name]
    cap = bundle["capture"]; rt = cap["runtime"]
    mem = rt["memory_configuration"]; delays = rt["delay_configuration"]
    manifest = {
        "schema": "trollfx-es5510-factory-init-v1", "initialization_basis": "cold_load",
        "provenance": {"effect_id": profile["effect_id"], "effect_name": profile["effect_name"],
                       "os_version": "3.53", "selection_evidence": "two fresh stable ROM selector sweeps; active image digest matches ROM-correlated effect capture"},
        "sample_rate_hz": int(profile["dsp_rate_hz"]),
        "program": {"format": "es5510-six-byte-big-endian", "path": "program.bin",
                    "sha256": sha(program), "active_words": profile["active_words"], "end_word": profile["end_word"]},
        "gpr": {"path": "gpr.bin", "sha256": sha(gpr), "count": 192},
        "special_registers": {"path": "special-registers.bin", "sha256": sha(spr), "count": 22},
        "dram": {"mode": "zeroed", "word_count": cap["runtime"]["dram_words"], "sha256": sha(dram)},
        "memory": {"memsiz": mem["memsiz"], "memmask": mem["memmask"],
                   "memincrement": mem["memincrement"], "memshift": mem["memshift"],
                   "dlength": delays["DLENGTH"], "abase": delays["ABASE"],
                   "bbase": delays["BBASE"], "dbase": delays["DBASE"],
                   "sigreg": rt["signal_configuration"]["SIGREG"]},
        "serial": {"host_serial": rt["control"]["host_serial"],
                   "input_ports": profile["input_ports"], "output_ports": profile["output_ports"]},
        "lifecycle": {"halt_before_load": True, "run_after_load": True,
                      "initialization_order": ["halt", "memory", "program", "gpr", "special_registers", "dram", "reset_pipeline", "run"]},
        "pipeline": {"status": "reset_after_load", "complete": True},
        "observed_run": {"absolute_frame": bundle["run_frame"], "checkpoint_sha256": cap["file_sha256"],
                         "clock": bundle["clock"], "transaction_commit_counts": {
                             "instruction_commits": profile["instruction_commits"],
                             "unique_instruction_addresses": profile["unique_instruction_addresses"],
                             "register_commits": profile["register_commits"]},
                         "startup_event_sha256": event_fingerprint(bundle),
                         "post_run_gpr_event_count": len(bundle["updates"]),
                         "post_run_event_sha256": sha(json.dumps(bundle["updates"], sort_keys=True, separators=(",", ":")).encode()),
                         "source_correlation": bundle.get("source_correlation")}
    }
    path = out / "factory-state.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def make_io(path: Path, bundle: dict, count: int) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "cycles", "host_pc", *[f"lane{i}" for i in range(8)], "reference_left", "reference_right"])
        for inp, out in zip(bundle["inputs"][:count], bundle["outputs"][:count]):
            w.writerow([inp["frame"], inp["cycles"], inp["pc"], *inp["lanes"], out["lanes"][2], out["lanes"][3]])


def make_updates(path: Path, bundle: dict, count: int) -> None:
    end = bundle["run_frame"] + count
    chosen = [u for u in bundle["updates"] if u["boundary_frame"] < end]
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["boundary_frame", "event_id", "cpu_cycles", "dsp_frame", "host_pc", "index", "value"])
        for u in chosen:
            w.writerow([u["boundary_frame"], u["event_id"], u["cycles"], u["frame"], u["pc"],
                        f'{u["address"]:02x}', f'{u["value"]:06x}'])


def compare_outputs(engine_csv: Path, bundle: dict) -> dict:
    with engine_csv.open(newline="") as f:
        rows = list(csv.DictReader(f))
    report = {}
    for n in bundle.get("windows", WINDOWS):
        native_os = {"mismatches": 0, "first": None,
                     "per_channel": {k: {"mismatches": 0, "peak_absolute_error": 0, "sum_squared_error": 0}
                                     for k in ("SER1L", "SER1R")}}
        mame_os = {"mismatches": 0, "first": None,
                   "per_channel": {k: {"mismatches": 0, "peak_absolute_error": 0, "sum_squared_error": 0}
                                   for k in ("SER1L", "SER1R")}}
        native_mame = {"mismatches": 0, "first": None}
        for i in range(n):
            row = rows[i]; ref = bundle["outputs"][i]
            for engine, acc in (("native", native_os), ("mame", mame_os)):
                for lane, name in ((2, "SER1L"), (3, "SER1R")):
                    actual = int(row[f"{engine}{lane}"]); expected = ref["lanes"][lane]
                    if actual != expected:
                        err = actual - expected
                        acc["mismatches"] += 1
                        acc["per_channel"][name]["mismatches"] += 1
                        acc["per_channel"][name]["peak_absolute_error"] = max(
                            acc["per_channel"][name]["peak_absolute_error"], abs(err))
                        acc["per_channel"][name]["sum_squared_error"] += err * err
                        if acc["first"] is None:
                            acc["first"] = {"index": i, "absolute_frame": ref["frame"], "channel": name,
                                             "difference": actual - expected}
            for lane in range(8):
                x, y = int(row[f"native{lane}"]), int(row[f"mame{lane}"])
                if x != y:
                    native_mame["mismatches"] += 1
                    if native_mame["first"] is None:
                        native_mame["first"] = {"index": i, "absolute_frame": ref["frame"], "lane": lane}
        for acc in (native_os, mame_os):
            for stats in acc["per_channel"].values():
                stats["rms_error"] = (stats.pop("sum_squared_error") / n) ** 0.5
        report[str(n)] = {"native_vs_os": native_os, "mame_vs_os": mame_os,
                          "native_vs_mame_all_lanes": native_mame,
                          "sample_exact": native_os["mismatches"] == 0 and mame_os["mismatches"] == 0}
    return report


def compare_instruction_traces(native_path: Path, mame_path: Path) -> dict:
    def parse(path: Path) -> list[tuple[str, ...]]:
        with path.open(newline="") as f:
            return [tuple(row) for row in csv.reader(f)]
    native, mame = parse(native_path), parse(mame_path)
    for i, (left, right) in enumerate(zip(native, mame)):
        if left == right:
            continue
        if left[0] == right[0] == "RQ":
            return {"event_index": i, "event_type": "RAM request", "pc": int(left[2], 16),
                    "native_request_address": int(left[5], 16), "mame_request_address": int(right[5], 16),
                    "request_addresses_differ": left[5] != right[5]}
        if left[0] == right[0] == "RR":
            return {"event_index": i, "event_type": "RAM read", "pc": int(left[2], 16),
                    "read_addresses_differ": left[4] != right[4], "read_data_differ": left[5] != right[5]}
        return {"event_index": i, "event_type": "instruction trace event", "native_event": left[0], "mame_event": right[0]}
    if len(native) != len(mame):
        return {"event_index": min(len(native), len(mame)), "event_type": "trace length", "native_events": len(native), "mame_events": len(mame)}
    return {"event_index": None, "event_type": "no internal difference within selected frame"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("profile", choices=sorted(PROFILES))
    p.add_argument("manifest", type=Path)
    p.add_argument("reference_root", type=Path, help="private root with boot-a/boot-b RUN captures")
    p.add_argument("--run-frame", required=True, type=int)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--diagnostic-frame", type=int, help="absolute DSP frame for one-frame instruction tracing")
    a = p.parse_args(); profile = PROFILES[a.profile]
    out = a.out.expanduser().resolve()
    if out == ROOT or ROOT in out.parents:
        p.error("all state-bearing replay output must remain outside the checkout")
    out.mkdir(parents=True, exist_ok=True)
    gate = subprocess.run([sys.executable, str(ROOT / "tools/audio_validation/factory_manifest.py"),
                           str(a.manifest.resolve(strict=True)), "--require-replay-ready"], capture_output=True, text=True)
    if gate.returncode:
        raise SystemExit("factory manifest validation failed; payload values withheld")
    ref = a.reference_root.resolve(strict=True)
    bundles = [read_run(ref / f"boot-{which}", a.run_frame, WINDOWS[-1], profile) for which in ("a", "b")]
    if bundles[0]["snapshot"].read_bytes() != bundles[1]["snapshot"].read_bytes():
        raise SystemExit("fresh ROM reference RUN checkpoints differ")
    if event_fingerprint(bundles[0]) != event_fingerprint(bundles[1]):
        raise SystemExit("fresh ROM reference startup/load event histories differ")
    if bundles[0]["updates"] != bundles[1]["updates"]:
        raise SystemExit("fresh ROM reference post-RUN firmware histories differ")
    if bundles[0]["host_wav"].read_bytes() != bundles[1]["host_wav"].read_bytes() or bundles[0]["host_map"].read_bytes() != bundles[1]["host_map"].read_bytes():
        raise SystemExit("fresh ROM reference host WAV or source-position map differs")
    for key in ("inputs", "outputs"):
        if bundles[0][key] != bundles[1][key]:
            raise SystemExit("fresh ROM reference serial traces differ")
    b = bundles[0]
    man = json.loads(a.manifest.read_text())
    if man.get("provenance", {}).get("effect_id") != profile["effect_id"] or man.get("provenance", {}).get("effect_name") != profile["effect_name"]:
        raise SystemExit("manifest effect identity does not match selected profile")
    if man["program"]["sha256"] != sha(b["program"]) or man["program"]["active_words"] != profile["active_words"]:
        raise SystemExit("manifest source image does not match observed checkpoint")
    source_gate = man.get("observed_run", {}).get("source_correlation")
    if profile.get("program_sha256") and (not source_gate or
            source_gate.get("active_instruction_matches") != profile["active_words"] or
            source_gate.get("paired_gpr_initializers") != profile["source_paired_gprs"] or
            source_gate.get("source_aliases") != profile["source_aliases"] or
            source_gate.get("program_sha256") != profile["program_sha256"]):
        raise SystemExit("ROM effect source-to-run correlation gate is missing or incomplete")
    if man["gpr"]["sha256"] != b["capture"]["registers"]["gpr_sha256"] or man["special_registers"]["sha256"] != b["capture"]["registers"]["special_sha256"]:
        raise SystemExit("manifest register payloads do not match observed RUN checkpoint")
    if abs(float(man["sample_rate_hz"]) - float(profile["dsp_rate_hz"])) > 0.51:
        raise SystemExit("manifest clock does not match selected effect profile")
    observed_rt = b["capture"]["runtime"]
    manifest_mem = man["memory"]
    for field in ("memsiz", "memmask", "memincrement", "memshift"):
        if int(manifest_mem[field]) != int(observed_rt["memory_configuration"][field]):
            raise SystemExit(f"manifest {field} does not match observed RUN state")
    for key, field in (("DLENGTH", "dlength"), ("ABASE", "abase"), ("BBASE", "bbase"), ("DBASE", "dbase")):
        if int(manifest_mem[field]) != int(observed_rt["delay_configuration"][key]):
            raise SystemExit(f"manifest {key} does not match observed RUN state")
    if int(manifest_mem["sigreg"]) != int(observed_rt["signal_configuration"]["SIGREG"]):
        raise SystemExit("manifest SIGREG does not match observed RUN state")
    if (man["dram"].get("mode") != "zeroed" or
            int(man["dram"]["word_count"]) != int(observed_rt["dram_words"]) or
            (man["dram"].get("sha256") and man["dram"]["sha256"] != observed_rt["dram_sha256"]) or
            observed_rt["dram_nonzero_words"] != 0):
        raise SystemExit("manifest DRAM image does not match zeroed observed RUN state")
    if int(man["serial"]["host_serial"]) != profile["host_serial"]:
        raise SystemExit("manifest serial mode does not match observed run profile")

    exe = out / "factory-boundary-replay"
    sources = [ROOT / "src/es5510.cpp", ROOT / "third_party/trollfx_mame_es5510/mame_es5510_standalone.cpp",
               ROOT / "tools/audio_validation/factory_boundary_replay.cpp"]
    subprocess.run(["c++", "-std=c++17", "-O2", "-Isrc", "-Ithird_party/trollfx_mame_es5510",
                    *map(str, sources), "-o", str(exe)], cwd=ROOT, check=True)
    run_dir = out / "32768"; run_dir.mkdir(exist_ok=True)
    io = run_dir / "serial-input.csv"; updates = run_dir / "firmware-events.csv"
    make_io(io, b, WINDOWS[-1]); make_updates(updates, b, WINDOWS[-1])
    output = run_dir / "engine-output.csv"; state = run_dir / "register-boundaries.csv"
    command = [str(exe), str(b["snapshot"]), str(updates), str(io), str(output), str(state)]
    if a.diagnostic_frame is not None:
        if not a.run_frame <= a.diagnostic_frame < a.run_frame + WINDOWS[-1]:
            p.error("diagnostic frame lies outside the captured replay interval")
        command += [str(a.diagnostic_frame), str(run_dir / "first-instruction")]
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit("standalone engines failed: " + proc.stderr.strip())
    comparisons = compare_outputs(output, b)
    summary = {"schema": "trollfx-es5510-factory-replay-v1", "profile": a.profile,
               "effect": f'{profile["effect_id"]} {profile["effect_name"]}', "os_version": "3.53",
               "run_frame": a.run_frame, "instruction_image_sha256": sha(b["program"]),
               "checkpoint_sha256": b["capture"]["file_sha256"],
               "fresh_boot_checkpoints_identical": True,
               "load_transaction": {"instruction_commits": profile["instruction_commits"],
                                    "unique_instruction_addresses": profile["unique_instruction_addresses"],
                                    "end_word": profile["end_word"], "register_commits": profile["register_commits"],
                                    "transaction_matches_checkpoint": True},
               "source_correlation": man.get("observed_run", {}).get("source_correlation"),
               "clock": {"dsp_hz": float(b["clock"]["dsp_rate_hz"]),
                         "host_hz": int(float(b["clock"]["host_output_rate_hz"])),
                         "active_voices": int(b["clock"]["active_voices"]),
                         "serial_route": b["clock"]["serial_route"]},
               "post_run_firmware_events": len(b["updates"]), "post_run_event_history_identical": True,
               "startup_event_history_identical": True, "initial_input_hash": sha(b"".join(
                   struct.pack("<hh", *x["lanes"][4:6]) for x in b["inputs"])),
               "host_reference": {"mapping_validated_against_wav": True,
                                  "mapped_host_frames": b["host_mapped_frames"],
                                  "two_boot_wav_and_mapping_identical": True},
               "windows": comparisons, "runner": proc.stderr.strip(),
               "host_wav_comparison": "OS source mapping and repeatability verified; no standalone DAC WAV candidate was produced",
               "payload_values_disclosed": False}
    with state.open(newline="") as f:
        state_rows = [r for r in csv.DictReader(f) if int(r["mismatching_registers"]) > 0]
    summary["earliest_native_mame_register_state_difference"] = (
        {"phase": state_rows[0]["phase"], "frame": int(state_rows[0]["boundary_frame"]),
         "mismatching_register_count": int(state_rows[0]["mismatching_registers"]),
         "first_register_address": int(state_rows[0]["first_address"])} if state_rows else None)
    if a.diagnostic_frame is not None:
        summary["instruction_trace"] = compare_instruction_traces(
            run_dir / "first-instruction.native.csv", run_dir / "first-instruction.mame.csv")
        summary["instruction_trace"]["absolute_frame"] = a.diagnostic_frame
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if all(v["sample_exact"] for v in comparisons.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
