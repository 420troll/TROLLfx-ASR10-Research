#!/usr/bin/env python3
"""Run validated ASR-10 packages through the native ES5510 playback harness.

Collection packages enter only through Codex 1's importer audit. Independent
HALL/ROM-02 references enter only after the repository's strict runtime-package
validator succeeds. All generated state, WAVs, and reports remain outside Git.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools/audio_validation/validate_factory_runtime_package.py"
HARNESS_CPP = ROOT / "tools/audio_validation/es5510_playback_harness.cpp"
BACKEND_CPP = ROOT / "force_plugin/src/ES5510DSPBackend.cpp"
RUNTIME_CPP = ROOT / "src/es5510_factory_runtime.cpp"
DSP_CPP = ROOT / "src/es5510.cpp"

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()

def safe_text(value: str) -> str:
    if any(c in value for c in "\t\r\n"): raise ValueError("descriptor text contains TSV delimiters")
    return value

def read_schedule_csv(path: Path, run_frame: int) -> list[tuple[int,int,int]]:
    events=[]
    with path.open(newline="") as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames != ["boundary_frame","event_id","cpu_cycles","dsp_frame","host_pc","index","value"]:
            raise ValueError("firmware schedule header is invalid")
        last=-1
        for row in reader:
            frame=int(row["boundary_frame"])-run_frame
            index=int(row["index"],16); value=int(row["value"],16)
            if frame<0 or frame<last or index>=0xc0 or value>0xffffff: raise ValueError("firmware schedule is out of bounds")
            last=frame;events.append((frame,index,value))
    if len(events)>256: raise ValueError("firmware schedule exceeds runtime queue capacity")
    return events

def save_schedule(path: Path, events: list[tuple[int,int,int]]) -> None:
    with path.open("w") as stream:
        for frame,index,value in events: stream.write(f"{frame}\t{index}\t{value:x}\n")

def dump_reference_csv(input_path: Path, output_path: Path, run_frame: int,
                       input_binary: Path, output_binary: Path) -> int:
    with input_path.open(newline="") as stream: inputs=list(csv.DictReader(stream))
    with output_path.open(newline="") as stream: outputs=list(csv.DictReader(stream))
    if len(inputs)!=len(outputs) or not inputs: raise ValueError("reference input/output CSV frame counts differ")
    in_frames=[];out_frames=[]
    for index,(a,b) in enumerate(zip(inputs,outputs)):
        if int(a["frame"])!=run_frame+index or int(b["frame"])!=run_frame+index:
            raise ValueError("reference frame coordinates are not contiguous at RUN")
        in_frames.extend((int(a["lane4"]),int(a["lane5"])))
        out_frames.extend((int(b["reference_left"]),int(b["reference_right"])))
    for path,frames in ((input_binary,in_frames),(output_binary,out_frames)):
        with path.open("wb") as stream:
            for sample in frames: stream.write(struct.pack("<f",sample/32768.0))
    return len(inputs)

def package_from_importer(item: dict, output: Path) -> dict | None:
    if item.get("registry_eligible") is not True: return None
    d=item.get("descriptor")
    if not isinstance(d,dict): raise ValueError("eligible importer entry has no descriptor")
    route=d["routing"]; checkpoint=Path(d["run_checkpoint_path"]).resolve(strict=True)
    events=[(int(e["relative_dsp_frame"]),int(e["gpr"]),int(e["value24"])) for e in d.get("firmware_event_schedule",[])]
    schedule=output/f"slot-{int(d['slot']):02d}-events.tsv";save_schedule(schedule,events)
    return {"slot":int(d["slot"]),"name":str(d["factory_name"]),"words":int(d["active_program_words"]),
        "end":int(d["end_word"]),"program_sha":str(d["program_sha256"]),"rate":float(d["factory_reference_rate_hz"]),
        "serial":int(route["host_serial_mode"]),"input_port":int(route["input_port"]),"output_port":int(route["output_port"]),
        "checkpoint":str(checkpoint),"checkpoint_sha":str(d["run_checkpoint_sha256"]),
        "manifest":str(Path(d.get("initialization_manifest_path") or d["package_manifest_path"]).resolve()),
        "schedule":str(schedule),"ref_in":"","ref_out":"","ref_frames":0,"source":"collection_importer"}

def validated_reference(spec: dict, output: Path, validator: Path) -> dict:
    effect=spec["effect"]
    manifest=Path(spec["manifest"]).resolve(strict=True);checkpoint=Path(spec["checkpoint"]).resolve(strict=True)
    reference_root=Path(spec["reference_root"]).resolve(strict=True);events_path=Path(spec["events"]).resolve(strict=True)
    cmd=[sys.executable,str(validator),"--effect",effect,"--manifest",str(manifest),"--checkpoint",str(checkpoint),
         "--reference-root",str(reference_root),"--events",str(events_path)]
    result=subprocess.run(cmd,capture_output=True,text=True)
    if result.returncode: raise ValueError(f"{effect} trusted package validation failed: {result.stderr.strip()}")
    receipt=json.loads(result.stdout)
    if receipt.get("valid") is not True: raise ValueError(f"{effect} trusted validator did not issue a valid receipt")
    m=json.loads(manifest.read_text());d=m
    slot=1 if effect=="hall" else 2
    profile_name="ROM-01" if effect=="hall" else "ROM-02"
    route=m["serial"]
    events=read_schedule_csv(events_path,int(receipt["run_frame"]))
    schedule=output/f"slot-{slot:02d}-reference-events.tsv";save_schedule(schedule,events)
    base=output/f"slot-{slot:02d}-reference"
    ref_frames=dump_reference_csv(Path(spec["reference_input_csv"]).resolve(strict=True),
        Path(spec["reference_output_csv"]).resolve(strict=True),int(receipt["run_frame"]),base.with_suffix(".in.f32"),base.with_suffix(".out.f32"))
    return {"slot":slot,"name":m["provenance"]["effect_name"],"words":int(m["program"]["active_words"]),
        "end":int(m["program"]["end_word"]),"program_sha":m["program"]["sha256"],
        "rate":float(m["sample_rate_hz"]),"serial":int(route["host_serial"]),
        "input_port":int(route["input_ports"][0]),"output_port":int(route["output_ports"][0]),
        "checkpoint":str(checkpoint),"checkpoint_sha":sha(checkpoint),"manifest":str(manifest),
        "schedule":str(schedule),"ref_in":str(base.with_suffix(".in.f32")),
        "ref_out":str(base.with_suffix(".out.f32")),"ref_frames":ref_frames,
        "source":"independent_reference","receipt":receipt}

def write_inventory(path: Path, packages: list[dict]) -> None:
    fields=("slot","name","words","end","program_sha","rate","serial","input_port","output_port",
            "checkpoint","checkpoint_sha","manifest","schedule","ref_in","ref_out","ref_frames")
    with path.open("w") as stream:
        stream.write("\t".join(("slot","name","words","end","hash","rate","serial","input_port","output_port",
            "checkpoint","checkpoint_sha","manifest","schedule","ref_input","ref_output","ref_frames"))+"\n")
        for p in sorted(packages,key=lambda x:x["slot"]):
            stream.write("\t".join(safe_text(str(p[k])) for k in fields)+"\n")

def schedule_rows(path: str) -> list[tuple[int,int,int]]:
    rows=[]
    if not path: return rows
    with Path(path).open() as stream:
        for line in stream:
            frame,index,value=line.strip().split("\t")
            rows.append((int(frame),int(index),int(value,16)))
    return rows

def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packages",type=Path,required=True,help="directory of Codex 1 collection packages")
    ap.add_argument("--importer",type=Path,help="Codex 1 import_factory_effect_collection.py; omit only to test independent references")
    ap.add_argument("--reference-config",type=Path,help="private JSON config for trusted HALL/ROM-02 references")
    ap.add_argument("--validator",type=Path,default=VALIDATOR)
    ap.add_argument("--output-dir",type=Path,required=True,help="private output directory outside repository and input packages")
    ap.add_argument("--host-rate",type=float,default=48000.0)
    args=ap.parse_args()
    try:
        packages_root=args.packages.resolve(strict=True);out=args.output_dir.resolve()
        repo=ROOT.resolve()
        if out==repo or repo in out.parents: raise ValueError("output directory must be outside the Git checkout")
        if out==packages_root or packages_root in out.parents: raise ValueError("output directory must not be inside package source")
        out.mkdir(parents=True,exist_ok=True)
        slots=[];collection_count=0;captured_count=0
        if args.importer:
            importer=args.importer.resolve(strict=True);audit_path=out/"collection-import-audit.json"
            run=subprocess.run([sys.executable,str(importer),str(packages_root),"--output",str(audit_path)],capture_output=True,text=True)
            if run.returncode: raise ValueError("Codex 1 importer failed: "+run.stderr.strip())
            audit=json.loads(audit_path.read_text());entries=audit.get("slots",[])
            captured_count=len(entries);collection_count=sum(e.get("registry_eligible") is True for e in entries)
            for e in entries:
                p=package_from_importer(e,out)
                if p: slots.append(p)
        independent=[];reference_packages=[]
        if args.reference_config:
            config=json.loads(args.reference_config.read_text())
            for spec in config.get("references",[]):
                try:
                    p=validated_reference(spec,out,args.validator.resolve(strict=True))
                    existing=next((x for x in slots if x["slot"]==p["slot"]),None)
                    if existing:
                        same=(existing["checkpoint_sha"]==p["checkpoint_sha"] and
                              existing["program_sha"]==p["program_sha"] and
                              abs(existing["rate"]-p["rate"])<0.01 and
                              schedule_rows(existing["schedule"])==schedule_rows(p["schedule"]))
                        if same:
                            existing["ref_in"]=p["ref_in"];existing["ref_out"]=p["ref_out"]
                            existing["ref_frames"]=p["ref_frames"]
                        else:
                            reference_packages.append(p)
                        independent.append({"slot":p["slot"],"effect":spec["effect"],"valid":True,
                            "matches_imported_checkpoint":same,"reference_attached":same})
                    else:
                        slots.append(p)
                        independent.append({"slot":p["slot"],"effect":spec["effect"],"valid":True,
                            "matches_imported_checkpoint":False,"reference_attached":True})
                except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
                    independent.append({"effect":spec.get("effect"),"valid":False,"error":str(exc)})
        inventory=out/"accepted-packages.tsv";write_inventory(inventory,slots)
        reference_inventory=out/"independent-reference-packages.tsv";write_inventory(reference_inventory,reference_packages)
        exe=out/"es5510_playback_harness"
        cmd=[os.environ.get("CXX","g++"),"-std=c++17","-O2","-Wall","-Wextra","-Wpedantic",
             "-I"+str(ROOT/"include"),"-I"+str(ROOT/"src"),"-I"+str(ROOT/"force_plugin/src"),
             str(HARNESS_CPP),str(BACKEND_CPP),str(RUNTIME_CPP),str(DSP_CPP),"-pthread","-o",str(exe)]
        built=subprocess.run(cmd,capture_output=True,text=True)
        if built.returncode: raise RuntimeError("native harness build failed:\n"+built.stderr)
        run=subprocess.run([str(exe),str(inventory),str(out),str(args.host_rate),str(reference_inventory)],capture_output=True,text=True)
        if run.returncode: raise RuntimeError("native harness failed:\n"+run.stderr)
        result=json.loads((out/"native-audio-results.json").read_text())
        result["collection_import"]={"captured":captured_count,"registry_eligible":collection_count,
            "blocked_or_unverified":max(0,50-collection_count),"audit":str(out/"collection-import-audit.json") if args.importer else None}
        result["independent_reference_packages"]=independent
        result["counts"]["available_from_collection"]=collection_count
        result["counts"]["available_total_validated"]=result["counts"]["available_validated_packages"]
        result["counts"]["collection_slots_blocked_or_unverified"]=max(0,50-collection_count)
        result_path=out/"asr10-50-effect-audio-report.json"
        result_path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        print(json.dumps({"report":str(result_path),"collection_captured":captured_count,
            "collection_eligible":collection_count,"available_total_validated":result["counts"]["available_validated_packages"],
            "loaded":result["counts"]["loaded"],"finite_effects":result["counts"]["finite_effects"],
            "matched_reference_passes":result["counts"]["matched_reference_passes"],
            "collection_slots_blocked_or_unverified":max(0,50-collection_count)},indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError,RuntimeError) as exc:
        print(f"run_es5510_playback_harness: {exc}",file=sys.stderr);return 2

if __name__=="__main__": raise SystemExit(main())
