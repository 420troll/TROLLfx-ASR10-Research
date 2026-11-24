# ASR-10 50-effect native playback validation

The harness runs validated package state through the existing native ES5510
FactoryRuntime. It does not emulate a second DSP or infer package validity.
Collection entries are considered only when the supplied Codex 1 importer
emits registry_eligible: true; independent HALL and ROM-02 reference packages
are considered only after validate_factory_runtime_package.py returns a valid
receipt. The provider and output files are private inputs and must stay
outside the repository.

## Run

Use a private output folder outside both the checkout and package source tree.
Supply the current Codex 1 importer and, optionally, a private JSON reference
config containing validated HALL/ROM-02 manifest, checkpoint, two-boot root,
event CSV, and same-capture serial input/output CSV paths.

    python3 tools/audio_validation/run_es5510_playback_harness.py \
      --packages "$ASR10_PRIVATE/validated-packages" \
      --importer "$CODEX1_WORKTREE/tools/audio_validation/import_factory_effect_collection.py" \
      --reference-config "$ASR10_PRIVATE/reference-config.json" \
      --output-dir "$ASR10_PRIVATE/playback-harness" \
      --host-rate 48000

The runner builds the C++ harness in the output folder. It calls the Codex 1
importer, maps only eligible descriptors into EffectRegistry, and invokes the
existing native runtime. Optional known-profile comparisons use the
repository's strict HALL/ROM-02 package validator. The private output folder
contains the importer audit, accepted descriptor tables, temporary reference
sample files, the machine report, and three PCM WAV renders per loaded effect
(impulse, sustained, transient). The WAVs and report include local paths and
stay private.

Without --reference-config, references are marked not_matched. A profile is
attached to a collection checkpoint only when checkpoint SHA, active program
identity, factory rate, and future event schedule match. The runner also stores
validated independent references separately when their state does not match a
collection checkpoint.

## Measurement contract

All three generated stimuli use stereo inputs with independent left/right
content. Each effect is reloaded from its validated checkpoint between
stimuli, with its bounded firmware event schedule reapplied. Generated audio
uses experimental 48 kHz DSP processing and the requested host rate. The
reference pass uses the profile's factory processing rate and original captured
SER2 input frames, then compares SER1 output after the runtime's reported
two-frame latency.

Per stimulus, the JSON reports peak, RMS, clipped and finite sample counts,
stereo difference RMS, relative gain, silence, DSP frame count, callback
allocations, total and worst-block processing times, and real-time factor.
Reference comparisons report timing offset, per-channel and aggregate RMS
deviation, peak deviation, relative gain, stereo-separation deviation, and
last-ten-percent tail deviation. A direct comparison is reported only when the
input, rate, program, checkpoint state, and event schedule match. The pass
gate is RMS error at most one PCM16 step and peak error at most two PCM16 steps.

Switch tests use the existing ES5510DSPBackend, exercise twelve HALL/ROM-02
switches when both packages are present, check the 239-frame/240-frame 5 ms
fade-out boundary, verify deterministic output after repeated checkpoint
reloads, test finite stereo output, and count allocations on the audio thread.
The firmware-event queue is fixed-capacity at 1,024 writes; no event list is
truncated or streamed from disk in the callback.

## Run captured in this branch

The private Codex 1 audit accepted all 50 current collection packages. The
native runtime loaded all 50, and all 50 produced finite, non-silent output for
each of the three generated stimuli. No package was rejected by the registry.
The independently validated HALL and ROM-02 references both passed direct
32,768-frame comparisons with zero RMS and peak deviation, unity relative
gain, zero tail deviation, and a two-frame latency alignment. Those reference
tests are separate from the collection-slot count; no reference is claimed for
a collection package whose checkpoint state differs.

On the capture host, the 150 renders ran at 7.4× to 23.9× real time, with a
median of 12.0×. Package load time ranged from 2.1 to 3.7 ms. The largest
measured 256-frame processing block took 1.57 ms at a 48 kHz host rate.
Aggregate output included 4,345 samples at the PCM16 clipping threshold.
The process peak resident set was about 89.7 MiB; this is a whole-process
high-water measurement, not a per-effect allocation figure. These desktop
measurements do not predict Force ARMv7 timing.

## Current collection status

The machine report records:

- Collection packages captured by importer: 50.
- Registry-eligible collection packages: 50.
- Native loads successful: 50.
- Effects with finite audio for all stimuli: 50.
- Direct matched reference comparisons passed: 2 (independent HALL and ROM-02).
- Collection slots blocked or unverified: 0 in this importer result.

If a future importer marks entries ineligible, they are not promoted by this
harness. They remain in the import audit with Codex 1's reason and count as
blocked/unverified. No private checkpoint, audio file, program image,
instruction word, register dump, or raw event stream belongs in Git.
