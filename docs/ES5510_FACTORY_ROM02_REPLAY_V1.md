# Authentic factory ROM-02 44KHZ REVERB replay V1

## Result

The authentic OS 3.53 ROM-02 44KHZ REVERB program now runs from its observed RUN checkpoint in both standalone ES5510 engines. The active image has 60 instructions, END at word 59. Its source EFE, ordered OS upload, and checkpoint were correlated with the private source comparator. A replay-ready ROM-02 manifest and all payloads were generated outside Git from two fresh, byte-identical RUN captures.

Native output is sample-exact against the OS 3.53 emulator for all 32,768 captured DSP frames. MAME-derived output matches through 4,096 frames, then diverges. This completes primary execution and native-reference replay; it does not establish physical-chip accuracy because the OS emulator uses the native ES5510 core.

## Evidence and load sequence

The inspected research baseline was:

| Branch / commit | Use |
|---|---|
| `research/es5510-hall-replay-v4` / `f93030b` | Reusable RUN checkpoint, event scheduler, and standalone runner baseline |
| `research/es5510-hall-reference-capture-v2` / `464b8bb` | OS serial, clock, source-position map, and boundary-capture instrumentation |
| `research/es5510-factory-hall-comparison-v1` / `32ddea7` | Existing strict comparison interface |
| `research/es5510-hardware-state-v1` / `e1a1934` | HALT, DRAM-clear, pipeline-reset, and serial-latch evidence |
| `research/factory-efe-reconstruction-v2` / `0d4c5a5` | ROM-02 EFE layout and source/runtime correlation |
| `research/es5510-delay-ram-addressing` / `437f986` | Prior delay-address arithmetic findings; no arithmetic was changed here |
| `research/asr10-loader-disassembly-v2` / `289ad20` | Available loader timing/disassembly work |

No ROM-02-specific loader-analysis or reference-capture branch was available from the remote when checked. No task agent's worktree or background branch was assumed complete or modified.

The actual load was captured in two fresh boots after an ascending OS selector sweep. This matters: the earlier ROM-50 stable-display snapshot called ROM-02 44KHZ REVERB contained an 89-word HALL image. The display is a selection marker, not the load boundary. That snapshot was rejected. The accepted target is the later RUN checkpoint whose program bytes match the source-correlated ROM-02 image.

| Event | ESP frame | Verification |
|---|---:|---|
| PA4 HALT / pipeline reset acknowledgement | 903301 | Pending pipeline slots and DOL queue reset |
| Full DRAM clear | 903301 | RUN checkpoint contains zero nonzero DRAM words |
| Instruction upload starts | 904447 | Ordered host trace captured |
| PA4 RUN release | 905027 | Followed by the first running frame |
| RUN checkpoint / first instruction / first input and output | 905028 | PC 0, all observed at the same DSP frame boundary |

The load report records 61 instruction-memory commits to 60 unique addresses and 283 register commits in the HALT-to-RUN event window. The committed active image is 60 words through END 59. Independent EFE comparison confirms 60/60 active instruction matches and all 58 paired GPR initializer values. The source layout contains 58 paired records, one instruction-only record, and one alias: active instruction 58 resolves to source instruction 0. The loader emits two instruction-only host commits for the alias and final instruction. The alias bytes are checked against the active program before replay.

The checkpoint gate verifies identical full capture bytes from both boots, including the 60-word active program, all 192 GPRs, all 22 SPRs, zeroed 1,048,576-word DRAM, memory configuration, serial latches, and runtime boundary. The RUN snapshot follows the measured pipeline-reset acknowledgement and precedes PC 0's first instruction. Engines load the observed checkpoint; the manifest is used only to validate that state.

The OS logged 202 post-RUN GPR events. Both boots have the same event sequence. Replay applies each write only when the log places it between output frame *n* and input frame *n+1*; it does not infer sub-frame timing. The native and MAME engines start from the same captured checkpoint and receive the same eight-lane serial input frames. Initial registers match, and the event scheduler applies all 202 writes.

## Clock, routing, and reference validation

ROM-02 runs with 23 active voices, a 16.9344 MHz OTTO clock, and a 44,100 Hz DSP frame rate. Host output is also 44,100 Hz. The observed route is `-1,-1,1,-1`: input SER2 L/R (lanes 4/5), effect output SER1 L/R (lanes 2/3), and host serial mode `0x48`. The captured first input sample is already present in the RUN checkpoint's serial latches.

The two 32,768-frame OS runs have identical input/output lane traces, identical RUN snapshots, identical startup and post-RUN event histories, and identical host WAVs. The 32,768-entry host source-position map was checked against its PCM16 WAV values. No sample shifting, correlation search, normalization, or resampling was used.

## Standalone and OS comparison

| DSP window | Native vs OS | MAME-derived vs OS | Native vs MAME |
|---:|---|---|---|
| 256 | Exact | Exact | Exact |
| 4,096 | Exact | Exact | Exact |
| 32,768 | Exact | Diverged | Diverged |

Native has zero SER1L/SER1R mismatches at each window. MAME has zero mismatches through 4,096 frames. Over 32,768 frames, MAME differs on 7,398 serial-lane samples: 4,101 on SER1L (peak absolute error 26, RMS 0.5445) and 3,297 on SER1R (peak 17, RMS 0.4501).

The earliest observable native/MAME internal-state difference is after frame 909222 (relative sample index 4,194), when two registers differ; the first reported register is GPR `0x4B`. Instruction tracing at that frame locates the first differing event at PC `0x00`, a delay-RAM request whose engine addresses differ by one word. The first serial-output difference follows at sample index 4,252, absolute frame 909280, on SER1L. The address disagreement is consistent with the previously documented native/MAME delay-wrap difference. No production DSP arithmetic was changed.

The OS host WAV mapping was validated and the two OS WAVs match each other. A standalone host-DAC WAV was not produced, so OS-versus-standalone 44.1 kHz host WAV comparison remains open.

## HALL compatibility and tests

The new profile-driven runner also replayed ROM-01 HALL V4 from the same existing evidence. It preserved the established result: native matches the OS for 256, 4,096, and 32,768 frames; MAME matches through 4,096 and diverges at the known 32,768-frame point. The original `replay_hall_from_boundary.py` was run against the V4 private inputs as well; its strict state gate passed and it reported the same expected MAME divergence.

`python3 -m unittest discover -s tests -v` passed all **52 tests**, including the HALL replay tests and new profile, alias, event-boundary, and fixed-index numerical comparison tests. The research CLI built successfully. The new capture script recreated and validated two fresh ROM-02 captures; the private manifest passed `factory_manifest.py --require-replay-ready`.

## Reproduction

Use private OS ROMs, OS 3.53 disk image, and ROM-02 EFE object paths. All output paths must stay outside the checkout.

```sh
python3 tools/audio_validation/capture_factory_reference.py \
  rom02-44khz-reverb-v1 \
  --roms /private/asr10/roms \
  --disk /private/asr10/os353.img \
  --run-frame 905028 \
  --out /private/results/rom02-reference \
  --cli build/research-cli/asr10-cli

python3 tools/audio_validation/prepare_factory_manifest.py \
  rom02-44khz-reverb-v1 /private/results/rom02-reference \
  --run-frame 905028 \
  --efe-object /private/ROM02-44KHZ.payload.bin \
  --out /private/results/rom02-manifest

python3 tools/audio_validation/factory_manifest.py \
  /private/results/rom02-manifest/factory-state.json --require-replay-ready

python3 tools/audio_validation/replay_factory_from_boundary.py \
  rom02-44khz-reverb-v1 \
  /private/results/rom02-manifest/factory-state.json \
  /private/results/rom02-reference \
  --run-frame 905028 \
  --out /private/results/rom02-replay \
  --diagnostic-frame 909222
```

The replay command returns status 2 when a valid capture produces a numerical mismatch; it still writes the private comparison summary. The source/profile gate or any RUN-boundary mismatch fails before standalone execution.

## Remaining limits

- ROM-02 has no physical ASR-10 capture in this work. The native match is against the same core used by the OS emulator.
- MAME/native delay-RAM addressing remains unresolved against silicon; its implementation was intentionally preserved.
- The standalone runner emits DSP serial samples, not DAC-resampled host WAV output.
- The RUN snapshot omits in-flight pipeline slots, but this boundary is accepted only after the observed HALT pipeline reset and before the first instruction; standalone loaders reset the modeled slots accordingly.
- ROMs, EFE objects, firmware, program/register/DRAM payloads, serial samples, WAVs, and full traces remain outside Git.
