import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("os_probe", ROOT / "tools/parameter_controls/run_os_parameter_probe.py")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class OsProbeTests(unittest.TestCase):
    def test_recipe_command_and_reversible_windows(self):
        recipe = {"id": "synthetic", "seconds": 4, "actions": [
            {"seconds": 1, "type": "mark", "label": "before"},
            {"seconds": 1.1, "type": "button", "code": 10, "down": 1},
            {"seconds": 1.2, "type": "button", "code": 10, "down": 0},
            {"seconds": 2, "type": "mark", "label": "after"},
        ]}
        cmd, labels = PROBE.make_command(recipe, Path("cli"), Path("roms"), Path("disk"), Path("out.wav"))
        self.assertEqual(labels, {"before", "after"})
        self.assertIn("1.100000:10:1", cmd)
        self.assertIn("1.000000:before", cmd)
        with self.assertRaises(ValueError):
            PROBE.validate_recipe({"actions": [{"seconds": 2, "type": "mark", "label": "a"},
                                                 {"seconds": 1, "type": "mark", "label": "b"}]})

    def test_report_redaction_input_is_windows(self):
        log = """PARAMMARK label=a cycles=100 frame=10
ESPHOST event=1 cycles=110 frame=11 pc=fff97792 gpr 7c <- 3d0000
PARAMMARK label=b cycles=200 frame=20
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.log"
            path.write_text(log)
            report = PROBE.build_report(path, [{"before": "a", "after": "b", "action": "up"}])
            self.assertEqual(report["windows"][0]["destinations"][0]["destination_register"], "0x7c")
            self.assertEqual(report["windows"][0]["destinations"][0]["after_value"], "0x3d0000")


if __name__ == "__main__":
    unittest.main()
