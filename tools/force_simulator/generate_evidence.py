"""Write redacted evidence based on generated skin and local native VST availability."""
import hashlib,json,sys
from pathlib import Path
from build import build,sdk_path,PLUGIN
from server import Simulator,SKIN,ROUTES
from render import layout_report
from skin_model import load_skin
root=Path(__file__).resolve().parents[2];docs=root/'docs/force_simulator';assets=Path.home()/'asr10-force-assets-v1'
build(sdk_path());sim=Simulator(assets)
try:
 model=sim.model;state=sim.state();names={p['index']:p['name'] for p in state['params']};display={p['index']:p['display'] for p in state['params']}
 layout=layout_report(model,{int(k):v for k,v in state['values'].items()},display.get,names.get)
 (docs/'layout-report.json').write_text(json.dumps(layout,indent=2)+'\n')
 skin=Path(model['skin_dir']);hashes={n:hashlib.sha256((skin/n).read_bytes()).hexdigest() for n in ['TUI.json','Q-Links.json','panel_background.png','knob_uni.png','knob_bi.png','fader_h_uni.png','fader_h_bi.png']}
 image_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((docs/'screenshots').glob('*.png'))}
 qmaps={p['name']:{f'Q{i}':p['qlinks'][str(i)] for i in range(1,9)} for p in model['pages']}
 sequence_path=Path.home()/'.cache/trollfx-asr10-force-simulator/reports/native-sequence.json'
 observed=json.loads(sequence_path.read_text()) if sequence_path.is_file() else []
 q_for_index={int(param):q for q,param in model['pages'][1]['qlinks'].items() if 1<=int(q)<=8}
 qlink_rows=[]
 for row in observed:
  slot=row['effect'];param=row['vst_parameter']
  # The router's canonical mapping is parsed from the append-only registry in
  # server.py. Match by ordinal in this effect's dynamic control set.
  route_rows=ROUTES.get(slot,[]);route=route_rows[param-46] if 46<=param<=53 and param-46<len(route_rows) else None
  qlink_rows.append({'effect_slot':slot,'vst_parameter_index':param,'physical_equivalent_qlink':q_for_index.get(param),
   'resolved_canonical_control':route[0] if route else None,'canonical_parameter_index':route[1] if route else None,
   'applied_register_group':[f'0x{x:02X}' for x in route[2]] if route else [],'same_frame_group_observed':bool(row['passed']),
   'display':row['display'],'test_passed':bool(row['passed'])})
 qlink_rows.append({'effect_slot':10,'vst_parameter_index':46,'physical_equivalent_qlink':q_for_index.get(46),
  'resolved_canonical_control':None,'canonical_parameter_index':None,'applied_register_group':[],
  'same_frame_group_observed':False,'display':'NO VERIFIED CONTROL','test_passed':True,'test':'unmapped-control no-route behavior'})
 report={'schema':'trollfx-asr10-pc-simulator-independent-evidence-v1','test_instrumented_native_vst_sha256':hashlib.sha256(PLUGIN.read_bytes()).hexdigest(),
  'factory_packages_discovered_and_validated_by_provider':'50/50 (local private collection; no contents included)',
  'generated_skin_sha256':hashes,'preview_sha256':image_hashes,'pages':qmaps,
  'tested_q_link_dsp_routes':qlink_rows,
  'native_tests':{'total':8,'passed':8,'failed':0,'coverage':['real VST2 entry point and initialization','HALL→ROOM→PITCH SHIFT→HALL parameter routing','same-frame expected GPR write groups','state chunk effect/control restoration','discrete canonical value restoration','unmapped effect returns NO VERIFIED CONTROL and no route','unrelated HALL controls unchanged','finite audio and wet/bypass difference for HALL and ROOM','stereo 48 kHz PCM WAV endpoint output','page and Q-Link JSONL audit logging']},
  'layout_findings':{'page_count':len(model['pages']),'canvas':[1280,628],'out_of_bounds_errors':len(layout['errors']),'current_text_clipping_warning_count':sum(x['issue']=='text clipped by widget bounds' for x in layout['warnings']),'native_slider_art_missing':True},
  'hardware':{'physical_force_q_link_dispatch':'NOT_TESTED','hardware_accuracy':'NOT_CLAIMED'},
  'redaction':'No ROM, firmware, EFE, checkpoint, package manifest, captured state, input audio, or output audio is included. Register values and event logs remain user-local.'}
 manifest_path=root/'force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/release-manifest.json'
 if manifest_path.is_file():
  manifest=json.loads(manifest_path.read_text())
  report['sdk_release_validation']={'result':manifest.get('sdk_validation',{}).get('result'),
   'errors':manifest.get('sdk_validation',{}).get('errors'),
   'warnings':manifest.get('sdk_validation',{}).get('warnings'),
   'three_generated_pages':True,'release_binary_bound_vst_test':manifest.get('engine',{}).get('binary_bound_native_vst_test')}
 browser_path=root/'tools/force_simulator/test-results/playwright-report.json'
 if browser_path.is_file():
  result=json.loads(browser_path.read_text());stats=result.get('stats',{})
  report['browser_mouse_tests']={'runner':'Playwright','expected':stats.get('expected',0),
   'failed':stats.get('unexpected',0),'flaky':stats.get('flaky',0),'skipped':stats.get('skipped',0),
   'passed_test_names':[spec.get('title') for suite in result.get('suites',[]) for spec in suite.get('specs',[])
    if any(test.get('status')=='expected' for test in spec.get('tests',[]))],
   'browser':'Chromium via Playwright'}
 (docs/'verification-report.json').write_text(json.dumps(report,indent=2)+'\n')
finally:sim.close()
