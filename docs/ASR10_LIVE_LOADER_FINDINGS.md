# ASR-10 live ES5510 loader findings

**Status:** one OS 3.53 factory effect selection was reproduced in the alternate
ASR-10 emulator CLI, captured, correlated to its private EFE object, and replayed
through the separate MAME-derived TROLLfx executor. This is emulator evidence;
it is not a physical ASR-10 capture.

## REA and Ghidra availability

REA was not callable in this Codex session. The local Codex configuration has an
`mcp_servers.rea` entry for `rea-agents@6.9.0`, but the active tool registry
contains no REA/Ghidra methods and the visible MCP resource list contains no REA
server. No REA process was running. I did not install or relaunch REA.

The Ghidra user-state directory exists, but its saved Java path points to
`/tmp/dp4-rom-forensics/tooling/jdk/jdk-21.0.13+9`, which is no longer present.
No `analyzeHeadless` or `ghidraRun` executable was found in the checked local
install/config paths. Existing private project/log files remain on this PC.
Accordingly, this pass uses the existing static reports, private firmware
objects, and the executed emulator's host-write logs; it does not claim a new
Ghidra/REA decompilation of the OS loader.

## Reproducible capture

The fork's source base is the alternate emulator commit
`0112e3e6b503dcc840436c918849dae40b7bc2e9`. The changed native CLI was built
locally from the fork and run with the private verified ASR-10 boot ROMs and OS
3.53 image. The test selected `44DDL+CHORUS` from the OS Effects directory,
injected a 440 Hz test sine into the selected DSP input, and saved the CLI host
log, full ES5510 capture, and stereo WAV outside the repository.

Rebuild only the headless CLI (no CMake, SDL app, VST, or MAME build):

```sh
tools/build_research_cli.sh
```

Example invocation (replace paths with private local paths):

```sh
ASR_ROUTE=-1,-1,1,-1,0 ASR_TEST_SINE=440:0.25 ESP_HOSTLOG=1 \
  build/research-cli/asr10-cli \
  --roms /private/asr10/roms \
  --disk /private/asr10/roms/os353.img \
  --seconds 25 \
  --button 15:9:1 --button 15.2:9:0 \
  --button 15.5:35:1 --button 15.7:35:0 \
  --wav /private/captures/44DDL-chorus.wav \
  --esp-list --esp-dump /private/captures/44DDL-chorus.esp \
  > /private/captures/44DDL-chorus.log 2>&1
```

The private run showed the selected name `44DDL+CHORUS`, followed by
`DISK COMMAND COMPLETED`. The host logger recorded 1,718 events (437 combined
instruction/GPR commits, 1,247 GPR-only events, and 34 instruction-only events).
After resolving last-write-wins for each program index, all 60 active
instructions exactly matched the full state capture at indices 0–59. The first
END was at index 59. The private 60-word program SHA-256 is
`ff6ef8fcc7b5ec12b965f601ce71f3563ad65c16bfc0b523b4040b80261e2cc0`. The
full capture is 2,098,872 bytes (SHA-256
`a9eca102ea11462eb9126b79e5659baa2f7b748148ed2d09f853d4e93c940c1c`); its
GPR, special-register and DRAM section hashes are recorded privately in the
sidecar summary and not reproduced here.

The capture file contains all 160 instruction slots, 192 GPR values, 22 special
register readbacks, the runtime memory/control configuration, serial/MAC
state, and the full 1,048,576-word external DRAM image. It is a processor-state
snapshot, not a fully resumable CPU save state: transient execution pipelines
and the 68k CPU state are not serialized. The capture and raw host log remain
private and are not tracked by Git.

The WAV is 44.1 kHz stereo PCM16, 1,103,686 frames, peak 9,506, RMS 3,762.955,
and 944,689 nonzero samples. Its SHA-256 is
`76867a1732fb94f7175e0156761aad856af5b5df2920eadc251c9dd69b975ea6`, matching
the earlier corrected Windows CLI render. A second native render produced the
same WAV hash. The effect selection, 60-word program and nonzero render are
repeatable.

The built-in OS 3.53 `HALL REVERB` selection was also repeated. It yielded 89
active instructions, END at index 88, a full register/DRAM capture, and a
nonzero 44.1 kHz stereo render (peak 9,492; RMS 3,380.145). Its WAV hash
`63f7e10c8eee746220e8d125262ca47f9fbd859812250240c77eb3b5694f07b4` matches the
prior private Windows render. The display establishes the selected built-in
HALL name; the CLI does not emit a separate effect-table identifier.

After building the native CLI, both selections can be checked in one command;
it refuses to write captures beneath the repository:

```sh
tools/run_private_effect_smokes.sh \
  /private/asr10/roms \
  /private/asr10/roms/os353.img \
  /private/asr10/captures/repeat
```

## Why the static scan said 90 words but the live program has 60

The private OS 3.53 EFE object is 3,584 bytes including block padding. Its
header says `FxSize=3161` (`0x0c59`) and `FxUcode=0x0a3c`. Counting every six
bytes from `FxUcode` to `FxSize` gives 90 complete six-byte chunks plus one
trailer byte. That arithmetic treated a mixed object region as a plain
instruction stream.

The live 60-word program correlates byte-for-byte with the source object in a
mixed layout:

| Source range / rule | Live records | Host operation observed |
|---|---:|---|
| GPR at `0x0a47 + 9*i`; instruction at `0x0a4a + 9*i`, `i=0..28` | 29 | Combined instruction/GPR commit to matching index; all 29 source GPR values match the host log |
| Instruction at `0x0b4f + 6*(i-29)`, `i=29..59` | 31 | Instruction-only commits; all 31 words match the host log |

The total EFE extent therefore includes an 11-byte prefix before the first
paired record, 29 nine-byte GPR/instruction records, a three-byte unclassified
gap, 31 six-byte instructions, and an 80-byte unclassified suffix. The 29
paired records account for 174 instruction bytes plus 87 GPR bytes. The 31
instruction-only records account for 186 instruction bytes. The 60 live
instructions total 360 bytes.

The captured instruction byte ranges appear unchanged in the EFE object; the
loader path observed here selects those ranges and skips interleaved fields.
This is a verified source-to-host mapping for the selected object in this
emulator run. The 11-byte prefix, three-byte gap, and 80-byte suffix are not
decoded here. The exact firmware code that chooses this split layout has not
yet been mapped to a main-OS loader routine. The object-local `FxUcode` field
is not itself the start of a flat 48-bit instruction array.

The comparison can be regenerated without printing program bytes or parameter
values:

```sh
python3 tools/compare_asr10_effect_capture.py \
  /private/effects/01_44DDL+CHORUS.payload.bin \
  /private/captures/44DDL-chorus.esp \
  /private/captures/44DDL-chorus.log \
  --expected-name '44DDL+CHORUS'
```

The tool checks the selected object name, capture bounds, contiguous active
program, last host commits, unique source locations, paired GPR values, and
the two observed source strides. It emits counts, hashes and offsets only.

Validation on the native development build:

- `python3 -m unittest discover -s tests -v` — 5 tests passed.
- Strict capture-writer test compiled with `-Wall -Wextra -Wpedantic -Werror` — passed.
- Individual `sh -n` checks of both shell scripts — passed.
- `tools/run_private_effect_smokes.sh ...` — 44DDL+CHORUS (60 words) and
  HALL REVERB (89 words) both passed selection, capture, WAV format and nonzero
  audio checks; repeated output hashes matched the previous CLI renders.
- The native headless CLI build succeeded. Existing warnings remain in
  `asr10.cpp:447` and `m68302.cpp:214` for misleading indentation; no compiler
  error was emitted.

## Loader and parameter-update path

The emulator's executed OS selection plus host log is the strongest evidence
for the loader dataflow so far: OS 3.53 selects the named effect, commits its
program words through the ES5510 host protocol, initializes paired GPRs, and
leaves a running program with a captured memory configuration and DRAM state.
It is not yet an address-level disassembly of the OS's file parser or transfer
routine.

The existing private static analysis of the EFE object identifies
`FxUpdateTask=0x0452`. It calls helper `0x0564`, which computes an object-relative
pointer around `FxUcode`, then calls updater `0x0468` twice. That updater reads
parameter-relative state, interpolates/limits values, and calls absolute
service `$801e`. The service body and its mapping to ES5510 host writes remain
unknown. These offsets are in the effect object, not a proven OS firmware
loader address.

A deterministic CLI `--analog-at` perturbation on one input channel produced
the same 1,718 ES5510 host-event lines as the baseline run. It does not establish
an effect parameter-to-GPR mapping. The final GPR snapshots differed because
they are end-of-render runtime states; no host write associated with the
perturbation was observed. A user-driven parameter edit with a timestamped GUI
trace or an address-resolved `$801e` service is still required.

## MAME-derived executor comparison

The captured 60-word program, 192 GPRs, special registers, 2 MiB DRAM image,
and MEMSIZ shift were loaded in a temporary research harness using the existing
TROLLfx MAME-derived `MameES5510` adapter (source repository commit
`ab202d16e73c34a8347ecf2720ee7622e0c47453`). The harness fed the same class of
stereo test tone and read the ASR program's actual SER1 output registers. It
executed 60 instructions per frame for 970,200 frames and produced nonzero
output (peak 8,191; RMS 5,791.549). This confirms that the captured instruction
sequence runs in the separate MAME-derived executor with nonzero audio.

This was not a bit-exact comparison against the alternate emulator. The
captured state is taken after the OS run, and internal ALU/MAC/RAM pipeline state
is not in the snapshot; the two emulators also have distinct system-level
routing. The MAME adapter's generic WAV harness normally reads SER3, so the
research run explicitly read SER1, as the ASR-10 CLI routes it. The mismatch in
RMS/peak is therefore diagnostic only and does not establish algorithmic
accuracy. No full MAME build was performed.

## Remaining questions and next evidence

1. Map the executed OS 3.53 file-loader and selection path to CPU addresses and
   its exact reads from the EFE object. REA tools are configured locally but
   were not exposed to this Codex session; the Ghidra executable/JDK path saved
   in user state is stale. Restore access through the existing integration,
   without reinstalling dependencies, or use a private headless Ghidra setup.
2. Explain the EFE's 11-byte prefix, three-byte gap, and 80-byte suffix from
   firmware dataflow and the ESP1 object specification.
3. Capture a known GUI parameter change with before/after host commits and map
   it through the `$801e` service to its GPR(s), scale, and update timing.
4. Compare a fresh identical initialized state in both executors. A state
   capture at the frame boundary must include pipeline state or deliberately
   reset both processors before replay.
5. Repeat selection with a delay/reverb object and compare its source layout
   against the same host-commit rules.

No ROM, OS image, EFE object, program bytes, raw event log, capture file, or WAV
is committed. No Force plugin or hardware was modified.
