# Force Q-Link Read-Only Diagnostic Protocol

Status: design only; not built or deployed. This procedure does not authorize installation, MPC restart, or Force changes.

## Evidence in the V4.1 candidate

The V4.1 `Q-Links.json` has separate maps:

- **Screen Mode:** EDIT tab 2 maps physical Q1–Q8 to VST parameter indices 46–53.
- **Program Mode:** Q1–Q16 map to VST parameter indices 0–15.

Therefore the PC/SDK simulator driving 46–53 does not prove that a physical encoder used outside Screen Mode delivers those indices. A physical event in Program Mode follows a different mapping. This is a credible host-mode integration fault path, not yet a verified explanation for the observed Force behavior.

In `ASR10FXCollection.cpp` at V4.1, `parameterChanged()` marks router slots 46–53 changed. On the audio thread, `applyRoutedEditSlots()` resolves the active FX slot, selected bank, and edit ordinal, then sets the underlying effect-qualified control. `applyV4Controls()` later consumes the control-change flag and calls the verified backend mapping. It returns without routing if `active_slot != selected_slot`; an unavailable slot or zero-point descriptor also yields no write. The code calls `formatValue()` to return a dynamic `control label: value` string, while the parameter's static name is `EDIT SLOT N`. Whether MPC displays the formatted string as each Q-Link's live label is host-dependent and remains UNKNOWN. The JSON itself contains index maps, not dynamic labels.

## Minimal reversible instrumentation design

Build a diagnostic-only variant from the exact candidate source; keep it offline until separate deployment authorization. Do not change the Force binary or install it as part of this task.

1. Add fixed-size atomic counters/last-value snapshots at `parameterChanged(index,value)` for the eight router indices. No strings, allocation, locks, disk, or network in the callback.
2. On the existing audio thread, expose separate snapshots for: router-slot flag consumed; resolved `(effect slot, bank, ordinal, canonical parameter ID, base VST index)`; active-vs-selected slot result; backend `set_verified_*` status; exact register-write sequence/count and DSP frame.
3. Use a test-only query surface read by a host-side UI/timer thread. It reads snapshots only; it cannot mutate parameters. Include a monotonically increasing sequence number so unrelated old events cannot masquerade as the current encoder turn.
4. For audible confirmation, record finite per-channel input/output RMS and output hash over a fixed, deterministic test window in the host harness. No audio-file writes on callback. Hardware audio should be externally recorded only if separately approved.
5. Ensure diagnostic code is disabled in release builds and test that its counters do not allocate or block in the callback.

## Decision table

| Observation after one encoder detent | Diagnosis |
|---|---|
| No parameter callback counter increments | Host/Q-Link map or event-delivery issue. First verify Screen Mode EDIT and installed skin/binary hashes. |
| Callback increments, index not 46–53 (Screen EDIT path) | Wrong mode/page map, stale skin, or index mismatch. Record the received index/value; do not infer from labels. |
| Correct router index increments but router-consumed sequence does not | Plugin-side callback flag, audio callback, or state synchronization fault. |
| Router resolves wrong slot/bank/identity | Plugin-side dynamic routing defect or stale bank/effect state. |
| Correct identity resolves but active != selected or no backend write | Effect not yet active, package unavailable, or apply guard; inspect status and sequence numbers. |
| Backend reports expected register write, audio unchanged | Could be inactive/wrong register schedule, overwritten firmware event, insensitive stimulus, wet/dry setting, or no audible effect. Confirm with independent DSP register snapshot and designed input before concluding no effect. |
| Correct callback, identity, write and measurable audio delta | End-to-end evidence for this one effect/control/point only. |

## Safe manual protocol (read-only on the device)

After the diagnostic candidate has separately passed offline tests and deployment is authorized:

1. Record hashes of installed VST, `TUI.json`, `Q-Links.json`; compare to the intended diagnostic build. Preserve V1 backup untouched.
2. Open the plugin's **Screen Mode**, select EDIT, select an available verified effect/control, and note effect, bank, visible label/value, Q-Link number, and current host parameter index.
3. Turn one Q-Link by one small detent. Read the diagnostic snapshot from the host-side display, not from log files written on the audio thread.
4. Repeat in Program Mode only as a controlled comparison: expected mapping is indices 0–15, not dynamic indices 46–53. Do not infer successful control from the displayed name.
5. Restore the original value and verify the canonical parameter and register value return. Stop if an unrelated parameter changes.

No physical event was read in this QA task. Physical Q-Link delivery stays **NOT TESTED**.
