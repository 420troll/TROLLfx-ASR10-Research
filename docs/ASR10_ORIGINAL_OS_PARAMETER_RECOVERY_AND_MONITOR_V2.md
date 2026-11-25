# Original OS Parameter Recovery and Monitor V2

## Result summary

The supplied ASR-10 Musician's Manual was available at `/mnt/c/Users/Gamer/Downloads/23583406.pdf` (391 pages). Sections 5 and 6 and the Appendix beginning at PDF page 368 were inspected locally. The PDF and extracted full text remain outside Git.

The existing Section 6 catalog is complete against the supplied manual text: regeneration produced 50 effects and 594 descriptors, with no parameter/range differences from `ASR10_FACTORY_PARAMETER_CATALOG_V1.json`. The prior OS editor inventory covers 49 effects (slot 02 remains deferred), with 1,040 live LCD field associations. It reports 585 documented descriptors among the 49 scanned effects, 491 exact/alias matches and 94 descriptor entries still unmatched for review. These are different counts from OS-only associations: those include modulation, bus mix, and variation fields that are not separate Section 6 direct-effect descriptors. Do not treat the 94 unmatched manual entries as proven absent controls.

The manual Appendix documents 12 additional Version 2 44 kHz algorithms, not 12 more numbered ROM slots. A separate manual-only catalog now records 215 parameter field headings with their Appendix ranges, variations, expert groups, algorithm-specific differences, and live-verification status. It has no guessed OS2 editor ordering or DSP mapping. ROM-02 remains deferred.

HALL DECAY TIME's original OS display domain has been traversed through all 100 values, but the full display-to-DSP mapping is not established. Existing exact 40/41 points remain supported by V2 capture/runtime evidence and produce an audible native-runtime difference under the earlier test. A fresh CPU-attributed trace identifies the parameter-operation dispatcher and the conversion routines used for that point. It also shows that the coefficient input is a hidden OS value, not the displayed 0–99 integer. No production DSP mapping was changed and no full-range control is promoted.

## Manual-to-inventory discrepancy report

| Evidence source | Coverage | Interpretation |
|---|---:|---|
| Section 6 catalog | 50 effects / 594 descriptors | Exact regeneration match to the existing catalog; no discrepancy found in labels or ranges. |
| V4 OS field inventory | 49 effects / 1,040 field associations | Slot 02 intentionally deferred. Captures multiple variations and cursor/value fields, including fields not represented as direct Section 6 descriptors. |
| Manual descriptors matched by V4 | 491 of 585 in scanned effects | Exact labels or known aliases were seen. The remaining 94 are review items, not proof that the OS omits them. |
| OS-only association labels | 76 unique labels / 500 observations in the inventory | Includes modulation source/destination/range fields, BUS mixes and composite/abbreviated aliases. Examples include `MOD SRC1`, `DST1`, `MIN1`, `MAX1`, `BUS1 MIX`, and `BUS2 MIX`; these are not automatically new direct algorithm parameters. |
| Appendix | 12 OS2 additional 44 kHz algorithms / 215 field headings | Separate namespace/catalog. Appendix descriptions are documentation, not proof that the local OS2 build exposes these fields or that an ES5510 mapping is known. |

The manual says there are four variations and two modulation source/destination assignments in addition to algorithm parameters (Section 5, pp. 99–100 in the supplied PDF). The catalog already represents the four-variation selector and eight common modulation fields at shared scope. The V4 captures show their effect-specific availability and repeated observations. Therefore they must not be counted as replacements for direct effect parameters. The manual's parameter headings sometimes group independent controls, such as left/right delay values and numbered chorus voices; the Appendix catalog retains these as distinct fields. Similar labels are not merged across algorithms when the manual gives different limits.

The Codex 2 Force editor branch `feature/asr10-force-effect-dependent-editor-v4.1` (reviewed from remote commit history) retains the 50-slot/594-descriptor catalog and currently routes 19 runtime-ready controls. The new 44 kHz Appendix catalog is an additive file; it does not renumber the original slots, VST controls, or existing parameter IDs.

## Appendix / 44 kHz coverage matrix

Parameter counts below count manual-listed field headings. A heading with `(1-3)` or `(1-4)` also specifies a numbered group of distinct controls; the JSON records group size. `EXPERT PARAMS` is a manual section/group, not itself a DSP control. Four variations are listed for each algorithm.

| Appendix effect | PDF page | Field headings | Notable distinct fields / exceptions | Status |
|---|---:|---:|---|---|
| 44LUSH PLATE | 368 | 13 | ER time and level, L/R; second diffusion | Manual only |
| 44LUSH PLAT2 | 368 | 9 | ER time and level are explicitly unavailable | Manual only |
| 44PERC PLATE | 368 | 13 | Decay range 0.40–1.21 sec, unlike other listed reverbs | Manual only |
| 44EQ+DDL | 369 | 15 | EQ plus independent L/R echo time, regen, cross-regen | Manual only |
| 44DDL+CH+REV | 370 | 34 | Three chorus voice levels, pans, LFO rates, widths and delays; four-tap expert groups | Manual only |
| 44DDL+CHORUS | 371 | 11 | Separate chorus/delay regeneration, L/R echo times, LFO spread | Manual only |
| 44DLYLFO+REV | 372 | 21 | L/R delay rate, width and delay; two diffusers; four-tap expert groups | Manual only |
| 44EQ+DDL+CHO | 373 | 27 | EQ, delay and three individually listed chorus voices | Manual only |
| 44PARAM EQ | 373 | 8 | Three EQ bands, separate frequency/Q/gain fields and input trim | Manual only |
| 44EQ+REVERB | 374 | 18 | EQ plus reverb and four-tap expert groups | Manual only |
| 44ROTO+REVRB | 375 | 23 | Separate speed min/max, AM/FM min/max, inertia and reverb controls | Manual only |
| 44EQ+ROT+DDL | 376 | 23 | EQ, rotary and independent L/R echo/cross-regeneration fields | Manual only |

The complete labels and range citations are in [ASR10_OS2_44KHZ_APPENDIX_PARAMETER_CATALOG_V1.json](ASR10_OS2_44KHZ_APPENDIX_PARAMETER_CATALOG_V1.json), reproducibly built by `tools/parameter_controls/build_44khz_appendix_catalog.py`. It contains 215 field headings, all with an Appendix range entry. Group indexing preserves multiple voices and tap controls without claiming that a multi-control heading is a single runtime parameter.

## Original OS conversion path observed for HALL DECAY TIME

The live OS 3.53 run exposed an operation-byte dispatcher in RAM. The disassembly at `0x71C2` is:

```text
71C2  lea     ($8,A3),A2
71C6  moveq   #0,D0
71C8  move.b  (A2)+,D0
71CA  beq     71E4
71CC  cmp.w   #$1e,D0
71D0  bge     71E4
71D2  asl.w   #2,D0
71D4  movea.w #$8048,A0
71D8  movea.l (A0,D0.w),A0
71DC  jsr     (A0)
71DE  moveq   #0,D0
71E0  move.b  (A2)+,D0
71E2  bra     71CA
71E4  rts
```

This is a small bytecode interpreter. Each nonzero operation byte selects a handler through the table at `0x8048`; handlers consume an effect/parameter descriptor and can issue multiple ordered ES5510 writes. This establishes why treating a display number as a direct GPR scalar or fitting two sampled points is unsafe. The full table and raw OS memory are private and are not checked into Git.

CPU-attributed host-write evidence for the observed HALL edit includes:

- Host writer: `0xFFF97792`; common caller return observed at `0xFFF97694`.
- Parameter conversion helper: `0xFFF97960` clamps/scales its descriptor input and calls `0xFFF97998`; a related packed-field helper begins at `0xFFF9792C`.
- For displayed 40, the live parameter structure at A6 had byte `A6+0 = 0x34` (52) while `A6+3 = 0x28` (40). During the transition to displayed 41, `A6+0` became `0x35` while `A6+3` still showed 40 at the write instant. Thus the displayed value, the internal coefficient, and UI display-refresh state are separate evidence.
- The established 40 point write group is `GPR 6E=340000`, `5B=080034`, `03=340000`, `04=CC0000`, `05=6ADFFF`; the 41 point is `6E=350000`, `5B=080035`, `03=350000`, `04=CB0000`, `05=6A0DFF`. The 40→41 native audio comparison from the earlier validated checkpoint produced nonzero stereo difference (difference RMS about 0.000403 left / 0.000433 right over 144,000 frames). This verifies those points, not the whole range.
- For the captured 40→41 change, CPU host-write coordinates were frame 905055 / cycle 447882720 (GPR 6E) through frame 905065 / cycle 447888466 (GPR 05). Writes were issued at PC `0xFFF97792`, with caller return `0xFFF97694`, in the order `6E,5B,03,04,05`. At the first write A6 held raw coefficient `0x35` while the stored display byte at A6+3 was still `0x28` (40). The matching probe recorded LCD `DECAY TIME=40` then `DECAY TIME=41`; its CPU snapshot demonstrates that the coefficient was already updated before the display field caught up.

The three derived coefficients are consistent with the original 68000 helper arithmetic for raw coefficient `c` stored in A6: `x = c << 8`; `GPR03 = x << 8`; `GPR04 = -GPR03` in 24-bit form; and `GPR05 = (0x3fffffff - x*x) arithmetic-shift-right 7`, masked to 24 bits. At `c=0x34`, this gives `0x340000`, `0xCC0000`, and `0x6ADFFF`. This is a conversion from the internal coefficient to three DSP coefficients. It is not the missing conversion from displayed 0–99 to the internal coefficient.

## HALL DECAY TIME 0–99 status

The latest UI range run visited 0 through 99 and returned to the starting displayed value, with 200 one-step transitions in variation 1. After correcting the host-event parser to accept the optional `caller=...` field introduced by the CPU tracing instrumentation, the existing raw range log was reparsed without repeating the OS run. That restored the actual per-step GPR event windows and confirmed direction-dependent raw coefficients at 28 of the 98 interior displayed values. At every differing point, the descending route's GPR `0x6E` coefficient is exactly one code above the ascending route. The differing display values are `1, 4, 8, 12, 15, 19, 22, 26, 29, 33, 36, 40, 44, 47, 51, 54, 58, 62, 65, 69, 72, 76, 79, 83, 86, 90, 94, 97`. The other 70 interior values match. For example, display 40 has raw codes `0x33` (ascending) and `0x34` (descending); display 65 has `0x53` and `0x54`. This is now event-level measurement, not stale full-register snapshots.

The raw internal code is not the displayed integer: at display 40 the OS writes GPR `0x6E=0x330000` or `0x340000` depending on route, while the parameter structure stores the display byte separately. This is consistent with an integer display quantizing a finer internal code, but it does not establish whether the exact behavior is a deliberate stateful conversion, a particular rounding rule, or a lookup table. The CPU trace also captures a delayed display refresh after a coefficient write. The one-code route difference is real in the captured OS event history; its algorithmic cause remains unresolved.

| Check | Result |
|---|---|
| Manual UI range | 0–99, documented |
| OS full-range display traversal | Complete; 100 displayed values observed and baseline restored |
| Exact adjacent DSP points | 40/41 verified across three repeated reversible OS edits; the ordered five-GPR write group is identical on all trials |
| CPU conversion path | Operation-byte dispatcher and downstream coefficient helpers located; bytecode handler chain not fully decoded |
| Register evidence across all values | Per-transition host GPR windows recovered from the existing raw log; 28/98 interior displays have a one-code route difference, so there is no unique static map |
| Fresh-load / min / max / randomized route comparison | Not yet completed with CPU snapshots synchronized to every LCD update |
| Audio validation across 100 values | Not done |
| Runtime status | No new full-range mapping; existing exact-point behavior unchanged |

The next decisive capture should repeat selected ambiguous targets from a fresh effect load, minimum, maximum and randomized prior values while recording each panel edit, the A6 raw parameter byte immediately before its handler, the A2 bytecode stream/handler PCs, and ordered writes from that same CPU action. It should identify whether the displayed target selects one of two adjacent coefficient codes based on the current hidden code or whether the OS later normalizes them. This separates an intentional stateful edit rule from a value-formatting/lookup-table detail.

## Live monitor and CPU trace tooling

`tools/asr10_os_monitor/monitor.py` serves a local-only dashboard at `http://localhost:8765`, starts a separate instrumented OS 3.53 CLI session, shows the exact 22-character LCD and cursor/underline, and injects real front-panel events on the emulator thread. It labels navigation/page changes separately from parameter-value changes and presents ordered host GPR events and register deltas. The bounded in-memory event ring is 3,000 entries. Raw emulator output is not served.

Set `"cpu_trace": true` in a private copy of `config.example.json` to enable targeted CPU snapshots around HALL decay GPR writes. The browser receives PC, SP and A2/A3/A6 addresses only. `extract_os_cpu_parameter_trace.py` accepts a private log and emits paired CPU/register JSON to a requested private output path; it supports older CPU snapshots without memory windows and newer A2/A6 memory snapshots. The V5 host-event parser now accepts optional CPU caller attribution and correctly reparses both GPR and paired instruction/GPR records. A prior evidence summary made while the caller field was present omitted those events; the summary has been regenerated from the same raw private log, not from a new emulator run. The current monitor starts a separate emulator process rather than attaching to a pre-existing GUI instance; it does not modify the emulator display or apply DSP values itself.

Build and launch from this worktree:

```sh
bash tools/build_research_cli.sh
cp tools/asr10_os_monitor/config.example.json /home/gamer/research/private-results/asr10-os-monitor-config.json
# Edit that private config with the authorized local CLI, ROM, OS disk, selector inventory and evidence paths.
python3 tools/asr10_os_monitor/monitor.py --config /home/gamer/research/private-results/asr10-os-monitor-config.json
```

For expanded CPU evidence, run:

```sh
ESP_CALLER_TRACE=1 python3 tools/parameter_controls/run_factory_dsp_mapping_probe_v05.py \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --selector-inventory /home/gamer/research/private-results/asr10-all-50-effects/inventory.json \
  --slot 1 --variation 1 --field 'DECAY TIME' --repetitions 3 \
  --output /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/caller-trace-mem
python3 tools/parameter_controls/extract_os_cpu_parameter_trace.py \
  --input /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/caller-trace-mem/slot-01-var1-decay-time.log \
  --output /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/caller-trace-mem/parsed-cpu-trace.json
```

The command is a tracing recipe, not a full-range validation test. The latest private trace parser run produced 172 targeted CPU snapshots matched to 172 of 4,848 host GPR writes; it had no structured LCD lines because that run used the mapping probe rather than `--monitor-stdio`. Combine it with the monitor/full-sweep logging for synchronized UI evidence.

## Evidence classification and unresolved assumptions

- **Directly measured in OS 3.53:** 0–99 LCD traversal, exact 40/41 displayed values, CPU PC/register snapshots, A6 internal byte examples, ordered GPR values, observed stale display byte at the host write.
- **Established from emulator code/disassembly:** 0x71C2 bytecode dispatch loop, handler vector lookup at 0x8048, host transfer PC and arithmetic in the inspected helper routines.
- **Audio verified:** the previously accepted 40/41 native-runtime comparison produced finite, measurably different stereo output. It does not prove every full-range setting is valid or factory-accurate.
- **Inferred:** displayed integer maps through OS parameter-specific state/handler operations to a separate internal coefficient. The observed trace strongly supports that distinction.
- **Unresolved:** why the same display reached by opposite directions yielded one-code raw coefficient differences in earlier sweeps; whether the difference is intended hysteresis or capture timing; the exact full 0–99 display-to-coefficient curve; and OS2 live edit behavior for Appendix effects.
- **Not done:** no new mapping was promoted, no production DSP arithmetic or factory checkpoint was changed, and no Force installation or rollback artifact was touched.

## Focused tests and build

```sh
python3 -m unittest tests.test_asr10_os_monitor \
  tests.parameter_controls.test_44khz_appendix_catalog \
  tests.parameter_controls.test_full_factory_parameter_registry \
  tests.parameter_controls.test_factory_dsp_mapping_probe_v05 -v
```

Validation completed:

- `bash tools/build_research_cli.sh` — passed; the CLI rebuilt with the optional monitor and CPU caller trace. Existing `-Wmisleading-indentation` warnings in `asr10.cpp` and `m68302.cpp` remain.
- `python3 -m unittest tests.test_asr10_os_monitor tests.parameter_controls.test_44khz_appendix_catalog tests.parameter_controls.test_full_factory_parameter_registry tests.parameter_controls.test_factory_dsp_mapping_probe_v05 -v` — 29 tests passed.
- `python3 -m unittest discover -s tests -p 'test_*.py' -v` — 87 tests passed in 63.529 seconds.
- Real local monitor smoke: `/`, `/api/status`, and `/api/events?after=0` returned HTTP 200 from the OS emulator process. Port 8765 was already occupied by an existing simulator; this smoke used 8766 and did not interrupt that process.
- `python3 tools/parameter_controls/build_catalog.py --manual-text /tmp/asr10-manual-full.txt --inventory /home/gamer/research/private-results/asr10-all-50-effects/inventory.json --output /tmp/parameter-catalog-regenerated.json` — generated 50 effects / 594 descriptors; zero differences from the checked-in Section 6 catalog.
- `python3 tools/parameter_controls/build_44khz_appendix_catalog.py --output docs/ASR10_OS2_44KHZ_APPENDIX_PARAMETER_CATALOG_V1.json` — generated 12 algorithms / 215 field headings; every heading has a range entry and remains manual-only.
