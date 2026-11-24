# Force ES5510 DSP backend integration

force_plugin/src/ES5510DSPBackend.* adapts the native FactoryRuntime to the
Force stereo effect callback. It keeps a continuous ES5510 instance, maps host
stereo to the descriptor's serial input/output, runs in experimental 48 kHz DSP
mode, and resamples through FactoryRuntime at the host rate. The wet/dry path
delays dry audio to the runtime's reported processing latency; input/output
gain and bypass are applied without resetting DSP state.

## Package-provider boundary

Codex 1 owns package trust and import. Implement
IValidatedFactoryPackageProvider::package_for_slot() using its trusted
validated-package objects. Returned packages and referenced local checkpoints
must remain available and immutable for the provider lifetime. Do not set
validation flags from raw UI choices or unvalidated user files. Install the
provider before plugin prepare() using
TROLLfx_InstallValidatedFactoryPackageProvider(); a backend can also receive
the provider directly for native tests. This backend performs no manifest
parsing and makes no provenance decisions.

The first two UI slots select independent ROM-01 HALL and ROM-02 44KHZ REVERB
packages. Slot identity warnings in the 50-effect catalog remain applicable to
the catalog's separately captured selector snapshots. Slots without a provider
package are unavailable and output silence; no dry or synthetic effect is
reported as factory DSP.

## Real-time and switching behavior

Package lookup, checkpoint loading, and DSP initialization happen in prepare
or on the backend worker for a later effect switch. The callback uses fixed
stack blocks, fixed dry-delay storage, atomics, and the native allocation-free
processStereo() method. It performs no file access, mutex operation, or
allocation. Effect changes fade out over 5 ms, load into the inactive runtime
off-thread, exchange at silence, then fade in over 5 ms. If loading fails, the
backend remains silent and reports failure.

The provider must be installed before initial prepare. Do not replace or
destroy a provider while an instance is running.

## Verification

Run force_plugin/tools/test_es5510_backend.sh in the research environment
with the authorized local HALL and ROM-02 RUN checkpoints present. The test
processes both authentic checkpoints, checks nonzero/non-dry output, checks
48 kHz DSP scheduling on a 96 kHz host, exercises the 5 ms switch boundary,
and counts allocations made on the audio test thread.

This checkout does not include the Akai Force SDK. Its existing candidate
build helper stages only ASR10FXCollection.cpp; SDK build integration must
add ES5510DSPBackend.cpp, the repository runtime and ES5510 core, and their
include paths. That build/package tooling belongs to Codex 3 and was left
unchanged. Therefore the native DSP backend is verified here, but a rebuilt
ARM VST2 and an on-device Force callback run remain pending SDK integration.
