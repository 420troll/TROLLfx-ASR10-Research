# ASR-10 V4 GUI and Q-Link acceptance

Use this gate on the exact candidate source tree, generated SDK skin, and binary. V4 is currently **pending**: Codex 2's candidate branch has not yet been published in the available remote refs. No V4 PASS is recorded here.

## Desktop pre-deployment gate

1. Record candidate branch, commit, binary SHA-256, package manifest SHA-256, SDK revision and ARMv7 ABI report.
2. Run `inspect_skin.py` against authored `ui.json`, generated `TUI.json`, `Q-Links.json`, skin assets and actual host parameter descriptors. Fail on missing handles, invalid indices, unintended duplicate bindings, out-of-bounds widgets, missing artwork or effect/Q-Link assignment mismatches. Treat approximate text warnings as requiring screenshot review.
3. Produce an SDK-rendered screenshot for every BROWSE, EDIT, EDIT 2 and MIX state if an actual SDK renderer exists. Label all non-SDK renders approximate. Review long labels at the real Force display scale and confirm no text/control/background collisions.
4. Compare authored visibility predicates with physical Q-Link maps for every active effect and all banks. A hidden control must not leave its old assignment/label active. Verify EDIT versus EDIT 2 selection and Q-Link bank direction on device.
5. Run the independent binary-bound parameter harness. For every available control, select effect, page and bank; actuate Q-Link; collect the gate schema in `tools/force_gui_qa/validate_qlink_trace.py`; prove host event, internal state delta, intended ordered register write delta, unrelated-state invariance, reverse restoration, repeated values, save/reload, and unavailable behavior. Host parameter round-trip alone is insufficient.
6. For every mapped control, test both verified discrete points and the no-write sentinel. Test values repeated without change, effect-switch-away/back, and project-state save/reload. Do not extrapolate unverified ranges.
7. Regenerate the 50-effect/manual-parameter matrix from public catalog and current runtime/editor data. A control gets runtime-ready only with a validated descriptor and passing runtime evidence; it gets audio verified only with a measured output difference; it gets Force verified only with physical evidence.
8. Validate all 50 package identities and playback remains PASS from the existing package gates, but keep that independent from GUI/Q-Link status.

Required result: no unexplained static Q-Link assignment for conditionally hidden controls, zero mapping collisions, readable rendered labels, and binary-bound end-to-end control evidence. Anything unavailable or unobserved remains NOT TESTED. Do not copy V3's playable marker to a changed binary.

## V3 baseline machine result

`qa-v3/v3-v4-acceptance-matrix.csv` has 50 effect rows plus all 19 available V3 control rows. It identifies all 19 conditional/static Q-Link assignments as FAIL, the physical parameter path as NOT TESTED, and V4 as pending. Thirty-seven V3 slots have no verified effect-specific controls; this records a coverage gap, not proof that controls should be exposed without recovery evidence.

## Physical Force procedure

Use a non-production project and keep the installed V3 untouched until all release gates pass and the user authorizes replacement. Keep the accepted rollback at `/media/SSD250g/TROLLfx/ASR10/rollback-v1-20261125/` and both plugin and assets on `/media/SSD250g`.

1. Photograph or capture the existing plugin identity and version. Open plugin, then verify BROWSE, EDIT, EDIT 2 and MIX are selectable and readable at actual screen scale.
2. Select **HALL REVERB**. Confirm the displayed active identity, visible HALL-only controls and all Q-Link labels. Move each available Q-Link through the two documented points and `UNCHANGED`; capture label, host event evidence and the resulting register group.
3. Select **ROOM REVERB**. Check that HALL BUS/decay controls are removed or reassigned, and ROOM controls are shown with matching Q-Link labels. Confirm no stale HALL assignment remains.
4. Select **FLANGER+REV**. Confirm FLANGE RATE is shown in its assigned page/bank, change both verified points, and confirm the expected writes. Keep the distinction between host-display change and DSP register change.
5. Select **PITCH SHIFT**. Verify QUALITY's two labels, values and write group; verify reverse selection restores the first group exactly.
6. Run repeatable stereo audio. Compare wet enabled versus bypass at identical gain; then left-only, right-only and stereo input. Record audible/waveform results and output routing. Do not claim wet output just from a package status indicator.
7. Save the MPC project, close/reopen the project using normal host operations, and verify effect, parameters, Q-Link labels and wet output restore. Do not restart MPC as part of this QA task.
8. Run the existing read-only CPU sampler with the same session, loop, routing, buffer and gains across bypass, HALL REVERB, 8-VOICE CHOR and PITCH SHIFT. Example: `tools/force_hardware/measure_force_cpu.sh akai-force 60 1 15 v4-force-cpu.csv`. Keep the accepted V1 user snapshots (20%, 18%, 17% MPC; 80–81% idle) as historical context only. Record glitches and callback/xrun evidence separately; aggregate CPU is not deadline proof.
9. Record every observation with date, candidate hash, slot/name, page/bank/Q-Link, expected and actual label, event trace, register evidence, audio observation, CPU, save/restore result and screenshot. A field not tested physically must say NOT TESTED.

Do not write to the Force during desktop QA. Hardware deployment/replacement requires separate explicit authorization after review; do not restart MPC or alter mount settings.
