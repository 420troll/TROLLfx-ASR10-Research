#!/usr/bin/env python3
"""Focused checks for the Force collection labels, V4 metadata and static Q-Link maps."""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
effects=json.loads((ROOT/"effects.json").read_text())
assert len(effects)==50 and [x["slot"] for x in effects]==list(range(1,51))
catalog=(ROOT.parent/"docs/ASR10_ROM_EFFECT_CATALOG.md").read_text()
expected=[(int(n),name.strip()) for n,name in re.findall(r'^\|\s*(\d{2})\s*\|\s*([^|]+?)\s*\|',catalog,re.M)]
expected=[x for x in expected if 1<=x[0]<=50]
assert [(x["slot"],x["name"]) for x in effects]==expected
ui=json.loads((ROOT/"ui.json").read_text())
assert ui["kit"]["theme"]=="cyan" and ui["backgroundImage"]=="panel_background.png"
assert [p["name"] for p in ui["pages"][:2]]==["BROWSE","MIX"]
assert all(len(p["controls"])==16 for p in ui["pages"])
src=(ROOT/"src/ASR10FXCollection.cpp").read_text()
header=(ROOT.parent/"include/trollfx/es5510_factory_editor_v04.hpp").read_text()
provider=(ROOT/"src/ES5510FactoryPackageProvider.cpp").read_text()
for slot,name in expected: assert f'"{slot:02d} {name}"' in header
assert "TROLLfx_GetProductionFactoryPackageProvider()" in src and "backend_.set_verified_parameter" in src
assert "parameterChanged(int index" in src and "v4_control_changed_" in src
assert "append_verified_parameters(d)" in provider
registry=json.loads((ROOT.parent/"docs/ASR10_FACTORY_EDITOR_REGISTRY_V04.json").read_text())
assert registry["documented_parameter_count"]==594 and registry["runtime_ready_control_count"]==19
slot_index=27
ready=[e for e in registry["effects"] if e["runtime_ready_parameters"]]
expected_pages=[]
for effect in registry["effects"]:
    controls=effect["runtime_ready_parameters"]
    for bank,start in enumerate(range(0,len(controls),8),start=1):
        expected_pages.append((effect,bank,controls[start:start+8]))
assert len(ui["pages"])==2+len(expected_pages)
for page,(effect,bank,controls) in zip(ui["pages"][2:],expected_pages):
    assert page["name"]==(f'{effect["slot"]:02d} EDIT' if bank==1 else f'{effect["slot"]:02d} E{bank}')
    names=[page["controls"][i]["param"] for i in [12,13,14,15,8,9,10,11]
           if isinstance(page["controls"][i],dict) and "param" in page["controls"][i]]
    assert names==[c["host_parameter_name"] for c in controls]
    slot_index+=len(controls)
assert slot_index==46
release_skin=ROOT/"dist"/"TROLLfx - VST - ASR10 FX Collection"/"Plugin Skins"
if release_skin.is_dir():
    tui=json.loads((release_skin/"TUI.json").read_text())
    qlinks=json.loads((release_skin/"Q-Links.json").read_text())
    tabs=tui["pageData"]["tabs"]; maps=qlinks["Screen Mode Q-Links"]["map"]
    assert len(tabs)==len(maps)==len(expected_pages)+2
    first=maps[0]["Q-Links"]
    assert [first[f"Q-Link {n}"] for n in range(1,6)]==[1,2,3,0,4]
    index=27
    for (effect,bank,controls),entry in zip(expected_pages,maps[2:]):
        count=len(controls); q=entry["Q-Links"]
        assert [q[f"Q-Link {n}"] for n in range(1,count+1)]==list(range(index,index+count))
        assert all(q[f"Q-Link {n}"]==-1 for n in range(count+1,17))
        index+=count
    assert index==46
print("50 effect labels, 594 descriptors, 19 controls and static effect Q-Link maps: PASS")
