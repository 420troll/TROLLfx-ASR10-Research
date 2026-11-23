# ES5510 factory HALL replay verification

This worktree adds a read-only comparison path. It does not change emulator or MAME DSP arithmetic and does not package factory firmware, ROM, EFE, DRAM, serial capture, or rendered audio.

## Replay eligibility

Each replay JSON must identify the exact input stream, initial DSP state, ordered firmware event sequence, and alignment with SHA-256 fingerprints/description. Both traces must match all four fields before any output comparison runs. Adapter-created data remains observational: `hall_replay_adapters.py` accepts canonical divergence-trace serial events, fingerprints the redacted HALL load-boundary lifecycle, and carries audio-lab summaries while marking them as non-factory evidence. Provide capture-backed hashes; a manifest hash alone does not prove matching execution state.

## Clock domains and samples

Native HALL serial samples use the observed ES5510 frame rate **29,761.89453125 Hz**. Host WAV samples use **44,100 Hz**. These streams are reported separately. Mapping a host frame to the corresponding DSP frame is `floor(host_frame * 29761.89453125 / 44100)`. There is no resampling, automatic lag search, or implied one-to-one frame correspondence. Reports identify the first unequal sample, mismatch count, maximum absolute difference, and stereo RMS difference.

Factory checks are emitted for 256, 4,096, and 32,768 DSP frames only when both gated traces contain that many samples. Synthetic tests cover these behaviors but are not factory measurements.

## Use

```sh
python3 tools/hall_replay_verify.py /private/runA.json /private/runB.json \
  --left-wav /private/runA.wav --right-wav /private/runB.wav \
  --output /private/hall-comparison.json
python3 -m unittest discover -s tests -p 'test_hall_replay_verify.py' -v
```

All private inputs and reports must remain outside this checkout. `dsp_serial_samples` contains stereo integer observations indexed contiguously from frame zero. Host WAV inputs must be stereo PCM at 44.1 kHz. A clock rate mismatch or replay gate mismatch prevents a comparison.

## Available-reference status

No factory audio result is claimed by this change. The available private HALL load-boundary material records redacted hashes and serial lane-state hashes/checkpoints; it does not provide an adequate pair of full numeric native DSP serial sample streams and corresponding host WAV references under the same verified replay gates. Therefore no 256/4,096/32,768-frame factory comparison or earliest factory divergence can be reported. The earliest confirmed divergence from the current work is synthetic only and is exercised by regression tests.
