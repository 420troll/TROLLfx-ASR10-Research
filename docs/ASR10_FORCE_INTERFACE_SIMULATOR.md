# TROLLfx ASR-10 PC Force Interface Simulator

The simulator previews the V4.1 generated Akai skin and drives the plugin's **actual native VST2 entry point**. It is for fast PC layout and control iteration. It does not emulate MPC/Force firmware or prove hardware behavior.

## Launch

From the `feature/asr10-force-effect-dependent-editor-v4.1` worktree:

```sh
python3 tools/force_simulator/launch.py
```

The launcher builds a desktop-only, test-instrumented VST in `~/.cache/trollfx-asr10-force-simulator/` and serves `http://127.0.0.1:8765`. Open that URL in a Windows browser when running under WSL. The default SDK discovery includes `/mnt/c/Users/Gamer/research/AkaiForceSDK`; override with `AKAI_FORCE_SDK` or `--sdk`.

The plugin's existing trusted local provider is required. By default it looks for `~/asr10-force-assets-v1/provider-index.tsv`. Set `TROLLFX_FACTORY_PACKAGES_DIR` or use `--assets /path/to/local/provider-root` to choose another provider root. The root is checked before the VST is loaded. The provider performs its normal package validation during plugin initialization. No packages are copied into this worktree or simulator cache.

For repeatable automated checks:

```sh
TROLLFX_FACTORY_PACKAGES_DIR="$HOME/asr10-force-assets-v1" \
  python3 -m unittest discover -s tools/force_simulator/tests -v
```

To refresh the committed UI-only previews and redacted evidence after changing the generated skin:

```sh
TROLLFX_FACTORY_PACKAGES_DIR="$HOME/asr10-force-assets-v1" python3 tools/force_simulator/capture_screenshots.py
TROLLFX_FACTORY_PACKAGES_DIR="$HOME/asr10-force-assets-v1" python3 tools/force_simulator/generate_evidence.py
```

## What it exercises

- It parses the checked-in generated `Plugin Skins/TUI.json`, `Q-Links.json`, and referenced PNG files. The pages use the generated 1280 × 628 logical coordinate system and the actual page order.
- The browser reads parameter indices and Q-Link indices from those files. Touch gestures call VST `setParameter`; the eight rotary controls call the same API using the current generated EDIT Q-Link map.
- The VST is loaded using its exported `VSTPluginMain` entry point. The host invokes its real dispatcher, `getParameter`, `setParameter`, `processReplacing`, `effGetChunk`, and `effSetChunk` methods.
- The audio tool accepts stereo PCM WAV at 48 kHz, processes it through the plugin in configurable host blocks, and offers wet and VST-bypass output WAVs.
- Page changes and parameter changes are recorded in a JSONL audit log. Parameter events include the active effect, page, physical-equivalent Q-Link, host VST parameter index and normalized value, plugin parameter text, resolved canonical control, and the GPR writes observed at the runtime's GPR-port write site. A verified control write group is identified only when its ordered register group appears at one DSP frame. These logs can contain factory state details and are kept only in the user's cache directory.
- An optional compile-time-only, fixed-size atomic trace ring is enabled for the desktop test binary. The release/Force build does not define `TROLLFX_SIMULATOR_TRACE`; this adds no release behavior and does not change DSP arithmetic.

The A/B tool runs bypass and wet passes through one advancing plugin instance. It is an audible comparison, not a same-state null test. Neither pass is normalized. WAV output conversion is PCM16 and clamps to that format's range.

## Preview fidelity and visible findings

The screenshots in [`docs/force_simulator/screenshots`](force_simulator/screenshots/) are rendered from the generated V4.1 TUI and its actual PNG artwork. Pillow and the browser canvas renderer use the TUI coordinates, font names/sizes, labels, parameter display strings, knob filmstrip frames, button art, and Q-Link map. They are genuine previews of the generated skin assets, not captures of the Force renderer. The plugin page is the SDK's 1280 × 628 tab content area within its documented 1280 × 800 display, starting 110 pixels below the top edge. The outer host/status region is intentionally omitted instead of replaced with guessed hardware chrome.

Known differences and limitations:

- The TUI defines no custom `Slider` track/thumb artwork. The desktop renderer draws a clearly marked approximate slider. The plugin's actual SDK slider remains native on the Force.
- Font rasterization, SDK/host widget styling, touch focus, overlays/menu behavior, display scaling, and clipping may differ on hardware.
- Knob rotation and touchscreen gestures approximate host gestures; the simulator translates them into VST parameter calls and does not reproduce encoder acceleration, hardware focus, or event timing.
- The desktop host has no MPC automation/transport/session manager and cannot prove project compatibility beyond the plugin's own state chunk.
- Wet/bypass comparison is sequential and uses evolving DSP state.
- The current EDIT page has generic parameter names `EDIT SLOT 1` through `EDIT SLOT 8` in `effGetParamName`. The plugin supplies effect-dependent text using its value-display callback. Whether MPC/Force refreshes the displayed Q-Link labels on FX Slot changes, or sends the expected 46–53 parameter events from its physical encoders, requires a device test.

The generated TUI now uses a compact text profile: 20 px page headings, 18 px control names, and 15 px values, with the value column widened within the existing knob cell. The title strings are concise. The SDK-generated control positions, parameter indices, and Q-Link maps are unchanged. The screenshot/layout report should show no clipping or label/widget overlap warnings. Empty card artwork and disabled EDIT slots remain part of the generated skin and are not simulator-created controls.

After installing the simulator's npm development dependencies, run `npm run test:browser` from `tools/force_simulator/`. Playwright uses real browser mouse input to verify all three tabs, HALL/ROOM selection, HALL Q3 and ROOM Q1 rotations, and their native VST event/register traces. Browser automation is desktop evidence only and does not emulate Force firmware.

## Independent native evidence

[`verification-report.json`](force_simulator/verification-report.json) records hashes of the V4.1 skin and screenshot outputs, plus the redacted focused test results. Its `tested_q_link_dsp_routes` section lists the physical-equivalent EDIT Q-Link, actual VST parameter index, canonical control resolved from the C++ registry, and observed same-frame GPR group for each tested route. Raw GPR values and per-event logs stay outside Git. At the captured run the local provider reported 50/50 packages validated, but this task's runtime coverage is focused on HALL (slot 1), ROOM REVERB (slot 3), PITCH SHIFT (slot 39), and an effect with no verified controls.

Eight focused native integration tests and four Playwright browser interaction tests passed. They exercise the actual plugin callback; HALL → ROOM → PITCH SHIFT → HALL routing; verified same-frame GPR groups; no change to unrelated HALL controls; state save/restore to the discrete canonical value; `NO VERIFIED CONTROL` behavior; finite wet audio; stereo 48 kHz WAV output; page navigation; effect selection; mouse-operated HALL Q3 and ROOM Q1; and audit event logging. Register values, firmware payloads, audio files, checkpoints, provider files, and detailed event logs are excluded from Git; raw test logs remain local.

This proves that these host parameter updates can reach the runtime and apply verified DSP writes under the desktop VST host. It does **not** prove an encoder on the Force invokes the same VST parameter index.

## Physical Q-Link investigation

V4.1's generated EDIT map binds Q1–Q8 to VST indices 46–53. The VST source keeps those names static (`EDIT SLOT n`) and provides effect-specific control names/values through the parameter display callback and router. The desktop VST host test directly setting those indices results in the expected control route and applied GPR group. Unmapped effects show `NO VERIFIED CONTROL` and the processor has no route for that selection.

Therefore, the tested plugin-side route is not the cause of a failed desktop VST `setParameter` → DSP path. The remaining physical failure boundary is host integration: MPC/Force Q-Link map activation/dispatch, whether it writes indices 46–53 on the active screen, and what label/display callbacks it refreshes after FX Slot changes. Static names may make the control's identity appear stale, but do not alone explain a missing DSP write. No device event trace was available in this task, so the physical root cause remains **unresolved**, not attributed to the plugin or host.

A useful next device diagnostic would capture the displayed Q-Link assignment/value before and after switching effects and observe whether a physical rotation changes the displayed value. If the value changes, collect a plugin-side parameter trace while audio is running; if it does not, compare the installed `Q-Links.json` hash and active page/map behavior. This is a future read-only diagnostic suggestion only; this task did not connect to or modify the Force.

## Third-party code and assets

No source from the examined projects was copied into the simulator. The approach was informed by:

- [inMusic MPC Plugin Builder SDK](https://github.com/inmusic-software/mpc-plugin-builder-sdk) — MIT SDK, used by the existing plugin build.
- [open-mpc/mpc-vst-plugins](https://github.com/open-mpc/mpc-vst-plugins) — MIT Skin Studio and desktop preview conventions.
- [jacob-sabella/mpc-addin-commander](https://github.com/jacob-sabella/mpc-addin-commander) — MIT project; its Titillium Web font files are included under their separate SIL OFL 1.1 license. See [`NOTICE.txt`](../tools/force_simulator/fonts/NOTICE.txt) and [`OFL.txt`](../tools/force_simulator/fonts/OFL.txt).

The simulator itself uses Python standard library, Pillow, a small browser UI, and the already available native compiler/SDK. It does not install add-ins or connect to the hardware.
