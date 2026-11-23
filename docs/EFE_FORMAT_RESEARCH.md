# EFE effect-file format — independent extraction track

## Scope and evidence

This branch is independent of the Force single-unit plugin and does not change the ES5510 audio executor.

**Verified against one private OS 3.53 object and its live host log:** the selected `44DDL+CHORUS` program contains 60 active 48-bit instructions (END at 59) embedded in a mixed source region. A naive six-byte scan reported 90 chunks but was not valid instruction decoding.

Observed structure (object-relative offsets):

| Region | Offset | Length | Evidence |
|---|---:|---:|---|
| Undecoded prefix | 0x0a3c | 11 bytes | Unknown role |
| 29 paired records | 0x0a47 | 261 bytes | 3-byte GPR followed by 6-byte instruction; host commits and values match |
| Undecoded gap | 0x0b4c | 3 bytes | Unknown role |
| 31 instruction-only records | 0x0b4f | 186 bytes | Host instruction commits match |
| Undecoded suffix | 0x0c09 | 80 bytes | Unknown role |
| Declared effect extent | through 0x0c59 | — | FxSize=3161 |

Header fields **observed in the existing parser**: effect name encoded in alternating bytes at positions 10..33, big-endian 32-bit FxSize at 34..37, and big-endian 16-bit FxUcode at 38..39. These offsets are *not* a complete documented format specification. The header may vary across object types or versions.

## What is not established

- Meaning of the 11-byte prefix, 3-byte gap, 80-byte suffix.
- Whether these boundaries apply to other effects, particularly the 89-word HALL REVERB.
- Full EFE header layout, parameter definitions and scale/curve tables.
- Firmware transfer/relocation rules and effects loaded from banks.
- Factory parameter-to-GPR mapping and the unresolved updater service $801e.
- Whether snapshots after execution can be converted to pristine initialization state.

Do not generalize the 29+31 split to other algorithms without new evidence.

## New conservative inventory tool

```sh
python3 tools/profile_efe_objects.py /private/effects/ --output /private/reports/efe-inventory.json
python3 -m unittest discover -s tests -v
```

Input is a private directory containing extracted `.efe` or `.bin` effect objects (or individual paths). The JSON contains object sizes, hashes, names, declared bounds, and a *clearly labeled naive* six-byte chunk count, not firmware bytes or guessed instruction arrays. The --output path must remain outside Git. The report **does not establish** any new field meanings.

Synthetic-only tests validate header bounds and redaction. Real private-object validation has not been run in this branch.

## Next falsifiable tests

1. Run the inventory over a private multi-effect corpus; classify objects by bounds and region lengths.
2. Repeat the live host-log vs source comparison for HALL REVERB and at least one other delay/reverb object. Do not assume the same pairing counts or strides.
3. Map the remaining unexplained bytes by differential comparison between related effect objects, with names, hashes, offsets and lengths only in public reports.
4. Capture an actual user-controlled parameter edit; distinguish runtime host writes from evolving DSP GPR state.
5. Disassemble the OS parser/updater path privately to validate field semantics and service $801e.
6. Develop a generalized, bounds-checked parser **only after** multi-effect evidence supports shared rules.

All ROMs, OS images, effect objects, raw host logs, reconstructed factory programs and audio renders remain private. No factory DSP data is committed.
