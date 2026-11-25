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

def load_registry():
    cat = json.loads((ROOT / "docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json").read_text())
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
        catalog_keys=set()
        for p in sorted(effect["parameters"], key=lambda x: x.get("display_order", 0)):
            ident = _key(p["id"])
            catalog_keys.add(ident)
            route = vst.get((effect["slot"], ident)) or vst_by_label.get((effect["slot"],_label_key(p["display_name"])))
            recovered = v05.get((effect["slot"], ident))
            source_range = _range(p.get("documented_range", ""))
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
            controls.append({"id": p["id"], "key": ident, "name": p["display_name"],
                "order": p.get("display_order", 0), "range_text": p.get("documented_range", ""),
                "range": source_range, "type": p.get("display_type", "numeric_or_continuous"),
                "format": p.get("display_format", ""), "domain": p.get("display_domain", ""),
                "range_variants": p.get("documented_range_variants", []),
                "display_scale_curve": p.get("display_scale_curve", p.get("editor_scale_curve", [])),
                "group": p.get("group", p.get("parameter_group", "")),
                "units": p.get("units"), "evidence": p.get("evidence", ""),
                "observed_choices": obs, "status": status, "route": route,
                "v05_runtime_ready": bool(recovered and recovered.get("runtime_ready")),
                "v05_points": recovered.get("verified_points", []) if recovered else []})
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
        controls.sort(key=lambda c:(c["order"],not c["catalog_descriptor"],c["name"]))
        result.append({"slot": effect["slot"], "name": effect["factory_name"], "controls": controls})
    return result
