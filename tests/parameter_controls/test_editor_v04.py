import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("editor_v04",ROOT/"tools/parameter_controls/build_editor_v04.py")
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
reg=json.loads((ROOT/"docs/ASR10_FACTORY_EDITOR_REGISTRY_V04.json").read_text())
ui=json.loads((ROOT/"force_plugin/ui.json").read_text())
assert reg["effect_count"]==50 and reg["documented_parameter_count"]==594
assert reg["runtime_ready_control_count"]==19
assert [p["name"] for p in ui["pages"][:2]]==["BROWSE","MIX"]
controls=[]
for effect in reg["effects"]:
    controls.extend((effect["slot"],c) for c in effect["runtime_ready_parameters"])
assert len(controls)==19
assert len({c["parameter_id_v3"] if "parameter_id_v3" in c else f"factory_v4_slot{s}_{c['id']}" for s,c in controls})==19
indices=[c["host_parameter_index_v4"] for _,c in controls]
assert indices==list(range(27,46))
assert all(c["current_value"] is None and c["automation"] and c["state_restoration"] for _,c in controls)
index=27
expected_pages=[]
for effect in reg["effects"]:
    controls=effect["runtime_ready_parameters"]
    for bank,start in enumerate(range(0,len(controls),8),start=1):
        expected_pages.append((effect,bank,controls[start:start+8]))
pages=ui["pages"][2:]
assert len(pages)==len(expected_pages)
for page,(effect,bank,expected) in zip(pages,expected_pages):
    slot=effect["slot"]
    assert page["name"]==(f"{slot:02d} EDIT" if bank==1 else f"{slot:02d} E{bank}")
    positions=[12,13,14,15,8,9,10,11]
    bindings=[page["controls"][i]["param"] for i in positions
              if isinstance(page["controls"][i],dict) and "param" in page["controls"][i]]
    assert bindings==[p["host_parameter_name"] for p in expected]
    assert len(bindings)<=8
    for p in expected:
        assert p["evidence"]["REGISTER_VERIFIED"] and p["evidence"]["RUNTIME_READY"]
        assert p["interpolation"]=="forbidden"
        index+=1
assert index==46
# SDK Q-Link generator uses slot_qlink(row,col)=13+col-4*row. Editor
# widgets occupy the Q1-Q8 grid cells, so maps are slot-specific and bounded.
for page in ui["pages"][2:]:
    controls_on_page=[page["controls"][i] for i in [12,13,14,15,8,9,10,11]
                      if isinstance(page["controls"][i],dict) and "param" in page["controls"][i]]
    assert len(controls_on_page)<=8
assert mod.build_registry()["documented_parameter_count"]==594
assert mod.header(reg).count("factory_v4_slot")==19
print("V4 evidence model, 50 effect pages, 19 static parameter bindings: PASS")
