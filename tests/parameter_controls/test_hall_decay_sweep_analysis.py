import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "analyze_hall_decay_sweep", ROOT / "tools/parameter_controls/analyze_hall_decay_sweep.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HallDecaySweepAnalysisTests(unittest.TestCase):
    def test_sparse_duplicate_code_rule_maps_full_raw_domain(self):
        shown = {MODULE.display(raw) for raw in range(128)}
        self.assertEqual(shown, set(range(100)))
        self.assertEqual(sum(MODULE.display(code) == MODULE.display(code - 1)
                             for code in MODULE.DUPLICATE_CODES), 28)

    def test_bidirectional_sweep_identifies_only_lookup_buckets(self):
        steps = []
        for value in range(1, 100):
            raws = [raw for raw in range(128) if MODULE.display(raw) == value]
            up = raws[0]
            steps.append({"segment": "to_max", "complete": True,
                          "to_display": f"DECAY TIME={value}",
                          "register_snapshot_after": {"0x6e": f"{up << 16:06x}"}})
        for value in range(98, -1, -1):
            raws = [raw for raw in range(128) if MODULE.display(raw) == value]
            down = raws[-1]
            steps.append({"segment": "to_origin", "complete": True,
                          "to_display": f"DECAY TIME={value}",
                          "register_snapshot_after": {"0x6e": f"{down << 16:06x}"}})
        result = MODULE.analyze({"variation": 1, "sweep_complete": True, "steps": steps})
        self.assertEqual(result["direction_mismatch_count"], 28)
        self.assertTrue(result["direction_mismatches_are_one_code"])
        self.assertTrue(result["matches_os_lookup_duplicate_buckets"])


if __name__ == "__main__":
    unittest.main()
