# ES5510 audio measurement laboratory

`tools/audio_lab/lab.py` is a standalone Python toolkit for deterministic PCM16 stimulus generation, WAV intake, measurements, comparisons, parameter sensitivity summaries, fingerprints, and report output. It complements `tools/audio_validation/run.py`, which remains the C++ executor regression runner. No factory audio is checked in.

## Install and use

Python 3.9+, NumPy, and Matplotlib (for plots) are used. WAV I/O uses the standard library. Matplotlib is optional for analysis and report generation; install with `python3 -m pip install numpy matplotlib` to emit PNG plots. No SciPy is required.

```sh
python3 tools/audio_lab/lab.py stimulus impulse --rate 48000 --frames 96000 --output /tmp/impulse.wav
python3 tools/audio_lab/lab.py analyze /private/render.wav --input /tmp/impulse.wav --json /private/render.measurements.json
python3 tools/audio_lab/lab.py compare /private/reference.wav /private/candidate.wav --json /private/comparison.json
python3 tools/audio_lab/lab.py demo --out /tmp/es5510-synthetic-demo
python3 -m unittest discover -s tests/audio_lab -v
```

Stimuli include single/stereo impulses, logarithmic sweep, sine, multitone, seeded uniform noise, silence, and controlled step, at 44.1 or 48 kHz. `analyze()` emits peak/RMS, active tail endpoint, arrival peaks, Schroeder-integrated EDT/T20/T30/RT60 estimates, stereo channel correlation, and input-conditioned transfer spectrum, level ratio, and dominant correlation delay. `compare()` keeps bit equality explicitly separate from alignment/error metrics. Its spectral/decay differences are numerical signal comparisons, not perceptual similarity claims.

## Method and limits

Decay is estimated from the reverse cumulative squared signal (Schroeder energy curve), with linear regression over standard level spans. T20/T30 are extrapolated to 60 dB only when enough samples span the measurement range; absent spans return null and a reliability reason. EDT uses the 0 to -10 dB slope extrapolated to 60 dB. These estimates presume a sufficiently isolated decay and are not dependable with noise floors, continuing modulation, clipping, short renders, or strong unrelated direct sound. Tail endpoint is threshold-relative (-100 dB from peak), not a physical silence claim.

The transfer spectrum is the averaged output-input cross spectrum divided by input power, with a Hann window and 50% overlap. It is valid only where the stimulus has energy and for approximately linear time-invariant behavior; modulation/reverb violate that assumption. Delay is the dominant cross-correlation lag, best interpreted using an impulse. Predelay and early-reflection candidates are output envelope peaks, not automatically classified reflections. Correlation between opposite channels is not proof of internal cross-feedback. A true wet/dry ratio requires a dry-reference render; the reported output/input level ratio is labeled accordingly.

## Fingerprints and private factory renders

Fingerprint JSON uses `schema`, `effect_id`, `source_type` (`reference_render`, `emulator_prediction`, or `synthetic`), `provenance`, `parameters`, and a `measurement` object. Keep provenance factual: record emulator/build, effect selection evidence, sample rate, stimulus identity/hash, render duration, and any load/replay manifest. Set `source_type` to `reference_render` only for a render from the reference ASR-10 emulator under documented conditions; use `emulator_prediction` for a standalone implementation output. Never transfer a prediction into a reference field. Run tools with private paths under a local private output directory; the repository ignores WAV files, but also avoid adding reports/plots containing private-derived measurements unless approved for publication.

The synthetic example in `docs/audio-lab/example/` illustrates report shape only. Its acoustic values are not factory measurements.
