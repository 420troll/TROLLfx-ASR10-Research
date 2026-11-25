# ASR-10 FX Collection V3 retro graphics handoff

Branch: `feature/asr10-retro-graphics-v3`

Codex 2 owns the V3 layout, parameter bindings, Q-Link assignments and runtime. This branch contributes images and integration guidance only; it does not alter those implementation files.

## Asset paths

Pack root: `force_plugin/graphics/v3/`

- SDK-ready page art: `force_plugin/graphics/v3/assets/panel_background.png`
- SDK film strips and button states: `force_plugin/graphics/v3/assets/knob_*.png`, `knob_small_*.png`, `fader_h_*.png`, `toggle_*.png`, `button_*.png`, `seg2/3/4_*.png`
- Reusable concept/source elements: card states, LCD/program frames, wordmark, LEDs, separators, tab badges and Q-Link Q1–Q8 badges in the same `assets/` folder
- Full reference: `force_plugin/graphics/v3/README.md` and `asset-manifest.json`
- Layout preview: `force_plugin/graphics/v3/preview/retro-interface-concept.png`
- Regenerator: `tools/graphics/generate_asr10_retro_graphics.py`

The supported production integration is the single 1280×628 page background plus native SDK film-strip/button resources. The label/value controls, effect identities, state indicators, function tabs and Q-Link assignment remain native and state-aware. Custom LCD as an independent control, free-position art, custom tab artwork, dynamic Q1–Q8 images, and per-control disabled/unavailable card skins are concept/reference elements because the inspected SDK's `ui.json` generator does not support arbitrary image widgets or dynamic card switching.

## SDK investigation and validation

No separate ASR-10 retro mockup file was available in the checked-out repository, so the preview follows the supplied style description rather than claiming a pixel-matched recreation.

Inspected the official checkout at `/mnt/c/Users/Gamer/research/AkaiForceSDK`: `tools/make_ui_kit.py`, `tools/gen_ui.py`, `schemas/ui.schema.json`, `tools/validate.py`, `ui-kit/README.md` and the currently generated ASR-10 `Plugin Skins` folder. The SDK uses ARGB hex strings for UI colors and RGBA PNG for image resources. Its native grid is fixed at 4×4, 278×107 per slot. Film strips are vertical: 127 frames, minimum at the top; knob frames are 90×90 (or 56×56 small), horizontal fader frames 248×36. Button assets are native single-frame PNGs: 64×32 toggle, 120×44 push button, and 122/80/58×40 segment assets. Images are drawn at native dimensions. SVG support was not found in the UI kit/generator documentation and was not tested; all shipped art is PNG.

The generator accepts `backgroundImage` by filename and places it in each tab's focused/unfocused background data; the build copies `assets/` into `Plugin Skins/`. The custom kit uses `ff00c7c2` teal, with graphite bodies and pale display graphics. It does not require new plugin dependencies beyond Pillow for regenerating the custom raster art; installed assets are PNG only.

The generator smoke check uses a temporary parameter table and the actual SDK `gen_ui.py`, confirming the generated `TUI.json` references `panel_background.png` in focused and unfocused page backgrounds, and creates the Q-Link map and film-strip controls. Re-run it with `python3 tools/graphics/smoke_sdk_skin_generation.py --sdk /path/to/AkaiForceSDK`. The pack checker validates every PNG's dimensions, channel mode, alpha metadata, film-strip frame geometry and manifest coverage. These are asset and generator checks only; they do not verify final V3 layout placement or physical display rendering.

## Integration status

Integrated into `integration/asr10-force-per-effect-editor-v3` at source commit `a9c0255`. The project stages `panel_background.png` and the selected official-SDK kit images from `force_plugin/assets/`; generated TUI references the background, and the SDK build copies the supported assets into `Plugin Skins/`. The generated four-page Q-Link map remains data-driven from the existing plugin parameter controls. The native VST/SDK host tests, Q-Link/catalog tests, and package checks were rerun after integration.

Only the full-page background and official SDK film-strip/button assets are active. Separate LCD/card overlays, custom tab images, Q-Link badges, and changing per-control state art remain reference components because `ui.json` cannot bind them dynamically. The actual generated skin has not been rendered on a physical Force; it follows the concept's industrial palette and layout within the SDK's supported background and native widget model.
