# TROLLfx ASR-10 FX Collection — Force candidate

Version 1.0.0-experimental. Original Akai Force ARMv7 hard-float target; experimental 48 kHz mode.

This unverified Force candidate provides the expandable 50-slot browser and host parameter shell. All 50 OS-observed slot labels are present; slots 3–50 are marked unavailable. HALL and ROM-02 are marked as needing packages, but this candidate has no Force-side factory package loader. Until authentic, validated state packages are connected, the signal remains dry passthrough. No mock factory audio is used or claimed.

The current VST state chunk saves the fixed parameter values, but named user presets, parameter application, meters, and actual wet/dry blending are not implemented. See `docs/TROLLFX_ASR10_FORCE_COLLECTION_V1.md` for the runtime/API blocker.

Build with `force_plugin/tools/build_candidate.sh`. Output is a build candidate, not a device-tested release. No firmware, ROM, EFE, checkpoints, microprograms, captures or audio are bundled. The folder contains `SHA256SUMS` and license notices. The repository source is GPL-3.0; the linked MPC SDK framework identifies as MIT.

Manual install: `force_plugin/tools/install.sh PACKAGE_DIR FORCE_VST2_PLUGINS_DIR`. Manual rollback: `force_plugin/tools/rollback.sh FORCE_VST2_PLUGINS_DIR`. Neither script restarts the host.
