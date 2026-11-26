# Agent 2 — production VST2 / two-page Force editor / original parameter behavior

**Active owner:** plugin code, fixed SDK UI maps and production HALL 0–99. Read [coordinator](00_COORDINATOR.md), [architecture audit](../TROLLFX_ASR10_ARCHITECTURE_WORKFLOW_AUDIT_V1.md), [test policy](../TROLLFX_ASR10_TEST_POLICY_V1.md), [local manual index](../ASR10_MANUAL_LOCAL_REFERENCE.md), [historical V4.1 SDK analysis](../ASR10_FORCE_DYNAMIC_EDITOR_V41.md) if available in your branch.

## Recover existing work first

Existing development branch `feature/asr10-force-pc-gui-simulator` (prior snapshot `e5bdee2`, integrated source `9ef73e6`); secondary historical `feature/asr10-force-effect-dependent-editor-v4.1`. These may have moved: inspect local worktrees, HEAD, status and current changes before touching. Do not discard edits or merge entire research/QA branches (older source contains stub VST). Preserve the proven `VSTPluginMain -> setParameter/processReplacing -> FactoryRuntime` path and all 50 local factory packages.

## User's locked design

**Exactly 2 static pages** (MAIN, EFFECT), simple readable graphics and native SDK widgets. No conditional visibility, dynamic parameter/Q-Link naming, complex bank selector, decorative clutter, hidden generic edit routing presented as controls or visible BUS1/BUS2/BUS3. One stereo effect engine only; second effect in series is future. Avoid overfilling Q1–Q8.

- **MAIN**: Q1 effect select across 50; Q2 wet/dry; Q3 input gain; Q4 output gain. Retain working on-screen bypass, using a clearly labeled switch if needed without pretending its Q-Link behavior is known.
- **EFFECT**: initially HALL-specific Q1 DECAY TIME 0–99, Q2 HI FREQ DAMPING **only if proven functional**; other Q-Links blank. Static page remains static when other effect selected; never silently edit HALL while a different algorithm is active. For other effects, prefer a safely unavailable edit or a future explicit fixed-page design, not fake dynamic labels. Confirm exact SDK `gen_ui.py` semantics and emitted `Plugin Skins/TUI.json` + `Q-Links.json`.
- Physical touchscreen usability in deployed V1 **FAIL**. Touch bypass works; gain appeared responsive. Physical knobs not conclusively tested. HI FREQ DAMPING had **no audible effect**; delay range too narrow to assess. These are mandatory targeted end-to-end tests.

## Original HALL mapping

- HALL REVERB Variation 1 verified original startup raw 52 -> displayed 40; raw 51 also displays 40; raw 53 displays 41. Original 128 raw states display 0–99 with duplicate buckets. Stepper skips duplicate LCD values; internal raw state identity still matters. Original HALL five-register group `6E/5B/03/04/05`. Startup original schedule: 213 writes through DSP frame 12983; first safe edit frame 12984. This is HALL-specific and requires validated startup and correct active variation. Do not assume Variation 2–4 identical or original all-variation save/return proven.
- Source map `include/trollfx/es5510_hall_decay_control.hpp`; native adapter `include/trollfx/hall_decay_native_adapter.hpp`; production currently gates raw overrides/test-only API. The catalog's `kPointValues29[] = {40,41}` and `ASR10FXCollection.cpp` condition `verified_points.size() == 2` are **prototype caps**; remove these arbitrary restrictions with tests, not by just inventing 100 arbitrary coefficient values.
- HALL raw 0–127 formula/GPR groups and 0/99 & 10/90 instrumented VST2 audio comparisons exist, but **they were not an accepted production full-range host parameter**. Integrate via production-safe runtime path, support discrete original UI semantics, raw-state stepping, deferred writes and complete group application; measure actual VST2 audio changes, not only UI callbacks.
- A 0–99 displayed value is not a unique raw state. Define explicit deterministic display->raw selection and host automation semantics while preserving raw state where available. Don't lose original-state semantics on duplicate buckets.
- Existing parameter indices 0–63, IDs and chunk version must be preserved. Replacing a normalized two-choice `DECAY TIME` list in-place with 100 choices is **not automatically state compatible**. Agent 3 must review append-only vs versioned migration; publish exact old/new state round-trip before acceptance.

## Broader parameter recovery

19 runtime-ready routes currently documented across 50 effects and 594 manual descriptors. **19 is a current implementation count, not an SDK absolute limit.** Audit high-frequency damping (UI -> setParameter -> accepted -> scheduled/applied GPR -> measured audio), current narrow delay control versus manual/OS data, any `verified_points.size()==2` gates, missing registration and wrong-effect edits. Use original ASR-10 Musician's Manual and original OS captures as separate evidence. ROOM GPR5B differs from HALL. Don't copy a HALL raw mapping to a different effect.

Avoid scope creep: near-term milestone is 50 playable effects + reliable two-page UI + validated HALL full-range, not a claim that all 594 parameter mappings have been reconstructed.

## Implementation/test contract

1. Identify all old V4 dynamic routing and layout code, remove only from **visible UI** while maintaining ABI indices and old saved chunks. Do not hard delete legacy VST parameters.
2. Ensure every active control is readable, has fixed real param identity/Q-Link page assignment, and gives a measurable effect when changed with suitable audio. Unverified controls absent/disabled, not masquerading as functional.
3. Distinguish parameter **host accepted**, **queued**, **DSP applied** and **audible output difference**. Avoid stale `applied_control_values_` caches and consumptive flags before backend success.
4. Test HALL raw boundaries, duplicate steps, full 0–99, startup safety, switching, bypass, wet/dry/gain, HALL inactive selection, state-save/restore, NaN/Inf, zero audio callback allocations, correct process rate and direct VST2 callback path.
5. The current backend sets `RateMode::Experimental48000` in initial and worker loads; not an original-rate equivalence claim. Do not casually change DSP sample-rate mode during UI rebuild.
6. Use change-based T0/T1 then immutable T2 when ready, not repeated full original-OS sweeps. SDK host simulator and generated JSON **do not** establish physical touchscreen or Q-Link operation.
7. Commit/push source and immutable candidate only after checking generated package SHA256SUMS, manifest, private asset-index identity and absence of proprietary payloads. Never deploy, restart, reflash or modify the Force from this role.

## Handoff to QA

Provide exact source branch/commit, dirty status, 64-param layout hash/ABI migration, direct Q-Link per-page mapping (page, Q position, exact parameter index/id), HALL display/raw mapping policy, variation rules and GPR evidence, binary SHA-256 native+ARM32, private index digest, generated skins, package path, results and known fail/blocked cases. Do not say 'ready' while candidate hash/manifest is changing.
