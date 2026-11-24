# ES5510 delay-RAM address disagreement

## Finding

The first native/MAME request mismatch is at DSP frame 0, PC `0x02`, while executing the captured factory HALL program. Both request delay RAM (`ram access=0`, cycle `2`, read). Native requests word `0x25AB`; the MAME-derived engine requests word `0x25AA`.

This is caused by the delay-ring wrap calculation, not by signed arithmetic, addition order before masking, or the final word shift in isolation. The engines apply the ring modulus in different units. Native converts the aligned base and 24-bit offset to words, then wraps over `floor(DLength / MEMINCR) + 1` words. MAME follows upstream's byte-domain expression `(DBase + offset) % (DLength + MEMINCR)` before masking and shifting. For the captured full-range DLength `0xFFFFFF` with MEMINCR `0x100`, that MAME modulus is `0x10000FF`, 255 bytes larger than the 16 MiB ring. A wrapped byte address can therefore land one 256-byte word earlier after the mask and shift.

## First divergence state and arithmetic

The exact diagnostic trace and RUN checkpoint establish:

| Field | Value |
|---|---:|
| Frame / PC | `0` / `0x02` |
| Instruction | `0xEE7BFFFF9168` |
| RAM operation | Delay FIFO read, RAM control `5`, access `0`, cycle `2` |
| Address offset source | GPR[PC], GPR[2] = `0x7C0000` |
| DBase | `0xA9AB00` |
| DLength | `0xFFFFFF` |
| MEMSHIFT / MEMINCR / MEMMASK | `8` / `0x100` / `0xFFFF00` |
| DRAM | 1,048,576 words, zeroed at RUN boundary |

The offset is positive here; its sign bit is clear. The 24-bit mask has no effect on it. No signed conversion is involved.

**Native (`src/es5510.cpp`, delay case):**

```text
len = (DLength >> shift) + 1
    = 0xFFFFFF >> 8 + 1 = 0x10000 words
w   = (DBase >> 8) + ((offset & 0xFFFFFF) >> 8)
    = 0xA9AB + 0x7C00 = 0x125AB
wrap: 0x125AB - 0x10000 = 0x25AB
mask: 0x25AB & (0xFFFF00 >> 8) = 0x25AB
request word = 0x25AB
```

**MAME-derived adapter (`third_party/trollfx_mame_es5510/mame_es5510_standalone.cpp`):**

```text
length = DLength + MEMINCR = 0xFFFFFF + 0x100 = 0x10000FF bytes
sum    = DBase + offset = 0xA9AB00 + 0x7C0000 = 0x125AB00
mod    = 0x125AB00 % 0x10000FF = 0x25AA01
mask   = 0x25AA01 & 0xFFFF00 = 0x25AA00
shift  = 0x25AA00 >> 8 = 0x25AA
request word = 0x25AA
```

This reproduces the trace exactly. The instruction and offset are the same in both engines. On the following request, differing DIL data and later state are consequences, not the initial cause.

## Formula comparison

For delay accesses, the native implementation is equivalent to:

```text
S = 1 << MEMSHIFT
L_words = floor(DLength / S) + 1
A_native = ((floor(DBase / S) + floor((offset & 0xFFFFFF) / S)) mod L_words)
           & (MEMMASK / S)
```

The MAME-derived adapter and current upstream MAME use:

```text
A_mame = (((DBase + offset) mod (DLength + MEMINCR)) & MEMMASK) >> MEMSHIFT
```

The HALL configuration has aligned DBase, offset, and DLength low bits for the 256-byte granularity. Thus the difference is not ordinary byte/word alignment loss; it is the modulus. `DLength + MEMINCR` is not rounded or masked before modulo. With `DLength=0xFFFFFF`, `MEMINCR=0x100`, it is `0x10000FF`, whereas the aligned byte span implied by the native word count is `0x1000000` bytes. At addresses that do not wrap the two expressions agree; at this wrapped address they do not.

For table A/B, the implementations also differ in expression form: native masks the base before adding the offset and masks the sum; MAME adds first, then masks. With the hardware-consistent aligned values exercised here these are equal modulo the mask. I found no evidence that table addressing causes this first mismatch.

## Minimal reproductions

The following arithmetic-only vectors isolate delay address generation. Each assumes `MEMSHIFT=8`, `MEMINCR=0x100`, `MEMMASK=0xFFFF00`, with the result reported in DRAM words. Offset values are 24-bit GPR contents; `0xFFFF00` represents a negative one-word offset in 24-bit two's-complement notation.

| DLength | DBase | Offset | Native | MAME | What it isolates |
|---:|---:|---:|---:|---:|---|
| `FFFFFF` | `A9AB00` | `7C0000` | `25AB` | `25AA` | Authentic first mismatch; wrapped, nonzero positive offset |
| `FFFFFF` | `A9AB00` | `000000` | `A9AB` | `A9AB` | Nonzero base without wrap |
| `FFFFFF` | `001000` | `000200` | `000012` | `000012` | Nonzero offset without wrap |
| `FFFFFF` | `A9AB00` | `FFFF00` | `A9AA` | `A9AA` | Negative one-word offset, no wrap below zero |
| `000FFF` | `001000` | `000200` | `000002` | `000001` | Small 16-word ring, positive wrap |
| `FFFFFF` | `000000` | `FFFFFF` | `FFFF` | `FFFF` | End-of-range value before the next address increment |

The `000FFF` case shows the mismatch is not specific to the factory base or program: the native ring has `(0xFFF >> 8)+1 = 16` words, while MAME takes modulo `0x10FF` bytes and subsequently discards the low byte. The first four vectors also distinguish wrap behavior from low-bit alignment and signed-offset handling.

An instruction-level reproducer needs only a one-instruction delay read at PC `0x02` with GPR[2] set to the chosen offset, and the stated DBase/DLength/MEMSHIFT values. The other instruction slots and DRAM contents do not affect the request coordinate. To exercise the END address increment, add one `MEMINCR` (`0x100` bytes, one word) to DBase and rerun the vectors; for example, factory DBase becomes `0xA9AC00` and the same offset yields native `0x25AC` versus MAME `0x25AB`. This predicted next-base result follows directly from the expressions; it has not been observed on physical silicon.

## Documentation, history, and independent evidence

The publicly indexed [Ensoniq ESP (ES5510) Technical Specification v2.4](https://zine.r-massive.com/ensoniq-technical-documents-and-schematics/) and unofficial ESP microcode programming guide are available through Google Drive, but their contents were not accessible to text inspection in this investigation. I therefore cannot claim that either document specifies inclusive DLength semantics or resolves this discrepancy.

The [upstream MAME ES5510 source](https://github.com/mamedev/mame/blob/master/src/devices/cpu/es5510/es5510.cpp) contains the same delay equation as the adapter: modulo by `dlength + memincrement`, followed by MEMMASK and MEMSHIFT. Upstream's log text describes its length as `(dlength + memincrement) >> memshift`, but that diagnostic does not establish that modulo is performed in word units. This implementation history is independent code, but not independent silicon evidence; MAME itself notes that ES5510 DRAM size is unverified. The vendored adapter derives from MAME commit `8be57cdc5f44ab830dff44c06dd39f24190742d` (per the existing audio-validation audit).

The OS 3.53 replay reference matches native exactly, but its emulator uses the same native ES5510 core, so it is not independent arithmetic evidence. The checked-in replay notes and available captures contain no physical-chip address trace or independently measured sample proving either address. REA/Ghidra examination is not applicable to this arithmetic discrepancy: it could establish firmware register setup, already captured here, but cannot disclose internal silicon wrap behavior.

The arithmetic and exact first mismatch are high-confidence. Which behavior matches silicon remains unresolved. Native's word-count formula is consistent with a ring of aligned words and with rounding the number of addressable words from an inclusive final byte address. MAME's formula is a direct upstream implementation precedent. Neither fact alone is proof of chip behavior. No production correction is justified by the available independent evidence.

## Discriminating hardware experiment

Use a physical ES5510 with a minimal halted-load/run microprogram and known memory state:

1. Configure `MEMSHIFT=8`, `DLength=0xFFFFFF`, `DBase=0xA9AB00`; initialize the candidate DRAM words around `0x25AA`, `0x25AB`, and the non-wrapping control region to distinct values.
2. Set the PC-indexed delay offset to `0x7C0000`; issue one delay read and route DIL unchanged to an observable serial output. Repeat with a nearby no-wrap offset as a control.
3. Capture the output and compare against both candidate word signatures. Repeat with the 16-word synthetic ring (`DLength=0x000FFF`, base `0x001000`, offset `0x000200`) if the board's memory setup permits it.
4. Repeat after one END/DBase increment and with a negative offset (`0xFFFF00`). This checks whether address generation wraps before or after increment and whether the low 24-bit offset is treated unsigned.

The data values must be made unique across candidate words, and the measurement must observe the first read result before later instructions overwrite DIL or the output path. A known physical-unit test would resolve whether silicon returns the `0x25AA` or `0x25AB` signature. Until then, preserve both behaviors behind the existing separate engines and treat this case as a known divergence.

## Reproduction and test status

The address vectors above are small deterministic calculations from the two checked-in formulas. The factory trace came from the private V4 diagnostic capture under `/home/gamer/research/private-results`; no capture, program binary, firmware, or ROM was copied into Git. The investigation did not add production arithmetic changes. `python3 -m unittest discover -s tests -v` passed all 47 tests.
