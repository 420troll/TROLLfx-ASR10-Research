# ES5510 factory HALL replay V2

## Result

The isolated branch is based on the verified replay V1 branch and incorporates the evidence-backed prior-history GPR correction. Remote refs were fetched and inspected before work began: load-boundary `bad3f817`, replay V1 `61e1189`, audio verification `9c074eb`, Ghidra loader analysis `d199d23`, SPR/REA analysis `8b39889`, GPR reconciliation `c065a06`, timeline reconciliation `e63dd1c`, and first-divergence analysis `e95d6e9`. The GPR, timeline, and first-divergence refs existed remotely; their commit IDs were verified rather than inferred.

The value-bearing 23-register JSON table was generated outside Git at:

`/home/gamer/research/private-results/asr10-hall-reconciliation-20261123T220000Z/register-reconciliation-v2.private.json`

It contains expected manifest values, transaction-only and complete recorded-history reconstructions, last recorded write coordinates, the execution boundary, hardware-update notes, evidence, and resolution status. Rebuild it with `tools/audio_validation/build_hall_register_reconciliation.py`; the tool rejects output paths inside the checkout. The existing manifest validator and replay-ready requirement were not changed.

| Register group | Differences resolved | Remaining at checkpoint | Finding |
|---|---:|---:|---|
| GPR `0x90`–`0x9f` | 16 | 0 | Earlier halted `BOTH_COMMIT` writes from the same boot persist across the HALL HALT and pipeline reset. Two fresh OS 3.53 captures agree, and full ordered host history reproduces all 192 GPRs. The active HALL program has no operands in this range. Their narrower purpose is not established. |
| SPRs in the original seven-register discrepancy set | 1 | 6 | The startup SIGREG write is present in recorded history. SER2R/L, MACH, DIL/readback, DBASE, and CCR still disagree with transaction-only replay at the manifest checkpoint. Their roles are runtime or retained state, rather than six absent HALL loader writes. |

The capture-derived private table uses each SPR’s true offset from address `0xEA`; the symbolic names and values are not rewritten into the replay image to force a match. The six remaining SPR differences are SER2R, SER2L, MACH, DIL/readback, DBASE, and CCR.

## Verified execution sequence

The timeline reconciliation and selected private event trace establish these measured coordinates:

| Event | Host cycles | DSP frame | PC / evidence |
|---|---:|---:|---|
| PA4 HALT and pipeline reset | 420,614,232 | 854,142 | `FFF977B8`; pending pipeline results discarded and pipeline slots cleared |
| DRAM clear | 420,614,390 | 854,143 | `FFF9775C`; one-megaword clear while halted |
| First instruction upload commit | 421,228,220 | 855,284 | `FFF97792` |
| 89-word program complete | 421,309,626 | 855,436 | 89 distinct instruction words, END at word 88 |
| PA4 RUN release | 421,550,288 | 855,972 | `FFF977C6` |
| DSP_RUN and RUN_SNAPSHOT | 421,550,328 | 855,973 | `FFF977D2`; manifest snapshot follows RUN in event order |
| AUDIO_PRE and first frame end | 421,550,328 | 855,973 | Both are logged after RUN_SNAPSHOT; no separate first-instruction event is present |

The verified halted transaction contains 342 GPR/SPR commits and 89 instruction commits. The trace records 213 later register/instruction commits overall; the bounded replay stream contains 87 updates, all to GPR `0x7f`. The trace ordering is exact for recorded events; it does not provide an instruction-cycle timestamp for the first DSP instruction.

The private snapshot stores the first `0xE90D` sample in SER2R and SER2L. Its `RUN_SNAPSHOT` event precedes `AUDIO_PRE` in the event log, so that log alone cannot establish whether the serial latches were updated before the snapshot. The standalone `Asr10::otto_frame` path writes serial inputs before calling `run_frame`, but that implementation ordering is not proof of the historical MAME capture instrumentation edge. The patched capture instrumentation source is not available in the local MAME source checkout. The latch boundary therefore remains unresolved; no event ordering was invented.

The private trace and REA/Ghidra analysis identify the six SPR discrepancies as live or retained state: MACH is the MAC high word, DIL is a live delayed-memory input readback despite writes to SPR index `0xF4` configuring memory, DBASE advances as delay memory executes, SIGREG is startup configuration, and CCR is live condition state. The available trace does not identify the prior DSP producer for MACH or CCR. These meanings are corroborated by native and MAME-derived implementation behavior, not direct silicon measurements.

## Replay and audio status

The strict replay attempt was run against the private tail capture. Its state gate stopped before engine execution with **0 GPR mismatches and 6 SPR mismatches**. Accordingly:

- The state gate did not pass.
- Authentic standalone HALL execution was not reached in either engine.
- Native versus MAME-derived serial output comparison was not run.
- OS 3.53 sample-for-sample audio comparison was not valid and was not run.
- There is no verified DSP audio divergence yet. The earliest verified blocker is the six-register checkpoint mismatch, with the earliest causal timing uncertainty at the frame-855973 SER2 input/snapshot edge.

This stop preserves the verifier's state, input, clock, and alignment requirements. The internal DSP clock is 29,761.89453125 Hz; host audio is 44,100 Hz. A host WAV frame must not be compared directly to a DSP serial frame without the verifier's fixed clock mapping and matching initial state, ordered updates, input, and alignment. The independent audio verification utilities from `research/es5510-hall-audio-verification` remain gated until those preconditions hold. No impulse, sine, sweep, noise, or stereo result is claimed.

## REA/Ghidra integration

The SPR analysis uses the corrected interleaved hi/lo boot-ROM import as big-endian 68000 at `FFF80000`, length `0x40000`; runtime `FFFxxxxx` PCs map by subtracting `FFF80000`. This corrected the earlier analysis that had imported the OS floppy payload at the ROM base. The static decode supports the HALT helper (`FFF977B8`), DRAM-clear path (`FFF9775C`), shared upload helper (`FFF97792`), and RUN release (`FFF977C6`/`FFF977D2`). Some shared paths remain absent from Ghidra's listing due to analysis flow discovery, not a mismatched CPU map. Firmware bytes, ROMs, Ghidra projects, captures, register-value tables, and reference audio remain outside Git.

## Reproduction

Validate the private manifest and attempt the strict replay:

```sh
python3 tools/audio_validation/factory_manifest.py /private/path/factory-state.json --require-replay-ready
python3 tools/audio_validation/replay_hall.py /private/path/factory-state.json \
  --load-events /private/path/events.csv --out /private/path/replay-output
```

Generate the value-bearing reconciliation table outside the checkout:

```sh
python3 tools/audio_validation/build_hall_register_reconciliation.py \
  /private/path/gpr-reconciliation.private.json \
  /private/path/factory-state.json /private/path/events.csv \
  --out /private/path/register-reconciliation-v2.private.json
```

The private replay attempt and table contain no repository assets. The next technical blocker is to capture or reconstruct the complete pre-RUN live SPR state and establish the serial latch edge, then rerun the unchanged strict gate before standalone audio comparison.
