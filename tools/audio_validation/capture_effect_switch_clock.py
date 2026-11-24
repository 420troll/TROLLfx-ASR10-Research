#!/usr/bin/env python3
"""Record ROM-01 -> ROM-02 -> ROM-01 clock transitions in two fresh OS runs."""
from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import capture_asr10_rom_effects as capture
SELECT=re.compile(r"ESP_ROM_SELECT id=(\d+) time=([0-9.]+) cycles=(\d+) frame=(\d+) dsp_rate_hz=([0-9.]+) otto_clock_hz=([0-9.]+) active_voices=(\d+) host_output_rate_hz=([0-9.]+) display=(.*)$")
PHASE=re.compile(r"ESPPHASE kind=([a-z0-9_]+) frame=(\d+) cycles=(\d+)")
WRITE=re.compile(r"OTTO_CLOCK_WRITE cycles=(\d+) frame=(\d+) register=([0-9a-fA-F]+) value=([0-9a-fA-F]+) active_voices=(\d+) otto_clock_hz=([0-9.]+) dsp_rate_hz=([0-9.]+) pc=([0-9a-fA-F]+)")

def make_sequence(raw_last:int,raw_hall:int,raw_rom02:int):
    t=16.0; events=[]
    for raw in range(8,raw_last+1): events += ['--analog-at',f'{t:.3f}:5:{raw}']; t+=0.15
    # Hold ROM-02 long enough to complete its upload and run, then return to HALL.
    t+=5.0; events += ['--analog-at',f'{t:.3f}:5:{raw_hall}']
    return events,t+6.0

def parse(log:Path):
    selections=[]; phases=[]; writes=[]
    with log.open(errors='replace') as f:
        for line in f:
            m=SELECT.search(line)
            if m: selections.append({'id':int(m.group(1)),'time_s':float(m.group(2)),'cycles':int(m.group(3)),'frame':int(m.group(4)),'rate_hz':float(m.group(5)),'otto_hz':float(m.group(6)),'voice_register':int(m.group(7)),'host_rate_hz':float(m.group(8))})
            m=PHASE.search(line)
            if m: phases.append({'kind':m.group(1),'frame':int(m.group(2)),'cycles':int(m.group(3))})
            m=WRITE.search(line)
            if m: writes.append({'cycles':int(m.group(1)),'frame':int(m.group(2)),'voice_register':int(m.group(5)),'otto_hz':float(m.group(6)),'rate_hz':float(m.group(7)),'pc':m.group(8).lower()})
    ids=[]
    for s in selections:
        if not ids or ids[-1]!=s['id']: ids.append(s['id'])
    starts=[]
    for p in phases:
        if p['kind']=='run_start': starts.append(p)
    return {'selection_ids':ids,'selections':selections,'run_starts':starts,'clock_writes':writes,'phases':phases}

def boot(cli,roms,disk,out,tag,hall_raw,rom02_raw):
    d=out/tag; d.mkdir(); dump=d/'rom-snapshots'; dump.mkdir()
    args=['--panel-log','--trace-esp-io','--esp-list','--esp-snapshot-rom-dir',str(dump),'--wav',str(d/'render.wav'),'--button','15:7:1','--button','15.2:7:0']
    sequence,seconds=make_sequence(rom02_raw,hall_raw,rom02_raw); args+=sequence
    env=capture.emulator_env(); env['ASR_OTTO_CLOCK_TRACE']='1'; env['ESP_PIPELOG']='1'; env['ESP_HOSTLOG']='1'
    capture.run(cli,roms,disk,seconds,args,env,d/'session.log')
    return parse(d/'session.log')

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--cli',required=True,type=Path); p.add_argument('--roms',required=True,type=Path); p.add_argument('--disk',required=True,type=Path); p.add_argument('--out',required=True,type=Path); p.add_argument('--hall-raw',type=int,default=79); p.add_argument('--rom02-raw',type=int,default=90)
    a=p.parse_args(); out=a.out.expanduser().resolve()
    if out==ROOT or ROOT in out.parents:p.error('private capture output must remain outside Git')
    out.mkdir(parents=True,exist_ok=False); cli=a.cli.resolve(strict=True); roms=a.roms.resolve(strict=True); disk=a.disk.resolve(strict=True)
    x=boot(cli,roms,disk,out,'boot-a',a.hall_raw,a.rom02_raw); y=boot(cli,roms,disk,out,'boot-b',a.hall_raw,a.rom02_raw)
    want=[1,2,1]
    if x['selection_ids']!=want or y['selection_ids']!=want: raise SystemExit('switch sequence was not HALL -> ROM-02 -> HALL')
    if [(z['kind'],z['frame'],z['cycles']) for z in x['run_starts']]!=[(z['kind'],z['frame'],z['cycles']) for z in y['run_starts']]: raise SystemExit('fresh switch timelines differ')
    if [(z['voice_register'],z['otto_hz'],z['rate_hz']) for z in x['clock_writes']]!=[(z['voice_register'],z['otto_hz'],z['rate_hz']) for z in y['clock_writes']]: raise SystemExit('fresh clock-write histories differ')
    # Report only identity/timing/configuration facts; full traces and ROM snapshots stay private.
    print(json.dumps({'fresh_processes':2,'selection_order':want,
      'selection_clock_observations':[{k:s[k] for k in ('id','cycles','frame','rate_hz','otto_hz','voice_register','host_rate_hz')} for s in x['selections']],
      'run_boundaries':x['run_starts'],
      'otto_voice_clock_write_count':len(x['clock_writes']),
      'clock_write_configs':sorted({(w['voice_register'],round(w['otto_hz']),round(w['rate_hz'])) for w in x['clock_writes']}),
      'phase_kinds':[p['kind'] for p in x['phases'] if p['kind'] in ('pa4_halt_assert','host_halt_pipeline_reset','host_dram_clear','instruction_upload_start','pa4_run_release','run_start')],
      'private_output':str(out)},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
