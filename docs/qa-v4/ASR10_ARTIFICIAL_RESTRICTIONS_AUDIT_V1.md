# ASR-10 artificial restrictions and silent failure audit

**QA branch:** `qa/asr10-v4-gui-independent`  
**QA base:** `b800d78`  
**VST source inspected:** Codex 2 `feature/asr10-force-pc-gui-simulator`, published source `e5bdee257781fde46829df61ac474a58613e9bff` (VST integration ancestry `9ef73e612356da68e7cee424c542ced4fa4379c1`).  
**Scope:** source and evidence review plus the added complete 64-parameter ABI contract. No production source or Force installation was changed.

## Executive results

- **Confirmed obsolete restriction:** the legacy V2 choice builder hides any parameter unless its verified point count is exactly two. The current V4 control table also happens to contain two points for each of its 19 controls. HALL decay's production VST mapping remains 40/41; the full 128-raw-state OS mapping is available only through test/simulator code in Codex 2's unpublished V1.1 experiment.
- **HALL state evidence:** Variation 1 has 128 raw codes, 100 displayed values, 28 duplicate-display buckets, and 198 direction-specific OS transition groups. Each group writes five GPRs in order `6E, 5B, 03, 04, 05`. `clamp(raw, 12, 76)` applies to the GPR 03–05 coefficient path; raw values remain in 6E and 5B. Existing QA reports document 990 matching runtime writes. That proves the tested mapping/register behavior, not a production VST full-range control or hardware UI behavior.
- **High-frequency damping:** the VST harness proves only index 30's 31/32 value and label path. Its HALL case does not inspect the DSP register group or compare audio across those values. The supplied physical evaluation reports no audible effect. Therefore damping is **NOT DSP/audio-verified for the installed candidate**. Historical OS capture shows a reversible candidate transition; an early trial had extensive unrelated writes and a later trial isolated writes to GPR `6D` and `6C` (`31→32`: `6D=0x290000`, `6C=0x56FFFF`; reverse observed on `32→31`: `6D=0x280000`, `6C=0x57FFFF`). These observations alone do not prove the packaged VST applies that exact pair or that the output changes audibly.
- **Hardware UI:** touchscreen operation of bypass and on-screen volume was observed, but the editor usability evaluation **FAILED**: cluttered layout and missing/inaccessible controls. Physical Q-Link knob response remains **NOT TESTED**. SDK JSON validation and the desktop simulator do not constitute physical Q-Link evidence.
- **State/acknowledgement risk:** `setParameter` returns after enqueueing register events. The VST marks controls “applied” on that acceptance result; runtime offers aggregate pending/applied counters and one global last-write flag, not a per-parameter acknowledgement correlated to the VST parameter revision. A displayed or accepted value therefore cannot be presented as an applied DSP value without additional evidence.
- **ABI:** exact 64 parameter names and IDs are now encoded in the independent callback test. The previous count-only 12-parameter expectation is obsolete. Adding full-range decay by changing the existing index 29 choice meaning would reinterpret old normalized/chunk values. Preserve index 29 semantics and use append-only state with an explicit migration if full raw-state persistence is introduced.
- **Temporary QEMU harness exit crash:** preserved log evidence shows all-slot `BINARY_PASS`, return from `main`, completed destructors and `dlclose`, followed by QEMU SIGSEGV during process exit. It is an unresolved test-harness/target teardown failure, not evidence of a live Force crash. It is not a PASS for the current binary's QEMU gate.

## Physical observations and status

| Item | Status | Evidence boundary |
|---|---|---|
| Plugin loads on the Force and HALL wet audio is heard | PASS (user-observed) | Physical device report; no new device action in this audit |
| Touchscreen bypass | PASS (user-observed) | The on-screen bypass control operated |
| On-screen volume controls | PASS (user-observed) | Functional observation only; not a Q-Link test |
| Touchscreen editor usability | **FAIL** | Cluttered layout; controls missing or inaccessible |
| HALL decay range on installed candidate | **FAIL / restricted** | Available control only reached 40/41 |
| HALL high-frequency damping audible response | **FAIL in supplied evaluation; cause unresolved** | User reported no audible effect; input, state, and measurement window were not recorded |
| Individual physical Q1–Q8 knob behavior | **NOT TESTED** | No individual knob response was conclusively confirmed |
| Physical Force Q-Link assignment/delivery | **NOT TESTED** | UI artifacts and desktop host callbacks are not physical encoder evidence |
| Force hardware callback/thread crash | **NOT OBSERVED** | QEMU teardown crash is unrelated to live Force evidence |

The earlier user phrase “delay-time adjustment” is corrected here to **HALL decay**. No delay-time control result is inferred from that observation.

## Findings

Finding IDs are stable keys in the companion JSON. “Change evidence” means evidence to remove a cap or change a behavior; it is not permission to enable an unverified control.

### AR-01 — Hard-coded two-point support in legacy choice construction

- **Severity:** High; **classification:** confirmed artificial cap; **owner:** Codex 2.
- **Reference:** Codex 2 source `force_plugin/src/ASR10FXCollection.cpp:125-134` at `e5bdee2`.
- **Restriction / original reason:** `parameterChoices()` sets `supported` only if `verified_points.size() == 2`; otherwise it returns `UNVERIFIED`. The surrounding code uses a variable-length vector, so exactly two is a semantic gate, not a container limit. This was a conservative early prototype policy.
- **Evidence to change:** verified catalogs can contain more than two observed points; HALL has an independently recovered full raw/display transition map. Codex 2's V1.1 experiment document proposes raw-state editing behind a test-only gate.
- **Risk if removed globally:** package point lists may be sparse, non-monotonic, variation-specific, or only partially verified. Iterating all points does not establish full-range coverage or safe interpolation. The Force legacy UI may also become overcrowded.
- **Minimum regression:** reject empty/unverified sets; enumerate all verified values without interpolation; test per-effect and per-variation lookup; assert unsupported settings create no writes; test old chunks.

### AR-02 — HALL DECAY remains two-point in production while OS has 128 raw states

- **Severity:** High; **classification:** confirmed production feature gap; **owner:** Codex 2, with Codex 1's OS evidence.
- **References:** `include/trollfx/es5510_factory_editor_v04.hpp:97-105` has VST index 29 with `{40,41}`; `tests/force_vst_binary_audio_test.cpp:38-41, 98-100` checks those two display endpoints; `src/es5510_factory_runtime.cpp:518-580` only accepts values present in the validated package descriptor. Codex 2's local V1.1 proposal documents a test-only full raw selector and explicitly says production ABI/chunk remain unchanged.
- **Restriction / original reason:** only two packaged points were promoted into the stable VST ABI. The full original-OS raw map was research-only and the raw state was not serialized.
- **Evidence to change:** independent OS evidence records 128 raw codes mapping to 100 displayed values, 28 duplicate buckets and 198 transition groups; full five-GPR groups and runtime stepping passed existing QA. Every duplicate bucket needs raw-state preservation.
- **Risk if expanded by replacing index 29's choice list:** old VST host automation/chunks stored normalized 40/41 values; remapping that index to 0–99 or 0–127 changes their meaning. A displayed-value-only state loses which raw member of a duplicate bucket was selected. Absolute normalized Force controls may also fail to reproduce directional OS stepping.
- **Minimum regression:** retain old index/name/ID/choice semantics; append a versioned raw-state parameter or chunk field; migrate old 40/41 projects explicitly; round-trip all 128 raw values; check 28 duplicate buckets; run accepted→queued→applied register traces after the 213-event startup schedule; compare audio at low/mid/high states. Hardware Q-Link behavior remains separate.

### AR-03 — HALL state mapping is correct in the tested runtime path, but the production editor path is absent

- **Severity:** High; **classification:** evidence split; **owner:** Codex 1 (mapping source), Codex 2 (production integration), QA (regression).
- **Reference:** public reports `docs/qa-v4/ASR10_HALL_DECAY_INDEPENDENT_VALIDATION_V2.md` and `ASR10_HALL_FULL_RANGE_AUDIO_QA_V1.md`; runtime implementation `src/es5510_factory_runtime.cpp` in the Codex 1 runtime branch; independent test report documents 198 five-GPR groups / 990 writes.
- **Restriction / reason:** existing candidate only exposes 40/41; the full range was withheld because raw provenance, duplicate representations and saved-state semantics had not been integrated into the public VST ABI.
- **Change evidence:** OS sweeps and runtime stepping independently match all 128 raw states. The correct order is `6E, 5B, 03, 04, 05`; coefficient path uses `clamp(raw,12,76)` while the first two registers preserve raw. Existing seeded-state test reaches all raw states and verifies 990 register writes.
- **Risk if treated as end-to-end proof:** those tests do not establish that the installed touchscreen exposes the range, host state preserves raw duplicates, an absolute Q-Link generates OS-equivalent steps, or hardware audio responds as expected.
- **Minimum regression:** same checks through VST `setParameter`/chunk and actual `processReplacing`, correlated per-edit write acknowledgement, then compare meaningful audio. Keep hardware gate NOT TESTED until physical controls are tested.

### AR-04 — HALL damping UI acceptance is distinct from DSP and audio acceptance

- **Severity:** Critical for user-facing promotion; **classification:** confirmed verification gap plus physical audio failure; **owner:** Codex 1 (mapping), Codex 2 (disable/fix UI), QA (test).
- **References:** index 30 is `factory_v4_slot1_hi_freq_damping` in `include/trollfx/es5510_factory_editor_v04.hpp:104-105`; VST sets are routed by `ASR10FXCollection.cpp:459-468`; backend `ES5510DSPBackend.cpp:88-103` resolves package descriptor and calls `FactoryRuntime::setParameter`; runtime `src/es5510_factory_runtime.cpp:518-580` validates the value and queues the descriptor's register group; `tests/force_vst_binary_audio_test.cpp:38-41, 98-100` selects both displays but asserts only the formatted string.
- **Observed user result:** the Force damping control produced no audible difference during the physical evaluation. Input program, damping endpoints, test signal, duration, output capture and level measurements were not recorded. This is a failed user-facing audio evaluation with an unresolved cause; it does not show whether the UI setParameter callback ran.
- **OS evidence:** private `asr10-parameter-discovery-v2/slot-01-hi-freq-damping-report.json` captures display 31→32 and reverse. Trial 1's up window has 555 host writes, including periodic activity. Trial 2 isolates two writes in each direction (`6D/6C` values above). The VST's public test checks do not compare that pair against the plugin trace or against audio. The corresponding capture files remain private and are not included in Git.
- **Restriction / reason:** only two points are catalogued; the package-gated mapping requires an exact descriptor point. It was appropriate to avoid interpolation, but the control was promoted to the editor without an end-to-end audio PASS.
- **Risk if marked functional from callback or write acceptance:** asynchronous scheduling can be accepted but not yet applied; periodic GPR updates may overwrite the value; correct GPRs may belong to an inactive path; damping may be inaudible on the chosen stimulus/window.
- **Minimum regression:** through the exact VST binary, vary damping on a fresh HALL Variation 1 package after initialization; log VST index 30 input, descriptor ID, expected GPR pair, actual ordered writes and frame, later register state after firmware/periodic updates, then compare fixed-gain stereo broadband/noise and high-frequency impulse-tail output with no alignment shifting/normalization. Require finite output and a repeat. Expose as verified only after an audio difference above measured repeat noise and a register match. If no causal result, hide/disable the control and label it unsupported.

### AR-05 — Accepted and queued edits can appear “applied” before the writes execute

- **Severity:** High; **classification:** confirmed acknowledgement-model limitation; **owner:** Codex 2; QA test ownership.
- **References:** candidate `ASR10FXCollection.cpp:438-468` marks legacy control cache on `set_verified_parameter()` success and clears the V4 changed flag when that API returns true; backend `ES5510DSPBackend.cpp:88-103`; runtime `src/es5510_factory_runtime.cpp:518-580` returns after enqueue; actual writes occur in `:279-291`; status publishes a global applied count at `:626-637`.
- **Current behavior:** runtime returns `true` when the complete register group is validated and queued. It later decrements pending count while executing. `last_parameter_write_applied` is global and only set when the pending parameter count reaches zero at the final group event. It has no edit ID, parameter ID, generation, expected register group or value. `applied_control_values_` is named and used as applied-state cache although it records API acceptance.
- **Risk:** UI can show a new value while queued behind startup or when later firmware writes supersede it. Multiple pending edits cannot be individually correlated to applied status. A true callback result is not proof of a final register value/audio result.
- **Minimum regression:** issue several distinct edits across startup boundary; capture accepted sequence IDs, queue count, application frame, effect generation, group writes and final GPRs. Switch/reset while pending and ensure no stale acknowledgement is shown. Test callback/UI does not claim applied until matched acknowledgement.

### AR-06 — Effect switching and router slots have a stale-edit drop risk

- **Severity:** Medium; **classification:** suspected race, not reproduced; **owner:** Codex 2.
- **References:** candidate `ASR10FXCollection.cpp:363-377, 422-434, 459-468`.
- **Current behavior:** effect changes clear `applied_control_values_`; dynamic slot events are consumed with `exchange(false)` before verifying that a matching current control exists or that the point is valid. `applyV4Controls()` keeps an event pending when backend rejects the write, but an accepted queue has no generation token. `active != selected` returns before routed-slot processing; the flag remains pending in that branch.
- **Evidence / potential failure:** the design guards by active slot and only routes slots after ready, but not every failure path is tested for stale GUI bank/control events across two rapid effect changes. A stale VST edit could be dropped or the UI cache could reflect a value from a prior effect. No wrong-effect write has been confirmed.
- **Minimum regression:** deterministic rapid A→B→A / A→B→C switching with edits before, during and after prepare; log `selected_slot`, `active_slot`, request generation, editor bank/slot, stable parameter ID, accepted/applied frame and all target GPR writes. Assert no wrong-effect GPR write and explicit retry or rejection for every edit.

### AR-07 — Full-range state must preserve VST2 IDs and old chunk meaning

- **Severity:** High; **classification:** migration gate; **owner:** Codex 2.
- **References:** VST 64-param list is declared in `ASR10FXCollection.cpp` around lines 147-210 of `e5bdee2`; independent QA exact names/IDs/chunk parser is `tests/force_vst_binary_audio_test.cpp:27-87`; V1.1 proposal says index 29 40/41 remains unchanged and recommends append-only interface/chunk migration.
- **Current evidence:** a complete 64-name/ID VST callback contract passes for binary `dd5f964ecc8f856ece67793a8154e1881a50a9f465f292144a1725bf41782e26`; candidate chunk is `MPCP` version 2 with 64 parameter identities. This verifies that candidate only, not any future ABI change.
- **Change evidence / safe path:** Codex 2's proposal to preserve index 29 and append new state is the compatible direction. It is not yet a published, migrated, or independently tested production implementation.
- **Risk:** reordering indices or changing normalized choice semantics silently corrupts automation and saved projects. Adding a 65th parameter can affect Force SDK/host limits and requires binary-bound proof.
- **Minimum regression:** old v2 chunk fixture and host automation values restore unchanged; new chunk stores raw 0–127 including duplicate display pairs; new state upgrades old 40/41 deterministically; roundtrip on current and target SDK; verify exact ABI IDs/order and parameter count.

### AR-08 — Screen JSON/SDK validation was previously over-interpretable as hardware evidence

- **Severity:** High; **classification:** test-claim defect; **owner:** Codex 3 and Codex 2.
- **References:** candidate `force_plugin/tools/test_packaged_vst.py:45-56` verifies SDK/package and VST callback claims; `tests/force_vst_binary_audio_test.cpp:38-41, 98-100` checks the VST parameter endpoint but has no physical encoder input. Existing `docs/ASR10_FORCE_INTERFACE_SIMULATOR.md` describes desktop event routing, not a Force hardware trace.
- **Evidence:** actual Force touchscreen usability FAILED despite prior simulator/SDK pass. Individual physical Q-Links remain NOT TESTED.
- **Minimum regression:** reports must label generated JSON/render checks as static/desktop only. Hardware Q-Link PASS requires a physical test log with selected page/bank, encoder identity/direction, displayed label/value, corresponding host `setParameter` event, applied DSP write, and audible/observable effect. Do not infer that a generated Q-Link binding receives a physical event.

### AR-09 — Temporary ARM/QEMU test harness crashes after reporting test PASS

- **Severity:** Medium; **classification:** unresolved test infrastructure failure; **owner:** Codex 3 / release QA.
- **Evidence:** preserved logs outside Git: `/tmp/trollfx-arm32-qemu/teardown.log` SHA-256 `2c0f383cb4e17f4f919f29e9771158fbb27a61cb8bdf70d2022c1916b58cf411`; `/tmp/trollfx-arm32-qemu/pass.log` SHA-256 `96d81fa2a431e73586c877f4ebbca1a5eab9187cd7167224337f68c408f8fdd7`; `/tmp/trollfx-arm32-v3-qemu.log` SHA-256 `2913fed3133bdc001f62bf6c08d9531c783ad1832217c8e288396257959f351f`. The teardown log shows all 50 slot assertions, `BINARY_PASS`, return from `main`, completed destructor and `dlclose`, then QEMU SIGSEGV during process exit. No core stack or unambiguous candidate-binary hash was recorded with the log.
- **Interpretation:** not a live Force crash, and not a clean QEMU PASS for a specific current binary. Preserve the logs and do not suppress the exit signal.
- **Minimum regression:** reproduce with exact binary/asset-index hashes and command; capture exit code/core stack; compare a minimal no-plugin QEMU process and an ARM host run; identify whether plugin destructor, host shim or QEMU teardown causes it.

### AR-10 — UI's 40/41 control is an underspecified fixed range, not evidence of full HALL support

- **Severity:** High; **classification:** confirmed shipped UI limitation; **owner:** Codex 2.
- **References:** generated control entries at `es5510_factory_editor_v04.hpp:103-105`; candidate test asserts two options at `force_vst_binary_audio_test.cpp:38-41, 98-100`; physical report states decay stops at 40/41 and editor usability fails.
- **Original reason:** conservative point-level promotion from exact package evidence; no raw-state public persistence protocol.
- **Evidence to change:** independent full OS raw/display transitions and runtime test have been published. The display has 100 distinct values but 128 raw states and duplicate buckets.
- **Risk:** using a naïve 0–99 scalar loses raw-state identity and original duplicate stepping; existing chunks and automation break if the old parameter index is redefined.
- **Minimum regression:** append/version new raw-state representation, preserve old ABI parameter meaning, state-migrate, test every raw step and duplicate bucket via VST and runtime, then audio A/B and target Force UI validation.

## High-frequency damping investigation result

| Stage | Evidence/result | Status |
|---|---|---|
| Touchscreen/UI interaction | Physical user evaluation: control visible/adjustable, but no audible change | **FAIL for audio response; callback delivery unconfirmed** |
| VST parameter route | Candidate source index 30 resolves to `factory_v4_slot1_hi_freq_damping`; existing binary harness sets it to both values | **PASS for parameter/display path only** |
| Expected OS register evidence | HALL OS probe observed value pair on GPR `6D` and `6C` in one repeat; first repeat was contaminated by many writes | **PARTIAL** |
| Packaged runtime write accepted | Backend routes descriptor point to FactoryRuntime; package-local exact mapping cannot be independently revalidated here without the private package directory | **NOT TESTED in this audit** |
| DSP write executed / not overwritten | No VST-bound ordered trace and post-write register snapshot for damping in the public evidence | **NOT TESTED** |
| Audio difference | Physical observation says none; no controlled binary-bound stereo noise/high-frequency A/B capture for damping | **FAIL in physical evaluation; independent cause/difference NOT TESTED** |

Recommended policy: keep HALL damping off the functional production interface until the package's exact register group is traced through the VST and an appropriate repeated audio A/B passes. Do not replace the physical failure with a register-only pass.

## Codex 2 proposal review (read-only)

Codex 2's local, uncommitted `docs/ASR10_HALL_V11_EDITOR_EXPERIMENT_V1.md` proposes a simulator-only raw selector 0–127, OS-equivalent directional stepping, and keeping existing public parameter index 29 at 40/41. It also states raw-state selection is not serialized, physical Q-Link behavior is untested, and a future public control should be append-only with chunk migration. This is a sound compatibility direction and preserves the two-static-page design. It is not production code and does not satisfy the required full-range Force editor. The new raw selector must not be described as a production fix until it is integrated, has per-raw state restoration, and passes target hardware acceptance.

## 64-parameter VST2 ABI

The independent harness now checks all 64 parameter names and all 64 stable IDs in index order from the candidate's `MPCP` version-2 chunk, replacing the obsolete 12-parameter expectation. Exact identity order is encoded in `tests/force_vst_binary_audio_test.cpp:28-82` and checked by `verify_64_parameter_abi()` at `:67-87`. The check passed against the candidate binary hash above. It is not an approval to reorder or repurpose existing IDs. Any new HALL state must be append-only or version-migrated.

## Tests run / skipped

- **Ran previously, preserved:** candidate-bound native VST tests against binary SHA-256 `dd5f964e…`, private asset index SHA-256 `8bbb71d3…`; 50 package audio smoke and core host behavior passed. The relevant VST test did not assert damping GPR application or damping A/B output.
- **Ran previously, preserved:** candidate VST ABI 64 names/IDs and version-2 chunk mapping pass; callback allocation counter zero; HALL full raw-state OS/runtime research remains as published in the QA reports.
- **Ran in prior task:** focused `tools/audio_validation/test_factory_runtime.sh` on clean e5 source passed synthetic runtime tests.
- **Not rerun:** unrelated 50-slot acceptance, HALL 128-state exhaustive sweeps, historical ROM/OS capture or full regression. No code under test changed in this audit.
- **Not run here:** controlled binary-bound HALL damping audio/GPR trace, because the validated private factory package/checkpoint assets were not present at the paths accessible to this audit session. Existing report evidence was read from local private results only; no assets were copied into Git.
- **Not run:** physical Force knob tests, QEMU reproduction, install/restart, and any hardware instrumentation. Force was not modified.

## Release conclusions

| Gate | Status | Reason |
|---|---|---|
| Bypass and on-screen gain | PASS (user-observed) | Physical feedback |
| Touchscreen editor usability | **FAIL** | Clutter and inaccessible/missing controls |
| HALL decay full-range production editing | **FAIL / not implemented in candidate** | Production index 29 remains 40/41 |
| HALL raw/display/register mapping research | PASS at research/runtime test boundary | 128 raw / 100 display / 28 duplicate buckets; 198 groups / 990 writes |
| HALL decay full-range VST state migration | NOT TESTED | Test-only raw interface is not persisted or public |
| HALL high-frequency damping audio behavior | **FAIL in physical evaluation; independent cause unresolved** | User heard no difference; no controlled desktop VST A/B exists |
| Physical Q-Link input behavior | NOT TESTED | Knob actions not individually confirmed |
| QEMU candidate execution/clean teardown | NOT TESTED | Preserved test harness has post-main SIGSEGV and lacks exact candidate hash binding |
| Original hardware full audio equivalence | NOT TESTED | No matching Force reference capture |

