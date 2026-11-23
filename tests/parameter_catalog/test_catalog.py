import importlib.util, json, pathlib, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
P=ROOT/'tools/parameter_catalog/catalog.py'
spec=importlib.util.spec_from_file_location('parameter_catalog',P); cat=importlib.util.module_from_spec(spec); spec.loader.exec_module(cat)
class CatalogTests(unittest.TestCase):
 def test_seed_has_exact_public_inventory_and_explicit_unknowns(self):
  d=cat.seed(); self.assertEqual(len(d['effects']),50); self.assertEqual(d['effects'][0]['display_name'],'HALL REVERB'); self.assertEqual(d['effects'][-1]['display_name'],'VAN DER POL'); self.assertEqual(cat.validate(d),[])
  self.assertEqual(d['effects'][0]['parameters'],[]); self.assertEqual(d['effects'][0]['parameter_enumeration_status'],'not_enumerated')
 def test_verified_mapping_table(self):
  d=cat.seed(); found={(e['display_name'],p['name']):p['dsp_mapping']['address'] for e in d['effects'] for p in e['parameters']}
  self.assertEqual(found[('PARAM EQ','BASS GAIN')],'0x56'); self.assertEqual(found[('44KHZ REVERB','REVERB MIX BUS2')],'0x7A')
  for e in d['effects']:
   for p in e['parameters']: self.assertIsNone(p['default']); self.assertIsNone(p['range']['minimum'])
 def test_parse_emulator_display_and_merge_deduplicates(self):
  d=cat.seed(); log='''[ 1.000s] |REVERB MIX BUS2=25    |\n[ 1.001s] |REVERB MIX BUS2=25    |\n[ 1.500s] |REVERB MIX BUS2=26    |\nFINAL |REVERB MIX BUS2=26    |\n'''
  rows=cat.enum_intake(d,2,log); p=d['effects'][1]['parameters'][0]
  self.assertEqual(len(rows),2); self.assertEqual(p['displayed_values_observed'],['25','26']); self.assertEqual(cat.validate(d),[])
 def test_intake_unknown_param_never_infers_range_or_gpr(self):
  d=cat.seed(); cat.enum_intake(d,1,'[ 2.0s] |NEW PARAM=7    |')
  p=d['effects'][0]['parameters'][0]; self.assertIsNone(p['default']); self.assertIsNone(p['range']['maximum']); self.assertEqual(p['dsp_mapping']['status'],'unknown'); self.assertIsNone(p['dsp_mapping']['address'])
 def test_invalid_effect_sequence_rejected(self):
  d=cat.seed(); d['effects'][8]['id']=99; self.assertTrue(cat.validate(d))
 def test_catalog_json_roundtrip(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'catalog.json'; p.write_text(json.dumps(cat.seed())); self.assertEqual(cat.validate(json.loads(p.read_text())),[])
if __name__=='__main__': unittest.main()
