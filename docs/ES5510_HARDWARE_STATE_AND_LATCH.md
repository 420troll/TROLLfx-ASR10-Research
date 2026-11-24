# ES5510 hardware state and serial-latch investigation

## Result

The remaining six SPR values are reproducible for the OS 3.53 HALL load in the OpenASR reference emulator. Two clean processes produced identical state traces. At the frame-855973 boundary, the routed serial input is written to the SER2 latches **before** `run_frame()` enters the frame, before the snapshot is created, and before DSP PC 00 executes. Thus the snapshot is a pre-instruction checkpoint that already contains input sample `0xE90D` in both SER2 lanes.

The HALL reload is an in-place HALT/load/RUN, not an ES5510 reset. HALT clears pending ALU/MAC write enables, the three RAM pipeline slots, and DOL count, but retains the MAC accumulator, DIL, DBASE, CCR, and serial latches. The first DSP frame then changes those live values through normal DSP execution and the cleared-DRAM pipeline. This explains the snapshot mismatches without adding firmware SPR writes.

This is verified emulator behavior. Neither the two software captures nor MAME-derived code proves that physical ES5510 silicon samples serial data on the same edge. That remains the hardware-only uncertainty.

## Source and environment provenance

REA 6.9.0 is connected; its live server reports version 6.9.0. Ghidra 12.1.4 is available and was used on the private interleaved OS 3.53 boot ROM. The private Ghidra project from the loader analysis remains under the private results directory. REA opened the private boot-ROM copy read-only; the original ROMs/projects and other worktrees were not changed.

The reference-capture V2 source is published at `research/es5510-hall-reference-capture-v2` commit `464b8bb`. Its capture metadata does not embed the CLI binary hash or a source revision, so the exact executable that created those earlier bundles cannot be proven from the bundle alone. This task therefore repeated the experiment using the instrumented source committed with this report. The MAME-derived standalone adapter declares its upstream source as MAME commit [`8be57cdc5f44ab830dff44c06dd39f24190742d4`](https://github.com/mamedev/mame/tree/8be57cdc5f44ab830dff44c06dd39f24190742d4/src/devices/cpu/es5510); serial-pump routing follows that revision's `esqpump.cpp`. The native OS reference capture uses `src/es5510.cpp`, not the standalone MAME adapter.

The previous loader investigation found why mapped runtime PCs could be absent from Ghidra's instruction listing. The earlier same-base import was the floppy OS payload, not the runtime boot ROM. On the correct ROM, default analysis also failed to flow from its high-base entry/vector data into every shared loader helper. In the live REA session, `FFF977D2` again returned `not-in-listing`; the private trace-seeded Ghidra analysis recovered it as a `MOVE.B #1,$FFFC3025` instruction in the RUN helper. The 68000 language, big-endian ROM bytes, executable block, address mapping, even alignment, and instruction bytes were verified in the prior loader report. See [loader disassembly and timing](research/ASR10-OS353-loader-disassembly-timing.md).

## Six-register evidence matrix

SPR indices are hexadecimal. Values are the internal 24-bit values serialized by `write_capture()`, unless identified as host-port readback.

| SPR | At snapshot, frame 855973 | First-frame transition | At frame exit | Confirmed source of change | Remaining limit |
|---|---:|---|---:|---|---|
| SER2R `EE` | `E90D00` | No change through DSP END | `E90D00` | `ser_w(lane 5, 0xE90D)` writes the serial latch and its GPR mirror before frame entry. | Input edge is exact in this emulator; physical silicon edge is unmeasured. |
| SER2L `EF` | `E90D00` | No change through DSP END | `E90D00` | `ser_w(lane 4, 0xE90D)` writes the serial latch and its GPR mirror before frame entry. | Same hardware-edge limit. |
| MACH `F3` | `FEA960`; full accumulator `FEA960000000`, overflow clear | Visible writebacks at DSP PCs `02,03,05,0A,0C,0D,38,3A,3B`; first becomes `000000` at PC `02` | `000000` | MAC pipeline writeback. The previous accumulator is retained across HALT; HALL executes multiply operations beginning at PC 00. PC 01's non-accumulating product becomes visible at the next pipeline boundary. | Silicon multiplier/writeback behavior remains emulator-derived. |
| DIL `F4` | `0EC400` (`dil16=0EC4`) | Becomes `000000` at the end of DSP PC `00` | `000000` | DIL is the delayed RAM input latch. HALT has cleared the three RAM slots; DRAM was explicitly zeroed. The initial cleared read slot at address 0 supplies zero on the first instruction; the HALL instruction then queues its first real read at word `0x0ADAB`. | No missing F4/DIL firmware write. Physical clear/latch timing unmeasured. |
| DBASE `F8` | `A9AB00` | Becomes `A9AA00` at END PC `58` (decimal 88) | `A9AA00` | END advances the circular delay pointer by the configured `MEMINCREMENT=0x100`. | Exact in the emulator; silicon END timing unmeasured. |
| CCR `FA` | `400000` (`ccr=0x40`) | ALU flag writebacks visible at PCs `05,24,38,3B,3C,3E,41,45,51`; final visible value is `080000` | `080000` | The HALL ALU updates condition flags during ordinary instruction execution. The listed PC is where the pipelined writeback becomes visible; the producing ALU operation is the preceding pipeline instruction. | Exact emulator result; silicon flag behavior and sample phase not independently measured. |

The two trace logs contain 185 `ESPSTATE` records each and have identical ordered contents. Both report the same snapshot, first instruction, SPR transitions, memory addresses, and frame-exit state. Private logs, captures, program listing, and ROMs remain outside Git.

## Exact event ordering and coordinates

All cycles are the MC68302 cycle counter; DSP frame numbers count `run_frame()` calls.

| Ordered event | Event coordinate | Observation |
|---|---|---|
| HALT pipeline reset | cycle `420614232`, frame `854142`, firmware PC `FFF977B8` | Clears pending ALU/MAC results, all three RAM slots, and DOL count. It does not clear MACH, DIL, DBASE, CCR, or serial state. |
| DRAM clear accepted | cycle `420614390`, frame `854143`, firmware PC `FFF9775C` | Host control write `2`; modeled 1,048,576 16-bit words are cleared. |
| PA4 RUN release | cycle `421550288`, frame `855972`, firmware PC `FFF977C6` | Firmware sets PA4 to RUN. |
| Serial input latch, left | cycle `421550606`, next frame `855973`, host PC `FFF97638`, trace sequence 1 | Lane 4 writes sample `E90D`, SPR `EF` becomes `E90D00`. |
| Serial input latch, right | cycle `421550606`, next frame `855973`, host PC `FFF97638`, trace sequence 2 | Lane 5 writes sample `E90D`, SPR `EE` becomes `E90D00`. |
| Frame entry and RUN state | cycle `421550606`, frame `855973`, trace sequence 3–4 | Frame counter increments. Snapshot-start SPR state is `EE=E90D00`, `EF=E90D00`, `F3=FEA960`, `F4=0EC400`, `F8=A9AB00`, `FA=400000`; pending ALU/MAC flags and RAM slots are clear; DOL count is zero. |
| RUN snapshot | cycle `421550606`, frame `855973`, host PC `FFF97638`, trace sequence 5 | Capture is written after the two serial-latch updates and before instruction execution. |
| First instruction boundary | cycle `421550606`, frame `855973`, DSP PC `00`, trace sequence 6–7 | First HALL instruction begins. The snapshot does not include the post-instruction state. |
| First frame END | cycle `421550606`, frame `855973`, DSP END PC `58` | DBASE has decremented once. DSP serial output is reported on SER1 for this same frame by the independent V2 reference trace. |
| First post-RUN host GPR commit | event `4977`, cycle `421551112`, frame `855973`, firmware PC `FFF97792` | Writes GPR `7F=000000`, 506 CPU cycles after the run-frame boundary. It is not an SPR-index write. |

The exact event sequence in the new logger is `serial_input_latch(lane 4)`, `serial_input_latch(lane 5)`, `frame_enter`, `run_start`, `snapshot_created`, `pre_instruction_boundary`, `instruction_begin(00)`. This establishes the order from calls and ordered trace records, rather than inferring it from equal timestamps.

The pre-instruction pipeline state is also determined: ALU and MAC pending write enables are false; RAM, RAM-p, and RAM-pp are reset slots; DOL count is zero. Full saved ALU/MAC operand payload fields are not serialized, but their write enables are false and the halt path clears them before RUN. They cannot produce a preexisting writeback on the first HALL instruction. Frame execution then fills the pipeline. DBASE remains `A9AB00` through the program and updates at END; the delayed RAM pipeline starts with zeroed DRAM and supplies zero to DIL on its first operation.

## Post-RUN host events

The two new clean boots each contain 213 post-RUN `ESPHOST` GPR commits, all through firmware PC `FFF97792`. The range is event 4977 at cycle `421551112`, frame `855973`, through event 5189 at cycle `428530738`, frame `868956`. The destination histogram is identical in both runs:

| Destination | Writes |
|---|---:|
| GPR `7F` | 111 |
| GPR `7C` | 37 |
| GPR `7D` | 37 |
| Other GPRs in `00–7F` | 28 |

No post-RUN host transaction directly writes indices `EE`, `EF`, `F3`, `F4`, `F8`, or `FA`. These are host-to-GPR parameter/control writes using the shared transfer routine. Their later influence through the HALL program's GPR dataflow is possible, but the event record alone does not identify every affected DSP operation. For Replay V4, preserve these ordered GPR writes after the halted load; do not turn them into direct SPR initializers.

The smallest experiment to map indirect effects is another private run with state-transition logging enabled for the complete 9,000-frame post-RUN interval, recording only changes to the six SPRs plus each commit's caller PC. The current evidence already establishes that the 213 operations are not direct writes to the six SPRs.

## Implementation evidence and cross-checks

The native reference implementation's relevant code is in [ES5510 source](../src/es5510.cpp):

- `reset()` clears serial, DRAM, MACH, DIL, DBASE, CCR and pipelines. The HALL sequence does not call this reset.
- `host_w(0x1f, ...)` on accepted HALT clears `alu.write_result` and `mulacc.write_result`, resets `ram`, `ram_p`, `ram_pp`, and clears DOL count.
- `read_reg()` maps `EE/EF` to SER2R/L, `F3` to MACH high word, `F4` to DIL, `F8` to DBASE, and `FA` to `ccr << 16`.
- `write_reg(F4, v)` derives memory shift, mask, size and increment, then aligns DBASE; it does not write DIL. Host readback of `F4` returns DIL. Host readback of `F9/FA/FB` ORs the documented unimplemented-bit masks, while `write_capture()` records internal register values without those host-port masks.
- `run_frame()` reads the two-cycle delayed RAM result into DIL, applies pipelined MAC/ALU writebacks, and handles END through `alu_operation_end()`, which advances DBASE.
- `ser_w()` now emits opt-in `ESPSTATE` events. `run_frame()` records the selected frame's entry, snapshot, instruction boundaries and exit when `ESP_STATE_TRACE_FRAME` is set. `ESP_RUN_SNAPSHOT_FRAME` and `ESP_RUN_SNAPSHOT_DIR` create the private pre-instruction snapshot. With both variables unset, the added trace code does not emit events or alter DSP results.

The MAME-derived adapter independently implements the same register aliases, input-before-execute ordering, delayed RAM/DIL update, MAC accumulator, CCR, and END/DBASE behavior in [MAME adapter](../third_party/trollfx_mame_es5510/mame_es5510_standalone.cpp). This is implementation cross-checking only; its adapter and the native emulator are not independent physical-chip measurements. The upstream source revision and register names are documented in [`THIRD_PARTY_NOTICES.md`](../third_party/trollfx_mame_es5510/THIRD_PARTY_NOTICES.md) and the upstream [MAME ES5510 source](https://github.com/mamedev/mame/blob/8be57cdc5f44ab830dff44c06dd39f24190742d4/src/devices/cpu/es5510/es5510.cpp).

## Reproducible checks and remaining hardware question

Run the focused semantic regression with:

```sh
make test-es5510-hardware-state
```

The synthetic test exercises serial SPR aliases, host readback masks versus internal snapshot values, F4 memory-configuration side effects, delayed DIL reads from DRAM, END DBASE movement, MAC/MACH writeback, ALU/CCR writeback, and reset clearing. It uses generated instruction/data words only; no factory payload is included.

For the original capture procedure, use private ROM and disk copies, set `ESP_STATE_TRACE_FRAME=855973`, `ESP_RUN_SNAPSHOT_FRAME=855973`, and point `ESP_RUN_SNAPSHOT_DIR` outside the checkout. Start a fresh CLI process for each boot and use the HALL selector sequence from the reference-capture procedure. The state trace is frame-scoped; it does not dump the program bytes or raw audio. The two reproduced private logs had the same 185-record state trace and the expected `89` instruction / `342` halted-register load.

The emulator state required at the V4 boundary is now concrete. Physical ES5510 confirmation still needs one instrumented unit capture: apply a known serial sample with the original HALL program, measure serial data against the DSP frame clock/PA4 RUN edge, then expose the six SPR readbacks after the first END (or route them through a diagnostic program). That experiment is needed only to confirm the physical chip's input-latch edge and matching internal pipeline behavior.
