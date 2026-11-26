#!/usr/bin/env python3
"""Render controlled HALL decay comparisons from private validated ROM-01 assets.

All WAV outputs and temporary seeded checkpoints are written outside the repo.
The report and SVG envelope plots contain measurements and hashes only.
"""
from __future__ import annotations
import argparse, hashlib, json, math, shutil, struct, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HOME=Path.home()
RUNTIME=HOME/'worktrees/asr10-hall-decay-audit-6779dc8'
BOOT=HOME/'research/private-results/asr10-hall-reference-capture-v2-20261124/boot-a'
SWEEPS=HOME/'research/private-results/asr10-v4-gui-independent/hall-decay-recheck-20261125'
AUDIT=HOME/'research/private-results/asr10-all-50-effects/production-provider-audit.json'
PRIVATE_OUT=HOME/'research/private-results/asr10-v4-gui-independent/hall-extreme-range-20261126'
ORDER=('0x6e','0x5b','0x03','0x04','0x05')
DISPLAY_RAW={10:13,90:115,0:0,99:127,25:32,75:96,40:51,41:53}
RAW_VALUES=(0,13,32,51,52,53,96,115,116,127)
PAIRS={'display_10_vs_90':(13,115),'display_0_vs_99':(0,127),'display_25_vs_75':(32,96),
       'display_40_vs_41':(51,53),'raw_51_vs_52':(51,52),'same_raw_51_vs_51':(51,51)}

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def group(step):
    writes=step.get('register_writes',[])
    found=None
    for i in range(len(writes)-4):
        part=writes[i:i+5]
        if tuple(x.get('gpr','').lower() for x in part)==ORDER:
            found=tuple(int(x['value24'],16) for x in part)
    return found

def parse_sweep(path):
    doc=json.loads(path.read_text()); maps={'up':{},'down':{}}
    for step in doc['steps']:
        if not step.get('complete'):continue
        text=step.get('to_display',''); import re
        m=re.search(r'DECAY TIME\s*=\s*(\d+)',text)
        g=group(step)
        if not m or g is None:continue
        direction=step.get('direction')
        if direction not in maps:direction={'to_max':'up','restore':'up','to_min':'down','to_origin':'down'}.get(step.get('segment'))
        if direction in maps:maps[direction][int(m.group(1))]=g
    return maps

def get_float_wav(path:Path):
    b=path.read_bytes()
    if b[:4]!=b'RIFF' or b[8:12]!=b'WAVE' or b[20:22]!=b'\x03\x00' or b[22:24]!=b'\x02\x00' or b[34:36]!=b'\x20\x00':
        raise RuntimeError(f'{path.name} is not stereo IEEE-float32 WAV')
    rate=struct.unpack_from('<I',b,24)[0]; frames=struct.unpack_from('<I',b,40)[0]//8
    vals=struct.unpack_from('<'+'f'*(frames*2),b,44)
    return rate,frames,vals

def _f32(x:float)->float:return struct.unpack('<f',struct.pack('<f',x))[0]
def stimulus_sha(kind:str,frames:int,rate:float)->str:
    h=hashlib.sha256();burst=round(rate*.5);seed=0x5eed5510
    for n in range(frames):
        if kind=='impulse':left,right=(.75,.42) if n==0 else (0.0,0.0)
        elif n>=burst:left=right=0.0
        else:
            l=(seed+n*2+1)&0xffffffff;r=(seed+n*2+2)&0xffffffff
            def xs(x):
                x^=(x<<13)&0xffffffff;x&=0xffffffff;x^=x>>17;x&=0xffffffff;x^=(x<<5)&0xffffffff;return x&0xffffffff
            left=_f32(_f32(_f32(xs(l)&0xffffff)/_f32(8388607.5))-1.0);right=_f32(_f32(_f32(xs(r)&0xffffff)/_f32(8388607.5))-1.0)
            left=_f32(left*_f32(.12));right=_f32(right*_f32(.12))
        h.update(struct.pack('<ff',_f32(left),_f32(right)))
    return h.hexdigest()

def svg_plot(report,rate_mode,stimulus,path):
    runs=[x for x in report['runs'] if x['rate_mode']==rate_mode and x['stimulus']==stimulus and not x.get('repeat')]
    colors=['#005f73','#0a9396','#94d2bd','#ca6702','#bb3e03','#ae2012','#9b2226','#5a189a','#3c096c','#212529']
    w,h=1180,770; left,top,right,bottom=92,72,1000,665
    vals=[v for x in runs for v in x['rms_100ms'] if v>0]
    lo=max(-160,20*math.log10(min(vals)) if vals else -120);hi=max(0,20*math.log10(max(vals)) if vals else 0)
    if hi-lo<10:lo=hi-10
    def y(db):return bottom-(db-lo)/(hi-lo)*(bottom-top)
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
      '<rect width="100%" height="100%" fill="#fff"/>',f'<text x="{w/2}" y="32" text-anchor="middle" font-family="sans-serif" font-size="22" font-weight="bold">HALL {stimulus.replace("_"," ")} — {rate_mode}</text>',
      f'<text x="{w/2}" y="58" text-anchor="middle" font-family="sans-serif" font-size="14">100 ms RMS envelope; no normalization; y = 20 log10(native RMS)</text>']
    for db in range(int(math.floor(lo/20)*20),int(math.ceil(hi/20)*20)+1,20):
        yy=y(db);parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="#ddd"/>');parts.append(f'<text x="{left-10}" y="{yy+5:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{db} dB</text>')
    duration=runs[0]['frames']/runs[0]['rate_hz'] if runs else 10
    for sec in range(0,int(math.ceil(duration))+1,1):
        xx=left+sec/duration*(right-left);parts.append(f'<line x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{bottom}" stroke="#eee"/>');parts.append(f'<text x="{xx:.1f}" y="{bottom+22}" text-anchor="middle" font-family="sans-serif" font-size="12">{sec}</text>')
    for idx,r in enumerate(sorted(runs,key=lambda x:x['raw'])):
        pts=[]
        for i,v in enumerate(r['rms_100ms']):
            sec=i*.1+.05; xx=left+sec/duration*(right-left); yy=y(20*math.log10(max(v,1e-8)));pts.append(f'{xx:.1f},{yy:.1f}')
        parts.append(f'<polyline fill="none" stroke="{colors[idx%len(colors)]}" stroke-width="1.8" points="{" ".join(pts)}"/>')
        ly=top+18+idx*22;parts.append(f'<line x1="{right+25}" y1="{ly-5}" x2="{right+48}" y2="{ly-5}" stroke="{colors[idx%len(colors)]}" stroke-width="3"/>');parts.append(f'<text x="{right+56}" y="{ly}" font-family="sans-serif" font-size="13">raw {r["raw"]}</text>')
    parts += [f'<text x="{(left+right)/2}" y="{h-25}" text-anchor="middle" font-family="sans-serif" font-size="15">Time from stimulus start (seconds)</text>',f'<text transform="translate(24 {(top+bottom)/2}) rotate(-90)" text-anchor="middle" font-family="sans-serif" font-size="15">Output RMS, dB re 1.0</text>','</svg>']
    path.write_text('\n'.join(parts)+'\n')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime-root',type=Path,default=RUNTIME);ap.add_argument('--reference-boot',type=Path,default=BOOT)
    ap.add_argument('--sweeps-root',type=Path,default=SWEEPS);ap.add_argument('--provider-audit',type=Path,default=AUDIT)
    ap.add_argument('--private-output',type=Path,default=PRIVATE_OUT);ap.add_argument('--report',type=Path,default=ROOT/'docs/qa-v4/ASR10_HALL_EXTREME_RANGE_AUDIO_QA_V1.json')
    ap.add_argument('--plots-dir',type=Path,default=ROOT/'docs/qa-v4/plots');ap.add_argument('--seconds',type=float,default=10.0);ap.add_argument('--cxx',default='g++');a=ap.parse_args()
    runtime=a.runtime_root.resolve(strict=True);boot=a.reference_boot.resolve(strict=True);checkpoint=boot/'snapshots/run-frame-855973.esp'
    meta=json.loads((boot/'capture-metadata.json').read_text());audit=json.loads(a.provider_audit.resolve(strict=True).read_text());row=next(x for x in audit['slots'] if int(x['slot'])==1);d=row['descriptor']
    if not row['registry_eligible'] or not row['capture_state_valid'] or not row['checkpoint_is_at_run_boundary']:raise SystemExit('HALL package audit gate failed')
    if sha(checkpoint)!=d['run_checkpoint_sha256'] or d['program_sha256']!=meta['initial_state']['program']['active_program_sha256']:raise SystemExit('checkpoint/program provenance mismatch')
    if meta['effect']!='ROM-01 HALL REVERB' or meta['os_version']!='3.53':raise SystemExit('reference is not OS 3.53 HALL')
    sched=Path(d['firmware_event_schedule_path']).resolve(strict=True)
    if sha(sched)!=d['firmware_event_schedule_sha256']:raise SystemExit('firmware schedule checksum mismatch')
    maps=[parse_sweep((a.sweeps_root/bootname/'slot-01-var1-decay-time-range.json').resolve(strict=True)) for bootname in ('boot-a','boot-b')]
    for disp,raw in DISPLAY_RAW.items():
        direction='down' if disp==0 else 'up'
        got=[(maps[0][direction].get(disp),maps[1][direction].get(disp))]
        if any(x is None for x in got[0]) or got[0][0]!=got[0][1] or ((got[0][0][0]>>16)&127)!=raw:raise SystemExit(f'OS raw/display evidence mismatch for display {disp} raw {raw}')
    if maps[0]['up'].get(40) is None or maps[0]['down'].get(40) is None or ((maps[0]['up'][40][0]>>16)&127)!=51 or ((maps[0]['down'][40][0]>>16)&127)!=52:raise SystemExit('duplicate display 40 evidence changed')
    groups={}
    for direction in ('up','down'):
        for g in maps[0][direction].values():groups[(g[0]>>16)&127]=g
    if set(groups)!=set(range(128)):raise SystemExit('OS-derived register table lacks raw codes')
    a.private_output.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True);a.plots_dir.mkdir(parents=True,exist_ok=True)
    group_file=a.private_output/'os-derived-registers-private.csv'
    group_file.write_text(''.join(f'{raw},'+','.join(f'{v:06x}' for v in groups[raw])+'\n' for raw in range(128)))
    with tempfile.TemporaryDirectory(prefix='hall-extreme-audio-') as td:
        tmp=Path(td);include=tmp/'include';src=tmp/'src';shutil.copytree(runtime/'include',include);src.mkdir()
        for name in ('es5510_factory_runtime.cpp','es5510.cpp','es5510.h','es5510_capture.h'):shutil.copy2(runtime/'src'/name,src/name)
        header=include/'trollfx/es5510_factory_runtime.hpp';t=header.read_text();marker='    RuntimeStatus getStatus() const noexcept;'
        if t.count(marker)!=1:raise SystemExit('runtime API marker changed')
        header.write_text(t.replace(marker,marker+'\n    std::uint32_t qaReadRegister(std::uint8_t index) const noexcept;'))
        cpp=src/'es5510_factory_runtime.cpp';t=cpp.read_text();marker='} // namespace trollfx::es5510'
        if t.count(marker)!=1:raise SystemExit('runtime implementation marker changed')
        cpp.write_text(t.replace(marker,'std::uint32_t FactoryRuntime::qaReadRegister(std::uint8_t index) const noexcept { return impl_->dsp.register_value(index); }\n'+marker))
        binary=tmp/'hall-extreme-audio'
        cmd=[a.cxx,'-std=c++17','-O2','-Wall','-Wextra','-Wpedantic','-DTROLLFX_QA_REGISTER_ACCESS','-I'+str(include),'-I'+str(src),str(ROOT/'tests/force_gui_qa/test_hall_extreme_range_audio.cpp'),str(cpp),str(src/'es5510.cpp'),'-o',str(binary)]
        build=subprocess.run(cmd,capture_output=True,text=True)
        if build.returncode:raise SystemExit('native build failed:\n'+build.stderr[-4000:])
        run=subprocess.run([str(binary),str(checkpoint),str(group_file),str(a.private_output),str(sched),d['program_sha256'],d['run_checkpoint_sha256'],str(a.seconds)],capture_output=True,text=True)
        if run.returncode:raise SystemExit('native render failed:\n'+run.stderr[-3000:])
        raw_report=json.loads(run.stdout)
    run_index={}
    for item in raw_report['runs']:
        wav=a.private_output/item['wav'];rate,frames,vals=get_float_wav(wav)
        if frames!=item['frames'] or len(vals)!=frames*2:raise SystemExit(f'WAV frame count mismatch: {wav.name}')
        if item['finite_samples']!=frames*2:raise SystemExit(f'non-finite WAV output count: {wav.name}')
        if item['schedule_writes_applied']!=raw_report['schedule_events'] or item['writes_after_edit']!=raw_report['schedule_events']+5:raise SystemExit(f'firmware/parameter write count mismatch: {wav.name}')
        item['wav_sha256']=sha(wav);item['wav_header_rate_hz']=rate;item['late_tail_rms_8_10s']=math.sqrt(sum(x*x for x in item['rms_100ms'][80:100])/max(1,len(item['rms_100ms'][80:100])))
        item['window_energy_100ms']=[v*v*.1 for v in item['rms_100ms']]
        key=(item['rate_mode'],item['stimulus'],item['raw'],bool(item.get('repeat')));run_index[key]=(item,vals)
    initial_states={tuple(x['registers_before_edit']) for x in raw_report['runs'] if 'registers_before_edit' in x}
    if len(initial_states)!=1:raise SystemExit('fresh loads did not begin from identical post-schedule register state')
    for item in raw_report['runs']:
        if item['registers_after_render']!=item['registers_before_render']:raise SystemExit('parameter GPR state changed during output render')
    pair_rows=[]
    for rate_mode in ('FactoryReference','Experimental48000'):
      for stimulus in ('impulse','noise_burst'):
       for name,(left_raw,right_raw) in PAIRS.items():
        left=run_index[(rate_mode,stimulus,left_raw,False)][1]
        right=run_index[(rate_mode,stimulus,right_raw,True if name=='same_raw_51_vs_51' else False)][1]
        if len(left)!=len(right):raise SystemExit('comparison pair length mismatch')
        ds=[float(x)-float(y) for x,y in zip(left,right)];diff_rms=math.sqrt(sum(x*x for x in ds)/len(ds));diff_peak=max(abs(x) for x in ds)
        pair_rows.append({'rate_mode':rate_mode,'stimulus':stimulus,'comparison':name,'raw_left':left_raw,'raw_right':right_raw,'difference_rms':diff_rms,'difference_peak':diff_peak,'bit_identical':all(x==y for x,y in zip(left,right))})
    for rate_mode in ('FactoryReference','Experimental48000'):
      for stimulus in ('impulse','noise_burst'):
       primary=run_index[(rate_mode,stimulus,51,False)][1];repeat=run_index[(rate_mode,stimulus,51,True)][1]
       if primary!=repeat:raise SystemExit(f'fresh-run repeatability failed for {rate_mode}/{stimulus}/raw51')
    report={'schema':'trollfx-asr10-hall-extreme-range-audio-qa-v1','provenance':{'qa_branch_base':'27cb9a25ad0eac006a4ec891bebe4b207f5b2be1','runtime_source_commit':subprocess.check_output(['git','-C',str(runtime),'rev-parse','HEAD'],text=True).strip(),'reference_effect':'ROM-01 HALL REVERB','os_version':'3.53','checkpoint_sha256':d['run_checkpoint_sha256'],'active_program_sha256':d['program_sha256'],'firmware_schedule_sha256':sha(sched),'os_boot_a_trace_sha256':sha((a.sweeps_root/'boot-a/slot-01-var1-decay-time-range.json')),'os_boot_b_trace_sha256':sha((a.sweeps_root/'boot-b/slot-01-var1-decay-time-range.json')),'register_order':['0x6e','0x5b','0x03','0x04','0x05'],'factory_clock_hz':meta['dsp_rate_hz'],'routing':d['routing']},
      'method':{'duration_seconds':a.seconds,'same_authenticated_RUN_checkpoint_each_run':True,'explicit_runtime_reset_each_run':True,'same_completed_firmware_schedule_each_run':True,'schedule_event_count':raw_report['schedule_events'],'last_schedule_frame':raw_report['last_schedule_frame'],'schedule_settle_frames':raw_report['last_schedule_frame']+2,'test_only_OS_group_application':True,'input_gain':1.0,'output_gain':1.0,'normalization':'none','float_wav':'IEEE float32 stereo; integer WAV header rate rounds factory clock to 29762 Hz; exact DSP clock retained in metadata','input':{'impulse':'stereo one-frame impulse L=0.75 R=0.42','noise_burst':{'duration_seconds':0.5,'algorithm':'xorshift32 per frame/lane','seed_hex':f'0x{0x5eed5510:08x}','amplitude_peak_below':0.12},'per_rate_sha256':{mode:{kind:stimulus_sha(kind,round(rate*a.seconds),rate) for kind in ('impulse','noise_burst')} for mode,rate in [('FactoryReference',29761.89453125),('Experimental48000',48000.0)]}},'selected_display_raw':{'display 10':{'raw':13,'selection':'up route; unique'},'display 90':{'raw':115,'selection':'up route; duplicate display also has raw 116 on down route'},'display 0':{'raw':0,'selection':'down endpoint'},'display 99':{'raw':127,'selection':'up endpoint'},'display 25':{'raw':32,'selection':'up route; unique'},'display 75':{'raw':96,'selection':'up route; unique'},'display 40':{'raw':51,'selection':'up/lower raw representation; raw 52 is retained on the down route'},'display 41':{'raw':53,'selection':'up route; unique'}},'comparison_pairs':PAIRS},
      'runs':raw_report['runs'],'comparisons':pair_rows,'repeatability':'PASS_EXACT_RAW51_OUTPUTS_FOR_BOTH_STIMULI_AND_RATES','physical_hardware':'NOT_TESTED','exact_factory_audio_equivalence':'NOT_TESTED'}
    report['verification']={'all_44_renders_finite':all(x['finite_samples']==x['frames']*2 for x in report['runs']),
      'all_runs_completed_213_startup_events':all(x['schedule_writes_applied']==raw_report['schedule_events'] for x in report['runs']),
      'identical_post_schedule_initial_register_state':len(initial_states)==1,
      'five_selected_gprs_stable_during_render':all(x['registers_after_render']==x['registers_before_render'] for x in report['runs'] if 'registers_before_render' in x),
      'same_raw_51_pairs_bit_exact':all(x['bit_identical'] for x in pair_rows if x['comparison']=='same_raw_51_vs_51'),
      'no_normalization':True}
    for item in report['runs']:item.pop('wav',None)
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    for mode in ('FactoryReference','Experimental48000'):
      for stim in ('impulse','noise_burst'):
       svg_plot(report,mode,stim,a.plots_dir/f'ASR10_HALL_{mode}_{stim}_envelope.svg')
    print(json.dumps({'report':str(a.report),'plot_files':[str(a.plots_dir/f'ASR10_HALL_{m}_{s}_envelope.svg') for m in ('FactoryReference','Experimental48000') for s in ('impulse','noise_burst')],'private_wav_count':len(list(a.private_output.glob('*.wav'))),'comparison_count':len(pair_rows),'repeatability':report['repeatability']},indent=2))
if __name__=='__main__':main()
