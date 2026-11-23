import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("esp_capture", ROOT / "tools" / "esp_capture.py")
esp_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(esp_capture)


def fixture(end_at=59):
    ins = [bytearray(6) for _ in range(160)]
    end_word = 0x00000000F000
    ins[end_at][:] = end_word.to_bytes(6, "big")
    program = b"".join(ins)
    gprs = bytes(192 * 3)
    specials = bytes(22 * 3)
    state = bytearray(74)
    struct.pack_into("<I", state, 7, 0xFF)
    struct.pack_into("<I", state, 11, 0xFFFF00)
    struct.pack_into("<I", state, 15, 0x100)
    dram = bytearray(1 << 21)
    dram[0:2] = b"4\x12"
    payload = program + gprs + specials + state + dram
    header = b"ES5510C\0" + struct.pack(
        "<9I", 1, 44, 160, 192, 22, 1 << 20, 1, 74, len(payload)
    )
    return header + payload


class ES5510CaptureTests(unittest.TestCase):
    def test_valid_capture_and_program_end(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "synthetic.esp"
            p.write_bytes(fixture())
            summary = esp_capture.read_capture(p)
        self.assertEqual(summary["program"]["active_words_through_first_END"], 60)
        self.assertEqual(summary["program"]["END_indices"], [59])
        self.assertEqual(summary["runtime"]["memory_configuration"]["memshift"], 0)
        self.assertEqual(summary["runtime"]["dram_nonzero_words"], 1)

    def test_truncated_capture_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "truncated.esp"
            p.write_bytes(fixture()[:-1])
            with self.assertRaisesRegex(ValueError, "length/flags"):
                esp_capture.read_capture(p)

    def test_invalid_magic_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "invalid.esp"
            p.write_bytes(b"badmagic" + fixture()[8:])
            with self.assertRaisesRegex(ValueError, "not an ES5510C"):
                esp_capture.read_capture(p)


if __name__ == "__main__":
    unittest.main()
