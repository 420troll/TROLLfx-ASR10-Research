#!/usr/bin/env python3
"""Generate an all-slot, explicitly unrun Akai Force QA matrix from effects.json."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ["slot", "effect", "families", "package_available", "plugin_ready", "wet_vs_bypass",
          "left_only", "right_only", "stereo_image", "sustained_2min", "switch_3x",
          "host_save_restore", "verified_parameter_response", "mpc_cpu_peak_pct",
          "system_idle_pct", "audio_glitches", "evidence_ref", "physical_status"]

def families(name: str) -> list[str]:
    n = name.upper()
    tags = []
    if any(x in n for x in ("REVERB", "REVRB", "REVB", "ROOM", "HALL", "PLATE")): tags.append("Reverb")
    if any(x in n for x in ("DDL", "DELAY")): tags.append("Delay")
    if any(x in n for x in ("CHOR", "PHASER", "FLANGER", "FLNGR", "ROT.", "VIBR", "TREM")): tags.append("Modulation")
    if "PITCH" in n: tags.append("Pitch")
    if any(x in n for x in ("CMP", "COMPRESS", "EXPAND", "DE-ESS", "DUCKER")): tags.append("Dynamics")
    if any(x in n for x in ("DIST", "WAH", "GUITAR AMP", "SPKR CABINET")): tags.append("Drive")
    if any(x in n for x in ("FILTER", "VCF", "RUMBLE")): tags.append("Filter")
    if "EQ" in n: tags.append("EQ")
    if not tags: tags.append("Other")
    return tags

def generate(catalog: Path, output: Path) -> int:
    effects = json.loads(catalog.read_text())
    if len(effects) != 50 or [int(x["slot"]) for x in effects] != list(range(1, 51)):
        raise ValueError("effect catalog must contain the ordered 1..50 factory slots")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for e in effects:
            writer.writerow({"slot": e["slot"], "effect": e["name"], "families": ";".join(families(e["name"])),
                **{f: "NOT_RUN" for f in FIELDS[3:]}})
    return len(effects)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", type=Path, default=ROOT / "force_plugin/effects.json")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    print(f"generated {generate(args.catalog, args.output)} explicit NOT_RUN rows: {args.output}")

if __name__ == "__main__":
    main()
