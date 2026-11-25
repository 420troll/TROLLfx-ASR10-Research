# ASR-10 Full-Parameter PC Editor

## What the simulator exposes

The PC editor builds effect-specific groups from the manual catalog, Codex 1's registry and Codex 3's independent control matrix. It has 50 factory effect selections and 895 generated editor field instances after the QA corrections. That widget count is not a count of distinct or OS-verified Ensoniq controls. The independent matrix records 594 manual descriptors, 13 additional recovered-control records, 1,040 LCD field associations and 5,484 observations. Its DSP classification is 51 UNKNOWN, 36 PARTIAL and 507 UNMAPPED; zero full documented ranges are implemented. The native editor bridge retains its 19 exact VST routes.

Controls carry slot-scoped stable editor identities (`ASR10:ROM-nn:<control-id>`), source manual parameter IDs where a direct association exists, original-OS association evidence, independent DSP classification, register observations, audio status and runtime route status as separate fields. The local adapter is [ASR10_EDITOR_EVIDENCE_ADAPTER_V1.json](../../tools/force_simulator/data/ASR10_EDITOR_EVIDENCE_ADAPTER_V1.json); it was generated from Codex 3's versioned validation matrix and specification audit, with source commits and SHA-256 values recorded inside. It is read-only evidence, never a DSP write allowlist.

The integration consumes Codex 1's versioned `ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json` (manual/runtime metadata) and V05 mapping catalog alongside Codex 3's QA crosswalk; it does not introduce another parameter authority. The editor keeps IDs from the registries and adds a slot namespace for UI draft keys. New mappings need an exact stable control ID, supported display values or an explicit verified conversion, runtime implementation and audio-validation states, then an accepted native VST route. A display label, `runtime_ready` bit or register observation alone cannot enable a write.

The machine-readable presentation schema is [ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json](../../tools/force_simulator/data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json). It keeps manual display metadata and DSP evidence in separate objects. The input registry snapshot is [ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json](../../tools/force_simulator/data/ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json), copied read-only from Codex 1's `research/asr10-full-factory-parameter-recovery` at commit `7d38ec2bc3369ecd16f9e284ba85ccfd6fe46b55`.

The 594 catalog entries are retained as source descriptors. The UI expands only documented groups into editor fields; these generated fields are not counted as unique verified controls. The QA crosswalk corrections include:

- ROM-04/05: separate BUS1/BUS2 mix and feedback, plus independent left/right delay time for each bus. The existing verified BUS1-left VST identity remains in use.
- ROM-06 through ROM-13: the shared reverb, chorus, bus, compressor, and distortion parameters named by each algorithm's Section 6 text. Only the named shared controls are inherited; a whole referenced effect is not copied.
- ROM-17/18 and ROM-21: the four early reflection levels are separate.
- ROM-22 through ROM-24: Section 6 documents nine envelope levels, while the captured OS row displays five values. The editor exposes five captured components and leaves components 6–9 in the machine-readable manual schema, hidden from editing until their OS field/page identities are established.
- ROM-09: the composite distortion gain heading is represented as distinct input and output controls.
- ROM-10: DDL left/right time controls are separate.
- Multi-unit ranges such as `1 ms to 10 s` and `50 µs to 100 ms` are converted to a common PC display unit without claiming a DSP coefficient curve.

The supplied PDF was found at `C:\Users\Gamer\Downloads\23583406.pdf` (SHA-256 `e8ab5100904caf91fe355065ed9646aff197761b0663a7d452dc98af1f9a29dc`). Section 5 is PDF pages 87–97 and Section 6 is PDF pages 98–153. Text extraction supplied descriptions for 590 of the 594 catalog entries. The four ROM-50 entries remain undocumented in this copy because Section 6 ends after ROM-49. ROM-02 is explicitly marked OS-inventory deferred; its manual controls are not presented as OS-observed.

## Variation and modulation behavior

Each effect's four variation choices have independent PC draft buffers, keyed by factory slot and variation. Selecting a variation changes the draft buffer only. The native VST has no variation parameter route in this interface. Therefore even an otherwise exact mapped point stays pending for variations 2–4; only the default VST variation can use the current exact routes. The comparison panel shows the PC draft separately from the last value applied to the VST. Reset clears the selected variation's draft to editor seed values; these seeds are not claimed as factory defaults. Undo reverts the prior PC draft edit and sends no DSP write. PC draft JSON is versioned separately from native VST state chunks and migrates by stable control ID, retaining unknown identities as orphans for review.

A modulation section appears only for algorithms where the manual lists that block. The two assignments remain separate and draft state is variation-specific. The editor compares those controls with the independent matrix's OS field associations. The documented source list and MIN/MAX ranges are editable as PC drafts; destination choices remain read-only unless enumerated by evidence. Direct-destination lockout behavior for an active assignment remains unverified.

## DSP and Force boundaries

The PC display range is separate from DSP support. The simulator sends an edit only when (1) the selected effect has an existing native VST route, (2) the value matches one of that route's exact points, and (3) the selected variation is the VST's default variation. It does not extrapolate a register curve or use the Codex 1 registry's `runtime_ready` flag as authorization. Existing VST parameter IDs, indices and saved-state behavior are retained.

Codex 1's registry and Codex 3's independent matrix remain descriptive inputs. Codex 1's registry reports merge discrepancies in `runtime_ready`, so that field is not used as a write allowlist. To activate a future recovered control without a GUI rewrite, Codex 1's accepted semantic mapping must be associated with the control's stable slot-scoped identity, then the native VST bridge must publish an append-only route and exact supported points. `parameter_registry.py` discovers those route descriptors from the VST registry header on startup; the route is the only write authorization. The independent matrix alone cannot enable DSP writes. The current native VST bridge still exposes 19 routes; no newly recovered full-range mapping was promoted.

The comparison panel shows the selected PC identity/value, captured original LCD labels and values by variation, independent DSP/audio state, VST index and stable VST ID when routed, register evidence, the last applied runtime writes, and why an edit is pending. For a live original-OS view, launch Codex 1's monitor on localhost and set `TROLLFX_OS_MONITOR_URL=http://127.0.0.1:<port>` before starting the simulator. The simulator reads only `/api/status` and `/api/events`; it does not send monitor button events or DSP edits. Without that setting, the panel uses the checked-in, read-only independent matrix.

The skin preview and generated BROWSE / EDIT / MIX pages remain a separate stock-SDK preview. PC effect sections, dynamic PC banks, mouse Q-Links, PC variation drafts and expanded parameter groups are PC simulator capabilities. They do not establish that the stock Force SDK can show effect-dependent tabs or dynamically reassign physical Q-Links. Nothing was installed on a Force.

## Rebuild and tests

To regenerate the schema from the supplied manual and registry snapshot:

```sh
python3 tools/force_simulator/build_editor_evidence_adapter.py \
  --validation-matrix /path/to/codex3/docs/qa-v4/factory-parameter-validation-matrix.json \
  --spec-audit /path/to/codex3/docs/qa-v4/ASR10_FACTORY_PARAMETER_SPEC_AUDIT_V1.json \
  --output tools/force_simulator/data/ASR10_EDITOR_EVIDENCE_ADAPTER_V1.json
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

The Force-facing strategy remains the three static SDK pages and their fixed Q-Link maps. Desktop groups and banks have no automatic physical Q-Link equivalent. A hardware-safe mapping needs an explicit per-effect static map that the stock SDK can express and independent callback/device validation; this editor does not infer one.

## Screenshots

- [HALL REVERB](screenshots/pc-editor-hall-bank-1.png)
- [DUAL DELAYS](screenshots/pc-editor-dual-delays.png)
- [CHORUS+REVRB](screenshots/pc-editor-chorus-reverb.png)
- [FLANGER+REV](screenshots/pc-editor-flanger-reverb.png)
- [PITCH SHIFT bank 1](screenshots/pc-editor-pitch-bank-1.png)
- [PITCH SHIFT bank 2](screenshots/pc-editor-pitch-bank-2.png)

## Remaining evidence gaps

The original PDF does not document ROM-50 in Section 6, and the modulation destination lists and destination lockout behavior have not been recovered per effect. The recovered registry's register evidence is not a complete set of native VST routes. Physical Force font/layout behavior, host-state recall of PC-only drafts, and physical Q-Link behavior remain outside the simulator proof.
