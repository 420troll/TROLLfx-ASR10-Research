import json
import subprocess
import sys
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
        self.assertEqual([p["name"] for p in pages], ["BROWSE", "MIX", "EDIT", "EDIT 2"])
        edit = pages[2]["controls"]
        self.assertEqual(len(edit), 16)
        layout = (list(range(20, 24)) + list(range(16, 20)) +
                  list(range(12, 16)) + list(range(8, 12)))
        control_by_index = {c["plugin_parameter_index"]: c for c in controls}
        expected = [control_by_index[index] for index in layout]
        self.assertEqual([c["param"] for c in edit], [c["plugin_parameter_name"] for c in expected])
        for item, control in zip(edit, expected):
            self.assertEqual(item["visibleWhen"], {"param": "FX Slot", "index": control["slot"] - 1})
        edit_v3 = pages[3]["controls"]
        self.assertEqual(len(edit_v3), 16)
        self.assertEqual([c["param"] for c in edit_v3[12:15]], [
            "BS1 TIME L (44KHZ DELAYS)", "FLANGE RATE", "QUALITY"])
        self.assertEqual([c["visibleWhen"]["index"] for c in edit_v3[12:15]], [4, 7, 38])

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
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/parameter_controls/build_editor_registry_v03.py"), "--check"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
