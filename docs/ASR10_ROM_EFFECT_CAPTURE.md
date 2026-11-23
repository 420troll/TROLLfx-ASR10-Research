# ASR-10 OS 3.53 Factory ROM-Effect Capture

## Scope and evidence

This pipeline reads the effect selector from the running ASR-10 OS 3.53 in the
existing native headless emulator. It presses the OS FX Select control, sweeps
the emulator's `AN_DATA` input (channel 5), and records the visible `ROM-nn`
identifier and label. The inventory is therefore derived from executed OS
behavior, not a pre-entered list. The built-in `INST HALL REVERB` is captured
first as a separate reference because it is not a ROM-selector entry.

Initial exploratory scan of the private OS 3.53 image observed IDs 1–50 with
no gaps. The display labels were:

1 HALL REVERB; 2 44KHZ REVERB; 3 ROOM REVERB; 4 DUAL DELAYS; 5 44KHZ DELAYS;
6 CHORUS+REVRB; 7 PHASER+REVRB; 8 FLANGER+REV; 9 ROT.SPKR+REV;
10 CHOR+REV+DDL; 11 CMP+DIST+REV; 12 DIST+CHO+REV; 13 WAH+DIST+REV;
14 SMALL ROOM; 15 LARGE ROOM; 16 HALL REVERB2; 17 SMALL PLATE;
18 LARGE PLATE; 19 REVRSE REVRB; 20 REVRSE REVB2; 21 GATED REVERB;
22 NLIN REVRB 1; 23 NLIN REVRB 2; 24 NLIN REVRB 3; 25 MULTITAP DDL;
26 EQ+DELAY LFO; 27 VCF+DISTORT; 28 GUITAR AMP1; 29 GUITAR AMP2;
30 GUITAR AMP3; 31 SPKR CABINET; 32 TUNABLE SPKR; 33 EQ+CHOR+DDL;
34 EQ+VIBR+DDL; 35 EQ+FLNGR+DDL; 36 EQ+TREM+DDL; 37 PHASER+DDL;
38 8-VOICE CHOR; 39 PITCH SHIFT; 40 PITCH+DDL; 41 FAST PITCHSH;
42 EQ+CMPRESSOR; 43 EXPANDER; 44 KEYED EXPNDR; 45 INVRS EXPNDR;
46 DE-ESSER; 47 DUCKER; 48 RUMBLE FILTR; 49 PARAM EQ; 50 VAN DER POL.

This list is an observed scan result, not an assertion that all 50 selections
have been captured or that names describe internal DSP topologies.

## Run

```sh
tools/run_rom50_capture_pipeline.sh \
  /home/gamer/OpenASR-run/roms/asr10booth \
  /home/gamer/OpenASR-run/floppies/os353.img \
  /mnt/c/Users/Gamer/research/private-results/asr10-rom50-run
```

The script builds only `build/research-cli/asr10-cli` if absent, scans the OS
selector, then captures the HALL reference and each observed ROM ID.

The OS selector is stateful: applying a raw value in a fresh boot does not
always select the row associated with that value during an ascending sweep.
Therefore the capture pass sweeps the control once and snapshots a program
only after its actual `ROM-nn` display remains stable. The native CLI option
`--esp-snapshot-rom-dir` and timestamped `ESPHOST` diagnostics are capture
instrumentation in the headless frontend; they do not change the ES5510 engine.
The CLI writes at most one snapshot per observed ID and never overwrites an
existing snapshot. The full sweep WAV is split into per-effect audio windows.

Each effect is placed in its own `ROM-nn-name/` directory. `manifest.json` is
written atomically as each capture starts and finishes. Re-running with the
same firmware hashes skips only captures whose files still match manifest
hashes; incomplete `running` or `failed` jobs are retried. A firmware hash
mismatch requires a new output root. `inventory.json`, raw `host.log`, full
`.esp` snapshots, and WAV files must remain outside Git.

The runner requires an active program END and a running DSP snapshot, then
checks that the captured active instruction words equal the last host-committed
instruction words at each active address. It records all instruction END
positions and first-END length, GPR and special-register section hashes,
memory configuration (MEMSIZ/masks/increment/shift), named DLENGTH/ABASE/
BBASE/DBASE/SIGREG and serial registers, DRAM hash, ordered host transaction
log hash/counts, and audio peak/RMS. Silent audio is reported separately from capture failure. The
`.esp` is a state snapshot during execution, not a complete processor/CPU save
state. Host logs are preserved privately because they contain firmware-
generated register values. Their event counts are metadata only; a final GPR
snapshot is not misrepresented as the initial GPR state.

Generate the public/redacted catalog from private inventory and status JSON:

```sh
python3 tools/render_rom_effect_catalog.py PRIVATE_OUT/inventory.json \
  PRIVATE_OUT/status.json docs/ASR10_ROM_EFFECT_CATALOG.md
```

The redacted Markdown contains display names, IDs and capture status only.
Do not commit the inventory/status JSON, captures, source logs, or renders.

## Current capture qualification

The known built-in HALL REVERB reference is reproducible in the existing
private smoke script (89 instructions through END index 88, nonzero stereo
render). A first full-range inventory run observed IDs 1–50. An isolated
selection test exposed the stateful-control issue above; that naive capture
pass was stopped, and failed or misselected attempts are not presented as
successful catalog results. The stable-display snapshot path is the corrected
capture mechanism and must pass the full run before claiming completion.

The CLI prints the actual ROM label, while program capture records the active
ES5510 state and the host log records commits. This is emulator evidence under
OS 3.53; it does not establish that an identical capture was made on physical
ASR-10 hardware.
