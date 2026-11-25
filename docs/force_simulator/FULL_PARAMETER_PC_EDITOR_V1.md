# ASR-10 Full-Parameter PC Editor

## What the simulator exposes

The PC editor now builds effect-specific control groups from the manual-derived catalog and Codex 1's registry snapshot. It exposes 50 factory effect selections and 907 visible edit controls across them, including independently adjustable subparameters derived from explicit Section 6 wording. Controls are grouped by effect area and use eight virtual Q-Link controls per bank. Bank and section changes update the visible Q-Link assignments immediately.

The machine-readable presentation schema is [ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json](../../tools/force_simulator/data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json). It keeps manual display metadata and DSP evidence in separate objects. The input registry snapshot is [ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json](../../tools/force_simulator/data/ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json), copied read-only from Codex 1's `research/asr10-full-factory-parameter-recovery` at commit `7d38ec2bc3369ecd16f9e284ba85ccfd6fe46b55`.

The 594 catalog entries are retained as source descriptors. The UI schema expands explicit independent controls that the catalog collapsed or left under cross-references, including:

- ROM-04/05: separate BUS1/BUS2 mix and feedback, plus independent left/right delay time for each bus. The existing verified BUS1-left VST identity remains in use.
- ROM-06 through ROM-13: the shared reverb, chorus, bus, compressor, and distortion parameters named by each algorithm's Section 6 text. Only the named shared controls are inherited; a whole referenced effect is not copied.
- ROM-14 through ROM-16: the shared decay control uses the selected room/hall algorithm's own range; the three position-balance controls are separate.
- ROM-17/18 and ROM-21: the four early reflection levels are separate.
- ROM-22 through ROM-24: the nine envelope levels are separate.
- ROM-10: DDL left/right time controls are separate.
- Multi-unit ranges such as `1 ms to 10 s` and `50 µs to 100 ms` are converted to a common PC display unit without claiming a DSP coefficient curve.

The supplied PDF was found at `C:\Users\Gamer\Downloads\23583406.pdf` (SHA-256 `e8ab5100904caf91fe355065ed9646aff197761b0663a7d452dc98af1f9a29dc`). Section 5 is PDF pages 87–97 and Section 6 is PDF pages 98–153. Text extraction supplied descriptions for 590 of the 594 catalog entries, with concise manual-derived paraphrases where the extracted layout did not yield a complete paragraph. The four entries for ROM-50 have no descriptions because this PDF's Section 6 ends after ROM-49. Their catalog ranges remain visibly catalog-derived; no missing ROM-50 manual text was inferred.

## Variation and modulation behavior

Each effect's four variation choices have independent PC draft buffers, keyed by factory slot and variation. Selecting a variation changes the draft buffer only. The native VST has no variation parameter route in this interface, so the UI identifies variation drafts as PC-only. Reset clears the selected variation's draft to editor seed values; these seeds are not claimed as factory defaults. Undo reverts the prior PC draft edit and sends no DSP write.

A modulation section appears only for the 32 algorithms with an explicit Section 6 MOD SRC/DST/MIN/MAX block. The two assignments are represented separately. The documented modulation source list and MIN/MAX ranges are editable as PC drafts. DST choices remain read-only because the current registry does not enumerate valid destination choices per algorithm. Direct-destination lockout behavior for an active modulation assignment also remains unverified; no guessed destination or lockout is presented as original OS behavior.

## DSP and Force boundaries

The PC display range is separate from DSP support. The current simulator sends an edit to the native VST only when it matches one of the existing exact points in the append-only VST control registry. It does not extrapolate a register curve or send an unsupported draft value. Existing VST parameter IDs, indices and saved-state behavior are retained.

Codex 1's full registry reports 33 register-mapped controls, but its current `runtime_ready` merge does not match the V05 source flags for several controls. This editor therefore does not use that field as a write allowlist. The current native VST bridge still exposes the existing 19 exact VST routes. Other recovered DSP controls require a verified host-facing mapping before they can write.

The skin preview and generated BROWSE / EDIT / MIX pages remain a separate stock-SDK preview. PC effect sections, dynamic PC banks, mouse Q-Links, PC variation drafts and expanded parameter groups are PC simulator capabilities. They do not establish that the stock Force SDK can show effect-dependent tabs or dynamically reassign physical Q-Links. Nothing was installed on a Force.

## Rebuild and tests

To regenerate the schema from the supplied manual and registry snapshot:

```sh
PYTHONPATH=/tmp/asr10-pypdf python3 tools/force_simulator/build_ui_schema.py \
  --manual-pdf /mnt/c/Users/Gamer/Downloads/23583406.pdf
```

The generator uses `pypdf` only at build time. Runtime and test execution do not need the PDF. If Codex 1 updates the registry, replace the local snapshot from the reviewed registry commit and rerun this generator; new runtime writes still require an exact route in the VST registry.

QA commands:

```sh
python3 -m unittest discover -s tools/force_simulator/tests -v
TROLLFX_SIM_PORT=8782 npm --prefix tools/force_simulator run test:browser
```

The automated suite covers all 50 selections, control range metadata, signed and mixed-unit domains, enumerations, repeated and stereo controls, variations, modulation availability, per-effect draft retention, undo/reset, banked mouse-operated Q-Links, existing native VST/register traces, state save/restore, widget clipping and generated skin layout. Current run summaries are recorded in [pc-editor-full-parameter-qa-results.json](pc-editor-full-parameter-qa-results.json).

## Screenshots

- [HALL REVERB](screenshots/pc-editor-hall-bank-1.png)
- [DUAL DELAYS](screenshots/pc-editor-dual-delays.png)
- [CHORUS+REVRB](screenshots/pc-editor-chorus-reverb.png)
- [FLANGER+REV](screenshots/pc-editor-flanger-reverb.png)
- [PITCH SHIFT bank 1](screenshots/pc-editor-pitch-bank-1.png)
- [PITCH SHIFT bank 2](screenshots/pc-editor-pitch-bank-2.png)

## Remaining evidence gaps

The original PDF does not document ROM-50 in Section 6, and the modulation destination lists and destination lockout behavior have not been recovered per effect. The recovered registry's register evidence is not a complete set of native VST routes. Physical Force font/layout behavior, host-state recall of PC-only drafts, and physical Q-Link behavior remain outside the simulator proof.
