# ASR-10 Parameter Reconciliation and Independent QA

Date: 2026-11-25
QA branch: `qa/asr10-v4-gui-independent`
Sources: ASR-10 Musician's Manual PDF `e8ab5100904caf91fe355065ed9646aff197761b0663a7d452dc98af1f9a29dc`; Codex 1 parameter recovery `3885d3d`; Codex 2 PC editor `4d4a0d4`.

## Manual and OS inventories

The 594 Section 6 catalog entries remain the correct transcription-level inventory for the 50 numbered factory ROM effects. An independent PDF text audit found 542 exact range strings, all 50 shared four-variation rows, and no missing range row. This does not mean that every catalog row is one cursor field. Grouped headings must be expanded only when manual text and/or OS cursor evidence identifies the member controls.

Codex 1's OS inventory reports 49 effects (ROM-02 deferred), 1,040 effect/field associations across 5,484 observations, 491 exact/alias links, 94 unmatched manual entries, and 500 OS-only associations across 76 labels. These units are not additive control counts. The 94 are unresolved associations, not controls proven absent. The 500 extras include modulation fields, bus mix, aliases, and split/composite labels; they are not 500 newly proven direct effect parameters.

The Appendix at PDF page 368 adds a separate manual-only namespace of 12 OS2 44 kHz algorithms and 215 field headings. It must not be added as numbered slots 51–62. Live OS2 fields, register mappings, and audio behavior remain unverified. The copied manual-only catalog is [ASR10_OS2_44KHZ_APPENDIX_PARAMETER_CATALOG_V1.json](ASR10_OS2_44KHZ_APPENDIX_PARAMETER_CATALOG_V1.json).

### Specific resolutions and open disagreements

| Case | Manual statement | OS evidence | QA disposition |
|---|---|---|---|
| ROOM decay, ROM-14/15/16 | One `DECAY TIME`, with effect domains 0.20–100.0 s, 0.20–150.0 s, and 0.70–250.0 s. | One DECAY TIME field observed per effect. | One identity per effect; range depends on selected effect. The current PC editor gets ROM-15 and ROM-16 wrong (see below). |
| PLATE decay, ROM-17/18 | One `DECAY TIME`, 0.2–100.0 s small and 0.4–140.0 s large. | One field observed per effect. | One identity per effect. Current PC editor gets ROM-18 wrong. |
| PLATE predelay | 0–500 ms small, 0–430 ms large. | Separate predelay field observations. | Keep effect-specific range. Do not reuse the small plate domain for ROM-18. |
| DUAL DELAYS | BUS1/BUS2 have bus-specific mix/feedback; delay-time heading groups independent left/right values with BUS1 0–2000 ms and BUS2 0–150 ms. | Separate bus mixes/feedback and four cursor-selected BS1/BS2 L/R values observed. | Separate semantic IDs by bus and channel; no single combined time knob. |
| Nonlinear envelope | Manual defines nine `ENV LEV` output tap levels, 0–99. | Captured LCD field observations show five values per observed row; four members have no matching cursor proof in this inventory. | Show the five observed fields as OS-observed; mark 6–9 manual-only until a page/variation sweep finds them. Do not claim the nine as fully OS-exposed. |
| Composite position balance / ER levels | `POSITN BAL (1 to 3)` and `ER LEV (1 to 4)` each name independent indexed values. | Cursor underlines show the individual displayed components. | Represent three and four independent values respectively, signed -99…+99. |
| Modulation | Two assignments, each SRC/DST/MIN/MAX; destination names are algorithm-specific and direct edit locks when modulated. | Shared and effect-specific field labels appear in the OS inventory; coverage is not exhaustive for every effect/variation. | Keep assignment 1 and 2 independent; unknown destination choices and lockout conditions must remain unverified, not inferred from the global source list. |
| Conditional options | Manual documents source-dependent FAST/SLOW switch behavior and reversal when SLOW exceeds FAST. | OS inventory provides selected values, not a complete behavior truth table. | UI should use source/threshold semantics; no generic continuous interpretation is verified. |

## Codex 2 full-parameter editor audit

The candidate reports 50 effects, 594 schema descriptors and 907 expanded UI controls. The independent schema audit confirms 594 unique `(effect slot, descriptor ID)` identities; 907 is a presentation expansion, not evidence of 907 distinct original controls or 907 DSP routes.

Independent Python run: **21 passed, 0 failed**. It includes registry coverage, exact existing VST points, no-write behavior, native audio callback, state restore, and layout constraints. The branch's Playwright result says **16 passed**, but this QA environment lacks the `playwright` executable, so that browser result was not independently rerun.

The candidate schema has three manual-range failures:

- ROM-15 LARGE ROOM DECAY TIME: schema says 0.20–100.0 s; manual says 0.20–150.0 s.
- ROM-16 HALL REVERB2 DECAY TIME: schema says 0.20–100.0 s; manual says 0.70–250.0 s.
- ROM-18 LARGE PLATE DECAY TIME: schema says 0.2–100.0 s; manual says 0.4–140.0 s.

The independent checker is [audit_pc_editor_schema.py](../../tools/force_gui_qa/audit_pc_editor_schema.py); machine output is [codex2-pc-editor-independent-audit.json](codex2-pc-editor-independent-audit.json). The schema already models separate L/R delay names, indexed composites, manual-only unsupported ranges, effect variations as PC drafts, and modulation destinations without guessed choices. Specific correction for Codex 2: patch the three ranges and add a regression assertion against the manual source. Keep ROM-22–24 values 6–9 explicitly labeled manual-only until OS observations support them. Do not present PC-only draft or modulation controls as working VST controls.

## HALL DECAY TIME GPR 0x6E independent investigation

The existing private OS trace was re-parsed independently from its step-level host GPR events. It contains 200 transitions over 0–99 and restores the initial display. For each step, the ordered parameter group was selected from the final contiguous `6E, 5B, 03, 04, 05` host-write sequence, excluding unrelated preceding GPR 0x7F writes. Across the 98 shared interior display values, GPR 0x6E differs by one coefficient code between upward and downward approaches at exactly:

`1, 4, 8, 12, 15, 19, 22, 26, 29, 33, 36, 40, 44, 47, 51, 54, 58, 62, 65, 69, 72, 76, 79, 83, 86, 90, 94, 97`.

At display 40 the measured raw coefficients are 0x33 ascending and 0x34 descending; at 65 they are 0x53 and 0x54. The register order is consistently `0x6E, 0x5B, 0x03, 0x04, 0x05`. At 40/41, the prior V2 mapping table lists the same final per-register values in a different `ordered_writes` sequence (`0x03, 0x04, 0x05, 0x5B, 0x6E`). Values agree at those two points, but the stored mapping sequence does not match the newly inspected OS host-event order. Since the OS writes are separated in time, a standalone sequence should not be called OS-sequence-equivalent without a cycle/frame-scheduled comparison. The two routes converge at 28 and 41. This confirms a route-dependent result in the captured trace; it does **not** identify the intended OS quantizer or establish stable fresh-boot behavior.

The published helper reproduces the multiply/negation arithmetic from internal raw coefficient to GPR 03/04/05 for tested valid operands. It does not map LCD integer to raw coefficient. Independent recomputation across the 196 interior directional write groups matched the three derived registers in 102 cases; the remaining 94 did not. The exact 40/41 groups agree with the helper. This narrow agreement cannot promote the full 0–99 range.

Several private derived summaries have different raw-log hashes, but share the same first LCD event, cycle 947,797,188, frame 1,834,868 and display 40. As they lack a unique emulator-process/boot identifier, their independent-boot status is **INCONCLUSIVE**; equal deterministic start coordinates alone neither prove nor disprove independent boots. Do not describe the 28-point discrepancy as fresh-boot reproducibility.

Independent native-runtime A/B used the existing private RUN-boundary package/checkpoint and firmware schedule, exact values 40 and 41, deterministic stereo 431/997 Hz tones plus impulse, 32,768-frame warmup and 65,536-frame measured tail. Outputs were finite; stereo difference RMS `0.000623683`, peak `0.0017395`. This demonstrates audible numerical response for those two points only. It is not original-OS exact audio matching.

**Classification: PARTIAL.** The 40/41 register groups and a measurable runtime A/B are supported. Full-range mapping is not verified; direction-dependent codes and unclear independent-run provenance block promotion. No DSP algorithm was changed.

## Release disposition

Current release readiness is **NOT READY**. See [ASR10_RELEASE_GATES_V2.json](ASR10_RELEASE_GATES_V2.json). The non-finite VST input issue remains an open robustness defect. Physical Force Q-Link callback delivery, ARMv7 compatibility for the current editor candidate, cross-version host chunk corpus compatibility, and exact OS-reference audio are not tested here.
