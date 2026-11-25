# ASR-10 Factory DSP Parameter Mapping V5

## Result

V5 adds **30 adjacent value mappings** from OS 3.53 factory editor actions for seven prioritized effects. Each mapping was selected by exact V4 cursor/page position, captured at the 22-character LCD, changed one step, reversed, and repeated twice. The listed GPR writes and their ordering are present in the machine-readable catalog and runtime header.

The native ES5510 comparison accepted all 30 parameter events and returned finite stereo audio. **23 controls produced a nonzero output difference** over a 65,536-frame comparison window (1.365 seconds at 48 kHz). Seven remain register-verified but have no demonstrated audio difference under that signal and are not marked runtime-ready.

Slot 02 remains deferred and was not selected, probed, relabeled, or modified.

## New mappings

| Effect | New register-verified controls | Native audio difference |
|---|---:|---:|
| HALL REVERB (01) | 5 | 5 |
| ROOM REVERB (03) | 5 | 5 |
| DUAL DELAYS (04) | 3 | 2 |
| CHORUS+REVRB (06) | 5 | 2 |
| FLANGER+REV (08) | 3 | 0 |
| 8-VOICE CHOR (38) | 6 | 6 |
| PITCH SHIFT (39) | 3 | 3 |
| **Total** | **30** | **23** |

The exact displayed strings, variation, editor order, two observed values, ordered GPR groups, documented-range evidence and native measurements are in [ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05.json](ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05.json). Runtime definitions are in [es5510_factory_parameter_discovery_v05.hpp](../include/trollfx/es5510_factory_parameter_discovery_v05.hpp).

### Codex 2 integration

Include `trollfx/es5510_factory_parameter_discovery_v05.hpp` and call `parameter_discovery_v05::append_verified_parameters(descriptor)` on the validated slot descriptor before registry registration. Keep V2 and V3 appenders for their existing controls. Expose a V5 control only when its JSON `runtime_ready` field is `true`; use `parameter_id`, `display_name`, and the two exact `verified_points`. `FactoryRuntime::setParameter` rejects values outside those points. The seven `runtime_ready=false` entries remain visible as unavailable metadata rather than generic or interpolated controls.

Documented ranges are descriptive metadata only. `FactoryRuntime` accepts only the two measured points for each V5 control. No intermediate points or full curves were generated. Signed LCD text such as `+9` and `-5` is retained separately from its numeric runtime value. No nonlinear or lookup-table curve is claimed from adjacent samples.

## Ordered multi-register findings

The probes found ordered groups for HALL DIFFUSION (six GPRs), HALL and ROOM PRE-DELAY TIME (two each), ROOM HI FREQ BANDWIDTH (GPR `0x02` then `0x00`), CHORUS+REVRB REVERB DECAY TIME (five GPRs), CHORUS+REVRB DIFFUSION (three), FLANGER CENTER (four), FLANGER WIDTH (two), and 8-VOICE CHOR LFO RATE (eight). Exact point values and order are recorded in the JSON; no interpolation is applied.

HALL and ROOM detune rate/amount each updated one GPR. The 8-VOICE/PITCH rate controls also update different register sets; the 8-VOICE LFO RATE point changed eight coefficients together, while PITCH SHIFT LFO RATE changed GPR `0x90`.

## Controls withheld from runtime-ready status

These seven controls passed reversible OS edits and scheduled GPR writes, but the native pair comparison produced `difference_rms=0` and `difference_peak=0` in the stated test. They remain in the catalog as register-verified evidence and have `runtime_ready=false`:

- DUAL DELAYS `BS1 TIME R` (700→701)
- CHORUS+REVRB `BUS1 REV AFTER CHOR` (25→26)
- CHORUS+REVRB `CHORUS FEEDBACK` (+9→+10)
- CHORUS+REVRB `CHORUS RATE AMT` (39→40)
- FLANGER+REV `FLANGE CENTER` (19→20)
- FLANGER+REV `FLANGE WIDTH` (19→20)
- FLANGER+REV `FLANGE DEPTH` (99→98)

The tested signal was stereo sustained tones with an impulse during warm-up. A zero difference means no native response was demonstrated by this comparison; it does not establish that the OS field is ineffective. Host-side mixing, program state, write cadence, or a more suitable input/window may explain the result. Keep these controls disabled in a user-facing runtime until follow-up evidence shows the intended effect.

## Probed but not promoted

- HALL `HI FREQ BANDWIDTH` changed the LCD and produced reversible writes to GPRs `0x00` and `0x02`, but repeated final-state deltas were not stable. It is not in the runtime catalog.
- CHORUS+REVRB `HI FREQ DAMPING` had no isolated stable delta in this capture.
- ROOM `REVERB MIX BUS1` wrote GPR `0x7C`, but later/periodic writes obscured a stable final-state delta. It is not promoted.
- DUAL DELAYS `BUS1 FEEDBACK` did not yield a stable delta. `BUS2 FEEDBACK` did (25→26, GPR `0x07`).
- FLANGER+REV `FLANGE FEEDBACK` was captured at variation 1 (`+58→+59`, GPR `0x86` `0x4B0000→0x4C0000`) and variation 3 (`-78→-77`, GPR `0x86` `0x9C0000→0x9D0000`). The display edits reversed exactly, but the final register state was not stable across the broad write window; variation 3 also had 41 GPR `0x86` writes in its no-edit baseline. Neither sign is promoted as a static runtime mapping. Both probe references and their reason for exclusion are in `unresolved_probes` in the JSON.

## Native comparison method

Each comparison loads the corresponding RUN-boundary checkpoint from the existing trusted private package audit, validates the checkpoint and firmware schedule SHA-256 values, warms each runtime with 32,768 frames, schedules one exact parameter point at the same absolute DSP frame, and renders 65,536 further stereo frames at experimental 48 kHz. The program image and audio input are identical for both runs. Output WAVs and the detailed private report remain outside Git.

Measured outputs were finite for all 30 pairs. Differences ranged from very small coefficient changes to large timing/pitch responses. The machine-readable report contains before/after RMS, difference RMS/peak, and signal peaks for each control.

## Reproduction

From the repository root, using the authorized local OS 3.53 installation:

```sh
python3 tools/parameter_controls/run_factory_dsp_mapping_probe_v05.py \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --selector-inventory /home/gamer/research/private-results/asr10-all-50-effects/inventory.json \
  --slot 1 --variation 1 --field 'DIFFUSION' --repetitions 2 \
  --output /home/gamer/research/private-results/asr10-factory-dsp-parameter-mapping-v5/probes
```

Build the CLI and run focused tests:

```sh
bash tools/build_research_cli.sh
python3 -m unittest tests.parameter_controls.test_factory_dsp_mapping_probe_v05 tests.parameter_controls.test_v05_runtime_catalog -v
```

Generate paired native audio and update the catalog's audio/runtime status:

```sh
python3 tools/parameter_controls/run_v05_native_audio_validation.py \
  --audit /home/gamer/research/private-results/asr10-all-50-effects/production-provider-audit.json \
  --output /home/gamer/research/private-results/asr10-factory-dsp-parameter-mapping-v5/native-audio \
  --binary /tmp/trollfx-v05-audio-compare
```

The audio tool checks private checkpoint and schedule hashes before loading packages. It writes rendered WAVs and its detailed JSON report only under the requested private output directory. Do not copy private probe logs, captures, checkpoints, or WAVs into Git.

## Remaining work

The next useful experiments are to isolate recurring writes for feedback and chorus/flanger controls, determine whether bus mixing is partly host-side, and use longer algorithm-specific stimuli for delay and modulation controls. Additional values are required before any exact nonlinear curve or full display range can be mapped to registers.
