#!/usr/bin/env python3
"""Audit private selector-sweep packages and emit safe universal-runtime descriptors.

This importer treats the captured checkpoint as the current DSP state. Writes
in firmware-events.log occurred before that snapshot and are already reflected
in its GPR/DRAM state; they are validated as history and are not replayed from
frame zero. Only independently identity-supported slots are eligible.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import esp_capture

KNOWN = {
    1: {"name": "HALL REVERB", "words": 89, "program": "34eec2eb04319c0d167a4110608e1e99f2aa13d8b7908f79852c2be3c0aefd4c"},
    2: {"name": "44KHZ REVERB", "words": 60, "program": "12119e86d4d232ab7d7ab4278e9c9dbed9db19a6b6eb352bfb29441181da4486"},
}
QUARANTINE = {}
EVENT = re.compile(r"^ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-fA-F]+) (gpr|instr|both|ram)\b")

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def package_eligibility(slot: int, name: str, words: int, program_sha: str,
                        run_frame: int, checkpoint_frame: int,
                        source_correlated: bool = False) -> tuple[bool, str | None]:
    reason = QUARANTINE.get(slot)
    profile = KNOWN.get(slot)
    if profile and (name != profile["name"] or words != profile["words"] or program_sha != profile["program"]):
        reason = "independent replay identity conflict"
    if checkpoint_frame != run_frame:
        reason = reason or "checkpoint is after RUN; omitted pipeline slots cannot be reconstructed as a RUN-boundary state"
    if not source_correlated:
        reason = reason or "OS selector to uploaded RUN program correlation is not verified"
    return reason is None, reason

def verified_factory_variation(slot: int, name: str, words: int) -> int:
    """Return only factory variation defaults directly observed on OS 3.53."""
    hall = KNOWN[1]
    if slot == 1 and name == hall["name"] and words == hall["words"]:
        # Independent HALL editor-state capture observed factory selection at
        # VAR=1. Defaults for all other effect identities remain unknown.
        return 1
    return 0

def validate_one(package_file: Path, quarantined: dict[int,str]) -> dict:
    doc = json.loads(package_file.read_text())
    slot = int(doc["effect_id"])
    base = package_file.parent
    checkpoint = (base / doc["checkpoint"]).resolve(strict=True)
    event_path = (base / doc["firmware_events"]).resolve(strict=True)
    if doc.get("files", {}).get(checkpoint.name) != sha(checkpoint): raise ValueError("checkpoint hash mismatch")
    if doc.get("files", {}).get(event_path.name) != sha(event_path): raise ValueError("firmware history hash mismatch")
    cap = esp_capture.read_capture(checkpoint)
    if cap["file_sha256"] != sha(checkpoint): raise ValueError("checkpoint changed during validation")
    if cap["program"]["active_program_sha256"] != doc["active_program_sha256"]: raise ValueError("active program digest mismatch")
    if cap["program"]["active_words_through_first_END"] != doc["active_program_words"]: raise ValueError("active program length mismatch")
    if cap["registers"]["gpr_sha256"] != doc["registers"]["gpr_sha256"]: raise ValueError("GPR state digest mismatch")
    if cap["registers"]["special_sha256"] != doc["registers"]["special_sha256"]: raise ValueError("SPR state digest mismatch")
    if cap["runtime"]["dram_sha256"] != doc["dram"]["sha256"]: raise ValueError("DRAM digest mismatch")
    if cap["runtime"]["dram_words"] != 1 << 20: raise ValueError("incomplete DRAM image")
    if cap["runtime"]["memory_configuration"] != doc["memory_configuration"]: raise ValueError("memory configuration mismatch")
    if cap["runtime"]["delay_configuration"] != doc["delay_configuration"]: raise ValueError("delay register mismatch")
    if cap["runtime"]["control"]["pc"] != 0 or cap["runtime"]["control"]["halted"]: raise ValueError("checkpoint is not running at PC zero")
    if cap["runtime"]["control"]["host_serial"] != 0x48: raise ValueError("serial mode mismatch")
    route = doc.get("serial_route", {})
    if (route.get("host_serial") != 0x48 or route.get("configured_input_ports") != [2] or
        route.get("configured_output_ports") != [1]): raise ValueError("manifest route evidence mismatch")
    if doc["registers"]["gpr_count"] != 192 or doc["registers"]["special_count"] != 22: raise ValueError("register geometry mismatch")
    if not doc.get("host_commit_match", {}).get("verified"): raise ValueError("host commit correlation is absent")
    if not doc.get("pipeline_reset_acknowledged"): raise ValueError("pipeline reset evidence absent")
    evidence = doc.get("run_boundary_phase_evidence", {})
    phases = evidence.get("events", [])
    expected = ["pa4_halt_assert", "halt", "host_halt_pipeline_reset", "host_dram_clear",
                "instruction_upload_start", "pa4_run_release", "program_upload_summary", "run_start",
                "run_snapshot", "first_instruction"]
    if not evidence.get("ordered") or [x.get("kind") for x in phases] != expected:
        raise ValueError("HALT/reset/clear/upload/RUN phase chain mismatch")
    run_frame = next(x["frame"] for x in phases if x["kind"] == "run_start")
    lines = [int(x["line"]) for x in phases]
    if lines != sorted(lines): raise ValueError("RUN boundary phases are not in observed log order")
    if not doc.get("run_boundary_source_correlation", {}).get("verified"):
        raise ValueError("selected-slot to uploaded-program source correlation is absent")
    snap_frame = int(doc["run_frame"])
    if snap_frame < run_frame: raise ValueError("checkpoint predates RUN")
    count = 0; last_event = -1; last_cycle = -1; last_frame = -1
    for line in event_path.open(errors="replace"):
        m = EVENT.match(line)
        if not m: raise ValueError("unexpected firmware transaction line")
        event, cycles, frame = int(m[1]), int(m[2]), int(m[3])
        if event <= last_event or cycles < last_cycle or frame < last_frame or frame > snap_frame:
            raise ValueError("firmware transaction history is unordered or exceeds checkpoint")
        last_event, last_cycle, last_frame = event, cycles, frame
        count += 1
    if count != int(doc["firmware_transaction_count"]): raise ValueError("firmware history count mismatch")

    # Only writes observed after this first-instruction checkpoint are replayed.
    schedule_doc = doc.get("firmware_schedule", {})
    schedule_path = (base / schedule_doc.get("path", "")).resolve(strict=True)
    if doc.get("files", {}).get(schedule_path.name) != sha(schedule_path): raise ValueError("firmware schedule hash mismatch")
    import csv
    with schedule_path.open(newline="") as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames != ["relative_dsp_frame","event_id","cpu_cycles","gpr","value24"]:
            raise ValueError("firmware schedule schema mismatch")
        scheduled=[]; prev_frame=-1; prev_event=-1
        for item in reader:
            frame=int(item["relative_dsp_frame"]); event=int(item["event_id"])
            gpr=int(item["gpr"],16); value=int(item["value24"],16)
            if frame < prev_frame or frame >= int(schedule_doc.get("window_frames",0)) or event <= prev_event or gpr >= 0xc0 or value > 0xffffff:
                raise ValueError("firmware schedule is malformed or outside its capture window")
            scheduled.append({"relative_dsp_frame":frame,"event_id":event,"gpr":gpr,"value24":value})
            prev_frame,prev_event=frame,event
    if len(scheduled) != int(schedule_doc.get("count",-1)): raise ValueError("firmware schedule count mismatch")
    if len(scheduled) > 1024: raise ValueError("required firmware schedule exceeds the runtime's bounded 1024-event queue")
    corr=doc["run_boundary_source_correlation"]
    if int(corr.get("slot",-1)) != slot or int(corr.get("run_frame",-1)) != run_frame or corr.get("program_sha256") != doc["active_program_sha256"]:
        raise ValueError("slot selection, RUN frame, and active program source correlation disagree")
    eligible, reason = package_eligibility(slot, doc["display_name"], doc["active_program_words"],
                                            doc["active_program_sha256"], run_frame, snap_frame, True)
    if reason: quarantined[slot] = reason
    desc = None
    if eligible:
        desc = {
            "slot": slot, "factory_name": doc["display_name"],
            "factory_variation": verified_factory_variation(
                slot, doc["display_name"], doc["active_program_words"]),
            "active_program_words": doc["active_program_words"],
            "end_word": doc["active_program_words"] - 1,
            "program_sha256": doc["active_program_sha256"],
            "factory_reference_rate_hz": doc["sample_rate_hz"],
            "routing": {"host_serial_mode": 0x48, "input_port": 2, "output_port": 1, "stereo": True},
            "package_manifest_path": str(package_file.resolve()),
            "initialization_manifest_path": str(package_file.resolve()),
            "run_checkpoint_path": str(checkpoint), "run_checkpoint_sha256": sha(checkpoint),
            "firmware_event_schedule_path": str(schedule_path), "firmware_event_schedule_sha256": sha(schedule_path),
            "firmware_event_schedule": scheduled, "parameters": [],
        }
    return {"slot": slot, "name": doc["display_name"], "capture_state_valid": True,
            "registry_eligible": eligible, "quarantine_reason": reason,
            "run_start_frame": run_frame, "checkpoint_frame": snap_frame,
            "checkpoint_is_at_run_boundary": snap_frame == run_frame,
            "historical_transactions_validated": count, "future_schedule_count": len(scheduled),
            "descriptor": desc}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("collection",type=Path);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();root=a.collection.resolve(strict=True); out=a.output.resolve()
    if out == root or root in out.parents: raise ValueError("output must not overwrite the private collection")
    quarantine=dict(QUARANTINE)
    result=[]
    for file in sorted((root/"packages").glob("ROM-*/package.json")):
        try: result.append(validate_one(file,quarantine))
        except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as e:
            try: slot=int(json.loads(file.read_text()).get("effect_id",0))
            except Exception: slot=0
            result.append({"slot":slot,"registry_eligible":False,"quarantine_reason":str(e),"descriptor":None})
    result.sort(key=lambda x:x["slot"])
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"schema":"trollfx-universal-import-audit-v1","slots":result,
      "counts":{"captured":len(result),"registry_eligible":sum(bool(x.get("registry_eligible")) for x in result),
                "quarantined":sum(not x.get("registry_eligible") for x in result)}},indent=2,sort_keys=True)+"\n")
    print(json.dumps({"output":str(out),"captured":len(result),
      "registry_eligible":sum(bool(x.get("registry_eligible")) for x in result),
      "quarantined":[x["slot"] for x in result if not x.get("registry_eligible")]},indent=2))
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as e:
        print(f"import_factory_effect_collection: {e}",file=sys.stderr);raise SystemExit(2)
