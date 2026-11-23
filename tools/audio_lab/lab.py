#!/usr/bin/env python3
"""Reusable, deterministic audio stimulus, measurement, comparison and reporting tools."""
from __future__ import annotations
import argparse, json, math, pathlib, struct, wave
import numpy as np

SCHEMA = 'https://example.invalid/ensonq/es5510-audio-fingerprint-1.0.json'

def _audio(x):
    a=np.asarray(x,dtype=np.float64)
    if a.ndim==1: a=a[:,None]
    if a.ndim!=2 or a.shape[1] not in (1,2) or not np.all(np.isfinite(a)): raise ValueError('audio must be finite mono or stereo frames')
    return a

def stimulus(kind, rate=44100, frames=65536, seed=5510, frequency=997.0, amplitude=.5, **kw):
    if rate not in (44100,48000): raise ValueError('sample rate must be 44100 or 48000 Hz')
    if frames<1: raise ValueError('frames must be positive')
    t=np.arange(frames)/rate; x=np.zeros((frames,2),float); amp=float(amplitude)
    if kind in ('impulse','stereo_impulse'):
        x[min(int(kw.get('at',0)),frames-1),0]=amp
        if kind=='stereo_impulse': x[min(int(kw.get('right_at',kw.get('at',0))),frames-1),1]=amp
    elif kind=='sine': x[:]=amp*np.sin(2*np.pi*frequency*t)[:,None]
    elif kind=='multitone':
        fs=kw.get('frequencies',(127.,997.,4001.)); x[:]=sum(np.sin(2*np.pi*f*t) for f in fs)[:,None]*(amp/len(fs))
    elif kind=='sweep':
        f0=float(kw.get('start_hz',20)); f1=float(kw.get('end_hz',rate*.45)); dur=frames/rate
        phase=2*np.pi*f0*dur/np.log(f1/f0)*(np.exp(t*np.log(f1/f0)/dur)-1) if f1>f0 else 2*np.pi*f0*t
        x[:]=amp*np.sin(phase)[:,None]
    elif kind=='noise': x[:]=np.random.default_rng(seed).uniform(-amp,amp,(frames,2))
    elif kind=='silence': pass
    elif kind=='step': x[int(kw.get('at',0)):]=amp
    else: raise ValueError('unknown stimulus kind: '+kind)
    return x

def write_wav(path, x, rate=44100):
    a=np.clip(_audio(x),-1,1); pcm=np.round(a*32767).astype('<i2')
    with wave.open(str(path),'wb') as w: w.setnchannels(a.shape[1]); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm.tobytes())

def read_wav(path):
    with wave.open(str(path),'rb') as w:
        if w.getsampwidth()!=2: raise ValueError('only PCM16 WAV is supported')
        rate=w.getframerate(); c=w.getnchannels(); n=w.getnframes(); a=np.frombuffer(w.readframes(n),dtype='<i2').reshape(-1,c).astype(float)/32768
    return a,rate

def _corr(a,b):
    if len(a)<2 or np.std(a)==0 or np.std(b)==0: return None
    return float(np.corrcoef(a,b)[0,1])

def _decay(ch, rate):
    energy=np.cumsum((ch[::-1]**2))[::-1]; energy=energy/max(float(energy[0]),1e-300)
    db=10*np.log10(np.maximum(energy,1e-300)); times=np.arange(len(ch))/rate
    out={'edt_s':None,'t20_s':None,'t30_s':None,'rt60_s':None,'reliable':False,'reason':'insufficient decay range'}
    for key,lo,hi in [('edt_s',0,-10),('t20_s',-5,-25),('t30_s',-5,-35)]:
        mask=(db<=lo)&(db>=hi)
        if mask.sum()>=max(8,int(rate*.01)):
            slope=np.polyfit(times[mask],db[mask],1)[0]
            if slope<0:
                val=(lo-hi)/-slope; out[key]=float(val); 
                if key=='t20_s': out['rt60_s']=float(val*3)
                if key=='t30_s': out['rt60_s']=float(val*2)
                if key=='edt_s': out['edt_s']=float(val*6)
                out['reliable']=True; out['reason']=None
    return out,db

def analyze(x, rate=44100, input_audio=None):
    a=_audio(x); n,c=a.shape
    peak=np.max(np.abs(a),axis=0) if n else np.zeros(c); rms=np.sqrt(np.mean(a*a,axis=0)) if n else np.zeros(c)
    decay,db=_decay(a[:,0],rate) if n else ({'reliable':False,'reason':'empty audio'},np.array([]))
    floor=max(float(np.max(peak))*1e-5,1e-12); active=np.flatnonzero(np.max(np.abs(a),axis=1)>floor)
    # First arrival and subsequent local peak arrivals from channel-combined envelope.
    env=np.max(np.abs(a),axis=1); arrivals=[]
    if len(env):
        candidates=np.flatnonzero((env[1:-1]>env[:-2])&(env[1:-1]>=env[2:])&(env[1:-1]>floor))+1
        if env[0]>floor: candidates=np.r_[0,candidates]
        arrivals=[{'frame':int(i),'time_s':float(i/rate),'peak':float(env[i])} for i in candidates[:64]]
    freq=None
    if len(a)>=8:
        nfft=1<<(len(a)-1).bit_length(); window=np.hanning(len(a)); spec=np.fft.rfft(a[:,0]*window,nfft); step=max(1,nfft//4096); freq={'frequency_hz':(np.fft.rfftfreq(nfft,1/rate)[::step]).tolist(),'magnitude_db':(20*np.log10(np.maximum(np.abs(spec),1e-12))[::step]).tolist()}
    stereo={'channel_correlation':_corr(a[:,0],a[:,1]) if c==2 else None,'cross_feedback_estimate':None,'interpretation':'not identifiable from output alone' if c==2 else 'mono'}
    if c==2 and input_audio is not None:
        i=_audio(input_audio); m=min(len(a),len(i)); stereo['cross_feedback_estimate']={'left_from_right_correlation':_corr(i[:m,1],a[:m,0]),'right_from_left_correlation':_corr(i[:m,0],a[:m,1]),'caveat':'correlation is not causal attribution'}
    # Transfer estimate is a stabilized Welch-style averaged FFT ratio, suitable when input is known.
    fr=None; modulation={'reliable':False,'candidate_sidebands_hz':[],'reason':'requires a known stationary carrier probe'}
    if input_audio is not None:
        i=_audio(input_audio); m=min(len(a),len(i)); nfft=min(4096,1<<(max(8,m)-1).bit_length()); win=np.hanning(min(m,nfft)); step=max(1,len(win)//2); accx=accy=None; count=0
        if m>=len(win):
            for st in range(0,m-len(win)+1,step):
                X=np.fft.rfft(i[st:st+len(win),0]*win,nfft); Y=np.fft.rfft(a[st:st+len(win),0]*win,nfft)
                xx=np.abs(X)**2; xy=Y*np.conj(X); accx=xx if accx is None else accx+xx; accy=xy if accy is None else accy+xy; count+=1
            h=accy/np.maximum(accx,1e-20); fr={'frequency_hz':np.fft.rfftfreq(nfft,1/rate).tolist(),'magnitude_db':(20*np.log10(np.maximum(np.abs(h),1e-12))).tolist(),'method':'averaged cross-spectrum / input power','reliable_bins':int(np.sum(accx>max(accx.max()*1e-8,1e-20)))}
        # A stationary single-tone probe permits candidate sideband reporting, not causal attribution.
        ii=i[:m]; oo=a[:m];
        if m>=64:
            win_sb=np.hanning(m); inp_spec=np.abs(np.fft.rfft(ii[:,0]*win_sb)); out_spec=np.abs(np.fft.rfft(oo[:,0]*win_sb)); hz=np.fft.rfftfreq(m,1/rate); carrier=int(np.argmax(inp_spec)); cf=hz[carrier]; bw=max(3*rate/m,100.0); region=(np.abs(hz-cf)<=bw)&(np.abs(hz-cf)>max(2*rate/m,1.0)); inds=np.flatnonzero(region); candidates=[]
            if len(inds) and out_spec[carrier]>0:
                peaks=inds[(out_spec[inds]>=np.r_[0,out_spec[:-1]][inds])&(out_spec[inds]>=np.r_[out_spec[1:],0][inds])&(out_spec[inds]>=out_spec[carrier]*.01)]
                candidates=[{'frequency_hz':float(hz[q]),'offset_from_carrier_hz':float(hz[q]-cf),'relative_to_carrier_db':float(20*np.log10(out_spec[q]/out_spec[carrier]))} for q in peaks[:32]]
            modulation={'reliable':False,'carrier_hz':float(cf),'candidate_sidebands_hz':candidates,'reason':'spectral peaks near the carrier may be modulation sidebands, distortion, leakage, or time variation; confirm with known modulation rate'}
        # Direct-path ratio proxy, explicitly conditioned on input/output overlap. stereo['wet_dry']={'input_rms':float(np.sqrt(np.mean(ii**2))),'output_rms':float(np.sqrt(np.mean(oo**2))),'output_to_input_db':float(20*np.log10(max(np.sqrt(np.mean(oo**2)),1e-15)/max(np.sqrt(np.mean(ii**2)),1e-15))),'interpretation':'level ratio; wet/dry separation requires a declared dry reference'}
        # Cross-correlation timing, bounded to full available duration; impulse is the preferred probe.
        il=ii[:,0]-ii[:,0].mean(); ol=oo[:,0]-oo[:,0].mean(); size=1<<(2*m-1).bit_length(); corr=np.fft.irfft(np.fft.rfft(ol,size)*np.conj(np.fft.rfft(il,size)),size); corr=np.r_[corr[-(m-1):],corr[:m]]; lag=int(np.argmax(np.abs(corr))-(m-1)); stereo['delay']={'cross_correlation_lag_frames':lag,'seconds':lag/rate,'interpretation':'dominant linear delay; ambiguous for periodic or highly reverberant signals'}
    return {'sample_rate_hz':rate,'frames':n,'duration_s':n/rate,'channels':c,'peak':peak.tolist(),'rms':rms.tolist(),'tail_end_s':float(active[-1]/rate) if len(active) else None,'first_active_frame':int(active[0]) if len(active) else None,'arrival_peaks':arrivals,'decay':decay,'stereo':stereo,'frequency_response':fr,'modulation_sidebands':modulation,'spectrum':freq,'decay_curve_db':db[::max(1,len(db)//4096)].tolist()}

def compare(reference,candidate,rate=44100):
    r=_audio(reference); c=_audio(candidate)
    if r.shape[1]!=c.shape[1]: raise ValueError('reference and candidate channel counts differ')
    n=min(len(r),len(c)); a=r[:n]; b=c[:n]; e=b-a
    exact=len(r)==len(c) and np.array_equal(r,c); maxlag=min(n-1,rate*2); 
    if n:
        aa0=a[:,0]-a[:,0].mean(); bb0=b[:,0]-b[:,0].mean(); size=1<<(2*n-1).bit_length(); corr=np.fft.irfft(np.fft.rfft(bb0,size)*np.conj(np.fft.rfft(aa0,size)),size); corr=np.r_[corr[-(n-1):],corr[:n]]; lag=int(np.argmax(np.abs(corr))-(n-1))
    else: lag=0
    aligned=0.0
    if n:
        if lag>=0: aa,bb=a[:n-lag or None],b[lag:]
        else: aa,bb=a[-lag:],b[:n+lag]
        aligned=float(np.sqrt(np.mean((bb-aa)**2))) if len(aa) else None
    metrics={'exact_sample_equal':bool(exact),'perceptual_similarity_claimed':False,'frames_compared':n,'lengths_equal':len(r)==len(c),'max_abs_sample_error':float(np.max(np.abs(e))) if e.size else 0.0,'rms_sample_error':float(np.sqrt(np.mean(e*e))) if e.size else 0.0,'cross_correlation_lag_frames':lag,'cross_correlation':_corr(a[:,0],b[:,0]),'aligned_rms_error':aligned,'stereo_correlation_difference':(_corr(a[:,0],a[:,1]),_corr(b[:,0],b[:,1])) if a.shape[1]==2 and b.shape[1]==2 else None}
    # Spectral and impulse differences are meaningful when supplied captures are corresponding probe responses.
    if n>=8:
        N=1<<(n-1).bit_length(); win=np.hanning(n); R=np.fft.rfft(a[:,0]*win,N); C=np.fft.rfft(b[:,0]*win,N); metrics['frequency_response_difference_db']=(20*np.log10(np.maximum(abs(C),1e-12))-20*np.log10(np.maximum(abs(R),1e-12))).tolist()
    metrics['impulse_response_difference']=e.tolist()
    dr,_=_decay(a[:,0],rate); dc,_=_decay(b[:,0],rate); metrics['decay_envelope_difference_db']=(10*np.log10(np.maximum(np.cumsum(a[::-1,0]**2)[::-1],1e-300)/max(np.sum(a[:,0]**2),1e-300))-10*np.log10(np.maximum(np.cumsum(b[::-1,0]**2)[::-1],1e-300)/max(np.sum(b[:,0]**2),1e-300)))[::max(1,n//4096)].tolist()
    metrics['decay_estimate_difference']={k:(dc.get(k)-dr.get(k) if dr.get(k) is not None and dc.get(k) is not None else None) for k in ('edt_s','t20_s','t30_s','rt60_s')}
    return metrics

def fingerprint(effect_id, x, rate=44100, source_type='synthetic', provenance=None, input_audio=None, parameters=None):
    if source_type not in ('reference_render','emulator_prediction','synthetic'): raise ValueError('invalid source_type')
    return {'schema':SCHEMA,'effect_id':effect_id,'source_type':source_type,'provenance':provenance or {},'parameters':parameters or {},'measurement':analyze(x,rate,input_audio),'note':'A fingerprint records measured audio properties; it does not imply factory authenticity.'}

def sensitivity(before,after,rate=44100):
    a=analyze(before,rate); b=analyze(after,rate); return {'before':a,'after':b,'changes':{'peak_db':_level_delta(a['peak'],b['peak']),'rms_db':_level_delta(a['rms'],b['rms']),'tail_end_s':None if a['tail_end_s'] is None or b['tail_end_s'] is None else b['tail_end_s']-a['tail_end_s'],'decay':{k:(b['decay'].get(k)-a['decay'].get(k) if a['decay'].get(k) is not None and b['decay'].get(k) is not None else None) for k in ('edt_s','t20_s','t30_s','rt60_s')},'stereo_correlation':None if a['stereo']['channel_correlation'] is None or b['stereo']['channel_correlation'] is None else b['stereo']['channel_correlation']-a['stereo']['channel_correlation']}}
def _level_delta(a,b): return [20*math.log10(max(y,1e-15)/max(x,1e-15)) for x,y in zip(a,b)]

def report(x, rate, out, name='synthetic-example'):
    out=pathlib.Path(out); out.mkdir(parents=True,exist_ok=True); m=analyze(x,rate); (out/f'{name}.json').write_text(json.dumps(fingerprint(name,x,rate),indent=2)+'\n')
    summary=f'# {name}\n\nSynthetic demonstration; no factory render was used.\n\n- Sample rate: {rate} Hz\n- Frames: {m["frames"]}\n- Peak: {m["peak"]}\n- RMS: {m["rms"]}\n- Tail end: {m["tail_end_s"]} s\n- Decay: `{json.dumps(m["decay"])}`\n\nFrequency response and decay plot are in the adjacent PNG.\n'
    (out/f'{name}.md').write_text(summary)
    try:
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(2,1,figsize=(9,6)); ax[0].plot(np.arange(len(x))/rate,np.asarray(x)[:,0]); ax[0].set(xlabel='Time (s)',ylabel='Amplitude',title='Synthetic response'); ax[1].plot(np.arange(len(m['decay_curve_db']))/rate,m['decay_curve_db']); ax[1].set(xlabel='Time (s)',ylabel='Schroeder decay (dB)',ylim=(-80,2)); fig.tight_layout(); fig.savefig(out/f'{name}.png',dpi=140); plt.close(fig)
    except ImportError:
        # Small dependency-free PNG fallback keeps the example artifact available.
        from PIL import Image, ImageDraw
        w,h=1000,560; im=Image.new('RGB',(w,h),'white'); draw=ImageDraw.Draw(im); mid=260; draw.line((50,mid,w-20,mid),fill='#777'); draw.line((50,30,50,mid),fill='#777')
        vals=np.asarray(x)[:,0]; stride=max(1,len(vals)//(w-70)); pts=[]
        for k in range(0,len(vals),stride): pts.append((50+int(k/max(1,len(vals)-1)*(w-70)),mid-int(vals[k]*200)))
        if len(pts)>1: draw.line(pts,fill='#2468a2',width=1)
        dbv=np.asarray(m['decay_curve_db']); pts=[]
        for k,v in enumerate(dbv): pts.append((50+int(k/max(1,len(dbv)-1)*(w-70)),30+int(min(80,max(0,-v))/80*(h-80))))
        if len(pts)>1: draw.line(pts,fill='#b44',width=2)
        im.save(out/f'{name}.png')

def demo_effect(rate=44100,frames=88200):
    x=np.zeros((frames,2)); x[0]=.7
    for t,g in ((.037,.33),(.091,.2),(.17,.12)):
        k=round(t*rate)
        if k<frames: x[k]=g
    rng=np.random.default_rng(2); tail=np.arange(frames)/rate; x[:,0]+=rng.normal(0,.008,frames)*np.exp(-tail/.7); x[:,1]+=rng.normal(0,.008,frames)*np.exp(-tail/.8)
    return x

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    g=sub.add_parser('stimulus'); g.add_argument('kind',choices=['impulse','stereo_impulse','sweep','sine','multitone','noise','silence','step']); g.add_argument('--rate',type=int,default=44100); g.add_argument('--frames',type=int,default=65536); g.add_argument('--seed',type=int,default=5510); g.add_argument('--frequency',type=float,default=997); g.add_argument('--output',required=True)
    a=sub.add_parser('analyze'); a.add_argument('wav'); a.add_argument('--input'); a.add_argument('--json',required=True)
    d=sub.add_parser('demo'); d.add_argument('--out',default='docs/audio-lab/example'); d.add_argument('--rate',type=int,default=44100)
    c=sub.add_parser('compare'); c.add_argument('reference'); c.add_argument('candidate'); c.add_argument('--json',required=True)
    z=p.parse_args()
    if z.cmd=='stimulus': write_wav(z.output,stimulus(z.kind,z.rate,z.frames,z.seed,z.frequency),z.rate)
    elif z.cmd=='analyze':
        x,r=read_wav(z.wav); i=None if not z.input else read_wav(z.input)[0]; pathlib.Path(z.json).write_text(json.dumps(analyze(x,r,i),indent=2)+'\n')
    elif z.cmd=='demo': report(demo_effect(z.rate),z.rate,z.out)
    else:
        x,r=read_wav(z.reference); y,ry=read_wav(z.candidate)
        if r!=ry: raise SystemExit('sample rates differ')
        pathlib.Path(z.json).write_text(json.dumps(compare(x,y,r),indent=2)+'\n')
if __name__=='__main__': main()
