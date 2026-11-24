#!/usr/bin/env python3
"""Replay verified HALL RUN-boundary captures through both standalone engines.

Private OS captures, host event logs, sample data, and replay traces must remain
outside this checkout. The state gate checks the captured RUN image against the
separate cold-load manifest; it never writes expected manifest values into an
engine.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
import esp_capture
from replay_hall import extract_load_history

VERIFY_PATH = ROOT / "tools/audio_validation/hall_replay_verify.py"
CAPTURE_TOOL = ROOT / "tools/audio_validation/capture_hall_reference.py"
FRAME_RE = re.compile(r"ESPPFRAME kind=(input|output) index=(\d+) frame=(\d+) cycles=(\d+) host_pc=([0-9a-fA-F]+) serial=([0-9a-fA-F]+) lanes=([0-9a-fA-F,]+)")
PHASE_RE = re.compile(r"ESPPHASE kind=([a-z0-9_]+)\s+(.*)$")
HOST_GPR_RE = re.compile(r"ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-fA-F]+) gpr ([0-9a-fA-F]+) <- ([0-9a-fA-F]+)")
WINDOWS = (256, 4096, 32768)
DSPRATE = 29761.89453125
HOSTRATE = 44100


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def private_child(base: Path, rel: str) -> Path:
    p = (base / rel).resolve(strict=True)
    if base.resolve() not in p.parents:
        raise ValueError("manifest path escapes its private directory")
    return p


def parse_bundle(run_dir: Path, start: int, frame_count: int) -> dict:
    metadata = json.loads((run_dir / "capture-metadata.json").read_text())
    log_path = run_dir / "session.log"
    phases, samples, writes = [], [], []
    run_seq = None
    with log_path.open(errors="replace") as f:
        for line_no, line in enumerate(f, 1):
            pm = PHASE_RE.search(line)
            if pm:
                fields = dict(re.findall(r"([a-z_]+)=([^\s]+)", pm.group(2)))
                fields.update(kind=pm.group(1), log_sequence=line_no)
                if fields["kind"] == "run_start" and int(fields.get("frame", -1)) == start:
                    run_seq = line_no
                if fields["kind"] in ("pa4_halt_assert", "host_halt_pipeline_reset", "host_dram_clear",
                                      "instruction_upload_start", "program_upload_summary", "pa4_run_release",
                                      "run_start", "run_snapshot", "first_instruction"):
                    phases.append(fields)
            fm = FRAME_RE.search(line)
            if fm:
                kind, idx, frame, cycles, pc, serial, lanes = fm.groups()
                frame = int(frame)
                if start <= frame < start + frame_count:
                    raw = [int(x, 16) for x in lanes.split(",")]
                    if len(raw) != 8:
                        raise ValueError("serial frame does not contain eight lanes")
                    lanes_s16 = [v - 65536 if v & 0x8000 else v for v in raw]
                    samples.append({"kind": kind, "index": int(idx), "frame": frame,
                                    "cycles": int(cycles), "host_pc": pc.lower(),
                                    "serial": serial.lower(), "lanes": lanes_s16,
                                    "log_sequence": line_no})
            if run_seq is not None and line_no > run_seq:
                hm = HOST_GPR_RE.search(line)
                if hm:
                    eid, cycles, frame, pc, address, value = hm.groups()
                    writes.append({"event_id": int(eid), "cycles": int(cycles), "dsp_frame": int(frame),
                                   "host_pc": pc.lower(), "index": int(address, 16),
                                   "value": int(value, 16), "log_sequence": line_no})
    inputs = [x for x in samples if x["kind"] == "input"]
    outputs = [x for x in samples if x["kind"] == "output"]
    expected = list(range(start, start + frame_count))
    if [x["frame"] for x in inputs] != expected or [x["frame"] for x in outputs] != expected:
        raise ValueError("private serial capture is incomplete or out of order")
    phase = lambda kind: [x for x in phases if x["kind"] == kind and int(x.get("frame", -1)) == start]
    snaps, starts, firsts = phase("run_snapshot"), phase("run_start"), phase("first_instruction")
    if len(snaps) != 1 or len(starts) != 1 or len(firsts) != 1:
        raise ValueError("selected RUN must have unique start, snapshot, and first-instruction events")
    first_input = inputs[0]
    if not snaps[0]["log_sequence"] < first_input["log_sequence"] < firsts[0]["log_sequence"] < outputs[0]["log_sequence"]:
        raise ValueError("RUN snapshot/input/first-instruction/output event order is not verified")
    resets = [x for x in phases if x["kind"] == "host_halt_pipeline_reset" and int(x.get("frame", -1)) <= start and x["log_sequence"] < starts[0]["log_sequence"]]
    if not resets:
        raise ValueError("no HALT pipeline-reset acknowledgement precedes RUN")
    if int(metadata["firmware_load"]["instruction_commits"]) != 89 or int(metadata["firmware_load"]["gpr_spr_commit_count"]) != 342:
        raise ValueError("RUN bundle does not carry the measured 89/342 factory transaction")
    if int(metadata["timeline"][-1].get("frame", start)) != start:
        raise ValueError("selected capture timeline does not end on the configured RUN frame")
    inputs_by_frame = {x["frame"]: x for x in inputs}
    outputs_by_seq = sorted(outputs, key=lambda x: x["log_sequence"])
    scheduled = []
    for w in writes:
        later_inputs = [x for x in inputs if x["log_sequence"] > w["log_sequence"]]
        earlier_outputs = [x for x in outputs_by_seq if x["log_sequence"] < w["log_sequence"]]
        if not later_inputs or not earlier_outputs:
            raise ValueError("post-RUN host write is not bounded between serial frames")
        before = later_inputs[0]
        after = earlier_outputs[-1]
        if before["frame"] != after["frame"] + 1:
            raise ValueError("post-RUN host write falls inside a DSP frame; no instruction boundary is recorded")
        if not after["log_sequence"] < w["log_sequence"] < before["log_sequence"]:
            raise ValueError("post-RUN host write ordering cannot be assigned to a between-frame boundary")
        scheduled.append({**w, "boundary_frame": before["frame"]})
    scheduled.sort(key=lambda x: x["log_sequence"])
    return {"metadata": metadata, "inputs": inputs, "outputs": outputs,
            "writes": scheduled, "phases": phases, "snapshot_path": run_dir / "snapshots" / f"run-frame-{start}.esp"}


def validate_checkpoint(a: dict, b: dict, manifest_path: Path, gpr_table_path: Path,
                        reference_root: Path, load_events_path: Path) -> dict:
    if a["metadata"]["replay"] != b["metadata"]["replay"]:
        raise ValueError("fresh reference boots disagree on input, RUN state, firmware load, or alignment")
    if a["inputs"] != b["inputs"] or a["outputs"] != b["outputs"]:
        raise ValueError("fresh OS reference serial event traces differ")
    if digest(a["snapshot_path"]) != a["metadata"]["replay"]["initial_state_sha256"] or digest(b["snapshot_path"]) != a["metadata"]["replay"]["initial_state_sha256"]:
        raise ValueError("fresh RUN snapshots do not match the recorded initial-state digest")
    if a["metadata"]["replay"]["initial_state_sha256"] != b["metadata"]["replay"]["initial_state_sha256"]:
        raise ValueError("fresh RUN checkpoint hashes differ")
    ma = esp_capture.read_capture(a["snapshot_path"])
    mb = esp_capture.read_capture(b["snapshot_path"])
    manifest = json.loads(manifest_path.read_text())
    base = manifest_path.resolve(strict=True).parent
    program = private_child(base,manifest["program"]["path"]).read_bytes()
    historical, commits = extract_load_history(load_events_path.resolve(strict=True), int(manifest["capture"]["run_frame"]))
    halted_gprs=sum(kind in ("gpr","both") for kind,*_ in commits)
    halted_instr=sum(kind in ("instr","both") for kind,*_ in commits)
    if halted_gprs != 342 or halted_instr != 89:
        raise ValueError("ordered load trace does not contain the verified 342/89 halted commit sequence")
    reconstructed_instr=[0]*160
    for kind,address,value,second in commits:
        if kind in ("instr","both"):
            reconstructed_instr[int(address,16)]=int(value,16)
    if any(reconstructed_instr[i] != int.from_bytes(program[i*6:(i+1)*6],"big") for i in range(89)):
        raise ValueError("ordered halted instruction commits do not reproduce the manifest program")
    for cap, label in ((ma, "boot A"), (mb, "boot B")):
        for section, actual_key in (("program", "active_program_sha256"), ("gpr", "gpr_sha256"), ("special_registers", "special_sha256")):
            expected = manifest[section]["sha256"]
            actual = cap["program"][actual_key] if section == "program" else cap["registers"][actual_key]
            payload = private_child(base, manifest[section]["path"])
            if digest(payload) != expected or actual != expected:
                raise ValueError(f"{label} RUN checkpoint {section} does not match validated manifest")
        rt = cap["runtime"]
        mem = manifest["memory"]
        for key in ("memsiz", "memmask", "memincrement", "memshift"):
            if int(rt["memory_configuration"][key]) != int(mem[key]):
                raise ValueError(f"{label} RUN checkpoint memory configuration mismatch")
        for reg, field in (("DLENGTH", "dlength"), ("ABASE", "abase"), ("BBASE", "bbase"), ("DBASE", "dbase"), ("SIGREG", "sigreg")):
            if int(rt["delay_configuration" if reg in ("DLENGTH", "ABASE", "BBASE", "DBASE") else "signal_configuration"][reg]) != int(mem[field]):
                raise ValueError(f"{label} RUN checkpoint {reg} mismatch")
        if rt["dram_nonzero_words"] != 0 or manifest["dram"]["mode"] != "zeroed":
            raise ValueError(f"{label} RUN checkpoint DRAM does not match zeroed manifest")
        if rt["control"]["host_serial"] != int(manifest["serial"]["host_serial"]):
            raise ValueError(f"{label} RUN checkpoint serial mode mismatch")
        if float(a["metadata"]["dsp_rate_hz"]) != DSPRATE or int(a["metadata"]["host_rate_hz"]) != HOSTRATE:
            raise ValueError("reference capture clock domains do not match the required DSP/host rates")
        if a["metadata"]["clock"]["serial_route"] != "-1,-1,1,-1":
            raise ValueError("reference serial route does not match the measured HALL route")
        if rt["control"]["halted"] or rt["control"]["pc"] != 0:
            raise ValueError(f"{label} checkpoint is not positioned at the first RUN instruction")
    for bundle in (a, b):
        if not bundle["metadata"]["initial_state"]["pipeline"]["halt_reset_acknowledged"]:
            raise ValueError("RUN boundary is missing measured HALT pipeline-reset acknowledgement")
    table = json.loads(gpr_table_path.resolve(strict=True).read_text())
    manifest_gpr_sha=digest(private_child(base,manifest["gpr"]["path"]))
    if len(table.get("captures",[])) != 2 or any(not x["all_manifest_gprs_match_full_history"] or
           x["manifest_gpr_sha256"] != manifest_gpr_sha for x in table["captures"]):
        raise ValueError("GPR history table does not verify the current manifest payload in both captures")
    gpr_rows = [r for r in table["registers"] if r["capture"] == "fresh-2020"]
    if len(gpr_rows) != 16 or sum(bool(r["resolved_by_prior_history"]) for r in gpr_rows) != 16:
        raise ValueError("the established 16-address prior GPR history is not fully resolved")
    if len(a["writes"]) != 213 or a["writes"] != b["writes"]:
        raise ValueError("fresh reference boots disagree on the 213 post-RUN host writes")
    for count in WINDOWS:
        ref_path=reference_root/"boot-a"/f"reference-{count}.json"
        ref_meta=a["metadata"].get("reference_traces",{}).get(str(count),{})
        if not ref_meta or digest(ref_path) != ref_meta.get("sha256"):
            raise ValueError("reference trace digest does not match its capture metadata")
        reference=json.loads(ref_path.read_text())
        if reference.get("replay",{}).get("initial_state_sha256") != a["metadata"]["replay"]["initial_state_sha256"]:
            raise ValueError("sample reference trace does not use the verified RUN checkpoint")
        if len(reference.get("dsp_serial_samples",[])) != count or len(reference.get("input_samples",[])) != count:
            raise ValueError("sample reference trace has incomplete frame coverage")
    first = a["inputs"][0]["lanes"]
    serial = ma["runtime"]["serial_samples"]
    if serial != first:
        raise ValueError("RUN checkpoint serial latches do not equal the captured first input state")
    sp = ma["runtime"]["special_registers"]
    if sp["SER2R"] != ((first[5] & 0xffff) << 8) or sp["SER2L"] != ((first[4] & 0xffff) << 8):
        raise ValueError("SER2 SPR aliases disagree with first-frame serial input latches")
    return {"checkpoint_sha256": a["metadata"]["replay"]["initial_state_sha256"],
            "program_matches_manifest": True, "all_192_gprs_match_manifest": True,
            "all_22_sprs_match_manifest": True, "dram_zeroed": True,
            "pipeline_reset_acknowledged": True, "first_input_preloaded_in_serial_state": True,
            "historical_gpr_addresses_resolved": 16, "halted_register_commits": halted_gprs,
            "halted_instruction_commits": halted_instr, "post_run_write_count": 213}


def build_private_register_table(bundle: dict, manifest_path: Path, gpr_table_path: Path,
                                 load_events_path: Path, out_path: Path) -> None:
    manifest=json.loads(manifest_path.read_text()); base=manifest_path.resolve().parent
    gpr_payload=private_child(base,manifest["gpr"]["path"]).read_bytes()
    spr_payload=private_child(base,manifest["special_registers"]["path"]).read_bytes()
    program=private_child(base,manifest["program"]["path"]).read_bytes()
    history,commits=extract_load_history(load_events_path.resolve(strict=True),int(manifest["capture"]["run_frame"]))
    full=[0]*256; full[252:255]=[0xffffff,0x800000,0x7fffff]
    for kind,address,value,second in history:
        if kind=="seed_gpr":full[int(address,16)]=int(value,16)
    for kind,address,value,second in commits:
        i=int(address,16)
        if kind in ("gpr","both"):full[i]=int(second if kind=="both" else value,16)
        if kind in ("instr","both"):pass
    private_gpr=json.loads(gpr_table_path.read_text())
    selected={r["gpr_address"]:r for r in private_gpr["registers"] if r["capture"]=="fresh-2020"}
    raw=bundle["snapshot_path"].read_bytes();gpr_start=44+160*6;spr_start=gpr_start+192*3
    rows=[]
    for address,r in sorted(selected.items()):
        observed=int.from_bytes(raw[gpr_start+address*3:gpr_start+address*3+3],"big")
        rows.append({"address":f"0x{address:02X}","symbolic_name":f"GPR{address:02X}",
                     "expected_manifest":r["expected_manifest_hex"],
                     "transaction_only":r["observed_hall_transaction_only_hex"],
                     "reconstructed_from_recorded_history":r["observed_full_history_hex"],
                     "run_boundary_snapshot":f"{observed:06X}",
                     "last_firmware_write":r["last_write_before_hall_transaction"],
                     "execution_frame":855973,"instruction_boundary":"RUN snapshot before first instruction",
                     "implicit_hardware_update":None,
                     "root_cause":"prior halted BOTH_COMMIT state survives HALT and pipeline reset",
                     "resolved_at_run_boundary":observed==int(r["expected_manifest_hex"],16) and full[address]==observed})
    names={0xEE:"SER2R",0xEF:"SER2L",0xF3:"MACH",0xF4:"DIL",0xF8:"DBASE",0xF9:"SIGREG",0xFA:"CCR"}
    runtime=esp_capture.read_capture(bundle["snapshot_path"])["runtime"]
    observed_by_address={0xEE:runtime["special_registers"]["SER2R"],0xEF:runtime["special_registers"]["SER2L"],
                         0xF3:runtime["special_registers"]["MACHL_HI"],0xF4:runtime["special_registers"]["DIL"],
                         0xF8:runtime["special_registers"]["DBASE"],0xF9:runtime["special_registers"]["SIGREG"],
                         0xFA:runtime["special_registers"]["CCR"]}
    implicit={0xEE:"SER2 input latch contains first captured input before RUN snapshot",
              0xEF:"SER2 input latch contains first captured input before RUN snapshot",
              0xF3:"live MAC high word captured at RUN boundary",
              0xF4:"live delayed input readback; F4 host write configures memory",
              0xF8:"live delay base pointer captured at RUN boundary",
              0xF9:"retained startup SIGREG configuration",
              0xFA:"live condition flags captured at RUN boundary"}
    last={}
    with load_events_path.resolve(strict=True).open(newline="") as f:
        for event in csv.reader(f):
            if len(event)<6 or not event[0].isdigit():continue
            if event[5]=="DSP_RUN" and int(event[2])==855973:break
            if event[5] not in ("GPR_COMMIT","BOTH_COMMIT"):continue
            fields=dict(x.split("=",1) for x in event[6:] if "=" in x)
            try: addr=int(fields["index"],16)
            except (KeyError,ValueError):continue
            if addr in names:
                last[addr]={"event_id":int(event[0]),"cpu_cycles":int(event[1]),
                            "dsp_frame":int(event[2]),"host_pc":event[4],"kind":event[5]}
    spr_offsets={a:a-234 for a in names}
    for address,name in names.items():
        expected=int.from_bytes(spr_payload[spr_offsets[address]*3:spr_offsets[address]*3+3],"big")
        snapshot=observed_by_address[address]
        rows.append({"address":f"0x{address:02X}","symbolic_name":name,
                     "expected_manifest":f"{expected:06X}","transaction_only":"000000",
                     "reconstructed_from_recorded_history":f"{full[address]:06X}",
                     "run_boundary_snapshot":f"{snapshot:06X}","last_firmware_write":last.get(address),
                     "execution_frame":855973,"instruction_boundary":"RUN snapshot before first instruction",
                     "implicit_hardware_update":implicit[address],
                     "root_cause":"live/retained SPR state was absent from transaction-only reconstruction",
                     "resolved_at_run_boundary":snapshot==expected})
    result={"schema":"trollfx-asr10-hall-register-reconciliation-v4-private-v1",
            "run_boundary_frame":855973,"ordered_halted_program_words":89,
            "ordered_halted_register_commits":342,"registers":sorted(rows,key=lambda r:int(r["address"],16)),
            "values_private":True}
    out_path.write_text(json.dumps(result,indent=2)+"\n")


def write_private_inputs(bundle: dict, frames: int, out: Path) -> tuple[Path, Path, list[dict]]:
    selected_inputs = bundle["inputs"][:frames]
    selected_outputs = bundle["outputs"][:frames]
    max_frame = selected_inputs[-1]["frame"]
    updates = [w for w in bundle["writes"] if w["boundary_frame"] <= max_frame]
    update_path, io_path = out / "scheduled-firmware-writes.csv", out / "serial-io.csv"
    with update_path.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(("boundary_frame", "event_id", "cpu_cycles", "dsp_frame", "host_pc", "index", "value"))
        for e in updates:
            w.writerow((e["boundary_frame"], e["event_id"], e["cycles"], e["dsp_frame"], e["host_pc"], f'{e["index"]:02x}', f'{e["value"]:06x}'))
    with io_path.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(("frame", "cycles", "host_pc", *[f"lane{i}" for i in range(8)], "reference_left", "reference_right"))
        for x,y in zip(selected_inputs,selected_outputs):
            w.writerow((x["frame"], x["cycles"], x["host_pc"], *x["lanes"], y["lanes"][2], y["lanes"][3]))
    return update_path, io_path, updates


def make_trace(path: Path, trace_id: str, metadata: dict, replay_gate: dict, rows: list[dict], outputs: list[tuple[int,int]]) -> None:
    trace={"schema":"trollfx-es5510-hall-replay-v1","trace_id":trace_id,
           "replay":replay_gate,"dsp_rate_hz":DSPRATE,"host_rate_hz":HOSTRATE,
           "dsp_serial_samples":[{"index":i,"left":x[0],"right":x[1]} for i,x in enumerate(outputs)],
           "input_samples":[{"index":i,"left":r["lanes"][4],"right":r["lanes"][5]} for i,r in enumerate(rows)],
           "metadata":{"absolute_start_frame":rows[0]["frame"],"frame_count":len(rows),
                       "initial_state":metadata["initial_state"],"firmware_load":metadata["firmware_load"],
                       "stimulus":metadata["stimulus"],"host_output":metadata["host_output"]}}
    path.write_text(json.dumps(trace,separators=(",",":"))+"\n")


def compare_all_lanes(path: Path, expected: list[dict]) -> dict:
    mismatch=0; first=None; frames=0
    with path.open(newline="") as f:
        for row,ref in zip(csv.DictReader(f),expected):
            frames+=1
            for engine in ("native","mame"):
                for lane in range(8):
                    if int(row[f"{engine}{lane}"]) != ref["lanes"][lane]:
                        mismatch+=1
                        if first is None:first={"frame":ref["frame"],"sample_index":frames-1,"engine":engine,"serial_lane":lane}
    return {"compared_frames":frames,"mismatching_lane_samples":mismatch,"first_divergence":first}


def compare_instruction_traces(native_path: Path, mame_path: Path, absolute_frame: int) -> dict:
    """Compare first-instruction diagnostic CSVs without treating native DIL's
    private operand shadow (GPR 0x100) as an architectural register write."""
    def rows(path):
        result=[]
        for line in path.read_text().splitlines():
            fields=line.split(",")
            if fields[0]=="W" and len(fields)>3 and fields[3]=="100":
                continue
            result.append(fields)
        return result
    left,right=rows(native_path),rows(mame_path)
    for pos in range(max(len(left),len(right))):
        a=left[pos] if pos<len(left) else None; b=right[pos] if pos<len(right) else None
        if a==b: continue
        sample=a or b
        kind=sample[0] if sample else "missing_event"
        pc=sample[2] if sample and len(sample)>2 else None
        diffs=[]
        if a is not None and b is not None:
            diffs=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
        field="event_presence"
        if kind=="RQ" and 5 in diffs: field="ram_request_address"
        elif kind=="RR" and 4 in diffs: field="ram_read_address"
        elif kind=="RR" and 5 in diffs: field="ram_read_data"
        elif kind=="I" and 3 in diffs: field="instruction_word"
        elif kind=="W" and 3 in diffs: field="register_index"
        elif kind=="W" and 4 in diffs: field="register_value"
        elif kind=="RW": field="ram_write_event"
        return {"status":"diverged","absolute_dsp_frame":absolute_frame,
                "event_ordinal":pos,"event_type":kind,"program_counter":pc,"field":field,
                "native_event_count":len(left),"mame_event_count":len(right),
                "native_dil_shadow_writes_excluded":True}
    return {"status":"exact","native_event_count":len(left),"mame_event_count":len(right),
            "native_dil_shadow_writes_excluded":True}


def analyze_instruction_traces(native_path: Path, mame_path: Path, out_dir: Path) -> dict:
    analyzer_path=ROOT/"tools/divergence/analyzer.py"
    spec=importlib.util.spec_from_file_location("hall_divergence_analyzer",analyzer_path)
    analyzer=importlib.util.module_from_spec(spec);spec.loader.exec_module(analyzer)
    filtered=[]
    for source,name in ((native_path,"native"),(mame_path,"mame")):
        dest=out_dir/f"first-divergence.{name}.filtered.csv"
        lines=[]
        for line in source.read_text().splitlines():
            z=line.split(",")
            if z[0]=="W" and len(z)>3 and z[3]=="100":continue
            lines.append(line)
        dest.write_text("\n".join(lines)+"\n");filtered.append(dest)
    left=analyzer.import_csv(filtered[0],"native-first-frame","trollfx-native",29762,
                             "ES5510 instruction index within absolute diagnostic frame",DSPRATE)
    right=analyzer.import_csv(filtered[1],"mame-first-frame","mame-derived",29762,
                              "ES5510 instruction index within absolute diagnostic frame",DSPRATE)
    report=analyzer.compare(left,right)
    first=report.get("earliest_confirmed_divergence") or {}
    return {"classification":report.get("classification"),"category":first.get("category"),
            "event_type":first.get("event_type"),"frame_index_within_trace":first.get("frame"),
            "instruction_index":first.get("instruction_index"),
            "differing_fields":sorted(first.get("differing_fields",{})),
            "native_dil_shadow_writes_excluded":True}


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest",type=Path)
    ap.add_argument("gpr_table",type=Path)
    ap.add_argument("load_events",type=Path,help="private ordered HALL HALT/load/RUN event CSV")
    ap.add_argument("reference_root",type=Path,help="private two-boot capture directory")
    ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--diagnostic-frame",type=int,help="absolute DSP frame for one-frame native/MAME instruction tracing")
    args=ap.parse_args(); out=args.out.expanduser().resolve()
    if out==ROOT or ROOT in out.parents: ap.error("all replay output must remain outside this checkout")
    out.mkdir(parents=True,exist_ok=True)
    gate=subprocess.run([sys.executable,str(ROOT/"tools/audio_validation/factory_manifest.py"),str(args.manifest),"--require-replay-ready"],capture_output=True,text=True)
    if gate.returncode: raise SystemExit("factory manifest validation failed")
    bundles=[parse_bundle(args.reference_root/f"boot-{x}",855973,32768) for x in ("a","b")]
    state_gate=validate_checkpoint(*bundles,args.manifest,args.gpr_table,args.reference_root,args.load_events)
    build_private_register_table(bundles[0],args.manifest,args.gpr_table,args.load_events,out/"register-reconciliation.private.json")
    # The input and startup-event fingerprints are captured identically by both boots.
    meta=bundles[0]["metadata"]; refmeta=meta["replay"]
    startup_hash=refmeta["firmware_events_sha256"]
    scheduler_lines=[f'{e["event_id"]}:{e["cycles"]}:{e["dsp_frame"]}:{e["host_pc"]}:{e["index"]:02x}:{e["value"]:06x}:{e["boundary_frame"]}' for e in bundles[0]["writes"]]
    full_events_sha=sha((startup_hash+"\n"+"\n".join(scheduler_lines)+"\n").encode())
    exe=out/"hall-boundary-replay"
    sources=[ROOT/"src/es5510.cpp",ROOT/"third_party/trollfx_mame_es5510/mame_es5510_standalone.cpp",ROOT/"tools/audio_validation/factory_boundary_replay.cpp"]
    subprocess.run(["c++","-std=c++17","-O2","-Isrc","-Ithird_party/trollfx_mame_es5510",*map(str,sources),"-o",str(exe)],cwd=ROOT,check=True)
    verify_spec=importlib.util.spec_from_file_location("hall_replay_verify",VERIFY_PATH)
    verifier=importlib.util.module_from_spec(verify_spec);verify_spec.loader.exec_module(verifier)
    results={}; eligible_continue=True; first_actual=None
    for n in WINDOWS:
        if not eligible_continue: results[str(n)]={"status":"not_run","reason":"shorter window was not sample-exact"}; continue
        run_dir=out/str(n);run_dir.mkdir(exist_ok=True)
        updates,io,selected_updates=write_private_inputs(bundles[0],n,run_dir)
        output=run_dir/"engine-serial.csv"
        state_checks=run_dir/"register-state-boundaries.csv"
        command=[str(exe),str(bundles[0]["snapshot_path"]),str(updates),str(io),str(output),str(state_checks)]
        if args.diagnostic_frame is not None and n==32768:
            trace_prefix=str(run_dir/"first-divergence")
            command.extend([str(args.diagnostic_frame),trace_prefix])
        proc=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        if proc.returncode:
            raise SystemExit("standalone replay runner failed: "+proc.stderr.strip())
        replay_rows=bundles[0]["inputs"][:n]
        with output.open(newline="") as f: engine_rows=list(csv.DictReader(f))
        native=[];mame=[];all_mismatch=0;all_first=None
        for idx,(r,ref) in enumerate(zip(engine_rows,bundles[0]["outputs"][:n])):
            nl=[int(r[f"native{i}"]) for i in range(8)]; ml=[int(r[f"mame{i}"]) for i in range(8)]
            native.append((nl[2],nl[3]));mame.append((ml[2],ml[3]))
            for i,(x,y) in enumerate(zip(nl,ml)):
                if x!=y:
                    all_mismatch+=1
                    if all_first is None:all_first={"sample_index":idx,"absolute_frame":ref["frame"],"serial_lane":i}
        input_bytes=b"".join(struct.pack("<hh",r["lanes"][4],r["lanes"][5]) for r in replay_rows)
        replay_gate={"input_sha256":sha(input_bytes),"initial_state_sha256":refmeta["initial_state_sha256"],
                     "firmware_events_sha256":full_events_sha,"alignment":refmeta["alignment"]}
        ref_path=args.reference_root/"boot-a"/f"reference-{n}.json"
        ref_trace=json.loads(ref_path.read_text()); ref_trace["replay"]=replay_gate
        normalized_ref=run_dir/"os-reference.json"; normalized_ref.write_text(json.dumps(ref_trace,separators=(",",":"))+"\n")
        for engine,samples in (("native",native),("mame",mame)):
            trace=run_dir/f"{engine}.json";make_trace(trace,f"hall-{engine}-{n}",meta,replay_gate,replay_rows,samples)
        native_vs_os=verifier.verify(normalized_ref,run_dir/"native.json")
        mame_vs_os=verifier.verify(normalized_ref,run_dir/"mame.json")
        native_vs_mame=verifier.verify(run_dir/"native.json",run_dir/"mame.json")
        n_exact=native_vs_os["factory_windows"][str(n)]["samples_equal"]
        m_exact=mame_vs_os["factory_windows"][str(n)]["samples_equal"]
        em_exact=native_vs_mame["factory_windows"][str(n)]["samples_equal"]
        windows={str(n):n_exact}
        windows_m={str(n):m_exact}
        result={"frames":n,"scheduled_updates_applied":len(selected_updates),"native_matches_os":n_exact,
                "mame_matches_os":m_exact,"native_matches_mame":em_exact,
                "native_mame_mismatching_lane_samples":all_mismatch,"native_mame_first_divergence":all_first,
                "native_os_windows":windows,"mame_os_windows":windows_m,
                "native_os_first_difference":native_vs_os["factory_windows"].get(str(n),{}).get("first_difference"),
                "mame_os_first_difference":mame_vs_os["factory_windows"].get(str(n),{}).get("first_difference"),
                "all_eight_lanes_match_os":compare_all_lanes(output,bundles[0]["outputs"][:n]),
                "register_state_boundaries": {"rows":sum(1 for _ in state_checks.open())-1,
                                               "first_difference":next((r for r in csv.DictReader(state_checks.open()) if int(r["mismatching_registers"])>0),None)},
                "raw_runner_status":proc.stderr.strip()}
        if args.diagnostic_frame is not None and n==32768:
            result["instruction_trace_first_divergence"]=compare_instruction_traces(run_dir/"first-divergence.native.csv",run_dir/"first-divergence.mame.csv",args.diagnostic_frame)
            result["independent_divergence_analyzer"]=analyze_instruction_traces(run_dir/"first-divergence.native.csv",run_dir/"first-divergence.mame.csv",run_dir)
        results[str(n)]=result
        if not (n_exact and m_exact and em_exact):
            eligible_continue=False
            candidate=[]
            if result["native_os_first_difference"]:candidate.append((result["native_os_first_difference"]["index"],"native_vs_os"))
            if result["mame_os_first_difference"]:candidate.append((result["mame_os_first_difference"]["index"],"mame_vs_os"))
            if all_first:candidate.append((all_first["sample_index"],"native_vs_mame"))
            if candidate:first_actual={"sample_index":min(candidate)[0],"comparison":min(candidate)[1]}
    summary={"schema":"trollfx-asr10-factory-hall-replay-v4","state_gate":state_gate,
             "standalone_execution_occurred":True,"native_mame_and_os_comparison_eligible":True,
             "clock_domains":{"dsp_hz":DSPRATE,"host_hz":HOSTRATE},
             "post_run_schedule":{"event_count":len(bundles[0]["writes"]),"event_order_identical_across_two_boots":True,
                                   "scheduler":"apply each recorded host commit after its preceding output frame and before its next input frame; no sub-frame ordering inferred"},
             "windows":results,"sample_exact_through_32768":all(results.get(str(n),{}).get("native_matches_os") and results.get(str(n),{}).get("mame_matches_os") and results.get(str(n),{}).get("native_matches_mame") for n in WINDOWS),
             "earliest_verified_numerical_divergence":first_actual,"payload_values_disclosed":False}
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k not in ("windows",)},indent=2))
    for n,v in results.items(): print(json.dumps({"window":n,**{k:x for k,x in v.items() if k not in ("native_os_first_difference","mame_os_first_difference","all_eight_lanes_match_os")}},sort_keys=True))
    return 0 if summary["sample_exact_through_32768"] else 2


if __name__=="__main__": raise SystemExit(main())
