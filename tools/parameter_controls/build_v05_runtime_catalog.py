#!/usr/bin/env python3
"""Build the public V5 point catalog from the hand-reviewed probe allowlist.

Raw emulator logs and evidence remain in the private results tree. This tool
checks each cited evidence file and copies only LCD/register facts to Git.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRIVATE = Path("/home/gamer/research/private-results/asr10-factory-dsp-parameter-mapping-v5/probes")

# evidence file, slot, factory name, stable parameter id, V4 field label,
# exact ordered GPR subset. Slot 2 is intentionally absent.
SPECS = [
    ("slot-01-var1-low-freq-decay-evidence.json",1,"HALL REVERB","low_freq_decay","LOW FREQ DECAY",[0x5b]),
    ("slot-01-var1-diffusion-evidence.json",1,"HALL REVERB","diffusion","DIFFUSION",[0x07,0x09,0x0a,0x0b,0x0c,0x14]),
    ("slot-01-var1-detune-rate-evidence.json",1,"HALL REVERB","detune_rate","DETUNE RATE",[0x6a]),
    ("slot-01-var1-detune-amt-evidence.json",1,"HALL REVERB","detune_amount","DETUNE AMT",[0x68]),
    ("slot-01-var1-pre-delay-time-evidence.json",1,"HALL REVERB","pre_delay_time","PRE-DELAY TIME",[0x01,0x08]),
    ("slot-03-var1-low-freq-decay-evidence.json",3,"ROOM REVERB","low_freq_decay","LOW FREQ DECAY",[0x5b]),
    ("slot-03-var1-hi-freq-bandwidth-evidence.json",3,"ROOM REVERB","hi_freq_bandwidth","HI FREQ BANDWIDTH",[0x02,0x00]),
    ("slot-03-var1-detune-rate-evidence.json",3,"ROOM REVERB","detune_rate","DETUNE RATE",[0x6a]),
    ("slot-03-var1-detune-amt-evidence.json",3,"ROOM REVERB","detune_amount","DETUNE AMT",[0x68]),
    ("slot-03-var1-pre-delay-time-evidence.json",3,"ROOM REVERB","pre_delay_time","PRE-DELAY TIME",[0x01,0x08]),
    ("slot-04-var1-bs1-time-r-evidence.json",4,"DUAL DELAYS","dual_bs1_time_r","BS1 TIME R",[0x0c]),
    ("slot-04-var1-bus2-feedback-evidence.json",4,"DUAL DELAYS","dual_bus2_feedback","BUS2 FEEDBACK",[0x07]),
    ("slot-04-var1-bs2-time-l-evidence.json",4,"DUAL DELAYS","dual_bs2_time_l","BS2 TIME L",[0x0f]),
    ("slot-06-var1-reverb-decay-time-evidence.json",6,"CHORUS+REVRB","reverb_decay_time","REVERB DECAY TIME",[0x6e,0x6c,0x71,0x72,0x73]),
    ("slot-06-var1-diffusion-evidence.json",6,"CHORUS+REVRB","diffusion","DIFFUSION",[0x5a,0x5b,0x5c]),
    ("slot-06-var1-bus1-rev-after-chor-evidence.json",6,"CHORUS+REVRB","bus1_rev_after_chor","BUS1 REV AFTER CHOR",[0x7c]),
    ("slot-06-var1-chorus-feedback-evidence.json",6,"CHORUS+REVRB","chorus_feedback","CHORUS FEEDBACK",[0x86]),
    ("slot-06-var1-chorus-rate-amt-evidence.json",6,"CHORUS+REVRB","chorus_rate_amount","CHORUS RATE AMT",[0x8d]),
    ("slot-08-var1-flange-center-evidence.json",8,"FLANGER+REV","flange_center","FLANGE CENTER",[0x68,0x67,0x64,0x63]),
    ("slot-08-var1-flange-width-evidence.json",8,"FLANGER+REV","flange_width","FLANGE WIDTH",[0x8d,0x8e]),
    ("slot-08-var1-flange-depth-evidence.json",8,"FLANGER+REV","flange_depth","FLANGE DEPTH",[0x88]),
    ("slot-38-var1-lfo-rate-evidence.json",38,"8-VOICE CHOR","lfo_rate","LFO RATE",[0x90,0x91,0x92,0x93,0x94,0x95,0x96,0x97]),
    ("slot-38-var1-lfo-rate-width-evidence.json",38,"8-VOICE CHOR","lfo_width","LFO RATE WIDTH",[0x8d]),
    ("slot-38-var1-chorus-regen-evidence.json",38,"8-VOICE CHOR","chorus_regen","CHORUS REGEN",[0x8a]),
    ("slot-38-var1-l-regen-time-evidence.json",38,"8-VOICE CHOR","l_regen_time","L REGEN TIME",[0x45]),
    ("slot-38-var1-r-regen-time-evidence.json",38,"8-VOICE CHOR","r_regen_time","R REGEN TIME",[0x43]),
    ("slot-38-var1-delay-regen-evidence.json",38,"8-VOICE CHOR","delay_regen","DELAY REGEN",[0x89]),
    ("slot-39-var1-lfo-rate-evidence.json",39,"PITCH SHIFT","lfo_rate","LFO RATE",[0x90]),
    ("slot-39-var1-vc1-semi-evidence.json",39,"PITCH SHIFT","vc1_semitone","VC1 SEMI",[0x60]),
    ("slot-39-var1-vc1-semi-fine-evidence.json",39,"PITCH SHIFT","vc1_fine","VC1 FINE",[0x60]),
]

def parse_display(label, lcd):
    aliases = {"BS1 TIME R":"R", "BS2 TIME L":"L", "DETUNE AMT":"AMT", "CHORUS RATE AMT":"AMT",
               "LFO RATE WIDTH":"WIDTH", "VC1 SEMI":"SEMI", "VC1 FINE":"FINE"}
    key = aliases.get(label, label)
    if key == "SEMI":
        key = "SEMI"
    normalized = re.sub(r"\s*=\s*", "=", lcd)
    marker = key + "="
    pos = normalized.find(marker)
    if pos < 0:
        raise ValueError(f"LCD {lcd!r} does not contain {marker!r}")
    value = normalized[pos+len(marker):].strip().split()[0]
    if value.endswith("="):
        raise ValueError(f"could not parse {label} from {lcd!r}")
    if value.startswith("+"):
        return int(value)
    return int(value) if value.lstrip("-").isdigit() else value

def display_text(label, lcd):
    aliases = {"BS1 TIME R":"R", "BS2 TIME L":"L", "DETUNE AMT":"AMT", "CHORUS RATE AMT":"AMT",
               "LFO RATE WIDTH":"WIDTH", "VC1 SEMI":"SEMI", "VC1 FINE":"FINE"}
    key=aliases.get(label,label)
    normalized=re.sub(r"\s*=\s*", "=", lcd)
    marker=key+"="
    pos=normalized.find(marker)
    if pos < 0: raise ValueError(f"LCD {lcd!r} does not contain {marker!r}")
    return normalized[pos+len(marker):].strip().split()[0]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--private-evidence", type=Path, default=DEFAULT_PRIVATE)
    ap.add_argument("--output", type=Path, default=ROOT/"docs/ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05.json")
    args = ap.parse_args()
    inventory = json.loads((ROOT/"docs/ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json").read_text())
    catalog = json.loads((ROOT/"docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json").read_text())
    inv_by_slot = {x["slot"]: x for x in inventory["entries"]}
    cat_by_slot = {x["slot"]: x for x in catalog["effects"]}
    manual_aliases = {
        (4,"BS1 TIME R"):"DELAY TIME", (4,"BS2 TIME L"):"DELAY TIME",
        (4,"BUS2 FEEDBACK"):"BUS1 (and 2) FEEDBACK",
        (6,"CHORUS RATE AMT"):"CHORUS AMT",
        (38,"LFO RATE WIDTH"):"WIDTH",
        (39,"VC1 SEMI"):"VC 1 SEMI", (39,"VC1 FINE"):"VC 1 FINE",
    }
    controls=[]
    for filename,slot,name,pid,label,gprs in SPECS:
        ev=json.loads((args.private_evidence/filename).read_text())
        if not ev.get("selection_verified") or ev.get("slot") != slot or int(ev.get("variation",0)) != 1:
            raise SystemExit(f"bad selected identity/variation: {filename}")
        if len(ev.get("probe_trials",[])) != 2 or not all(t.get("restored_exactly") for t in ev["probe_trials"]):
            raise SystemExit(f"probe is not two-trial reversible evidence: {filename}")
        deltas={int(x["gpr"],16):x for x in ev.get("stable_edit_state_deltas_across_trials",[])}
        if set(deltas) != set(gprs) or any(x.get("trials") != 2 for x in deltas.values()):
            raise SystemExit(f"stable GPR set differs from reviewed allowlist: {filename} {set(deltas)}")
        order=[int(x["gpr"],16) for x in ev.get("stable_ordered_write_group_from_first_trial",[])]
        order=[g for g in order if g in gprs]
        if order != gprs:
            raise SystemExit(f"ordered writes differ from reviewed allowlist: {filename}: {order}")
        trials=ev["probe_trials"]
        before_lcd=trials[0]["before_lcd"]
        after_lcd=trials[0]["after_edit_lcd"]
        before=parse_display(label,before_lcd)
        after=parse_display(label,after_lcd)
        writes_before=[{"gpr":f"0x{g:02X}","value24":deltas[g]["before"]} for g in gprs]
        writes_after=[{"gpr":f"0x{g:02X}","value24":deltas[g]["after"]} for g in gprs]
        inv=inv_by_slot[slot]
        observed=next((f for f in inv["os_observed_fields"] if f["label"]==label),None)
        obs=next((x for x in observed["observations"] if x.get("variation")==1),None) if observed else None
        manual_label=manual_aliases.get((slot,label),label)
        doc=next((p for p in cat_by_slot[slot]["parameters"] if p.get("display_name")==manual_label),None)
        if doc is None and obs:
            doc=next((p for p in cat_by_slot[slot]["parameters"] if p.get("id")==obs.get("catalog_parameter_id")),None)
        controls.append({
            "slot":slot,"factory_name":name,"variation":1,"parameter_id":pid,
            "display_name":label,"editor_order":int(ev["field_selection"]["page"]),
            "documented_label":manual_label if doc else None,
            "documented_range":doc.get("documented_range") if doc else None,
            "units":doc.get("units") if doc else None,
            "range_status":"DOCUMENTED" if doc and doc.get("documented_range") else "NOT_FOUND_IN_V1_MANUAL_CATALOG",
            "observed_lcd_before":before_lcd,"observed_lcd_after":after_lcd,
            "verified_points":[
                {"value":before,"text":display_text(label,before_lcd),"ordered_writes":writes_before},
                {"value":after,"text":display_text(label,after_lcd),"ordered_writes":writes_after}],
            "probe_evidence_id":filename,
            "probe_trials":2,"display_restored_each_trial":True,
            "mapping_status":"REGISTER_VERIFIED_ADJACENT_POINTS",
            "audio_status":"PENDING_NATIVE_RUNTIME_COMPARISON",
            "runtime_ready":False
        })
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({"schema":"trollfx-asr10-factory-dsp-parameter-mappings-v05",
        "source_inventory":"ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json",
        "slot_02":"DEFERRED",
        "policy":"Only exact repeated adjacent points are included; documented ranges remain metadata and do not authorize interpolation.",
        "controls":controls,
        "unresolved_probes":[
            {"slot":1,"factory_name":"HALL REVERB","variation":1,"display_name":"HI FREQ BANDWIDTH","evidence":"slot-01-var1-hi-freq-bandwidth-evidence.json","lcd_before":"HI FREQ BANDWIDTH=86","lcd_after":"HI FREQ BANDWIDTH=87","status":"NOT_PROMOTED_UNSTABLE_REGISTER_STATE"},
            {"slot":3,"factory_name":"ROOM REVERB","variation":1,"display_name":"REVERB MIX BUS1","evidence":"slot-03-var1-reverb-mix-bus1-evidence.json","lcd_before":"REVERB MIX BUS1=39","lcd_after":"REVERB MIX BUS1=40","observed_reversible_writes":[{"gpr":"0x7C","before":"0x5A0000"},{"gpr":"0x7C","after":"0x5C0000"}],"status":"NOT_PROMOTED_FINAL_STATE_OVERWRITTEN"},
            {"slot":4,"factory_name":"DUAL DELAYS","variation":1,"display_name":"BUS1 FEEDBACK","evidence":"slot-04-var1-bus1-feedback-evidence.json","status":"NOT_PROMOTED_NO_STABLE_REGISTER_DELTA"},
            {"slot":6,"factory_name":"CHORUS+REVRB","variation":1,"display_name":"HI FREQ DAMPING","evidence":"slot-06-var1-hi-freq-damping-evidence.json","status":"NOT_PROMOTED_NO_STABLE_REGISTER_DELTA"},
            {"slot":6,"factory_name":"CHORUS+REVRB","variation":1,"display_name":"CHORUS MIX","evidence":"slot-06-var1-chorus-mix-evidence.json","lcd_before":"CHORUS MIX=99","lcd_after":"CHORUS MIX=98","status":"NOT_PROMOTED_NO_STABLE_REGISTER_DELTA"},
            {"slot":8,"factory_name":"FLANGER+REV","variation":1,"display_name":"FLANGE FEEDBACK","evidence":"slot-08-var1-flange-feedback-evidence.json","lcd_before":"FLANGE FEEDBACK=+58","lcd_after":"FLANGE FEEDBACK=+59","observed_reversible_writes":[{"gpr":"0x86","before":"0x4B0000"},{"gpr":"0x86","after":"0x4C0000"}],"status":"REGISTER_WRITES_OBSERVED_BUT_FINAL_STATE_NOT_STABLE"},
            {"slot":8,"factory_name":"FLANGER+REV","variation":3,"display_name":"FLANGE FEEDBACK","evidence":"slot-08-var3-flange-feedback-evidence.json","lcd_before":"FLANGE FEEDBACK=-78","lcd_after":"FLANGE FEEDBACK=-77","observed_reversible_writes":[{"gpr":"0x86","before":"0x9C0000"},{"gpr":"0x86","after":"0x9D0000"}],"no_edit_baseline":{"gpr":"0x86","write_count":41},"status":"NEGATIVE_POINTS_OBSERVED_BUT_REGISTER_IS_MODULATED_AND_NO_STATIC_MAPPING_PROMOTED"}
        ]},indent=2,ensure_ascii=False)+"\n")
    print(f"runtime_candidate_controls={len(controls)} output={args.output}")

if __name__=="__main__": main()
