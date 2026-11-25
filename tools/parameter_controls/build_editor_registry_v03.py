#!/usr/bin/env python3
"""Generate the centralized 50-slot editor registry, runtime table and Force skin."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "force_plugin/effects.json"
CATALOG = ROOT / "docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json"
MAPPINGS = ROOT / "docs/ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json"
REGISTRY = ROOT / "docs/ASR10_FACTORY_EDITOR_REGISTRY_V03.json"
UI = ROOT / "force_plugin/ui.json"
HEADER = ROOT / "include/trollfx/es5510_factory_editor_v03.hpp"

# The first four indices are long-standing BUS controls. All later IDs are the
# append-only V2 choice parameters. Keep this map explicit and tested.
PARAMETER_BINDINGS = {
    (1, "reverb_mix_bus1"): (8, "REVERB MIX BUS1 (HALL)"),
    (1, "reverb_mix_bus2"): (9, "REVERB MIX BUS2 (HALL)"),
    (2, "reverb_mix_bus1"): (10, "REVERB MIX BUS1 (44KHZ)"),
    (2, "reverb_mix_bus2"): (11, "REVERB MIX BUS2 (44KHZ)"),
    (1, "decay_time"): (12, "DECAY TIME (HALL)"),
    (1, "hi_freq_damping"): (13, "HI FREQ DAMPING (HALL)"),
    (3, "decay_time"): (14, "DECAY TIME (ROOM)"),
    (3, "diffusion"): (15, "DIFFUSION"),
    (3, "hi_freq_damping"): (16, "HI FREQ DAMPING (ROOM)"),
    (4, "delay_time_l"): (17, "BS1 TIME L"),
    (6, "chorus_rate"): (18, "CHORUS RATE"),
    (7, "phase_rate"): (19, "PHASE RATE"),
    (28, "preamp_gain"): (20, "PREAMP GAIN"),
    (41, "voice1_fine"): (21, "VOICE1 FINE"),
    (42, "comp_ratio"): (22, "COMP RATIO"),
    (49, "bass_fc"): (23, "BASS FC"),
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_registry() -> dict:
    effects = read_json(EFFECTS)
    catalog = read_json(CATALOG)
    mapping_source = read_json(MAPPINGS)
    catalog_by_slot = {row["slot"]: row for row in catalog["effects"]}
    mapped_by_slot = {row["slot"]: row for row in mapping_source["effects"]}
    registry_effects = []
    for effect in effects:
        slot = effect["slot"]
        catalog_effect = catalog_by_slot[slot]
        mapped = mapped_by_slot.get(slot, {"parameters": []})
        verified_by_id = {p["id"]: p for p in mapped["parameters"]}
        verified = []
        for parameter in mapped["parameters"]:
            key = (slot, parameter["id"])
            if key not in PARAMETER_BINDINGS:
                raise ValueError(f"No stable plugin parameter binding for slot {slot} {parameter['id']}")
            index, host_name = PARAMETER_BINDINGS[key]
            verified.append({
                "slot": slot,
                "id": parameter["id"],
                "original_ui_label": parameter["ui_label"],
                "plugin_parameter_index": index,
                "plugin_parameter_name": host_name,
                "display_units": parameter.get("units"),
                "display_format": parameter.get("display_format"),
                "display_order": parameter.get("live_display_order"),
                "verified_points": parameter["points"],
                "editable": True,
                "interpolation": "unsupported",
                "bank": 1 if index <= 15 else 2,
                "qlink": index - 7,
                "evidence": "OS 3.53 repeated live UI adjustment, reversal, and ordered host GPR write observation",
            })
        if len(verified) != len(mapped["parameters"]):
            raise ValueError(f"Inconsistent verified mapping count for slot {slot}")
        registry_effects.append({
            "slot": slot,
            "program_id": catalog_effect["id"],
            "factory_name": effect["name"],
            "category": effect.get("category"),
            "runtime_id": effect.get("runtime"),
            "package_availability": "resolved from validated provider at runtime",
            "documented_controls": [
                {
                    "id": p["id"],
                    "original_ui_label": p["display_name"],
                    "documented_range": p.get("documented_range"),
                    "units": p.get("units"),
                    "status": "documentation-only; live register mapping unverified",
                    "editable": False,
                }
                for p in catalog_effect["parameters"]
            ],
            "verified_controls": verified,
            "verified_control_count": len(verified),
            "editor_status": "verified-controls" if verified else "unmapped-no-verified-controls",
        })
    if len(registry_effects) != 50:
        raise ValueError(f"Expected exactly 50 effects, got {len(registry_effects)}")
    if sum(e["verified_control_count"] for e in registry_effects) != 16:
        raise ValueError("Expected 16 V2 verified controls")
    return {
        "schema": "trollfx-asr10-factory-editor-registry-v03",
        "version": 3,
        "parameter_ids": "unchanged; controls use existing V2 plugin indices 8..23",
        "package_policy": "all effect availability is obtained from the trusted package provider; metadata never makes a package eligible",
        "editing_policy": "only verified discrete display points are editable; no interpolation or guessed defaults",
        "effects": registry_effects,
    }


def make_ui(registry: dict) -> dict:
    by_index = {
        control["plugin_parameter_index"]: control
        for effect in registry["effects"] for control in effect["verified_controls"]
    }
    # The SDK assigns a grid row to its Q-Link group in reverse vertical order.
    # This preserves the existing Q1..Q16 -> parameter 8..23 mapping.
    qlink_layout = (list(range(20, 24)) + list(range(16, 20)) +
                    list(range(12, 16)) + list(range(8, 12)))
    if set(by_index) != set(qlink_layout):
        raise ValueError("The fixed V2 Q-Link contract requires parameter indices 8..23")
    editor_rows = [by_index[index] for index in qlink_layout]
    # Preserve the shipped V2 order: Q1-Q4 remain the four HALL/ROM02 BUS
    # bindings and Q5-Q16 remain the twelve appended controls.
    editor_controls = []
    for control in editor_rows:
        editor_controls.append({
            "param": control["plugin_parameter_name"],
            "widget": "switch" if control["plugin_parameter_index"] < 12 else "slider",
            "overlay": "menu",
            "visibleWhen": {"param": "FX Slot", "index": control["slot"] - 1},
        })
    if len(editor_controls) != 16:
        raise ValueError("UI must expose exactly the 16 verified controls")
    return {
        "kit": {"theme": "cyan", "accent": "ff00d4d8"},
        "style": {"background": "ff15191c", "accent": "ff00d4d8",
                  "text": "fff4f8fa", "muted": "ff85949a"},
        "pages": [
            {"name": "BROWSE", "controls": [
                {"widget": "text", "text": "TROLLfx / ASR-10 FACTORY FX"},
                {"widget": "text", "text": "50 SLOTS / STATUS IN EFFECT LABEL"},
                {"widget": "text", "text": "EDIT SHOWS VERIFIED CONTROLS ONLY"},
                {"widget": "text", "text": "NO VERIFIED EDIT? AUDIO STILL LOADS"},
                "empty", "empty", "empty", "empty",
                {"param": "Host Bypass", "widget": "switch"}, "empty", "empty", "empty",
                "Wet / Dry", "Input Gain", "Output Gain",
                {"param": "FX Slot", "widget": "slider", "overlay": "menu"},
            ]},
            {"name": "MIX", "controls": [
                {"widget": "text", "text": "STEREO / NATIVE ES5510 / EXPERIMENTAL 48 kHz"},
                {"widget": "text", "text": "HOST MIX CONTROLS"},
                "empty", "empty", "empty", "empty", "empty", "empty",
                {"param": "Host Bypass", "widget": "switch"}, "empty", "empty", "empty",
                {"param": "Wet / Dry", "widget": "fader"},
                {"param": "Input Gain", "widget": "knob"},
                {"param": "Output Gain", "widget": "knob"},
                {"param": "FX Slot", "widget": "slider", "overlay": "menu"},
            ]},
            {"name": "EDIT", "controls": editor_controls},
        ],
    }


def make_header(registry: dict) -> str:
    rows = sorted((c for e in registry["effects"] for c in e["verified_controls"]),
                  key=lambda c: c["plugin_parameter_index"])
    lines = [
        "// Generated by tools/parameter_controls/build_editor_registry_v03.py; do not edit.",
        "#pragma once", "#include <cstddef>", "#include <cstdint>",
        "namespace trollfx::es5510::factory_editor_v03 {",
        "inline constexpr const char* kEffectNames[] = {",
    ]
    for effect in registry["effects"]:
        lines.append(f'    "{effect["slot"]:02d} {effect["factory_name"]}",')
    lines += [
        "};",
        "struct FactoryControl { int parameter_index; std::uint8_t slot; const char* id; const char* label; };",
        "inline constexpr std::size_t kLegacyControlCount = 4;",
        "inline constexpr FactoryControl kControls[] = {",
    ]
    for control in rows:
        lines.append(
            f'    {{{control["plugin_parameter_index"]}, {control["slot"]}, '
            f'"{control["id"]}", "{control["plugin_parameter_name"]}"}},'
        )
    lines += ["};", "} // namespace trollfx::es5510::factory_editor_v03", ""]
    return "\n".join(lines)


def write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args()
    registry = build_registry()
    outputs = {
        REGISTRY: json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        UI: json.dumps(make_ui(registry), indent=2, ensure_ascii=False) + "\n",
        HEADER: make_header(registry),
    }
    stale = []
    for path, contents in outputs.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != contents:
                stale.append(str(path.relative_to(ROOT)))
        else:
            write(path, contents)
    if stale:
        raise SystemExit("stale generated editor files: " + ", ".join(stale))
    print("50-slot editor registry, Force skin, and C++ control bindings: " + ("CURRENT" if args.check else "GENERATED"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
