import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "parameter_controls"))
from run_full_parameter_range_sweep import build_command


class ParameterStateCaptureCommandTests(unittest.TestCase):
    def test_state_only_loads_and_navigates_without_scheduling_a_range_sweep(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cli, roms, disk = (base / "cli", base / "roms", base / "disk")
            for item in (cli, roms, disk):
                item.touch()
            args = SimpleNamespace(cli=cli, roms=roms, disk=disk, field_timeout=2.0,
                variation=1, edit_button=10, revert_button=11, max_sweep_seconds=300.0,
                settle_seconds=.75, monitor_stdio=True, state_only=True, slot=1)
            selector = {"select_raw": 8}
            location = {"page": {"ordinal": 4}, "marker_start": -1,
                        "needle": "DECAY TIME"}
            command = build_command(args, selector, location, "private_state_probe")
            self.assertIn("--panel-probe-field", command)
            self.assertNotIn("--panel-probe-range", command)
            self.assertIn("--monitor-stdio", command)
            self.assertEqual(command[command.index("--seconds") + 1], "20.50")


if __name__ == "__main__":
    unittest.main()
