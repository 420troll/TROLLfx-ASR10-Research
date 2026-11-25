#!/usr/bin/env python3
"""Run DSP assertions against a freshly built native SDK VST shared object."""
from __future__ import annotations
import argparse, hashlib, json, math, os, random, shutil, struct, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def run(args,env=None,check=True):
    p=subprocess.run([str(x) for x in args],text=True,capture_output=True,env=env)
    if check and p.returncode:raise RuntimeError(f"command failed ({p.returncode}): {' '.join(map(str,args))}\n{p.stdout}\n{p.stderr}")
    return p

def make_stimulus(path:Path,frames=8192,seed=0x5510A551):
    rng=random.Random(seed)
    with path.open('wb') as f:
        for i in range(frames):
            nl=rng.uniform(-0.015,0.015);nr=rng.uniform(-0.015,0.015)
            l=0.18*math.sin(2*math.pi*330*i/48000)+nl
            r=0.17*math.sin(2*math.pi*277*i/48000+0.31)+nr
            f.write(struct.pack('<ff',l,r))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native-plugin',type=Path,required=True);ap.add_argument('--arm32-plugin',type=Path,required=True)
    ap.add_argument('--sdk',type=Path,required=True);ap.add_argument('--collection',type=Path,required=True)
    ap.add_argument('--host-sim',type=Path,required=True);ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--cxx',default=os.environ.get('CXX','g++'));a=ap.parse_args()
    plugin=a.native_plugin.resolve(strict=True);arm=a.arm32_plugin.resolve(strict=True);sdk=a.sdk.resolve(strict=True)
    collection=a.collection.resolve(strict=True);hostsim=a.host_sim.resolve(strict=True)
    a.report=a.report.resolve();a.report.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='trollfx-vst-binary-check-') as t:
        work=Path(t);assets=work/'FactoryAssets';stimulus=work/'input-stimulus.f32';renders=work/'renders';renders.mkdir()
        prep=run([sys.executable,ROOT/'force_plugin/tools/prepare_force_assets.py',collection,assets])
        audit_result=json.loads(prep.stdout)
        prep_clock_gaps=audit_result.get('clock_unverified_after_run_slots',[])
        make_stimulus(stimulus);input_hash=sha(stimulus)
        harness=work/'vst-binary-test'
        run([a.cxx,'-std=c++17','-O2','-Wall','-Wextra','-Wpedantic','-rdynamic',
             '-I',sdk/'framework',ROOT/'tests/force_vst_binary_audio_test.cpp','-ldl','-pthread','-o',harness])
        env=os.environ.copy();env['TROLLFX_FACTORY_PACKAGES_DIR']=str(assets)
        result=run([harness,plugin,assets,stimulus,renders],env=env,check=False)
        (work/'binary-host.log').write_text(result.stdout+'\n'+result.stderr)
        if result.returncode:raise RuntimeError('packaged VST audio harness failed:\n'+result.stdout+'\n'+result.stderr)
        slot_lines=[x for x in result.stdout.splitlines() if x.startswith('SLOT ')]
        if len(slot_lines)!=50 or 'BINARY_PASS ' not in result.stdout:raise RuntimeError('binary-bound host did not report all 50 package results')
        if 'v4_controls=19 v4_verified_points=38' not in result.stdout or 'callbacks_allocations=0' not in result.stdout:
            raise RuntimeError('packaged VST did not verify all V4 points with an allocation-free callback')
        slot_results=[];output_hash=hashlib.sha256();non_silent=0
        for line in slot_lines:
            parts=line.split();slot=int(parts[1]);metrics={}
            for field in parts[3:]:
                k,v=field.split('=',1);metrics[k]=float(v) if k in ('rms_l','rms_r','peak') else int(v)
            render=renders/f'slot-{slot:02d}.f32'
            if not render.is_file():raise RuntimeError(f'VST audio output missing for slot {slot}')
            raw=render.read_bytes();output_hash.update(slot.to_bytes(1,'little'));output_hash.update(raw)
            samples=struct.iter_unpack('<f',raw)
            non_silent+=sum(1 for (v,) in samples if v!=0.0)
            slot_results.append({'slot':slot,'status':'PASS','frames':8192,'rms_left':metrics['rms_l'],'rms_right':metrics['rms_r'],'peak':metrics['peak'],'switch_completion_frames':metrics['transition_frames'],'clock_verified_after_run':slot not in prep_clock_gaps})
        empty=work/'empty-assets';empty.mkdir()
        missing=run([harness,plugin,empty,stimulus,work/'missing-renders','missing'],env=env,check=False)
        if missing.returncode or 'MISSING_PASS' not in missing.stdout:raise RuntimeError('packaged VST missing-package silence test failed:\n'+missing.stdout+'\n'+missing.stderr)
        wav=work/'host-sim.wav'
        host=run([hostsim,plugin,'test','--seconds','1','--sr','48000','--block','256','--seed','5510','--wav',wav],env=env,check=False)
        (work/'sdk-host-sim.log').write_text(host.stdout+'\n'+host.stderr)
        if host.returncode or 'FAIL' in host.stdout:raise RuntimeError('official SDK host simulator rejected the packaged native VST:\n'+host.stdout+'\n'+host.stderr)
        if not wav.is_file():raise RuntimeError('SDK host simulator produced no test WAV')
        index_hash=sha(assets/'provider-index.tsv')
        report={'schema':'trollfx-force-dsp-integration-report-v1','status':'PASS','engine_id':'native-es5510-factory-runtime-v0.1',
          'mock_backend':False,'binary_bound_native_vst':True,'native_binary_sha256':sha(plugin),'arm32_binary_sha256':sha(arm),
          'test_command':'force_plugin/tools/test_packaged_vst.py','input_sha256':input_hash,'output_sha256':output_hash.hexdigest(),
          'asset_index_sha256':index_hash,'asset_collection_slots':audit_result['eligible_slots'],'verified_slots':list(range(1,51)),
          'plugin_parameter_count':46,
          'verified_factory_parameter_points':19,
          'processed_dsp_frames':50*8192,'non_silent_output_frames':non_silent,'callback_allocations':0,
          'passed_tests':['factory_processing','effect_switching','no_mock_fallback','initialization_validation','stereo_routing',
            'verified_factory_parameter_points','all_19_v4_controls_both_verified_points','missing_package_silence','state_roundtrip_including_v4_parameter','sdk_host_simulator'],
          'slot_results':slot_results,'switch_contract':{'fade_out_frames_at_48k':240,'fade_in_frames_at_48k':240,
            'measured_selection_to_ready_frames_are_including_worker_preparation':True},
          'sdk_host_simulator':{'result':'PASS','wav_sha256':sha(wav)},
          'clock_evidence_gaps':prep_clock_gaps}
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':'PASS','binary_bound_native_vst':True,'slots':50,'missing_package_silence':'PASS',
      'sdk_host_simulator':'PASS','callback_allocations':0,'native_sha256':report['native_binary_sha256'],
      'arm32_sha256':report['arm32_binary_sha256'],'report':str(a.report)},indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,KeyError,TypeError,json.JSONDecodeError) as e:
        print(f'test_packaged_vst: ERROR: {e}',file=sys.stderr);raise SystemExit(2)
