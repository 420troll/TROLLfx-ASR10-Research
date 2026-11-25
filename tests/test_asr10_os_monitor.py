import sys
import unittest
from collections import deque
from pathlib import Path
from threading import RLock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "asr10_os_monitor"))
import monitor
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "parameter_controls"))
import extract_os_cpu_parameter_trace


class MonitorParserTests(unittest.TestCase):
    def setUp(self):
        self.m = monitor.Monitor.__new__(monitor.Monitor)
        self.m.lock = RLock()
        self.m.events = deque(maxlen=3)
        self.m.registers = {}
        self.m.lcd = " " * 22
        self.m.underline = " " * 22
        self.m.cursor = " " * 22
        self.m.selected_slot = None
        self.m.selected_name = None
        self.m.variation = None
        self.m.slot_names = {1: "HALL REVERB"}
        self.m.mapping_status = {(1, "DECAY TIME"): {"status": "UNRESOLVED", "points": [40, 41]}}
        self.m.last_activity = None
        self.m.last_error = None
        self.m.process = None
        self.m.next_id = 1
        self.m.pending_edit = None
        self.m.pending_action = None
        self.m.diffs = deque(maxlen=100)

    def test_exact_lcd_and_cursor_are_kept(self):
        lcd = "DECAY TIME=40         "
        self.m.ingest_line(f'PANELLCD cycles=120 frame=7 lcd="{lcd}" underline="                      " cursor="         ^            "')
        s = self.m.status()
        self.assertEqual(s["lcd"], lcd)
        self.assertEqual(s["parameter"], "DECAY TIME")
        self.assertEqual(s["display_value"], "40")

    def test_gpr_event_and_writer_pc_are_recorded(self):
        self.m.ingest_line("ESPHOST event=7 cycles=800 frame=12 pc=fff97792 caller=fff979b6 gpr 03 <- 340000 t=0.010000")
        self.assertEqual(self.m.registers["0x03"], "0x340000")
        e = list(self.m.events)[0]
        self.assertEqual(e["pc"], "0xfff97792")
        self.assertEqual(e["caller"], "0xfff979b6")

    def test_effect_selection_and_variation_are_tracked_separately(self):
        self.m.ingest_line("ESP_ROM_SELECT id=01 time=1 cycles=2 frame=3 dsp_rate_hz=29761.895 display=FX=ROM-01  HALL REVERB")
        self.m.ingest_line('PANELLCD cycles=10 frame=1 lcd="VAR=3 FAVORITE REVERB " underline="                      " cursor="                      "')
        s = self.m.status()
        self.assertEqual((s["selected_slot"], s["selected_name"]), (1, "HALL REVERB"))
        self.assertEqual(s["variation"], 3)

    def test_edit_window_correlates_real_lcd_change_and_gpr(self):
        start = 'PANELLCD cycles=10 frame=1 lcd="DECAY TIME=40         " underline="                      " cursor="                      "'
        self.m.ingest_line(start)
        action = {"before_lcd": self.m.lcd, "before_underline": self.m.underline,
                  "before_registers": dict(self.m.registers),
                  "before_cursor": self.m.cursor, "writes": [], "write_ids": []}
        self.m.pending_edit = self.m.pending_action = action
        self.m.ingest_line("ESPHOST event=1 cycles=20 frame=2 pc=fff97792 gpr 03 <- 350000 t=0.001000")
        self.m.ingest_line('PANELLCD cycles=30 frame=3 lcd="DECAY TIME=41         " underline="                      " cursor="                      "')
        self.assertEqual(len(self.m.diffs), 1)
        self.assertEqual(self.m.diffs[0]["after_lcd"], "DECAY TIME=41         ")
        self.assertEqual(self.m.diffs[0]["writes"][0]["value"], "0x350000")
        self.assertEqual(self.m.diffs[0]["change_kind"], "parameter_value")

    def test_cursor_selects_the_active_field_on_multi_field_lcd(self):
        lcd = "DECAY=40  DAMP=22       "
        cursor = "            ^         "
        self.m.lcd, self.m.cursor = lcd, cursor
        s = self.m.status()
        self.assertEqual((s["parameter"], s["display_value"]), ("DAMP", "22"))

    def test_underline_selects_the_active_field_when_edit_cursor_is_blank(self):
        self.m.lcd = "DECAY=40  DAMP=22       "
        self.m.cursor = " " * 22
        self.m.underline = "            ^^        "
        s = self.m.status()
        self.assertEqual((s["parameter"], s["display_value"]), ("DAMP", "22"))

    def test_navigation_change_is_not_misreported_as_parameter_edit(self):
        self.m.ingest_line('PANELLCD cycles=10 frame=1 lcd="DECAY TIME=40         " underline="                      " cursor="^                     "')
        self.m.pending_action = {"before_lcd": self.m.lcd, "before_underline": self.m.underline,
                                 "before_cursor": self.m.cursor, "button": 17, "writes": [], "write_ids": []}
        self.m.ingest_line('PANELLCD cycles=20 frame=2 lcd="DAMPING=22            " underline="                      " cursor=" ^                    "')
        self.assertEqual(self.m.diffs[-1]["change_kind"], "navigation_or_page")
        self.assertEqual(self.m.diffs[-1]["before_lcd"], "DECAY TIME=40         ")

    def test_unstructured_emulator_output_is_discarded(self):
        self.m.ingest_line("failed to open /private/path/secret.img")
        self.assertIsNone(self.m.last_error)
        self.assertEqual(len(self.m.events), 0)

    def test_event_ring_is_bounded(self):
        for i in range(5):
            self.m._event({"type": "effect_select", "slot": i, "name": "test"})
        self.assertEqual(len(self.m.events), 3)


class CpuTraceParserTests(unittest.TestCase):
    def test_correlates_cpu_snapshot_to_matching_host_write(self):
        regs = ":".join(f"{i:08x}" for i in range(16))
        a2 = ":".join(f"{i:02x}" for i in range(32))
        a6 = ":".join(f"{i+32:02x}" for i in range(32))
        text = (f"ESPCALL cycles=100 frame=2 pc=fff979b6 sp=001e6e gpr=03 regs={regs} stack=00 a2mem={a2} a6mem={a6}\n"
                "ESPHOST event=7 cycles=150 frame=2 pc=fff97792 caller=fff979b6 gpr 03 <- 340000 t=0.1\n")
        out = extract_os_cpu_parameter_trace.parse_log(text)
        self.assertEqual(out["summary"]["writes_with_cpu_snapshot"], 1)
        self.assertEqual(out["writes"][0]["cpu_trace"]["a6"], 14)
        self.assertEqual(out["writes"][0]["value"], "0x340000")

    def test_accepts_older_cpu_snapshot_without_memory_windows(self):
        regs = ":".join(f"{i:08x}" for i in range(16))
        text = (f"ESPCALL cycles=100 frame=2 pc=fff979b6 sp=001e6e gpr=03 regs={regs} stack=00\n"
                "ESPHOST event=7 cycles=150 frame=2 pc=fff97792 caller=fff979b6 gpr 03 <- 340000 t=0.1\n")
        out = extract_os_cpu_parameter_trace.parse_log(text)
        self.assertEqual(out["summary"]["cpu_snapshots"], 1)
        self.assertIsNone(out["writes"][0]["cpu_trace"]["a6_memory_window_hex"])

    def test_parses_bounded_instruction_and_parameter_memory_window(self):
        text = (
            'PANELLCD cycles=90 frame=1 lcd="DECAY TIME=40         " underline="                      " cursor="                      "\n'
            "ESPTRACE_BEGIN cycles=150 frame=2 gpr=6e value_before=330000 a6=02a44d\n"
            "ESPINS cycles=149 pc=fff97998 d=00000034:00000000 a=00000000:0002a44d\n"
            "ESPMEM cycles=148 pc=fff91000 address=02a44d size=1 before=33 after=34\n"
            "ESPTRACE_END cycles=150 instruction_count=1 memory_write_count=1\n"
        )
        out = extract_os_cpu_parameter_trace.parse_log(text)
        self.assertEqual(out["summary"]["parameter_cpu_windows"], 1)
        window = out["parameter_cpu_windows"][0]
        self.assertEqual(window["instructions"][0]["pc"], "0xfff97998")
        self.assertEqual(window["memory_writes"][0]["address"], "0x02a44d")
        self.assertEqual(window["lcd_snapshot_before"]["lcd"], "DECAY TIME=40         ")

if __name__ == "__main__":
    unittest.main()
