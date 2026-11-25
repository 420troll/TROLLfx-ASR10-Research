import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = json.loads((ROOT / "docs/qa-v4/ASR10_FACTORY_PARAMETER_SPEC_AUDIT_V1.json").read_text())
PDF_AUDIT = json.loads((ROOT / "docs/qa-v4/manual-pdf-audit.json").read_text())


class ParameterSpecAuditTests(unittest.TestCase):
    def test_full_effect_inventory_and_names_are_joined(self):
        self.assertEqual(len(AUDIT["effects"]), 50)
        self.assertEqual([e["slot"] for e in AUDIT["effects"]], list(range(1, 51)))
        self.assertEqual(sum(e["manual_descriptor_count"] for e in AUDIT["effects"]), 594)
        self.assertTrue(all(e["effect_name_match"] for e in AUDIT["effects"] if e["os_effect_name"]))

    def test_os_lcd_scope_and_94_review_rows_are_explicit(self):
        self.assertEqual(AUDIT["coverage"]["os_field_label_associations"], 1040)
        self.assertEqual(AUDIT["coverage"]["os_field_observations"], 5484)
        self.assertEqual(AUDIT["coverage"]["manual_rows_review_unmatched"], 94)
        self.assertEqual(AUDIT["coverage"]["slot_2_lcd_status"], "deferred")

    def test_manual_descriptor_is_not_promoted_to_dsp_verified(self):
        self.assertTrue(all("dsp_verified" in p for e in AUDIT["effects"] for p in e["parameters"]))
        self.assertEqual(AUDIT["coverage"]["dsp_verified_rows"], 33)
        self.assertTrue(all(p["manual_catalog_claim"] == "DOCUMENTED; see cautions in audit report"
                            for e in AUDIT["effects"] for p in e["parameters"]))

    def test_algorithm_specific_ranges_are_retained(self):
        effects = AUDIT["effects"]
        room = effects[13]["known_manual_heading_normalizations"][0]
        hall = effects[15]["known_manual_heading_normalizations"][0]
        self.assertEqual(room["effect_specific_range"], "0.20 to 100.0 sec.")
        self.assertEqual(hall["effect_specific_range"], "0.70 to 250.0 sec.")
        plate_small = effects[16]["known_manual_heading_normalizations"]
        plate_large = effects[17]["known_manual_heading_normalizations"]
        self.assertEqual(plate_small[1]["effect_specific_range"], "0 to 500 ms")
        self.assertEqual(plate_large[1]["effect_specific_range"], "0 to 430 ms")

    def test_delay_buses_and_channels_remain_independent(self):
        for slot in (4, 5):
            groups = AUDIT["effects"][slot - 1]["known_manual_heading_normalizations"]
            delay = next(g for g in groups if g["canonical_control_id"] == "bus_delay_time_lr")
            self.assertEqual(len(delay["os_field_labels"]), 4)
            self.assertIn("BUS2", delay["effect_specific_ranges"])

    def test_subfields_use_cursor_evidence_and_envelope_gap_stays_open(self):
        position = AUDIT["effects"][13]["os_observed_fields"]
        pos = next(f for f in position if f["label"] == "POSITN BAL")
        self.assertGreaterEqual(len(pos["selected_subfield_observations"]), 3)
        env = AUDIT["effects"][21]["known_manual_heading_normalizations"][0]
        self.assertIn("UNRESOLVED", env["relationship"])
        self.assertEqual(env["os_selected_value_count_per_observation"], 5)

    def test_manual_pdf_text_evidence_covers_all_catalog_ranges(self):
        self.assertEqual(PDF_AUDIT["effect_headers_found"], 50)
        self.assertTrue(PDF_AUDIT["all_effect_names_match_after_punctuation_normalization"])
        self.assertEqual(PDF_AUDIT["range_status_counts"], {
            "EXACT_RANGE_TEXT_FOUND": 542,
            "SHARED_VARIATION_TEXT_FOUND": 50,
            "RANGE_ENDPOINTS_FOUND_UNITS_IN_PROSE": 2,
            "NOT_FOUND_REVIEW": 0,
        })


if __name__ == "__main__":
    unittest.main()
