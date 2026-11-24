# TROLLfx ES5510 Experimental Audio Host V0.1

## Scope and backend status

V0.1 is a self-contained, standard-library-only WAV processor and reusable
callback host. Its `MockProcessor` produces deterministic delay/reverb-like
audio so WAV conversion, buffer handling, controls, and effect switching can be
tested now. The names **HALL** and **ROM-02** select two mock profiles only;
this build does not execute either authentic factory program and makes no
factory sound-quality claim.

The `IProcessor` interface is the runtime integration seam. The referenced
ROM-02 replay and clock branches were reviewed; the worktree for
`feature/es5510-experimental-runtime-v01` is not available in this environment,
so there is no real-runtime adapter to integrate yet. `--backend runtime`
requires a private `--factory-state` path, reports missing state packages, and
then clearly reports that the runtime adapter is unavailable. No private
firmware/state data is read or committed by the mock host.

## Build and process WAV files

```sh
sh tools/build_experimental_audio_host.sh
build/experimental-audio-host/trollfx-audio-host input.wav output.wav \
  --effect hall --wet 0.35 --input-gain-db 0 --output-gain-db 0 --block 256
```

The input must be stereo RIFF/WAVE using PCM16, PCM24, PCM32, or IEEE float32.
Output is stereo PCM16 at 48 kHz. Non-48-kHz input is converted to 48 kHz with
linear interpolation; a 48 kHz source goes straight into the 48 kHz processor
with no rate conversion. Wet/dry and both gains are host controls, not factory
effect parameters. Non-finite input is silenced, output is clamped before PCM
conversion, and the source WAV is left untouched.

`--block` selects the maximum offline processing block size. The processor
state is continuous between blocks, so changing block size does not change the
output samples. The callback API accepts mono/stereo input, mono/stereo output,
null input as silence, and any callback frame count. It splits work into fixed
512-frame stack chunks; callback processing makes no heap allocations. The
processor reports zero algorithmic latency. A real audio device would add its
own buffer latency.

## Effect switching

The CLI can schedule the experimental application-level sequence
HALL → ROM-02 → HALL while processing sustained audio:

```sh
build/experimental-audio-host/trollfx-audio-host sustained.wav switched.wav \
  --effect hall --switch-at 2:rom02 --switch-at 5:hall
```

The single processor fades out over 5 ms, enters silence, and is reinitialized
by the control thread. The callback then fades the new state in over 5 ms. The
processor's fixed delay memory is 64 KiB; no second engine state or crossfade
memory is allocated. The callback remains muted until `service_control()` runs,
so a live application must keep polling that control method outside the audio
callback. Offline mode does this between blocks. Requests during an active
switch are ignored and can be retried when `switch_pending()` becomes false.
Tests verify the transition state and output samples; **click-free switching
has not been established**. This application behavior does not model OS
HALT/load/RUN firmware transitions.

## Rate model

The initial host and mock DSP both operate directly at 48 kHz. The API stores
host and DSP rates separately so a future runtime adapter can add virtual
factory rates and I/O conversion at the boundary. V0.1 rejects unequal host
and DSP rates; it performs no undocumented timing compensation. Fixed-frame
delays therefore occupy less time if a future adapter runs the same frame
program faster, as expected in the experimental mode. The clock experiment
documents emulator-only 48 kHz capability, not a physical OTTO/ES5510 timing
claim.

## Tests and measured performance

Run the host-specific tests with:

```sh
sh tools/test_experimental_audio_host.sh
```

Generated WAV tests cover silence, impulse, sine, sweep, reproducible noise,
stereo anti-phase input, sustained audio through HALL → ROM-02 → HALL, 44.1 to
48 kHz duration conversion, deterministic output, and block-size independence.
The C++ callback tests cover irregular lengths including 1, 511, 512, 513, and
2,049 frames, mono/stereo routing, finite/clamped PCM conversion, a 48 kHz
clock check, and zero callback heap allocations. The runtime-backend test
checks both missing private state and the unavailable adapter error.

One local measurement used a generated 10-second 48 kHz stereo sine, mock
HALL, 256-frame blocks, and the optimized build:

| Measurement | Result |
|---|---:|
| Frames processed | 480,000 |
| Processing loop | 7.17 ms |
| Processing time / audio duration | 0.000717× real time |
| Estimated processing working set | 11,589,632 bytes |
| Reported processor latency | 0 frames |

The timing covers the host processing loop, not WAV decoding, sample-rate
conversion, or output-file writing. The memory number estimates owned audio
buffers plus mock delay memory; it is not peak process RSS. These are one local
mock benchmark, not a real-time device benchmark or DSP quality measurement.

## Device playback

Interactive playback was not added. This environment has no CMake executable,
SDL2/ALSA development headers or package metadata, and `/dev/snd` exposes only
the timer node, not a playback device. The repository's existing SDL/RtAudio
front end cannot be built here with a reliable output backend. The callback API
is ready for a device adapter once a supported local audio backend is
available.
