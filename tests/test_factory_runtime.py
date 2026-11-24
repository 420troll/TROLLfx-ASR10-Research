import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class FactoryRuntimeBuildTests(unittest.TestCase):
    def test_synthetic_runtime_suite(self):
        result = subprocess.run([str(ROOT / 'tools/audio_validation/test_factory_runtime.sh')],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('synthetic tests: PASS', result.stdout)

if __name__ == '__main__':
    unittest.main()
