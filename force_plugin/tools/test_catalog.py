#!/usr/bin/env python3
"""Focused checks for factory labels, V4 metadata and V4.1 routed Q-Link maps."""
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
assert [p["name"] for p in ui["pages"]]==["BROWSE","EDIT","MIX"]
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
edit=ui["pages"][1]
positions=[12,13,14,15,8,9,10,11]
names=[edit["controls"][i]["param"] for i in positions]
assert names==[f"EDIT SLOT {i}" for i in range(1,9)]
assert edit["controls"][4]["visibleWhen"]["param"]=="BANK SELECT ON"
assert edit["controls"][4]["widget"]=="knob"
assert all(edit["controls"][i]["visibleWhen"]["param"]==f"SLOT {n} ON"
           for n,i in enumerate(positions,1))
release_skin=ROOT/"dist"/"TROLLfx - VST - ASR10 FX Collection"/"Plugin Skins"
if release_skin.is_dir():
    tui=json.loads((release_skin/"TUI.json").read_text())
    qlinks=json.loads((release_skin/"Q-Links.json").read_text())
    tabs=tui["pageData"]["tabs"]; maps=qlinks["Screen Mode Q-Links"]["map"]
    assert len(tabs)==len(maps)==3
    first=maps[0]["Q-Links"]
    assert [first[f"Q-Link {n}"] for n in range(1,6)]==[1,2,3,0,4]
    q=maps[1]["Q-Links"]
    assert [q[f"Q-Link {n}"] for n in range(1,9)]==list(range(46,54))
    assert q["Q-Link 9"]==54
    assert sum(q[f"Q-Link {n}"]!=-1 for n in range(1,17))==9
print("50 effect labels, 594 descriptors, 19 verified controls and one routed EDIT map: PASS")
