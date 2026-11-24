import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json").read_text())


class FactoryCatalogV1Tests(unittest.TestCase):
    def test_fifty_slots_and_evidence_tiers(self):
        self.assertEqual(DOC["schema"], "trollfx-asr10-factory-parameter-catalog-v1")
        self.assertEqual(len(DOC["effects"]), 50)
        self.assertEqual([x["slot"] for x in DOC["effects"]], list(range(1, 51)))
        self.assertEqual([x["factory_name"] for x in DOC["effects"][:3]],
                         ["HALL REVERB", "44KHZ REVERB", "ROOM REVERB"])
        self.assertEqual(sum(len(x.get("verified_runtime_parameters", [])) for x in DOC["effects"]), 4)
        self.assertEqual(DOC["effects"][0]["parameters"][1]["display_name"], "DECAY TIME")
        self.assertIsNone(DOC["effects"][0]["parameters"][1]["default"])

    def test_no_undocumented_interpolation_or_private_payload_paths(self):
        text = json.dumps(DOC)
        for forbidden in ("/home/gamer/", "session.log", "checkpoint", "microprogram", "EFE payload"):
            self.assertNotIn(forbidden, text)
        self.assertIn("Only the two observed points", text)
        self.assertIn("no interpolation", text)
        self.assertIn("CMP+DIST+REV", DOC["effects"][12]["manual_cross_references"])


if __name__ == "__main__":
    unittest.main()
