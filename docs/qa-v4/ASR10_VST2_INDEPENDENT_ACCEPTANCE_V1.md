# Independent VST2 acceptance and parameter evidence audit, V1

Baseline: QA branch `6115232`. Runtime reference: Codex 1 `1984744`.
Codex 2 AUDIO LAB revision inspected: `6a9317f`. That revision publishes the
simulator/AUDIO LAB work, not a new native FX Collection VST2 integration
candidate. No future candidate source or binary was available for callback
acceptance during this audit.

## VST2 acceptance contract

[`ASR10_VST2_ACCEPTANCE_CONTRACT_V1.json`](ASR10_VST2_ACCEPTANCE_CONTRACT_V1.json)
defines the callback sequence and gating rules. The test binary must load the
actual candidate shared object through `VSTPluginMain`, initialize it using
the VST2 dispatcher, call `AEffect.setParameter` and `processReplacing`, and
exercise `effGetChunk`/`effSetChunk`, mains-off/on, and close. Direct calls to
`FactoryRuntime` do not satisfy the VST gate.

The existing independent callback harness is
[`tests/force_vst_binary_audio_test.cpp`](../../tests/force_vst_binary_audio_test.cpp),
launched by `force_plugin/tools/test_packaged_vst.py`. It now includes
pre-startup parameter writes, multiple queued values, a switch across a
pending initialization, restart after edit, non-finite parameter checks and
non-finite audio checks, in addition to binary loading, effect selection,
callback audio, state chunks, missing-package silence and allocation checks.
The modified harness compiles against the installed SDK headers. It has not
been run against Codex 2's new candidate because that candidate is not
published. Thus these cases are **implemented, not passed**.

The existing harness does not expose candidate DSP registers. A parameter
getter or visible display value is not register proof. The candidate must
provide or produce an independently verifiable trace that binds the selected
effect, active program and package/checkpoint hashes, completed package-specific
startup schedule and hash, serial routing, edit application frame, ordered register writes
and active register snapshot. Missing any one blocks parameter acceptance.
Startup event counts are package-specific: the HALL package must apply its
213-event schedule; the complete 50-slot collection contains distinct
per-effect schedule lengths (116–583 in the inspected package index), each
validated against its own manifest and schedule hash. A universal 213-event
requirement would be incorrect for non-HALL effects.

## Audio artifact comparison

The future artifact pair contract is
[`ASR10_VST2_AUDIO_PAIR_V1.schema.json`](ASR10_VST2_AUDIO_PAIR_V1.schema.json).
Each A/B comparison supplies original/native reference WAVs and actual VST2
candidate WAVs, with the same input hash for A/B and matching effect, display
value and raw-code identity for corresponding reference/candidate renders.
It requires the startup, clock, checkpoint/program/schedule, routing, host
parameter, register and binary-source evidence listed in the schema.

Run the comparator with:

```sh
python3 tools/force_gui_qa/compare_vst2_audio.py /path/to/pairs.json --output /path/to/report.json
```

The comparator keeps internal DSP processing rate separate from the WAV host
sample rate. It does not resample just because those two metadata values
differ. It measures stereo RMS/peak, uncentered L/R correlation, 100 ms
tail envelopes, A-minus-B RMS/peak, and candidate-to-reference differences.
It reports parameter application frames, firmware event counts and active
register snapshots. It does not apply gain normalization, infer alignment from
waveforms, or impose an unsubstantiated numeric tolerance. WAV frame zero must
be declared; only recorded fixed latency is removed. Different rates are
rejected by default. `--allow-rate-conversion` enables explicit polyphase
conversion (SciPy required), recorded through the manifest processing rate.
Any loss of length is visible in the measured overlap frame count. Exact
bitwise identity is not required, but a future release needs a separately
approved tolerance based on host conversion and measured latency.

The prior HALL measurement source remains
[`ASR10_HALL_EXTREME_RANGE_AUDIO_QA_V1.json`](ASR10_HALL_EXTREME_RANGE_AUDIO_QA_V1.json)
and its AUDIO LAB package remains
[`ASR10_HALL_AUDIO_LAB_EXPORT_V1.json`](ASR10_HALL_AUDIO_LAB_EXPORT_V1.json).
It preserves HALL 10/90, 0/99, 25/75, 40/41 and raw 51/52 cases at the factory
reference and 48 kHz rates for impulse and noise. Selected raw representations
are explicit: display 10→13, 90→115, 0→0, 99→127, 25→32, 75→96, 40→51 and
41→53. Extra render records include raw 116 (also display 90), raw 52 (also
display 40), and same-state/repeat renders. These are standalone runtime
renders; they are not actual VST output and cannot pass the VST2 audio gate.

## Parameter evidence mismatch inventory

[`ASR10_PARAMETER_EVIDENCE_MISMATCH_INVENTORY_V1.json`](ASR10_PARAMETER_EVIDENCE_MISMATCH_INVENTORY_V1.json)
contains the 94 manual rows with no linked OS field and all 500 OS field
associations not directly linked to a catalog row. It also lists the 9
additional descriptors in the deferred ROM-02 OS inventory separately. It
preserves the 594 descriptor / 1,040 field association / 5,484 observation
distinction. Categories are conservative: among the 94 manual rows, 6 have
explicit composite-heading evidence, 20 fall under published naming or
algorithm-range normalization, and 68 remain unresolved. The 500 unlinked OS
associations include modulation labels, cursor-selected composite fields and
unresolved fields. A normalized exact label is only an exact-label candidate;
the inventory never converts it into semantic control identity. Raw OS
inventory, captures, firmware, ROMs, and private state remain outside Git.

The top ten research queue is a deterministic evidence-density heuristic, not
a DSP-importance ranking. It prioritizes cursor-selected fields with rich OS
observations, led by the nonlinear reverb `ENV LEV` fields and `ER LEV` /
`POSITN BAL` composites. The current ranked queue is:

1. NLIN REVRB 1 — `ENV LEV`
2. NLIN REVRB 2 — `ENV LEV`
3. NLIN REVRB 3 — `ENV LEV`
4. SMALL PLATE — `ER LEV`
5. LARGE PLATE — `ER LEV`
6. GATED REVERB — `ER LEV`
7. SMALL ROOM — `POSITN BAL`
8. LARGE ROOM — `POSITN BAL`
9. HALL REVERB2 — `POSITN BAL`
10. HALL REVERB — `BUS1 MIXMOD`

This preserves the existing nine manual envelope
levels versus five observed selected values as unresolved; it does not infer
that a field absent from the supplied inventory is absent from the original OS.

## Baseline binary results

The QA baseline source was staged outside Git and rebuilt with SDK Zig 0.17.1.
SDK validation reported zero errors and zero warnings. The exact native and
ARM32 binary hashes, source/SDK revisions, 50/50 slot result, callback test
results and simulator report hash are in
[`ASR10_VST2_BASELINE_CALLBACK_RESULTS_V1.json`](ASR10_VST2_BASELINE_CALLBACK_RESULTS_V1.json).
The native x86-64 VST2 loaded via `VSTPluginMain`; all 50 local validated
factory slots produced finite, non-silent stereo output. Pending-startup
switching, restart after edit and state chunk value restoration passed before
the fail-fast robustness probes.

The independent harness then failed on a NaN passed to VST2 `setParameter`:
the plugin returned a non-finite parameter value. A separate callback test
sent NaN on the left input and got non-finite output. These are confirmed
robustness failures on the QA baseline binary, not hypothetical release risks.
Positive/negative infinity parameter cases were not reached after the NaN
assertion. The SDK host simulator passed 20 standard checks, but its sweep used
finite values and therefore missed both defects. A desktop CPU timing result
from that simulator is not a Force real-time measurement.

The HALL native reference WAV hashes were independently rechecked: 44 original
float WAVs, 44 PCM32 copies and four private AUDIO LAB bundles all match their
public manifests. The comparison WAVs are standalone reference renders; the
baseline VST test did not produce comparable A/B HALL WAV artifacts.

## Release status

[`ASR10_VST2_INDEPENDENT_RELEASE_GATES_V1.json`](ASR10_VST2_INDEPENDENT_RELEASE_GATES_V1.json)
is the machine-readable status matrix:

| Gate | Status | Evidence boundary |
|---|---|---|
| Original-OS register equivalence | PASS | Existing HALL OS/register evidence for the audited mappings only |
| Standalone native audio | PASS | Existing full-range HALL standalone renders and comparisons |
| Native desktop VST2 audio | BLOCKED | No new candidate binary/source commit was available; older VST wrapper's 40/41 identity issue remains unresolved |
| Full-range HALL control | BLOCKED | Current plugin source has no HALL DECAY full-range VST parameter; BUS selectors are not a substitute |
| ARMv7 binary build | NOT TESTED | No candidate binary bound to the integration commit |
| Physical Akai Force operation | NOT TESTED | Not inferred from simulator or previous releases |
| Exact original-hardware audio equivalence | NOT TESTED | No candidate-bound same-state VST/OS audio comparison |

At the inspected source baseline, the plugin exposes 12 host parameters:
effect selection, wet/dry, input/output gain, bypass, status, two legacy hidden
selectors, HALL BUS1/BUS2, and ROM-02 BUS1/BUS2. It does not expose HALL DECAY
TIME; the VST full-range control is therefore blocked independently of the
runtime's standalone support.

## Candidate run command

After Codex 2 publishes a fresh native candidate, use the SDK's native binary,
the ARM32 binary from the same source build, trusted private package collection
and SDK host simulator:

```sh
python3 force_plugin/tools/test_packaged_vst.py \
  --native-plugin /path/to/candidate/native/asr10-fx-collection.so \
  --arm32-plugin /path/to/candidate/arm32/asr10-fx-collection-arm32.so \
  --sdk "$AKAI_FORCE_SDK" \
  --collection "$TROLLFX_FACTORY_PACKAGE_COLLECTION" \
  --host-sim "$AKAI_FORCE_SDK/.sdk-tools/host_sim" \
  --report /tmp/asr10-vst2-acceptance.json
```

Keep the package collection and rendered WAV artifacts private. Do not mark a
candidate playable on this command alone: require the independent parameter
register evidence, artifact comparator, ARM ABI/release gates and physical
Force tests separately.
