import hashlib
import json
import subprocess
import sys
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from tools.force_gui_qa.compare_vst2_audio import (
    REQUIRED, difference, read_stereo_wav, summarize, verify_evidence,
)


class Vst2AudioComparatorTests(unittest.TestCase):
    def evidence(self):
        digest = "a" * 64
        return {
            "effect_slot": 1, "effect_name": "HALL REVERB", "variation": 1,
            "display_value": 40, "raw_code": 51, "input_sha256": digest,
            "processing_rate_hz": 48000, "wav_sample_rate_hz": 48000,
            "startup_complete": True, "firmware_events_expected": 213,
            "firmware_events_applied": 213, "startup_complete_frame": 12985,
            "initial_state_sha256": digest, "checkpoint_sha256": digest,
            "program_sha256": digest, "firmware_schedule_sha256": digest,
            "serial_routing": {"stereo": True}, "parameter_index": 8,
            "host_parameter_value": 0.0, "parameter_application_frame": 12986,
            "active_registers": {"0x6e": 51}, "register_trace_sha256": digest,
            "frame_zero": "input_frame_0", "known_latency_frames": 0,
            "binary_sha256": digest, "source_commit": "test-only",
            "vst_callbacks": ["open", "set_sample_rate", "set_block_size", "mains_on",
                              "set_parameter", "process_replacing", "get_chunk", "set_chunk",
                              "mains_off", "close"],
        }

    def test_gate_rejects_missing_firmware_events(self):
        evidence = self.evidence()
        evidence["firmware_events_applied"] = 212
        with self.assertRaisesRegex(ValueError, "schedule application count is incomplete"):
            verify_evidence(evidence, "test")

    def test_package_specific_event_count_is_accepted_for_non_hall_effect(self):
        evidence = self.evidence()
        evidence.update({"effect_slot": 2, "effect_name": "44KHZ REVERB",
                         "firmware_events_expected": 202, "firmware_events_applied": 202})
        verify_evidence(evidence, "ROM-02")

    def test_gate_rejects_missing_callback_evidence(self):
        evidence = self.evidence()
        evidence["vst_callbacks"].remove("process_replacing")
        with self.assertRaisesRegex(ValueError, "process_replacing"):
            verify_evidence(evidence, "test")

    def test_float_wav_metrics_and_ab_difference(self):
        with tempfile.TemporaryDirectory() as td:
            wav_path = Path(td) / "stereo-float.wav"
            a = [(0.25, -0.25)] * 4800
            with wave.open(str(wav_path), "wb") as w:
                w.setnchannels(2); w.setsampwidth(4); w.setframerate(48000)
                w.writeframes(struct.pack("<" + "i" * (len(a) * 2), *(int(v * (1 << 31)) for pair in a for v in pair)))
            rate, decoded = read_stereo_wav(wav_path)
            self.assertEqual(rate, 48000)
            self.assertEqual(decoded, a)
            self.assertAlmostEqual(summarize(decoded, rate)["stereo_rms"], 0.25)
            b = [(0.0, 0.0)] * len(a)
            self.assertAlmostEqual(difference(decoded, b)["difference_rms"], 0.25)

    def test_required_evidence_contract_is_complete(self):
        evidence = self.evidence()
        self.assertEqual(set(REQUIRED) - set(evidence), set())
        verify_evidence(evidence, "valid")

    def test_end_to_end_pair_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            callbacks = ["open", "set_sample_rate", "set_block_size", "mains_on", "set_parameter",
                         "process_replacing", "get_chunk", "set_chunk", "mains_off", "close"]
            pairs = []
            common = "a" * 64
            for name, value, raw in (("a", 40, 51), ("b", 41, 53)):
                rows = {}
                for prefix, changed in (("reference", False), ("candidate", True)):
                    path = root / f"{prefix}_{name}.wav"
                    amp = (0.25 if value == 40 else 0.1) * (1.0 if not changed else 0.99)
                    samples = [(amp, -amp)] * 4800
                    with wave.open(str(path), "wb") as w:
                        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
                        w.writeframes(struct.pack("<" + "h" * 9600,
                                                   *(max(-32768, min(32767, round(v * 32768))) for pair in samples for v in pair)))
                    meta = self.evidence()
                    meta.update({"display_value": value, "raw_code": raw, "active_registers": {"0x6e": raw}, "vst_callbacks": callbacks})
                    if changed:
                        meta["processing_rate_hz"] = 29761.89453125
                    rows[prefix] = {"wav": path.name, "wav_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "evidence": meta}
                rows["reference"]["evidence"]["host_parameter_value"] = 0.0
                rows["candidate"]["evidence"]["host_parameter_value"] = 1.0
                pair = {"pair_id": f"hall_{name}"}
                pair["reference_a" if name == "a" else "reference_b"] = rows["reference"]
                pair["candidate_a" if name == "a" else "candidate_b"] = rows["candidate"]
                pairs.append(pair)
            combined = {"pair_id": "hall_40_vs_41"}
            for pair in pairs: combined.update({k: v for k, v in pair.items() if k != "pair_id"})
            manifest = root / "pairs.json"; output = root / "report.json"
            manifest.write_text(json.dumps({"schema": "asr10-vst2-audio-pair-v1", "pairs": [combined]}))
            subprocess.run([sys.executable, str(Path(__file__).resolve().parents[2] / "tools/force_gui_qa/compare_vst2_audio.py"), str(manifest), "--output", str(output)], check=True, capture_output=True, text=True)
            report = json.loads(output.read_text())
            self.assertEqual(report["pairs"][0]["sample_rate_hz"], 48000)
            self.assertGreater(report["pairs"][0]["candidate_a_minus_b"]["difference_rms"], 0)
            self.assertEqual(report["pairs"][0]["rate_conversion_performed"]["candidate_a"], False)
            self.assertFalse(report["pairs"][0]["processing_clock_match"])


if __name__ == "__main__":
    unittest.main()
