# ES5510 Experimental Runtime V0.1 API contract

Header: `include/trollfx/es5510_factory_runtime.hpp`.

The runtime accepts a **private validated RUN checkpoint package**, not just a microprogram. `EffectPackage` supplies a path to an `ES5510C` checkpoint and evidence metadata: effect identity, active instruction count, factory reference rate, HALT/pipeline-reset acknowledgement, and provenance validation. The package author must establish these booleans from the private manifest, independent program/source correlation, and recorded load sequence. Missing or unvalidated state is a hard load error. The runtime calls the existing `ES5510::load_capture_after_pipeline_reset`; it does not recreate firmware initialization or infer missing live registers.

The supported captured route is stereo input SER2 L/R on serial lanes 4/5 and stereo output SER1 L/R on lanes 2/3. `processStereo` accepts and returns interleaved float samples. Conversion to signed 16-bit serial values is deterministic; the implementation owns rate-conversion phase and retains DSP state between calls. The V0.1 callback path allocates no memory. Processing/control methods are serialized on one owning thread; make register/rate/load changes between process blocks. Register events use absolute DSP frame numbers and apply before the selected frame.

`RateMode::Experimental48000` selects 48,000 DSP frames per second. `RateMode::FactoryReference` selects the package's measured factory rate (29,761.89453125 Hz for ROM-01 HALL, 44,100 Hz for ROM-02). The latter preserves captured cadence as represented by the emulator, not proven physical-chip timing. Rate conversion sits at the input/output boundary; no rate enters or changes the ES5510 arithmetic.

Example (after obtaining a validated private package):

```cpp
#include <trollfx/es5510_factory_runtime.hpp>
#include <array>
using namespace trollfx::es5510;
FactoryRuntime fx;
EffectPackage pkg{EffectId::Rom01Hall, "/private/hall/run.esp", 89,
                  29761.89453125, true, true};
if (!fx.loadEffect(pkg, RateMode::Experimental48000)) { /* inspect fx.getStatus() */ }
std::array<float, 512 * 2> input{}, output{};
fx.processStereo(input.data(), output.data(), 512, 48000.0);
```

The example intentionally contains no effect payload and its booleans are placeholders for a package-validation layer, not permission to trust unverified metadata. V0.1 has no GUI, plugin wrapper, live cross-thread control queue, physical-device timing claim, or factory parameter mapping.
