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
