# ASR-10 full-parameter PC editor

The PC simulator builds a per-effect editor model from the 594-entry V1 factory parameter catalog, the V04 OS-observation inventory, V05 DSP mapping evidence, and the append-only VST control registry in `include/trollfx/es5510_factory_editor_v04.hpp`. It preserves all 594 catalog descriptors and supplements six exact runtime controls omitted from that catalog, for 600 editor controls and all 19 current VST routes. The GUI has no HALL/ROOM-specific control table. Each effect's ordered parameters are split into banks of eight virtual PC Q-Links.

## Original ranges and DSP support

The displayed original range is separate from implemented DSP support. Numeric ranges and observed enumerations are inspectable, but they do not authorize DSP writes. An edit is sent to the native VST only when its value exactly matches an existing effect-qualified VST registry point. The GUI does not interpolate register values.

- **VERIFIED** means the current native VST route covers the complete documented domain. The present routes generally have only two recovered points, so they remain PARTIAL.
- **PARTIAL** means the exact supported points or a Codex 1 `runtime_ready` mapping cover less than the full editor range. A recovered audio mapping that has not been connected to a VST parameter is labelled as pending integration and is not sent to an unrelated route.
- **UNMAPPED** means no runtime mapping is available. The control remains an editor inspection/draft only.

HALL REVERB DECAY TIME displays the documented integer range 0–99. The existing VST route has exact values 40 and 41. Those values route through its existing stable VST identity and produce the existing runtime register trace; an edit such as 42 changes the PC draft only and produces no DSP write. Labels and values in the trace identify the selected factory effect, original editor value, normalized VST value (when sent), host parameter index, canonical parameter identity, applied runtime writes and trace/group verification.

Discrete and enumerated controls use values actually observed in the OS inventory or exact verified VST display points. A manual description alone is not expanded into guessed choices. The GUI accepts explicit `display_scale_curve` metadata as normalized/display-value pairs to shape the slider and Q-Link gesture. No curve is inferred from current ranges. For controls without that evidence, the PC slider operates in displayed editor units and only exact known VST points are writable; it does not imply or fabricate an editor-to-GPR conversion. Documented range variants remain visible alongside the primary range.

## State and stable IDs

Per-effect inspection drafts remain in the simulator while switching among effects. The native plugin's existing 64 parameter identities, append-only VST IDs and chunk compatibility are unchanged. The new PC-only draft values are not serialized in the VST chunk; VST-supported parameter values continue to use the plugin's existing state mechanism.

The registry loader is data-driven. New catalog controls render with their metadata and status without GUI-specific effect code. A control becomes writable only after a corresponding verified control is present in the native VST registry/host route. Codex 1's mapping data by itself does not extend the current host parameter surface. The [capability matrix](force_simulator/factory-control-mapping-matrix.csv) lists per-effect descriptor counts, runtime additions, PC banks, current native routes and exact values.

## PC and physical Force boundaries

The PC editor can immediately assign its virtual Q1–Q8 controls to the selected effect and visible bank. The plugin source defines eight routed edit slots and an EDIT BANK parameter. This demonstrates plugin-side routing, not dynamic hardware Q-Link relabeling. The stock SDK skin retains its fixed page and Q-Link definitions; the PC-only editor is a flexible host UI. Physical Force label refresh, Q-Link reassignment/dispatch and bank interaction still require device verification. Nothing was installed to the Force.

## Screenshots

- [HALL REVERB, bank 1](force_simulator/screenshots/pc-editor-hall-bank-1.png)
- [ROOM REVERB, bank 1](force_simulator/screenshots/pc-editor-room-bank-1.png)
- [PITCH SHIFT, bank 1](force_simulator/screenshots/pc-editor-pitch-bank-1.png)
- [PITCH SHIFT, bank 2](force_simulator/screenshots/pc-editor-pitch-bank-2.png)

## QA

From `tools/force_simulator/`:

```sh
TROLLFX_SIM_PORT=8766 npm run test:browser
python3 -m unittest discover -s tests -v
```

The browser suite uses the actual native VST simulator and local validated factory package root. It covers range display, numeric/enum editing, no-write unsupported values, exact VST routes and register traces, effect draft recall, bank/Q-Link mouse interaction, card overlap and the separate SDK preview. Browser screenshots are generated in `docs/force_simulator/screenshots/`. The Python integration suite includes SDK generated-skin checks, VST routing/state and audio tests; tests requiring private local packages are skipped when those assets are absent.

QA results and screenshot hashes are in [pc-editor-qa-results.json](force_simulator/pc-editor-qa-results.json). This run passed 11 Playwright browser tests, 14 Python tests (8 native VST integration, 4 registry and 2 skin layout), plus SDK catalog checks. The existing ARMv7 QEMU report is PASS and its plugin digest matches the current binary, but QEMU was unavailable to rerun in this session.

The screenshots and tests establish PC simulator behavior only. SDK JSON validation and plugin source do not establish Force host behavior. No package was installed to the Force; physical Q-Link labels, dynamic page visibility and hardware dispatch remain unverified.
