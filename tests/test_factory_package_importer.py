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
        self.assertEqual(importer.package_eligibility(1, hall["name"], hall["words"], hall["program"], 10, 10, True),
                         (True, None))
        self.assertFalse(importer.package_eligibility(1, hall["name"], hall["words"], hall["program"], 10, 11, True)[0])

    def test_selector_correlation_is_required_to_accept_slots_02_and_03(self):
        rom02=importer.KNOWN[2]
        self.assertFalse(importer.package_eligibility(2, rom02["name"], rom02["words"], rom02["program"], 10, 10)[0])
        self.assertEqual(importer.package_eligibility(2, rom02["name"], rom02["words"], rom02["program"], 10, 10, True), (True,None))
        self.assertFalse(importer.package_eligibility(3, "ROOM REVERB", 89, "1" * 64, 10, 10)[0])

    def test_known_hall_identity_rejects_wrong_program_geometry(self):
        hall = importer.KNOWN[1]
        ok, reason = importer.package_eligibility(1, hall["name"], 60, hall["program"], 10, 10)
        self.assertFalse(ok)
        self.assertEqual(reason, "independent replay identity conflict")

    def test_only_os_observed_hall_factory_default_gets_variation_identity(self):
        hall = importer.KNOWN[1]
        self.assertEqual(importer.verified_factory_variation(1, hall["name"], hall["words"]), 1)
        self.assertEqual(importer.verified_factory_variation(1, hall["name"], 60), 0)
        self.assertEqual(importer.verified_factory_variation(3, "ROOM REVERB", 60), 0)


if __name__ == "__main__":
    unittest.main()
