# ES5510 factory replay divergence analyzer

The independent analyzer compares normalized execution traces from the ASR-10 OS 3.53 emulator, the standalone native ES5510, and a MAME-derived ES5510. It neither reconstructs cold load nor changes firmware/DSP execution. It never infers instruction-cycle timing from a frame number.

## Trace formats and import

Canonical JSON follows [`../../tools/divergence/trace.schema.json`](../../tools/divergence/trace.schema.json), schema ID `trollfx-es5510-execution-trace-v1`. Each trace records a source identity, sample rate, clock/frame basis, alignment assumption, coverage declarations, optional initial state and manifest reference, and events. Event-specific fields are optional. `coverage.complete_event_types` is an explicit assertion that absence of those events within the captured trace window is meaningful. Missing fields and undeclared event coverage remain unknown.

The converter accepts the existing audio-validation diagnostic CSV records `I`, `RQ`, `RR`, `RW`, `W`, `END`, and `ROUTE` and emits canonical JSON. This CSV includes frame/PC/instruction boundaries and some GPR/special writes, RAM events, END, plus a serial snapshot for the first frame. It has no cycle timestamps and does not contain firmware-originated writes or full serial streams. `instruction_index` for this import is an ordinal of emitted `I` rows within the frame, not a DSP cycle count. `W` values are tagged as observed after the emitted boundary; the update may have been produced by an earlier pipelined instruction.

Codex 1 can supply canonical JSON directly or add a non-destructive adapter from its capture records. No capture implementation change is required. Preserve exact frame/cycle counters and event sequence where available; identify before/after-consumer phases only if instrumented. For a factory-state manifest, set `initialization_manifest` to a redacted metadata summary/reference and `initial_state` to explicit observed fields. Do not embed ROM, EFE, microcode, DRAM, or capture payload bytes.

```sh
python3 tools/divergence/analyzer.py import-csv /private/es5510.csv \
  --trace-id os353-rom01-runA --implementation asr10-os353 \
  --sample-rate 44100 --frame-basis 'ES5510 frame counter' \
  --output /private/runA.trace.json

python3 tools/divergence/analyzer.py compare /private/runA.trace.json /private/runB.trace.json \
  --json /private/divergence.json --markdown /private/divergence.md \
  --svg /private/timeline.svg
```

For three implementations, compare each pair separately (OS emulator ↔ native, OS emulator ↔ MAME, native ↔ MAME). Reports retain trace IDs, sample rate, frame/clock basis, and the no-auto-alignment assumption. Different sample rates/bases are reported; the tool never silently resamples or shifts traces.

## Findings and classifications

The analyzer reports the earliest confirmed mismatch with supporting entries, a frame timeline around it, all later findings, and observations that cannot be compared. A missing event is confirmed only when both traces declare that event type complete; otherwise it is potential. Values present on only one side are never counted as equal. Classifications are initialization state, missing firmware events, register-write ordering, pipeline state, RAM address/data, serial input/output alignment, arithmetic/execution, or insufficient evidence. A mismatch describes observed records; the classification does not prove a causal explanation.

Frame offsets and explicit cycle/boundary differences are reported separately. Instruction-cycle offsets require captured `cycle` values. Instruction-boundary shifts require `instruction_index` on the selected event and are not represented as cycles. Serial sample indices and repeated indices are examined when supplied; equal consecutive audio values alone are not treated as a dropped/repeated sample because silence and steady tones naturally repeat values. HALT/RESET/RUN transitions should be represented as `state_transition` events.

## Diagnostic timing hypotheses

Transforms create a new, labeled trace and never mutate the input. They are experiments for comparison only:

```json
[
  {"kind":"shift_gpr_frame","register":122,"frames":1},
  {"kind":"only_gpr_writes","registers":[122]},
  {"kind":"initial_state_only"},
  {"kind":"swap_event_order","frame":20,"first_index":1,"second_index":2},
  {"kind":"shift_event_boundary","event_index":12,"boundaries":1}
]
```

```sh
python3 tools/divergence/analyzer.py experiment /private/runA.trace.json /private/actions.json \
  --output /private/runA-hypothesis.trace.json
python3 tools/divergence/analyzer.py compare /private/runA.trace.json /private/runA-hypothesis.trace.json \
  --json /private/hypothesis-comparison.json
```

A transformed trace does not establish a fix. Any correction claim needs an independent DSP execution and paired output comparison under matching stimuli and initial state.

## Tests and limits

Synthetic regression tests cover identical traces, missing GPR/firmware writes, one-frame write displacement, same-frame order, cycle phase, RAM divergence, serial mismatch/index offsets, sample-rate differences, incomplete fields, initialization state, and instruction sequence. No factory trace or private input is included in the example report. Existing manifest schema is an initialization-state evidence contract, not an execution trace.

Current existing CSV traces only instrument a synthetic diagnostic pass/delay program, not ROM-01 HALL REVERB. The OS emulator's frame-level host-write logs are separate and should be adapted with explicit frame/order provenance; do not assign cycles where none were captured. No divergence for factory HALL REVERB is claimed until complete, same-stimulus traces are available from each implementation.
