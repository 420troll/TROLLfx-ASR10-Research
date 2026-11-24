#!/usr/bin/env python3
"""Replace late selector snapshots with source-correlated first-RUN packages.

The capture report must come from capture_factory_run_boundaries.py. This
updater changes only selected private package folders; it never relaxes gates.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, shutil
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import esp_capture

EVENT = re.compile(r"^ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-fA-F]+) (gpr|instr|both|ram)\s+([0-9a-fA-F]+) <- ([0-9a-fA-F]+)(?: / ([0-9a-fA-F]+))?")
PHASE = re.compile(r"ESPPHASE kind=([a-z0-9_]+)\s+(.*)$")
FIELD = re.compile(r"([a-z_]+)=([^\s]+)")
SELECT = re.compile(r"ESP_ROM_SELECT id=(\d+) time=([0-9.]+).*?frame=(\d+).*?dsp_rate_hz=([0-9.]+).*?display=(.*)$")

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--collection",type=Path,required=True)
    p.add_argument("--capture-report",type=Path,required=True)
    a=p.parse_args(); root=a.collection.resolve(strict=True); report=json.loads(a.capture_report.resolve(strict=True).read_text())
    if report.get("schema")!="es5510-selected-run-boundary-capture-v1": raise ValueError("unrecognized boundary capture report")
    log=Path(report["private_log"]).resolve(strict=True); lines=log.read_text(errors="replace").splitlines()
    phases=[]; selects=[]; events=[]
    for n,line in enumerate(lines,1):
        m=PHASE.search(line)
        if m:
            f=dict(FIELD.findall(m.group(2))); f.update(kind=m.group(1),line=n); phases.append(f)
        m=SELECT.search(line)
        if m: selects.append({"slot":int(m[1]),"time":float(m[2]),"frame":int(m[3]),"rate":float(m[4]),"display":m[5],"line":n})
        m=EVENT.match(line)
        if m:
            eid,cy,fr,pc,kind,addr,val,second=m.groups()
            events.append({"line":n,"event":int(eid),"cycles":int(cy),"frame":int(fr),"pc":pc.lower(),"kind":kind,"address":int(addr,16),"value":int(val,16),"second":int(second,16) if second else None,"text":line})
    records=[]
    for rec in report["records"]:
        slot=int(rec["slot"]); frame=int(rec["frame"]); cap_path=Path(rec["checkpoint"]).resolve(strict=True)
        pkgfile=next((root/"packages").glob(f"ROM-{slot:02d}-*/package.json")); base=pkgfile.parent; doc=json.loads(pkgfile.read_text())
        cap=esp_capture.read_capture(cap_path)
        run=next(x for x in phases if x["kind"]=="run_start" and int(x.get("frame",-1))==frame)
        runline=int(run["line"])
        selection=[x for x in selects if x["slot"]==slot and x["line"]<runline]
        if not selection: raise ValueError(f"slot {slot}: no prior stable OS slot display correlates to RUN")
        sel=selection[-1]
        after_selects=[x for x in selects if x["slot"]==slot+1 and x["line"]>runline]
        # ESP_ROM_SELECT is emitted only after the display/clock has stabilized.
        # The following slot's stable observation therefore samples the clock
        # left by this slot's completed RUN/load transition.
        clock_evidence=after_selects[0] if after_selects else None
        observed_rate=clock_evidence["rate"] if clock_evidence else sel["rate"]
        chain_kinds=["pa4_halt_assert","halt","host_halt_pipeline_reset","host_dram_clear","instruction_upload_start","pa4_run_release","program_upload_summary","run_start","run_snapshot","first_instruction"]
        chain=[]
        for kind in chain_kinds:
            candidates=[x for x in phases if x["kind"]==kind and int(x["line"])<=int(rec["first_instruction"]["line"] if "line" in rec["first_instruction"] else 1)]
            if kind=="first_instruction": candidates=[x for x in phases if x["kind"]==kind and int(x.get("frame",-1))==frame]
            elif kind in ("run_start","run_snapshot","program_upload_summary"): candidates=[x for x in phases if x["kind"]==kind and int(x.get("frame",-1))==frame]
            elif kind in ("pa4_halt_assert","halt","host_halt_pipeline_reset","host_dram_clear","instruction_upload_start","pa4_run_release"):
                candidates=[x for x in phases if x["kind"]==kind and int(x["line"])<runline]
            if not candidates: raise ValueError(f"slot {slot}: required {kind} phase is absent")
            chain.append(candidates[-1])
        chain_lines=[int(x["line"]) for x in chain]
        if chain_lines != sorted(chain_lines) or not (int(chain[7]["line"]) < int(chain[8]["line"]) < int(chain[9]["line"])):
            raise ValueError(f"slot {slot}: HALT/reset/load/RUN/snapshot/instruction phase order is invalid")
        # Prove the uploaded words immediately preceding this RUN match the captured image.
        upload=next(x for x in chain if x["kind"]=="host_halt_pipeline_reset")
        instrs={}
        for e in events:
            if int(upload["line"])<e["line"]<runline and e["kind"] in ("instr","both"):
                addr=e["address"]&0xff
                instrs[addr]=e["value"]&0xffffffffffff
        active=int(cap["program"]["active_words_through_first_END"])
        raw=cap_path.read_bytes(); words=[int.from_bytes(raw[44+i*6:44+(i+1)*6],"big") for i in range(active)]
        # The log prints the 48-bit instruction as an integer in hex. Compare the same packed value.
        missing=[i for i in range(active) if i not in instrs]
        mismatch=[i for i in range(active) if i in instrs and instrs[i]!=words[i]]
        if missing or mismatch: raise ValueError(f"slot {slot}: uploaded instruction correlation failed (missing={missing[:5]}, mismatch={mismatch[:5]})")
        # Convert observed post-RUN GPR writes into a bounded frame-relative schedule.
        future=[e for e in events if frame<=e["frame"]<frame+32768 and e["kind"] in ("gpr","both") and e["address"]<0xc0]
        schedule=base/"firmware-schedule.csv"
        with schedule.open("w",newline="") as stream:
            w=csv.writer(stream); w.writerow(["relative_dsp_frame","event_id","cpu_cycles","gpr","value24"])
            for e in future: w.writerow([e["frame"]-frame,e["event"],e["cycles"],f'{e["address"]:02x}',f'{e["value"]&0xffffff:06x}'])
        # Keep full verified pre-RUN transaction history in the existing log.
        history=[e["text"] for e in events if e["frame"]<=frame]
        evpath=base/doc["firmware_events"]; evpath.write_text("\n".join(history)+("\n" if history else ""))
        checkpoint=base/doc["checkpoint"]; shutil.copyfile(cap_path,checkpoint)
        doc.update({"capture_kind":"OS-selected first-instruction RUN-boundary snapshot",
                    "run_frame":frame,"snapshot_time_seconds":sel["time"],"sample_rate_hz":observed_rate,
                    "clock_evidence":{"measured_rate_hz":observed_rate,"observation":"next stable factory-slot display after this RUN" if clock_evidence else "target slot stable display before RUN; post-RUN clock unobserved","verified_after_run":clock_evidence is not None,"observation_slot":slot+1 if clock_evidence else slot},
                    "active_program_words":active,"active_program_sha256":cap["program"]["active_program_sha256"],
                    "registers":{"gpr_count":192,"gpr_sha256":cap["registers"]["gpr_sha256"],"special_count":22,"special_sha256":cap["registers"]["special_sha256"]},
                    "dram":{"words":cap["runtime"]["dram_words"],"nonzero_words":cap["runtime"]["dram_nonzero_words"],"sha256":cap["runtime"]["dram_sha256"]},
                    "memory_configuration":cap["runtime"]["memory_configuration"],"delay_configuration":cap["runtime"]["delay_configuration"],
                    "signal_configuration":cap["runtime"]["signal_configuration"],
                    "pipeline_reset_acknowledged":True,"host_commit_match":{"verified":True,"active_words":active,"source":"ordered host instruction commits between reset/load and correlated RUN"},
                    "run_boundary_source_correlation":{"verified":True,"slot":slot,"display":sel["display"],"display_frame":sel["frame"],"display_line":sel["line"],"run_frame":frame,"uploaded_instruction_count":active,"program_sha256":cap["program"]["active_program_sha256"]},
                    "run_boundary_phase_evidence":{"ordered":True,"events":[{k:(int(x[k]) if k in ("frame","cycles","line") else x[k]) for k in ("kind","frame","cycles","pc","line") if k in x} for x in chain]},
                    "firmware_transaction_count":len(history),"firmware_schedule":{"path":schedule.name,"sha256":sha(schedule),"count":len(future),"window_frames":32768},
                    "files":{**doc["files"],checkpoint.name:sha(checkpoint),evpath.name:sha(evpath),schedule.name:sha(schedule)}})
        pkgfile.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
        records.append({"slot":slot,"name":doc["display_name"],"frame":frame,"program_words":active,"program_sha256":doc["active_program_sha256"],"schedule_events":len(future),"package":str(pkgfile),"checkpoint_sha256":sha(checkpoint)})
    print(json.dumps({"updated":len(records),"records":records,"source_log":str(log)},indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())
