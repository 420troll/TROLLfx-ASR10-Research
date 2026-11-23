# EFE multi-effect capture comparison

## Evidence

Four standalone objects from the private OS 3.53 disk were selected through the
native ASR-10 CLI. Each run recorded the displayed effect filename, the complete
ES5510 host-write log, and a processor-state capture. The private object was
matched against the captured live program and its host commits. All captures,
logs, WAVs, source objects, and instruction/GPR payloads remain outside Git.

The comparison tool checks the capture's contiguous program through its first
END, verifies the host instruction commits, resolves source locations, and
checks paired source GPR values against paired host writes. It reports offsets
and counts only. Some instruction words occur more than once in an object; the
tool resolves those locations from host GPR values and record strides and fails
closed if the resulting layout is ambiguous.

## Verified layouts

Offsets are relative to the beginning of each extracted object. `Gap` is the
unclassified byte count between the paired records and instruction-only run.
The prefix and suffix lengths are measured from `FxUcode` and to `FxSize`,
respectively. Their meanings are unknown.

| Effect name | FxSize | FxUcode | Live instructions | END position | Paired records | Instruction-only records | Source-to-host match | Unknown prefix / gap / suffix | Confidence |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| 44DDL+CHORUS | 3161 | 2620 | 60 | 59 | 29 | 31 | All 60 instructions; all 29 paired GPR values | 11 / 3 / 80 bytes | High |
| 44DDL+CH+REV | 7458 | 6846 | 60 | 59 | 56 | 4 | All 60 instructions; all 56 paired GPR values | 11 / 3 / 70 bytes | High |
| 44EQ+REVERB | 6093 | 5496 | 60 | 59 | 26 | 34 | All 60 instructions; all 26 paired GPR values | 11 / 3 / 145 bytes | High |
| 44PARAM EQ | 3047 | 2554 | 60 | 59 | 0 | 60 | All 60 instructions | 11 / none / 122 bytes | High |

High confidence here means that object selection was displayed by the CLI and
the source mapping was independently checked against both the live capture and
host writes. This is emulator evidence, not a physical ASR-10 capture.

## Structural rules supported by these captures

- In the three mixed objects, each paired record is a three-byte GPR value
  immediately followed by a six-byte instruction. Consecutive paired records
  have a nine-byte stride.
- The mixed objects place a six-byte-stride instruction-only run after the
  paired run. All three observed boundaries have a three-byte gap, even though
  paired and instruction-only record counts differ substantially.
- `44PARAM EQ` has a six-byte-stride instruction-only run with no paired run.
- All four objects have an 11-byte prefix from `FxUcode` to the first live
  record and a suffix whose size varies by object. The available evidence does
  not identify the meanings of the prefix, gap, or suffix.
- Duplicate instruction words prevent a globally unique byte search from
  identifying every live source location. Host GPR values distinguish paired
  records; run order and stride resolve repeated words in instruction-only
  records. The comparator rejects ambiguous or nonconforming mappings.
- Host `both`, `instr`, and GPR-only events are treated separately. Runtime GPR
  snapshot contents are not substituted for host-written initialization
  values.

## Remaining unknowns

| Field or behavior | Evidence | Confidence in interpretation |
|---|---|---|
| 11-byte prefix | Same length in four independent objects; no mapping to a known table or loader field | Low; role unknown |
| Three-byte mixed-layout gap | Same length in four mixed captures; no host write maps to it | Low; role unknown |
| Variable suffix | 70–145 bytes in these captures; excluded from active program mapping | Low; contents unknown |
| Parameter tables and scales | Not identified from static bytes or host writes | Unknown |
| GPR-only host writes | Present in full logs, but not yet tied to source records or user edits | Unknown |
| Firmware loader and `$801e` update service | Existing analysis remains unresolved | Unknown |

The matching native capture for built-in HALL REVERB has 89 live instructions,
but no standalone HALL EFE object is present in the available disk extraction.
It therefore does not contribute to this source-object layout comparison.

## Clean initialization bundle proposal

For each verified object, generate a private bundle containing only the
captured active instructions in index order, the source-verified GPR values
from paired records, and the host-written GPR-only initialization events in
their observed order. Preserve event type and target index. Keep runtime GPR
snapshots, DRAM state, special-register readbacks, and evolving execution state
in separate optional capture sections; do not treat them as factory
initialization. Emit a redacted manifest with effect name, source hash, counts,
source offsets, END index, and per-section hashes. Require all program commits
to match the capture and all paired GPR values to match the source before
writing a bundle. This proposal is not implemented yet; it needs a clearer
classification of the GPR-only host writes and confirmation of initialization
ordering.

## Reproduction

The native CLI runs and their raw outputs are under the local private results
directory. A redacted comparison can be regenerated with:

```sh
python3 tools/compare_asr10_effect_capture.py \
  /private/effects/02_44DDL+CH+REV.payload.bin \
  /private/captures/44DDL-CH-REV.esp \
  /private/captures/44DDL-CH-REV.log \
  --expected-name '44DDL+CH+REV'
```

Do not place effect objects, OS images, firmware, DSP words, GPR values, raw
logs, captures, or WAVs in this repository.
