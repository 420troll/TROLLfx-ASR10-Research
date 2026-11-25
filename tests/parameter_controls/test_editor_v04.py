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
assert [p["name"] for p in ui["pages"]]==["BROWSE","EDIT","MIX"]
controls=[]
for effect in reg["effects"]:
    controls.extend((effect["slot"],c) for c in effect["runtime_ready_parameters"])
assert len(controls)==19
assert len({c["parameter_id_v3"] if "parameter_id_v3" in c else f"factory_v4_slot{s}_{c['id']}" for s,c in controls})==19
indices=[c["host_parameter_index_v4"] for _,c in controls]
assert indices==list(range(27,46))
assert all(c["current_value"] is None and c["automation"] and c["state_restoration"] for _,c in controls)
edit=ui["pages"][1]
assert edit["controls"][4]["param"]=="EDIT BANK"
assert edit["controls"][4]["widget"]=="knob"
assert edit["controls"][4]["visibleWhen"]["param"]=="BANK SELECT ON"
positions=[12,13,14,15,8,9,10,11]
edit_controls=[edit["controls"][i] for i in positions]
assert [x["param"] for x in edit_controls]==[f"EDIT SLOT {i}" for i in range(1,9)]
assert [x["visibleWhen"]["param"] for x in edit_controls]==[f"SLOT {i} ON" for i in range(1,9)]
assert all(x["widget"]=="knob" and x["overlay"]=="knob" for x in edit_controls)
assert [e["runtime_ready_count"] for e in reg["effects"] if e["runtime_ready_count"]]==[4,2,3,1,1,1,1,1,1,1,1,1,1]
# The official generator binds the eight stable routing parameters. Runtime
# effect routing happens in the plugin, not by changing this SDK map.
assert mod.build_registry()["documented_parameter_count"]==594
assert mod.header(reg).count("factory_v4_slot")==19
assert mod.build_registry()["documented_parameter_count"]==594
assert mod.header(reg).count("factory_v4_slot")==19
print("V4.1 evidence model, three shared tabs, 19 routed verified controls: PASS")
