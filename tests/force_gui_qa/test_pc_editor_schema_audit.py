import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/force_gui_qa/audit_pc_editor_schema.py"
SPEC = importlib.util.spec_from_file_location("pc_editor_schema_audit", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PcEditorSchemaAuditTests(unittest.TestCase):
    def test_published_editor_candidate_is_audited_against_manual_domains(self):
        candidate = Path("/home/gamer/worktrees/asr10-pc-editor-audit-08cc600/tools/force_simulator/data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json")
        if not candidate.exists():
            candidate = Path("/home/gamer/worktrees/asr10-pc-editor-audit/tools/force_simulator/data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json")
        if not candidate.exists():
            self.skipTest("detached read-only candidate worktree is not present")
        result = MODULE.audit(candidate)
        self.assertEqual(result["effect_count"], 50)
        self.assertEqual(result["catalog_descriptor_count"], 594)
        self.assertEqual(result["unique_effect_parameter_identities"], 594)
        # These published schema errors must remain visible until the editor is corrected.
        self.assertEqual(len(result["findings"]), 4)
        self.assertTrue(any("ROM-15 DECAY TIME" in item for item in result["findings"]))
        self.assertTrue(any("ROM-16 DECAY TIME" in item for item in result["findings"]))
        self.assertTrue(any("ROM-18 DECAY TIME" in item for item in result["findings"]))
        self.assertTrue(any("ROM-18 PREDELAY TIME" in item for item in result["findings"]))
        # The effective editor registry repairs these domains by slot even though
        # the serialized source schema still has generic small-room/plate text.
        simulator = candidate.parents[1]
        sys.path.insert(0, str(simulator))
        try:
            spec = importlib.util.spec_from_file_location("candidate_parameter_registry",
                simulator / "parameter_registry.py")
            registry = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(registry)
            effects = registry.load_registry()
            expected = {14: [0.2, 100.0], 15: [0.2, 150.0], 16: [0.7, 250.0],
                        17: [0.2, 100.0], 18: [0.4, 140.0]}
            for slot, bounds in expected.items():
                effect = effects[slot - 1]
                control = next(c for c in effect["controls"]
                               if c["name"] == "DECAY TIME" and c.get("editor_visible", True))
                self.assertEqual(control["range"], bounds)
            plate = effects[17]
            predelay = next(c for c in plate["controls"] if c["name"] == "PREDELAY TIME")
            self.assertEqual(predelay["range"], [0, 430])
        finally:
            sys.path.remove(str(simulator))

    def test_hall_trace_audit_reproduces_private_full_range_result(self):
        module_path = ROOT / "tools/force_gui_qa/audit_hall_decay_trace.py"
        spec = importlib.util.spec_from_file_location("hall_trace_audit", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        private = Path.home() / "research/private-results/asr10-full-factory-parameter-recovery/hall-decay-lcd-caller-final/slot-01-var1-decay-time-range.json"
        if not private.exists():
            self.skipTest("private OS trace is not installed on this machine")
        result = module.transition_matrix(private)
        self.assertEqual(result["transition_count"], 198)
        self.assertEqual(result["raw_code_count"], 128)
        self.assertEqual(result["display_value_count"], 100)
        self.assertEqual(result["duplicate_display_bucket_count"], 28)
        self.assertEqual(result["register_formula_mismatch_count"], 0)
        self.assertEqual(result["os_step_transition_mismatch_count"], 0)
        self.assertEqual(result["raw_to_display"][0], {"raw_code": 0, "display_value": 0})
        self.assertEqual(result["raw_to_display"][-1], {"raw_code": 127, "display_value": 99})
        newest = private.parents[1] / "v3-hall-decay-routine-trace/slot-01-var1-decay-time-range.json"
        second = module.transition_matrix(newest)
        self.assertEqual(second["raw_to_display"], result["raw_to_display"])
        self.assertEqual(second["duplicate_buckets"], result["duplicate_buckets"])
        self.assertEqual(second["transitions"], result["transitions"])


if __name__ == "__main__":
    unittest.main()
