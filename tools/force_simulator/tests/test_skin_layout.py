"""Pure-Python checks for the generated SDK skin readability profile."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
import sys
sys.path.insert(0, str(HERE))
from compact_skin import compact_skin
from render import layout_report
from skin_model import load_skin

SKIN = ROOT / "force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/Plugin Skins"


class GeneratedSkinLayoutTests(unittest.TestCase):
    def test_profile_is_idempotent_and_preserves_page_and_qlink_maps(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "skin"
            shutil.copytree(SKIN, target)
            tui = target / "TUI.json"
            qlinks_before = (target / "Q-Links.json").read_bytes()
            compact_skin(tui)
            first = tui.read_bytes()
            compact_skin(tui)
            self.assertEqual(tui.read_bytes(), first)
            self.assertEqual((target / "Q-Links.json").read_bytes(), qlinks_before)

            document = json.loads(first)
            tabs = document["pageData"]["tabs"]
            self.assertEqual([tab["tabName"] for tab in tabs], ["BROWSE", "EDIT", "MIX"])
            model = load_skin(target)
            self.assertEqual(model["pages"][1]["qlinks"]["1"], 46)
            self.assertEqual(model["pages"][1]["qlinks"]["8"], 53)

    def test_long_hall_room_and_unmapped_strings_fit_without_widget_overlap(self):
        model = load_skin(SKIN)
        names = {i: f"EDIT SLOT {i - 45}" for i in range(46, 54)}
        display = {
            46: "REVERB MIX BUS1: 28", 47: "REVERB MIX BUS2: 28",
            48: "DECAY TIME: 41", 49: "HI FREQ DAMPING: 31",
            50: "NO VERIFIED CONTROL", 51: "NO VERIFIED CONTROL",
            52: "NO VERIFIED CONTROL", 53: "NO VERIFIED CONTROL",
        }
        report = layout_report(model, {}, lambda i: display.get(i, ""), lambda i: names.get(i, ""))
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["warnings"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
