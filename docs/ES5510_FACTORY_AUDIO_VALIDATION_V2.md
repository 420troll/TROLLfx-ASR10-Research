# ES5510 Factory Audio Validation V2

## Scope and baseline

Work is isolated on `research/factory-audio-validation-v2`; the `research/rom50-capture` worktree was left unchanged. Baseline commit: `93a23262726fc61a0bec48be1d0b16d6dd80067a`.

Before changes, `python3 -m unittest discover -s tests/audio_validation -v` passed 3 tests. The existing runner compared pass-through and the original TROLLfx diagnostic delay across impulse, sine, sweep, seeded noise, and stereo phase inputs. At 44.1 kHz and 13,000 frames, all ten cases were sample-exact, with zero max/RMS deviation and no first divergent frame. Existing delay golden taps and values remain in `docs/ES5510_AUDIO_VALIDATION.md`.

The bounded 13,000-frame report has all 10 engine/algorithm cases at zero deviation and zero alignment offset. For the left-only impulse (frame 1,625), output taps are 24,000 at offset 0 and 13,199 at offset 11,025; no later echo falls inside this bounded render. The 997 Hz diagnostic-delay estimate is +0.0314228 dB over this shorter window. Stereo-difference RMS for impulse is 210.49 pass / 240.23 delay; seeded-noise is 13,426.94 / 13,782.33; quarter-cycle stereo-phase is 21,998.82 / 22,491.27. These figures describe the diagnostic fixtures only, not HALL REVERB.

## Trace and manifest additions

`run.py --trace` now emits a bounded one-frame execution trace from each engine per case, including instruction/PC, register writes, RAM pipeline activity, END and serial routing. The default path remains untraced. The trace is diagnostic tooling, not a firmware capture mechanism.

The external factory-state manifest contract is in `tools/audio_validation/factory_state_manifest.schema.json`; `factory_manifest.py` validates structure, payload hashes, load order, serial and memory configuration, and reset-pipeline declaration while reporting no payload bytes. It rejects runtime snapshots. Synthetic tests cover valid intake, incomplete runtime state rejection, payload hash verification, trace presence, and unchanged golden results.

## ROM-01 HALL REVERB decision

A local-only `ROM-01-HALL-REVERB/state.esp` was inspected with the existing capture summarizer. It contains a 160-word instruction store with the first END at index 88 (89 words), 192 GPR snapshots, 22 special-register snapshots, 1,048,576 DRAM words, memory settings, serial mode, PC/control state, and a post-run DRAM image. The first END is consistent with the observed 89-word loaded program.

It is **not** sufficient to claim reproducible factory playback. The T551CAP v1 format is explicitly a research snapshot, not a complete resumable DSP save state. It omits in-flight ALU/MAC pipeline operations, RAM pipeline stages, DOL FIFO/pointers and other execution state at the capture frame. The capture also records a running machine rather than the original cold-load order and exact point at which zero/initialized DRAM and program state were established. No public data or guessed defaults were used to fill these gaps. The HALL factory-vs-MAME audio comparison was therefore not run.

## What deterministic replay needs

At minimum: exact active instruction words and active boundary; all 192 GPRs; all 22 special registers; full 24-bit memory configuration and DLength/base registers; full external DRAM contents or a proven cold-load initialization rule; serial direction/routing and sample-rate evidence; HALT/load/RUN order; and a known frame boundary with either a reset pipeline after cold load or complete in-flight ALU/MAC/RAM/DOL state. Parameter updates must be captured as ordered writes, not inferred from labels.

## Numerical audit and limitations

See `docs/ES5510_AUDIO_VALIDATION.md` for the implementation comparison table. The audit found signed left-shifts of negative values in the ASR-10 core's MAC/ASL scaling and serial/DIL conversion paths. These expressions were replaced with equivalent multiplication or unsigned shifts. A negative-input UBSan build and one-frame original/MAME delay smoke test then completed without diagnostics. Signed right-shifts used for sign extension and PCM rounding are still implementation-defined in C++17 and should be made explicit before claiming cross-compiler reproducibility. Arithmetic overflow, special flags, all ALU opcodes, and all address edge cases are not yet exhaustively compared.

The MAME-derived adapter and ASR-10 emulator agree for the tested programs. Internal agreement alone does not establish processor silicon accuracy, and no factory audio accuracy claim is made.

## Reproduction

```sh
python3 -m json.tool tools/audio_validation/factory_state_manifest.schema.json >/dev/null
python3 -m unittest discover -s tests/audio_validation -v
python3 tools/audio_validation/run.py --out /tmp/es5510-v2 --frames 13000 --trace
```

All generated traces/audio/reports stay under `/tmp` or a caller-specified private output directory. No ROM, EFE object, factory program, capture, or factory audio was added to Git.
