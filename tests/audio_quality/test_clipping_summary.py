import json
import unittest
from pathlib import Path

REPORT = Path(__file__).resolve().parents[2] / "docs/ES5510_AUDIO_QUALITY_CLIPPING_V1.json"

class ClippingSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text())

    def test_all_effects_have_finite_preconversion_output_and_zero_overrange(self):
        self.assertEqual(len(self.report["effects"]), 50)
        self.assertEqual(self.report["totals"]["float_overrange_samples"], 0)
        self.assertEqual(self.report["totals"]["wav_clamped_samples"], 0)
        self.assertTrue(all(s["finite_samples"] == 32768
                            for e in self.report["effects"] for s in e["stimuli"]))

    def test_threshold_count_is_near_full_scale_and_slot_attribution_is_stable(self):
        self.assertEqual(self.report["totals"]["near_full_scale_pcm16_threshold_samples"], 4345)
        nonzero = {e["slot"]: sum(s["near_full_scale_pcm16_threshold_samples"] for s in e["stimuli"])
                   for e in self.report["effects"]}
        self.assertEqual({slot: count for slot, count in nonzero.items() if count}, {31: 4324, 37: 21})

    def test_available_os_emulator_wavs_are_reported_as_unmatched_pcm16_context(self):
        refs = self.report["original_os_emulator_selector_audio"]
        self.assertEqual(refs["31"]["peak_pcm16"], 19105)
        self.assertEqual(refs["37"]["peak_pcm16"], 22167)
        self.assertEqual(refs["31"]["near_full_scale_samples"], 0)
        self.assertIn("not matched", self.report["reference_comparison_note"])

if __name__ == "__main__":
    unittest.main()
