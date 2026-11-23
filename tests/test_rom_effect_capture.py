import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rom_capture", ROOT / "tools" / "capture_asr10_rom_effects.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class RomEffectCaptureTests(unittest.TestCase):
    def test_os_display_enumeration_keeps_id_name_and_control_value(self):
        log = """[ 16.001s] |FX=ROM-01 HALL REVERB|
[ 16.151s] |FX=ROM-02 HALL REVERB|
[ 16.301s] |FX=ROM-02 SMALL ROOM|
[ 16.451s] |FX=ROM-03 SMALL ROOM|
"""
        result = capture.parse_display_log(log, 16.0, 0.15, [100, 200, 300, 400])
        self.assertEqual([x["id"] for x in result["entries"]], [1, 2, 3])
        self.assertEqual(result["entries"][0]["name"], "HALL REVERB")
        # The panel can repaint a row in fragments; choose the modal stable label.
        self.assertEqual(result["entries"][1]["name"], "SMALL ROOM")
        self.assertEqual(result["entries"][1]["select_raw"], 300)
        self.assertTrue(result["entries"][1]["display_variants"])

    def test_missing_ids_are_not_invented(self):
        result = capture.parse_display_log("[ 16.01s] |FX=ROM-04 SMALL ROOM|\n", 16, .15, [8, 9])
        self.assertEqual([x["id"] for x in result["entries"]], [4])
        self.assertEqual(result["entries"][0]["raw_values"], [8, 9])
        self.assertEqual(result["entries"][0]["select_raw"], 9)

    def test_private_output_rejects_checkout_and_accepts_external_temp(self):
        with self.assertRaisesRegex(ValueError, "outside the Git repository"):
            capture.private_dir(ROOT / "research_local")
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(capture.private_dir(Path(td)), Path(td).resolve())

    def test_status_separates_captured_failed_and_untested(self):
        inventory = {"entries": [{"id": i} for i in range(1, 5)]}
        manifest = {"effects": {"1": {"status": "captured"}, "3": {"status": "failed"}}}
        status = capture.summarize_status(inventory, manifest)
        self.assertEqual(status["captured"], [1])
        self.assertEqual(status["failed"], [3])
        self.assertEqual(status["untested"], [2, 4])

    def test_host_log_counts_initialization_and_commit_targets(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "host.log"
            p.write_text("ESPHOST gpr f4 <- 0000ff\nESPHOST both 00 <- ffffffffffff / ffffff\nESPHOST instr 01 <- 000000000000\nESPHOST ram wr ctl=00 dadr=000000 -> word 00000 dol=0000\n")
            summary = capture.host_event_summary(p)
        self.assertEqual(summary["event_counts"], {"gpr": 1, "instruction": 1, "combined": 1, "ram": 1})
        self.assertEqual(summary["unique_gpr_commit_indices"], 2)
        self.assertEqual(summary["unique_instruction_commit_indices"], 2)

    def test_snapshot_program_matches_host_commits_at_snapshot_time(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            ins = [bytes(6) for _ in range(160)]
            ins[1] = (0xF000).to_bytes(6, "big")
            body = b"".join(ins) + bytes(192*3 + 22*3 + 74 + 2)
            esp = d/"state.esp"
            esp.write_bytes(b"ES5510C\0" + struct.pack("<9I", 1, 44, 160, 192, 22, 1, 1, 74, len(body)) + body)
            log = d/"host.log"
            log.write_text("ESPHOST both 00 <- 000000000000 / 000000 t=4.000000\n"
                           "ESPHOST instr 01 <- 00000000f000 t=4.000000\n"
                           "ESPHOST instr 00 <- 0123456789ab t=5.000000\n")
            snap = {"program": {"active_words_through_first_END": 2}}
            self.assertTrue(capture.active_program_matches_host(log, esp, snap, 4.5)["verified"])
            result = capture.active_program_matches_host(log, esp, snap, 5.5)
            self.assertFalse(result["verified"])
            self.assertEqual(result["mismatched_active_indices"], [0])


if __name__ == "__main__":
    unittest.main()
