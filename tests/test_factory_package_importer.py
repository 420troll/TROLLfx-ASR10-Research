import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "factory_collection_importer", ROOT / "tools/audio_validation/import_factory_effect_collection.py")
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


class FactoryPackageImporterTests(unittest.TestCase):
    def test_only_known_identity_and_true_run_boundary_can_be_eligible(self):
        hall = importer.KNOWN[1]
        self.assertEqual(importer.package_eligibility(1, hall["name"], hall["words"], hall["program"], 10, 10),
                         (True, None))
        self.assertFalse(importer.package_eligibility(1, hall["name"], hall["words"], hall["program"], 10, 11)[0])

    def test_collection_slots_02_and_03_are_quarantined(self):
        self.assertFalse(importer.package_eligibility(2, "44KHZ REVERB", 89, "0" * 64, 10, 10)[0])
        self.assertFalse(importer.package_eligibility(3, "ROOM REVERB", 60, "1" * 64, 10, 10)[0])

    def test_known_hall_identity_rejects_wrong_program_geometry(self):
        hall = importer.KNOWN[1]
        ok, reason = importer.package_eligibility(1, hall["name"], 60, hall["program"], 10, 10)
        self.assertFalse(ok)
        self.assertEqual(reason, "independent replay identity conflict")


if __name__ == "__main__":
    unittest.main()
