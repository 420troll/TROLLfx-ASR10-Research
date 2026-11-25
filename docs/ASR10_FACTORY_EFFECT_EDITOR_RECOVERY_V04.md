# ASR-10 Factory Effect Editor Recovery V4

## Scope and result

V4 ran the original OS 3.53 front-panel editor through the existing emulator for every factory slot except slot 02. Per the current investigation instruction, slot 02 remains deferred; this sweep does not revisit the earlier ROM-02 identity question.

The scanner selected each effect, entered EDIT/EFFECTS, and traversed four variations without incrementing individual effect controls. It recorded exact 22-character LCD snapshots and panel cursor attributes. It also kept the current factory slot, variation, page ordinal, displayed field/value pairs, selected field (when the emulator exposes a cursor marker), and the time-windowed host GPR writes as separate evidence.

**Result:** 49 of 49 nondeferred slots completed all four variation scans. The output is an OS-observed field inventory and manual comparison, not a complete value-range or DSP-mapping recovery.

## Sweep summary

| Measure | Result |
| --- | ---: |
| Factory slots in catalog | 50 |
| Slots scanned | 49 |
| Slot deferred by instruction | 02 |
| Completed variation scans | 196 |
| LCD page stops | 4,548 |
| OS-observed field associations (per effect) | 1,040 |
| Distinct observed LCD labels across the collection | 247 |
| Manual-derived entries in scanned slots | 585 |
| Manual entries matched by exact label or explicit grouping/expansion | 491 |
| Manual entries requiring label/visibility review | 94 |
| OS-only field associations | 500 |
| Register mappings newly verified in V4 | 0 |
| Audio mappings newly verified in V4 | 0 |

The machine-readable, redacted scan is [ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json](ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json). It preserves the original slot ordering and includes slot 02 with a `deferred` status. For scanned effects, each page stores the exact LCD string, variation and ordinal, cursor-attribute spans, parsed display fields and values, selected-field observations, and a summary of GPR activity between page timestamps. Manual-catalog comparison rows point to matching observed labels; the values and per-variation observations are stored once in `os_observed_fields` and page records.

Raw emulator logs and ordered GPR events are private and remain outside Git at:

`/home/gamer/research/private-results/asr10-factory-editor-recovery-v4/logs/`

The private progress JSON stores the same ordered event windows. The public machine catalog deliberately omits raw event values; it keeps the event count, affected GPR indices, write kinds, paired instruction/GPR-write count, and a flag pointing to the private raw evidence. The parser retains both standalone `gpr` writes and the GPR half of `both` instruction/GPR writes. The scan itself changes only the variation selector and navigates the editor. GPR activity around those events is retained as chronology, not attributed to a parameter mapping.

## First-nine comparison checkpoint

The first nine selector slots comprise eight scanned effects plus deferred slot 02. For the scanned eight:

| Slot | Effect | Manual entries | OS LCD fields | Manual entries observed | OS-only fields | Manual entries left for review |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 01 | HALL REVERB | 9 | 13 | 9 | 4 | none |
| 02 | 44KHZ REVERB | 9 | deferred | deferred | deferred | deferred |
| 03 | ROOM REVERB | 9 | 13 | 9 | 4 | none |
| 04 | DUAL DELAYS | 4 | 9 | 4 | 0 | none |
| 05 | 44KHZ DELAYS | 4 | 9 | 4 | 0 | none |
| 06 | CHORUS+REVRB | 8 | 16 | 7 | 8 | CHORUS AMT |
| 07 | PHASER+REVRB | 8 | 17 | 8 | 9 | none |
| 08 | FLANGER+REV | 8 | 17 | 8 | 9 | none |
| 09 | ROT.SPKR+REV | 10 | 14 | 10 | 3 | none |

These counts compare independently editable LCD fields, not just screen labels. The parser splits compound rows such as `DETUNE RATE=26 AMT=9`, `BS1 TIME L=350 R=700`, and `DIST GAIN IN=25 OUT=50` into separately displayed values. Underline spans are retained separately and associated with a field only when they overlap that value. If the emulator exposes no underline/edit-cursor attribute for a page, the inventory leaves `selected_fields` empty; page ordinal is not misrepresented as a selected control.

This comparison shows that the manual-derived parameter catalog is not the whole live editor structure. Shared mix and modulation pages, independently addressable bus controls, and additional reverb sections appear in the OS. For example, the HALL and ROOM scans include `REVERB MIX BUS1`, `REVERB MIX BUS2`, `REVERB MIX BUS3`, and `BUS1 MIXMOD`; combined reverb/modulation algorithms expose additional controls as well. Conversely, the first-nine scan did not find `CHORUS AMT` on slot 06, despite finding the other manual-listed chorus fields. That remains an explicit review item, not evidence that the parameter is absent from every OS state.

The delay catalog groups BUS1/BUS2 controls and delay time together. The live editor exposes bus-specific mix and feedback fields, plus independently focused left/right times. V4 records those OS fields as expansions of the grouped manual entries rather than reporting them as missing controls.

## Full-catalog comparison

The 94 unmatched manual entries are concentrated in controls whose catalog names include effect-variation qualifiers, abbreviations, or grouped labels. Examples include `GATE ON`, `PRIMARY SEND LEVEL`, several nonlinear reverb names, and `DIST GAIN IN and OUT`. Some apparent mismatches are spelling/abbreviation differences between manual-derived names and the OS LCD; these are not silently normalized unless the relationship is clear. They remain reviewable in the JSON under `manual_comparison`.

The most frequent OS-only labels include eight common modulation assignment fields (`MOD SRC1`, `DST1`, `MIN1`, `MAX1`, `MOD SRC2`, `DST2`, `MIN2`, `MAX2`), observed on 37 scanned effects. BUS1/BUS2 mix fields and shared reverb sections also recur. The full inventory is the evidence for comparing page structure; the totals alone do not imply that every displayed field writes ES5510 registers.

## Evidence boundaries

- **OS-observed:** LCD label, displayed value, variation, page order, and visible cursor attributes in the OS 3.53 emulator.
- **Selection evidence:** explicit underline/edit-cursor spans mapped to display-value spans. Empty spans mean the emulator did not expose a cursor marker for that snapshot; no selected field is inferred from screen order.
- **DSP chronology:** host GPR events grouped between successive page cycle timestamps. These windows can include background firmware activity. No parameter attribution is made from a window alone.
- **Factory values:** values shown for the four OS variations. These are not minimum/maximum values and do not define the complete control range.
- **Not established by this inventory:** parameter-to-register mappings, conversion curves, complete ranges/discrete options, or audio response. Those require stable before/change/reverse probes and suitable audio validation.

The inventory automation uses physical panel events and live display-state checks rather than blind sleeps. The manual describes entering Edit then Effects, moving among parameters with Left/Right, changing values with Up/Down, and using Right+Up to advance screens; V4 validates page traversal on OS 3.53 but does not assume manual page order equals live cursor order. See the [ASR-10 Instruction Manual, Effect Parameters](https://ensoniq.manymanuals.com/digital-pianos/asr-10/instruction-manual-11191/98) and [Effect Modulation](https://ensoniq.manymanuals.com/digital-pianos/asr-10/instruction-manual-11191/96). OpenASR remains a useful reference for front-panel/display regression patterns, not a source of factory parameter mappings: [OpenASR](https://github.com/peroberg/OpenASR).

## Reproduction

Build the headless research CLI:

```sh
bash tools/build_research_cli.sh
```

Run or resume the sweep, keeping logs and progress outside Git:

```sh
python3 tools/parameter_controls/run_factory_editor_inventory_v04.py \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --inventory /home/gamer/research/private-results/asr10-all-50-effects/inventory.json \
  --progress /home/gamer/research/private-results/asr10-factory-editor-recovery-v4/progress.json \
  --logs /home/gamer/research/private-results/asr10-factory-editor-recovery-v4/logs \
  --summary docs/ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json \
  --resume --timeout 90 --max-pages 64
```

To rebuild parsed evidence without booting the emulator, add `--reparse-logs` and keep `--resume` enabled. Slot 02 is excluded by the runner. Its prior package and evidence are not overwritten.

## Next work

1. Review the 94 unmatched manual entries against LCD abbreviations and effect-specific page qualifiers; keep unresolved items visible.
2. Add controlled, reversible edits for fields with an observable selected-value cursor. Separate edit-correlated writes from baseline firmware activity.
3. Sample minimum/maximum/discrete choices only where safely observable; do not derive ranges from four variation presets.
4. Validate accepted register mappings with the native runtime and appropriate audio stimuli before labeling them audio-verified or runtime-ready.
