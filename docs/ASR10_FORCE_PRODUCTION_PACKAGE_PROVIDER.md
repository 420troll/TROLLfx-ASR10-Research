# ASR-10 Force Production Factory Package Provider

## Local factory asset setup

The plugin reads an authorized, user-local package collection. It checks
`TROLLFX_FACTORY_PACKAGES_DIR` first, then `factory-assets-path.txt` beside the
plugin, then `FactoryAssets` beside the plugin. The collection is imported
using the universal factory importer and its registration rules. The runtime
rechecks the local index, SHA-256 hashes, package manifests, RUN checkpoints,
firmware-event history, and bounded event schedules before registering a slot
with `EffectRegistry`. Invalid or absent packages stay unavailable and render
silence; the provider does not select a mock processor.

Prepare a transfer directory from a trusted private collection outside the
repository:

```sh
python3 force_plugin/tools/prepare_force_assets.py \
  /path/to/private/validated-packages \
  /tmp/TROLLfx-FactoryAssets
```

Copy the resulting directory to the Force plugin folder as `FactoryAssets`,
or create `factory-assets-path.txt` containing its local path. Alternatively,
set `TROLLFX_FACTORY_PACKAGES_DIR` in the host's environment if the Force host
supports that configuration. The helper rejects incomplete collections and
copies only manifests, RUN checkpoints, firmware transaction histories, and
event schedules. It excludes ROMs, firmware, EFE payloads, raw program dumps,
and captured audio. Keep the resulting package data private and transfer it
only for assets the user is authorized to use.

## Build and package

From the repository root, with the official SDK and Zig available:

```sh
AKAI_FORCE_SDK=/path/to/AkaiForceSDK \
ZIG_PYTHONPATH=/path/to/ziglang-python-module \
TROLLFX_FACTORY_PACKAGE_COLLECTION=/path/to/private/validated-packages \
  force_plugin/tools/build_candidate.sh --no-zip
```

Use `force_plugin/tools/build_candidate.sh` without `--no-zip` to also create
the release archive. Build and package do not install or restart the Force.
The opt-in installer accepts only a package with a valid playable marker:

```sh
python3 force_plugin/tools/install_package.py \
  '/path/to/package/TROLLfx - VST - ASR10 FX Collection' \
  '/path/to/Force/Plugins' --replace
python3 force_plugin/tools/rollback_package.py '/path/to/Force/Plugins'
```

Installation keeps a prior package as a rollback copy. The host restart is a
separate manual action.

## Verification boundary

`force_plugin/tools/test_packaged_vst.py` loads the freshly built native SDK
VST binary and runs test audio through the binary's VST callback. It checks all
50 slots against the local collection, stereo non-silent output, finite
samples, switching, state recall, missing-package silence, and callback
allocation count, then invokes the SDK host simulator. The generated
`factory-playback-status.json` is bound to the tested native and ARMv7 hashes
and lists per-slot results. A playable package marker is written only after
that full binary-bound gate and SDK package validation pass.

This verifies the native binary built from the same source and binds the
results to the corresponding ARMv7 binary hash; it does not execute ARMv7 code
on a Force. Physical-device compatibility, touch/Q-Link interaction, storage
permissions, and audio behavior remain unverified until tested on hardware.
The current trusted collection also lacks verified post-RUN clock evidence
for slot 50; this limitation is reported per slot and is not hidden by the
playback pass.

## Licensing and private data

The plugin source is GPL-3.0-only; SDK framework files retain their MIT
notices. Proprietary factory payloads and the local checkpoint collection are
not included in the public build or archive. The user must provide authorized
local assets.
