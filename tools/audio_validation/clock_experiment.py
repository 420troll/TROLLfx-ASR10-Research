#!/usr/bin/env python3
"""Measure OTTO-to-ESP scheduling and analyze direct DSP serial traces.

Raw capture data and extracted CSVs must remain in a private result directory.
"""
from __future__ import annotations
import argparse, csv, json, math, re
from pathlib import Path

CPU_HZ = 16_000_000.0
OLD_OTTO_HZ = 30_476_180.0 / 2.0
VOICE24_OTTO_HZ = 33_868_800.0 / 2.0
FRAME_RE = re.compile(r"ESPPFRAME kind=(input|output) index=(\d+) frame=(\d+) cycles=(\d+) host_pc=([0-9a-fA-F]+) serial=([0-9a-fA-F]+) lanes=([0-9a-fA-F,]+)")
CLOCK_RE = re.compile(r"ESPAUDIO kind=clock frame=(\d+) cycles=(\d+) otto_clock_hz=([0-9.]+) dsp_rate_hz=([0-9.]+) active_voices=(\d+) host_output_rate_hz=([0-9.]+)")
WRITE_RE = re.compile(r"OTTO_CLOCK_WRITE cycles=(\d+) frame=(\d+) register=([0-9a-fA-F]+) value=([0-9a-fA-F]+) active_voices=(\d+) otto_clock_hz=([0-9.]+) dsp_rate_hz=([0-9.]+) pc=([0-9a-fA-F]+)")


def rate_hz(otto_clock_hz: float, active_voice_register: int) -> float:
    """ES5506 voice register N means N+1 voice slots; each consumes 16 clocks."""
    if not 0 <= active_voice_register <= 31: raise ValueError("voice register must be 0..31")
    return otto_clock_hz / (16.0 * (active_voice_register + 1))


def selected_clock(active_voice_register: int) -> float:
    """Mirror the source's two-clock choice, independent of effect identity."""
    slots = active_voice_register + 1
    return VOICE24_OTTO_HZ if slots <= 24 else OLD_OTTO_HZ


def schedule_frames(cycle_chunks: list[int], otto_clock_hz: float, active_voice_register: int,
                    cpu_clock_hz: float = CPU_HZ, initial_accumulator: float = 0.0) -> tuple[int, float]:
    if cpu_clock_hz <= 0 or otto_clock_hz <= 0: raise ValueError("clock rates must be positive")
    acc = initial_accumulator; frames = 0; threshold = 16.0 * (active_voice_register + 1)
    for chunk in cycle_chunks:
        if chunk < 0: raise ValueError("cycle chunks cannot be negative")
        acc += chunk * (otto_clock_hz / cpu_clock_hz)
        while acc >= threshold:
            acc -= threshold; frames += 1
    return frames, acc


def pcm16(v: str) -> int:
    n=int(v,16)&0xffff
    return n-65536 if n&0x8000 else n


def extract_serial(log: Path, start_frame: int, frame_count: int, output_csv: Path, kind: str = "output") -> dict:
    stop=start_frame+frame_count; rows=0; first=None; last=None
    output_csv.parent.mkdir(parents=True,exist_ok=True)
    with log.open(errors="replace") as src, output_csv.open("w",newline="") as dst:
        writer=csv.writer(dst); prefix="ser1" if kind=="output" else "ser2"; lane_indices=(2,3) if kind=="output" else (4,5); writer.writerow(("frame","absolute_frame","cycles",prefix+"_left",prefix+"_right"))
        for line in src:
            m=FRAME_RE.search(line)
            if not m or m.group(1)!=kind: continue
            frame=int(m.group(3))
            if frame<start_frame or frame>=stop: continue
            raw_lanes=m.group(7).split(",")
            if len(raw_lanes)!=8: continue
            cycles=int(m.group(4)); writer.writerow((frame-start_frame,frame,cycles,pcm16(raw_lanes[lane_indices[0]]),pcm16(raw_lanes[lane_indices[1]])))
            point=(frame,cycles)
            if first is None: first=point
            last=point; rows+=1
    return {"frames_written":rows,"first":first,"last":last,"path":str(output_csv),"kind":kind}


def extract_all_lanes(log: Path,start_frame:int,frame_count:int,output_csv:Path,kind:str="input") -> int:
    stop=start_frame+frame_count; count=0; output_csv.parent.mkdir(parents=True,exist_ok=True)
    with log.open(errors="replace") as src, output_csv.open("w",newline="") as dst:
        writer=csv.writer(dst); writer.writerow(("frame","absolute_frame","cycles","host_pc",*[f"lane{i}" for i in range(8)]))
        for line in src:
            m=FRAME_RE.search(line)
            if not m or m.group(1)!=kind: continue
            frame=int(m.group(3))
            if frame<start_frame or frame>=stop: continue
            lanes=m.group(7).split(",")
            if len(lanes)!=8: continue
            writer.writerow((frame-start_frame,frame,int(m.group(4)),m.group(5).lower(),*[pcm16(v) for v in lanes])); count+=1
    return count


def measure_log(log: Path, selected_frame: int | None = None) -> dict:
    first=last=None; clocks=[]; writes=[]
    with log.open(errors="replace") as src:
        for line in src:
            m=FRAME_RE.search(line)
            if m and m.group(1)=="output" and (selected_frame is None or int(m.group(3))>=selected_frame):
                point=(int(m.group(3)),int(m.group(4)))
                if first is None: first=point
                last=point
            m=CLOCK_RE.search(line)
            if m: clocks.append({"frame":int(m.group(1)),"cycles":int(m.group(2)),"otto_clock_hz":float(m.group(3)),"reported_rate_hz":float(m.group(4)),"voice_register":int(m.group(5)),"host_rate_hz":float(m.group(6))})
            m=WRITE_RE.search(line)
            if m: writes.append({"cycles":int(m.group(1)),"frame":int(m.group(2)),"register":int(m.group(3),16),"value":int(m.group(4),16),"voice_register":int(m.group(5)),"otto_clock_hz":float(m.group(6)),"rate_hz":float(m.group(7)),"pc":m.group(8).lower()})
    measured=None
    if first and last and last[0]>first[0] and last[1]>first[1]: measured=(last[0]-first[0])*CPU_HZ/(last[1]-first[1])
    return {"first_output_frame_cycle":first,"last_output_frame_cycle":last,"measured_rate_hz":measured,"clock_markers":clocks,"clock_register_writes":writes}


def serial_metrics(path: Path, rate: float, block_frames: int = 256) -> dict:
    if rate<=0 or block_frames<1: raise ValueError("rate and block size must be positive")
    blocks=[]; first=None; peak=0; clipped=0; nonzero=0
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            idx=int(r.get("frame",r.get("absolute_frame",0))); l=int(r["ser1_left"]); rr=int(r["ser1_right"])
            if first is None: first=idx
            if not blocks or blocks[-1]["count"]>=block_frames:
                blocks.append({"start":idx,"count":0,"left_sq":0,"right_sq":0,"peak":0,"clipped":0})
            b=blocks[-1]; b["count"]+=1; b["left_sq"]+=l*l; b["right_sq"]+=rr*rr
            b["peak"]=max(b["peak"],abs(l),abs(rr)); b["clipped"]+=int(abs(l)>=32767 or abs(rr)>=32767)
            peak=max(peak,abs(l),abs(rr)); clipped+=int(abs(l)>=32767 or abs(rr)>=32767); nonzero+=int(l!=0 or rr!=0)
    envelopes=[]
    for b in blocks:
        left=math.sqrt(b["left_sq"]/b["count"]); right=math.sqrt(b["right_sq"]/b["count"])
        envelopes.append({"first_frame":b["start"],"frame_count":b["count"],"left_rms":left,"right_rms":right,"stereo_rms":math.sqrt((b["left_sq"]+b["right_sq"])/(2*b["count"])),"peak_abs_pcm":b["peak"],"clipped_frames":b["clipped"],"start_seconds":(b["start"]-(first or 0))/rate})
    peak_block=max(range(len(envelopes)),key=lambda i:envelopes[i]["stereo_rms"]) if envelopes else None
    below=None
    if peak_block is not None:
        threshold=envelopes[peak_block]["stereo_rms"]*0.01
        below=next((e["first_frame"] for e in envelopes[peak_block+1:] if e["stereo_rms"]<=threshold),None)
    frame_count=sum(b["count"] for b in blocks)
    duration=frame_count/rate
    return {"frames":frame_count,"first_frame":first,"rate_hz":rate,"capture_duration_seconds":duration,"peak_abs_pcm":peak,"nonzero_frames":nonzero,"clipped_frames":clipped,"peak_rms_block_first_frame":envelopes[peak_block]["first_frame"] if peak_block is not None else None,"one_percent_peak_frame":below,"one_percent_peak_seconds":((below-envelopes[peak_block]["first_frame"])/rate if below is not None and peak_block is not None else None),"block_rms":envelopes}


def compare_serial(left: Path,right: Path,left_rate:float,right_rate:float,left_channels=("ser1_left","ser1_right"),right_channels=("ser1_left","ser1_right"))->dict:
    with left.open(newline="") as a,right.open(newline="") as b:
        aa=list(csv.DictReader(a)); bb=list(csv.DictReader(b))
    n=min(len(aa),len(bb)); count=0; peak=0; sq=0; first=None
    for i in range(n):
        if int(aa[i]["frame"])!=int(bb[i]["frame"]): raise ValueError("relative frame indices differ; no automatic alignment is performed")
        for lane_a,lane_b in zip(left_channels,right_channels):
            d=int(aa[i][lane_a])-int(bb[i][lane_b]); peak=max(peak,abs(d)); sq+=d*d
            if d: count+=1; first=first or {"frame":int(aa[i]["frame"]),"lane":lane_a}
    return {"frames_compared":n,"lane_sample_mismatches":count,"first_mismatch":first,"peak_abs_error":peak,"rmse":math.sqrt(sq/(2*n)) if n else None,"left_rate_hz":left_rate,"right_rate_hz":right_rate,"time_scale_right_over_left":left_rate/right_rate if right_rate else None,"same_frame_different_time":left_rate!=right_rate,"automatic_alignment":False}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="cmd",required=True)
    m=sub.add_parser("measure"); m.add_argument("log",type=Path); m.add_argument("--frame",type=int)
    e=sub.add_parser("extract"); e.add_argument("log",type=Path); e.add_argument("--start-frame",required=True,type=int); e.add_argument("--frames",required=True,type=int); e.add_argument("--kind",choices=("input","output"),default="output"); e.add_argument("--all-lanes",action="store_true"); e.add_argument("--out",required=True,type=Path)
    a=sub.add_parser("analyze"); a.add_argument("csv",type=Path); a.add_argument("--rate",required=True,type=float); a.add_argument("--block",default=256,type=int)
    c=sub.add_parser("compare"); c.add_argument("left",type=Path); c.add_argument("right",type=Path); c.add_argument("--left-rate",required=True,type=float); c.add_argument("--right-rate",required=True,type=float)
    x=p.parse_args()
    if x.cmd=="measure": result=measure_log(x.log,x.frame)
    elif x.cmd=="extract": result={"frames_written":extract_all_lanes(x.log,x.start_frame,x.frames,x.out,x.kind),"path":str(x.out)} if x.all_lanes else extract_serial(x.log,x.start_frame,x.frames,x.out,x.kind)
    elif x.cmd=="analyze": result=serial_metrics(x.csv,x.rate,x.block)
    else: result=compare_serial(x.left,x.right,x.left_rate,x.right_rate)
    print(json.dumps(result,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
