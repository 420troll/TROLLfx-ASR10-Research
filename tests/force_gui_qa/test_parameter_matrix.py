import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
M=json.loads((ROOT/'docs/qa-v4/factory-parameter-validation-matrix.json').read_text())
class MatrixTests(unittest.TestCase):
 def test_full_inventory_coverage(self):
  self.assertEqual(len(M['effects']),50)
  self.assertEqual(sum(len(e['parameters']) for e in M['effects']),594)
  self.assertEqual(sorted(e['slot'] for e in M['effects']),list(range(1,51)))
 def test_classification_is_conservative(self):
  for e in M['effects']:
   for p in e['parameters']:
    if p['classification']=='VERIFIED':
     self.assertTrue(p['full_documented_range_implemented'])
     self.assertEqual(p['audio_behavior_validation'],'OBSERVED_CHANGE')
     self.assertTrue(p['register_mapping'].get('observed_setting_points'))
  self.assertEqual(M['summary']['full_range_implemented'],0)
  self.assertEqual(M['summary']['classification'].get('VERIFIED',0),0)
 def test_register_evidence_only_contains_explicit_points(self):
  for e in M['effects']:
   for p in e['parameters']:
    reg=p['register_mapping']
    if reg:
     self.assertGreaterEqual(len(reg['observed_setting_points']),1)
     self.assertTrue(reg['register_addresses'])
     for pt in reg['observed_setting_points']:
      self.assertTrue(pt.get('ordered_writes'))
      for w in pt['ordered_writes']:
       self.assertIn('gpr',w);self.assertTrue('raw24' in w or 'value24' in w)
 def test_current_v41_vst_map_is_nineteen_stable_controls(self):
  self.assertEqual(M['summary']['current_vst_controls'],19)
  routes=[]
  for e in M['effects']:
   for p in e['parameters']:
    routes+=p['current_vst_mapping']
   for p in e['additional_recovered_controls']:
    routes+=p['current_vst_mapping']
  # Each V4.1 registry mapping is represented exactly once.
  uniq={(r['slot'],r['control_id']) for r in routes}
  self.assertEqual(len(uniq),19)
  self.assertEqual(len([r for r in routes if r['dynamic_router_vst_parameter_index'] is not None]),19)
  for e in M['effects']:
   for p in e['parameters']:
    for r in p['current_vst_mapping']:
     self.assertIn(r['dynamic_router_vst_parameter_index'],range(46,54))
 def test_signed_manual_ranges_are_preserved(self):
  found=[]
  for e in M['effects']:
   for p in e['parameters']:
    lo=p['documented_range']['minimum']
    if isinstance(lo,dict) and lo['value']<0:found.append((e['slot'],p['original_parameter_name'],lo['value']))
  self.assertTrue(found)
 def test_report_does_not_promote_no_difference_as_ineffective(self):
  for e in M['effects']:
   for p in e['parameters']:
    self.assertNotEqual(p['audio_behavior_validation'],'NO_DSP_EFFECT')
if __name__=='__main__':unittest.main(verbosity=2)
