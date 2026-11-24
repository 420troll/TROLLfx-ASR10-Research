import json
import unittest
from pathlib import Path

REPORT = Path(__file__).resolve().parents[2] / "docs/ES5510_ROM02_PARAMETER_RESPONSE_V1.json"

class Rom02ParameterResponseReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text())

    def test_strict_reference_and_write_schedule_evidence(self):
        self.assertTrue(self.report["validated_reference"]["two_boot_checkpoint_match"])
        self.assertEqual(self.report["validated_reference"]["serial_route"], "SER2 stereo input -> SER1 stereo output")
        schedule = self.report["schedule"]
        self.assertEqual(schedule["events"], 202)
        self.assertEqual((schedule["bus1_write_count"], schedule["bus1_last_write_frame"]), (33, 17075))
        self.assertEqual((schedule["bus2_write_count"], schedule["bus2_last_write_frame"]), (1, 501))
        self.assertLess(schedule["bus1_last_write_frame"], schedule["factory_edit_frame"])

    def test_bus1_and_bus2_responses_are_separated_at_both_rates(self):
        self.assertEqual(len(self.report["comparisons"]), 36)
        for mode in ("factory-44100", "experimental-48000"):
            bus1 = [x for x in self.report["comparisons"] if x["mode"] == mode and x["control"] == "BUS1"]
            bus2 = [x for x in self.report["comparisons"] if x["mode"] == mode and x["control"] == "BUS2"]
            self.assertEqual(len(bus1), 9)
            self.assertTrue(all(x["different_samples"] == 0 for x in bus1))
            self.assertTrue(all(x["different_samples"] > 0 for x in bus2))
            self.assertEqual({x["route"] for x in bus2}, {"left", "right", "stereo"})
            self.assertEqual({x["signal"] for x in bus2}, {"impulse", "noise", "sustained"})
        self.assertTrue(all(x["deterministic_repeat"] for x in self.report["comparisons"]))

if __name__ == "__main__":
    unittest.main()
