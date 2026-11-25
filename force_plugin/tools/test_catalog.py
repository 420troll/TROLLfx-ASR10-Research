#!/usr/bin/env python3
"""Focused checks for the Force collection labels and skin bindings."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
effects = json.loads((ROOT / "effects.json").read_text())
assert len(effects) == 50 and [x["slot"] for x in effects] == list(range(1, 51))
catalog = (ROOT.parent / "docs/ASR10_ROM_EFFECT_CATALOG.md").read_text()
expected = [(int(n), name.strip()) for n, name in
            re.findall(r'^\|\s*(\d{2})\s*\|\s*([^|]+?)\s*\|', catalog, re.M)]
expected = [item for item in expected if 1 <= item[0] <= 50]
assert [(x["slot"], x["name"]) for x in effects] == expected

ui = json.loads((ROOT / "ui.json").read_text())
assert ui["kit"]["theme"] == "cyan"
assert [page["name"] for page in ui["pages"]] == ["BROWSE", "MIX", "EDIT", "EDIT 2"]
for page in ui["pages"]:
    assert len(page["controls"]) == 16

src = (ROOT / "src/ASR10FXCollection.cpp").read_text()
control_header = (ROOT.parent / "include/trollfx/es5510_factory_editor_v03.hpp").read_text()
provider_src = (ROOT / "src/ES5510FactoryPackageProvider.cpp").read_text()
for label in expected:
    assert f'"{label[0]:02d} {label[1]}"' in control_header
assert "provider->package_for_slot(slot)" in src
assert "[UNAVAILABLE]" in src and "[READY]" in src
assert '#include "ES5510FactoryPackageProvider.h"' in src
assert "TROLLfx_GetProductionFactoryPackageProvider()" in src
assert "backend_.set_verified_parameter" in src
assert "kFactoryControls" in src and "set_verified_parameter" in src
assert "parameter_discovery_v02.hpp" in provider_src
assert "parameter_discovery_v03.hpp" in provider_src
assert "append_verified_parameters(d)" in provider_src
assert "append_verified_parameters(d);" in provider_src
assert "backend_.request_effect" in src and "backend_.process" in src
assert "not a factory default/reset" in src
assert "visibleWhen" in (ROOT / "ui.json").read_text()
assert "NO VERIFIED EDIT" in (ROOT / "ui.json").read_text()
editor_controls = ui["pages"][2]["controls"]
assert [x["param"] for x in editor_controls] == [
    "PREAMP GAIN", "VOICE1 FINE", "COMP RATIO", "BASS FC",
    "HI FREQ DAMPING (ROOM)", "BS1 TIME L", "CHORUS RATE", "PHASE RATE",
    "DECAY TIME (HALL)", "HI FREQ DAMPING (HALL)", "DECAY TIME (ROOM)",
    "DIFFUSION",
    "REVERB MIX BUS1 (HALL)", "REVERB MIX BUS2 (HALL)",
    "REVERB MIX BUS1 (44KHZ)", "REVERB MIX BUS2 (44KHZ)"]
editor_v3 = ui["pages"][3]["controls"]
assert [x["param"] for x in editor_v3[12:15]] == [
    "BS1 TIME L (44KHZ DELAYS)", "FLANGE RATE", "QUALITY"]
catalog_v2 = json.loads((ROOT.parent / "docs/ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json").read_text())
assert sum(len(effect["parameters"]) for effect in catalog_v2["effects"]) == 16
catalog_v3 = json.loads((ROOT.parent / "docs/ASR10_FACTORY_PARAMETER_RECOVERY_V03.json").read_text())
assert len(catalog_v3["new_verified_controls"]) == 3
assert len(catalog_v3["range_scans"]) == 3
release_skin = ROOT / "dist" / "TROLLfx - VST - ASR10 FX Collection" / "Plugin Skins"
if (release_skin / "Q-Links.json").is_file():
    qlinks = json.loads((release_skin / "Q-Links.json").read_text())
    maps = qlinks["Screen Mode Q-Links"]["map"]
    assert len(maps) == 4
    first = maps[0]["Q-Links"]
    assert [first[f"Q-Link {n}"] for n in range(1, 6)] == [1, 2, 3, 0, 4]
    editor = maps[2]["Q-Links"]
    assert [editor[f"Q-Link {n}"] for n in range(1, 17)] == list(range(8, 24))
    v3_editor = maps[3]["Q-Links"]
    assert [v3_editor[f"Q-Link {n}"] for n in range(1, 4)] == [24, 25, 26]
print("50 original labels, provider-derived availability, page layout and verified controls: PASS")
