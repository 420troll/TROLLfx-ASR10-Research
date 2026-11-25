# ASR-10 PC Audio Test Backend V0.1

## Purpose

This branch adds an offline and streaming test layer over the existing native
`FactoryRuntime`. It does not add a second DSP implementation, change native DSP
arithmetic, modify the PC GUI, or touch the Force plugin/install.

The WAV runner loads trusted private effect packages through the existing
collection importer, uses the native ES5510 core, processes stereo audio at the
experimental 48 kHz rate, and writes PCM16 WAV files. The collection, source
audio, audit output, and rendered audio remain under
`/home/gamer/research/private-results/` and are not in Git.

## Codex 2 integration API

Public header: `include/trollfx/es5510_audio_test_backend.hpp`.

### Streaming host

```cpp
using namespace trollfx::es5510;
using namespace trollfx::es5510::audio_test;

FactoryAudioTestBackend backend(registry); // registry owns validated packages
if (!backend.selectEffect(slot, RateMode::Experimental48000)) { /* report status */ }
backend.setParameter("low_freq_decay", 7, backend.status().processed_dsp_frames);
backend.process(input_interleaved, output_interleaved, frames, 48000.0);
```

Effect loading, package validation, file reads, and runtime setup belong on the
host/control thread. Process variable frame counts in blocks. The runtime retains
DSP, pipeline, and DRAM state between calls. Parameter changes are applied by
calling `setParameter` between blocks at the requested absolute DSP frame.
Only verified display points present in the loaded descriptor are accepted.

`parameterWriteLog()` reports the verified mapping's exact ordered GPR writes
and scheduled frame. It is an audit of requested parameter updates; it does not
claim to observe every internal ES5510 register write. The existing runtime
status reports processing state and algorithmic latency. This V0.1 adapter does
not add allocation, file I/O, or blocking to the DSP process call.

### WAV tools

```sh
python3 tools/audio_validation/run_es5510_wav_test.py \
  --collection /home/gamer/research/private-results/asr10-all-50-effects/validated-packages \
  --slot 1 --input /path/to/stereo.wav --output-dir /path/outside/repository \
  --block 257 --tail-frames 48000 --bypass-ab
```

For a parameter comparison, render independent checkpoint-identical runs:

```sh
python3 tools/audio_validation/run_es5510_wav_test.py \
  --collection /home/gamer/research/private-results/asr10-all-50-effects/validated-packages \
  --slot 1 --input /path/to/stereo.wav --output-dir /path/outside/repository \
  --block 257 --tail-frames 48000 --compare low_freq_decay 7 32768
```

The wrapper runs `import_factory_effect_collection.py` first, checks the
importer's eligibility result and private file hashes, and only then constructs
runtime packages with validated state flags. It refuses to put output inside
the Git checkout or private source collection. WAV input is converted to
48 kHz outside the DSP core using linear interpolation; no automatic alignment,
normalization, or resampling is used for the A/B audio comparison after that
input conversion. The WAV runner currently accepts the experimental 48 kHz
configuration only.

Available CLI options:

- `--slot N`: authentic private collection slot, 1 through 50.
- `--event FRAME:PARAMETER_ID:DISPLAY_VALUE`: schedule one or more exact,
  verified parameter points.
- `--compare PARAMETER_ID DISPLAY_VALUE FRAME`: compare checkpoint-identical
  baseline and changed renders.
- `--bypass-ab`: render processed and latency-aligned dry WAVs.
- `--block N`, `--tail-frames N`: select host block size and post-input tail.

Build/test command:

```sh
tools/audio_validation/test_es5510_audio_test_backend.sh
```

The command compiles and runs the synthetic backend tests without private
assets. For an authentic package render, use the wrapper above. The underlying
CLI can also be compiled directly using the wrapper's generated command and
sources; the wrapper is preferred because it applies the trust gates.

## Evidence gathered

### HALL path

An authorized local HALL WAV smoke render used slot 1, 48 kHz, 127-frame
blocks, and 48,000 tail frames. It processed 144,000 DSP frames with 213
scheduled firmware writes applied and reported two host frames of algorithmic
latency. The output was finite and stereo. Against the aligned bypass render,
the difference RMS was 0.031401 left and 0.0325915 right, with peak difference
0.549988. This demonstrates non-dry native processing for this stimulus.

An exact catalog-point A/B at frame 32,768 for HALL `low_freq_decay` display
value 7 applied GPR `0x5B=0x090034`; it produced difference RMS 0.000245449
left / 0.000222274 right and peak 0.000915527. These are test observations,
not a claim that a full control range or curve is known.

### FLANGER+REV no-response case

Slot 8 `flange_depth` display 98 maps to GPR `0x88=0x7E7E7E`; display 99 maps
to `0x88=0x7F7F7F`. The runtime accepted and logged the update. Two comparisons
with the current sustained stereo test file, one at frame 32,768 and one at
frame 0, both reported exactly zero floating-point output difference. The
tested file is not a sufficient proof that the control has no audible effect.

The captured ROM-08 active instruction image references GPR `0x88` as an ALU
operand at PC `0x0B` (instruction word `851c8889e128`). In the private package's
post-RUN schedule, a firmware write also sets GPR `0x88` to `0x7F7F7F` at
relative frame 451. This is a candidate reason that an edit may be masked or
short-lived, but it is not yet established: the frame-0 edit is scheduled
before processing, and its waveform still matched the baseline exactly. The
mapping is preserved unchanged. Follow-up should inspect the internal per-frame
GPR value around PC `0x0B`, then test impulse/noise bursts and modulated swept
tones both before and after the frame-451 firmware update, while retaining the
observed firmware event ordering.

## Tests and limits

The synthetic test suite verifies native runtime loading, stereo processing,
parameter scheduling/logging, reset, WAV output, A/B metrics, and finite samples
without private payloads. The HALL and FLANGER runs above additionally exercise
the trusted private import path and real factory programs. The full repository
regression suite has not yet been run on this branch; run it at the integration
gate alongside existing strict HALL/ROM-02 regressions.

This backend does not implement the simulator GUI, a general host-rate
resampler, real-time effect switching/fades, internal per-instruction register
instrumentation, or parameter values beyond the verified points already in the
descriptors. Output is PCM16, so subtle float-domain differences may be lost in
the exported files; reported A/B metrics are computed before PCM16 encoding.

## Handoff to Codex 2

Use `FactoryAudioTestBackend` for the GUI's streaming audio adapter and
`WavAudioTestRunner` for offline audition/export and parameter A/B checks. Pass
the same `EffectRegistry` that owns the validated package objects. Load/select
effects and prepare any asset-backed state off the audio callback. Apply
parameter changes between process blocks using the current DSP frame from
`status()`. Use the runtime's reported latency for dry-path alignment. Report
failed `selectEffect` or parameter calls using `status().message`; never fall
back to dry or mock output on a package/runtime failure.

The handoff is source-level and does not imply that Codex 2's GUI branch has
already integrated or tested this API.
