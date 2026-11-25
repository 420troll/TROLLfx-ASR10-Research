#!/usr/bin/env python3
"""Build a manual-only catalog for the twelve OS2 44 kHz appendix effects."""
import json
from pathlib import Path

EFFECTS = [
    ("44LUSH PLATE", ["DECAY TIME", "DEPTH", "PREDELAY TIME", "DEFINITION", "HF DAMPING", "DIFFUSION (1)", "DIFFUSION (2)", "BW", "ER TIME (L)", "ER TIME (R)", "DETUNE RATE", "ER LEVEL (L)", "ER LEVEL (R)"], ["ER TIME (L)", "ER TIME (R)", "ER LEVEL (L)", "ER LEVEL (R)"], "1 LUSH REVERB; 2 STANDARD REVERB; 3 MEDIUM REVERB; 4 LONG REVERB"),
    ("44LUSH PLAT2", ["DECAY TIME", "DEPTH", "PREDELAY TIME", "DEFINITION", "HF DAMPING", "DIFFUSION (1)", "DIFFUSION (2)", "BW", "DETUNE RATE"], [], "1 LUSH REVERB; 2 STANDARD REVERB; 3 MEDIUM REVERB; 4 LONG REVERB"),
    ("44PERC PLATE", ["DECAY TIME", "DEPTH", "PREDELAY TIME", "DEFINITION", "HF DAMPING", "DIFFUSION (1)", "DIFFUSION (2)", "BW", "ER TIME (L)", "ER TIME (R)", "DETUNE RATE", "ER LEVEL (L)", "ER LEVEL (R)"], [], "1 AMBIENT REVERB; 2 SLAP REVERB; 3 SHORT REVERB; 4 PERC REVERB"),
    ("44EQ+DDL", ["EQ IN", "MID", "EQ BW", "OUT", "ECHO WET", "GAIN", "BASS", "TREB", "ECHOTIME (L)", "ECHOTIME (R)", "ECHO REGEN (L)", "ECHO REGEN (R)", "CROSS REGN (L)", "CROSS REGN (R)", "DRY"], [], "1 LEFT RIGHT CENTR; 2 SLAP ECHOES; 3 WHEEL ECHO; 4 RHYTHMIC ECHOES"),
    ("44DDL+CH+REV", ["REVERB MIX", "DECAY TIME", "ECHO SEND", "PREDELAY TIME", "REGEN", "HF DAMPING", "ECHOTIME (L)", "ECHOTIME (R)", "BW", "CH RATE", "DEFINITION", "DIFFUSION (1)", "DIFFUSION (2)", "CH DRY LEV", "CH WET LEV (1)", "CH WET LEV (2)", "CH WET LEV (3)", "CH WET PAN (1)", "CH WET PAN (2)", "CH WET PAN (3)", "CH LFORATE (1)", "CH LFORATE (2)", "CH LFORATE (3)", "CH WIDTH (1)", "CH WIDTH (2)", "CH WIDTH (3)", "CH DELAY (1)", "CH DELAY (2)", "CH DELAY (3)", "EXPERT PARAMS", "FDBK T (1-4)", "TIME L (1-4)", "TIME R (1-4)", "GAIN L (1-4)", "GAIN R (1-4)"], [], "1 SWIRLING CHORUS; 2 DDL+SLOW CHORUS; 3 FLANGED CHORUS; 4 WARM CHORUS"),
    ("44DDL+CHORUS", ["ECHO LEV", "CH RATE", "REGEN (Chorus)", "REGEN (Delay)", "ECHOTIME (L)", "ECHOTIME (R)", "CH WET", "CH LFO SPREAD", "CH WIDTH", "DRY", "DELAY"], [], "1 PING PONG CHORUS; 2 FAT CHORUS; 3 ORGAN VIBRATO; 4 CLOCKWORK PIANO"),
    ("44DLYLFO+REV", ["REVERB MIX", "BW", "DL WET", "DEFINITION", "DRY", "DIFFUSION (1)", "DIFFUSION (2)", "DL RATE (L)", "DL RATE (R)", "DL WIDTH (L)", "DL WIDTH (R)", "DL DELAY (L)", "DL DELAY (R)", "DECAY TIME", "PREDELAY TIME", "HF DAMPING", "EXPERT PARAMS", "FDBK T (1-4)", "TIME L (1-4)", "TIME R (1-4)", "GAIN L (1-4)", "GAIN R (1-4)"], [], "1 PING PONG CHORUS; 2 SIDE TO SIDE; 3 DETUNER; 4 WHEEL WOW"),
    ("44EQ+DDL+CHO", ["EQ IN", "OUT", "EQ FREQ", "GAIN", "EQ BW", "ECHO LEV", "REGEN", "CH DRY LEV", "PAN", "CH WET LEV (1)", "CH WET LEV (2)", "CH WET LEV (3)", "CH WET PAN (1)", "CH WET PAN (2)", "CH WET PAN (3)", "CH LFORATE (1)", "CH LFORATE (2)", "CH LFORATE (3)", "CH WIDTH (1)", "CH WIDTH (2)", "CH WIDTH (3)", "DELAY (1)", "DELAY (2)", "DELAY (3)", "CH RATE", "ECHOTIME (L)", "ECHOTIME (R)"], [], "1 SWIRLING CHORUS; 2 DDL+SLOW CHORUS; 3 FLANGED CHORUS; 4 WARM CHORUS"),
    ("44PARAM EQ", ["BASS FC", "MID Q", "GAIN (BASS FC)", "TREBLE FC", "MID FC", "GAIN (MID FC)", "GAIN (TREBLE FC)", "INPUT TRIM"], [], "1 LA CURVE; 2 HYPED VOCALS; 3 BASS BOOST; 4 ASR SWEETENER"),
    ("44EQ+REVERB", ["REVERB MIX", "DEFINITION", "EQ IN", "DIFFUSION (1)", "DIFFUSION (2)", "OUT", "EQ FREQ", "GAIN", "EQ BW", "DECAY TIME", "PREDELAY TIME", "HF DAMPING", "BW", "EXPERT PARAMS", "FDBK T (1-4)", "TIME L (1-4)", "TIME R (1-4)", "GAIN L (1-4)", "GAIN R (1-4)"], [], "1 LUSH REVERB; 2 STANDARD REVERB; 3 MEDIUM REVERB; 4 LONG REVERB"),
    ("44ROTO+REVRB", ["REVERB MIX", "PREDELAY TIME", "SPKR WET", "HF DAMPING", "DRY", "BW", "SPEED", "DEFINITION", "INERTIA", "DIFFUSION (1)", "DIFFUSION (2)", "SPEED MIN", "MAX", "AM MIN", "AM MAX", "FM MIN", "FM MAX", "DECAY TIME", "EXPERT PARAMS", "FDBK T (1-4)", "TIME L (1-4)", "TIME R (1-4)", "GAIN L (1-4)", "GAIN R (1-4)"], [], "1 AMBIENT REVERB; 2 SLAP REVERB; 3 SHORT REVERB; 4 PERC REVERB"),
    ("44EQ+ROT+DDL", ["EQ IN", "MAX", "OUT", "AM MIN", "EQ FREQ", "AM MAX", "GAIN", "FM MIN", "EQ BW", "FM MAX", "SPKR WET", "ECHO WET", "DRY (speaker)", "DRY (delay)", "SPEED", "ECHOTIME (L)", "ECHOTIME (R)", "INERTIA", "ECHO REGEN (L)", "ECHO REGEN (R)", "SPEED MIN", "CROSS REGN (L)", "CROSS REGN (R)"], [], "1 PATCH SELECT; 2 MOD WHEEL; 3 TREMOLO PATCH; 4 VIBRATO PATCH"),
]

RANGES = {
    "AM MIN": "0 to 127", "AM MAX": "0 to 127", "BASS FC": "0 to 1000 Hz",
    "BW": "1 to 99", "CH DELAY": "0 to 50 ms", "CH DRY LEV": "-99 to +99",
    "CH LFORATE": "0 to 130", "CH RATE": "0 to 127 (44DDL+CH+REV and 44EQ+DDL+CHO); 0 to 130 (44DDL+CHORUS)",
    "CH WET": "-99 to +99", "CH WET LEV": "-99 to +99", "CH WET PAN": "-99 to +99",
    "CH WIDTH": "0 to 127", "CROSS REGN": "-99 to +99", "DECAY TIME": "0.40 to 1.21 sec (44PERC PLATE); 0.40 to 140 sec (listed reverb algorithms)",
    "DEFINITION": "0 to 99", "DELAY": "0 to 50 (44EQ+DDL+CHO); 0 to 100 (44DDL+CHORUS)",
    "DEPTH": "0 to 99", "DETUNE RATE": "0 to 99", "DIFFUSION": "0 to 99",
    "DL DELAY": "0 to 400 msec", "DL RATE": "0 to 130", "DL WET": "-99 to +99",
    "DL WIDTH": "0 to 127", "DRY": "0 to 99 (44EQ+DDL); -99 to +99 (other listed algorithms)",
    "ECHOTIME": "0 to 1000 msec (44DDL+CHORUS); 0 to 700 msec (44EQ+ROT+DDL); 0 to 700 msec (44EQ+DDL); 0 to 500 msec (44DDL+CH+REV); 0 to 1400 msec (44EQ+DDL+CHO)",
    "ECHO LEV": "0 to 99", "ECHO REGEN": "-99 to +99", "ECHO SEND": "00 to 99",
    "ECHO WET": "0 to 99", "EQ BW": "0 to 20K", "EQ FREQ": "0 to 20000",
    "EQ IN": "-99 to +48 dB", "ER TIME": "0 to 127", "ER LEVEL": "-99 to +99",
    "FM MIN": "0 to 127", "FM MAX": "0 to 127", "GAIN": "-99 to +48 dB",
    "GAIN (BASS FC)": "-48 to +24 dB", "GAIN (MID FC)": "-48 to +24 dB",
    "GAIN (TREBLE FC)": "-48 to +24 dB", "GAIN BASS": "-99 to +48 dB",
    "BASS": "-99 to +48 dB", "TREB": "-99 to +48 dB",
    "HF DAMPING": "0 to 99", "INERTIA": "0 to 127", "INPUT TRIM": "-24 to +0 dB",
    "LFO SPREAD": "0 to 127", "MAX": "0 to 130", "MID": "0 to 20000",
    "MID BW": "0 to 20K", "MID FC": "0 to 9999 Hz", "MID Q": "1 to 18",
    "OUT": "-99 to +48 dB", "PAN": "-99 to +99",
    "PREDELAY TIME": "0 to 300 msec (plate reverbs); 0 to 150 msec (listed non-plate algorithms)",
    "REGEN": "-99 to +99", "REGEN (CHORUS)": "-99 to +99", "REGEN (DELAY)": "-99 to +99",
    "REVERB MIX": "0 to 99", "SPEED": "MIN or MAX", "SPEED MIN": "0 to 130",
    "SPKR WET": "-99 to +99", "TREB": "-99 to +48 dB", "TREBLE FC": "1 to 20 kHz",
    "FDBK T": "0 to 127 (each of four expert taps)", "TIME L": "0 to 127 (each of four expert taps)",
    "TIME R": "0 to 127 (each of four expert taps)", "GAIN L": "-99 to +99 (each of four expert taps)",
    "GAIN R": "-99 to +99 (each of four expert taps)",
}


def range_for(label, effect):
    upper = label.upper()
    if upper.startswith("CH DELAY") or upper.startswith("DELAY ("):
        return RANGES["CH DELAY"] if effect == "44DDL+CH+REV" else RANGES["DELAY"]
    if upper.startswith("CH LFORATE"):
        return RANGES["CH LFORATE"]
    if upper.startswith("DL RATE"):
        return RANGES["DL RATE"]
    if upper.startswith("CH WET LEV"):
        return RANGES["CH WET LEV"]
    if upper.startswith("CH WET PAN"):
        return RANGES["CH WET PAN"]
    if upper.startswith("CH WIDTH"):
        return RANGES["CH WIDTH"]
    if upper.startswith("DIFFUSION"):
        return RANGES["DIFFUSION"]
    if upper.startswith("ER TIME"):
        return RANGES["ER TIME"]
    if upper.startswith("ER LEVEL"):
        return RANGES["ER LEVEL"]
    if upper.startswith("DL DELAY"):
        return RANGES["DL DELAY"]
    if upper.startswith("DL WIDTH"):
        return RANGES["DL WIDTH"]
    if upper.startswith("ECHOTIME"):
        if effect == "44EQ+DDL":
            return "0 to 700 msec"
        if effect == "44DDL+CH+REV":
            return "0 to 500 msec"
        if effect == "44EQ+DDL+CHO":
            return "0 to 1400 msec"
        if effect == "44DDL+CHORUS":
            return "0 to 1000 msec"
        if effect == "44EQ+ROT+DDL":
            return "0 to 700 msec"
        return RANGES["ECHOTIME"]
    if upper.startswith("ECHO REGEN"):
        return RANGES["ECHO REGEN"]
    if upper.startswith("CROSS REGN"):
        return RANGES["CROSS REGN"]
    if upper.startswith("FDBK T"):
        return RANGES["FDBK T"]
    if upper.startswith("TIME L"):
        return RANGES["TIME L"]
    if upper.startswith("TIME R"):
        return RANGES["TIME R"]
    if upper.startswith("GAIN L"):
        return RANGES["GAIN L"]
    if upper.startswith("GAIN R"):
        return RANGES["GAIN R"]
    if upper in {"DRY (SPEAKER)", "DRY (DELAY)"}:
        return RANGES["DRY"]
    if upper == "REGEN (CHORUS)":
        return RANGES["REGEN (CHORUS)"]
    if upper == "REGEN (DELAY)":
        return RANGES["REGEN (DELAY)"]
    if upper == "CH LFO SPREAD":
        return RANGES["LFO SPREAD"]
    return RANGES.get(upper)


def build():
    out = []
    page_by_effect = {"44LUSH PLATE": 368, "44LUSH PLAT2": 368, "44PERC PLATE": 368,
                      "44EQ+DDL": 369, "44DDL+CH+REV": 370, "44DDL+CHORUS": 371,
                      "44DLYLFO+REV": 372, "44EQ+DDL+CHO": 373, "44PARAM EQ": 373,
                      "44EQ+REVERB": 374, "44ROTO+REVRB": 375, "44EQ+ROT+DDL": 376}
    for effect, labels, unavailable, variations in EFFECTS:
        params = []
        for i, label in enumerate(labels):
            if label == "EXPERT PARAMS":
                continue
            base = label.split(" (")[0]
            if base.startswith("FDBK T"):
                base = "FDBK T"
            elif base.startswith("TIME L"):
                base = "TIME L"
            elif base.startswith("TIME R"):
                base = "TIME R"
            elif base.startswith("GAIN L"):
                base = "GAIN L"
            elif base.startswith("GAIN R"):
                base = "GAIN R"
            r = range_for(label, effect)
            params.append({"id": f"os2_{effect.lower().replace('+','_').replace(' ','_')}_{i+1:02d}",
                           "display_name": label, "manual_listing_order": i + 1,
                           "documented_range": r,
                           "group": "EXPERT PARAMS" if " (1-4)" in label else "MAIN",
                           "grouped_instances": 4 if " (1-4)" in label else 1,
                           "availability": "not available in 44LUSH PLAT2" if label in unavailable else "manual-listed",
                           "manual_page": page_by_effect[effect],
                           "os_observed": False, "register_mapping": "unverified", "audio_validation": "unverified"})
        out.append({"name": effect, "source": "ASR-10 Musician's Manual, Appendix, pp. 368-376",
                    "variations": variations, "parameters": params,
                    "expert_parameters": ("FDBK T", "TIME L", "TIME R", "GAIN L", "GAIN R") if "EXPERT PARAMS" in labels else (),
                    "ui_order_status": "manual layout listing only; live OS cursor order unverified",
                    "evidence_status": "MANUAL_DOCUMENTED_ONLY; not an OS2 editor/runtime validation"})
    return {"schema": "trollfx-asr10-os2-44khz-appendix-catalog-v1",
            "scope_note": "Twelve additional OS2 44 kHz effect algorithms; these are not additional numbered ROM effect slots.",
            "parameter_field_heading_count": sum(len(e["parameters"]) for e in out),
            "grouped_expert_instances": "FDBK T, TIME L, TIME R, GAIN L, and GAIN R each describe four tap controls when listed.",
            "variation_and_modulation": {
                "variation_count": 4,
                "variation_behavior": "Each variation is individually editable and acts as an effect edit buffer.",
                "modulator_count_per_variation": 2,
                "manual_applicability": "Section 5 says most effects support these controls; applicability for each OS2 algorithm requires live OS confirmation.",
                "sources": ["WHEEL", "PBEND", "PRESS", "PEDAL", "XCTRL", "KBD", "VEL", "KEYDN", "SUSTN", "FSW-L", "PATCH", "OFF"],
                "destination": "algorithm-specific parameter name; options vary",
                "modulation_ranges": {"MIN 1": "0 to 99 percent of destination range", "MAX 1": "0 to 99 percent of destination range", "MIN 2": "0 to 99 percent of destination range", "MAX 2": "0 to 99 percent of destination range"},
                "restriction": "A parameter assigned as a modulation destination cannot be edited directly until modulation is disabled; disabling modulation restores its saved value.",
                "source_pages": [99, 100]
            },
            "range_evidence": "ASR-10 Musician's Manual Appendix, alphabetized effect parameter reference, PDF pp. 377-382",
            "effects": out}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build(), indent=2) + "\n")
