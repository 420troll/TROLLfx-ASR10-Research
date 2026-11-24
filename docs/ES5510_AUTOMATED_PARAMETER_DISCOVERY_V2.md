# ES5510 Automated Factory Parameter Discovery V2

## Result

The OS 3.53 front-panel controller now selects a factory slot, waits for the selector sweep to finish, opens Edit → Effects, records the live variation screen, walks the live LCD one parameter at a time, and performs repeated one-step edits with reversible-state checks. It exposes an evidence-bounded parameter metadata helper for the native `FactoryRuntime`.

The V2 work verified **12 new control mappings**, in addition to re-probing the four existing BUS1/BUS2 mappings. In total, **16 controls across 10 effects** have two directly observed display points each. Each mapping was changed Up, reversed, and repeated with exact restoration of the 22-character display. Two ROM-12 candidates, `DISTORTION MIX` and `DIST FILTER FC`, were navigated and tested but were not promoted: their GPR writes did not repeat and reverse to the same stable values. Both remain unavailable in runtime metadata.

All newly registered points were accepted by `FactoryRuntime::setParameter` in the synthetic native-runtime tests. Separate private-package audio renders produced finite output for all 16 controls. The chosen 8,192-frame post-edit window showed a nonzero output delta for 10 controls and no measurable delta for six; those six remain register-mapped, but this stimulus/window does not establish an audible change. The WAVs and full per-control measurements are in the private output directory, not Git.

## Verified navigation

The original ASR-10 manual documents Edit followed by Effects, left/right parameter navigation, up/down value changes, and Cancel/No restoration. The live OS 3.53 panel confirmed that route and the observed live cursor sequence. The captured display is exactly 22 characters per state.

Observed ROM-01 HALL sequence:

1. The factory selector shows `FX=ROM-01  HALL REVERB`.
2. `Edit` (panel code 5) changes the display to `FREE SYSTEM BLKS=...`.
3. `Effects` (panel code 9) opens `VAR=1 FAVORITE REVERB`.
4. One Right press (code 17) reaches `REVERB MIX BUS1=28`.
5. Subsequent parameter pages are reached only after the complete display is stable; the runner stops when the requested live label appears.
6. Up (code 10) changes a single value step. Down (code 11) reverses it. Cancel/No (code 33) was also tested on HALL BUS1 and restored 28 from 29.

The active variation recorded for every successful probe was **VAR=1**. Other variations and their state differences have not been tested. The manual's statement about advancing screens by holding Right and pressing Up was not needed by the single-step navigation procedure and was not independently exercised.

The metadata's `display_order` is the observed number of single Right steps from the VAR screen (VAR is step 0), not a manual-derived order. Confirmed positions include HALL BUS1=1, BUS2=2, DECAY TIME=4, HI FREQ DAMPING=7; ROOM DECAY TIME=4, DIFFUSION=6, HI FREQ DAMPING=7; DUAL DELAYS `BS1 TIME L`=3; CHORUS RATE=11; PHASE RATE=12; GUITAR AMP1 PREAMP GAIN=3; FAST PITCHSH VOICE1 FINE=3; EQ+CMPRESSOR COMP RATIO=2; PARAM EQ BASS FC=1. Unmapped pages between these positions remain undocumented in the catalog.

Two controller races were found and fixed before accepting results:

- The selector temporarily displayed a target slot before the final analog selector event. Editing during that interval let a later selector update change the active effect. The runner now waits until the slow selector sweep is complete plus 500 ms before Edit.
- Holding Up while waiting for a settled LCD allowed OS key-repeat. The probe now emits a one-slice press pulse, releases it, and waits for a stable display transition. It records both exact before/after displays and cycle/frame coordinates.

Button numbers are from the emulator's panel table. They are not guessed from the manual. Every probe also records the selected slot display and current variation. Raw logs, WAVs, JSON reports, ROMs, OS disk images, and checkpoint state remain under `/home/gamer/research/private-results/`.

## Evidence table

Every listed value is one of two adjacent points directly observed in the OS. The GPR groups below are written in observed order. Values are 24-bit hexadecimal ES5510 writes. No full range, factory default, interpolation curve, or OS smoothing law is inferred.

| Slot / live control | Reversible display points | Ordered GPR writes |
|---|---:|---|
| 01 HALL — REVERB MIX BUS1 | 28 ↔ 29 | `7C:3D0000` ↔ `7C:3F0000` |
| 01 HALL — REVERB MIX BUS2 | 28 ↔ 29 | `7A:3D0000` ↔ `7A:3F0000` |
| 01 HALL — DECAY TIME | 40 ↔ 41 | `03,04,05,5B,6E`: `340000,CC0000,6ADFFF,080034,340000` ↔ `350000,CB0000,6A0DFF,080035,350000` |
| 01 HALL — HI FREQ DAMPING | 31 ↔ 32 | `6C,6D`: `57FFFF,280000` ↔ `56FFFF,290000` |
| 02 44KHZ REVERB — REVERB MIX BUS1 | 25 ↔ 26 | `7C:350000` ↔ `7C:370000` |
| 02 44KHZ REVERB — REVERB MIX BUS2 | 25 ↔ 26 | `7A:350000` ↔ `7A:370000` |
| 03 ROOM — DECAY TIME | 64 ↔ 65 | `6E:520000` ↔ `6E:530000` |
| 03 ROOM — DIFFUSION | 50 ↔ 51 | `07,09,0A,0B,0C,12`: `400000,C00000,5FFFFF,330000,CD0000,6BADFF` ↔ `410000,BF0000,5EFDFF,33CC00,CC3400,6B0A2A` |
| 03 ROOM — HI FREQ DAMPING | 9 ↔ 10 | `6C,6D`: `73FFFF,0C0000` ↔ `72FFFF,0D0000` |
| 04 DUAL DELAYS — live `BS1 TIME L` (manual `DELAY TIME`) | 350 ↔ 351 | `0B:290500` ↔ `0B:292300` |
| 06 CHORUS+REVRB — CHORUS RATE | 24 ↔ 25 | `90,91,92`: `0007F7,000C91,000B11` ↔ `000836,000CF5,000B69` |
| 07 PHASER+REVRB — PHASE RATE | 20 ↔ 21 | `8E:0003D7` ↔ `8E:00049C` |
| 28 GUITAR AMP1 — PREAMP GAIN | +12 ↔ +13 | `70:020100` ↔ `70:023F00` |
| 41 FAST PITCHSH — VOICE1 FINE | -11 ↔ -10 | `60:FF36EA` ↔ `60:FF4547` |
| 42 EQ+CMPRESSOR — COMP RATIO | 4/1 ↔ 5/1 | `8B:1FFFFF` ↔ `8B:199999` |
| 49 PARAM EQ — BASS FC | 100 ↔ 101 | `57,58`: `7D5E06,82A1FA` ↔ `7D574A,82A8B6` |

The full machine-readable mapping with literal display strings and ordered register groups is [ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json](ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json). The 50-effect catalog now includes the 16 direct OS mappings and retains documented-but-unverified controls separately.

### Periodic writes and control attribution

The runner separates a stable 500 ms no-edit window from Up and reverse windows, and repeats each edit twice. A no-edit HALL DECAY TIME window after selector settling had zero host GPR writes. In edit windows the firmware can also write other registers. Those writes were excluded unless the same target/value transition repeated and reversed:

- Chorus rate produced repeatable `0x90..0x92` updates. `0x76/0x77` changed cyclically during the observation window and were excluded as modulation-related writes.
- Phaser rate produced a repeatable `0x8E` change. `0x86` varied during the window and was excluded.
- ROM-02's first BUS edit included a one-time `0x6D` change that was absent from the repeated edit; it is not assigned to BUS1/BUS2.
- ROM-12 DISTORTION MIX produced `0x76/0x77` values that track changing cyclic state, while `0x85` did not reverse to the same value on both trials. No mapping is exported for it.
- ROM-12 DIST FILTER FC displayed 18 ↔ 19, but `0x85` did not restore the prior raw value on either reverse trial. No mapping is exported for it.

These exclusions are control attribution, not claims about the semantic purpose of an otherwise-unassigned GPR.

## Runtime contract

`include/trollfx/es5510_factory_parameter_discovery_v02.hpp` provides `append_verified_parameters(EffectDescriptor&)`. Call it while constructing a validated package descriptor, before registration. It adds controls only for slots with direct evidence. The helper labels the parameters with the observed OS display name, formatting, evidence note, and verified points. Repeated calls do not duplicate IDs.

For a validated, currently loaded package:

```cpp
parameter_discovery_v02::append_verified_parameters(descriptor);
runtime.setParameter(descriptor, "diffusion", 51, next_dsp_frame);
```

`FactoryRuntime::setParameter` schedules a multi-register point atomically at one DSP frame and rejects values not in the verified point list. Invoke it between `processStereo` blocks on the runtime-owning thread. Store the numeric display point and parameter ID in a user preset; do not persist program or checkpoint content. Exact display strings such as `+12` and `4/1` are also present in each `ParameterPoint::display_text`.

The host runtime applies the settled GPR state at a selected frame. It does not reproduce the OS's intermediate writes, background update cadence, or possible smoothing. That behavior remains undocumented and should not be presented as an authentic smoothing curve.

## Native audio comparison

All 16 controls were applied through the native runtime with private packages accepted by the existing production-provider audit. The validation tool verifies each RUN-boundary checkpoint hash and firmware-schedule hash before launching the renderer. It warms two identical runtimes with the same stereo impulse/two-tone signal for 32,768 host frames at experimental 48 kHz, schedules point A versus point B, then compares the next 8,192 stereo frames. Outputs are finite for all comparisons.

Ten controls yielded nonzero RMS difference in that particular window. Six yielded exactly zero measured delta: HALL BUS1, 44KHZ REVERB BUS1, DUAL DELAYS `BS1 TIME L`, CHORUS RATE, PHASE RATE, and COMP RATIO. This is stimulus/window evidence only; those controls still have reversible OS GPR evidence and pass the runtime scheduling checks. The native comparison WAVs and JSON report are generated outside the repository.

Run the native comparison using the local trusted private audit:

```sh
python3 tools/parameter_controls/run_native_audio_validation.py \
  --audit /home/gamer/research/private-results/asr10-all-50-effects/production-provider-audit.json \
  --output /home/gamer/research/private-results/asr10-parameter-discovery-v2/native-audio \
  --binary /tmp/es5510-parameter-audio-compare
```

## Status counts and limits

- Parameter pages successfully navigated: **18** (16 mapped controls plus two unmapped ROM-12 candidates).
- Reversible parameter probes: **18**.
- Newly verified controls: **12**.
- Existing controls re-probed and confirmed: **4**.
- Controls accepted by the native runtime metadata/API: **16**, in **10** slots.
- Effects with at least one mapping: **10**.
- Two candidates remain unassigned: ROM-12 DISTORTION MIX and DIST FILTER FC.
- Parameter variations recorded: **VAR=1 only**.
- All 50 effects are cataloged, but only the 10 listed slots have direct parameter mappings in this work. Unknown controls remain disabled/read-only.
- The current direct runtime API accepts only the sampled points; it does not interpolate undocumented values.
- Ten controls changed native output in the tested comparison window; six had zero measured delta in that test. Runtime audio response and timing still need testing with control-specific material and longer windows where delays/reverbs require it.

## Reproducibility and tests

Build the OS 3.53 headless runner:

```sh
bash tools/build_research_cli.sh
```

Example live HALL DECAY TIME probe (all outputs stay private):

```sh
python3 tools/parameter_controls/run_display_driven_probe.py \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --inventory /home/gamer/research/private-results/asr10-all-50-effects/inventory.json \
  --slot 1 --candidate 'DECAY TIME' --seconds 55 \
  --output /home/gamer/research/private-results/asr10-parameter-discovery-v2
```

Pass `--repetitions 0` to capture a no-edit baseline; `--revert-button 33 --repetitions 1` tests the panel's Cancel/No restore operation. `--seconds` is a minimum; higher-numbered slots extend the run long enough to finish the selector sweep and probe.

The panel controller uses state-based waits and the synthetic parser tests do not require ROMs. OpenASR's Lua regression scripts provided a useful observational testing pattern (read the virtual front display, drive a button, assert the result); their MAME Lua APIs are emulator-specific and were not imported. The controller uses this repository's live panel and host-write trace instead.

Successful focused verification commands:

```sh
python3 -m unittest discover -s tests/parameter_controls -p 'test_*.py' -v
c++ -std=c++17 -Iinclude tests/parameter_controls/test_adapter.cpp -o /tmp/asr10-parameter-adapter-test
/tmp/asr10-parameter-adapter-test
bash tools/audio_validation/test_factory_runtime.sh
python3 -m unittest tests.test_factory_package_importer tests.test_parameter_host_diff tests.test_experimental_audio_host_cli
```

The parameter-control Python discovery ran **11 tests**; the adapter executable passed; the native runtime suite passed; the relevant importer/host regression command ran **11 tests**. The runtime test includes accepted ordered groups, finite output, and the existing queue-capacity atomicity check.

## References

- [ASR-10 Musician's Manual — front panel](https://ensoniq.manymanuals.com/digital-pianos/asr-10/instruction-manual-11191/18)
- [ASR-10 Musician's Manual — effect parameter operation](https://ensoniq.manymanuals.com/digital-pianos/asr-10/instruction-manual-11191/98)
- [OpenASR Lua regression harness](https://raw.githubusercontent.com/peroberg/OpenASR/master/docs/asr10/regression-test.sh)
- [OpenASR Lua test README](https://raw.githubusercontent.com/peroberg/OpenASR/master/docs/asr10/lua/README.md)
