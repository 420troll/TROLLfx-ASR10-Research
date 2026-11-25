import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "factory_editor_inventory_v04", ROOT / "tools/parameter_controls/run_factory_editor_inventory_v04.py")
INVENTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INVENTORY)


class FactoryEditorInventoryV04Tests(unittest.TestCase):
    def test_exact_lcd_and_cursor_attribute_pages_are_preserved(self):
        log = '''ESP_ROM_SELECT id=01 time=5.0 display=FX=ROM-01 HALL REVERB
PANEL_EDITOR_VARIATION_BEGIN id=editor_scan variation=1 display="VAR=1 FAVORITE REVERB "
PANEL_EDITOR_PAGE id=editor_scan variation=1 ordinal=0 display="VAR=1 FAVORITE REVERB " underline="                      " cursor="                      " cycles=100 frame=20
PANEL_EDITOR_PAGE id=editor_scan variation=1 ordinal=9 display="DETUNE RATE=26 AMT=9  " underline="            ^^        " cursor="                      " cycles=200 frame=40
PANEL_EDITOR_PAGE id=editor_scan variation=1 ordinal=10 display="DETUNE RATE=26 AMT=9  " underline="                   ^^ " cursor="                      " cycles=210 frame=42
PANEL_EDITOR_VARIATION_DONE id=editor_scan variation=1 page_transitions=14
PANEL_EDITOR_SCAN_DONE id=editor_scan variations=1
'''
        result = INVENTORY.parse_inventory_log(log, 1)
        self.assertTrue(result["selection_verified"])
        self.assertTrue(result["scan_completed"])
        self.assertEqual(result["variation_count"], 1)
        self.assertEqual(len(result["pages"]), 3)
        self.assertEqual(result["pages"][1]["display"], result["pages"][2]["display"])
        self.assertNotEqual(result["pages"][1]["underline"], result["pages"][2]["underline"])
        fields = result["pages"][1]["displayed_fields"]
        self.assertEqual([(f["label"], f["displayed_value"]) for f in fields],
                         [("DETUNE RATE", "26"), ("DETUNE AMT", "9")])
        self.assertEqual(result["pages"][1]["selected_fields"][0]["field_label"], "DETUNE RATE")
        self.assertEqual(result["pages"][2]["selected_fields"][0]["field_label"], "DETUNE AMT")

    def test_paired_abbreviated_lcd_values_remain_distinct(self):
        cases = {
            "BS1 TIME L=350  R=700 ": [("BS1 TIME L", "350"), ("BS1 TIME R", "700")],
            "DIST GAIN IN=25 OUT=50 ": [("DIST GAIN IN", "25"), ("DIST GAIN OUT", "50")],
        }
        for display, expected in cases.items():
            with self.subTest(display=display):
                fields = INVENTORY.lcd_fields(display)
                self.assertEqual([(f["label"], f["displayed_value"]) for f in fields], expected)

    def test_gpr_and_paired_instruction_gpr_events_are_separate(self):
        log = '''ESPHOST event=1 cycles=10 frame=1 pc=fff97354 both 9f <- 000000000000 / 000000 t=0.001000
ESPHOST event=2 cycles=20 frame=1 pc=fff97364 gpr f4 <- 0000ff t=0.001000
PANEL_EDITOR_PAGE id=editor_scan variation=1 ordinal=0 display="X=1                  " underline="                      " cursor="                      " cycles=30 frame=2
'''
        result = INVENTORY.parse_inventory_log(log, 1)
        writes = result["pages"][0]["dsp_register_window"]["ordered_writes"]
        self.assertEqual([w["write_kind"] for w in writes], ["instruction_and_gpr", "gpr"])
        self.assertEqual([w["gpr"] for w in writes], ["0x9f", "0xf4"])
        self.assertEqual(writes[0]["instruction_word"], "0x000000000000")

    def test_build_command_requests_variation_sweep_and_no_audio_artifact(self):
        args = SimpleNamespace(cli=Path("cli"), roms=Path("roms"), disk=Path("os.img"),
                               timeout=90, max_pages=64)
        command = INVENTORY.build_command(args, {"select_raw": 79}, 1)
        self.assertIn("--panel-scan-effects", command)
        self.assertIn("/dev/null", command)
        action = command[command.index("--panel-scan-effects") + 1]
        self.assertEqual(action.split(",")[-2:], ["VAR=", "editor_scan"])
        self.assertEqual(action.split(",")[3], "4")

    def test_noncomplete_scans_and_deferred_slot_remain_distinct(self):
        report = INVENTORY.parse_inventory_log("PANEL_EDITOR_SCAN_NO_CHANGE id=editor_scan variation=1 phase=1 display=\"X\"", 3)
        self.assertFalse(report["scan_completed"])
        self.assertEqual(report["failure"]["event"], "SCAN_NO_CHANGE")


if __name__ == "__main__":
    unittest.main()
