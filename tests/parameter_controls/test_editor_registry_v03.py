import json
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "docs/ASR10_FACTORY_EDITOR_REGISTRY_V03.json"
UI_PATH = ROOT / "force_plugin/ui.json"
EFFECTS_PATH = ROOT / "force_plugin/effects.json"


class EditorRegistryV03Tests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads(REGISTRY_PATH.read_text())
        self.ui = json.loads(UI_PATH.read_text())
        self.effects = json.loads(EFFECTS_PATH.read_text())

    def test_fifty_effects_have_explicit_verified_or_unmapped_status(self):
        self.assertEqual(self.registry["schema"], "trollfx-asr10-factory-editor-registry-v03")
        self.assertEqual(len(self.registry["effects"]), 50)
        self.assertEqual([e["slot"] for e in self.registry["effects"]], list(range(1, 51)))
        self.assertEqual([e["factory_name"] for e in self.registry["effects"]],
                         [e["name"] for e in self.effects])
        self.assertEqual(sum(e["verified_control_count"] for e in self.registry["effects"]), 19)
        self.assertEqual(sum(e["editor_status"] == "unmapped-no-verified-controls"
                             for e in self.registry["effects"]), 37)
        for effect in self.registry["effects"]:
            for item in effect["documented_controls"]:
                self.assertFalse(item["editable"])
                self.assertIn("unverified", item["status"])

    def test_banks_bind_only_verified_parameters_and_keep_stable_indices(self):
        controls = [c for e in self.registry["effects"] for c in e["verified_controls"]]
        self.assertEqual(sorted(c["plugin_parameter_index"] for c in controls), list(range(8, 27)))
        self.assertEqual(sum(c["bank"] == 1 for c in controls), 8)
        self.assertEqual(sum(c["bank"] == 2 for c in controls), 8)
        self.assertEqual(sum(c["bank"] == 3 for c in controls), 3)
        for control in controls:
            self.assertTrue(control["editable"])
            self.assertEqual(control["interpolation"], "unsupported")
            self.assertTrue(control["verified_points"])
            expected_qlink = (control["plugin_parameter_index"] - 7
                              if control["plugin_parameter_index"] <= 23
                              else control["plugin_parameter_index"] - 23)
            self.assertEqual(control["qlink"], expected_qlink)
        pages = self.ui["pages"]
        self.assertEqual([p["name"] for p in pages], ["BROWSE", "EDIT", "MIX"])
        edit = pages[1]["controls"]
        positions = [12, 13, 14, 15, 8, 9, 10, 11]
        self.assertEqual([edit[i]["param"] for i in positions],
                         [f"EDIT SLOT {i}" for i in range(1, 9)])
        self.assertEqual([edit[i]["visibleWhen"]["param"] for i in positions],
                         [f"SLOT {i} ON" for i in range(1, 9)])
        self.assertFalse(any(c.get("param") in {x["plugin_parameter_name"] for x in controls}
                             for page in pages for c in page["controls"] if isinstance(c, dict)))

    def test_v3_ranges_do_not_expand_writable_register_points(self):
        effects = {e["slot"]: e for e in self.registry["effects"]}
        expected = {(1, "decay_time"): ("0", "99"),
                    (3, "diffusion"): ("0", "99"),
                    (3, "hi_freq_damping"): ("0", "99")}
        for (slot, ident), (lo, hi) in expected.items():
            control = next(c for c in effects[slot]["verified_controls"] if c["id"] == ident)
            self.assertEqual((control["verified_display_range"]["minimum"],
                              control["verified_display_range"]["maximum"]), (lo, hi))
            self.assertEqual(len(control["verified_points"]), 2)
        for slot, ident in ((5, "delay_time_l"), (8, "flange_rate"), (39, "quality")):
            control = next(c for c in effects[slot]["verified_controls"] if c["id"] == ident)
            self.assertIsNone(control["verified_display_range"])
            self.assertEqual(len(control["verified_points"]), 2)
        self.assertEqual([c["id"] for c in effects[2]["verified_controls"]],
                         ["reverb_mix_bus1", "reverb_mix_bus2"])

    def test_generation_is_reproducible(self):
        spec = importlib.util.spec_from_file_location(
            "editor_registry_v03", ROOT / "tools/parameter_controls/build_editor_registry_v03.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(self.registry, module.build_registry())
        self.assertEqual((ROOT / "include/trollfx/es5510_factory_editor_v03.hpp").read_text(),
                         module.make_header(self.registry))


if __name__ == "__main__":
    unittest.main()
