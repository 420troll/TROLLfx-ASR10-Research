# ES5510 ROM-02 and audio quality investigation v1

## Findings

### ROM-02 BUS controls

The starting concern is reproduced for BUS1. The strict ROM-02 reference
validator accepted the two-boot RUN checkpoint (60 active instructions,
44,100 Hz factory clock, SER2 stereo input to SER1 stereo output). The
post-RUN history contains 202 writes: BUS1/GPR `0x7C` is written 33 times,
from relative frame 492 through 17,075, ending at `0x350000`; BUS2/GPR `0x7A`
is written once at frame 501 to `0x350000`. The runtime test warms the program
with sustained stereo input to the same OS edit point, 177,123 frames
(4.01639 s) after RUN at 44.1 kHz, scaled to frame 192,787 at 48 kHz. Parameter
edits therefore occur after the last scheduled factory write.

It tested both verified settings, `0x350000` (display 25) and `0x370000`
(display 26), for BUS1 and BUS2. It also sent the observed unchanged companion
register (`0x7D=0x7FFF00` for BUS1 or `0x7B=0x7FFF00` for BUS2). BUS1 received
the repeated transaction 456 frames after the first. Every transaction was
scheduled and applied by `FactoryRuntime`; repeated same-setting runs were
bit-identical and all outputs finite.

BUS1 produced zero differing output samples in all 18 combinations: both
44,100 Hz factory mode and experimental 48,000 Hz mode; left-only, right-only,
and stereo input; impulse, deterministic noise, and sustained tones. BUS1
renders ran for 262,144 frames (5.94 s) after each edit. The scheduled firmware
writes had ended before the edit, so later schedule overwrites do not explain
the no-difference result. The ROM-02 BUS1 mapping is a verified OS register
correlation, but a direct experimental runtime GPR edit does not yet show
audio efficacy. The OS's first BUS1 Up also included an unclassified one-time
GPR `0x6D` change; this investigation does not invent its meaning or add it to
the adapter. No DSP arithmetic change is justified by current evidence.

BUS2 behaved differently: every left-only, right-only, and stereo case changed
the output at both rates. For example, sustained stereo input at 44,100 Hz
changed 32,090 of 32,768 output samples in the first 16,384-frame window,
with aggregate RMS difference 0.00236971 and peak difference recorded in the
JSON results. Each isolated input channel also changed both output channels.
This measures the active path under the validated routing; it does not infer
the meaning of the ASR-10's UI bus labels beyond the verified GPR mapping.

The `FactoryRuntime` routing maps input left/right to ES5510 serial indices 4
and 5 (SER2L/R), runs one DSP frame, and reads output indices 2 and 3
(SER1L/R). Both serial input lanes therefore excite the observed BUS2-sensitive
path. BUS1's lack of response persists with either lane independently and
with stereo input.

The touchscreen smoke-test finding is not explained by scheduled firmware
overwrites or by testing only one signal. It remains an experimental BUS1
control-efficacy gap: the OS write mapping is established, but the runtime's
direct write does not change numerical output in the tested window. An exact
same-stimulus OS-emulator audio recording around ROM-02 BUS1 edits is not
available, so equivalence to OS audio behavior cannot be decided. Keep BUS1
marked unverified for audible response until the OS update service and its
associated writes are understood.

### PCM16 threshold count

The historical 4,345 count used `abs(float_output) >= 32767/32768` before WAV
conversion. It was not a count of samples outside full scale. The fresh 50-slot
run measured:

| Measure | Count |
| --- | ---: |
| Near-full-scale threshold | 4,345 |
| Floating-point output with `abs(x) > 1` | 0 |
| Samples clamped by PCM16 WAV conversion | 0 |
| Non-finite samples | 0 |

Per-effect and per-stimulus results are in
[`ES5510_AUDIO_QUALITY_CLIPPING_V1.json`](ES5510_AUDIO_QUALITY_CLIPPING_V1.json).
All 4,324 near-threshold samples came from slot 31 (`SPKR CABINET`) sustained
audio; the other 21 came from slot 37 (`PHASER+DDL`) transient/noise audio.
The stored floating-point ES5510 samples stay within [-1,+1], so the WAV
converter did not clip them and no gain correction is warranted.

The available OS-emulator selector WAVs for slots 31 and 37 have PCM16 peaks
19,105 and 22,167, respectively, with no near-full-scale samples. Those WAVs
use the capture-session audio, not the generated harness stimuli, so this is
context rather than a matched comparison. No same-stimulus OS reference was
found for either slot.

## Regression evidence

The native 50-effect harness rerun loaded all 50 packages, produced finite
output for all 150 effect/stimulus renders, and reported no callback
allocations. The independent HALL and ROM-02 RUN references both remained an
exact 32,768-frame match at their factory rates with a two-frame alignment,
unity gain, and zero RMS/peak deviation. Twelve HALL/ROM-02 switches passed;
each configured fade is 240 host frames (5 ms) at 48 kHz, with deterministic
repeat loads and zero switch-callback allocations.

## Reproduction

ROM-02 uses the trusted private package, two-boot checkpoint evidence, and
event history. Keep output outside the checkout:

```sh
python3 tools/audio_validation/run_rom02_parameter_response.py \
  --manifest /home/gamer/research/private-results/rom02-provenance-v1-reference/replay-manifest/factory-state.json \
  --checkpoint /home/gamer/research/private-results/rom02-provenance-v1-reference/boot-a/snapshots/run-frame-905028.esp \
  --reference-root /home/gamer/research/private-results/rom02-provenance-v1-reference \
  --events /home/gamer/research/private-results/rom02-replay-v1-replay/32768/firmware-events.csv \
  --output /home/gamer/research/private-results/audio-quality-v1-rom02.json
```

Rebuild and run the 50-slot clipping, finite-output, HALL-reference, ROM-02
reference, continuity, and switching harness:

```sh
mkdir -p /home/gamer/research/private-results/audio-quality-v1/harness
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic \
  -Iinclude -Isrc -Iforce_plugin/src \
  tools/audio_validation/es5510_playback_harness.cpp \
  force_plugin/src/ES5510DSPBackend.cpp src/es5510_factory_runtime.cpp src/es5510.cpp \
  -pthread -o /home/gamer/research/private-results/audio-quality-v1/harness/es5510_playback_harness
/home/gamer/research/private-results/audio-quality-v1/harness/es5510_playback_harness \
  /home/gamer/research/private-results/es5510-50-effect-harness/accepted-packages.tsv \
  /home/gamer/research/private-results/audio-quality-v1/harness 48000 \
  /home/gamer/research/private-results/es5510-50-effect-harness/independent-reference-packages.tsv
python3 tools/audio_validation/summarize_audio_quality.py \
  /home/gamer/research/private-results/audio-quality-v1/harness/native-audio-results.json \
  /home/gamer/research/private-results/audio-quality-v1/clipping-summary.json \
  --collection-root /home/gamer/research/private-results/asr10-all-50-effects/validated-packages
```

All checkpoints, WAV files, raw captures, package state, and generated harness
outputs remain outside Git. The committed JSON files contain only redacted
measurements and status.
