# ASR-10 factory parameter recovery

## Result

This branch adds an evidence-tiered catalog for the 50 original factory slots, a repeatable OS 3.53 parameter-probe runner, and ordered multi-register parameter events in the universal runtime.

The catalog contains 594 effect/parameter entries with a printed range or the common `VAR` control (544 algorithm-specific entries plus 50 `VAR` entries), representing 206 distinct displayed labels. The manual's shared modulation controls are recorded separately. These are documentation-derived controls and ranges; the manual's ordering is not presented as verified LCD cursor order. The catalog records cross-references for inherited parameter groups rather than fabricating extra mappings.

Only four parameter IDs have live OS-to-GPR mappings: `REVERB MIX BUS1` and `REVERB MIX BUS2` in ROM-01 HALL, and the same two controls in ROM-02 44KHZ REVERB. Each has two observed display points, for eight verified points total. These four controls remain functional through the native runtime. No other factory control is currently writable through this evidence-bounded parameter API.

The standalone catalog is [ASR10_FACTORY_PARAMETER_CATALOG_V1.json](ASR10_FACTORY_PARAMETER_CATALOG_V1.json), validated by [catalog.schema.json](../tools/parameter_controls/catalog_v1.schema.json). It contains names, slot labels, documented ranges, shared control references, and the four live-mapped controls. It contains no ROM bytes, programs, checkpoints, raw traces, or local asset paths.

## Evidence levels

- **Documented:** parameter labels, ranges, units embedded in range text, reverb/delay shared groups, and shared modulation controls are transcribed from Section 6 and the modulation-control description in Section 5 of the [ASR-10 Musician's Manual](https://datassette.s3.us-west-004.backblazeb2.com/manuais/ensoniq_eq_musicians_manual.pdf).
- **Live OS verified:** the four BUS mix mappings above were observed in reversible OS 3.53 Up/Down/Up host-write captures with no-edit comparisons. ROM-01 points are display 28/29 to GPR 0x7C/0x7A values 0x3D0000/0x3F0000. ROM-02 points are display 25/26 to GPR 0x7C/0x7A values 0x350000/0x370000.
- **Native runtime functional:** those four mapped controls can be scheduled in the native runtime at exact observed points. The adapter does not recreate firmware's repeated update cadence, transient writes, or unverified companion writes.
- **Unresolved:** factory defaults, clean-reset display defaults, exhaustive LCD cursor order, exact value curves, and parameter destinations for the remaining 48 effects. The catalog does not interpolate between measured points.

`VAR` is documented as selecting one of four editable variations. Its OS display encoding and register effects have not been live traced here. Several manual entries refer to a previously described effect family; those references are included in `manual_cross_references`. A referenced family is not evidence that its every control is visible or has identical encoding in each related ROM slot.

## Repeating a controlled OS parameter probe

`tools/parameter_controls/run_os_parameter_probe.py` accepts a private recipe containing timed button/analog actions and marker windows. It runs the existing native emulator with `ESP_HOSTLOG=1`, writes the emulator trace and WAV to caller-selected paths, and produces a before/after GPR summary. It does not assume how a particular OS menu is opened: the researcher supplies the known, tested action schedule for effect selection, Edit/Effects navigation, parameter selection, and reversible changes.

Minimal recipe shape:

```json
{
  "id": "private-rom01-bus1-up-down-up",
  "seconds": 35,
  "actions": [
    {"seconds": 26.0, "type": "mark", "label": "before_up"},
    {"seconds": 26.2, "type": "button", "code": 10, "down": 1},
    {"seconds": 26.4, "type": "button", "code": 10, "down": 0},
    {"seconds": 27.0, "type": "mark", "label": "after_up"}
  ],
  "windows": [
    {"action": "up", "before": "before_up", "after": "after_up"}
  ]
}
```

Run it with paths in the private results tree:

```sh
python3 tools/parameter_controls/run_os_parameter_probe.py \
  --recipe /home/gamer/research/private-results/parameter-probes/rom01-bus1.json \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --wav /home/gamer/research/private-results/parameter-probes/rom01-bus1.wav \
  --host-log /home/gamer/research/private-results/parameter-probes/rom01-bus1.log \
  --report /home/gamer/research/private-results/parameter-probes/rom01-bus1-report.json
```

For a report that contains raw 24-bit register values, add `--include-values` and keep the report private. Recipes should include a matched no-edit control run, before/after markers around settled edits, Down reversal, and a repeated Up. Host-write differences alone do not prove that a register belongs to the edited control; screen values and effect selection identity must also be checked from the capture. Periodic firmware writes remain unassigned unless a controlled comparison proves otherwise.

The analyzer in `tools/parameter_host_diff.py` continues to provide a redacted-by-default marker-window report. The runner and its recipe validator are covered by synthetic tests; this branch did not launch another broad emulator sweep.

## Runtime/API change

`ParameterPoint` now accepts `ordered_writes`, a bounded ordered list of GPR writes associated with one verified display point. `FactoryRuntime::setParameter()` validates the complete list and available queue capacity before scheduling any write. The writes receive the same DSP frame and stable insertion order. If capacity is insufficient, the group is rejected without partially consuming queue capacity. Existing single-GPR verified points retain their behavior.

`VerifiedParameterDefinition` can carry display order, units, documented numeric bounds, and a string describing the evidence for those bounds. These fields are UI metadata only: `setParameter()` still accepts only explicitly verified display points. A manual range therefore cannot accidentally enable extrapolated runtime values.

This is the integration interface for the Force UI. It can display manual-derived metadata with an explicit documented/unverified badge, but must show controls as disabled until a live verified point mapping is attached to the package descriptor. The Force VST wrapper and SDK files were not changed.

## Tests

Focused tests:

```sh
python3 -m unittest tests/parameter_controls/test_catalog_v1.py \
  tests/parameter_controls/test_os_probe.py tests/test_parameter_host_diff.py
bash tools/audio_validation/test_factory_runtime.sh
```

They validate 50 catalog slots, the known names for the first three slots, evidence-tier separation, probe recipe scheduling, trace analysis, runtime single and grouped parameter events, bounded queue failure, and no partial group insertion. The existing v0.1 catalog and parameter-adapter tests remain in place.

## Status

| Measure | Result |
|---|---:|
| Factory slots cataloged | 50 |
| Manual-derived effect/control entries | 594 |
| Distinct display labels in those entries | 206 |
| Additional common modulation controls documented | 8 |
| Parameters with reversible live OS-to-GPR evidence | 4 |
| Verified display-to-GPR points | 8 |
| Parameters functional in the native runtime | 4 |
| Parameters with proven general conversion curves | 0 |
| Multi-register factory parameter mappings proven | 0 |

The runtime supports ordered multi-register groups, but no factory multi-register control has been claimed without live evidence. The next high-value work is to run controlled traces for representative reverb, delay, modulation, dynamics, pitch, and EQ controls, then attach only verified mappings to descriptors.
