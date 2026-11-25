import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/force_gui_qa/audit_pc_editor_schema.py"
SPEC = importlib.util.spec_from_file_location("pc_editor_schema_audit", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PcEditorSchemaAuditTests(unittest.TestCase):
    def test_published_editor_candidate_is_audited_against_manual_domains(self):
        candidate = Path("/home/gamer/worktrees/asr10-pc-editor-audit/tools/force_simulator/data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json")
        if not candidate.exists():
            self.skipTest("detached read-only candidate worktree is not present")
        result = MODULE.audit(candidate)
        self.assertEqual(result["effect_count"], 50)
        self.assertEqual(result["catalog_descriptor_count"], 594)
        self.assertEqual(result["unique_effect_parameter_identities"], 594)
        # These published schema errors must remain visible until the editor is corrected.
        self.assertEqual(len(result["findings"]), 3)
        self.assertTrue(any("ROM-15 DECAY TIME" in item for item in result["findings"]))
        self.assertTrue(any("ROM-16 DECAY TIME" in item for item in result["findings"]))
        self.assertTrue(any("ROM-18 DECAY TIME" in item for item in result["findings"]))

    def test_hall_trace_audit_reproduces_private_full_range_result(self):
        module_path = ROOT / "tools/force_gui_qa/audit_hall_decay_trace.py"
        spec = importlib.util.spec_from_file_location("hall_trace_audit", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        private = Path.home() / "research/private-results/asr10-full-factory-parameter-recovery/hall-decay-lcd-caller-final/slot-01-var1-decay-time-range.json"
        if not private.exists():
            self.skipTest("private OS trace is not installed on this machine")
        result = module.summarize(private)
        self.assertEqual(result["step_count"], 200)
        self.assertEqual(result["shared_interior_display_values"], 98)
        self.assertEqual(result["gpr6e_direction_difference_count"], 28)
        self.assertIn(40, result["gpr6e_direction_difference_values"])
        self.assertEqual(result["helper_03_04_05_match_count"], 102)
        self.assertEqual(result["helper_03_04_05_total_directional_cases"], 196)


if __name__ == "__main__":
    unittest.main()
