import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RecoveryV03Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_RECOVERY_V03.json").read_text())

    def test_v2_baseline_and_new_control_counts(self):
        self.assertEqual(self.data["counts"]["v2_verified_controls_preserved"], 16)
        self.assertEqual(len(self.data["new_verified_controls"]), 3)
        self.assertEqual(self.data["counts"]["total_controls_with_verified_points"], 19)
        self.assertEqual(sum(len(x["points"]) for x in self.data["new_verified_controls"]), 6)

    def test_range_scans_are_exactly_restored_and_not_promoted_to_curves(self):
        self.assertEqual(len(self.data["range_scans"]), 3)
        for scan in self.data["range_scans"]:
            self.assertEqual((scan["minimum"], scan["maximum"]), ("0", "99"))
            self.assertTrue(scan["restored_exactly"])
        for control in self.data["new_verified_controls"]:
            self.assertIn(control["conversion"], {
                "verified discrete points only", "verified discrete modes only"})

    def test_new_points_have_unique_ordered_register_writes(self):
        for control in self.data["new_verified_controls"]:
            self.assertEqual(len(control["points"]), 2)
            for point in control["points"]:
                gprs = [write[0] for write in point["writes"]]
                self.assertEqual(len(gprs), len(set(gprs)))
                self.assertTrue(all(0 <= gpr < 256 for gpr in gprs))
        flange = next(x for x in self.data["new_verified_controls"] if x["slot"] == 8)
        self.assertNotIn(0x86, [w[0] for p in flange["points"] for w in p["writes"]])

    def test_rom02_is_deferred_from_v3_promotion(self):
        self.assertIn("deferred per user direction", self.data["counts"]["slot_2_v3_followup"])
        self.assertNotIn(2, [x["slot"] for x in self.data["new_verified_controls"]])
        self.assertNotIn(2, [x["slot"] for x in self.data["range_scans"]])


if __name__ == "__main__":
    unittest.main()
