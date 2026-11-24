# ASR-10 OS 3.53 Factory Effect Collection

## Result

The stable OS FX Select sweep produced **50 of 50 validated private effect
packages**, one for each displayed ROM slot, with **0 failed**. It retained one
active RUN-state ES5510 checkpoint, the complete GPR/SPR and 1,048,576-word
DRAM image, the memory/delay/signal configuration, ordered post-reset host
transactions, phase evidence, and a short stereo audio render per slot.
All 50 checkpoints have an active program matching the timestamp-bounded
instruction commits in the OS host log. Every capture has HALT, pipeline reset,
DRAM clear, upload, RUN, and first-instruction evidence before its state
snapshot. Checkpoints have PC 0 and the DSP running.

The private package collection is:

`/home/gamer/research/private-results/asr10-all-50-effects/validated-packages/`

Each `packages/ROM-nn-name/` directory contains `package.json`,
`run-checkpoint.esp`, `firmware-events.log`, and `selector-audio.wav`. The
collection-level manifest and full event/source trace are also private. The
capture inputs and 50 short WAVs were kept outside the checkout; no raw state,
instruction bytes, audio, private hashes, or event values are committed.

## Inventory and shared programs

The IDs and names in [the machine-readable catalog](ASR10_ROM_EFFECT_CATALOG.json)
come from the OS 3.53 FX Select display. The sweep contained **46 distinct
active instruction images** across 50 slots. Four pairs used the same active
instruction image but had distinct captured GPR and special-register states:

| ROM slots | Display names | Observation |
|---|---|---|
| 01, 02 | HALL REVERB; 44KHZ REVERB | Same active image; GPR and SPR state differ |
| 18, 19 | LARGE PLATE; REVRSE REVRB | Same active image; GPR and SPR state differ |
| 23, 24 | NLIN REVRB 2; NLIN REVRB 3 | Same active image; GPR and SPR state differ |
| 29, 30 | GUITAR AMP2; GUITAR AMP3 | Same active image; GPR and SPR state differ |

These are captured state differences, not a verified parameter-control map.
The collection preserves selector identity and does not infer DSP topology
from the names.

## Measured clock and state

The selector snapshot markers recorded the actual emulator DSP rate and frame
for each slot. In this sweep, **48** slots were observed at 29,761.895 Hz and
**2** at 44,100 Hz. The names do not select those rates intrinsically: these
are observations from this OS/emulator run and reflect the runtime clock and
voice configuration at each capture. Per-slot rates and DSP frame coordinates
are in the JSON catalog and private package manifests.

All checkpoint files contain the complete state payload supported by the
ES5510 capture format: 160 instruction slots, 192 GPRs, 22 special registers,
runtime latches, serial samples, and 1 Miword DRAM. The private per-effect
event log contains the ordered host writes from the last captured pipeline
reset through the checkpoint, while the package manifest records reset,
clear, upload, RUN, and first-instruction phase coordinates. The test audio is
the short stereo OS-emulator selector-sweep output, cut from the stable display
window for each slot.

## Reproduce

Use the authorized local ROM and OS paths and a new empty output directory:

```sh
tools/run_rom50_capture_pipeline.sh \
  /home/gamer/OpenASR-run/roms/asr10booth \
  /home/gamer/OpenASR-run/floppies/os353.img \
  /home/gamer/research/private-results/asr10-rom50-new-run
```

The pipeline builds the native headless CLI if required, enumerates the OS
selector, performs a single stable-display capture sweep with phase logging,
validates each state and host program match, and creates private per-slot
packages plus the redacted public catalog. It refuses to put captures inside
the Git checkout and package generation refuses to overwrite a non-empty
package output directory. Keep the generated private directory out of Git.

To package an already completed sweep and inventory without repeating the OS
run:

```sh
python3 tools/package_rom_effect_collection.py \
  --source /path/to/private-completed-sweep \
  --inventory /path/to/private-completed-sweep/inventory.json \
  --output /home/gamer/research/private-results/asr10-rom50-packages \
  --catalog docs/ASR10_ROM_EFFECT_CATALOG.json
```

## Limits

This is an OS-emulator collection, not a physical ASR-10 hardware capture.
The active rate is a per-run observation rather than an effect requirement.
The catalog records the OS display identity, observed active program length,
rate, and equality groups without exposing private payloads or digests. It
does not claim that every effect is integrated into the V0.1 WAV runtime;
that runtime's public `EffectId` currently exposes HALL and ROM-02 only. Nor
does this sweep establish full parameter ranges, smoothing, long-term audio
quality, or silicon equivalence.
