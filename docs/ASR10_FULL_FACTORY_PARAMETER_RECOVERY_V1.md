# ASR-10 Factory Parameter Recovery V1

## Status

This increment creates a resumable parameter registry and full-range OS probe. It does **not** complete all 50 effects. The catalog preserves the original 594 manual-derived control entries and 1,040 V4 LCD field associations. It merges prior V2/V3/V5 register evidence into a consumer-facing registry with exact supported points only.

Current coverage:

- 50 factory slots and 594 documented parameter entries retained.
- 49 effects have completed V4 OS editor inventory; slot 02 remains deferred as previously requested.
- 1,040 live LCD field observations and 491 exact/alias matches against the manual catalog. The 94 unmatched manual entries remain review items.
- 33 unique controls have prior register mappings (66 exact display points in the merged V2/V3/V5 evidence). These are point maps, not full curves.
- 0 controls have a newly established full DSP value curve in this increment.
- Five controls have complete OS UI endpoint sweeps: HALL REVERB and ROOM REVERB DECAY TIME (0–99); CHORUS+REVERB CHORUS FEEDBACK (−99…+99); FLANGER+REV FLANGE DEPTH (0–99); and DUAL DELAYS BUS1 FEEDBACK (0–99). Each sweep returned exactly to its OS-loaded value. Their DSP tables remain unresolved because identical LCD values did not yield matching GPR state in both directions.

The “normalized” values in the registry are for mapping a GUI control to the documented display domain only. They do not imply linear DSP coefficients. A control is runtime-ready only for the exact `supported_values` array.

## Machine-readable handoff

- [ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json](ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json) includes all slots, controls, documented domains, observed labels/values, known exact GPR points, UI-range confidence, DSP mapping confidence, and normalized UI-domain formula where numeric bounds are documented.
- [ASR10_FACTORY_PARAMETER_RANGE_RECOVERY_V1.json](ASR10_FACTORY_PARAMETER_RANGE_RECOVERY_V1.json) records completed range sweeps separately from DSP mappings.
- The runtime’s stable parameter IDs and existing V2/V3/V5 maps are unchanged. The registry does not invent missing values or interpolate between known points.

## OS endpoint sweeps and DSP mapping stability

HALL REVERB, variation 1, DECAY TIME was selected using the V4 page ordinal and live OS panel editor. ROOM REVERB variation 1 was swept with the same procedure and independently confirmed the same endpoints. HALL recorded 198 one-step LCD changes across 40→99→40→0→40; ROOM recorded 198 across 64→99→64→0→64; CHORUS FEEDBACK recorded 396 across +9→+99→+9→−99→+9; FLANGE DEPTH scanned down from its loaded maximum 99 to 0 and restored 99; DUAL DELAYS BUS1 FEEDBACK scanned 19→99→19→0→19. All five ranges matched their documented bounds and restored the exact OS-loaded values.

For each LCD transition, the probe retains the exact before/after 22-character LCD, frame/cycle coordinates, ordered host GPR events, and a register snapshot. A 0.75-second quiet window is used after each changed LCD before closing the event window. Raw logs and expanded trace data stay outside Git.

The register evidence is not yet a safe full-value mapping. For several LCD values, the same GPRs held different values depending on sweep direction. Across 98 bidirectional value pairs, HALL DECAY’s GPR 0x03/0x04/0x05 agreed in 84 pairs (85.7%); GPR 0x5B and 0x6E agreed in 70 pairs (71.4%). For example, display 40 produced 0x340000/0x080034/0x340000/0xCC0000/0x6ADFFF after a decrement from 41, but 0x330000/0x080033/0x330000/0xCD0000/0x6BADFF after incrementing from 39. The exact reason is unresolved. The sweep therefore remains an investigation, not a curve accepted by the runtime.

The FLANGER+REV sweep started at its upper endpoint; the controller now accepts that boundary without stepping away from the initial value, then scans downward and restores 99. Its GPR 0x88 state agreed in both directions at 70/98 (71.4%) repeated values. DUAL DELAYS BUS1 FEEDBACK restored 19 after scanning 0–99; the emulator omits one step-completion line at the return-to-baseline phase boundary. The parser joins it only using the explicit baseline-restored marker and matching subsequent LCD transition. GPR 0x06 agreed at 70/97 (72.2%) comparable values. These are UI-range observations, not accepted DSP curves.

The existing direct, repeated 40/41 mapping remains preserved. A separate native-runtime audio comparison used the validated HALL checkpoint and 48 kHz WAV backend: moving from the checkpoint’s 40 to 41 scheduled five exact GPR writes and produced difference RMS 0.000403280 left / 0.000432715 right, peak difference 0.00195312 over 144,000 frames. Thus the accepted adjacent change is audible under this stimulus; that does not validate other display values.

## Coverage matrix

“Observed” means V4 saw live labels/values in OS 3.53, not that every range endpoint was traversed. “Mapped” counts controls with exact prior register points, not controls with complete original ranges. The full per-control unknowns are in the machine-readable registry.

| Slot | Factory effect | Manual entries | V4 OS inventory | OS endpoint sweeps | Exact mapped controls |
|---:|---|---:|---|---:|---:|
| 01 | HALL REVERB | 9 | observed | 1 | 7 |
| 02 | 44KHZ REVERB | 9 | deferred | 0 | 0 |
| 03 | ROOM REVERB | 9 | observed | 1 | 8 |
| 04 | DUAL DELAYS | 4 | observed | 1 | 0 |
| 05 | 44KHZ DELAYS | 4 | observed | 0 | 0 |
| 06 | CHORUS+REVRB | 8 | observed | 1 | 3 |
| 07 | PHASER+REVRB | 8 | observed | 0 | 1 |
| 08 | FLANGER+REV | 8 | observed | 1 | 4 |
| 09 | ROT.SPKR+REV | 10 | observed | 0 | 0 |
| 10 | CHOR+REV+DDL | 4 | observed | 0 | 0 |
| 11 | CMP+DIST+REV | 7 | observed | 0 | 0 |
| 12 | DIST+CHO+REV | 8 | observed | 0 | 0 |
| 13 | WAH+DIST+REV | 4 | observed | 0 | 0 |
| 14 | SMALL ROOM | 21 | observed | 0 | 0 |
| 15 | LARGE ROOM | 21 | observed | 0 | 0 |
| 16 | HALL REVERB2 | 21 | observed | 0 | 0 |
| 17 | SMALL PLATE | 12 | observed | 0 | 0 |
| 18 | LARGE PLATE | 12 | observed | 0 | 0 |
| 19 | REVRSE REVRB | 11 | observed | 0 | 0 |
| 20 | REVRSE REVB2 | 10 | observed | 0 | 0 |
| 21 | GATED REVERB | 15 | observed | 0 | 0 |
| 22 | NLIN REVRB 1 | 16 | observed | 0 | 0 |
| 23 | NLIN REVRB 2 | 16 | observed | 0 | 0 |
| 24 | NLIN REVRB 3 | 16 | observed | 0 | 0 |
| 25 | MULTITAP DDL | 6 | observed | 0 | 0 |
| 26 | EQ+DELAY LFO | 16 | observed | 0 | 0 |
| 27 | VCF+DISTORT | 13 | observed | 0 | 0 |
| 28 | GUITAR AMP1 | 20 | observed | 0 | 1 |
| 29 | GUITAR AMP2 | 20 | observed | 0 | 0 |
| 30 | GUITAR AMP3 | 20 | observed | 0 | 0 |
| 31 | SPKR CABINET | 2 | observed | 0 | 0 |
| 32 | TUNABLE SPKR | 6 | observed | 0 | 0 |
| 33 | EQ+CHOR+DDL | 16 | observed | 0 | 0 |
| 34 | EQ+VIBR+DDL | 16 | observed | 0 | 0 |
| 35 | EQ+FLNGR+DDL | 19 | observed | 0 | 0 |
| 36 | EQ+TREM+DDL | 18 | observed | 0 | 0 |
| 37 | PHASER+DDL | 11 | observed | 0 | 0 |
| 38 | 8-VOICE CHOR | 8 | observed | 0 | 5 |
| 39 | PITCH SHIFT | 12 | observed | 0 | 2 |
| 40 | PITCH+DDL | 14 | observed | 0 | 0 |
| 41 | FAST PITCHSH | 9 | observed | 0 | 0 |
| 42 | EQ+CMPRESSOR | 14 | observed | 0 | 1 |
| 43 | EXPANDER | 13 | observed | 0 | 0 |
| 44 | KEYED EXPNDR | 14 | observed | 0 | 0 |
| 45 | INVRS EXPNDR | 12 | observed | 0 | 0 |
| 46 | DE-ESSER | 17 | observed | 0 | 0 |
| 47 | DUCKER | 18 | observed | 0 | 0 |
| 48 | RUMBLE FILTR | 4 | observed | 0 | 0 |
| 49 | PARAM EQ | 9 | observed | 0 | 1 |
| 50 | VAN DER POL | 4 | observed | 0 | 0 |

## Sweep tool and reproduction

`tools/parameter_controls/run_full_parameter_range_sweep.py` combines the V4 field locator with the emulator’s display-driven endpoint sweep. It logs both directions and refuses to classify a register curve as complete unless each displayed value has reversible register evidence. No firmware/control inputs, DSP arithmetic, or factory checkpoint were changed.

Using the authorized local OS 3.53 assets:

```sh
bash tools/build_research_cli.sh
python3 tools/parameter_controls/run_full_parameter_range_sweep.py \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --selector-inventory /home/gamer/research/private-results/asr10-all-50-effects/inventory.json \
  --slot 1 --variation 1 --field 'DECAY TIME' \
  --output /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/range-sweeps \
  --field-timeout 30 --max-sweep-seconds 300 --settle-seconds 0.75
```

The tool writes private `.log` and `.json` evidence to the output directory; do not point it inside the repository. The public registry is regenerated with:

```sh
python3 tools/parameter_controls/build_full_factory_parameter_registry.py
```

## Verification

Passed focused tests:

```sh
python3 tests/parameter_controls/test_full_factory_parameter_registry.py
python3 -m unittest discover -s tests/parameter_controls -p 'test_*.py' -v  # 38 passed
python3 -m unittest discover -s tests -p 'test_*.py' -v  # 76 passed
python3 -m unittest tests.parameter_controls.test_factory_editor_inventory_v04 tests.parameter_controls.test_factory_dsp_mapping_probe_v05 tests.parameter_controls.test_v05_runtime_catalog -v
tools/audio_validation/test_es5510_audio_test_backend.sh
bash tools/audio_validation/test_factory_runtime.sh
python3 tests/test_factory_package_importer.py
python3 tests/test_parameter_host_diff.py
bash tools/test_experimental_audio_host.sh
```

The emulator CLI builds with `bash tools/build_research_cli.sh`. Its build reports pre-existing `-Wmisleading-indentation` warnings in `src/asr10.cpp` and `src/m68302.cpp`; the build succeeds. `test_factory_runtime.sh` also emits the existing test-only replacement-new/delete warning and passes.

## Per-effect gaps and next steps

The registry is the authoritative per-effect status table: every one of the 594 entries has UI-range confidence and DSP-mapping confidence separately. For the 589 controls without a full endpoint sweep, manual-derived ranges remain documented-only unless the record says otherwise; V4 observations establish live names/values but not endpoints. Even a verified UI range does not make a parameter DSP-ready.

Next work should sweep the remaining priority fields in HALL, ROOM, CHORUS+REVERB, FLANGER+REVERB, and DUAL DELAYS, then refine register correlation before expanding any runtime point table. The HALL DECAY direction mismatch must first be resolved with a stable-value experiment that records the post-edit host write cadence independently of neighboring panel actions. Audio tests should cover minimum/default/maximum only after each value-to-GPR pair is reversible and repeatable.

Full access to all 50 original effects is **not yet achieved**. No Force deployment or GUI edit was made.
