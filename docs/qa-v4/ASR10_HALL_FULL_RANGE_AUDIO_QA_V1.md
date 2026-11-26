# ASR-10 HALL Full-Range Audio and Runtime QA

**QA branch baseline:** `qa/asr10-v4-gui-independent` at `6ebe633b76d2c7c5669bacbac54e2d95cf070a2d`  
**Codex 1 runtime:** `research/asr10-full-factory-parameter-recovery` at `6779dc8a93dbecb30c3ad445ea24aeeb4ec9a03b`  
**Codex 2 editor:** `feature/asr10-force-pc-gui-simulator` at `0a25d72f83f6ad622771193d0c6bc064a59d75a0`

Earlier QA commits `17fe43e` and `35e2a0b` remain in this branch history. Their OS sweep and register reconstruction results are consistent with this run; the later runtime recheck at `6ebe633` pins the independent API check to Codex 1's published `6779dc8` source. No owner worktree was edited.

## Result

The OS-derived HALL raw/display/register mapping and the standalone runtime's ordered step API pass on an OS-seeded, schedule-free checkpoint. Native rendering with the actual validated RUN checkpoint and its firmware event schedule is finite, repeatable, and measurably responds across all 128 OS-derived register states.

**The production HALL editor is not ready for full-range native VST integration.** The authentic RUN checkpoint has an unknown raw 6E state, the validated package's post-RUN schedule contains GPR 6E writes that invalidate the step state, and the VST-bound 40/41 compatibility control currently emits a different register order while producing bit-identical audio. These are separate from the passing step algorithm tests.

## Preserved original-OS evidence

The two existing independent OS 3.53 HALL Variation 1 sweeps cover 128 raw codes, 100 display values, 28 duplicate-display buckets and 198 transition groups. The earlier numerical recheck confirms the original five-register order is `0x6E, 0x5B, 0x03, 0x04, 0x05`. The raw code is preserved for GPR 6E and the low byte of GPR 5B. The GPR 03–05 coefficient path uses `clamp(raw, 12, 76)`. This reconciles the previous 102/196 comparison: its 94 misses were the 16 codes below 12 and 78 codes above 76 when the coefficient input was not clamped.

The 40→41 OS transition's five write offsets are `[0, 3, 6, 8, 11]` DSP frames. The OS trace files and firmware remain in local private directories; only hashes and summary evidence are in Git.

## Native runtime audio

The runner takes expected GPR vectors only from the two original-OS sweep files. It loads the authentic ROM-01 HALL Variation 1 RUN checkpoint, validates the checkpoint, active program and firmware schedule against the local package audit, lets post-RUN scheduled writes settle, then applies each OS-observed raw-code GPR group through the standalone native `FactoryRuntime` at 29,761.89453125 Hz. It renders deterministic stereo sine-plus-noise input in varied block sizes.

- All 128 raw settings rendered 8,192 frames each; every sample was finite and all 128 output hashes differed.
- Eight 65,536-frame impulse-tail renders (about 2.2 seconds each) at short, duplicate, middle and long raw values were finite. The later RMS windows varied with the selected setting; raw 127's late-window RMS was about `0.00043`, versus about `0.000061` at raw 0. No normalization was applied.
- Six fresh repeated native runs at raw 0, 44, 51, 52, 53 and 127 had identical output hashes for each repeated setting.
- 1,000 adjacent alternating edits at 32-frame intervals completed 32,000 finite frames. This is an adjacent-step stress test, not a full-range modulation sweep.
- This compares the native runtime against OS-derived register values, not against original-OS audio at matching parameter settings. Exact factory audio equivalence remains **NOT TESTED**.

## Batched versus OS-staggered writes

The test warms two identical runtime instances from the same checkpoint and schedule. It applies the OS-observed raw-51→raw-53 group to one in one DSP frame, and to the other at offsets `[0,3,6,8,11]`. Both end with identical five GPR values and process 65,536 tail frames each; 131,072 output samples were finite.

The outputs are not bit-identical. Across the four measured windows (16, 112, 3,968 and 61,440 frames), difference RMS was respectively `7.63e-6`, `6.45e-6`, `6.50e-6` and `1.68e-5`; the largest measured difference peak was `9.16e-5`. The long-window output RMS was about `0.002275` for each path. No runaway feedback or non-finite output was observed in this run. These measurements do not establish inaudibility; listener testing was **NOT TESTED**. The data supports retaining the batched implementation for PC experimentation with a documented timing deviation, while preserving the staggered sequence as the reference for any later exactness work.

## Runtime API and package-state finding

The public step API passed 99 upward and 99 downward calls on a temporary checkpoint seeded from the authentic RUN state with OS-observed raw 0 values. All 128 raw codes, including both representations of duplicate display buckets, were visited; all 990 applied GPR writes were checked against the independent OS table. Reset restored the seeded raw state. This validates the API's stateful stepping and register calculation, but the isolated API fixture intentionally uses the legacy `EffectPackage` path without the production firmware schedule.

The unchanged authentic checkpoint starts with GPR 6E `0x2c0831`. The published runtime seeds a step state only when the low 16 bits of GPR 6E are zero, so this authentic state is correctly reported as unknown. The validated package schedule also includes later GPR 6E writes (including frames 348 and 364), which cause the generic package path to disable HALL stepping. Thus `stepHallDecayTime()` cannot currently operate on the authentic validated HALL package. The native adapter added by Codex 2 at `0a25d72` defaults its promotion gate off; its tests demonstrate the schedule-free behavior, not production package readiness.

The VST compatibility route also needs resolution: the published VST test records the five GPRs in order `0x03, 0x04, 0x05, 0x5B, 0x6E` for values 40/41, whereas the original OS order is `0x6E, 0x5B, 0x03, 0x04, 0x05`. Its two 65,536-frame HALL outputs are bit-identical despite those register writes. Unsupported value 99 remains pending and emits no DSP writes, which is the correct fail-closed behavior.

## VST non-finite input robustness

An independent raw VST2 `setParameter` probe against the native plugin showed NaN persisted for FX, Wet, In, Out and Bypass normalized parameters. The simulator's ordinary bridge clamps inputs before calling VST, so this probe used a temporary test-only bridge that invoked the plugin's actual VST2 `setParameter` callback directly. A second run sent a NaN audio input through the real native VST callback with HALL READY and found one non-finite output sample.

The SDK's `setNormalised()` uses a comparison-based clamp; both comparisons are false for NaN, so NaN reaches the stored atomic parameter. `getInt()` can then call `lround()` on that value. Separately, `ES5510DSPBackend::process()` multiplies audio input by gain and stores it in the dry delay without a finite check. Minimal corrective options for the owning implementation are to reject a non-finite normalized parameter before storage (preserving the last valid value), and to replace each non-finite audio input sample with zero before gain, dry-delay and DSP processing. This report does not patch either owner.

## Codex 2 editor schema audit

The published editor commit `0a25d72` corrects four serialized manual ranges and retains the correction citations:

| Slot | Parameter | Manual range in published schema |
|---|---|---|
| ROM-15 LARGE ROOM | Decay time | 0.20–150.0 s |
| ROM-16 HALL REVERB2 | Decay time | 0.70–250.0 s |
| ROM-18 LARGE PLATE | Decay time | 0.4–140.0 s |
| ROM-18 LARGE PLATE | Predelay time | 0–430 ms |

The corresponding values remain manual metadata, not OS-measured ranges or DSP mappings. The 12 OS2 44 kHz appendix algorithms remain in `OS2_44KHZ_APPENDIX`, explicitly outside the original 50 numbered factory slots. All 33 tests in the clean published editor worktree passed.

## Release decisions

| Gate | Decision | Reason |
|---|---|---|
| Native PC engine audio | **PASS for experimental package playback** | Real native runtime processes the validated HALL checkpoint; deterministic audio tests pass. |
| Native PC full-range HALL control | **NOT READY** | Authentic checkpoint raw state is unknown; production event schedule invalidates step state; VST route is not audibly effective and its write order differs from OS. |
| Standalone HALL step arithmetic/register groups | **PASS, isolated seeded state only** | 198 directional steps and 990 GPR writes match independent OS evidence. |
| ARMv7 release readiness for this HALL control | **NOT TESTED** | This QA did not build or validate a new ARMv7 artifact containing the HALL integration. |
| Physical Force installation/Q-Link behavior | **NOT TESTED** | No deployment or hardware modification performed. |
| Exact original-OS audio equivalence | **NOT TESTED** | Matching original-OS audio recordings for these parameter states were unavailable. |

## Reproduction

With the private local HALL capture, validated package schedule and two sweep JSON files present in the runner's defaults:

```sh
cd /home/gamer/worktrees/asr10-v4-gui-independent
python3 tools/force_gui_qa/run_hall_decay_audio_qa.py
```

The command compiles a temporary instrumented copy of the published runtime; the register accessor and temporary raw-seeded checkpoints are created only in a temporary directory and the local private output directory. No firmware, effect image, checkpoint, WAV or private state file is added to Git. The machine-readable measurements are in [ASR10_HALL_FULL_RANGE_AUDIO_QA_V1.json](ASR10_HALL_FULL_RANGE_AUDIO_QA_V1.json).
