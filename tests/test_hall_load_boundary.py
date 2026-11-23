import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hall_load_boundary", ROOT / "tools/hall_load_boundary.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HallLoadBoundaryTests(unittest.TestCase):
    def test_orders_load_and_redacts_instruction_payload(self):
        text = "\n".join([
            "ESPPHASE kind=pa4_halt_assert frame=10 cycles=100 host_pc=001000",
            "ESPPHASE kind=halt frame=10 cycles=101 pc=001001 host_control=04",
            "ESPHOST event=1 cycles=102 frame=10 pc=001002 instr 00 <- 000000000000 t=0.1",
            "ESPPHASE kind=instruction_upload_start frame=10 cycles=102 pc=001002 address=00",
            "ESPHOST event=2 cycles=103 frame=10 pc=001003 both 01 <- 000000000001 / 000002",
            "ESPPHASE kind=host_dram_clear frame=11 pc=001004 halted=1",
            "ESP_ROM_SELECT id=01 time=0.2 cycles=104 frame=11 dsp_rate_hz=29761.895 otto_clock_hz=15238090 active_voices=31 host_output_rate_hz=44100 display=FX=ROM-01 HALL REVERB",
            "ESPPHASE kind=program_upload_summary frame=12 cycles=105 pc=001005 commits=2 unique_addresses=2 first_end=1 gpr_commits=1",
            "ESPPHASE kind=run_start frame=12 cycles=105 host_pc=001005 pc=00 alu_pending=0 mac_pending=0 host_serial=48 memshift=8 memsiz=0000ff memmask=ffff00 memincrement=000100 dlength=ffffff abase=000000 bbase=000000 dbase=001000 sigreg=ffffff",
            "ESPPHASE kind=first_instruction frame=12 cycles=105 host_pc=001005 pc=00 word=000000000000",
            "ESPPFRAME kind=input index=0 frame=12 cycles=105 host_pc=001005 serial=48 lanes=0000,0000,0000,0000,0000,0000,0000,0000",
            "ESPPFRAME kind=output index=0 frame=12 cycles=105 host_pc=001005 serial=48 lanes=0000,0000,0001,0001,0000,0000,0000,0000",
        ])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "trace.log"
            p.write_text(text)
            result = MODULE.summarize(p)
        self.assertEqual(result["selection_count"], 1)
        self.assertEqual(result["transaction_count"], 1)
        tx = result["transactions"][0]
        self.assertEqual(tx["selection"]["id"], 1)
        self.assertLess(tx["lifecycle"][0]["log_sequence"], tx["lifecycle"][-1]["log_sequence"])
        self.assertEqual(tx["upload"]["first_end"], 1)
        self.assertEqual(tx["transaction_halt_cpu_cycles"], 101)
        self.assertEqual([x["kind"] for x in tx["lifecycle"]],
                         ["pa4_halt_assert", "halt", "instruction_upload_start",
                          "host_dram_clear", "program_upload_summary", "run_start", "first_instruction"])
        self.assertEqual(tx["instruction_records"], 2)
        self.assertEqual(tx["gpr_records"], 1)
        self.assertEqual([x["kind"] for x in tx["serial_frame_checkpoints"]], ["input", "output"])
        self.assertEqual(tx["serial_frame_checkpoints"][0]["lane_count"], 8)
        self.assertNotEqual(tx["serial_frame_checkpoints"][0]["serial_lane_state_sha256"],
                            tx["serial_frame_checkpoints"][1]["serial_lane_state_sha256"])
        self.assertNotIn("000000000001", str(result))
        self.assertFalse(result["raw_payloads_included"])

    def test_repeated_loads_remain_separate_and_hash_state(self):
        base = "ESP_ROM_SELECT id=01 time={t} cycles={cy} frame={fr} dsp_rate_hz=29761.895 otto_clock_hz=15238090 active_voices=31 host_output_rate_hz=44100 display=FX=ROM-01 HALL REVERB"
        text = []
        for n in range(2):
            b = 100 + n * 20
            text.extend([base.format(t=n, cy=b, fr=b),
                         f"ESPPHASE kind=instruction_upload_start frame={b} cycles={b} pc=001000 address=00",
                         f"ESPHOST event={n+1} cycles={b+1} frame={b} pc=001001 instr 00 <- 000000000000 t=0.0",
                         f"ESPPHASE kind=program_upload_summary frame={b+2} cycles={b+2} pc=001002 commits=1 unique_addresses=1 first_end=0 gpr_commits=0",
                         f"ESPPHASE kind=run_start frame={b+2} cycles={b+2} host_pc=001002 pc=00 alu_pending=0 mac_pending=0 host_serial=48 memshift=8 memsiz=0000ff memmask=ffff00 memincrement=000100 dlength=ffffff abase=000000 bbase=000000 dbase=001000 sigreg=ffffff"])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "trace.log"
            p.write_text("\n".join(text))
            result = MODULE.summarize(p)
        self.assertEqual(result["transaction_count"], 2)
        self.assertEqual(result["transactions"][0]["instruction_state_sha256"],
                         result["transactions"][1]["instruction_state_sha256"])


if __name__ == "__main__":
    unittest.main()
