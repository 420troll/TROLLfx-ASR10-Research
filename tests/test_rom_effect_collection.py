import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "rom_collection", ROOT / "tools" / "package_rom_effect_collection.py")
collection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collection)


class RomEffectCollectionTests(unittest.TestCase):
    def test_sweep_parser_retains_state_clock_and_pipeline_coordinates(self):
        text = (
            "ESPPHASE kind=host_halt_pipeline_reset frame=10 cycles=100 pc=fff000\n"
            "ESP_ROM_STATE id=01 time=2.000 frame=12 dsp_rate_hz=29761.895 cycles=120 host_output_rate_hz=44100\n"
            "ESPHOST event=1 cycles=110 frame=11 pc=fff000 gpr 01 <- 000001 t=1.9\n")
        path = ROOT / "tests" / ".rom-effect-parser-fixture.log"
        try:
            path.write_text(text)
            states, phases, host = collection.parse_sweep(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(states[0]["id"], 1)
        self.assertAlmostEqual(states[0]["rate"], 29761.895)
        self.assertEqual(phases[0]["kind"], "host_halt_pipeline_reset")
        self.assertEqual(host[0][0], 110)

    def test_run_boundary_requires_ordered_reset_clear_upload_and_first_frame(self):
        kinds = ["pa4_halt_assert", "halt", "host_halt_pipeline_reset", "host_dram_clear",
                 "instruction_upload_start", "pa4_run_release", "program_upload_summary",
                 "run_start", "first_instruction"]
        phases = [{"kind": k, "cycles": i + 1, "frame": i} for i, k in enumerate(kinds)]
        start, evidence = collection.last_complete_run(phases, 20)
        self.assertEqual(start, 1)
        self.assertTrue(evidence["ordered"])
        with self.assertRaisesRegex(ValueError, "no complete"):
            collection.last_complete_run(phases[:3], 20)

    def test_private_output_cannot_be_inside_checkout(self):
        with self.assertRaisesRegex(ValueError, "outside the Git checkout"):
            collection.external(ROOT / "private-results")


if __name__ == "__main__":
    unittest.main()
