# TROLLfx ASR-10 — Test Policy V1 (change-based, candidate-bound)

**Effective:** 2026-11-26. **Canonical:** `main/docs/TROLLFX_ASR10_TEST_POLICY_V1.md`. Read alongside [the cross-agent master handoff](TROLLFX_ASR10_CODEX_MASTER_HANDOFF.md). The adjacent [test matrix](TROLLFX_ASR10_TEST_MATRIX_V1.json) is a **policy specification**, not an already-implemented executable test selector. No test runs or deployment are claimed by publishing these documents.

## Why this policy exists — observed repo audit

We inspected the actual published `e5bdee2`, `b800d78`, and `64d893f` branches. They contain complementary but overlapping gates:

- `force_plugin/tools/build_candidate.sh` delegates to `build_release.py`; the release build can run `test_es5510_backend.sh` (private HALL/ROM-02 and plugin wrapper), SDK multi-target compilation/validation, `test_packaged_vst.py` (actual native binary VST2 all 50 slots, callback integrity, simulator), packaging/hash checks.
- `force_plugin/tools/test_packaged_vst.py` prepares a 50-slot temporary private asset tree, compiles `tests/force_vst_binary_audio_test.cpp`, executes the real native VST2, runs a missing-package case and SDK host simulator. It is authoritative for **packaged candidate**, not necessary for every UI-only edit.
- `tools/force_simulator/tests/test_native_integration.py` rebuilds the native simulator VST bridge for tests; browser `npm run test:browser` uses Playwright and a launched simulator. Some tests require private assets and one real-audio browser case is fixture-dependent.
- `tools/audio_validation/test_factory_runtime.sh` compiles native runtime and input-sanitization C++ tests. Separate Python original-OS/catalog/parameter suites and Codex 3 audio comparisons cover research evidence, rather than binary-bound release.
- `force_plugin/tools/test_release_infrastructure.sh` checks catalog, packaging-infrastructure unit tests, schema and Python syntax. Its packaging fixture is based on a checked-in `force_plugin/dist` folder, so **fixture tests are not proof that a new candidate folder is installable**.
- The checked-in `build_release.py` source digest includes `docs/ASR10_FORCE_DYNAMIC_EDITOR_V41_ARMV7_QEMU.json`, a **historical test result**, and it may reject a newly built ARM binary if that historical report is present but its hash differs. QEMU validation must be **candidate-bound** and decoupled from source inputs.
- An older Codex 3 harness asserted **12** host parameters; Codex 2's integrated candidate has **64**. Correct the **complete layout** in independent QA, not merely the count. A temporary adjusted harness passing on Codex 2's machine does not replace independent QA.

## Principle: fewer repeated tests, not weaker safety gates

Keep all historical evidence, raw WAVs, exact register traces and full suites available. Do not regenerate unchanged 44-WAV captures, broad original-OS sweeps or 50-slot playback on every change. **Never** cache positive results across different candidate binary hashes unless the gate explicitly checks source-only content and names the source digest.

There are four levels:

| Tier | Trigger | Expected action | Typical time policy |
|---|---|---|---|
| **T0** — quick preflight | Every commit or local edit | Syntax/import/lint, changed module unit tests, `git diff --check`, affected schema checks; no SDK rebuild unless necessary | Fast and local |
| **T1** — focused integration | Affected subsystem changes | Run the specific native/runtime/VST2/UI tests selected below; test actual VST2 callback if plugin logic changed | Per change |
| **T2** — immutable candidate acceptance | Candidate nominated for device installation or release, binary changed | **Once per exact source + binary + private asset-index identity**: all 50 slots, 64-index ABI/chunk, NaN/Inf, zero callback allocations, switching/startup, SDK, ARM ABI, hash-bound package verification, install/rollback preflight | Mandatory before deployment |
| **T3** — deep research and physical evidence | New DSP algorithm/OS mapping/clock/serialization semantics; physical installation/functional testing | Complete relevant original-OS mapping, register/event replay, all 128 HALL raw states if affected, multi-stimulus reference audio, real-device performance and user-visible interaction where available | Evidence-driven |

The scopes can stack. A change involving both code and packaging triggers both affected T1 tests plus T2 if building a device candidate. T3 **research** tests are not prerequisites for package-only changes. T3 **physical** tests become necessary to claim a release works on Force.

## Change impact selector

Compute changed paths relative to the exact approved base/commit, **including uncommitted modifications and generated artifacts that will be shipped**. If a change touches multiple categories, take the **union**. If the set is unknown or impacts generated code, run T1 for every plausible affected subsystem, then T2 before a device candidate.

| Changed area | Run in T1 | Can skip at T1 when unrelated |
|---|---|---|
| `src/es5510*`, `src/hall_decay_native_adapter.cpp`, `include/trollfx/es5510*`, validated DSP conversion/step code | `tools/audio_validation/test_factory_runtime.sh`, matching `tests/parameter_controls` and native backend HALL/ROOM/ROM-02 tests with assets available; deterministic A/B stimulus | Entire browser suite, 44-WAV research archive |
| `force_plugin/src/ASR10FXCollection.cpp`, `ES5510DSPBackend*`, provider, parameter routing, state code | Focused actual VST2 callback tests (parameter safety, startup, state, audio, one HALL 40/41 pair), backend tests | Full original-OS catalog, 50-slot long run until T2 |
| `force_plugin/plugin.json`, `ui.json`, assets/graphics, `tools/force_simulator/web`, layout/skin | Model/layout and changed-page Playwright tests; ABI/state test if VST parameter ordering, IDs, Q-Link or serialization touched | Full factory audio render and OS reconstruction if audio code unchanged |
| `force_plugin/tools/build_release.py`, `install_package.py`, `rollback_package.py`, `mark_playable.py`, private asset path/index logic, manifest schema | `force_plugin/tools/test_release_infrastructure.sh`, install/rollback temporary-folder fixtures, package inventory/hash/asset-root resolution tests, metadata validation | Full 44-WAV comparison and original OS trace |
| `tools/audio_validation/*`, original-OS monitors, `tests/parameter_controls/*`, mapping catalogs | Relevant Python catalog/OS capture/parser tests and targeted original register-group replay; preserve independent provenance | SDK 50-slot run if no runtime/plugin/output files change |
| `tools/force_simulator/audio_lab*`, `web/audio-lab.js`, audio comparison schema | `test_audio_lab.py`, focused browser import/decode/plot/measurement test with synthetic fixture; test one private real bundle when available | All four bundles and 44 WAVs on every edit; full DSP build |
| `tests/*` or test runners only | Run the changed tests, plus a fixture-negative case; use coverage to decide whether they exercise production | All other unrelated suites |
| Docs-only with no executable/config/manifest change | Markdown/link/schema consistency only; code tests not mandatory | All compilation and audio gates |

**Exception:** A document, asset index, UI JSON, generated file or release manifest consumed by the build/runtime is **configuration**, not “docs-only.” Changing it invokes the relevant tests. Treat generated output changes as code changes even if only an input generator script was edited.

## Required T2 candidate gates (never omit for speed)

1. Record full Git SHA, branch, dirty state, SDK SHA, toolchain, build command and native + ARMv7 binary SHA-256. A candidate with untracked build-affecting changes must record those inputs; prefer a clean reproducible source checkout.
2. Verify ARMv7 ELF class, hard-float ABI, required libraries and host compatibility. QEMU result is **PASS only if run against this exact binary hash**; otherwise `NOT_TESTED`, not a fake FAIL or inherited PASS. QEMU unavailability by itself does not block an explicitly controlled Force smoke.
3. Validate all 50 **private locally authorized** packages through actual `VSTPluginMain` / `processReplacing`, finite/non-silent stereo, exact per-slot availability and missing-package fail-closed behavior. A 50/50 smoke is **runtime coverage**, not original-hardware equivalence.
4. Independently confirm full **64-parameter** identities/order/serialization (not just number), VST saved-state chunks, effect switching/restart, 213-event HALL schedule, first editable DSP frame 12,984 for the validated HALL case, active instance/register ownership, 40/41 audio delta, actual parameter completion, NaN/±Inf parameter/audio protection, zero callback allocations.
5. Run SDK validation and package checks. Confirm `SHA256SUMS` matches **every packaged file** and the playable/release marker points to the exact shipped ARM binary and accepted native test report. Verify installer + rollback dry-runs against a **temporary** tree (including an old/customized installed folder).
6. Resolve actual **device-local** `factory-assets-path.txt` or provider-supported directory using observed filesystem data; verify real `provider-index.tsv`, its 50 entries, hashes and permissions. The pointer is not factory payload; assets remain private. If added inside a checksummed package, regenerate all checksums and revalidate; if added as local config after install, explicitly record installed-file divergence from release artifact.
7. Produce a candidate-bound matrix (`PASS`, `FAIL`, `BLOCKED`, `NOT_TESTED`) with logs, source + binary SHA, asset-index SHA, and distinct results for native, ARM-QEMU and physical Force. `BLOCKED` means required execution was prevented. `NOT_TESTED` means not run/not applicable to the present claim.

**Release decision:** Any FAIL in required T2 gates blocks install; investigate and rebuild, then rerun impacted T1 and full T2 on the **new** binary. QEMU `NOT_TESTED` with valid ARM ABI and a verified backup can be accepted for **controlled physical smoke**, not marketed as QEMU-tested. Missing device asset index, unverifiable backup, broken rollback, or installed hash mismatch blocks installation/restart even if desktop DSP passes.

## Required T3 evidence, by trigger

- **OS editor / raw code / DSP microprogram / firmware schedule changes:** run original-OS provenance, startup-order and exact GPR transaction matching, duplicate display bucket stepping and raw-state checks. For HALL changes to conversion/stepping, run the **128-code** sweep and relevant 40/41, 10/90, 0/99 comparisons with stimulus/clock/latency metadata. Reuse existing reference WAV hashes if unchanged.
- **Audio DSP math, clock, routing or latency changes:** deterministic impulse and noise/sweep tests, stereo/tail/A−B metrics; verify native vs actual VST2 separately; prove original hardware equivalence **only** with actual same-state device recordings.
- **UI/parameter saved-state semantics:** exercise backward chunk compatibility, reload, 64-index mappings, Q-Link touch/UI tests **on device** when available; browser success is not Force screen validation.
- **Deployment:** document real Force plugin discovery, stereo wet audio, CPU/xruns/memory, switching, bypass and restore/restart, observed UI/Q-Link; independent remote logs do not substitute for user listening.

A change to a factory package's identity or event schedule must revalidate **that package** thoroughly in T1 and all 50 slots at T2. Never assume HALL's 213 events apply to the other 49 slots.

## Test-result and skip discipline

Each result must say **what was executed, where, which exact binary and assets, and what was not**. Use this minimum record (human-readable table or JSON): `test_id`, `tier`, `scope`, `source_sha`, `native_sha256`, `arm32_sha256`, `asset_index_sha256`, `environment` (`desktop`, `qemu_arm32`, `force_device`, `research`), `status`, `command`, `result_path`, `reason` for non-PASS, and `timestamp`. Redact sensitive paths/IPs and do not commit private content.

- A skipped private-bundle test is `NOT_TESTED`, not `PASS`; report the rest of the suite separately.
- A stale QEMU report or stale 12-parameter assertion is a **provenance/contract issue**: fix the contract and retest; do not weaken the assertion by removing ABI checks.
- Never reuse an unrelated SHA result. Test caching must key on **test logic SHA + effective source/inputs + binary SHA (if binary tests) + asset index SHA + environment**. If an input changes, invalidate relevant cached gates. Archive reports without embedding proprietary audio.
- Stable historical raw measurements and SHA-256 digests are **immutable evidence**, not required to be regenerated on every build.
- **No fake time quotas:** a fast test can be lengthy on a slow machine. The tiers define scope, not hard wall-clock deadlines.

## Ownership and practical procedures

**Codex 1 — release/deployment:** T0/T1 packaging and asset-root changes, T2 final package/manifest/ARM build, physical T3 smoke and rollback. Do **not** re-run original OS-wide research on install-only patches; do not overwrite Codex 2's VST2 code. For current install, the old QEMU hash mismatch must remain NOT TESTED and asset-path config must be validated before final checksum generation.

**Codex 2 — production/editor:** T0/T1 affected VST2/runtime/UI tests during development; export real-VST-only audio artifacts with correct labels. Run T2 locally before asking Codex 3 for acceptance, but don't repeatedly run the full 50-effect gate on every UI change. No deployment while Codex 1 owns the Force.

**Codex 3 — independent QA:** Own immutable candidate-bound T2 independent callback/ABI acceptance, audio comparator and gate audit; run T3 original-OS/research tests only when original mapping or DSP changes. Reuse reference files by verified hash instead of rebuilding them. Never silently combine baseline FAIL with newer candidate PASS. No Force changes.

**Agent release handoff sequence:** Codex 2 nominates commit and binaries → Codex 3 independently verifies those exact identities → Codex 1 packages/installs the **same checked candidate** (or reruns T2 if source/binary changes) → observed Force T3 smoke → update the [master handoff](TROLLFX_ASR10_CODEX_MASTER_HANDOFF.md). Codex 1's currently authorized installation may be a **controlled hardware smoke** before a fresh independent Codex 3 report, but mark the independent gate `NOT_TESTED` and do not call it an independently accepted release.

## Implementation plan (not yet implemented)

1. Build a safe `tools/test_select.py` that computes changed paths, accepts explicit base/head, includes dirty/untracked build inputs, unions matching areas and prints required test groups with `--explain`. **Default to broader selection if uncertain**.
2. Add test IDs and a machine-readable result schema; implement `--tier T0|T1|T2|T3` with a read-only dry-run first, not automatic device deploy.
3. Deduplicate repeated native 50-slot checks: Codex 2's development run is advisory; once Codex 3's candidate-specific acceptance passes, link to the same immutable report, do not rerun it for documentation-only edits. Do rerun for any binary or asset index changes.
4. Decouple historical QEMU JSON from source digest and its presence from unconditional release failure; validate report SHA only against the exact candidate, or explicitly mark `NOT_TESTED`.
5. Add asset-pointer package tests for both **missing/wrong** and **correct existing** root, plus checkout-customized old plugin rollback test.
6. Document the test fixtures and ensure the CI default never requires proprietary assets. Full private/candidate and device tests belong in authorized local runners.

**This policy is immediately applicable as a human-readable operating procedure.** Automation is a separate, reviewable implementation task and must not be presumed functional.
