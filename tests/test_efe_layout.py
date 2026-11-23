import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("efe_layout", ROOT / "tools" / "efe_layout.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def synthetic(size=600, ucode=64):
    data = bytearray(size)
    data[34:38] = size.to_bytes(4, "big")
    data[38:40] = ucode.to_bytes(2, "big")
    return bytes(data)


class EFELayoutTests(unittest.TestCase):
    def test_geometry_uses_evidence_supplied_starts_and_counts(self):
        result = mod.describe_layout(synthetic(), paired_start_gpr=91, paired_count=2,
                                     instruction_start=118, instruction_count=3)
        self.assertEqual(result["paired_records"], {"offset": 91, "count": 2, "stride": 9, "length": 18})
        self.assertEqual(result["instruction_only_records"],
                         {"offset": 118, "count": 3, "stride": 6, "length": 18})
        self.assertEqual(result["unclassified"], {
            "prefix_bytes_from_FxUcode": 27,
            "gap_bytes_between_segments": 9,
            "suffix_bytes_to_FxSize": 464,
            "outside_declared_extent": 0,
        })

    def test_instruction_only_variant_has_no_assumed_prefix_or_gap(self):
        result = mod.describe_layout(synthetic(), instruction_start=129, instruction_count=20)
        self.assertIsNone(result["paired_records"])
        self.assertEqual(result["instruction_only_records"]["offset"], 129)
        self.assertEqual(result["unclassified"]["prefix_bytes_from_FxUcode"], 65)
        self.assertIsNone(result["unclassified"]["gap_bytes_between_segments"])

    def test_alias_is_explicit_and_does_not_add_a_source_record(self):
        result = mod.describe_layout(synthetic(size=1400, ucode=800), paired_start_gpr=811,
                                     paired_count=58, instruction_start=1336,
                                     instruction_count=1, aliases=((58, 0),))
        self.assertEqual(result["aliases"], [{"active_index": 58, "source_active_index": 0}])
        self.assertEqual(result["unclassified"]["gap_bytes_between_segments"], 3)
        self.assertEqual(result["unclassified"]["suffix_bytes_to_FxSize"], 58)

    def test_rejects_invalid_bounds_counts_and_overlapping_segments(self):
        with self.assertRaises(ValueError):
            mod.describe_layout(b"short", instruction_start=60, instruction_count=1)
        with self.assertRaises(ValueError):
            mod.describe_layout(synthetic(size=120), paired_start_gpr=75, paired_count=10)
        with self.assertRaises(ValueError):
            mod.describe_layout(synthetic(), paired_start_gpr=75, paired_count=1,
                                instruction_start=80, instruction_count=1)
        with self.assertRaises(ValueError):
            mod.describe_layout(synthetic(), instruction_start=75, instruction_count=1,
                                aliases=((2, 1), (2, 0)))


if __name__ == "__main__":
    unittest.main()
