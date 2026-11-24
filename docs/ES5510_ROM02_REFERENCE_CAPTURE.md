# ES5510 ROM-02 reference capture

## Result

This branch prepares a ROM-02 evidence gate, but does **not** contain two ROM-02
reference datasets. An authentic capture could not be performed in this checkout:
the OS ROM pair and `os353.img` are absent (`roms/README.txt` documents their
private placement), and no private ROM/EFE payload, ESP snapshot, numeric trace,
session log, or WAV was present in the workspace. The report therefore makes no
claim about repeatability, ROM-02 audio, or standalone engine accuracy.

The recorded workspace search found no `*.img`, `*.bin`, `*.esp`, `*.wav`, or
session log available for either boot. Consequently there are no run hashes,
sample counts, first-difference frame, measured ROM-02 clock, or host WAV
coverage to report. No placeholder or synthetic dataset is presented as OS
output.

## ROM-02 facts and unresolved capture coordinates

The independent EFE reconstruction documents the factory identity as
`ROM-02 44KHZ REVERB`, with 60 active instructions through END word 59, 58
paired GPR/instruction records, one instruction-only record, and one alias.
Those are source/load facts; they do not identify the numeric RUN frame, serial
input/output lane selection, selected-boundary DRAM contents, reset pipeline
values, serial clock, or the OS processing clock. The HALL values (89 words,
frame 855973, SER2 input/SER1 output, and 29,761.89453125 Hz) are not used as
ROM-02 defaults.

Two independent OS 3.53 boots still need to establish all of the following from
their own raw logs and snapshots:

- ROM-02 identity and its 60-word program digest at the selected RUN boundary.
- Exact selected RUN frame, snapshot-before-first-instruction ordering, and
  contiguous eight-lane DSP serial frames.
- Actual input and output serial lane routing and the measured ES5510 rate.
- Initial program, GPR/SPR, memory configuration, DRAM, and acknowledged
  pipeline reset state.
- Ordered pre-RUN firmware events and execution events over each requested
  window.
- Deterministic stimulus generator, seed/settings, captured input hash, and
  host source-time map.

The two-run gate must compare these fields before numerical output. It must
compare sample index `i` directly with `i`, report the first unequal absolute
DSP frame, and preserve the host WAV at its own measured sample rate. No
correlation shift, normalization, or resampling is part of the gate.

## Standalone comparison contract

`tools/audio_validation/factory_hall_compare.py` now accepts the factory
reference schema alongside the established HALL schema. It derives the DSP
rate from measured metadata and requires the candidate rate to match; it no
longer imposes the HALL rate on a factory effect. Both reference and candidate
must carry effect ID/name. Candidate JSON must identify its samples as
`es5510_serial`, and its input samples, frame alignment, program/register/DRAM
state hashes, reset pipeline, firmware-event digests, clock, routing, and
boundary evidence are gated before output is compared. Host PCM WAV is checked
separately against its measured host rate and source-time mapping.

Candidate adapters remain `native` and `mame`. ROM-02 candidate output must use
the same effect identity and explicit serial lane/frame contract as the OS
trace. The legacy engine-CSV adapter requires an explicit output serial port;
the JSON adapter carries the selected samples directly. The generic gate does
not infer ROM-02 lanes or clock from HALL. A
successful synthetic unit test only checks comparator behavior; it is not a
factory comparison. No successful gated standalone comparison is claimed.

## Coverage and hashes

| Evidence | ROM-02 result |
|---|---|
| Independent OS boots | 0 of 2 available |
| DSP frames at 256 / 4,096 / 32,768 | not captured |
| DSP sample rate | not measured |
| Host WAV and source-time mapping | not captured |
| Program, state, input, event, and clock hashes | unavailable |
| Exact sample comparison / first difference | not run |
| Native and MAME eligibility | blocked: no qualifying OS reference package |

The commit contains no proprietary firmware, effect data, capture, or audio.
