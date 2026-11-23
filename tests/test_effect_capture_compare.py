import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("compare_capture", ROOT / "tools" / "compare_asr10_effect_capture.py")
compare_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_capture)


def fixtures(directory: Path):
    obj = bytearray(641)
    fx_name = b"PAIRTEST"
    for i, c in enumerate(fx_name):
        obj[10 + i * 2] = c
    obj[34:38] = (641).to_bytes(4, "big")
    obj[38:40] = (100).to_bytes(2, "big")
    words = [0x120000000000 + i * 0x10000 for i in range(59)] + [0x00000000F000]
    gprs = [0x300000 + i for i in range(29)]
    for i, value in enumerate(gprs):
        pos = 111 + i * 9
        obj[pos:pos + 3] = value.to_bytes(3, "big")
        obj[pos + 3:pos + 9] = words[i].to_bytes(6, "big")
    for i in range(29, 60):
        pos = 375 + (i - 29) * 6
        obj[pos:pos + 6] = words[i].to_bytes(6, "big")
    # Match exact production capture v1 section layout; the rest is synthetic zero DRAM.
    instructions = b"".join(w.to_bytes(6, "big") for w in words + [0] * 100)
    gpr_state = bytes(192 * 3)
    specials = bytes(22 * 3)
    state = bytes(74)
    dram = bytes(1 << 21)
    payload = instructions + gpr_state + specials + state + dram
    cap = b"ES5510C\0" + __import__("struct").pack("<9I", 1, 44, 160, 192, 22, 1 << 20, 1, 74, len(payload)) + payload
    capture = directory / "state.esp"
    capture.write_bytes(cap)
    object_path = directory / "effect.efe"
    object_path.write_bytes(obj)
    log = directory / "host.log"
    rows = ["FINAL |PAIRTEST|"]
    for i, word in enumerate(words):
        if i < 29:
            rows.append(f"ESPHOST both {i:02x} <- {word:012x} / {gprs[i]:06x}")
        else:
            rows.append(f"ESPHOST instr {i:02x} <- {word:012x}")
    log.write_text("\n".join(rows) + "\n")
    return object_path, capture, log


class EffectCaptureComparisonTests(unittest.TestCase):
    def test_recovers_mixed_29_pair_31_instruction_layout(self):
        with tempfile.TemporaryDirectory() as td:
            paths = fixtures(Path(td))
            result = compare_capture.compare(*paths, expected_name="PAIRTEST")
        self.assertEqual(result["naive_six_byte_candidate_words"], 90)
        self.assertEqual(result["capture_active_instructions"], 60)
        self.assertEqual(result["host_instruction_commits_exact_match"], 60)
        self.assertEqual(result["source_offsets"]["paired_records_count"], 29)
        self.assertEqual(result["source_offsets"]["instruction_only_count"], 31)
        self.assertEqual(result["source_offsets"]["unclassified_prefix_bytes_from_FxUcode"], 11)
        self.assertEqual(result["source_offsets"]["unclassified_bytes_before_instruction_only"], 3)
        self.assertEqual(result["source_offsets"]["unclassified_suffix_bytes_to_FxSize"], 80)
        self.assertTrue(result["remaining_host_commits_are_instruction_only"])
        self.assertFalse(result["payload_bytes_disclosed"])

    def test_wrong_host_word_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            obj, cap, log = fixtures(Path(td))
            log.write_text(log.read_text().replace("120000000000", "120000000001", 1))
            with self.assertRaisesRegex(ValueError, "host instruction commits"):
                compare_capture.compare(obj, cap, log)


if __name__ == "__main__":
    unittest.main()
