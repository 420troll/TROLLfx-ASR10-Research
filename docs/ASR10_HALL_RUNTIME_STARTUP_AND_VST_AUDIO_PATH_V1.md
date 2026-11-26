# HALL Runtime Startup Ownership and VST Audio Path

Date: 2026-11-26
Research branch: `research/asr10-full-factory-parameter-recovery`
Base: `6779dc8`

## Result

The zero-difference HALL 40/41 result was caused by applying the coefficient group at DSP frame 0 while the authentic OS post-RUN schedule was still running. The schedule rewrote the same five coefficient GPRs and restored the factory value before the audio comparison. The parameter groups are active in the HALL program: post-initialization 40/41 renders differ, and the full-range 10/90 native renders differ substantially.

This work makes initialization completion and parameter-write completion observable in `FactoryRuntime`, defers verified parameter groups behind pending startup writes, and exposes that status through `FactoryRuntimeProcessor`. It does **not** claim that the present ASR-10 emulator VST3 wrapper processes the new factory runtime. That wrapper's audio callback still calls `Asr10Engine::process`; the validated factory runtime is currently connected to the standalone WAV host. The VST-specific comparison and VST 10/90 test remain blocked until a factory-runtime VST adapter exists.

## Authenticated test setup

The rerun used the local OS 3.53 ROM-01 HALL package after the QA runner validated the private provider audit, RUN-boundary checkpoint digest, firmware-schedule digest, two-boot references, and HALL program identity. No checkpoint, microprogram, reference capture, or WAV was added to Git.

The shared independent QA runner was run against this worktree's runtime source:

```bash
python3 tools/force_gui_qa/run_hall_extreme_range_audio_qa.py \
  --runtime-root /home/gamer/worktrees/asr10-full-factory-parameter-recovery \
  --private-output /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/hall-vst-integration-reference-rerun \
  --report /tmp/hall-vst-integration-rerun.json \
  --plots-dir /tmp/hall-vst-integration-plots
```

The source runner and independent measurements are on Codex 3's QA branch at `qa/asr10-v4-gui-independent`, commit `27cb9a2`, in `tools/force_gui_qa/run_hall_extreme_range_audio_qa.py` and `tests/force_gui_qa/test_hall_extreme_range_audio.cpp`.

The test loads a fresh RUN checkpoint for each render and uses stereo SER2 input and SER1 output. It processes DSP frames through the terminal event frame plus one frame, then applies the selected five-register OS-derived group and verifies all five GPRs before and after rendering. Stimuli are an L/R impulse (0.75/0.42) and a deterministic 0.5-second stereo noise burst (peak below 0.12); render length is 10 seconds, without normalization. The factory-rate mode is 29,761.89453125 Hz; experimental mode is 48,000 Hz.

## Startup and edit coordinates

The HALL schedule contains 213 post-RUN register events. Its final event is at relative DSP frame **12,983**, so initialization is complete only after processing DSP frame 12,983; the first safe parameter-write frame is **12,984**. The test processes 12,985 frames to get to that boundary.

At checkpoint load, the relevant GPR state is:

| GPR | Value |
|---|---:|
| `0x6E` | `0x2C0831` |
| `0x5B` | `0x100000` |
| `0x03` | `0x400000` |
| `0x04` | `0xC00000` |
| `0x05` | `0x600000` |

The schedule rewrites the coefficient family during startup. In particular, it writes GPR `0x6E = 0x340000` at relative frames 348 and 364; the surrounding write group finishes through frame 375. The end-of-startup group is:

| Order | GPR | Value |
|---:|---:|---:|
| 1 | `0x6E` | `0x340000` |
| 2 | `0x5B` | `0x080034` |
| 3 | `0x03` | `0x340000` |
| 4 | `0x04` | `0xCC0000` |
| 5 | `0x05` | `0x6ADFFF` |

The GPR order is the independently observed OS parameter-write order. The original early test queued decay 40 and 41 at frame 0. Subsequent startup writes replaced both groups with the factory state, so the renders were bit-identical. The fixed path keeps all firmware events and applies a requested verified group at frame 12,984, after all 213 events.

The regression tool now runs both cases explicitly. Its legacy-path control queues the two verified groups through low-level GPR writes at frame 0, processes silence until startup completes, verifies both instances end at the same factory group, and then renders identical stimulus. It reproduces the prior failure exactly: difference RMS and peak are **0** at both 48 kHz and 29,761.89453125 Hz. The corrected early-request path defers those same parameter groups until frame 12,984 and produces the same nonzero 40/41 metrics as an edit requested after initialization.

The runner reports `initialization_schedule_complete`, `firmware_writes_pending`, `parameter_writes_pending`, and `last_parameter_write_applied`. Acceptance into the event queue is not reported as application. An early edit initially reports unapplied and five parameter writes pending; after frame 12,984 executes, the count reaches zero and the last-write flag becomes true. The ordered parameter group is applied to the same `FactoryRuntime` instance that processes the following audio blocks.

## Audio results

The private 44-file rerun on this branch matched Codex 3's existing 44 float-WAVs **byte for byte**. Same raw-51 repeat renders were bit-identical across both stimuli and both rates.

Post-startup 40/41 settings use raw codes 51 and 53:

| DSP rate | Stimulus | RMS difference | Peak difference | Output RMS, 40 / 41 |
|---|---|---:|---:|---:|
| 48 kHz | impulse | `0.0000524594` | `0.000518799` | `0.000910827` / `0.000918646` |
| 48 kHz | noise burst | `0.000152528` | `0.00234985` | `0.0167848` / `0.0167924` |
| 29,761.89453125 Hz | impulse | `0.0000464281` | `0.000518799` | `0.00115276` / `0.00115781` |
| 29,761.89453125 Hz | noise burst | `0.000156922` | `0.00189209` | `0.0165937` / `0.0166064` |

Post-startup coefficient groups:

| Display | Raw | Ordered GPR values (`6E, 5B, 03, 04, 05`) |
|---:|---:|---|
| 40 | 51 | `330000, 080033, 330000, CD0000, 6BADFF` |
| 41 | 53 | `350000, 080035, 350000, CB0000, 6A0DFF` |
| 10 | 13 | `0D0000, 08000D, 0D0000, F30000, 7EADFF` |
| 90 | 115 | `730000, 080073, 4C0000, B40000, 52DFFF` |

The large display 10/90 comparison is from the independent native test-only OS-group renderer, not a production control. At 48 kHz, the 10-second noise-burst render has difference RMS **0.00813245**, peak **0.0782166**; 8–10 second tail RMS is **0.0000628351** for raw 13 and **0.00117723** for raw 115. At factory rate, the corresponding difference RMS is **0.00870020**, peak **0.0664368**; tail RMS is **0.0000627290** and **0.00175575**. This confirms a large audible-tail change in the native runtime. It is not VST-output evidence.

All samples were finite. QA metadata explicitly says physical hardware was not tested and exact factory-reference WAV equivalence was not established.

## Register consumers

Inspection of the active 89-word HALL program shows it reads all five registers in the edited group:

- `0x6E` at PCs `0x1F` and `0x4C`.
- `0x5B` at PCs `0x20` and `0x4D`.
- `0x03`, `0x04`, and `0x05` in coefficient paths at PCs `0x0F–0x11`, `0x19–0x1B`, `0x2C–0x2E`, and `0x46–0x48`.

Thus the groups are read by the loaded program, and the post-init audio differences demonstrate that they affect wet output in this runtime. The startup schedule is not a permanent owner of these registers; it only writes its values at the observed startup frames.

## Runtime changes

- `FactoryRuntime` marks validated startup writes separately from parameter writes and tracks initialization completion from the **maximum scheduled event frame plus one**, not event count alone.
- `setParameter()` defers both single-register and ordered multi-register verified values until after pending initialization events. Its completion flag only becomes true when the final group event executes.
- `scheduleInitializationRegister()` is used by the private-package audio adapter; it preserves firmware writes instead of filtering or suppressing them.
- `FactoryRuntimeProcessor::runtime_status()` exposes the actual owner runtime's state to the host. BUS controls now go through the verified descriptor path, so their applied status is observable too.
- The host package gate accepts the current `asr10-private-rom-effect-package-v1` only through `import_factory_effect_collection.validate_one()`, then requires exact checkpoint matches in both fresh-boot reference folders. The loader accepts that collection's five-column relative-frame CSV and the legacy seven-column absolute-frame CSV; both are bounded, and the terminal event frame determines completion.
- HALL Variation 1 raw stepping remains fail-closed. Checkpoint GPR `0x6E = 0x2C0831` is not a valid raw code, and the startup schedule has no correlated LCD/editor snapshot proving the original OS's active raw code at the end of initialization. The known 40/41 and 10/90 groups were supplied as test-only OS-derived write groups. No production full-range route is enabled.
- Non-finite audio input is zeroed before it reaches emulator input conversion or dry-delay storage. VST volume/state values use finite clamping at storage/callback boundaries.

## VST boundary and remaining work

This source tree's `plugin/source/asr10_plugin.cpp` callback calls `Asr10Engine::process()`, which drives the original emulator machine. It does not own `FactoryRuntime`, does not select a private validated factory package, and has no HALL decay parameter control; its VST parameter is the emulator's master volume. `FactoryRuntimeProcessor` is the backend of `trollfx-audio-host`, not that VST3 target. Therefore this change fixes and validates the factory runtime's initialization/edit ownership and the native WAV-host adapter, but it cannot truthfully report a VST 40/41 or VST 10/90 wet/final-output measurement.

The smallest next integration step is a distinct desktop factory-effects VST processor that owns `FactoryRuntimeProcessor` (or `FactoryRuntime`), loads only validated local private packages off the audio thread, uses the existing `processStereo` serial routing and reports `RuntimeStatus`. The existing ASR-10 emulator VST should remain unchanged as a separate instrument. Once that target exists, repeat the exact signal and coefficient comparisons against both its raw wet output and host-mixed output. No plugin installation or Force deployment was performed here.

## Verification

Focused native test:

```bash
bash tools/audio_validation/test_factory_runtime.sh
```

The test checks early parameter deferral through firmware startup, the applied-status transition, ordered five-register updates, variable blocks, finite inputs/outputs, and existing runtime controls. The native private-package HALL runner and exact Codex 3 WAV comparison are described above. The Python test suite was also run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Result after the final changes: 91 tests passed. The focused native runtime suite and experimental audio host build also passed.

An authentic private-package host smoke test also completed with `--backend runtime --effect hall --wet 1 --block 256 --bus1 28`: both HALL and ROM-02 packages passed validation; the HALL schedule completed with zero pending firmware writes, and the accepted BUS edit completed with zero pending parameter writes and `last_parameter_write_applied=true` at DSP frame 48,000. The latest 1-second stereo 48 kHz run took 105.8 ms (0.1058x real-time), reported 2 host frames of algorithmic latency, and estimated 3,388,416 bytes of runtime/host memory. Final PCM16 output RMS was 4332.87 versus input RMS 4242.17, peak 7059 versus 6000; output was not frame-identical to input (difference RMS 917.79). This is a short host smoke test with a verified BUS setting, not the requested VST decay comparison.

The ASR-10 VST3 target was not rebuilt: it is not the factory-runtime processor, `cmake` is not installed in this environment (`cmake: command not found`), and no local VST3 SDK is installed.
