# ASR-10 OS 3.53 ROM-01 HALL load boundary

## Scope and source

This report continues the cold-load work from `research/es5510-factory-coldload` commit
`b4d3abede24e20451f34308cdd2bd6ae16a277c6`. It adds bounded tracing to the native OpenASR
emulator. It does not alter ES5510 arithmetic, factory bytes, ROMs, or Force plugins. All ROMs,
OS images, captures, instruction/GPR bytes, RAM traces, and rendered audio stayed under
`/mnt/c/Users/Gamer/research/private-results/`.

The logger is opt-in (`ESP_PIPELOG=1`, `ESP_HOSTLOG=1`, `ESP_FRAMELOG=N`). It records host CPU
cycles and ESP frame numbers at host writes, PA4 transitions, run start, first instruction, and
serial boundaries. `ESP_FRAMELOG` is bounded to 4096 frames per RUN; RAM read/write details are
logged only during those requested frames. Logging is observational and has no DSP-state writes.
The raw log's line order is the global event order; `hall_load_boundary.py` preserves the original
line ordinal as `log_sequence` for its redacted event summary.
The new `tools/hall_load_boundary.py` emits event counts, algorithm selection metadata, and hashes
of ordered program/register/frame data; it never exports factory instruction, register, RAM, or
audio sample values. Its output path must be outside the checkout.

## Confirmed OS 3.53 transaction

The controlled run used the private boot ROM pair and OS 3.53 disk image, a 440 Hz / 0.25-level
test input routed to the emulated ESP input pair, and the normal 44.1 kHz host output renderer. The
OS effect selector must be traversed in ascending control values from 8; a direct jump to raw 79
from boot selected Room, not HALL. The verified inventory maps selector values 74–84 to ROM-01
HALL and 85–95 to ROM-02 44KHZ REVERB.

The key finding is that the ROM-01 display is a **selection marker, not the load boundary**. In
the first selected-HALL transaction:

| Event | OS trace coordinate | Result |
|---|---:|---|
| Stable `ROM-01 HALL REVERB` display | CLI schedule 26.114 s; CPU cycle 418,325,634; ESP frame 849,885 | UI selection observed; DSP is still running the previous loaded state |
| PA4 HALT asserted | CPU cycle 420,614,232; ESP frame 854,142 | Firmware begins replacing the loaded DSP state |
| Host HALT-enable accepted | CPU cycle 420,614,232 | Pending ALU/MAC results cleared, three RAM pipeline slots cleared, DOL count reset |
| Host DRAM clear | CPU cycle 420,614,390; ESP frame 854,143 | All 1,048,576 modeled 16-bit DRAM words zeroed |
| Instruction upload begins | CPU cycle 421,228,220; frame 855,284 | First instruction-memory commit in this transaction |
| PA4 RUN release | CPU cycle 421,550,288; ESP frame 855,972 | Firmware releases the DSP immediately before its next scheduler frame |
| Upload complete / RUN | CPU cycle 421,550,606; frame 855,973 | 89 instruction commits to 89 unique addresses; first END at word 88; 342 GPR/SPR commits while halted |
| First instruction | Same first run frame, PC 0 | Program begins at address 0 after RUN release |
| First serial input/output | Frame 855,973 | First input and processed output were captured at the same ESP frame boundary |

The first output is on SER1 (special-register lanes 2/3); the test stimulus enters on the configured
input pair (lanes 4/5). The host serial setting was `0x48`. The logged frame checkpoint includes all
eight serial lanes, but the public report stores only lane-state hashes.

The first instruction and register-state fingerprints for the boot-time 89-word transaction match
the selected ROM-01 HALL transaction. Thus OS 3.53 loads the HALL instruction image during startup
before the user opens the ROM effect selector. This is a program/state identity match within the
emulator and firmware capture, not proof of factory sound equivalence on hardware.

## Controlled switching and repeatability

One fresh emulator process performed the selector sweep and then the sequence HALL → ROM-02 → HALL
→ ROM-02 → HALL. The first HALL load had 89/89 unique instruction addresses and END at 88. Each
subsequent HALL load had the same ordered instruction fingerprint and the same ordered GPR/SPR
commit fingerprint as the first selected-HALL load. Repeated selection therefore **does** perform
a new HALT/clear/upload/RUN transaction; it is not merely a display change.

A second fresh CLI process repeated the boot and ascending selector sweep. It reproduced the same
first HALL run frame, instruction fingerprint, GPR/SPR fingerprint, and first-frame serial input
checkpoint as the first process. A separate bounded pair of fresh runs captured 256 input and 256
output serial-frame checkpoints from the startup/default HALL transaction. Both ordered streams
matched exactly. The SHA-256 fingerprints over the ordered per-frame lane-state hashes are
`36a9120c481d88beae6012cb1f399e2e262d48d0c48713d7b8b4c74d7726ff20` for the input frames and
`53173d6b89baef6f2eb7ca9cd0e57fe0cc596ee77eafffea378e09d3c47e7777` for ordered output frames.
The load's ordered instruction fingerprint is `ca2cab387d1bee51bccc9a97f2c5d26386b8b801ee9bf4ea406e80a7019e4f92`; its ordered 342 GPR/SPR commit fingerprint is
`3ac3a2f01d9dfda8bc225ca16b27c872f102da76d0098974c40aa912d84936e0`. The complete fingerprints
match between the two fresh runs. These are content hashes only; no raw factory or audio values are
in Git. The bounded run also observed 17,152 internal delay-RAM reads and 5,632 writes over the
first 256 HALL frames, matching in both runs.

The sequence also demonstrates that switching effects can change the OTTO voice allocation and
therefore the DSP call rate. At 31 active voices the configured OTTO clock is 15,238,090 Hz and the
ES5510 `run_frame()` rate is 29,761.89453125 Hz. At 23 active voices the OTTO clock is 16,934,400 Hz
and `run_frame()` rate is 44,100 Hz. The host PCM output rate remains 44,100 Hz; `dac.push()` resamples
the OTTO/ESP stream to that rate. These are observed emulator clock configurations, not a universal
ASR-10 fixed rate. The formula in the implementation is
`otto_clock / (16 * (active_voices + 1))`.

The CPU coordinate is the MC68302 model's 16 MHz cycle counter. The CLI's `time` label is its
nominal 1 ms schedule coordinate; due to the emulator's execute-slice behavior it is not a substitute
for the recorded cycle coordinate. The ESP frame counter increments on every `run_frame()` call,
including calls while the device is halted, so it is not the PCM WAV frame index. Inside each RUN,
the emulator executes instructions from PC 0 through END once per OTTO frame.

## Reproduction

Use a private working copy of the ROM directory and OS image. Example output below is private and
must not be placed in the repository:

```sh
ESP_HOSTLOG=1 ESP_PIPELOG=1 ESP_FRAMELOG=256 \
ASR_TEST_SINE=440:0.25 ASR_ROUTE='-1,-1,1,-1,0' \
build/research-cli/asr10-cli \
  --roms /private/asr10/roms --disk /private/asr10/os353.img \
  --seconds 28 --trace-esp-io --panel-log \
  --button 15:7:1 --button 15.2:7:0 \
  --esp-snapshot-rom-dir /private/results/romsnapshots \
  --analog-at 16.00:5:8 ... --analog-at 27.40:5:84 \
  > /private/results/session.log 2>&1

python3 tools/hall_load_boundary.py /private/results/session.log \
  --output /private/results/redacted-report.json
```

The selector values between the shown endpoints must be supplied in ascending order with the
existing 150 ms interval. Do not replace the sequence with a jump to 79. `ESP_FRAMELOG=256` records
input/output serial checkpoints and the DSP's internal delay-RAM reads/writes for the first 256
frames following each RUN. Lower the value for shorter diagnostics.

## Replay boundary and limitations

The capture identifies the exact firmware load event and the first instruction/input/output frame.
The HALT path clears pending pipeline work, and the host DRAM clear is observed. The ordered raw
`ESPIO` and `ESPHOST` events plus the bounded frame stream are sufficient to build an event-sourced
replay experiment, but this milestone does **not** claim a validated native/MAME factory replay.

The current `write_capture()` format is a snapshot, not a resumable MC68302/ES5510 event replay
container. Its complete DSP checkpoint also does not by itself preserve the CPU, all in-flight
pipeline internals, or host/audio scheduler phase. The 256-frame stream is serial data at the ESP
boundary, not the host's resampled DAC WAV. A replay runner must apply the exact ordered writes,
model PA4/HALT and zero-memory clear, establish the same OTTO rate and sample boundary, and compare
both implementations against the private OpenASR stream before the factory manifest can be marked
replay-ready. No sample-exact claim is made from native-versus-MAME agreement alone.

The refreshed [`ES5510_FACTORY_COLDLOAD_PARTIAL_V1.json`](ES5510_FACTORY_COLDLOAD_PARTIAL_V1.json)
uses the existing factory-manifest validator's partial schema. It records the ordered load evidence
and remains explicitly `replay_ready: false` until a factory event replay is compared against both
standalone engines.

Confirmed: OS selector value 79 identifies ROM-01 after the required sweep; the HALL loader asserts
HALT, resets the modeled pipeline, clears DRAM, commits 89 instructions through END 88, applies GPR
and special-register writes, then runs PC 0; the first HALL serial frame is bounded and repeatable;
the same HALL program/init fingerprints are seen at startup and across reloads.

Unresolved: whether this emulator model's reset and observed host protocol exactly match physical
ASR-10 silicon; the precise analog-rate transition boundary within OTTO scheduling; completeness of
the current public manifest fields for replay; and MAME/native agreement against the captured
factory stream beyond future offline replay tests.
