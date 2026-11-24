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
assert [page["name"] for page in ui["pages"]] == ["BROWSE", "MIX", "EDIT"]
for page in ui["pages"]:
    assert len(page["controls"]) == 16

src = (ROOT / "src/ASR10FXCollection.cpp").read_text()
for label in expected:
    assert f'"{label[0]:02d} {label[1]}"' in src
assert "provider->package_for_slot(slot)" in src
assert "[UNAVAILABLE]" in src and "[READY]" in src
assert '#include "ES5510FactoryPackageProvider.h"' in src
assert "TROLLfx_GetProductionFactoryPackageProvider()" in src
assert "backend_.set_verified_bus" in src
assert "backend_.request_effect" in src and "backend_.process" in src
assert "visibleWhen" in (ROOT / "ui.json").read_text()
release_skin = ROOT / "dist" / "TROLLfx - VST - ASR10 FX Collection" / "Plugin Skins"
if (release_skin / "Q-Links.json").is_file():
    qlinks = json.loads((release_skin / "Q-Links.json").read_text())
    maps = qlinks["Screen Mode Q-Links"]["map"]
    assert len(maps) == 3
    first = maps[0]["Q-Links"]
    assert [first[f"Q-Link {n}"] for n in range(1, 6)] == [1, 2, 3, 0, 4]
    editor = maps[2]["Q-Links"]
    assert [editor[f"Q-Link {n}"] for n in range(1, 5)] == [8, 9, 10, 11]
    assert all(editor[f"Q-Link {n}"] == -1 for n in range(5, 9))
print("50 original labels, provider-derived availability, page layout and verified controls: PASS")
