# ASR-10 OS 3.53 ES5510 factory HALL load

## Scope and evidence

This note reconciles the private `asr10-hall-load-boundary` trace and cold-load manifest with an REA 6.9.0 / Ghidra 12.1.4 import of the OS payload. Analysis used an isolated worktree on `research/asr10-ghidra-loader-analysis`. The firmware image, captures, emulator state, and prior project files remain outside this repository; no proprietary bytes, coefficient tables, register payloads, or private hashes are included here.

The cold-load manifest records the selection marker for **ROM-01 — HALL REVERB** before the load phases and captures state immediately after DSP RUN and before the first DSP instruction. It identifies 89 active program words (END at index 88), 192 GPR values in the resulting state, serial host value `0x48`, and a full clear of 1,048,576 DRAM words. This is emulator trace evidence, not a physical-hardware capture. The separate boundary trace independently records repeated 89-commit uploads and the first cold-start upload's 342 GPR commits.

## Verified load path

Addresses below are 68000 OS PC values from the execution trace, not ES5510 host-port addresses. The payload was imported as raw big-endian 68000 code at `0xFFF80000`; offsets in parentheses are relative to that base.

| Phase | Trace evidence |
|---|---|
| Select factory program | UI/selection marker resolves to ROM-01 HALL REVERB in the cold-load run; selection precedes HALT. |
| Assert HALT | `0xFFF977B8` writes host port `0x1F`; the trace records HALT and a pipeline reset. A second host-control write at `0xFFF9734E` precedes initial program upload. |
| Upload preamble | `0xFFF97354` starts instruction upload at address `0x9F`; setup writes GPRs `0xF4`, `0xF5`, and `0xF8` at `0xFFF97364`, `0xFFF97370`, and `0xFFF97380`. |
| DRAM and routing setup | Host-port `0x12` writes at `0xFFF97386` and `0xFFF9738C` are tagged as DRAM-clear operations while halted. Host-port `0x18` at `0xFFF97392` sets serial configuration to `0x48`. Manifest routing decodes this as input serial port 2 to main output port 1. |
| Zero fill / initial program | Sequential host-port `0xE0` writes begin at `0xFFF973AA`. The later factory program upload uses the address-zero path, ending with 89 unique instruction commits through index 88. The trace summary records 342 GPR commits for the first cold-start upload. |
| Factory HALL load and RUN | Factory-state markers: selection event 88,936; HALT 91,467; pipeline clear 91,470; DRAM clear 91,478; program-ready 95,826; RUN 97,682. The separate boundary trace confirms RUN only after all 89 words are committed. |
| Post-RUN firmware writes | The first-frame trace continues with host accesses from `0xFFF97678`, `0xFFF97792`, `0xFFF9770E`, and related sites. These include per-frame input/output and GPR/register traffic after RUN; they are runtime activity, not part of the 89-word image. |

The captured ES5510 settings at the run boundary are `memshift=8`, `memsiz=0xFF`, `memmask=0xFFFF00`, `memincrement=0x100`, `dlength=0xFFFFFF`, `abase=bbase=0`, `dbase=0xA99C00` (decimal 11,119,360), and `sigreg=0xFFFFFF`. The capture reports a 29,761.895 Hz DSP frame rate (nominal 29,762 Hz) and 44.1 kHz output clock.

## Firmware decompilation cross-reference and limits

REA imported the private OS payload successfully as a 195,584-byte raw image and Ghidra reported 240 procedures. Decompiled entries near the relevant areas include `FUN_fff974f8`, `FUN_fff97ae4`, and `FUN_fff97bba`; these do not contain the traced host-I/O sequence. The trace PCs `0xFFF9734E`, `0xFFF97354`, `0xFFF97386`, `0xFFF9738C`, `0xFFF97392`, `0xFFF977B8`, and `0xFFF97678` are in mapped memory, but Ghidra 12.1.4 reports them as **not in listing** and returns no function body for them. `0xFFF882D0` is within the Ghidra-listed `FUN_fff882c2`, whose decompilation is only a return and does not explain the observed upload. Therefore the exact transfer loop and post-RUN path are established by runtime trace and phase instrumentation, while source-level attribution to a decompiled routine remains unresolved. Treating nearby disassembled code as the loader would overstate the static evidence.

The trace does provide a repeatable runtime call pattern: HALT → pipeline reset → DRAM clear/configuration → sequential program transfer → GPR commits → RUN → first instruction → subsequent firmware I/O. The initial 89-word transfer is distinct from later factory-effect reloads in the boundary experiment; subsequent loads also show 89 words but vary in GPR commit count (256–370). Do not conflate the ROM-01 HALL cold-load selection with later menu selections in that experiment.

## Timing caveats

The event log carries multiple clocks. CPU cycles are at 16 MHz; DSP frame count advances at about 29.762 kHz; UI/session timestamps are a separate host-time label. For example, the boundary log places the first RUN at 229,088,812 CPU cycles / frame 426,313, while a nearby displayed time is approximately 14.3 seconds. The cold-load manifest's host elapsed time is 26.316 seconds at frame 855,973, whereas its event-time field is not a hardware timestamp. These clocks align sequence ordering but should not be collapsed into a single precise latency. HALT settling, bus-write duration on physical hardware, and hardware-to-emulator timing equivalence are not established by this capture.

## Reproduction pointers (private, not tracked)

- `research/private-results/asr10-hall-load-boundary-20261123/experiment.log`
- `research/private-results/asr10-coldload-manifest-20261123T204000Z/factory-state.json`
- `research/private-results/asr10-coldload-tail-20261123T210000Z/events.csv` and `session.log`

These are analyst-local evidence paths only. They must not be copied into the repository or treated as distributable firmware artifacts.
