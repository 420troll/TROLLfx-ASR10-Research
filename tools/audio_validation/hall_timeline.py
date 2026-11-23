#!/usr/bin/env python3
"""Build a redacted, deterministic timeline and HALL state-gate diagnostic.

Reads private manifest/event/capture files and emits coordinates, counts, hashes,
and register indexes only. It never emits private register or audio values.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_TOOL = Path(__file__).with_name("factory_manifest.py")
CAPTURE_TOOL = ROOT / "tools/esp_capture.py"


def event_rows(path: Path) -> list[dict]:
    out = []
    with path.open(newline="") as f:
        for row in csv.reader(f):
            if len(row) < 6 or not row[0].isdigit():
                continue
            fields = {}
            for item in row[6:]:
                k, sep, v = item.partition("=")
                if sep:
                    fields[k] = v
            out.append({"event_id": int(row[0]), "cpu_cycles": int(row[1]),
                        "dsp_frame": int(row[2]), "host_seconds": float(row[3]),
                        "cpu_pc": row[4], "kind": row[5], "fields": fields})
    return out


def _coord(e: dict | None, label: str) -> dict:
    if e is None:
        return {"event": label, "observed": False}
    return {"event": label, "observed": True, "event_id": e["event_id"],
            "cpu_cycles": e["cpu_cycles"], "dsp_frame": e["dsp_frame"],
            "host_seconds": e["host_seconds"], "cpu_pc": e["cpu_pc"]}


def _u24(payload: bytes, i: int) -> int:
    return int.from_bytes(payload[i * 3:i * 3 + 3], "big")


def _capture_sections(path: Path) -> tuple[bytes, bytes]:
    raw = path.read_bytes()
    if len(raw) < 44 or raw[:8] != b"ES5510C\0":
        raise ValueError(f"invalid private checkpoint capture: {path.name}")
    return raw[44 + 160 * 6:44 + 160 * 6 + 192 * 3], raw[44 + 160 * 6 + 192 * 3:44 + 160 * 6 + 192 * 3 + 22 * 3]


def analyze(events_path: Path, manifest_path: Path, checkpoint_frame: int | None = None,
            prior_capture: Path | None = None) -> dict:
    manifest = json.loads(manifest_path.read_text())
    cap = manifest["capture"]
    frame = int(cap["run_frame"]) if checkpoint_frame is None else checkpoint_frame
    events = event_rows(events_path)
    selected = [e for e in events if e["kind"] == "DSP_RUN" and e["dsp_frame"] == frame]
    if len(selected) != 1:
        raise ValueError(f"checkpoint frame {frame} does not select exactly one DSP_RUN event")
    run = selected[0]
    snapshots = [e for e in events if e["kind"] == "RUN_SNAPSHOT" and e["dsp_frame"] == frame and e["event_id"] > run["event_id"]]
    if len(snapshots) != 1:
        raise ValueError(f"checkpoint frame {frame} does not select exactly one RUN_SNAPSHOT")
    snap = snapshots[0]
    if frame != int(cap["run_frame"]):
        raise ValueError("selected RUN_SNAPSHOT differs from manifest checkpoint; state gate not eligible")
    snapshot_path = Path(snap["fields"]["path"]).resolve(strict=True)
    if events_path.parent.resolve() not in snapshot_path.parents:
        raise ValueError("event snapshot path escapes private event directory")
    snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    if snapshot_sha256 != cap.get("snapshot_sha256"):
        raise ValueError("selected RUN_SNAPSHOT hash does not match manifest checkpoint")
    run_index = events.index(run)
    prior_clear_ix = max((i for i, e in enumerate(events[:run_index + 1])
                         if e["kind"] in ("PIPELINE_CLEAR", "PIPELINE_CLEARED")), default=-1)
    transaction = events[prior_clear_ix + 1:run_index]
    # The clear event itself marks the transaction's reset boundary.
    if prior_clear_ix >= 0:
        transaction.insert(0, events[prior_clear_ix])
    commit_rows = [e for e in transaction if e["kind"] in ("GPR_COMMIT", "INSTR_COMMIT", "BOTH_COMMIT")]
    gpr = [0] * 256
    gpr[252:255] = [0xffffff, 0x800000, 0x7fffff]
    instr = [0] * 160
    touched = set()
    last_write = {}
    for e in commit_rows:
        f = e["fields"]
        addr = int(f["index"], 16)
        if e["kind"] in ("GPR_COMMIT", "BOTH_COMMIT"):
            value = int(f["value"] if e["kind"] == "GPR_COMMIT" else f["gpr"], 16)
            gpr[addr] = value; touched.add(addr); last_write[addr] = e["event_id"]
        if e["kind"] in ("INSTR_COMMIT", "BOTH_COMMIT"):
            word = f.get("word")
            if word is not None:
                instr[addr] = int(word, 16)
    # Manifest paths are constrained to the manifest directory, as in replay_hall.py.
    def private_file(rel: str) -> Path:
        p = (manifest_path.parent / rel).resolve(strict=True)
        if manifest_path.parent.resolve() not in p.parents:
            raise ValueError("manifest payload path escapes its private directory")
        return p
    gpr_expected = private_file(manifest["gpr"]["path"]).read_bytes()
    spr_expected = private_file(manifest["special_registers"]["path"]).read_bytes()
    spr_mapped = {234 + i: _u24(spr_expected, i) for i in range(22)}
    mismatched = sorted([i for i in range(192) if gpr[i] != int.from_bytes(gpr_expected[i*3:i*3+3], "big")] +
                        [i for i in range(234, 256) if gpr[i] != spr_mapped[i]])
    mismatch_touched = [i for i in mismatched if i in touched]
    mismatch_unwritten = [i for i in mismatched if i not in touched]
    instr_count = sum(e["kind"] in ("INSTR_COMMIT", "BOTH_COMMIT") for e in commit_rows)
    gpr_count = sum(e["kind"] in ("GPR_COMMIT", "BOTH_COMMIT") for e in commit_rows)
    first_instr = next((e for e in commit_rows if e["kind"] in ("INSTR_COMMIT", "BOTH_COMMIT")), None)
    ready = next((e for e in events[:run_index] if e["kind"] == "PROGRAM_READY" and e["dsp_frame"] <= frame), None)
    release = next((e for e in reversed(events[:run_index]) if e["kind"] == "PA4" and e["fields"].get("HALT", "") == "" and e["fields"].get("prior_state") == "halted"), None)
    halt = next((e for e in reversed(events[:run_index]) if e["kind"] == "PA4" and e["fields"].get("prior_state") == "running" and e["fields"].get("HALT", "") == ""), None)
    # PA4 data is positional (HALT/RUN); use the nearest phase before the selected run.
    pa4 = [e for e in events[:run_index] if e["kind"] == "PA4"]
    halt = next((e for e in reversed(pa4) if "HALT" in e["fields"].values()), halt)
    release = next((e for e in reversed(pa4) if "RUN" in e["fields"].values()), release)
    clear = events[prior_clear_ix] if prior_clear_ix >= 0 else None
    dram = next((e for e in transaction if e["kind"] == "DRAM_CLEAR"), None)
    ready = next((e for e in transaction if e["kind"] == "PROGRAM_READY"), ready)
    first_audio = next((e for e in events[run_index + 1:] if e["kind"] == "AUDIO_PRE" and e["dsp_frame"] == frame), None)
    first_end = next((e for e in events[run_index + 1:] if e["kind"] == "DSP_FIRST_END" and e["dsp_frame"] == frame), None)
    after = [e for e in events if e["event_id"] > snap["event_id"] and e["kind"] in ("GPR_COMMIT", "BOTH_COMMIT", "INSTR_COMMIT")]
    after_by_addr = {}
    for e in after:
        if e["kind"] in ("GPR_COMMIT", "BOTH_COMMIT"):
            addr = int(e["fields"]["index"], 16)
            after_by_addr[addr] = after_by_addr.get(addr, 0) + 1
    report = {"schema": "trollfx-es5510-hall-timeline-v1", "selected_checkpoint": {
                  "frame": frame, "manifest_frame": int(cap["run_frame"]), "selection_valid": True,
                  "event_id": snap["event_id"], "kind": "RUN_SNAPSHOT", "snapshot_sha256": snapshot_sha256,
                  "strict_state_gate_unchanged": True},
              "timeline": [_coord(halt, "PA4_HALT"), _coord(clear, "pipeline_reset"),
                           _coord(dram, "DRAM_clear"), _coord(first_instr, "first_instruction_upload_commit"),
                           _coord(ready, "instruction_upload_complete"), _coord(release, "PA4_RUN_release"),
                           _coord(run, "DSP_RUN"), _coord(snap, "manifest_checkpoint"),
                           {**_coord(run, "first_instruction_start"), "event_id": None,
                            "evidence": "checkpoint PC=0 and HALL boundary report; no dedicated first-instruction row in this event CSV"},
                           _coord(first_audio, "first_input_frame"), _coord(first_end, "first_frame_end")],
              "halted_commit_summary": {"gpr_spr_commits": gpr_count, "instruction_commits": instr_count,
                  "unique_register_targets": len(touched), "unique_instruction_targets": len({int(e["fields"]["index"],16) for e in commit_rows if e["kind"] in ("INSTR_COMMIT","BOTH_COMMIT")}),
                  "manifest_state_gate_pass": not mismatched, "mismatching_register_count": len(mismatched),
                  "mismatching_gpr_count": sum(i < 192 for i in mismatched),
                  "mismatching_spr_count": sum(i >= 234 for i in mismatched),
                  "mismatches_with_halted_write": mismatch_touched,
                  "mismatches_without_halted_write": mismatch_unwritten,
                  "registers_written_after_checkpoint": {f"{k:02x}": v for k,v in sorted(after_by_addr.items())},
                  "post_checkpoint_commit_count": len(after)},
              "earliest_blocker": "manifest state differs from replayed halted-commit state" if mismatched else None,
              "payload_values_disclosed": False}
    if prior_capture:
        pg, ps = _capture_sections(prior_capture)
        cg, cs = _capture_sections(snapshot_path)
        report["prior_checkpoint_comparison"] = {
            "prior_capture_sha256": hashlib.sha256(prior_capture.read_bytes()).hexdigest(),
            "gpr_equal_to_selected_checkpoint": sum(pg[i*3:i*3+3] == cg[i*3:i*3+3] for i in range(192)),
            "spr_equal_to_selected_checkpoint": sum(ps[i*3:i*3+3] == cs[i*3:i*3+3] for i in range(22)),
            "mismatches_inherited_from_prior": [i for i in mismatched if i < 192 and pg[i*3:i*3+3] == cg[i*3:i*3+3]]}
    report["transaction_fingerprints"] = {
        "ordered_gpr_spr_commits_sha256": hashlib.sha256("\n".join(
            f'{e["kind"]}:{e["fields"].get("index","")}:{e["fields"].get("value","")}:{e["fields"].get("gpr","")}'
            for e in commit_rows if e["kind"] in ("GPR_COMMIT","BOTH_COMMIT")).encode()).hexdigest(),
        "ordered_instruction_commits_sha256": hashlib.sha256("\n".join(
            f'{e["kind"]}:{e["fields"].get("index","")}:{e["fields"].get("word","")}'
            for e in commit_rows if e["kind"] in ("INSTR_COMMIT","BOTH_COMMIT")).encode()).hexdigest()}
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest", type=Path); p.add_argument("--events", type=Path, required=True)
    p.add_argument("--checkpoint-frame", type=int, help="select a DSP_RUN/RUN_SNAPSHOT frame; defaults to manifest capture frame")
    p.add_argument("--prior-capture", type=Path, help="optional private prior RUN_SNAPSHOT capture for register continuity diagnostics")
    p.add_argument("--output", type=Path, help="redacted JSON output; keep private paths outside this checkout")
    a = p.parse_args()
    if a.output:
        out = a.output.resolve()
        if out == ROOT or ROOT in out.parents:
            p.error("report output must be outside the repository")
    gate = subprocess.run(["python3", str(MANIFEST_TOOL), str(a.manifest), "--require-replay-ready"],
                          capture_output=True, text=True)
    if gate.returncode:
        raise SystemExit("factory manifest gate failed; timeline state diagnostics withheld")
    result = analyze(a.events, a.manifest, a.checkpoint_frame, a.prior_capture)
    rendered = json.dumps(result, indent=2) + "\n"
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(rendered)
    print(rendered, end="")
    return 0 if result["halted_commit_summary"]["manifest_state_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
