import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs/ES5510_FACTORY_PARAMETER_CATALOG_V01.json"


class ParameterCatalogTests(unittest.TestCase):
    def test_catalog_preserves_only_verified_points_and_unknown_bounds(self):
        doc = json.loads(CATALOG.read_text())
        self.assertEqual(doc["schema"], "trollfx-es5510-factory-parameter-catalog-v0.1")
        self.assertEqual([x["id"] for x in doc["effects"]], ["ROM-01", "ROM-02"])
        expected = {
            ("ROM-01", "reverb_mix_bus1"): ("0x7C", [(28, "0x3D0000"), (29, "0x3F0000")]),
            ("ROM-01", "reverb_mix_bus2"): ("0x7A", [(28, "0x3D0000"), (29, "0x3F0000")]),
            ("ROM-02", "reverb_mix_bus1"): ("0x7C", [(25, "0x350000"), (26, "0x370000")]),
            ("ROM-02", "reverb_mix_bus2"): ("0x7A", [(25, "0x350000"), (26, "0x370000")]),
        }
        seen = set()
        for effect in doc["effects"]:
            for parameter in effect["parameters"]:
                key = (effect["id"], parameter["id"])
                seen.add(key)
                gpr, points = expected[key]
                self.assertIsNone(parameter["display"]["full_range"])
                self.assertIsNone(parameter["display"]["factory_default"])
                self.assertIsNone(parameter["efe_parameter_record_offset"])
                self.assertIsNone(parameter["firmware_parameter_cpu_address"])
                self.assertEqual([(p["display_value"], p["raw24"]) for p in parameter["verified_points"]], points)
                self.assertTrue(all(p["gpr"] == gpr for p in parameter["verified_points"]))
                self.assertIn("unverified", parameter["experimental_runtime_live_safety"])
        self.assertEqual(seen, set(expected))

    def test_catalog_does_not_contain_private_capture_paths_or_program_payloads(self):
        text = CATALOG.read_text()
        for forbidden in ("/home/gamer/", "/mnt/c/Users/", "session.log", "render.wav", "program.bin"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
