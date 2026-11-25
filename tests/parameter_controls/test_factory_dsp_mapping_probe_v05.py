import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "factory_dsp_mapping_probe_v05", ROOT / "tools/parameter_controls/run_factory_dsp_mapping_probe_v05.py")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class FactoryDspMappingProbeV05Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads((ROOT / "docs/ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json").read_text())

    def test_compound_secondary_value_uses_its_exact_cursor_page(self):
        location = PROBE.select_field(self.inventory, 1, 1, "DETUNE AMT")
        self.assertEqual(location["page"]["ordinal"], 10)
        self.assertEqual(location["page"]["display"].strip(), "DETUNE RATE=26 AMT=9")
        self.assertEqual(location["field"]["displayed_value"], "9")
        self.assertEqual(location["marker_start"], 19)
        self.assertEqual(location["needle"], "AMT=")

    def test_lr_delay_value_is_not_confused_with_the_other_cursor(self):
        location = PROBE.select_field(self.inventory, 4, 1, "BS1 TIME R")
        self.assertEqual(location["page"]["ordinal"], 4)
        self.assertEqual(location["field"]["displayed_value"], "700")
        self.assertEqual(location["marker_start"], 18)
        self.assertEqual(location["needle"], "R=")

    def test_signed_factory_variation_value_is_preserved(self):
        location = PROBE.select_field(self.inventory, 8, 3, "FLANGE FEEDBACK")
        self.assertEqual(location["field"]["displayed_value"], "-78")
        self.assertIn("FLANGE FEEDBACK=-78", location["page"]["display"])

    def test_register_parser_keeps_gpr_and_paired_writes_ordered(self):
        log = '''ESPHOST event=4 cycles=100 frame=3 pc=fff97354 both 90 <- 000000000000 / 0007f7 t=0.1
ESPHOST event=5 cycles=120 frame=4 pc=fff97364 gpr 91 <- 000c91 t=0.2
'''
        events = PROBE.parse_register_events(log)
        self.assertEqual([e["write_kind"] for e in events], ["instruction_and_gpr", "gpr"])
        self.assertEqual(events[0]["gpr"], "0x90")
        self.assertEqual(events[0]["instruction_word"], "0x000000000000")
        window = PROBE.summarize_write_window(events, 90, 121)
        self.assertEqual(list(window["gpr_summary"]), ["0x90", "0x91"])
        self.assertEqual(window["write_count"], 2)

    def test_register_parser_accepts_optional_cpu_caller_trace_field(self):
        text = "ESPHOST event=4 cycles=100 frame=2 pc=fff97792 caller=fff97694 gpr 6e <- 340000 t=0.1\n"
        events = PROBE.parse_register_events(text)
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]["gpr"], events[0]["value24"]), ("0x6e", "0x340000"))

    def test_build_command_uses_inventoried_target_and_direction(self):
        location = PROBE.select_field(self.inventory, 6, 1, "CHORUS FEEDBACK")
        args = SimpleNamespace(cli=Path("cli"), roms=Path("roms"), disk=Path("os.img"),
                               timeout=90, slot=6, variation=1, repetitions=2, edit_button=11, revert_button=10)
        command = PROBE.build_command(args, {"select_raw": 90}, location)
        self.assertIn("--panel-probe-field", command)
        value = command[command.index("--panel-probe-field") + 1].split(",")
        self.assertEqual(value[2:8], ["1", str(location["page"]["ordinal"]), "-1", "2", "11", "10"])


if __name__ == "__main__":
    unittest.main()
