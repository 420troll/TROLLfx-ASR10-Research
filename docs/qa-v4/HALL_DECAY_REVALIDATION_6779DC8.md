# Independent HALL DECAY Revalidation at 6779dc8

Date: 2026-11-26  
QA branch: `qa/asr10-v4-gui-independent`  
Runtime under test: `research/asr10-full-factory-parameter-recovery` at `6779dc8`

## Result

The previously published independent OS and runtime checks reproduced without changes to the Codex 1 runtime worktree. The raw/display transition model and final register groups are supported for ROM-01 HALL REVERB Variation 1. This does not establish original-OS audio equivalence or physical silicon behavior.

Two stored OS 3.53 emulator sweeps, recorded under distinct CLI process IDs 154605 and 154697, agree on all 200 edit events and 198 five-register transition groups. The source OS table maps 128 raw codes to all 100 LCD values, with 28 two-code buckets. Every captured Up/Down route matches the table. Direct raw-code writes are not an operation of the original panel editor and were not injected into the OS; the tested interface is authentic directional editor stepping.

The register order is `0x6E, 0x5B, 0x03, 0x04, 0x05`. All five register values and cycle/frame coordinates match between the independent sweeps. The older `102/196` coefficient comparison used an unclamped input for GPR 03/04/05. Its 94 mismatches are exactly the 16 cases with raw code below 12 and 78 cases above 76. The OS observations support clamping that coefficient path to `[12,76]`; the raw code still goes to GPR 6E and GPR 5B's low byte, and GPR 5B's upper tag is `min(8, 127 - raw)`. The corrected calculation matches all 198 groups. This is independently reconstructed from OS writes, not imported from the runtime helper.

An isolated temporary QA build of the runtime, with a read-only register accessor added only to its temporary copy, completed the 0→99→0 UI path. It visited all 128 raw codes, including both raw representations in every duplicate bucket. It matched the OS-derived display/raw state after all 198 transitions and all 990 applied parameter-register writes. Invalid direction, unknown raw state after a direct GPR 6E edit, and unsupported variations reject; reset restores the validated synthetic checkpoint seed. A synthetic checkpoint verifies control logic and register behavior only.

The legacy verified VST parameter catalog remains separate: its DECAY TIME routes still cover only display points 40 and 41. The stateful stepper is not connected to a stable VST parameter index. Do not treat a successful display transition as proof that the writes have reached the DSP: the runtime status in this source revision reports the queued target, and the independent harness verified writes only after processing the scheduled DSP frame.

## Audio and release status

The previously measured native 40→41 comparison is finite and measurably different (stereo difference RMS `0.000623683`, peak `0.0017395`). It proves an audio response for those two points under that test only. The full 0–99 domain, duplicate-path audio, and intermediate-frame transient behavior were not tested. The OS spreads the five writes across frames at offsets `0, 3, 6, 8, 11` in the captured 40→41 edit, while the runtime batches them on one frame. No intermediate audio comparison establishes that batching is transparent.

Therefore the control is **OS-transition and final-register verified**, **partially audio verified**, and **not ready for full-range production/VST promotion**. Stable VST state compatibility, ARMv7 integration, and physical Force behavior remain untested. No claim of exact factory-audio or hardware equivalence is made.

## Reproduction

From the QA worktree:

```sh
python3 tools/force_gui_qa/audit_hall_decay_trace.py \
  /home/gamer/research/private-results/asr10-v4-gui-independent/hall-decay-recheck-20261125/boot-a/slot-01-var1-decay-time-range.json \
  --compare /home/gamer/research/private-results/asr10-v4-gui-independent/hall-decay-recheck-20261125/boot-b/slot-01-var1-decay-time-range.json \
  --process-id 154605 --process-id 154697 \
  --matrix-output /tmp/HALL_DECAY_OS_TRANSITION_MATRIX_QA.json \
  --output /tmp/hall-decay-independent-audit-current.json

python3 tools/force_gui_qa/run_hall_decay_runtime_register_qa.py \
  --runtime-root /home/gamer/worktrees/asr10-hall-decay-audit-6779dc8 \
  --trace-a /home/gamer/research/private-results/asr10-v4-gui-independent/hall-decay-recheck-20261125/boot-a/slot-01-var1-decay-time-range.json \
  --trace-b /home/gamer/research/private-results/asr10-v4-gui-independent/hall-decay-recheck-20261125/boot-b/slot-01-var1-decay-time-range.json

python3 -m unittest tests.force_gui_qa.test_hall_decay_raw_domain \
  tests.force_gui_qa.test_parameter_spec_audit \
  tests.force_gui_qa.test_parameter_matrix
python3 -m unittest discover -s tests -p 'test_*.py'
bash /home/gamer/worktrees/asr10-hall-decay-audit-6779dc8/tools/audio_validation/test_factory_runtime.sh
```

Observed results: trace audit reported `PASS_DISTINCT_PROCESS_IDS_AND_IDENTICAL_FULL_TRANSITION_TRACES`; temporary runtime harness printed `198 LCD steps, 99 each direction, PASS`; focused Python tests passed 16/16; complete Python discovery passed 82/82; native C++ runtime regression printed `ES5510 runtime synthetic tests: PASS`. The C++ build emits existing `-Wmismatched-new-delete` warnings from the test's custom allocation instrumentation; no test failed.

Private traces, checkpoints, firmware, ROMs, and audio remain outside Git.
