# TROLLfx ASR-10 FX Collection — Codex master handoff

**Snapshot:** 2026-11-26. **Purpose:** one public-safe, cross-agent index of verified status, source evidence, unresolved gates, and immediate ownership. **This is not an installation success report or release certificate.** Check current branch heads and device logs before acting; update this page when evidence changes.

## Testing protocol (current)

**All Codex agents must read [TEST POLICY V1](TROLLFX_ASR10_TEST_POLICY_V1.md) and [TEST MATRIX V1](TROLLFX_ASR10_TEST_MATRIX_V1.json) before their next test or release run.** This replaces the informal expectation to run every suite on every change: use T0 quick, change-selected T1, hash-bound T2 for release candidates, and triggered T3 for deep OS/DSP research or real Force operation. The JSON matrix is a policy specification only; automatic selection has not yet been implemented. Never treat an older QEMU result or an unconfigured skipped test as a new candidate PASS. The in-progress Codex 1 installation must still enforce binary checksums, device-local asset path validity and rollback.

## 1. Branch baselines and ownership

| Owner | Branch | Verified snapshot commit | Assignment |
|---|---|---|---|
| Codex 1 | `research/asr10-full-factory-parameter-recovery` | `64d893f` | Original OS/HALL evidence; currently preparing/installing Force candidate, hardware/restart/rollback owner |
| Codex 2 | `feature/asr10-force-pc-gui-simulator` | `e5bdee2` (VST2 implementation `9ef73e6`) | Actual FX Collection VST2; desktop editor/AUDIO LAB; V1.1 full-range editor |
| Codex 3 | `qa/asr10-v4-gui-independent` | `b800d78` | Independent VST2 callback/ABI acceptance, audio comparator, release gates |

The branches are **not interchangeable**: some research worktrees have an older/stub `force_plugin/src/ASR10FXCollection.cpp`. Do not replace Codex 2's integrated source with that file. The original ASR-10 emulator **VST3** is separate from the **Akai Force FX Collection VST2**. The goal of this handoff is to coordinate, not merge whole branches.

## 2. Authoritative current evidence

Read these reports by exact immutable commit; reports on other branches and earlier releases can describe different realities.

- [Codex 2 actual VST2 factory-runtime integration](https://github.com/420troll/TROLLfx-ASR10-Research/blob/e5bdee2/docs/ASR10_VST2_FACTORY_RUNTIME_INTEGRATION_V1.md): actual callbacks, 40/41 audio, corrected startup, nonfinite fixes, binary hashes, candidate-specific limits.
- [Codex 1 original OS HALL raw editor state](https://github.com/420troll/TROLLfx-ASR10-Research/blob/64d893f/docs/ASR10_HALL_EDITOR_RAW_STATE_PROVENANCE_V1.md): CPU addresses and GPR values, post-RUN startup, duplicate raw-code behavior.
- [Codex 3 independent VST2 QA and baseline](https://github.com/420troll/TROLLfx-ASR10-Research/blob/b800d78/docs/qa-v4/ASR10_VST2_INDEPENDENT_ACCEPTANCE_V1.md): callback harness, its outdated 12-parameter assertion, older baseline nonfinite failures, comparator.
- [Codex 3 full HALL audio artifacts and provenance](https://github.com/420troll/TROLLfx-ASR10-Research/blob/b800d78/docs/qa-v4/ASR10_HALL_AUDIO_LAB_EXPORT_V1.md); [Codex 2 AUDIO LAB](https://github.com/420troll/TROLLfx-ASR10-Research/blob/e5bdee2/docs/force_simulator/HALL_AUDIO_COMPARISON_LAB_V1.md).
- [Unmatched parameter evidence inventory](https://github.com/420troll/TROLLfx-ASR10-Research/blob/b800d78/docs/qa-v4/ASR10_PARAMETER_EVIDENCE_MISMATCH_INVENTORY_V1.json).
- [Older Force package/install/rollback instructions](https://github.com/420troll/TROLLfx-ASR10-Research/blob/e5bdee2/docs/ASR10_FORCE_RELEASE_VERIFICATION_V1.md) — **historical de708d2 release**, not automatic approval of the new candidate.

**Stale-document warnings:** `docs/TROLLFX_ASR10_FORCE_50_INTEGRATION_RC.md` says an older unconnected/stub backend was not playable; this does **not** describe later integrated `9ef73e6`. Codex 3's `b800d78` baseline FAIL for NaN and BLOCKED candidate audio predates the new integration and is not a failure report about the new candidate. Conversely, Codex 2's locally adjusted independent harness is **not** a fresh independent acceptance by Codex 3.

## 3. What is verified (and at what boundary)

### Original OS / native runtime

- Original OS 3.53 HALL REVERB Variation 1 editor raw byte `0x34` = **52**, displayed DECAY TIME **40**. OS parameter structure seen at `A6=0x2A6ED`, byte at `A6+0`, step routine `0xF8AE98`. Variation 2 was separately observed at `A6=0x2A6FB`, raw 0; **same-session 1→2→1 return and saved-state restoration were not demonstrated**.
- HALL validated 89-word program has **213** scheduled firmware writes; terminal event at DSP frame **12,983**, first safe editor step **12,984**. These are **specific to HALL**, not universal for all 50 algorithms.
- After startup the runtime accepts the HALL editor state only when the **entire** GPR tuple `6E / 5B / 03 / 04 / 05` matches an OS-observed group. It never seeds from checkpoint GPR6E alone; partial matches fail closed.
- Raw **51** and **52** both display **40**; original stepping must preserve separate states. Initial factory Variation 1 raw is **52**.
- ROOM Variation 1 shares observed raw stepping and GPR03/04/05 conversions, **but GPR5B differs**. Do not reuse the whole HALL register conversion for ROOM.
- Standalone HALL comparison WAVs and four AUDIO LAB bundles passed independent hash/measurement/playback checks. “Factory-reference” denotes **processing-rate mode** (measured 29,761.89453125 Hz); there is **no original physical ASR-10 same-state audio reference** in this acceptance.

### Actual FX Collection VST2 — Codex 2 integration `9ef73e6`

- Real `VSTPluginMain`, `setParameter`, and `processReplacing` callback path now reaches active `FactoryRuntime`.
- HALL 40/41 yields **nonzero VST2 audio delta**, verified via actual callbacks; 10/90 and 0/99 comparisons use **test-only** raw overrides and match standalone reference measures in stated test conditions. Test-only controls are **not** permission to expose production full-range writes.
- The newer VST2 candidate rejects NaN/±Inf parameter values without mutation and sanitizes nonfinite audio. Older QA-baseline failures are real for the old baseline, but **new candidate's fixes passed Codex 2's adjusted harness**. Codex 3 still needs an independent, candidate-bound rerun.
- Current editor VST2 API has **64 host parameters**, not 12; the older Codex 3 harness expects 12. Update by validating **identities, order, names/IDs, and saved chunk semantics**, not just changing a constant. The `19 verified control routes` are not a count of VST host parameters.
- SDK-produced x86-64, ARMv7 hard-float, and AArch64 binaries and ABI checks passed. Integration report lists candidate SHA-256: native `dd5f964ecc8f856ece67793a8154e1881a50a9f465f292144a1725bf41782e26`; ARMv7 `4af2be5d75515c89e83be798e2133cd60bc9640a5dcd26b48c5d2ef1d027868f`; ARM64 `2b99e3f7d9dd21d23adc3331231ddf407981b61f231b267422e0ca897a6ef105`. **Historical build hashes only; re-hash whatever is actually packaged and installed.**
- Desktop VST2 all-50 package smoke, stereo finite audio, chunk checks, effect switching, nonfinite checks, and zero callback allocations passed in the adjusted candidate test. This **does not** establish physical Force performance, original-effect accuracy, or arbitrary-parameter equivalence.

## 4. Urgent deployment lessons — Codex 1 current install

Codex 1 reported: a new source build passed HALL/ROOM/ROM-02 backend and 50-slot desktop binary checks; it found (a) a checked-in QEMU PASS report for **a different ARM binary** and unavailable QEMU on this machine, and (b) missing reference to the Force's **existing private asset directory** in the deployment package. This was reported **before installation**. These are release-metadata and asset-discovery issues, not new evidence of DSP failure.

**QEMU binding rule:** `force_plugin/dist/.../release-manifest.json` on Codex 2's published branch is historical and contains a `arm32_qemu_validation: PASS` for ARM SHA `badefa8...`, whereas the newer integrated VST report lists ARM SHA `4af2be5...`. Do **not** transplant that PASS to a differently hashed candidate. For the freshly built ARM32 hash, record QEMU **NOT RUN / NOT TESTED** (and reason). Never falsely change a hash to make reports match. A previous build's QEMU result can be retained as explicitly historical evidence, but must not gate the new binary as passed.

**Factory asset discovery (verified in `force_plugin/src/ES5510FactoryPackageProvider.cpp` on `e5bdee2`):**

1. `TROLLFX_FACTORY_PACKAGES_DIR` environment variable, if non-empty.
2. `factory-assets-path.txt` in the **plugin package root** (the code computes plugin_dir from the binary's parent, then parent again), first nonempty line; an absolute path is accepted, or a relative path resolved against plugin package root.
3. Otherwise package-root `FactoryAssets` directory.

The provider **fails closed** when assets/index are absent or invalid. It reads `provider-index.tsv` and verifies referenced files and SHA-256. Therefore Codex 1 must inspect the **real on-Force existing asset directory**, ensure readable `provider-index.tsv` plus all 50 valid entries and referenced files, and write the correct absolute (or carefully resolved relative) path. **Do not guess the existing directory from old WSL paths, copy private assets into Git, replace or erase the current assets, or assume asset-index compatibility without validation.** Existing assets may require the trusted importer/preparation step if schema differs; handle that as a distinct approved local transformation, preserving originals.

**Installer integrity caveat:** `force_plugin/tools/install_package.py` requires the package file inventory to match `SHA256SUMS` **exactly** and uses a binary-bound `INTEGRATION_STATUS` playable marker. Adding `factory-assets-path.txt` inside the packaged directory **after** generating sums will invalidate that inventory. Options: create path reference **before final checksums/manifest packaging**, with the matching verification pipeline, **or** install an already validated package first and add a local machine-specific reference outside the verified release artifact, explicitly logging that local configuration and confirming loader behavior. When replacing an existing installation, note that the current installer's `verify(target)` can refuse an old customized folder: **do not force-delete it**; use a separate complete verified backup/installer plan. A symlink may also be rejected by installer package verification, so prefer a regular UTF-8 text config file.

**Before/after restart:** verify live Force hardware architecture, target path, disk space, plugin binary hash, library dependencies, asset directory resolution/readability, existing plugin backups **outside scanner visibility**, restoration plan, and host-not-in-active-show. User authorized install/restart, **not** firmware flashing or erasing unrelated projects. Restart using a device-supported method; verify reconnect, plugin discovery and actual audio after. If unavailable through remote tools, mark physical interaction **NOT TESTED** and ask for a short user observation. If a significant problem arises, restore the previous plugin and document the exact failure. No uncontrolled restart loops.

**Deployment status at this snapshot: no successful installation/restart/physical audio result has been received.** The current private live Force state cannot be inferred from GitHub.

## 5. Independent QA / release gates next

| Gate | Snapshot status | Required next evidence |
|---|---|---|
| Original HALL startup raw state / ordered GPR writes | PASS for documented package and Variation 1 | Other variations and preset return remain open |
| HALL 40/41 **actual VST2** callback audio | PASS in Codex 2 candidate | Codex 3 independent same candidate |
| NaN/±Inf and startup-race protection | PASS in Codex 2 adjusted candidate tests | Codex 3 independent unchanged binary |
| 50 local factory packages in VST2 desktop smoke | PASS in scoped tests | Force real-device representative smoke |
| Native/ARMv7/AArch64 build | PASS in Codex 2 integration report | Match new release manifest to new hashes |
| QEMU on **new** ARM binary | NOT TESTED | New binary-specific QEMU run, if available |
| Force install, restart, UI, wet output and performance | NOT YET REPORTED | Codex 1 device-bound report |
| Full-range HALL production host control | GATED | Independent V1.1 semantics, variation/saved state, state compatibility |
| Original-ASR-10 hardware audio equivalence | NOT TESTED | Genuine hardware recording with matched original state |
| Four-unit DSP rack | NOT IN THIS RELEASE | Later standalone feature project |

## 6. Immediate parallel work, no overlapping files/devices

**Codex 1 — deployment owner:** complete exact-candidate preflight; fix *asset path reference without breaking package checksums*, record QEMU as not run for new hash, preserve installer and rollback, install/restart only on verified device and non-active session, collect binary hash, scanned plugin status, asset status, stereo wet/dry, switching, CPU and observed UI results. New release report must distinguish automated checks from human-listening/physical Q-Link checks. Do not claim success without evidence.

**Codex 2 — next version V1.1, no Force access:** keep `9ef73e6` VST2 working; design full-range HALL 128-raw-state control with explicit provenance, duplicate LCD bucket behavior, original stepping, state and automation compatibility, Q-Link/editor UI; ensure 64-index stable ABI/serialization. Keep unsupported variation and saved-preset transitions fail closed, production full-range gate disabled until acceptance. Generate actual VST2-only audio artifacts with correct source label. Publish tests and migration/gating plan, **do not deploy**.

**Codex 3 — independent candidate QA, no Force access:** update stale 12-parameter harness to verify exact 64-slot ABI rather than weaken; rebuild/rerun candidate-specific VST2 callback and nonfinite tests; independently verify raw states, GPR writes, audio, state restoration, 50 slots and hashes. Expand CPU/algorithm test matrix and independent full-range HALL test only on evidence-supported routes. Publish PASS/FAIL/BLOCKED matrix tied to source+binary hashes. Do **not** modify Codex 2 implementation or the Force.

## 7. Next phases / planning only

These are **rough planning estimates**, not CI measurement, and must not be used as release evidence: V1.0 Force stable install ~85% before physical result; V1.1 full-range HALL ~70% research+test foundation but **production gated**; V1.2 ROOM/PLATE/DELAY control ~35%; V1.3 50-effect GUI ~40% (many GUI fields drafts); V1.4 original modulation/presets ~20%; V2.0 separate four-unit rack ~25% (prior research only); V2.1 physical accuracy/performance ~20% (desktop validation only). These stages overlap; percentages are not additive. Recalculate as real Force evidence arrives.

Parameter inventory: **594 manual descriptors**, **1,040 OS field associations**, **94 unmatched manual rows** (6 composite-heading evidence, 20 naming/range candidates, 68 unresolved), **500 unlinked OS associations**. These are **different accounting populations** and not percentages of verified DSP controls. Priority research: NLIN REVRB `ENV LEV`, PLATE `ER LEV`, ROOM/HALL `POSITN BAL`, HALL `BUS1 MIXMOD`. One-to-one label similarity is not proof of a DSP mapping.

## 8. Handoff update protocol

When an agent finishes, append or revise **this single page** with: date, owner, branch+full source SHA, build package SHA, pass/fail/blocked evidence links, physical-device observations (if any), newly discovered blockers, and the next ownership boundary. Do not replace proven reports or turn historical PASS into current PASS. Agents working on separate branches should fetch this page from **`main`** explicitly. Changes to this document are coordination-only and should not merge plugin code across branches.

**Privacy:** Keep original ASR-10 ROMs/OS, proprietary factory payloads, local private assets, WAVs, credentials, and device IPs outside Git. Publish only vetted hashes, nonprivate evidence descriptions, tests, and reproducible instructions.
