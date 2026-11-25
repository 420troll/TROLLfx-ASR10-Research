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

## Retro graphics integration

The graphics pack from `feature/asr10-retro-graphics-v3@febda4f` is now
integrated into the actual generated skin. `force_plugin/ui.json` selects
`panel_background.png` and the `ff00c7c2` cyan accent. The release build stages
the SDK-ready art under `force_plugin/assets/`; the SDK emits the background
reference in `TUI.json` and copies the branded background plus custom SDK kit
film strips/buttons into `Plugin Skins/`. The skin includes the background,
knob/fader strips, toggle and segment button states. The graphics manifest and
credits remain alongside the source art.

The visual follows the retro charcoal, brushed-panel, cyan and pale-LCD concept,
but it is not a pixel-identical recreation. The graphics branch did not contain
a supplied Force screenshot/mockup for direct comparison. The SDK supports a
static full-page background and native controls, not separate dynamic LCD/card
images, arbitrary tab artwork, Q-Link image badges, or per-control unavailable
art. Those remain reference assets; effect names, values, status and Q-Link
behavior stay in the native generated widgets and maps. The same background is
used on each tab. A Force display review is still needed to confirm final
readability and fit.

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

The final candidate in `force_plugin/dist/TROLLfx - VST - ASR10 FX Collection`
is built from source commit `ef6d185a428881863ba5ab308319feba58e9b715`, with
source-input SHA-256
`167a3f83a109e49582c75b9fae097ae3b59451ca2ca685bbd42341498376c1c8`, using
SDK commit `4521c247a2deae30efb9e93d53fc8f9390c51e81` and Zig 0.17.1.

| Artifact | SHA-256 | Verification |
|---|---|---|
| Native x86_64 VST2 | `fa4f514c38a441438516415e21f1cd92742fe8364a2b7b583950927608b8fdf6` | Native binary-bound test and SDK host simulator passed |
| ARMv7 hard-float VST2 | `18b5272b5c0b5656bb1f81a24d81490b0283b5c7a4397142375595685d0f771c` | ELF32 ARMv7 / hard-float, SDK validation, and QEMU VST execution passed |
| ARM64 VST2 | `53e1732f017440afa471fb876ed4a5c0999d02f696591ff54393b7a6c7e123d0` | ELF64 AArch64 and SDK package validation passed |
| Native binary playback report | `beb707af51882062e7e6a346638b70422de20a0b2edb52bfcd23610c97e1d85f` | 50 eligible packages, 27 parameters, all 19 verified points, zero callback allocations |
| ARM32 QEMU report | `49230c16023982b0955e9863c98a35946c56097b2c0c06452f27fdbcfe5fef23` | 50 ARMv7 binary-bound package renders and assertions passed under QEMU 8.2.2; not hardware validation |

The native binary test verifies the VST entry point, all 50 factory packages,
both verified points for all 19 factory controls, stereo finite/non-silent
output, missing-package silence, host wet/dry/gain/bypass, switching, host
chunk restore including a V3 control, and zero callback allocations. The
QEMU run checks the same ARM32 VST entry and 50-slot playback path; the
release directory contains per-slot finite-output metrics and exact plugin,
input, package-index, and render hashes. Its checks are emulated and do not
prove Force hardware behavior. The generated map preserves EDIT Q1–Q16 →
indices 8–23 and assigns the new EDIT 2 controls to Q1–Q3 → indices 24–26.
SDK validation reports four tabs, parameter handles in 0–26, zero errors, and
zero warnings. Both ARM binaries require at most GLIBC 2.27.

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

Final regression results: 80 repository unit tests passed; the 5 release
infrastructure tests passed with `AKAI_FORCE_SDK` set; the 19-control
registry tests passed; synthetic runtime, native VST wrapper, all-50 native
binary package playback, ARM32 QEMU package playback, catalog/Q-Link checks,
and package checksum validation passed. The QEMU test harness is
`force_plugin/tools/test_arm32_vst_qemu.py` and writes a redacted JSON report;
its generated audio and temporary package assets remain outside Git.

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
