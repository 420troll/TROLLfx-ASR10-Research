# ROM-01 HALL timeline and replay-state reconciliation

This report uses the two private fresh-boot event captures from 2026-11-23 20:20 UTC and 20:40 UTC and the externally held replay manifest. Private payloads and captures remain outside Git. `tools/audio_validation/hall_timeline.py` produces a redacted event table and state-gate diagnostic; its CLI first requires the unchanged replay-ready manifest validator, and its default checkpoint is the manifest's exact `RUN_SNAPSHOT` frame.

## Selected transaction timeline

The selected checkpoint is DSP frame **855,973**, snapshot event 97683 in the 20:40 trace. All coordinates below are from the ordered host event CSV; CPU cycles are the MC68302 counter, and DSP frame is the ES5510 scheduler frame.

| Event | Event ID | CPU cycles | DSP frame | Evidence |
|---|---:|---:|---:|---|
| PA4 HALT | 91467 | 420,614,232 | 854,142 | Firmware asserts HALT |
| Pipeline reset | 91470 | 420,614,232 | 854,142 | Pipeline clear acknowledged |
| DRAM clear | 91478 | 420,614,390 | 854,143 | 1,048,576 words |
| First instruction upload commit | 94514 | 421,228,220 | 855,284 | First instruction commit in this transaction |
| Program upload complete | 95826 | 421,309,626 | 855,436 | 89 active words, END at word 88 |
| PA4 RUN release | 97679 | 421,550,288 | 855,972 | Firmware releases HALT |
| DSP_RUN | 97682 | 421,550,328 | 855,973 | RUN event, PC 0 |
| Manifest checkpoint | 97683 | 421,550,328 | 855,973 | `RUN_SNAPSHOT`; snapshot hash matches manifest |
| First input frame | 97684 | 421,550,328 | 855,973 | First `AUDIO_PRE` row |
| First frame end | 97685 | 421,550,328 | 855,973 | `DSP_FIRST_END` row |

The event CSV has no separate first-instruction-start row. The selected snapshot reports PC 0, and the HALL boundary report establishes that execution starts at PC 0 in the same RUN frame. The visualizer reports this coordinate as inferred from those two observations, not as a separate event.

## Does the boundary explain the 23 mismatches?

The manifest says its register payload is captured after `DSP_RUN` and before the first instruction. Its snapshot file hash is exactly the same as the event's `RUN_SNAPSHOT` file. `RUN_SNAPSHOT` immediately follows `DSP_RUN`; both have the same CPU cycle and DSP frame, and both precede `AUDIO_PRE`. The 342 halted GPR/SPR commits and 89 instruction commits occur before RUN. Re-running the guarded replay still fails its existing full-state check: **16 GPRs and 7 SPRs differ**. The native and MAME executors were not started by this guarded run.

The count breaks down as follows, using register indexes only; register values are withheld:

- GPR 144–159 and SPR 238, 239, 243, 248, 249, and 250 are absent from the halted commit write set. The replay reconstruction starts these unwritten locations at zero, so its input history does not establish their values at the checkpoint.
- The 16 mismatching GPRs 144–159 match the preceding private RUN snapshot, and all 192 GPRs match between that snapshot and the selected HALL checkpoint. This supports inherited GPR state as the cause of those 16 differences; it does not prove the state immediately after HALT because the preceding snapshot is earlier than the HALL load.
- SPR 244 is the only mismatching register touched by a halted commit. Six other mismatching SPRs are not touched by that commit stream. The available trace does not establish whether their differences came from the HALT/pipeline-reset transition or another checkpoint phase. This leaves an unresolved SPR initialization/timing issue.

The boundary hypothesis therefore does **not** explain the mismatch as a simple off-by-one checkpoint selection. The chosen checkpoint is the documented RUN boundary, and its snapshot hash is verified. Most of the mismatch is caused by comparing a partial halted write stream applied to a zero baseline with a checkpoint that retains state. The one touched SPR mismatch and six uncommitted SPR mismatches still need state provenance before a replay correction is justified. No register values are patched.

## Post-RUN activity and fresh-boot repeatability

The full 20:40 event log records 213 later host register commits after `RUN_SNAPSHOT`; none targets the 23 mismatching addresses. Its bounded 256-frame replay-update stream contains 87 updates, all to GPR 0x7f. Those updates are scheduled after the first HALL input/process frame, so they cannot account for values already present in the pre-first-frame snapshot. DSP execution changes live pipeline/serial state after that checkpoint, but this capture does not provide an intermediate register snapshot to attribute the six uncommitted SPR differences to a specific instruction or lifecycle event.

Both independent fresh-boot event captures select frame 855,973 and have the same snapshot SHA-256 (`a7c4196bd74d0d7d1d28f474620c081ec790b1c912aefd7a732c0ffc555e661d`), ordered instruction-commit fingerprint (`d35a7cc732b11eb2fb39330bb228caef64faf28e7ae21d51b9a85a676c92b8d7`), and ordered GPR/SPR-commit fingerprint (`b1861befe6c92828d969fb1512947fa2e61505bcf2b8c50e30e26a762143ef9d`). The event IDs differ by 11 at HALT and 12 by the RUN/checkpoint rows because of logging-row differences; cycle/frame coordinates, payload fingerprints, and checkpoint state agree. The selected state comparison reports the same 16 GPR / 7 SPR mismatch in both captures.

No published HALL-specific GPR/SPR reconciliation finding was present in the dependency branches. The published parameter mapping validates a `44PARAM EQ` control at GPR 0x56 and does not apply to these HALL registers, so it is not used to explain or modify the HALL state.

## Guarded replay and blocker

The strict command was rerun with the private manifest and ordered host event log. The manifest validator passes, then `replay_hall.py` stops before engine execution with: `ordered commits disagree with final payloads at 16 GPRs and 7 SPRs`. No correction is safe from the available trace, so the strict gate remains unchanged. The independent audio verifier was not run because the state gate did not pass; no HALL sample-exactness claim is made.

A separate pre-existing private directory contains an engine-comparison CSV and a summary claiming 90,000 compared frames and 213 ordered updates. Those figures do not match this manifest's guarded 256-frame / 87-update stream, and the current `replay_hall.py` invocation cannot produce that artifact because it stops at the state gate. That output is therefore not accepted as a guarded replay result and is not used to claim an OS/native/MAME match or mismatch.

The earliest remaining blocker is a complete, capture-backed initial register state at the HALL HALT boundary (including untouched GPRs and the SPR lifecycle state), or enough ordered pre-HALT and reset events to reconstruct it. Once that state passes the unchanged replay gate, run the independent native/MAME/OS serial comparison and the separate 44.1 kHz host-output verification.

## Reproduce the redacted timeline

```sh
python3 tools/audio_validation/hall_timeline.py \
  /private/asr10/hall/factory-state.json \
  --events /private/asr10/hall/events.csv \
  --prior-capture /private/asr10/hall/prior-run.esp \
  --output /private/results/hall-timeline.json
```

`--checkpoint-frame` can select another logged RUN frame for diagnostics. A frame that does not match the manifest's snapshot frame is rejected before state comparison. The existing `replay_hall.py` full-state gate is unchanged.
