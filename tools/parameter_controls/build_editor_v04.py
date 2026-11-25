#!/usr/bin/env python3
"""Generate V4 evidence-tiered parameter descriptors, stable bindings and Force pages."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json"
V3 = ROOT / "docs/ASR10_FACTORY_EDITOR_REGISTRY_V03.json"
REGISTRY = ROOT / "docs/ASR10_FACTORY_EDITOR_REGISTRY_V04.json"
UI = ROOT / "force_plugin/ui.json"
HEADER = ROOT / "include/trollfx/es5510_factory_editor_v04.hpp"

def read(path): return json.loads(path.read_text(encoding="utf-8"))

def compound_identity(label):
    m=re.search(r"\s+(L|R|LEFT|RIGHT|IN|OUT)$",label,re.I)
    if not m: return None,None
    return re.sub(r"\s+(L|R|LEFT|RIGHT|IN|OUT)$","",label,flags=re.I),m.group(1).upper()

def build_registry():
    catalog, old = read(CATALOG), read(V3)
    old_by_slot = {e["slot"]: e for e in old["effects"]}
    result=[]
    next_v4_index=27
    for effect in catalog["effects"]:
        slot=effect["slot"]
        old_effect=old_by_slot[slot]
        docs=[]
        for p in effect["parameters"]:
            name=p["display_name"]
            compound,subfield=compound_identity(name)
            docs.append({"id":p["id"],"original_label":name,"editor_order":p.get("display_order"),
                "compound_row_id":compound if compound != name else None,"subfield":subfield,
                "display_format":p.get("display_format"),"units":p.get("units"),
                "documented_range":p.get("documented_range"),"discrete_choices":p.get("choices"),
                "default":p.get("default"),"current_value":None,"evidence":{"DOCUMENTED":True,"OS_OBSERVED":False,
                "REGISTER_VERIFIED":False,"AUDIO_VERIFIED":False,"RUNTIME_READY":False},
                "mapping":None,"current_value_source":"host parameter state when runtime-ready; otherwise unavailable",
                "automation":"read-only until register mapping is verified","state_restoration":"documented value is not stored as a writable DSP value"})
        verified=[]
        for c in old_effect["verified_controls"]:
            compound,subfield=compound_identity(c["original_ui_label"])
            verified.append({"id":c["id"],"label":c["original_ui_label"],
                "host_parameter_name":f"{c['original_ui_label']} @ {slot:02d}",
                "compound_row_id":compound,"subfield":subfield,
                "editor_order":c.get("display_order"),"host_parameter_index_v3":c["plugin_parameter_index"],
                "host_parameter_id_v4":f"factory_v4_slot{slot}_{c['id']}",
                "host_parameter_index_v4":next_v4_index,
                "host_parameter_id_v3":"preserved","display_format":c.get("display_format"),
                "units":c.get("display_units"),"verified_points":c["verified_points"],
                "display_range":c.get("verified_display_range"),"interpolation":"forbidden",
                "current_value":None,"current_value_authority":"live VST parameter state",
                "automation":"host automation calls parameterChanged; audio thread applies the selected verified point",
                "state_restoration":"host chunk restores this effect-qualified stable parameter ID",
                "evidence":{"DOCUMENTED":True,"OS_OBSERVED":True,"REGISTER_VERIFIED":True,
                    "AUDIO_VERIFIED":False,"RUNTIME_READY":True},
                "q_link_ready":True,"write_policy":"only an explicitly selected listed verified point"})
            next_v4_index+=1
        result.append({"slot":slot,"program_id":effect["id"],"factory_name":effect["factory_name"],
            "parameters":docs,"runtime_ready_parameters":verified,
            "runtime_ready_count":len(verified),"package_availability":"resolved by validated package provider",
            "effect_audio_available_without_editor_mapping":True})
    if len(result)!=50 or sum(e["runtime_ready_count"] for e in result)!=19: raise ValueError("Expected 50 effects and 19 verified runtime-ready mappings")
    return {"schema":"trollfx-asr10-factory-editor-registry-v04","version":4,
        "host_parameter_policy":"all existing V1-V3 parameter IDs and indices remain unchanged; V4 verified controls append stable IDs",
        "evidence_classes":["DOCUMENTED","OS_OBSERVED","REGISTER_VERIFIED","AUDIO_VERIFIED","RUNTIME_READY"],
        "mapping_policy":"verified display ranges do not establish value-to-register encoding; no interpolation is permitted",
        "effect_count":50,"documented_parameter_count":sum(len(e["parameters"]) for e in result),
        "runtime_ready_control_count":19,"effects":result}

def build_ui(reg):
    pages=[]
    pages.append({"name":"BROWSE","controls":[
        {"widget":"text","text":"ASR-10 FACTORY FX"},
        "empty","empty","empty",
        "empty","empty","empty","empty",
        {"param":"Host Bypass","widget":"switch"},"empty","empty","empty",
        "Wet / Dry","Input Gain","Output Gain",{"param":"FX Slot","widget":"slider","overlay":"menu"}]})
    edit_cells=["empty"]*16
    edit_cells[0]={"widget":"text","text":"FACTORY EDIT"}
    edit_cells[4]={"param":"EDIT BANK","widget":"knob","overlay":"knob",
        "visibleWhen":{"param":"BANK SELECT ON","choice":"On"}}
    edit_positions=[12,13,14,15,8,9,10,11]
    for i,pos in enumerate(edit_positions,1):
        edit_cells[pos]={"param":f"EDIT SLOT {i}","widget":"knob","overlay":"knob",
            "visibleWhen":{"param":f"SLOT {i} ON","choice":"On"}}
    pages.append({"name":"EDIT","controls":edit_cells})
    pages.append({"name":"MIX","controls":[
        {"widget":"text","text":"EFFECT MIX"},
        "empty","empty","empty",
        "empty","empty","empty","empty",
        {"param":"Host Bypass","widget":"switch"},"empty","empty","empty",
        {"param":"Wet / Dry","widget":"fader"},{"param":"Input Gain","widget":"knob"},
        {"param":"Output Gain","widget":"knob"},{"param":"FX Slot","widget":"slider","overlay":"menu"}]})
    return {"backgroundImage":"panel_background.png","kit":{"theme":"cyan","accent":"ff00c7c2"},
        "style":{"background":"ff12171a","accent":"ff00c7c2","text":"fff4f8fa","muted":"ff85949a"},"pages":pages}

def header(reg):
    lines=["// Generated by tools/parameter_controls/build_editor_v04.py; do not edit.","#pragma once","#include <cstddef>","#include <cstdint>","namespace trollfx::es5510::factory_editor_v04 {",
        "struct Control { std::uint8_t slot; const char* id; const char* label; const char* host_name; const char* parameter_id; int parameter_index; const char* const* labels; const int* values; std::size_t point_count; };",
        "inline constexpr const char* kEffectNames[] = {"]
    for e in reg["effects"]: lines.append(f'    "{e["slot"]:02d} {e["factory_name"]}",')
    lines += ["};","inline constexpr Control kControls[] = {"]
    index=27
    for e in reg["effects"]:
        for c in e["runtime_ready_parameters"]:
            points=c["verified_points"]
            ident=f"factory_v4_slot{e['slot']}_{c['id']}"
            labels=f"kPointLabels{index}"
            values=f"kPointValues{index}"
            host_name=f"{c['label']} @ {e['slot']:02d}"
            lines.append(f"    {{{e['slot']}, \"{c['id']}\", \"{c['label']}\", \"{host_name}\", \"{ident}\", {index}, {labels}, {values}, {len(points)}}},")
            lines.insert(len(lines)-1, f"    // Stable append-only parameter; verified points only.")
            # Emit arrays before controls in a second pass below.
            index+=1
    lines += ["};","} // namespace trollfx::es5510::factory_editor_v04",""]
    # Add point label arrays before control declaration.
    at=lines.index("inline constexpr Control kControls[] = {")
    arr=[]; index=27
    for e in reg["effects"]:
        for c in e["runtime_ready_parameters"]:
            vals=", ".join(json.dumps(p.get("text") or str(p.get("value"))) for p in c["verified_points"])
            arr.append(f"inline constexpr const char* kPointLabels{index}[] = {{{vals}}};")
            nums=", ".join(str(int(p["value"])) for p in c["verified_points"])
            arr.append(f"inline constexpr int kPointValues{index}[] = {{{nums}}};")
            index+=1
    lines[at:at]=arr
    return "\n".join(lines)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--check",action="store_true"); a=ap.parse_args()
    reg=build_registry(); outputs={REGISTRY:json.dumps(reg,indent=2,ensure_ascii=False)+"\n",UI:json.dumps(build_ui(reg),indent=2,ensure_ascii=False)+"\n",HEADER:header(reg)}
    stale=[]
    for p,s in outputs.items():
        if a.check:
            if not p.exists() or p.read_text(encoding="utf-8")!=s: stale.append(str(p.relative_to(ROOT)))
        else: p.write_text(s,encoding="utf-8")
    if stale: raise SystemExit("stale V4 generated files: "+", ".join(stale))
    print(f"V4 registry: 50 effects, {reg['documented_parameter_count']} documented descriptors, 19 runtime-ready controls")
if __name__=="__main__": main()
