import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / 'tools/audio_validation/run.py'
spec = importlib.util.spec_from_file_location('audio_validation', SCRIPT)
av = importlib.util.module_from_spec(spec); spec.loader.exec_module(av)

class AudioValidationTests(unittest.TestCase):
    def test_stimuli_are_deterministic_and_cover_required_cases(self):
        a = av.stimuli(44100, 512); b = av.stimuli(44100, 512)
        self.assertEqual(set(a), {'impulse','sine','sweep','noise','stereo_phase'})
        self.assertEqual(a, b)
        self.assertTrue(any(l != r for l, r in a['stereo_phase']))
        self.assertEqual(a['impulse'][64], (24000, 0))

    def test_metrics_detect_deviation_and_alignment(self):
        ref = [[0,0],[1,-1],[2,-2],[0,0]]
        got = [[0,0],[0,0],[1,-1],[2,-2]]
        m = av.metrics(ref, got)
        self.assertEqual(m['best_alignment_lag_frames'], 1)
        self.assertFalse(m['bit_exact'])
        self.assertGreater(m['max_abs_deviation'], 0)

    def test_end_to_end_repeatability_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            out=pathlib.Path(td)
            subprocess.run(['python3',str(SCRIPT),'--out',td,'--frames','13000'],check=True,stdout=subprocess.DEVNULL)
            first=(out/'summary.json').read_bytes()
            subprocess.run(['python3',str(SCRIPT),'--out',td,'--frames','13000'],check=True,stdout=subprocess.DEVNULL)
            self.assertEqual(first,(out/'summary.json').read_bytes())
            import json
            report=json.loads(first)
            self.assertEqual(set(report['summaries']), {'impulse','sine','sweep','noise','stereo_phase'})
            self.assertIn('best_alignment_lag_frames',report['summaries']['impulse']['pass'])
            delay=report['summaries']['impulse']['delay']
            self.assertTrue(delay['bit_exact'])
            self.assertEqual(delay['first_divergent_frame'],None)
            for engine in ('original','mame'):
                taps=delay['impulse_response_taps'][engine]
                self.assertEqual(taps[0]['offset_from_input_frames'],0)
                self.assertEqual(taps[1]['offset_from_input_frames'],11025)
                self.assertEqual(taps[1]['left'],13199)

if __name__ == '__main__': unittest.main()
