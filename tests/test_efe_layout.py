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
    def test_mixed_layout_uses_verified_prefix_gap_and_strides(self):
        result = mod.decode_layout(synthetic(), 29, 31)
        self.assertEqual(result["paired_records"], {"offset": 75, "count": 29, "stride": 9, "length": 261})
        self.assertEqual(result["mixed_gap"], {"offset": 336, "length": 3})
        self.assertEqual(result["instruction_only_records"], {"offset": 339, "count": 31, "stride": 6, "length": 186})
        self.assertEqual(result["suffix"]["length"], 75)
        self.assertFalse(result["payload_bytes_disclosed"])

    def test_instruction_only_layout_has_no_mixed_gap(self):
        result = mod.decode_layout(synthetic(), 0, 20)
        self.assertIsNone(result["paired_records"])
        self.assertIsNone(result["mixed_gap"])
        self.assertEqual(result["instruction_only_records"]["offset"], 75)

    def test_rejects_header_and_record_bounds(self):
        with self.assertRaises(ValueError):
            mod.decode_layout(b"short", 1, 0)
        with self.assertRaises(ValueError):
            mod.decode_layout(synthetic(size=120), 10, 10)

    def test_rejects_invalid_counts_and_header(self):
        with self.assertRaises(ValueError):
            mod.decode_layout(synthetic(), -1, 4)
        with self.assertRaises(ValueError):
            mod.decode_layout(synthetic(), 4, 0)
        data = bytearray(synthetic())
        data[34:38] = (999).to_bytes(4, "big")
        with self.assertRaises(ValueError):
            mod.decode_layout(bytes(data), 1, 1)


if __name__ == "__main__":
    unittest.main()
