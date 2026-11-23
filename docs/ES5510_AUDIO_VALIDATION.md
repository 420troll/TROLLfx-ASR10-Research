# ES5510 audio validation

`tools/audio_validation/run.py` builds and drives a test-only executable that compares the ASR-10 emulator's `ES5510` execution with the isolated TROLLfx MAME-derived `MameES5510` adapter. It runs both the pass-through baseline and the original TROLLfx stereo feedback-delay microprogram. The copied adapter and its BSD-3-Clause notice are under `third_party/trollfx_mame_es5510/`. No factory program, ROM, OS, capture, or rendered factory audio is included.

Run:

```sh
python3 tools/audio_validation/run.py
python3 -m unittest discover -s tests/audio_validation -v
```

All inputs, per-engine sample CSVs, and `summary.json` go to `/tmp/es5510-audio-validation` by default. Pass `--out DIR`, `--rate HZ`, or `--frames N` to change that. Inputs are identical signed PCM16 stereo stimuli: impulse, 997 Hz sine, exponential sweep, seeded stereo noise, and a 431 Hz quarter-cycle stereo phase offset. The delay microprogram is the original TROLLfx diagnostic algorithm (not Ensoniq firmware): its 11 instructions use SER2 input, SER3 output, delay reads/writes, ALU feedback summing, and MAC feedback multiplication. Both engines receive MEMSIZ 0, DLength `0x0d754f`, DBase 0, GPR0/1 `0x2b11`/`0x6e5b9`, GPR6/7 `0`/`0x6baa8`, GPR40 `0x233333`, host serial `0x20`, and zeroed 1 Miword DRAM. The C++ runner starts each engine from its own reset state and applies these writes before frame 0.

The summary reports frame count, exact sample equality, first divergent output frame, maximum and RMS deviation, best cross-correlation lag over ±128 frames (bounded to a quarter of shorter captures), unaligned and aligned error, per-channel peak/RMS, stereo difference, first active frame, peak frame, and input-to-output delay. The impulse report records each nonzero output tap. Sine and sweep reports add windowed left-channel gain estimates for both engines. These measures characterize these generated probes; they do not characterize a factory effect. No bit-exact claim is made unless `bit_exact` is true for the specific generated case.

## State and interpretation

The two implementations have separate state models. The original emulator resets its 1 Miword DRAM to zero, starts its processor in `RUNNING`, and advances its END/HALT frame lifecycle in `run_frame()`. The adapter's `prepare()` also zeroes its 1 Miword DRAM, `resetExecutionState()` clears register and ALU/MAC/RAM pipeline state, and `processFrame()` pulses the MAME pump lifecycle. The pass-through baseline consumes SER0 and outputs SER3. The delay test consumes SER2 and outputs SER3, matching the program's register operands and the engines' documented serial mapping. The delay test exercises address generation, delayed RAM read/write, ALU, MAC, and pipeline state together.

These are controlled regression measurements for these microprograms and initial conditions. A factory loader/init sequence from Agent 5 is not present in this worktree; static EFE layout and a post-run capture do not provide a reproducible cold-start sequence. The existing capture omits in-flight pipelines. The `44DDL+CHORUS` attempt is therefore deferred until a loader can define all program, GPR/special register, DRAM, serial-routing, and frame-boundary initialization. No factory comparison or factory-accuracy claim is made. Keep captures and renders outside the repository.

## Milestone 2 results

At 44.1 kHz and 32,768 frames per stimulus, both the pass-through baseline and feedback delay matched on every sample for all five stimuli. Each case had maximum deviation 0, RMS deviation 0, best alignment lag 0, and no divergent output frame. The complete per-case peak/RMS, stereo, frequency-gain, delay, and impulse-tap values are in [`summary.json`](audio-validation/summary.json).

For the impulse, both engines output the direct sample at frame 4,096, then echoes at frames 15,121 and 26,146: offsets of exactly 11,025 and 22,050 frames. The left-channel values were 24,000, 13,199, and 7,259; the right channel remained silent for this left-only stimulus. The 997 Hz sine gain was -0.245918 dB in both engines. Since all observable outputs matched, there is no first divergent frame or instruction in this run. The reset/configuration comparison also showed no startup frame offset despite the original core starting RUNNING and the adapter starting halted before its frame pump.

This validates external behavior for the tested microprogram. It does not compare internal MAC/ALU/pipeline registers after each instruction; no instruction-level divergence was observable at the output. No implementation correction was justified by these results.

## Factory initialization manifest and diagnostic tracing

The harness accepts an externally produced factory-state description through the manifest validator:

```sh
python3 tools/audio_validation/factory_manifest.py /private/path/effect-init.json
```

The JSON contract is `tools/audio_validation/factory_state_manifest.schema.json`. Program, GPR, special-register, and optional DRAM payloads are external files referenced by relative path and SHA-256. The manifest records OS/effect selection provenance, sample rate, active six-byte big-endian instruction count and END location, all 192 GPRs, all 22 special registers, DRAM initialization, MEMSIZ/MEMMASK/MEMINCR/MEMSHIFT, DLength/ABase/BBase/DBase/SIGREG, host serial routing, HALT/RUN order, and pipeline initialization. Validation reports metadata only. It does not print payload bytes.

A reproducible cold-load manifest must assert HALT, configure memory, load program and registers, initialize DRAM, reset the execution pipeline, and release RUN in that order. A running-state snapshot is rejected; it cannot be silently coerced into a cold-load state. The contract is an intake/validation interface; execution from factory manifests remains unavailable until the loader and full pipeline state support are implemented.

The optional `--trace` switch writes one frame of per-engine instruction diagnostics for every stimulus/algorithm case. Example:

```sh
python3 tools/audio_validation/run.py --out /tmp/es5510-trace --frames 128 --trace
```

Each `*-original.trace.csv` and `*-mame.trace.csv` contains instruction words, instruction PC, RAM request/read/write events, changed GPR/special-register values, END, plus a serial route record for frame 0. Without `--trace`, tracing is disabled and the comparison output remains unchanged. Traces belong in private output directories if they contain factory state.

## Numerical implementation audit

This section compares the checked-in ASR-10 `ES5510` core with the standalone adapter copied from MAME commit `8be57cdc5f44ab830dff44c06dd39f24190742d4`. It describes implementation behavior; it is not a substitute for silicon conformance evidence.

| Area | ASR-10 core | MAME-derived adapter | Assessment |
|---|---|---|---|
| Data widths | GPRs masked to 24 bits; MAC held in signed 64-bit storage, architecturally checked against signed 48-bit limits | GPRs masked to 24 bits; signed 64-bit MAC with the same 48-bit overflow limits | Matched for tested pass and delay programs |
| Saturating arithmetic | ADD/SUB detect signed 24-bit overflow and clamp to `0x800000`/`0x7fffff`; unsigned operations wrap to 24 bits | Same structure | Output exact in current tests; not exhaustively flag-tested |
| MAC scaling | Signed 24×24 product, shifted by SIGREG-selected 1 or 2 bits, optional full-precision accumulation, 48-bit overflow check, high 24-bit writeback | Same intended scaling and writeback | The audit found signed left-shifts of negative values in MAC/ASL scaling and serial/DIL conversions. The arithmetic shifts were replaced with equivalent bounded multiplication and unsigned shift operations; this removes those undefined behaviors without changing intended 24/48-bit results. A negative-input UBSan smoke test passed after the change. Other implementation-defined signed right-shifts in sign extension and PCM rounding remain noted below |
| DOL conversion | Signed 24-bit arithmetic right shift by 8 to PCM16 | Same conversion | Both rely on arithmetic right-shift behavior for negative signed values, which is implementation-defined in C++17; tested Linux/Force targets are two's-complement GCC environments |
| Delay RAM pipeline | Three RAM stages; read data reaches DIL after two instruction cycles; DOL is a two-entry FIFO; writes retire through delayed stages | Same modeled three-stage RAM path and DOL FIFO | The diagnostic delay golden test covers this path; no independent silicon validation |
| Delay addressing | Converts left-justified DLength/offsets using MEMSHIFT, wraps over `DLength>>shift + 1`, then masks | Uses modulo by `DLength + MEMINCR`, then masks/shifts | Algebraically equivalent for validated aligned configurations; edge configurations need dedicated differential cases |
| Frame lifecycle | Starts RUNNING after reset; END advances DBase and only drains pipeline when HALT is asserted | Pump executes through END and pulses its modeled halt/run lifecycle | Current tested programs have no sample offset; captured live snapshots do not include full in-flight pipeline state |
| Serial routing | Serial registers 0L/0R through 3L/3R are mapped by special-register aliases; host serial controls directions | Pump accepts stereo input pairs on serial ports 0–2 and emits port 3 when configured | Tested pass/delay routing is sample-exact; this does not prove ASR/DP-4 board routing |

The two executors are demonstrably sample-identical for the current pass-through and TROLLfx diagnostic feedback-delay programs at the tested conditions. That result does not establish identical behavior for every instruction or for a factory program.
