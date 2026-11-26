# TROLLfx ASR-10 — Architecture / Workflow Risk Audit V1

Snapshot 2026-11-26. Based on public branches `main@56c6707`, `feature/asr10-force-pc-gui-simulator@e5bdee2`, `research/asr10-full-factory-parameter-recovery@64d893f`, `qa/asr10-v4-gui-independent@b800d78`, plus the user-supplied ASR-10 Musician's Manual. This document is an **audit and test proposal**, not a claim any newly proposed checks were executed. The active Force deployment has separate ownership.

## 1. Confirmed code and release architecture facts

- `main` carries coordinating documentation and the general ASR-10 emulator; all three Codex implementation branches are long-diverged from main. The Force VST2 production implementation lives on Codex 2's branch. Do not bulk-merge divergent branch trees, especially `force_plugin/src/ASR10FXCollection.cpp`.
- The Force VST2 uses `ASR10FXCollection::process` → `ES5510DSPBackend::process` → active `FactoryRuntime::processStereo`, with an async worker preparing the inactive of two runtime instances. Real VST2 HALL 40/41 delta and OS editor startup raw 52 are demonstrated on Codex 2's candidate.
- In the inspected `ES5510DSPBackend.cpp`, both initial `prepare()` and background `loadEffect()` explicitly select `RateMode::Experimental48000`. This is supported experimental 48-kHz processing, **not original factory-rate audio equivalence for all 50 algorithms**. The original manual distinguishes 30-kHz and 44-kHz rate classes and sample-rate/polyphony effects.
- `build_release.py` includes `docs/ASR10_FORCE_DYNAMIC_EDITOR_V41_ARMV7_QEMU.json` in `source_digest()`, and if that historical report exists it rejects any newly-built ARM binary whose digest differs. QEMU evidence is testing output, not source input; decouple from digest and treat as candidate-specific optional execution result.
- `ES5510FactoryPackageProvider::discover_asset_root()` prioritizes `TROLLFX_FACTORY_PACKAGES_DIR`, then plugin-root `factory-assets-path.txt`, then plugin-root `FactoryAssets`. It validates `provider-index.tsv` and referenced asset SHA hashes. Missing private assets fail closed. `install_package.py` checks an exact `SHA256SUMS` inventory; adding a pointer after packaging requires documented local configuration or new checksums.
- `install_package.py` calls `verify(target)` before replacing an installed folder; a historic/customized installation may fail the current release's integrity schema. Build a separate preservation and rollback-safe migration path rather than deleting the target.
- `ASR10FXCollection.cpp` exposes 64 stable host parameters in the current candidate; older independent test assertions expect 12. Protect **the full parameter ID/index/choice/chunk identity**, not just a parameter count.
- Current HALL production editing remains evidence-gated; raw 51/52 both display 40 and starting raw 52 is proven only for factory Variation 1. Current separate VST3 instrument is not FX Collection VST2.

## 2. High-value potential bugs requiring tests (not confirmed failures)

### A. Worker / audio thread state-machine concurrency

Code pointers: `force_plugin/src/ES5510DSPBackend.cpp` `worker_loop()`, `process()`, `set_verified_parameter()`; `ES5510DSPBackend.h` atomic generations/indexes/global status.

The worker writes the inactive runtime, publishes a `ready_index` and generation, and uses global `status_` that also describes loading/unavailable. Verify invariants in an explicit state-transition model:

1. Active runtime must never be mutated by the worker while callback processes it.
2. A ready generation can be activated only if it still corresponds to the requested slot and package identity.
3. A stale worker completion cannot mark the currently audible slot Failed/Unavailable or make its sound disappear unexpectedly.
4. Parameter writes cannot be applied to an active slot with another slot's descriptor; early edits must either queue with correct ownership or be explicitly rejected.
5. Reset, destructor, rate reprepare, rapid changes A→B→A, unavailable package, and empty block sizes cannot cause a silent deadlock, crash or permanent Waiting state.

Use deterministic barriers and a stress harness before performance tests; ThreadSanitizer can supplement but is not a substitute for modelled transitions. **Do not label these as observed failures without reproductions.**

### B. Parameter event acknowledgement / host state

In `ASR10FXCollection.cpp`, `applyVerifiedControls()` advances its applied-control cache when `backend_.set_verified_parameter()` **accepts** a write. The runtime distinguishes queued versus actually applied events, so acceptance is not the same as audible completion. `applyRoutedEditSlots()` clears a changed flag before it verifies the selected bank/control is usable; verify that a bank switch or unready control cannot silently lose the desired edit. `applyV4Controls()` retries rejected writes; investigate whether persistent rejection can cause useless retries.

Develop a desired / queued / applied / rejected state machine keyed by `slot,variation,parameter,raw_value,load_generation`. Preserve VST 64-ID host compatibility; add internal diagnostics without adding public parameters.

### C. Real-time side effects

The reviewed code does not explicitly allocate within `ES5510DSPBackend::process()`, but `ASR10FXCollection::process()` calls `set()` for routed edit sync and accesses host parameter/SDK code. Profile whether any SDK callback, UI refresh, string conversion, contention, or hidden allocator occurs during audio callback under automation and switching. Existing zero-allocation tests are useful but don't prove bounded worst-case execution. Test 64/128/256/512/1024 block sizes, burst automation, all 50 algorithms, long feedback tails and cold/warm cache.

### D. Host vs DSP rate and delay alignment

Current backend forces Experimental48000. Host rate changes and dry alignment rely on calculated latency and a short delay ring. Measure actual impulse latency and left/right wet-dry cancellation at 44.1/48/96 kHz, partial/zero frames, and algorithm switching. Separate host WAV header rates, internal DSP rate and original factory sample-rate classifications. Do not silently switch to original rate until resampling/latency and CPU tests are accepted.

## 3. Manual findings worth modelling before broad parameter exposure

User-provided ASR-10 Musician's Manual Section 5 distinguishes **ROM, BANK and INSTRUMENT effects**. It describes an edit of a ROM effect copying the current effect into BANK; loading instruments/banks can change effect ownership, while some selection changes do not reload the ESP. Manual documents **four independent editable variations** with modulation source/destination and range semantics, plus BUS1/BUS2/BUS3 routing and optional AUX dry paths. It documents algorithm-dependent 30-kHz/44-kHz rate behavior (31 versus 23 polyphony) and that **variation-only changes need not reload the DSP program**.

These manual statements are **original device behavior descriptions**, not claims the desktop VST must implement the sampler's voice/polyphony or full effect ownership now. First implement a pure, testable original-OS state-transition specification for comparison, then decide which semantics belong in the FX VST, which in a later emulator mode, and which remain intentionally out of scope. Avoid conflating host bypass, original BUS3 dry routing, and original FX OFF / INST / BANK / ROM selection.

Manual Section 6 specifies parameter roles and units; the original OS raw state and DSP conversion remains the authority for actual control behavior. Preserve source IDs, edition/section/page, displayed ranges, raw ranges, OS byte/step routine, DSP GPR group, variation and evidence grade independently.

## 4. Error-prevention opportunities, ranked

**P0 — Release identity and preflight:**
- One immutable candidate JSON record: source full SHA, clean/dirty input fingerprint, SDK/compiler SHA, native+ARM binary hashes, plugin identity/64-index ABI hash, provider-index hash, checksummed package hash, exact test run IDs.
- Validate the installed ARM binary and device-local asset index against this record before activation; QEMU `NOT_TESTED` when not run on same binary.
- Atomic stage/activate/backup/rollback, handling older customized installs. Store rollback outside plugin scanner.
- Make install/reboot a separate explicit action from source build/test; current user authorization may allow controlled install, but no silent broad system changes.

**P1 — Branch and evidence workflow:**
- Keep `main` as a stable docs/handoff branch; name one canonical Force VST2 integration branch/release tag. Port specific isolated research commits/cherry-picks with tests, not bulk cross-branch merges.
- Add one `artifact_provenance.json` per candidate and test result; ban naked PASS without candidate SHA. Strict `PASS/FAIL/BLOCKED/NOT_TESTED`.
- Gate changes using [Test Policy V1](TROLLFX_ASR10_TEST_POLICY_V1.md) / [Matrix V1](TROLLFX_ASR10_TEST_MATRIX_V1.json). Do not implement a test selector that mistakes build-consumed docs for prose-only.
- Auto-detect stale manifest hashes, mismatched VST registry and mismatched provider index before any slow tests.

**P1 — Runtime state and host integration:**
- Model-based effect-switch stress as above; per-generation state; queue accepted-vs-applied parameter acknowledgements.
- Verify host state chunks round-trip and desired values after reset/variation changes; compare against original OS semantics where relevant.
- Add output finite/clipping/feedback limit telemetry for dev builds, without making DSP alterations without sonic regression tests.

**P2 — Research productivity:**
- Build a source-of-truth parameter evidence database with `algorithm_id,variation,manual_page,display_range,raw_code,step_direction,OS_trace_hash,ordered_GPR_writes,clock_mode,status`.
- Generate GUI registry, tests and coverage report from the same reviewed evidence, **not** by writing three parallel inventories. Keep experimental/unverified data visible but non-writable to DSP.
- Automated original-OS A→B→A variation and saved-value experiments; duplicate-display raw state coverage; use ROOM shared routines only where register-conversion equivalence is observed.
- Perform original-device same-state audio capture when hardware is available. Emulator-to-emulator equality is not a physical-hardware oracle.

## 5. Agent ownership and stopping conditions

- **Codex 1**: current Force deployment, immutable release artifact and device/asset/rollback checks. Avoid new DSP architecture refactors during install.
- **Codex 2**: on isolated worktree, test effect-switch concurrency, control event ownership and V1.1 editor implementation; no Force access.
- **Codex 3**: independently test same candidate ABI, callback safety, variation/serialization semantics, cross-rate latency and compare evidence; no Force access.
- After device smoke: nominate a source and binary hash; do not change candidate underfoot. Any source change to shipped code requires a new candidate fingerprint and relevant T2 gate.

## 6. Suggested focused initial experiments

1. Run deterministic A→B→A slot switch with barriers while changing parameters; assert no inactive-runtime write reaches the active instance and no stale completion activates wrong package.
2. Simulate missing asset root, wrong `provider-index.tsv`, unreadable file and customized old plugin installation; confirm safe refusal without destroying backup.
3. Capture one host save/restore sequence including raw52, raw51, variation selection and switching; record whether restored **host control values** actually become active DSP registers. Do not claim original variation restoration where evidence absent.
4. Verify 44.1/48/96k host impulse latency and wet/dry routing; record DSP mode and hardware CPU separately.
5. Build one reviewed manual-to-OS-to-DSP evidence record for ROOM Variation 1, including the GPR5B divergence, before cloning HALL's complete mapping.

**References:** `docs/ASR10_VST2_FACTORY_RUNTIME_INTEGRATION_V1.md` on `e5bdee2`; `docs/ASR10_HALL_EDITOR_RAW_STATE_PROVENANCE_V1.md` on `64d893f`; `docs/qa-v4/ASR10_VST2_INDEPENDENT_ACCEPTANCE_V1.md` on `b800d78`; Musician's Manual Sections 5–6 and 44-kHz appendix from user-provided PDF. This document summarizes and proposes; current full-device audio results remain unverified at snapshot.
