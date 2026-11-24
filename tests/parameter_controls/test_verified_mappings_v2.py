import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAPPINGS = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json").read_text())
CATALOG = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json").read_text())


class VerifiedMappingV2Tests(unittest.TestCase):
    def test_exact_verified_control_and_point_counts(self):
        self.assertEqual(sum(len(e["parameters"]) for e in MAPPINGS["effects"]), 16)
        self.assertEqual(sum(len(p["points"]) for e in MAPPINGS["effects"] for p in e["parameters"]), 32)
        self.assertEqual(CATALOG["verified_control_count"], 16)
        self.assertEqual(CATALOG["verified_display_point_count"], 32)
        hall = next(e for e in CATALOG["effects"] if e["slot"] == 1)
        orders = {p["id"]: p["display_order"] for p in hall["verified_runtime_parameters"]}
        self.assertEqual(orders, {"reverb_mix_bus1": 1, "reverb_mix_bus2": 2,
                                  "decay_time": 4, "hi_freq_damping": 7})

    def test_multiregister_groups_are_ordered_and_values_bounded(self):
        hall = next(e for e in MAPPINGS["effects"] if e["slot"] == 1)
        decay = next(p for p in hall["parameters"] if p["id"] == "decay_time")
        self.assertEqual([row[0] for row in decay["points"][1]["writes"]], [3, 4, 5, 91, 110])
        room = next(e for e in MAPPINGS["effects"] if e["slot"] == 3)
        diffusion = next(p for p in room["parameters"] if p["id"] == "diffusion")
        self.assertEqual([row[0] for row in diffusion["points"][1]["writes"]], [7, 9, 10, 11, 12, 18])
        for effect in MAPPINGS["effects"]:
            for parameter in effect["parameters"]:
                self.assertEqual(len(parameter["points"]), 2)
                for point in parameter["points"]:
                    self.assertTrue(point["writes"])
                    for gpr, raw in point["writes"]:
                        self.assertGreaterEqual(gpr, 0)
                        self.assertLess(gpr, 0xC0)
                        self.assertGreaterEqual(int(raw, 16), 0)
                        self.assertLessEqual(int(raw, 16), 0xFFFFFF)

    def test_catalog_retains_private_payload_separation_and_exact_text(self):
        serialized = json.dumps(CATALOG)
        for private in ("/home/gamer/", "checkpoint.esp", "firmware_events.csv", "program.bin"):
            self.assertNotIn(private, serialized)
        slot42 = next(e for e in CATALOG["effects"] if e["slot"] == 42)
        ratio = next(p for p in slot42["verified_runtime_parameters"] if p["id"] == "comp_ratio")
        self.assertEqual([p["display_text"] for p in ratio["verified_display_points"]], ["4/1", "5/1"])


if __name__ == "__main__":
    unittest.main()
