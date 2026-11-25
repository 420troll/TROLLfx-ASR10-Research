import sys
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/parameter_controls"))
from build_full_factory_parameter_registry import build_registry
from run_full_parameter_range_sweep import documented_domain, parse_sweep_log


class FullParameterRegistryTests(unittest.TestCase):
    def test_keeps_all_manual_entries_and_marks_partial_points(self):
        registry = build_registry()
        self.assertEqual(registry["coverage"]["factory_effects"], 50)
        self.assertEqual(registry["coverage"]["parameter_entries"], 594)
        hall = registry["effects"][0]
        decay = next(p for p in hall["parameters"] if p["display_name"] == "DECAY TIME")
        self.assertEqual(decay["documented_numeric_domain"], {"minimum": 0, "maximum": 99, "step": 1})
        self.assertEqual(decay["ui_range_status"], "OS_RANGE_VERIFIED")
        self.assertEqual(decay["observed_os_numeric_domain"], {"minimum": 0, "maximum": 99, "step": 1})
        self.assertEqual(decay["dsp_mapping_status"], "EXACT_POINTS_ONLY")
        self.assertEqual([p["value"] for p in decay["supported_values"]], [40, 41])
        self.assertEqual(decay["normalized_ui_mapping"]["scope"],
                         "UI-only coordinate mapping; makes no claim about DSP coefficient scaling")

    def test_public_registry_has_no_private_absolute_paths(self):
        registry = build_registry()
        encoded = json.dumps(registry)
        self.assertNotIn("/home/gamer/", encoded)
        self.assertNotIn("run-checkpoint.esp", encoded)

    def test_sweep_parser_preserves_lcd_and_ordered_gpr_writes(self):
        text = "\n".join([
            'PANEL_RANGE_STEP_BEGIN id=sweep segment=to_max direction=up step=1 display="DECAY TIME=40" time=1 cycles=100 frame=2',
            'ESPHOST event=1 cycles=120 frame=2 pc=03 gpr 03 <- 350000',
            'ESPHOST event=2 cycles=130 frame=2 pc=04 gpr 04 <- cb0000',
            'PANEL_RANGE_STEP_DONE id=sweep segment=to_max direction=up step=1 before="DECAY TIME=40" after="DECAY TIME=41" cycles=150 frame=3',
            'PANEL_RANGE_MAX id=sweep display="DECAY TIME=99" up_steps=59 cycles=500 frame=8',
            'PANEL_RANGE_MIN id=sweep display="DECAY TIME=0" down_steps=99 cycles=900 frame=15',
            'PANEL_RANGE_RESTORE id=sweep display="DECAY TIME=40" baseline="DECAY TIME=40" exact=1 up_steps=59 down_steps=99 cycles=1000 frame=17'])
        result = parse_sweep_log(text)
        self.assertTrue(result["sweep_complete"])
        self.assertEqual(result["steps"][0]["from_display"], "DECAY TIME=40")
        self.assertEqual(result["steps"][0]["to_display"], "DECAY TIME=41")
        self.assertEqual([w["gpr"] for w in result["steps"][0]["register_writes"]], ["0x03", "0x04"])

    def test_origin_marker_closes_legacy_phase_boundary_step(self):
        text = "\n".join([
            'PANEL_RANGE_STEP_BEGIN id=sweep segment=to_origin direction=down step=1 display="BUS1 FEEDBACK=20" time=1 cycles=100 frame=2',
            'PANEL_RANGE_ORIGIN_RESTORED id=sweep display="BUS1 FEEDBACK=19"',
            'PANEL_RANGE_STEP_DONE id=sweep segment=to_min direction=down step=1 before="BUS1 FEEDBACK=20" after="BUS1 FEEDBACK=19" cycles=200 frame=3',
            'PANEL_RANGE_MIN id=sweep display="BUS1 FEEDBACK=0" down_steps=20 cycles=300 frame=4',
            'PANEL_RANGE_MAX id=sweep display="BUS1 FEEDBACK=99" up_steps=80 cycles=400 frame=5',
            'PANEL_RANGE_RESTORE id=sweep display="BUS1 FEEDBACK=19" baseline="BUS1 FEEDBACK=19" exact=1 up_steps=80 down_steps=20 cycles=500 frame=6'])
        result = parse_sweep_log(text)
        origin = next(x for x in result["steps"] if x.get("closed_by_origin_restored_event"))
        self.assertTrue(result["sweep_complete"])
        self.assertEqual(origin["to_display"], 'BUS1 FEEDBACK=19')
        self.assertEqual(origin["end_cycles"], 200)

    def test_editor_alias_can_receive_range_evidence(self):
        registry = build_registry()
        dual = registry["effects"][3]
        feedback = next(p for p in dual["parameters"] if p["id"] == "bus1_and_2_feedback_1")
        # The live OS uses BUS1 FEEDBACK while the manual-derived catalog
        # describes the shared field as BUS1 (and 2) FEEDBACK.
        self.assertEqual(feedback["ui_range_status"], "OS_RANGE_VERIFIED")
        self.assertEqual(feedback["observed_os_numeric_domain"],
                         {"minimum": 0, "maximum": 99, "step": 1})

    def test_manual_range_is_separate_from_live_range_evidence(self):
        label, domain = documented_domain(1, "DECAY TIME")
        self.assertEqual(label, "0 to 99")
        self.assertEqual(domain, {"minimum": 0, "maximum": 99, "step": 1})
        dual_label, dual_domain = documented_domain(4, "BUS1 FEEDBACK")
        self.assertEqual(dual_label, "0 to 99")
        self.assertEqual(dual_domain, {"minimum": 0, "maximum": 99, "step": 1})


if __name__ == "__main__":
    unittest.main()
