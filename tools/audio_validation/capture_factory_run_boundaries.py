#!/usr/bin/env python3
"""Capture exact ES5510 first-instruction checkpoints for selected OS factory slots.

The OS display is used only to arm the next observed HALT-to-RUN transition.
The resulting program identity is read from that RUN snapshot and must be
correlated independently before a package is accepted. All outputs are private.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import esp_capture

PHASE = re.compile(r"ESPPHASE kind=([a-z0-9_]+)\s+(.*)$")
FIELD = re.compile(r"([a-z_]+)=([^\s]+)")
ARM = re.compile(r"ESP_EXPERIMENT_CAPTURE_ARM id=(\d+) .*?frame=(\d+)")
DONE = re.compile(r"ESP_EXPERIMENT_CAPTURE_COMPLETE id=(\d+) frame=(\d+)")

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cli", type=Path, required=True)
    p.add_argument("--roms", type=Path, required=True)
    p.add_argument("--disk", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--ids", required=True, help="comma-separated factory slots")
    p.add_argument("--raw-first", type=int, default=8)
    p.add_argument("--raw-last", type=int, default=79)
    p.add_argument("--start", type=float, default=16.0)
    p.add_argument("--interval", type=float, default=0.15)
    a = p.parse_args()
    out = a.out.expanduser().resolve()
    if out == ROOT or ROOT in out.parents:
        p.error("private capture output must be outside the checkout")
    ids = sorted({int(x) for x in a.ids.split(",") if x.strip()})
    if not ids or any(x < 1 or x > 50 for x in ids):
        p.error("ids must select one or more slots in 1..50")
    for f in (a.cli, a.disk): f.resolve(strict=True)
    a.roms.resolve(strict=True)
    out.mkdir(parents=True, exist_ok=False)
    snapdir = out / "snapshots"; snapdir.mkdir()
    args = [str(a.cli.resolve()), "--roms", str(a.roms.resolve()), "--disk", str(a.disk.resolve()),
            "--seconds", f"{a.start + (a.raw_last-a.raw_first+1)*a.interval + 1.0:.3f}",
            "--panel-log", "--trace-esp-io", "--button", "15:7:1", "--button", "15.2:7:0",
            "--wav", str(out / "selector.wav")]
    t = a.start
    for raw in range(a.raw_first, a.raw_last + 1):
        args += ["--analog-at", f"{t:.3f}:5:{raw}"]
        t += a.interval
    env = os.environ.copy()
    env.update({"ASR_ROUTE": "-1,-1,1,-1,0", "ASR_TEST_SINE": "440:0.25", "ESP_PIPELOG": "1",
                "ESP_HOSTLOG": "1", "ESP_EXPERIMENT_CAPTURE_ROM_IDS": ",".join(map(str, ids)),
                "ESP_EXPERIMENT_CAPTURE_WORDS": "0", "ESP_RUN_SNAPSHOT_DIR": str(snapdir)})
    log = out / "session.log"
    with log.open("w") as stream:
        subprocess.run(args, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)
    text = log.read_text(errors="replace")
    arms = [(int(m[1]), int(m[2])) for m in ARM.finditer(text)]
    dones = [(int(m[1]), int(m[2])) for m in DONE.finditer(text)]
    if sorted(x for x, _ in dones) != ids or len(dones) != len(ids):
        raise SystemExit(f"boundary capture set mismatch: requested={ids} completed={dones}")
    phases = []
    for line_no, line in enumerate(text.splitlines(), 1):
        m = PHASE.search(line)
        if m:
            f = dict(FIELD.findall(m.group(2))); f.update(kind=m.group(1), line=line_no); phases.append(f)
    records = []
    for slot, frame in dones:
        cap_path = snapdir / f"run-frame-{frame}.esp"
        if not cap_path.is_file(): raise SystemExit(f"missing RUN snapshot for slot {slot}: {cap_path.name}")
        cap = esp_capture.read_capture(cap_path)
        run = [x for x in phases if x["kind"] == "run_start" and int(x.get("frame", -1)) == frame]
        snap = [x for x in phases if x["kind"] == "run_snapshot" and int(x.get("frame", -1)) == frame]
        first = [x for x in phases if x["kind"] == "first_instruction" and int(x.get("frame", -1)) == frame]
        summary = [x for x in phases if x["kind"] == "program_upload_summary" and int(x.get("frame", -1)) == frame]
        if any(len(x) != 1 for x in (run, snap, first, summary)):
            raise SystemExit(f"slot {slot}: RUN boundary phases are missing or non-unique")
        run, snap, first, summary = run[0], snap[0], first[0], summary[0]
        if not (int(run["line"]) < int(snap["line"]) < int(first["line"])):
            raise SystemExit(f"slot {slot}: expected run_start < snapshot < first_instruction")
        if snap.get("ok") != "1" or snap.get("pc") != "00" or first.get("pc") != "00":
            raise SystemExit(f"slot {slot}: snapshot is not at PC 0 before first instruction")
        if cap["runtime"]["control"]["halted"] or cap["runtime"]["control"]["pc"] != 0:
            raise SystemExit(f"slot {slot}: checkpoint state is not running at PC 0")
        records.append({"slot": slot, "frame": frame, "checkpoint": str(cap_path),
                        "checkpoint_sha256": cap["file_sha256"],
                        "active_program_words": cap["program"]["active_words_through_first_END"],
                        "active_program_sha256": cap["program"]["active_program_sha256"],
                        "gpr_sha256": cap["registers"]["gpr_sha256"],
                        "special_sha256": cap["registers"]["special_sha256"],
                        "dram_sha256": cap["runtime"]["dram_sha256"],
                        "run_start": run, "run_snapshot": snap, "first_instruction": first,
                        "upload_summary": summary})
    report = {"schema": "es5510-selected-run-boundary-capture-v1", "requested_slots": ids,
              "completed_slots": sorted(x["slot"] for x in records), "arms": arms,
              "records": records, "private_log": str(log)}
    (out / "capture-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"requested": ids, "completed": report["completed_slots"],
                      "records": [{k: r[k] for k in ("slot", "frame", "active_program_words", "active_program_sha256")}
                                  for r in records], "private_output": str(out)}, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
