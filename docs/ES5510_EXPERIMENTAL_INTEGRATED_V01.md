# TROLLfx ES5510 Experimental Integrated V0.1

## Delivered

`trollfx-audio-host` now connects the WAV host to the existing native
`FactoryRuntime`. It runs the captured ROM-01 HALL (89 active words) and ROM-02
44KHZ REVERB (60 active words) packages at experimental 48 kHz, retains DSP
state across blocks, sends stereo input to SER2 L/R, and reads stereo output
from SER1 L/R. The native DSP arithmetic and delay addressing were not changed.

The host validates both effects before processing. Validation checks the
private manifest, checkpoint digest and live state, program/GPR/SPR digests,
memory and delay configuration, reset and serial-route evidence, matching
captures from two boots, and the observed post-RUN event schedule. The runtime
evidence flags are set only after the validator succeeds. The replay-derived
firmware writes are queued relative to the recorded RUN frame whenever an
effect is loaded. Checkpoint and event files stay outside Git.

The host supports `--backend runtime` (authentic captured factory program in
the native experimental emulator core) and `--backend mock` (synthetic; never
described as factory processing). Controls include `--effect`, `--wet`,
`--block`, gain options, `--switch-at`, initial `--bus1`/`--bus2`, and scheduled
`--set-at SEC:EFFECT:BUS1|BUS2:VALUE`. Only observed BUS display values are
accepted: HALL 28/29, ROM-02 25/26. No wider range or factory smoothing is
claimed.

Effect changes use the host's 5 ms fade out, control-thread package reload, and
5 ms fade in. Package parsing/validation happens before the audio processing
loop; switch preparation is serviced between blocks. Each reload restores the
effect's own checkpoint and firmware schedule. The host reports two frames of
algorithmic latency at 48 kHz and delays the dry path to match it.

## Build

From the repository root:

```sh
sh tools/build_experimental_audio_host.sh
```

The executable is `build/experimental-audio-host/trollfx-audio-host`.

## Private package paths

These existing private files were used for the delivered renders:

```sh
HALL_CHECKPOINT=/home/gamer/research/private-results/asr10-hall-reference-capture-v2-20261124/boot-a/snapshots/run-frame-855973.esp
HALL_MANIFEST=/home/gamer/research/private-results/asr10-coldload-tail-20261123T210000Z/state/factory-state.json
HALL_REFERENCES=/home/gamer/research/private-results/asr10-hall-reference-capture-v2-20261124
HALL_EVENTS=/home/gamer/research/private-results/asr10-hall-replay-v4-verified-20261124/32768/scheduled-firmware-writes.csv
ROM02_CHECKPOINT=/home/gamer/research/private-results/rom02-provenance-v1-reference/boot-a/snapshots/run-frame-905028.esp
ROM02_MANIFEST=/home/gamer/research/private-results/rom02-provenance-v1-reference/replay-manifest/factory-state.json
ROM02_REFERENCES=/home/gamer/research/private-results/rom02-provenance-v1-reference
ROM02_EVENTS=/home/gamer/research/private-results/rom02-replay-v1-replay/32768/firmware-events.csv
```

Example authenticated HALL render (with a 2 second silence tail):

```sh
build/experimental-audio-host/trollfx-audio-host input-48k.wav hall.wav \
  --backend runtime --effect hall --wet 1 --block 128 --tail-seconds 2 \
  --hall-checkpoint "$HALL_CHECKPOINT" --hall-manifest "$HALL_MANIFEST" \
  --hall-reference-dir "$HALL_REFERENCES" --hall-events "$HALL_EVENTS" \
  --rom02-checkpoint "$ROM02_CHECKPOINT" --rom02-manifest "$ROM02_MANIFEST" \
  --rom02-reference-dir "$ROM02_REFERENCES" --rom02-events "$ROM02_EVENTS"
```

Change HALL BUS2 from its observed display value 28 to 29 at two seconds:

```sh
... --backend runtime --effect hall --bus2 28 --set-at 2:hall:bus2:29 [package options]
```

Switch HALL → ROM-02 → HALL at 2 and 5 seconds:

```sh
... --backend runtime --effect hall --switch-at 2:rom02 --switch-at 5:hall [package options]
```

Both package sets are required so switching can only load a separately
validated state. For isolated CLI tests, select `--backend mock` explicitly.

## Playable renders and measurements

Generated WAVs are in the private, untracked directory
`/home/gamer/research/private-results/es5510-experimental-integrated-v01-demo/`:

- `sustained-stereo-48k-input.wav`: 8 seconds of stereo sustained test audio.
- `hall-48k.wav`: HALL plus 2 seconds of appended silence.
- `rom02-48k.wav`: ROM-02 plus the same tail.
- `hall-rom02-hall-switch-48k.wav`: HALL → ROM-02 → HALL, at 2/5 seconds.
- `hall-bus2-28-baseline.wav` and `hall-bus2-29-at-2s.wav`: parameter comparison.

The renders are PCM16 stereo at 48 kHz. On the recorded runs, HALL RMS/peak
were 0.128/0.437, ROM-02 0.131/0.417, and the switch render 0.129/0.436
(normalized to full scale). HALL wet-only output's aligned RMS difference from
the input was 0.0497; the appended two-second tail RMS was 0.0066. This
establishes that the output is not dry passthrough. Changing BUS2 from 28 to 29
at 2 seconds yielded a whole-file RMS difference of 0.00127 (maximum sample
difference 0.00562). These are emulator renders, not new physical-hardware
measurements or claims of sample-exact OS equivalence at 48 kHz.

At 128-frame blocks, offline wall time was 0.85 s for the 10 s HALL render,
0.46 s for ROM-02, and 0.70 s for the switching render (about 0.085x, 0.046x,
and 0.070x real time). Estimated resident working memory reported by the host
was 12,986,368 bytes, dominated by WAV input/output buffers and the native DSP
DRAM. Algorithmic latency is reported as 2 frames (41.7 microseconds at 48
kHz); no external audio-device latency is included. The host's fixed-size
buffers preserve block continuity. The switch uses a deliberate fade/reload
window, so it is not sample-continuous through the transition. No ARMv7 or Akai
Force performance claim is made.

## Verification and limits

Both private packages and their post-RUN schedules passed validation during
the smoke and demo renders. Focused WAV-host tests and the final repository
test gate are recorded with the integration commit. The native runtime's
existing replay regressions remain the authority for its captured-state DSP
behavior; this host integration does not change DSP arithmetic.

The processor is offline WAV software, not yet a live device/plug-in. It
requires authorized local private state and replay-event files; it does not
bundle any ROM, firmware, effect program, checkpoint, or audio. The 48 kHz mode
is experimental. Factory reference rates remain documented in package
validation (HALL 29,761.89453125 Hz, ROM-02 44,100 Hz), and successful 48 kHz
execution does not establish those effects' original silicon timing.
