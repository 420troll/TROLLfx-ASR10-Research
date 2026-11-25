# TROLLfx ASR-10 Per-Effect Editor V3

## Interface and SDK decisions

V3 uses the existing InMusic skin generator and its documented 1280×800 skin
canvas. SDK commit `febd2ca5bd9eb16c4a412837196e145566bc981b` supports up to 32
tabs, 16 parameter-bound controls per tab, the existing knob/fader/switch/menu
widgets, and `visibleWhen` conditions on choice parameters. The generated TUI
uses its native `IndexedEnabling` control for the `FX Slot` visibility tests.
The implementation adds no custom graphics engine, conditional widget type,
or unbound touchscreen control.

The skin has distinct BROWSE, MIX, and EDIT views. EDIT contains only verified
controls and uses the existing parameter positions and Q-Link map. Q1–Q4 stay
bound to the existing HALL/ROM-02 BUS parameter IDs; Q5–Q16 stay bound to the
twelve V2 controls. The 16 positions are documented in the registry as two
logical eight-control groups (Q1–Q8 and Q9–Q16). Effects with fewer controls
show only the controls whose `visibleWhen` condition matches the selected slot.

The browser retains all 50 original slot names. Its selection list shows the
package-provider availability and either the number of verified controls or
`NO EDIT`. The formatted selection readout adds `VERIFIED EDIT` or
`NO VERIFIED EDIT`. A static browser note explains that an unmapped effect
continues to load and process audio. Documented manual controls without a live
register mapping are stored in the registry as `editable: false`; no widget is
created for them.

## Central parameter registry

`docs/ASR10_FACTORY_EDITOR_REGISTRY_V03.json` is the data source for the
50-slot editor inventory, verified controls, effect-specific conditions,
parameter indices, Q-Link positions, and generated skin. It joins the public
effect list and V1 manual catalog with V2’s 16 independently verified
controls. `tools/parameter_controls/build_editor_registry_v03.py` generates:

- the V3 JSON registry;
- `force_plugin/ui.json`; and
- `include/trollfx/es5510_factory_editor_v03.hpp`, consumed by the plugin for
  its control index, effect slot, control ID, and display name table.

Run the generator from the repository root:

```sh
python3 tools/parameter_controls/build_editor_registry_v03.py
python3 tools/parameter_controls/build_editor_registry_v03.py --check
```

Each verified control retains its original Ensoniq label and exact observed
display text/points in the JSON registry. Duplicate labels use an effect
qualifier for the host-visible parameter name. Only the listed discrete
points are selectable; `UNCHANGED` remains a no-write state for V2 controls.
The runtime continues to schedule the verified ordered DSP register writes on
the audio thread through the existing bounded API. No filesystem access,
locking, or allocation was added to `process()`.

## State and compatibility

No plugin parameter ID, parameter index, effect slot, package validation rule,
factory program, DSP arithmetic, or 5 ms switching behavior changed. The V2
parameter range remains indices 0–23 and all V2 host chunk values remain
addressable by the same IDs. Host chunk serialization continues to use the
existing SDK mechanism; factory program data is not included in chunks.
Existing global Wet/Dry, Input Gain, Output Gain, Host Bypass, and FX Slot
controls remain on BROWSE/MIX.

Package availability continues to come from the trusted provider. Metadata
does not make a package eligible. A package that is unavailable cannot be
loaded; verified parameter controls remain gated by provider descriptor
metadata before runtime writes are queued. The runtime still fails closed for
missing packages.

## Verification

The V3 validation command and the exact ARM32/native binary hashes are recorded
in the release handoff appended during final packaging. Automated checks cover
all 50 slot identities, 16 verified mappings, 40 unmapped effects, generated
registry freshness, conditional control-slot bindings, preserved indices,
Q-Link maps, native package playback, chunk restore, SDK host simulation, and
ARMv7 package validation.

No screenshot is included: the local SDK build/host simulator generates and
validates the Force skin JSON but does not render the touchscreen. No Force
installation or replacement is part of this V3 task; the existing V1 plugin
remains untouched on hardware. The packaged candidate is handed to Codex 3 for
independent release validation.

## Known limitations

- Only 16 controls across 10 effects have verified live mappings. The other 40
  effects remain playable, but their factory parameters are not exposed as
  editable controls.
- The SDK JSON supports selection-dependent visibility, but does not expose a
  runtime conditional disabled state for controls based on package presence.
  Package availability is shown by the effect status; the backend rejects
  writes without an active validated descriptor.
- The local SDK validates schema and parameter bindings; final Force touch
  sizing and conditional visibility still require visual confirmation on the
  device. The user reports the installed V1 package already loads and produces
  wet audio; this branch has not been installed over that working package.
