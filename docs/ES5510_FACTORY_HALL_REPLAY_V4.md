# Authentic factory HALL replay V4

## Outcome

V4 passes the strict RUN-boundary state gate and executes the captured ROM-01 HALL REVERB program in both standalone ES5510 engines. The native engine matches the OS 3.53 emulator reference exactly for **256, 4096, and 32768 DSP serial frames**. The MAME-derived engine matches through 4096 frames, then diverges. The run is reproducible with `tools/audio_validation/replay_hall_from_boundary.py`; all payloads and value-bearing reports stay in the caller's private output directory.

The native 32768-frame result is an end-to-end integration check against two fresh OS 3.53 emulator boots. The OS emulator and native standalone use the repository's same ES5510 core, so this result does not independently establish physical-chip arithmetic. The MAME-derived engine provides a separate implementation check and exposes the remaining RAM-addressing disagreement described below.

## Verified research baseline

Remote branches were fetched and their reports/commits inspected before implementation:

| Branch | Verified commit | V4 use |
|---|---|---|
| `research/es5510-hall-replay-v2` | `79b25b8` | Latest verified replay baseline, including 16 retained GPR histories and the V2 strict gate |
| `research/asr10-loader-disassembly-v2` | `289ad20` | Correct 68000 boot-ROM mapping and loader/helper timing |
| `research/es5510-hall-reference-capture-v2` | `464b8bb` | Opt-in RUN snapshot, first-instruction, serial-frame, and host source-time capture |
| `research/asr10-hall-spr-rea-analysis` | `8b39889` | SPR names, REA/Ghidra mapping, and distinctions between stored configuration and live state |
| `research/es5510-hall-audio-verification` | `9c074eb` | Strict no-shift DSP comparison and distinct DSP/host clock domains |
| `research/es5510-hall-load-boundary` | `bad3f81` | Original measured HALT/upload/RUN boundary |
| `research/es5510-hall-gpr-reconciliation` | `c065a06` | Earlier halted writes that preserve GPR `0x90`–`0x9f` |
| `research/es5510-hall-timeline-reconciliation` | `e63dd1c` | Ordered load and RUN timeline |
| `research/es5510-first-divergence-analysis` | `e95d6e9` | Instruction/RAM/register trace comparison |

No remote `research/es5510-hall-spr-replay-v3` branch was present. V4 is isolated on `research/es5510-hall-replay-v4`; other worktrees and the Akai Force plugin were not changed.

## Boundary state and register reconciliation

The RUN-boundary captures are separate full ESP snapshots from two fresh OS boots. Their hashes agree with each other and with the independent cold-load manifest for the active HALL program, all 192 GPRs, all 22 SPRs, memory configuration, and zeroed DRAM. The ordered load trace independently validates 89 unique instruction commits through END word 88 and 342 halted register commits. The two recorded event histories also reproduce the 16 retained GPRs from earlier halted `BOTH_COMMIT` writes.

The checkpoint was taken after the HALT pipeline-reset acknowledgement and at PC 0 immediately before the first DSP instruction. The snapshot format does not contain in-flight ALU/MAC/RAM/DOL slots; V4's loader explicitly resets those slots and is only admitted after the recorded pipeline-reset event. It loads the RUN checkpoint bytes, not values copied from the final manifest. The gate then compares the loaded capture against the manifest and both fresh captures.

| Original difference | V4 reconciliation |
|---|---|
| 16 GPRs, `0x90`–`0x9f` | Resolved by the recorded prior halted writes. Both fresh checkpoints and the manifest agree. |
| SER2R/SER2L | Resolved at the emulator RUN boundary. The snapshot's serial latches and SER2 SPRs equal the first captured input sample. `Asr10::otto_frame` writes routed serial input before invoking `run_frame`; the `ESPPFRAME input` log is emitted inside that call, after the snapshot hook. |
| MACH, DIL/readback, DBASE, CCR | Resolved at the recorded RUN checkpoint from captured live state. They are not fabricated loader writes; the snapshot includes the MAC, DIL, delay-base, and condition state needed by execution. |
| SIGREG | Resolved by the earlier startup write and confirmed in the RUN checkpoint. |

All 23 originally disputed register fields now agree at the validated RUN checkpoint: 16 GPR differences are explained by prior firmware writes; the seven SPR differences are explained by retained startup state or the captured runtime boundary. There are zero unmatched register fields at the gate. The private machine-readable table is written as `register-reconciliation.private.json` under `--out` and includes expected, transaction-only, history-reconstructed, checkpoint-observed values, write coordinates, and resolution status.

The capture resolves the emulator event ordering: the logged RUN snapshot precedes the first `ESPPFRAME input` line, but its serial latches already contain that first input sample because the host routed the input before entering `run_frame`. This establishes the repository emulator's latch order. The physical ES5510 sampling edge is still not a hardware measurement.

## Firmware event scheduler

The two fresh captures contain the same 213 post-RUN GPR host commits with matching event order, frame, host-cycle, PC, register index, and value. Every commit falls after an observed output frame and before the next observed input frame. V4 applies it at that next input boundary; it does not infer an instruction-cycle position from the DSP frame counter. The native and MAME engines have identical state at initial load and at each scheduled host-write boundary.

The replay applies 87 writes in the first 256-frame window, 163 by 4096 frames, and all 213 in the 32768-frame window. These firmware writes remain separate from implicit DSP state changes. Register state is compared after every host-write boundary and at each frame boundary.

The standalone engines resume from the authentic captured RUN checkpoint rather than emulating the MC68302 boot ROM and reissuing its host-port HALT/DRAM-clear/upload bus cycles. V4 verifies that those measured events occurred, that the ordered 89/342 transaction matches the manifest, and that the checkpoint is its validated result. The 213 later writes are replayed by the deterministic scheduler.

## Execution and comparisons

| Comparison window | Native vs OS 3.53 emulator | MAME-derived vs OS 3.53 emulator | Native vs MAME-derived |
|---:|---|---|---|
| 256 DSP frames | Exact | Exact | Exact |
| 4096 DSP frames | Exact | Exact | Exact |
| 32768 DSP frames | Exact | Diverged | Diverged |

The OS reference traces use input lanes SER2 L/R and compare output lanes SER1 L/R. They are matched by initial checkpoint hash, per-window input hash, complete startup-plus-post-RUN event hash, absolute DSP frame, and the verifier's fixed alignment. No sample shifting or correlation search is used. The clock domains remain **29,761.89453125 Hz DSP** and **44,100 Hz host audio**. This task compared DSP serial samples; it did not compare standalone 44.1 kHz host WAV output.

The earliest MAME/native instruction-trace mismatch occurs in the first captured DSP frame, at program counter `0x02`, on a delay-RAM request address. The independent first-divergence analyzer classifies it as a RAM address difference. Native and MAME use different delay-address calculation order: the native core shifts the base and offset into word units before adding; the MAME-derived adapter follows upstream MAME's add/modulo/mask/shift expression. The request differs by one word in the private trace. V4 does not change either DSP calculation because the captured OS reference uses the native core and therefore cannot independently establish which address rule matches silicon.

The first MAME/native register-state difference occurs after absolute frame **868821** at GPR `0x99`. The first numerical serial-output difference occurs later at sample index **13164**, absolute DSP frame **869137**, on SER1L. MAME has 4026 differing serial-lane samples over the 32768-frame capture. The exact first instruction trace and sample mismatch are retained only in the private replay output.

## Tests and reproduction

The replay requires private arguments for the cold-load manifest, GPR reconciliation table, ordered load-event CSV, and two-boot reference-capture directory:

```sh
python3 tools/audio_validation/replay_hall_from_boundary.py \
  /private/path/factory-state.json \
  /private/path/gpr-reconciliation.private.json \
  /private/path/events.csv \
  /private/path/hall-reference-capture-v2 \
  --out /private/path/hall-replay-v4
```

It first requires the unchanged manifest validator's replay-ready gate, then validates both reference checkpoints, the 89/342 halted transaction, all 213 post-RUN events, and input/output coverage. It advances through 256, 4096, and 32768 frames only when the preceding comparison is exact. If requested, `--diagnostic-frame` captures one frame of instruction/RAM/register traces for the independent divergence analyzer.

Firmware, ROMs, captures, microprograms, reference audio, sample values, and value-bearing state tables remain outside Git. The native/MAME RAM-address rule remains the next technical question for an independent hardware trace or primary silicon documentation; it does not block native factory HALL execution or the verified 32768-frame native replay against the current OS emulator reference.
