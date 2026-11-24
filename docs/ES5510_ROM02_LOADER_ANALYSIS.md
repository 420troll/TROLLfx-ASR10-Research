# OS 3.53 ROM-02 44KHZ REVERB loader and timing

## Result and evidence scope

Two independent native-emulator processes booted from the private ASR-10 boot
ROM pair and OS 3.53 image, swept the effect selector, loaded ROM-02, and ran
the program. This is emulator evidence, not a physical ASR-10 measurement.
All boot ROMs, OS images, EFE exports, instruction/register values, raw traces,
full ESP captures, WAVs, Ghidra projects, and REA evidence remain outside Git.
The committed changes contain only redacted facts, hashes, counts, and trace
instrumentation.

The two runs agree on the selection, HALT, DRAM-clear, transfer, RUN, first
frame, and post-RUN timing coordinates. They also agree on the instruction
commit hash, full halted GPR/SPR transaction hash, EFE correlation, serial
frame hashes, measured DSP frame rate, and rendered WAV format. The active
program SHA-256 is `12119e86d4d232ab7d7ab4278e9c9dbed9db19a6b6eb352bfb29441181da4486`.
The hash of the private ROM-02 EFE export used only for source correlation is
`21562a079f5e1bf3d14cfeebfd9a7ef1afc0e5cb0edff788e4308d3552186f75`.
The private ordered instruction-commit stream hash is
`7627bd3f453acf7086e65ac2dc28531d2c938050c8e338516c778aa2f641b493`;
the ordered 283-write halted register stream hash is
`c592004db5c72843bee2951473f63a5f3c1a3199f93ff32a3a33d6287b2a0f83`.
These hashes identify streams without disclosing their contents.

## ROM-02 image and microprogram

The OS display settles on `ROM-02 44KHZ REVERB` at CPU cycle `444756026`,
ESP frame `899137`. This is a selection marker, not the load boundary. The
last-write-wins DSP image at the subsequent RUN boundary has 60 active words,
with END at program counter `0x3B` (decimal 59). During the halted transfer the
firmware issues 61 instruction commits to 60 unique addresses; address `0x3A`
is committed twice. The complete ordered instruction stream is stable across
both fresh boots.

The private EFE export correlation validates all 60 active instruction words
against the live image. It resolves 58 paired GPR/instruction source records,
one instruction-only source record, and a source alias from active index 58 to
index 0. The 61st host commit is explained by the repeated destination at
`0x3A`; it must not be counted as another active instruction. The EFE layout
also has an 11-byte prefix, a three-byte gap, and a 42-byte trailing region.
These offsets describe the private exported object examined in this run, not
portable file-format constants. No program words or EFE bytes are reproduced.

The total halted transaction contains 283 register commits: 224 GPR-only and
59 combined instruction/GPR writes. The distinction matters: 58 paired values
are source-correlated initializers, while the full 283-write stream is the
observed OS transaction. Do not replace it with only the 58 EFE pairs for a
guarded replay.

## ROM-02 load event sequence

The capture records 16 MHz MC68302 CPU cycles and the emulator's monotonic
`run_frame()` counter. The 1 ms CLI display timestamp is omitted because it is
not the source coordinate.

| Event | CPU cycle | ESP frame | Evidence |
|---|---:|---:|---|
| ROM-02 display stable | 444,756,026 | 899,137 | UI selection; prior DSP run is still active |
| PA4 HALT asserted / HALT accepted | 446,994,146 | 903,301 | Host PC `0xFFF977B0` / accepted at `0xFFF977B8` |
| Pipeline reset | 446,994,146 | 903,301 | Pending ALU/MAC cleared, three RAM pipeline slots cleared, DOL count reset |
| DRAM clear command | 446,994,304 | 903,301 | Host PC `0xFFF97756` writes F5=`0xFFFF00`, then `0xFFF9775C` clears 1,048,576 modeled 16-bit words |
| Instruction upload begins | 447,610,410 | 904,447 | Host PC `0xFFF97792`, destination 0 |
| Memory configuration SPR write | 447,669,138 | 904,556 | PC `0xFFF97792`, F4=`0x0000FF` |
| Delay-length SPR write | 447,669,766 | 904,557 | PC `0xFFF97792`, F5=`0xFFFFFF`; repeated at cycle 447,763,842 / frame 904,732 |
| Last instruction-only upload commit | 447,766,328 | 904,737 | Host PC `0xFFF97792`, destination 59; the earlier instruction-only write targets 58 |
| Last halted register commit | 447,841,488 | 905,001 | Host PC `0xFFF97792`, destination `0x7F` |
| PA4 RUN released | 447,850,934 | 905,027 | Host PC `0xFFF977C6` |
| Upload summary / DSP RUN | 447,851,290 | 905,028 | Host PC `0xFFF9763A`; 61 commits, 60 unique words, END 59, 283 register commits |
| First serial input latch | 447,851,290 | 905,028 | host serial mode `0x48`; input on SER2 lanes 4/5 |
| First DSP instruction | 447,851,290 | 905,028 | PC `0x00` |
| First END | 447,851,290 | 905,028 | PC `0x3B`, 60 instructions executed |
| First completed DSP frame / output checkpoint | 447,851,290 | 905,028 | output on SER1 lanes 2/3; checkpoint follows END in log order |

The first input and output checkpoints have matching lane-state hashes in both
boots. The event logger now emits `first_end` and `first_frame_complete`
markers in addition to the existing load and serial markers. These markers
record log order and frame coordinates; the emulator does not advance its CPU
cycle counter inside `run_frame()`, so equal cycle values within that frame do
not mean the instruction executed at one physical silicon clock edge.

The HALT-to-clear interval is 158 CPU cycles. The upload starts 616,106 cycles
after the clear. RUN release precedes the first DSP frame by 356 CPU cycles.
Selection-to-HALT spans 2,238,120 CPU cycles and 4,164 ESP frames. These are
stable emulator coordinates across both captures.

## GPR, SPR, memory, and routing state

The observed ROM-02 halted transaction writes the following special
registers:

| SPR | Writes during transaction | Verified effect at RUN |
|---|---:|---|
| `F4` (memory configuration) | 1 (`0x0000FF`) | `MEMSHIFT=8`, `MEMSIZ=0x0000FF`, `MEMMASK=0xFFFF00`, `MEMINCR=0x000100` |
| `F5` (delay length) | 2 (`0xFFFFFF` each) | `DLENGTH=0xFFFFFF`; the preceding clear preamble also writes `0xFFFF00` before clear |
| `F8` (delay base) | 0 | At first RUN the inherited/live `DBASE` is `0xF0CA00` |

At RUN, `ABASE=0`, `BBASE=0`, and `SIGREG=0xFFFFFF`. The ROM-02 selection
transaction does not commit serial SPRs or `F8`; `host_serial=0x48` and DBASE
are inherited state, not proof of an effect-local initializer. DRAM is zeroed
before upload and remains at that cleared boundary until RUN. DBASE then
advances with DSP execution. The absence of a ROM-02 `F8` write is material to
standalone replay: a cold independent replay must reproduce the observed
`0xF0CA00` run-boundary base or explicitly model the prior host/runtime state.

The serial route observed in the first frame is input SER2 (lanes 4/5) and
output SER1 (lanes 2/3). Host serial mode is `0x48`. Ghidra's cold-start
routine sets this mode; no ROM-02-specific serial SPR commit was observed.

## Clock and host-output timing

At the ROM-02 display marker, the previous DSP mode still measures
`29,761.895 Hz` (`15,238,090 Hz` OTTO clock, 31 active voices). That rate must
not be attributed to the ROM-02 program: HALT and upload occur later.

For the actual ROM-02 RUN, the two first post-RUN host writes span cycles
`447851758` / frame `905029` through cycles `454047624` / frame `922106`.
Across 6,195,866 CPU cycles the ESP frame counter advances 17,077 frames,
which gives a measured average of `44,099.08 frames/s` using the emulator's
16 MHz CPU counter. The stable result is approximately 44,100 DSP frames/s.
Both rendered WAVs are stereo PCM16 at exactly 44,100 Hz. The numbers match
within scheduler quantization, but the boundaries are distinct: OTTO schedules
ESP frames, while the host DAC path emits/resamples PCM frames.

## EFE-to-runtime and post-RUN firmware writes

The source comparison is against the private `44KHZ REVERB` EFE exported from
the factory ROM selection. It proves that the EFE's active program and 58
paired GPR initializers match the live ROM-02 image; it does not prove the
ROM's internal address or caller pointer. The captured display and program
correlation identify the selected effect, while the exact effect-record source
pointer passed to firmware register `A3` remains unavailable.

After RUN, each observed host write in the measured interval uses PC
`0xFFF97792`. From cycle `447851758` / frame `905029` to cycle
`454047624` / frame `922106`, the trace contains 202 register writes. The most
frequent destinations are GPR `0x7F` (111), `0x7C` (33), and `0x7D` (33); the
remaining writes target other GPRs. These events are retained as ordered host
transactions; their full semantics are not established by the address alone.

A separate controlled ROM-02 UI edit previously mapped `REVERB MIX BUS2` to
GPR `0x7A`; the reversible commits also came from writer PC `0xFFF97792`.
The effect-object updater offsets `0x0452`, `0x0564`, and `0x0468`, and its
service call at `$801E`, are EFE-object offsets / an unresolved service entry,
not OS ROM addresses. They remain a decompiler-based dataflow hypothesis for
how that parameter reaches the common firmware writer.

The fresh sequence selects HALL at cycle `418325634` / frame `849885` and runs
its 89-word image at cycle `421550606` / frame `855973`. It then selects ROM-02
at cycle `444756026` / frame `899137` and performs the transaction above.
This confirms the HALL-to-ROM-02 direction performs a new HALT, clear, upload,
and RUN. ROM-02-to-HALL was not exercised in these two captures.

## REA / Ghidra findings and dynamic correspondence

REA 6.9.0 used its Ghidra 12.1.4 provider on the private interleaved 256 KiB
68000 boot ROM (high lane then low lane; loaded at `0xFFF80000`). The ROM image
SHA-256 is `fe290ea4e52e7c9d229cc6e19529fdc6e5b33e74ddfcd54345660121a19cabbf`.
Trace-seeded headless Ghidra analysis was run in a private project because the
default analysis had not listed several runtime-observed helpers. It
identified:

| Address | Static finding | Dynamic correspondence |
|---|---|---|
| `0xFFF97346` | Cold-start DSP initialization; calls the HALT and host-base helpers, clears/initializes host-visible DSP state, sets host serial mode `0x48` | Startup setup; not ROM-02's selector caller |
| `0xFFF973F0` | Generic effect-record parser/transfer/verification entry; accepts a record pointer via A3 and loops over record types/counts | The exact ROM-02 A3 pointer and callsite were not recorded |
| `0xFFF97744` | HALT / DRAM-clear preamble | Trace records clear at PC `0xFFF9775C` |
| `0xFFF97776` | Shared indexed host-port writer and ready polling | All 61 ROM-02 instruction commits and the observed runtime writes use PC `0xFFF97792` |
| `0xFFF97662` | Shared register exchange / retry helper | Static helper used by generic transfer and register verification |
| `0xFFF977B0` | PA4 HALT helper | Dynamic HALT observed at `0xFFF977B8` |
| `0xFFF977C6` | PA4 RUN release helper | Dynamic RUN release at `0xFFF977C6`; control write at `0xFFF977D2` |

The function names are analyst labels, not firmware symbols. The generic
loader's parsed record format and transfer loops are decompiler evidence; the
ROM-02 run trace proves the host-port behavior and values at the ESP boundary,
but it does not capture the MC68302 A3 source pointer, full caller chain, or
all 68k register values. No ROM-02-specific wrapper is assigned from address
proximity alone. The HALL-to-ROM-02 event correlation verifies a common
low-level transfer path, not the exact effect selector branch.

## Unresolved replay fields and targeted captures

The current evidence is a repeatable load boundary and initialization ledger,
not a complete standalone save state. The fields below are the remaining gaps
for guarded standalone replay:

1. **ROM-02 record pointer / bank source:** exact A3 value, caller PC, and
   ROM-bank/object range at the `0xFFF973F0` call. Add a 68k trace at that entry
   and its callers capturing PC, A3, D0-D7, A0-A6, and the return address; pair
   it with the record-copy source address range. Keep values private.
2. **Inherited DBASE and startup state:** the first RUN uses `DBASE=0xF0CA00`
   without a ROM-02 F8 commit. Repeat after forcing a clean startup HALL run
   and after loading ROM-02 directly from a controlled alternate prior DSP
   program; capture F8 and DRAM at clear, upload, and RUN boundaries.
3. **Halted register image completeness:** retain the exact 283 ordered GPR /
   SPR writes outside Git and compare them with a replay applying all records.
   The 58 EFE initializer pairs alone are incomplete.
4. **Reverse effect switching:** run HALL → ROM-02 → HALL → ROM-02 in one
   process, plus repeat in two fresh processes. Capture each HALT/clear/upload/
   RUN boundary and DBASE transition to determine whether the reverse switch
   uses the same state and record loader.
5. **ROM-02-specific clock selector:** log OTTO master clock, active-voice
   count, DSP frame count, and CPU cycle count at the exact RUN release and
   through several thousand frames. Current evidence measures about 44.1 kHz
   from cycle/frame deltas; the `ESP_ROM_SELECT` clock fields are sampled
   before the load and report the prior mode.
6. **Parameter-update service:** while changing `REVERB MIX BUS2`, log the
   68k call/return path, argument registers, object pointer, and PC at the
   `0xFFF97792` transaction. This would resolve how the EFE updater hypothesis
   maps to GPR `0x7A` and separate it from periodic runtime maintenance writes.
7. **Physical behavior:** no host-emulator record establishes the physical
   ES5510 sampling edge or silicon clock. A hardware capture is still needed
   for silicon equivalence claims.

## Reproduction

Build the native research CLI with the private assets outside the repository.
For each independent run, use a new output directory and fresh CLI process:

```sh
bash tools/build_research_cli.sh

python3 - <<'PY'
import os, subprocess
from pathlib import Path

repo = Path.cwd()
roms = Path('/private/asr10/roms')
out = Path('/private/results/rom02-boot1')
out.mkdir(parents=True, exist_ok=False)
args = [str(repo/'build/research-cli/asr10-cli'), '--roms', str(roms),
        '--disk', str(roms/'os353.img'), '--seconds', '34',
        '--button', '15:7:1', '--button', '15.2:7:0',
        '--esp-dump', str(out/'final.esp'),
        '--esp-snapshot-rom-dir', str(out/'romsnapshots'),
        '--wav', str(out/'render.wav')]
for value in range(8, 96):
    time = 16 + (value - 8) * .15
    args += ['--analog-at', f'{time:.2f}:5:{value}']
env = os.environ.copy()
env.update({'ASR_ROUTE':'-1,-1,1,-1,0', 'ASR_TEST_SINE':'440:0.25',
            'ESP_HOSTLOG':'1', 'ESP_PIPELOG':'1', 'ESP_FRAMELOG':'1',
            'ESP_FRAMELOG_START_FRAME':'905028'})
with (out/'trace.log').open('wb') as log:
    subprocess.run(args, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
PY

python3 tools/hall_load_boundary.py \
  /private/results/rom02-boot1/trace.log \
  --output /private/results/rom02-boot1/redacted.json
python3 tools/compare_asr10_effect_capture.py \
  /private/effects/ROM02-44KHZ.payload.bin \
  /private/results/rom02-boot1/final.esp \
  /private/results/rom02-boot1/trace.log \
  --expected-name '44KHZ REVERB'
```

Repeat with a new output path and independent process. The two-boot results in
this report were captured on 2026-11-24; captures and output artifacts are
stored privately under the matching `rom02-loader-analysis` results folder.
