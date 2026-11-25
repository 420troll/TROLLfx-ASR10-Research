"""Local browser simulator using the generated TUI and actual native VST2 API."""
from __future__ import annotations
import base64, hashlib, http.server, io, json, math, os, struct, threading, time, wave
from pathlib import Path
from urllib.parse import urlparse

from bridge import VSTBridge
from render import layout_report, render_page
from skin_model import load_skin
from build import SIM_DIR, PLUGIN, HOST

ROOT=Path(__file__).resolve().parents[2]
PACKAGE=ROOT/"force_plugin/dist/TROLLfx - VST - ASR10 FX Collection"
SKIN=PACKAGE/"Plugin Skins"
WEB=Path(__file__).resolve().parent/"web"
EFFECTS=json.loads((ROOT/"force_plugin/effects.json").read_text())
EFFECT_ROWS=EFFECTS.get("effects",[]) if isinstance(EFFECTS,dict) else EFFECTS
if isinstance(EFFECT_ROWS,dict): EFFECT_ROWS=[EFFECT_ROWS[str(i)] if str(i) in EFFECT_ROWS else EFFECT_ROWS[i] for i in range(1,51)]
EFFECT_NAMES=[str(x.get("name",x)) if isinstance(x,dict) else str(x) for x in EFFECT_ROWS]

# host canonical index and GPR group, taken from the verified append-only V4 registry.
# Exact applied values are supplied by the traced VST, never synthesized by the GUI.
ROUTES={
 1:[("reverb_mix_bus1",27,[0x7c]),("reverb_mix_bus2",28,[0x7a]),("decay_time",29,[0x03,0x04,0x05,0x5b,0x6e]),("hi_freq_damping",30,[0x6c,0x6d])],
 2:[("reverb_mix_bus1",31,[0x7c]),("reverb_mix_bus2",32,[0x7a])],
 3:[("decay_time",33,[0x6e]),("diffusion",34,[0x07,0x09,0x0a,0x0b,0x0c,0x12]),("hi_freq_damping",35,[0x6c,0x6d])],
 4:[("delay_time_l",36,[0x0b])],5:[("delay_time_l",37,[0x0b])],
 6:[("chorus_rate",38,[0x90,0x91,0x92])],7:[("phase_rate",39,[0x8e])],
 8:[("flange_rate",40,[0x84,0x85])],28:[("preamp_gain",41,[0x70])],
 39:[("quality",42,[0x04,0x07,0x0a,0x61,0x64,0xa0])],
 41:[("voice1_fine",43,[0x60])],42:[("comp_ratio",44,[0x8b])],49:[("bass_fc",45,[0x57,0x58])]
}

class Simulator:
    def __init__(self, assets: Path):
        self.model=load_skin(SKIN)
        self.model["effect_names"]=[str(x) for x in EFFECT_NAMES]
        self.assets=assets
        self.host=VSTBridge(HOST,PLUGIN,assets)
        if self.host.num_params != 64: raise RuntimeError(f"expected 64 VST parameters, got {self.host.num_params}")
        if not self.host.has_trace: raise RuntimeError("simulator VST lacks test-only applied-GPR trace API")
        self.lock=threading.RLock()
        self.session_id=f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
        self.log_path=SIM_DIR/"logs"/(self.session_id+".jsonl")
        self.log_path.parent.mkdir(parents=True,exist_ok=True)
        self.ui_page=0
        self.last_trace=self.host.trace_latest()

    def slot(self): return max(1,min(50,int(math.floor(self.host.get(0)*49+0.5))+1))
    def effect_name(self,slot):
        return str(EFFECT_NAMES[slot-1]) if len(EFFECT_NAMES)>=slot else f"FX SLOT {slot:02}"
    def selected(self): return {"slot":self.slot(),"name":self.effect_name(self.slot())}
    def state(self):
        values={str(i):self.host.get(i) for i in range(self.host.num_params)}
        params=[]
        for i in range(self.host.num_params):
            params.append({"index":i,"normalized":values[str(i)],"name":self.host.text(i,True),"display":self.host.text(i)})
        return {"params":params,"values":values,"selected_effect":self.selected(),"page":self.model["pages"][self.ui_page]["name"],
                "status":self.host.text(5),"trace_available":self.host.has_trace}
    def _wait_effect(self, slot):
        deadline=time.monotonic()+5.0
        while time.monotonic()<deadline:
            self.host.pump(256)
            txt=self.host.text(0)
            if " / READY" in txt and f"{slot:02}" in txt: return True
            if "UNAVAILABLE" in txt or "LOAD FAILED" in txt or "PACKAGE REQUIRED" in txt: return False
            time.sleep(0.002)
        return False
    def _route(self,slot,host_index):
        if not 46<=host_index<=53: return None
        controls=ROUTES.get(slot,[]); ordinal=host_index-46
        if ordinal>=len(controls): return None
        cid,canonical,gprs=controls[ordinal]
        return {"id":cid,"canonical_parameter_index":canonical,"registers":[f"0x{x:02X}" for x in gprs],"gpr_ints":gprs}
    @staticmethod
    def _matching_group(rows, slot, expected_gprs):
        # A parameter group is applied atomically at one ES5510 frame. Only a contiguous
        # exact ordered GPR group at one frame counts; background firmware writes are listed separately.
        for i in range(len(rows)):
            group=rows[i:i+len(expected_gprs)]
            if len(group)!=len(expected_gprs): continue
            if all(x["slot"]==slot for x in group) and len({x["dsp_frame"] for x in group})==1 and [x["gpr"] for x in group]==expected_gprs:
                return group
        return []
    def set_param(self,param,norm,page=None,qlink=None):
        param=int(param); norm=max(0.0,min(1.0,float(norm)))
        if not 0<=param<self.host.num_params: raise ValueError("VST parameter index out of range")
        with self.lock:
            before_slot=self.slot(); before_trace=self.host.trace_latest()
            self.host.set(param,norm)
            after_slot=self.slot()
            ready=True
            if param==0: ready=self._wait_effect(after_slot)
            else: self.host.pump(256)
            time.sleep(0.002)
            rows=self.host.trace_since(before_trace)
            resolved=self._route(after_slot,param) if 46<=param<=53 else None
            expected=resolved["gpr_ints"] if resolved else []
            matched=self._matching_group(rows,after_slot,expected) if expected else []
            raw_name=self.host.text(param,True); raw_display=self.host.text(param)
            event={"schema":"trollfx-force-simulator-event-v1","time_utc":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                "ui_page":page or self.model["pages"][self.ui_page]["name"],"physical_equivalent_qlink":int(qlink) if qlink else None,
                "vst_parameter_index":param,"vst_parameter_name":raw_name,"normalized_value":norm,
                "selected_effect_before":{"slot":before_slot,"name":self.effect_name(before_slot)},
                "selected_effect_after":{"slot":after_slot,"name":self.effect_name(after_slot)},
                "resolved_canonical_control":({k:v for k,v in resolved.items() if k!="gpr_ints"} if resolved else None),
                "vst_display_after":raw_display,"package_ready":bool(ready),
                "dsp_register_writes_applied":[{"slot":r["slot"],"dsp_frame":r["dsp_frame"],"gpr":f"0x{r['gpr']:02X}","value24":f"0x{r['value24']:06X}"} for r in rows],
                "resolved_control_register_group_verified":bool(matched),
                "matched_control_write_group":[{"slot":r["slot"],"dsp_frame":r["dsp_frame"],"gpr":f"0x{r['gpr']:02X}","value24":f"0x{r['value24']:06X}"} for r in matched]}
            with self.log_path.open("a",encoding="utf-8") as f: f.write(json.dumps(event,separators=(",",":"))+"\n")
            self.last_trace=self.host.trace_latest()
            return event
    def select_page(self,index):
        index=max(0,min(int(index),len(self.model["pages"])-1)); previous=self.model["pages"][self.ui_page]["name"]
        self.ui_page=index; current=self.model["pages"][index]["name"]
        event={"schema":"trollfx-force-simulator-event-v1","event_type":"page_navigation","time_utc":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            "from_page":previous,"ui_page":current,"physical_equivalent_qlink":None,"vst_parameter_index":None,
            "normalized_value":None,"selected_effect":self.selected(),"resolved_canonical_control":None,"dsp_register_writes_applied":[]}
        with self.log_path.open("a",encoding="utf-8") as f:f.write(json.dumps(event,separators=(",",":"))+"\n")
        return event
    def process_wav(self,raw:bytes,block=256):
        with wave.open(io.BytesIO(raw),"rb") as wf:
            if wf.getnchannels()!=2: raise ValueError("provide a stereo PCM WAV")
            if wf.getframerate()!=48000: raise ValueError("input WAV must be 48,000 Hz; resampling is not simulated")
            if wf.getcomptype()!="NONE": raise ValueError("compressed WAV is not supported")
            width=wf.getsampwidth(); data=wf.readframes(wf.getnframes())
        if width not in (2,3,4): raise ValueError("PCM WAV must be 16-, 24- or 32-bit integer")
        vals=[]
        if width==2:
            vals=[x[0]/32768.0 for x in struct.iter_unpack("<h",data)]
        elif width==3:
            for i in range(0,len(data),3):
                v=data[i]|(data[i+1]<<8)|(data[i+2]<<16)
                if v&0x800000: v-=1<<24
                vals.append(v/8388608.0)
        else:
            vals=[max(-1.0,min(1.0,x[0]/2147483648.0)) for x in struct.iter_unpack("<i",data)]
        if len(vals)%2: raise ValueError("stereo WAV has a partial frame")
        frames=len(vals)//2
        with self.lock:
            # Bypass reference and wet process through the same real VST. This is a practical A/B,
            # not a reset-state null test; plugin state advances between passes.
            self.host.set(4,1.0); self.host.pump(256)
            dry=self.host.process(vals,frames,block)
            self.host.set(4,0.0); self.host.pump(256)
            wet=self.host.process(vals,frames,block)
        def make_wav(samples):
            out=io.BytesIO()
            with wave.open(out,"wb") as wf:
                wf.setnchannels(2);wf.setsampwidth(2);wf.setframerate(48000)
                pcm=bytearray()
                for value in samples:
                    if not math.isfinite(value): value=0.0
                    value=max(-1.0,min(32767/32768,value))
                    q=int(math.floor(value*32768+0.5)) if value>=0 else int(math.ceil(value*32768-0.5))
                    pcm+=struct.pack("<h",max(-32768,min(32767,q)))
                wf.writeframes(pcm)
            return out.getvalue()
        wet_wav=make_wav(wet); dry_wav=make_wav(dry)
        def rms(v): return math.sqrt(sum(x*x for x in v)/max(1,len(v)))
        return {"frames":frames,"sample_rate_hz":48000,"wet_rms":rms(wet),"bypass_rms":rms(dry),
                "wet_sha256":hashlib.sha256(wet_wav).hexdigest(),"bypass_sha256":hashlib.sha256(dry_wav).hexdigest(),
                "wet_wav_base64":base64.b64encode(wet_wav).decode(),"bypass_wav_base64":base64.b64encode(dry_wav).decode(),
                "note":"A/B uses the actual VST bypass. The two passes share one evolving DSP instance; this is not an identical-state null comparison."}
    def screenshot(self,page_index):
        state=self.state(); disp={p["index"]:p["display"] for p in state["params"]}; names={p["index"]:p["name"] for p in state["params"]}
        def get_disp(i): return disp.get(i,"")
        def get_name(i): return names.get(i,"")
        image,_=render_page(self.model,page_index,{int(k):v for k,v in state["values"].items()},get_disp,get_name,None)
        buf=io.BytesIO();image.convert("RGB").save(buf,format="PNG");return buf.getvalue()
    def close(self): self.host.close()

class Handler(http.server.BaseHTTPRequestHandler):
    server_version="TROLLfxForceSim/0.1"
    def log_message(self,*args): pass
    @property
    def sim(self): return self.server.sim
    def send_bytes(self,data,kind="application/json",status=200):
        self.send_response(status);self.send_header("Content-Type",kind);self.send_header("Content-Length",str(len(data)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(data)
    def send_json(self,obj,status=200): self.send_bytes(json.dumps(obj).encode(),"application/json; charset=utf-8",status)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/": return self.send_bytes((WEB/"index.html").read_bytes(),"text/html; charset=utf-8")
        if path=="/app.js": return self.send_bytes((WEB/"app.js").read_bytes(),"text/javascript; charset=utf-8")
        if path=="/style.css": return self.send_bytes((WEB/"style.css").read_bytes(),"text/css; charset=utf-8")
        if path=="/font/regular": return self.send_bytes((Path(__file__).parent/"fonts/TitilliumWeb-Regular.ttf").read_bytes(),"font/ttf")
        if path=="/font/semibold": return self.send_bytes((Path(__file__).parent/"fonts/TitilliumWeb-SemiBold.ttf").read_bytes(),"font/ttf")
        if path=="/api/model": return self.send_json(self.sim.model)
        if path=="/api/state": return self.send_json(self.sim.state())
        if path=="/api/layout-report":
            st=self.sim.state(); names={p["index"]:p["name"] for p in st["params"]}; displays={p["index"]:p["display"] for p in st["params"]}
            return self.send_json(layout_report(self.sim.model,{int(k):v for k,v in st["values"].items()},displays.get,names.get))
        if path.startswith("/asset/"):
            name=Path(path.removeprefix("/asset/")).name
            target=SKIN/name
            if not target.is_file(): return self.send_json({"error":"asset not found"},404)
            return self.send_bytes(target.read_bytes(),"image/png")
        if path.startswith("/api/screenshot/"):
            page=int(path.rsplit("/",1)[-1]); page=max(0,min(page,len(self.sim.model["pages"])-1))
            return self.send_bytes(self.sim.screenshot(page),"image/png")
        return self.send_json({"error":"not found"},404)
    def do_POST(self):
        path=urlparse(self.path).path
        raw=self.rfile.read(int(self.headers.get("Content-Length","0")))
        try:
            if path=="/api/set":
                x=json.loads(raw);self.sim.ui_page=max(0,min(int(x.get("page",self.sim.ui_page)),len(self.sim.model["pages"])-1))
                event=self.sim.set_param(x["param"],x["normalized"],x.get("page_name"),x.get("qlink"))
                return self.send_json({"event":event,"state":self.sim.state()})
            if path=="/api/page":
                x=json.loads(raw);event=self.sim.select_page(x["page"])
                return self.send_json({"event":event,"state":self.sim.state()})
            if path=="/api/process":
                result=self.sim.process_wav(raw,int(self.headers.get("X-Audio-Block","256")))
                return self.send_json(result)
            if path=="/api/state/restore":
                b64=json.loads(raw)["state_base64"]
                with self.sim.lock:self.sim.host.restore_state(base64.b64decode(b64));self.sim.host.pump(256)
                return self.send_json({"state":self.sim.state()})
        except Exception as e:
            return self.send_json({"error":str(e)},400)
        return self.send_json({"error":"not found"},404)

def serve(assets:Path,host="127.0.0.1",port=8765):
    sim=Simulator(assets)
    class Server(http.server.ThreadingHTTPServer): daemon_threads=True
    server=Server((host,port),Handler);server.sim=sim
    st=sim.state(); names={p["index"]:p["name"] for p in st["params"]}; displays={p["index"]:p["display"] for p in st["params"]}
    report=layout_report(sim.model,{int(k):v for k,v in st["values"].items()},displays.get,names.get)
    (SIM_DIR/"latest-layout-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"TROLLfx Force simulator: http://{host}:{server.server_port}/",flush=True)
    print(f"Actual VST2: {PLUGIN} | params={sim.host.num_params} | DSP trace={'on' if sim.host.has_trace else 'off'}",flush=True)
    print(f"Local factory assets: {assets} | session log: {sim.log_path}",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close();sim.close()
