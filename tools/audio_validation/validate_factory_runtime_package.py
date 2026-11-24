#!/usr/bin/env python3
"""Fail-closed validation of private RUN checkpoints for the real audio host."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
import esp_capture
import factory_manifest

PROFILES = {
    "hall": {"effect_id":"ROM-01", "name":"HALL REVERB", "words":89, "end":88,
             "rate":29761.89453125, "frame":855973, "commits":89, "unique":89, "registers":342},
    "rom02": {"effect_id":"ROM-02", "name":"44KHZ REVERB", "words":60, "end":59,
              "rate":44100.0, "frame":905028, "commits":61, "unique":60, "registers":283},
}
PHASE = re.compile(r"ESPPHASE kind=([a-z0-9_]+)\s+(.*)$")
FIELD = re.compile(r"([a-z_]+)=([^\s]+)")


def fail(msg: str):
    raise ValueError(msg)


def validate(effect: str, manifest_path: Path, checkpoint: Path, reference_root: Path, events_path: Path) -> dict:
    if effect not in PROFILES: fail("unknown factory effect profile")
    profile = PROFILES[effect]
    manifest_path = manifest_path.resolve(strict=True)
    checkpoint = checkpoint.resolve(strict=True)
    reference_root = reference_root.resolve(strict=True)
    events_path = events_path.resolve(strict=True)
    result = factory_manifest.validate(manifest_path)
    if not result.get("valid") or not result.get("replay_ready"):
        fail("factory manifest is not replay-ready")
    doc = json.loads(manifest_path.read_text())
    if (doc.get("provenance", {}).get("effect_id") != profile["effect_id"] or
        doc.get("provenance", {}).get("effect_name") != profile["name"] or
        doc.get("provenance", {}).get("os_version") != "3.53" or
        int(doc.get("program", {}).get("active_words", -1)) != profile["words"] or
        int(doc.get("program", {}).get("end_word", -1)) != profile["end"] or
        abs(float(doc.get("sample_rate_hz", 0)) - profile["rate"]) > 1.0):
        fail("manifest effect identity, program geometry, or rate does not match the selected factory profile")
    if (doc.get("serial", {}).get("host_serial") != 0x48 or
        doc.get("serial", {}).get("input_ports") != [2] or
        doc.get("serial", {}).get("output_ports") != [1] or
        doc.get("pipeline") != {"status":"reset_after_load", "complete":True}):
        fail("manifest lacks the validated SER2-to-SER1 route or pipeline-reset state")
    if effect == "rom02":
        corr = doc.get("observed_run", {}).get("source_correlation", {})
        if (corr.get("effect_name") != profile["name"] or
            corr.get("active_instruction_matches") != 60 or
            corr.get("paired_gpr_initializers") != 58 or
            corr.get("source_pair_values_match") is not True):
            fail("ROM-02 source-to-RUN program correlation is incomplete")

    cap = esp_capture.read_capture(checkpoint)
    if cap["file_sha256"] != hashlib.sha256(checkpoint.read_bytes()).hexdigest():
        fail("checkpoint digest is inconsistent")
    if cap["program"]["active_words_through_first_END"] != profile["words"]:
        fail("checkpoint active instruction length mismatch")
    expected = {
        "program": doc["program"]["sha256"],
        "gpr": doc["gpr"]["sha256"],
        "special_registers": doc["special_registers"]["sha256"],
    }
    actual = {"program":cap["program"]["active_program_sha256"],
              "gpr":cap["registers"]["gpr_sha256"],
              "special_registers":cap["registers"]["special_sha256"]}
    if actual != expected: fail("checkpoint program or live register digests do not match the manifest")
    memory = doc["memory"]
    runtime_memory = cap["runtime"]["memory_configuration"]
    for key in ("memsiz","memmask","memincrement","memshift"):
        if int(memory[key]) != int(runtime_memory[key]): fail("checkpoint memory configuration does not match manifest")
    delay = cap["runtime"]["delay_configuration"]
    for key in ("dlength","abase","bbase","dbase"):
        spr = {"dlength":"DLENGTH","abase":"ABASE","bbase":"BBASE","dbase":"DBASE"}[key]
        if int(memory[key]) != int(delay[spr]): fail("checkpoint delay configuration does not match manifest")
    if (cap["runtime"]["control"]["halted"] or cap["runtime"]["control"]["pc"] != 0 or
        cap["runtime"]["control"]["host_serial"] != 0x48):
        fail("checkpoint is not at the first RUN frame or has an unexpected serial mode")
    if cap["runtime"]["dram_words"] != 1 << 20:
        fail("checkpoint DRAM geometry is incomplete")
    if doc["dram"]["mode"] == "zeroed" and cap["runtime"]["dram_nonzero_words"]:
        fail("checkpoint DRAM is not the validated zeroed image")
    if doc["dram"]["mode"] == "image" and cap["runtime"]["dram_sha256"] != doc["dram"].get("sha256"):
        fail("checkpoint DRAM digest does not match manifest")

    declared_frame = (doc.get("capture", {}).get("run_frame") or
                      doc.get("observed_run", {}).get("absolute_frame"))
    if int(declared_frame or -1) != profile["frame"]:
        fail("manifest RUN frame does not match the selected factory profile")
    expected_writes = 213 if effect == "hall" else 202
    manifest_writes = (doc.get("capture", {}).get("replay_update_count") if effect == "hall"
                       else doc.get("observed_run", {}).get("post_run_gpr_event_count"))
    if int(manifest_writes or -1) != expected_writes:
        fail("manifest does not attest the expected post-RUN firmware schedule count")
    with events_path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["boundary_frame", "event_id", "cpu_cycles", "dsp_frame", "host_pc", "index", "value"]:
            fail("post-RUN firmware schedule has an unexpected schema")
        scheduled = list(reader)
    if len(scheduled) != expected_writes:
        fail("post-RUN firmware schedule count does not match verified replay evidence")
    previous = profile["frame"]
    for item in scheduled:
        frame, index, value = int(item["boundary_frame"]), int(item["index"], 16), int(item["value"], 16)
        if frame < previous or frame > profile["frame"] + 32768 or index > 0xbf or value > 0xffffff:
            fail("post-RUN firmware schedule is outside the validated frame/register bounds")
        previous = frame
    declared_capture_sha = (doc.get("capture", {}).get("snapshot_sha256") or
                            doc.get("observed_run", {}).get("checkpoint_sha256"))
    actual_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if declared_capture_sha != actual_sha: fail("checkpoint digest is not the manifest RUN checkpoint")

    captures=[]
    for boot in ("boot-a","boot-b"):
        folder=reference_root/boot
        snapshot=folder/"snapshots"/f"run-frame-{profile['frame']}.esp"
        log=folder/"session.log"
        if not snapshot.is_file() or not log.is_file(): fail("two-boot reference evidence is incomplete")
        if snapshot.read_bytes() != checkpoint.read_bytes(): fail("selected checkpoint differs from the matching fresh-boot captures")
        events=[]
        with log.open(errors="replace") as src:
            for line in src:
                m=PHASE.search(line)
                if m:
                    fields=dict(FIELD.findall(m.group(2))); fields["kind"]=m.group(1)
                    if int(fields.get("frame",-1)) == profile["frame"] or m.group(1) in ("host_halt_pipeline_reset","host_dram_clear","instruction_upload_start"):
                        events.append(fields)
                if "ESPAUDIO kind=clock" in line and f"frame={profile['frame']} " in line:
                    events.append({"kind":"audio_clock", **dict(FIELD.findall(line.split("ESPAUDIO kind=clock",1)[1]))})
        def one(kind):
            matches=[e for e in events if e["kind"]==kind and int(e.get("frame",-1))==profile["frame"]]
            if len(matches)!=1: fail("RUN evidence event is missing or ambiguous: "+kind)
            return matches[0]
        summary=one("program_upload_summary"); run=one("run_start"); snap=one("run_snapshot"); first=one("first_instruction"); clock=one("audio_clock")
        if (int(summary.get("commits",-1))!=profile["commits"] or
            int(summary.get("unique_addresses",-1))!=profile["unique"] or
            int(summary.get("first_end",-1))!=profile["end"] or
            int(summary.get("gpr_commits",-1))!=profile["registers"]):
            fail("ordered OS load transaction counts do not match the effect profile")
        if (run.get("pc")!="00" or run.get("host_serial")!="48" or snap.get("ok")!="1" or
            first.get("pc")!="00"):
            fail("RUN, checkpoint, serial configuration, or first-instruction boundary is invalid")
        if (abs(float(clock.get("dsp_rate_hz",0))-profile["rate"])>0.01 or
            abs(float(clock.get("host_output_rate_hz",0))-44100.0)>0.01 or
            clock.get("serial_route")!="-1,-1,1,-1"):
            fail("captured clock or serial routing does not match the verified factory evidence")
        reset_idx=max((i for i,e in enumerate(events) if e["kind"]=="host_halt_pipeline_reset"),default=-1)
        clear_idx=max((i for i,e in enumerate(events) if e["kind"]=="host_dram_clear"),default=-1)
        upload_idx=max((i for i,e in enumerate(events) if e["kind"]=="instruction_upload_start"),default=-1)
        ordered=[i for i,e in enumerate(events) if e in (summary,run,snap,first)]
        if reset_idx<0 or clear_idx<=reset_idx or upload_idx<=clear_idx or not (reset_idx<clear_idx<upload_idx) or len(ordered)!=4 or ordered!=sorted(ordered):
            fail("HALT pipeline reset, DRAM clear, upload, and RUN order is invalid")
        captures.append(True)
    return {"valid":True,"effect":effect,"active_program_words":profile["words"],
            "run_frame":profile["frame"],"processing_rate_hz":48000.0,
            "factory_reference_rate_hz":profile["rate"],"host_serial":0x48,
            "serial_route":"SER2 stereo input -> SER1 stereo output",
            "two_boot_checkpoint_match":all(captures),"state_payload_disclosed":False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--effect",choices=sorted(PROFILES),required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--checkpoint",type=Path,required=True)
    p.add_argument("--reference-root",type=Path,required=True)
    p.add_argument("--events",type=Path,required=True)
    a=p.parse_args()
    try:
        print(json.dumps(validate(a.effect,a.manifest,a.checkpoint,a.reference_root,a.events),indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as e:
        print(json.dumps({"valid":False,"effect":a.effect,"error":str(e),"state_payload_disclosed":False}),file=sys.stderr)
        return 2

if __name__=="__main__": raise SystemExit(main())
