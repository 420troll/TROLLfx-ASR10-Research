#!/usr/bin/env python3
"""Smoke-test the operator-driven sampler with a fake, read-only SSH command."""
import csv
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/force_hardware/measure_force_cpu.sh"


class CpuSamplerTest(unittest.TestCase):
    def test_records_all_four_states_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            fake_bin = tmp / "bin"
            fake_bin.mkdir()
            fake_ssh = fake_bin / "ssh"
            fake_ssh.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "i=1\n"
                "while [ $i -le 10 ]; do echo \"$i,12,86\"; i=$((i+1)); done\n"
            )
            fake_ssh.chmod(0o755)
            output = tmp / "cpu.csv"
            env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}")
            subprocess.run([str(SCRIPT), "fake-force", "10", "1", "5", str(output)],
                           input="\n\n\n\n", text=True, env=env, check=True,
                           stdout=subprocess.DEVNULL)
            with output.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 40)
            self.assertEqual({r["state"] for r in rows},
                             {"bypass", "hall_reverb", "8_voice_chor", "pitch_shift"})
            self.assertTrue(all(r["mpc_cpu_pct"] == "12" and r["system_idle_pct"] == "86"
                                for r in rows))
            with self.assertRaises(subprocess.CalledProcessError):
                subprocess.run([str(SCRIPT), "fake-force", "10", "1", "5", str(output)],
                               input="", text=True, env=env, check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()
