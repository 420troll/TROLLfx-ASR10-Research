#!/usr/bin/env python3
"""Strictly gate and compare OS HALL serial samples against standalone adapters.

Private inputs and reports should be kept outside the checkout. Candidate JSON
uses trollfx-es5510-factory-candidate-v1; legacy native/MAME engine-comparison
CSVs from replay_hall.cpp can be selected with --candidate-format engine-csv.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import wave
from pathlib import Path

from hall_replay_verify import compare_samples

WINDOWS = (256, 4096, 32768)
SCHEMA = "trollfx-es5510-factory-candidate-v1"
DSP_RATE = 29761.89453125  # Observed ROM-01 HALL rate; compatibility only, never a ROM-02 assumption.


def _require(obj: dict, path: str):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur or cur[part] is None:
            raise ValueError(f"required evidence missing: {path}")
        cur = cur[part]
    return cur


def host_mapping_digest(path: Path) -> str:
    with path.open(newline="") as f:
        return host_mapping_digest_rows(list(csv.DictReader(f)))


def host_mapping_digest_rows(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update(f'{int(row["host_frame_index"])},{float(row["source_dsp_frame_position"]):.12f},'
                 f'{int(row["emission_dsp_frame"])}\n'.encode())
    return h.hexdigest()


def measure_event_trace(path: Path, start_frame: int, end_frame: int) -> dict:
    lines = path.read_text(errors="strict").splitlines()
    run_candidates = [i for i, line in enumerate(lines) if "ESPPHASE kind=run_start " in line and
                      re.search(rf"\bframe={start_frame}(?:\s|$)", line)]
    if len(run_candidates) != 1:
        raise ValueError("candidate event trace lacks a unique selected RUN marker")
    run = run_candidates[0]
    reset_candidates = [i for i, line in enumerate(lines[:run])
                        if "ESPPHASE kind=host_halt_pipeline_reset " in line]
    reset = reset_candidates[-1] if reset_candidates else None
    if reset is None or reset >= run:
        raise ValueError("candidate event trace lacks ordered pipeline-reset and selected RUN markers")
    pre_run = [line for line in lines[reset:run+1]
               if any(tag in line for tag in ("ESPPHASE ", "ESPHOST ", "ESPIO "))]
    execution = []
    host_count = io_count = 0
    for line in lines[reset:]:
        is_host, is_io = "ESPHOST " in line, "ESPIO " in line
        if not (is_host or is_io):
            continue
        m = re.search(r"\bframe=(\d+)", line)
        if not m or int(m.group(1)) > end_frame:
            continue
        execution.append(line)
        host_count += is_host
        io_count += is_io
    def digest(rows): return hashlib.sha256(("\n".join(rows) + "\n").encode()).hexdigest()
    return {"ordered_event_sha256": digest(pre_run), "execution_event_sequence": digest(execution),
            "execution_event_count": len(execution), "host_event_count": host_count,
            "io_event_count": io_count, "last_frame_inclusive": end_frame,
            "_records": {"pre_run": pre_run, "execution": execution}}


def input_sample_digest(samples: list[dict]) -> str:
    raw = bytearray()
    for row in samples:
        left, right = int(row["left"]), int(row["right"])
        if not (-32768 <= left <= 32767 and -32768 <= right <= 32767):
            raise ValueError("candidate input sample exceeds PCM16 range")
        raw.extend(struct.pack("<hh", left, right))
    return hashlib.sha256(raw).hexdigest()


def os_reference(trace_path: Path, metadata_path: Path) -> dict:
    trace = json.loads(trace_path.read_text())
    meta = json.loads(metadata_path.read_text())
    if trace.get("schema") not in ("trollfx-es5510-hall-replay-v1", "trollfx-es5510-factory-replay-v1"):
        raise ValueError("unsupported OS trace schema")
    if meta.get("schema") not in ("trollfx-es5510-hall-reference-capture-v2", "trollfx-es5510-factory-reference-capture-v1"):
        raise ValueError("unsupported OS capture metadata schema")
    effect = _require(meta, "effect")
    if isinstance(effect, str):
        if effect == "ROM-01 HALL REVERB":
            effect = {"id": "ROM-01", "name": "HALL REVERB"}
        else:
            raise ValueError("legacy effect label cannot identify an unsupported factory effect")
    if not isinstance(effect, dict) or not effect.get("id") or not effect.get("name"):
        raise ValueError("factory effect identity must include id and name")
    if trace.get("metadata", {}).get("effect", effect) != effect:
        raise ValueError("OS trace factory effect identity disagrees with capture metadata")
    state = _require(meta, "initial_state")
    reset = _require(state, "pipeline.reset_event")
    timeline_rows = _require(meta, "timeline")
    timeline = {e["kind"]: e for e in timeline_rows}
    for kind in ("run_start", "run_snapshot", "first_instruction"):
        if sum(e.get("kind") == kind for e in timeline_rows) != 1:
            raise ValueError(f"OS timeline must contain one selected {kind} marker")
    run = timeline.get("run_start")
    snapshot = timeline.get("run_snapshot")
    first_instruction = timeline.get("first_instruction")
    if not all((run, snapshot, first_instruction)):
        raise ValueError("OS execution-boundary evidence incomplete")
    runtime = _require(state, "runtime")
    reg_hashes = _require(state, "register_hashes")
    firmware = _require(meta, "firmware_load")
    window_firmware = _require(trace, "metadata.firmware_load")
    trace_state = _require(trace, "metadata.initial_state")
    clock = _require(meta, "clock")
    route = clock.get("serial_route")
    if not route or len(route.split(",")) != 4:
        raise ValueError("OS serial routing evidence incomplete")
    rate = float(trace.get("dsp_rate_hz", 0))
    host_rate = int(trace.get("host_rate_hz", 0))
    if not math.isfinite(rate) or rate <= 0 or not math.isclose(rate, float(clock.get("dsp_rate_hz", 0)), abs_tol=1e-8):
        raise ValueError("OS DSP clock is missing or inconsistent with measured clock evidence")
    if host_rate <= 0 or int(float(clock.get("host_output_rate_hz", 0))) != host_rate:
        raise ValueError("OS host clock evidence is missing or inconsistent")
    if trace.get("replay", {}).get("initial_state_sha256") != state.get("capture_sha256"):
        raise ValueError("OS trace initial-state digest disagrees with RUN snapshot metadata")
    for path in ("capture_sha256", "program.active_program_sha256", "register_hashes.gpr_sha256",
                 "register_hashes.special_sha256", "runtime.dram_sha256"):
        if _require(trace_state, path) != _require(state, path):
            raise ValueError(f"OS trace and capture metadata disagree on initial state: {path}")
    if trace.get("replay", {}).get("firmware_events_sha256") != firmware.get("ordered_event_sha256"):
        raise ValueError("OS trace firmware-event digest disagrees with load metadata")
    if (window_firmware.get("ordered_event_sha256") != firmware.get("ordered_event_sha256") or
            window_firmware.get("instruction_commits") != firmware.get("instruction_commits") or
            window_firmware.get("gpr_spr_commit_count") != firmware.get("gpr_spr_commit_count")):
        raise ValueError("OS per-window firmware history disagrees with capture metadata")
    start = int(_require(trace, "metadata.absolute_start_frame"))
    frame_count = int(_require(trace, "metadata.frame_count"))
    if (int(run["frame"]) != start or int(snapshot["frame"]) != start or
            int(first_instruction["frame"]) != start or
            int(reset.get("frame", start)) >= start or
            int(snapshot["log_sequence"]) >= int(first_instruction["log_sequence"])):
        raise ValueError("OS RUN/reset/snapshot/first-instruction coordinates do not establish the selected boundary")
    event_window = _require(window_firmware, "execution_event_sequence")
    if int(_require(event_window, "last_frame_inclusive")) != start + frame_count - 1:
        raise ValueError("OS firmware-event window does not end at the final captured DSP frame")
    os_events = measure_event_trace(metadata_path.parent / "session.log", start, start + frame_count - 1)
    for key in ("ordered_event_sha256", "execution_event_sequence", "execution_event_count",
                "host_event_count", "io_event_count", "last_frame_inclusive"):
        expected = (firmware.get("ordered_event_sha256") if key == "ordered_event_sha256" else
                    event_window.get("sha256") if key == "execution_event_sequence" else
                    event_window.get("event_count" if key == "execution_event_count" else key))
        if os_events.get(key) != expected:
            raise ValueError(f"OS raw event log disagrees with its metadata: {key}")
    output_samples = trace.get("dsp_serial_samples")
    if not isinstance(output_samples, list) or len(output_samples) != frame_count:
        raise ValueError("OS output frame count disagrees with trace metadata")
    for i, sample in enumerate(output_samples):
        if (sample.get("index") != i or not isinstance(sample.get("left"), int) or
                not isinstance(sample.get("right"), int) or
                not (-32768 <= sample["left"] <= 32767 and -32768 <= sample["right"] <= 32767)):
            raise ValueError("OS output serial frames must be contiguous signed PCM16 stereo")
    input_samples = trace.get("input_samples")
    if not isinstance(input_samples, list) or len(input_samples) != frame_count:
        raise ValueError("OS input serial samples are missing or incomplete")
    input_bytes = bytearray()
    for i, sample in enumerate(input_samples):
        if sample.get("index") != i or not isinstance(sample.get("left"), int) or not isinstance(sample.get("right"), int):
            raise ValueError("OS input serial frames must be contiguous numeric stereo samples")
        if not (-32768 <= sample["left"] <= 32767 and -32768 <= sample["right"] <= 32767):
            raise ValueError("OS input serial sample exceeds PCM16 range")
        input_bytes.extend(struct.pack("<hh", sample["left"], sample["right"]))
    if hashlib.sha256(input_bytes).hexdigest() != trace.get("replay", {}).get("input_sha256"):
        raise ValueError("OS input samples do not match their declared input hash")
    evidence = {
        "input_sha256": _require(trace, "replay.input_sha256"),
        "state": {"program_sha256": _require(state, "program.active_program_sha256"),
                  "gpr_sha256": _require(reg_hashes, "gpr_sha256"),
                  "spr_sha256": _require(reg_hashes, "special_sha256"),
                  "dram_sha256": _require(runtime, "dram_sha256"),
                  "memory_configuration": runtime["memory_configuration"]},
        "pipeline": {"reset_acknowledged": state["pipeline"].get("halt_reset_acknowledged") is True,
                     "alu_pending": int(_require(reset, "alu_pending")),
                     "mac_pending": int(_require(reset, "mac_pending")),
                     "ram_slots_cleared": int(_require(reset, "ram_slots_cleared")),
                     "dol_count": int(_require(reset, "dol_count"))},
        "firmware": {"ordered_event_sha256": _require(trace, "replay.firmware_events_sha256"),
                     "execution_event_sequence": _require(window_firmware, "execution_event_sequence.sha256"),
                     "execution_event_count": int(_require(window_firmware, "execution_event_sequence.event_count")),
                     "host_event_count": int(_require(window_firmware, "execution_event_sequence.host_event_count")),
                     "io_event_count": int(_require(window_firmware, "execution_event_sequence.io_event_count")),
                     "last_frame_inclusive": int(_require(window_firmware, "execution_event_sequence.last_frame_inclusive")),
                     "instruction_commits": int(_require(firmware, "instruction_commits")),
                     "gpr_spr_commit_count": int(_require(firmware, "gpr_spr_commit_count"))},
        "effect": effect,
        "clock": {"dsp_rate_hz": rate, "host_rate_hz": host_rate},
        "routing": {"host_serial": int(_require(runtime, "control.host_serial")),
                    "serial_route": route, "direct_mask": clock.get("direct_mask")},
        "alignment": {"absolute_start_frame": start, "sample_zero_is_frame": start,
                      "input_lanes": ["SER2L", "SER2R"], "output_lanes": ["SER1L", "SER1R"]},
        "boundary": {"run_frame": int(run["frame"]), "snapshot_frame": int(snapshot["frame"]),
                     "first_instruction_frame": int(first_instruction["frame"]),
                     "first_instruction_pc": int(first_instruction["pc"], 16),
                     "snapshot_before_first_instruction": int(snapshot["log_sequence"]) < int(first_instruction["log_sequence"])},
    }
    map_path = metadata_path.parent / _require(meta, "host_output.host_map_file")
    count = frame_count
    with map_path.open(newline="") as f:
        selected_map = [row for row in csv.DictReader(f)
                        if start <= float(row["source_dsp_frame_position"]) < start + count]
    host_n = int(_require(trace, "metadata.host_output.host_frames"))
    if len(selected_map) != host_n:
        raise ValueError("OS mapped host window count does not match its reference trace metadata")
    evidence["host_mapping_sha256"] = host_mapping_digest_rows(selected_map)
    evidence["host_window_frames"] = host_n
    return {"engine": "os353", "evidence": evidence, "samples": output_samples,
            "_event_records": os_events["_records"],
            "trace_id": trace.get("trace_id"), "source": trace_path.name}


def load_candidate(path: Path, kind: str, evidence_path: Path,
                   fmt: str = "json", input_path: Path | None = None,
                   output_serial_port: int | None = None) -> dict:
    evidence_doc = json.loads(evidence_path.read_text())
    evidence = evidence_doc.get("evidence", evidence_doc)
    if fmt == "json":
        doc = json.loads(path.read_text())
        if doc.get("schema") != SCHEMA:
            raise ValueError(f"candidate JSON schema must be {SCHEMA}")
        if doc.get("engine") != kind:
            raise ValueError("candidate engine does not match requested native/mame adapter")
        if doc.get("sample_domain") != "es5510_serial" or doc.get("output_domain") == "host_pcm":
            raise ValueError("candidate DSP samples must identify the separate es5510_serial domain")
        if doc.get("effect") != evidence.get("effect"):
            raise ValueError("candidate factory effect identity does not match evidence")
        samples = doc.get("dsp_serial_samples")
        inputs = doc.get("input_samples")
    else:
        if input_path is None:
            raise ValueError("--candidate-input replay_io CSV is required for engine-csv adapter")
        if output_serial_port not in (0, 1, 2, 3):
            raise ValueError("engine-csv adapter requires an explicit output serial port 0..3")
        samples = []
        last = None
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                frame = int(row["frame"])
                if last is not None and frame != last + 1:
                    raise ValueError("candidate engine CSV has a frame gap or duplicate")
                last = frame
                # Replay V2/V4 engine comparison CSV stores all four ports;
                # factory routing evidence chooses the output port explicitly.
                prefix = f"{kind}{output_serial_port}"
                samples.append({"index": len(samples), "absolute_frame": frame,
                                "left": int(row[prefix + "l"]), "right": int(row[prefix + "r"])})
        inputs = []
        with input_path.open(newline="") as f:
            for row in csv.DictReader(f):
                frame = int(row["frame"])
                if "in_ser2l" in row:
                    left, right = int(row["in_ser2l"]), int(row["in_ser2r"])
                else:
                    left, right = int(row["left"]), int(row["right"])
                inputs.append({"index": len(inputs), "absolute_frame": frame, "left": left, "right": right})
    if not isinstance(samples, list):
        raise ValueError("candidate DSP samples missing")
    if not samples:
        raise ValueError("candidate DSP sample trace is empty")
    start = int(_require(evidence, "alignment.absolute_start_frame"))
    for i, sample in enumerate(samples):
        if sample.get("index") != i or not isinstance(sample.get("left"), int) or not isinstance(sample.get("right"), int):
            raise ValueError("candidate samples require contiguous indexed signed integer stereo frames")
        if "absolute_frame" not in sample or int(sample["absolute_frame"]) != start + i:
            raise ValueError("candidate sample frame does not match declared absolute alignment")
    if not isinstance(inputs, list) or len(inputs) != len(samples):
        raise ValueError("candidate must include the exact input sample stream for every output frame")
    for i, sample in enumerate(inputs):
        if (sample.get("index") != i or not isinstance(sample.get("left"), int) or
                not isinstance(sample.get("right"), int) or int(sample.get("absolute_frame", -1)) != start + i):
            raise ValueError("candidate input samples must be contiguous, numeric, and frame-aligned")
    if input_sample_digest(inputs) != evidence.get("input_sha256"):
        raise ValueError("candidate input samples do not match the declared input hash")
    return {"engine": kind, "evidence": evidence, "samples": samples,
            "input_samples": inputs, "source": path.name}


EVIDENCE_PATHS = (
    "effect.id", "effect.name", "input_sha256", "state.program_sha256", "state.gpr_sha256", "state.spr_sha256",
    "state.dram_sha256", "state.memory_configuration", "pipeline.reset_acknowledged",
    "pipeline.alu_pending", "pipeline.mac_pending", "pipeline.ram_slots_cleared", "pipeline.dol_count",
    "firmware.ordered_event_sha256", "firmware.execution_event_sequence", "firmware.execution_event_count",
    "firmware.host_event_count", "firmware.io_event_count", "firmware.last_frame_inclusive",
    "firmware.instruction_commits", "firmware.gpr_spr_commit_count",
    "clock.dsp_rate_hz", "clock.host_rate_hz", "routing.host_serial", "routing.serial_route",
    "routing.direct_mask", "alignment.absolute_start_frame", "alignment.sample_zero_is_frame",
    "alignment.input_lanes", "alignment.output_lanes", "boundary.run_frame", "boundary.snapshot_frame",
    "boundary.first_instruction_frame", "boundary.first_instruction_pc", "boundary.snapshot_before_first_instruction",
)


def event_brief(line: str | None) -> dict | None:
    if line is None:
        return None
    category = "ESPPHASE" if "ESPPHASE " in line else "ESPHOST" if "ESPHOST " in line else "ESPIO" if "ESPIO " in line else "unknown"
    brief = {"category": category}
    for key in ("kind", "frame", "cycles", "pc", "direction"):
        match = re.search(rf"\b{key}=([^\s]+)", line)
        if match:
            brief[key] = match.group(1)
    return brief


def compare_event_records(reference: dict, candidate: dict) -> dict:
    result = {}
    for stream in ("pre_run", "execution"):
        left = reference.get("_event_records", {}).get(stream, [])
        right = candidate.get("_records", {}).get(stream, [])
        limit = min(len(left), len(right))
        index = next((i for i in range(limit) if left[i] != right[i]), limit if len(left) != len(right) else None)
        result[stream] = {"events_equal": index is None and len(left) == len(right),
                          "os_event_count": len(left), "candidate_event_count": len(right),
                          "first_difference_ordinal": index,
                          "os_event": event_brief(left[index]) if index is not None and index < len(left) else None,
                          "candidate_event": event_brief(right[index]) if index is not None and index < len(right) else None}
    return result


def compare_datasets(reference: dict, candidate: dict, event_diagnostics: dict | None = None) -> dict:
    gates = {}
    for path in EVIDENCE_PATHS:
        try:
            left = _require(reference["evidence"], path)
            right = _require(candidate["evidence"], path)
            equal = left == right
            gates[path] = {"os_reference": left, "candidate": right, "equal": equal}
        except ValueError as exc:
            gates[path] = {"equal": False, "reason": str(exc)}
    # Reset acknowledgement and a known-empty pipeline are mandatory evidence.
    pipe = candidate["evidence"].get("pipeline", {})
    if (pipe.get("reset_acknowledged") is not True or pipe.get("alu_pending") != 0 or
            pipe.get("mac_pending") != 0 or pipe.get("ram_slots_cleared") != 3 or pipe.get("dol_count") != 0):
        gates["pipeline.known_reset_state"] = {"equal": False, "reason": "known reset/empty pipeline evidence required"}
    if not isinstance(candidate["evidence"].get("clock", {}).get("dsp_rate_hz"), (int, float)):
        gates["clock.measured_rate"] = {"equal": False, "reason": "measured candidate DSP rate required"}
    eligible = all(g.get("equal") is True for g in gates.values())
    windows = {}
    for n in WINDOWS:
        if eligible and len(reference["samples"]) >= n and len(candidate["samples"]) >= n:
            windows[str(n)] = compare_samples(reference["samples"], candidate["samples"], n)
            windows[str(n)]["first_divergent_absolute_frame"] = (
                int(reference["evidence"]["alignment"]["absolute_start_frame"]) +
                windows[str(n)]["first_difference"]["index"] if windows[str(n)]["first_difference"] else None)
            windows[str(n)]["channel_metrics"] = channel_metrics(reference["samples"], candidate["samples"], n)
            first = windows[str(n)]["first_difference"]
            windows[str(n)]["divergence_context"] = None if first is None else {
                "absolute_frame": windows[str(n)]["first_divergent_absolute_frame"],
                "os": reference["samples"][first["index"]].get("context"),
                "candidate": candidate["samples"][first["index"]].get("context")}
        else:
            windows[str(n)] = {"status": "not_run", "reason": "all evidence gates must pass and both traces must contain the requested frames"}
    return {"schema": "trollfx-es5510-factory-comparison-report-v1", "candidate_engine": candidate["engine"],
            "eligible": eligible, "comparison_suppressed": not eligible, "gates": gates, "dsp_windows": windows,
            "firmware_event_diagnostics": event_diagnostics,
            "execution_context": "candidate metadata may include instruction/register context keyed by sample index; no context is inferred when absent"}


def channel_metrics(a: list[dict], b: list[dict], n: int) -> dict:
    result = {}
    for channel in ("left", "right"):
        diffs = [a[i][channel] - b[i][channel] for i in range(min(n, len(a), len(b)))]
        mismatch = next((i for i, d in enumerate(diffs) if d), None)
        result[channel] = {"mismatching_frames": sum(d != 0 for d in diffs),
                           "first_difference_index": mismatch,
                           "max_absolute_difference": max((abs(d) for d in diffs), default=0),
                           "rms_difference": math.sqrt(sum(d*d for d in diffs)/len(diffs)) if diffs else None}
    return result


def compare_wavs_gated(reference_wav: Path, candidate_wav: Path, reference: dict, candidate: dict) -> dict:
    if not compare_datasets(reference, candidate)["eligible"]:
        return {"status": "not_run", "reason": "DSP evidence gates failed"}
    if not candidate["evidence"].get("host_mapping_sha256") or candidate["evidence"]["host_mapping_sha256"] != reference["evidence"]["host_mapping_sha256"]:
        return {"status": "not_run", "reason": "identical per-frame host source-time mapping evidence required"}
    def read(path, expected_rate):
        with wave.open(str(path), "rb") as w:
            if w.getnchannels() != 2 or w.getsampwidth() != 2:
                raise ValueError("host WAVs must be stereo PCM16")
            if w.getframerate() != expected_rate:
                raise ValueError("host WAV rate does not match its separately measured host output clock")
            data = w.readframes(w.getnframes())
        vals = struct.unpack("<" + "h" * (len(data)//2), data)
        return [{"index": i, "left": vals[i*2], "right": vals[i*2+1]} for i in range(len(vals)//2)]
    left = read(reference_wav, reference["evidence"]["clock"]["host_rate_hz"])
    right = read(candidate_wav, candidate["evidence"]["clock"]["host_rate_hz"])
    expected_n = reference["evidence"]["host_window_frames"]
    if len(left) != expected_n or len(right) != expected_n or len(right) != int(candidate["evidence"].get("host_window_frames", -1)):
        return {"status": "not_run", "reason": "host WAV frame counts do not match the verified mapped window"}
    return {"domain": "44.1 kHz host PCM16; separate from DSP serial",
            **compare_samples(left, right), "channel_metrics": channel_metrics(left, right, len(left))}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--os-trace", type=Path, required=True)
    p.add_argument("--os-metadata", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--candidate-evidence", type=Path, required=True)
    p.add_argument("--candidate-events", type=Path, required=True)
    p.add_argument("--candidate-input", type=Path,
                   help="replay_io CSV for legacy engine-csv adapter; JSON adapters carry input_samples")
    p.add_argument("--engine", choices=("native", "mame"), required=True)
    p.add_argument("--candidate-format", choices=("json", "engine-csv"), default="json")
    p.add_argument("--output-serial-port", type=int, choices=(0, 1, 2, 3),
                   help="required for engine-csv; port selected from verified factory routing evidence")
    p.add_argument("--os-wav", type=Path)
    p.add_argument("--candidate-wav", type=Path)
    p.add_argument("--candidate-host-map", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    checkout = Path(__file__).resolve().parents[2]
    output_path = a.output.expanduser().resolve()
    if output_path == checkout or checkout in output_path.parents:
        p.error("comparison report must be written outside the checkout")
    if bool(a.os_wav) != bool(a.candidate_wav):
        p.error("--os-wav and --candidate-wav must be supplied together")
    if a.candidate_host_map and not a.os_wav:
        p.error("--candidate-host-map is only valid with host WAV inputs")
    ref = os_reference(a.os_trace, a.os_metadata)
    if a.candidate_format == "json" and a.candidate_input:
        p.error("candidate JSON must carry its own input_samples")
    if a.candidate_format == "engine-csv" and a.output_serial_port is None:
        p.error("--output-serial-port is required for engine-csv")
    candidate = load_candidate(a.candidate, a.engine, a.candidate_evidence,
                               a.candidate_format, a.candidate_input, a.output_serial_port)
    event_evidence = measure_event_trace(a.candidate_events,
                                         int(candidate["evidence"]["alignment"]["absolute_start_frame"]),
                                         int(candidate["evidence"]["alignment"]["absolute_start_frame"]) +
                                         len(candidate["samples"]) - 1)
    for key, measured in event_evidence.items():
        if key == "_records":
            continue
        if candidate["evidence"].get("firmware", {}).get(key) != measured:
            raise ValueError(f"candidate firmware-event sidecar mismatch: {key}")
    event_diagnostics = compare_event_records(ref, event_evidence)
    report = compare_datasets(ref, candidate, event_diagnostics)
    if a.os_wav:
        if not a.candidate_host_map:
            p.error("--candidate-host-map is required with host WAVs")
        measured_map = host_mapping_digest(a.candidate_host_map)
        declared_map = candidate["evidence"].get("host_mapping_sha256")
        if declared_map != measured_map or candidate["evidence"].get("host_window_frames") != int(_require(ref["evidence"], "host_window_frames")):
            report["host_gates"] = {"host_mapping_sha256": {"os_reference": ref["evidence"]["host_mapping_sha256"],
                                                              "candidate_declared": declared_map,
                                                              "candidate_measured": measured_map, "equal": False}}
            report["host_wav"] = {"status": "not_run", "reason": "candidate host source-time mapping evidence failed"}
        else:
            report["host_gates"] = {"host_mapping_sha256": {"equal": True, "digest": measured_map}}
            report["host_wav"] = compare_wavs_gated(a.os_wav, a.candidate_wav, ref, candidate)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    host_ok = "host_wav" not in report or report["host_wav"].get("samples_equal") is True
    return 0 if report["eligible"] and host_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
