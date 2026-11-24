import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[2] / "tools/audio_validation/reference_provenance.py"
spec = importlib.util.spec_from_file_location("reference_provenance", MODULE)
provenance = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(provenance)


class ReferenceProvenanceTests(unittest.TestCase):
    def _receipt(self, root: Path) -> Path:
        source = root / "input.bin"
        output = root / "boot-a" / "session.log"
        source.write_bytes(b"private input")
        output.parent.mkdir()
        output.write_bytes(b"captured log")
        receipt = {
            "schema": provenance.SCHEMA,
            "output_root": str(root),
            "inputs": {"disk": provenance.describe_file(source)},
            "output_artifacts": {"boot-a/session.log": {
                "size_bytes": output.stat().st_size,
                "sha256": provenance.sha256_file(output)}},
            "boots": [{"pid": 101}, {"pid": 202}],
            "validation": {"two_boots_identical": True},
        }
        path = root / "provenance.json"
        provenance.write_json(path, receipt)
        return path

    def test_verifies_inputs_outputs_and_independent_processes(self):
        with tempfile.TemporaryDirectory() as td:
            result = provenance.verify_provenance(self._receipt(Path(td)), check_source=False)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["boot_count"], 2)

    def test_detects_mutated_output_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipt = self._receipt(root)
            (root / "boot-a" / "session.log").write_bytes(b"changed")
            result = provenance.verify_provenance(receipt, check_source=False)
        self.assertFalse(result["valid"])
        self.assertIn("output artifact hash mismatch: boot-a/session.log", result["errors"])

    def test_rejects_reused_process_id(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipt = self._receipt(root)
            data = json.loads(receipt.read_text())
            data["boots"][1]["pid"] = data["boots"][0]["pid"]
            receipt.write_text(json.dumps(data))
            result = provenance.verify_provenance(receipt, check_source=False)
        self.assertFalse(result["valid"])
        self.assertIn("reference capture does not record two distinct process IDs", result["errors"])


if __name__ == "__main__":
    unittest.main()
