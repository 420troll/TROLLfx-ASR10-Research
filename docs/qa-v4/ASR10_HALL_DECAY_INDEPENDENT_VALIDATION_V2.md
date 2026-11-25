# Independent HALL DECAY Reconstruction Validation

Date: 2026-11-25
QA branch: `qa/asr10-v4-gui-independent`
Codex 1 source: `research/asr10-full-factory-parameter-recovery` at `6779dc8`
Codex 2 editor: `feature/asr10-force-pc-gui-simulator` at `08cc600`

## Result

**OS parameter behavior: VERIFIED for HALL ROM-01 Variation 1 in the OS 3.53 emulator.** Two fresh full traversals ran in separate CLI/emulator processes (recorded PIDs `154605` and `154697`). The independent parser recovered all 128 raw codes, all 100 LCD values, 28 two-code display buckets, and 198 transition register groups (99 per direction, endpoints included). The run-specific JSON trace hashes differ; the underlying raw log content hash is identical, while separately recorded CLI PIDs establish two emulator processes. Their raw/display maps, GPR values, write order, cycles and DSP frames match for every transition. This is repeatability across distinct emulator processes, not a physical hardware measurement.

All 198 ordered five-register groups match an independently implemented formula inferred from OS values with zero mismatches. The group order is `0x6E, 0x5B, 0x03, 0x04, 0x05`. The redacted exact cross-run summary is in [HALL_DECAY_OS_CROSSRUN_QA_V1.json](HALL_DECAY_OS_CROSSRUN_QA_V1.json), and runtime API results are in [HALL_DECAY_INDEPENDENT_RUNTIME_QA_V2.json](HALL_DECAY_INDEPENDENT_RUNTIME_QA_V2.json). Raw source captures and the per-event transition matrix remain outside Git. No ROM, firmware, or audio is committed.

## Mapping and duplicate buckets

The raw-code/display relationship is derived from the original OS transition traces: raw codes 0–127 map onto display values 0–99. All 28 duplicate display/raw pairs are explicitly listed in the machine-readable cross-run summary. At each duplicate, the lower and upper raw code show the same display but can be retained depending on the edit path. The two full-startup captures reproduce every bucket and transition identically.

For example, display `40` corresponds to raw codes `51` and `52`; display `1` corresponds to `1` and `2`. From display 40, the upward OS step reaches raw 53 / display 41 whether its starting raw state is 51 or 52. A down step from raw 52 skips raw 51 because its LCD value is unchanged, then reaches raw 50 / display 39. This is a stateful raw transition; an LCD scalar alone is insufficient to restore the exact underlying state.

## Register arithmetic and the earlier 102/196 result

The previous 102/196 comparison tested the older helper that used `raw` directly as the quadratic coefficient. The original OS clamps only the coefficient path used by GPR 03–05: `q = clamp(raw, 12, 76)`. It still writes the unmodified raw code to GPR 6E and the low byte of GPR 5B. Rechecking the 196 interior directional cases without that clamp gives 102 matches and 94 mismatches; every mismatch has raw `<12` or `>76`. Applying the clamp yields exact GPR 03/04/05 values for all 198 captured groups, including endpoints. An earlier trace counted the 94 mismatch cases as 16 lower-range and 78 upper-range cases.

GPR 5B's tag is also not constant over the entire raw domain: the OS uses `min(8,127-raw)`. A fixed tag 8 is wrong for high raw codes. The full inferred expression was checked against every captured value. These findings independently explain the older result; expected values were generated from the OS traces and arithmetic-width behavior, not by importing Codex 1's helper/header.

The runtime header at `6779dc8` now includes the coefficient clamp and raw-dependent 5B tag. Its ordered array agrees with the captured OS register order. Source inspection confirms `stepHallDecayTime()` inserts the array in order and its frame/order queue preserves FIFO for same-frame events.

### Event timing limitation

The original OS writes the five registers on successive DSP frames, not at one shared frame. In the captured 40→41 edit the observed frames were 1,852,556; 1,852,559; 1,852,562; 1,852,564; and 1,852,567 (intervals +3, +3, +2, +3). `FactoryRuntime::stepHallDecayTime()` schedules all five writes at the caller's single target frame. Therefore final register values and order are verified, while cycle/frame-equivalent timing is **PARTIAL**. The intermediate audio state is not yet compared, and an “exact OS event replay” claim is not justified.

## Independent runtime API check

I built a temporary test-only instrumented copy of the published runtime, adding a read-only test accessor to its private ES5510 register file. No source file in Codex 1's worktree or branch was changed. The harness built expected per-raw GPR vectors from two original-OS sweeps, checked that both traces agree, and traversed the complete display path 0→99→0 (99 UI steps each way). Across both directions it visited all 128 raw codes, including both representations for every duplicate LCD bucket. After processing each group, it checked API raw/display state and GPR 6E/5B/03/04/05. **198/198 UI transitions and 990/990 parameter GPR writes matched** the OS-derived values.

Additional published runtime tests passed for invalid direction, unknown variation, direct GPR 6E modification invalidating the step state, checkpoint reset restoring the seed raw state, and all-or-none queue-capacity failure. The independent full-range harness also confirmed a Variation 2 load rejects the HALL step API. Runtime status reports a scheduled raw/display state immediately on queueing; it is not itself proof that DSP writes were applied. The instrumented check waited for processing and read the resulting register file.

Direct raw-code setting is not an original front-panel operation in the captured UI path. The standalone runtime's generic `setRegister(0x6E,...)` is a low-level escape hatch and correctly invalidates HALL step state; the following step is rejected until reset/reload re-establishes a validated raw state.

The independent runtime test uses a synthetic package and compares applied internal register state against per-raw values extracted from both OS traces. The test-only read accessor exists only in a temporary source copy; neither Codex 1's worktree nor the production API is changed. This verifies register behavior, not authentic factory audio.

## Audio and runtime promotion status

The earlier independent HALL 40→41 runtime A/B remains finite and measurably different (65,536 frames; stereo difference RMS `0.000623683`, peak `0.0017395`). This only establishes an audible change at those exact points. There is no full 0–99 OS-reference audio comparison, no independent audio test at each duplicate bucket, and no verification of intermediate-frame transients. Full factory audio equivalence remains **NOT TESTED**.

**Runtime promotion: PARTIAL / NOT READY.** OS display/raw transitions and final register groups are verified across the full domain. Exact frame scheduling and full-range audio behavior remain unresolved. The new API also has no stable host/VST parameter route in the 19-control registry. Do not expose it as a full-range native control yet.

## Manual range corrections

The exact range citations are machine-readable in [ASR10_MANUAL_RANGE_CORRECTIONS_V1.json](ASR10_MANUAL_RANGE_CORRECTIONS_V1.json): ROOM effect variants at Section 6 PDF p.107; PLATE decay and predelay variants at Section 6 PDF p.110. Codex 2's resolved runtime parameter registry at `08cc600` displays the correct ROM-15, ROM-16, ROM-18 decay domains and ROM-18 predelay domain. The serialized source PC schema still retains the small-room/small-plate template labels and domains; this is now a provenance/schema consistency correction, not a currently observed runtime range error. All four controls remain DSP-unmapped in the QA matrix.

## Reproduction

```sh
python3 tools/force_gui_qa/audit_hall_decay_trace.py \
  /home/gamer/research/private-results/asr10-v4-gui-independent/hall-decay-recheck-20261125/boot-a/slot-01-var1-decay-time-range.json \
  --compare /home/gamer/research/private-results/asr10-v4-gui-independent/hall-decay-recheck-20261125/boot-b/slot-01-var1-decay-time-range.json \
  --process-id 154605 --process-id 154697 \
  --matrix-output /tmp/HALL_DECAY_OS_TRANSITION_MATRIX_V1.json \
  --output /tmp/hall-decay-independent-audit.json
```

Runtime test command on Codex 1's published detached worktree:

```sh
tools/audio_validation/test_factory_runtime.sh
c++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Iinclude \
  tests/test_hall_decay_control.cpp -o /tmp/asr10-hall-control-test
/tmp/asr10-hall-control-test
```

The independent full-range API/register harness was a temporary instrumented build and is documented above; it does not write any source into Codex 1's worktree. Re-run the reproducible harness with `python3 tools/force_gui_qa/run_hall_decay_runtime_register_qa.py --runtime-root /home/gamer/worktrees/asr10-hall-decay-audit-6779dc8 --trace-a /home/gamer/research/private-results/asr10-v4-gui-independent/hall-decay-recheck-20261125/boot-a/slot-01-var1-decay-time-range.json --trace-b /home/gamer/research/private-results/asr10-v4-gui-independent/hall-decay-recheck-20261125/boot-b/slot-01-var1-decay-time-range.json`; it compiles an isolated temporary copy and emits only aggregate results.
