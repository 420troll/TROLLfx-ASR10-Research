# TROLLfx ASR-10 Force Release Verification V1

Date: 2026-11-24  
Branch: `integration/asr10-force-release-v1`  
Release: experimental VST2 package 1.0.0  
Source revision used for the release build: `de708d210a9546cea25a8f62a38c4113fba665b0`

## Result

The integrated package passed the SDK's native and ARM binary validation and the binary-bound native VST audio gate. The release folder is marked playable for software testing. This is not evidence of operation on a physical Akai Force; no Force was connected to this WSL2 environment and no deployment was performed.

The provider reads user-local validated effect packages. The distributable contains no factory checkpoints or proprietary program images. An authorized `FactoryAssets` directory must be prepared and copied beside the plugin on the device before factory effects can load.

## Integrated components

- Universal `EffectRegistry`, trusted 50-slot package importer, and production `IValidatedFactoryPackageProvider`.
- Native ES5510 backend, stereo VST2 wrapper, existing 5 ms fade-out/fade-in transitions, host mix/gain/bypass, and touchscreen/Q-Link skin.
- Provider package assets remain local and fail closed to silence when missing or rejected.
- Existing parameter IDs and plugin identity (`TfxF`, `ASR10 FX Collection`, `TROLLfx`) are retained. The dynamic Load Status display now derives its text from backend state without mutating the serialized parameter value. This fixes host chunk round-trip instability while preserving the parameter index and ID.

## Binary-bound verification

The official SDK checkout was `/mnt/c/Users/Gamer/research/AkaiForceSDK`, commit `4521c247a2deae30efb9e93d53fc8f9390c51e81`; Zig was 0.17.1 via `python3 -m ziglang`.

| Target | Result | SHA-256 | Validation |
|---|---|---|---|
| Native x86_64 VST2 | PASS | `179f7dabe145e8d65ef1eed70aa98ce380de3d905bb94ecd2b211ff859abcef5` | Loaded by VST ABI harness and SDK `host_sim` |
| ARMv7 hard-float VST2 | PASS | `225aacdcd3a0a200f5851af924f0128b20f1ff6b4e8c354df343e804fe0d9de5` | ELF32 ARM, exports `VSTPluginMain`; max GLIBC 2.27 |
| AArch64 VST2 | PASS | `e340cffbe07be006d901053edfc8947ea34a51b9023ea9fb66bb81c87715835b` | ELF64 AArch64, exports `VSTPluginMain`; max GLIBC 2.27 |

The binary-bound test loaded the actual freshly built native plugin through `VSTPluginMain` and its `processReplacing` callback. It exercised all 50 locally validated packages with deterministic stereo input (8,192 host frames per slot), and reported 50/50 slot passes, finite non-silent output, 805,111 nonzero output frames across renders, missing-package silence, stereo routing, state round-trip, and zero callback allocations. The SDK host simulator also passed, including audio render and state round-trip. SDK package validation reported zero errors and zero warnings. The result is recorded in the distributable's `factory-playback-status.json`, SHA-256 `6d175b7c844d34370bddba08ed2697e54a4ded8762f04b86e0fd0ea082a09268`.

The native backend checks independently exercised HALL and ROM-02 playback and asynchronous effect switching. At 48 kHz the ramps are 240 frames each (5 ms fade-out and 5 ms fade-in); effect preparation occurs between ramps. The binary harness's measured selected-slot-ready time spans 256–1,792 frames because it includes worker preparation and 256-frame host callback polling; it is not a measurement of ramp duration alone.

Wet/dry, input/output gain, bypass, factory slot selection, user-local asset discovery, host state chunks, and missing-package behavior are bound to the packaged VST API and covered by the release harness/SDK simulator. HALL BUS controls produced an observed audio difference in the wrapper smoke test. ROM-02 BUS1's mapped write was accepted, but the short smoke stimulus reported no output delta (`0`); the mapping remains identified, while audible effect of that control is not established by this release test.

## Known evidence limit

Slot 50, `VAN DER POL`, passed the same 48 kHz package-load and finite-audio test, but the trusted capture collection has no verified post-RUN clock evidence for it. The per-slot report explicitly records `clock_verified_after_run: false` for slot 50; the other 49 entries are true. Do not describe slot 50's factory clock as verified. This run tests experimental 48 kHz runtime behavior, not authentic factory-rate equivalence for that slot.

The release tests ran on desktop/WSL2. They do not establish Force CPU headroom, display/Q-Link interaction, filesystem behavior, or device audio compatibility. No actual Force use is claimed.

## Reproduction

With the official SDK, Zig Python module, and authorized private validated package collection available:

```sh
AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK \
TROLLFX_FACTORY_PACKAGE_COLLECTION=/path/to/private/validated-packages \
  sh force_plugin/tools/build_candidate.sh --toolchain auto --no-zip
```

That command runs the native backend/wrapper checks, builds native, ARMv7, and AArch64 binaries, validates the SDK package, and runs `test_packaged_vst.py` against the freshly built native VST and the private 50-package collection. It writes a playable marker only when the binary-bound gate passes. `--no-zip` keeps a package folder without creating an archive.

The final regression gate used:

```sh
python3 -m unittest discover -s tests -v
AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK \
  sh force_plugin/tools/test_release_infrastructure.sh
git diff --check
```

Results: 80 repository tests passed; 5 release-infrastructure tests passed; catalog validation passed; whitespace validation passed. The focused native backend test also passed during the final candidate build. `pytest` is not installed in this environment; tests were run with the repository's built-in `unittest` suite.

## Deployment and rollback

No install or rollback evidence exists because this environment had no Force device mount or USB device. WSL2 exposed only its system disks and host drives; no removable Force volume was mounted. There is no safe basis to verify whether the Force is in an active session, and no hardware test could be performed. The package was therefore left uninstalled.

When the Force is available and outside an active audio session/show, prepare the authorized assets outside the repository:

```sh
python3 force_plugin/tools/prepare_force_assets.py \
  /path/to/private/validated-packages \
  /path/to/TROLLfx-FactoryAssets
```

Copy that directory as `FactoryAssets` beside the plugin on the Force. Then install the verified package while retaining rollback:

```sh
python3 force_plugin/tools/install_package.py \
  'force_plugin/dist/TROLLfx - VST - ASR10 FX Collection' \
  '/path/to/Force/Plugins' --replace
```

The installer verifies the package checksums and playable marker, stages the new plugin, and retains the previous folder under `.rollback-TROLLfx - VST - ASR10 FX Collection-*`. Roll back with:

```sh
python3 force_plugin/tools/rollback_package.py '/path/to/Force/Plugins'
```

Host restart is manual and should happen only after the user confirms the Force is not in an active session/show. Required hardware tests after deployment: load the plugin, verify all 50 labels and availability, test stereo audio and wet/dry/gain/bypass, exercise HALL and ROM-02 controls and switching, confirm the local assets load, and verify audio stability on the Force. Record actual device model/OS, plugin status, measured CPU behavior, and rollback outcome.
