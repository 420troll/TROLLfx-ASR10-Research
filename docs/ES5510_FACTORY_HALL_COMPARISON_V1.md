# Factory HALL comparison V1

## Result

This branch adds a read-only, evidence-gated interface for comparing standalone ES5510 serial output with the OS 3.53 HALL reference. It does not modify the standalone replay engine, register initialization, DSP arithmetic, or the existing state gate. Private firmware, captures, sample values, WAVs, and replay state remain outside Git.

The existing OS reference pair was reused; no new factory audio was captured. The private independent verifier was rerun against both fresh boots:

| Domain | Coverage | Result |
| --- | ---: | --- |
| Native DSP serial | 256 frames | exact, 0 differing frames, max/RMS error 0 |
| Native DSP serial | 4096 frames | exact, 0 differing frames, max/RMS error 0 |
| Native DSP serial | 32768 frames | exact, 0 differing frames, max/RMS error 0 |
| Full host WAV | 1,257,935 frames at 44.1 kHz | exact, 0 differing frames, max/RMS error 0 |
| Mapped HALL host windows | 379 / 6069 / 48554 frames | exact, 0 differing frames, max/RMS error 0 |

These are OS boot A versus OS boot B repeatability results, not standalone-versus-OS results. The sample-exact standalone comparison is **not eligible** with the available replay evidence.

## Replay readiness and earliest blocker

The Replay V2 guarded runner (`79b25b8`) was run read-only against the available private manifest and ordered load log. It exits before building or running either engine:

```text
state gate failed before audio comparison: ordered commits disagree with final payloads at 0 GPRs and 6 SPRs
```

No register values were patched. Replay V2 incorporates the validated prior-history GPR reconstruction, resolving all 16 GPR differences. The halted HALL transaction still has 342 GPR/SPR commits and 89 instruction commits, while the selected checkpoint is the RUN snapshot before the first instruction. Six SPR differences remain (SER2R/L, MACH, DIL/readback, DBASE, and CCR); the startup SIGREG write is accounted for. The earliest causal timing uncertainty is the SER2 input-latch/snapshot edge at frame 855973. The comparison blocker is an evidence-backed standalone initial state that passes the unchanged gate, including the remaining live SPR state plus DRAM and reset pipeline state at the selected boundary.

An older private replay directory contains a 90,000-frame engine CSV and a summary claiming native/MAME agreement but 179,996 mismatching samples per engine against its OS stream, beginning at frame 855973 on SER1L. That output is excluded: its event/input package does not match the current 32,768-frame reference package, and the Replay V2 guarded command refuses the associated state at 0 GPRs / 6 SPRs before engine execution. Those numbers are historical artifact metadata, not an accepted factory comparison or a confirmed first HALL divergence.

No `research/es5510-hall-spr-replay-v3` or Replay V4 branch was available from the configured remote during this work. The adapter therefore defines a stable handoff contract and also supports the existing native/MAME engine-comparison CSV format; it does not assume a V4 private output schema.

## Strict adapter and evidence contract

`tools/audio_validation/factory_hall_compare.py` accepts:

- An OS reference trace (`reference-256/4096/32768.json`) and its matching `capture-metadata.json`.
- A native or MAME candidate JSON using `factory_hall_candidate.schema.json`, including its exact numeric input samples, or the read-only `engine-comparison.csv` produced by the existing replay harness (`--candidate-format engine-csv`) plus its private `replay_io.csv` via `--candidate-input`. The CSV adapter extracts SER1 L/R from the selected `native` or `mame` columns and SER2 L/R from `in_ser2l/r` in the input CSV.
- A candidate evidence sidecar described by `factory_hall_evidence.schema.json`.

For each window, the candidate must prove the same signed PCM16 input samples/hash, active program and GPR/SPR/DRAM state, memory configuration, HALT pipeline-reset acknowledgement and cleared ALU/MAC/RAM/DOL pipeline indicators, ordered halted firmware events, per-window host I/O event history, DSP and host clocks, serial routing, and RUN/snapshot/first-instruction coordinates. The event sidecar is checked against `--candidate-events`, an ordered private trace containing `ESPPHASE`, `ESPHOST`, and `ESPIO` records; the adapter recomputes the pre-RUN and window-bounded event hashes and counts. The OS adapter independently checks its input sample hash, RUN snapshot digest, firmware-load digest, observed rate, frame counts, pipeline-reset log fields, and mapped host window. A missing or unequal field suppresses every DSP sample comparison. Samples must carry contiguous indices and absolute ESP frame numbers. There is no shifting, normalization, resampling, or correlation alignment.

At a confirmed first difference, the report includes the absolute frame, channel-specific mismatch counts/max/RMS errors, and optional per-frame instruction/register context supplied by the candidate trace. Missing context remains null; it is never inferred. The host WAV path is a separate comparison and requires a candidate source-time map whose measured digest and frame count match the selected OS HALL window.

### Reproducible checks

Run the OS-pair verification for each stored DSP window, keeping outputs private:

```sh
python3 tools/audio_validation/hall_replay_verify.py \
  /private/hall-reference/boot-a/reference-256.json \
  /private/hall-reference/boot-b/reference-256.json \
  --output /private/results/os-repeatability-256.json
```

Run the verifier on each exact window, including the mapped host window, then compare the full 44.1 kHz WAV separately:

```sh
for n in 256 4096 32768; do
  python3 tools/audio_validation/hall_replay_verify.py \
    "/private/hall-reference/boot-a/reference-${n}.json" \
    "/private/hall-reference/boot-b/reference-${n}.json" \
    --left-wav "/private/hall-reference/boot-a/host-window-${n}.wav" \
    --right-wav "/private/hall-reference/boot-b/host-window-${n}.wav" \
    --output "/private/results/os-repeatability-${n}.json"
done
python3 tools/audio_validation/hall_replay_verify.py \
  /private/hall-reference/boot-a/reference-32768.json \
  /private/hall-reference/boot-b/reference-32768.json \
  --left-wav /private/hall-reference/boot-a/render.wav \
  --right-wav /private/hall-reference/boot-b/render.wav \
  --output /private/results/os-full-wav-repeatability.json
```

Once a standalone dataset passes the existing replay state gate and has been emitted in the candidate contract, compare each window independently. Use the matching OS `reference-N.json` and `host-window-N.wav` for that size:

```sh
python3 tools/audio_validation/factory_hall_compare.py \
  --os-trace /private/hall-reference/boot-a/reference-32768.json \
  --os-metadata /private/hall-reference/boot-a/capture-metadata.json \
  --candidate /private/replay/native-32768.json \
  --candidate-evidence /private/replay/native-evidence-32768.json \
  --candidate-events /private/replay/native-events.log \
  --engine native \
  --output /private/results/native-vs-os-32768.json
```

For the legacy engine CSV, replace the candidate with its CSV path and add `--candidate-format engine-csv`. MAME uses `--engine mame`. Use the matching candidate trace and event log length for each OS reference window. For a separate host-window comparison, supply `--os-wav`, `--candidate-wav`, and `--candidate-host-map`; the evidence sidecar must contain the digest of that map's ordered `(host_frame_index, source_dsp_frame_position, emission_dsp_frame)` rows and its mapped host frame count. A WAV without a verified source map is refused.

With the legacy CSV adapter, also supply `--candidate-input /private/replay/replay_io.csv`. Input bytes are recomputed as signed PCM16 little-endian SER2 stereo and must hash to the candidate evidence sidecar's `input_sha256`.

## Validation

Synthetic regression tests cover exact first-256/4096/32768 comparison behavior, missing pipeline evidence refusal, mismatched input and state refusal, exact absolute first-divergence and channel metrics/context, native/MAME engine CSV adapters, OS evidence ingestion, and the distinction between clock domains. These tests do not substitute for a factory replay comparison.

Run all tests with:

```sh
python3 -m unittest discover -s tests -v
```

The required next input is a candidate replay that passes the unchanged initialization gate and provides the full per-window firmware event and numerical output evidence. Until then there is no eligible standalone-versus-OS first-divergence frame to report.
