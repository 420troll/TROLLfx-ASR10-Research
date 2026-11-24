# TROLLfx ASR-10 Force 50-slot integration assessment

## Release decision

**Not an installable or playable release candidate.** The merged Force source
still has no connection from the plugin callback to `RegistryFactoryRuntime`;
the supplied plugin binary is from the earlier dry-pass shell. This checkout
does not contain the Force SDK required by `force_plugin/tools/build_candidate.sh`,
so no ARMv7 binary was rebuilt or inspected here. No device installation was
attempted. Do not install the existing `force_plugin/dist` candidate.

The working branch merges the requested universal runtime, Force browser, and
50-slot capture/catalog sources. The universal C++ runtime can load a
`ValidatedEffectPackage`, but the capture collection is not in that package
schema and has no Force-side manifest validator or asset importer. The
collection's `firmware-events.log` is not the runtime's bounded scheduled GPR
event format. A raw selector snapshot cannot be marked ready by setting
validation flags. In this branch the UI marks packages unavailable and emits
silence when the backend is unavailable; it no longer passes input through in
a way that could be mistaken for an effect.

## Focused slot 01–03 identity comparison

The independent reference manifests and collection package manifests were
compared by active instruction count and digest:

| Source | Display identity | Active words | Match to independent replay |
|---|---|---:|---|
| Independent ROM-01 replay | ROM-01 HALL REVERB | 89 | HALL reference |
| Collection slot 01 | HALL REVERB | 89 | Matches ROM-01 |
| Collection slot 02 | 44KHZ REVERB | 89 | Also matches ROM-01; conflicts with expected ROM-02 |
| Independent ROM-02 replay | ROM-02 44KHZ REVERB | 60 | ROM-02 reference |
| Collection slot 03 | ROOM REVERB | 60 | Matches the independent ROM-02 program digest |

This proves a catalog/package identity mismatch for slot 02 and an unresolved
identity collision at slot 03. The snapshots did match the timestamp-bounded
host instruction commits and recorded stable selector labels, so the evidence
does not distinguish display-transition timing from OS reuse of a program or
an error in how the selector ID was attached to a snapshot. It is not justified
to relabel slot 03 as ROM-02 or to substitute it into slot 02. The independent
HALL and ROM-02 replay packages remain the only acceptable playback packages
for those two named effects until the discrepancy is resolved.

## Per-slot Force status

The following status means integration/playability in the Force plugin, not
whether an emulator snapshot exists. No slot was loaded or processed by the
Force backend in this branch.

| Slot | OS name | Force status |
|---:|---|---|
| 01 | HALL REVERB | Unavailable: runtime not integrated |
| 02 | 44KHZ REVERB | Unavailable: active program conflicts with HALL |
| 03 | ROOM REVERB | Unavailable: active program matches independent ROM-02; identity ambiguous |
| 04 | DUAL DELAYS | Unavailable: no Force package loader or playback test |
| 05 | 44KHZ DELAYS | Unavailable: no Force package loader or playback test |
| 06 | CHORUS+REVRB | Unavailable: no Force package loader or playback test |
| 07 | PHASER+REVRB | Unavailable: no Force package loader or playback test |
| 08 | FLANGER+REV | Unavailable: no Force package loader or playback test |
| 09 | ROT.SPKR+REV | Unavailable: no Force package loader or playback test |
| 10 | CHOR+REV+DDL | Unavailable: no Force package loader or playback test |
| 11 | CMP+DIST+REV | Unavailable: no Force package loader or playback test |
| 12 | DIST+CHO+REV | Unavailable: no Force package loader or playback test |
| 13 | WAH+DIST+REV | Unavailable: no Force package loader or playback test |
| 14 | SMALL ROOM | Unavailable: no Force package loader or playback test |
| 15 | LARGE ROOM | Unavailable: no Force package loader or playback test |
| 16 | HALL REVERB2 | Unavailable: no Force package loader or playback test |
| 17 | SMALL PLATE | Unavailable: no Force package loader or playback test |
| 18 | LARGE PLATE | Unavailable: no Force package loader or playback test |
| 19 | REVRSE REVRB | Unavailable: no Force package loader or playback test |
| 20 | REVRSE REVB2 | Unavailable: no Force package loader or playback test |
| 21 | GATED REVERB | Unavailable: no Force package loader or playback test |
| 22 | NLIN REVRB 1 | Unavailable: no Force package loader or playback test |
| 23 | NLIN REVRB 2 | Unavailable: no Force package loader or playback test |
| 24 | NLIN REVRB 3 | Unavailable: no Force package loader or playback test |
| 25 | MULTITAP DDL | Unavailable: no Force package loader or playback test |
| 26 | EQ+DELAY LFO | Unavailable: no Force package loader or playback test |
| 27 | VCF+DISTORT | Unavailable: no Force package loader or playback test |
| 28 | GUITAR AMP1 | Unavailable: no Force package loader or playback test |
| 29 | GUITAR AMP2 | Unavailable: no Force package loader or playback test |
| 30 | GUITAR AMP3 | Unavailable: no Force package loader or playback test |
| 31 | SPKR CABINET | Unavailable: no Force package loader or playback test |
| 32 | TUNABLE SPKR | Unavailable: no Force package loader or playback test |
| 33 | EQ+CHOR+DDL | Unavailable: no Force package loader or playback test |
| 34 | EQ+VIBR+DDL | Unavailable: no Force package loader or playback test |
| 35 | EQ+FLNGR+DDL | Unavailable: no Force package loader or playback test |
| 36 | EQ+TREM+DDL | Unavailable: no Force package loader or playback test |
| 37 | PHASER+DDL | Unavailable: no Force package loader or playback test |
| 38 | 8-VOICE CHOR | Unavailable: no Force package loader or playback test |
| 39 | PITCH SHIFT | Unavailable: no Force package loader or playback test |
| 40 | PITCH+DDL | Unavailable: no Force package loader or playback test |
| 41 | FAST PITCHSH | Unavailable: no Force package loader or playback test |
| 42 | EQ+CMPRESSOR | Unavailable: no Force package loader or playback test |
| 43 | EXPANDER | Unavailable: no Force package loader or playback test |
| 44 | KEYED EXPNDR | Unavailable: no Force package loader or playback test |
| 45 | INVRS EXPNDR | Unavailable: no Force package loader or playback test |
| 46 | DE-ESSER | Unavailable: no Force package loader or playback test |
| 47 | DUCKER | Unavailable: no Force package loader or playback test |
| 48 | RUMBLE FILTR | Unavailable: no Force package loader or playback test |
| 49 | PARAM EQ | Unavailable: no Force package loader or playback test |
| 50 | VAN DER POL | Unavailable: no Force package loader or playback test |

Machine-readable per-slot status is also included in
[`ASR10_ROM_EFFECT_CATALOG.json`](ASR10_ROM_EFFECT_CATALOG.json).

## What is present and what remains

- Present: native ES5510 implementation; generic registry/runtime API;
  50-slot browser metadata and touchscreen skins; Q-Link definitions; schema
  definitions for factory packages and user presets; installer/rollback
  scripts and third-party notices.
- Not implemented: a trusted loader from the 50 collection manifests to the
  universal package schema; Force callback ownership of the runtime; 48 kHz
  host-rate adaptation in the VST; latency-aligned wet/dry, gain and bypass;
  meters; BUS controls connected to DSP; named preset save/recall; and
  end-to-end switching through all slots.
- Not verified: 50-slot package loading/stereo smoke, plugin-side HALL and
  ROM-02 audio, repeated switching, ARMv7 binary architecture, SDK packaging,
  installation directory behavior, or physical Force execution.

The original plugin artifact stays in the repository as source history, but it
must not be presented as a playable package. GPLv3 applies to the reused
emulator/runtime code; retain the repository GPL text and the SDK MIT notice
in any future package. No Ensoniq ROM, firmware, checkpoint, effect program,
event data, or audio may be distributed by this branch.
