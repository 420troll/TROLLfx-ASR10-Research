# ASR-10 FX Collection V3 retro graphics pack

This pack supplies reusable graphite, brushed-metal and pale-LCD graphics for the V3 interface. No separate retro mockup image was present in the checked-out repository, so the preview follows the visual brief in the task. It is an asset handoff for Codex 2; it does not change `force_plugin/ui.json`, parameter bindings, Q-Link maps, DSP code or the V1 package.

## Contents

- `assets/panel_background.png`: production SDK background image at 1280×628. The recessed parameter wells align to the SDK's fixed 4×4 slots.
- `assets/knob_*.png`, `fader_h_*.png`, `toggle_*`, `button_*` and `seg*`: rendered by the official SDK `make_ui_kit.py` with a custom teal accent. These are the native film-strip and button resources.
- `assets/parameter_card*.png`, `lcd_frame.png`, `factory_program_display_frame.png`, `status_led_*.png`, `separator.png`, `tab_*.png`, `qlink_q1.png`–`qlink_q8.png`, and `trollfx_asr10_wordmark.png`: reusable source graphics for supported background composition and design reference. The manifest distinguishes the assets the SDK can bind from concept components.
- `asset-manifest.json`: dimensions, color mode, alpha/transparency, frame dimensions, intended use and integration classification for every image.
- `preview/retro-interface-concept.png`: visual example of the assets over a representative VST page, with supported and concept-only parts called out.
- `tools/graphics/generate_asr10_retro_graphics.py`: source artwork generator. It requires Python 3, Pillow 9.1+ and an SDK checkout.

All PNG resources use RGBA samples; partially transparent assets keep alpha. The full panel is opaque. TUI JSON colors use 8-digit ARGB hex (`ff00c7c2`); this differs from the PNG channel order. There are no bundled fonts, Ensoniq logos, device captures, or firmware artwork.

The SDK-generated UI-kit assets carry the inMusic SDK MIT notice in `LICENSES/SDK-MIT-NOTICE.txt`; original TROLLfx artwork and generation sources are credited in `LICENSES/GRAPHICS-CREDITS.md`.

## SDK behavior and integration

The inspected SDK targets the 1280×628 tab-content area and lays controls out in fixed 278×107 slots at x=`23,343,663,983` and y=`45,196,346,497`. It supports a single whole-page `backgroundImage`, vertical PNG knob film strips, button image states, native text/value labels, and native function-key tab and Q-Link JSON. The checked-in UI kit and generator document PNG resources; SVG support was not found or tested. The SDK does not provide an arbitrary image widget or per-control dynamic background-image switching through `ui.json`.

The production background is a single 1280×628 PNG. Its sixteen card wells are part of that image; the SDK's native widgets draw above them. Copy the file into the V3 project's `assets/` directory and set this in the layout JSON (Codex 2 owns that file):

```json
{
  "backgroundImage": "panel_background.png",
  "kit": { "theme": "cyan", "accent": "ff00c7c2" },
  "style": {
    "background": "ff15191c",
    "accent": "ff00c7c2",
    "text": "fff4f8fa",
    "muted": "ff85949a"
  }
}
```

The SDK build copies project `assets/` into `Plugin Skins/`; it then generates `TUI.json` and `Q-Links.json`. Keep dynamic control names, parameter values, active factory slot, availability and status in native UI widgets/logic. The blank program LCD bezel is already part of the panel; putting dynamic text in the header would require a hand-authored, host-validated TUI label at a tested coordinate. With the generator's grid-only layout, show the effect name in a native grid text/control slot instead. Do not bake a selected effect name or parameter value into `panel_background.png`.

The custom tab chips and Q1–Q8 badges are preview/reference art. MPC tabs must use native editable function-key labels; Q-Link assignment must be made in `Q-Links.json` from the active effect's actual parameter map. The SDK describes 16 physical Q-Links, so Q1–Q8 badges do not replace or alter its map. Active/disabled/unavailable card images and LEDs are static reference states: this SDK interface does not dynamically switch arbitrary card art per control. Use native text or supported widget states to communicate missing/unavailable effects.

## Regenerate

```sh
python3 tools/graphics/generate_asr10_retro_graphics.py \
  --sdk /path/to/AkaiForceSDK
python3 tools/graphics/test_graphics_pack.py
python3 tools/graphics/smoke_sdk_skin_generation.py \
  --sdk /path/to/AkaiForceSDK
```

The generator calls only the SDK's `tools/make_ui_kit.py`, writes into this V3 graphics directory, and does not modify the SDK checkout. `kit.json` retains the SDK theme and frame metadata.
