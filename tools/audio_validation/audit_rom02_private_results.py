#!/usr/bin/env python3
"""Audit existing private ROM-02 reference and replay artifacts without rerunning captures.

Only redacted measurements are written. All input files and the report must stay
outside the checkout. The audit does not execute or alter either DSP engine.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
from factory_manifest import validate as validate_manifest
from factory_replay_profiles import PROFILES
import esp_capture
import capture_asr10_rom_effects as effect_capture
from replay_factory_from_boundary import WINDOWS, event_fingerprint, read_run

PROFILE_NAME = "rom02-44khz-reverb-v1"
PROFILE = PROFILES[PROFILE_NAME]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def input_hash(frames: list[dict]) -> str:
    return sha(b"".join(struct.pack("<hh", *frame["lanes"][4:6]) for frame in frames))


def event_rows(path: Path) -> list[tuple]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    required = ("boundary_frame", "event_id", "cpu_cycles", "dsp_frame", "host_pc", "index", "value")
    if not rows or any(any(k not in row for k in required) for row in rows):
        raise ValueError("standalone firmware event file is empty or malformed")
    return [(int(r["boundary_frame"]), int(r["event_id"]), int(r["cpu_cycles"]),
             int(r["dsp_frame"]), r["host_pc"].lower(), int(r["index"], 16), int(r["value"], 16)) for r in rows]


def fresh_process_start(path: Path) -> bool:
    with path.open(errors="replace") as f:
        first = next(f, "")
        second = next(f, "")
    return ("ESPPHASE kind=pa4_halt_assert frame=1 " in first and
            "ESPPHASE kind=pa4_run_release frame=1 " in second)


def expected_event_rows(bundle: dict, count: int) -> list[tuple]:
    end = bundle["run_frame"] + count
    return [(u["boundary_frame"], u["event_id"], u["cycles"], u["frame"], u["pc"].lower(),
             u["address"], u["value"])
            for u in bundle["updates"] if u["boundary_frame"] < end]


def audit(reference_root: Path, replay_root: Path, manifest_path: Path,
          corroboration_root: Path | None = None,
          loader_evidence_root: Path | None = None,
          reproducible_replay_binary: Path | None = None,
          selector_sweep_root: Path | None = None) -> dict:
    reference_root = reference_root.resolve(strict=True)
    replay_root = replay_root.resolve(strict=True)
    manifest_path = manifest_path.resolve(strict=True)
    if any(ROOT == p or ROOT in p.parents for p in (reference_root, replay_root, manifest_path)):
        raise ValueError("private inputs must stay outside the repository")

    manifest_status = validate_manifest(manifest_path)
    if not manifest_status["valid"] or not manifest_status["replay_ready"]:
        raise ValueError("existing factory manifest is not replay-ready")
    boots = [read_run(reference_root / f"boot-{x}", 905028, 32768, PROFILE) for x in ("a", "b")]
    a, b = boots
    ref_pair = {
        "checkpoint_equal": a["snapshot"].read_bytes() == b["snapshot"].read_bytes(),
        "startup_events_equal": event_fingerprint(a) == event_fingerprint(b),
        "post_run_events_equal": a["updates"] == b["updates"],
        "input_serial_equal": a["inputs"] == b["inputs"],
        "output_serial_equal": a["outputs"] == b["outputs"],
        "host_wav_equal": a["host_wav"].read_bytes() == b["host_wav"].read_bytes(),
        "host_map_equal": a["host_map"].read_bytes() == b["host_map"].read_bytes(),
        "separate_session_logs": (a["snapshot"].parents[1] / "session.log").resolve() !=
                                 (b["snapshot"].parents[1] / "session.log").resolve(),
    }
    log_a = a["snapshot"].parents[1] / "session.log"
    log_b = b["snapshot"].parents[1] / "session.log"
    ref_pair["session_log_hashes_distinct"] = sha(log_a.read_bytes()) != sha(log_b.read_bytes())
    ref_pair["both_logs_start_at_fresh_emulator_frame_one"] = fresh_process_start(log_a) and fresh_process_start(log_b)
    reset = a["lifecycle"]["reset"]
    reset_values = {k: int(reset.get(k, -1)) for k in
                    ("alu_pending", "mac_pending", "ram_slots_cleared", "dol_count")}
    reset_values["acknowledged"] = True
    reset_gate = reset_values == {"alu_pending": 0, "mac_pending": 0,
                                  "ram_slots_cleared": 3, "dol_count": 0, "acknowledged": True}

    manifest = json.loads(manifest_path.read_text())
    profile_identity = (manifest["provenance"]["effect_id"], manifest["provenance"]["effect_name"])
    source = manifest.get("observed_run", {}).get("source_correlation") or {}
    program_digest = sha(a["program"])
    active_identity_gate = profile_identity == (PROFILE["effect_id"], PROFILE["effect_name"])
    program_gate = (program_digest == PROFILE["program_sha256"] == manifest["program"]["sha256"] ==
                    source.get("program_sha256") and source.get("active_instruction_matches") == 60 and
                    source.get("paired_gpr_initializers") == 58 and source.get("source_aliases") == 1)

    replay_summary_path = replay_root / "summary.json"
    summary = json.loads(replay_summary_path.read_text())
    output_path = replay_root / "32768/engine-output.csv"
    input_path = replay_root / "32768/serial-input.csv"
    updates_path = replay_root / "32768/firmware-events.csv"
    if not all(p.is_file() for p in (output_path, input_path, updates_path)):
        raise ValueError("existing standalone output package is incomplete")
    with output_path.open(newline="") as f:
        outputs = list(csv.DictReader(f))
    with input_path.open(newline="") as f:
        inputs = list(csv.DictReader(f))
    count = 32768
    if len(outputs) != count or len(inputs) != count:
        raise ValueError("existing replay CSVs do not contain 32,768 frames")
    input_match = True
    output_frame_match = True
    native_counts = {str(n): 0 for n in WINDOWS}
    mame_counts = {str(n): 0 for n in WINDOWS}
    first_native = None
    first_mame = None
    for i, (inrow, outrow, osin, osout) in enumerate(zip(inputs, outputs, a["inputs"], a["outputs"])):
        absolute = 905028 + i
        input_match &= int(inrow["frame"]) == absolute == osin["frame"]
        input_match &= [int(inrow[f"lane{x}"]) for x in range(8)] == osin["lanes"]
        output_frame_match &= int(outrow["frame"]) == absolute == osout["frame"]
        output_frame_match &= (int(outrow["reference_left"]) == osout["lanes"][2] and
                               int(outrow["reference_right"]) == osout["lanes"][3])
        for engine, counts in (("native", native_counts), ("mame", mame_counts)):
            mismatch = any(int(outrow[f"{engine}{lane}"]) != osout["lanes"][lane] for lane in range(8))
            if mismatch:
                if engine == "native" and first_native is None:
                    first_native = i
                if engine == "mame" and first_mame is None:
                    first_mame = i
                for n in WINDOWS:
                    if i < n:
                        counts[str(n)] += 1

    replay_events = event_rows(updates_path)
    event_match = replay_events == expected_event_rows(a, count)
    ref_clock = a["clock"]
    clock_routing_gate = (float(ref_clock["dsp_rate_hz"]) == PROFILE["dsp_rate_hz"] and
                          int(float(ref_clock["host_output_rate_hz"])) == PROFILE["host_rate_hz"] and
                          ref_clock["serial_route"] == PROFILE["serial_route"] and
                          int(a["lifecycle"]["run"]["host_serial"], 16) == PROFILE["host_serial"])
    frame_gate = (a["run_frame"] == 905028 and
                  a["lifecycle"]["run"]["seq"] < a["lifecycle"]["snapshot"]["seq"] <
                  a["lifecycle"]["first_instruction"]["seq"] and
                  int(a["lifecycle"]["first_instruction"]["pc"], 16) == 0)
    dram_gate = (a["capture"]["runtime"]["dram_nonzero_words"] == 0 and
                 a["capture"]["runtime"]["dram_words"] == 1_048_576)

    # The session files contain no CLI executable hash, OS ROM hash, or OS disk hash.
    provenance_markers = (b"executable_sha256", b"cli_sha256", b"os_rom_sha256", b"disk_sha256")
    provenance_present = any(marker in log_a.read_bytes().lower() for marker in provenance_markers)
    gates = {
        "rom02_identity": active_identity_gate,
        "source_correlated_program_digest": program_gate,
        "two_run_checkpoint_event_and_audio_repeatability": all(ref_pair[k] for k in
            ("checkpoint_equal", "startup_events_equal", "post_run_events_equal", "input_serial_equal",
             "output_serial_equal", "host_wav_equal", "host_map_equal",
             "both_logs_start_at_fresh_emulator_frame_one")),
        "reset_pipeline_acknowledgement": reset_gate,
        "zeroed_initial_dram": dram_gate,
        "clock_and_serial_routing": clock_routing_gate,
        "absolute_frame_alignment": frame_gate and input_match and output_frame_match,
        "candidate_input_matches_os": input_match,
        "candidate_firmware_events_match_os": event_match,
        "reference_emulator_executable_and_rom_provenance": provenance_present,
    }
    eligible = all(gates.values())
    candidate = {
        "existing_native_binary_sha256_prefix": sha((replay_root / "factory-boundary-replay").read_bytes())[:12]
            if (replay_root / "factory-boundary-replay").is_file() else None,
        "engine_output_sha256_prefix": sha(output_path.read_bytes())[:12],
        "native_exact_fixed_index": first_native is None,
        "native_mismatch_counts_by_window": native_counts,
        "mame_results": (None if not eligible else {"mismatch_counts_by_window": mame_counts,
                                                     "first_difference_index": first_mame}),
        "mame_result_suppressed": not eligible,
        "firmware_update_count": len(replay_events),
    }
    report = {
        "schema": "trollfx-es5510-rom02-independent-audit-v1",
        "effect": "ROM-02 44KHZ REVERB",
        "reference_run_frame": a["run_frame"],
        "reference_frames": count,
        "reference_program_sha256_prefix": program_digest[:12],
        "reference_checkpoint_sha256_prefix": a["capture"]["file_sha256"][:12],
        "reference_startup_event_sha256_prefix": event_fingerprint(a)[:12],
        "reference_input_sha256_prefix": input_hash(a["inputs"])[:12],
        "clock_hz": {"dsp": float(ref_clock["dsp_rate_hz"]),
                     "host": int(float(ref_clock["host_output_rate_hz"]))},
        "serial_route": "input SER2 L/R, output SER1 L/R",
        "two_boot_repeatability": ref_pair,
        "reset_pipeline_counters": reset_values,
        "manifest_valid_replay_ready": bool(manifest_status["replay_ready"]),
        "gates": gates,
        "comparison_eligible": eligible,
        "native_and_mame": candidate,
        "host_dac_candidate_present": False,
        "full_pipeline_state_in_checkpoint": False,
        "reference_executable_provenance": {
            "recorded_in_session_logs": provenance_present,
            "missing": ["emulator CLI executable hash/build ID", "OS ROM image hashes", "OS disk image hash",
                         "per-boot process IDs or invocation receipt"],
        },
        "firmware_event_timing_limit": "post-RUN GPR writes are placed between adjacent frames; no sub-frame execution instant is asserted",
        "payload_values_disclosed": False,
    }
    if corroboration_root:
        croot = corroboration_root.resolve(strict=True)
        csum = json.loads((croot / "replay/summary.json").read_text())
        replay_a = croot / "replay/32768/engine-output.csv"
        replay_match = replay_a.read_bytes() == output_path.read_bytes()
        replay_bin = croot / "replay/factory-boundary-replay"
        report["second_capture_script_check"] = {
            "effect_summary_agrees": csum.get("effect") == summary.get("effect"),
            "engine_output_byte_identical": replay_match,
            "standalone_binary_sha256_prefix": sha(replay_bin.read_bytes())[:12] if replay_bin.is_file() else None,
        }
        cbundles = [read_run(croot / f"boot-{x}", 905028, 32768, PROFILE) for x in ("a", "b")]
        report["second_capture_script_check"].update({
            "two_boot_dsp_traces_match_primary_reference": all(
                cbundles[0][k] == cbundles[1][k] == a[k] for k in ("inputs", "outputs", "updates")),
            "two_boot_checkpoints_match_primary_reference":
                cbundles[0]["snapshot"].read_bytes() == cbundles[1]["snapshot"].read_bytes() == a["snapshot"].read_bytes(),
            "two_boot_wavs_match_primary_reference":
                cbundles[0]["host_wav"].read_bytes() == cbundles[1]["host_wav"].read_bytes() == a["host_wav"].read_bytes(),
        })
    if loader_evidence_root:
        lroot = loader_evidence_root.resolve(strict=True)
        loader_boots = []
        for name in ("verified-boot1", "verified-boot2"):
            folder = lroot / name
            redacted = json.loads((folder / "redacted.json").read_text())
            correlation = json.loads((folder / "efe-correlation.json").read_text())
            capture = esp_capture.read_capture(folder / "final.esp")
            rom02_displays = [s.get("display", "") for s in redacted.get("selections", [])
                              if "ROM-02 44KHZ REVERB" in s.get("display", "")]
            loader_boots.append({
                "rom02_selection_observed": bool(rom02_displays),
                "correlated_program_sha256": correlation.get("capture_program_sha256"),
                "snapshot_program_sha256": capture["program"]["active_program_sha256"],
                "efe_program_match_count": correlation.get("host_instruction_commits_exact_match"),
                "paired_gpr_match": correlation.get("host_commit_gpr_bytes_match_source_for_paired_records"),
                "trace_sha256": redacted.get("trace_sha256"),
                "raw_payloads_included": redacted.get("raw_payloads_included"),
            })
        report["independent_loader_evidence"] = {
            "two_trace_digests_distinct": loader_boots[0]["trace_sha256"] != loader_boots[1]["trace_sha256"],
            "both_rom02_selection_and_source_correlations_match": all(
                x["rom02_selection_observed"] and
                x["correlated_program_sha256"] == PROFILE["program_sha256"] == x["snapshot_program_sha256"] and
                x["efe_program_match_count"] == 60 and x["paired_gpr_match"] is True for x in loader_boots),
            "boot_count": len(loader_boots),
            "source_efe_payload_present": any(lroot.rglob("*.efe")) or
                any(lroot.rglob("*ROM02*payload*")) or any(lroot.rglob("*44KHZ*payload*")),
        }
    if selector_sweep_root:
        sroot = selector_sweep_root.resolve(strict=True)
        catalog = effect_capture.parse_display_log((sroot / "selector-sweep.log").read_text(errors="replace"),
                                                   16.0, 0.15, list(range(8, 96)))
        report["separate_selector_sweep"] = {
            "rom02_name_observed": any(x["id"] == 2 and x["name"] == "44KHZ REVERB"
                                        for x in catalog["entries"]),
            "wav_matches_reference_host_wav": (sroot / "selector.wav").read_bytes() == a["host_wav"].read_bytes(),
        }
    if reproducible_replay_binary:
        rebuilt_hash = sha(reproducible_replay_binary.resolve(strict=True).read_bytes())
        check_binary = ((corroboration_root.resolve(strict=True) / "replay/factory-boundary-replay")
                        if corroboration_root else None)
        report["standalone_binary_provenance"] = {
            "rebuild_sha256_prefix": rebuilt_hash[:12],
            "matches_capture_script_check_binary": bool(check_binary and check_binary.is_file() and
                                                         rebuilt_hash == sha(check_binary.read_bytes())),
            "matches_original_replay_binary": rebuilt_hash == sha((replay_root / "factory-boundary-replay").read_bytes()),
        }
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-root", type=Path, required=True)
    p.add_argument("--replay-root", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--corroboration-root", type=Path)
    p.add_argument("--loader-evidence-root", type=Path)
    p.add_argument("--selector-sweep-root", type=Path)
    p.add_argument("--reproducible-replay-binary", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    output = a.output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        p.error("redacted report must be written outside the checkout")
    report = audit(a.reference_root, a.replay_root, a.manifest, a.corroboration_root,
                   a.loader_evidence_root, a.reproducible_replay_binary, a.selector_sweep_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["comparison_eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
