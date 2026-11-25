"""Focused real-VST2 integration tests; requires local validated factory packages."""
import os, sys, unittest, math, hashlib, struct, io, wave, json
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from build import build,sdk_path
from bridge import VSTBridge
from skin_model import load_skin
from render import layout_report
from server import SKIN,ROUTES,EFFECT_NAMES,Simulator

ASSETS=Path(os.environ.get('TROLLFX_FACTORY_PACKAGES_DIR',str(Path.home()/'asr10-force-assets-v1'))).expanduser()
SDK=sdk_path(os.environ.get('AKAI_FORCE_SDK'))

@unittest.skipUnless((ASSETS/'provider-index.tsv').is_file(),'private validated package root absent')
class NativePluginIntegration(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  p,h=build(SDK)
  cls.v=VSTBridge(h,p,ASSETS)
 @classmethod
 def tearDownClass(cls): cls.v.close()
 def select(self,slot):
  self.v.set(0,(slot-1)/49)
  for _ in range(50):
   self.v.pump(256)
   if f'{slot:02}' in self.v.text(0) and 'READY' in self.v.text(0): break
  self.assertIn('READY',self.v.text(0),f'{slot} failed package load: {self.v.text(0)}')
 def group(self,slot,param):
  self.v.reset_trace(); self.v.set(param,.83); self.v.pump(256)
  rows=self.v.trace_since(0)
  expected=ROUTES[slot][param-46][2]
  for i in range(len(rows)-len(expected)+1):
   g=rows[i:i+len(expected)]
   if [x['gpr'] for x in g]==expected and len({x['dsp_frame'] for x in g})==1: return g
  return []
 def test_layout_reads_real_generated_files(self):
  m=load_skin(SKIN)
  self.assertEqual([p['name'] for p in m['pages']],['BROWSE','EDIT','MIX'])
  self.assertEqual([p['width'] for p in m['pages']],[1280]*3)
  self.assertEqual(len(EFFECT_NAMES),50)
  self.assertEqual(m['pages'][1]['qlinks']['1'],46)
  self.assertEqual(m['pages'][1]['qlinks']['8'],53)
  self.select(1);values={i:self.v.get(i) for i in range(self.v.num_params)}
  report=layout_report(m,values,self.v.text,lambda i:self.v.text(i,True))
  self.assertFalse(any(w['issue']=='text clipped by widget bounds' for w in report['warnings']),report['warnings'])
  self.assertFalse(any(w['issue'] in ('overlapping label widget bounds','label overlaps control widget bounds') for w in report['warnings']),report['warnings'])
 def test_hall_room_pitch_and_return_route_to_dsp(self):
  cases=[(1,48,'DECAY TIME'),(3,46,'DECAY TIME'),(3,47,'DIFFUSION'),(39,46,'QUALITY'),(1,48,'DECAY TIME')]
  report=[]
  for slot,p,name in cases:
   self.select(slot); rows=self.group(slot,p)
   shown=self.v.text(p)
   ok=bool(rows) and name in shown
   report.append({'effect':slot,'vst_parameter':p,'display':shown,'gpr_group':rows,'passed':ok})
   self.assertTrue(ok,f'{slot} param {p} did not route: {shown}, trace={rows}')
  out=Path.home()/'.cache/trollfx-asr10-force-simulator/reports/native-sequence.json'
  out.parent.mkdir(parents=True,exist_ok=True);out.write_text(__import__('json').dumps(report,indent=2)+'\n')
 def test_routed_change_leaves_other_hall_controls_unchanged(self):
  self.select(1);before=[self.v.get(i) for i in (27,28,30)]
  rows=self.group(1,48)
  after=[self.v.get(i) for i in (27,28,30)]
  self.assertTrue(rows)
  self.assertEqual(before,after)
 def test_unmapped_effect_control_does_not_claim_verified_write(self):
  slot=10;self.select(slot);self.v.reset_trace();self.v.set(46,.91);self.v.pump(256)
  self.assertIn('NO VERIFIED CONTROL',self.v.text(46))
  self.assertIsNone(ROUTES.get(slot))
 def test_state_save_restore_preserves_effect_and_control(self):
  self.select(1);self.v.set(48,.99);self.v.pump(256);saved=self.v.save_state(); expected_canonical=self.v.get(29)
  self.select(3);self.v.pump(512);self.v.restore_state(saved);self.v.pump(512)
  self.assertIn('HALL REVERB',self.v.text(0));self.assertAlmostEqual(self.v.get(29),expected_canonical,places=3)
  self.assertAlmostEqual(self.v.get(48),1.0,places=3) # router snaps to the verified discrete point after restoration
 def test_audio_callback_is_finite_and_effect_output_differs_from_bypass(self):
  n=4096;data=[];x=0x2468ace1
  for i in range(n):
   x=(1664525*x+1013904223)&0xffffffff; l=((x>>8)/8388608)-1
   x=(1664525*x+1013904223)&0xffffffff; r=((x>>8)/8388608)-1
   data.extend((l*.08,r*.08))
  for slot in (1,3):
   self.select(slot);self.v.set(4,1);dry=self.v.process(data,n,128)
   self.v.set(4,0);wet=self.v.process(data,n,128)
   self.assertTrue(all(math.isfinite(y) for y in wet+dry),f'effect {slot} non-finite')
   self.assertGreater(sum(abs(a-b) for a,b in zip(wet,dry))/len(wet),1e-5,f'effect {slot} has no wet/bypass difference')
 def test_wav_endpoint_builds_wet_and_bypass_pcm_outputs(self):
  buf=io.BytesIO(); vals=[]
  for i in range(2048):
   x=9000 if i==0 else int(3000*math.sin(i*.071));vals.extend((x,-x))
  with wave.open(buf,'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000);w.writeframes(struct.pack('<'+'h'*len(vals),*vals))
  sim=Simulator(ASSETS)
  try:
   sim.set_param(0,0,page='BROWSE');res=sim.process_wav(buf.getvalue(),128)
   self.assertEqual(res['frames'],2048);self.assertEqual(res['sample_rate_hz'],48000)
   self.assertNotEqual(res['wet_sha256'],res['bypass_sha256'])
   self.assertTrue(res['wet_wav_base64'] and res['bypass_wav_base64'])
  finally:sim.close()
 def test_audit_event_logs_page_qlink_vst_canonical_and_dsp(self):
  sim=Simulator(ASSETS)
  try:
   sim.select_page(1);event=sim.set_param(48,.9,page='EDIT',qlink=3)
   self.assertEqual(event['physical_equivalent_qlink'],3)
   self.assertEqual(event['vst_parameter_index'],48)
   self.assertEqual(event['resolved_canonical_control']['id'],'decay_time')
   self.assertTrue(event['matched_control_write_group'])
   self.assertTrue(sim.log_path.is_file())
   lines=sim.log_path.read_text().splitlines()
   self.assertEqual(json.loads(lines[0])['event_type'],'page_navigation')
   self.assertEqual(json.loads(lines[-1])['physical_equivalent_qlink'],3)
  finally:sim.close()

if __name__=='__main__': unittest.main(verbosity=2)
