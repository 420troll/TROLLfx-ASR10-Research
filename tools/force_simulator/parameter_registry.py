"""Factory parameter metadata for the flexible PC editor.

The manual catalog supplies presentation ranges; only points in the append-only
VST registry are writable. This separation prevents an inspector value from
being mistaken for a DSP mapping.
"""
from __future__ import annotations
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = Path(__file__).resolve().parent

def _key(value: str) -> str:
    return re.sub(r"_\d+$", "", value.strip().lower().replace(" ", "_"))

def _label_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())

def _range(text: str):
    if not text: return None
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:to|–|-)\s*\+?(-?\d+(?:\.\d+)?)", text, re.I)
    if not m: return None
    try: return [float(m.group(1)), float(m.group(2))]
    except ValueError: return None

def _numeric_domain(text: str, units=None, rich_domain=None):
    """Parse documented bounds while normalizing mixed time/frequency units."""
    rich_domain=rich_domain or {}
    if text:
        m=re.search(r"(-?\d+(?:\.\d+)?)\s*(µs|us|ms|s|Hz|kHz|KHz)?\s+to\s+(-?\d+(?:\.\d+)?)\s*(µs|us|ms|s|Hz|kHz|KHz)?",text,re.I)
        if m:
            a,ua,b,ub=m.groups();ua=ua or ub;ub=ub or ua
            vals=[float(a),float(b)]
            def canonical(u):
                if not u:return None
                u=u.casefold().replace('µ','u')
                return {'us':'s','ms':'s','s':'s','hz':'Hz','khz':'kHz'}.get(u,u)
            ra=ua.replace('µ','u').replace('μ','u').casefold() if ua else None; rb=ub.replace('µ','u').replace('μ','u').casefold() if ub else None
            if ra and rb and ra!=rb and {ra,rb}<={'us','ms','s'}:
                factors={'us':1e-6,'ms':1e-3,'s':1.0}; vals=[vals[0]*factors[ra],vals[1]*factors[rb]];units='s'
            elif ra and rb and ra!=rb and {ra,rb}<={'hz','khz'}:
                factors={'hz':1.0,'khz':1000.0}; vals=[vals[0]*factors[ra],vals[1]*factors[rb]];units='Hz'
            else:
                c=canonical(ua or ub)
                if c: units={'s':'s','Hz':'Hz','kHz':'kHz'}.get(c,units)
            return vals,units
    if rich_domain.get("minimum") is not None and rich_domain.get("maximum") is not None:
        return [float(rich_domain["minimum"]),float(rich_domain["maximum"])], units
    return _range(text),units

def _load_vst_controls():
    source = (ROOT / "include/trollfx/es5510_factory_editor_v04.hpp").read_text()
    out = {}
    pat = re.compile(r'\{\s*(\d+),\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*(\d+),\s*(kPointLabels\d+),\s*(kPointValues\d+),\s*(\d+)\s*\}')
    arrays = {}
    for name, vals in re.findall(r'inline constexpr int (kPointValues\d+)\[\] = \{([^}]+)\};', source):
        arrays[name] = [int(v.strip()) for v in vals.split(',')]
    labels = {}
    for name, vals in re.findall(r'inline constexpr const char\* (kPointLabels\d+)\[\] = \{([^}]+)\};', source):
        labels[name] = re.findall(r'"([^"]*)"', vals)
    ordinals = {}
    for match in pat.finditer(source):
        slot, ident, label, host_name, canonical_id, index, label_id, value_id, count = match.groups()
        slot, index, count = int(slot), int(index), int(count)
        ordinal = ordinals.get(slot, 0); ordinals[slot] = ordinal + 1
        out[(slot, _key(ident))] = {"label":label,"host_parameter_index": 46 + (ordinal % 8), "bank": ordinal // 8,
            "canonical_parameter_index": index, "canonical_identity": canonical_id,
            "point_values": arrays.get(value_id, [])[:count], "point_labels": labels.get(label_id, [])[:count]}
    return out

def _group_for(label: str, ident: str) -> str:
    text=(label+" "+ident).upper()
    if "MOD SRC" in text or text.startswith("DST ") or "MIN_" in text or "MAX_" in text: return "Modulation"
    if any(x in text for x in ("BUS", "MIX", "FEEDBACK", "SEND", "ROUT")): return "Bus mixing & routing"
    if any(x in text for x in ("REVERB", "DECAY", "DIFFUS", "DAMP", "REFL", "REFLECTION", "PRE-DELAY", "PREDELAY", "DETUNE")): return "Reverb"
    if any(x in text for x in ("DELAY", "DDL", "ECHO", "REGEN")): return "Delay"
    if any(x in text for x in ("FILTER", " FC", "FC ", "EQ", "TREBLE", "BASS", "GAIN", "Q ", "LPF", "HPF")): return "Filter / EQ"
    if any(x in text for x in ("COMP", "THRESH", "RATIO", "ATTACK", "RELEASE", "EXPAN", "GATE", "DUCK")): return "Dynamics"
    if any(x in text for x in ("CHOR", "FLANGE", "PHASE", "VIBR", "TREMOLO", "LFO", "RATE", "WIDTH", "DEPTH")): return "Modulation effect"
    if any(x in text for x in ("PAN", "SEMI", "FINE", "PITCH", "QUALITY", "VC ")): return "Pitch & voice"
    return "Main effect"

def load_registry():
    cat = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json").read_text())
    full = json.loads((SIM / "data/ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json").read_text())
    full_by_slot={int(e["slot"]):e for e in full.get("effects",[])}
    ui_schema=json.loads((SIM / "data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json").read_text())
    ui_by_slot={int(e["slot"]):e for e in ui_schema.get("effects",[])}
    qa_contract=json.loads((SIM / "data/ASR10_EDITOR_EVIDENCE_ADAPTER_V1.json").read_text())
    qa_by_slot={int(e["slot"]):e for e in qa_contract.get("effects",[])}
    inventory = json.loads((SIM / "data/ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json").read_text())
    mappings = json.loads((SIM / "data/ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05.json").read_text())
    vst = _load_vst_controls()
    vst_by_label={(slot,_label_key(route["label"])):route for (slot,_),route in vst.items()}
    v05 = {}
    for x in mappings.get("controls", []):
        v05[(int(x["slot"]), _key(x["parameter_id"]))] = x
    inv = {int(x["slot"]): x for x in inventory["entries"]}
    result = []
    for effect in cat["effects"]:
        controls = []
        full_effect=full_by_slot.get(int(effect["slot"]),{})
        full_params={_key(p["id"]):p for p in full_effect.get("parameters",[])}
        ui_effect=ui_by_slot.get(int(effect["slot"]),{})
        ui_params={_key(p["id"]):p.get("manual",{}) for p in ui_effect.get("parameters",[])}
        qa_effect=qa_by_slot.get(int(effect["slot"]),{})
        qa_params={p["id"]:p for p in qa_effect.get("parameters",[])}
        qa_additional=qa_effect.get("additional_recovered_controls",[])
        qa_additional_by_id={ident:x for x in qa_additional for ident in x.get("parameter_ids",[])}
        normalization_by_source={}
        for normalization in qa_effect.get("normalizations",[]):
            for source_id in normalization.get("source_descriptor_ids",[]):
                normalization_by_source[source_id]=normalization
        catalog_keys=set()
        for p in sorted(effect["parameters"], key=lambda x: x.get("display_order", 0)):
            ident = _key(p["id"])
            catalog_keys.add(ident)
            route = vst.get((effect["slot"], ident)) or vst_by_label.get((effect["slot"],_label_key(p["display_name"])))
            recovered = v05.get((effect["slot"], ident))
            source_range,parsed_units = _numeric_domain(p.get("documented_range", ""),p.get("units"))
            obs = []
            entry = inv.get(effect["slot"], {})
            for field in entry.get("os_observed_fields", []):
                if field.get("label", "").casefold() == p["display_name"].casefold():
                    seen=[]
                    for observation in field.get("observations", []):
                        value=observation.get("displayed_value", "").strip()
                        if value and value not in seen: seen.append(value)
                    obs=seen
                    break
            if not obs and route and p.get("display_type") in ("enumerated", "discrete"):
                obs=list(route["point_labels"])
            if not obs and recovered and p.get("display_type") in ("enumerated", "discrete"):
                obs=[point.get("text", str(point.get("value", ""))) for point in recovered.get("verified_points", [])]
            if route:
                status = "PARTIAL"
                if source_range and route["point_values"] and len(route["point_values"]) >= int(source_range[1]-source_range[0]+1): status = "VERIFIED"
            elif recovered and recovered.get("runtime_ready"):
                # Audio backend has evidence but the native GUI VST adapter is not
                # connected to that mapping yet; never route it through another ID.
                status = "PARTIAL"
            else: status = "UNMAPPED"
            rich=full_params.get(ident,{})
            ui_manual=ui_params.get(ident,{})
            rich_domain=rich.get("documented_numeric_domain") or ui_manual.get("documented_numeric_domain") or {}
            source_range,parsed_units=_numeric_domain(p.get("documented_range", ""),parsed_units,rich_domain)
            choices=rich.get("discrete_choices") or obs
            controls.append({"id": p["id"], "key": ident, "name": p["display_name"],
                "order": p.get("display_order", 0), "range_text": p.get("documented_range", ""),
                "range": source_range, "type": p.get("display_type", "numeric_or_continuous"),
                "format": p.get("display_format", ""), "domain": p.get("display_domain", ""),
                "range_variants": p.get("documented_range_variants", []),
                "group": _group_for(p["display_name"],p["id"]),
                "description": ui_manual.get("description") or rich.get("description", ""),
                "description_source":ui_manual.get("description_source","registry"),
                "manual_confidence": rich.get("ui_range_confidence", ui_manual.get("ui_range_confidence", "manual catalog")),
                "default_value": rich.get("default_value"),
                "observed_variation_values": rich.get("os_observed_values_across_factory_variations", []),
                "documented_choices": choices,
                "supported_values": rich.get("supported_values", []),
                "display_scale_curve": p.get("display_scale_curve", p.get("editor_scale_curve", [])),
                "group": p.get("group") or p.get("parameter_group") or _group_for(p["display_name"],p["id"]),
                "units": parsed_units, "evidence": p.get("evidence", ""),
                "observed_choices": choices, "status": status, "route": route,
                "v05_runtime_ready": bool(recovered and recovered.get("runtime_ready")),
                "v05_points": recovered.get("verified_points", []) if recovered else []})
        # The original Section 6 explicitly says DUAL/44KHZ DELAYS give BUS1 and
        # BUS2 separate mix/feedback/time values, with independent L/R time values.
        # Keep the collapsed catalog descriptor for identity/provenance, but replace
        # it in the editable UI with the manual's independently adjustable controls.
        if int(effect["slot"]) in (4,5):
            parent_ids={"bus1_and_2_delay_mix","bus1_and_2_feedback","delay_time"}
            high=1300 if int(effect["slot"])==5 else 2000
            for c in controls:
                if c["key"] in parent_ids: c["editor_visible"]=False
                if c["key"]=="delay_time_l":
                    # Existing VST identity is retained as BUS1 left delay time.
                    c.update({"name":"BUS1 DELAY TIME L","range_text":f"0 to {high} ms","range":[0,high],"type":"numeric_or_continuous","format":"integer","domain":"integer steps documented","group":"Delay","units":"ms","description":"BUS1 left-channel delay time; the manual states left and right channels are independently adjustable.","editor_visible":True})
            specs=[
                ("dual_bus1_delay_mix","BUS1 DELAY MIX",[0,99],"The dry/wet balance for the BUS1 delay path."),
                ("dual_bus2_delay_mix","BUS2 DELAY MIX",[0,99],"The dry/wet balance for the BUS2 delay path."),
                ("dual_bus1_feedback","BUS1 FEEDBACK",[0,99],"Feedback amount for BUS1; the manual describes this as the amount returned from the right delay output."),
                ("dual_bus2_feedback","BUS2 FEEDBACK",[0,99],"Feedback amount for BUS2."),
                ("dual_bus1_delay_time_r","BUS1 DELAY TIME R",[0,high],"BUS1 right-channel delay time in milliseconds; left and right are independently adjustable."),
                ("dual_bus2_delay_time_l","BUS2 DELAY TIME L",[0,150],"BUS2 left-channel delay time in milliseconds; left and right are independently adjustable."),
                ("dual_bus2_delay_time_r","BUS2 DELAY TIME R",[0,150],"BUS2 right-channel delay time in milliseconds; left and right are independently adjustable.")]
            for order,(ident,label,limits,description) in enumerate(specs,500):
                controls.append({"id":ident,"key":ident,"name":label,"order":order,"range_text":f"{limits[0]} to {limits[1]}"+(" ms" if "time" in ident else ""),"range":limits,"type":"numeric_or_continuous","format":"integer","domain":"integer steps documented","range_variants":[],"display_scale_curve":[],"group":"Delay" if "time" in ident else "Bus mixing & routing","units":"ms" if "time" in ident else None,"evidence":"ASR-10 Musician's Manual Section 6; independently adjustable BUS/L/R controls described in ROM-04/05.","description":description,"manual_confidence":"direct manual statement","default_value":None,"observed_variation_values":[],"documented_choices":[],"supported_values":[],"observed_choices":[],"status":"UNMAPPED","route":None,"v05_runtime_ready":False,"v05_points":[],"catalog_descriptor":False,"manual_subparameter":True,"editor_visible":True})
        # Manual parameter groups with explicit independently adjustable members.
        # Their legacy aggregate descriptor remains in metadata but is hidden from
        # editing; new PC draft IDs do not affect append-only VST parameter IDs.
        split_specs={
            9:[("dist_gain_in","DIST GAIN IN","0 to 99","Input gain into the amplifier simulation."),("dist_gain_out","DIST GAIN OUT","0 to 99","Output level of the amplifier distortion path.")],
            11:[("dist_gain_in","DIST GAIN IN","0 to 99","Input gain into the distortion stage."),("dist_gain_out","DIST GAIN OUT","0 to 99","Output level from the distortion stage."),("dist_lpf","DIST LPF","0 to 99","Low-pass filtering of high frequencies after distortion."),("dist_hpf","DIST HPF","0 to 99","High-pass filtering of low frequencies after distortion.")],
            12:[("dist_gain_in","DIST GAIN IN","0 to 99","Input gain into the distortion stage."),("dist_gain_out","DIST GAIN OUT","0 to 99","Output level from the distortion stage.")]
        }
        if int(effect["slot"]) in split_specs:
            parents={"dist_gain_in_out_in_and_out","dist_gain_in_and_out","dist_lpf_hpf"}
            for c in controls:
                if c["key"] in parents:c["editor_visible"]=False
            for order,(ident,label,rng,description) in enumerate(split_specs[int(effect["slot"])],600):
                controls.append({"id":f"manual_{ident}","key":f"manual_{ident}","name":label,"order":order,"range_text":rng,"range":[0,99],"type":"numeric_or_continuous","format":"integer","domain":"integer steps documented","range_variants":[],"display_scale_curve":[],"group":"Main effect","units":None,"evidence":"ASR-10 Musician's Manual Section 6; grouped name explicitly describes two independent controls.","description":description,"manual_confidence":"direct manual statement","default_value":None,"observed_variation_values":[],"documented_choices":[],"supported_values":[],"observed_choices":[],"status":"UNMAPPED","route":None,"v05_runtime_ready":False,"v05_points":[],"catalog_descriptor":False,"manual_subparameter":True,"editor_visible":True})
        repeated_specs={
            14:("positn_bal_1_to_3","POSITN BAL",3,[-99,99],"Controls the stereo position balance at one of three room/hall depth positions."),
            15:("positn_bal_1_to_3","POSITN BAL",3,[-99,99],"Controls the stereo position balance at one of three room/hall depth positions."),
            16:("positn_bal_1_to_3","POSITN BAL",3,[-99,99],"Controls the stereo position balance at one of three room/hall depth positions."),
            17:("er_lev_1_to_4","ER LEVEL",4,[-99,99],"Sets the level for one of the four early reflections."),
            18:("er_lev_1_to_4","ER LEVEL",4,[-99,99],"Sets the level for one of the four early reflections."),
            21:("er_lev_1_to_4","ER LEVEL",4,[-99,99],"Sets the level for one of the four early reflections."),
            22:("env_lev_1_to_9","ENV LEVEL",9,[0,99],"Sets the level of one envelope level in the nonlinear reverb."),
            23:("env_lev_1_to_9","ENV LEVEL",9,[0,99],"Sets the level of one envelope level in the nonlinear reverb."),
            24:("env_lev_1_to_9","ENV LEVEL",9,[0,99],"Sets the level of one envelope level in the nonlinear reverb.")}
        if int(effect["slot"]) in repeated_specs:
            parent,label,count,limits,description=repeated_specs[int(effect["slot"])]
            for c in controls:
                if c["key"]==parent:c["editor_visible"]=False
            for n in range(1,count+1):
                controls.append({"id":f"manual_{parent.rsplit('_1',1)[0]}_{n}","key":f"manual_{parent.rsplit('_1',1)[0]}_{n}","name":f"{label} {n}","order":650+n,"range_text":f"{limits[0]} to {limits[1]}","range":limits,"type":"numeric_or_continuous","format":"integer","domain":"integer steps documented","range_variants":[],"display_scale_curve":[],"group":"Reverb" if parent.startswith(("positn","er_lev")) else "Main effect","units":None,"evidence":"ASR-10 Musician's Manual Section 6; explicitly plural independent parameter group.","description":description,"manual_confidence":"direct manual statement","default_value":None,"observed_variation_values":[],"documented_choices":[],"supported_values":[],"observed_choices":[],"status":"UNMAPPED","route":None,"v05_runtime_ready":False,"v05_points":[],"catalog_descriptor":False,"manual_subparameter":True,"editor_visible":True})
            if int(effect["slot"]) in (22,23,24):
                for c in controls:
                    m=re.fullmatch(r"manual_env_lev_(\d+)",c.get("id",""))
                    if m and int(m.group(1))>5:
                        c.update({"editor_visible":False,"input_disabled":True,"identity_confidence":"manual-documented; original OS subfield not located"})
        # Reverb groups share one control whose manual range varies by algorithm.
        slot=int(effect["slot"])
        if 14<=slot<=16:
            decay_ranges={14:(0.2,100.0,"0.20 to 100.0 sec."),15:(0.2,150.0,"0.20 to 150.0 sec."),16:(0.7,250.0,"0.70 to 250.0 sec.")}
            decay=next((c for c in controls if c["key"]=="decay_time_small_room"),None)
            if decay:
                lo,hi,label=decay_ranges[slot];decay.update({"name":"DECAY TIME","range":[lo,hi],"range_text":label,"units":"sec"})
            for c in controls:
                if c["name"] in ("Large Room","Hall Reverb2"):c["editor_visible"]=False
        if slot in (17,18):
            ranges={17:(0.2,100.0,0,500),18:(0.4,140.0,0,430)};decay_lo,decay_hi,pre_lo,pre_hi=ranges[slot]
            decay=next((c for c in controls if c["key"]=="decay_time_small_plate"),None)
            pre=next((c for c in controls if c["key"]=="predelay_time_small_plate"),None)
            if decay:
                range_text="0.4 to 140.0 sec." if slot==18 else "0.2 to 100.0 sec."
                decay.update({"name":"DECAY TIME","range":[decay_lo,decay_hi],"range_text":range_text,"units":"sec"})
            if pre:pre.update({"name":"PREDELAY TIME","range":[pre_lo,pre_hi],"range_text":f"{pre_lo} to {pre_hi} ms","units":"ms"})
            for c in controls:
                if c["name"]=="Large Plate":c["editor_visible"]=False
        # Section 6 uses named cross-references for shared subassemblies. Expand
        # only the parameter rows named by each algorithm's text, never the whole
        # referenced effect and never its bus mix or VAR selector.
        shared={
            "hall_chorus":[("DECAY TIME","REVERB DECAY TIME"),("LOW FREQ DECAY","REVERB LOW FREQ DECAY"),("DIFFUSION","REVERB DIFFUSION"),("HI FREQ DAMPING","REVERB HI FREQ DAMPING"),("HI FREQ BANDWIDTH","REVERB HI FREQ BANDWIDTH"),("DETUNE RATE","REVERB DETUNE RATE"),("DETUNE AMT","REVERB DETUNE AMT")],
            "hall_short":[("DECAY TIME","REVERB DECAY TIME"),("DIFFUSION","REVERB DIFFUSION"),("HI FREQ DAMPING","REVERB HI FREQ DAMPING")],
            "hall_10":[("DECAY TIME","REVERB DECAY TIME"),("LOW FREQ DECAY","REVERB LOW FREQ DECAY"),("HI FREQ DAMPING","REVERB HI FREQ DAMPING"),("DETUNE RATE","REVERB DETUNE RATE"),("DETUNE AMT","REVERB DETUNE AMT")],
            "hall_12":[("DECAY TIME","REVERB DECAY TIME"),("LOW FREQ DECAY","REVERB LOW FREQ DECAY"),("HI FREQ DAMPING","REVERB HI FREQ DAMPING"),("HI FREQ BANDWIDTH","REVERB HI FREQ BANDWIDTH"),("DETUNE RATE","REVERB DETUNE RATE"),("DETUNE AMT","REVERB DETUNE AMT")],
            "hall_13":[("DECAY TIME","REVERB DECAY TIME"),("HI FREQ DAMPING","REVERB HI FREQ DAMPING")],
            "chorus_core":[("CHORUS RATE","CHORUS RATE"),("CHORUS AMT","CHORUS AMT"),("CHORUS MIX","CHORUS MIX"),("CHORUS FEEDBACK","CHORUS FEEDBACK")],
            "chorus_short":[("CHORUS RATE","CHORUS RATE"),("CHORUS AMT","CHORUS AMT"),("CHORUS MIX","CHORUS MIX")],
            "bus_chorus":[("BUS1 REV AFTER CHOR","BUS1 REV AFTER CHOR"),("BUS2 REVERB MIX","BUS2 REVERB MIX")],
            "bus_dist":[("BUS2 REVERB MIX","BUS2 REVERB MIX")],
            "dist_refs":[("COMPRESSOR THRESHLD","COMPRESSOR THRESHLD"),("SYSTEM FEEDBACK","SYSTEM FEEDBACK"),("DIST GAIN IN","DIST GAIN IN"),("DIST GAIN OUT","DIST GAIN OUT")]
        }
        inherit_specs={
            6:[("HALL REVERB","hall_chorus")],
            7:[("HALL REVERB","hall_chorus"),("CHORUS+REVRB","early_only")],
            8:[("HALL REVERB","hall_chorus"),("CHORUS+REVRB","early_only")],
            9:[("HALL REVERB","hall_short")],
            10:[("HALL REVERB","hall_10"),("CHORUS+REVRB","bus_chorus"),("CHORUS+REVRB","chorus_core")],
            11:[("HALL REVERB","hall_10"),("CHORUS+REVRB","bus_dist")],
            12:[("HALL REVERB","hall_12"),("CHORUS+REVRB","chorus_short")],
            13:[("HALL REVERB","hall_13"),("CHORUS+REVRB","bus_dist"),("CMP+DIST+REV","dist_refs")]
        }
        if slot:=int(effect["slot"]):
            specgroups=inherit_specs.get(slot,[])
            existing={_label_key(c["name"]) for c in controls if c.get("editor_visible",True)}
            for reference,groupname in specgroups:
                source_slot=1 if reference=="HALL REVERB" else (6 if reference=="CHORUS+REVRB" else 11)
                source_effect=next((x for x in result if int(x["slot"])==source_slot),None)
                source_controls=source_effect["controls"] if source_effect else controls if source_slot==slot else []
                pairs=shared.get(groupname,[])
                if groupname=="early_only":pairs=[("EARLY RFLECTION LEV","EARLY RFLECTION LEV")]
                for source_name,target_name in pairs:
                    source=next((c for c in source_controls if _label_key(c.get("name",""))==_label_key(source_name) and c.get("editor_visible",True)),None)
                    if not source or _label_key(target_name) in existing:continue
                    cloned=dict(source);key="manual_inherited_"+_key(source.get("id",source_name))
                    cloned.update({"id":key,"key":key,"name":target_name,"order":800+len(controls),"group":_group_for(target_name,key),"route":None,"status":"UNMAPPED","v05_runtime_ready":False,"v05_points":[],"supported_values":[],"catalog_descriptor":False,"manual_subparameter":True,"editor_visible":True,"evidence":f"ASR-10 Musician's Manual Section 6 cross-reference in ROM-{slot:02}; inherited display metadata only; DSP mapping unavailable."})
                    controls.append(cloned);existing.add(_label_key(target_name))
            # BUS1/BUS2 controls named directly in these algorithm descriptions.
            direct_bus={10:[("BUS1 REV AFTER CHOR",6),("BUS2 REVERB MIX",6)],11:[("BUS2 REVERB MIX",6)],12:[],13:[("BUS2 REVERB MIX",6)]}
            if slot in direct_bus:
                for source_name,source_slot in direct_bus[slot]:
                    source_effect=next((x for x in result if int(x["slot"])==source_slot),None)
                    source_controls=source_effect["controls"] if source_effect else []
                    source=next((c for c in source_controls if _label_key(c.get("name",""))==_label_key(source_name) and c.get("editor_visible",True)),None)
                    if source and _label_key(source_name) not in existing:
                        cloned=dict(source);key=f"manual_inherited_{_key(source.get('id',source_name))}"
                        cloned.update({"id":key,"key":key,"order":810+len(controls),"group":"Bus mixing & routing","route":None,"status":"UNMAPPED","v05_runtime_ready":False,"v05_points":[],"supported_values":[],"catalog_descriptor":False,"manual_subparameter":True,"editor_visible":True,"evidence":f"ASR-10 Musician's Manual Section 6 ROM-{slot:02}; algorithm-specific bus control."})
                        controls.append(cloned);existing.add(_label_key(source_name))
            # Slot 10's explicit chorus/reverb group includes detune and low-frequency decay.
            if slot==10:
                for source_name,target_name in [("LOW FREQ DECAY","REVERB LOW FREQ DECAY"),("DETUNE RATE","REVERB DETUNE RATE"),("DETUNE AMT","REVERB DETUNE AMT")]:
                    source=next((c for c in result[0]["controls"] if _label_key(c.get("name",""))==_label_key(source_name)),None)
                    if source and _label_key(target_name) not in existing:
                        cloned=dict(source);key="manual_inherited_"+_key(source.get("id",source_name));cloned.update({"id":key,"key":key,"name":target_name,"order":820+len(controls),"group":"Reverb","route":None,"status":"UNMAPPED","v05_runtime_ready":False,"v05_points":[],"supported_values":[],"catalog_descriptor":False,"manual_subparameter":True,"editor_visible":True,"evidence":"ASR-10 Musician's Manual Section 6 ROM-10 references the Chorus+Reverb detune and reverb parameter group."});controls.append(cloned);existing.add(_label_key(target_name))
            # Slot 13 explicitly reuses compressor/distortion controls from ROM-11.
            if slot==13:
                source_effect=next((x for x in result if int(x["slot"])==11),None)
                for source_name in ("COMPRESSOR THRESHLD","SYSTEM FEEDBACK","DIST GAIN IN","DIST GAIN OUT"):
                    source=next((c for c in (source_effect or {}).get("controls",[]) if c.get("name")==source_name and c.get("editor_visible",True)),None)
                    if source and _label_key(source_name) not in existing:
                        cloned=dict(source);key="manual_inherited_"+_key(source.get("id",source_name));cloned.update({"id":key,"key":key,"order":830+len(controls),"route":None,"status":"UNMAPPED","v05_runtime_ready":False,"v05_points":[],"supported_values":[],"catalog_descriptor":False,"manual_subparameter":True,"editor_visible":True,"evidence":"ASR-10 Musician's Manual Section 6 ROM-13 cross-references CMP+DIST+REV controls."});controls.append(cloned);existing.add(_label_key(source_name))
        # ROM-10 says the DDL left/right delay times are independently adjustable.
        if int(effect["slot"])==10:
            for c in controls:
                if c["key"]=="ddl_time_l_r": c["editor_visible"]=False
            parent=next((x for x in controls if x["key"]=="ddl_time_l_r"),None)
            for side in ("L","R"):
                controls.append({**(parent or {}),"id":f"ddl_time_{side.lower()}","key":f"ddl_time_{side.lower()}","name":f"DDL TIME {side}","order":501 if side=="L" else 502,"range_text":"0 to 1500 ms","range":[0,1500],"group":"Delay","units":"ms","description":f"Digital delay time for the {side} channel, independently adjustable.","route":None,"status":"UNMAPPED","catalog_descriptor":False,"manual_subparameter":True,"editor_visible":True})
        # Section 6 contains explicit MOD SRC/DST/MIN/MAX blocks only for these
        # algorithms. Do not apply the generic template to the other ROM algorithms.
        mod_pages={14:109,15:109,16:109,17:111,18:111,19:112,20:113,21:115,22:117,23:117,24:117,25:118,26:120,28:122,29:122,30:124,31:126,32:126,33:127,34:129,37:134,38:136,39:137,40:139,41:140,42:141,44:145,45:148,46:149,47:151,48:152,49:153}
        if int(effect["slot"]) in mod_pages:
            sources=["WHEEL","PBEND","PRESS","PEDAL","XCTRL","KBD","VEL","KEYDN","SUSTN","FSW-L","PATCH","OFF"]
            mod_defs=[
                ("mod_src_1","MOD SRC 1","discrete",None,sources,"Selects modulation source 1."),
                ("dst_1","DST 1","discrete",None,[],"Chooses an algorithm-specific parameter destination. Valid destination choices are not enumerated in the available registry."),
                ("min_1","MIN 1","numeric_or_continuous",[0,99],[],"Sets the lower modulation amount as a percent of the destination range."),
                ("max_1","MAX 1","numeric_or_continuous",[0,99],[],"Sets the upper modulation amount as a percent of the destination range."),
                ("mod_src_2","MOD SRC 2","discrete",None,sources,"Selects the independent modulation source 2."),
                ("dst_2","DST 2","discrete",None,[],"Chooses the second algorithm-specific parameter destination. Valid destination choices are not enumerated in the available registry."),
                ("min_2","MIN 2","numeric_or_continuous",[0,99],[],"Sets the lower modulation amount for assignment 2 as a percent of its destination range."),
                ("max_2","MAX 2","numeric_or_continuous",[0,99],[],"Sets the upper modulation amount for assignment 2 as a percent of its destination range.")]
            for order,(ident,label,kind,limits,choices,description) in enumerate(mod_defs,700):
                controls.append({"id":f"mod_{ident}","key":f"mod_{ident}","name":label,"order":order,"range_text":("0 to 99 percent of destination range" if limits else (", ".join(choices) if choices else "Algorithm-specific destination; choices not established")),"range":limits,"type":kind,"format":"integer" if limits else "","domain":"integer steps documented" if limits else "enumerated documented source choices","range_variants":[],"display_scale_curve":[],"group":"Modulation","units":"% of destination range" if limits else None,"evidence":f"ASR-10 Musician's Manual Section 6 explicit modulation block (PDF page {mod_pages[int(effect['slot'])]}); source and numeric range from Section 5/6.","description":description,"manual_confidence":"documented; effect-specific live values unverified","default_value":None,"observed_variation_values":[],"documented_choices":choices,"supported_values":[],"observed_choices":choices,"status":"UNMAPPED","route":None,"v05_runtime_ready":False,"v05_points":[],"catalog_descriptor":False,"manual_subparameter":True,"editor_visible":True,"input_disabled":ident.startswith("dst_")})
        # Variation selection is handled by a dedicated PC draft selector, not as
        # an ordinary parameter card or as a native-VST write.
        for c in controls:
            c.setdefault("editor_visible",True)
            if c["key"]=="effect_variation": c["editor_visible"]=False

        # V1's exact runtime registry contains some proven controls not represented
        # among the 594 manual/editor descriptors (notably the reverb bus selectors).
        # Keep those stable controls visible as exact-point selectors, without
        # inventing a broader original range.
        for p in effect.get("verified_runtime_parameters", []):
            ident=_key(p["id"])
            if ident in catalog_keys: continue
            route=vst.get((effect["slot"],ident)); recovered=v05.get((effect["slot"],ident))
            if route and any(c["route"] is route for c in controls): continue
            points=p.get("verified_display_points", [])
            choices=[str(x.get("display_text",x.get("display_value",""))) for x in points]
            if not choices and route: choices=list(route["point_labels"])
            if not route and not (recovered and recovered.get("runtime_ready")): continue
            controls.append({"id":p["id"],"key":ident,"name":p.get("display_name",ident.upper()),
                "order":p.get("display_order",0),"range_text":"Exact verified runtime points: "+", ".join(choices),
                "range":None,"type":"discrete","format":p.get("display_format",""),
                "domain":"enumerated exact verified points","units":p.get("units"),
                "evidence":p.get("trace_evidence",""),"observed_choices":choices,
                "status":"PARTIAL","route":route,"v05_runtime_ready":bool(recovered and recovered.get("runtime_ready")),
                "v05_points":recovered.get("verified_points",[]) if recovered else [],
                "catalog_descriptor":False})
        covered_routes={id(c["route"]) for c in controls if c["route"]}
        for (slot,ident),route in vst.items():
            if slot!=effect["slot"] or id(route) in covered_routes: continue
            choices=list(route["point_labels"])
            controls.append({"id":ident,"key":ident,"name":route["label"],
                "order":route["canonical_parameter_index"],
                "range_text":"Exact verified VST points: "+", ".join(choices),"range":None,
                "type":"discrete","format":"","domain":"enumerated exact VST points",
                "range_variants":[],"display_scale_curve":[],"group":"","units":None,
                "evidence":"Existing append-only VST control; exact point list only.",
                "observed_choices":choices,"status":"PARTIAL","route":route,
                "v05_runtime_ready":False,"v05_points":[],"catalog_descriptor":False})
        for control in controls:
            control.setdefault("catalog_descriptor",True)
            control.setdefault("group",_group_for(control.get("name",""),control.get("id","")))
            if int(effect["slot"]) in (4,5) and control.get("key")=="delay_time_l":
                high=1300 if int(effect["slot"])==5 else 2000
                control.update({"name":"BUS1 DELAY TIME L","range_text":f"0 to {high} ms","range":[0,high],"type":"numeric_or_continuous","format":"integer","domain":"integer steps documented","group":"Delay","units":"ms","description":"BUS1 left-channel delay time; the manual states left and right channels are independently adjustable.","editor_visible":True})
            # Stable identities are scoped by factory slot. The QA matrix is a
            # read-only overlay and never grants DSP write permission.
            qa=qa_params.get(control.get("id"))
            if qa is None and control.get("original_parameter_id"):
                qa=qa_params.get(control["original_parameter_id"])
            parent_id=control.get("parent_parameter_id")
            if qa is None and parent_id:
                qa=qa_params.get(parent_id if str(parent_id).endswith("_1") else f"{parent_id}_1")
            normalization=normalization_by_source.get(control.get("id")) or normalization_by_source.get(control.get("parent_parameter_id"))
            if qa is None and normalization:
                source_id=normalization["source_descriptor_ids"][0]
                qa=qa_params.get(source_id)
            if qa is None and control.get("id","").startswith("manual_env_lev_"):
                qa=qa_params.get("env_lev_1_to_9_1")
            if qa is None and control.get("id","").startswith("manual_positn_bal_"):
                qa=qa_params.get("positn_bal_1_to_3_1")
            if qa is None and control.get("id","").startswith("manual_er_lev_"):
                qa=qa_params.get("er_lev_1_to_4_1")
            if qa is None and control.get("id","").startswith("manual_dist_gain_"):
                qa=qa_params.get("dist_gain_in_out_in_and_out_1")
            if qa is None and int(effect["slot"]) in (4,5):
                control_id=control.get("id","")
                parent_for={"dual_bus1_delay_mix":"bus1_and_2_delay_mix_1","dual_bus2_delay_mix":"bus1_and_2_delay_mix_1",
                    "dual_bus1_feedback":"bus1_and_2_feedback_1","dual_bus2_feedback":"bus1_and_2_feedback_1",
                    "dual_bus1_delay_time_r":"delay_time_1","dual_bus2_delay_time_l":"delay_time_1","dual_bus2_delay_time_r":"delay_time_1"}
                qa=qa_params.get(parent_for.get(control_id,""))
            if qa is None and control.get("id","").startswith("ddl_time_") and int(effect["slot"])==10:
                qa=qa_params.get("ddl_time_l_r_1")
            extra=qa_additional_by_id.get(control.get("id"))
            if extra is None and int(effect["slot"]) in (4,5):
                extra_id={"dual_bus1_delay_time_r":"dual_bs1_time_r","dual_bus2_delay_time_l":"dual_bs2_time_l","dual_bus2_delay_time_r":"dual_bs2_time_r"}.get(control.get("id"))
                extra=qa_additional_by_id.get(extra_id)
            if extra is None:
                extra=next((x for x in qa_additional if _label_key(x.get("control_label",""))==_label_key(control.get("name",""))),None)
            if extra is None and int(effect["slot"])==6 and control.get("name")=="REVERB DIFFUSION":
                extra=next((x for x in qa_additional if x.get("control_label")=="DIFFUSION"),None)
            if extra:
                if qa is None:
                    control["original_parameter_id"]=(extra.get("parameter_ids") or [None])[0]
                control["independent_classification"]=extra.get("classification","UNKNOWN")
                if extra.get("original_os",{}).get("observed"):
                    control["original_os_evidence"]=extra["original_os"]
                control["dsp_evidence"]=extra.get("dsp_evidence",{"classification":"UNKNOWN","mapping":{},"vst_mappings":[],"full_range_implemented":False,"audio_status":"NOT_VALIDATED"})
            control["canonical_identity"]=f"ASR10:ROM-{int(effect['slot']):02}:{control.get('id')}"
            control["original_parameter_id"]=qa.get("id") if qa else control.get("original_parameter_id")
            control["canonical_manual_control_id"]=(normalization or {}).get("canonical_control_id",qa.get("id") if qa else control.get("original_parameter_id") or control.get("id"))
            if qa:
                control["independent_classification"]=qa.get("classification","UNKNOWN")
                control["original_os_evidence"]=qa.get("original_os",{"association_status":"UNKNOWN","observed":False,"labels":[],"values_by_variation":[]})
            if not qa and control.get("group")=="Modulation":
                normalized=_label_key(control.get("name",""))
                os_field=next((f for f in qa_effect.get("os_observed_fields",[]) if _label_key(f.get("label",""))==normalized),None)
                if os_field:
                    control["original_os_evidence"]={"association_status":"OS_OBSERVED_LABEL_MATCH","observed":True,"labels":[os_field["label"]],
                        "values_by_variation":[{"variation":v.get("variation"),"value":v.get("value")} for v in os_field.get("values",[])]}
            if qa:
                control["dsp_evidence"]=qa.get("dsp",{"classification":"UNKNOWN","mapping":{},"vst_mappings":[],"full_range_implemented":False,"audio_status":"NOT_VALIDATED"})
            if extra:
                control["independent_classification"]=extra.get("classification","UNKNOWN")
                if extra.get("original_os",{}).get("observed"):
                    control["original_os_evidence"]=extra["original_os"]
                control["dsp_evidence"]=extra.get("dsp_evidence",control["dsp_evidence"])
            control.setdefault("independent_classification","UNKNOWN")
            control.setdefault("original_os_evidence",{"association_status":"UNKNOWN","observed":False,"labels":[],"values_by_variation":[]})
            control.setdefault("dsp_evidence",{"classification":"UNKNOWN","mapping":{},"vst_mappings":[],"full_range_implemented":False,"audio_status":"NOT_VALIDATED"})
            control["os_scan_status"]=qa_effect.get("os_scan_status","UNKNOWN")
            matrix_routes=control["dsp_evidence"].get("vst_mappings",[])
            matrix_points=next((x.get("point_values",[]) for x in matrix_routes if x.get("point_values")),[])
            control["mapping_evidence_mismatch"]=bool(control.get("route") and matrix_points and list(control["route"].get("point_values",[]))!=list(matrix_points))
            if control.get("route"):
                control["runtime_state"]="EXACT_POINTS_AVAILABLE"
                control["runtime_reason"]="Native VST route is limited to its listed exact display points; other values remain pending PC drafts."
                if control["mapping_evidence_mismatch"]:
                    control["runtime_reason"]+=f" Independent matrix VST points {matrix_points} differ from this route {control['route'].get('point_values')}; the route was not changed."
            elif control["dsp_evidence"].get("mapping",{}).get("observed_setting_points"):
                control["runtime_state"]="PENDING_HOST_ROUTE"
                control["runtime_reason"]="Register evidence is partial and has no accepted native VST route in this editor."
            else:
                control["runtime_state"]="UNMAPPED"
                control["runtime_reason"]="No accepted native VST route is available for this parameter."
        controls.sort(key=lambda c:(c["order"],not c["catalog_descriptor"],c["name"]))
        result.append({"slot": effect["slot"], "name": effect["factory_name"],
            "manual_parameter_count":full_effect.get("parameter_count"),
            "modulation_note":full_effect.get("modulation_controls", ""),
            "os_scan_status":qa_effect.get("os_scan_status","UNKNOWN"),
            "variations_evidence":qa_effect.get("variations",{}),
            "modulation_evidence":qa_effect.get("modulation",{}),
            "os_observed_fields":qa_effect.get("os_observed_fields",[]),
            "normalizations":qa_effect.get("normalizations",[]),
            "additional_recovered_controls":qa_effect.get("additional_recovered_controls",[]),
            "manual_group_warnings":(["Section 6 documents ENV LEV 1–9, but the captured original OS row presents five values. Components 6–9 remain in the manual schema and are hidden from editing until their LCD/page identities are established."] if int(effect["slot"]) in (22,23,24) else []),
            "controls": controls})
    return result
