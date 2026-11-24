# Force Parameter Mapping Integration V2

Integration branch: `integration/asr10-force-parameter-mappings-v2`
Codex 1 source: `research/asr10-automated-parameter-discovery-v2` at `e29cb8a`
Release source commit: `c4d3d7b531b4c8ba516036318423d928b8342b90`

## Controls and runtime behavior

The trusted local package provider attaches the OS 3.53 V2 verified parameter definitions to the validated effect descriptors. Those definitions contain discrete display points and ordered register write groups. The Force wrapper sends selected points through `ES5510DSPBackend::set_verified_parameter`, which schedules a complete verified group at the runtime's current DSP frame. Package validation, effect loading, DSP arithmetic, and the 5 ms switching ramps are unchanged.

Sixteen controls across ten effects are exposed:

| Slot | Factory effect | Verified controls |
|---:|---|---|
| 1 | HALL REVERB | REVERB MIX BUS1, REVERB MIX BUS2, DECAY TIME, HI FREQ DAMPING |
| 2 | 44KHZ REVERB | REVERB MIX BUS1, REVERB MIX BUS2 |
| 3 | ROOM REVERB | DECAY TIME, DIFFUSION, HI FREQ DAMPING |
| 4 | DUAL DELAYS | BS1 TIME L |
| 6 | CHORUS+REVRB | CHORUS RATE |
| 7 | PHASER+REVRB | PHASE RATE |
| 28 | GUITAR AMP1 | PREAMP GAIN |
| 41 | FAST PITCHSH | VOICE1 FINE |
| 42 | EQ+CMPRESSOR | COMP RATIO |
| 49 | PARAM EQ | BASS FC |

Each mapping exposes only its two adjacent, independently verified display points. A leading `UNCHANGED` choice schedules no register write. It is a no-write state, not a claimed factory default or a reset operation. There is no interpolation between points. Effects without recovered controls keep their audio path and do not receive guessed editor parameters.

Plugin parameter IDs and indices 0–11 remain unchanged. The twelve additional controls append at indices 12–23 in this order: slot 1 DECAY TIME, slot 1 HI FREQ DAMPING, slot 3 DECAY TIME, slot 3 DIFFUSION, slot 3 HI FREQ DAMPING, slot 4 BS1 TIME L, slot 6 CHORUS RATE, slot 7 PHASE RATE, slot 28 PREAMP GAIN, slot 41 VOICE1 FINE, slot 42 COMP RATIO, slot 49 BASS FC. Duplicate visible labels include an effect qualifier in the TUI so the SDK can bind them unambiguously; the original OS labels remain in the catalog and descriptor metadata.

The Edit page keeps its original Q-Link assignments: Q1–Q4 still map to parameter indices 8–11. Q5–Q16 map to the new indices 12–23. The SDK-generated `Q-Links.json` confirms the map. No parameter beyond the 16 verified controls is assigned on the Edit page. The other 40 effects remain selectable/loadable and have no factory editor widgets.

Existing VST chunk format and old parameter IDs are preserved. New host choices serialize by stable appended parameter IDs. `UNCHANGED` is the default for new controls, so merely loading an effect or restoring an older chunk does not write an assumed value. The binary gate verified a modified V2 value survives save/restore.

## Binary-bound release evidence

The SDK build used `/mnt/c/Users/Gamer/research/AkaiForceSDK` at `4521c247a2deae30efb9e93d53fc8f9390c51e81` and Zig 0.17.1.

| Artifact | SHA-256 | Result |
|---|---|---|
| Native x86_64 VST2 | `48fd2f6a0a946f933a2b7121cb364e50cf8f69a8c0836b38ebd57c169178da49` | Binary-bound VST callback and SDK host simulator passed |
| ARMv7 hard-float VST2 | `a7ae1752ec99cd40c98ea41dda94b91031aa219f240ef0205f4a1752514a8c56` | ELF32 ARMv7; exported VST entry; SDK package validation passed |
| AArch64 VST2 | `c2e6279d59a3150d11279583d026dd4b3f767b2ee89386fcff082929bd3e73be` | ELF64 AArch64; SDK package validation passed |
| Binary playback report | `768d6e189a79bdc2c07e8a4bd7177bd97e5b6e50948926fc72b24efa79428091` | Bound to the native and ARMv7 hashes above |

The native VST harness loaded the packaged plugin binary and processed all 50 validated packages. It exercised both verified points for each of the twelve appended controls, checked the visible strings, and restored the saved slot, host controls, BUS values, and a V2 parameter choice. The recorded suite also passed finite stereo output, missing-package silence, effect switching, zero callback allocations, and the official SDK host simulator. The SDK validator reported zero errors and zero warnings; TUI parameter handles are within 0–23. The release report records 50/50 slot passes, `callback_allocations: 0`, and slot 50 in `clock_evidence_gaps`.

The ARMv7 binary was built and ABI-checked but not executed on ARM hardware. Slot 50 retains the existing evidence note: it plays in the experimental 48 kHz package test, while its authentic post-RUN factory clock remains unverified.

Final test results: 80 repository `unittest` tests passed; 11 parameter-discovery tests passed; 5 Force release-infrastructure tests passed; native VST wrapper/audio smoke passed; binary-bound 50-slot harness and SDK simulator passed; package checksum and installer read-only verification passed. The focused backend test compiler emits existing `-Wmismatched-new-delete` diagnostics from the allocation-counting test override; the test passes and callback allocations remain zero.

Reproduce the complete native/ARM package gate with the command in [the release verification record](ASR10_FORCE_RELEASE_VERIFICATION_V1.md), setting `TROLLFX_FACTORY_PACKAGE_COLLECTION` to the authorized private package directory. Factory package data remains external and was not committed.

No Force device test was run. Parameter recovery does not block hardware testing; deploy and validate this candidate on Force independently when the device and authorized local `FactoryAssets` are available.
