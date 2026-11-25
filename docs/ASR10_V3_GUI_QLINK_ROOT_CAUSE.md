# V3 GUI and Q-Link independent investigation

**Status: FAIL for physical usability based on the user's V3 hardware report; source-level causes independently confirmed. Physical events were not independently recorded in this investigation.** The active V3 plugin was not modified and no device write, service restart, or MPC restart was performed.

## Root causes

### 1. Q-Link assignments outlive effect-specific widgets — confirmed in source

V3 has 19 dynamic factory controls, split across EDIT (indices 8–23, 16 controls) and EDIT 2 (indices 24–26, 3 controls). Each widget is conditionally enabled using an `IndexedEnabling/<slot>/50/Parameter 0` invalidation handle in generated `TUI.json`. The four EDIT pages contain control rows only for 13 factory slots; the other 37 slots have no verified editor control.

The SDK generator's `build_qlinks()` assigns every parameter widget in a page to the corresponding Q-Link (`tools/gen_ui.py:705–714`). It does not evaluate the TUI invalidation condition. The resulting V3 `Q-Links.json` therefore keeps all 16 EDIT and 3 EDIT 2 assignments fixed while effect changes hide controls belonging to other effects. Our independent inspection reports 19 `STATIC_QLINK_CONDITIONAL_WIDGET` findings. This explains how the physical Q-Link can retain an unrelated parameter assignment when its visible control is hidden. The exact MPC label/physical response still needs a Force event trace.

There are no duplicate parameter indices within EDIT or EDIT 2 in the generated mappings. The repeated host-control assignments on BROWSE and MIX are intentional page reuse. The defect is the absent coupling between effect-dependent visibility and Q-Link assignment, rather than a duplicate index inside one page.

### 2. Host parameter acceptance is not DSP write proof — confirmed gap in existing evidence

The binary-bound harness invokes VST `setParameter`, then checks the host value and display string (`tests/force_vst_binary_audio_test.cpp:86–101`). It does not observe an accepted parameter event inside the plugin, the active slot's internal parameter value, the scheduled register group, or the actual register state after scheduling. Its report therefore cannot establish the full physical Q-Link-to-DSP path.

The plugin consumes editor choices on the audio thread. `applyVerifiedControls()` skips controls whose registered slot is not active (`ASR10FXCollection.cpp:209–225`), then asks the backend to set a verified value. The backend rejects non-active slots, requires a ready package, resolves the parameter descriptor, and schedules it (`ES5510DSPBackend.cpp:87–101`). Thus a stale hidden Q-Link can change its host parameter value without producing a DSP write for the currently selected effect.

### 3. `UNCHANGED` is an intentional no-write sentinel — confirmed in source

For supported controls the choice list begins with `UNCHANGED` (`ASR10FXCollection.cpp:82–90`). Selecting choice zero records the sentinel and deliberately skips the write; the source comment says it is not a factory reset/default (`:214–219`). A display reading `UNCHANGED` is therefore expected at initialization and must not be reported as an event failure by itself. QA must separately verify that selecting a supported point schedules the correct register group and that selecting `UNCHANGED` causes no write.

### 4. Text is likely to exceed its widget bounds — independent static warning

The BROWSE page puts four long static strings in 278×107 cells at 30 px font size (`ui.json:13–51`; generated bounds are in `TUI.json`). MIX also has long static text. The static width heuristic flags seven strings as likely to overflow their 278 px widget bounds. It is not an SDK font renderer and cannot prove the physical pixel collision; the generated approximate previews are provided only to make placement review easier. The user-reported touchscreen overlap is consistent with this source/layout risk.

### 5. Verified controls cover only a small portion of the catalog

The catalog has 594 manual-listed parameter entries across 50 effects. V3 registers 19 verified discrete controls for 13 effects; 37 slots have zero such controls. Catalog entries are documentation, not controls. The coverage matrix deliberately counts only promoted register-mapped controls as an observed lower bound and marks all physical operation NOT TESTED. V2's public report says 10/16 controls changed the chosen audio window, but does not identify those ten per control; the machine matrix does not guess. V3 explicitly reports an audio difference for PITCH SHIFT QUALITY; two other new mappings were bit-identical in their selected window.

## Why previous gates missed this

The SDK validator checks skin schema, handles in parameter range, tab/Q-Link structure and referenced images (`AkaiForceSDK/tools/validate.py:433–536`). Those checks do not compare conditional widget visibility to Q-Link mappings, estimate static text overflow, emulate the Force UI, or dispatch physical Q-Link events. The SDK host simulator and QEMU/audio tests establish plugin/package and DSP behavior; they do not simulate a touchscreen or Q-Link surface. Passing those gates was not evidence of a usable hardware editor.

The independent generated skin has four tabs and all referenced files present. The inspector found no out-of-bounds top-level controls or invalid Q-Link parameter indices. It found 19 conditional/static Q-Link mismatches, seven likely text overflows and one unreferenced skin file. The exact findings are in `qa-v3/skin-inspection.json`; four approximate layouts are in `qa-v3/approx-preview/`. No genuine SDK/Force screenshot renderer was available.

## Installed artifact identity

Read-only SHA-256 checks on the Force matched the V3 worktree for the ARMv7 binary and skin resources:

| Artifact | SHA-256 |
|---|---|
| Installed ARMv7 binary | `18b5272b5c0b5656bb1f81a24d81490b0283b5c7a4397142375595685d0f771c` |
| `TUI.json` | `f1eabe4a06ca1ce5119269531470a8f6511026819c0d2c6b1670afa8271c328e` |
| `Q-Links.json` | `e1d28fb7fa87126ea3a0054f35a4817706e1c21438bf56ec60931b4a76435ffe` |
| `panel_background.png` | `b33d76620163911169fc71a4006d56c7085e33b7eb8c4e2f5067ecd29a834d1d` |

The installed package's release manifest identifies source commit `a9c0255e628eb82516c7ac192a83361afaec656e`. The full V1 rollback at `/media/SSD250g/TROLLfx/ASR10/rollback-v1-20261125/` was not accessed or altered by this task. Private package assets, captures and audio remain off Git.

## Remaining independent evidence needed

- Force-side event trace linking physical Q-Link/page/bank to VST parameter event, internal parameter state and actual ordered DSP register writes.
- Per-control unrelated-state invariance, reverse restoration, repeated-value behavior, unavailable-control behavior and save/reload behavior from that same binary-bound trace.
- Genuine Force screenshots or captured screen renders for BROWSE, MIX, EDIT and EDIT 2, including effect changes.
- V4 candidate branch/commit and exact binary/package hashes. V4 comparison is pending publication.
- Physical per-effect and CPU/audio-glitch testing. Existing V1 CPU snapshot is only a comparison baseline, not a V3 result.
