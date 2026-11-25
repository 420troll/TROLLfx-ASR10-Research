import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CATALOG=ROOT/"docs/ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05.json"

class V05RuntimeCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=json.loads(CATALOG.read_text())

    def test_slot_two_is_deferred_and_not_exposed(self):
        self.assertEqual(self.catalog["slot_02"],"DEFERRED")
        self.assertNotIn(2,{x["slot"] for x in self.catalog["controls"]})

    def test_every_control_has_two_explicit_observed_points(self):
        self.assertEqual(len(self.catalog["controls"]),30)
        for control in self.catalog["controls"]:
            self.assertEqual(len(control["verified_points"]),2,control["parameter_id"])
            self.assertEqual(control["probe_trials"],2)
            self.assertTrue(control["display_restored_each_trial"])
            self.assertEqual(control["mapping_status"],"REGISTER_VERIFIED_ADJACENT_POINTS")
            self.assertTrue(control["probe_evidence_id"].endswith("-evidence.json"))

    def test_register_writes_are_ordered_and_24_bit(self):
        for control in self.catalog["controls"]:
            for point in control["verified_points"]:
                writes=point["ordered_writes"]
                self.assertTrue(writes,control["parameter_id"])
                self.assertEqual(len({w["gpr"] for w in writes}),len(writes),control["parameter_id"])
                for write in writes:
                    self.assertRegex(write["gpr"],r"^0x[0-9A-F]{2}$")
                    self.assertRegex(write["value24"],r"^0x[0-9a-f]{6}$")

    def test_range_metadata_does_not_replace_exact_supported_points(self):
        for control in self.catalog["controls"]:
            self.assertIn(control["range_status"],{"DOCUMENTED","NOT_FOUND_IN_V1_MANUAL_CATALOG"})
            self.assertIsInstance(control["runtime_ready"],bool)
            self.assertNotEqual(control["documented_range"],"inferred")

    def test_signed_lcd_text_and_runtime_status_are_preserved(self):
        controls={(x["slot"],x["parameter_id"]):x for x in self.catalog["controls"]}
        self.assertEqual([p["text"] for p in controls[(6,"chorus_feedback")]["verified_points"]],["+9","+10"])
        self.assertEqual([p["text"] for p in controls[(39,"vc1_fine")]["verified_points"]],["-5","-4"])
        self.assertEqual(sum(x["runtime_ready"] for x in self.catalog["controls"]),23)
        self.assertEqual(len([x for x in self.catalog["controls"] if not x["runtime_ready"]]),7)

    def test_catalog_contains_no_private_absolute_paths(self):
        serialized=json.dumps(self.catalog)
        self.assertNotIn("/home/gamer/",serialized)
        self.assertNotIn("production-provider-audit",serialized)

if __name__=="__main__": unittest.main()
