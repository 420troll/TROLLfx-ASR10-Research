#!/usr/bin/env python3
"""Capture a factory effect at an experimental OTTO/ESP rate.

This is explicitly an emulator override experiment, not a claim about supported
silicon operation. ROMs, logs, checkpoints, WAVs and serial samples stay private.
"""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys, wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools')); sys.path.insert(0,str(ROOT/'tools/audio_validation'))
import capture_asr10_rom_effects as capture
from esp_capture import read_capture
from factory_replay_profiles import PROFILES
from clock_experiment import extract_serial, measure_log, serial_metrics

SUMMARY=re.compile(r"ESPPHASE kind=program_upload_summary .*commits=(\d+) unique_addresses=(\d+) first_end=(-?\d+) gpr_commits=(\d+)")
RUN=re.compile(r"ESPPHASE kind=run_start frame=(\d+) cycles=(\d+)")
DISPLAY=re.compile(r"ESP_ROM_SELECT id=(\d+).*display=(.*)$")


def target_frame(log:Path,profile:dict)->int:
    selected=False; summary=None
    with log.open(errors='replace') as f:
        for line in f:
            dm=DISPLAY.search(line)
            if dm: selected=(int(dm.group(1))==int(profile['effect_id'].split('-')[1]) and profile['effect_name'] in dm.group(2))
            sm=SUMMARY.search(line)
            if sm: summary=tuple(map(int,sm.groups()))
            rm=RUN.search(line)
            if rm and selected and summary==(profile['instruction_commits'],profile['unique_instruction_addresses'],profile['end_word'],profile['register_commits']):
                return int(rm.group(1))
    raise ValueError('target factory RUN boundary was not observed')


def one_boot(cli,roms,disk,root,boot,profile_name,rate,voice_slots,impulse,frame_sine,frames,tail_seconds):
    profile=PROFILES[profile_name]; d=root/f'boot-{boot}'; d.mkdir(); (d/'snapshots').mkdir()
    args=['--panel-log','--trace-esp-io','--wav',str(d/'render.wav'),'--button','15:7:1','--button','15.2:7:0']
    t=16.0
    for raw in range(8,int(profile['selector_raw_last'])+1):
        args += ['--analog-at',f'{t:.3f}:5:{raw}']; t+=0.15
    env=capture.emulator_env()
    env.update({'ESP_PIPELOG':'1','ESP_HOSTLOG':'1','ESP_FRAMELOG':str(frames),'ESP_RUN_SNAPSHOT_DIR':str(d/'snapshots'),
                'ESP_EXPERIMENT_CAPTURE_ROM_ID':profile['effect_id'].split('-')[1],
                'ESP_EXPERIMENT_CAPTURE_WORDS':str(profile['active_words']),
                'ASR_OTTO_CLOCK_TRACE':'1'})
    if rate: env['ASR_EXPERIMENT_DSP_RATE_HZ']=str(rate)
    if voice_slots: env['ASR_EXPERIMENT_VOICE_SLOTS']=str(voice_slots)
    if impulse: env['ASR_EXPERIMENT_RUN_IMPULSE']='1'
    if frame_sine: env['ASR_EXPERIMENT_SINE_FRAMES']=frame_sine
    capture.run(cli,roms,disk,t+tail_seconds,args,env,d/'session.log')
    frame=target_frame(d/'session.log',profile)
    snap=d/'snapshots'/f'run-frame-{frame}.esp'
    cap=read_capture(snap)
    if cap['program']['active_words_through_first_END']!=profile['active_words']:
        raise ValueError('RUN checkpoint active program length mismatch')
    if cap['runtime']['control']['halted'] or cap['runtime']['control']['pc']!=0:
        raise ValueError('target checkpoint is not the pre-instruction RUN boundary')
    serial=extract_serial(d/'session.log',frame,frames,d/'dsp-serial-output.csv')
    if serial['frames_written']!=frames: raise ValueError('target direct serial trace is incomplete')
    clock=measure_log(d/'session.log',frame)
    if not clock['measured_rate_hz']: raise ValueError('cannot measure CPU-cycle/frame clock')
    with wave.open(str(d/'render.wav'),'rb') as w:
        host={'rate_hz':w.getframerate(),'channels':w.getnchannels(),'frames':w.getnframes()}
    metrics=serial_metrics(d/'dsp-serial-output.csv',clock['measured_rate_hz'])
    return {'dir':d,'frame':frame,'snapshot':snap,'program_sha256':cap['program']['active_program_sha256'],
            'serial':serial,'clock':clock,'host':host,'metrics':metrics}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('profile',choices=sorted(PROFILES)); p.add_argument('--roms',required=True,type=Path); p.add_argument('--disk',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path); p.add_argument('--cli',required=True,type=Path)
    p.add_argument('--dsp-rate',type=float,help='experimental rate override, e.g. 48000; not an authentic hardware clock')
    p.add_argument('--voice-slots',type=int,help='force supported ES5506 slot count (1..32); 24 slots selects modeled 44.1 kHz clock')
    p.add_argument('--impulse',action='store_true',help='one 0.25-amplitude impulse on selected effect RUN frame, then silence'); p.add_argument('--frame-sine',help='frequency:amplitude:reference-rate; identical per-frame sine sequence across rates'); p.add_argument('--boots',type=int,choices=(1,2),default=2,help='fresh processes to capture'); p.add_argument('--tail-seconds',type=float,default=1.0,help='run duration after final selector change'); p.add_argument('--frames',type=int,default=32768,help='captured DSP frames, 1..131072'); p.add_argument('--baseline-snapshot',type=Path,help='private original-rate RUN checkpoint for active-program/state comparison')
    a=p.parse_args(); out=a.out.expanduser().resolve()
    if out==ROOT or ROOT in out.parents: p.error('private captures must be outside the checkout')
    roms=a.roms.resolve(strict=True); disk=a.disk.resolve(strict=True); cli=a.cli.resolve(strict=True)
    baseline=read_capture(a.baseline_snapshot.resolve(strict=True)) if a.baseline_snapshot else None
    if a.dsp_rate and not 8000<=a.dsp_rate<=192000: p.error('experimental rate is outside 8–192 kHz')
    if a.voice_slots and not 1<=a.voice_slots<=32: p.error('voice slots must be 1..32')
    if not 1<=a.frames<=131072: p.error('frames must be 1..131072')
    out.mkdir(parents=True,exist_ok=False)
    first=one_boot(cli,roms,disk,out,'a',a.profile,a.dsp_rate,a.voice_slots,a.impulse,a.frame_sine,a.frames,a.tail_seconds)
    runs=[first]
    if a.boots==2:
        second=one_boot(cli,roms,disk,out,'b',a.profile,a.dsp_rate,a.voice_slots,a.impulse,a.frame_sine,a.frames,a.tail_seconds); runs.append(second)
        if first['snapshot'].read_bytes()!=second['snapshot'].read_bytes(): raise SystemExit('two experimental RUN checkpoints differ')
        if first['serial']['frames_written']!=second['serial']['frames_written']: raise SystemExit('serial coverage differs')
        if Path(first['serial']['path']).read_bytes()!=Path(second['serial']['path']).read_bytes(): raise SystemExit('direct DSP serial output differs across fresh runs')
        if (first['dir']/'render.wav').read_bytes()!=(second['dir']/'render.wav').read_bytes(): raise SystemExit('host WAV differs across fresh runs')
        if first['clock']['clock_register_writes']!=second['clock']['clock_register_writes']: raise SystemExit('OTTO clock-register histories differ across fresh runs')
        if first['program_sha256']!=second['program_sha256']: raise SystemExit('active program image differs across fresh boots')
    if baseline and first['program_sha256']!=baseline['program']['active_program_sha256']:
        raise SystemExit('active program image changed relative to original-rate baseline')
    for b in runs:
        if b['host']['rate_hz']!=44100 or b['host']['channels']!=2: raise SystemExit('host WAV is not stereo 44.1 kHz')
        expected=a.dsp_rate or (44100.0 if a.voice_slots and a.voice_slots<=24 else PROFILES[a.profile]['dsp_rate_hz'])
        if abs(b['clock']['measured_rate_hz']-expected)>0.2: raise SystemExit('measured CPU-cycle/frame rate differs from requested test condition')
    print(json.dumps({'profile':a.profile,'boot_runs':len(runs),'checkpoint_equal':len(runs)==1 or first['snapshot'].read_bytes()==runs[-1]['snapshot'].read_bytes(),'program_image_equal':len({b['program_sha256'] for b in runs})==1,
      'dsp_rates_hz':[round(b['clock']['measured_rate_hz'],6) for b in runs],
      'host_rate_hz':first['host']['rate_hz'],'frames_per_run':first['serial']['frames_written'],
      'otto_clock_write_count':len(first['clock']['clock_register_writes']),
      'clock_configs_observed':sorted({(w['voice_register'],round(w['otto_clock_hz'],3),round(w['rate_hz'],3)) for w in first['clock']['clock_register_writes']}),
      'impulse_test':a.impulse,'frame_sine_test':a.frame_sine,'voice_slots_override':a.voice_slots,'forced_rate_hz':a.dsp_rate,
      'baseline_program_image_equal':(first['program_sha256']==baseline['program']['active_program_sha256']) if baseline else None,
      'baseline_gpr_image_equal':(read_capture(first['snapshot'])['registers']['gpr_sha256']==baseline['registers']['gpr_sha256']) if baseline else None,
      'baseline_special_register_image_equal':(read_capture(first['snapshot'])['registers']['special_sha256']==baseline['registers']['special_sha256']) if baseline else None,
      'private_output':str(out)},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
