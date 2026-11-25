# ASR-10 Factory Parameter Specification Audit

Date: 2026-11-25
Branch: `qa/asr10-v4-gui-independent`
Scope: independent specification and OS LCD inventory audit; **no DSP coefficient recovery**.

## Evidence and limits

The specification authority used was the ASR-10 Musician's Manual, Sections 5 and 6. The supplied local PDF was `C:\Users\Gamer\Downloads\23583406.pdf` (SHA-256 `e8ab5100904caf91fe355065ed9646aff197761b0663a7d452dc98af1f9a29dc`). Section 6's 50 ROM-effect headings are on PDF pages 99–153. A public copy of the same manual is available [here](https://datassette.s3.us-west-004.backblazeb2.com/manuais/ensoniq_eq_musicians_manual.pdf).

Independent PDF text validation found all 50 ordered effect names (punctuation normalized). For the 594 catalog descriptors, 542 range strings occur verbatim in the relevant manual-page window, all 50 shared VAR rows match the Section 6 four-variation statement, and the two delay-time rows have the range endpoints in the manual with milliseconds specified in the accompanying increment sentence. No range row was absent from the source text. This is a transcription/association check; it does not validate whether a manual heading is one or several independently editable fields. Results are in [manual-pdf-audit.json](manual-pdf-audit.json). The original PDF is not in Git.

OS implementation evidence comes from Codex 1's existing OS 3.53 inventory V04 (`f1a9f0f524835de8c85bf66012e4a1e29a6df24b`), whose stated source is the live LCD, underline/edit cursor attributes, and host GPR event windows. That evidence is derived field data, not raw emulator captures. No raw captures, firmware, ROM, effect program, checkpoint, or DSP write trace was copied into this branch. The ROM-02 row remains explicitly deferred in this inventory.

## Main finding: 594 catalog entries are not 594 distinct controls

The manual-derived catalog has 594 descriptors. The OS inventory covers 49 effects and reports 1,040 effect/field-label associations across 5,484 observations. Of the 585 manual rows with completed OS inventory coverage, 435 are exact label matches, 56 are alias/expansion associations, and 94 remain flagged for review. Nine ROM-02 descriptors have no OS association because that inventory marks slot 2 deferred. There are also 500 OS field associations not directly linked to catalog rows, representing 76 distinct labels; these include shared modulation fields, bus mixes, split fields, and repeated algorithm parameters. These totals are different kinds of rows and must not be added as unique-control counts.

The manual describes both single fields and grouped headings. Some current catalog records mistakenly treat range variants as separate controls, while other records compress several independently cursor-selectable values into one descriptor. The correct data model must preserve the manual group, then represent its indexed subfields and effect-specific ranges separately. Exact OS presence is not DSP verification.

## Corrections and unresolved groupings

| Effects | Manual/catalog issue | OS observation | Correction for Codex 2's UI / registry |
|---|---|---|---|
| ROM-14 SMALL ROOM, ROM-15 LARGE ROOM, ROM-16 HALL REVERB2 | The catalog creates three decay descriptors (`DECAY TIME Small Room`, `Large Room`, `Hall Reverb2`) on each effect. In the manual these are one `DECAY TIME` control with three algorithm-specific ranges: 0.20–100.0 s, 0.20–150.0 s, and 0.70–250.0 s respectively. | Each effect's captured row is `DECAY TIME`; the current inventory marks the range variants unmatched. | One `DECAY TIME` per effect; select the correct range by effect slot. Do not render three decay controls on every effect. |
| ROM-17 SMALL PLATE, ROM-18 LARGE PLATE | The catalog turns the Small/Large Plate range alternatives into names such as `Large Plate`, including a second `Large Plate` row for predelay. | OS LCD exposes one `DECAY TIME` and one `PREDELAY TIME` row per effect. | Use `DECAY TIME` (0.2–100 s / 0.4–140 s) and `PREDELAY TIME` (0–500 ms / 0–430 ms) once each, with effect-specific domains. |
| ROM-04 DUAL DELAYS, ROM-05 44KHZ DELAYS | Three manual headings group bus-specific values; the one delay-time descriptor omits independent left/right and bus-2 limits. | OS exposes BUS1 and BUS2 mix, feedback, and four independently underlined `BS1/BS2 TIME L/R` values. | UI must expose per-bus mix/feedback and four independent times. BUS1 time is 0–2000 ms (ROM-04) or 0–1300 ms (ROM-05); BUS2 time is 0–150 ms; both channels increment independently in 1 ms according to the manual. |
| ROM-09 ROT. SPKR+REV | `DIST GAIN IN/OUT` is one catalog row. | LCD has distinct `DIST GAIN IN` and `DIST GAIN OUT` fields. | Split into two controls while preserving their input/output semantics. |
| ROM-14..16 | `POSITN BAL (1 to 3)` is one descriptor. | LCD displays three signed values in one row; the existing capture records underline each component separately. | Preserve 1/2/3 as distinct indexed controls or use an explicit composite editor with independent values. Each is -99…+99. |
| ROM-17, ROM-18, ROM-21 | `ER LEV (1 to 4)` is one descriptor. | Captured LCD observations underline four separate signed components. | Preserve ER LEV 1–4 as separate values, -99…+99. |
| ROM-22..24 NLIN REVRB 1/2/3 | Manual states `ENV LEV (1 to 9)` and describes nine output tap levels. | Captured LCD row displays five values per observation and the cursor observations cover five values. | **Unresolved discrepancy:** do not present nine values as OS-verified; determine whether the remaining four levels are on another page/field or the OS exposes a different subset. |
| ROM-06 CHORUS+REVRB | Manual calls the parameter `CHORUS AMT`; 1 manual row is unmatched. | Related `CHORUS RATE AMT` appears as an extra LCD label on ROM-10 and ROM-12, not ROM-06. | Keep unmatched until ROM-06's actual field association is proven; do not globally alias `CHORUS AMT` to `CHORUS RATE AMT`. |
| ROM-10 CHOR+REV+DDL | Manual's `DDL TIME L/R` heading describes two independent channel times. | LCD shows `DDL TIME L` and `DDL TIME R` in the unlisted field set. | Split L/R time controls; keep the manual's common 0–1500 ms domain and 1 ms step. |

These are evidence-backed schema corrections or explicitly unresolved matches, not claims of DSP functionality. The machine-readable matrix preserves the original catalog descriptors while placing known normalizations in `known_manual_heading_normalizations`.

## Variation, modulation, and conditional controls

The manual says `VAR` selects one of four individually editable effect-variation buffers. Each variation can define two modulation sources, two destinations, and their min/max ranges. The shared documented source choices are WHEEL, PBEND, PRESS, PEDAL, XCTRL, KBD, VEL, KEYDN, SUSTN, FSW-L, PATCH, and OFF. Destination choices depend on algorithm. The inventory records variation-specific labels and observed values, but its captures do not exhaustively establish every source/destination availability rule or every range under every variation. Treat missing rows as “not observed in these captured states,” not as proof of an unavailable control.

One documented source-dependent behavior is `FAST-SLOW SWITCH` on ROM-09: continuous sources (WHEEL, PBEND, PRESS, PEDAL, XCTRL, KBD, VEL) act as a threshold switch, while KEYDN, SUSTN, FSW-L, and PATCH toggle on a positive transition. Manual text also notes switch polarity can be reversed by setting ROTOR SLOW above ROTOR FAST. Any runtime registry must include this context; a generic numeric mapping is incorrect.

The matrix keeps (a) manual range/domain/choices, (b) OS label/value and selected-subfield observations, and (c) DSP mapping/audio status in separate fields. The registry evidence currently says 33 rows are runtime-ready at exact recovered points; that number is not 33 full manual ranges and does not make the other inventory rows DSP-functional.

## Manual-to-LCD disposition

The complete per-effect/manual-row-to-LCD mapping is [ASR10_FACTORY_PARAMETER_SPEC_AUDIT_V1.json](ASR10_FACTORY_PARAMETER_SPEC_AUDIT_V1.json). It includes the original effect number/name, Section 6 PDF page, label, range, unit, step confidence, enumeration, field match status, observed OS labels and values, selected subfield cursor observations, and the DSP status imported from the separately versioned registry.

The 94 unmatched rows remain enumerated at parameter level in that JSON. The 56 alias/expansion rows remain explicit, including bus and L/R expansions; they are not silently rewritten as exact manual labels. The OS-only field names are retained by effect so future manual-to-LCD joining can be reviewed independently.

## Guidance for Codex 2 (editor)

1. Use stable per-effect control IDs that include semantic owner: bus, left/right, band, voice, reflection index, or envelope index. A repeated generic `GAIN` ID is insufficient for multiple EQ bands.
2. Show the original instrument label but expose grouped values as independently selectable subfields where cursor evidence demonstrates that behavior.
3. Treat effect-specific ranges as metadata on the one logical control, not separate controls (room/plate decay and predelay).
4. Use true choice controls for VAR, QUALITY, source, destination, phase, and switch enums; do not coerce them to continuous knobs.
5. Keep modulation source/destination/min/max state inside each effect variation. Rebuild destination choices from per-effect evidence and disable unavailable destinations visibly.
6. ROM-02 must show its inventory/provenance gap until its OS screen fields have been captured; do not fill it by copying HALL labels/ranges without the manual's ROM-02 distinctions.
7. Keep “manual documented,” “OS observed,” “register mapped,” and “audio verified” as separate badges/states.

## Guidance for Codex 1 (monitor / recovery)

For cursor-to-GPR traces, key the field identity by `(slot, variation, LCD label, selected subfield text/index, bus/channel/band/voice, ordinal)`. The captured underlines show that one LCD label can represent multiple independently editable subfields (POSITN BAL, ER LEV, ENV LEV, and bus L/R fields). Register probes should correlate one selected component change and its reversal while holding all other components constant. Do not promote the 94 unmatched manual rows or 500 OS-only associations to parameter mappings without that controlled evidence.

## Validation

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/force_gui_qa/audit_factory_parameter_spec.py \
  --inventory /home/gamer/worktrees/asr10-full-factory-parameter-recovery/docs/ASR10_FACTORY_EFFECT_EDITOR_INVENTORY_V04.json
PYTHONPATH=/tmp/asr10-pypdf:tools/force_gui_qa PYTHONDONTWRITEBYTECODE=1 \
  python3 tools/force_gui_qa/audit_manual_pdf_text.py /mnt/c/Users/Gamer/Downloads/23583406.pdf
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/force_gui_qa -v
```

For the optional PDF check, install `pypdf` into a user-local target directory (for example, `python3 -m pip install --target /tmp/asr10-pypdf pypdf`). The generator reads the other worktree without modifying it and emits normalized field/value evidence only. It does not copy raw captures or DSP write payloads.
