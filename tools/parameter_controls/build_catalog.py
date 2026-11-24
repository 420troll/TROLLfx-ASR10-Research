#!/usr/bin/env python3
"""Build the public, evidence-tiered factory parameter catalog from manual text.

The ASR-10 manual is supplied by the operator and is not copied into this repo.
Parameter names/ranges are transcribed metadata; live register mappings are
kept in the separate, evidence-bounded V2 mapping table.
"""
import argparse
import json
import re
from pathlib import Path
from verified_mapping_catalog import apply_verified_mappings

ROM = re.compile(r"^ROM-(\d{2})\s+(.+?)\s*$", re.M)
RANGE = re.compile(r"^\s*([A-Z0-9][A-Z0-9 /+()\-.,&']*?)\s+Ranges?:\s*(.*?)\s*$", re.I)


def slug(label, occurrence):
    base = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "control"
    return f"{base}_{occurrence}"


def infer_units(value):
    text = value.lower()
    if "khz" in text:
        return "kHz"
    if "hz" in text:
        return "Hz"
    if "ms" in text or "millisecond" in text:
        return "ms"
    if "sec" in text or "second" in text:
        return "seconds"
    if "db" in text:
        return "dB"
    if "semitone" in text:
        return "semitones"
    if "cent" in text:
        return "cents"
    if ":" in text:
        return "ratio"
    return None


def find_parameters(text):
    lines = text.splitlines()
    found, counts = [], {}
    for i, line in enumerate(lines):
        m = RANGE.match(line)
        if m:
            label, raw_range = m.group(1).strip(), m.group(2).strip()
        elif re.match(r"^\s*Ranges?:\s*", line, re.I):
            # The printed manual occasionally breaks the parameter label and
            # its range across lines. Accept only an all-caps preceding line.
            label = ""
            for prior in reversed(lines[max(0, i - 3):i]):
                candidate = prior.strip().rstrip("•")
                if not candidate:
                    continue
                if candidate == candidate.upper() and re.fullmatch(r"[A-Z0-9 /+()\-.,&']+", candidate):
                    label = candidate.strip()
                break
            if not label:
                continue
            raw_range = re.sub(r"^\s*Ranges?:\s*", "", line, flags=re.I).strip()
        else:
            continue
        # Some headings put the actual range on the next line (for example
        # the ROM-01/02/03 predelay variants).
        if not raw_range and i + 1 < len(lines):
            raw_range = lines[i + 1].strip()
        if not raw_range:
            continue
        if label.startswith("PRE-DELAY TIME ROOM and HALL REVERB"):
            label = "PRE-DELAY TIME"
        elif label.startswith("BUS1 (and 2) DELAY TIME"):
            label = "DELAY TIME"
        # These are continuation lines spelling out variant-dependent limits
        # for the immediately preceding control, not separate controls.
        if label in {"44KHZ REVERB", "44 KHZ Delays Bus1", "Bus2"} and found:
            found[-1].setdefault("documented_range_variants", []).append({
                "variant": label, "range": raw_range
            })
            continue
        occurrence = counts.get(label, 0) + 1
        counts[label] = occurrence
        units = infer_units(raw_range)
        if label in {"PRE-DELAY TIME", "DELAY TIME", "DLY TIME L", "DLY TIME R", "DLY 1 TIME", "ECHOTIME L", "ECHOTIME R", "ECHO TIME L", "ECHO TIME R"}:
            units = "ms"
        integer_range = bool(re.fullmatch(r"\s*[+-]?\d+\s+to\s+[+-]?\d+\s*", raw_range, re.I))
        found.append({
            "id": slug(label, occurrence),
            "display_name": label,
            "display_order": len(found),
            "documented_range": raw_range,
            "display_type": "enumerated" if re.search(r"\b(OFF|ON|IN-PHASE|OUT-OF-PHASE|LONG/|SHORT/|see below|infinity|INF)\b", raw_range, re.I) else "numeric_or_continuous",
            "display_format": "integer" if integer_range else "enumeration" if re.search(r"\b(OFF|ON|IN-PHASE|OUT-OF-PHASE|LONG/|SHORT/|see below|infinity|INF)\b", raw_range, re.I) else "numeric",
            "display_domain": "integer steps documented" if integer_range else "not established from manual text",
            "units": units,
            "default": None,
            "register_mapping": None,
            "evidence": "ASR-10 Musician's Manual; not independently verified in the OS emulator",
        })
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual-text", required=True, type=Path)
    ap.add_argument("--inventory", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--verified-mappings", type=Path,
                    default=Path(__file__).resolve().parents[2] / "docs/ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json")
    args = ap.parse_args()
    text = args.manual_text.read_text(errors="replace")
    start = text.find("ROM-01  HALL REVERB")
    end = text.find("Section 7", start)
    if start < 0 or end < 0:
        raise SystemExit("could not locate the effect parameter section in manual text")
    section = text[start:end]
    heads = list(ROM.finditer(section))
    groups = []
    i = 0
    while i < len(heads):
        j = i + 1
        # Adjacent ROM titles are one shared algorithm section (e.g. 1–3).
        while j < len(heads) and not section[heads[j-1].end():heads[j].start()].strip():
            j += 1
        slot_ids = [int(heads[k].group(1)) for k in range(i, j)]
        body_end = heads[j].start() if j < len(heads) else len(section)
        body = section[heads[j-1].end():body_end]
        params = find_parameters(body)
        inherited = sorted(set(re.findall(r"See the descriptions under ([A-Z0-9+& ,/-]+)", body)))
        for slot in slot_ids:
            groups.append((slot, params, inherited))
        i = j

    inventory = json.loads(args.inventory.read_text())
    names = {e["id"]: e["name"] for e in inventory["entries"]}
    by_slot = {slot: (params, inherited) for slot, params, inherited in groups}
    effects = []
    for slot in range(1, 51):
        raw_params, inherited = by_slot.get(slot, ([], []))
        params = [dict(p) for p in raw_params]
        for p in params:
            variants = p.get("documented_range_variants", [])
            if slot in (1, 3) and p["display_name"] == "PRE-DELAY TIME":
                p.pop("documented_range_variants", None)
            elif slot == 2 and p["display_name"] == "PRE-DELAY TIME":
                p["documented_range"] = "0 to 340"
                p.pop("documented_range_variants", None)
            elif slot == 4 and p["display_name"] == "DELAY TIME":
                p["documented_range"] = "0 to 2000 ms"
                p["documented_range_variants"] = [v for v in variants if v["variant"] == "Bus2"]
            elif slot == 5 and p["display_name"] == "DELAY TIME":
                p["documented_range"] = "0 to 1300 ms"
                p["documented_range_variants"] = [v for v in variants if v["variant"] == "Bus2"]
            if "documented_range_variants" in p and not p["documented_range_variants"]:
                del p["documented_range_variants"]
        # A variation selector is described as common to all effects. Its exact
        # value coding is intentionally not guessed here.
        params.insert(0, {
            "id": "effect_variation", "display_name": "VAR", "display_order": 0,
            "documented_range": "four Effect Variations (manual description)",
            "display_type": "discrete", "units": None, "default": None,
            "register_mapping": None,
            "evidence": "ASR-10 Musician's Manual; emulator values and register mapping unverified",
        })
        for n, p in enumerate(params):
            p["display_order"] = n
        effects.append({
            "slot": slot, "id": f"ROM-{slot:02d}", "factory_name": names[slot],
            "parameters": params,
            "parameter_count_documented": len(params),
            "runtime_parameter_status": "no verified GPR mapping in this catalog",
            "manual_cross_references": inherited,
            "modulation_controls": "See catalog-level shared controls; manual says the final eight controls apply to most effects.",
            "identity_note": "Factory slot/name from the existing private-asset-derived public inventory; no program payload included.",
        })

    catalog = {
        "schema": "trollfx-asr10-factory-parameter-catalog-v1",
        "catalog_evidence": {
            "documented_ranges": "ASR-10 Musician's Manual Section 6, Effect Parameters; ranges are documentation, not emulator measurements",
            "live_register_mappings": "Only explicit verified_runtime_parameters entries are live-trace verified",
            "factory_defaults": "No clean factory-reset defaults claimed",
            "display_order": "Order of parameter descriptions in the manual; UI cursor ordering still requires emulator confirmation",
            "curve_policy": "No undocumented interpolation or conversion curves are generated",
        },
        "shared_documented_controls": [
            {"display_order": "final eight controls where supported", "id": "mod_src_1", "name": "MOD SRC 1", "range": "WHEEL, PBEND, PRESS, PEDAL, XCTRL, KBD, VEL, KEYDN, SUSTN, FSW-L, PATCH, OFF", "kind": "discrete", "status": "documented; effect-specific availability not live-verified"},
            {"display_order": "final eight controls where supported", "id": "mod_src_2", "name": "MOD SRC 2", "range": "WHEEL, PBEND, PRESS, PEDAL, XCTRL, KBD, VEL, KEYDN, SUSTN, FSW-L, PATCH, OFF", "kind": "discrete", "status": "documented; effect-specific availability not live-verified"},
            {"display_order": "final eight controls where supported", "id": "dst_1", "name": "DST 1", "range": "algorithm-dependent parameter destinations", "kind": "discrete", "status": "documented; per-effect options not exhaustively established"},
            {"display_order": "final eight controls where supported", "id": "dst_2", "name": "DST 2", "range": "algorithm-dependent parameter destinations", "kind": "discrete", "status": "documented; per-effect options not exhaustively established"},
            *[{"display_order": "final eight controls where supported", "id": key.lower().replace(" ", "_"), "name": key, "range": "0 to 99 percent of selected destination parameter range", "kind": "numeric", "status": "documented; emulator mapping not live-verified"} for key in ("MIN 1", "MAX 1", "MIN 2", "MAX 2")],
        ],
        "shared_parameter_index": {
            name: [e["id"] for e in effects if any(x["display_name"] == name for x in e["parameters"])]
            for name in sorted({p["display_name"] for e in effects for p in e["parameters"]})
            if sum(any(x["display_name"] == name for x in e["parameters"]) for e in effects) > 1
        },
        "effects": effects,
    }
    apply_verified_mappings(catalog, args.verified_mappings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, indent=2) + "\n")


if __name__ == "__main__":
    main()
