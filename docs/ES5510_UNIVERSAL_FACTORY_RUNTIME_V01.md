# Universal ES5510 factory runtime integration contract v1

This contract generalizes effect identity from two hard-coded programs to ASR-10 factory slots 1–50. The registry is manifest-driven. Package state remains local to the user and is referenced by path plus SHA-256; no ROM, EFE, program, GPR/SPR table, DRAM image, or checkpoint bytes belong in the application or presets.

## Package format

Schema: [`factory_effect_package.schema.json`](../tools/audio_validation/factory_effect_package.schema.json). A package descriptor names a slot and factory effect, carries active program identity/length, measured factory rate and routing, and references:

- A Codex 1 `trollfx-es5510-factory-init-v1` cold-load manifest for program, all 192 GPRs, all 22 SPRs, DRAM/memory setup, route, and HALT/RUN/pipeline-reset evidence.
- A user-local RUN checkpoint whose program/GPR/SPR identity must match that manifest.
- An optional bounded post-RUN firmware event schedule whose frames are relative to checkpoint frame zero.
- Verified display-value-to-GPR parameter points. Missing definitions or unmeasured points stay absent; the loader never extrapolates them.

The runtime's existing binary checkpoint reader remains responsible for initializing native ES5510 state and checking variable active program length. The manifest wrapper adds identity, routing, schedule, and parameter metadata; it does not replace or reinterpret Codex 1 payloads. Current `factory_manifest.py` supports variable program lengths from 1 through 160 words and fixed architectural register geometry. Future Codex 1 packages can use the wrapper without embedding payloads.

## C++ API

Headers: [`include/trollfx/es5510_factory_registry.hpp`](../include/trollfx/es5510_factory_registry.hpp) and [`include/trollfx/es5510_factory_runtime.hpp`](../include/trollfx/es5510_factory_runtime.hpp). `EffectDescriptor` is the normalized descriptor. `ValidatedEffectPackage` carries the validator result and `EffectRegistry::register_validated()` rejects incomplete validation, invalid geometry/rates/routes, duplicate slots, bad parameter points, and oversized or malformed firmware schedules. Registry mutation and package loading are control-thread operations; the callback sees only already loaded fixed-state DSP data. The generic loader verifies that checkpoint active-word count and serial mode agree with the descriptor; the package validator remains responsible for referenced hashes and state/program identity before it sets the validation flags.

`RoutingDescriptor` describes one stereo serial input and output port. The native implementation validates these port indices against the captured serial mode and maps them to the corresponding ES5510 lanes. Unsupported mono/multiport topologies fail closed. The factory-reference clock is metadata; `Experimental48000` remains a runtime mode independent of it.

Parameter definitions map only explicitly verified integer display points to one 24-bit GPR write. Generic low-level `setRegister(gpr, value24, absolute_dsp_frame)` remains bounded and frame scheduled. Calls are made between audio blocks; same-frame writes retain insertion order. No allocations occur in `processStereo`.

## User presets

[`user_preset.schema.json`](../tools/audio_validation/user_preset.schema.json) stores a preset name, effect slot, and parameter IDs/display values only. It rejects binary/checkpoint fields. The package is separately installed or selected by the user, so a preset never bundles proprietary factory data.

## Current validated profiles and synthetic coverage

ROM-01 HALL and ROM-02 44KHZ REVERB remain compatibility profiles with their established clocks, routing, 5 ms fade/reload/fade behavior, and parameter evidence. General registry tests use synthetic 1-, 3-, 60-, 89-, and 160-word programs and synthetic 192-GPR/22-SPR checkpoints; they do not assert new factory identities. Until additional validated user packages arrive, unrepresented slots have no fabricated descriptors.

## Future package creation

1. Codex 1 supplies the factory initialization manifest and matching user-local RUN checkpoint with hashes.
2. A package wrapper adds the observed slot/name, program identity, rate, route, bounded firmware schedule, and only verified parameter points.
3. The validator checks wrapper and initialization manifest, all referenced hashes, checkpoint program/GPR/SPR match, END position, routing, and event ordering before producing a `ValidatedEffectPackage`.
4. The host registers that package, loads/switches by slot, and stores user preset values without copying package bytes.

The existing experimental host's 5 ms fade/reload/fade remains the effect switch policy. [`RegistryFactoryRuntimeProcessor`](../src/factory_runtime_audio_adapter.h) adapts an `EffectRegistry` to that host seam: selection values 0..49 map to factory slots 1..50, and `prepare()` loads the already registered package while the host is muted. Preparation/reload occurs on the control thread while output is muted. New registry package validation must complete before a switch is requested. The current standalone WAV CLI still exposes only its two legacy private package arguments; universal slot selection is available through the C++ registry adapter.
