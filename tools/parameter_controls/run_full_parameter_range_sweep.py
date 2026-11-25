#!/usr/bin/env python3
"""Sweep one authentic OS 3.53 editor field and preserve LCD/GPR chronology.

The tool records an up-to-maximum, return-to-origin, down-to-minimum,
return-to-origin pass through the emulator's display-driven panel controller.
It does not infer a mapping from a single GPR write or interpolate values.
All raw logs/reports must be outside the repository and private source assets.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "parameter_controls"
sys.path.insert(0, str(TOOLS))
from run_factory_dsp_mapping_probe_v05 import select_field, parse_register_events  # noqa: E402

RANGE = re.compile(r"PANEL_RANGE_(FOUND|IDLE_END|MAX|MIN|RESTORE|ORIGIN_RESTORED|STEP_BEGIN|STEP_DONE|RETURN_FAILED|STEP_LIMIT)\b(.*)$")
FIELD = re.compile(r'(\w+)="([^"]*)"|([\w]+)=([^ ]+)')


def _fields(tail: str) -> dict[str, str]:
    result = {}
    for match in FIELD.finditer(tail):
        result[match.group(1) or match.group(3)] = match.group(2) if match.group(1) else match.group(4)
    return result


def documented_domain(slot: int, field_label: str) -> tuple[str | None, dict | None]:
    catalog = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json").read_text())
    effect = next((x for x in catalog["effects"] if x["slot"] == slot), None)
    parameter = next((x for x in (effect or {}).get("parameters", [])
                      if x["display_name"].upper() == field_label.upper()), None)
    if parameter is None:
        inventory = json.loads((ROOT / "docs/ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json").read_text())
        editor = next((x for x in inventory["entries"] if x["slot"] == slot), {})
        aliases = {field_label.upper()}
        matching = next((x for x in editor.get("manual_comparison", [])
                         if field_label.upper() in {v.upper() for v in x.get("observed_labels", [])}), None)
        if matching:
            parameter = next((x for x in (effect or {}).get("parameters", [])
                              if x["id"] == matching.get("id")), None)
    if not parameter:
        return None, None
    text = parameter.get("documented_range")
    match = re.fullmatch(r"\s*([+-]?\d+)\s+to\s+([+-]?\d+)\s*", text or "", re.I)
    domain = ({"minimum": int(match.group(1)), "maximum": int(match.group(2)), "step": 1}
              if match else None)
    return text, domain


def _lcd_number(event: dict | None) -> int | None:
    if not event:
        return None
    match = re.search(r"=\s*([+-]?\d+)\s*$", event.get("display", ""))
    return int(match.group(1)) if match else None


def parse_sweep_log(text: str) -> dict:
    events = []
    writes = parse_register_events(text)
    for line in text.splitlines():
        match = RANGE.search(line)
        if match:
            events.append({"event": match.group(1), **_fields(match.group(2))})
    starts = [e for e in events if e["event"] == "STEP_BEGIN"]
    done_by = {(e.get("segment"), e.get("step")): e for e in events if e["event"] == "STEP_DONE"}
    steps = []
    for start in starts:
        key = (start.get("segment"), start.get("step"))
        end = done_by.get(key)
        if not end:
            steps.append({"segment": key[0], "step": key[1], "complete": False,
                          "from_display": start.get("display"),
                          "start_cycles": int(start["cycles"]), "start_frame": int(start["frame"]),
                          "register_writes": []})
            continue
        first, last = int(start["cycles"]), int(end["cycles"])
        interval = [x for x in writes if first <= x["cycles"] < last]
        steps.append({"segment": key[0], "step": int(key[1]), "complete": True,
                      "direction": start.get("direction"), "from_display": start.get("display"),
                      "to_display": end.get("after"), "start_cycles": first, "end_cycles": last,
                      "start_frame": int(start["frame"]), "end_frame": int(end["frame"]),
                      "register_writes": interval})
    terminal = {}
    for e in events:
        if e["event"] in {"MAX", "MIN", "RESTORE", "ORIGIN_RESTORED", "RETURN_FAILED", "STEP_LIMIT"}:
            terminal[e["event"].lower()] = e
    # A panel phase transition can emit the exact-baseline notification while
    # omitting that final STEP_DONE record. Close only the unmatched return
    # step covered by this explicit event; preserve the missing-record fact.
    if terminal.get("origin_restored"):
        candidates = [x for x in steps if not x["complete"] and x["segment"] == "to_origin"]
        if candidates:
            step = candidates[-1]
            event = terminal["origin_restored"]
            # The legacy panel logger omits cycle/frame coordinates on this
            # marker. The corresponding final STEP_DONE is emitted just after
            # it, sometimes under the next phase's segment/step label.
            closing = next((x for x in events[events.index(event) + 1:]
                            if x["event"] == "STEP_DONE" and
                            x.get("after") == event.get("display")), None)
            end_cycles = int(event["cycles"]) if "cycles" in event else (
                int(closing["cycles"]) if closing and "cycles" in closing else None)
            end_frame = int(event["frame"]) if "frame" in event else (
                int(closing["frame"]) if closing and "frame" in closing else None)
            if end_cycles is not None and end_frame is not None:
                step["register_writes"] = [x for x in writes
                    if step["start_cycles"] <= x["cycles"] < end_cycles]
            step.update({"complete": True, "to_display": event.get("display"),
                         "end_cycles": end_cycles, "end_frame": end_frame,
                         "closed_by_origin_restored_event": True,
                         "close_coordinates_source": "following matching STEP_DONE" if closing else "origin marker"})
    # Endpoints are deliberately detected with one no-change key press. Accept
    # those two unmatched begin records only when the displayed value agrees
    # with the independently logged endpoint event.
    for step in steps:
        if step["complete"]:
            continue
        boundary = terminal.get("max" if step["segment"] == "to_max" else
                                "min" if step["segment"] == "to_min" else "")
        if boundary and step["from_display"] == boundary.get("display"):
            step["expected_endpoint_stop"] = True
    # Reconstruct the OS-visible host GPR image at each LCD transition. Many
    # coefficients are held across display values, so per-step writes alone
    # under-report the current register value.
    state = {}
    ordered_writes = sorted(writes, key=lambda x: (x["cycles"], x["event"]))
    complete_steps = sorted((x for x in steps if x["complete"]), key=lambda x: x["end_cycles"])
    write_index = 0
    transitions = {}
    for step in complete_steps:
        while write_index < len(ordered_writes) and ordered_writes[write_index]["cycles"] <= step["end_cycles"]:
            row = ordered_writes[write_index]
            state[row["gpr"]] = row["value24"]
            write_index += 1
        step["register_snapshot_after"] = dict(state)
        value_match = re.search(r"=\s*([+-]?\d+)\s*$", step["to_display"] or "")
        if not value_match:
            continue
        value = int(value_match.group(1))
        direction = "up" if step["segment"] in ("to_max", "restore") else "down"
        transitions.setdefault(value, {}).setdefault(direction, []).append(dict(state))
    points, gpr_counts, gpr_values = [], {}, {}
    consistency = {}
    pair_observations = [
        (value, rows["up"][-1], rows["down"][-1])
        for value, rows in transitions.items() if rows.get("up") and rows.get("down")]
    for value, up_state, down_state in pair_observations:
        for reg in set(up_state) | set(down_state):
            row = consistency.setdefault(reg, {"compared_values": 0, "equal_values": 0,
                                                "distinct_up_values": set(), "distinct_down_values": set()})
            row["compared_values"] += 1
            if up_state.get(reg) == down_state.get(reg):
                row["equal_values"] += 1
            if reg in up_state: row["distinct_up_values"].add(up_state[reg])
            if reg in down_state: row["distinct_down_values"].add(down_state[reg])
    for value in sorted(transitions):
        dirs = transitions[value]
        up_states, down_states = dirs.get("up", []), dirs.get("down", [])
        if not up_states and not down_states:
            continue
        up_state = up_states[-1] if up_states else {}
        down_state = down_states[-1] if down_states else {}
        common = ({reg: val for reg, val in up_state.items() if down_state.get(reg) == val}
                  if up_states and down_states else (up_state or down_state))
        points.append({"display_value": value, "reversible_register_state": common,
                       "up_register_state": up_state or None, "down_register_state": down_state or None,
                       "evidence_direction": "bidirectional" if up_states and down_states else "single_direction_endpoint",
                       "exact_state_match": bool(up_states and down_states and up_state == down_state),
                       "direction_pair_count": [len(up_states), len(down_states)]})
        for reg, val in common.items():
            gpr_counts[reg] = gpr_counts.get(reg, 0) + 1
            gpr_values.setdefault(reg, set()).add(val)
    min_value = max_value = None
    try:
        min_value = int(re.search(r"=\s*([+-]?\d+)\s*$", terminal["min"]["display"]).group(1))
        max_value = int(re.search(r"=\s*([+-]?\d+)\s*$", terminal["max"]["display"]).group(1))
    except (KeyError, AttributeError, TypeError, ValueError):
        pass
    compared_point_count = sum(bool(t.get("up") and t.get("down")) for t in transitions.values())
    eligible_gprs = sorted(reg for reg, count in gpr_counts.items()
                           if count == compared_point_count and len(gpr_values.get(reg, ())) > 1)
    consistency_summary = []
    for reg, row in sorted(consistency.items()):
        compared = row["compared_values"]
        equal = row["equal_values"]
        consistency_summary.append({"gpr": reg, "compared_values": compared, "equal_values": equal,
            "consistency": equal / compared if compared else 0.0,
            "distinct_up_values": len(row["distinct_up_values"]),
            "distinct_down_values": len(row["distinct_down_values"]),
            "candidate_only": equal < compared})
    all_values_observed = (min_value is not None and max_value is not None and
                           len(points) == max_value - min_value + 1 and
                           [p["display_value"] for p in points] == list(range(min_value, max_value + 1)))
    for point in points:
        if point["up_register_state"] and point["down_register_state"] and eligible_gprs:
            point["exact_state_match"] = all(
                point["up_register_state"].get(reg) == point["down_register_state"].get(reg)
                for reg in eligible_gprs)
    all_interior_values_reversible = all(p["exact_state_match"] for p in points
                                         if min_value is not None and min_value < p["display_value"] < max_value)
    complete_mapping = all_values_observed and all_interior_values_reversible and bool(eligible_gprs)
    return {"events": events, "steps": steps, "terminal": terminal,
            "total_host_gpr_writes": len(writes),
            "sweep_complete": bool(terminal.get("max") and terminal.get("min") and terminal.get("restore")) and
                              not terminal.get("return_failed") and not terminal.get("step_limit") and
                              all(x["complete"] or x.get("expected_endpoint_stop") for x in steps),
            "reversible_points": points,
            "mapping_analysis": {"minimum": min_value, "maximum": max_value,
                "candidate_gprs_written_with_same_value_in_both_directions": eligible_gprs,
                "all_display_values_observed": all_values_observed,
                "all_interior_values_reversible": all_interior_values_reversible,
                "endpoint_values_have_one_direction_evidence": any(p["evidence_direction"] != "bidirectional" for p in points),
                "complete_exact_point_mapping": complete_mapping,
                "per_gpr_bidirectional_consistency": consistency_summary,
                "warning": "Only intersecting exact up/down GPR values are promoted; raw event windows remain attached to every step."}}


def build_command(args, selector: dict, location: dict, log_id: str) -> list[str]:
    raw = int(selector["select_raw"])
    if not 8 <= raw <= 1023:
        raise ValueError("selector raw is outside supported 8..1023")
    command = [str(args.cli.resolve(strict=True)), "--roms", str(args.roms.resolve(strict=True)),
               "--disk", str(args.disk.resolve(strict=True)), "--wav", "/dev/null",
               "--panel-log", "--log-rom-select",
               "--panel-tap-on-display", "0,25,7,NO INST OR BANK FILES,fx_select"]
    scan_end = 16.0 + .15 * (raw - 8)
    for i, value in enumerate(range(8, raw + 1)):
        command += ["--analog-at", f"{16.0 + .15 * i:.2f}:5:{value}"]
    settled = scan_end + .5
    field_timeout = args.field_timeout
    field_args = [f"{settled:.2f}", f"{field_timeout:.2f}", str(args.variation),
                  str(location["page"]["ordinal"]), str(location["marker_start"]), "0",
                  str(args.edit_button), str(args.revert_button), location["needle"], "field_select"]
    sweep_after = settled + field_timeout + 2.0
    range_args = [f"{sweep_after:.2f}", f"{args.max_sweep_seconds:.2f}",
                  f"{args.settle_seconds:.2f}", location["needle"], log_id]
    command += ["--seconds", f"{sweep_after + args.max_sweep_seconds:.2f}",
                "--panel-tap-on-display", f"{settled:.2f},45,5,FX=ROM-{args.slot:02d},edit",
                "--panel-tap-on-display", f"{settled:.2f},45,9,FREE,effects",
                "--panel-probe-field", ",".join(field_args),
                "--panel-probe-range", ",".join(range_args)]
    return command


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cli", type=Path, required=True)
    ap.add_argument("--roms", type=Path, required=True)
    ap.add_argument("--disk", type=Path, required=True)
    ap.add_argument("--selector-inventory", type=Path, required=True)
    ap.add_argument("--editor-inventory", type=Path, default=ROOT / "docs/ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json")
    ap.add_argument("--slot", type=int, required=True)
    ap.add_argument("--variation", type=int, default=1)
    ap.add_argument("--field", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--field-timeout", type=float, default=30.0)
    ap.add_argument("--max-sweep-seconds", type=float, default=300.0)
    ap.add_argument("--settle-seconds", type=float, default=0.75,
                    help="quiet period after each changed LCD value before closing its GPR write window")
    ap.add_argument("--edit-button", type=int, default=10)
    ap.add_argument("--revert-button", type=int, default=11)
    args = ap.parse_args()
    if not 1 <= args.slot <= 50 or not 1 <= args.variation <= 4:
        ap.error("slot must be 1..50 and variation 1..4")
    if args.field_timeout <= 0 or args.max_sweep_seconds <= 0 or args.settle_seconds <= 0:
        ap.error("timeouts must be positive")
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        ap.error("raw capture and report output must be outside the Git repository")
    selectors = json.loads(args.selector_inventory.read_text())
    selector = next((x for x in selectors["entries"] if int(x["id"]) == args.slot), None)
    if not selector:
        ap.error(f"slot {args.slot} is missing from selector inventory")
    inventory = json.loads(args.editor_inventory.read_text())
    location = select_field(inventory, args.slot, args.variation, args.field)
    output.mkdir(parents=True, exist_ok=True)
    token = re.sub(r"[^a-z0-9]+", "-", args.field.lower()).strip("-")
    log_path = output / f"slot-{args.slot:02d}-var{args.variation}-{token}-range.log"
    report_path = output / f"slot-{args.slot:02d}-var{args.variation}-{token}-range.json"
    command = build_command(args, selector, location, "full_range_sweep")
    env = dict(os.environ, ESP_HOSTLOG="1", ASR_ROUTE="-1,-1,1,-1,0", ASR_TEST_SINE="440:0.25")
    with log_path.open("w") as stream:
        run = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=env, check=False)
    parsed = parse_sweep_log(log_path.read_text(errors="replace"))
    selected = any("PANEL_FIELD_SELECTED id=field_select" in line for line in log_path.read_text(errors="replace").splitlines())
    range_text, manual_domain = documented_domain(args.slot, args.field)
    observed_min, observed_max = _lcd_number(parsed["terminal"].get("min")), _lcd_number(parsed["terminal"].get("max"))
    domain_matches_manual = (bool(manual_domain) and observed_min == manual_domain["minimum"] and
                             observed_max == manual_domain["maximum"])
    ui_range_status = ("OS_RANGE_VERIFIED" if parsed["sweep_complete"] and domain_matches_manual else
                       "OS_BOUNDS_OBSERVED_MANUAL_RANGE_UNCONFIRMED" if parsed["sweep_complete"] else "INCOMPLETE")
    report = {"schema": "trollfx-asr10-full-parameter-range-sweep-v1", "slot": args.slot,
              "factory_name": next(x["factory_name"] for x in inventory["entries"] if x["slot"] == args.slot),
              "variation": args.variation, "parameter_label": args.field,
              "documented_range": range_text, "documented_domain": manual_domain,
              "observed_domain": ({"minimum": observed_min, "maximum": observed_max, "step": 1}
                                  if observed_min is not None and observed_max is not None else None),
              "domain_matches_manual": domain_matches_manual, "ui_range_status": ui_range_status,
              "inventory_default_or_observation": location["field"].get("displayed_value"),
              "v4_page_ordinal": location["page"]["ordinal"], "selection_marker_start": location["marker_start"],
              "field_selection_verified": selected, "exit_code": run.returncode,
              "raw_log": str(log_path), "report_path": str(report_path), **parsed}
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(report_path), "selected": selected,
                      "sweep_complete": report["sweep_complete"], "step_count": len(parsed["steps"]),
                      "ui_range_status": ui_range_status, "domain_matches_manual": domain_matches_manual,
                      "max": parsed["terminal"].get("max"), "min": parsed["terminal"].get("min"),
                      "restore": parsed["terminal"].get("restore"), "exit_code": run.returncode}, indent=2))
    if run.returncode or not selected or not report["sweep_complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
