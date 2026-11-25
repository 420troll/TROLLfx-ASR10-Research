# ASR-10 Original Parameter Engine Reconstruction — HALL DECAY V1

## Result

The one-code GPR `0x6E` difference is an original OS editor behavior, not a DSP rounding error. HALL Variation 1 stores a 7-bit raw decay code and displays it through a 128-entry lookup table with 28 duplicate adjacent display buckets. A displayed value therefore has either one raw representation or two. The editor changes the raw code by one or two, depending on the direction and whether the adjacent raw code would leave the LCD unchanged. It does not canonicalize a value that is already displayed.

The original parameter is consequently stateful at the UI-to-register boundary. A single function of LCD value alone cannot reproduce every valid OS state. The correct conversion input is the current raw code plus the requested one-step direction.

## Evidence sources and privacy

- Original OS 3.53 running in the existing emulator; complete Variation 1 display traversal, both directions, repeated on independent runs.
- New bounded CPU and RAM-write capture from `ESP_CALLER_TRACE=1`; raw logs and parsed traces remain under `/home/gamer/research/private-results/`.
- Private OS disassembly for the specific editor and RAM update instructions.
- Transformed duplicate-code list and executable model in [es5510_hall_decay_control.hpp](../include/trollfx/es5510_hall_decay_control.hpp).
- The local original manual is present at `/mnt/c/Users/Gamer/Downloads/23583406.pdf` (391 pages). This environment has no PDF text extraction utility, so the range check uses the already checked-in manual-derived catalog; this report does not claim a new PDF transcription.

No ROM, OS image, raw trace, audio capture, private table dump, or checkpoint is included in Git.

## Exact first divergence

The first display value where the paired routes diverge is `DECAY TIME=1`:

| Route to displayed 1 | Previous display | Stored raw code | GPR `0x6E` write | Cycle / DSP frame |
|---|---:|---:|---:|---:|
| ascending from minimum | 0 | `0x01` | `0x010000` | 2923171904 / 5509388 |
| descending from 2 | 2 | `0x02` | `0x020000` | 2893588916 / 5454360 |

Both LCD values are exactly `DECAY TIME=1`; the raw state byte is at OS address `A6=0x02A6ED` (`A6+0`). The display byte at `A6+3` is separately updated and can still show the preceding LCD value when the DSP write occurs. Both write groups originate at host writer PC `0xFFF97792`; the panel-action caller observed on this edit path is `0xFFF97694`.

The full Variation 1 sweep found the same one-code difference at exactly 28 interior display values:

`1, 4, 8, 12, 15, 19, 22, 26, 29, 33, 36, 40, 44, 47, 51, 54, 58, 62, 65, 69, 72, 76, 79, 83, 86, 90, 94, 97`.

All 70 other interior values match between routes. At every mismatch, the descending representation is the ascending raw code plus one. Endpoints were visited and logged, but by definition have only one legal direction.

## Original editor path

The relevant code is a small OS editor operation handler, not a DSP-side calculation:

1. The active raw parameter byte is read from `(A6)`.
2. `A0` points to the observed display lookup table (one trace has `A0=0xFFF825A9`).
3. At `F8AE98..F8AECA`, the handler compares the current and neighboring table entries. If they display the same value, it performs an extra `add.b D7,(A6)` before returning.
4. The normal RAM editor handler then executes `00DBBA: addq.b #1,(A6)` for Up or `00DB8E: subq.b #1,(A6)` for Down.
5. The coefficient service sends the resulting raw value to ES5510 host writer `0xFFF97792`.

The relevant ROM instructions are directly visible in the private OS disassembly:

```text
F8AE98: move.b  (A6), D0
F8AE9E: move.b  (A0,D0.w), D2
F8AEA2: sub.b   D7, D0
F8AEA4: cmp.b   (A0,D0.w), D2
F8AEA8: bne     $f8aeac
F8AEAA: add.b   D7, (A6)
...
F8AEBC: move.b  (A0,D0.w), D2
F8AEC0: add.w   D7, D0
F8AEC2: cmp.b   (A0,D0.w), D2
F8AEC6: bne     $f8aeca
F8AEC8: add.b   D7, (A6)
F8AECA: rts
```

For positive and negative D7, it checks the neighbor in the requested direction and skips a raw code only if the table lookup is unchanged. The event trace captures the extra raw-byte write at PC `F8AEC8`, followed by the ordinary `DBBA`/`DB8E` increment/decrement. This directly accounts for the duplicated display buckets.

### Competing explanations ruled out for the discrepancy

- **Fixed-point rounding or DSP arithmetic:** the disagreement exists before the ES5510 consumes the GPR value. The raw OS byte differs by one; the editor table and key-step path explain exactly which route selects it.
- **Background modulation or periodic writes:** the conflicting `0x6E` values are host writes in the marked one-step action windows and match the A6 raw byte changes. Unrelated events are outside those windows.
- **Incomplete snapshots:** the conclusion uses ordered host writes and RAM before/after events, not only final GPR snapshots.
- **Timing race / stale LCD:** the screen refresh may lag the internal byte, but both transitions are independently tied to stable before/after LCD captures and different raw bytes. The stale display byte is not the cause of route selection.
- **Random hidden state or initialization:** the complete bidirectional pattern recurred across independent fresh OS processes and matches the lookup table's duplicate entries. The necessary state is the current raw code itself, not an unexplained DSP history variable.
- **Variation/modulation effects:** Variation 2's incomplete sweep independently reproduces the same 28-value `0x6E` bucket pattern, but other register behavior differs; it is not used to validate the Variation 1 five-register model.

## Conversion model, ROM-01 HALL Variation 1

### Raw/display transition

Let `r` be the unsigned raw byte `0..127` stored at `(A6)`. Let the 28 values in `hall_decay_duplicate_codes` be the second raw code for a repeated lookup result. The LCD lookup is:

```text
d(r) = r - count(k <= r for k in duplicate_codes)
```

For a one-step panel action, compare `d(r)` with `d(r + direction)`. If equal, apply an extra raw step in that direction; then apply the generic editor's ordinary step. The current code in the header encodes this transition and rejects directions other than `-1` or `+1`.

This yields 100 displayed values over 128 raw codes. Every repeated display bucket has a lower raw code used when entering from below and an upper code used when entering from above. The 28 pairs are derived from the private table; only the transformed duplicate list is versioned in source.

### Ordered ES5510 write group

For Variation 1, all 198 complete captured transition snapshots (99 in each direction; each endpoint is also recorded by the sweep terminal markers) match the following raw-code model with zero register mismatches:

```text
q = clamp(r, 12, 76)
x = q << 8
GPR 6E = r << 16
GPR 5B = (min(8, 127-r) << 16) | r
GPR 03 = (x << 8) & 0xFFFFFF
GPR 04 = -GPR03 mod 2^24
GPR 05 = ASR32((signed16(x) * signed16(-x) + 0x3FFFFFFF), 7) & 0xFFFFFF
```

OS event order is `6E, 5B, 03, 04, 05`. For `r=0x34`, the observed group is `6E=340000, 5B=080034, 03=340000, 04=CC0000, 05=6ADFFF`. For `r=0x4D`, the raw path remains 0x4D in `6E` and `5B` low bits, while `03..05` use the saturated `q=0x4C`. For `r=0x7F`, the 5B upper byte is zero. These saturation/upper-byte behaviors are part of the measured conversion and are covered by the helper and tests.

The `0x6E` state discrepancy is therefore not corrected by changing DSP arithmetic. The application must preserve the raw code and perform the OS-equivalent state transition. Setting a displayed number as though it were a unique scalar loses authentic path behavior.

## Validation and limits

| Evidence layer | Status |
|---|---|
| Manual display range | 0–99 from existing manual-derived catalog; local PDF present but not independently transcribed here |
| OS LCD domain | All 100 values observed in complete Variation 1 traversal |
| Lookup explanation | Direct disassembly, table comparisons, RAM byte chronology; high confidence |
| Route state | 28 exact adjacent raw-code differences; repeated independent Variation 1 full sweeps |
| Five-register conversion | 198 complete up/down transition states match the formula; zero mismatches |
| Variation 2 | Same 28-bucket `0x6E` pattern; sweep completion gate failed at its initial endpoint and its other register group differs, so not promoted |
| Audio | Existing 40/41 native HALL comparison is finite and measurably different in stereo; full 0–99 OS-reference audio comparison not done |
| Native runtime integration | A stateful `FactoryRuntime::stepHallDecayTime(direction, frame)` API now schedules all five writes atomically, exposes raw/LCD state, and requires validated Variation 1 metadata. Synthetic runtime verifies stepping, duplicate skips, reset, and fail-closed invalidation. It is not yet wired into the stable parameter registry/PC editor, and authentic-package audio validation of this API is not complete. |

This establishes exact Variation 1 OS register behavior across the displayed range. It does not establish full-range exact audio equivalence against OS reference audio, nor does it justify applying the complete HALL write group to other HALL variations or 44 kHz effects.

## ROOM REVERB routine reuse check

After the HALL curve was decoded, one complete ROOM REVERB (factory slot 03, Variation 1) 0–99 OS sweep was run with the same bounded tracing. It completed 200 panel transitions, visited both endpoints, and restored its starting display. The same PCs were observed: table-neighbor check `F8AEC8`, generic Up `00DBBA`, and generic Down `00DB8E`. Its GPR `0x6E` route pairs differ at the same 28 LCD buckets, with the same lower/upper raw codes as HALL. This directly establishes reuse of the editor stepping path.

Across 198 complete ROOM transition snapshots, HALL's `q=clamp(raw,12,76)` quadratic calculation matched ROOM GPR `03`, `04`, and `05` with zero mismatches. ROOM's `0x6E` values matched the same raw lookup states. However, ROOM does not use HALL's GPR `0x5B` update: that register differs for 197 compared snapshots. Thus the editor lookup and three-coefficient helper are shared for the tested Variation 1 reverb cases, while the complete register group is effect-specific. This one ROOM sweep is not a complete ROOM parameter recovery, and no ROOM audio comparison was performed in this task.

## CPU tracing and reproducibility

The emulator CPU trace is opt-in and bounded (4096 instruction snapshots and 2048 RAM-write records in fixed rings). Enable only for a focused private capture:

```sh
bash tools/build_research_cli.sh
ESP_CALLER_TRACE=1 python3 tools/parameter_controls/run_full_parameter_range_sweep.py \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --selector-inventory /home/gamer/research/private-results/asr10-all-50-effects/inventory.json \
  --slot 1 --variation 1 --field 'DECAY TIME' \
  --output /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/v4-hall-decay-instruction-trace \
  --monitor-stdio
python3 tools/parameter_controls/extract_os_cpu_parameter_trace.py \
  --input /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/v4-hall-decay-instruction-trace/slot-01-var1-decay-time-range.log \
  --output /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/v4-hall-decay-instruction-trace/parsed-cpu-trace.json
python3 tools/parameter_controls/analyze_hall_decay_sweep.py \
  --input /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/v4-hall-decay-instruction-trace/slot-01-var1-decay-time-range.json \
  --output /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/v4-hall-decay-instruction-trace/aggregate.json
```

The analyzer reports only aggregates and formula mismatches, not raw events. `ESP_CALLER_TRACE` records no unrestricted host output; normal runs leave the instruction callback disabled.

## Canonical parameter contract proposal

[ASR10_FACTORY_PARAMETER_CONTRACT_V1.schema.json](ASR10_FACTORY_PARAMETER_CONTRACT_V1.schema.json) separates manual, original-OS observation, stored identity, DSP mapping, audio validation, and runtime status. [ASR10_HALL_DECAY_PARAMETER_V1.json](ASR10_HALL_DECAY_PARAMETER_V1.json) is the first example. This is a versioned proposal, not a migration: it does not alter existing VST IDs, state chunks, editor layouts, or factory package schemas. Codex 2 and Codex 3 should review the layer semantics before broad adoption.

## Next justified work

1. Validate Variation 2's complete register group from a non-endpoint baseline; its incomplete minimum-origin sweep confirms only the 6E duplicate-bucket pattern.
2. Compare full-range native impulse/noise renders against an OS-reference capture for the same state and stimulus.
3. Extend ROOM with its independently observed register group and audio checks. Reuse only the editor/03-05 portions demonstrated by this sweep.
