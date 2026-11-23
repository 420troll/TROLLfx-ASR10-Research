#!/usr/bin/env python3
"""Replay private ROM-01 HALL serial events through the native and MAME engines.

All payloads, streams, engine output and reports must remain outside this checkout.
The public output is a redacted match/blocker summary only.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools/audio_validation/factory_manifest.py"

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def private_ref(base: Path, rel: str) -> Path:
    p = (base / rel).resolve(strict=True)
    if base.resolve() not in p.parents:
        raise ValueError("manifest payload path escapes its private directory")
    return p

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", type=Path, help="complete external factory-state manifest")
    ap.add_argument("--load-events", type=Path, required=True,
                    help="private ordered host-event CSV containing the recorded HALT/load/RUN transaction")
    ap.add_argument("--out", type=Path, required=True, help="private output directory outside this checkout")
    a = ap.parse_args()
    manifest = a.manifest.resolve(strict=True); out = a.out.expanduser().resolve()
    if ROOT == out or ROOT in out.parents:
        ap.error("output must be outside the repository")
    out.mkdir(parents=True, exist_ok=True)
    gate = subprocess.run(["python3", str(VALIDATOR), str(manifest), "--require-replay-ready"],
                          capture_output=True, text=True)
    if gate.returncode:
        raise SystemExit("factory manifest gate failed; payload contents withheld")
    doc = json.loads(manifest.read_text())
    if doc.get("provenance", {}).get("effect_id") != "ROM-01" or doc.get("provenance", {}).get("effect_name") != "HALL REVERB":
        raise SystemExit("manifest is not the verified ROM-01 HALL state")
    base = manifest.parent
    payloads = {k: private_ref(base, doc[k]["path"]) for k in ("program", "gpr", "special_registers")}
    for k,p in payloads.items():
        if digest(p) != doc[k]["sha256"]: raise SystemExit(f"{k} payload digest mismatch")
    cap = doc["capture"]
    streams = {k: private_ref(base, cap[k+"_path"]) for k in ("replay_updates", "replay_io")}
    for k,p in streams.items():
        if digest(p) != cap[k+"_sha256"]: raise SystemExit(f"{k} stream digest mismatch")
    with streams["replay_io"].open(newline="") as f:
        reader=csv.DictReader(f); rows=iter(reader); first=next(rows); count=1
        prev=int(first["frame"])
        if prev != int(cap["run_frame"]): raise SystemExit("serial replay does not start on recorded RUN frame")
        for row in rows:
            frame=int(row["frame"])
            if frame != prev+1: raise SystemExit("serial frame stream has a gap or duplicate")
            prev=frame; count+=1
    if count != int(cap["replay_frames"]): raise SystemExit("serial replay frame count mismatch")
    event_path=a.load_events.resolve(strict=True)
    # The ordered transaction ends at the recorded RUN and starts at its latest
    # pipeline-clear event. CSV rows after the six fixed metadata columns carry
    # the private register/instruction write payloads.
    run_frame=int(cap["run_frame"])
    commits=[]; current=[]; run_count=0
    def payload(field: str, expected_key: str) -> str:
        key,sep,value=field.partition("=")
        if not sep or key != expected_key or not value:
            raise SystemExit("malformed private load commit field")
        return value
    with event_path.open(newline="") as f:
        for r in csv.reader(f):
            if len(r)>5 and r[5]=="PIPELINE_CLEAR": current=[]
            elif len(r)>5 and r[5] in ("GPR_COMMIT","INSTR_COMMIT","BOTH_COMMIT"):
                kind={"GPR_COMMIT":"gpr","INSTR_COMMIT":"instr","BOTH_COMMIT":"both"}[r[5]]
                fields=r[6:]; expected=3 if kind=="both" else 2
                if len(fields)!=expected: raise SystemExit("malformed private load commit event")
                address=payload(fields[0],"index")
                value=payload(fields[1],"word" if kind in ("instr","both") else "value")
                second=payload(fields[2],"gpr") if kind=="both" else "0"
                current.append((kind,address,value,second))
            elif len(r)>5 and r[5]=="DSP_RUN" and r[2]==str(run_frame):
                run_count+=1; commits=list(current)
    if run_count!=1: raise SystemExit("ordered event trace lacks a unique recorded RUN boundary")
    gpr_count=sum(kind in ("gpr","both") for kind,*_ in commits)
    instr_count=sum(kind in ("instr","both") for kind,*_ in commits)
    if gpr_count!=342 or instr_count!=89:
        raise SystemExit("ordered HALT/load/RUN transaction does not contain the verified 342 GPR/SPR and 89 instruction commits")
    registers=[0]*256; registers[252]=0xffffff; registers[253]=0x800000; registers[254]=0x7fffff
    instructions=[0]*160
    for kind,address,value,second in commits:
        aidx=int(address,16)
        if kind=="gpr": registers[aidx]=int(value,16)
        elif kind=="instr": instructions[aidx]=int(value,16)
        else: registers[aidx]=int(second,16); instructions[aidx]=int(value,16)
    expected_program=payloads["program"].read_bytes()
    if any(instructions[i] != int.from_bytes(expected_program[i*6:(i+1)*6],"big") for i in range(89)):
        raise SystemExit("ordered instruction commits do not reproduce the gated program payload")
    expected_gpr=payloads["gpr"].read_bytes(); expected_spr=payloads["special_registers"].read_bytes()
    gpr_mismatches=sum(registers[i] != int.from_bytes(expected_gpr[i*3:(i+1)*3],"big") for i in range(192))
    spr_mismatches=sum(registers[234+i] != int.from_bytes(expected_spr[i*3:(i+1)*3],"big") for i in range(22))
    if gpr_mismatches or spr_mismatches:
        raise SystemExit(f"state gate failed before audio comparison: ordered commits disagree with final payloads at {gpr_mismatches} GPRs and {spr_mismatches} SPRs")
    load_commits=out/"private-load-commits.csv"
    with load_commits.open("w",newline="") as f:
        w=csv.writer(f);w.writerow(("kind","address","value","second_value"));w.writerows(commits)
    exe=out/"hall-replay"
    sources=[ROOT/"src/es5510.cpp",ROOT/"third_party/trollfx_mame_es5510/mame_es5510_standalone.cpp",
             ROOT/"tools/audio_validation/hall_replay.cpp"]
    subprocess.run(["c++","-std=c++17","-O2","-Isrc","-Ithird_party/trollfx_mame_es5510",
                    *map(str,sources),"-o",str(exe)],cwd=ROOT,check=True)
    result=out/"engine-comparison.csv"
    subprocess.run([str(exe),str(load_commits),str(streams["replay_updates"]),str(streams["replay_io"]),str(result)],check=True)
    first={"native":None,"mame":None}; mismatches={"native":0,"mame":0}; engine_differences=0; compared=0
    with result.open(newline="") as f:
        for row in csv.DictReader(f):
            compared+=1
            for engine in ("native","mame"):
                for p in range(4):
                    for c in ("l","r"):
                        field=f"{engine}{p}{c}"
                        if row[field] != row[f"recorded{p}{c}"]:
                            mismatches[engine]+=1
                            if first[engine] is None: first[engine]={"frame":int(row["frame"]),"serial_lane":f"SER{p}{c.upper()}"}
            for p in range(4):
                for c in ("l","r"):
                    engine_differences += row[f"native{p}{c}"] != row[f"mame{p}{c}"]
    ref_valid = mismatches["native"] == 0
    summary={"schema":"trollfx-es5510-hall-replay-result-v1","effect":"ROM-01 HALL REVERB",
             "os_version":doc["provenance"]["os_version"],"manifest_sha256":digest(manifest),
             "replay_start_frame":int(cap["run_frame"]),"replay_frames":compared,
             "input_sample_rate_hz":doc["audio_clock"]["esp_frame_rate_hz"],
             "host_output_rate_hz":doc["audio_clock"]["output_rate_hz"],
             "host_serial":doc["serial"]["host_serial"],"halted_gpr_spr_commits":gpr_count,
             "halted_instruction_commits":instr_count,"load_commit_stream_sha256":digest(load_commits),
             "ordered_update_count":int(cap["replay_update_count"]),
             "native_mame_agree":engine_differences==0,"native_mame_differing_samples":engine_differences,
             "os_comparison_valid":ref_valid,
             "earliest_verified_blocker":None if ref_valid else "native replay output diverges from the OS serial reference; initialization/input alignment is not established",
             "engines":{"native":{"matches_os_reference":mismatches["native"]==0,"mismatching_samples":mismatches["native"],"first_divergence":first["native"]},
                        "mame":{"matches_os_reference":mismatches["mame"]==0,"mismatching_samples":mismatches["mame"],"first_divergence":first["mame"]}},
             "outputs_private":True,"payload_values_disclosed":False}
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
