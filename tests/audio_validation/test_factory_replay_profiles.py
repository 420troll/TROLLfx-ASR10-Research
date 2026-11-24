import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
from factory_replay_profiles import PROFILES
from replay_factory_from_boundary import assign_event_boundary, compare_outputs, validate_instruction_aliases


class FactoryReplayProfileTests(unittest.TestCase):
    def test_hall_v4_profile_preserves_verified_constants(self):
        p = PROFILES["rom01-hall-v4"]
        self.assertEqual((p["active_words"], p["end_word"]), (89, 88))
        self.assertEqual((p["instruction_commits"], p["unique_instruction_addresses"], p["register_commits"]),
                         (89, 89, 342))
        self.assertEqual((p["dsp_rate_hz"], p["host_rate_hz"]), (29761.89453125, 44100))

    def test_rom02_profile_captures_alias_and_44khz_clock(self):
        p = PROFILES["rom02-44khz-reverb-v1"]
        self.assertEqual((p["active_words"], p["end_word"]), (60, 59))
        self.assertEqual((p["instruction_commits"], p["unique_instruction_addresses"], p["register_commits"]),
                         (61, 60, 283))
        self.assertEqual(p["instruction_aliases"], {58: 0})
        self.assertEqual(p["source_paired_gprs"], 58)
        self.assertEqual(p["dsp_rate_hz"], 44100.0)

    def test_rom02_instruction_alias_is_content_checked(self):
        validate_instruction_aliases([11] * 60, {58: 0})
        with self.assertRaises(ValueError):
            validate_instruction_aliases([11] * 58 + [12, 13], {58: 0})

    def test_firmware_write_requires_an_observed_between_frame_boundary(self):
        inputs = [{"seq": 20, "frame": 100}, {"seq": 40, "frame": 101}, {"seq": 60, "frame": 102}]
        outputs = [{"seq": 30, "frame": 100}, {"seq": 50, "frame": 101}]
        self.assertEqual(assign_event_boundary(35, inputs, outputs), 101)
        with self.assertRaises(ValueError):
            assign_event_boundary(45, inputs, outputs)

    def test_comparison_uses_fixed_indices_and_reports_channel_errors(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "engine.csv"
            fields = ["frame", *[f"native{i}" for i in range(8)], *[f"mame{i}" for i in range(8)]]
            rows = []
            for frame in (20, 21):
                row = {"frame": str(frame)}
                for lane in range(8):
                    row[f"native{lane}"] = "100"
                    row[f"mame{lane}"] = "100"
                rows.append(row)
            rows[1]["mame2"] = "104"
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
            bundle = {"windows": (2,), "outputs": [
                {"frame": 20, "lanes": [0, 0, 100, 100, 0, 0, 0, 0]},
                {"frame": 21, "lanes": [0, 0, 100, 100, 0, 0, 0, 0]},
            ]}
            result = compare_outputs(path, bundle)["2"]
            self.assertTrue(result["native_vs_os"]["mismatches"] == 0)
            self.assertEqual(result["mame_vs_os"]["first"]["absolute_frame"], 21)
            self.assertEqual(result["mame_vs_os"]["per_channel"]["SER1L"]["peak_absolute_error"], 4)
            self.assertFalse(result["sample_exact"])


if __name__ == "__main__":
    unittest.main()
