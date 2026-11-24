# ES5510 HALL reference capture V2

This branch adds opt-in numerical traces to the original OS 3.53 emulator and a redacted capture adapter. It does not change the standalone replay engine or DSP arithmetic. Private ROMs, disk images, logs, snapshots, sample traces, WAVs, and generated reference JSON stay outside Git.

## Reproduce a private pair

Build the research CLI and run two fresh boots, writing results outside the checkout:

```sh
python3 tools/audio_validation/capture_hall_reference.py \
  --roms /path/to/private/OS353/roms \
  --disk /path/to/private/OS353/os353.img \
  --out /path/outside/checkout/hall-reference
```

The runner rejects output paths inside the checkout. It uses a 440 Hz, amplitude 0.25 test sine with phase initialized at fresh process start, and route `-1,-1,1,-1,0`. The capture begins at absolute ESP frame 855973 by default and takes 32768 contiguous frames. `--run-frame`, `--frames`, and `--seconds` allow controlled variants. Each boot is a fresh CLI process with the same stimulus and settings.

## Captured domains and alignment

The numerical DSP reference is the eight-lane serial frame trace at **29,761.89453125 Hz**. Input is SER2 L/R (lanes 4/5) and effect output is SER1 L/R (lanes 2/3). The capture preserves all eight signed PCM16 lanes, cycles, host PC, serial control, and absolute DSP frame. DSP sample zero maps to the selected absolute ESP frame; there is no correlation search or sample shifting.

Host output is captured independently at **44,100 Hz** after the emulator's TDA1541A DAC model and DacOut resampling/routing. For each host frame the trace records its emitted host index, DSP emission frame, and source-time position. Window selection uses the logged source-time coordinate in `[start_frame, start_frame + count)`; it does not shift the samples. The PCM values are checked against the CLI WAV before a bundle is accepted. The WAV and host-domain comparisons are distinct from the native DSP serial comparison.

The runner records the OTTO clock, active voice count, host rate, DAC model, serial routing and direct mask. It also stores the test sine setup and the DAC noise seed (`22222`) and weight-seed formula (`1541 + channel*977 + attempt*31`).

## Observed factory execution boundary

Coordinates below are from the private boot-A event log; boot-B is independently checked for matching state, event fingerprints, and samples. The generated private `capture-metadata.json` contains full event coordinates for both boots.

| Event | ESP frame | Host cycles |
| --- | ---: | ---: |
| PA4 HALT assert | 854142 | 420614232 |
| HALT pipeline reset acknowledgement | 854142 | 420614232 |
| DRAM clear | 854143 | 420614390 |
| HALL instruction upload begins | 855284 | 421228220 |
| PA4 RUN release | 855972 | 421550288 |
| upload summary / RUN boundary / snapshot | 855973 | 421550606 |
| first input serial frame | 855973 | 421550606 |
| first output serial frame | 855973 | 421550606 |

The upload has 89 unique instruction addresses through END word 88 and 342 halted GPR/SPR commits. The RUN-boundary snapshot includes program/register/DRAM hashes and observable runtime configuration. A HALT pipeline-reset acknowledgement is recorded before RUN. The snapshot format does not serialize all in-flight ALU, MAC, RAM-slot, and DOL state, so this evidence does not manufacture or claim complete pipeline state. The first-instruction phase event records the host execution coordinate immediately following the snapshot and is included in the machine-readable timeline.

## Reference validation and coverage

The private capture run used two fresh OS boots with the 32768-frame native trace. The bundled independent verifier compared the two boot bundles:

| Domain | Coverage | Result |
| --- | ---: | --- |
| Native DSP serial | 256 / 4096 / 32768 frames | exact; zero mismatches |
| Host HALL source-time windows | 379 / 6069 / 48554 host frames | exact; zero mismatches |
| Full 44.1 kHz WAV | 1,257,935 host frames | exact; zero mismatches |

The native windows are prefixes of the captured 32768-frame run; host windows contain the host samples whose source-time coordinates fall inside the corresponding DSP interval. This establishes repeatability of the two OS reference boots, not equality with standalone replay. The independent verifier is vendored byte-for-byte from the published `research/es5510-hall-audio-verification` implementation and is used without weakening its input/state/event/alignment checks.

No standalone replay trace satisfying those gates was available in this workstream, so there is no OS-versus-replay difference count or earliest cross-implementation divergence to report. The earliest remaining blocker is obtaining a standalone replay capture with matching numerical SER2 input, RUN-boundary state, ordered firmware events, clock domain, and absolute frame alignment. Even with those matches, complete pipeline state is not represented by the current snapshot format and must be addressed by the replay gate/evidence before declaring sample-exactness.

## Tests

Run `python3 -m unittest discover -s tests -v`. The added synthetic tests exercise eight-lane serial parsing, source-time host mapping without shifts, exact earliest-difference reporting, and equivalence of DacOut output with and without the source-coordinate observer. No private binary or audio payload is a test fixture.
