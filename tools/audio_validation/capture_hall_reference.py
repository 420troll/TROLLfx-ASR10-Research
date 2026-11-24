#!/usr/bin/env python3
"""Capture and bundle a private, reproducible OS 3.53 HALL audio reference.

The emulator is run twice from fresh process state. Raw logs, snapshots, WAVs,
serial samples, and bundle JSON must stay outside the repository.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "tools/audio_validation/hall_replay_verify.py"
FRAME_RE = re.compile(r"ESPPFRAME kind=(input|output) index=(\d+) frame=(\d+) cycles=(\d+) host_pc=([0-9a-fA-F]+) serial=([0-9a-fA-F]+) lanes=([0-9a-fA-F,]+)")
PHASE_RE = re.compile(r"ESPPHASE kind=([a-z0-9_]+)\s+(.*)$")
AUDIO_RE = re.compile(r"ESPAUDIO kind=clock\s+(.*)$")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def kv(text: str) -> dict[str, str]:
    return dict(re.findall(r"([a-z_]+)=([^\s]+)", text))


def signed16(v: str) -> int:
    n = int(v, 16) & 0xffff
    return n - 0x10000 if n & 0x8000 else n


def parse_session(path: Path, start_frame: int, frames: int) -> dict:
    lines = path.read_text(errors="replace").splitlines()
    audio = []
    for line_no, line in enumerate(lines):
        m = FRAME_RE.search(line)
        if m:
            kind, index, frame, cycles, pc, serial, lanes = m.groups()
            frame = int(frame)
            if start_frame <= frame < start_frame + frames:
                raw = [int(x, 16) for x in lanes.split(",")]
                if len(raw) != 8:
                    raise ValueError(f"expected eight serial lanes at log line {line_no+1}")
                audio.append({"kind": kind, "index": int(index), "frame": frame,
                              "cycles": int(cycles), "host_pc": int(pc, 16),
                              "host_serial": int(serial, 16), "lanes": [signed16(f"{v:04x}") for v in raw],
                              "log_sequence": line_no + 1})
    by_kind = {kind: [r for r in audio if r["kind"] == kind] for kind in ("input", "output")}
    expected_frames = list(range(start_frame, start_frame + frames))
    for kind, rows in by_kind.items():
        if [r["frame"] for r in rows] != expected_frames:
            raise ValueError(f"{kind} serial trace is incomplete, duplicated, or out of order")

    phases = []
    clock = None
    for i, line in enumerate(lines):
        m = PHASE_RE.search(line)
        if m:
            d = kv(m.group(2)); d["kind"] = m.group(1); d["log_sequence"] = i + 1
            if d["kind"] in ("pa4_halt_assert", "host_halt_pipeline_reset", "host_dram_clear",
                              "instruction_upload_start", "program_upload_summary", "pa4_run_release",
                              "run_start", "run_snapshot", "first_instruction"):
                phases.append(d)
        am = AUDIO_RE.search(line)
        if am:
            d = kv(am.group(1))
            if int(d.get("frame", -1)) == start_frame:
                clock = d
    run_starts = [p for p in phases if p["kind"] == "run_start" and p.get("frame") == str(start_frame)]
    snapshots = [p for p in phases if p["kind"] == "run_snapshot" and p.get("frame") == str(start_frame)]
    if len(run_starts) != 1 or len(snapshots) != 1 or not clock:
        raise ValueError("missing unique HALL RUN/checkpoint/pipeline-reset/clock event evidence")
    run_start = run_starts[0]
    resets = [p for p in phases if p["kind"] == "host_halt_pipeline_reset" and
              int(p.get("frame", -1)) <= start_frame and int(p["log_sequence"]) < int(run_start["log_sequence"])]
    if not resets:
        raise ValueError("selected RUN has no preceding pipeline reset acknowledgement")
    upload = [p for p in phases if p["kind"] == "program_upload_summary"]
    upload = [p for p in upload if p.get("frame") == str(start_frame)]
    if len(upload) != 1 or int(upload[0].get("unique_addresses", -1)) != 89 or int(upload[0].get("first_end", -1)) != 88:
        raise ValueError("selected run is not the expected 89-word HALL transaction")
    timeline_kinds = ("pa4_halt_assert", "host_halt_pipeline_reset", "host_dram_clear",
                      "instruction_upload_start", "program_upload_summary", "pa4_run_release",
                      "run_start", "run_snapshot", "first_instruction")
    timeline = []
    first_instructions = [p for p in phases if p["kind"] == "first_instruction" and
                          int(p.get("frame", -1)) == start_frame]
    timeline_end = int(first_instructions[0]["log_sequence"]) if first_instructions else int(snapshots[0]["log_sequence"])
    for kind in timeline_kinds:
        candidates = [p for p in phases if p["kind"] == kind and int(p.get("log_sequence", 0)) <= timeline_end]
        item = candidates[-1] if candidates else None
        if item:
            timeline.append({k: item[k] for k in ("kind", "frame", "cycles", "host_pc", "pc", "log_sequence") if k in item})
    for kind, rows in (("first_input_frame", by_kind["input"]), ("first_output_frame", by_kind["output"])):
        x = rows[0]
        timeline.append({"kind": kind, "frame": x["frame"], "cycles": x["cycles"],
                         "host_pc": f'{x["host_pc"]:06x}', "log_sequence": x["log_sequence"]})
    return {"input": by_kind["input"], "output": by_kind["output"], "timeline": timeline, "run_start": run_start,
            "snapshot_event": snapshots[0], "pipeline_reset": resets[-1], "upload": upload[0],
            "clock": clock, "lines": lines}


def event_fingerprint(lines: list[str], reset_sequence: int, run_sequence: int) -> str:
    ordered = [line for i, line in enumerate(lines, 1) if reset_sequence <= i <= run_sequence and
               ("ESPPHASE " in line or "ESPHOST " in line or "ESPIO " in line)]
    return sha(("\n".join(ordered) + "\n").encode())


def inspect_snapshot(path: Path) -> dict:
    p = subprocess.run([sys.executable, str(ROOT/"tools/esp_capture.py"), str(path)],
                       capture_output=True, text=True, check=True)
    d = json.loads(p.stdout)
    return {"capture_sha256": d["file_sha256"], "program": d["program"],
            "register_hashes": d["registers"],
            "runtime": {"control": d["runtime"]["control"],
                        "memory_configuration": d["runtime"]["memory_configuration"],
                        "dram_words": d["runtime"]["dram_words"],
                        "dram_sha256": d["runtime"]["dram_sha256"],
                        "dram_nonzero_words": d["runtime"]["dram_nonzero_words"],
                        "delay_configuration": d["runtime"]["delay_configuration"],
                        "signal_configuration": d["runtime"]["signal_configuration"]},
            "pipeline": {"halt_reset_acknowledged": True,
                         "snapshot_contains_complete_in_flight_pipeline": False,
                         "pipeline_reset_event": "observed before RUN; full ALU/MAC/RAM/DOL state is not serialized"}}


def read_wav16(path: Path) -> tuple[int, list[tuple[int, int]]]:
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 2 or w.getsampwidth() != 2:
            raise ValueError("CLI host reference must be stereo PCM16 WAV")
        rate, n = w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    vals = struct.unpack("<" + "h" * (len(raw)//2), raw)
    return rate, list(zip(vals[::2], vals[1::2]))


def write_wav16(path: Path, rate: int, samples: list[tuple[int, int]]) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<hh", *s) for s in samples))


def select_host_window_rows(rows: list[dict], start_frame: int, frame_count: int) -> list[dict]:
    """Select by the logged source-time coordinate; never shift by audio correlation."""
    end = start_frame + frame_count
    return [r for r in rows if start_frame <= float(r["source_dsp_frame_position"]) < end]


def bundle_run(run_dir: Path, start_frame: int, frames: int, boot_id: str) -> dict:
    log = run_dir / "session.log"
    parsed = parse_session(log, start_frame, frames)
    snapshot_path = run_dir / "snapshots" / f"run-frame-{start_frame}.esp"
    if not snapshot_path.is_file():
        raise ValueError("RUN-boundary state snapshot is missing")
    state = inspect_snapshot(snapshot_path)
    if state["capture_sha256"] != sha(snapshot_path.read_bytes()):
        raise ValueError("snapshot digest is inconsistent")
    host_map_path = run_dir / "host-output-map.csv"
    host_rows = list(csv.DictReader(host_map_path.open(newline="")))
    if not host_rows:
        raise ValueError("host output source-position map is empty")
    host_rate, full_host = read_wav16(run_dir / "render.wav")
    if host_rate != 44100:
        raise ValueError(f"host renderer returned {host_rate}, expected 44100 Hz")
    host_rows_checked = []
    for row in host_rows:
        index = int(row["host_frame_index"])
        source_frame = float(row["source_dsp_frame_position"])
        l, r = full_host[index]
        if [l, r] != [int(row["left_pcm16"]), int(row["right_pcm16"])]:
            raise ValueError(f"host output trace does not match WAV at host frame {index}")
        host_rows_checked.append({"host_frame_index": index, "source_dsp_frame_position": source_frame,
                                  "emission_dsp_frame": int(row["emission_dsp_frame"])})
    host_windows = {}
    for n in (256, 4096, 32768):
        rows_n = select_host_window_rows(host_rows_checked, start_frame, n)
        samples_n = [full_host[row["host_frame_index"]] for row in rows_n]
        filename = f"host-window-{n}.wav"
        write_wav16(run_dir / filename, host_rate, samples_n)
        host_windows[str(n)] = {"wav_file": filename, "wav_sha256": sha((run_dir/filename).read_bytes()),
                                "host_frames": len(samples_n)}

    dsp_csv = run_dir / "dsp-serial-all-lanes.csv"
    with dsp_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_index", "absolute_dsp_frame", "kind", "host_cycles", "host_pc", "host_serial",
                    *[f"lane{i}_s16" for i in range(8)]])
        for kind in ("input", "output"):
            for x in parsed[kind]:
                w.writerow([x["frame"]-start_frame, x["frame"], kind, x["cycles"], f'{x["host_pc"]:06x}',
                            f'{x["host_serial"]:02x}', *x["lanes"]])

    raw_lines = parsed["lines"]
    fw_hash = event_fingerprint(raw_lines, int(parsed["pipeline_reset"]["log_sequence"]),
                                int(parsed["run_start"]["log_sequence"]))
    input_rows, output_rows = parsed["input"], parsed["output"]
    raw_in = b"".join(struct.pack("<hh", x["lanes"][4], x["lanes"][5]) for x in input_rows)
    rate = float(parsed["clock"]["dsp_rate_hz"])
    meta = {"schema": "trollfx-es5510-hall-reference-capture-v2",
            "boot_id": boot_id, "effect": "ROM-01 HALL REVERB", "os_version": "3.53",
            "replay": {"input_sha256": sha(raw_in), "initial_state_sha256": state["capture_sha256"],
                       "firmware_events_sha256": fw_hash,
                       "alignment": f"DSP sample index 0 = absolute ESP frame {start_frame}; no shifting; input SER2 L/R, output SER1 L/R"},
            "dsp_rate_hz": rate, "host_rate_hz": host_rate,
            "clock": {k: parsed["clock"].get(k) for k in ("otto_clock_hz", "dsp_rate_hz", "active_voices", "host_output_rate_hz", "dac_model", "serial_route", "direct_mask")},
            "stimulus": {"generator": "ASR_TEST_SINE", "frequency_hz": 440, "amplitude": 0.25,
                         "phase_origin": "0 at fresh process start", "formula": "int32(sin(phase)*amplitude*524287); phase += 2*pi*f/OTTO_sample_rate; then to16",
                         "route_environment": "-1,-1,1,-1,0",
                         "captured_dsp_input_lanes": ["SER2L", "SER2R"], "input_hash_format": "ordered signed PCM16 little-endian stereo bytes"},
            "initial_state": state,
            "timeline": parsed["timeline"],
            "firmware_load": {"instruction_commits": int(parsed["upload"]["commits"]),
                              "unique_instruction_addresses": int(parsed["upload"]["unique_addresses"]),
                              "first_end_word": int(parsed["upload"]["first_end"]),
                              "gpr_spr_commit_count": int(parsed["upload"]["gpr_commits"]),
                              "ordered_event_sha256": fw_hash},
            "host_output": {"wav_file": "render.wav", "wav_sha256": sha((run_dir/"render.wav").read_bytes()),
                            "windows": host_windows,
                            "host_map_file": "host-output-map.csv", "mapped_host_frames": len(host_rows_checked),
                            "dac_noise_seed": 22222,
                            "dac_weight_seed_formula": "1541 + channel*977 + attempt*31",
                            "source_mapping": "DacOut t_next zero-origin coordinate + 1 = absolute ESP frame position; output values are post-TDA1541A model/resampler and match render.wav PCM16"},
            "coverage": {"dsp_frames": frames, "dsp_serial_file": dsp_csv.name,
                         "input_rows": len(input_rows), "output_rows": len(output_rows),
                         "host_window_frames": len(host_rows_checked)},
            "payloads_private": True}
    refs = {}
    for n in (256, 4096, 32768):
        if frames < n: continue
        input_hash_n = sha(b"".join(struct.pack("<hh", x["lanes"][4], x["lanes"][5])
                                     for x in input_rows[:n]))
        replay_gate = {**meta["replay"], "input_sha256": input_hash_n}
        trace = {"schema": "trollfx-es5510-hall-replay-v1", "trace_id": f"os353-hall-{boot_id}-{n}",
                 "replay": replay_gate, "dsp_rate_hz": rate, "host_rate_hz": host_rate,
                 "dsp_serial_samples": [{"index": i, "left": output_rows[i]["lanes"][2],
                                          "right": output_rows[i]["lanes"][3]} for i in range(n)],
                 "input_samples": [{"index": i, "left": input_rows[i]["lanes"][4],
                                    "right": input_rows[i]["lanes"][5]} for i in range(n)],
                 "metadata": {"absolute_start_frame": start_frame, "frame_count": n,
                              "initial_state": state, "firmware_load": meta["firmware_load"],
                              "stimulus": meta["stimulus"], "host_output": {
                                  "host_rate_hz": host_rate, "wav_file": meta["host_output"]["windows"][str(n)]["wav_file"],
                                  "wav_sha256": meta["host_output"]["windows"][str(n)]["wav_sha256"],
                                  "host_frames": meta["host_output"]["windows"][str(n)]["host_frames"],
                                  "dac_noise_seed": meta["host_output"]["dac_noise_seed"],
                                  "dac_weight_seed_formula": meta["host_output"]["dac_weight_seed_formula"],
                                  "source_mapping": meta["host_output"]["source_mapping"]}}}
        trace_path = run_dir / f"reference-{n}.json"
        trace_path.write_text(json.dumps(trace, separators=(",", ":")) + "\n")
        refs[str(n)] = {"path": trace_path.name, "sha256": sha(trace_path.read_bytes())}
    meta["reference_traces"] = refs
    (run_dir/"capture-metadata.json").write_text(json.dumps(meta, indent=2)+"\n")
    return meta


def command_args(cli: Path, roms: Path, disk: Path, run_dir: Path, seconds: float,
                 frame: int, frames: int) -> list[str]:
    args = [str(cli), "--roms", str(roms), "--disk", str(disk), "--seconds", str(seconds),
            "--panel-log", "--trace-esp-io", "--wav", str(run_dir/"render.wav"),
            "--button", "15:7:1", "--button", "15.2:7:0"]
    value = 8
    when = 16.0
    while value <= 79:
        args += ["--analog-at", f"{when:.3f}:5:{value}"]
        when += 0.15; value += 1
    return args


def run_boot(cli: Path, roms: Path, disk: Path, out: Path, boot: str,
             seconds: float, frame: int, frames: int) -> dict:
    run_dir = out / boot
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir/"snapshots").mkdir()
    env = os.environ.copy()
    env.update({"ASR_TEST_SINE": "440:0.25", "ASR_ROUTE": "-1,-1,1,-1,0",
                "ESP_PIPELOG": "1", "ESP_HOSTLOG": "1", "ESP_FRAMELOG": str(frames),
                "ESP_FRAMELOG_START_FRAME": str(frame), "ESP_RUN_SNAPSHOT_FRAME": str(frame),
                "ESP_RUN_SNAPSHOT_DIR": str(run_dir/"snapshots"),
                "ASR_HOST_PCM_TRACE": str(run_dir/"host-output-map.csv"),
                "ASR_HOST_PCM_START_FRAME": str(frame), "ASR_HOST_PCM_FRAMES": str(frames)})
    cmd = command_args(cli, roms, disk, run_dir, seconds, frame, frames)
    with (run_dir/"session.log").open("wb") as log:
        p = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError(f"emulator boot {boot} exited {p.returncode}; inspect private session.log")
    return bundle_run(run_dir, frame, frames, boot)


def compare_pair(out: Path) -> dict:
    sys.path.insert(0, str(ROOT))
    # The verifier is intentionally imported from the repository's independent implementation.
    import importlib.util
    spec = importlib.util.spec_from_file_location("hall_replay_verify", VERIFIER)
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    a, b = out/"boot-a", out/"boot-b"
    results = {}
    for n in (256, 4096, 32768):
        result = verifier.verify(a/f"reference-{n}.json", b/f"reference-{n}.json")
        results[str(n)] = result["factory_windows"][str(n)]
    host_full = verifier.compare_wavs(a/"render.wav", b/"render.wav")
    host_windows = {str(n): verifier.compare_wavs(a/f"host-window-{n}.wav", b/f"host-window-{n}.wav")
                    for n in (256, 4096, 32768)}
    report = {"schema": "trollfx-es5510-hall-capture-repeatability-v2", "dsp_windows": results,
              "host_output_full_wav": host_full, "host_output_hall_windows": host_windows,
              "comparison_scope": "two fresh OS 3.53 boots; this establishes capture repeatability only"}
    (out/"repeatability.json").write_text(json.dumps(report, indent=2)+"\n")
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roms", type=Path, required=True, help="private OS 3.53 ROM directory")
    p.add_argument("--disk", type=Path, required=True, help="private OS 3.53 disk image")
    p.add_argument("--out", type=Path, required=True, help="private output directory outside this checkout")
    p.add_argument("--cli", type=Path, help="existing headless CLI; builds it if omitted")
    p.add_argument("--run-frame", type=int, default=855973)
    p.add_argument("--frames", type=int, choices=(256, 4096, 32768), default=32768)
    p.add_argument("--seconds", type=float, default=28.5)
    a = p.parse_args()
    out = a.out.expanduser().resolve()
    if out == ROOT or ROOT in out.parents:
        p.error("private capture output must be outside the repository")
    if not a.roms.is_dir() or not a.disk.is_file():
        p.error("private ROM directory or OS disk is missing")
    out.mkdir(parents=True, exist_ok=False)
    if a.cli:
        cli = a.cli.resolve(strict=True)
    else:
        subprocess.run(["sh", str(ROOT/"tools/build_research_cli.sh")], cwd=ROOT, check=True)
        cli = ROOT/"build/research-cli/asr10-cli"
    run_boot(cli, a.roms.resolve(), a.disk.resolve(), out, "boot-a", a.seconds, a.run_frame, a.frames)
    run_boot(cli, a.roms.resolve(), a.disk.resolve(), out, "boot-b", a.seconds, a.run_frame, a.frames)
    report = compare_pair(out)
    print(json.dumps(report, indent=2))
    return 0 if all(v["samples_equal"] for v in report["dsp_windows"].values()) and report["host_output_full_wav"]["samples_equal"] and all(v["samples_equal"] for v in report["host_output_hall_windows"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
