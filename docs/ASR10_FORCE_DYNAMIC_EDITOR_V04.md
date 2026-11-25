# TROLLfx ASR-10 Dynamic Factory Editor V4

## Current scope

V4 builds the per-effect editor from the existing 19 directly verified controls. It does not wait for Codex 1's broader OS sweep and does not infer additional DSP mappings. The generated registry contains all 50 effect slots and 594 documented manual parameter descriptors. The 19 writable controls span 13 effects; the other 37 slots continue to load and process without editable factory controls.

The three ROM-02 reverb controls carried forward from V2 remain historical verified mappings. V4 adds no new ROM-02 research. Newly discovered controls can be appended to the registry and receive a unique parameter ID and a static effect-specific page without changing the existing GUI model.

## Parameter evidence model

`docs/ASR10_FACTORY_EDITOR_REGISTRY_V04.json` is the generated machine-readable registry. Each documented parameter has separate evidence flags:

- `DOCUMENTED`: present in the manual-derived 594-row catalog.
- `OS_OBSERVED`: label/value observed in the OS editor.
- `REGISTER_VERIFIED`: a controlled OS adjustment produced a repeatable ordered register-write mapping.
- `AUDIO_VERIFIED`: an isolated audio comparison established the parameter's behavior. This remains false unless that evidence exists for the individual control.
- `RUNTIME_READY`: an explicit point is accepted by the native runtime adapter.

Verified live display ranges remain separate from `verified_points`. A display range such as 0–99 does not define intermediate register values. The runtime offers only the recorded points, never an interpolated curve. `compound_row_id` and `subfield` preserve paired row metadata where identifiable; parameter entries remain separately represented.

## Host IDs and Q-Link architecture

All V1/V2/V3 plugin parameters and indices 0–26 are unchanged. V4 appends 19 uniquely identified parameters at indices 27–45 (`factory_v4_slotN_<parameter-id>`). Their SDK-visible names retain the original label and add an effect-slot suffix (for example, `DECAY TIME (HALL) @ 01`) because `ui.json` binds by the SDK parameter name, not by VST ID. Each appended choice exposes the observed display text and value points for one effect. Its setting is persisted by the host using the normal parameter state/chunk mechanism and is isolated from the same-named control on another effect.

The SDK generator `tools/gen_ui.py` derives a fixed Q-Link map from the parameter cells on each tab. It does not apply `visibleWhen` to the Q-Link map, and the plugin SDK has no dynamic parameter-name or dynamic Q-Link-assignment callback. V3 placed parameters for many effects on the same EDIT page; therefore the physical map continued targeting controls hidden by `visibleWhen`, and parameter names stayed fixed. This explains irrelevant/stale assignments even when the touch view hid a control.

V4 gives each of the 13 editable effects its own tab. Each tab's Q1–Q8 positions are static and refer only to that effect's parameters; unused Q-Links are generated as `-1`. Q1–Q4 occupy the lower grid row and Q5–Q8 the row above. BROWSE and MIX keep the established fixed host parameters. This avoids reusing parameter identities when the selected effect changes. Controls on a page have the factory label and only verified point values.

The prior V3 choice parameters retained the literal `UNCHANGED` sentinel ahead of two verified points. A three-choice mapping has larger normalized detents, so small physical movements can remain on that sentinel. V4 retains those old IDs for old-project compatibility but removes them from the skin. Appended V4 parameters contain only actual verified choices. The host's `parameterChanged` callback sets an atomic pending flag; the audio thread consumes the flag and issues the bounded verified write only for the matching active effect. No UI-thread call writes DSP state directly. On package switching, each effect keeps its own host parameter values.

## SDK and visual audit

Inspected SDK sources: `framework/mpc_plugin.h`, `tools/gen_ui.py`, and `tools/validate.py` from `/mnt/c/Users/Gamer/research/AkaiForceSDK`.

- SDK `ui.json` permits 16 grid controls per page and the validator permits up to 32 tabs.
- The generator assigns tabs to function-key indices and emits one Q-Link map per tab. Its implementation supports static parameter indices only.
- The SDK host calls `Plugin::setNormalised()` for VST `setParameter`, then `parameterChanged(index, plain)`. Chunk restoration also goes through parameter setters.
- `formatValue()` can update value text, not a parameter's static name. `visibleWhen` only gates display.
- The approved 1280×628 panel background has the wordmark/header and 16 empty recessed wells; it contains no baked parameter labels or decorative knobs. SDK widgets draw over the wells. V3's overlapping controls came from dense text/native widget placement and sharing an EDIT tab across unrelated effect controls, not duplicate knob art in the background.
- The SDK checkout has a TUI generator and host audio simulator, but no touchscreen skin renderer. No screenshot is claimed as a real Force render. Generated `TUI.json`/`Q-Links.json` are the actual SDK artifacts and are validated by the SDK.

The original Force has six physical function keys. The SDK validates 15 pages and assigns them to 15 function-key indices, but neither its source nor host simulator verifies how the Force navigates beyond six pages. Therefore access to all 15 tabs on physical hardware remains an explicit hardware QA item. V4 is not to be installed until independent release QA verifies tab navigation and Q-Link behavior on the Force. This is the SDK capability limit that prevents a truthful claim of hardware-ready navigation.

## Coverage matrix

| Effect slot | Q-Link controls | Runtime mapping status |
|---|---|---|
| 01 HALL REVERB | BUS1, BUS2, DECAY TIME, HI FREQ DAMPING | 4 verified points each; ranges remain separate evidence |
| 02 44KHZ REVERB | BUS1, BUS2 | preserved V2 mapping; no V4 research |
| 03 ROOM REVERB | DECAY TIME, DIFFUSION, HI FREQ DAMPING | verified points; three documented display ranges stay separate |
| 04 DUAL DELAYS | BS1 TIME L | two verified points |
| 05 44KHZ DELAYS | BS1 TIME L | two verified points |
| 06 CHORUS+REVRB | CHORUS RATE | two verified points |
| 07 PHASER+REVRB | PHASE RATE | two verified points |
| 08 FLANGER+REV | FLANGE RATE | two verified points |
| 28 GUITAR AMP1 | PREAMP GAIN | two verified points |
| 39 PITCH SHIFT | QUALITY | two verified discrete choices |
| 41 FAST PITCHSH | VOICE1 FINE | two verified signed values |
| 42 EQ+CMPRESSOR | COMP RATIO | two verified discrete choices |
| 49 PARAM EQ | BASS FC | two verified points |

All other effect slots retain their original package selection and audio path; their factory editor mappings remain unavailable until independently verified. Effect package availability still comes only from the validated provider.

## Tests and rebuild

Run the focused metadata and generated-file checks:

```sh
python3 tools/parameter_controls/build_editor_v04.py --check
python3 tests/parameter_controls/test_editor_v04.py
AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK python3 force_plugin/tools/build_release.py --no-zip
```

The release build stages the source and data, runs strict HALL/ROM-02 package validation, native backend and wrapper audio tests, builds native/ARMv7/ARM64 binaries, invokes the official SDK skin generation and validation, exercises the packaged native VST through the SDK host simulator against all 50 local validated packages, and writes a refreshed manifest/checksum set plus `binary-validation-report.json`. The ARMv7 binary is ELF-validated and its digest is bound into binary-bound test evidence; QEMU execution is a separate script and is not part of the current release command. Private checkpoints and generated render data remain outside the repository.

Focused runtime test: `force_plugin/tools/test_es5510_backend.sh`. This test compiles a native VST wrapper with isolated validated HALL and ROM-02 packages. It checks V4's Hall decay parameter changes output against a default instance and checks the existing callback allocation guard.

## Limitations and QA handoff

- The Force SDK's static parameter names mean the effect number is shown in the static tab label, while the original parameter label/value is shown by each native widget. There is no supported dynamic LCD overlay or Q-Link renaming.
- Fifteen tabs are within the SDK JSON limit, but navigation beyond six function keys is unverified on physical Force hardware. QA must confirm a usable way to reach every effect page before declaring the full per-effect editor operational.
- The headless SDK does not render touchscreen screenshots. Check generated TUI geometry/parameters and verify the 1280×628 appearance on the actual Force.
- Physical Q-Link dispatch, touchscreen label clipping, state recall in a saved Force project, and editor navigation require hardware QA. Native VST and SDK tests cannot prove those device behaviors.
- Controls with only two observed points remain two-position controls; no continuous DSP values between them are claimed.

The implementation preserves the existing DSP arithmetic, package validator/provider, factory assets, 5 ms effect switching, and V1 rollback. It does not install or replace any Force plugin.
