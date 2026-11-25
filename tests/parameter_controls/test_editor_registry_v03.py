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
        self.assertEqual(sum(e["verified_control_count"] for e in self.registry["effects"]), 16)
        self.assertEqual(sum(e["editor_status"] == "unmapped-no-verified-controls"
                             for e in self.registry["effects"]), 40)
        for effect in self.registry["effects"]:
            for item in effect["documented_controls"]:
                self.assertFalse(item["editable"])
                self.assertIn("unverified", item["status"])

    def test_banks_bind_only_verified_parameters_and_keep_stable_indices(self):
        controls = [c for e in self.registry["effects"] for c in e["verified_controls"]]
        self.assertEqual(sorted(c["plugin_parameter_index"] for c in controls), list(range(8, 24)))
        self.assertEqual(sum(c["bank"] == 1 for c in controls), 8)
        self.assertEqual(sum(c["bank"] == 2 for c in controls), 8)
        for control in controls:
            self.assertTrue(control["editable"])
            self.assertEqual(control["interpolation"], "unsupported")
            self.assertTrue(control["verified_points"])
            self.assertEqual(control["qlink"], control["plugin_parameter_index"] - 7)
        pages = self.ui["pages"]
        self.assertEqual([p["name"] for p in pages], ["BROWSE", "MIX", "EDIT"])
        edit = pages[2]["controls"]
        self.assertEqual(len(edit), 16)
        layout = (list(range(20, 24)) + list(range(16, 20)) +
                  list(range(12, 16)) + list(range(8, 12)))
        control_by_index = {c["plugin_parameter_index"]: c for c in controls}
        expected = [control_by_index[index] for index in layout]
        self.assertEqual([c["param"] for c in edit], [c["plugin_parameter_name"] for c in expected])
        for item, control in zip(edit, expected):
            self.assertEqual(item["visibleWhen"], {"param": "FX Slot", "index": control["slot"] - 1})

    def test_generation_is_reproducible(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/parameter_controls/build_editor_registry_v03.py"), "--check"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
