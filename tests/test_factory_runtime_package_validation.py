import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
spec = importlib.util.spec_from_file_location(
    "factory_runtime_package_validator", ROOT / "tools/audio_validation/validate_factory_runtime_package.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class CollectionPackageAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package = self.root / "package.json"
        self.checkpoint = self.root / "run-checkpoint.esp"
        self.events = self.root / "firmware-schedule.csv"
        self.checkpoint.write_bytes(b"validated run checkpoint")
        self.events.write_text("validated schedule")
        self.doc = {
            "schema": "asr10-private-rom-effect-package-v1",
            "effect_id": 1,
            "display_name": "HALL REVERB",
            "active_program_words": 89,
            "active_program_sha256": "a" * 64,
            "sample_rate_hz": 29761.895,
        }
        self.package.write_text(json.dumps(self.doc))
        for boot in ("boot-a", "boot-b"):
            folder = self.root / "references" / boot
            (folder / "snapshots").mkdir(parents=True)
            (folder / "snapshots/run-frame-855973.esp").write_bytes(self.checkpoint.read_bytes())
            (folder / "session.log").write_text("verified test evidence\n")
        self.descriptor = {
            "slot": 1, "factory_name": "HALL REVERB", "active_program_words": 89,
            "program_sha256": "a" * 64,
            "run_checkpoint_path": str(self.checkpoint),
            "firmware_event_schedule_path": str(self.events),
            "firmware_event_schedule": [{"relative_dsp_frame": 12, "gpr": 3, "value24": 0}],
        }
        self.audit_result = {
            "capture_state_valid": True, "registry_eligible": True,
            "run_start_frame": 855973, "future_schedule_count": 1,
            "descriptor": self.descriptor,
        }

    def tearDown(self):
        self.temp.cleanup()

    def validate(self):
        with patch("import_factory_effect_collection.validate_one", return_value=self.audit_result):
            return validator.validate_collection_package(
                "hall", self.package, self.checkpoint, self.root / "references", self.events)

    def test_accepts_importer_validated_package_with_two_exact_boots(self):
        result = self.validate()
        self.assertTrue(result["valid"])
        self.assertTrue(result["two_boot_checkpoint_match"])
        self.assertEqual(result["firmware_event_count"], 1)
        self.assertEqual(result["terminal_schedule_frame"], 12)

    def test_rejects_checkpoint_not_named_by_importer_descriptor(self):
        other = self.root / "other.esp"
        other.write_bytes(b"different")
        with patch("import_factory_effect_collection.validate_one", return_value=self.audit_result):
            with self.assertRaisesRegex(ValueError, "not the checkpoint named"):
                validator.validate_collection_package(
                    "hall", self.package, other, self.root / "references", self.events)

    def test_rejects_reference_boot_mismatch(self):
        (self.root / "references/boot-b/snapshots/run-frame-855973.esp").write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "differs from a fresh-boot"):
            self.validate()


if __name__ == "__main__":
    unittest.main()
