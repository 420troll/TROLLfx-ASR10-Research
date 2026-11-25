# ASR-10 Force Effect-Dependent Editor V4.1

## SDK investigation

Inspected the installed Akai/InMusic SDK source at `/mnt/c/Users/Gamer/research/AkaiForceSDK`, commit `4521c247a2deae30efb9e93d53fc8f9390c51e81` (checked 2026-11-25). The SDK repository has an unrelated modified Python bytecode file; no SDK files were changed.

| Capability | SDK finding | V4.1 consequence |
|---|---|---|
| Dynamic tab visibility | No tab visibility predicate or plugin callback exists in `ui.json`, `gen_ui.py`, `mpc_plugin.h`, or the validator. Tabs are generated from a fixed array. | Use three fixed tabs: BROWSE, EDIT, MIX. |
| Dynamic page selection | No page-selection callback or tab API is exposed to plugins. `gen_ui.py` assigns fixed function-key indices. | Effect selection changes routing inside the plugin; the EDIT tab remains in the same place. |
| Dynamic parameter names | `effGetParamName` returns the stored `Param::name`. `formatValue()` changes the value string only. `requestDisplayUpdate()` asks the host to refresh; it does not provide a replacement name. | The permanent parameter names are `EDIT SLOT 1` through `EDIT SLOT 8`. The formatted value includes the active factory label and verified value, such as `DECAY TIME: 41`. This is the closest stock-SDK presentation; true dynamic parameter/Q-Link names are not available. |
| Dynamic Q-Link map | `gen_ui.py` builds one fixed map per tab from static parameter references. There is no plugin callback for replacing it. | EDIT Q1–Q8 always point to eight appended routing parameters. The plugin dispatches each changed slot to the selected effect's corresponding verified control. Missing slots are hidden and ignored. |
| Fixed EDIT page with effect-dependent routing | Supported by ordinary VST parameter callbacks and plugin code. | Implemented. Per-effect V4 parameters remain canonical and retain their existing IDs/indices; the router parameters are appended. |
| Custom tab/control handler | No touchscreen event or custom tab interface is exposed. | No SDK or firmware behavior is inferred from accepting generated JSON. |

Evidence sources: SDK `framework/mpc_plugin.h` (`parameterChanged`, `formatValue`, `requestDisplayUpdate`, `effGetParamName`), `tools/gen_ui.py` (`MAX_PAGES`, control parsing, tab construction and `build_qlinks`), and `tools/validate.py` (static tab and map validation). The SDK host simulator exercises VST parameter/state/audio behavior, not the Force touchscreen renderer. The generator warns that tabs beyond six function keys have not been verified on the device; V4.1 uses three.

## Hall/Room prototype and implementation

The Hall/Room prototype uses one shared EDIT workspace. HALL REVERB exposes four active slots: Q1 BUS1, Q2 BUS2, Q3 DECAY TIME, Q4 HI FREQ DAMPING. ROOM REVERB exposes three: Q1 DECAY TIME, Q2 DIFFUSION, Q3 HI FREQ DAMPING. Selecting a different effect updates the slot value, formatted label, and per-slot visibility. The underlying stored parameter is still the effect-qualified V4 control. Register writes are scheduled only for the selected and active effect and only at a recorded verified point.

The same router serves all 50 factory slots. The registry remains at 594 documented descriptors, while the UI binds only the 19 runtime-ready mappings. Slots with no mapping have no visible EDIT knobs; they cannot write DSP registers. The first eight mappings for any effect use Q1–Q8. If a future effect has more than eight verified mappings, the EDIT BANK selector appears for that effect and selects the next eight-control bank on the same EDIT page. No current effect needs another bank.

All existing V1–V4 parameter IDs and indices 0–45 are unchanged. V4.1 appends routing parameters at 46–53, EDIT BANK at 54, availability flags at 55–63. The effect-qualified V4 parameters remain the source of truth in saved project state. When the selected effect changes, router values mirror that effect's stored settings; a Q-Link move updates the selected effect's existing parameter and enters the same verified register-write path. The V1 rollback files and package are not changed.

The EDIT page uses the existing Ensoniq-style cyan panel, a single heading, eight evenly placed knob widgets, and a conditional bank selector. Each grid cell has at most one widget; empty cells do not carry decorative text or controls. BROWSE and MIX use one short header each with bottom-row host controls.

### Current control-mapping matrix

| Factory slot | Effect | Visible EDIT controls / active Q-Links |
|---:|---|---|
| 01 | HALL REVERB | Q1 BUS1, Q2 BUS2, Q3 DECAY TIME, Q4 HI FREQ DAMPING |
| 02 | 44KHZ REVERB | Q1 BUS1, Q2 BUS2 |
| 03 | ROOM REVERB | Q1 DECAY TIME, Q2 DIFFUSION, Q3 HI FREQ DAMPING |
| 04 | DUAL DELAYS | Q1 BS1 TIME L |
| 05 | 44KHZ DELAYS | Q1 BS1 TIME L |
| 06 | CHORUS+REVRB | Q1 CHORUS RATE |
| 07 | PHASER+REVRB | Q1 PHASE RATE |
| 08 | FLANGER+REV | Q1 FLANGE RATE |
| 28 | GUITAR AMP1 | Q1 PREAMP GAIN |
| 39 | PITCH SHIFT | Q1 QUALITY |
| 41 | FAST PITCHSH | Q1 VOICE1 FINE |
| 42 | EQ+CMPRESSOR | Q1 COMP RATIO |
| 49 | PARAM EQ | Q1 BASS FC |

All other slots expose no EDIT knobs. Static EDIT Q1–Q8 indices are 46–53; Q9 index 54 selects an additional bank only when the selected effect has more than eight runtime-ready controls. The present 19-control registry has no such effect. Q10–Q16 are unmapped on EDIT.

## Verification evidence

Commands run for the implementation are recorded in the V4.1 handoff after build. Evidence must be interpreted in these scopes:

- **SDK JSON validation:** proves generated pages, parameter handles, widget geometry and static Q-Link indices are valid SDK artifacts. It does not prove dynamic visibility or physical Q-Link routing.
- **SDK host simulator:** proves the packaged VST loads, parameter values format, state chunks restore, and audio remains finite under host parameter changes. It does not render TUI screens or simulate Force Q-Link hardware.
- **Native wrapper/register tests:** prove Hall and Room routing selects the intended existing parameter, preserves the other effect's value, and reaches the validated register-write path in the native test runtime.
- **ARMv7 tests:** prove the built binary architecture and, when QEMU is available, run the ARM wrapper test under emulation. They do not prove touchscreen appearance or Force firmware behavior.
- **Physical Force verification still required:** confirm conditional slot visibility, value text legibility in the knob and Q-Link overlays, Q1–Q8 dispatch after effect changes, EDIT BANK behavior when a future effect exceeds eight controls, and project save/recall. No installation is authorized or performed.

V4.1 verification completed on 2026-11-25:

- `python3 tools/parameter_controls/build_editor_v04.py --check` — PASS; registry remains 50 effects, 594 documented descriptors, 19 runtime-ready mappings.
- `python3 tests/parameter_controls/test_editor_v04.py` and `python3 force_plugin/tools/test_catalog.py` — PASS; generated editor has exactly BROWSE / EDIT / MIX and one fixed EDIT Q-Link map.
- `AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK python3 force_plugin/tests/test_release_infrastructure.py -v` — PASS, 5/5 tests.
- `AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK force_plugin/tools/test_es5510_backend.sh` — PASS; strict HALL/ROM-02 backend checks, 50-slot asset import, HALL Q3 decay and ROOM Q1 decay register paths, distinct native renders, and state isolation. Output: HALL energy `406.486234`, HALL Q3 comparison delta `350.638062`; ROOM energy `279.894178`, ROOM Q1 comparison delta `199.423004`.
- `AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK python3 force_plugin/tools/build_release.py --sdk /mnt/c/Users/Gamer/research/AkaiForceSDK --toolchain auto --no-zip` — PASS; native, ARMv7 hard-float and ARM64 builds, packaged VST tests, SDK-generated skin and validator (0 errors, 0 warnings), 3 tabs, and 50 package binary/audio checks. The SDK host simulator passed; it does not render the touchscreen skin.
- `force_plugin/tools/test_arm32_vst_qemu.py` — PASS, all 50 slots, 19 verified mappings, HALL/ROOM routing, state isolation and finite stereo output under `qemu-arm 8.2.2`. The machine-readable result is [ASR10_FORCE_DYNAMIC_EDITOR_V41_ARMV7_QEMU.json](ASR10_FORCE_DYNAMIC_EDITOR_V41_ARMV7_QEMU.json); ARM32 digest matches the packaged candidate.

## Codex 3 handoff

Branch: `feature/asr10-force-effect-dependent-editor-v4.1`. Generated skin artifacts are in `force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/Plugin Skins/`: `TUI.json`, `Q-Links.json`, the retro panel background, and SDK widget film strips. The source UI is `force_plugin/ui.json`; the matrix above is the control map.

### QA instructions

1. Use a Force test unit only after a separate deployment authorization. This work did not install or copy a package to a Force.
2. Open the VST and check that the only tabs are BROWSE, EDIT, and MIX. Confirm BROWSE selects the effect and EDIT remains the shared workspace.
3. Select HALL REVERB. Verify four controls only, in Q order: BUS1, BUS2, DECAY TIME, HI FREQ DAMPING. Turn Q3 between its two verified points and confirm the displayed value changes from 40 to 41.
4. Select ROOM REVERB. Verify three controls only: DECAY TIME, DIFFUSION, HI FREQ DAMPING. Confirm Q1 edits ROOM decay (64/65), Q2 edits diffusion (50/51), and the formatted label follows each slot.
5. Switch HALL → ROOM → HALL. Confirm each effect retains its own choices and no HALL Q-Link edits a ROOM register after selection. Save and reopen a project, then repeat the checks.
6. Select an effect with no verified mappings, such as slot 09. Confirm the EDIT knobs disappear and turning unused Q-Links produces no DSP parameter writes.
7. Capture the Force model/firmware, editor screenshots for HALL, ROOM and an unmapped effect, Q-Link behavior, and project recall outcome. Treat clipped/stale labels, visible unused knobs, wrong-effect writes, or state crossover as a failure.

No current effect has more than eight controls, so the additional-bank control has native routing/count unit coverage but has no real factory mapping for physical QA yet.

## Remaining SDK limitation

V4.1 removes navigation through thirteen unrelated EDIT tabs and routes Q1–Q8 to the selected effect's controls. The fixed SDK map still names the generic router parameters, and unused physical Q-Links remain bound to hidden generic slots because the SDK cannot replace a Q-Link map dynamically. The factory parameter label is shown in formatted value text rather than the parameter-name field. If Force firmware does not refresh conditional visibility/value text after `requestDisplayUpdate()`, the stock SDK offers no callback to repair that behavior. This implementation is therefore a tested plugin-side routing alternative, not a claim that the SDK supports genuinely dynamic tabs, parameter names, or Q-Link maps.
