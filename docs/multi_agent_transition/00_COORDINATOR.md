# TROLLfx ASR-10 — multi-agent transition / coordinator

**Prepared 2026-11-26.** Read this document together with the three role handoffs. This is a planning snapshot, **not** evidence that independent Codex terminals have been joined, that worktrees are clean, or that a new build is approved. On startup inspect the actual running sessions, Git refs, local dirty changes and exact binary hashes before actions.

## User decisions — authoritative current direction

1. **One effect at a time**, stereo in -> single factory ES5510 effect -> stereo out. Two effects in series is a later investigation; do not implement a second DSP instance now. Investigate Force-native chaining later.
2. Exactly **two STATIC Force pages**, **MAIN** and **EFFECT**. No dynamic page switching, conditional visibility, generic EDIT SLOT routing in visible UI, decorative clutter, or visible BUS controls. Preserve original DSP BUS configuration safely underneath.
3. MAIN fixed controls: Q1 effect select (50 slots), Q2 wet/dry, Q3 input gain, Q4 output gain, subject to actual SDK mapping constraints. EFFECT starts with HALL DECAY on Q1; HI FREQ DAMPING may appear only **after real parameter-to-DSP-to-audio verification**. No fake controls; unused Q-Links remain unassigned.
4. HALL DECAY must expose the **original displayed 0–99 range**, backed by the OS-derived **128 raw codes 0–127** and five-register state groups. Raw 51/52 both display 40, raw 53 displays 41; preserve original stepping and raw-state identity. The production **40/41-only** choice was an old prototype gate, not the intended user range. However do not claim all raw codes are production-safe solely because a test instrumented render passed; validate production integration and compatibility first.
5. Manual-original behavior is the target; independent effect mappings are required. Never copy HALL's coefficient conversion uncritically to ROOM or all other controls. The 594 manual descriptors are NOT 594 implemented controls. Current V4.1 documented 19 runtime-ready mappings; that number is not a physical SDK limit either.
6. Preserve all **64 existing VST2 parameter identities, indices, and saved project chunks**. Changing two-choice enumeration semantics can corrupt old normalized states; use append-only or versioned migration after testing.
7. Aim for all **50 microprograms playable** plus a reliable minimal editor; complete accurate editing of all 594 parameters in 1–2 days is not a credible acceptance commitment.

## Current physical baseline — Codex 1 already deployed V1

Deployment branch `deploy/asr10-force-fx-collection-v1`, reported latest `1da5dd9`. Source `f58f21fc052ce143d9ec31b2b70d7e6b6cb4b40a`. Device ARM32 VST SHA-256 `4af2be5d75515c89e83be798e2133cd60bc9640a5dcd26b48c5d2ef1d027868f`. 64-entry parameter layout SHA-256 `0ee1bf05ea85f1a848ca5854cb743eb4f7b8359e2bb0e552a2fe5d7faef02ddf`. Private asset index SHA-256 `8bbb71d362529d39f94305ec5c927cb7c93477eb6cdcf627afaf90de464b8267`. Installed package at `/media/SSD250g/VST2 Plugins/TROLLfx - VST - ASR10 FX Collection`, assets at `/media/SSD250g/TROLLfx/ASR10/factory-effects`, verified external rollback at `/media/SSD250g/TROLLfx/ASR10/rollback-v1-20261126/TROLLfx - VST - ASR10 FX Collection`. Device host service `acvs.service`.

**User physical observation:** plugin discovered, HALL audio PASS, on-screen bypass PASS, on-screen gain/volumes appear to work (PROVISIONAL), screen usability FAIL (clutter and missing controls), HI FREQ DAMPING **no audible response** (not yet root-caused), available DELAY TIME span **too narrow to assess**, HALL decay limited to 40/41 in deployed editor. Individual physical Q-Link knob movement **not conclusively observed**; distinguish touchscreen testing from knob testing. Project recall, other effects and CPU/xrun performance untested.

Packaged native all-50 playback passes, package integrity and rollback hashes pass. Independent exact-candidate 64-param/NaN tests remain **UNVERIFIED** because the successful rebuild hash differed. Temporary ARM harness crashed before test assertions; that is not a demonstrated crash of the live plugin. QEMU unavailable for candidate. Release remains **experimental hardware smoke, NOT fully accepted**.

Authoritative device report: [ASR10_FORCE_HARDWARE_DEPLOYMENT_V1](https://github.com/420troll/TROLLfx-ASR10-Research/blob/deploy/asr10-force-fx-collection-v1/docs/ASR10_FORCE_HARDWARE_DEPLOYMENT_V1.md).

## Agents and ownership

- **Agent 1 — deployment and recovery.** Owns live Force, release packaging checks, checksum-verifiable backup, install/rollback, host restart and device-bound report. **Idle until new QA-approved exact candidate and explicit user approval.** Never infer approval from a changed branch head.
- **Agent 2 — implementation.** Owns VST2 `force_plugin/src/*`, editor source `force_plugin/ui.json`, generated UI maps, DSP control integration and compatibility migration. No Force installation.
- **Agent 3 — independent QA and restriction audit.** Owns QA source, independent exact-binary tests and reports, manual-vs-production evidence matrix, fault reproduction; no silent product changes or Force installation.
- **Coordinator — handoffs and gating.** Tracks owners, commits, asset-index hashes, candidate digest and statuses, resolves conflicts, commissions only the required T0/T1/T2/T3 checks and requests user approval before live install.

Existing main docs: [master handoff](../TROLLFX_ASR10_CODEX_MASTER_HANDOFF.md), [test policy](../TROLLFX_ASR10_TEST_POLICY_V1.md), [matrix](../TROLLFX_ASR10_TEST_MATRIX_V1.json), [architecture audit](../TROLLFX_ASR10_ARCHITECTURE_WORKFLOW_AUDIT_V1.md), [manual reference](../ASR10_MANUAL_LOCAL_REFERENCE.md). The master handoff's older "not yet installed" paragraph was superseded by the above physical report. Do not promote obsolete statements.

## Non-destructive transition protocol

1. Ask each existing session to finish/stop at a checkpoint, report `pwd`, `git status --short`, branch, HEAD, uncommitted files, generated outputs, tests and pending tasks; save the Codex conversation/session ID. A new parent session cannot automatically inherit all transcript state from three old independent sessions.
2. List all worktrees and branch heads. Preserve local uncommitted modifications. Do not reset, clean, rebase or merge whole diverged branches; do not overwrite implementation from an older/stub research branch.
3. Coordinator creates three delegated tasks with **explicit file ownership** and separated worktrees. Read the exact role handoff first. Verify native multi-agent/subagent feature availability in the installed Codex build; if unavailable, implement documented handoff protocol in a single coordinator session instead.
4. Candidate handoff: Agent 2 publishes source commit, full parameter-layout hash, asset-index hash, native/ARM package hashes, generated skin verification, test list and the **single immutable candidate location**. Agent 3 tests precisely that candidate, publishes PASS/FAIL/BLOCKED/NOT_TESTED and its own unchanged-hash verification. Coordinator compares identities and accepts/rejects. Agent 1 remains idle unless exact QA approval plus explicit user's install authorization; when authorized it rechecks live preflight, stages rollback and installs exact accepted package.
5. Communication can be through parent-agent messages and committed handoff documents. Independent tmux Codex sessions do NOT automatically talk or wake. No unattended watcher or automatic deployment exists unless explicitly built and confirmed.

## Test discipline and stop conditions

T0 quick changed-file checks; T1 targeted UI/state/register/audio tests; T2 once per immutable full candidate (all 50, ABI 64 identities/chunks, nonfinite, allocations, switching, build/SDK checksums, package/asset index/rollback); T3 original OS and physical Force only when needed. Simulator/UI JSON success is not physical Q-Link verification. No stale QEMU hash promotion. Keep private ROMs, checkpoints, factory assets and copyrighted manual PDF OUT of public repo.

Stop and escalate if exact package hashes fail, assets cannot be resolved, ABI/saved-state identities change without migration, active effect receives incorrect writes, worker switch races corrupt state, or rollback cannot be verified.

## Roles

- [Agent 1 deployment](01_DEPLOYMENT.md)
- [Agent 2 implementation](02_DEVELOPMENT.md)
- [Agent 3 independent QA](03_QA.md)
