import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("display_probe", ROOT / "tools/parameter_controls/run_display_driven_probe.py")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class DisplayProbeTests(unittest.TestCase):
    def test_panel_route_waits_until_selector_sweep_ends(self):
        class Args:
            cli = Path("cli")
            roms = Path("roms")
            disk = Path("disk")
            seconds = 55
            output = Path("private")
            revert_button = 33
            mode = "point"
        entry = {"id": 1, "select_raw": 79}
        command = PROBE.build_command(Args(), entry, "BUS1", "bus1")
        edit = command[command.index("--panel-tap-on-display", command.index("--panel-tap-on-display") + 1) + 1]
        # Selector reaches raw 79 at 26.65 s, then the controller waits 500 ms.
        self.assertEqual(edit, "27.15,45,5,FX=ROM-01,edit")
        self.assertIn("--seconds", command)
        self.assertIn("--log-rom-select", command)

    def test_range_scan_records_endpoint_steps_and_restoration(self):
        class Args:
            cli = Path("cli")
            roms = Path("roms")
            disk = Path("disk")
            seconds = 55
            output = Path("private")
            revert_button = 11
            mode = "range"
        command = PROBE.build_command(Args(), {"id": 1, "select_raw": 79}, "DECAY TIME", "decay")
        self.assertIn("--panel-probe-range", command)
        self.assertIn("27.15,180,DECAY TIME,candidate_range", command)
        self.assertIn("--seconds", command)

    def test_parser_uses_full_display_and_gpr_not_packed_host_events(self):
        log = '''ESP_ROM_SELECT id=01 time=10.0 cycles=100 frame=20 dsp_rate_hz=29761.895 otto_clock_hz=15238090 active_voices=31 host_output_rate_hz=44100 display=FX=ROM-01 HALL
PANEL_TAP_BEGIN id=edit button=5 before="FX=ROM-01 HALL       " time=10.1 cycles=101 frame=21
PANEL_PROBE_FOUND id=probe display="REVERB MIX BUS1=28    " time=11 cycles=110 frame=22
PANEL_PROBE_IDLE_BEGIN id=probe display="REVERB MIX BUS1=28    " time=11 cycles=110 frame=22
ESPHOST event=1 cycles=111 frame=23 pc=fff97792 gpr 7c <- 3d0000
ESPHOST event=2 cycles=112 frame=23 pc=fff97792 both 7c <- ffffff / 000000
PANEL_PROBE_IDLE_END id=probe display="REVERB MIX BUS1=28    " time=11.5 cycles=120 frame=24
PANEL_PROBE_UP_BEGIN id=probe iteration=1 display="REVERB MIX BUS1=28    " time=11.6 cycles=130 frame=25
PANEL_PROBE_DOWN_BEGIN id=probe iteration=1 display="REVERB MIX BUS1=29    " time=11.8 cycles=140 frame=26
PANEL_PROBE_UP_DISPLAY id=probe iteration=1 before="REVERB MIX BUS1=28    " after="REVERB MIX BUS1=29    " time=11.7 cycles=135 frame=25
PANEL_PROBE_DOWN_DISPLAY id=probe iteration=1 before="REVERB MIX BUS1=29    " after="REVERB MIX BUS1=28    " time=11.9 cycles=145 frame=27
PANEL_PROBE_RESTORE id=probe iteration=1 display="REVERB MIX BUS1=28    " baseline="REVERB MIX BUS1=28    " exact=1 time=12 cycles=150 frame=28
PANEL_RANGE_FOUND id=range display="DECAY TIME=40         " time=13 cycles=160 frame=29
PANEL_RANGE_STEP_BEGIN id=range segment=to_max direction=up step=1 display="DECAY TIME=40         " time=13.1 cycles=161 frame=30
PANEL_RANGE_STEP_DONE id=range segment=to_max direction=up step=1 before="DECAY TIME=40         " after="DECAY TIME=41         " cycles=162 frame=31
PANEL_RANGE_STEP_BEGIN id=range segment=to_origin direction=down step=1 display="DECAY TIME=99         " time=14.1 cycles=171 frame=32
PANEL_RANGE_STEP_DONE id=range segment=to_origin direction=down step=1 before="DECAY TIME=99         " after="DECAY TIME=98         " cycles=172 frame=33
PANEL_RANGE_MAX id=range display="DECAY TIME=99         " up_steps=59 time=14 cycles=170 frame=30
PANEL_RANGE_MIN id=range display="DECAY TIME=0          " down_steps=40 time=15 cycles=180 frame=31
PANEL_RANGE_RESTORE id=range display="DECAY TIME=40         " baseline="DECAY TIME=40         " exact=1 up_steps=59 down_steps=40 cycles=190 frame=32
'''
        report = PROBE.summarize_log(log, 1)
        self.assertTrue(report["selection_verified"])
        self.assertEqual(report["selected_effect_slots_observed"][0]["source"], "ESP_ROM_SELECT")
        probe = report["probes"][0]
        self.assertEqual(probe["candidate_display_before"], "REVERB MIX BUS1=28    ")
        self.assertTrue(probe["trials"][0]["restored_exactly"])
        self.assertEqual(probe["baseline_window"]["host_write_count"], 1)
        self.assertEqual(report["range_scans"][0]["minimum_steps_from_baseline"], 40)
        self.assertEqual(report["range_scans"][0]["maximum_steps_from_baseline"], 59)
        self.assertTrue(report["range_scans"][0]["restored_exactly"])
        range_steps = [e for e in report["range_scans"][0]["events"] if e["event"] == "PANEL_RANGE_STEP_DONE"]
        self.assertEqual([(e["segment"], e["direction"], e["step"]) for e in range_steps],
                         [("to_max", "up", "1"), ("to_origin", "down", "1")])


if __name__ == "__main__":
    unittest.main()
