#!/usr/bin/env python3
"""Validate every V5 adjacent parameter pair through the native runtime."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audit",type=Path,required=True,help="trusted private collection audit")
    ap.add_argument("--metadata",type=Path,default=ROOT/"docs/ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05.json")
    ap.add_argument("--output",type=Path,required=True,help="private WAV and report directory outside Git")
    ap.add_argument("--binary",type=Path,required=True)
    args=ap.parse_args()
    audit=json.loads(args.audit.resolve(strict=True).read_text())
    rows={x["slot"]:x for x in audit["slots"]}
    metadata=json.loads(args.metadata.resolve(strict=True).read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    binary=args.binary.resolve()
    subprocess.run(["c++","-std=c++17","-O2","-I"+str(ROOT/"include"),"-I"+str(ROOT/"src"),
        str(ROOT/"tools/audio_validation/factory_parameter_audio_compare.cpp"),
        str(ROOT/"src/es5510_factory_runtime.cpp"),str(ROOT/"src/es5510.cpp"),"-o",str(binary)],cwd=ROOT,check=True)
    results=[]
    by_id={}
    for control in metadata["controls"]:
        row=rows.get(control["slot"])
        if not row or not row.get("registry_eligible") or not row.get("capture_state_valid"):
            raise SystemExit(f"slot {control['slot']} is not eligible in the trusted private audit")
        d=row["descriptor"]
        if not row.get("checkpoint_is_at_run_boundary"):
            raise SystemExit(f"slot {control['slot']} checkpoint is not at RUN boundary")
        checkpoint=Path(d["run_checkpoint_path"]).resolve(strict=True)
        schedule=Path(d["firmware_event_schedule_path"]).resolve(strict=True)
        if sha256(checkpoint)!=d["run_checkpoint_sha256"]: raise SystemExit(f"slot {control['slot']} checkpoint hash mismatch")
        if sha256(schedule)!=d["firmware_event_schedule_sha256"]: raise SystemExit(f"slot {control['slot']} schedule hash mismatch")
        a,b=control["verified_points"]
        prefix=args.output/f"slot-{control['slot']:02d}-{control['parameter_id']}"
        cmd=[str(binary),str(control["slot"]),d["factory_name"],str(d["active_program_words"]),
            d["program_sha256"],str(checkpoint),d["run_checkpoint_sha256"],str(d["factory_reference_rate_hz"]),
            str(schedule),control["parameter_id"],str(a["value"]),str(b["value"]),str(prefix)]
        result=subprocess.run(cmd,cwd=ROOT,check=True,text=True,capture_output=True)
        line=result.stdout.strip(); print(line,flush=True)
        fields={}
        for token in line.split():
            if "=" in token:
                key,value=token.split("=",1); fields[key]=value
        if fields.get("finite") != str(65536*2):
            raise SystemExit(f"slot {control['slot']} {control['parameter_id']} produced non-finite or incomplete audio")
        diff=float(fields.get("difference_rms","nan"))
        control["runtime_event_accepted"]=True
        control["audio_status"]="AUDIO_DIFFERENCE_OBSERVED" if diff>0.0 else "NO_DIFFERENCE_WITH_1_36S_STIMULUS"
        control["runtime_ready"]=diff>0.0
        control["native_audio_measurement"]={k:fields[k] for k in
            ("frames","finite","rms_before","rms_after","difference_rms","difference_peak","peak_before","peak_after") if k in fields}
        by_id[(control["slot"],control["parameter_id"])]=control
        results.append({"slot":control["slot"],"parameter_id":control["parameter_id"],
            "point_texts":[a["text"],b["text"]],"render_prefix":str(prefix),"measurement":line})
    report=args.output/"v05-native-audio-validation.json"
    report.write_text(json.dumps({"schema":"trollfx-asr10-v05-native-audio-validation-v1",
        "engine":"native ES5510, experimental 48 kHz", "results":results},indent=2)+"\n")
    args.metadata.write_text(json.dumps(metadata,indent=2,ensure_ascii=False)+"\n")
    print(f"validated_control_pairs={len(results)} report={report}")

if __name__=="__main__": main()
