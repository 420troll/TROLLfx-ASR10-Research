import importlib.util
import json
import tempfile
import unittest
import wave
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

verify = module("hall_replay_verify", "tools/hall_replay_verify.py")
adapters = module("hall_replay_adapters", "tools/hall_replay_adapters.py")


class HallReplayTests(unittest.TestCase):
    def trace(self, n=32768):
        return {"schema": "trollfx-es5510-hall-replay-v1",
                "replay": {"input_sha256": "input", "initial_state_sha256": "state",
                           "firmware_events_sha256": "events", "alignment": "DSP frame 0 paired"},
                "dsp_rate_hz": verify.DSP_RATE, "host_rate_hz": verify.HOST_RATE,
                "dsp_serial_samples": [{"index": i, "left": i, "right": -i} for i in range(n)]}

    def test_clock_mapping_and_distinct_domains(self):
        self.assertEqual(verify.host_frame_to_dsp_frame(44100), 29761)
        self.assertEqual(verify.host_frame_to_dsp_frame(32768), 22114)
        self.assertNotEqual(verify.DSP_RATE, verify.HOST_RATE)

    def test_factory_windows_and_earliest_difference(self):
        a, b = self.trace(), self.trace()
        b["dsp_serial_samples"][145]["left"] += 1
        with tempfile.TemporaryDirectory() as d:
            pa, pb = Path(d)/"a.json", Path(d)/"b.json"
            pa.write_text(json.dumps(a)); pb.write_text(json.dumps(b))
            report = verify.verify(pa, pb)
        self.assertTrue(report["replay_eligible"])
        self.assertEqual(report["factory_windows"]["256"]["first_difference"]["index"], 145)
        self.assertEqual(report["factory_windows"]["4096"]["mismatching_frames"], 1)
        self.assertEqual(report["factory_windows"]["32768"]["max_absolute_difference"], 1)

    def test_gate_mismatch_suppresses_factory_result(self):
        a, b = self.trace(256), self.trace(256); b["replay"]["firmware_events_sha256"] = "different"
        with tempfile.TemporaryDirectory() as d:
            pa, pb = Path(d)/"a.json", Path(d)/"b.json"
            pa.write_text(json.dumps(a)); pb.write_text(json.dumps(b))
            report = verify.verify(pa, pb)
        self.assertFalse(report["replay_eligible"])
        self.assertEqual(report["factory_windows"]["256"]["status"], "not_run")

    def test_canonical_trace_adapter(self):
        t = {"schema": "trollfx-es5510-execution-trace-v1", "trace_id": "synthetic",
             "events": [{"event_type":"serial_output","sample_index":0,"channel":"left","value":4},
                        {"event_type":"serial_output","sample_index":0,"channel":"right","value":-4}]}
        adapted = adapters.canonical_to_replay(t, input_sha256="i", initial_state_sha256="s",
                    firmware_events_sha256="f", alignment="frame 0")
        self.assertEqual(adapted["dsp_serial_samples"], [{"index":0,"left":4,"right":-4}])
        self.assertEqual(adapted["dsp_rate_hz"], 29761.89453125)

    def test_factory_audio_lab_adapter_does_not_label_synthetic_as_factory(self):
        result = adapters.audio_lab_summary({"sample_rate_hz":44100,"frames_per_stimulus":32768,
            "comparison":"diagnostic adapter","summaries":{"impulse":{"pass":{"frames":32768,
            "bit_exact":True,"first_divergent_frame":None,"max_abs_deviation":0,"rms_deviation":0.0}}}})
        self.assertFalse(result["factory_hall_evidence"])
        self.assertEqual(result["cases"]["impulse/pass"]["frames"], 32768)

    def test_host_wav_is_separate_44100_domain(self):
        with tempfile.TemporaryDirectory() as d:
            paths = [Path(d)/"a.wav", Path(d)/"b.wav"]
            for p in paths:
                with wave.open(str(p), "wb") as w:
                    w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
                    w.writeframes(struct.pack("<hhhh", 1, 2, 3, 4))
            result = verify.compare_wavs(*paths)
        self.assertTrue(result["samples_equal"])
        self.assertEqual(result["compared_frames"], 2)


if __name__ == "__main__":
    unittest.main()
