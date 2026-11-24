# ES5510 Force DSP integration report

## Integration

The Force SDK candidate compiles the real ES5510 DSP core, `FactoryRuntime`,
`ES5510DSPBackend`, and the plugin wrapper. The build stages four C++ sources
and the runtime, registry, core, and backend headers. HALL and ROM-02 are
selected by their one-based factory slot through
`IValidatedFactoryPackageProvider::package_for_slot()`. Package lookup and
checkpoint loading happen outside the audio callback. The callback uses the
continuous runtime, fixed-size processing blocks, atomics, and no file I/O or
allocations. Switching fades out over 5 ms, loads the inactive runtime on its
worker, then fades in over 5 ms.

The shipping provider implementation is not present in this checkout. The
backend is connected to its provider API, and the native integration test
registers packages only after the strict repository package validator passes.
Until the authorized local package importer installs a provider into the plugin,
all factory effects report unavailable and produce silence. No dry or synthetic
effect is substituted. The build remains an unplayable candidate.

## Evidence and tests

Command:

```sh
AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK \
  force_plugin/tools/build_candidate.sh --no-zip
```

Toolchain: Zig 0.17.1 through `/usr/bin/python3 -m ziglang`; SDK commit
`4521c247a2deae30efb9e93d53fc8f9390c51e81`.

`force_plugin/tools/test_es5510_backend.sh` first runs
`tools/audio_validation/validate_factory_runtime_package.py` on the existing
private HALL and ROM-02 initialization manifests, RUN checkpoints, reference
trees, and firmware event schedules. Only after both validations succeed does it
generate a temporary provider outside Git and compile the real backend and
plugin wrapper for native audio tests. The tested evidence was:

| Effect | Program words | RUN frame | DSP rate | Firmware writes |
|---|---:|---:|---:|---:|
| ROM-01 HALL REVERB | 89 | 855973 | 29761.895 Hz | 213 |
| ROM-02 44KHZ REVERB | 60 | 905028 | 44100 Hz | 202 |

The native tests passed: non-silent wet output for both effects through the
plugin wrapper, backend effect selection/switching, a 96 kHz host rate retaining
48 kHz experimental DSP scheduling, arbitrary short blocks, dry alignment, and
fail-closed missing-package behavior. The callback allocation counter reported
zero allocations. Across final runs, the 8,192-frame HALL test segment took
0.012–0.015 s (11.3–14.7x real time); one complete backend-test process peaked
at 22,616 KiB RSS. These are host measurements, not Force-device performance
measurements.

The SDK build compiled the native host library and both cross targets. The ARM
binary exports `VSTPluginMain`, is ELF32 ARMv7-A hard-float, requires glibc no
newer than 2.27, and has dependencies `libm.so.6`, `libc.so.6`,
`ld-linux-armhf.so.3`, `libpthread.so.0`, and `libdl.so.2`. SDK validation
reported zero errors and zero warnings. The ARM32 candidate SHA-256 is
`7857d0f47981f3bcb09b54f1fbc5aa0e9bd726772dbf011d3f09fbb2da1e2f72`; ARM64 is
`b30afc7a0a422a1b2807a0c31751c7580835d1a168e1879de20334e736b8ae04`.

These results establish that the ARM binary was freshly linked from the real
engine sources and passes SDK/ABI validation. They do not establish binary-bound
audio playback through the packaged shared object, production package-provider
availability, or hardware behavior. Therefore no playable marker was written
and no device was installed or restarted.

## Release candidate and rollback

The build places the candidate under
`force_plugin/dist/TROLLfx - VST - ASR10 FX Collection`. It is labeled
**BUILD CANDIDATE ONLY — NOT PLAYABLE / DO NOT INSTALL**. A release marker can
only be created by the packaging gate after binary-bound native VST tests and
the required processing evidence pass; this integration did not create one.

Build the package with the command above. The package installer remains opt-in;
do not run it for this unplayable candidate. For any later authorized install,
use the installer’s matching rollback script and the documented pre-install
backup. No Force device test was available for this report.

## 50-effect playback harness

The branch also carries the native 50-effect playback harness from commit
`071d860`. It accepts packages only through the importer audit's
`registry_eligible` entries, exercises the existing FactoryRuntime, renders
deterministic stereo stimuli, and records timing, finite-sample, output, and
matched-reference metrics. Its captured report is desktop/native evidence and
does not replace a test of the packaged VST shared object. Binary-bound plugin
verification is performed separately by `force_plugin/tools/test_packaged_vst.py`
on the provider branch and must be repeated after the final integration build.
