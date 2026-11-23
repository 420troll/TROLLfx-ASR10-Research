# Factory EFE reconstruction, version 2

## Scope and evidence

This report compares private OS 3.53 exports for ROM-01 HALL REVERB and
ROM-02 44KHZ REVERB with their native-emulator ES5510 captures and host-write
logs. It also records one controlled ROM-02 parameter edit. ROM/EFE files,
firmware, raw logs, captures, and WAVs remain outside Git. This is emulator
evidence; no physical ASR-10 comparison was performed.

## EFE layouts confirmed against runtime

The comparator correlates every active instruction with the capture and
last-write-per-index host commits. For combined transactions it also checks
the source's preceding three-byte GPR initializer against the host GPR value.
Boundaries and gaps are inferred from matching offsets; the parser does not
assume a fixed prefix, gap, suffix, or record count.

| Effect | Active program | Source records validated | Source geometry | Runtime result |
|---|---:|---|---|---|
| ROM-01 HALL REVERB | 89 instructions, END at 88 | 86 paired GPR/instruction; 3 instruction-only | prefix 11 bytes; gap 3; suffix 50 | 89/89 instruction commits match; all 86 paired GPR values match |
| ROM-02 44KHZ REVERB | 60 instructions, END at 59 | 58 paired GPR/instruction; 1 instruction-only; 1 instruction alias | prefix 11 bytes; gap 3; suffix 42 | 60/60 instruction commits match; all 58 paired GPR values match |

ROM-02 differs from the HALL structure in both active program length and its
source/run association. Its host load sequence has 58 combined commits followed
by two instruction-only commits. The first of those final instructions has no
second physical source record: it is byte-identical to active instruction 0
and resolves to that earlier source location. The final instruction maps to a
new standalone source record. The parser reports this as an alias (active index
58 to source active index 0), not as another initializer. The alias is a
source-to-runtime observation and does not explain why the loader emits the
extra commit.

The verified ROM-01 standalone export was loaded back from disk and its
instructions and paired values matched again. ROM-02 was explicitly selected
as `ROM-02 44KHZ REVERB`, copied to Bank, and exported as a code-bearing EFE;
its source was correlated with the live ROM-02 capture. A ROM-02 disk reload
was not independently validated. The documented OS sequence is to select the
ROM effect, run `COPY CURRENT EFFECT` with direction `COPY TO BANK`, then
`SAVE BANK EFFECT` as a separate effect file. `COPY TO INST` is a distinct
destination and was not used for these exports.

The capture-comparison parser is [compare_asr10_effect_capture.py](../tools/compare_asr10_effect_capture.py).
The geometry checker [decode_efe_layout.py](../tools/decode_efe_layout.py)
validates starts and counts supplied from that runtime comparison; it does
not invent them. Both reject out-of-bounds layouts and ambiguous source
locations. Synthetic coverage includes paired/instruction-only layouts,
repeated words, a repeated-source alias, and ambiguous-object failure.

Example private commands (keep JSON output outside the repository):

```sh
python3 tools/compare_asr10_effect_capture.py \
  /private/ROM01-HALL.payload.bin /private/ROM01-HALL-live.esp \
  /private/ROM01-HALL-export.log --expected-name 'HALL REVERB'

python3 tools/compare_asr10_effect_capture.py \
  /private/ROM02-44KHZ.payload.bin /private/ROM02-44KHZ-live.esp \
  /private/ROM02-44KHZ-export.log --expected-name '44KHZ REVERB'

python3 tools/decode_efe_layout.py /private/ROM02-44KHZ.payload.bin \
  --paired-start 811 --paired 58 --instruction-start 1336 \
  --instruction-only 1 --alias 58:0
```

The numerical offsets above are evidence for this private ROM-02 object, not
portable format constants. Use the comparator output from the matching object
and capture to supply them.

## Factory initialization manifest

The checked-in machine-readable summary is
[FACTORY_EFFECT_INITIALIZATION_MANIFEST.json](FACTORY_EFFECT_INITIALIZATION_MANIFEST.json).
It lists observed transaction sections and marks unknown state explicitly.
The ES5510 capture format records 160 instruction slots, 192 GPRs, 22 SPRs,
74 bytes of selected control/latch state, and 1,048,576 DRAM words. These
captures were taken after selection and ongoing DSP processing. They are not
cold-start images or fully resumable save states.

Host logs contain GPR-only, instruction-only, combined, and special-register
writes. The paired values in the table above are the GPR initializers that can
be attributed to source records. The larger GPR-only stream includes OS and
runtime activity and is not a verified effect initializer table. Host writes
were observed for serial SPRs `SER0R` through `SER3L`, plus `DIL`, `DLENGTH`,
`DBASE`, and `SIGREG`; their effect-specific necessity and initial values are
unknown. Other SPR state is present in captures but cannot be assigned to
effect setup from a post-run snapshot.

The two post-run captures have different GPR, SPR, serial sample, MAC, DBASE,
and DRAM state. Each DRAM snapshot contains nonzero words. The host logs have
no explicit host-side RAM transaction in the selected setup windows. This does
not capture DSP-side delay-memory writes or establish the cold-start DRAM
contents. Serial routing was controlled by the emulator input route for audio
tests; the exact factory serial routing setup sequence is unresolved. The
capture omits in-flight instruction, RAM, and ALU pipelines. Those fields must
be initialized or allowed to settle by an actual loader/runtime sequence
before a factory-faithful replay can be claimed.

No separate “Agent 5 loader” implementation or reproducible cold-start
manifest was present in the inspected branches. Existing loader notes confirm
effect selection, source-correlated host writes, and a running DSP, but not
address-resolved OS file-loader instructions. See
[ASR10_LIVE_LOADER_FINDINGS.md](ASR10_LIVE_LOADER_FINDINGS.md). Factory
accuracy is not claimed.

## Controlled ROM-02 parameter mapping

With ROM-02 selected, the Edit/Effects page showed `REVERB MIX BUS2=25`. One
Up action changed it to `26`; Down restored `25`; another Up returned it to
`26`. The reversible host destination was GPR `0x7a`. Its raw 24-bit host
values changed from `0x350000` to `0x370000`, back to `0x350000`, then to
`0x370000`. These values document only this one-step sample; they do not
establish the full scale or interpolation rule. Adjacent GPR `0x7b` was
rewritten with an unchanged value. GPR `0x6d` changed once during the first
edit window but did not follow the down/up repetition, so it is left
unassigned.

The matched no-edit control had zero host commits in all three edit windows.
The edited run had two commits for the reversible down and repeated-up
windows, with only GPR `0x7a` changing in each. The first increase window had
597 host commits, including a broad rewrite; only `0x7a` followed the complete
reversible pattern. This prevents treating the other startup/rewrite events
as parameter destinations. The mapped commits were emitted by host-writer PC
`0xfff97792`; the final GPR `0x7a` update after the first increase was observed
at ES5510 frame 1,047,499, with the reverse and repeated increase at frames
1,092,445 and 1,136,604. The control and edited audio were bit-identical
through 30 seconds before the edit. In the first one-second window containing
the increase, their PCM16 difference had RMS about 6,266 and peak 14,494.
This establishes a measurable output change, not a subjective quality claim
or a general loudness direction. The reverb tail means restoring the parameter
does not restore prior delay-memory history immediately.

Reproduction used the private verified OS 3.53 setup, the native CLI,
`ESP_HOSTLOG=1`, a 440 Hz sine input and the same emulator route for both
runs. Open FX Select, sweep the selector from raw value 8 through 90, confirm
the display says `ROM-02 44KHZ REVERB`, then enter Edit, Effects, and advance
to `REVERB MIX BUS2`. Place cycle/frame markers around one Up, one Down, and a
repeat Up. Analyze with:

```sh
python3 tools/parameter_host_diff.py private.log \
  --before before_up --after after_up
```

Repeat the same UI sequence with no edits as a control. Keep the source logs
private; the tool omits written values unless `--include-values` is requested.

## Unresolved questions

- What OS loader routines read each EFE segment, emit the ROM-02 alias commit,
  initialize serial routing, and populate delay memory?
- Which GPR-only writes belong to a clean factory initialization sequence?
- What are the cold-start GPR/SPR/DRAM values, and what clear/fill sequence is
  required before execution?
- How should in-flight ES5510 pipelines and frame-boundary ordering be
  reproduced?
- What are the full parameter scaling curves and click-suppression behavior
  for ROM-01/ROM-02 controls?
- Does ROM-02 reload from its exported disk EFE reproduce its ROM-selected
  capture?

Until these are answered, the manifest is evidence of observed state coverage,
not an executable factory initialization recipe.
