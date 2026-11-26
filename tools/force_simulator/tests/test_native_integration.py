"""Focused real-VST2 integration tests; requires local validated factory packages."""
import os, sys, unittest, math, hashlib, struct, io, wave, json, threading, http.server, subprocess, tempfile, csv
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

def _new_vst_bridge():
 plugin,host=build(SDK)
 return VSTBridge(host,plugin,ASSETS)

def _deterministic_noise(frames,seed=0x5eed5510,amplitude=.12):
 def f32(x): return struct.unpack('<f',struct.pack('<f',x))[0]
 result=[]
 for n in range(frames):
  if n>=round(48000*.5): result.extend((0.0,0.0));continue
  row=[]
  for lane in (1,2):
   x=(seed+n*2+lane)&0xffffffff
   x^=(x<<13)&0xffffffff;x&=0xffffffff;x^=x>>17;x&=0xffffffff;x^=(x<<5)&0xffffffff;x&=0xffffffff
   x=f32(f32(f32(x&0xffffff)/f32(8388607.5))-1.0)
   row.append(f32(x*f32(amplitude)))
  result.extend(row)
 return result

def _reference_input_sha(samples):
 return hashlib.sha256(struct.pack('<'+'f'*len(samples),*samples)).hexdigest()

def _expected_hall_startup_writes():
 row=next(x for x in (ASSETS/'provider-index.tsv').read_text().splitlines()[1:] if x.split('\t',1)[0]=='1')
 schedule=ASSETS/row.split('\t')[12]
 with schedule.open(newline='') as src:
  return [(int(x['relative_dsp_frame']),int(x['gpr'],16),int(x['value24'],16))
          for x in csv.DictReader(src)]

def _write_pcm32_stereo(path,samples,rate=48000):
 with wave.open(str(path),'wb') as wf:
  wf.setnchannels(2);wf.setsampwidth(4);wf.setframerate(rate)
  vals=[max(-2147483648,min(2147483647,round(max(-1.0,min(1.0,x))*2147483648))) for x in samples]
  wf.writeframes(struct.pack('<'+'i'*len(vals),*vals))

def _export_actual_vst_pair(name,stimulus,values,raw_codes,outputs,register_rows,rate=48000):
 from audio_lab import analyze_bundle
 base=Path.home()/'.cache/trollfx-asr10-force-simulator/reports/actual-vst-audio-lab'
 base.mkdir(parents=True,exist_ok=True)
 wav_paths=[]
 for label,samples in zip(('a','b'),outputs):
  path=base/f'{name}-{label}.wav';_write_pcm32_stereo(path,samples,rate);wav_paths.append(path)
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE.parents[1],text=True).strip()
 def row(index):
  frame,registers=register_rows[index]
  return {'display_value':values[index],'raw_code':raw_codes[index],
   'raw_code_basis':'original_os_observation','dsp_status':'applied','runtime_status':'ready',
   'firmware_status':'initialized','processing_rate_hz':48000.0,
   'package_provenance':'validated_factory_checkpoint','provenance_id':'ROM01-HALL-RUN-a7c4196b',
   'source_commit':commit,'register_updates':[{'frame':frame,'register':f'0x{gpr:02X}'} for gpr in registers]}
 metadata={'source':'actual_vst_audio','variation':1,'stimulus':stimulus,'case_id':name,
  'a':row(0),'b':row(1)}
 meta_path=base/f'{name}-metadata.json';meta_path.write_text(json.dumps(metadata,indent=2)+'\n')
 bundle_path=base/f'{name}.json'
 packer=HERE/'audio_lab_pack.py'
 subprocess.run([sys.executable,str(packer),'--metadata',str(meta_path),'--a-wav',str(wav_paths[0]),
  '--b-wav',str(wav_paths[1]),'--output',str(bundle_path)],check=True,capture_output=True,text=True)
 bundle=json.loads(bundle_path.read_text())
 checked=analyze_bundle(bundle)
 if checked['source']!='actual_vst_audio' or len(checked['cases'])!=1:
  raise AssertionError('VST2 output failed the existing AUDIO LAB artifact contract')
 return {'bundle':str(bundle_path),'wav_paths':[str(p) for p in wav_paths],
  'sha256':hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
  'a_metrics':checked['cases'][0]['a']['metrics'],'b_metrics':checked['cases'][0]['b']['metrics']}

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
  # Firmware writes own the DSP through frame 12,983 (HALL) or each other
  # effect's validated terminal event. Make the edit only after that schedule.
  status=self.v.runtime_status()
  self.v.pump(max(0,status['initialization_complete_frame']-status['dsp_frames'])+2)
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
   register_orders=([3,4,5,0x5b,0x6e],[0x6e,0x5b,3,4,5])
   self.assertTrue(any(gprs[i:i+5] in register_orders for i in range(len(gprs)-4)),gprs)
   self.assertTrue(all(math.isfinite(x) for x in out40+out41))
   rms=math.sqrt(sum((x-y)**2 for x,y in zip(out40,out41))/len(out40))
   self.assertGreater(rms,1e-8,'HALL 40/41 must differ through actual VST2 processReplacing output')
   trace=b.host.trace_latest()
   unsupported=b.set_control('decay_time_1',99)['event']
   self.assertFalse(unsupported['dsp_sent'])
   self.assertEqual(unsupported['dsp_register_writes_applied'],[])
   self.assertEqual(b.host.trace_latest(),trace)
  finally:a.close();b.close()

 def test_vst2_hall_startup_defers_40_41_and_changes_processReplacing_audio(self):
  n=32768;stimulus=_deterministic_noise(n)
  results=[]
  expected_values={40:{3:0x340000,4:0xcc0000,5:0x6adfff,0x5b:0x080034,0x6e:0x340000},
                   41:{3:0x350000,4:0xcb0000,5:0x6a0dff,0x5b:0x080035,0x6e:0x350000}}
  # The verified host route uses its captured canonical state for display 40
  # (raw 52); the independent OS stepping experiment uses the lower raw 51
  # representation for an Up-selected display-40 comparison.
  for value,norm in ((40,0.0),(41,1.0)):
   vst=_new_vst_bridge()
   try:
    self.assertIn('DECAY TIME',vst.text(29,name=True))
    before=vst.runtime_status()
    self.assertEqual(before['firmware_writes_pending'],213)
    self.assertEqual(before['initialization_complete_frame'],12984)
    vst.reset_trace();vst.pump(12985)
    initialized=vst.runtime_status()
    self.assertEqual(initialized['initialization_complete'],1)
    self.assertEqual(initialized['firmware_writes_pending'],0)
    self.assertEqual(initialized['dsp_frames'],12985)
    vst.set(29,norm)
    audio=vst.process([0.0,0.0],1,1)+vst.process(stimulus,n,128)
    self.assertTrue(all(math.isfinite(x) for x in audio))
    status=vst.runtime_status()
    self.assertEqual(status['dsp_frames'],12986+n)
    self.assertEqual(status['initialization_complete'],1)
    self.assertEqual(status['firmware_writes_pending'],0)
    self.assertEqual(status['parameter_writes_pending'],0)
    self.assertEqual(status['last_parameter_write_applied'],1)
    rows=vst.trace_since(0)
    self.assertEqual(len([x for x in rows if x['dsp_frame']<12984]),213)
    self.assertEqual([(x['dsp_frame'],x['gpr'],x['value24']) for x in rows[:213]],_expected_hall_startup_writes())
    target=None
    for i in range(len(rows)-4):
     group=rows[i:i+5]
     if [x['gpr'] for x in group]==[3,4,5,0x5b,0x6e] and len({x['dsp_frame'] for x in group})==1:
      if {x['gpr']:x['value24'] for x in group}==expected_values[value]:target=group;break
    self.assertIsNotNone(target,f'VST2 register group for decay {value} not applied: {rows[-10:]}')
    self.assertEqual(target[0]['dsp_frame'],12985)
    results.append({'value':value,'audio':audio,'trace':target})
   finally:vst.close()
  diff=math.sqrt(sum((x-y)**2 for x,y in zip(results[0]['audio'],results[1]['audio']))/len(results[0]['audio']))
  self.assertGreater(diff,1e-8)
  exported=_export_actual_vst_pair('vst2_hall_40_vs_41_noise','noise',[40,41],[52,53],
   [results[0]['audio'],results[1]['audio']],
   [(results[i]['trace'][0]['dsp_frame'],[x['gpr'] for x in results[i]['trace']]) for i in range(2)])
  self.assertEqual(exported['a_metrics']['stereo']['rms']>0,True)

 def test_vst2_parameter_edit_during_startup_waits_for_terminal_firmware_event(self):
  vst=_new_vst_bridge()
  try:
   before=vst.runtime_status()
   self.assertEqual(before['firmware_writes_pending'],213)
   self.assertEqual(before['initialization_complete_frame'],12984)
   vst.reset_trace();vst.set(29,1.0)  # DECAY 41 through the VST2 setParameter callback
   vst.pump(12984)                  # executes DSP frames 0..12983
   waiting=vst.runtime_status()
   self.assertEqual(waiting['dsp_frames'],12984)
   self.assertEqual(waiting['firmware_writes_pending'],0)
   self.assertEqual(waiting['initialization_complete'],1)
   self.assertEqual(waiting['hall_state_provenance'],0,
    'overlapping HALL decay edit during startup must keep the raw editor state fail-closed')
   self.assertGreater(waiting['parameter_writes_pending'],0)
   self.assertEqual(waiting['last_parameter_write_applied'],0)
   self.assertEqual(len([r for r in vst.trace_since(0) if r['dsp_frame']<12984]),213)
   startup_rows=vst.trace_since(0)[:213]
   self.assertEqual([(r['dsp_frame'],r['gpr'],r['value24']) for r in startup_rows],_expected_hall_startup_writes())
   vst.pump(1)                     # first safe parameter frame is 12,984
   applied=vst.runtime_status()
   self.assertEqual(applied['dsp_frames'],12985)
   self.assertEqual(applied['parameter_writes_pending'],0)
   self.assertEqual(applied['last_parameter_write_applied'],1)
   self.assertEqual(applied['hall_state_provenance'],0)
   expected={3:0x350000,4:0xcb0000,5:0x6a0dff,0x5b:0x080035,0x6e:0x350000}
   rows=vst.trace_since(0);group=None
   for i in range(len(rows)-4):
    candidate=rows[i:i+5]
    if [r['gpr'] for r in candidate]==[3,4,5,0x5b,0x6e] and {r['gpr']:r['value24'] for r in candidate}==expected:
     group=candidate;break
   self.assertIsNotNone(group,rows[-10:])
   self.assertEqual(group[0]['dsp_frame'],12984)
  finally:vst.close()

 def test_vst2_hall_editor_state_resolves_and_steps_raw_51_52(self):
  vst=_new_vst_bridge()
  try:
   before=vst.runtime_status()
   self.assertEqual(before['hall_state_provenance'],0)
   self.assertEqual(before['hall_display_value'],-1)
   vst.pump(12984)  # authenticated schedule ends at frame 12,983
   startup=vst.runtime_status()
   self.assertEqual(startup['initialization_complete'],1)
   self.assertEqual(startup['factory_variation'],1)
   self.assertEqual(startup['hall_state_provenance'],1)
   self.assertEqual((startup['hall_raw_code'],startup['hall_display_value']),(52,40))
   # Two unrelated verified BUS controls are queued for first safe frame;
   # they do not affect the five-GPR decay state match.
   self.assertEqual(startup['parameter_writes_pending'],2)
   # The OS step routine skips duplicate LCD buckets. At raw 52 / display 40,
   # Down skips raw 51 and reaches raw 50 / display 39; Up returns to raw 52.
   self.assertEqual(vst.test_step_hall_decay(-1),1)  # adapter accepted; group pending
   pending=vst.runtime_status()
   self.assertEqual((pending['hall_raw_code'],pending['hall_display_value']),(50,39))
   self.assertGreater(pending['parameter_writes_pending'],0)
   vst.pump(1)
   down=vst.runtime_status()
   self.assertEqual((down['hall_raw_code'],down['hall_display_value']),(50,39))
   self.assertEqual(down['hall_state_provenance'],2)
   self.assertEqual(down['parameter_writes_pending'],0)
   self.assertEqual(vst.test_step_hall_decay(1),1)
   vst.pump(1)
   up=vst.runtime_status()
   self.assertEqual((up['hall_raw_code'],up['hall_display_value']),(51,40))
   self.assertEqual(up['hall_state_provenance'],2)
   self.assertEqual(up['parameter_writes_pending'],0)
   self.assertEqual(vst.test_step_hall_decay(1),1)
   vst.pump(1)
   next_up=vst.runtime_status()
   self.assertEqual((next_up['hall_raw_code'],next_up['hall_display_value']),(53,41))
   self.assertEqual(next_up['hall_state_provenance'],2)
   self.assertEqual(vst.test_step_hall_decay(0),3)  # unsupported direction rejected
   self.assertEqual(vst.test_step_hall_decay(1,variation=2),3)  # unverified Variation 2 fails closed
   self.assertEqual((vst.runtime_status()['hall_raw_code'],vst.runtime_status()['hall_display_value']),(53,41))
  finally:vst.close()

 def test_vst2_raw_hall_extremes_match_codex3_standalone_measurements(self):
  bundle_dir=os.environ.get('TROLLFX_HALL_AUDIO_LAB_BUNDLE_DIR')
  qa_path=os.environ.get('TROLLFX_HALL_AUDIO_LAB_QA_REPORT')
  if not bundle_dir or not qa_path:self.skipTest('local Codex 3 HALL artifacts are not configured')
  qa=json.loads(Path(qa_path).read_text())
  if qa['validator']['bundle_analysis']!='PASS_FOR_ALL_FOUR_BUNDLES':self.fail('Codex 3 artifact validation was not PASS')
  measurement_rows=[c for group in qa['audio_lab_measurements'] for c in group['cases']]
  input_audio=_deterministic_noise(480000)
  self.assertEqual(_reference_input_sha(input_audio),qa['stimuli']['per_rate_sha256']['Experimental48000']['noise_burst'])
  pairs=((10,90,13,115),(0,99,0,127));measurements=[]
  def metrics(samples):
   return {'rms':math.sqrt(sum(x*x for x in samples)/len(samples)),
           'peak':max(abs(x) for x in samples)}
  for left_display,right_display,left_raw,right_raw in pairs:
   outputs=[];trace_groups=[]
   for raw in (left_raw,right_raw):
    vst=_new_vst_bridge()
    try:
     self.assertTrue(vst.enable_test_raw_override())
     vst.reset_trace();vst.pump(12985) # finish the authentic 213-event schedule with silence
     initialized=vst.runtime_status()
     self.assertEqual(initialized['initialization_complete'],1)
     self.assertEqual(initialized['firmware_writes_pending'],0)
     self.assertEqual(initialized['writes_applied'],213)
     self.assertTrue(vst.set_test_hall_raw(raw))
     vst.process([0.0,0.0],1,1)       # commit the five-register OS group at the current DSP frame
     applied=vst.runtime_status()
     self.assertEqual(applied['parameter_writes_pending'],0)
     self.assertEqual(applied['last_parameter_write_applied'],1)
     rows=vst.trace_since(0);target=None
     self.assertEqual([(r['dsp_frame'],r['gpr'],r['value24']) for r in rows[:213]],_expected_hall_startup_writes())
     expected_order=[0x6e,0x5b,0x03,0x04,0x05]
     for i in range(len(rows)-4):
      group=rows[i:i+5]
      if [r['gpr'] for r in group]==expected_order and len({r['dsp_frame'] for r in group})==1 and group[0]['value24']==raw<<16:
       target=group;break
     self.assertIsNotNone(target,f'OS raw group {raw} missing from VST2 trace')
     self.assertEqual(target[0]['dsp_frame'],12985)
     audio=vst.process(input_audio,480000,256)
     self.assertTrue(all(math.isfinite(x) for x in audio))
     outputs.append(audio)
     trace_groups.append((target[0]['dsp_frame'],[r['gpr'] for r in target]))
    finally:vst.close()
   actual_a,actual_b=metrics(outputs[0]),metrics(outputs[1])
   diff=[a-b for a,b in zip(outputs[0],outputs[1])]
   actual_diff=metrics(diff)
   expected=next(c for c in measurement_rows if c['display_values']==[left_display,right_display]
                 and c['stimulus']=='noise' and c['processing_rates_hz']==[48000,48000])
   # The VST backend applies no normalization, runs wet=100%, input/output at
   # 0 dB, and has the same two-frame runtime latency. The desktop plugin's
   # 5 ms effect-switch fade is completed during the 0.27 s firmware settle.
   for got,want in zip((actual_a['rms'],actual_b['rms']),expected['rms']):
    self.assertLess(abs(got-want),max(2e-5,want*.02),(got,want))
   self.assertLess(abs(actual_diff['rms']-expected['difference_rms']),max(2e-5,expected['difference_rms']*.02),
                   (actual_diff['rms'],expected['difference_rms']))
   self.assertLess(abs(actual_diff['peak']-expected['difference_peak']),.005,
                   (actual_diff['peak'],expected['difference_peak']))
   name=f'vst2_hall_{left_display}_vs_{right_display}_noise'
   artifact=_export_actual_vst_pair(name,'noise',[left_display,right_display],[left_raw,right_raw],outputs,trace_groups)
   measurements.append({'case':name,'display':[left_display,right_display],'raw':[left_raw,right_raw],
    'actual_rms':[actual_a['rms'],actual_b['rms']],'reference_rms':expected['rms'],
    'actual_difference_rms':actual_diff['rms'],'reference_difference_rms':expected['difference_rms'],
    'actual_difference_peak':actual_diff['peak'],'reference_difference_peak':expected['difference_peak'],
    'artifact':artifact})
  report=Path.home()/'.cache/trollfx-asr10-force-simulator/reports/vst2-hall-reference-reconciliation.json'
  report.parent.mkdir(parents=True,exist_ok=True)
  report.write_text(json.dumps({'source':'actual_vst_audio','reference_source':'standalone_experimental_runtime',
   'processing_rate_hz':48000,'host_rate_hz':48000,'wet':1.0,'input_gain_db':0.0,'output_gain_db':0.0,
   'normalization':'none','dry_latency_frames':2,'plugin_switch_fade_frames':240,
   'cases':measurements},indent=2)+'\n')

 def test_vst2_nonfinite_parameter_and_audio_inputs_are_sanitized(self):
  vst=_new_vst_bridge()
  try:
   for index in range(vst.num_params):
    vst.set(index,.375)
    prior=vst.get(index)
    for value in (float('nan'),float('inf'),float('-inf')):
     vst.set(index,value)
     self.assertEqual(vst.get(index),prior,
      f'non-finite setParameter for index {index} must be rejected without mutation')
   n=4096;inputs=[]
   for i in range(n):
    if i%4==0:inputs.extend((float('nan'),float('inf')))
    elif i%4==1:inputs.extend((float('-inf'),.25))
    elif i%4==2:inputs.extend((.5,float('nan')))
    else:inputs.extend((0.0,-.25))
   output=vst.process(inputs,n,128)
   self.assertTrue(all(math.isfinite(x) for x in output))
  finally:vst.close()

 def test_vst2_rapid_repeated_hall_edits_preserve_latest_value(self):
  vst=_new_vst_bridge()
  try:
   vst.reset_trace()
   for value in (0.0,1.0,0.0,1.0):vst.set(29,value)
   vst.pump(12985)
   initialized=vst.runtime_status()
   self.assertEqual(initialized['initialization_complete'],1)
   self.assertEqual(initialized['parameter_writes_pending'],0)
   self.assertEqual(initialized['last_parameter_write_applied'],1)
   # Latest edit is DECAY 41; its complete registered five-GPR group must be
   # the final value, even if other startup controls were queued in the block.
   vst.set(29,0.0);vst.set(29,1.0)
   vst.process([0.0,0.0],1,1)
   status=vst.runtime_status()
   self.assertEqual(status['parameter_writes_pending'],0)
   self.assertEqual(status['last_parameter_write_applied'],1)
   rows=vst.trace_since(0)
   groups=[]
   for i in range(len(rows)-4):
    g=rows[i:i+5]
    if [r['gpr'] for r in g]==[3,4,5,0x5b,0x6e] and len({r['dsp_frame'] for r in g})==1:
     groups.append(g)
   self.assertTrue(groups,rows[-12:])
   self.assertEqual(groups[-1][0]['dsp_frame'],12985)
   self.assertEqual({r['gpr']:r['value24'] for r in groups[-1]},
    {3:0x350000,4:0xcb0000,5:0x6a0dff,0x5b:0x080035,0x6e:0x350000})
  finally:vst.close()
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
   status=sim.host.runtime_status()
   sim.host.pump(max(0,status['initialization_complete_frame']-status['dsp_frames'])+2)
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
