#!/usr/bin/env python3
"""Audio-check selected recovered points through Codex1's native FactoryRuntime without modifying its tree."""
from __future__ import annotations
import argparse, hashlib, json, math, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path.home()/'worktrees/asr10-full-factory-parameter-recovery'
AUDIT=Path.home()/'research/private-results/asr10-all-50-effects/production-provider-audit.json'
META=ROOT/'docs/qa-v4/source/ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05.json'
V2=ROOT/'docs/qa-v4/source/ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json'
V3=ROOT/'docs/qa-v4/source/ASR10_FACTORY_PARAMETER_RECOVERY_V03.json'
PRIVATE_OUT=Path.home()/'research/private-results/asr10-independent-full-parameter-qa/audio'
PUBLIC_REPORT=ROOT/'docs/qa-v4/parameter-audio-validation-report.json'
CASES=[(1,'decay_time','v2'),(1,'hi_freq_damping','v2'),(3,'decay_time','v2'),(3,'diffusion','v2'),
       (6,'chorus_rate','v2'),(6,'chorus_rate_amount','v5'),(8,'flange_rate','v3'),(8,'flange_depth','v5'),
       (4,'dual_bs1_time_r','v5'),(4,'dual_bus2_feedback','v5')]

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,default=SOURCE);ap.add_argument('--audit',type=Path,default=AUDIT);ap.add_argument('--output-private',type=Path,default=PRIVATE_OUT);ap.add_argument('--report',type=Path,default=PUBLIC_REPORT);a=ap.parse_args()
 src=a.source_root.resolve();audit_path=a.audit.resolve(strict=True);audit=json.loads(audit_path.read_text());rows={x['slot']:x for x in audit['slots']}
 v1=json.loads((ROOT/'docs/qa-v4/source/ASR10_FACTORY_PARAMETER_CATALOG_V1.json').read_text());v2=json.loads(V2.read_text());v3=json.loads(V3.read_text());v5=json.loads(META.read_text())
 controls={}
 for e in v2['effects']:
  for c in e.get('parameters',[]):controls[(e['slot'],c['id'])]={'points':c['points'],'source':'V2'}
 for c in v3.get('new_verified_controls',[]):controls[(c['slot'],c['parameter_id'])]={'points':c['points'],'source':'V3'}
 for c in v5['controls']:controls[(c['slot'],c['parameter_id'])]={'points':c['verified_points'],'source':'V5'}
 a.output_private.mkdir(parents=True,exist_ok=True);binary=Path('/tmp/asr10-qa-factory-audio-compare')
 run=subprocess.run(['c++','-std=c++17','-O2','-I'+str(src/'include'),'-I'+str(src/'src'),
  str(src/'tools/audio_validation/factory_parameter_audio_compare.cpp'),str(src/'src/es5510_factory_runtime.cpp'),str(src/'src/es5510.cpp'),'-o',str(binary)],cwd=src,capture_output=True,text=True)
 if run.returncode:raise SystemExit('QA audio comparator build failed: '+run.stderr[-3000:])
 results=[]; extra_results=[]
 for slot,param_id,version in CASES:
  item=controls.get((slot,param_id))
  if not item:raise SystemExit(f'missing recovered point evidence for slot {slot} {param_id}')
  source_row=rows.get(slot);d=source_row.get('descriptor') if source_row else None
  if not d or not source_row.get('registry_eligible') or not source_row.get('capture_state_valid') or not source_row.get('checkpoint_is_at_run_boundary'):
   raise SystemExit(f'private audit does not authorize slot {slot} for native runtime playback')
  checkpoint=Path(d['run_checkpoint_path']).resolve(strict=True);schedule=Path(d['firmware_event_schedule_path']).resolve(strict=True)
  if digest(checkpoint)!=d['run_checkpoint_sha256'] or digest(schedule)!=d['firmware_event_schedule_sha256']:
   raise SystemExit(f'private checkpoint or schedule hash mismatch for slot {slot}')
  p0,p1=item['points']
  # V2/V3 point dictionaries use text/value/writes; V5 uses the same contract.
  stem=f'slot-{slot:02d}-{param_id}-{version}'
  cmd=[str(binary),str(slot),d['factory_name'],str(d['active_program_words']),d['program_sha256'],str(checkpoint),d['run_checkpoint_sha256'],
       str(d['factory_reference_rate_hz']),str(schedule),param_id,str(p0['value']),str(p1['value']),str(a.output_private/stem)]
  proc=subprocess.run(cmd,cwd=src,capture_output=True,text=True)
  if proc.returncode:raise SystemExit(f'native audio comparison failed for slot {slot} {param_id}: {proc.stderr[-1500:]}')
  fields={}
  for token in proc.stdout.strip().split():
   if '=' in token:k,v=token.split('=',1);fields[k]=v
  finite=int(fields.get('finite','0'));frames=int(fields.get('frames','0'));diff=float(fields.get('difference_rms','nan'));peak=float(fields.get('difference_peak','nan'))
  if finite!=frames*2 or not math.isfinite(diff) or not math.isfinite(peak):raise SystemExit(f'non-finite/incomplete audio for slot {slot} {param_id}')
  results.append({'slot':slot,'factory_effect':d['factory_name'],'parameter_id':param_id,'evidence_source':version,
   'tested_points':[p0['text'],p1['text']],'native_runtime':'FactoryRuntime 48 kHz, checkpoint + firmware schedule validated privately',
   'frames_per_render':frames,'finite_stereo_samples_per_render':finite,'difference_rms':diff,'difference_peak':peak,
   'audio_change_observed':diff>0.0,'interpretation':'No measurable difference with this stimulus/window does not establish an ineffective parameter.',
   'exact_factory_audio_match':'NOT_TESTED','private_wav_files':True})
 no_difference=[r for r in results if not r['audio_change_observed']]
 if no_difference:
  original=(src/'tools/audio_validation/factory_parameter_audio_compare.cpp').read_text()
  start=original.index('static std::vector<float> input_signal(');end=original.index('\nstatic void warm(',start)
  replacement=r'''static std::vector<float> input_signal(std::size_t frames, std::size_t offset) {
    std::vector<float> x(frames*2);
    const char* mode=std::getenv("ASR10_QA_STIMULUS");
    for(std::size_t i=0;i<frames;++i){const std::size_t n=offset+i;float l=0,r=0;
      if(mode && std::string(mode)=="noise"){
        auto noise=[](std::uint64_t z){z^=z>>12;z^=z<<25;z^=z>>27;z*=2685821657736338717ULL;return float((z>>40)&0xffffff)/8388607.5f-1.0f;};
        l=.18f*noise(0x9e3779b97f4a7c15ULL+n*2);r=.18f*noise(0xd1b54a32d192ed03ULL+n*2+1);
      } else {
        const double duration=6.4, f0=20.0, f1=18000.0, k=f1/f0, t=std::fmod(double(n)/48000.0,duration);
        const double phase=2.0*3.141592653589793*f0*duration/std::log(k)*(std::pow(k,t/duration)-1.0);
        l=.24f*float(std::sin(phase));r=.20f*float(std::sin(phase*1.013+0.37));
      }
      if(n==0){l+=.7f;r-=.4f;}x[2*i]=l;x[2*i+1]=r;
    }return x;
}
'''
  transformed=original[:start]+replacement+original[end:]
  if '#include <cstdlib>' not in transformed:transformed=transformed.replace('#include <cstdint>','#include <cstdint>\n#include <cstdlib>')
  transformed=transformed.replace('constexpr std::size_t frames=65536, block=256;','constexpr std::size_t frames=262144, block=256;')
  extended_source=Path('/tmp/asr10-qa-factory-audio-extended.cpp');extended_source.write_text(transformed)
  extended_binary=Path('/tmp/asr10-qa-factory-audio-extended')
  compiled=subprocess.run(['c++','-std=c++17','-O2','-I'+str(src/'include'),'-I'+str(src/'src'),str(extended_source),str(src/'src/es5510_factory_runtime.cpp'),str(src/'src/es5510.cpp'),'-o',str(extended_binary)],cwd=src,capture_output=True,text=True)
  if compiled.returncode:raise SystemExit('extended stimulus comparator failed to build: '+compiled.stderr[-3000:])
  for r in no_difference:
   slot=r['slot'];param_id=r['parameter_id'];item=controls[(slot,param_id)];source_row=rows[slot];d=source_row['descriptor'];checkpoint=Path(d['run_checkpoint_path']).resolve(strict=True);schedule=Path(d['firmware_event_schedule_path']).resolve(strict=True)
   for stimulus in ('noise','sweep'):
    stem=f'slot-{slot:02d}-{param_id}-{stimulus}';p0,p1=item['points'];cmd=[str(extended_binary),str(slot),d['factory_name'],str(d['active_program_words']),d['program_sha256'],str(checkpoint),d['run_checkpoint_sha256'],str(d['factory_reference_rate_hz']),str(schedule),param_id,str(p0['value']),str(p1['value']),str(a.output_private/stem)]
    proc=subprocess.run(cmd,cwd=src,capture_output=True,text=True,env={**os.environ,'ASR10_QA_STIMULUS':stimulus})
    if proc.returncode:raise SystemExit(f'extended {stimulus} compare failed for {slot}/{param_id}: {proc.stderr[-1200:]}')
    fields={}
    for token in proc.stdout.strip().split():
     if '=' in token:k,v=token.split('=',1);fields[k]=v
    diff=float(fields.get('difference_rms','nan'));peak=float(fields.get('difference_peak','nan'))
    if int(fields.get('finite','0'))!=int(fields.get('frames','0'))*2 or not math.isfinite(diff):raise SystemExit(f'extended {stimulus} output invalid for slot {slot}/{param_id}')
    extra_results.append({'slot':slot,'parameter_id':param_id,'stimulus':stimulus,'frames_per_render':int(fields['frames']),
      'difference_rms':diff,'difference_peak':peak,'audio_change_observed':diff>0,'interpretation':'Longer deterministic stimulus; zero difference remains inconclusive.'})
 report={'schema':'asr10-independent-native-audio-parameter-validation-v1','test_source_commit':subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip(),
  'source_mapping_commits':['ce4bfdaa6dba8b3787e013a3262bbdeb7ec4d3ab'],'private_reference_assets_in_git':False,
  'test_stimulus':'Existing comparator deterministic stereo 431 Hz / 997 Hz sustained sinusoids plus stereo impulse; 32,768-frame warmup and 65,536-frame measured tail.',
  'results':results,'extended_stimulus_results':extra_results,'summary':{'pairs_tested':len(results),'audio_changes_observed':sum(r['audio_change_observed'] for r in results),
   'no_difference_in_this_window':sum(not r['audio_change_observed'] for r in results),'extended_stimulus_pairs':len(extra_results),'extended_changes_observed':sum(r['audio_change_observed'] for r in extra_results),'exact_factory_matches':0,
   'private_wav_directory':'user-local; not included in this report or Git'}}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report['summary'],indent=2))
if __name__=='__main__':main()
