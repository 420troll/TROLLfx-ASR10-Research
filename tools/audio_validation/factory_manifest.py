#!/usr/bin/env python3
"""Validate private, externally supplied ES5510 factory initialization manifests.

Only validation status and field names are printed; state payloads are never emitted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "trollfx-es5510-factory-init-v1"
PARTIAL_SCHEMA = "trollfx-es5510-factory-init-partial-v1"

def _get(doc, path):
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise ValueError(f"missing required field: {path}")
        cur = cur[part]
    return cur

def validate(path: Path) -> dict:
    doc = json.loads(path.read_text())
    if doc.get("schema") == PARTIAL_SCHEMA:
        required = ("provenance.effect_id", "provenance.effect_name", "provenance.os_version",
                    "capture.selection_time_s", "capture.host_frame_count", "capture.sample_rate_hz",
                    "capture.instruction_commits", "capture.paired_gpr_initializers",
                    "capture.capture_kind", "known", "unknown", "replay_ready")
        for field in required:
            _get(doc, field)
        if doc["initialization_basis"] != "partial_cold_load":
            raise ValueError("partial manifest initialization_basis must be partial_cold_load")
        if doc["capture"]["capture_kind"] != "post_selection_runtime_snapshot":
            raise ValueError("partial manifest capture_kind unsupported")
        if doc["replay_ready"] is not False:
            raise ValueError("partial evidence cannot be marked replay_ready")
        if doc["capture"]["instruction_commits"] != 89 or doc["capture"]["paired_gpr_initializers"] != 86:
            raise ValueError("ROM-01 HALL correlation counts do not match the verified evidence")
        return {"valid": True, "replay_ready": False, "errors": [],
                "replay_blockers": list(doc.get("replay_blockers", [])),
                "effect_id": doc["provenance"]["effect_id"],
                "active_words": doc["capture"]["instruction_commits"],
                "sample_rate_hz": doc["capture"]["sample_rate_hz"],
                "state_payload_disclosed": False}
    if doc.get("schema") != SCHEMA:
        raise ValueError("unsupported schema")
    if doc.get("initialization_basis") != "cold_load":
        raise ValueError("initialization_basis must be cold_load; runtime snapshots are not accepted")
    fields = ("provenance.effect_id", "provenance.effect_name", "provenance.os_version",
              "provenance.selection_evidence", "sample_rate_hz", "program.format", "program.path",
              "program.sha256", "program.active_words", "program.end_word", "gpr.path", "gpr.sha256",
              "gpr.count", "special_registers.path", "special_registers.sha256", "special_registers.count",
              "dram.mode", "dram.word_count", "memory.memsiz", "memory.memmask", "memory.memincrement",
              "memory.memshift", "memory.dlength", "memory.abase", "memory.bbase", "memory.dbase",
              "memory.sigreg", "serial.host_serial", "serial.input_ports", "serial.output_ports",
              "lifecycle.halt_before_load", "lifecycle.run_after_load", "lifecycle.initialization_order",
              "pipeline.status", "pipeline.complete")
    for field in fields:
        _get(doc, field)
    errors = []
    if doc["program"]["format"] != "es5510-six-byte-big-endian": errors.append("program.format unsupported")
    if not 1 <= int(doc["program"]["active_words"]) <= 160: errors.append("program.active_words out of range")
    if int(doc["program"]["end_word"]) != int(doc["program"]["active_words"]) - 1: errors.append("program.end_word inconsistent")
    if int(doc["gpr"]["count"]) != 192: errors.append("gpr.count must be 192")
    if int(doc["special_registers"]["count"]) != 22: errors.append("special_registers.count must be 22")
    if not 8000 <= int(doc["sample_rate_hz"]) <= 192000: errors.append("sample_rate_hz implausible")
    if doc["pipeline"] != {"status": "reset_after_load", "complete": True}:
        errors.append("pipeline must be explicitly reset_after_load and complete")
    dram = doc["dram"]
    if dram["mode"] not in ("zeroed", "image"): errors.append("dram.mode unsupported")
    refs = [(key, doc[key]["path"], doc[key]["sha256"]) for key in ("program", "gpr", "special_registers")]
    if dram["mode"] == "image":
        for key in ("path", "sha256"):
            if key not in dram: errors.append(f"dram.{key} required for image mode")
        if "path" in dram and "sha256" in dram: refs.append(("dram", dram["path"], dram["sha256"]))
    order = ["halt", "memory", "program", "gpr", "special_registers", "dram", "reset_pipeline", "run"]
    if doc["lifecycle"]["initialization_order"] != order: errors.append("lifecycle.initialization_order invalid")
    if doc["lifecycle"]["halt_before_load"] is not True or doc["lifecycle"]["run_after_load"] is not True:
        errors.append("lifecycle must HALT before loading and release RUN after initialization")
    mem = doc["memory"]
    shift = int(mem["memshift"])
    if not 0 <= shift <= 24: errors.append("memory.memshift out of range")
    else:
        if int(mem["memincrement"]) != (1 << shift): errors.append("memory.memincrement inconsistent with memshift")
        if int(mem["memsiz"]) != ((1 << shift) - 1): errors.append("memory.memsiz inconsistent with memshift")
        if int(mem["memmask"]) != (0xffffff ^ ((1 << shift) - 1)): errors.append("memory.memmask inconsistent with memshift")
    for key in ("dlength", "abase", "bbase", "dbase", "sigreg"):
        if not 0 <= int(mem[key]) <= 0xffffff: errors.append(f"memory.{key} outside 24-bit range")
    if len(doc["serial"]["input_ports"]) > 3 or any(not 0 <= int(v) <= 2 for v in doc["serial"]["input_ports"]):
        errors.append("serial.input_ports must identify available ports 0..2")
    if not doc["serial"]["output_ports"] or any(not 0 <= int(v) <= 3 for v in doc["serial"]["output_ports"]):
        errors.append("serial.output_ports must identify ports 0..3")
    if not 0 <= int(doc["serial"]["host_serial"]) <= 0xff: errors.append("serial.host_serial outside byte range")
    for sec, rel, expected in refs:
        ref = path.parent / rel
        if not ref.is_file(): errors.append(f"{sec}.path file missing"); continue
        data = ref.read_bytes()
        if hashlib.sha256(data).hexdigest().lower() != str(expected).lower(): errors.append(f"{sec}.sha256 mismatch")
        expected_sizes = {"program": int(doc["program"]["active_words"]) * 6, "gpr": 192 * 3,
                          "special_registers": 22 * 3}
        if sec in expected_sizes and len(data) != expected_sizes[sec]: errors.append(f"{sec}.path byte length mismatch")
        if sec == "program" and len(data) >= (int(doc["program"]["end_word"]) + 1) * 6:
            word = int.from_bytes(data[int(doc["program"]["end_word"]) * 6:(int(doc["program"]["end_word"]) + 1) * 6], "big")
            if ((word >> 12) & 0xf) != 0xf: errors.append("program.end_word does not contain END")
        if sec == "dram" and len(data) != int(dram["word_count"]) * 2: errors.append("dram image byte length mismatch")
    return {"valid": not errors, "replay_ready": not errors, "errors": errors, "effect_id": doc["provenance"]["effect_id"],
            "active_words": doc["program"]["active_words"], "sample_rate_hz": doc["sample_rate_hz"],
            "state_payload_disclosed": False}

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("manifest", type=Path)
    ap.add_argument("--require-replay-ready", action="store_true",
                    help="return status 2 unless the manifest is complete and replay-ready")
    args = ap.parse_args()
    try:
        result = validate(args.manifest); print(json.dumps(result, indent=2))
        if not result["valid"]: return 1
        if args.require_replay_ready and not result["replay_ready"]: return 2
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)], "state_payload_disclosed": False}, indent=2)); return 1

if __name__ == "__main__": raise SystemExit(main())
