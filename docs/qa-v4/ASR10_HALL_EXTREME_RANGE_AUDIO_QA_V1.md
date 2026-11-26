# ASR-10 HALL Extreme-Range Audio Validation

**QA branch:** `qa/asr10-v4-gui-independent` (based on `27cb9a2`)  
**Runtime source:** Codex 1 published revision `6779dc8`  
**Factory mapping source:** two independent OS 3.53 HALL Variation 1 sweeps already audited in this QA branch  
**Factory clock:** 29,761.89453125 Hz  
**Experimental clock:** 48,000 Hz

## Setup and repeatability

The runner validates the local private provider audit, authentic ROM-01 HALL RUN checkpoint hash, active program digest, and firmware schedule hash before building a temporary instrumented copy of `FactoryRuntime`. It loads the same authentic RUN checkpoint into a fresh runtime for every render, explicitly calls `reset()`, then processes all 213 validated startup firmware events through the last scheduled frame (12,983). It verifies identical post-schedule register state across runs.

The five OS-observed register values are applied through `setRegister()` at the same DSP frame as a **test-only comparison method**. One silent frame commits the group before the measured input begins. The runtime checks register state immediately before rendering and after the full tail. Each test run applied exactly 213 firmware writes and five test parameter writes. This does not add full-range control to the production VST.

The serial route is the validated stereo pair using host serial mode `0x48`, input port 2, output port 1. Input and output gains are 1.0; no normalization is applied. Each setting gets a 10 second render at its selected runtime rate. WAVs are stereo IEEE float32. Since standard WAV stores an integer sample rate, factory-clock files use a 29,762 Hz header; the actual runtime rate is retained in the report.

Stimuli are a one-frame stereo impulse (`L=0.75`, `R=0.42`) and a 0.5 second deterministic stereo noise burst (xorshift32 seed `0x5eed5510`, amplitude below 0.12), followed by silence. Their per-rate SHA-256 hashes are in the machine-readable report. The same byte-identical input is used for both settings in each pair at the same rate.

## Raw/display choices

The test covers raw values `0, 13, 32, 51, 52, 53, 96, 115, 116, 127`. Display selection follows the captured OS editor direction where a display has multiple raw representations:

- Display 10 uses raw 13; 25 uses raw 32; 75 uses raw 96.
- Display 90 uses raw 115 from the Up route. Raw 116 is its alternative duplicate representation and was rendered separately.
- Display 0 uses raw 0 at the lower endpoint; 99 uses raw 127 at the upper endpoint.
- Display 40 versus 41 uses raw 51 versus raw 53 from the captured Up route. Raw 52 is the alternate representation retained on the Down route for display 40.
- Raw 51 versus 52 is separately compared to test the two OS-observed representations of display 40.
- Raw 51 against itself uses a second fresh runtime load and reset. Its output is bit-identical in all four stimulus/rate combinations.

## Findings

The large settings produce clearly different late tails in the standalone runtime. The table gives the 8–10 second impulse-window RMS, averaged in power across the final twenty 100 ms windows. These values describe the measured envelope only; no RT60 is inferred.

| Comparison | 29.76 kHz late-tail RMS (low → high) | Ratio | 48 kHz late-tail RMS (low → high) | Ratio |
|---|---:|---:|---:|---:|
| Display 10 → 90 (raw 13 → 115) | 0.0000764 → 0.0006649 | 8.70× | 0.0000764 → 0.0009885 | 12.93× |
| Display 0 → 99 (raw 0 → 127) | 0.0000610 → 0.0007949 | 13.03× | 0.0000610 → 0.0011667 | 19.12× |
| Display 25 → 75 (raw 32 → 96) | 0.0000921 → 0.0004272 | 4.64× | 0.0000918 → 0.0005283 | 5.76× |
| Display 40 → 41 (raw 51 → 53) | 0.0001221 → 0.0001831 | 1.50× | 0.0001221 → 0.0001831 | 1.50× |
| Raw 51 → 52 (same LCD display bucket) | 0.0001221 → 0.0001644 | 1.35× | 0.0001221 → 0.0001644 | 1.35× |

At 29.76 kHz, the impulse peak was 0.749939 for the selected raw settings. Overall RMS rose from 0.0011456 at raw 0 to 0.0013318 at raw 127. At 48 kHz, the peak remained 0.749939; overall RMS was 0.0009028 at raw 0 and 0.0012390 at raw 127. Stereo cosine correlation (uncentered `sum(L*R)/sqrt(sum(L²)*sum(R²))`) decreased from 0.9197 to 0.7708 across raw 0→127 at factory clock, and from 0.9196 to 0.8083 at 48 kHz.

All 44 renders had finite output samples. The raw-51 fresh-run repeat pairs had zero difference RMS and peak. Register state matched the requested OS group before and after each render. There were no automatic shifts, gain matching, or normalization.

### Sample-level pair differences

Each cell is `difference RMS / difference peak` across all 10 seconds and both interleaved channels. This compares unmodified float output samples.

**29.76 kHz**

| Case | Impulse Δ RMS / peak | Noise-burst Δ RMS / peak |
|---|---:|---:|
| display 10 vs 90 | 0.000494436 / 0.0160828 | 0.0087002 / 0.0664368 |
| display 0 vs 99 | 0.000655548 / 0.0163269 | 0.0155924 / 0.0758362 |
| display 25 vs 75 | 0.000288426 / 0.0112305 | 0.00462092 / 0.0507812 |
| display 40 vs 41 | 4.64281e-05 / 0.000518799 | 0.000156922 / 0.00189209 |
| raw 51 vs 52 | 3.66907e-05 / 0.000274658 | 7.95792e-05 / 0.000946045 |
| same raw 51 vs 51 | 0 / 0 | 0 / 0 |
**48 kHz**

| Case | Impulse Δ RMS / peak | Noise-burst Δ RMS / peak |
|---|---:|---:|
| display 10 vs 90 | 0.000645482 / 0.0160828 | 0.00813245 / 0.0782166 |
| display 0 vs 99 | 0.000809754 / 0.0163269 | 0.0155423 / 0.098175 |
| display 25 vs 75 | 0.000341688 / 0.0112305 | 0.00437016 / 0.0560608 |
| display 40 vs 41 | 5.24594e-05 / 0.000518799 | 0.000152528 / 0.00234985 |
| raw 51 vs 52 | 3.96555e-05 / 0.000274658 | 7.75688e-05 / 0.00115967 |
| same raw 51 vs 51 | 0 / 0 | 0 / 0 |


## 29.76 kHz versus experimental 48 kHz

Both modes used the same checkpoint, reset state, completed firmware event sequence, register groups, gains, and 10 second duration. 48 kHz showed higher late-window RMS for the high raw settings (raw 127: 0.0011667 versus 0.0007949), while low raw settings had nearly equal late-window RMS. This confirms the experimental rate changes the measured time-domain behavior; it does not establish a simple speed multiplier or factory equivalence. The frame-based algorithm is running at a different rate, and no timing compensation was applied.

The four log-envelope plots show 100 ms RMS over the complete render. The vertical axis is logarithmic (`20 log10(native RMS)`), with no gain normalization:

- [Factory rate, impulse](plots/ASR10_HALL_FactoryReference_impulse_envelope.svg)
- [Factory rate, noise burst](plots/ASR10_HALL_FactoryReference_noise_burst_envelope.svg)
- [Experimental 48 kHz, impulse](plots/ASR10_HALL_Experimental48000_impulse_envelope.svg)
- [Experimental 48 kHz, noise burst](plots/ASR10_HALL_Experimental48000_noise_burst_envelope.svg)

## 40/41 VST zero-difference assessment

The prior independent VST test found values 40 and 41 emitted register writes but produced bit-identical HALL output. This standalone test applies the captured OS groups to the validated HALL checkpoint after completing the startup schedule. Display 40/raw 51 versus display 41/raw 53 is measurably different: at factory rate the impulse difference is RMS `4.6428e-5`, peak `5.188e-4`; the noise-burst difference is RMS `1.5692e-4`, peak `0.0018921`. Thus the OS-derived states do affect standalone native output in this controlled path. The VST zero-difference result is not explained by the effect being inherently insensitive at 40/41; the exact VST-side cause remains **under investigation**. This test does not prove that the production VST applies the same state or sequence.

## Reproduction and artifact location

From the QA worktree, with the local private package and two OS sweep traces available:

```sh
cd /home/gamer/worktrees/asr10-v4-gui-independent
python3 tools/force_gui_qa/run_hall_extreme_range_audio_qa.py
```

The command writes 44 native float WAVs to the local private output directory:

`~/research/private-results/asr10-v4-gui-independent/hall-extreme-range-20261126/`

No checkpoint, ROM, firmware, package payload, raw audio or WAV is committed. The report includes each WAV's SHA-256 and all per-run measurements. Default duration is 10 seconds; `--seconds` accepts 8–12 seconds.

## Status

- Standalone runtime response across requested settings: **PASS**.
- Startup event completion, routing, register readback, finite output: **PASS**.
- Fresh-run raw-51 repeatability: **PASS, bit-exact**.
- Meaningful 29.76 kHz / 48 kHz envelope comparison: **PASS, measured**.
- Exact original-OS audio equivalence and RT60: **NOT TESTED**.
- Production VST full-range behavior and 40/41 root cause: **NOT VERIFIED**.
- Physical Force behavior: **NOT TESTED**.
