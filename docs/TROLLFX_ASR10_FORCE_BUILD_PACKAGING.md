# Force build and packaging infrastructure

## Current release state

The release builder creates a **candidate** folder and ZIP only. It does not install, restart, or copy files to a Force. The current `ASR10FXCollection.cpp` output is silent until Codex 2 supplies the DSP integration; therefore the package has no `INTEGRATION_STATUS` playable marker and the installer refuses it. The builder performs compile, host-simulator parameter dump, SDK package validation, and static binary checks; it does not count a silent VST smoke as DSP verification.

The marker writer is deliberately stricter than an SDK build. The JSON schema is `force_plugin/schemas/dsp-integration-report.schema.json`. It accepts only a Codex 2 report with schema `trollfx-force-dsp-integration-report-v1`, `status: PASS`, a matching ARM32 binary hash, non-mock backend, non-silent numerical output, successful initialization/stereo/switch/no-mock tests, and all slots 1–50 verified. It writes `INTEGRATION_STATUS`, updates the release manifest/checksums, and creates a playable ZIP. No factory validation or DSP tests are implemented by this build infrastructure.

## SDK and toolchain discovery

The builder accepts `--sdk PATH` or `AKAI_FORCE_SDK=PATH`. Without either, it searches the worktree's sibling `AkaiForceSDK`, `$HOME/research/AkaiForceSDK`, `$HOME/work/AkaiForceSDK`, and `/opt/akai-force-sdk`. It requires `tools/build.py`, `tools/validate.py`, and `framework/mpc_plugin.h`; it never assumes `/home/gamer/worktrees/AkaiForceSDK`.

Toolchain selection is `--toolchain auto|zig|gcc`. `auto` prefers a working Zig executable or `ziglang` Python module, then requires both `arm-linux-gnueabihf-g++` and `aarch64-linux-gnu-g++`. Override Zig using `ZIG`, `ZIG_PYTHON`, and `ZIG_PYTHONPATH`. The SDK itself selects Cortex-A17 and `arm-linux-gnueabihf.2.31` for the original Force ARM32 target. Build target `all` includes the native host library, Force ARM32 hard-float, and optional-compatible AArch64 binaries so the SDK's two-architecture manifest validation can pass.

Inspected local SDK: `/mnt/c/Users/Gamer/research/AkaiForceSDK`, remote `https://github.com/420troll/AkaiForceSDK.git`, commit `4521c247a2deae30efb9e93d53fc8f9390c51e81`. The published official SDK source is [inMusic's MPC Plugin Builder SDK](https://github.com/inmusic-software/mpc-plugin-builder-sdk); framework headers in the inspected checkout state SPDX MIT. Local known-good ESP Lab artifacts were found in `plugins/TROLLfxESPLab`, `TROLLfxESPLabV02`, and `TROLLfxESPLabV03` under that SDK checkout; their ZIPs contain ARM32/ARM64 VST binaries and generated skins. No separately named local RTA VST build was found; the local RtAudio sources/licenses are audio-device code, not a Force plugin binary.

Current environment toolchain: `/usr/bin/python3 -m ziglang`, Zig `0.17.1`, imported from `/tmp/trollfx-force-zig`; ARM architecture inspection uses `/usr/bin/arm-linux-gnueabihf-readelf`. No `arm-linux-gnueabihf-g++` or `aarch64-linux-gnu-g++` compiler was found. In another environment, install/provision Zig or both cross compilers and set the override variables above.

## Build and validate

From the repository root:

```sh
AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK \
  force_plugin/tools/build_candidate.sh
```

This builds native + ARM32 + AArch64, gets the SDK's host-simulator parameter dump, runs the SDK validator, checks ELF class/machine and ARMv7 hard-float attributes, writes `release-manifest.json` and `SHA256SUMS`, and creates:

- `force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/`
- `force_plugin/dist/asr10-fx-collection-1.0.0-candidate.zip`
- matching `.sha256` sidecar

The package manifest records source commit and input hash, SDK path/remote/commit, compiler invocation/version, ABI results, binary hashes, and SDK validation. Plugin `version` is numeric `1.0.0` as required by the SDK and `releaseChannel: experimental` records the prerelease channel. This removes the SDK's prerelease-version warning and preserves the product's experimental designation.

The SDK validates dynamic dependencies and symbol exports. The release script independently checks ARM32 `ELF32/ARM`, `Tag_CPU_arch: v7`, and `Tag_ABI_VFP_args: VFP registers`, plus AArch64 `ELF64/AArch64`. The result is a Force architecture candidate; it is not hardware tested.

## Playable release gate

Only after Codex 2's full DSP integration suite has emitted its report:

```sh
python3 force_plugin/tools/mark_playable.py \
  --package 'force_plugin/dist/TROLLfx - VST - ASR10 FX Collection' \
  --report /path/to/private-or-ci/dsp-integration-report.json
```

The report must identify the exact ARM32 binary hash and record `verified_slots` as integers 1 through 50. The marker stores only hashes and test metadata; report/audio/private state is not copied into the release package. The marker writer then creates a `-playable.zip`. Build reports and binaries must be rebuilt after source changes, which clears the marker and returns the package to candidate status.

## Opt-in install and rollback

Build/package is the default. Installation needs an explicit package path and an explicit destination, and rejects candidates without the playable marker or with checksum, identity, or binary-hash mismatches:

```sh
force_plugin/tools/install.sh \
  'force_plugin/dist/TROLLfx - VST - ASR10 FX Collection' \
  '/media/FORCE/VST2 Plugins'
```

Existing installs are not overwritten unless `--replace` is passed to `install_package.py`; replacement preserves the previous directory under a timestamped rollback name. Rollback moves the active folder aside instead of deleting it and restores that backup when present:

```sh
force_plugin/tools/rollback.sh '/media/FORCE/VST2 Plugins'
```

Neither script restarts the Force application. These commands were not run against a device or removable Force volume.

## Licensing and private assets

The plugin/repository code is GPL-3.0-only; the package includes the repository GPL text. The SDK framework is MIT and its official notice/trademarks are included in `LICENSES/SDK-MIT-NOTICE.txt`. No ROM, firmware, EFE, factory program, microprogram, checkpoint, capture, event trace, or audio is packaged. The official SDK license is [MIT by inMusic Brands](https://github.com/inmusic-software/mpc-plugin-builder-sdk/blob/main/LICENSE).
