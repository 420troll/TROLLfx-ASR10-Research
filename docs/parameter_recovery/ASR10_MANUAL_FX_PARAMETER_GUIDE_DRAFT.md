# TROLLfx ASR-10 — Manual-derived effect parameter inventory

**Source:** Ensoniq *ASR-10 Musician's Manual*, user-provided PDF `23583406.pdf` (391 PDF pages), SHA-256 `e8ab5100904caf91fe355065ed9646aff197761b0663a7d452dc98af1f9a29dc`.

**Coverage:** ROM-01 through ROM-50 from Section 6 (PDF pp. 99–153), plus the **12 additional 44 kHz algorithms** from the manual appendix (PDF pp. 368–376). PDF page numbers are *viewer page numbers*, not the printed page footer.

**Purpose:** Requirements and research guide for Codex. Parameter appearance in this document is **not** evidence of a functioning production control, a verified OS register mapping, or accurate audio behavior. Keep those statuses separate.

**Interpretation warnings:**

- The ROM effects use up to four editable **variations**; variation is a separate concept from an effect parameter. See Section 6 PDF p. 99.
- Many ROM-14–50 effects refer to the shared modulation controls `MOD SRC 1/2`, `DST 1/2`, `MIN 1/2`, `MAX 1/2`; those eight names appear in each applicable effect below. The manually documented modulation destination capabilities are not yet implemented just because the labels are listed.
- Shared manual descriptions (e.g. ROM-01/02/03) have been duplicated under every corresponding ROM in this guide.
- Repeated manual `GAIN` labels were sometimes qualified by band for code clarity; verify exact on-screen LCD abbreviations when assigning UI labels.
- `See manual` means this extract did not safely resolve a numerical range. Do **not** invent a range from the label or assume `0–99` universally.
- Original BUS and modulation controls are documented even though the current two-page Force GUI intentionally hides them. They remain relevant to faithful DSP behavior.
- For HALL DECAY, the original manual says `0–99` **display values**; the independently recovered 128 raw-state OS mapping is research evidence, not itself a manual claim.

## ROM-01 to ROM-50

### ROM-01 — HALL REVERB  (PDF p. 99)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DECAY TIME | 0 to 99 | 99 |
| LOW FREQ DECAY | -99 to +99 | 99 |
| DIFFUSION | 0 to 99 | 99 |
| HI FREQ DAMPING | 0 to 99 | 99 |
| HI FREQ BANDWIDTH | 0 to 99 | 99 |
| DETUNE RATE | 0 to 99 | 99 |
| DETUNE AMT | 0 to 99 | 100 |
| PRE-DELAY TIME | ROOM and HALL REVERB Range:  0 to 500 | 100 |

*Parameter descriptions shared under ROM-03 in the manual.*

### ROM-02 — 44KHZ REVERB  (PDF p. 99)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DECAY TIME | 0 to 99 | 99 |
| LOW FREQ DECAY | -99 to +99 | 99 |
| DIFFUSION | 0 to 99 | 99 |
| HI FREQ DAMPING | 0 to 99 | 99 |
| HI FREQ BANDWIDTH | 0 to 99 | 99 |
| DETUNE RATE | 0 to 99 | 99 |
| DETUNE AMT | 0 to 99 | 100 |
| PRE-DELAY TIME | ROOM and HALL REVERB Range:  0 to 500 | 100 |

*Parameter descriptions shared under ROM-03 in the manual.*

### ROM-03 — ROOM REVERB  (PDF p. 99)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DECAY TIME | 0 to 99 | 99 |
| LOW FREQ DECAY | -99 to +99 | 99 |
| DIFFUSION | 0 to 99 | 99 |
| HI FREQ DAMPING | 0 to 99 | 99 |
| HI FREQ BANDWIDTH | 0 to 99 | 99 |
| DETUNE RATE | 0 to 99 | 99 |
| DETUNE AMT | 0 to 99 | 100 |
| PRE-DELAY TIME | ROOM and HALL REVERB Range:  0 to 500 | 100 |

### ROM-04 — DUAL DELAYS  (PDF p. 100)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 DELAY MIX | 0 to 99 | 100 |
| BUS2 DELAY MIX | 0 to 99 | 100 |
| BUS1 FEEDBACK | 0 to 99 | 100 |
| BUS2 FEEDBACK | 0 to 99 | 100 |
| BUS1 DELAY TIME L | Dual Delays Bus1 Range:  0 to 2000 | 100 |
| BUS1 DELAY TIME R | Dual Delays Bus1 Range:  0 to 2000 | 100 |
| BUS2 DELAY TIME L | Dual Delays Bus1 Range:  0 to 2000 | 100 |
| BUS2 DELAY TIME R | Dual Delays Bus1 Range:  0 to 2000 | 100 |

*Parameter descriptions shared under ROM-05 in the manual.*

### ROM-05 — 44KHZ DELAYS  (PDF p. 100)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 DELAY MIX | 0 to 99 | 100 |
| BUS2 DELAY MIX | 0 to 99 | 100 |
| BUS1 FEEDBACK | 0 to 99 | 100 |
| BUS2 FEEDBACK | 0 to 99 | 100 |
| BUS1 DELAY TIME L | Dual Delays Bus1 Range:  0 to 2000 | 100 |
| BUS1 DELAY TIME R | Dual Delays Bus1 Range:  0 to 2000 | 100 |
| BUS2 DELAY TIME L | Dual Delays Bus1 Range:  0 to 2000 | 100 |
| BUS2 DELAY TIME R | Dual Delays Bus1 Range:  0 to 2000 | 100 |

### ROM-06 — CHORUS+REVRB  (PDF p. 100)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 REV AFTER CHOR | 0 to 99 | 100 |
| BUS2 REVERB MIX | 0 to 99 | 100 |
| REVERB DECAY TIME | See manual | 100 |
| LOW FREQ DECAY | See manual | 100 |
| DIFFUSION | See manual | 100 |
| HI FREQ DAMPING | See manual | 100 |
| HI FREQ BANDWIDTH | See manual | 100 |
| REVERB DETUNE RATE | See manual | 100 |
| REVERB DETUNE AMT | See manual | 100 |
| EARLY RFLECTION LEV | 0 to 99 | 101 |
| CHORUS RATE | 0 to 99 | 101 |
| CHORUS AMT | 0 to 99 | 101 |
| CHORUS MIX | 0 to 99 | 101 |
| CHORUS FEEDBACK | -99 to +99 | 101 |

### ROM-07 — PHASER+REVRB  (PDF p. 101)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 REVERB MIX | 0 to 99 | 101 |
| BUS2 REVERB MIX | 0 to 99 | 101 |
| REVERB DECAY TIME | See manual | 101 |
| LOW FREQ DECAY | See manual | 101 |
| DIFFUSION | See manual | 101 |
| HI FREQ DAMPING | See manual | 101 |
| HI FREQ BANDWIDTH | See manual | 101 |
| REVERB DETUNE RATE | See manual | 101 |
| REVERB DETUNE AMT | See manual | 101 |
| EARLY RFLECTION LEV | See manual | 101 |
| PHASE CENTER | 0 to 99 | 101 |
| PHASE RATE | 0 to 99 | 101 |
| PHASE WIDTH | 0 to 99 | 101 |
| PHASE FEEDBACK | -99 to +99 | 101 |
| PHASE DEPTH | 0 to 99 | 102 |

### ROM-08 — FLANGER+REV  (PDF p. 102)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 REVERB MIX | 0 to 99 | 102 |
| BUS2 REVERB MIX | 0 to 99 | 102 |
| REVERB DECAY TIME | See manual | 102 |
| LOW FREQ DECAY | See manual | 102 |
| DIFFUSION | See manual | 102 |
| HI FREQ DAMPING | See manual | 102 |
| HI FREQ BANDWIDTH | See manual | 102 |
| REVERB DETUNE RATE | See manual | 102 |
| REVERB DETUNE AMT | See manual | 102 |
| EARLY RFLECTION LEV | See manual | 102 |
| FLANGE CENTER | 0 to 99 | 102 |
| FLANGE RATE | 0 to 99 | 102 |
| FLANGE WIDTH | 0 to 99 | 102 |
| FLANGE FEEDBACK | -99 to +99 | 102 |
| FLANGE DEPTH | 0 to 99 | 102 |

### ROM-09 — ROT. SPKR+REV  (PDF p. 102)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 REV AFTER ROTO | 0 to 99 | 102 |
| BUS2 REVERB MIX | 0 to 99 | 102 |
| REVERB DECAY TIME | See manual | 102 |
| DIFFUSION | See manual | 102 |
| HI FREQ DAMPING | See manual | 102 |
| ROTOR FAST | 0 to 99 | 103 |
| ROTOR SLOW | 0 to 99 | 103 |
| ROTOR INERTIA | 0 to 99 | 103 |
| FAST-SLOW SWITCH | see below | 103 |
| DIST GAIN IN | See manual | 102 |
| DIST GAIN OUT | See manual | 102 |
| SPEAKER GAIN | 0 to 99 | 103 |
| DISTORTION FILTER | 0 to 99 | 103 |

### ROM-10 — CHOR+REV+DDL  (PDF p. 103)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 REV AFTER CHOR | See manual | 103 |
| BUS2 REVERB MIX | See manual | 103 |
| BUS3 DDL MIX | 0 to 99 | 104 |
| REVERB DECAY TIME | See manual | 103 |
| LOW FREQ DECAY | See manual | 103 |
| HI FREQ DAMPING | See manual | 103 |
| REVERB DETUNE RATE | See manual | 103 |
| REVERB DETUNE AMT | See manual | 103 |
| CHORUS RATE | See manual | 103 |
| CHORUS AMT | See manual | 103 |
| CHORUS MIX | See manual | 103 |
| CHORUS FEEDBACK | See manual | 103 |
| DDL TIME L | 0 to 1500 | 104 |
| DDL TIME R | 0 to 1500 | 104 |
| DDL FEEDBACK | 0 to 99 | 104 |

### ROM-11 — CMP+DIST+REV  (PDF p. 104)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 REV AFTER DIST | 0 to 99 | 104 |
| BUS2 REVERB MIX | See manual | 104 |
| REVERB DECAY TIME | See manual | 104 |
| HI FREQ DAMPING | See manual | 104 |
| COMPRESSOR THRESHLD | 0 to 99 | 104 |
| DIST LPF | See manual | 104 |
| DIST HPF | See manual | 104 |
| DIST FLANGE RATE | 0 to 99 | 105 |
| SYSTEM FEEDBACK | -99 to +99 | 105 |

### ROM-12 — DIST+CHO+REV  (PDF p. 105)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 DIST INTO CHOR MIX | 0 to 99 | 105 |
| CHOR INTO REV MIX | 0 to 99 | 105 |
| BUS3 REVERB MIX | 0 to 99 | 105 |
| DIST FILTER FC | 0 to 99 | 105 |
| DIST FILTER Q | 1 to 25 | 105 |
| DISTORTION MIX | 0 to 99 | 106 |
| REVERB DECAY TIME | See manual | 105 |
| LOW FREQ DECAY | See manual | 105 |
| HI FREQ DAMPING | See manual | 105 |
| HI FREQ BANDWIDTH | See manual | 105 |
| REVERB DETUNE RATE | See manual | 105 |
| REVERB DETUNE AMT | See manual | 105 |
| EARLY RFLECTION LEV | See manual | 105 |
| CHORUS MIX | See manual | 105 |
| CHORUS RATE | See manual | 105 |
| CHORUS AMT | See manual | 105 |

### ROM-13 — WAH+DIST+REV  (PDF p. 106)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 REV AFTER DIST | 0 to 99 | 106 |
| BUS2 REVERB MIX | See manual | 106 |
| REVERB DAMPING | See manual | 106 |
| REVERB DECAY TIME | See manual | 106 |
| COMPRESSOR THRESHLD | See manual | 106 |
| WAH FILTER CENTER | 0 to 99 | 106 |
| WAH RANGE | -99 to +99 | 106 |
| SYSTEM FEEDBACK | See manual | 106 |

### ROM-14 — SMALL ROOM  (PDF p. 107)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DECAY TIME | Small Room Range:  0.20 to 100.0 sec. | 107 |
| PREDELAY TIME | 0 to 450 ms | 108 |
| LF DECAY TIME | -99 to +99 | 108 |
| HF DAMPING | 0 to 99 | 108 |
| HF BANDWIDTH | 1 to 99 | 108 |
| DIFFUS1 | 0 to 99 | 108 |
| DIFFUS2 | 0 to 99 | 108 |
| DECAY DEFINITION | 0 to 99 | 108 |
| DETUNE RATE | 0 to 99 | 108 |
| DETUNE DEPTH | 0 to 99 | 108 |
| PRIMARY SEND LEVEL | -99 to +99 | 108 |
| REFL 1 TIME | 0 to 120 milliseconds | 108 |
| REFL 1 LEVEL | 0 to 99 | 109 |
| REFL 1 SEND | 0 to 99 | 109 |
| REFL 2 TIME | 0 to 120 milliseconds | 109 |
| REFL 2 LEVEL | 0 to 99 | 109 |
| REF 2 SEND | 0 to 99 | 109 |
| MOD SRC 1 | See manual | 107 |
| MOD SRC 2 | See manual | 107 |
| DST 1 | See manual | 107 |
| DST 2 | See manual | 107 |
| MIN 1 | See manual | 107 |
| MIN 2 | See manual | 107 |
| MAX 1 | See manual | 107 |
| MAX 2 | See manual | 107 |

*Parameter descriptions shared under ROM-16 in the manual.*

### ROM-15 — LARGE ROOM  (PDF p. 107)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DECAY TIME | Small Room Range:  0.20 to 100.0 sec. | 107 |
| PREDELAY TIME | 0 to 450 ms | 108 |
| LF DECAY TIME | -99 to +99 | 108 |
| HF DAMPING | 0 to 99 | 108 |
| HF BANDWIDTH | 1 to 99 | 108 |
| DIFFUS1 | 0 to 99 | 108 |
| DIFFUS2 | 0 to 99 | 108 |
| DECAY DEFINITION | 0 to 99 | 108 |
| DETUNE RATE | 0 to 99 | 108 |
| DETUNE DEPTH | 0 to 99 | 108 |
| PRIMARY SEND LEVEL | -99 to +99 | 108 |
| REFL 1 TIME | 0 to 120 milliseconds | 108 |
| REFL 1 LEVEL | 0 to 99 | 109 |
| REFL 1 SEND | 0 to 99 | 109 |
| REFL 2 TIME | 0 to 120 milliseconds | 109 |
| REFL 2 LEVEL | 0 to 99 | 109 |
| REF 2 SEND | 0 to 99 | 109 |
| MOD SRC 1 | See manual | 107 |
| MOD SRC 2 | See manual | 107 |
| DST 1 | See manual | 107 |
| DST 2 | See manual | 107 |
| MIN 1 | See manual | 107 |
| MIN 2 | See manual | 107 |
| MAX 1 | See manual | 107 |
| MAX 2 | See manual | 107 |

*Parameter descriptions shared under ROM-16 in the manual.*

### ROM-16 — HALL REVERB2  (PDF p. 107)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DECAY TIME | Small Room Range:  0.20 to 100.0 sec. | 107 |
| PREDELAY TIME | 0 to 450 ms | 108 |
| LF DECAY TIME | -99 to +99 | 108 |
| HF DAMPING | 0 to 99 | 108 |
| HF BANDWIDTH | 1 to 99 | 108 |
| DIFFUS1 | 0 to 99 | 108 |
| DIFFUS2 | 0 to 99 | 108 |
| DECAY DEFINITION | 0 to 99 | 108 |
| DETUNE RATE | 0 to 99 | 108 |
| DETUNE DEPTH | 0 to 99 | 108 |
| PRIMARY SEND LEVEL | -99 to +99 | 108 |
| REFL 1 TIME | 0 to 120 milliseconds | 108 |
| REFL 1 LEVEL | 0 to 99 | 109 |
| REFL 1 SEND | 0 to 99 | 109 |
| REFL 2 TIME | 0 to 120 milliseconds | 109 |
| REFL 2 LEVEL | 0 to 99 | 109 |
| REF 2 SEND | 0 to 99 | 109 |
| MOD SRC 1 | See manual | 107 |
| MOD SRC 2 | See manual | 107 |
| DST 1 | See manual | 107 |
| DST 2 | See manual | 107 |
| MIN 1 | See manual | 107 |
| MIN 2 | See manual | 107 |
| MAX 1 | See manual | 107 |
| MAX 2 | See manual | 107 |

### ROM-17 — SMALL PLATE  (PDF p. 109)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DECAY TIME | Small Plate Range:  0.2 to 100.0 sec. | 110 |
| PREDELAY TIME | Small Plate Range:  0 to 500 ms | 110 |
| HF DAMPING | 0 to 99 | 110 |
| HF BANDWIDTH | 1 to 99 | 110 |
| DIFFUS1 | 0 to 99 | 110 |
| DIFFUS2 | 0 to 99 | 110 |
| DECAY DEFINITION | 0 to 99 | 110 |
| L/R BALANCE | -99 to +99 | 111 |
| MOD SRC 1 | See manual | 109 |
| MOD SRC 2 | See manual | 109 |
| DST 1 | See manual | 109 |
| DST 2 | See manual | 109 |
| MIN 1 | See manual | 109 |
| MIN 2 | See manual | 109 |
| MAX 1 | See manual | 109 |
| MAX 2 | See manual | 109 |

*Parameter descriptions shared under ROM-18 in the manual.*

### ROM-18 — LARGE PLATE  (PDF p. 109)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DECAY TIME | Small Plate Range:  0.2 to 100.0 sec. | 110 |
| PREDELAY TIME | Small Plate Range:  0 to 500 ms | 110 |
| HF DAMPING | 0 to 99 | 110 |
| HF BANDWIDTH | 1 to 99 | 110 |
| DIFFUS1 | 0 to 99 | 110 |
| DIFFUS2 | 0 to 99 | 110 |
| DECAY DEFINITION | 0 to 99 | 110 |
| L/R BALANCE | -99 to +99 | 111 |
| MOD SRC 1 | See manual | 109 |
| MOD SRC 2 | See manual | 109 |
| DST 1 | See manual | 109 |
| DST 2 | See manual | 109 |
| MIN 1 | See manual | 109 |
| MIN 2 | See manual | 109 |
| MAX 1 | See manual | 109 |
| MAX 2 | See manual | 109 |

### ROM-19 — REVRSE REVRB  (PDF p. 111)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| HOLD TIME | 1ms to 10.0s | 111 |
| ATTACK TIME | 1ms to 10.0s | 111 |
| RELEASE TIME | 1ms to 10.0s | 111 |
| TRIGGER THRESHOLD | -96 to +0 dB | 111 |
| HF DAMPING | 0 to 99 | 112 |
| DIFFUS1 | 0 to 99 | 112 |
| DIFFUS2 | 0 to 99 | 112 |
| DECAY DEFINITION | 0 to 99 | 112 |
| SLAPBACK TIME | 0 to 530ms | 112 |
| SLAPBACK LEVEL | 0 to 99 | 112 |
| MOD SRC 1 | See manual | 111 |
| MOD SRC 2 | See manual | 111 |
| DST 1 | See manual | 111 |
| DST 2 | See manual | 111 |
| MIN 1 | See manual | 111 |
| MIN 2 | See manual | 111 |
| MAX 1 | See manual | 111 |
| MAX 2 | See manual | 111 |

### ROM-20 — REVRSE REVB2  (PDF p. 112)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| HOLD TIME | 1ms to 10.0s | 112 |
| ATTACK TIME | 1ms to 10.0s | 112 |
| RELEASE TIME | 1ms to 10.0s | 113 |
| TRIGGER THRESHOLD | -96 to +0 dB | 113 |
| PRE-TRIGGER TIME | 0 to 530 ms | 113 |
| HF DAMPING | 0 to 99 | 113 |
| DIFFUS1 | 0 to 99 | 113 |
| DIFFUS2 | 0 to 99 | 113 |
| DECAY DEFINITION | 0 to 99 | 113 |
| MOD SRC 1 | See manual | 112 |
| MOD SRC 2 | See manual | 112 |
| DST 1 | See manual | 112 |
| DST 2 | See manual | 112 |
| MIN 1 | See manual | 112 |
| MIN 2 | See manual | 112 |
| MAX 1 | See manual | 112 |
| MAX 2 | See manual | 112 |

### ROM-21 — GATED REVERB  (PDF p. 113)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| ATTACK TIME | 1ms to 10.0s | 114 |
| HOLD TIME | 1ms to 10.0s | 114 |
| DECAY TIME | 0.2 to 100.0 sec. | 114 |
| RELEASE TIME | 1ms to 10.0s | 114 |
| TRIGGER THRESH | -96 to +0 dB | 115 |
| RETRIGGER THRESH | -96 to +0 dB | 115 |
| HF DAMPING | 0 to 99 | 115 |
| DIFFUS1 | 0 to 99 | 115 |
| DIFFUS2 | 0 to 99 | 115 |
| DEFINITION | 0 to 99 | 115 |
| SLAPBACK | 0 to 500 ms | 115 |
| SLAPBACK LEVEL | 0 to 99 | 115 |
| L/R BALANCE | -99 to +99 | 115 |
| MOD SRC 1 | See manual | 113 |
| MOD SRC 2 | See manual | 113 |
| DST 1 | See manual | 113 |
| DST 2 | See manual | 113 |
| MIN 1 | See manual | 113 |
| MIN 2 | See manual | 113 |
| MAX 1 | See manual | 113 |
| MAX 2 | See manual | 113 |

### ROM-22 — NLIN REVRB 1  (PDF p. 116)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| HF DAMPING | 0 to 99 | 116 |
| HF BANDWIDTH | 1 to 99 | 117 |
| DIFFUS1 | 0 to 99 | 117 |
| DIFFUS2 | 0 to 99 | 117 |
| DENSTY 1 | 0 to 99 | 117 |
| DENSTY 2 | 0 to 99 | 117 |
| PRIMARY SEND LEVEL | -99 to +99 | 117 |
| REFL 1 TIME | Non Lin 1, 3 Range:  0 to 600 ms | 117 |
| REFL 1 SEND LEVEL | -99 to +99 | 117 |
| REFL 2 TIME | Non Lin 1, 3 Range:  0 to 600 ms | 117 |
| REFL 2 SEND LEVEL | -99 to +99 | 117 |
| L/R BALANCE | -99 to +99 | 117 |
| MOD SRC 1 | See manual | 116 |
| MOD SRC 2 | See manual | 116 |
| DST 1 | See manual | 116 |
| DST 2 | See manual | 116 |
| MIN 1 | See manual | 116 |
| MIN 2 | See manual | 116 |
| MAX 1 | See manual | 116 |
| MAX 2 | See manual | 116 |

*Parameter descriptions shared under ROM-24 in the manual.*

### ROM-23 — NLIN REVRB 2  (PDF p. 116)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| HF DAMPING | 0 to 99 | 116 |
| HF BANDWIDTH | 1 to 99 | 117 |
| DIFFUS1 | 0 to 99 | 117 |
| DIFFUS2 | 0 to 99 | 117 |
| DENSTY 1 | 0 to 99 | 117 |
| DENSTY 2 | 0 to 99 | 117 |
| PRIMARY SEND LEVEL | -99 to +99 | 117 |
| REFL 1 TIME | Non Lin 1, 3 Range:  0 to 600 ms | 117 |
| REFL 1 SEND LEVEL | -99 to +99 | 117 |
| REFL 2 TIME | Non Lin 1, 3 Range:  0 to 600 ms | 117 |
| REFL 2 SEND LEVEL | -99 to +99 | 117 |
| L/R BALANCE | -99 to +99 | 117 |
| MOD SRC 1 | See manual | 116 |
| MOD SRC 2 | See manual | 116 |
| DST 1 | See manual | 116 |
| DST 2 | See manual | 116 |
| MIN 1 | See manual | 116 |
| MIN 2 | See manual | 116 |
| MAX 1 | See manual | 116 |
| MAX 2 | See manual | 116 |

*Parameter descriptions shared under ROM-24 in the manual.*

### ROM-24 — NLIN REVRB 3  (PDF p. 116)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| HF DAMPING | 0 to 99 | 116 |
| HF BANDWIDTH | 1 to 99 | 117 |
| DIFFUS1 | 0 to 99 | 117 |
| DIFFUS2 | 0 to 99 | 117 |
| DENSTY 1 | 0 to 99 | 117 |
| DENSTY 2 | 0 to 99 | 117 |
| PRIMARY SEND LEVEL | -99 to +99 | 117 |
| REFL 1 TIME | Non Lin 1, 3 Range:  0 to 600 ms | 117 |
| REFL 1 SEND LEVEL | -99 to +99 | 117 |
| REFL 2 TIME | Non Lin 1, 3 Range:  0 to 600 ms | 117 |
| REFL 2 SEND LEVEL | -99 to +99 | 117 |
| L/R BALANCE | -99 to +99 | 117 |
| MOD SRC 1 | See manual | 116 |
| MOD SRC 2 | See manual | 116 |
| DST 1 | See manual | 116 |
| DST 2 | See manual | 116 |
| MIN 1 | See manual | 116 |
| MIN 2 | See manual | 116 |
| MAX 1 | See manual | 116 |
| MAX 2 | See manual | 116 |

### ROM-25 — MULTITAP DDL  (PDF p. 118)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DLY 1 TIME | 0 to 2186 ms | 118 |
| DLY 1 RGN | 0 to 99 | 118 |
| DLY 1 LEVEL | 0 to 99 | 118 |
| DLY 1 PAN | -99 to +99 | 118 |
| DLY 2 TIME | See manual | 118 |
| DLY 2 RGN | See manual | 118 |
| DLY 2 LEVEL | See manual | 118 |
| DLY 2 PAN | See manual | 118 |
| DLY 3 TIME | See manual | 118 |
| DLY 3 RGN | See manual | 118 |
| DLY 3 LEVEL | See manual | 118 |
| DLY 3 PAN | See manual | 118 |
| DLY 4 TIME | See manual | 118 |
| DLY 4 RGN | See manual | 118 |
| DLY 4 LEVEL | See manual | 118 |
| DLY 4 PAN | See manual | 118 |
| REGEN DAMPING | 0 to 99 | 118 |
| MOD SRC 1 | See manual | 118 |
| MOD SRC 2 | See manual | 118 |
| DST 1 | See manual | 118 |
| DST 2 | See manual | 118 |
| MIN 1 | See manual | 118 |
| MIN 2 | See manual | 118 |
| MAX 1 | See manual | 118 |
| MAX 2 | See manual | 118 |

### ROM-26 — EQ + DELAY LFO  (PDF p. 119)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DLY TIME L | 0 to 845 ms | 119 |
| DLY TIME R | 0 to 845 ms | 119 |
| LFO RATE | 0 to 99 | 119 |
| LFO WIDTH | 0 to 99 | 119 |
| L/R LFO | OUT-OF-PHASE or IN-PHASE | 119 |
| DELAY REGEN | -99 to +99 | 119 |
| DLY CROSS REGEN | -99 to +99 | 120 |
| REGEN DAMPING | 0 to 99 | 120 |
| R DELAY INPUT | OFF or ON | 120 |
| R OUTPUT LEVEL | 0 to 99 | 120 |
| BASS FC | 0 to 1000 Hz | 120 |
| BASS GAIN | -48 to +24 dB | 120 |
| TREBLE FC | 1KHz to 15KHz | 120 |
| TREBLE GAIN | -48 to +24 dB | 120 |
| EQ TRIM | -24 to +0 dB | 120 |
| MOD SRC 1 | See manual | 119 |
| MOD SRC 2 | See manual | 119 |
| DST 1 | See manual | 119 |
| DST 2 | See manual | 119 |
| MIN 1 | See manual | 119 |
| MIN 2 | See manual | 119 |
| MAX 1 | See manual | 119 |
| MAX 2 | See manual | 119 |

### ROM-27 — VCF+DISTORT  (PDF p. 121)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| DIST LEVEL IN | 0 to 99 | 121 |
| DIST LEVEL OUT | 0 to 99 | 121 |
| PRE-DIST VCF FC | 1 to 99 | 121 |
| PRE-DIST VCF Q | 1 to 25 | 121 |
| PRE-DIST ENV FOL | -99 to +99 | 121 |
| POST-DIST VCF FC | 01 to 99 | 122 |
| POST-DIST VCF Q | 1 to 25 | 122 |
| POST-DIST ENV FOL | -99 to +99 | 122 |
| ATTACK | 50µs to 10.0s | 122 |
| RELEASE | 1ms to 10.0s | 122 |
| DISTORTION BYPASS | OFF or ON | 122 |
| PRE-EQ HP FC | 0 to 1000 Hz | 122 |
| MOD SRC 1 | See manual | 121 |
| MOD SRC 2 | See manual | 121 |
| DST 1 | See manual | 121 |
| DST 2 | See manual | 121 |
| MIN 1 | See manual | 121 |
| MIN 2 | See manual | 121 |
| MAX 1 | See manual | 121 |
| MAX 2 | See manual | 121 |

### ROM-28 — GUITAR AMP 1  (PDF p. 122)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| PREAMP GAIN | -48 to +48 dB | 123 |
| OUTPUT LEVEL | 0 to 99 | 123 |
| TUBE BIAS | 0 to 99 | 123 |
| PRE-EQ TRIM | -24 to +0 dB | 123 |
| PRE-EQ HIGH | 4 to 1000 Hz | 123 |
| PRE-EQ FC | 0 to 9999 Hz | 123 |
| PRE-EQ GAIN | -48 to +24 dB | 123 |
| PRE-EQ Q | 1 to 18 | 123 |
| GATE OFF | -96 to +0 dB | 123 |
| GATE ON | -96 to +0 dB | 123 |
| GATE RELEASE | 1ms to 10.0s | 123 |
| HIGH PASS FC | 4 to 1000 Hz | 123 |
| EQ1 FC | 0 to 9999 Hz | 124 |
| EQ1 GAIN | -48 to +24 dB | 124 |
| EQ1 Q | 1 to 18 | 124 |
| EQ2 FC | 0 to 9999 Hz | 124 |
| EQ2 GAIN | -48 to +24 dB | 124 |
| EQ2 Q | 1 to 18 | 124 |
| LOW PASS FC | 2.0 to 15.0 KHz | 124 |
| MOD SRC 1 | See manual | 122 |
| MOD SRC 2 | See manual | 122 |
| DST 1 | See manual | 122 |
| DST 2 | See manual | 122 |
| MIN 1 | See manual | 122 |
| MIN 2 | See manual | 122 |
| MAX 1 | See manual | 122 |
| MAX 2 | See manual | 122 |

*Parameter descriptions shared under ROM-29 in the manual.*

### ROM-29 — GUITAR AMP 2  (PDF p. 122)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| PREAMP GAIN | -48 to +48 dB | 123 |
| OUTPUT LEVEL | 0 to 99 | 123 |
| TUBE BIAS | 0 to 99 | 123 |
| PRE-EQ TRIM | -24 to +0 dB | 123 |
| PRE-EQ HIGH | 4 to 1000 Hz | 123 |
| PRE-EQ FC | 0 to 9999 Hz | 123 |
| PRE-EQ GAIN | -48 to +24 dB | 123 |
| PRE-EQ Q | 1 to 18 | 123 |
| GATE OFF | -96 to +0 dB | 123 |
| GATE ON | -96 to +0 dB | 123 |
| GATE RELEASE | 1ms to 10.0s | 123 |
| HIGH PASS FC | 4 to 1000 Hz | 123 |
| EQ1 FC | 0 to 9999 Hz | 124 |
| EQ1 GAIN | -48 to +24 dB | 124 |
| EQ1 Q | 1 to 18 | 124 |
| EQ2 FC | 0 to 9999 Hz | 124 |
| EQ2 GAIN | -48 to +24 dB | 124 |
| EQ2 Q | 1 to 18 | 124 |
| LOW PASS FC | 2.0 to 15.0 KHz | 124 |
| MOD SRC 1 | See manual | 122 |
| MOD SRC 2 | See manual | 122 |
| DST 1 | See manual | 122 |
| DST 2 | See manual | 122 |
| MIN 1 | See manual | 122 |
| MIN 2 | See manual | 122 |
| MAX 1 | See manual | 122 |
| MAX 2 | See manual | 122 |

### ROM-30 — GUITAR AMP 3  (PDF p. 124)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| PREAMP GAIN | -48 to +48 dB | 124 |
| OUTPUT LEVEL | 0 to 99 | 124 |
| PRE-EQ TRIM | -24 to +00 dB | 124 |
| PRE-EQ FC | 0 to 9999 Hz | 125 |
| PRE-EQ GAIN | -48 to +24 dB | 125 |
| PRE-EQ Q | 1 to 18 | 125 |
| EXPANSION RATIO | 1:1 to 40:1, infinity | 125 |
| THRESHOLD | -96 to +0 dB | 125 |
| GATE OFF | -96 to +0 dB | 125 |
| GATE ON | -96 to +0 dB | 125 |
| GATE RELEASE | 1ms to 10.0s | 125 |
| HIGH PASS FC | 4 to 1000 Hz | 125 |
| EQ1 FC | 0 to 9999 Hz | 125 |
| EQ1 GAIN | -48 to +24 dB | 125 |
| EQ1 Q | 1 to 18 | 125 |
| EQ2 FC | 0 to 9999 Hz | 125 |
| EQ2 GAIN | -48 to +24 dB | 125 |
| EQ2 Q | 1 to 18 | 126 |
| LOW PASS FC | 2.0 to 15.0 KHz | 126 |
| MOD SRC 1 | See manual | 124 |
| MOD SRC 2 | See manual | 124 |
| DST 1 | See manual | 124 |
| DST 2 | See manual | 124 |
| MIN 1 | See manual | 124 |
| MIN 2 | See manual | 124 |
| MAX 1 | See manual | 124 |
| MAX 2 | See manual | 124 |

### ROM-31 — SPKR CABINET  (PDF p. 126)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| OUTPUT GAIN | -48 to +24 dB | 126 |
| MOD SRC 1 | See manual | 126 |
| MOD SRC 2 | See manual | 126 |
| DST 1 | See manual | 126 |
| DST 2 | See manual | 126 |
| MIN 1 | See manual | 126 |
| MIN 2 | See manual | 126 |
| MAX 1 | See manual | 126 |
| MAX 2 | See manual | 126 |

### ROM-32 — TUNABLE SPKR  (PDF p. 126)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| MID1 FC | 0 to 9999 Hz | 126 |
| MID1 GAIN | -48 to +24 dB | 126 |
| MID1 Q | 1 to 18 | 126 |
| MID2 FC | See manual | 126 |
| MID2 GAIN | -48 to +24 dB | 126 |
| MID2 Q | See manual | 126 |
| MID3 FC | See manual | 126 |
| MID3 GAIN | -48 to +24 dB | 126 |
| MID3 Q | See manual | 126 |
| INPUT TRIM | -24 to +0 dB | 127 |
| OUTPUT GAIN | -48 to +24 dB | 127 |
| MOD SRC 1 | See manual | 126 |
| MOD SRC 2 | See manual | 126 |
| DST 1 | See manual | 126 |
| DST 2 | See manual | 126 |
| MIN 1 | See manual | 126 |
| MIN 2 | See manual | 126 |
| MAX 1 | See manual | 126 |
| MAX 2 | See manual | 126 |

### ROM-33 — EQ+CHOR+DDL  (PDF p. 127)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| CHOR RATE | 0 to 99 | 128 |
| CHOR WIDTH | 0 to 99 | 128 |
| CHORUS CENTER | 0 to 99 | 128 |
| L/R LFO | OUT-OF-PHASE or IN-PHASE | 128 |
| DLY TIME L | 0 to 1500 ms | 128 |
| DLY TIME R | 0 to 1500 ms | 128 |
| DELAY REGEN | -99 to +99 | 128 |
| ECHOTIME L | 0 to 1500 ms | 128 |
| ECHOTIME R | 0 to 1500 ms | 128 |
| ECHO LEVEL | 0 to 99 | 128 |
| BASS FC | 0 to 1000 Hz | 128 |
| BASS GAIN | -48 to +24 dB | 128 |
| TREBLE FC | 01KHz to 15KHz | 128 |
| TREBLE GAIN | -48 to +24 dB | 128 |
| EQ TRIM | -24 to +00 dB | 129 |
| MOD SRC 1 | See manual | 127 |
| MOD SRC 2 | See manual | 127 |
| DST 1 | See manual | 127 |
| DST 2 | See manual | 127 |
| MIN 1 | See manual | 127 |
| MIN 2 | See manual | 127 |
| MAX 1 | See manual | 127 |
| MAX 2 | See manual | 127 |

### ROM-34 — EQ+VIBR+DDL  (PDF p. 129)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| VIBR RATE | 0 to 99 | 129 |
| WIDTH | 0 to 99 | 129 |
| L/R LFO | OUT-OF-PHASE or IN-PHASE | 130 |
| SAMPLE/HOLD RATE | 0 to 100 | 130 |
| DELAY TIME L | 0 to 1500 ms | 130 |
| DELAY TIME R | 0 to 1500 ms | 130 |
| DELAY FEEDBACK | -99 to +99 | 130 |
| ECHOTIME L | 0 to 1500 ms | 130 |
| ECHOTIME R | 0 to 1500 ms | 130 |
| ECHO LEVEL | 0 to 99 | 130 |
| BASS FC | 0 to 1000 Hz | 130 |
| BASS GAIN | See manual | 129 |
| TREBLE FC | 01KHz to 15KHz | 130 |
| TREBLE GAIN | See manual | 129 |
| EQ TRIM | -24 to +0 dB | 130 |
| MOD SRC 1 | See manual | 129 |
| MOD SRC 2 | See manual | 129 |
| DST 1 | See manual | 129 |
| DST 2 | See manual | 129 |
| MIN 1 | See manual | 129 |
| MIN 2 | See manual | 129 |
| MAX 1 | See manual | 129 |
| MAX 2 | See manual | 129 |

### ROM-35 — EQ+FLNGR+DDL  (PDF p. 131)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| FLANGE RATE | 0 to 99 | 131 |
| WIDTH | 0 to 99 | 131 |
| FLANGE CENTER | 0 to 99 | 131 |
| FLANGE FEEDBACK | -99 to +99 | 131 |
| NOTCH DEPTH | -99 to +99 | 131 |
| L/R LFO | OUT-OF-PHASE or IN-PHASE | 131 |
| SAMPLE/HOLD RATE | 0 to 100 | 131 |
| DLY TIME L | 0 to 1500 ms | 131 |
| DLY TIME R | 0 to 1500 ms | 131 |
| DELAY FEEDBACK | -99 to +99 | 132 |
| ECHO TIME L | 0 to 1500 ms | 132 |
| ECHO TIME R | 0 to 1500 ms | 132 |
| ECHO LEVEL | 0 to 99 | 132 |
| BASS FC | 0 to 1000 Hz | 132 |
| BASS GAIN | -48 to +24 dB | 132 |
| TREBLE FC | 1KHz to 15KHz | 132 |
| TREBLE GAIN | -48 to +24 dB | 132 |
| EQ TRIM | -24 to +0 dB | 132 |
| MOD SRC 1 | See manual | 131 |
| MOD SRC 2 | See manual | 131 |
| DST 1 | See manual | 131 |
| DST 2 | See manual | 131 |
| MIN 1 | See manual | 131 |
| MIN 2 | See manual | 131 |
| MAX 1 | See manual | 131 |
| MAX 2 | See manual | 131 |

### ROM-36 — EQ+TREM+DDL  (PDF p. 133)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BUS1 DLY AFT TREM | 0 to 99 | 133 |
| BUS2 DELAY MIX | See manual | 133 |
| TREM RATE | 0 to 99 | 133 |
| DEPTH | 0 to 99 | 133 |
| L/R LFO | OUT-OF-PHASE or IN-PHASE | 133 |
| SAMPLE/HOLD RATE | 0 to 100 | 133 |
| DLY TIME L | 0 to 1500 ms | 134 |
| DLY TIME R | 0 to 1500 ms | 134 |
| DELAY FEEDBACK | -99 to +99 | 134 |
| ECHO TIME L | 0 to 1500 ms | 134 |
| ECHO TIME R | 0 to 1500 ms | 134 |
| ECHO LEVEL | 0 to 99 | 134 |
| BASS FC | 0 to 1000 Hz | 134 |
| BASS GAIN | -48 to +24 dB | 134 |
| TREBLE FC | 1KHz to 15KHz | 134 |
| TREBLE GAIN | -48 to +24 dB | 134 |
| EQ TRIM | -24 to +0 dB | 134 |
| MOD SRC 1 | See manual | 133 |
| MOD SRC 2 | See manual | 133 |
| DST 1 | See manual | 133 |
| DST 2 | See manual | 133 |
| MIN 1 | See manual | 133 |
| MIN 2 | See manual | 133 |
| MAX 1 | See manual | 133 |
| MAX 2 | See manual | 133 |

### ROM-37 — PHASER+DDL  (PDF p. 134)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| PHASE RATE | 0 to 99 | 135 |
| WIDTH | 0 to 99 | 135 |
| PHASE CENTER | -99 to +99 | 135 |
| PHASER FEEDBACK | -99 to +99 | 135 |
| NOTCH DEPTH | -99 to +99 | 135 |
| L/R LFO | OUT-OF-PHASE or IN-PHASE | 135 |
| SAMPLE/HOLD RATE | 0 to 100 | 136 |
| DLY TIME L | 0 to 1600 ms | 136 |
| DLY TIME R | 0 to 1600 ms | 136 |
| DELAY FEEDBACK | -99 to +99 | 136 |
| MOD SRC 1 | See manual | 134 |
| MOD SRC 2 | See manual | 134 |
| DST 1 | See manual | 134 |
| DST 2 | See manual | 134 |
| MIN 1 | See manual | 134 |
| MIN 2 | See manual | 134 |
| MAX 1 | See manual | 134 |
| MAX 2 | See manual | 134 |

### ROM-38 — 8-VOICE CHOR  (PDF p. 136)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| LFO RATE | 0 to 99 | 137 |
| WIDTH | 0 to 99 | 137 |
| STEREO SPREAD | 0 to 99 | 137 |
| CHORUS REGEN | 0 to 99 | 137 |
| L REGEN TIME | 0 to 800 ms | 137 |
| R REGEN TIME | 0 to 800 ms | 137 |
| DELAY REGEN | 0 to 99 | 137 |
| MOD SRC 1 | See manual | 136 |
| MOD SRC 2 | See manual | 136 |
| DST 1 | See manual | 136 |
| DST 2 | See manual | 136 |
| MIN 1 | See manual | 136 |
| MIN 2 | See manual | 136 |
| MAX 1 | See manual | 136 |
| MAX 2 | See manual | 136 |

### ROM-39 — PITCH SHIFT  (PDF p. 137)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| VC 1 SEMI | -12 to +12 | 138 |
| VC 1 FINE | -99 to +99 | 138 |
| VC 1 VOL | 0 to 99 | 138 |
| VC 1 PAN | -99 to +99 | 138 |
| VC 2 SEMI | -12 to +12 | 138 |
| VC 2 FINE | -99 to +99 | 138 |
| VC 2 VOL | 0 to 99 | 138 |
| VC 2 PAN | -99 to +99 | 138 |
| QUALITY | LONG/SMOOTHER or SHORT/COARSER | 138 |
| LFO RATE | 0 to 99 | 138 |
| WIDTH | 0 to 99 | 138 |
| MOD SRC 1 | See manual | 137 |
| MOD SRC 2 | See manual | 137 |
| DST 1 | See manual | 137 |
| DST 2 | See manual | 137 |
| MIN 1 | See manual | 137 |
| MIN 2 | See manual | 137 |
| MAX 1 | See manual | 137 |
| MAX 2 | See manual | 137 |

### ROM-40 — PITCH+DDL  (PDF p. 139)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| VC 1 SEMI | -12 to +12 | 139 |
| VC 1 FINE | -99 to +99 | 139 |
| VOICE 1 VOL | 0 to 99 | 139 |
| VOICE 1 PAN | -99 to +99 | 139 |
| VC 2 SEMI | -12 to +12 | 140 |
| VC 2 FINE | -99 to +99 | 140 |
| VOICE 2 VOL | 0 to 99 | 140 |
| VOICE 2 PAN | -99 to +99 | 140 |
| DRY LEVEL TO DDL | 0 to 99 | 140 |
| DLY TIME L | 0 to 1500 ms | 140 |
| DLY TIME R | 0 to 1500 ms | 140 |
| DLY MIX | 0 to 99 | 140 |
| DLY REGEN | -99 to +99 | 140 |
| MOD SRC 1 | See manual | 139 |
| MOD SRC 2 | See manual | 139 |
| DST 1 | See manual | 139 |
| DST 2 | See manual | 139 |
| MIN 1 | See manual | 139 |
| MIN 2 | See manual | 139 |
| MAX 1 | See manual | 139 |
| MAX 2 | See manual | 139 |

### ROM-41 — FAST PITCHSH  (PDF p. 140)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| VOICE 1 FINE | -99 to +99 | 141 |
| VOICE 1 VOL | 0 to 99 | 141 |
| VOICE 1 PAN | -99 to +99 | 141 |
| VOICE 2 FINE | -99 to +99 | 141 |
| VOICE 2 VOL | 0 to 99 | 141 |
| VOICE 2 PAN | -99 to +99 | 141 |
| LFO RATE | 0 to 99 | 141 |
| WIDTH | 0 to 99 | 141 |
| MOD SRC 1 | See manual | 140 |
| MOD SRC 2 | See manual | 140 |
| DST 1 | See manual | 140 |
| DST 2 | See manual | 140 |
| MIN 1 | See manual | 140 |
| MIN 2 | See manual | 140 |
| MAX 1 | See manual | 140 |
| MAX 2 | See manual | 140 |

### ROM-42 — EQ+CMPRESSOR  (PDF p. 141)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| COMP GAIN | -48 to +48 dB | 142 |
| COMP RATIO | 1/1 to 40/1, infinity | 142 |
| COMP THRESHOLD | -96 to +0 dB | 142 |
| COMP ATTACK | 50µs to 100ms | 142 |
| COMP RELEASE | 1ms to 10.0s | 142 |
| GATE OFF | -96 to +0 dB | 142 |
| GATE ON | -96 to +0 dB | 142 |
| GATE RELEASE | 1ms to 10.0s | 142 |
| BASS FC | 0 to 1000 Hz | 142 |
| BASS GAIN | -48 to +24 dB | 142 |
| TREBLE FC | 1KHz to 15KHz | 142 |
| TREBLE GAIN | -48 to +24 dB | 142 |
| EQ TRIM | -24 to +0 dB | 142 |
| MOD SRC 1 | See manual | 141 |
| MOD SRC 2 | See manual | 141 |
| DST 1 | See manual | 141 |
| DST 2 | See manual | 141 |
| MIN 1 | See manual | 141 |
| MIN 2 | See manual | 141 |
| MAX 1 | See manual | 141 |
| MAX 2 | See manual | 141 |

### ROM-43 — EXPANDER  (PDF p. 144)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| EXPANSION RATIO | 1/1 to 1/40, INF | 144 |
| THRESHOLD | -96 to +0 dB | 144 |
| ATTACK TIME | 50µs to 100ms | 144 |
| RELEASE TIME | 1ms to 10.0s | 144 |
| HOLD TIME | 1ms to 10.0s | 144 |
| EQ GAIN | -48 to +48 dB | 144 |
| HIGH PASS FC | 4 to 8000 Hz | 144 |
| LOW PASS FC | 100 Hz to 15 KHz | 144 |
| TRIGGER MASK | OFF or ON | 145 |
| TRIGGER TIME | 1ms to 10.0s | 145 |
| MASK THRESHOLD | -96 to +0 dB | 145 |
| OUTPUT GAIN | -48 to +48 dB | 145 |
| MOD SRC 1 | See manual | 144 |
| MOD SRC 2 | See manual | 144 |
| DST 1 | See manual | 144 |
| DST 2 | See manual | 144 |
| MIN 1 | See manual | 144 |
| MIN 2 | See manual | 144 |
| MAX 1 | See manual | 144 |
| MAX 2 | See manual | 144 |

### ROM-44 — KEYED EXPNDR  (PDF p. 145)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| EXPANSION RATIO | 1/1 to 1/40, INF | 145 |
| THRESHOLD | -96 to +0 dB | 146 |
| ATTACK TIME | 50µs to 100ms | 146 |
| RELEASE TIME | 1ms to 10.0s | 146 |
| HOLD TIME | 1ms to 10.0s | 146 |
| EQ GAIN | -48 to +48 dB | 146 |
| HIGH PASS FC | 4 to 8000 Hz | 146 |
| LOW PASS FC | 100 Hz to 15 KHz | 146 |
| TRIGGER MASK | OFF or ON | 146 |
| TRIGGER TIME | 1ms to 10.0s | 146 |
| MASK THRESHOLD | -96 to +0 dB | 146 |
| OUTPUT MIX | 0 to 99 | 146 |
| OUTPUT GAIN | -48 to +48 dB | 146 |
| MOD SRC 1 | See manual | 145 |
| MOD SRC 2 | See manual | 145 |
| DST 1 | See manual | 145 |
| DST 2 | See manual | 145 |
| MIN 1 | See manual | 145 |
| MIN 2 | See manual | 145 |
| MAX 1 | See manual | 145 |
| MAX 2 | See manual | 145 |

### ROM-45 — INVRS EXPNDR  (PDF p. 147)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| EXPANSION RATIO | 1/1 to 40/1, INF | 147 |
| THRESHOLD | -96 to +0 dB | 147 |
| ATTACK TIME | 50µs to 100ms | 147 |
| RELEASE TIME | 1ms to 10.0s | 147 |
| GATE OFF | -96 to +0 dB | 147 |
| GATE ON | -96 to +0 dB | 147 |
| BASS FC | 0 to 1000 Hz | 147 |
| BASS GAIN | -48 to +24 dB | 147 |
| TREBLE FC | 1KHz to 15KHz | 147 |
| TREBLE GAIN | -48 to +24 dB | 147 |
| EQ TRIM | -24 to +0 dB | 148 |
| MOD SRC 1 | See manual | 147 |
| MOD SRC 2 | See manual | 147 |
| DST 1 | See manual | 147 |
| DST 2 | See manual | 147 |
| MIN 1 | See manual | 147 |
| MIN 2 | See manual | 147 |
| MAX 1 | See manual | 147 |
| MAX 2 | See manual | 147 |

### ROM-46 — DE-ESSER  (PDF p. 148)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| OUTPUT GAIN | -48 to +48 dB | 148 |
| COMP RATIO | 1/1 to 40/1, INF | 148 |
| THRESHOLD | -96 to +0 dB | 148 |
| ATTACK TIME | 50µs to 100ms | 148 |
| RELEASE TIME | 1ms to 10.0s | 149 |
| GATE OFF | -96 to +0 dB | 149 |
| GATE ON | -96 to +0 dB | 149 |
| HIGH PASS FC | 4 to 8000 Hz | 149 |
| BASS FC | 0 to 1000 Hz | 149 |
| BASS GAIN | -48 to +24 dB | 149 |
| MID1 FC | 0 to 9999 Hz | 149 |
| MID1 GAIN | -48 to +24 dB | 149 |
| MID1 Q | 1 to 18 | 149 |
| MID2 FC | See manual | 148 |
| MID2 GAIN | -48 to +24 dB | 149 |
| MID2 Q | See manual | 148 |
| TREBLE FC | 1KHz to 15KHz | 149 |
| TREBLE GAIN | -48 to +24 dB | 149 |
| EQ TRIM | -48 to +0 dB | 149 |
| MOD SRC 1 | See manual | 148 |
| MOD SRC 2 | See manual | 148 |
| DST 1 | See manual | 148 |
| DST 2 | See manual | 148 |
| MIN 1 | See manual | 148 |
| MIN 2 | See manual | 148 |
| MAX 1 | See manual | 148 |
| MAX 2 | See manual | 148 |

### ROM-47 — DUCKER  (PDF p. 150)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| OUTPUT GAIN | -48 to +48 dB | 150 |
| OUTPUT MIX | 0 to 99 | 150 |
| COMP RATIO | 1/1 to 40/1, INF | 150 |
| THRESHOLD | -96 to +0 dB | 150 |
| ATTACK TIME | 50µs to 100ms | 150 |
| RELEASE TIME | 1ms to 10.0s | 151 |
| GATE OFF | -96 to +0 dB | 151 |
| GATE ON | -96 to +0 dB | 151 |
| BASS FC | 0 to 1000Hz | 151 |
| BASS GAIN | -48 to +24 dB | 151 |
| MID1 FC | 0 to 9999 Hz | 151 |
| MID1 GAIN | -48 to +24 dB | 151 |
| MID1 Q | 1 to 18 | 151 |
| MID2 FC | See manual | 150 |
| MID2 GAIN | -48 to +24 dB | 151 |
| MID2 Q | See manual | 150 |
| TREBLE FC | 1KHz to 15KHz | 151 |
| TREBLE GAIN | -48 to +24 dB | 151 |
| HIGH PASS FC | 4 to 8000 Hz | 151 |
| EQ TRIM | -48 to +0 dB | 151 |
| MOD SRC 1 | See manual | 150 |
| MOD SRC 2 | See manual | 150 |
| DST 1 | See manual | 150 |
| DST 2 | See manual | 150 |
| MIN 1 | See manual | 150 |
| MIN 2 | See manual | 150 |
| MAX 1 | See manual | 150 |
| MAX 2 | See manual | 150 |

### ROM-48 — RUMBLE FILTR  (PDF p. 152)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| HIGH PASS FC | 4 to 8000 Hz | 152 |
| LOW PASS FC | 100 Hz to 15 KHz | 152 |
| FILTER GAIN | -48 to +48 dB | 152 |
| MOD SRC 1 | See manual | 152 |
| MOD SRC 2 | See manual | 152 |
| DST 1 | See manual | 152 |
| DST 2 | See manual | 152 |
| MIN 1 | See manual | 152 |
| MIN 2 | See manual | 152 |
| MAX 1 | See manual | 152 |
| MAX 2 | See manual | 152 |

### ROM-49 — PARAM EQ  (PDF p. 152)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| BASS FC | 0 to 1000 Hz | 152 |
| BASS GAIN | -48 to +24 dB | 152 |
| MID1 FC | 0 to 9999 Hz | 152 |
| MID1 GAIN | -48 to +24 dB | 152 |
| MID1 Q | 1 to 18 | 152 |
| MID2 FC | See manual | 152 |
| MID2 GAIN | -48 to +24 dB | 152 |
| MID2 Q | See manual | 152 |
| TREBLE FC | 1 to 15 KHz | 153 |
| TREBLE GAIN | -48 to +24 dB | 152 |
| EQ TRIM | -24 to +0 dB | 153 |
| MOD SRC 1 | See manual | 152 |
| MOD SRC 2 | See manual | 152 |
| DST 1 | See manual | 152 |
| DST 2 | See manual | 152 |
| MIN 1 | See manual | 152 |
| MIN 2 | See manual | 152 |
| MAX 1 | See manual | 152 |
| MAX 2 | See manual | 152 |

### ROM-50 — VAN DER POL  (PDF p. 153)

| Original control / disambiguated label | Manual range | PDF page |
|---|---|---:|
| HIGH PASS FC | 4 to 8000 Hz | 153 |
| LOW PASS FC | 100 Hz to 15 KHz | 153 |
| FILTER GAIN | -48 to +48 dB | 153 |
| MOD SRC 1 | See manual | 153 |
| MOD SRC 2 | See manual | 153 |
| DST 1 | See manual | 153 |
| DST 2 | See manual | 153 |
| MIN 1 | See manual | 153 |
| MIN 2 | See manual | 153 |
| MAX 1 | See manual | 153 |
| MAX 2 | See manual | 153 |

## Additional twelve 44 kHz effect algorithms (manual appendix)

**Not part of the original ROM-01...ROM-50 numbering.** The appendix supplies names and separate alphabetized range definitions (PDF pp. 377–382). Expand/reconcile ranges before implementing a control.

### 44LUSH PLATE  (PDF p. 368)

DECAY TIME, PREDELAY TIME, HF DAMPING, BW, DETUNE RATE, DEPTH, DEFINITION, DIFFUSION 1, DIFFUSION 2, ER TIME L, ER TIME R, ER LEVEL L, ER LEVEL R.

### 44LUSH PLAT2  (PDF p. 368)

DECAY TIME, PREDELAY TIME, HF DAMPING, BW, DETUNE RATE, DEPTH, DEFINITION, DIFFUSION 1, DIFFUSION 2.

### 44PERC PLATE  (PDF p. 368)

DECAY TIME, PREDELAY TIME, HF DAMPING, BW, DETUNE RATE, DEPTH, DEFINITION, DIFFUSION 1, DIFFUSION 2, ER TIME L, ER TIME R, ER LEVEL L, ER LEVEL R.

### 44EQ+DDL  (PDF p. 369)

EQ IN, OUT, GAIN BASS, TREB, MID, GAIN, MID BW, ECHO WET, DRY, ECHOTIME L, ECHOTIME R, ECHO REGEN L, ECHO REGEN R, CROSS REGN L, CROSS REGN R.

### 44DDL+CH+REV  (PDF p. 370)

REVERB MIX, DECAY TIME, ECHO SEND, PREDELAY TIME, REGEN, HF DAMPING, ECHOTIME L, ECHOTIME R, BW, CH RATE, DEFINITION, DIFFUSION, CH DRY LEV, PAN, CH WET LEV 1–3, CH WET PAN 1–3, CH LFORATE 1–3, CH WIDTH 1–3, CH DELAY 1–3, EXPERT PARAMS, FDBK T, TIME L, TIME R, GAIN L, GAIN R.

### 44DDL+CHORUS  (PDF p. 371)

ECHO LEV, CH RATE, REGEN, ECHOTIME L, ECHOTIME R, CH LFO SPREAD, CH WET, CH WIDTH, DRY, DELAY.

### 44DLYLFO+REV  (PDF p. 372)

REVERB MIX, BW, DL WET, DEFINITION, DRY, DIFFUSION 1, DIFFUSION 2, DL RATE, REGEN, EXPERT PARAMS, DL WIDTH L, DL WIDTH R, FDBK T, DL DELAY L, DL DELAY R, TIME L, TIME R, DECAY TIME, PREDELAY TIME, GAIN L, GAIN R, HF DAMPING.

### 44EQ+DDL+CHO  (PDF p. 373)

EQ IN, OUT, EQ FREQ, GAIN, EQ BW, ECHO LEV, REGEN, ECHOTIME L, ECHOTIME R, CH RATE, CH DRY LEV, PAN, CH WET LEV 1–3, CH WET PAN 1–3, CH LFORATE 1–3, CH WIDTH 1–3, DELAY 1–3.

### 44PARAM EQ  (PDF p. 373)

BASS FC, GAIN (BASS), MID FC, GAIN (MID), MID Q, TREBLE FC, GAIN (TREBLE), INPUT TRIM.

### 44EQ+REVERB  (PDF p. 374)

REVERB MIX, DEFINITION, EQ IN, DIFFUSION 1, DIFFUSION 2, OUT, EQ FREQ, GAIN, EXPERT PARAMS, EQ BW, FDBK T, DECAY TIME, TIME L, PREDELAY TIME, TIME R, HF DAMPING, BW, GAIN L, GAIN R.

### 44ROTO+REVRB  (PDF p. 375)

REVERB MIX, PREDELAY TIME, SPKR WET, HF DAMPING, DRY, BW, SPEED, DEFINITION, INERTIA, DIFFUSION 1, DIFFUSION 2, SPEED MIN, SPEED MAX, AM MIN, AM MAX, FM MIN, FM MAX, EXPERT PARAMS, FDBK T, TIME L, TIME R, GAIN L, GAIN R, DECAY TIME.

### 44EQ+ROT+DDL  (PDF p. 376)

EQ IN, OUT, EQ FREQ, GAIN, EQ BW, SPKR WET, ECHO WET, DRY, SPEED, ECHOTIME L, ECHOTIME R, INERTIA, ECHO REGEN L, ECHO REGEN R, SPEED MIN, SPEED MAX, CROSS REGN L, CROSS REGN R, AM MIN, AM MAX, FM MIN, FM MAX.

## Recommended Codex implementation tracker schema

For **each parameter** maintain separate columns: `manual_name`, `manual_range`, `manual_pdf_page`, `variation`, `OS_raw_domain`, `display_to_raw_policy`, `OS_capture`, `GPR_write_group`, `runtime_implemented`, `VST_callback_test`, `audio_AB_test`, `Force_touchscreen_test`, `Force_QLink_test`, `saved_state_compatibility`, `blockers`.

Prioritize ROM-01 HALL REVERB first. Manual parameters are DECAY TIME, LOW FREQ DECAY, DIFFUSION, HI FREQ DAMPING, HI FREQ BANDWIDTH, DETUNE RATE, DETUNE AMT, and PRE-DELAY TIME. HALL DECAY is already user-tested across 0–99 on Candidate 3. Other HALL mappings and effects are *not* automatically confirmed.

Do not publish the copyrighted manual PDF in the public repository. This guide contains only names, numerical ranges and source-page references.