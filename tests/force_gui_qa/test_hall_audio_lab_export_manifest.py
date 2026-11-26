import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/qa-v4/ASR10_HALL_AUDIO_LAB_EXPORT_V1.json"


class HallAudioLabExportManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MANIFEST.read_text())

    def test_render_and_comparison_coverage(self):
        self.assertEqual(self.data["render_count"], 44)
        self.assertEqual(len(self.data["render_manifest"]), 44)
        self.assertEqual(len(self.data["comparison_pairs"]), 16)
        self.assertEqual(len(self.data["audio_lab_bundles"]), 4)
        self.assertTrue(self.data["original_float_wavs_preserved"])
        requested = {"display_10_vs_90", "display_0_vs_99", "display_25_vs_75", "display_40_vs_41"}
        for mode in ("FactoryReference", "Experimental48000"):
            for stimulus in ("impulse", "noise_burst"):
                got = {row["comparison"] for row in self.data["comparison_pairs"]
                       if row["rate_mode"] == mode and row["stimulus"] == stimulus}
                self.assertEqual(got, requested)

    def test_startup_provenance_and_path_redaction(self):
        startup = self.data["startup"]
        self.assertEqual(startup["schedule_events_applied"], 213)
        self.assertEqual(startup["schedule_events_expected"], 213)
        self.assertTrue(startup["post_schedule_initial_register_state_identical"])
        self.assertEqual(self.data["effect"], {"slot": 1, "name": "HALL REVERB", "variation": 1})
        serialized = json.dumps(self.data).lower()
        self.assertNotIn("/home/", serialized)
        self.assertNotIn("\\users\\", serialized)

    def test_bundle_manifest_hashes_and_case_counts(self):
        for bundle in self.data["audio_lab_bundles"]:
            self.assertEqual(bundle["case_count"], 4)
            self.assertEqual(len(bundle["sha256"]), 64)
            self.assertEqual(bundle["validator"], "Codex 2 audio_lab.analyze_bundle")

    def test_each_render_has_float_and_pcm_hashes_and_tail_metrics(self):
        for render in self.data["render_manifest"]:
            self.assertEqual(len(render["wav_float32_sha256"]), 64)
            self.assertEqual(len(render["wav_pcm32_sha256"]), 64)
            self.assertEqual(set(render["tail_energy_bands"]),
                             {"0-0.1s", "0.1-0.5s", "0.5-1s", "1-2s", "2-5s", "5-8s", "8-10s"})
            self.assertGreater(render["duration_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
