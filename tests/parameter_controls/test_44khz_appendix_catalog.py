import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "build_44khz_appendix_catalog",
    ROOT / "tools/parameter_controls/build_44khz_appendix_catalog.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
MODEL_SPEC = importlib.util.spec_from_file_location(
    "hall_decay_coefficient_model",
    ROOT / "tools/parameter_controls/hall_decay_coefficient_model.py")
model = importlib.util.module_from_spec(MODEL_SPEC)
MODEL_SPEC.loader.exec_module(model)


class AppendixCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = builder.build()
        self.effects = {e["name"]: e for e in self.catalog["effects"]}

    def test_appendix_has_twelve_additional_algorithms_and_215_field_headings(self):
        self.assertEqual(len(self.effects), 12)
        self.assertEqual(self.catalog["parameter_field_heading_count"], 215)
        self.assertIn("not additional numbered ROM effect slots", self.catalog["scope_note"])
        self.assertEqual(self.catalog["variation_and_modulation"]["variation_count"], 4)
        self.assertEqual(self.catalog["variation_and_modulation"]["modulator_count_per_variation"], 2)
        self.assertIn("saved value", self.catalog["variation_and_modulation"]["restriction"])

    def test_all_parameter_ranges_are_documented_separately_from_runtime_status(self):
        for effect in self.catalog["effects"]:
            for param in effect["parameters"]:
                self.assertTrue(param["documented_range"], (effect["name"], param["display_name"]))
                self.assertFalse(param["os_observed"])
                self.assertEqual(param["register_mapping"], "unverified")

    def test_plate2_excludes_early_reflection_controls(self):
        names = {p["display_name"] for p in self.effects["44LUSH PLAT2"]["parameters"]}
        self.assertNotIn("ER TIME (L)", names)
        self.assertNotIn("ER LEVEL (R)", names)

    def test_independent_chorus_voices_and_left_right_times_are_distinct(self):
        names = {p["display_name"] for p in self.effects["44DDL+CH+REV"]["parameters"]}
        for stem in ("CH WET LEV", "CH WET PAN", "CH LFORATE", "CH WIDTH", "CH DELAY"):
            self.assertEqual(sum(n.startswith(stem) for n in names), 3)
        delay_names = {p["display_name"] for p in self.effects["44EQ+DDL"]["parameters"]}
        self.assertTrue({"ECHOTIME (L)", "ECHOTIME (R)"} <= delay_names)

    def test_regeneration_retains_manual_only_status_and_stable_50_slot_catalog(self):
        generated = builder.build()
        self.assertEqual(json.dumps(generated, sort_keys=True),
                         json.dumps(self.catalog, sort_keys=True))
        rom = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json").read_text())
        self.assertEqual(len(rom["effects"]), 50)
        self.assertEqual(sum(e["parameter_count_documented"] for e in rom["effects"]), 594)
        self.assertEqual(rom["additional_os2_appendix_catalog"]["effect_count"], 12)

    def test_cpu_coefficient_arithmetic_reproduces_only_the_observed_internal_points(self):
        self.assertEqual(model.coefficient_registers(0x34),
                         {0x03: 0x340000, 0x04: 0xCC0000, 0x05: 0x6ADFFF,
                          0x5B: 0x080034, 0x6E: 0x340000})
        self.assertEqual(model.coefficient_registers(0x35),
                         {0x03: 0x350000, 0x04: 0xCB0000, 0x05: 0x6A0DFF,
                          0x5B: 0x080035, 0x6E: 0x350000})
        with self.assertRaises(ValueError):
            model.coefficient_registers(0x80)


if __name__ == "__main__":
    unittest.main()
