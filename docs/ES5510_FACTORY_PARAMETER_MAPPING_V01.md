# ES5510 factory parameter mapping v0.1

## Result

Controlled OS 3.53 UI edits establish four live mappings across the two factory reverbs. `REVERB MIX BUS1` updates GPR `0x7C`; `REVERB MIX BUS2` updates GPR `0x7A` for both effects. The tested values are adjacent settings only. The full ranges, units, stored defaults, EFE parameter-record offsets, scaling curves, and update-service implementation remain unknown.

| Factory effect | UI label | Fresh-selection value observed | Reversible settings tested | Changed GPR | Raw 24-bit values |
| --- | --- | ---: | --- | --- | --- |
| ROM-01 HALL REVERB | REVERB MIX BUS1 | 28 | 28 ↔ 29 | `0x7C` | `0x3D0000` ↔ `0x3F0000` |
| ROM-01 HALL REVERB | REVERB MIX BUS2 | 28 | 28 ↔ 29 | `0x7A` | `0x3D0000` ↔ `0x3F0000` |
| ROM-02 44KHZ REVERB | REVERB MIX BUS1 | 25 | 25 ↔ 26 | `0x7C` | `0x350000` ↔ `0x370000` |
| ROM-02 44KHZ REVERB | REVERB MIX BUS2 | 25 | 25 ↔ 26 | `0x7A` | `0x350000` ↔ `0x370000` |

The fresh-selection values repeated across boots; they are recorded as observations, not asserted as persistent factory defaults because a separate clean-disk factory-reset experiment was not run. No display units or supported endpoints were established. The machine-readable records, including nulls for those unknowns, are in [`ES5510_FACTORY_PARAMETER_CATALOG_V01.json`](ES5510_FACTORY_PARAMETER_CATALOG_V01.json).

## Evidence and firmware correspondence

The experiments selected each effect in a fresh OS 3.53 emulator process, opened Edit/Effects, captured the displayed control, and sent one Up, one Down, and a repeated Up. Each effect/control had an independent no-edit run with the same selection, route, sine stimulus, markers, and page navigation. Every no-edit window had zero host GPR commits. The changed runs reported display values that reversed with the buttons and host commits from the common writer at PC `0xFFF97792`.

Program identity and processing rate were checked against the existing factory-load evidence: ROM-01 HALL is 89 active instructions with END at 88 and a source-correlated instruction fingerprint `ca2cab387d1bee51bccc9a97f2c5d26386b8b801ee9bf4ea406e80a7019e4f92`; ROM-02 44KHZ REVERB is 60 active instructions with END at 59 and active-program SHA-256 `12119e86d4d232ab7d7ab4278e9c9dbed9db19a6b6eb352bfb29441181da4486`. Their private EFE source hashes are `862e54de6a3bb2708674d94d95247e947be51df764ca5c9bd2bf9f4218ad8a15` and `21562a079f5e1bf3d14cfeebfd9a7ef1afc0e5cb0edff788e4308d3552186f75`, respectively. Prior source comparisons established 89/89 HALL instruction matches plus 86/86 paired GPR initializers, and 60/60 ROM-02 instruction matches plus 58/58 paired GPR initializers. No program words or EFE bytes are included here.

The HALL DSP ran at 29,761.89453125 frames/s while host PCM output remained 44,100 Hz. ROM-02 DSP and host output both ran at 44,100 Hz. Parameter events below use absolute ESP frame coordinates; the WAV sample index is a separate host-output timeline.

### Changed and companion writes

For BUS2, settled reverse/repeat actions wrote the mapped GPR followed by an unchanged companion: HALL `0x7A` then `0x7B=0x7FFF00`; ROM-02 likewise `0x7A` then `0x7B=0x7FFF00`. For BUS1, each settled action wrote `0x7C` then unchanged `0x7D=0x7FFF00`, twice. These companion writes are part of the observed host transaction; their semantic roles are not established. The adapter emits only the value-changing GPR write.

| Effect/control | UI edit | Representative ESP frame(s) | Host write behavior |
| --- | --- | ---: | --- |
| HALL BUS2 | 28 → 29 → 28 → 29 | 938,696; 971,810; 1,007,562 | GPR `0x7A`; reverse/repeat each had the `0x7A`, `0x7B` pair |
| HALL BUS1 | 28 → 29 → 28 → 29 | ramp ended at 951,620; reverse 971,812 / 971,988; repeat 1,007,566 / 1,007,717 | GPR `0x7C`, then `0x7D`, twice per settled action |
| ROM-02 BUS1 | 25 → 26 → 25 → 26 | ramp ended at 1,082,151; reverse 1,114,521 / 1,114,977; repeat 1,167,507 / 1,167,925 | GPR `0x7C`, then `0x7D`, twice per settled action |
| ROM-02 BUS2 | 25 → 26 → 25 → 26 | 1,047,499; 1,092,445; 1,136,604 | GPR `0x7A`, then `0x7B`; see [`FACTORY_EFE_RECONSTRUCTION_V2.md`](FACTORY_EFE_RECONSTRUCTION_V2.md) |

BUS1 Up windows included repeated intermediate writes to GPR `0x7C` before the final value. The observed stream does not prove a general interpolation curve or a safe ramp law. First Up also produced broad edit-associated writes: ROM-02 had a one-time GPR `0x6D` change which did not repeat on Down/Up. That write is unassigned. ROM-02's 202 post-RUN GPR updates, including recurring `0x7F`, `0x7C`, and `0x7D` writes, are not generally parameter writes. Only the controlled reversible UI correlation above establishes `0x7C` as BUS1's changed-value destination. `0x7F` remains unassigned, and `0x7D`/`0x7B` remain unchanged companion writes with unknown roles.

The public evidence places the common ESP host writer at `0xFFF97792`. Other static EFE analysis describes an updater task/helper calling update service `$801E`, but those object offsets came from a different effect object. The ROM-01/ROM-02 parameter records and their service path were not resolved to EFE byte offsets or CPU addresses. EFE offsets are not CPU addresses; none are inferred here. The update service may perform value preparation or smoothing, but only the emitted GPR sequences above are dynamic observations.

## Audio check

For HALL BUS2, the same 440 Hz input, route, effect selection, and 44.1 kHz WAV renderer produced bit-identical output between an unedited control and the 28-setting run through output frame 1,280,269. After the UI changed 28 to 29, the first differing output sample was frame 1,280,270 (29.031066 s); the 29–30 s stereo PCM16 difference had RMS 9,812.7525 and peak 16,579. After the UI returned to 28, the next compared second still differed from the unedited run (RMS 10,357.999, peak 16,307). The reverb's retained delay state prevents immediate audio restoration even though the register setting reversed. A repeated Up changed the display and register back to 29.

Earlier ROM-02 BUS2 comparison showed bit-identical output before its edit and a nonzero first post-edit window (difference RMS about 6,266, peak 14,494). These are emulator measurements, not subjective quality claims or physical-hardware equivalence. No min/max audio sweep was possible because the supported endpoints are unknown. Neither a 48 kHz runtime response nor a click-free adapter transition has been validated.

## Minimal adapter and integration contract

Header: [`include/trollfx/es5510_factory_parameter_control_v01.hpp`](../include/trollfx/es5510_factory_parameter_control_v01.hpp). It is a separate, header-only translation layer; it does not include or duplicate the DSP engine. The exact mapping allowlist rejects every display value except the four evidenced points above. It returns one changed-GPR state write and does not guess values between them.

The reusable experimental runtime API was reviewed in its separate worktree at commit `de442aa0c522a0fe84ea53cc78bc1ef638c9ecce`. Integrate by mapping this adapter's `FactoryEffect` to that runtime's `EffectId`, then call:

```cpp
const auto next_frame = runtime.getStatus().processed_dsp_frames;
const auto result = trollfx::es5510::factory_parameters_v01::schedule(
    runtime,
    trollfx::es5510::factory_parameters_v01::FactoryEffect::Rom02Reverb44k,
    trollfx::es5510::factory_parameters_v01::Parameter::ReverbMixBus2,
    26,
    next_frame);
```

`FactoryRuntime::setRegister` applies a 24-bit GPR write before the selected absolute DSP frame. Make control calls between `processStereo` blocks on the owning audio thread; the runtime is not thread-safe and its queue is bounded. The example frame is valid only when it is still the next unprocessed frame at the call. The runtime must already have a validated full RUN-boundary package, the matching effect selected, and a known rate/route. A program image alone is insufficient. v0.1's adapter changes one register state directly; it does not reproduce the factory OS's repeated BUS1 write cadence. The factory UI edits are verified live, but the adapter's transition safety and 48 kHz sound are unverified. Keep it labeled experimental and do not expose invented min/max controls.

## Remaining research

- Capture each control's true endpoints, step law, and stored factory default from a clean-reset OS state; add mapping points only after reversible host-write correlation.
- Resolve the ROM-01/ROM-02 EFE parameter-record offsets and trace their actual OS update service path. Current offsets remain null.
- Determine the meaning of companion GPRs `0x7B` and `0x7D`, the one-time `0x6D` write, and recurring post-RUN GPR `0x7F` writes.
- Measure BUS1 transient-update timing at additional values; do not turn the observed staircase into an assumed general smoothing formula.
- Test adapter changes under equivalent initialized state at 48 kHz, including click behavior and deterministic reversion after delay memory settles.
- Enumerate all remaining controls on both effects before claiming a complete factory parameter inventory.

## Tests and smoke checks

Run the focused adapter and catalog tests:

```sh
g++ -std=c++17 -Wall -Wextra -Wpedantic -Werror -Iinclude \
  tests/parameter_controls/test_adapter.cpp -o /tmp/test_es5510_parameter_adapter
/tmp/test_es5510_parameter_adapter
python3 -m unittest discover -s tests/parameter_controls -v
```

The final integration gate also runs the repository suite once and a small HALL/ROM-02 audio smoke. ROMs, OS images, raw GPR logs, snapshots, EFE payloads, and WAV evidence remain outside Git.
