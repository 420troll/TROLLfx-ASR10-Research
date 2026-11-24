import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools/ghidra/interleave_rom_pair.py"
spec = importlib.util.spec_from_file_location("interleave_rom_pair", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class InterleaveRomPairTests(unittest.TestCase):
    def test_interleaves_byte_lanes_high_then_low(self):
        self.assertEqual(module.interleave(bytes([0x10, 0x20]), bytes([0x11, 0x21])),
                         bytes([0x10, 0x11, 0x20, 0x21]))

    def test_rejects_unequal_lanes(self):
        with self.assertRaises(ValueError):
            module.interleave(b"a", b"bc")


if __name__ == "__main__":
    unittest.main()
