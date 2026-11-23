# ASR-10 OS 3.53 HALL SPR reconciliation

## Result and evidence scope

This report reconciles the seven special-register differences between the OS 3.53 ROM-01 HALL load trace and the transaction-only state reconstruction. The firmware and trace were inspected through REA 6.9.0 with Ghidra 12.1.4; the private ROM pair was interleaved into a disposable analysis copy outside Git. No original ROM, Ghidra project, other worktree, or Akai Force plugin was changed. No proprietary instruction/register payloads, hashes, or extracted firmware are included here.

The selection is the ROM-01 HALL REVERB effect (selector control 79 after the required ascending sweep). The selected display precedes the load; it is not the load boundary. The runtime trace and the boot-time HALL image agree on the 89-word program identity. The load transaction commits 89 instruction words and 342 GPR/SPR writes while halted. The strict replay manifest gate remains unchanged.

Evidence has three different strengths. The private emulator trace directly records host events and values, and the firmware bytes decode at the corresponding ROM addresses. Register meanings and effects below are implementation-derived and cross-checked against the standalone MAME-derived adapter. They are not direct measurements of physical ES5510 silicon. The original MAME source also marks some behavior as unverified; emulator agreement is corroboration, not silicon validation.

## Seven differences at the recorded boundary

The comparison applies only the HALL transaction's explicit register commits to a zero-initialized register image, plus the ES5510 constant registers. It compares that reconstruction with the captured pre-first-frame snapshot. All values are 24-bit SPR values. “No commit” means there was no effective host write to that register in this transaction, not that the register is proven untouched by the DSP or silicon.

| SPR / address | Transaction reconstruction | Captured snapshot | HALL transaction evidence | Reconciliation |
|---|---:|---:|---|---|
| SER2R / `0xEE` | `000000` | `E90D00` | No `0xEE` commit in the halted transaction. At event 94100, frame 855973, `AUDIO_PRE` reports SER2R input `-5875` (`0xE90D`); the snapshot stores that signed 16-bit input left-justified. | Live serial input state, not an initialization write. Exact snapshot ordering versus application of the first input sample is the earliest unresolved divergence. |
| SER2L / `0xEF` | `000000` | `E90D00` | No `0xEF` commit. Same event/frame/input pair as SER2R. | Same live serial input state and timing uncertainty. |
| MACH / `0xF3` | `000000` | `FEA960` | No `0xF3` commit in the HALL transaction. | Upper 24 bits of the live 48-bit MAC accumulator; retained/runtime value or snapshot-phase effect is more likely than a missing loader write. Exact pre-first-instruction provenance remains unresolved. |
| DIL / `0xF4` | `000000` | `0EC400` | One attempted write: event 92332, cycle 421316334, frame 855448, PC `FFF97792`, `index=F4,value=0000FF`. | `0xF4` configures memory size/shift; it is not a writable data-input latch. Captured DIL is a live delayed-memory input value. No missing DIL initialization is established. |
| DBASE / `0xF8` | `000000` | `A9AB00` | No direct `0xF8` commit in the HALL transaction. | Runtime delay-memory base pointer. The first DSP frame advances it to `A9AA00` (event 94101); the captured pre-frame value is consistent with an active pointer at the boundary, not proof of an omitted write. |
| SIGREG / `0xF9` | `000000` | `FFFFFF` | Not directly committed in this HALL transaction. Cold-start routine writes `0xFFFFFF` at PC `FFF973BA` (trace startup event 371, cycle 28098, frame 52); the later startup reload also writes it at the same PC. | Retained configuration from firmware startup. It is not a HALL-transaction omission. |
| CCR / `0xFA` | `000000` | `400000` | No direct `0xFA` commit in the HALL transaction. | Live condition-code flags in the implementation. A prior DSP operation or checkpoint timing can explain it; the trace does not isolate the exact producer. |

All seven mismatches arise because the reconstruction treats the transaction as a complete reset image. The trace shows a partial state transition layered over an already running DSP and serial path. Of the seven, DIL is the only one with a host commit to its SPR index, and that write has a different documented/implemented meaning. The captured values do not establish that firmware omitted seven required initialization writes.

The HALL trace’s first serial checkpoint is event 94100 at cycle 421550328/frame 855973, same cycle and frame as `DSP_RUN` event 94098. Event 94099 marks the snapshot before event 94100's `AUDIO_PRE` in log order; the manifest describes the snapshot boundary as after DSP_RUN and before the first instruction. The saved SER2 values equal the first input sample. Since the trace is emulator-generated and its snapshot/log ordering does not prove the physical chip’s serial-latch sampling edge, SER2’s exact causal edge remains the earliest unresolved SPR divergence. No arithmetic change is justified by this evidence.

## Firmware path and runtime coordinates

The selected-HALL transaction is ordered as follows (coordinates are the OS CPU PC, CPU cycles, and DSP frame from the private trace):

| Phase | Trace coordinate | Firmware / hardware interpretation |
|---|---|---|
| HALT accepted / pipeline clear | event 87885; cycle 420614232; frame 854142; PC `FFF977B8` | Firmware helper writes HALT enable at the mapped host interface. Trace records pending ALU/MAC results discarded, three RAM pipeline slots cleared, and DOL count zeroed. |
| Full DRAM clear | event 87894; cycle 420614390; frame 854143; PC `FFF9775C` | Firmware writes host control `2`; trace reports 1,048,576 16-bit words cleared while halted. |
| First instruction commit | cycle 421228220; frame 855284; PC `FFF97792` | Shared host-write helper transfers the program. The selected transaction ends with 89 distinct words, END at word 88. |
| Final halted register/upload accounting | 342 GPR/SPR commits | The count includes ordinary GPRs and SPR aliases; the selected transaction runs from the latest pipeline-clear marker through DSP_RUN. |
| PA4 RUN release | event 94095; cycle 421550288; frame 855972; PC `FFF977C6` | Firmware releases the external HALT signal. |
| DSP_RUN / first scheduled DSP frame | event 94098; cycle 421550328; frame 855973; PC `FFF977D2` | Host serial `0x48`; configured frame clock is 29,761.895 Hz for 31 active voices. The first input/output boundary is frame 855973. |
| First post-RUN firmware host write | event 94103; cycle 421550922; frame 855973; PC `FFF97678` | Firmware resumes polling/reading host-visible DSP state. The trace subsequently records ordinary post-RUN register updates (213 in the event stream); they are outside the halted 342-commit transaction. |

The static boot-ROM decode at `FFF97744` calls the HALT and host-address setup helpers. `FFF977B0–FFF977C5` is the HALT helper: its instruction at `FFF977B8` writes the HALT-enable host register. In the loader body around `FFF9774C–FFF9775C`, firmware sets host control for DRAM clear. The setup helper at `FFF9776E` loads the host I/O base. The common transfer helper at `FFF97792` performs indexed host writes and status polling; it is shared by instruction/register transfers. The RUN path at `FFF977C6–FFF977D2` clears the HALT latch and writes host control `1`. A separate helper around `FFF97670–FFF97680` handles the post-RUN host transfer/poll path.

These are verified address-to-file mappings and decodes, not a claim that each trace PC was recovered as a Ghidra function. Ghidra decompiles the cold-start loader at `FFF97346` and the HALT/address helpers; its decompiled cold-start routine writes the serial configuration and initial special-register range. The HALL runtime trace later executes shared code at `FFF97792`, `FFF9775C`, `FFF977C6`, `FFF977D2`, and `FFF97678`. REA's instruction listing has bytes/function coverage at some of these PCs (for example `FFF977B8`) but reports `not-in-listing` at others. The independently decoded bytes at those even addresses are valid 68000 instructions. Their absence from the Ghidra listing is an analysis-flow/function-discovery gap: the loader uses shared helper/branch paths not fully seeded as instructions in the initial auto-analysis, rather than a bad mapped address or a CPU-PC mismatch. No forced function creation or mutation of an existing Ghidra project was needed.

## REA/Ghidra mapping checks

REA 6.9.0 and Ghidra 12.1.4 decompilation were operational. The first imported artifact used in the prior loader report was the OS floppy payload, not the runtime boot ROM; both had been placed at the same nominal `FFF80000` base. That made address-shaped bytes from the wrong artifact look relevant while leaving runtime loader PCs unmapped to the correct instructions. This analysis instead used a private interleaved copy of the hi/lo boot-ROM pair.

The correct import is big-endian Motorola 68000 at base `FFF80000`, length `0x40000`, with one initialized readable/writable/executable block through `FFFBFFFF`. The analyzed language is `68000:BE:32:default`; the emulator selects a 68000 CPU. Runtime PCs are even-aligned and within the ROM block. The 24-bit bus aliases the ROM at `00F80000`; the emulator/trace PC is sign-extended into `FFFxxxxx`, so file offset is `PC - FFF80000`. This confirms processor family, byte order, map, block permissions, alignment, and PC-to-file calculation. It also explains why fixing only memory permissions or changing CPU language would not have repaired the previous listing: the imported artifact was wrong, and auto-analysis did not discover every shared loader path even after the correct ROM was loaded.

No prior Ghidra project was found in the searched private analysis area; original binaries/projects were not edited. REA's current disposable target was closed after recording the results.

## SPR function and emulator cross-check

SPR indices and semantics below are corroborated by `src/es5510.cpp` and `third_party/trollfx_mame_es5510/mame_es5510_standalone.cpp`, which both follow the MAME ES5510 implementation model:

* `0xEE/0xEF` are SER2 right/left aliases; serial state contains signed 16-bit samples in the high 16 bits of a 24-bit register. Host serial `0x48` enables the observed route. The trace's selected setup routes input to serial port 2 and output to port 1; first output appears on SER1 lanes at frame 855973.
* `0xF3` is the high 24-bit MAC accumulator word. `0xF4` derives memory size, mask, shift, and increment from low one bits; it does not store a DIL value. DIL (`0xF4` readback) reflects the live delayed/input latch.
* `0xF8` is DBASE, decremented by the configured memory increment as the DSP runs; `0xF9` is SIGREG, including multiplier shift configuration; `0xFA` exposes condition flags in the high byte.
* HALT suppresses pending ALU/MAC results and clears pipeline slots in the emulator model. It does not clear the MAC accumulator, DIL, DBASE, SIGREG, or CCR. DRAM clear is an explicit separate host-control write accepted only while halted. Both the native model and MAME-derived adapter reset most state to zero at their own `reset()` boundary, but neither reset behavior should be confused with the firmware's in-place HALL reload.

The MAME source describes the ES5510 device as an emulation and flags some behaviors as unverified. We therefore label these meanings and side effects implementation-derived, with runtime values corroborating the trace interpretation; silicon-level confirmation requires a physical-device measurement or primary Ensoniq register documentation.

## Timing limits and earliest unresolved divergence

The firmware runs through an emulated MC68302 CPU cycle counter, the ESP advances at an OTTO-derived rate, and host audio renders at 44.1 kHz. At this selected transaction the ESP frame rate is 29,761.895 Hz; a frame number is not a WAV frame number. CLI millisecond schedule timestamps are coarse and must not replace recorded CPU cycles and DSP frames. RUN occurs immediately before frame 855973, and the event stream places the first serial input and output on that same frame.

Earliest unresolved SPR divergence: **SER2R/SER2L at the frame-855973 snapshot/input edge**. The reconstruction has zero because the HALL transaction has no serial SPR commits; the boundary snapshot contains the first `0xE90D` sample. Event order places the snapshot marker just before `AUDIO_PRE`, while the manifest places the snapshot before the first instruction. Current evidence cannot resolve whether the saved serial SPR values are the just-latched input or a boundary capture after input setup, nor establish the equivalent silicon sampling edge. Next runtime frames are deterministic in the emulator trace, but do not settle that first-edge attribution. The other six differences have the state-retention/derived-register explanations above; they remain unproven on hardware.

## Reproduction and safety

The private event log, state payloads, ROM pair, interleaved analysis image, extracted code, and REA target remain outside Git. Redacted verification can be repeated with the repository's existing HALL boundary tests and replay parser. Do not infer payload data from this report. Do not modify `tools/audio_validation/factory_manifest.py` or its replay-ready gate to force this transaction through audio comparison.

