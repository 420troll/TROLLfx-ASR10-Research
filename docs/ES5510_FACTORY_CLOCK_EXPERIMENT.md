# ES5510 Factory Clock Independence Experiment

## Result

The 29,761.89453125 Hz HALL rate is an observed OS 3.53 emulator configuration, not a rate encoded by the HALL instruction image and not an intrinsic ES5510 per-program requirement established by this evidence. The emulator executes the unchanged authentic HALL image at 44.1 kHz when OTTO is configured for 24 voice slots, and at an explicitly forced 48 kHz. ROM-02 likewise executes at 48 kHz under an explicit emulator override. The forced 48 kHz cases demonstrate capability of this software harness only; they do not prove that the physical OTTO/ES5510 system supports those oscillator configurations.

A same-checkpoint, same-eight-lane-input native-engine experiment produced bit-identical serial output at the tested rates (32,768 frames per comparison). This isolates the standalone ES5510 numerical frame sequence from the scheduler and shows that its per-frame arithmetic does not receive the clock rate. OS-level alternate-rate runs also retained the active program and GPR image, but their DBASE SPR changed, so their different direct outputs cannot be attributed solely to clock cadence. An impulse probe did not yield a useful reverb decay curve, even at 100,000 frames; time-domain decay behavior therefore remains unmeasured here.

No physical hardware or independent silicon measurement was available. The work establishes what this emulator and its OS firmware do, and what the standalone arithmetic does when clock labels change. It does not establish the complete physical factory time response at alternate clocks.

## Clock-control architecture

The source has three distinct rates:

1. The emulated 16 MHz 68000 host CPU cycle clock.
2. The OTTO-derived ESP/serial frame clock, computed by `ES5506::sample_rate(clock) = clock / (16 * (active_voice_register + 1))`. The active voice register is `N`; it schedules `N+1` voice slots.
3. Host output rate (`Asr10::out_rate`, default 44,100 Hz), consumed by the DAC/resampling path. The host WAV rate is not the ESP instruction rate.

In `Asr10::run`, CPU-cycle chunks accumulate OTTO ticks using `otto_acc += cycles * (otto_master()/cpu_clock)`. A frame is emitted for each `16*(active_voice_register+1)` OTTO ticks. `otto_frame()` obtains routed input at this frame rate, executes one ESP frame, then the DAC/output path converts the stream to `out_rate`. The OTTO master-clock choice in this source is 15,238,090 Hz for more than 24 voice slots and 16,934,400 Hz for at most 24 slots. Consequently:

- register 31 (32 slots): 15,238,090 / 512 = 29,761.89453125 Hz.
- register 23 (24 slots): 16,934,400 / 384 = 44,100 Hz.

The source comments describe the latter as the OS “23 VOICE 44K” mode; the physical select line/clock-generation details are not fully identified. Firmware writes OTTO register 11 to set the active voice register. Effect selection itself is not an input to the rate formula. The observed HALL/ROM-02 rate association results from firmware’s selected voice configuration during load.

The experiment added opt-in environment overrides for voice slots and DSP rate, gated on environment variables and explicitly labeled experimental. Unset, existing scheduling behavior is unchanged. The direct frame replay tool uses its rate argument only to label frame time; it does not modify the ESP arithmetic. The native and MAME arithmetic implementations were not changed.

## Fresh baseline captures

Two fresh OS 3.53 emulator processes were captured per effect with the authorized private assets. Each pair passed the existing repeatability checks. Private raw logs, snapshots, hashes, WAVs, ROM/OS material, and payloads remain outside Git.

| Effect | RUN / first instruction | Image | Voice register / slots | OTTO master | Measured DSP rate | Host WAV | Route |
|---|---:|---:|---:|---:|---:|---:|---|
| ROM-01 HALL REVERB | frame 855973 / PC 0 | 89 words | 31 / 32 | 15,238,090 Hz | 29,761.9034 Hz from frame/cycle delta (source formula 29,761.89453125) | 44,100 Hz | SER2 in, SER1 out |
| ROM-02 44KHZ REVERB | frame 905028 / PC 0 | 60 words | 23 / 24 | 16,934,400 Hz | 44,099.9999 Hz from frame/cycle delta (source formula 44,100) | 44,100 Hz | SER2 in, SER1 out |

Small differences between measured frame/cycle quotient and the nominal formula are finite-window/cycle scheduling effects, not a second configured rate. The observed active program digests matched the respective baseline images across rate variants (checked privately).

## Controlled experiment matrix

All alternate-rate cases were captured twice from fresh emulator processes. The same original factory image was loaded; active instruction image and GPR image matched the corresponding baseline. Every host WAV remained 44,100 Hz. No GPR, delay length, or program instruction was edited by the capture tooling.

| Case | Configuration | Measured rate | Interpretation |
|---|---|---:|---|
| A: HALL baseline | firmware register 31, 32 slots, standard low OTTO clock | 29,761.9 Hz | Original observed setup |
| B: HALL alternate | experimental 24-slot override, modeled high OTTO clock | 44,099.9 Hz | Emulator’s supported alternate voice/clock mode; not effect-derived |
| C: ROM-02 baseline | firmware register 23, 24 slots, high OTTO clock | 44,100.0 Hz | Original observed setup |
| D: ROM-02 alternate | force 48 kHz by experiment-only clock override | 48,000.1 Hz | Harness override, not evidence of authentic OTTO oscillator support |
| HALL forced alternate | force 48 kHz with 32 slots | 48,000.1 Hz | Harness override, not authentic-hardware evidence |

The 44.1 kHz HALL case changes active voice-slot configuration as well as frame rate; it should not be interpreted as an isolated oscillator-only change. The two 48 kHz cases bypass the source’s two modeled OTTO oscillator choices. All remain controlled software experiments, not physical hardware settings.

## Frame-domain and time-domain comparisons

For each effect, one baseline RUN checkpoint and the corresponding captured eight-lane input trace were replayed through the native ES5510 engine at multiple rate labels:

| Effect | Compared rates | Frames per comparison | SER1 lane sample mismatches | Peak error | RMSE |
|---|---|---:|---:|---:|---:|
| HALL | 29,761.8945 vs 44,100 | 32,768 | 0 | 0 | 0 |
| HALL | 29,761.8945 vs 48,000 | 32,768 | 0 | 0 | 0 |
| ROM-02 | 44,100 vs 48,000 | 32,768 | 0 | 0 | 0 |

The replay keeps the same captured DSP checkpoint, same serial inputs, and same frame order. Its rate affects seconds/frame only. This directly supports numerical frame-sequence independence for this standalone engine path; it does not exercise OTTO scheduling, the OS, clock-dependent host events, or physical chip timing.

In OS-integrated same-frame 440 Hz input probes, selected input samples were identical across HALL rate variants, but output differed. Inspection found DBASE was the only changed special-register image between each alternate-rate checkpoint and the baseline; GPR and instruction image matched. Because the captured run state was not otherwise equal, this output comparison is confounded and is not evidence of a rate-only arithmetic change. The direct impulse probe produced one nonzero output frame and no usable decay envelope, including a longer 100,000-frame HALL run. Consequently, early reflections, decay duration, modulation period, stereo decay, and time-domain equivalence are unresolved. The probe did not demonstrate an unstable, silent, or clipped output; the ordinary 32,768-frame sine captures were nonzero and unclipped, but are not a substitute for a measured impulse response.

A pure fixed-frame delay has time duration proportional to `1 / DSP_rate`: the same frame delay at 44.1 kHz takes 29,761.8945/44,100 = 0.6749 of its duration at the original HALL rate; at 48 kHz it takes 0.6200. This is a mathematical inference, not a measured factory reverb decay result.

## Effect-switching sequence

The OS selection UI and active RUN clock are not synchronous. In two fresh processes, the measured selector sequence was HALL → ROM-02 → HALL, with repeatable clock-write timelines:

- At ROM-02 selection display (cycle 444,756,026; frame 899,137), OTTO still had HALL’s register 31 / 29.7619 kHz configuration.
- ROM-02 HALT/reset and DRAM clear followed; upload began at cycle 447,610,410 (the exact frame is not needed for the clock-boundary conclusion). During upload/initialization, firmware wrote register 31 briefly, then register 23 at cycle 447,799,750/frame 904,886. RUN began at frame 905,028 with register 23 / 44.1 kHz.
- At the HALL return selection display (cycle 538,832,690; frame 1,155,795), OTTO still had ROM-02’s register 23 / 44.1 kHz configuration.
- HALL HALT/reset, DRAM clear, and upload followed. Firmware wrote register 31 at cycle 541,936,090/frame 1,164,349, briefly configured a startup register-0 state, and restored register 31 at cycle 541,955,572/frame 1,164,470. HALL RUN began at frame 1,164,585 with 29.7619 kHz.

Thus the desired clock/voice setting is restored by OS writes during the load interval, after HALT/reset has begun and before RUN. It does not change at the selector display event. In this source model voice count and derived OTTO rate are coupled by register 11 plus clock selection; there is no separate effect-rate field. DBASE changes across alternate-rate checkpoints were observed, but this experiment did not establish whether that difference is caused by rate configuration or another initialization detail. The two-process repeated transition timelines are direct emulator observations, not independent hardware observations.

## Explicit answers and evidence classification

| Question | Finding | Evidence class |
|---|---|---|
| Is 29,761.89453125 Hz a hard HALL requirement? | Not established as a hard algorithm requirement. It is the measured/formula rate of the observed 32-slot OS configuration. | Direct emulator measurement + source-established formula; physical silicon unresolved |
| Can HALL execute at 44,100 Hz? | Yes in this emulator under the alternate 24-slot configuration; the original HALL image remains active. | Direct emulator measurement |
| Can HALL execute at 48,000 Hz? | Yes with an explicit experimental rate override. | Direct emulator measurement under harness override only |
| Does HALL preserve numerical DSP behavior at another rate? | Same-checkpoint native frame replay was bit-identical at 29.7619/44.1/48 kHz. Full OS captures are confounded by DBASE state. | Direct engine experiment; full OS isolation unresolved |
| Does HALL preserve factory time-domain behavior? | Not established. Fixed-frame delays necessarily occupy less time at faster rates; a valid decay/early-reflection probe was not obtained. | Mathematical inference; acoustic/time-domain result unresolved |
| Is ROM-02 constrained to 44.1 kHz? | Its observed OS configuration is 44.1 kHz; the standalone emulator executes its unchanged image at 48 kHz under override. No silicon constraint was measured. | Direct emulator measurement; hardware limitation unresolved |
| Can a future Force plug-in use a fixed 48 kHz DSP clock without changing factory effects? | It can preserve frame-domain arithmetic in this engine, but cannot preserve time-domain delay behavior simply by changing cadence. Preserve a virtual factory clock and convert at I/O, or deliberately accept/research time scaling. | Recommendation based on direct engine result + mathematical inference |
| Which SRC stages are necessary? | When device/input and virtual DSP rates differ, rate conversion is needed at the relevant input/output boundary. The emulator separately resamples input to OTTO cadence and DAC output to host rate. A plug-in need not copy the TDA1541 model unless hardware DAC emulation is desired. | Source-established architecture; plug-in design inference |

## Recommendation

Do not hardcode 29,761.8945 Hz as an intrinsic HALL property. Keep **virtual DSP rate** distinct from **host/device I/O rate** in a future real-time engine. To preserve factory timing, run each effect at its captured virtual OTTO cadence and convert input/output to the device’s rate. A fixed 48 kHz DSP cadence is viable for frame-domain execution in the current native engine, but it changes fixed-frame time constants unless delay scaling or another timing-preservation mechanism is introduced and independently validated. Keep the original native and MAME-derived arithmetic implementations unchanged; this clock study is not evidence for changing delay-RAM addressing or other production DSP arithmetic.

## Reproduction and artifacts

The repository contains `tools/audio_validation/clock_experiment.py`, `capture_factory_clock_variant.py`, `capture_effect_switch_clock.py`, and the standalone `clocked_es5510_replay.cpp` plus its build script. Captures require the authorized local OS/ROM inputs and write raw artifacts only to a caller-selected private output directory. Use `--help` on capture scripts for options; do not place firmware, ROMs, EFE payloads, raw logs, snapshots, or audio in Git. The test module `tests/test_clock_experiment.py` exercises clock formulas, CPU-cycle scheduling, fixed-frame comparison without automatic alignment, and stimulus extraction/metrics.

The complete existing HALL V4 and ROM-02 replay regression suite plus the new scheduler tests passed: `python3 -m unittest discover -s tests -v` (60 tests). Proprietary/private captures and their provenance hashes remain outside the repository.
