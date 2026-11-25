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

The verified release candidate is
`force_plugin/dist/TROLLfx - VST - ASR10 FX Collection`. It was built from
source commit `77895655392c1308b81f6a8f926f3595cb96a0bd` with source-input
SHA-256 `a8298874b4a385324704cdd135d0d8b8e56d4c6c7ffef30df1330fe850e140fa`,
using SDK commit `4521c247a2deae30efb9e93d53fc8f9390c51e81` and Zig 0.17.1.

| Binary/report | SHA-256 | Verification |
|---|---|---|
| Native x86_64 VST2 | `c5bb9a8e6906126d820e4785667fbcba31cb2470236e70fe6812f6a4dc4944fa` | Binary-bound VST harness and SDK host simulator passed |
| ARMv7 hard-float VST2 | `fec8a0ccdbb8fbaa717a288d94b0b32ead63c5ba6b76c97a22661c6ce138f473` | ELF32 ARMv7/hard-float and SDK package validation passed |
| ARM64 VST2 | `2b743bb7ffb171a657e99b5db9d7ce506b22234fba2d7f987d17f14fb336a9ee` | ELF64 AArch64 and SDK package validation passed |
| Binary playback report | `d6704af9cb4cfc3cbf63e6c4bacf3393de495ecdee210587956c527bbdc5c8d4` | Native VST bound to 50 eligible packages; zero audio-callback allocations |

The binary test verified the VST2 entry point, 24-parameter ABI, all 50
factory packages, both verified points for the twelve appended controls,
stereo non-silent output, missing-package silence, host wet/dry/gain/bypass,
effect switching, and chunk restore for effect selection, host parameters,
BUS parameters, and a V2 control. It reported all 50 slots `PASS`, the 5 ms
fade contract, `state_roundtrip: PASS`, and `callback_allocations: 0`. The
generated Q-Link map remains Q1–Q16 → parameter indices 8–23. SDK validation
reported zero errors and zero warnings; generated TUI contains three tabs with
parameter handles in 0–23.

The build command was:

```sh
AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK \
TROLLFX_FACTORY_PACKAGE_COLLECTION=/home/gamer/research/private-results/asr10-all-50-effects/validated-packages \
  sh force_plugin/tools/build_candidate.sh --toolchain auto --no-zip
```

Final regression results: 80 repository unit tests passed; 14 parameter
registry/discovery tests passed; 5 release-infrastructure tests passed; the
native VST, SDK host simulator, all-50 package playback, Q-Link mapping, and
ARM target validation passed. Package checksums and the read-only installer
verification passed.

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
