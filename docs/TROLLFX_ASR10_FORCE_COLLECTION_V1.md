# TROLLfx ASR-10 FX Collection for Akai Force — V1.0.0 experimental

## Status

This is an **unverified Force candidate**, not a playable authentic factory-effects release. It builds the VST2 ARMv7 hard-float plugin shell and touchscreen browser for all 50 OS 3.53 ROM slots. Slots 1 and 2 are identified as the only effects accepted by the integrated ES5510 runtime; the browser marks them as requiring packages. Slots 3–50 display as unavailable. The plug-in outputs dry input while an effect package is not loaded, and does not use mock DSP. Its status page reports package required or unavailable.

The Force VST currently does not load authentic HALL or ROM-02 package data. The integrated runtime API (`docs/ES5510_EXPERIMENTAL_RUNTIME_API_V01.md`) accepts only ROM-01 HALL and ROM-02, and requires its embedding application to validate private checkpoint, two-boot, event, and serial-route evidence before creating runtime packages. It has no general 50-effect loader, Force asset importer, or live VST integration contract. BUS1/BUS2 controls are exposed for the verified mappings, but this candidate does not schedule them into a runtime. Wet/dry is retained in the host-facing parameter contract; until a package backend is present, processing remains dry passthrough. No factory playback or parameter functionality is claimed.

## Browser and controls

`force_plugin/effects.json` contains 50 OS-observed slot numbers, names and broad UI categories, based on the redacted catalog in `docs/ASR10_ROM_EFFECT_CATALOG.md`. The list is fixed-size for VST/Force parameter compatibility. No algorithm topology or unverified parameter mapping is inferred from a display name. The UI has browse, host-control and verified reverb BUS pages. Gain and bypass are host controls, not factory parameters.

## SDK and build

The inspected SDK clone is `420troll/AkaiForceSDK`, commit `4521c247a2deae30efb9e93d53fc8f9390c51e81`. Its builder targets the original Force with ARMv7-A, Cortex-A17, NEON/VFPv4 and hard-float and emits VST2 plus `Plugin Skins/TUI.json` and `Q-Links.json`. SDK project sources include the SDK MIT framework; the candidate does not introduce another plug-in framework.

From this repository root, build/package only:

```sh
python3 force_plugin/tools/test_catalog.py
force_plugin/tools/build_candidate.sh
```

Output is `force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/`. The build script uses `AKAI_FORCE_SDK` if set, otherwise looks for sibling `AkaiForceSDK`. It does not copy anything to a device. The package includes a SHA256SUMS file. To manually install or remove a package, use `force_plugin/tools/install.sh PACKAGE_DIR FORCE_VST2_PLUGINS_DIR` or `force_plugin/tools/rollback.sh FORCE_VST2_PLUGINS_DIR`; neither script restarts the host.

## User-local factory assets

No ROM, firmware, EFE, checkpoint, microprogram, audio capture, or private state is included. Do not place private assets in a distributable package. A later import tool must run the existing fail-closed runtime validator on authorized local packages, preserve their evidence and hashes, and reject packages without initialization, two-boot, event, clock, input, and routing evidence. The Force-side loader must verify the validation receipt and file hashes before setting runtime evidence flags. Until that work and a general runtime API exist, selecting HALL or ROM-02 reports that a package is required and leaves the signal dry.

## License and troubleshooting

The plugin source is GPL-3.0-only, as recorded in the repository license and package manifest. The compiled SDK framework headers identify as MIT; the package includes an MIT notice. No proprietary factory payload is redistributed. If the plugin does not appear, check that External Plugin Support is enabled and that the package folder name, `plugin.json`, ARM32 VST path and generated skin agree. Hardware detection and touchscreen layout remain unverified because no device test was performed.

## Presets and incomplete controls

The SDK persists the eight exposed parameter values in the standard VST state chunk. The candidate does not yet provide a named user-preset library, custom preset metadata, active-effect state package serialization, input/output meters, or functioning wet/dry blending. These require the missing runtime/package integration; the wet/dry control is present in the fixed host parameter contract but currently has no wet signal to blend. BUS1/BUS2 selections are present but are not sent to the ES5510 runtime. Do not treat these UI parameters as working factory edits in this build.

For a local HALL/ROM-02 package, the existing validator command forms are:

```sh
python3 tools/audio_validation/validate_factory_runtime_package.py \
  --effect hall --manifest PRIVATE_MANIFEST --checkpoint PRIVATE_CHECKPOINT \
  --reference-root PRIVATE_TWO_BOOT_ROOT --events PRIVATE_EVENT_CSV
python3 tools/audio_validation/validate_factory_runtime_package.py \
  --effect rom02 --manifest PRIVATE_MANIFEST --checkpoint PRIVATE_CHECKPOINT \
  --reference-root PRIVATE_TWO_BOOT_ROOT --events PRIVATE_EVENT_CSV
```

A future Force package importer must retain the validator result, bind it to file hashes, and feed the native runtime through a nonblocking, prevalidated load path. These commands validate local data; they do not make the current VST load it.
