import json
import unittest
from pathlib import Path

from tools.force_gui_qa.compare_vst2_audio import REQUIRED

ROOT = Path(__file__).resolve().parents[2]


class Vst2AcceptanceAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads((ROOT / "docs/qa-v4/ASR10_PARAMETER_EVIDENCE_MISMATCH_INVENTORY_V1.json").read_text())
        cls.gates = json.loads((ROOT / "docs/qa-v4/ASR10_VST2_INDEPENDENT_RELEASE_GATES_V1.json").read_text())
        cls.contract = json.loads((ROOT / "docs/qa-v4/ASR10_VST2_ACCEPTANCE_CONTRACT_V1.json").read_text())

    def test_mismatch_counts_and_no_implicit_semantic_links(self):
        c = self.inventory["counts"]
        self.assertEqual(c["manual_rows_unmatched"], 94)
        self.assertEqual(c["os_unlinked_associations"], 500)
        self.assertEqual(c["deferred_manual_rows_additional"], 9)
        self.assertTrue(all(not row["association_claimed"] for row in self.inventory["manual_unmatched_rows"]))
        self.assertTrue(all(not row["association_claimed"] for row in self.inventory["os_unlinked_fields"]))

    def test_top_ten_are_ranked_and_source_visible(self):
        rows = self.inventory["top_ten_future_research_fields"]
        self.assertEqual(len(rows), 10)
        self.assertEqual([r["rank"] for r in rows], list(range(1, 11)))
        self.assertTrue(all("priority_basis" in row and "classification" in row for row in rows))

    def test_release_gates_do_not_promote_hardware_or_equivalence(self):
        by_name = {r["gate"]: r["status"] for r in self.gates["gates"]}
        self.assertEqual(by_name["Native desktop VST2 audio"], "FAIL")
        self.assertEqual(by_name["Physical Akai Force operation"], "NOT TESTED")
        self.assertEqual(by_name["Exact original-hardware audio equivalence"], "NOT TESTED")
        self.assertEqual(by_name["Full-range HALL control"], "BLOCKED")

    def test_vst_contract_requires_actual_entry_and_audio_callbacks(self):
        seq = " ".join(self.contract["vst2_callback_sequence"])
        for name in ("VSTPluginMain", "setParameter", "processReplacing", "effGetChunk", "effSetChunk"):
            self.assertIn(name, seq)
        self.assertIn("non_finite_vst_parameter", [x["case"] for x in self.contract["startup_stress_cases"]])
        self.assertGreaterEqual(len(REQUIRED), 25)


if __name__ == "__main__":
    unittest.main()
