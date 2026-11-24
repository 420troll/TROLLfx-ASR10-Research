# TROLLfx ES5510 Experimental Runtime V0.1

## Status

V0.1 is a reusable continuous stereo runtime around the repository's existing native `ES5510` core. It loads a validated private RUN checkpoint, retains DSP/DRAM state between arbitrary host blocks, routes host stereo to SER2 and reads SER1 stereo, supports absolute-frame GPR writes, and offers 48 kHz experimental or per-effect factory-reference processing rates.

Authentic private HALL and ROM-02 checkpoints both loaded and processed a 48,000-frame sine smoke test. The runtime returned finite, nonzero, unclipped audio for both captured programs. This is an authentic-program execution smoke test, not a new OS sample-exact comparison at 48 kHz. No factory payload or private checkpoint is committed.

## Baseline and native-core boundaries

The implementation was based on these exact baselines and reports:

- HALL V4 `f93030b`: strict RUN checkpoint, 89-word program, 342 halted register commits, 213 post-RUN writes, native output exact against the OS emulator through 32,768 frames.
- ROM-02 replay V1 `ff36f79`: strict 60-word state, 283 load-register commits, 202 post-RUN writes, native output exact against OS emulator through 32,768 frames.
- ROM-02 independent audit `26caf22`: evidence/reproducibility audit and limitations.
- ROM-02 provenance V1 `7daad13`: fresh bound captures; historical capture environment was not retrospectively authenticated.
- Clock experiment `631c61c`: native frame output is bit-identical across tested rates with the same checkpoint/input; 48 kHz is an experimental cadence, not established physical-chip support or factory-time equivalence.

`ES5510::run_frame`, arithmetic, delay-RAM addressing, saturation, and pipeline execution were not changed. The only native-core addition is read-only `active_program_words()` to reject a checkpoint whose active END position does not match the package profile. Loading uses `ES5510::load_capture_after_pipeline_reset`, which imports the full existing capture state and resets omitted pipeline slots only because the external package is required to certify the HALT reset acknowledgement.

## API and integration contract

Public header: [include/trollfx/es5510_factory_runtime.hpp](../include/trollfx/es5510_factory_runtime.hpp). Detailed call and route contract: [ES5510_EXPERIMENTAL_RUNTIME_API_V01.md](ES5510_EXPERIMENTAL_RUNTIME_API_V01.md).

```cpp
using namespace trollfx::es5510;
FactoryRuntime fx;
EffectPackage pkg{EffectId::Rom01Hall, privateCheckpointPath, 89,
                  29761.89453125, true, true, true};
if (!fx.loadEffect(pkg, RateMode::Experimental48000)) {
    // fx.getStatus().message identifies the rejected state.
}
fx.setRegister(0x20, 0x123456, 0); // apply before DSP frame 0
fx.processStereo(inputInterleaved, outputInterleaved, frames, 48000.0);
```

The three booleans certify pipeline-reset acknowledgement, strict package/source provenance validation, and SER2-input/SER1-output routing. They must be produced by a trusted host-side package validator, not set from untrusted UI fields. The runtime also validates profile identity/rate/program length, checkpoint format and full-state parse, and active END length. A missing path, incomplete capture, mismatched profile, or absent validation flags causes a load error. V0.1 does **not** parse the existing JSON manifest or verify its SHA-256 fields itself; callers should run `factory_manifest.py --require-replay-ready` and the relevant strict replay/boundary validation before constructing a package.

`reset()` reloads the original validated RUN checkpoint, clearing post-load DSP history and scheduled writes. `setProcessingRate()` changes cadence while retaining the current DSP state; choose the intended mode before use if exact factory timing matters. `setRegister()` accepts only GPR indices `0x00..0xBF`, schedules up to 256 writes in fixed storage, and applies each write before the named zero-based DSP frame. Calls that change state must be serialized between process calls; there is no cross-thread control queue yet.

## Audio and timing behavior

- Input/output are interleaved stereo float PCM. Non-finite inputs become zero; samples clip to `[-1,+1]` and convert deterministically to signed PCM16 with symmetric nearest rounding and saturated endpoints.
- Host left/right feed native serial lanes 4/5 (SER2 L/R). Native lanes 2/3 (SER1 L/R) are returned as host stereo. This matches the documented factory route; other serial routings fail at the package-validation boundary.
- 48 kHz mode executes 48,000 DSP frames/second. Factory-reference mode uses 29,761.89453125 Hz for HALL and 44,100 Hz for ROM-02. The same core is used at every rate.
- Rate conversion stays outside `ES5510::run_frame`: input is linearly interpolated at DSP tick times and DSP serial output is linearly interpolated to host frame times. Fractional phases persist across blocks. The converter has `ceil(host_rate / DSP_rate) + 1` host frames of latency (two frames at 48/48 kHz; three at 48 kHz host with these factory rates). Send silence to render remaining effect tail; no automatic flush is provided.
- Callback processing contains no dynamic allocation, mutex, file operation, or state reconstruction. The synthetic callback test instruments global C++ allocations and observes zero allocations.

Linear interpolation provides a minimal dependency-free V0.1 converter. It is not a high-quality bandlimited SRC; alias rejection and subjective audio quality need evaluation before production use. The 48 kHz mode intentionally changes the real-time spacing of fixed-frame delays relative to the original factory cadence. The clock experiment supports frame-domain numerical independence for identical frame inputs, not physical clock support or full effect time-domain equivalence.

## Loading and build commands

The buildable example intentionally requires an externally validated private RUN checkpoint and includes no factory data:

```sh
tools/audio_validation/build_factory_runtime_example.sh
build/audio-validation/es5510-factory-runtime-example hall /private/path/run-checkpoint.esp
```

Build the synthetic runtime tests and 48 kHz private-checkpoint benchmark:

```sh
tools/audio_validation/test_factory_runtime.sh
tools/audio_validation/benchmark_factory_runtime.sh hall /private/path/hall-run.esp
tools/audio_validation/benchmark_factory_runtime.sh rom02 /private/path/rom02-run.esp
```

The normal Python test command also invokes the C++ synthetic runtime suite:

```sh
python3 -m unittest discover -s tests -v
```

A sample-loading example is in `examples/es5510_factory_runtime.cpp`. Private state may be passed by local filesystem path at runtime; never add ROMs, firmware, EFE objects, instruction images, checkpoints, captures, or audio to Git.

## Tests and regression results

Synthetic C++ tests create tiny two-channel pass-through test programs with HALL/ROM-02 profile lengths. These are not Ensoniq factory algorithms. They verify:

- 48 kHz continuous execution, stereo SER2→SER1 route, deterministic PCM conversion, and two-frame SRC behavior.
- One large block versus partitioned blocks using sizes 1, 7, 64, 128, 256, 512, and 1024: bit-identical output.
- Silence, impulse, sine, seeded noise, and stereo polarity stimuli.
- Register scheduling before frame 0 and at a later frame boundary, event-in-the-past rejection, fixed queue behavior, reset, and effect reload.
- HALL 29,761.8945 Hz and ROM-02 44,100 Hz factory-reference configuration, plus the 48 kHz experimental mode.
- Zero heap allocations while `processStereo` runs.

The strict existing authentic replay gates were rerun on this branch with authorized private inputs:

- HALL: native remains exact against OS at 256, 4,096, and 32,768 DSP frames. Existing MAME divergence remains at relative sample 13,164; it is unchanged and outside this runtime's implementation.
- ROM-02: native remains exact against OS at 256, 4,096, and 32,768 DSP frames. Existing MAME divergence remains at relative sample 4,252. No arithmetic correction was made.
- Runtime smoke/performance: the authentic captured HALL and ROM-02 checkpoints each processed 48,000 host frames at 48 kHz. This local optimized C++ build measured 0.0880 s for HALL (11.36× real time) and 0.0620 s for ROM-02 (16.14× real time) on this machine. It is a single-run throughput measurement, not a cross-platform CPU guarantee. The reported output was nonzero and below full scale.

`python3 -m unittest discover -s tests -v`, `tools/audio_validation/test_factory_runtime.sh`, and the example build are the final verification gates. The final full suite passed all **61 tests** in 62.7 seconds. The research CLI and example builds also succeeded.

## Limitations and next integration steps

- The runtime consumes a RUN capture, not a cold boot loader sequence. It requires the complete private live state; authentic program words alone are insufficient.
- Package integrity/provenance is asserted by the trusted caller; V0.1 does not parse manifests or verify hashes internally.
- Parameter semantics/ranges and effect-specific controls are not implemented here. Other work can use the stable `setRegister(index,value,scheduledFrame)` interface and build its mapping outside the DSP callback.
- No cross-thread SPSC event queue, GUI, device host, plugin, latency compensation, tail flush, bandlimited SRC, or hardware validation is included.
- The verified OS reference uses the same native core. Existing exactness protects integration/replay behavior but is not independent proof of silicon correctness.
