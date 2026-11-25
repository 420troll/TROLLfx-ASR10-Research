# TROLLfx ASR-10 Per-Effect Editor V3

## Interface and SDK decisions

V3 uses the existing InMusic skin generator and its documented 1280×800 skin
canvas. SDK commit `febd2ca5bd9eb16c4a412837196e145566bc981b` supports up to 32
tabs, 16 parameter-bound controls per tab, the existing knob/fader/switch/menu
widgets, and `visibleWhen` conditions on choice parameters. The generated TUI
uses its native `IndexedEnabling` control for the `FX Slot` visibility tests.
The implementation adds no custom graphics engine, conditional widget type,
or unbound touchscreen control.

The skin has distinct BROWSE, MIX, EDIT, and EDIT 2 views. EDIT retains the
existing V2 parameter positions and Q-Link map: Q1–Q16 still bind to indices
8–23 in the same order. The two eight-control groups are recorded in the
registry. EDIT 2 adds V3 controls at indices 24–26 on Q1–Q3; remaining Q-Links
are unassigned. Effects show only controls whose SDK-supported `visibleWhen`
condition matches the selected slot.

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
parameter indices, Q-Link positions, display range evidence, and generated
skin. It joins the public effect list and V1 manual catalog with V2’s 16 and
V3’s three independently verified controls. `tools/parameter_controls/build_editor_registry_v03.py` generates:

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
qualifier for the host-visible parameter name. Only explicitly mapped
discrete points are selectable; `UNCHANGED` remains a no-write state. The
three confirmed live display ranges—HALL DECAY TIME 0–99, ROOM DIFFUSION
0–99, and ROOM HI FREQ DAMPING 0–99—are stored separately from their two
verified register-write points. Those ranges do not imply a register curve or
enable interpolation. V3 adds 44KHZ DELAYS BS1 TIME L, FLANGER+REV FLANGE RATE,
and PITCH SHIFT QUALITY. ROM-02 is unchanged and receives no new V3 claim.

The inspected SDK has no dedicated LCD widget. Its supported parameter value
labels and choice-menu overlays display the exact Ensoniq text and values,
including `LONG/SMOOTHER` and `SHORT/COARSER`; EDIT 2 identifies the readout
area as LCD-style. No unsupported widget or custom renderer was added. The
runtime schedules only the observed ordered DSP register writes through the
existing bounded API. No filesystem access, locking, or allocation was added
to `process()`.

## State and compatibility

No existing plugin parameter ID, parameter index, effect slot, package
validation rule, factory program, DSP arithmetic, or 5 ms switching behavior
changed. V2 indices 0–23 and their host chunk IDs remain stable. The three V3
choices append at indices 24–26 with new IDs. Host chunk serialization
continues to use the existing SDK mechanism; factory program data is not
included in chunks.
Existing global Wet/Dry, Input Gain, Output Gain, Host Bypass, and FX Slot
controls remain on BROWSE/MIX.

Package availability continues to come from the trusted provider. Metadata
does not make a package eligible. A package that is unavailable cannot be
loaded; verified parameter controls remain gated by provider descriptor
metadata before runtime writes are queued. The runtime still fails closed for
missing packages.

## Verification

The V3 metadata and editor changes have passed focused registry generation,
parameter mapping, synthetic runtime, and native plugin-wrapper tests. The
release candidate is being rebuilt from the resulting source commit. Its exact
native, ARMv7, and ARM64 binary hashes, binary-bound playback report, SDK
validation, and independent Codex 3 review are recorded here after that build;
older V3 artifact hashes are intentionally not presented as evidence for this
updated 19-control candidate.

The build command was:

```sh
AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK \
TROLLFX_FACTORY_PACKAGE_COLLECTION=/home/gamer/research/private-results/asr10-all-50-effects/validated-packages \
  sh force_plugin/tools/build_candidate.sh --toolchain auto --no-zip
```

The ARMv7 package can also be tested under user-mode QEMU with the trusted
local package collection. This compiles the binary-bound harness with the
Force SDK framework, creates the same deterministic 8,192-frame stereo
stimulus and a temporary provider asset tree, and writes a redacted JSON
report (slot metrics and hashes only; no audio or package payloads):

```sh
PYTHONPATH=/tmp/trollfx-force-zig \
  python3 force_plugin/tools/test_arm32_vst_qemu.py \
    --arm32-plugin 'force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/VST/asr10-fx-collection-arm32.so' \
    --collection "$TROLLFX_FACTORY_PACKAGE_COLLECTION" \
    --sdk /mnt/c/Users/Gamer/research/AkaiForceSDK \
    --qemu-arm /tmp/trollfx-qemu-user/usr/bin/qemu-arm \
    --report /tmp/asr10-arm32-qemu-validation.json
```

This ARMv7 execution is an emulator check. It is not a physical Force test.

The updated binary-bound test is expected to verify the 27-parameter ABI,
all 50 factory packages, all 19 controls' exact verified points, stereo
non-silent output, missing-package silence, host wet/dry/gain/bypass, effect
switching, and host chunk restoration. No claim for this binary is made until
the new build and tests complete.

No screenshot is included: the local SDK build/host simulator generates and
validates the Force skin JSON but does not render the touchscreen. No Force
installation or replacement is part of this V3 task; the existing V1 plugin
remains untouched on hardware. The packaged candidate is handed to Codex 3 for
independent release validation.

## Known limitations

- Only 19 controls across 13 effects have verified live mappings. The other 37
  effects remain playable, but their factory parameters are not exposed as
  editable controls.
- The SDK JSON supports selection-dependent visibility, but does not expose a
  runtime conditional disabled state for controls based on package presence.
  Package availability is shown by the effect status; the backend rejects
  writes without an active validated descriptor.
- The local SDK validates schema and parameter bindings; final Force touch
  sizing and conditional visibility still require visual confirmation on the
  device. The user reports the installed V1 package already loads and produces
  wet audio; this branch has not been installed over that working package and
  remains gated on Codex 3's independent release validation.
