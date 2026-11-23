# ASR-10 OS 3.53 factory effect parameter catalog

The machine-readable catalog is [`ASR10_OS353_PARAMETER_CATALOG.json`](ASR10_OS353_PARAMETER_CATALOG.json). It contains all 50 OS 3.53 ROM effect IDs/names from the redacted running-OS inventory. The inventory does **not** mean their edit pages were enumerated: the available public evidence contains just two controlled parameter mappings. Unobserved labels and values are left out, while defaults and full ranges remain null even for the two observed controls.

## Verified GPR mappings

| Effect | Displayed control | Reversible display values observed | ES5510 destination | Evidence status |
|---|---|---|---|---|
| ROM-02 44KHZ REVERB | REVERB MIX BUS2 | 25 → 26 → 25 → 26 | GPR `0x7A` (`0x350000` ↔ `0x370000`) | Repeated up/down plus matched no-edit control, emulator host-write log |
| ROM-49 PARAM EQ | BASS GAIN | +3 → +4 → +3 → +4 | GPR `0x56` (`0x00B500` ↔ `0x00CB00`) | Repeated up/down plus matched no-edit control, emulator host-write log |

These observations establish the destination GPR for these specific controls. They do not establish complete value ranges, factory defaults, interpolation behavior, physical-hardware behavior, or universal behavior across similarly named controls. The ROM-02 redacted evidence is documented on branch `research/factory-efe-reconstruction-v2` in `FACTORY_EFE_RECONSTRUCTION_V2.md`; the ROM-49 evidence is in [`ASR10_PARAMETER_MAPPING.md`](ASR10_PARAMETER_MAPPING.md). ROMs, EFE/microcode bytes, captures, and raw logs remain outside this branch.

The recorded controls are effect-specific observations. No cross-effect shared control has been experimentally established. `possible_influence` tags are name-based hints only: REVERB MIX BUS2 could relate to routing or mix, and BASS GAIN could relate to gain or frequency response, but the signal path/function is not independently resolved. Delay, feedback, damping, modulation, routing, and output gain roles for the remaining parameters are unknown.

## Read-only display-log intake

The tool reads saved emulator output text and extracts complete timestamped display rows of the form `[ 30.708s] |PARAMETER=VALUE|`. It does not launch the emulator, press buttons, alter disk images, read or print DSP memory, or ingest host-write payloads. Use a disposable OS-image copy for any emulator session. Navigate the OS 3.53 UI to an effect's Edit/Effects page without changing values, save the console log outside the repository, then intake only the display rows:

```sh
python3 tools/parameter_catalog/catalog.py seed --output /tmp/catalog.json
python3 tools/parameter_catalog/catalog.py enumerate \
  --catalog /tmp/catalog.json --effect-id 2 \
  --display-log /private/rom02-ui.log --output /tmp/catalog-next.json
python3 tools/parameter_catalog/catalog.py validate /tmp/catalog-next.json
```

Enumeration is observational, not an automatic full parameter sweep. Repeat the same navigation sequence and capture each display row; current values are observations, **not defaults**. Range endpoints and step sizes require separate reversible tests with no-edit controls and must be recorded as such. Only map a control to a GPR after reproducible reversible one-step changes show the same host-write destination, and preserve ambiguous/startup writes as unassigned. Do not add raw logs or host values to Git.

The catalog is validated for exactly 50 ordered effect IDs and explicit mapping states (`experimentally_verified`, `candidate`, `unknown`). Synthetic tests cover inventory consistency, intake, deduplication, unknown preservation, and the two known mappings:

```sh
python3 -m unittest discover -s tests/parameter_catalog -v
python3 -m json.tool tools/parameter_catalog/catalog.schema.json >/dev/null
python3 tools/parameter_catalog/catalog.py validate docs/ASR10_OS353_PARAMETER_CATALOG.json
```

## Remaining blockers and ESP Lab path

Only two controls have a public reversible GPR mapping. The other 48 effect edit pages have not been enumerated in the accessible public evidence. No complete parameter count, defaults, endpoints, step law, shared-control set, or register mapping can currently be claimed. The emulator host writer is observable, but its cold-load state and all factory initialization requirements remain separate research questions.

Once populated from verified UI observations, this catalog can drive TROLLfx ESP Lab interface generation: effect selection from `id`/`display_name`; control widgets from observed labels and verified ranges/steps; units/formatting from captured display syntax; and register bindings only for verified mappings. Candidate and unknown mappings must remain unbound, while null ranges/defaults require explicit evidence before an interface can promise limits or initialize a parameter.
