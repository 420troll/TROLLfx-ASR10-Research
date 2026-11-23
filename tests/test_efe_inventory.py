import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("efe_inventory", ROOT / "tools" / "profile_efe_objects.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class EFEInventoryTests(unittest.TestCase):
    def test_valid_header_redacted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "private.efe"
            b = bytearray(128)
            for i, v in enumerate(b"TEST"):
                b[10 + 2*i] = v
            b[34:38] = (120).to_bytes(4, "big")
            b[38:40] = (46).to_bytes(2, "big")
            p.write_bytes(b)
            result = mod.profile(p)
            self.assertEqual(result["status"], "header_bounds_valid")
            self.assertEqual(result["name"], "TEST")
            self.assertEqual(result["undecoded_region_bytes"], 74)
            self.assertEqual(result["trailing_padding_bytes"], 8)
            self.assertNotIn("path", result)
            self.assertNotIn("raw", str(result))

    def test_invalid_bounds_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "invalid.efe"
            p.write_bytes(bytes(60))
            self.assertEqual(mod.profile(p)["status"], "header_bounds_invalid")

    def test_short_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "short.efe"
            p.write_bytes(b"abc")
            self.assertEqual(mod.profile(p)["status"], "too_short")

if __name__ == "__main__":
    unittest.main()
