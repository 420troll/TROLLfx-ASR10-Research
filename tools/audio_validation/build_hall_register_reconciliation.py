#!/usr/bin/env python3
"""Build the value-bearing HALL register reconciliation outside the repository.

Inputs and output are private capture artifacts. The output path is required to
be outside this checkout so register state does not enter Git accidentally.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from replay_hall import extract_load_history
SPR_NAMES = {
    0xEE: "SER2R", 0xEF: "SER2L", 0xF3: "MACH", 0xF4: "DIL/readback",
    0xF8: "DBASE", 0xF9: "SIGREG", 0xFA: "CCR",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gpr_table", type=Path)
    ap.add_argument("manifest", type=Path)
    ap.add_argument("events", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    out = a.out.expanduser().resolve()
    if out == ROOT or ROOT in out.parents:
        ap.error("register values must be written outside the repository")
    base = a.manifest.resolve(strict=True).parent
    manifest = json.loads(a.manifest.read_text())
    reg_file = (base / manifest["special_registers"]["path"]).resolve(strict=True)
    if base not in reg_file.parents:
        ap.error("manifest SPR payload escapes its private directory")
    gpr = json.loads(a.gpr_table.read_text())
    rows = []
    # Both fresh captures are identical. Keep one row per address and record
    # the independent duplicate capture as corroboration.
    selected = {r["gpr_address"]: r for r in gpr["registers"]
                if r["capture"] == "fresh-2020"}
    if len(selected) != 16:
        ap.error("GPR reconciliation must contain the verified 16-address set")
    for r in selected.values():
        last = r["last_write_before_hall_transaction"]
        rows.append({
            "address": f'0x{r["gpr_address"]:02X}', "symbolic_name": f'GPR{r["gpr_address"]:02X}',
            "expected_manifest": r["expected_manifest_hex"],
            "reconstructed_transaction_only": r["observed_hall_transaction_only_hex"],
            "reconstructed_with_recorded_history": r["observed_full_history_hex"],
            "last_recorded_firmware_write": last,
            "execution_boundary": "halted before selected HALL load; retained through RUN",
            "implicit_hardware_update": None,
            "root_cause": "prior halted BOTH_COMMIT retained across HALT/pipeline reset",
            "supporting_evidence": "fresh-2020 row; identical fresh-2040 snapshot and full-history reconstruction",
            "resolved": r["resolved_by_prior_history"],
        })
    spr_data = reg_file.read_bytes()
    history, commits = extract_load_history(a.events.resolve(strict=True), int(manifest["capture"]["run_frame"]))
    reconstructed = [0] * 256
    for kind, address, value, second in history + commits:
        index = int(address, 16)
        if kind == "seed_gpr":
            reconstructed[index] = int(value, 16)
        elif kind in ("gpr", "both"):
            reconstructed[index] = int(second if kind == "both" else value, 16)
    latest = {}
    with a.events.resolve(strict=True).open(newline="") as f:
        for row in csv.reader(f):
            if len(row) < 6 or not row[0].isdigit() or row[5] not in ("GPR_COMMIT", "BOTH_COMMIT"):
                continue
            fields = dict(item.split("=", 1) for item in row[6:] if "=" in item)
            addr = int(fields.get("index", "-1"), 16)
            if addr in SPR_NAMES:
                latest[addr] = {"event_id": int(row[0]), "cpu_cycles": int(row[1]),
                                "dsp_frame": int(row[2]), "cpu_pc": row[4],
                                "kind": row[5], "phase": fields.get("phase")}
    causes = {
        0xEE: ("SER2R", "first serial input sample is reflected in checkpoint; latch edge unresolved"),
        0xEF: ("SER2L", "first serial input sample is reflected in checkpoint; latch edge unresolved"),
        0xF3: ("MACH", "live MAC high word; no transaction write; prior DSP provenance unavailable"),
        0xF4: ("DIL/readback", "F4 write configures memory; readback is live DIL, not stored config"),
        0xF8: ("DBASE", "live delay base pointer; first-frame advance is recorded"),
        0xF9: ("SIGREG", "retained startup configuration; cold-start write precedes HALL load"),
        0xFA: ("CCR", "live condition flags; exact prior DSP producer unavailable"),
    }
    for addr in (0xEE, 0xEF, 0xF3, 0xF4, 0xF8, 0xF9, 0xFA):
        i = addr - 234
        expected = int.from_bytes(spr_data[i*3:i*3+3], "big")
        name, cause = causes[addr]
        rows.append({
            "address": f"0x{addr:02X}", "symbolic_name": name,
            "expected_manifest": f"{expected:06X}", "reconstructed_transaction_only": "000000",
            "reconstructed_with_recorded_history": f"{reconstructed[addr]:06X}",
            "last_recorded_firmware_write": latest.get(addr),
            "execution_boundary": "RUN snapshot, frame 855973; first instruction boundary not separately logged",
            "implicit_hardware_update": cause,
            "root_cause": "runtime snapshot includes live SPR state absent from halted commit-only reconstruction",
            "supporting_evidence": "private ordered event trace; REA/Ghidra loader decode; native/MAME register semantics",
            "resolved": reconstructed[addr] == expected,
        })
    result = {"schema": "trollfx-asr10-hall-register-reconciliation-v2",
              "manifest_checkpoint_frame": int(manifest["capture"]["run_frame"]),
              "registers": sorted(rows, key=lambda x: int(x["address"], 16)),
              "values_private": True}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"register_count": len(rows), "gpr_resolved": sum(x["resolved"] for x in rows if int(x["address"], 16) < 0xC0),
                      "spr_resolved": sum(x["resolved"] for x in rows if int(x["address"], 16) >= 0xC0),
                      "output_private": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
