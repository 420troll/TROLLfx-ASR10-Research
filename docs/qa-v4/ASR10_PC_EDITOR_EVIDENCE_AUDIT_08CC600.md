# Independent PC Editor Evidence Audit — `08cc600`

Date: 2026-11-25
Branch: `feature/asr10-force-pc-gui-simulator`
Candidate: `08cc600` (`Integrate full factory evidence into PC editor`)

## Verification

I fetched the published branch into a detached worktree at `/home/gamer/worktrees/asr10-pc-editor-audit-08cc600`; no Codex 2 source worktree was modified.

The candidate's Python suite independently passes **27/27**. Its report states Playwright **21/21**, but an independent browser run was unavailable because the `playwright` executable is not installed; `npm run test:browser` exits 127. ARMv7 and physical Force checks remain unrun.

Confirmed from source and tests:

- 50 effect identities and the existing append-only VST registry are preserved. The generated presentation reports 895 field instances and explicitly defines this as generated fields, not distinct OS-verified controls.
- The evidence adapter is a read-only crosswalk. It retains manual, OS, and DSP evidence separately; its own role text says it is not a DSP write allowlist. No full ranges are marked implemented in the adapter.
- `parameter_registry.py` gives ROOM/PLATE algorithms the correct selected-effect domains; the 27-test suite asserts ROM-14..18 decay ranges and passed. ROM-18 predelay resolves to 0–430 ms. Four controls in the manual correction list remain DSP-unmapped.
- Only exact entries in the stable native VST route table can call the VST host. The server requires an exact supported point and native variation 1; unmatched values remain PC drafts and send no VST parameter or register write. The 19 pre-existing native routes and canonical IDs are unchanged.
- Draft state is keyed by effect slot and variation, and import migration orphans unknown identities instead of applying them. Non-native variations remain pending and do not route to DSP.
- The original OS monitor panel performs localhost `GET /api/status` and `GET /api/events` reads. It sends no front-panel or DSP events. The event cursor is local simulator state only; the adapter and panel do not write to or synthesize changes in the reference emulator.

## Specific findings for Codex 2

1. The resolved runtime/editor registry has the correct ROOM/PLATE domains, but the serialized `ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json` retains template labels such as `DECAY TIME Small Room` and `DECAY TIME Small Plate` for the shared descriptors. The per-effect runtime normalizer repairs the displayed ranges, but consumers of the serialized schema or evidence adapter can still see a false small-effect label/domain. Make the canonical schema effect-specific or represent all range variants explicitly with citations, then generate both editor and adapter views from that single normalized representation.
2. Preserve the current distinction between the 594 source descriptors and expanded generated fields. Do not call 895/907 field instances distinct original OS controls.
3. Keep nonlinear envelope values 6–9 hidden or explicitly manual-only. Five values are OS-observed; the latest branch's browser/unit coverage now reflects that distinction.
4. Keep unknown modulation destinations and direct-edit lockout behavior uneditable until effect/variation-specific OS evidence is present.
5. Do not enable the new HALL stateful 0–99 stepper as a normal native VST route until its temporal write behavior and full-range audio are gated. It is not in the current 19-route registry.

## Result

**PASS:** evidence separation, effect-specific resolved ranges, stable VST identities, exact-point write authorization, variation draft isolation, unsupported-value no-write behavior, read-only OS monitor source path, Python tests.

**PARTIAL:** serialized source-schema label/range provenance for ROM-15/16/18 and ROM-18 predelay is stale even though the runtime editor registry resolves those ranges correctly; Playwright was branch-reported but not rerun here.

**NOT TESTED:** physical Force UI/Q-Link integration, ARMv7 build, actual device event path, full factory audio equivalence.
