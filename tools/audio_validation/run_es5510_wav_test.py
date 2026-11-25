#!/usr/bin/env python3
"""Run WAV tests through a selected, trusted native ES5510 factory package."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--collection",type=Path,required=True,help="private validated-packages collection")
    ap.add_argument("--slot",type=int,required=True)
    ap.add_argument("--input",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True,help="use a private output directory outside Git")
    ap.add_argument("--block",type=int,default=256)
    ap.add_argument("--tail-frames",type=int,default=0)
    ap.add_argument("--bypass-ab",action="store_true",help="export latency-aligned bypass WAV and compare")
    ap.add_argument("--compare",nargs=3,metavar=("PARAMETER_ID","DISPLAY_VALUE","DSP_FRAME"),
                    help="compare package baseline with one verified point")
    ap.add_argument("--event",action="append",default=[],metavar="FRAME:PARAMETER_ID:DISPLAY_VALUE")
    a=ap.parse_args()
    if not 1<=a.slot<=50:raise SystemExit("slot must be 1..50")
    if a.block<1 or a.block>1048576 or a.tail_frames<0:raise SystemExit("invalid block or tail frame count")
    if a.compare and (a.event or a.bypass_ab):raise SystemExit("--compare is a separate two-run mode; do not combine it with --event or --bypass-ab")
    collection=a.collection.resolve(strict=True); source=a.input.resolve(strict=True); out=a.output_dir.resolve()
    if not (collection/"packages").is_dir():raise SystemExit("collection must contain packages/ROM-*/package.json")
    if out==collection or collection in out.parents:raise SystemExit("output directory must not be inside the private collection")
    if out==ROOT or ROOT in out.parents:raise SystemExit("audio, audit, and report outputs must stay outside the Git checkout")
    out.mkdir(parents=True,exist_ok=True)
    audit_path=out/"native-package-audit.json"
    subprocess.run(["python3",str(ROOT/"tools/audio_validation/import_factory_effect_collection.py"),
                    str(collection),"--output",str(audit_path)],cwd=ROOT,check=True)
    audit=json.loads(audit_path.read_text())
    row=next((x for x in audit["slots"] if x.get("slot")==a.slot),None)
    if not row or not row.get("registry_eligible") or not row.get("capture_state_valid"):
        raise SystemExit(f"slot {a.slot} is unavailable: {row.get('quarantine_reason') if row else 'not present'}")
    if not row.get("checkpoint_is_at_run_boundary"):raise SystemExit("selected package is not a validated RUN-boundary checkpoint")
    d=row["descriptor"]
    checkpoint=Path(d["run_checkpoint_path"]).resolve(strict=True)
    schedule=Path(d["firmware_event_schedule_path"]).resolve(strict=True)
    if sha(checkpoint)!=d["run_checkpoint_sha256"]:raise SystemExit("checkpoint SHA-256 changed after package import")
    if sha(schedule)!=d["firmware_event_schedule_sha256"]:raise SystemExit("firmware schedule SHA-256 changed after package import")
    binary=ROOT/"build/audio-test-backend/es5510-wav-test-cli"
    binary.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(["c++","-std=c++17","-O2","-Wall","-Wextra","-Wpedantic",
        "-I"+str(ROOT/"include"),"-I"+str(ROOT/"src"),
        str(ROOT/"tools/audio_validation/es5510_wav_test_cli.cpp"),
        str(ROOT/"src/es5510_audio_test_backend.cpp"),str(ROOT/"src/es5510_factory_runtime.cpp"),
        str(ROOT/"src/es5510.cpp"),str(ROOT/"src/wav_io.cpp"),str(ROOT/"src/experimental_audio_host.cpp"),
        "-o",str(binary)],cwd=ROOT,check=True)
    output=out/f"slot-{a.slot:02d}-processed.wav"
    cmd=[str(binary),str(a.slot),d["factory_name"],str(d["active_program_words"]),d["program_sha256"],
         str(checkpoint),d["run_checkpoint_sha256"],str(d["factory_reference_rate_hz"]),str(schedule),str(source),str(output),
         "--block",str(a.block),"--tail",str(a.tail_frames)]
    for event in a.event:
        parts=event.split(":")
        if len(parts)!=3:raise SystemExit("--event must be FRAME:PARAMETER_ID:DISPLAY_VALUE")
        cmd.extend(["--event",event])
    if a.bypass_ab:
        cmd.extend(["--bypass",str(out/f"slot-{a.slot:02d}-bypass.wav")])
    if a.compare:
        pid,value,frame=a.compare
        cmd.extend(["--compare",pid,value,frame,str(out/f"slot-{a.slot:02d}-{pid}-ab")])
    result=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    print(result.stdout,end="")
    if result.returncode:
        print(result.stderr,end="");raise SystemExit(result.returncode)
    print(f"private_output_dir={out}")

if __name__=="__main__":main()
