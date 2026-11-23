import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("parameter_host_diff", ROOT / "tools" / "parameter_host_diff.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class ParameterHostDiffTests(unittest.TestCase):
    def test_redacted_destination_and_timing(self):
        log = """ESPHOST event=1 cycles=10 frame=1 pc=001000 gpr 12 <- 000010
PARAMMARK label=before cycles=20 frame=2
ESPHOST event=2 cycles=24 frame=2 pc=001100 gpr 12 <- 000020
ESPHOST event=3 cycles=25 frame=3 pc=001104 gpr 13 <- ffffff
PARAMMARK label=after cycles=40 frame=5
"""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "host.log"
            path.write_text(log)
            report = tool.analyze(path, "before", "after")
        self.assertEqual(report["markers"]["frame_delta"], 3)
        self.assertEqual([x["destination_register"] for x in report["destinations"]], ["0x12", "0x13"])
        self.assertTrue(all("after_value" not in x for x in report["destinations"]))

    def test_missing_marker_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "host.log"
            path.write_text("PARAMMARK label=before cycles=1 frame=1\n")
            with self.assertRaisesRegex(ValueError, "marker is absent"):
                tool.analyze(path, "before", "after")


if __name__ == "__main__":
    unittest.main()
