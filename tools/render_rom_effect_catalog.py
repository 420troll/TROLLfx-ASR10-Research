#!/usr/bin/env python3
"""Render a redacted public Markdown catalog from private JSON inventory/status."""
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inventory", type=Path)
    p.add_argument("status", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    inventory = json.loads(a.inventory.read_text(encoding="utf-8"))
    status = json.loads(a.status.read_text(encoding="utf-8"))
    states = {i: "captured" for i in status.get("captured", [])}
    states.update({i: "failed" for i in status.get("failed", [])})
    states.update({i: "untested" for i in status.get("untested", [])})
    lines = ["# ASR-10 OS 3.53 ROM Effect Catalog (Redacted)", "",
             "Names and selection numbers below were read from the running OS 3.53 display. "
             "This catalog contains no firmware, program bytes, register values, raw traces, WAVs, or private hashes.", "",
             f"OS-observed entries: **{len(inventory.get('entries', []))}**. Capture status is local-run status and may vary by researcher.", "",
             "| OS ID | Display name | Capture status |", "|---:|---|---|"]
    for entry in inventory.get("entries", []):
        i = int(entry["id"])
        name = entry["name"].replace("|", "\\|")
        lines.append(f"| {i:02d} | {name} | {states.get(i, 'untested')} |")
    lines += ["", f"Observed ID sequence contiguous from 1: **{bool(inventory.get('contiguous_ids_from_1'))}**.",
              "", "The built-in `INST HALL REVERB` is captured separately as a known reference; it is not an entry in this ROM catalog.", ""]
    a.output.write_text("\n".join(lines), encoding="utf-8")
    print(a.output)


if __name__ == "__main__":
    main()
