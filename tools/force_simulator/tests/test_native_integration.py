"""Focused real-VST2 integration tests; requires local validated factory packages."""
import os, sys, unittest, math, hashlib, struct, io, wave, json, threading, http.server, subprocess, tempfile
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
 def test_codex1_runtime_ready_flag_is_not_a_native_vst_route(self):
  sim=Simulator(ASSETS)
  try:
   sim.set_param(0,0,page='BROWSE');trace=sim.host.trace_latest()
   control=next(c for c in sim.model['factory_effects'][0]['controls'] if c['id']=='low_freq_decay_1')
   self.assertTrue(control['v05_runtime_ready']);self.assertIsNone(control['route'])
   event=sim.set_control('low_freq_decay_1',6)['event']
   self.assertFalse(event['dsp_sent']);self.assertEqual(event['runtime_state'],'PENDING_HOST_ROUTE')
   self.assertEqual(event['dsp_register_writes_applied'],[])
   self.assertEqual(sim.host.trace_latest(),trace)
  finally:sim.close()
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
 def test_hall_decay_register_route_is_not_yet_audible_and_unsupported_values_stay_pending(self):
  def render_at(value):
   sim=Simulator(ASSETS)
   sim.set_param(0,0,page='BROWSE')
   sim.select_variation(1) # PC Variation 1 context; provider manifest does not establish native variation metadata.
   event=sim.set_control('decay_time_1',value)['event']
   n=65536; audio=[]
   for i in range(n):
    left=.12*math.sin(2*math.pi*431*i/48000)+.03*math.sin(2*math.pi*997*i/48000)
    right=.11*math.sin(2*math.pi*563*i/48000)+.02*math.sin(2*math.pi*1301*i/48000)
    audio.extend((left,right))
   output=sim.host.process(audio,n,256)
   return sim,event,output
  a,e40,out40=render_at(40)
  b,e41,out41=render_at(41)
  try:
   self.assertEqual(e40['selected_effect']['slot'],1);self.assertEqual(e41['selected_variation'],1)
   self.assertTrue(e40['dsp_sent'] and e41['dsp_sent'])
   gprs=[int(x['gpr'],16) for x in e41['dsp_register_writes_applied']]
   self.assertTrue(any(gprs[i:i+5]==[3,4,5,0x5b,0x6e] for i in range(len(gprs)-4)),gprs)
   self.assertTrue(all(math.isfinite(x) for x in out40+out41))
   rms=math.sqrt(sum((x-y)**2 for x,y in zip(out40,out41))/len(out40))
   # The host parameter route emits the known register group, but these two
   # native VST renders are currently bit-identical. Keep that as an explicit
   # non-acceptance result: register writes alone do not prove audible DSP use.
   self.assertEqual(out40,out41)
   self.assertEqual(rms,0.0)
   trace=b.host.trace_latest()
   unsupported=b.set_control('decay_time_1',99)['event']
   self.assertFalse(unsupported['dsp_sent'])
   self.assertEqual(unsupported['dsp_register_writes_applied'],[])
   self.assertEqual(b.host.trace_latest(),trace)
  finally:a.close();b.close()
 def test_hall_native_runtime_adapter_real_api_both_gate_states(self):
  root=HERE.parents[1]
  source=root/'tools/force_simulator/tests/test_hall_decay_native_adapter.cpp'
  with tempfile.TemporaryDirectory(prefix='trollfx-hall-native-') as tmp:
   for gate in (0,1):
    binary=Path(tmp)/f'hall-adapter-gate-{gate}'
    command=['g++','-std=c++17','-O2','-Wall','-Wextra','-Wpedantic','-DTROLLFX_SIMULATOR_TRACE',
      f'-DTROLLFX_HALL_DECAY_NATIVE_GATE={gate}','-I'+str(root/'include'),'-I'+str(root/'src'),str(source),
      str(root/'src/es5510_factory_runtime.cpp'),str(root/'src/es5510.cpp'),str(root/'src/hall_decay_native_adapter.cpp'),'-pthread','-o',str(binary)]
    subprocess.run(command,check=True,cwd=root,capture_output=True,text=True)
    result=subprocess.run([str(binary)],check=True,cwd=root,capture_output=True,text=True)
    self.assertIn('HALL native adapter tests: PASS',result.stdout)
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

 def test_pc_variation_drafts_are_independent_and_unsupported_undo_reset_do_not_write(self):
  sim=Simulator(ASSETS)
  try:
   sim.set_param(0,0,page='BROWSE')
   sim.select_variation(2)
   trace_before=sim.host.trace_latest()
   exact_in_pc_variation=sim.set_control('decay_time_1',41)['event']
   self.assertFalse(exact_in_pc_variation['dsp_sent'])
   self.assertEqual(exact_in_pc_variation['runtime_state'],'PC_ONLY_VARIATION')
   self.assertEqual(sim.host.trace_latest(),trace_before)
   first=sim.set_control('decay_time_1',42)['event']
   self.assertFalse(first['dsp_sent'])
   sim.select_variation(3)
   sim.set_control('decay_time_1',43)
   sim.select_variation(2)
   self.assertEqual(next(c['value'] for c in sim.state()['inspector_controls'] if c['id']=='decay_time_1'),42)
   sim.undo_draft()
   self.assertEqual(next(c['value'] for c in sim.state()['inspector_controls'] if c['id']=='decay_time_1'),41)
   sim.set_control('decay_time_1',45)
   result=sim.reset_draft()
   self.assertFalse(result['event']['dsp_sent'])
   self.assertEqual(result['event']['dsp_register_writes_applied'],[])
   self.assertEqual(next(c['value'] for c in result['state']['inspector_controls'] if c['id']=='decay_time_1'),40)
  finally: sim.close()

 def test_pc_draft_schema_migrates_stable_id_without_changing_vst_state(self):
  first=Simulator(ASSETS);second=Simulator(ASSETS)
  try:
   first.set_param(0,0,page='BROWSE');first.select_variation(2);first.set_control('decay_time_1',47)
   document=first.export_pc_drafts()
   self.assertEqual(document['schema_version'],1)
   # Version 0 was the prior unversioned slot:variation draft dictionary.
   legacy={'schema_version':0,'drafts':{**document['drafts'],'1:2':{**document['drafts']['1:2'],'removed_manual_widget':9}}}
   second.set_param(0,0,page='BROWSE')
   trace_before=second.host.trace_since(0)
   result=second.import_pc_drafts(legacy)
   self.assertGreaterEqual(result['drafts_restored'],1);self.assertFalse(result['dsp_sent'])
   self.assertEqual(result['orphaned'][0]['control_id'],'removed_manual_widget')
   self.assertEqual(result['orphaned'][0]['value'],9)
   second.select_variation(2)
   control=next(c for c in second.state()['inspector_controls'] if c['id']=='decay_time_1')
   self.assertEqual(control['value'],47)
   self.assertEqual(control['canonical_identity'],'ASR10:ROM-01:decay_time_1')
   self.assertEqual(second.host.get(29),first.host.get(29))
   self.assertEqual(second.host.trace_since(0),trace_before)
  finally:first.close();second.close()

 def test_unresolved_envelope_components_do_not_accept_pc_edits(self):
  sim=Simulator(ASSETS)
  try:
   sim.set_param(0,21/49,page='BROWSE')
   with self.assertRaisesRegex(ValueError,'not part of the selected effect'):
    sim.set_control('manual_env_lev_6',60)
   effect=sim.model['factory_effects'][21]
   self.assertTrue(any('five values' in x for x in effect['manual_group_warnings']))
   self.assertEqual(effect['os_scan_status'],'complete')
  finally:sim.close()

 def test_original_os_monitor_proxy_is_local_and_read_only(self):
  requests=[]
  class Handler(http.server.BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    requests.append(('GET',self.path))
    if self.path=='/api/status':payload={'selected_slot':4,'selected_name':'DUAL DELAYS','variation':1,'parameter':'BS1 TIME R','display_value':'700','lcd':'DUAL DELAYS BS1 TIME R 700','recovery_status':'PARTIAL','register_count':2}
    else:payload={'events':[{'id':1,'type':'gpr','gpr':'0x0C','value':'0x520900','frame':12,'pc':'0xFFF0'}]}
    raw=json.dumps(payload).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
   def do_POST(self):requests.append(('POST',self.path));self.send_error(405)
  upstream=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
  thread=threading.Thread(target=upstream.serve_forever,daemon=True);thread.start()
  old=os.environ.get('TROLLFX_OS_MONITOR_URL');os.environ['TROLLFX_OS_MONITOR_URL']=f'http://127.0.0.1:{upstream.server_port}'
  sim=Simulator(ASSETS)
  try:
   data=sim.os_monitor_snapshot()
   self.assertTrue(data['connected']);self.assertEqual(data['selected_slot'],4)
   self.assertEqual(data['register_writes'][0]['gpr'],'0x0C')
   self.assertEqual([x[0] for x in requests],['GET','GET'])
   with self.assertRaisesRegex(ValueError,'localhost HTTP'):
    os.environ['TROLLFX_OS_MONITOR_URL']='https://example.com';Simulator.__new__(Simulator).__init__(ASSETS)
  finally:
   sim.close();upstream.shutdown();upstream.server_close();thread.join(timeout=1)
   if old is None:os.environ.pop('TROLLFX_OS_MONITOR_URL',None)
   else:os.environ['TROLLFX_OS_MONITOR_URL']=old

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
