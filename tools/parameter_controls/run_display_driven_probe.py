#!/usr/bin/env python3
"""Boot OS 3.53 and probe a factory parameter using observed panel text.

The CLI supplies test-only, read-only display observation and condition-gated
panel taps. Effect selection uses the existing selector sweep, then every
navigation/edit action is gated by the live 22-character panel display.
"""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENT = re.compile(r"ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-f]+) gpr ([0-9a-f]{2}) <- ([0-9a-f]{6})", re.I)
ROM_SELECT = re.compile(r"ESP_ROM_SELECT id=(\d+) time=([0-9.]+).*?display=(.*)$")
KV = re.compile(r"(PANEL_[A-Z_]+) id=([^ ]+)(.*)$")
FIELD = re.compile(r"(\w+)=\"([^\"]*)\"|(\w+)=([^ ]+)")


def display_events(text):
    result = []
    for line in text.splitlines():
        m = KV.search(line)
        if not m:
            continue
        fields = {}
        for f in FIELD.finditer(m.group(3)):
            key = f.group(1) or f.group(3)
            fields[key] = f.group(2) if f.group(1) else f.group(4)
        result.append({"event": m.group(1), "id": m.group(2), **fields})
    return result


def summarize_window(host_events, start_cycles, end_cycles):
    selected = [e for e in host_events if start_cycles <= e["cycles"] < end_cycles]
    last_before = {}
    for e in host_events:
        if e["cycles"] < start_cycles:
            last_before[e["gpr"]] = e["value"]
    last_after = dict(last_before)
    for e in selected:
        last_after[e["gpr"]] = e["value"]
    by_register = {}
    for register in sorted({e["gpr"] for e in selected}):
        writes = [e for e in selected if e["gpr"] == register]
        values = [e["value"] for e in writes]
        by_register[f"0x{register:02x}"] = {
            "write_count": len(writes),
            "distinct_values": len(set(values)),
            "first_value24": f"0x{values[0]:06x}",
            "last_value24": f"0x{values[-1]:06x}",
        }
    return {
        "cycle_window": [start_cycles, end_cycles],
        "host_write_count": len(selected),
        "register_activity": by_register,
        "variable_registers": [register for register, row in by_register.items() if row["distinct_values"] > 1],
        "writes": [{"cycles": e["cycles"], "frame": e["frame"], "pc": f"0x{e['pc']:08x}",
                    "gpr": f"0x{e['gpr']:02x}", "value24": f"0x{e['value']:06x}"} for e in selected],
        "changed_registers": [{"gpr": f"0x{reg:02x}",
                                "before": None if reg not in last_before else f"0x{last_before[reg]:06x}",
                                "after": f"0x{last_after[reg]:06x}"}
                               for reg in sorted({e["gpr"] for e in selected}) if last_after.get(reg) != last_before.get(reg)],
    }


def summarize_log(text, expected_slot):
    events = []
    for m in EVENT.finditer(text):
        events.append({"event": int(m.group(1)), "cycles": int(m.group(2)), "frame": int(m.group(3)),
                       "pc": int(m.group(4), 16), "gpr": int(m.group(5), 16), "value": int(m.group(6), 16)})
    panel = display_events(text)
    selects = [{"slot": int(m.group(1)), "time": float(m.group(2)), "display": m.group(3), "source": "ESP_ROM_SELECT"}
               for line in text.splitlines() if (m := ROM_SELECT.search(line))]
    # A stable, full FX=ROM-NN selection display immediately before the Edit
    # action is also direct selector evidence if the emulator's optional
    # ESP_ROM_SELECT logger did not emit a row.
    for event in display_events(text):
        if event["event"] == "PANEL_TAP_BEGIN" and event.get("id") == "edit":
            display = event.get("before", "")
            m = re.search(r"FX=ROM-(\d{2})", display)
            if m:
                selects.append({"slot": int(m.group(1)), "time": float(event["time"]),
                                "display": display, "source": "Edit-entry display"})
    by_id = {}
    for e in panel:
        by_id.setdefault(e["id"], []).append(e)
    probes = []
    for probe_id, group in by_id.items():
        get = lambda name: next((e for e in group if e["event"] == name), None)
        found, idle_b, idle_e = get("PANEL_PROBE_FOUND"), get("PANEL_PROBE_IDLE_BEGIN"), get("PANEL_PROBE_IDLE_END")
        if not found:
            continue
        row = {"id": probe_id, "candidate_display_before": found.get("display"),
               "baseline_window": None, "trials": []}
        if idle_b and idle_e:
            row["baseline_window"] = summarize_window(events, int(idle_b["cycles"]), int(idle_e["cycles"]))
        ups = [e for e in group if e["event"] == "PANEL_PROBE_UP_BEGIN"]
        for up in ups:
            n = up["iteration"]
            up_end = next((e for e in group if e["event"] == "PANEL_PROBE_DOWN_BEGIN" and e.get("iteration") == n), None)
            down_start = up_end
            restore = next((e for e in group if e["event"] == "PANEL_PROBE_RESTORE" and e.get("iteration") == n), None)
            up_display = next((e for e in group if e["event"] == "PANEL_PROBE_UP_DISPLAY" and e.get("iteration") == n), None)
            down_display = next((e for e in group if e["event"] == "PANEL_PROBE_DOWN_DISPLAY" and e.get("iteration") == n), None)
            trial = {"iteration": int(n), "up_before": up.get("display"),
                     "up_after": None if up_display is None else up_display.get("after"),
                     "down_after": None if down_display is None else down_display.get("after"),
                     "restored_exactly": None if restore is None else restore.get("exact") == "1"}
            if up_end:
                trial["up_host_writes"] = summarize_window(events, int(up["cycles"]), int(up_end["cycles"]))
            if down_start and restore:
                trial["down_host_writes"] = summarize_window(events, int(down_start["cycles"]), int(restore["cycles"]))
            row["trials"].append(trial)
        probes.append(row)
    return {"selected_effect_slots_observed": selects,
            "expected_slot": expected_slot,
            "selection_verified": any(s["slot"] == expected_slot for s in selects),
            "panel_events": panel, "probes": probes,
            "warning": "Host writes are correlated with display-driven action windows; baseline comparison is required before assigning a GPR. Periodic or modulated writes are not automatically classified as parameter writes."}


def build_command(args, entry, candidate, id_token):
    slot = entry["id"]
    raw = int(entry["select_raw"])
    if raw < 8 or raw > 1023:
        raise ValueError("selector inventory raw value outside the supported analog range")
    command = [str(args.cli.resolve()), "--roms", str(args.roms.resolve()), "--disk", str(args.disk.resolve()),
               "--wav", str(args.output / f"slot-{slot:02d}-{id_token}.wav"),
               "--panel-log", "--log-rom-select"]
    # FX Select page selection: this slot list needs a slow knob sweep. Every
    # resulting LCD transition is observed and checked for the requested slot.
    command += ["--panel-tap-on-display", "0,25,7,NO INST OR BANK FILES,fx_select"]
    scan_end = 16.0 + 0.15 * (raw - 8)
    for i, value in enumerate(range(8, raw + 1)):
        command += ["--analog-at", f"{16.0 + 0.15*i:.2f}:5:{value}"]
    code = f"FX=ROM-{slot:02d}"
    # Do not navigate while the selector sweep is still changing the active
    # factory slot. Earlier trial exposed a real race: the display briefly
    # showed HALL before the final analog selector event.
    settled = scan_end + 0.5
    run_seconds = max(args.seconds, settled + 8.0)
    command += ["--seconds", f"{run_seconds:.2f}"]
    command += ["--panel-tap-on-display", f"{settled:.2f},45,5,{code},edit"]
    command += ["--panel-tap-on-display", f"{settled:.2f},45,9,FREE,effects"]
    command += ["--panel-mark-on-display", f"{settled:.2f},45,VAR=,variation"]
    command += ["--panel-search-right", f"{settled:.2f},45,64,VAR=,{candidate},candidate_search"]
    command += ["--panel-probe-control", f"{settled:.2f},45,2,{candidate},candidate_probe,{args.revert_button}"]
    return command


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cli", type=Path, required=True)
    ap.add_argument("--roms", type=Path, required=True)
    ap.add_argument("--disk", type=Path, required=True)
    ap.add_argument("--inventory", type=Path, required=True, help="private inventory.json from the authorized 50-slot sweep")
    ap.add_argument("--slot", type=int, required=True)
    ap.add_argument("--candidate", required=True, help="short display substring from the documented catalog, e.g. DIFFUSION")
    ap.add_argument("--seconds", type=float, default=55)
    ap.add_argument("--repetitions", type=int, default=2, help="reversible probe repetitions; 0 records a stable no-edit baseline")
    ap.add_argument("--revert-button", type=int, default=11, help="panel button used to reverse the edit (11=Down, 33=Cancel/No)")
    ap.add_argument("--output", type=Path, required=True, help="private results directory outside Git")
    args = ap.parse_args()
    inventory = json.loads(args.inventory.read_text())
    entry = next((x for x in inventory["entries"] if x["id"] == args.slot), None)
    if not entry:
        raise SystemExit(f"slot {args.slot} missing from selector inventory")
    token = re.sub(r"[^a-z0-9]+", "-", args.candidate.lower()).strip("-")
    args.output.mkdir(parents=True, exist_ok=True)
    if not 0 <= args.repetitions <= 4:
        ap.error("--repetitions must be between 0 and 4")
    if not 0 <= args.revert_button <= 41:
        ap.error("--revert-button must be a panel button code from 0 through 41")
    command = build_command(args, entry, args.candidate, token)
    probe_arg = command.index("--panel-probe-control") + 1
    probe_fields = command[probe_arg].split(",")
    probe_fields[2] = str(args.repetitions)
    command[probe_arg] = ",".join(probe_fields)
    log_path = args.output / f"slot-{args.slot:02d}-{token}.log"
    report_path = args.output / f"slot-{args.slot:02d}-{token}-report.json"
    env = dict(os.environ, ESP_HOSTLOG="1", ASR_ROUTE="-1,-1,1,-1,0", ASR_TEST_SINE="440:0.25")
    with log_path.open("w") as stream:
        run = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=env, check=False)
    text = log_path.read_text(errors="replace")
    report = summarize_log(text, args.slot)
    report.update({"candidate": args.candidate, "variation": next((p.get("display") for p in report["panel_events"] if p["id"] == "variation"), None),
                   "simulated_seconds": max(args.seconds, 16.0 + 0.15 * (int(entry["select_raw"]) - 8) + 8.5),
                   "exit_code": run.returncode, "raw_log": str(log_path), "audio_file": command[command.index("--wav") + 1]})
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"slot={args.slot} candidate={args.candidate} selected={report['selection_verified']} probes={len(report['probes'])} exit={run.returncode}")
    if run.returncode or not report["selection_verified"] or not report["probes"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
