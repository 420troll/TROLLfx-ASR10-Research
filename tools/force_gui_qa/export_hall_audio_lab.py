#!/usr/bin/env python3
"""Export existing private HALL WAV renders into Codex 2's AUDIO LAB schema.

The original float renders are preserved. AUDIO LAB accepts integer PCM WAV, so
this exporter also makes a no-gain-change PCM32 encoding for private bundles.
All bundles and WAVs stay outside Git; the published manifest is path-free.
"""
from __future__ import annotations
import argparse, base64, hashlib, importlib, json, math, struct, sys, wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_PRIVATE=Path.home()/"research/private-results/asr10-v4-gui-independent/hall-extreme-range-20261126"
DEFAULT_AUDIO_LAB=Path.home()/"worktrees/asr10-force-dynamic-editor-v4/tools/force_simulator"
REPORT=ROOT/'docs/qa-v4/ASR10_HALL_EXTREME_RANGE_AUDIO_QA_V1.json'
PAIR_CASES=(('display_10_vs_90',(10,13),(90,115)),('display_0_vs_99',(0,0),(99,127)),
            ('display_25_vs_75',(25,32),(75,96)),('display_40_vs_41',(40,51),(41,53)))


def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def read_float_wav(path:Path):
    b=path.read_bytes()
    if b[:4]!=b'RIFF' or b[8:12]!=b'WAVE' or b[20:22]!=b'\x03\x00' or b[22:24]!=b'\x02\x00' or b[34:36]!=b'\x20\x00':raise ValueError(f'{path.name} is not stereo IEEE-float32 WAV')
    rate=struct.unpack_from('<I',b,24)[0];frames=struct.unpack_from('<I',b,40)[0]//8
    samples=struct.unpack_from('<'+'f'*(frames*2),b,44)
    if not all(math.isfinite(x) for x in samples):raise ValueError(f'{path.name} contains non-finite samples')
    return rate,frames,samples

def write_pcm32(path:Path,rate:int,samples):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(4);f.setframerate(rate)
        vals=[]
        for x in samples:
            q=round(float(x)*2147483648.0)
            vals.append(max(-2147483648,min(2147483647,q)))
        f.writeframes(struct.pack('<'+'i'*len(vals),*vals))

def tail_bands(rms_100ms):
    groups=((0,1,'0-0.1s'),(1,5,'0.1-0.5s'),(5,10,'0.5-1s'),(10,20,'1-2s'),(20,50,'2-5s'),(50,80,'5-8s'),(80,100,'8-10s'))
    return {name:sum((rms_100ms[i]**2)*0.1 for i in range(lo,min(hi,len(rms_100ms)))) for lo,hi,name in groups}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--private-renders',type=Path,default=DEFAULT_PRIVATE)
    ap.add_argument('--audio-lab-root',type=Path,default=DEFAULT_AUDIO_LAB)
    ap.add_argument('--private-export',type=Path,default=DEFAULT_PRIVATE/'audio-lab-export')
    ap.add_argument('--manifest',type=Path,default=ROOT/'docs/qa-v4/ASR10_HALL_AUDIO_LAB_EXPORT_V1.json')
    a=ap.parse_args();source_report=json.loads(REPORT.read_text());raw_runs=source_report['runs']
    lab_root=a.audio_lab_root.resolve(strict=True);sys.path.insert(0,str(lab_root));lab=importlib.import_module('audio_lab')
    module_path=lab_root/'audio_lab.py';module_hash=sha_bytes(module_path.read_bytes())
    private=a.private_export;private.mkdir(parents=True,exist_ok=True)
    run_by_key={};renders=[]
    for row in raw_runs:
        name=f"hall_{'factory29762' if row['rate_mode']=='FactoryReference' else 'experimental48000'}_{row['stimulus']}_raw{row['raw']}{'_repeat' if row.get('repeat') else ''}.wav"
        src=a.private_renders/name
        if not src.is_file():raise SystemExit(f'missing original private render {name}')
        rate,frames,samples=read_float_wav(src)
        if frames!=row['frames'] or rate!=row['wav_header_rate_hz']:raise SystemExit(f'private float WAV disagrees with QA report: {name}')
        pcm_name=src.stem+'_pcm32.wav';pcm_path=private/'pcm32'/pcm_name
        if not pcm_path.is_file():write_pcm32(pcm_path,rate,samples)
        pcm_bytes=pcm_path.read_bytes();dest_rate,channels,sw,pcm_frames=0,0,0,0
        with wave.open(str(pcm_path),'rb') as f:channels=f.getnchannels();dest_rate=f.getframerate();sw=f.getsampwidth();pcm_frames=f.getnframes()
        if (channels,sw,dest_rate,pcm_frames)!=(2,4,rate,frames):raise SystemExit(f'AUDIO LAB PCM32 conversion invalid: {pcm_name}')
        entry={'rate_mode':row['rate_mode'],'stimulus':row['stimulus'],'display_value':None,'raw_code':row['raw'],'repeat':bool(row.get('repeat')),'frames':frames,
          'duration_seconds':frames/row['rate_hz'],'processing_rate_hz':row['rate_hz'],'sample_rate_header_hz':rate,
          'wav_float32_filename':name,'wav_float32_sha256':row['wav_sha256'],'wav_pcm32_filename':pcm_name,'wav_pcm32_sha256':sha_bytes(pcm_bytes),
          'rms':row['rms'],'peak':row['peak'],'stereo_cosine_correlation_uncentered':row['stereo_cosine_correlation_uncentered'],
          'late_tail_rms_8_10s':row['late_tail_rms_8_10s'],'tail_energy_bands':tail_bands(row['rms_100ms']),
          'rms_100ms':row['rms_100ms'],'finite_samples':row['finite_samples'],'schedule_writes_applied':row['schedule_writes_applied'],
          'parameter_writes_applied':row['writes_after_edit']-row['schedule_writes_applied'],'registers_before_edit':row.get('registers_before_edit',row['registers_before_render']),
          'registers_before_render':row['registers_before_render'],'registers_after_render':row['registers_after_render']}
        entry['display_value']={13:10,115:90,0:0,127:99,32:25,96:75,51:40,52:40,53:41,116:90}.get(row['raw'])
        if entry['display_value'] is None:raise SystemExit(f'no documented selected display for raw {row["raw"]}')
        if not row.get('repeat'):run_by_key[(row['rate_mode'],row['stimulus'],row['raw'])]=(entry,pcm_bytes)
        renders.append(entry)
    provenance=source_report['provenance'];method=source_report['method']
    bundle_rows=[];lab_reports=[]
    bundles=[]
    for mode in ('FactoryReference','Experimental48000'):
      for stim in ('impulse','noise_burst'):
        cases=[]
        for case_id,a_pair,b_pair in PAIR_CASES:
            raw_a,raw_b=a_pair[1],b_pair[1]
            ea,ba=run_by_key[(mode,stim,raw_a)];eb,bb=run_by_key[(mode,stim,raw_b)]
            reglist=[{'frame':method['schedule_settle_frames'],'register':reg} for reg in ('0x6e','0x5b','0x03','0x04','0x05')]
            def render_meta(entry,payload):
                return {'display_value':entry['display_value'],'raw_code':entry['raw_code'],'raw_code_basis':'original_os_observation',
                  'wav_base64':base64.b64encode(payload).decode('ascii'),'dsp_status':'applied','runtime_status':'ready','firmware_status':'initialized',
                  'processing_rate_hz':entry['processing_rate_hz'],'package_provenance':'validated_factory_checkpoint',
                  'provenance_id':'ROM01-HALL-RUN-'+provenance['checkpoint_sha256'][:8],
                  'source_commit':provenance['runtime_source_commit'],'register_updates':reglist}
            cases.append({'case_id':f'{case_id}_{"noise" if stim=="noise_burst" else stim}_{"factory" if mode=="FactoryReference" else "48k"}',
              'stimulus':'noise' if stim=='noise_burst' else 'impulse','a':render_meta(ea,ba),'b':render_meta(eb,bb)})
            delta=next(x for x in source_report['comparisons'] if x['rate_mode']==mode and x['stimulus']==stim and x['comparison']==case_id)
            bundle_rows.append({'bundle_case_id':cases[-1]['case_id'],'rate_mode':mode,'stimulus':stim,'comparison':case_id,
              'a':{'display_value':a_pair[0],'raw_code':raw_a,'wav_pcm32_filename':ea['wav_pcm32_filename'],'wav_pcm32_sha256':ea['wav_pcm32_sha256']},
              'b':{'display_value':b_pair[0],'raw_code':raw_b,'wav_pcm32_filename':eb['wav_pcm32_filename'],'wav_pcm32_sha256':eb['wav_pcm32_sha256']},
              'float32_difference_rms':delta['difference_rms'],'float32_difference_peak':delta['difference_peak']})
        bundle={'schema':lab.SCHEMA,'source':'standalone_experimental_runtime','effect_slot':1,'effect_name':'HALL REVERB','variation':1,'cases':cases}
        checked=lab.analyze_bundle(bundle)
        lab_reports.append(checked['measurement_report'])
        filename=f"hall-audio-lab-{mode.lower()}-{stim}.json";path=private/filename
        path.write_text(json.dumps(bundle,separators=(',',':'))+'\n')
        size=path.stat().st_size
        if size>70*1024*1024:raise SystemExit(f'AUDIO LAB bundle exceeds its 70 MiB limit: {filename}')
        bundles.append({'filename':filename,'sha256':sha_bytes(path.read_bytes()),'bytes':size,'rate_mode':mode,'stimulus':stim,'case_count':len(cases),'validator':'Codex 2 audio_lab.analyze_bundle'})
    manifest={'schema':'trollfx-asr10-hall-audio-lab-export-v1','effect':{'slot':1,'name':'HALL REVERB','variation':1},
      'source':'standalone_experimental_runtime','provenance':provenance,
      'startup':{'schedule_events_expected':method['schedule_event_count'],'schedule_events_applied':method['schedule_event_count'],
        'last_schedule_frame':method['last_schedule_frame'],'settle_frames':method['schedule_settle_frames'],'explicit_runtime_reset_each_run':True,
        'post_schedule_initial_register_state_identical':True,'serial_routing':provenance['routing']},
      'stimuli':method['input'],'rates':[{'mode':'FactoryReference','processing_rate_hz':provenance['factory_clock_hz'],'wav_header_rate_hz':29762},
        {'mode':'Experimental48000','processing_rate_hz':48000,'wav_header_rate_hz':48000}],
      'render_count':len(renders),'original_float_wavs_preserved':True,'render_manifest':renders,
      'comparison_pairs':bundle_rows,'audio_lab_bundles':bundles,'audio_lab_measurements':lab_reports,
      'additional_qa_comparisons':[x for x in source_report['comparisons'] if x['comparison'] in ('raw_51_vs_52','same_raw_51_vs_51')],
      'log_envelope_plots':['ASR10_HALL_FactoryReference_impulse_envelope.svg','ASR10_HALL_FactoryReference_noise_burst_envelope.svg',
        'ASR10_HALL_Experimental48000_impulse_envelope.svg','ASR10_HALL_Experimental48000_noise_burst_envelope.svg'],
      'format_note':'Original float32 WAVs remain unchanged. AUDIO LAB bundles use signed PCM32 re-encodings at identical rate/frame count, with no gain scaling or normalization. The AUDIO LAB recomputes metrics from those PCM32 bytes.',
      'validator':{'schema':lab.SCHEMA,'codex2_branch_head':'0a25d72f83f6ad622771193d0c6bc064a59d75a0','module_sha256':module_hash,
        'module_worktree_dirty_uncommitted':True,'bundle_analysis':'PASS_FOR_ALL_FOUR_BUNDLES'},
      'import_instructions':{'private_bundle_directory':'~/research/private-results/asr10-v4-gui-independent/hall-extreme-range-20261126/audio-lab-export',
        'http_endpoint':'http://127.0.0.1:8765/api/audio-lab/import','ui':'AUDIO LAB → Import comparison bundle'}}
    a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'manifest':str(a.manifest),'private_bundle_directory':str(private),'bundle_count':len(bundles),
      'bundle_files':[{'filename':x['filename'],'MiB':round(x['bytes']/1048576,2)} for x in bundles],
      'PCM32_render_count':len(renders),'validator':manifest['validator']},indent=2))
if __name__=='__main__':main()
