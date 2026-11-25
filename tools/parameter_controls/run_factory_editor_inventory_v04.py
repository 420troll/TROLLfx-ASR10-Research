#!/usr/bin/env python3
"""Resumably scan OS 3.53 EDIT/EFFECTS pages for the non-deferred ROM slots.

All raw emulator logs and WAV sinks belong outside the repository. The scanner
uses physical front-panel events and exact 22-character display snapshots.
It never writes effect values except selecting the four VAR presets.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENT = re.compile(r"PANEL_EDITOR_(PAGE|VARIATION_BEGIN|VARIATION_DONE|SCAN_DONE|SCAN_NO_CHANGE|SCAN_PAGE_LIMIT|VARIATION_FAILED) id=([^ ]+)(.*)$")
FIELD = re.compile(r'(\w+)="([^"]*)"|(\w+)=([^ ]+)')
GPR_WRITE = re.compile(
    r"ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-f]+) "
    r"(?:gpr ([0-9a-f]{2}) <- ([0-9a-f]{6})|"
    r"both ([0-9a-f]{2}) <- ([0-9a-f]{12}) / ([0-9a-f]{6}))", re.I)


def event_fields(line: str):
    match = EVENT.search(line)
    if not match:
        return None
    fields = {}
    for item in FIELD.finditer(match.group(3)):
        key = item.group(1) or item.group(3)
        fields[key] = item.group(2) if item.group(1) else item.group(4)
    return {"event": match.group(1), "id": match.group(2), **fields}


def marked_spans(markers: str):
    spans, start = [], None
    for index, char in enumerate(markers + " "):
        if char in "^_" and start is None:
            start = index
        elif char not in "^_" and start is not None:
            spans.append([start, index])
            start = None
    return spans


def lcd_fields(display: str):
    """Parse independently displayed fields, including compact paired LCD rows.

    OS screens can look like ``DETUNE RATE=26 AMT=9`` or
    ``BS1 TIME L=350 R=700``.  A conventional non-overlapping regex treats
    the first value as ``26 AMT`` / ``350 R`` and loses the second field.
    Split at every equals sign and derive the abbreviated secondary label
    from the text immediately before it, retaining value character spans.
    """
    equals = [i for i, char in enumerate(display) if char == "="]
    if not equals:
        return []
    first_label = display[:equals[0]].strip()
    rows = []
    first_value_end = equals[1] if len(equals) > 1 else len(display)
    first_value_text = display[equals[0] + 1:first_value_end]
    parent_label = first_label
    # For later '=' signs, their labels are short suffixes after the preceding
    # value, so the value is the numeric/text portion before that suffix.
    starts = [equals[0] + 1]
    labels = [first_label]
    values = []
    for idx in range(1, len(equals)):
        segment = display[equals[idx - 1] + 1:equals[idx]]
        suffix = re.search(r"\s+([A-Z][A-Z0-9]*)\s*$", segment)
        if suffix:
            secondary = suffix.group(1)
            value = segment[:suffix.start()].rstrip()
        else:
            secondary = ""
            value = segment.rstrip()
        if secondary == "AMT" and "DETUNE RATE" in parent_label:
            label = parent_label.replace("DETUNE RATE", "DETUNE AMT")
        elif secondary == "OUT" and "DIST GAIN IN" in parent_label:
            label = parent_label.replace("DIST GAIN IN", "DIST GAIN OUT")
        elif secondary == "R" and parent_label.endswith("TIME L"):
            label = parent_label[:-1] + "R"
        else:
            label = (parent_label + " " + secondary).strip()
        labels.append(label)
        values.append(value)
        starts.append(equals[idx] + 1)
    values.append(display[equals[-1] + 1:].rstrip() if len(equals) > 1 else first_value_text.rstrip())
    for i, label in enumerate(labels):
        value_start = starts[i]
        value_end = equals[i + 1] if i + 1 < len(equals) else len(display.rstrip())
        # A later value begins after its own '=', and ends at the next '='.
        # Earlier values have their abbreviation removed from the end.
        if i + 1 < len(labels):
            end = equals[i + 1]
            segment = display[value_start:end]
            match = re.search(r"\s+[A-Z][A-Z0-9]*\s*$", segment)
            value_end = value_start + (match.start() if match else len(segment.rstrip()))
        rows.append({"label": label, "displayed_value": values[i].strip(),
                     "value_span": [value_start, value_end]})
    return rows


def selected_fields(display: str, underline: str, cursor: str):
    selected = []
    fields = lcd_fields(display)
    for marker_name, marks in (("underline", underline), ("cursor", cursor)):
        spans = marked_spans(marks)
        for start, end in spans:
            field = next((f for f in fields if start < f["value_span"][1] and end > f["value_span"][0]), None)
            selected.append({"marker": marker_name, "cursor_span": [start, end],
                             "selected_text": display[start:end].strip(),
                             "field_label": field["label"] if field else None,
                             "field_label_status": "derived-from-lcd-equals-and-value-span" if field else "unresolved-secondary-field"})
    return selected


def parse_inventory_log(text: str, expected_slot: int):
    pages, variation_done, host_writes = [], [], []
    selected = any(re.search(rf"ESP_ROM_SELECT id={expected_slot:02d} ", line) for line in text.splitlines())
    for line in text.splitlines():
        write = GPR_WRITE.search(line)
        if write:
            paired = write.group(7) is not None
            host_writes.append({"event": int(write.group(1)), "cycles": int(write.group(2)),
                                "frame": int(write.group(3)), "pc": "0x" + write.group(4),
                                "write_kind": "instruction_and_gpr" if paired else "gpr",
                                "gpr": "0x" + (write.group(7) if paired else write.group(5)),
                                "value24": "0x" + (write.group(9) if paired else write.group(6)),
                                **({"instruction_word": "0x" + write.group(8)} if paired else {})})
        event = event_fields(line)
        if not event:
            continue
        if event["event"] == "PAGE":
            event["variation"] = int(event["variation"])
            event["ordinal"] = int(event["ordinal"])
            event["frame"] = int(event.get("frame", 0))
            event["cursor_position"] = {"underline_spans": marked_spans(event.get("underline", "")),
                                        "edit_cursor_spans": marked_spans(event.get("cursor", ""))}
            event["displayed_fields"] = lcd_fields(event.get("display", ""))
            event["selected_fields"] = selected_fields(event.get("display", ""),
                                                        event.get("underline", ""), event.get("cursor", ""))
            pages.append(event)
        elif event["event"] == "VARIATION_DONE":
            variation_done.append({"variation": int(event["variation"]),
                                   "page_transitions": int(event["page_transitions"])})
    if not selected:
        selected = any(f"FX=ROM-{expected_slot:02d}" in line and "PANEL_TAP_BEGIN id=edit" in line
                       for line in text.splitlines())
    completed = any(e and e["event"] == "SCAN_DONE" for e in (event_fields(x) for x in text.splitlines()))
    failure = next((event_fields(x) for x in text.splitlines()
                    if (event := event_fields(x)) and event["event"] in
                    {"SCAN_NO_CHANGE", "SCAN_PAGE_LIMIT", "VARIATION_FAILED"}), None)
    previous_cycle = None
    for page in pages:
        cycle = int(page.get("cycles", 0))
        start = -1 if previous_cycle is None else previous_cycle
        window = [e for e in host_writes if start < e["cycles"] <= cycle]
        page["dsp_register_window"] = {"ordered_host_write_count": len(window),
                                       "registers_written": sorted({e["gpr"] for e in window}),
                                       "write_kinds": sorted({e["write_kind"] for e in window}),
                                       "paired_instruction_gpr_write_count": sum(e["write_kind"] == "instruction_and_gpr" for e in window),
                                       "ordered_writes": window}
        previous_cycle = cycle
    return {"slot": expected_slot, "selection_verified": selected, "scan_completed": completed,
            "variation_count": len(variation_done), "variation_summaries": variation_done,
            "pages": pages, "host_gpr_write_count": len(host_writes), "failure": failure}


def build_command(args, entry, slot):
    raw = int(entry["select_raw"])
    if raw < 8 or raw > 1023:
        raise ValueError(f"slot {slot}: selector raw value outside 8..1023")
    command = [str(args.cli.resolve()), "--roms", str(args.roms.resolve()),
               "--disk", str(args.disk.resolve()), "--wav", "/dev/null",
               "--panel-log", "--log-rom-select"]
    command += ["--panel-tap-on-display", "0,25,7,NO INST OR BANK FILES,fx_select"]
    scan_end = 16.0 + 0.15 * (raw - 8)
    for i, value in enumerate(range(8, raw + 1)):
        command += ["--analog-at", f"{16.0 + 0.15 * i:.2f}:5:{value}"]
    settled = scan_end + 0.5
    command += ["--seconds", f"{settled + args.timeout + 1:.2f}"]
    command += ["--panel-tap-on-display", f"{settled:.2f},45,5,FX=ROM-{slot:02d},edit"]
    command += ["--panel-tap-on-display", f"{settled:.2f},45,9,FREE,effects"]
    command += ["--panel-scan-effects", f"{settled:.2f},{args.timeout:.2f},{args.max_pages},4,VAR=,editor_scan"]
    return command


def load_catalog(path):
    data = json.loads(path.read_text())
    return {row["slot"]: row for row in data["effects"]}


def norm_label(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def build_summary(progress, catalog):
    report = {"schema": "trollfx-asr10-factory-effect-editor-inventory-v04",
              "evidence_source": "OS 3.53 emulator live 22-character LCD, underline/edit-cursor attributes, and host GPR event windows",
              "status_legend": {"DOCUMENTED": "manual entry only", "OS_OBSERVED": "LCD label/value observed in a completed variation sweep",
                                "REGISTER_VERIFIED": "requires a separate controlled reversible value edit", "AUDIO_VERIFIED": "requires native DSP audio comparison",
                                "RUNTIME_READY": "only allowlisted verified points are accepted; no interpolation"},
              "slot_2_status": "deferred per user instruction; existing evidence retained, no new V4 probes",
              "entries": []}
    for slot in range(1, 51):
        manual = catalog[slot]
        if slot == 2:
            report["entries"].append({"slot": 2, "factory_name": manual["factory_name"], "status": "deferred",
                                      "documented_parameter_count": len(manual["parameters"]), "os_observations": []})
            continue
        row = progress["completed_slots"].get(str(slot))
        if not row:
            report["entries"].append({"slot": slot, "factory_name": manual["factory_name"], "status": "not-run",
                                      "documented_parameter_count": len(manual["parameters"]), "os_observations": []})
            continue
        pages = row["pages"]
        labels = {}
        for page in pages:
            for field in page.get("displayed_fields", []):
                label = field["label"]
                labels.setdefault(norm_label(label), {"label": label, "observations": []})
                labels[norm_label(label)]["observations"].append({
                    "variation": page["variation"], "ordinal": page["ordinal"],
                    "displayed_value": field["displayed_value"], "lcd": page["display"].rstrip(),
                    "cursor_position": page["cursor_position"], "selected_fields": page["selected_fields"]})
        manual_rows = []
        matched_keys = set()
        for parameter in manual["parameters"]:
            name = parameter["display_name"]
            normalized = norm_label(name)
            observed_keys = [key for key in labels if key == normalized or (normalized and normalized in key)]
            # The paper catalog groups controls that OS 3.53 presents as
            # independently selectable values. Keep those expansions explicit.
            if name == "BUS1 (and 2) DELAY MIX":
                observed_keys = [k for k in labels if k in {"BUS1DELAYMIX", "BUS2DELAYMIX"}]
            elif name == "BUS1 (and 2) FEEDBACK":
                observed_keys = [k for k in labels if k in {"BUS1FEEDBACK", "BUS2FEEDBACK"}]
            elif name == "DELAY TIME":
                observed_keys = [k for k in labels if re.fullmatch(r"BS[12]TIME[LR]", k)]
            elif name == "DIST GAIN IN/OUT In and Out":
                observed_keys = [k for k in labels if k in {"DISTGAININ", "DISTGAINOUT"}]
            if observed_keys:
                matched_keys.update(observed_keys)
            exact = normalized in observed_keys
            manual_rows.append({"id": parameter["id"], "display_name": name,
                                "documented_range": parameter.get("documented_range"),
                                "units": parameter.get("units"),
                                "status": ("OS_OBSERVED_LABEL_MATCH" if exact else
                                           "OS_OBSERVED_LABEL_ALIAS_OR_EXPANSION" if observed_keys else
                                           "DOCUMENTED_NOT_LABEL_MATCHED_REVIEW"),
                                # Values are held once under os_observed_fields;
                                # avoid duplicating every variation/page record.
                                "observed_labels": [labels[k]["label"] for k in observed_keys]})
        # Keep all UI pages, but omit raw ordered GPR events from the public
        # inventory; they remain in the private progress/log package.
        public_pages = []
        for page in pages:
            clean = dict(page)
            window = dict(clean.pop("dsp_register_window", {}))
            window.pop("ordered_writes", None)
            window["ordered_writes_retained_in_private_log"] = True
            clean["dsp_register_window"] = window
            public_pages.append(clean)
        report["entries"].append({
            "slot": slot, "factory_name": manual["factory_name"], "status": row["status"],
            "variation_count": row["variation_count"], "documented_parameter_count": len(manual["parameters"]),
            "observed_field_label_count": len(labels), "lcd_stop_count": len(pages),
            "manual_comparison": manual_rows,
            "os_observed_fields": [dict(value, normalized_key=key) for key, value in labels.items()],
            "os_observed_not_directly_in_manual_catalog": [labels[k]["label"] for k in labels if k not in matched_keys],
            "pages": public_pages,
        })
    completed = [e for e in report["entries"] if e["status"] == "complete"]
    report["coverage"] = {
        "completed_effects": len(completed), "deferred_effects": 1,
        "completed_documented_parameter_entries": sum(e["documented_parameter_count"] for e in completed),
        "os_observed_parameter_fields": sum(e["observed_field_label_count"] for e in completed),
        "manual_entries_observed_exact_or_alias": sum(sum(p["status"] in {"OS_OBSERVED_LABEL_MATCH", "OS_OBSERVED_LABEL_ALIAS_OR_EXPANSION"} for p in e["manual_comparison"]) for e in completed),
        "manual_entries_unmatched_for_review": sum(sum(p["status"] == "DOCUMENTED_NOT_LABEL_MATCHED_REVIEW" for p in e["manual_comparison"]) for e in completed),
        "register_verified_v04": 0, "audio_verified_v04": 0, "runtime_ready_v04": 0,
        "note": "Inventory scans establish names, order, defaults/variation values and focus positions. They do not assign DSP mappings without separate controlled reversible probes."
    }
    return report


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--roms", required=True, type=Path)
    ap.add_argument("--disk", required=True, type=Path)
    ap.add_argument("--inventory", required=True, type=Path)
    ap.add_argument("--catalog", type=Path, default=ROOT / "docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json")
    ap.add_argument("--progress", required=True, type=Path, help="private resumable progress JSON outside Git")
    ap.add_argument("--logs", required=True, type=Path, help="private raw logs directory outside Git")
    ap.add_argument("--summary", required=True, type=Path, help="redacted machine-readable editor inventory")
    ap.add_argument("--slots", help="comma/range list; default is 1,3-50 (slot 2 remains deferred)")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--reparse-logs", action="store_true", help="refresh completed progress from existing private logs without booting the emulator")
    ap.add_argument("--timeout", type=float, default=90)
    ap.add_argument("--max-pages", type=int, default=64)
    args = ap.parse_args()
    if args.timeout <= 0 or not 1 <= args.max_pages <= 128:
        ap.error("timeout must be positive and max-pages must be 1..128")

    selector = json.loads(args.inventory.read_text())
    selectors = {int(row["id"]): row for row in selector["entries"]}
    catalog = load_catalog(args.catalog)
    slots = list(range(1, 51)) if not args.slots else []
    if args.slots:
        for token in args.slots.split(","):
            if "-" in token:
                lo, hi = map(int, token.split("-", 1)); slots.extend(range(lo, hi + 1))
            else:
                slots.append(int(token))
    slots = sorted(set(slots))
    if any(slot < 1 or slot > 50 for slot in slots):
        ap.error("slot selection must be within 1..50")
    slots = [slot for slot in slots if slot != 2]

    progress = json.loads(args.progress.read_text()) if args.resume and args.progress.exists() else {
        "schema": "trollfx-asr10-editor-inventory-progress-v04", "completed_slots": {},
        "deferred_slots": {"2": "deferred per user instruction; retain prior evidence without new probes"}}
    args.logs.mkdir(parents=True, exist_ok=True)
    if args.reparse_logs:
        logs = {int(match.group(1)): path for path in args.logs.glob("slot-*-editor-inventory.log")
                if (match := re.match(r"slot-(\d{2})-editor-inventory\.log$", path.name))}
        for slot, log in sorted(logs.items()):
            refreshed = parse_inventory_log(log.read_text(errors="replace"), slot)
            refreshed.update({"factory_name": catalog[slot]["factory_name"],
                              "manual_parameter_count": len(catalog[slot]["parameters"]),
                              "status": "complete" if refreshed["selection_verified"] and refreshed["scan_completed"] and refreshed["variation_count"] == 4 else "failed",
                              "exit_code": 0, "private_log": str(log)})
            progress["completed_slots"][str(slot)] = refreshed
        write_json(args.progress, progress)
        write_json(args.summary, build_summary(progress, catalog))
        print(f"reparsed_completed_slots={len(progress['completed_slots'])} summary={args.summary}")
        return
    for slot in slots:
        key = str(slot)
        previous = progress["completed_slots"].get(key)
        if args.resume and previous and previous.get("status") == "complete":
            print(f"slot={slot:02d} skipped=already-complete")
            continue
        if slot not in selectors or slot not in catalog:
            raise SystemExit(f"slot {slot} is missing from selector inventory or catalog")
        command = build_command(args, selectors[slot], slot)
        log = args.logs / f"slot-{slot:02d}-editor-inventory.log"
        env = dict(os.environ, ESP_HOSTLOG="1", ASR_ROUTE="-1,-1,1,-1,0", ASR_TEST_SINE="440:0.25")
        with log.open("w") as stream:
            run = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=env, check=False)
        parsed = parse_inventory_log(log.read_text(errors="replace"), slot)
        parsed["factory_name"] = catalog[slot]["factory_name"]
        parsed["manual_parameter_count"] = len(catalog[slot]["parameters"])
        parsed["status"] = "complete" if run.returncode == 0 and parsed["selection_verified"] and parsed["scan_completed"] and parsed["variation_count"] == 4 else "failed"
        parsed["exit_code"] = run.returncode
        parsed["private_log"] = str(log)
        progress["completed_slots"][key] = parsed
        write_json(args.progress, progress)
        print(f"slot={slot:02d} name={parsed['factory_name']} pages={len(parsed['pages'])} variations={parsed['variation_count']} status={parsed['status']}")
        if parsed["status"] != "complete":
            continue

    write_json(args.summary, build_summary(progress, catalog))


if __name__ == "__main__":
    main()
