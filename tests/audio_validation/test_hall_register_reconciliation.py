import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/audio_validation/build_hall_register_reconciliation.py"


class HallRegisterReconciliationTests(unittest.TestCase):
    def test_spr_addresses_use_full_0xea_based_payload_offsets(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # Give every SPR a distinguishable value so an off-by-four mapping
            # cannot accidentally pass for the selected addresses.
            spr = b"".join((0x100000 + i).to_bytes(3, "big") for i in range(22))
            (base / "spr.bin").write_bytes(spr)
            manifest = {"capture": {"run_frame": 3},
                        "special_registers": {"path": "spr.bin"}}
            (base / "manifest.json").write_text(json.dumps(manifest))
            rows = []
            for i in range(16):
                rows.append({"capture": "fresh-2020", "gpr_address": 0x90 + i,
                             "expected_manifest_hex": "000000",
                             "observed_hall_transaction_only_hex": "000000",
                             "observed_full_history_hex": "000000",
                             "resolved_by_prior_history": True,
                             "last_write_before_hall_transaction": None})
            (base / "gpr.json").write_text(json.dumps({"registers": rows}))
            with (base / "events.csv").open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(("event", "cycles", "frame", "seconds", "pc", "type", "fields..."))
                w.writerow(("1", "10", "1", "0", "fff000", "PIPELINE_CLEAR", "reason=boot"))
                w.writerow(("2", "11", "1", "0", "fff000", "GPR_COMMIT", "index=f9", "value=10000f"))
                w.writerow(("3", "20", "2", "0", "fff000", "PIPELINE_CLEAR", "reason=hall"))
                w.writerow(("4", "30", "3", "0", "fff000", "DSP_RUN", "program_ready=1"))
            output = base / "table.json"
            subprocess.run(["python3", str(SCRIPT), str(base / "gpr.json"),
                            str(base / "manifest.json"), str(base / "events.csv"),
                            "--out", str(output)], check=True, capture_output=True, text=True)
            table = json.loads(output.read_text())
            regs = {int(r["address"], 16): r for r in table["registers"]}
            self.assertEqual(regs[0xEE]["expected_manifest"], f"{0x100000 + 4:06X}")
            self.assertEqual(regs[0xF3]["expected_manifest"], f"{0x100000 + 9:06X}")
            self.assertEqual(regs[0xF9]["expected_manifest"], f"{0x100000 + 15:06X}")
            self.assertTrue(regs[0xF9]["resolved"])
            self.assertFalse(regs[0xEE]["resolved"])


if __name__ == "__main__":
    unittest.main()
