#!/usr/bin/env python3
"""Reconcile private ordered HALL host commits against captured GPR state.

Value-bearing JSON is written only to an external private output directory.
stdout contains addresses, counts, and verdicts, never register values.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay_hall import extract_load_history  # noqa: E402

CAPTURE_HEADER = 44
PROGRAM_BYTES = 160 * 6
GPR_BYTES = 192 * 3

def u24be(data: bytes, index: int) -> int:
    off=index*3
    return int.from_bytes(data[off:off+3], "big")

def decode_events(path: Path, target_frame: int) -> dict:
    """Keep event coordinates for every GPR write through the target RUN."""
    all_writes=[]; current_tx=[]; last_clear=None; pa4="unknown"; last_run=None
    target_run=None; target_snapshot=None; target_clear=None; target_tx=[]; run_hits=0
    with path.open(newline="") as f:
        for row in csv.reader(f):
            if len(row)<6: continue
            try: event_id,cycles,frame=int(row[0]),int(row[1]),int(row[2])
            except ValueError: continue
            kind=row[5]; extra=row[6:]
            if kind=="PA4" and extra: pa4=extra[0]
            elif kind=="PIPELINE_CLEAR":
                last_clear={"event_id":event_id,"cpu_cycles":cycles,"dsp_frame":frame}
                current_tx=[]
            elif kind=="DSP_RUN":
                if frame==target_frame:
                    run_hits+=1;target_run={"event_id":event_id,"cpu_cycles":cycles,"dsp_frame":frame}
                    target_clear=last_clear
                    target_tx=list(current_tx)
                last_run={"event_id":event_id,"cpu_cycles":cycles,"dsp_frame":frame}
            elif kind=="RUN_SNAPSHOT" and target_run and frame==target_frame:
                target_snapshot={"event_id":event_id,"cpu_cycles":cycles,"dsp_frame":frame}
                break
            if kind not in ("GPR_COMMIT","BOTH_COMMIT"): continue
            fields={}
            for item in extra:
                k,sep,v=item.partition("=")
                if sep: fields[k]=v
            try:
                address=int(fields["index"],16)
                value=int(fields["gpr" if kind=="BOTH_COMMIT" else "value"],16)
            except (KeyError,ValueError): continue
            write={"address":address,"value":value,"commit_kind":kind,"event_id":event_id,
                   "cpu_cycles":cycles,"dsp_frame":frame,"cpu_pc":row[4],"pa4_state":pa4,
                   "last_prior_pipeline_clear":last_clear.copy() if last_clear else None,
                   "last_prior_dsp_run":last_run.copy() if last_run else None}
            all_writes.append(write);current_tx.append(write)
    if run_hits!=1 or target_run is None or target_clear is None:
        raise ValueError("expected one target DSP_RUN preceded by pipeline reset")
    return {"writes":all_writes,"target_transaction_writes":target_tx,
            "target_run":target_run,"target_snapshot_marker":target_snapshot,
            "target_pipeline_clear":target_clear}

def snapshot_gprs(path: Path) -> tuple[bytes,str]:
    raw=path.read_bytes()
    if len(raw)<CAPTURE_HEADER+PROGRAM_BYTES+GPR_BYTES or raw[:8]!=b"ES5510C\0":
        raise ValueError("invalid private ES5510 capture")
    version,header,nins,ngpr,nspecial,ndram,flags,nstate,payload=struct.unpack_from("<9I",raw,8)
    if (version,header,nins,ngpr)!=(1,CAPTURE_HEADER,160,192):
        raise ValueError("unexpected private capture layout")
    gprs=raw[CAPTURE_HEADER+PROGRAM_BYTES:CAPTURE_HEADER+PROGRAM_BYTES+GPR_BYTES]
    return gprs,hashlib.sha256(raw).hexdigest()

def state_after_writes(writes: list[dict], base: list[int] | None=None) -> list[int]:
    state=list(base if base is not None else [0]*192)
    for w in writes:
        if w["address"]<192: state[w["address"]]=w["value"]
    return state

def active_operand_refs(program: bytes, addresses: set[int], words: int) -> dict[int,list[dict]]:
    result={a:[] for a in addresses}
    for i in range(words):
        word=int.from_bytes(program[i*6:i*6+6],"big")
        for field,shift in (("A",16),("B",24),("C",32),("D",40)):
            reg=(word>>shift)&255
            if reg in result: result[reg].append({"instruction":i,"operand":field})
    return result

def reconcile(manifest: Path, captures: list[tuple[str,Path,Path]], output: Path) -> dict:
    doc=json.loads(manifest.read_text()); base=manifest.parent
    gpr_path=(base/doc["gpr"]["path"]).resolve(strict=True)
    program_path=(base/doc["program"]["path"]).resolve(strict=True)
    expected=gpr_path.read_bytes(); program=program_path.read_bytes()
    if hashlib.sha256(expected).hexdigest()!=doc["gpr"]["sha256"]: raise ValueError("manifest GPR digest mismatch")
    if hashlib.sha256(program).hexdigest()!=doc["program"]["sha256"]: raise ValueError("manifest program digest mismatch")
    expected_values=[u24be(expected,i) for i in range(192)]
    capture_results=[]; private_rows=[]
    for label,event_path,snapshot_path in captures:
        events=decode_events(event_path,int(doc["capture"]["run_frame"]))
        snap_bytes,snap_sha=snapshot_gprs(snapshot_path)
        if hashlib.sha256(snap_bytes).hexdigest()!=doc["gpr"]["sha256"]:
            raise ValueError(f"{label}: snapshot GPR state does not match manifest")
        historical=[w for w in events["writes"] if w["event_id"]<events["target_pipeline_clear"]["event_id"]]
        target=events["target_transaction_writes"]
        current_state=state_after_writes(target)
        history_state=state_after_writes(historical+target)
        addresses=[i for i in range(192) if current_state[i]!=expected_values[i]]
        resolved=[i for i in addresses if history_state[i]==expected_values[i]]
        refs=active_operand_refs(program,set(addresses),int(doc["program"]["active_words"]))
        for address in addresses:
            ws=[w for w in events["writes"] if w["address"]==address]
            hws=[w for w in historical if w["address"]==address]
            current_writes=[w for w in target if w["address"]==address]
            private_rows.append({"capture":label,"gpr_address":address,
                "expected_manifest_hex":f"{expected_values[address]:06x}",
                "observed_hall_transaction_only_hex":f"{current_state[address]:06x}",
                "observed_full_history_hex":f"{history_state[address]:06x}",
                "resolved_by_prior_history":history_state[address]==expected_values[address],
                "last_write_before_hall_transaction":hws[-1] if hws else None,
                "writes_from_trace_start_to_checkpoint":ws,
                "writes_in_hall_transaction":current_writes,
                "active_hall_program_operand_references":refs[address]})
        capture_results.append({"capture":label,"snapshot_sha256":snap_sha,
            "event_trace_sha256":hashlib.sha256(event_path.read_bytes()).hexdigest(),
            "manifest_gpr_sha256":hashlib.sha256(expected).hexdigest(),
            "snapshot_equals_manifest":True,"target_run":events["target_run"],
            "snapshot_marker":events["target_snapshot_marker"],
            "pipeline_clear":events["target_pipeline_clear"],
            "target_transaction_gpr_writes":sum(w["commit_kind"] in ("GPR_COMMIT","BOTH_COMMIT") for w in target),
            "historical_gpr_writes":len(historical),"mismatches_without_history":addresses,
            "resolved_by_history":resolved,"unresolved": [i for i in addresses if i not in resolved],
            "all_manifest_gprs_match_full_history":history_state==expected_values})
    addresses=sorted({r["gpr_address"] for r in private_rows})
    table={"schema":"trollfx-asr10-hall-gpr-reconciliation-private-v1",
           "manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),
           "captures":capture_results,"registers":private_rows,
           "active_program_operand_references":active_operand_refs(program,set(addresses),int(doc["program"]["active_words"]))}
    output.mkdir(parents=True,exist_ok=True)
    (output/"gpr-reconciliation.private.json").write_text(json.dumps(table,indent=2)+"\n")
    redacted={"schema":"trollfx-asr10-hall-gpr-reconciliation-summary-v1",
      "mismatch_addresses":[f"0x{x:02x}" for x in addresses],
      "resolved_by_prior_history":sum(all(r["resolved_by_prior_history"] for r in private_rows if r["gpr_address"]==x) for x in addresses),
      "unresolved_after_history":sum(not all(r["resolved_by_prior_history"] for r in private_rows if r["gpr_address"]==x) for x in addresses),
      "capture_count":len(captures),"snapshot_hashes_identical":len({c["snapshot_sha256"] for c in capture_results})==1,
      "manifest_matches_each_snapshot":all(c["snapshot_equals_manifest"] for c in capture_results),
      "value_table_path":str(output/"gpr-reconciliation.private.json"),
      "register_values_disclosed":False}
    (output/"gpr-reconciliation-summary.json").write_text(json.dumps(redacted,indent=2)+"\n")
    return redacted

def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest",type=Path)
    ap.add_argument("--capture",action="append",nargs=3,metavar=("LABEL","EVENTS.csv","SNAPSHOT.esp"),required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    manifest=a.manifest.resolve(strict=True); out=a.out.expanduser().resolve()
    if out==ROOT or ROOT in out.parents: ap.error("value-bearing output must be outside the repository")
    captures=[(label,Path(events).resolve(strict=True),Path(snapshot).resolve(strict=True)) for label,events,snapshot in a.capture]
    try: result=reconcile(manifest,captures,out)
    except (OSError,ValueError,KeyError,struct.error) as exc: ap.error(str(exc))
    print(json.dumps(result,indent=2));return 0

if __name__=="__main__": raise SystemExit(main())
