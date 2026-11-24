# ASR-10 ROM Effect Capture — Status Report

## Result

The native OpenASR-based headless emulator booted the private OS 3.53 image,
opened the OS FX Select screen, and exposed a continuous sequence of displayed
ROM effect IDs and names from Data Entry channel 5. The scan observed IDs 1–50
without gaps. No effect inventory was hardcoded into the runner.

The capture run recorded all 50 selected states in separate private directories:

- Captured: **50**
- Failed: **0**
- Untested: **0**
- Built-in `INST HALL REVERB` reference: **captured separately**
- Active instruction count: **48 captures have 89 words; 2 have 60 words**
- Host commit comparison: **50/50 active instruction sequences match the last host commits visible at their snapshot time**
- Audio: **50/50 produced nonzero 44.1 kHz stereo PCM16 windows**
- Distinct active program hashes: **46** (some selectors use identical instruction streams)

Every capture includes the full instruction/GPR/special-register/runtime/DRAM
snapshot, first and all END positions, MEMSIZ/address masks, DLENGTH/ABASE/
BBASE/DBASE/SIGREG, serial configuration, final state section hashes, a
private ordered host log, host-event counts in the selector window, and a
0.5-second audio test render. Per-file SHA-256 values and detailed validation
metadata are in the private manifest, not this public report.

The output is from an emulator session under ASR-10 OS 3.53, not a physical
ASR-10 hardware capture. The `.esp` files are live processor snapshots and do
not contain all CPU or ES5510 pipeline state needed for exact mid-run resume.

The package collection produced by the newer phase-logged pipeline is
documented in [ASR10_ALL_50_EFFECTS.md](ASR10_ALL_50_EFFECTS.md). That run
retained per-slot reset/upload/RUN phase records and built 50 private package
manifests from its complete PC-zero state captures. Its per-run rate
observations and active-program sharing groups are in
[`ASR10_ROM_EFFECT_CATALOG.json`](ASR10_ROM_EFFECT_CATALOG.json).

## Repeatability check

A second deterministic selector run reproduced ROM IDs 1 and 2. For both
IDs, the complete `.esp` snapshot bytes matched the first run exactly. ROM ID 1
also produced an identical 0.5-second PCM sample sequence. This checks repeat
capture determinism for the known HALL/44 kHz reverb entries; it is not a full
second 50-effect sweep.

## Reliability correction

An initial per-effect strategy applied a stored raw Data Entry value in a fresh
boot. That control proved state-dependent: for example, the same input value
that appeared to select ROM 3 in an ascending sweep selected ROM 5 when applied
alone. Those attempts were not accepted as evidence. The final runner instead
captures each effect only while the actual on-screen ID/name remain stable
during a sweep. Each snapshot's active instructions are checked against the
timestamp-bounded host instruction commits preceding it. Host writes receive
diagnostic emulator timestamps at 1 ms resolution; this does not change DSP
execution.

The native headless CLI has a capture-only `--esp-snapshot-rom-dir` option. It
records one snapshot per stable ROM ID and refuses to overwrite an existing
snapshot. On resume, complete manifest-verified results are retained;
unverified remnants are preserved under `.previous` names and regenerated.

## Private artifacts

Artifacts are under:

`/mnt/c/Users/Gamer/research/private-results/asr10-rom50-sweep/`

The directory has one folder per effect, `HALL-REFERENCE/`, `manifest.json`,
`status.json`, `selector-sweep.log`, `selector-sweep.wav`, and raw snapshots.
All are local private research results and are intentionally excluded from Git.

## Build and validation

Build command:

```sh
tools/build_research_cli.sh
```

It produced `build/research-cli/asr10-cli` successfully. Existing warnings
remain in `src/asr10.cpp:447` and `src/m68302.cpp:214` about misleading
indentation; no compilation errors occurred.

Tests:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/capture_asr10_rom_effects.py tools/render_rom_effect_catalog.py
sh -n tools/run_rom50_capture_pipeline.sh
```

Result: **19 tests passed**, Python compilation passed, shell syntax passed, and
`git diff --check` passed. The full 50-ID capture was also the integration
exercise of snapshotting, host-commit matching, WAV extraction, and manifest
status generation.

## Rerun

```sh
tools/run_rom50_capture_pipeline.sh \
  /home/gamer/OpenASR-run/roms/asr10booth \
  /home/gamer/OpenASR-run/floppies/os353.img \
  /mnt/c/Users/Gamer/research/private-results/asr10-rom50-sweep
```

It scans the current OS image, captures the built-in HALL reference, then runs
the stable-display sweep with pipeline phase logging and packages the
validated per-effect states. It builds the native CLI when absent or stale.
Review the local `status.json` and `validated-packages/collection-manifest.json`
before treating results as complete. Never add the private output tree to Git.

## Remaining limits

- This does not recover proprietary program files or firmware from ROM; it
  records the ES5510 state actually observed in the emulator while the OS
  selected each effect.
- Program identity is supported by the displayed OS label, a running DSP, an
  END-terminated program snapshot, and matching host commit data. It is not a
  claim that the effects are bit-exact on hardware.
- The per-effect short render establishes nonzero output, not subjective
  quality or full behavior for every program. Use longer, algorithm-specific
  listening renders for sound evaluation.
- HALL reference and ROM-01 both display HALL REVERB. The catalog keeps ROM-01
  distinct because it has its own selectable ROM ID and independently
  captured processor state.
