import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("compare_capture", ROOT / "tools" / "compare_asr10_effect_capture.py")
compare_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_capture)


def fixtures(directory: Path, paired_count=29, instruction_count=None, gap_bytes=3, suffix_bytes=80):
    if instruction_count is None:
        instruction_count = 60 - paired_count
    if paired_count + instruction_count != 60:
        raise ValueError("synthetic captures use 60 active words")
    fx_ucode = 100
    paired_start_gpr = fx_ucode + 11
    paired_first_instruction = paired_start_gpr + 3
    instruction_only_start = (
        paired_first_instruction + 9 * paired_count - 3 + gap_bytes
        if paired_count else fx_ucode + 11
    )
    final_instruction = (
        instruction_only_start + 6 * (instruction_count - 1)
        if instruction_count else paired_first_instruction + 9 * (paired_count - 1)
    )
    fx_size = final_instruction + 6 + suffix_bytes
    obj = bytearray(fx_size + 8)
    fx_name = b"PAIRTEST"
    for i, c in enumerate(fx_name):
        obj[10 + i * 2] = c
    obj[34:38] = fx_size.to_bytes(4, "big")
    obj[38:40] = fx_ucode.to_bytes(2, "big")
    words = [0x120000000000 + i * 0x10000 for i in range(59)] + [0x00000000F000]
    # Repeated words exercise source-offset resolution by host GPR and stride.
    words[40] = words[9]
    words[53] = words[19]
    gprs = [0x300000 + i for i in range(paired_count)]
    for i, value in enumerate(gprs):
        pos = paired_start_gpr + i * 9
        obj[pos:pos + 3] = value.to_bytes(3, "big")
        obj[pos + 3:pos + 9] = words[i].to_bytes(6, "big")
    for i in range(paired_count, 60):
        pos = instruction_only_start + (i - paired_count) * 6
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
        if i < paired_count:
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

    def test_recovers_56_pair_4_instruction_layout_with_repeated_words(self):
        with tempfile.TemporaryDirectory() as td:
            paths = fixtures(Path(td), paired_count=56, instruction_count=4)
            result = compare_capture.compare(*paths, expected_name="PAIRTEST")
        self.assertEqual(result["source_offsets"]["paired_records_count"], 56)
        self.assertEqual(result["source_offsets"]["instruction_only_count"], 4)
        self.assertEqual(result["source_offsets"]["unclassified_bytes_before_instruction_only"], 3)
        self.assertTrue(result["source_instruction_locations_resolved_by_layout"])

    def test_recovers_26_pair_34_instruction_layout_with_repeated_words(self):
        with tempfile.TemporaryDirectory() as td:
            paths = fixtures(Path(td), paired_count=26, instruction_count=34)
            result = compare_capture.compare(*paths, expected_name="PAIRTEST")
        self.assertEqual(result["source_offsets"]["paired_records_count"], 26)
        self.assertEqual(result["source_offsets"]["instruction_only_count"], 34)
        self.assertFalse(result["source_instruction_words_unique"])
        self.assertTrue(result["source_instruction_locations_resolved_by_layout"])

    def test_recovers_instruction_only_layout(self):
        with tempfile.TemporaryDirectory() as td:
            paths = fixtures(Path(td), paired_count=0, instruction_count=60, gap_bytes=0)
            result = compare_capture.compare(*paths, expected_name="PAIRTEST")
        self.assertIsNone(result["source_offsets"]["paired_records_start_gpr"])
        self.assertEqual(result["source_offsets"]["paired_records_count"], 0)
        self.assertEqual(result["source_offsets"]["instruction_only_count"], 60)
        self.assertEqual(result["source_offsets"]["instruction_only_stride_bytes"], 6)

    def test_ambiguous_duplicate_program_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            object_path, capture, log = fixtures(
                Path(td), paired_count=0, instruction_count=60, gap_bytes=0
            )
            source = bytearray(object_path.read_bytes())
            fx_size = int.from_bytes(source[34:38], "big")
            first_instruction = int.from_bytes(source[38:40], "big") + 11
            duplicate = source[first_instruction:first_instruction + 60 * 6]
            source[fx_size:fx_size + len(duplicate)] = duplicate
            source[34:38] = (fx_size + len(duplicate)).to_bytes(4, "big")
            object_path.write_bytes(source)
            with self.assertRaisesRegex(ValueError, "source offsets remain ambiguous"):
                compare_capture.compare(object_path, capture, log, expected_name="PAIRTEST")

    def test_wrong_host_word_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            obj, cap, log = fixtures(Path(td))
            log.write_text(log.read_text().replace("120000000000", "120000000001", 1))
            with self.assertRaisesRegex(ValueError, "host instruction commits"):
                compare_capture.compare(obj, cap, log)


if __name__ == "__main__":
    unittest.main()
