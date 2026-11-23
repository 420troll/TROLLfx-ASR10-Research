#!/usr/bin/env python3
"""Generate controlled stereo stimuli and compare the two ES5510 executors.

All generated samples and reports go under --out (default: /tmp/es5510-audio-validation).
"""
import argparse
import csv
import json
import math
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

def clamp(x): return max(-32768, min(32767, round(x)))

def stimuli(rate, n):
    result = {}
    impulse = [(0, 0)] * n
    impulse[n // 8] = (24000, 0)
    result['impulse'] = impulse
    result['sine'] = [(clamp(24000*math.sin(2*math.pi*997*i/rate)),)*2 for i in range(n)]
    result['sweep'] = []
    phase = 0.0
    for i in range(n):
        f = 30 * (rate/2/30) ** (i/max(1,n-1))
        phase += 2*math.pi*f/rate
        v = clamp(18000*math.sin(phase)); result['sweep'].append((v,v))
    # Deterministic xorshift noise, independent channels.
    state = 0x5510a55a
    noise=[]
    for _ in range(n):
        pair=[]
        for _ch in range(2):
            state ^= (state << 13) & 0xffffffff; state ^= state >> 17; state ^= (state << 5) & 0xffffffff
            pair.append(((state & 0xffff)-32768)//2)
        noise.append(tuple(pair))
    result['noise'] = noise
    result['stereo_phase'] = [(clamp(22000*math.sin(2*math.pi*431*i/rate)), clamp(22000*math.sin(2*math.pi*431*i/rate + math.pi/2))) for i in range(n)]
    return result

def read_outputs(path):
    with path.open(newline='') as f: rows=list(csv.DictReader(f))
    return [[int(r['out_l']), int(r['out_r'])] for r in rows]

def metrics(ref, got):
    n=min(len(ref),len(got)); errors=[got[i][c]-ref[i][c] for i in range(n) for c in range(2)]
    best=(0, float('inf'))
    max_lag=min(128,max(1,n//4))
    for lag in range(-max_lag,max_lag+1):
        pairs=[(ref[i][c],got[i+lag][c]) for i in range(n) for c in range(2) if 0<=i+lag<n]
        e=sum((b-a)**2 for a,b in pairs)/max(1,len(pairs))
        if e<best[1]: best=(lag,e)
    def chstats(c):
        a=[ref[i][c] for i in range(n)]; b=[got[i][c] for i in range(n)]
        return {'reference_peak':max(map(abs,a),default=0),'candidate_peak':max(map(abs,b),default=0),
                'reference_rms':math.sqrt(sum(x*x for x in a)/max(1,n)),
                'candidate_rms':math.sqrt(sum(x*x for x in b)/max(1,n))}
    def timing(x):
        active=[i for i,row in enumerate(x) if row[0] or row[1]]
        peak=max(range(n),key=lambda i:max(map(abs,x[i]))) if n else 0
        return {'first_nonzero_frame':active[0] if active else None,'peak_frame':peak}
    first_diff=next((i for i in range(n) if ref[i]!=got[i]),None)
    return {'frames': n, 'bit_exact':len(ref)==len(got) and first_diff is None,
            'first_divergent_frame':first_diff,
            'max_abs_deviation':max(map(abs,errors),default=0),
            'rms_deviation':math.sqrt(sum(e*e for e in errors)/max(1,len(errors))),
            'best_alignment_lag_frames':best[0], 'aligned_rms_error':math.sqrt(best[1]),
            'channels':{'left':chstats(0),'right':chstats(1)},
            'stereo_difference_reference_rms':math.sqrt(sum((ref[i][0]-ref[i][1])**2 for i in range(n))/max(1,n)),
            'stereo_difference_candidate_rms':math.sqrt(sum((got[i][0]-got[i][1])**2 for i in range(n))/max(1,n)),
            'reference_timing':timing(ref),'candidate_timing':timing(got)}

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--out',type=pathlib.Path,default=pathlib.Path('/tmp/es5510-audio-validation'))
    ap.add_argument('--rate',type=int,default=44100); ap.add_argument('--frames',type=int,default=32768)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    exe=a.out/'es5510-audio-compare'
    sources=[ROOT/'src/es5510.cpp',ROOT/'third_party/trollfx_mame_es5510/mame_es5510_standalone.cpp',ROOT/'tools/audio_validation/compare.cpp']
    subprocess.run(['c++','-std=c++17','-O2','-Isrc','-Ithird_party/trollfx_mame_es5510',*map(str,sources),'-o',str(exe)],cwd=ROOT,check=True)
    summaries={}
    for name,samples in stimuli(a.rate,a.frames).items():
        inp=a.out/f'{name}.csv'
        with inp.open('w',newline='') as f:
            w=csv.writer(f); w.writerows(samples)
        summaries[name]={}
        active_input=next((i for i,row in enumerate(samples) if row[0] or row[1]),None)
        for algorithm in ('pass','delay'):
            outputs={}
            for mode in ('original','mame'):
                p=a.out/f'{name}-{algorithm}-{mode}.csv'; subprocess.run([str(exe),mode,algorithm,str(inp),str(p)],check=True); outputs[mode]=read_outputs(p)
            summary=metrics(outputs['original'],outputs['mame'])
            summary['input_first_nonzero_frame']=active_input
            for mode in ('original','mame'):
                active_output=next((i for i,row in enumerate(outputs[mode]) if row[0] or row[1]),None)
                summary[f'{mode}_input_to_output_delay_frames']=(active_output-active_input
                    if active_output is not None and active_input is not None else None)
            if name=='impulse' and algorithm=='delay':
                impulse_response={}
                for mode in ('original','mame'):
                    taps=[{'frame':i,'offset_from_input_frames':i-active_input,'left':row[0],'right':row[1]}
                          for i,row in enumerate(outputs[mode]) if row[0] or row[1]]
                    impulse_response[mode]=taps
                summary['impulse_response_taps']=impulse_response
            if name in ('sine','sweep') and algorithm=='delay':
                # Windowed least-squares tone gain; sweep is divided into 8 blocks.
                blocks=1 if name=='sine' else 8
                response={'original':[],'mame':[]}
                for block in range(blocks):
                    lo=block*a.frames//blocks; hi=(block+1)*a.frames//blocks
                    if name=='sine': freq=997
                    else: freq=30*(a.rate/2/30)**(((lo+hi)/2)/max(1,a.frames-1))
                    basis_c=basis_s=0.0; out_c=out_s=0.0; mame_c=mame_s=0.0
                    for i in range(lo,hi):
                        phase=2*math.pi*freq*i/a.rate; c=math.cos(phase); s=math.sin(phase)
                        basis_c+=samples[i][0]*c; basis_s+=samples[i][0]*s
                        out_c+=outputs['original'][i][0]*c; out_s+=outputs['original'][i][0]*s
                        mame_c+=outputs['mame'][i][0]*c; mame_s+=outputs['mame'][i][0]*s
                    input_amp=2*math.hypot(basis_c,basis_s)/max(1,hi-lo)
                    output_amp=2*math.hypot(out_c,out_s)/max(1,hi-lo)
                    mame_amp=2*math.hypot(mame_c,mame_s)/max(1,hi-lo)
                    response['original'].append({'frequency_hz':freq,'gain_db':20*math.log10(max(output_amp,1e-12)/max(input_amp,1e-12))})
                    response['mame'].append({'frequency_hz':freq,'gain_db':20*math.log10(max(mame_amp,1e-12)/max(input_amp,1e-12))})
                summary['frequency_response_left_db']=response
            summaries[name][algorithm]=summary
    report={'sample_rate_hz':a.rate,'frames_per_stimulus':a.frames,'comparison':'ASR-10 emulator ES5510 vs standalone TROLLfx MAME-derived adapter','summaries':summaries}
    (a.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
