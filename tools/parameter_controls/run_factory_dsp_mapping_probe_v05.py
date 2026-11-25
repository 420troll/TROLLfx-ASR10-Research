#!/usr/bin/env python3
"""Run a reversible OS 3.53 edit at an exact V4-inventoried editor field.

The V4 page ordinal and live underline marker disambiguate compact LCD rows.
Raw emulator logs and ordered host GPR events stay in the private output tree.
This script records evidence; it never promotes an unverified curve.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENT = re.compile(r"ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-f]+) (?:caller=[0-9a-f]+ )?(?:gpr ([0-9a-f]{2}) <- ([0-9a-f]{6})|both ([0-9a-f]{2}) <- ([0-9a-f]{12}) / ([0-9a-f]{6}))", re.I)
PANEL = re.compile(r"(PANEL_[A-Z_]+) id=([^ ]+)(.*)$")
FIELD = re.compile(r'(\w+)="([^"]*)"|(\w+)=([^ ]+)')


def parse_panel_event(line: str):
    match = PANEL.search(line)
    if not match:
        return None
    fields = {}
    for f in FIELD.finditer(match.group(3)):
        key = f.group(1) or f.group(3)
        fields[key] = f.group(2) if f.group(1) else f.group(4)
    return {"event": match.group(1), "id": match.group(2), **fields}


def parse_register_events(text: str):
    events = []
    for line in text.splitlines():
        m = EVENT.search(line)
        if not m:
            continue
        paired = m.group(7) is not None
        row = {"event": int(m.group(1)), "cycles": int(m.group(2)), "frame": int(m.group(3)),
               "pc": "0x" + m.group(4), "write_kind": "instruction_and_gpr" if paired else "gpr",
               "gpr": "0x" + (m.group(7) if paired else m.group(5)),
               "value24": "0x" + (m.group(9) if paired else m.group(6))}
        if paired:
            row["instruction_word"] = "0x" + m.group(8)
        events.append(row)
    return events


def summarize_write_window(events, start_cycles, end_cycles):
    rows = [e for e in events if start_cycles <= e["cycles"] < end_cycles]
    by_gpr = {}
    for gpr in sorted({e["gpr"] for e in rows}):
        writes = [e for e in rows if e["gpr"] == gpr]
        by_gpr[gpr] = {"count": len(writes), "first": writes[0]["value24"],
                       "last": writes[-1]["value24"], "distinct_values": len({e["value24"] for e in writes})}
    return {"cycle_window": [start_cycles, end_cycles], "write_count": len(rows),
            "write_kinds": sorted({e["write_kind"] for e in rows}), "gpr_summary": by_gpr,
            "ordered_writes": rows}


def state_delta(events, start_cycles, end_cycles):
    before, after = {}, {}
    for e in events:
        if e["cycles"] < start_cycles:
            before[e["gpr"]] = e["value24"]
        if e["cycles"] < end_cycles:
            after[e["gpr"]] = e["value24"]
    changed = []
    for gpr, value in sorted(after.items()):
        if before.get(gpr) != value:
            changed.append({"gpr": gpr, "before": before.get(gpr), "after": value})
    return changed


def select_field(inventory, slot, variation, field_label):
    effect = next((e for e in inventory["entries"] if e["slot"] == slot), None)
    if not effect or effect.get("status") != "complete":
        raise ValueError(f"slot {slot} has no completed V4 editor inventory")
    matches = []
    for page in effect["pages"]:
        if page["variation"] != variation:
            continue
        for field in page.get("displayed_fields", []):
            if field["label"] == field_label:
                selected = [x for x in page.get("selected_fields", []) if x.get("field_label") == field_label]
                matches.append((page, field, selected))
    marked_matches = [row for row in matches if row[2]]
    if marked_matches:
        matches = marked_matches
    if len(matches) != 1:
        raise ValueError(f"expected one V4 location for {slot=} {variation=} {field_label=}, found {len(matches)}")
    page, field, selected = matches[0]
    marker_start = selected[0]["cursor_span"][0] if selected else -1
    marker_kind = selected[0]["marker"] if selected else None
    display = page["display"]
    needle = field_label if field_label in display else field_label.split()[-1] + "="
    if needle not in display:
        raise ValueError(f"field label cannot be located in its V4 LCD: {field_label!r} / {display!r}")
    return {"page": page, "field": field, "marker_start": marker_start,
            "marker_kind": marker_kind, "needle": needle}


def build_command(args, selector, location):
    raw = int(selector["select_raw"])
    if not 8 <= raw <= 1023:
        raise ValueError(f"slot {args.slot} selector value outside 8..1023")
    command = [str(args.cli.resolve()), "--roms", str(args.roms.resolve()), "--disk", str(args.disk.resolve()),
               "--wav", "/dev/null", "--panel-log", "--log-rom-select",
               "--panel-tap-on-display", "0,25,7,NO INST OR BANK FILES,fx_select"]
    scan_end = 16.0 + 0.15 * (raw - 8)
    for i, value in enumerate(range(8, raw + 1)):
        command += ["--analog-at", f"{16.0 + 0.15 * i:.2f}:5:{value}"]
    settled = scan_end + 0.5
    probe = [f"{settled:.2f}", f"{args.timeout:.2f}", str(args.variation),
             str(location["page"]["ordinal"]), str(location["marker_start"]),
             str(args.repetitions), str(args.edit_button),
             str(args.revert_button), location["needle"], "v05_probe"]
    command += ["--seconds", f"{settled + args.timeout + 1:.2f}",
                "--panel-tap-on-display", f"{settled:.2f},45,5,FX=ROM-{args.slot:02d},edit",
                "--panel-tap-on-display", f"{settled:.2f},45,9,FREE,effects",
                "--panel-probe-field", ",".join(probe)]
    return command


def summarize(text, register_events, slot, variation, field_label):
    panel = [e for line in text.splitlines() if (e := parse_panel_event(line))]
    selected = next((e for e in panel if e["id"] == "v05_probe" and e["event"] == "PANEL_FIELD_SELECTED"), None)
    selection = []
    for line in text.splitlines():
        m = re.search(r"ESP_ROM_SELECT id=(\d+) .*?display=(.*)$", line)
        if m:
            selection.append({"slot": int(m.group(1)), "display": m.group(2), "source": "ESP_ROM_SELECT"})
    names = ("PANEL_PROBE_IDLE_BEGIN", "PANEL_PROBE_IDLE_END", "PANEL_PROBE_UP_BEGIN",
             "PANEL_PROBE_UP_DISPLAY", "PANEL_PROBE_DOWN_BEGIN", "PANEL_PROBE_DOWN_DISPLAY",
             "PANEL_PROBE_RESTORE")
    by_name = {name: [e for e in panel if e["id"] == "v05_probe" and e["event"] == name] for name in names}
    baseline = None
    if by_name["PANEL_PROBE_IDLE_BEGIN"] and by_name["PANEL_PROBE_IDLE_END"]:
        baseline = summarize_write_window(register_events,
            int(by_name["PANEL_PROBE_IDLE_BEGIN"][0]["cycles"]), int(by_name["PANEL_PROBE_IDLE_END"][0]["cycles"]))
    trials = []
    for begin in by_name["PANEL_PROBE_UP_BEGIN"]:
        iteration = begin["iteration"]
        up = next((e for e in by_name["PANEL_PROBE_UP_DISPLAY"] if e.get("iteration") == iteration), None)
        revert_begin = next((e for e in by_name["PANEL_PROBE_DOWN_BEGIN"] if e.get("iteration") == iteration), None)
        revert = next((e for e in by_name["PANEL_PROBE_DOWN_DISPLAY"] if e.get("iteration") == iteration), None)
        restore = next((e for e in by_name["PANEL_PROBE_RESTORE"] if e.get("iteration") == iteration), None)
        row = {"iteration": int(iteration), "edit_button": int(begin.get("button", 10)),
               "before_lcd": begin.get("display"), "after_edit_lcd": None if up is None else up.get("after"),
               "revert_button": None if revert_begin is None else int(revert_begin.get("button", 11)),
               "after_revert_lcd": None if revert is None else revert.get("after"),
               "restored_exactly": None if restore is None else restore.get("exact") == "1"}
        if up:
            row["edit_register_window"] = summarize_write_window(register_events, int(begin["cycles"]), int(up["cycles"]))
            row["edit_state_delta"] = state_delta(register_events, int(begin["cycles"]), int(up["cycles"]))
        if revert_begin and revert:
            row["revert_register_window"] = summarize_write_window(register_events,
                int(revert_begin["cycles"]), int(revert["cycles"]))
            row["revert_state_delta"] = state_delta(register_events, int(revert_begin["cycles"]), int(revert["cycles"]))
        trials.append(row)
    failures = [e for e in panel if e.get("id") == "v05_probe" and e["event"] in
                {"PANEL_FIELD_TARGET_MISMATCH", "PANEL_FIELD_NAV_NO_CHANGE", "PANEL_ACTION_TIMEOUT"}]
    stable_edits = None
    stable_ordered_writes = None
    stable_edit_write_values = None
    stable_revert_write_values = None
    if trials and all("edit_state_delta" in t for t in trials):
        maps = [{(x["gpr"], x["before"], x["after"]) for x in t["edit_state_delta"]} for t in trials]
        common = set.intersection(*maps) if maps else set()
        stable_edits = [{"gpr": gpr, "before": before, "after": after, "trials": len(trials)}
                        for gpr, before, after in sorted(common)]
        if common and trials[0].get("edit_register_window"):
            first_window = trials[0]["edit_register_window"]["ordered_writes"]
            used, ordered = set(), []
            for write in first_window:
                key = (write["gpr"], write["value24"])
                if any(gpr == write["gpr"] and after == write["value24"] for gpr, before, after in common) and key not in used:
                    ordered.append({"gpr": write["gpr"], "value24": write["value24"],
                                    "event": write["event"], "cycles": write["cycles"],
                                    "write_kind": write["write_kind"]})
                    used.add(key)
            stable_ordered_writes = ordered
    active_baseline_gprs = [] if baseline is None else sorted(baseline["gpr_summary"])
    def repeated_window_values(window_key):
        windows = [t.get(window_key, {}).get("ordered_writes", []) for t in trials]
        if not windows or any(not w for w in windows):
            return []
        registers = set.intersection(*[{w["gpr"] for w in rows} for rows in windows])
        result = []
        baseline_values = {} if baseline is None else {
            gpr: {w["value24"] for w in baseline["ordered_writes"] if w["gpr"] == gpr}
            for gpr in baseline["gpr_summary"]}
        for gpr in sorted(registers):
            values_by_trial = [{w["value24"] for w in rows if w["gpr"] == gpr} for rows in windows]
            common_values = set.intersection(*values_by_trial)
            first_order = []
            for write in windows[0]:
                if write["gpr"] == gpr and write["value24"] in common_values and write["value24"] not in first_order:
                    first_order.append(write["value24"])
            if common_values:
                result.append({"gpr": gpr, "values_seen_in_every_trial": first_order,
                               "values_also_seen_in_no_edit_baseline": sorted(common_values & baseline_values.get(gpr, set()))})
        return result
    if trials:
        stable_edit_write_values = repeated_window_values("edit_register_window")
        stable_revert_write_values = repeated_window_values("revert_register_window")
    return {"schema": "trollfx-asr10-v05-register-probe-evidence-v1", "slot": slot,
            "variation": variation, "field_label": field_label,
            "selection_verified": any(e["slot"] == slot for e in selection), "selector_events": selection,
            "field_selection": selected, "probe_trials": trials, "baseline_register_window": baseline,
            "baseline_active_gprs": active_baseline_gprs,
            "stable_edit_state_deltas_across_trials": stable_edits,
            "stable_ordered_write_group_from_first_trial": stable_ordered_writes,
            "stable_edit_write_values_across_trials": stable_edit_write_values,
            "stable_revert_write_values_across_trials": stable_revert_write_values,
            "panel_failures": failures, "probe_restored": bool(trials) and all(x["restored_exactly"] for x in trials),
            "raw_register_event_count": len(register_events),
            "evidence_note": "Write windows retain standalone and paired instruction/GPR host writes. Baseline comparison is required before attributing writes to the edited field."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cli", type=Path)
    ap.add_argument("--roms", type=Path)
    ap.add_argument("--disk", type=Path)
    ap.add_argument("--selector-inventory", type=Path)
    ap.add_argument("--editor-inventory", type=Path, default=ROOT / "docs/ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json")
    ap.add_argument("--slot", type=int, required=True)
    ap.add_argument("--variation", type=int, default=1)
    ap.add_argument("--field", required=True)
    ap.add_argument("--edit-button", type=int, choices=(10, 11), default=10, help="10=Up; 11=Down")
    ap.add_argument("--revert-button", type=int, choices=(10, 11), help="defaults to the opposite direction")
    ap.add_argument("--repetitions", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=90)
    ap.add_argument("--output", type=Path, required=True, help="private output directory outside Git")
    ap.add_argument("--raw-log", type=Path, help="reparse an existing private log without rerunning the emulator")
    args = ap.parse_args()
    if args.slot == 2:
        raise SystemExit("slot 02 is deferred and cannot be probed")
    if not 1 <= args.slot <= 50 or not 1 <= args.variation <= 4 or not 0 <= args.repetitions <= 4:
        ap.error("slot, variation, or repetitions outside supported bounds")
    if args.timeout <= 0:
        ap.error("timeout must be positive")
    if args.revert_button is None:
        args.revert_button = 11 if args.edit_button == 10 else 10
    editor = json.loads(args.editor_inventory.read_text())
    location = select_field(editor, args.slot, args.variation, args.field)
    args.output.mkdir(parents=True, exist_ok=True)
    token = re.sub(r"[^a-z0-9]+", "-", args.field.lower()).strip("-")
    if args.raw_log:
        log_path = args.raw_log.resolve(strict=True)
        evidence_path = log_path.with_name(log_path.stem + "-evidence.json")
        exit_code = 0
    else:
        if not (args.cli and args.roms and args.disk and args.selector_inventory):
            ap.error("--cli, --roms, --disk, and --selector-inventory are required unless --raw-log is used")
        selectors = json.loads(args.selector_inventory.read_text())
        selector = next((e for e in selectors["entries"] if int(e["id"]) == args.slot), None)
        if not selector:
            raise SystemExit(f"slot {args.slot} missing from selector inventory")
        log_path = args.output / f"slot-{args.slot:02d}-var{args.variation}-{token}.log"
        evidence_path = args.output / f"slot-{args.slot:02d}-var{args.variation}-{token}-evidence.json"
        command = build_command(args, selector, location)
        env = dict(os.environ, ESP_HOSTLOG="1", ASR_ROUTE="-1,-1,1,-1,0", ASR_TEST_SINE="440:0.25")
        with log_path.open("w") as stream:
            run = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=env, check=False)
        exit_code = run.returncode
    text = log_path.read_text(errors="replace")
    gpr = parse_register_events(text)
    report = summarize(text, gpr, args.slot, args.variation, args.field)
    report.update({"recorded_lcd": location["page"]["display"],
                   "recorded_display_value": location["field"]["displayed_value"],
                   "page_ordinal": location["page"]["ordinal"],
                   "expected_cursor_marker_start": location["marker_start"],
                   "expected_cursor_marker_kind": location["marker_kind"],
                   "edit_button": args.edit_button, "revert_button": args.revert_button,
                   "exit_code": exit_code, "raw_log": str(log_path)})
    evidence_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"slot={args.slot:02d} variation={args.variation} field={args.field!r} "
          f"selected={bool(report['field_selection'])} trials={len(report['probe_trials'])} "
          f"restored={report['probe_restored']} exit={exit_code}")
    valid_probe = (args.repetitions == 0) or (report["probe_trials"] and report["probe_restored"])
    if exit_code or not report["selection_verified"] or not report["field_selection"] or not valid_probe:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
