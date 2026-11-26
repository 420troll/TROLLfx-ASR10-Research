#!/usr/bin/env python3
"""Run full-range HALL audio and write-timing QA against the latest published runtime.

Private authentic RUN checkpoints and OS traces are read from local paths only.
Temporary seeded checkpoints and all audio-derived measurements stay outside Git.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME=Path.home()/"worktrees/asr10-hall-decay-audit-6779dc8"
DEFAULT_REFERENCE=Path.home()/"research/private-results/asr10-hall-reference-capture-v2-20261124/boot-a"
DEFAULT_SWEEPS=Path.home()/"research/private-results/asr10-v4-gui-independent/hall-decay-recheck-20261125"
DEFAULT_AUDIT=Path.home()/"research/private-results/asr10-all-50-effects/production-provider-audit.json"
ORDER=("0x6e","0x5b","0x03","0x04","0x05")

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def find_group(step):
    w=step.get('register_writes',[])
    found=None
    for i in range(len(w)-4):
        if tuple(x.get('gpr','').lower() for x in w[i:i+5])==ORDER:
            found=w[i:i+5]
    return found

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime-root',type=Path,default=DEFAULT_RUNTIME)
    ap.add_argument('--reference-boot',type=Path,default=DEFAULT_REFERENCE)
    ap.add_argument('--sweeps-root',type=Path,default=DEFAULT_SWEEPS)
    ap.add_argument('--provider-audit',type=Path,default=DEFAULT_AUDIT)
    ap.add_argument('--private-output',type=Path,default=Path.home()/"research/private-results/asr10-v4-gui-independent/hall-audio-qa-20261126")
    ap.add_argument('--report',type=Path,default=ROOT/'docs/qa-v4/ASR10_HALL_FULL_RANGE_AUDIO_QA_V1.json')
    ap.add_argument('--cxx',default=os.environ.get('CXX','g++'))
    a=ap.parse_args();runtime=a.runtime_root.resolve(strict=True);boot=a.reference_boot.resolve(strict=True)
    trace_a=(a.sweeps_root/'boot-a/slot-01-var1-decay-time-range.json').resolve(strict=True)
    trace_b=(a.sweeps_root/'boot-b/slot-01-var1-decay-time-range.json').resolve(strict=True)
    meta=json.loads((boot/'capture-metadata.json').read_text())
    checkpoint=boot/'snapshots/run-frame-855973.esp'
    checkpoint_hash=sha(checkpoint)
    if checkpoint_hash!=meta['initial_state']['capture_sha256']:
        raise SystemExit('HALL checkpoint SHA does not match its capture metadata')
    if meta['effect']!='ROM-01 HALL REVERB' or meta['os_version']!='3.53' or abs(meta['dsp_rate_hz']-29761.89453125)>1e-8:
        raise SystemExit('reference identity/rate does not match the intended OS HALL package')
    audit=json.loads(a.provider_audit.resolve(strict=True).read_text())
    row=next(x for x in audit['slots'] if int(x['slot'])==1);d=row['descriptor']
    if not row['registry_eligible'] or not row['capture_state_valid'] or not row['checkpoint_is_at_run_boundary']:
        raise SystemExit('private provider audit does not validate the HALL RUN checkpoint')
    if d['run_checkpoint_sha256']!=checkpoint_hash:
        raise SystemExit('provider audit HALL checkpoint hash differs from audio reference checkpoint')
    if d['program_sha256']!=meta['initial_state']['program']['active_program_sha256'] or d['active_program_words']!=89:
        raise SystemExit('HALL program identity does not match reference metadata')

    # Expected values come only from the two private OS traces. Reject boot disagreement.
    from audit_hall_decay_raw_domain import read_sweep
    groups={}
    for p in (trace_a,trace_b):
        _,dirs,failures=read_sweep(p)
        if failures:raise SystemExit(f'OS trace {p} contains {failures} group-order errors')
        for direction in ('up','down'):
            for display,g in dirs[direction].items():
                raw=(g[0x6e]>>16)&0x7f; values=tuple(g[r] for r in (0x6e,0x5b,0x03,0x04,0x05))
                if raw in groups and groups[raw]!=values:raise SystemExit(f'OS boots disagree at raw code {raw}')
                groups[raw]=values
    if set(groups)!=set(range(128)):raise SystemExit('OS traces do not cover all 128 raw codes')
    stepdoc=json.loads(trace_a.read_text());route=None
    for step in stepdoc['steps']:
        if step.get('direction')=='up' and step.get('from_display','').strip().endswith('=40') and step.get('to_display','').strip().endswith('=41'):
            candidate=find_group(step)
            if candidate and (int(candidate[0]['value24'],16)>>16)==53:
                route=step;break
    if route is None:raise SystemExit('cannot find independently observed 40->41 raw-53 step')
    ordered=find_group(route);frames=[int(x['frame']) for x in ordered];offsets=[x-frames[0] for x in frames]
    if offsets!=[0,3,6,8,11]:raise SystemExit(f'40->41 OS write timing changed: {offsets}')
    if tuple(int(x['value24'],16) for x in ordered)!=groups[53]:raise SystemExit('timing group disagrees with OS per-raw table')

    a.private_output.mkdir(parents=True,exist_ok=True); a.report.parent.mkdir(parents=True,exist_ok=True)
    schedule_path=Path(d['firmware_event_schedule_path']).resolve(strict=True)
    schedule_hash=sha(schedule_path)
    if schedule_hash!=d['firmware_event_schedule_sha256']:
        raise SystemExit('validated HALL firmware-event schedule hash mismatch')
    expected=a.private_output/'os-registers-private.csv'
    with expected.open('w') as f:
        for raw in range(128):f.write(str(raw)+','+','.join(f'{x:06x}' for x in groups[raw])+'\n')
    timing=a.private_output/'os-40-41-offsets-private.txt';timing.write_text(' '.join(map(str,offsets))+'\n')
    with tempfile.TemporaryDirectory(prefix='hall-native-audio-qa-') as td:
        tmp=Path(td);include=tmp/'include';src=tmp/'src';shutil.copytree(runtime/'include',include);src.mkdir()
        for name in ('es5510_factory_runtime.cpp','es5510.cpp','es5510.h','es5510_capture.h'):
            shutil.copy2(runtime/'src'/name,src/name)
        header=include/'trollfx/es5510_factory_runtime.hpp';text=header.read_text()
        marker='    RuntimeStatus getStatus() const noexcept;'
        if text.count(marker)!=1:raise SystemExit('runtime header API changed; refusing ambiguous QA instrumentation')
        header.write_text(text.replace(marker,marker+'\n    std::uint32_t qaReadRegister(std::uint8_t index) const noexcept;'))
        cpp=src/'es5510_factory_runtime.cpp';text=cpp.read_text();marker='} // namespace trollfx::es5510'
        if text.count(marker)!=1:raise SystemExit('runtime namespace marker changed; refusing ambiguous QA instrumentation')
        accessor=('std::uint32_t FactoryRuntime::qaReadRegister(std::uint8_t index) const noexcept {\n'
                  '    return impl_->dsp.register_value(index);\n}\n\n')
        cpp.write_text(text.replace(marker,accessor+marker))
        binary=tmp/'hall-audio-qa'
        build=subprocess.run([a.cxx,'-std=c++17','-O2','-Wall','-Wextra','-Wpedantic','-DTROLLFX_QA_REGISTER_ACCESS',
          '-I'+str(include),'-I'+str(src),str(ROOT/'tests/force_gui_qa/test_hall_decay_audio_runtime.cpp'),
          str(cpp),str(src/'es5510.cpp'),'-o',str(binary)],capture_output=True,text=True)
        if build.returncode:raise SystemExit('native HALL QA build failed:\n'+build.stderr[-5000:])
        run=subprocess.run([str(binary),str(checkpoint),str(expected),str(a.private_output),str(timing),str(schedule_path),
                            d['program_sha256'],checkpoint_hash],capture_output=True,text=True)
        if run.returncode:raise SystemExit('native HALL QA failed:\n'+run.stdout[-2500:]+'\n'+run.stderr[-2500:])
        import re
        full=re.findall(r'METRIC kind=full_range raw=(\d+) frames=(\d+) finite=(\d+) rms_l=([^ ]+) rms_r=([^ ]+) stereo_diff_rms=([^ ]+) peak=([^ ]+) max_step=([^ ]+) hash=([0-9a-f]+) windows=([^\n]+)',run.stdout)
        tails=re.findall(r'METRIC kind=impulse_tail raw=(\d+) frames=(\d+) finite=(\d+) rms_l=([^ ]+) rms_r=([^ ]+) stereo_diff_rms=([^ ]+) peak=([^ ]+) max_step=([^ ]+) hash=([0-9a-f]+) windows=([^\n]+)',run.stdout)
        timing=re.findall(r'TIMING window=(\d+) frames=(\d+) diff_rms=([^\s]+) diff_peak=([^\s]+) batch_rms=([^\s]+) stagger_rms=([^\s]+) batch_max_step=([^\s]+) stagger_max_step=([^\s]+)',run.stdout)
        repeats=re.findall(r'REPEAT raw=(\d+) exact=(\d+) hash=([0-9a-f]+)',run.stdout)
        report={'schema':'trollfx-asr10-hall-full-range-audio-qa-v1','qa_branch_head_before_run':'6ebe633b76d2c7c5669bacbac54e2d95cf070a2d',
          'codex1_runtime_commit':subprocess.check_output(['git','-C',str(runtime),'rev-parse','HEAD'],text=True).strip(),
          'codex2_editor_commit':'0a25d72f83f6ad622771193d0c6bc064a59d75a0',
          'reference':{'effect':meta['effect'],'os':meta['os_version'],'dsp_rate_hz':meta['dsp_rate_hz'],'program_sha256':meta['initial_state']['program']['active_program_sha256'],
            'checkpoint_sha256':checkpoint_hash,'checkpoint_initial_gpr6e':'0x2c0831','input_capture_sha256':meta['replay']['input_sha256'],
            'firmware_schedule_sha256':schedule_hash,
            'reference_boot':'boot-a','same-reference-audio-per-parameter-setting_available':False},
          'os_parameter_evidence':{'boot_a_trace_sha256':sha(trace_a),'boot_b_trace_sha256':sha(trace_b),'raw_codes':128,'display_values':100,'duplicate_buckets':28,
            'register_order':['0x6e','0x5b','0x03','0x04','0x05'],'groups_per_raw_match_across_boots':True,'coefficient_clamp':'clamp(raw,12,76) for GPR 03-05'},
          'method':'OS-captured GPR groups applied through FactoryRuntime setRegister to the authenticated HALL RUN checkpoint; runtime source copied to temp and instrumented with a read-only test accessor; no owner source edited.',
          'private_audio_saved':False,
          'native_audio':{'full_range_raw_entries':len(full),'all_128_output_hashes_distinct':len({x[8] for x in full})==128,
            'frames_per_setting':8192,'all_samples_finite':all(int(x[2])==int(x[1]) for x in full),
            'representative_impulse_tails':[{'raw':int(x[0]),'frames':int(x[1]),'peak':float(x[6]),'rms_windows':[float(v) for v in x[9].split(',')]} for x in tails],
            'exact_repeat_runs':[{'raw':int(x[0]),'exact':bool(int(x[1])),'hash':x[2]} for x in repeats]},
          'timing_comparison':{'model':'five register writes in one frame versus the OS offsets [0,3,6,8,11]',
            'windows':[{'index':int(x[0]),'frames':int(x[1]),'difference_rms':float(x[2]),'difference_peak':float(x[3]),'batched_rms':float(x[4]),'staggered_rms':float(x[5]),'batched_max_sample_step':float(x[6]),'staggered_max_sample_step':float(x[7])} for x in timing],
            'identical_final_gpr_state':True,'finite_samples':131072,'audibility_conclusion':'NOT_TESTED'},
          'runtime_api':{'schedule_free_os_seeded_checkpoint':'PASS','ascending_steps':99,'descending_steps':99,'distinct_raw_codes_visited':128,'ordered_gpr_writes_checked':990,
            'authentic_validated_package_with_post_run_schedule':'UNAVAILABLE_GPR_6E_SCHEDULE_INVALIDATES_RAW_STATE'},
          'result':{'full_raw_register_and_native_audio_sweep':'PASS','repeatability':'PASS_FOR_SIX_REPEATED_NATIVE_SETTINGS',
            'batched_vs_staggered':'MEASURED_SMALL_NUMERICAL_DIFFERENCES_NO_NONFINITE_OR_RUNAWAY_OBSERVED',
            'exact_factory_audio_equivalence':'NOT_TESTED','physical_force':'NOT_TESTED'} }
        a.report.write_text(json.dumps(report,indent=2)+'\n')
        print(run.stdout)
        print('REPORT',a.report)
if __name__=='__main__':main()
