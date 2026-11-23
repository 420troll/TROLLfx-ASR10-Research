import importlib.util, pathlib, tempfile, unittest
import numpy as np
P=pathlib.Path(__file__).resolve().parents[2]/'tools/audio_lab/lab.py'
spec=importlib.util.spec_from_file_location('lab',P); lab=importlib.util.module_from_spec(spec); spec.loader.exec_module(lab)
class LabTests(unittest.TestCase):
 def test_stimuli_deterministic_supported_rates(self):
  for rate in (44100,48000):
   self.assertEqual(lab.stimulus('noise',rate,100,22).tolist(),lab.stimulus('noise',rate,100,22).tolist())
   self.assertEqual(lab.stimulus('stereo_impulse',rate,32).shape,(32,2))
   self.assertTrue(np.all(lab.stimulus('silence',rate,16)==0))
 def test_delay_detected_from_impulse(self):
  x=np.zeros((256,1)); x[0]=1; y=np.zeros_like(x); y[17]=1
  m=lab.analyze(y,48000,x)
  self.assertEqual(m['stereo']['delay']['cross_correlation_lag_frames'],17)
 def test_exponential_decay_t60(self):
  rate=1000; t=np.arange(10000)/rate; x=np.exp(-t/(2/6.907755))[:,None]
  d=lab.analyze(x,rate)['decay']; self.assertTrue(d['reliable']); self.assertAlmostEqual(d['rt60_s'],2,delta=.08)
 def test_frequency_response_flattened_and_correlations(self):
  rate=48000; t=np.arange(8192)/rate; x=np.sin(2*np.pi*1000*t); y=np.column_stack([x,x])
  m=lab.analyze(y,rate,y)
  self.assertAlmostEqual(m['stereo']['channel_correlation'],1,places=6)
  self.assertIn('magnitude_db',m['frequency_response'])
 def test_compare_exact_distinct_and_shift(self):
  x=np.random.default_rng(3).normal(size=(64,1)); y=np.r_[np.zeros((3,1)),x[:-3]]
  c=lab.compare(x,y); self.assertFalse(c['exact_sample_equal']); self.assertEqual(c['cross_correlation_lag_frames'],3)
  self.assertTrue(lab.compare(x,x)['exact_sample_equal'])
 def test_wav_roundtrip_and_fingerprint_source(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'x.wav'; x=lab.stimulus('impulse',44100,128); lab.write_wav(p,x,44100); y,r=lab.read_wav(p)
   self.assertEqual(r,44100); self.assertEqual(y.shape,x.shape)
   self.assertEqual(lab.fingerprint('test',y,r,'emulator_prediction')['source_type'],'emulator_prediction')
if __name__=='__main__': unittest.main()
