#!/usr/bin/env python3
"""Focused checks for the physical QA matrix; these do not exercise hardware."""
import csv
import tempfile
import unittest
from pathlib import Path

from generate_hardware_test_matrix import FIELDS, generate

ROOT = Path(__file__).resolve().parents[2]


class HardwareMatrixTest(unittest.TestCase):
    def test_all_slots_are_present_and_unrun(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "matrix.csv"
            count = generate(ROOT / "force_plugin/effects.json", output)
            with output.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(count, 50)
            self.assertEqual([r["slot"] for r in rows], [str(i) for i in range(1, 51)])
            self.assertTrue(all(set(r) == set(FIELDS) for r in rows))
            self.assertTrue(all(r[k] == "NOT_RUN" for r in rows for k in FIELDS[3:]))

    def test_matrix_covers_requested_effect_families(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "matrix.csv"
            generate(ROOT / "force_plugin/effects.json", output)
            with output.open(newline="") as stream:
                families = {name for row in csv.DictReader(stream)
                            for name in row["families"].split(";")}
            self.assertTrue({"Reverb", "Delay", "Modulation", "Pitch", "Dynamics"}.issubset(families))


if __name__ == "__main__":
    unittest.main()
