# ES5510 factory package import audit V1

## Outcome

The private selector-sweep collection contains 50 structurally complete
captures, but **zero are eligible for `ValidatedEffectPackage`**. The capture
checkpoint for each slot is later than its RUN phase, and the capture format
omits in-flight pipeline state. The generic runtime loader resets those omitted
pipeline slots; a prior reset before RUN does not prove the later checkpoint's
pipeline is reset. The importer therefore does not create a runtime descriptor
for any of these snapshots.

The independent ROM-01 HALL and ROM-02 replay assets remain untouched and are
still the known-good packages for those two programs. They are not silently
replaced with selector-sweep packages.

## Slot 02/03 discrepancy

The collection manifests match their checkpoints, and each active program
matches host instruction commits at the captured display time. Those checks
establish what was running, not that the displayed selector name uniquely
identifies its source program.

| Slot | Display | RUN frame from phase log | Captured checkpoint frame | Active image comparison | Decision |
|---:|---|---:|---:|---|---|
| 01 | HALL REVERB | 805327 | 849885 | 89-word HALL image; agrees with independent ROM-01 | Not importable: later state snapshot |
| 02 | 44KHZ REVERB | 855973 | 899137 | Same 89-word HALL image, not the independent 60-word ROM-02 image | Quarantine identity conflict |
| 03 | ROOM REVERB | 905028 | 969447 | Same 60-word image as independent ROM-02 | Quarantine identity ambiguous |

Slot 02 runs after its selector transition with the HALL image and distinct
captured register state. Slot 03 runs with the same 60-word image as the
independent ROM-02 replay, under the ROOM REVERB display label. This is
consistent with either intentional program reuse under different labels or a
selector/capture identity problem. The present traces cannot distinguish those
cases. No relabeling or reassignment is made.

All three checkpoints were captured tens of thousands of DSP frames after the
corresponding `run_start`: offsets are 44,558, 43,164, and 64,419 frames for
slots 01–03. Their `firmware-events.log` files include initialization and
post-RUN writes through the later snapshot. Those writes are already reflected
in the checkpoint state, so they are validated as historical evidence and are
not replayed from checkpoint frame zero. The importer reports a future event
schedule count of zero; it never truncates the raw history to fit the runtime's
256-entry queue. To import a true RUN-boundary package, capture the checkpoint
at the RUN/first-instruction boundary and provide only subsequent GPR writes as
the bounded schedule, or extend the runtime with a justified unbounded/event
streaming design.

## Importer and Codex 2 contract

Run the local audit without writing to the source package collection:

```sh
python3 tools/audio_validation/import_factory_effect_collection.py \
  /home/gamer/research/private-results/asr10-all-50-effects/validated-packages \
  --output /home/gamer/research/private-results/asr10-all-50-effects/universal-import-audit.json
```

The JSON is private because it contains local paths and checkpoint digests. It
has a result per slot with separate `capture_state_valid` and
`registry_eligible` fields. Codex 2 should consume only entries with
`registry_eligible: true`, map the descriptor fields to `EffectDescriptor`,
and construct `ValidatedEffectPackage` only after that receipt is verified.
The current audit emits no descriptor for the 50 later-frame snapshots. The
known-good HALL and ROM-02 package validation path remains separate.

For an eligible descriptor, mapping is direct: effect slot/name, active
program words and END index, program digest, factory reference rate, serial
mode/ports, checkpoint path/hash, verified initialization manifest path, and
the ordered future GPR schedule. `pipeline_reset_valid` describes the actual
checkpoint boundary, not a reset that happened earlier in the same emulator
run. Parameters remain empty unless independently mapped.

## Per-slot result

Slots 02 and 03 are quarantined for identity ambiguity. Slots 01 and 04–50
have internally validated captured program/register/DRAM/route/event evidence
and stable OS selector labels, but are quarantined from the runtime because
their checkpoints are post-RUN and omit the pipeline state needed to establish
a true resumable boundary. This is not a claim those effects are invalid on the
instrument; it is a refusal to assert runtime package readiness from this
capture shape.

## Verification

The importer validates hashes for the checkpoint and event file, active
program/GPR/SPR/DRAM identities, register/DRAM geometry, PC-zero running state,
serial mode, HALT/reset/clear/upload/RUN phase ordering, and monotonic host
event IDs/cycles/frames through the checkpoint. It checks known HALL and ROM-02
program identities and quarantines conflicting selector entries. Focused
synthetic tests cover identity and RUN-boundary gating; local package audit
results remain outside Git.
