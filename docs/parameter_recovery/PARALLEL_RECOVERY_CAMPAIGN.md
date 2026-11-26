# TROLLfx ASR-10 — Parallel FX control recovery campaign

**Coordinator instruction / current priority: HIGH. Prepared 2026-11-26.** Goal: maximize **verified, audible, original-manual-consistent** parameter coverage across the 50 factory microprograms while retaining a recoverable Force plugin. **Do not interpret parameter documentation or a VST callback as a working DSP control.** No deadline promises.

## Canonical inputs to inspect in this order

1. [Manual-derived ROM-01..50 guide plus twelve additional 44 kHz effects](ASR10_MANUAL_FX_PARAMETER_GUIDE_DRAFT.md) (DRAFT; PDF source SHA-256 `e8ab5100904caf91fe355065ed9646aff197761b0663a7d452dc98af1f9a29dc`).
2. [Machine-readable draft catalog](ASR10_MANUAL_FX_PARAMETER_CATALOG_DRAFT.json). Do not treat all listed values as independently cross-checked: shared groups and printed GAIN labels may have been normalized. Numerical ranges marked `See manual` are *unknown*, not universal 0–99.
3. [Cross-agent transition index](../multi_agent_transition/00_COORDINATOR.md), [test policy](../TROLLFX_ASR10_TEST_POLICY_V1.md), [architecture audit](../TROLLFX_ASR10_ARCHITECTURE_WORKFLOW_AUDIT_V1.md), [verified manual local reference](../ASR10_MANUAL_LOCAL_REFERENCE.md).
4. [Codex 3 artificial restriction audit](https://github.com/420troll/TROLLfx-ASR10-Research/blob/0ef75e8/docs/qa-v4/ASR10_ARTIFICIAL_RESTRICTIONS_AUDIT_V1.md).
5. Source-truth for current working Force Candidate 3: source commit `d2e3105f753a10e1b5606e6aa4d35636090a1dad`, installed ARM32 SHA-256 `64cd57dca34214c57c030f21bf12c0398e2c2a6560ca7a516bdf06bf89d17d8c`, external verified rollback `/media/SSD250g/TROLLfx/ASR10/experimental-smoke-backup-c3-20261126T203250Z/TROLLfx - VST - ASR10 FX Collection`.

**Physical update supersedes device logs:** User tested Candidate 3: plugin appears, HALL audio and full 0–99 DECAY control work. Force GUI usability FAILED; only HALL decay accessible; high-frequency damping and other original HALL parameters absent. Deployment agent couldn't access locked remote screen, so its "discovery unconfirmed" is superseded by user observation. Knob-by-knob physical Q-Link response, project recall and other 49 effect audio remain unverified on this build.

## Required distinction: DSP vs UI vs manual

Keep separate evidence columns: (a) manual label/range and source page; (b) original OS 3.53 effect/variation-specific raw-state/mapping; (c) factory microprogram/startup checkpoint plus GPR/coefficients/event schedule; (d) production runtime write accepted, queued, executed; (e) exact packaged VST2 audio A/B; (f) physical Force touchscreen/Q-Link; (g) state migration/automation. **Do not mark production READY until (d) and (e) pass**; hardware status separately. Recheck original manual page before widening a control. HALL raw-state logic is not universal for every algorithm. The 50 local packages have passed a packaged desktop **playback** test; fidelity and full editability remain separate gates.

## Parallel execution plan / safe file ownership

**Coordinator:** Inspect current worktrees and uncommitted changes first. Use native spawned subagents if available; otherwise retain independent Git worktrees and explicit report/commit handoffs. Never merge entire historical divergent branches or wipe staged deletions in the primary checkout. Split the workload into independent evidence/discovery jobs with different output filenames and no overlapping source files. Allow concurrent workers but set a sensible limit based on host CPU/memory and available private fixtures.

**Agent 2 — sole product integrator:** Own production VST2 implementation and GUI source only. Preserve working HALL raw-state path, 64 ordered parameter identities, VST2 saved chunk semantics, and all 50 FX; correct GUI using only proven SDK primitives, exactly MAIN and EFFECT. Do not repeat the broken dynamic-name/visibility scheme. Develop reusable per-effect parameter mapping based on captured original OS semantics, **but avoid pretending a fixed Q-Link label can dynamically rename**. Arrange additional validated controls into the two-page constraint only after a concrete SDK-backed navigation/label design is accepted; do not exceed physical Q-Link capacity or invent third static page silently. Handle no-effect/other-effect case safely.

**Agent 3 — independent verification and original firmware evidence:** Own independent QA tests, original OS emulator capture studies and acceptance matrix. Prioritize HALL **HI FREQ DAMPING, LOW FREQ DECAY, DIFFUSION, HI FREQ BANDWIDTH, DETUNE RATE, DETUNE AMT, PRE-DELAY TIME** in addition to already-working DECAY; test original 4 variations separately. Record each complete GPR group and post-startup apply time, measured actual VST2 audio and exact hash. Previously damping 31/32 host callback/display did NOT establish executed registers or audible effect. No production source writes and no Force restart.

**Additional scoped research subagents, if environment permits:**
- **Reverb family:** ROM 01–03, 06–09, 14–24 (share only genuinely corroborated mappings; ROOM GPR5B differs from HALL; original 44k rate caveat).
- **Time/modulation family:** ROM 04–05, 10, 25–26, 33–38 and 39–41; original delay time units/ranges, regen/pan, chorus/flanger/phaser and pitch controls.
- **Dynamics/EQ/guitar family:** ROM 11–13, 27–32, 42–50; dynamics thresholds/curves, filter frequencies/Q/gains, distortion and special algorithms.
- **Appendix 44k family:** the additional 12 algorithms are a **separate inventory**; first determine presence in actual 50-slot factory packages, do not assume append-only effect slot additions or silently increase slot count.

Research workers may write **only** their own `docs/parameter_recovery/evidence_<family>.md` and `.json` plus isolated test artifacts, not production `src`, `force_plugin`, public private assets or deployment scripts. Where effects overlap family lanes, assign per-effect single owner in the coordinator's run plan, and let reviewer independently cross-check after the owner submits findings. Avoid two workers editing the same file.

**Agent 1 — deployment owner:** Hold running Candidate 3 and its verified rollbacks. Gather read-only package/device diagnostics if asked. Install only an immutable newly approved candidate after explicit user authorization, fresh backup and verified rollback. Never install to keep agents busy.

## Prioritization

**Wave A — HALL full-controls and physical GUI:** verify 8 original HALL parameters in manual, original 4 variations, DSP GPR group, measurable audio and usability. Keep current 0–99 decay working.

**Wave B — controls with existing evidence:** enumerate the 19 earlier two-point "runtime-ready" routes and all existing research snapshots. Expand a control to full manual range only where original raw/OS evidence and A/B audio support it. Research ROM 02/03 and nearby shared reverb family first, then simple DELAY/EQ/GAIN controls. Batch parameter register captures by ROM program and variation to amortize startup cost without abusing DSP.

**Wave C — broad 50-effect coverage:** research remaining families in parallel with complete evidence and prioritized integration. Avoid treating "594 documented descriptors" as 594 functioning mappings; the manual inventory duplicates shared modulation groups and may contain repeated GAIN names. Only exact original OS mapping or justified independently validated models count as faithful.

**Wave D — separate additional 44k algorithms:** investigate appendix algorithms and machine availability before assigning slot IDs.

## Measurable progress and acceptance

Maintain an authoritative `docs/parameter_recovery/RECOVERY_STATUS.json` keyed by effect slot + variation + parameter with evidence source, status enum `MANUAL_DRAFT|MANUAL_VERIFIED|OS_CAPTURED|GPR_VERIFIED|VST_INTEGRATED|VST_AUDIO_PASS|FORCE_VERIFIED|BLOCKED`, the exact binary hash, last tested commit and blocking reason. Count **unique controls confirmed to alter DSP audio**, and unique effect algorithms with >=1 verified edit. Do not count generic MOD SRC/MIN/MAX fields as working unless they truly work. Publish a short daily/wave checkpoint: confirmed effect slots, new verified control count, sampled original OS traces, test coverage, failed routes, and next bottleneck. T0/T1 focused during work, T2 once per immutable release candidate, T3 Force when genuinely ready. QA must remain independent of product integrator.

## Immediate coordinator actions

1. Fetch and read both catalog artifacts. Cross-check ROM-01–03 with original manual pages and note any catalog extraction defects before bulk generation.
2. Record Candidate 3 on Force as working HALL decay but failed graphical editor (user observation), preserve hash and rollback.
3. Start up to three parallel **read-only evidence** tracks plus Agent 2 production/editor engineering and Agent 3 independent QA, subject to actual resource availability and owner conflicts.
4. Produce the per-ROM parameter evidence coverage matrix and top ten controls with strongest evidence, with concrete original OS register-write tests. Do not block GUI redesign on manual transcription of all 50 algorithms.
5. Give Agent 2 only verified parameter mappings with exact test evidence; Agent 3 checks them independently. No autoplay deployment, no stale QEMU/manifest reuse.
6. Report first concrete batch: verified HALL missing controls, actual VST audio deltas, UI prototype screenshots or generated TUI/Q-Link validation, 50 slot playback intact, and exact candidate hashes.

## Important limitations

Public documentation alone cannot determine raw ES5510 register writes. Local proprietary manual PDF, captured program packages and checkpoints must remain private and are not uploaded to GitHub. Some manual source ranges are still `See manual`, and appendix parameter names require independent review. Original-rate processing differs: current plugin previously used `Experimental48000` for all slots, so don't claim original 29.76/44.1 kHz equivalence without testing. Full original 50-algorithm editing is research-intensive; don't invent a 48-hour completion guarantee.
