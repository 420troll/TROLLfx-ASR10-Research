import csv
import hashlib
import importlib.util
import json
import sys
import struct
import wave
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
spec = importlib.util.spec_from_file_location("factory_hall_compare", ROOT / "tools/audio_validation/factory_hall_compare.py")
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)


def valid_evidence():
    return {
        "input_sha256": "input",
        "state": {"program_sha256": "program", "gpr_sha256": "gpr", "spr_sha256": "spr",
                  "dram_sha256": "dram", "memory_configuration": {"mask": 1}},
        "pipeline": {"reset_acknowledged": True, "alu_pending": 0, "mac_pending": 0,
                     "ram_slots_cleared": 3, "dol_count": 0},
        "firmware": {"ordered_event_sha256": "events", "execution_event_sequence": "exec-events",
                     "execution_event_count": 1, "host_event_count": 1, "io_event_count": 0,
                     "last_frame_inclusive": 500, "instruction_commits": 89,
                     "gpr_spr_commit_count": 342},
        "clock": {"dsp_rate_hz": compare.DSP_RATE, "host_rate_hz": 44100},
        "routing": {"host_serial": 72, "serial_route": "-1,-1,1,-1", "direct_mask": "00"},
        "alignment": {"absolute_start_frame": 500, "sample_zero_is_frame": 500,
                      "input_lanes": ["SER2L", "SER2R"], "output_lanes": ["SER1L", "SER1R"]},
        "boundary": {"run_frame": 500, "snapshot_frame": 500, "first_instruction_frame": 500,
                     "first_instruction_pc": 0, "snapshot_before_first_instruction": True},
        "host_mapping_sha256": "map",
        "host_window_frames": 2,
    }


def samples(n):
    return [{"index": i, "absolute_frame": 500 + i, "left": i % 32768,
             "right": -(i % 32768)} for i in range(n)]


class FactoryHallCompareTests(unittest.TestCase):
    def test_synthetic_exact_native_candidate_runs_requested_windows(self):
        ref = {"engine": "os353", "evidence": valid_evidence(), "samples": samples(32768)}
        candidate = {"engine": "native", "evidence": valid_evidence(), "samples": samples(32768)}
        report = compare.compare_datasets(ref, candidate)
        self.assertTrue(report["eligible"])
        for n in (256, 4096, 32768):
            self.assertTrue(report["dsp_windows"][str(n)]["samples_equal"])
            self.assertIsNone(report["dsp_windows"][str(n)]["first_divergent_absolute_frame"])

    def test_missing_pipeline_evidence_suppresses_all_sample_comparisons(self):
        ref = {"engine": "os353", "evidence": valid_evidence(), "samples": samples(32768)}
        ev = valid_evidence(); ev["pipeline"].pop("ram_slots_cleared")
        candidate = {"engine": "mame", "evidence": ev, "samples": samples(32768)}
        report = compare.compare_datasets(ref, candidate)
        self.assertFalse(report["eligible"])
        self.assertTrue(report["comparison_suppressed"])
        self.assertEqual(report["dsp_windows"]["256"]["status"], "not_run")

    def test_mismatched_input_and_state_are_reported_as_gate_failures(self):
        ref = {"engine": "os353", "evidence": valid_evidence(), "samples": samples(256)}
        ev = valid_evidence(); ev["input_sha256"] = "different"; ev["state"]["spr_sha256"] = "different"
        candidate = {"engine": "native", "evidence": ev, "samples": samples(256)}
        report = compare.compare_datasets(ref, candidate)
        self.assertFalse(report["eligible"])
        self.assertFalse(report["gates"]["input_sha256"]["equal"])
        self.assertFalse(report["gates"]["state.spr_sha256"]["equal"])

    def test_first_divergence_has_absolute_frame_and_channel_metrics(self):
        ref_samples, cand_samples = samples(256), samples(256)
        cand_samples[19]["right"] += 3
        cand_samples[19]["context"] = {"pc": 4, "instruction_index": 4, "register": "SPR244"}
        ref = {"engine": "os353", "evidence": valid_evidence(), "samples": ref_samples}
        candidate = {"engine": "native", "evidence": valid_evidence(), "samples": cand_samples}
        window = compare.compare_datasets(ref, candidate)["dsp_windows"]["256"]
        self.assertEqual(window["first_divergent_absolute_frame"], 519)
        self.assertEqual(window["channel_metrics"]["right"]["first_difference_index"], 19)
        self.assertEqual(window["channel_metrics"]["right"]["max_absolute_difference"], 3)
        self.assertIsNone(window["channel_metrics"]["left"]["first_difference_index"])
        self.assertEqual(window["divergence_context"]["candidate"]["register"], "SPR244")

    def test_engine_csv_adapter_selects_native_and_mame_ser1_channels(self):
        evidence = valid_evidence()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "engine.csv"
            path.write_text("frame,native1l,native1r,mame1l,mame1r\n500,10,-10,11,-11\n501,20,-20,21,-21\n")
            input_rows = [{"index": 0, "absolute_frame": 500, "left": 0, "right": 0},
                          {"index": 1, "absolute_frame": 501, "left": 1, "right": -1}]
            evidence["input_sha256"] = compare.input_sample_digest(input_rows)
            ev = Path(td) / "evidence.json"; ev.write_text(json.dumps({"evidence": evidence}))
            input_path = Path(td) / "input.csv"
            input_path.write_text("frame,in_ser2l,in_ser2r\n500,0,0\n501,1,-1\n")
            native = compare.load_candidate(path, "native", ev, "engine-csv", input_path)
            mame = compare.load_candidate(path, "mame", ev, "engine-csv", input_path)
        self.assertEqual(native["samples"][0]["left"], 10)
        self.assertEqual(mame["samples"][0]["left"], 11)
        self.assertEqual(native["samples"][1]["absolute_frame"], 501)

    def test_candidate_json_input_samples_are_hashed_and_frame_checked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_rows = [{"index": 0, "absolute_frame": 500, "left": 9, "right": -9}]
            evidence = valid_evidence(); evidence["input_sha256"] = compare.input_sample_digest(input_rows)
            candidate = {"schema": compare.SCHEMA, "engine": "native", "dsp_serial_samples": samples(1),
                         "input_samples": input_rows}
            path, sidecar = root / "candidate.json", root / "evidence.json"
            path.write_text(json.dumps(candidate)); sidecar.write_text(json.dumps({"evidence": evidence}))
            loaded = compare.load_candidate(path, "native", sidecar)
            self.assertEqual(len(loaded["input_samples"]), 1)
            candidate["input_samples"][0]["right"] = -8
            path.write_text(json.dumps(candidate))
            with self.assertRaisesRegex(ValueError, "input samples do not match"):
                compare.load_candidate(path, "native", sidecar)

    def test_os_adapter_requires_reset_details_and_preserves_clock_domains(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_lines = [
                "ESPPHASE kind=host_halt_pipeline_reset frame=14 cycles=100 pc=fff000 alu_pending=0 mac_pending=0 ram_slots_cleared=3 dol_count=0",
                "ESPPHASE kind=run_start frame=500 cycles=110 host_pc=fff000 pc=00",
                "ESPHOST event=1 cycles=120 frame=500 pc=fff000 gpr 7f <- 000000 t=0.1",
            ]
            (root / "session.log").write_text("\n".join(event_lines) + "\n")
            event_evidence = compare.measure_event_trace(root / "session.log", 500, 500)
            window_event_evidence = {"sha256": event_evidence["execution_event_sequence"],
                                     "event_count": event_evidence["execution_event_count"],
                                     "host_event_count": event_evidence["host_event_count"],
                                     "io_event_count": event_evidence["io_event_count"],
                                     "last_frame_inclusive": event_evidence["last_frame_inclusive"]}
            trace = {"schema": "trollfx-es5510-hall-replay-v1", "trace_id": "synthetic",
                     "replay": {"input_sha256": hashlib.sha256(struct.pack("<hh", 1, -1)).hexdigest(),
                                "initial_state_sha256": "capture",
                                "firmware_events_sha256": event_evidence["ordered_event_sha256"]},
                     "dsp_rate_hz": compare.DSP_RATE, "host_rate_hz": 44100,
                     "dsp_serial_samples": samples(1), "input_samples": [{"index": 0, "left": 1, "right": -1}],
                     "metadata": {"absolute_start_frame": 500,
                                                                         "frame_count": 1,
                                 "firmware_load": {"ordered_event_sha256": event_evidence["ordered_event_sha256"],
                                                   "instruction_commits": 89,
                                                   "gpr_spr_commit_count": 342,
                                                   "execution_event_sequence": window_event_evidence},
                                                                         "host_output": {"host_frames": 1}}}
            state = {"program": {"active_program_sha256": "program"},
                     "capture_sha256": "capture",
                     "register_hashes": {"gpr_sha256": "gpr", "special_sha256": "spr"},
                     "pipeline": {"halt_reset_acknowledged": True,
                                  "reset_event": {"frame": "14", "alu_pending": 0, "mac_pending": 0,
                                                  "ram_slots_cleared": 3, "dol_count": 0}},
                     "runtime": {"dram_sha256": "dram", "memory_configuration": {"mask": 1},
                                 "control": {"host_serial": 72}},
                     "program": {"active_program_sha256": "program"}}
            meta = {"schema": "trollfx-es5510-hall-reference-capture-v2", "initial_state": state,
                    "firmware_load": {"instruction_commits": 89, "gpr_spr_commit_count": 342,
                                      "ordered_event_sha256": event_evidence["ordered_event_sha256"]},
                    "clock": {"serial_route": "-1,-1,1,-1", "direct_mask": "00",
                              "host_output_rate_hz": "44100.000"},
                    "timeline": [{"kind": "run_start", "frame": "500"},
                                 {"kind": "run_snapshot", "frame": "500", "log_sequence": 2},
                                 {"kind": "first_instruction", "frame": "500", "pc": "00", "log_sequence": 3}],
                    "host_output": {"host_map_file": "map.csv"}}
            trace["metadata"]["initial_state"] = state
            with (root / "map.csv").open("w") as f:
                f.write("host_frame_index,source_dsp_frame_position,emission_dsp_frame,left_pcm16,right_pcm16\n0,500.0,500,0,0\n")
            tp, mp = root / "trace.json", root / "meta.json"
            tp.write_text(json.dumps(trace)); mp.write_text(json.dumps(meta))
            ref = compare.os_reference(tp, mp)
        self.assertEqual(ref["evidence"]["clock"], {"dsp_rate_hz": compare.DSP_RATE, "host_rate_hz": 44100})
        self.assertEqual(ref["evidence"]["pipeline"]["ram_slots_cleared"], 3)
        self.assertTrue(ref["evidence"]["boundary"]["snapshot_before_first_instruction"])

    def test_host_wav_requires_matching_measured_source_map_and_frame_count(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            map_path = root / "map.csv"
            map_path.write_text("host_frame_index,source_dsp_frame_position,emission_dsp_frame\n"
                                "10,500.0,500\n11,500.7,501\n")
            ev = valid_evidence(); ev["host_mapping_sha256"] = compare.host_mapping_digest(map_path)
            ref = {"engine": "os353", "evidence": ev, "samples": samples(256)}
            candidate = {"engine": "native", "evidence": dict(ev), "samples": samples(256)}
            for name in ("os.wav", "candidate.wav"):
                with wave.open(str(root / name), "wb") as w:
                    w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
                    w.writeframes(struct.pack("<hhhh", 1, -1, 2, -2))
            exact = compare.compare_wavs_gated(root / "os.wav", root / "candidate.wav", ref, candidate)
            self.assertTrue(exact["samples_equal"])
            candidate["evidence"]["host_mapping_sha256"] = "wrong"
            blocked = compare.compare_wavs_gated(root / "os.wav", root / "candidate.wav", ref, candidate)
            self.assertEqual(blocked["status"], "not_run")

    def test_firmware_event_trace_adapter_hashes_order_and_window_bounds(self):
        lines = [
            "ESPPHASE kind=host_halt_pipeline_reset frame=14 cycles=100 pc=fff000 alu_pending=0 mac_pending=0 ram_slots_cleared=3 dol_count=0",
            "ESPIO event=1 direction=W cycles=110 frame=15 port=1f value=02 pc=fff000",
            "ESPPHASE kind=run_start frame=20 cycles=120 host_pc=fff000 pc=00",
            "ESPHOST event=2 cycles=130 frame=20 pc=fff000 gpr 7f <- 000001 t=0.1",
            "ESPIO event=3 direction=W cycles=140 frame=21 port=1f value=02 pc=fff000",
            "ESPHOST event=4 cycles=150 frame=22 pc=fff000 gpr 7f <- 000002 t=0.2",
        ]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "events.log"; path.write_text("\n".join(lines) + "\n")
            measured = compare.measure_event_trace(path, 20, 21)
        self.assertEqual(measured["host_event_count"], 1)
        self.assertEqual(measured["io_event_count"], 2)
        self.assertEqual(measured["execution_event_count"], 3)
        self.assertEqual(measured["last_frame_inclusive"], 21)
        candidate = dict(measured)
        candidate["_records"] = {k: list(v) for k, v in measured["_records"].items()}
        candidate["_records"]["execution"][1] = candidate["_records"]["execution"][1].replace("frame=20", "frame=21")
        diagnostics = compare.compare_event_records({"_event_records": measured["_records"]}, candidate)
        self.assertFalse(diagnostics["execution"]["events_equal"])
        self.assertEqual(diagnostics["execution"]["first_difference_ordinal"], 1)
        self.assertEqual(diagnostics["execution"]["candidate_event"]["frame"], "21")


if __name__ == "__main__":
    unittest.main()
