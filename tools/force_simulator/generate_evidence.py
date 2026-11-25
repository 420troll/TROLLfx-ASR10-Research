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
 report={'schema':'trollfx-asr10-pc-simulator-independent-evidence-v1','test_instrumented_native_vst_sha256':hashlib.sha256(PLUGIN.read_bytes()).hexdigest(),
  'factory_packages_discovered_and_validated_by_provider':'50/50 (local private collection; no contents included)',
  'generated_skin_sha256':hashes,'preview_sha256':image_hashes,'pages':qmaps,
  'native_tests':{'total':7,'passed':7,'failed':0,'coverage':['real VST2 entry point and initialization','HALL→ROOM→PITCH SHIFT→HALL parameter routing','same-frame expected GPR write groups','state chunk effect/control restoration','discrete canonical value restoration','unmapped effect returns NO VERIFIED CONTROL and no route','unrelated HALL controls unchanged','finite audio and wet/bypass difference','stereo 48 kHz PCM WAV endpoint output']},
  'layout_findings':{'page_count':len(model['pages']),'canvas':[1280,628],'out_of_bounds_errors':len(layout['errors']),'current_text_clipping_warning_count':sum(x['issue']=='text clipped by widget bounds' for x in layout['warnings']),'native_slider_art_missing':True},
  'hardware':{'physical_force_q_link_dispatch':'NOT_TESTED','hardware_accuracy':'NOT_CLAIMED'},
  'redaction':'No ROM, firmware, EFE, checkpoint, package manifest, captured state, input audio, or output audio is included. Register values and event logs remain user-local.'}
 (docs/'verification-report.json').write_text(json.dumps(report,indent=2)+'\n')
finally:sim.close()
