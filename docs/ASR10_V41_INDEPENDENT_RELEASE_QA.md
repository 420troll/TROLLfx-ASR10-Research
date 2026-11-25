# ASR-10 V4.1 Independent Release QA

**Candidate:** `feature/asr10-force-effect-dependent-editor-v4.1`  
**Commit inspected:** `f159cde7daa7ba91b5aac8c93999b6a32835bf3f`  
**Scope:** read-only source/package inspection, SDK build and host/QEMU simulation. No Force install, MPC restart, V3 change, or V1 rollback change was performed.

## Result summary

| Gate | Result | Evidence |
|---|---|---|
| Generated page count and names | **PASS** | Fresh SDK build and packaged `TUI.json`: exactly `BROWSE`, `EDIT`, `MIX` in that order. Three matching static Q-Link tab maps. SDK validator: 0 errors, 0 warnings. |
| Stable EDIT Q-Link bindings | **PASS** | Q1–Q8 map to append-only host parameter indices 46–53; Q9 maps to EDIT BANK index 54. The controls' parameter IDs are appended after prior indices 0–45. |
| Dynamic effect-to-control routing | **PASS (simulated, partial mapping coverage)** | Binary-bound ARMv7 test passed all 50 package slots and the HALL/ROOM dynamic routing assertions. Source trace confirms one router dispatches through the selected effect's verified descriptor. The 19 canonical verified parameter points also passed the packaged binary harness. |
| No accidental cross-effect write | **PASS (source and simulated assertions)** | Router lookup is effect-qualified; the backend requires the same active slot and a validated package; `FactoryRuntime::setParameter` rejects a descriptor whose slot differs from the loaded effect. Unmapped ordinals resolve to null and are consumed without a DSP write. HALL and ROOM state-isolation assertions passed. |
| Requested HALL → ROOM → PITCH SHIFT → HALL route sequence | **NOT_TESTED as a dedicated assertion** | The binary harness visits all 50 slots in order and later returns to HALL; it specifically asserts HALL and ROOM routing, but does not assert the PITCH SHIFT dynamic route or each transition in the requested four-step sequence. |
| Original parameter identity and project state | **PASS (host simulation)** | Existing parameter indices 0–45 remain in their original order; new router params are appended. SDK state chunks serialize parameter IDs and values; the binary-bound state round-trip test restored effect, host values, canonical controls and router values. No host automation collision was found in source or test evidence. |
| Layout bounds, widget duplication and artwork | **PASS with text-fit warning** | Independent generated-skin scan found no out-of-bounds widgets, invalid Q-Link targets, duplicated parameter widgets, or missing artwork. It warns that the two long page headings may exceed their 278 px cell. The scan is an approximate 1280×628 overlay, not Force rendering. |
| SDK layout rendering / physical labels | **NOT_TESTED** | SDK validator and host simulator do not render the Force touchscreen. No physical Force observation was made. |
| ARMv7 ABI/package | **PASS** | Fresh SDK candidate build validated ARMv7 hard-float, required VST symbol and dependencies, GLIBC ≤2.27; package validator reports zero errors/warnings. ARMv7 package SHA-256: `badefa8fa322b812adbf82166d9782e17d770d4453cb06f428b2f9ed98a3cab4`. |
| Binary-bound VST behavior | **PASS in desktop simulation** | Independently rebuilt native SDK VST and ran its packaged-binary harness against 50 validated local packages: 50/50 stereo renders; HALL/ROOM verified-control response; missing-package silence; chunk-state round trip; SDK host simulator WAV; 0 callback allocations. This is not Force hardware validation. |
| Physical Force release readiness | **NOT_TESTED / BLOCKED** | Touchscreen visibility, physical Q-Link dispatch and actual visible labels still require a controlled Force test. Candidate manifest correctly remains `playable: false`. |

## Q-Link name and display behavior

The generated SDK map is static. EDIT Q1–Q8 always target generic VST parameters named `EDIT SLOT 1` … `EDIT SLOT 8`; Q9 is statically mapped to `EDIT BANK` (index 54), but the registry currently has at most four controls per effect, so the bank widget is hidden and runtime selection is clamped to bank 0; the SDK's VST wrapper returns the immutable `Param.name` for `effGetParamName`. V4.1's `formatValue()` computes the active formatted value (`DECAY TIME: 41`, for example) and asks the host to refresh display text. The inspected SDK has `effGetParamDisplay` and `audioMasterUpdateDisplay`, but no callback for renaming a parameter or rewriting a tab's Q-Link map.

Therefore the physical Q-Link *name* should be expected to stay generic when effects change. The name is not effect-specifically wrong, but it does not tell the player which control is active. Whether MPC/Force visibly renders the dynamic value string beside each physical Q-Link is **NOT_TESTED**. Do not describe this as dynamic Q-Link relabeling.

Truthful V0.1 presentation: keep generic `EDIT SLOT n` names; show the current effect and explicit per-slot control/value labels on EDIT; show `NO VERIFIED CONTROL` for empty slots; use only confirmed display text. Before hardware release, confirm that the formatted value is visible during physical Q-Link adjustment. If it is not, add persistent on-screen labels through supported SDK widgets (or fall back to effect-specific fixed pages), rather than claiming Q-Link names change dynamically.

## Host-index → router → verified register-write trace

The physical EDIT map binds Qn to host parameter `45+n` for Q1–Q8 (indices 46–53). `parameterChanged` marks the matching router slot. On the audio thread, `applyRoutedEditSlots()` computes the selected effect's descriptor ordinal, converts the router value to one of that control's discrete points, and sets that control's stable canonical VST parameter. `applyV4Controls()` then calls `ES5510DSPBackend::set_verified_parameter`; that validates active slot/package and delegates to `FactoryRuntime::setParameter`. The runtime schedules the complete verified `ordered_writes` group at the current DSP frame. The register numbers below are the groups used by the corresponding verified descriptor points; register values and private captures are intentionally omitted from this public QA report.

| Effect slot / effect | EDIT Q-Link → router index | Canonical parameter index / ID | Verified DSP GPR write group |
|---|---:|---|---|
| 01 HALL REVERB | Q1 → 46 | 27 `reverb_mix_bus1` | 7C |
| 01 HALL REVERB | Q2 → 47 | 28 `reverb_mix_bus2` | 7A |
| 01 HALL REVERB | Q3 → 48 | 29 `decay_time` | 03, 04, 05, 5B, 6E |
| 01 HALL REVERB | Q4 → 49 | 30 `hi_freq_damping` | 6C, 6D |
| 02 44KHZ REVERB | Q1 → 46 | 31 `reverb_mix_bus1` | 7C |
| 02 44KHZ REVERB | Q2 → 47 | 32 `reverb_mix_bus2` | 7A |
| 03 ROOM REVERB | Q1 → 46 | 33 `decay_time` | 6E |
| 03 ROOM REVERB | Q2 → 47 | 34 `diffusion` | 07, 09, 0A, 0B, 0C, 12 |
| 03 ROOM REVERB | Q3 → 48 | 35 `hi_freq_damping` | 6C, 6D |
| 04 / 05 delay effects | Q1 → 46 | 36 / 37 `delay_time_l` | 0B |
| 06 CHORUS+REVERB | Q1 → 46 | 38 `chorus_rate` | 90, 91, 92 |
| 07 PHASER | Q1 → 46 | 39 `phase_rate` | 8E |
| 08 FLANGER+REVERB | Q1 → 46 | 40 `flange_rate` | 84, 85 |
| 28 PREAMP | Q1 → 46 | 41 `preamp_gain` | 70 |
| 39 PITCH SHIFT | Q1 → 46 | 42 `quality` | 04, 07, 0A, 61, 64, A0 |
| 41 PITCH SHIFT (effect slot 41) | Q1 → 46 | 43 `voice1_fine` | 60 |
| 42 COMPRESSOR | Q1 → 46 | 44 `comp_ratio` | 8B |
| 49 PARAM EQ | Q1 → 46 | 45 `bass_fc` | 57, 58 |

For a given effect, only its own entries above can be returned by `dynamicEditControl`. An unmapped effect has no descriptor: the router ignores it, formats `NO VERIFIED CONTROL`, and does not call the backend. A static SDK map remains assigned to each generic router parameter even when its corresponding widget is hidden; the source-side null lookup is the fail-closed behavior. The hardware host's handling of a hidden but statically mapped Q-Link still needs device validation.

## Controls, IDs and state

The 19 append-only canonical parameters retain their stable IDs `factory_v4_slot{slot}_{control}` at indices 27–45, and their two verified points are retained in `es5510_factory_editor_v04.hpp`. The Q-Link router parameters use distinct IDs `factory_edit_slot_1` … `factory_edit_slot_8`; the bank control and visibility flags are also appended. The SDK saves/restores chunks by parameter ID, with a compatibility fallback to plain values. The binary harness restored the Hall/ROM-02 canonical values and router state, and checked effect-specific state isolation. No evidence of replacing prior IDs or reusing their automation indices was found.

## Layout inspection

The generated skin contains exactly three tabs. All widgets are within the SDK's 1280×628 canvas, and EDIT Q-Link targets 46–54 have matching controls. Conditional widgets use the SDK's indexed invalidation handles for appended availability flags. No parameter is bound twice on one page. The EDIT BANK control is not needed by any current effect and its Q9 entry remains statically assigned while the widget is hidden. The background art is referenced; fourteen packaged knob/fader/toggle artwork variants are present but not referenced by the generated TUI (the SDK draws those native control styles itself). The approximate scanner flags the headings `TROLLfx / ASR-10 FACTORY FX` and `ACTIVE FACTORY PARAMETERS` as potentially wider than their 278 px cells; this is a fit warning, not a screenshot-confirmed clip. There are no generated SDK screenshots in this evidence set.

## Reproduction evidence

- `python3 tools/parameter_controls/build_editor_v04.py --check` — PASS; 50 slots, 594 documented descriptors, 19 runtime-ready mappings.
- `python3 tests/parameter_controls/test_editor_v04.py` — PASS; generated editor has BROWSE / EDIT / MIX and a single EDIT router map.
- `python3 force_plugin/tools/test_catalog.py` — PASS.
- `AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK python3 force_plugin/tests/test_release_infrastructure.py -v` — PASS, 5/5.
- `python3 /mnt/c/Users/Gamer/research/AkaiForceSDK/tools/validate.py 'force_plugin/dist/TROLLfx - VST - ASR10 FX Collection'` — PASS, 0 errors / 0 warnings.
- `PYTHONPATH=/tmp/trollfx-force-zig python3 force_plugin/tools/test_arm32_vst_qemu.py --arm32-plugin 'force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/VST/asr10-fx-collection-arm32.so' --collection "$ASR10_PRIVATE_COLLECTION" --sdk /mnt/c/Users/Gamer/research/AkaiForceSDK --qemu-arm /tmp/codex-v41-qemu/root/usr/bin/qemu-arm --sysroot /usr/arm-linux-gnueabihf --report /tmp/asr10-v41-independent-qemu.json --zig-pythonpath /tmp/trollfx-force-zig` — PASS, all 50 slots; QEMU user-mode only.
- Clean SDK release build using Zig 0.17.1 — PASS for native, ARMv7 hard-float and AArch64; SDK validation 0/0. The native VST binary-bound package test passed all 50 slots, missing-package silence, state restore, SDK host simulator and callback allocation checks. The build/report was made from the candidate source; the candidate's tracked release artifacts were restored afterwards. The exact source build's native SHA-256 was `c012bc0c86cecabb564370494bfbbb706225e273219d6715059f326c6cf0e128`; ARMv7 output matched the published hash above.
- Independent skin inspection: `/tmp/asr10-v41-skin-qa.json` (approximate overlay; findings are summarized above). This temporary file is not required for reproduction and contains only package/UI digests and generated layout data.

## Outstanding acceptance evidence

1. On a Force, verify EDIT tab navigation, conditional control visibility, physical Q-Link labels and displayed values while switching HALL → ROOM → PITCH SHIFT → HALL.
2. Specifically adjust PITCH SHIFT Q1 and verify the intended QUALITY write group on hardware; then verify HALL and ROOM values remain unchanged.
3. Check the two headings at actual Force scaling and confirm the generic Q-Link label plus formatted display is understandable.
4. Keep the candidate unplayable until those physical editor checks pass; do not reuse the V3 or V1 marker for this binary.
