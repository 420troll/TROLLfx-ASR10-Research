import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/force_gui_qa"))
from audit_hall_decay_raw_domain import (  # noqa: E402
    GROUP_ORDER, derived_registers, lcd_value, parameter_group, parse_os_table,
)


class HallDecayRawDomainTests(unittest.TestCase):
    def test_os_table_has_100_values_and_exactly_28_double_buckets(self):
        values = [raw - sum(code <= raw for code in
            (2,6,11,16,20,25,29,34,38,43,47,52,57,61,66,70,75,80,84,89,93,98,102,107,111,116,121,125))
            for raw in range(128)]
        lines = []
        base = 0xFFF825A9
        for offset in range(0, 128, 16):
            chunk = values[offset:offset + 16]
            lines.append(f"{base + offset:08X}: " + " ".join(f"{v:02X}" for v in chunk))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "table.log"
            path.write_text("\n".join(lines))
            table = parse_os_table(path)
        self.assertEqual(len(table), 128)
        self.assertEqual(set(table), set(range(100)))
        counts = {value: table.count(value) for value in set(table)}
        self.assertEqual(sum(count == 2 for count in counts.values()), 28)
        self.assertTrue(all(count in (1, 2) for count in counts.values()))

    def test_independently_recomputed_coefficient_examples(self):
        self.assertEqual(derived_registers(1), {0x03: 0x0C0000, 0x04: 0xF40000, 0x05: 0x7EDFFF})
        self.assertEqual(derived_registers(51), {0x03: 0x330000, 0x04: 0xCD0000, 0x05: 0x6BADFF})
        self.assertEqual(derived_registers(52), {0x03: 0x340000, 0x04: 0xCC0000, 0x05: 0x6ADFFF})
        self.assertEqual(derived_registers(127), {0x03: 0x4C0000, 0x04: 0xB40000, 0x05: 0x52DFFF})

    def test_extracts_final_os_write_group_and_lcd_value(self):
        writes = [{"gpr": f"0x{gpr:02x}", "value24": f"{value:06X}"} for gpr, value in
                  ((0x6E, 0x330000), (0x5B, 0x080033), (0x03, 0x330000),
                   (0x04, 0xCD0000), (0x05, 0x6BADFF))]
        step = {"register_writes": writes}
        self.assertEqual([w["gpr"].lower() for w in writes], GROUP_ORDER)
        self.assertEqual(parameter_group(step), {0x6E:0x330000, 0x5B:0x080033,
                                                  0x03:0x330000, 0x04:0xCD0000,
                                                  0x05:0x6BADFF})
        self.assertEqual(lcd_value("HALL DECAY TIME=40"), 40)


if __name__ == "__main__":
    unittest.main()
