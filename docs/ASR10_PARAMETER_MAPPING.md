# ASR-10 effect parameter to ES5510 mapping

**Status: one standalone factory effect parameter is validated.** The capture
and ROM/effect files are private and remain outside this repository. REA/Ghidra
was unavailable in this session; the conclusions combine native-emulator
host-write capture, UI display capture, a service breakpoint, and a controlled
audio comparison.

## Verified example

| ASR-10 effect / visible parameter | Displayed change | ES5510 host write |
|---|---|---|
| `44PARAM EQ`, `BASS GAIN` | `+3` → `+4` | GPR `0x56`: `0x00b500` → `0x00cb00` |

The reverse edit (`+4` → `+3`) wrote `0x00b500` to the same GPR, and a repeated
increase wrote `0x00cb00` again. Each single UI action produced one GPR commit.
The observed one-step raw delta is `0x1600`; this does not establish the full
scale, endpoint behavior, or interpolation law for this or other parameters.
The ASR-10 parameter index is not treated as an ES5510 address.

The event log records the three edit commits at PC `0xfff97792`. They occurred
at ES5510 frames 676138, 724715, and 768872 respectively. A no-edit control
window produced no host commits. The display log showed the matching `+3`,
`+4`, `+3`, `+4` sequence. The effect object was selected as standalone file 10
(`44PARAM EQ`); its loaded code was checked against the existing private EFE
source correlation.

## Update path and timing

Existing static object analysis identifies `FxUpdateTask` at object offset
`0x0452`, helper `0x0564`, then updater `0x0468` twice. The updater reads
parameter-relative state, applies value preparation/interpolation, and calls
absolute service `$801e`. These are effect-object offsets, not ASR-10 GPRs.
During the edited run, a 68k breakpoint at the OS 3.53 binding target
`$0071c6` (the ROM binding-table target for service slot `$801e`) fired at
21.1257 seconds, immediately after the `+3` to `+4` action. Thus the dynamic
trace confirms the parameter update reaches the bound service. The trace and
the subsequent host commit at `0xfff97792` support the service-to-host-write
path; they do not by themselves prove the service's internal implementation
or that every effect uses the same path. The separate host-writer routine is
the point at which the ES5510 GPR commit is observed.

Updates were not continuous in the measured edit window: one host commit
followed each action. No intermediate sequence of GPR values was observed, so
this capture does not establish a ramp rate or prove click suppression. The
static updater's interpolation behavior needs additional captures across
parameters and values. The evidence also does not distinguish a parameter
that is copied immediately from one whose current value was prepared earlier
in the update task.

## Audio measurement

The control and edited runs used the same 50 Hz test input and routing. The
pre-edit audio was bit-identical. In the first second after increasing gain,
output RMS changed from about 7298 in the control to 7994 in the edited run
(PCM16 scale); after a repeated increase, the sustained edited RMS was about
8088 versus 7298 in the control. The difference signal was nonzero, so the
register change had a measurable audible-path consequence. After decreasing
gain, a short residual remained, consistent with filter state settling; it
was not used as proof of a separate mapping.

## Reproduction

Use a verified OS 3.53 setup and keep all ROM, disk, effect, logs, and WAV files
outside Git. Set `ESP_HOSTLOG=1`. In the native emulator, select file 10
`44PARAM EQ`, enter Edit mode, select the Effects page, then move the cursor
to `BASS GAIN`. Confirm that the display reads `+3`. Keep the same 50 Hz input
and routing for control and edit runs. Place `--param-mark` markers on either
side of one Up action, then repeat with Down and Up. The tested panel codes
were Effects selection 9, Up 10, Enter 35, Edit 5, and Right 17; confirm the
displayed effect and parameter before interpreting a capture.

Analyze a private host log with:

```sh
python3 tools/parameter_host_diff.py capture.log \
  --before before_gain --after after_gain --include-values
```

Omit `--include-values` for a redacted summary. Compare the capture with the
matching no-edit log and repeat both directions. `--include-values` output,
host logs, effect objects, firmware, and renders contain private material and
must stay outside the repository. Existing tooling for verifying an effect
capture against source is `tools/compare_asr10_effect_capture.py`.

## Limits and evidence

This is one verified mapping for one factory effect on one OS setup. It does
not establish mappings for other controls, effects, or DP/4 parameters; nor
does it prove a general scaling curve, interpolation cadence, or click
suppression. The redacted report intentionally contains only the values needed
to document this single example. Raw captures and private hashes are retained
in the local research results directory and are not included here.

The associated tracing changes add sequenced cycle/frame/PC metadata to
`ESPHOST` events and labeled `--param-mark` timing markers. Tests cover event
parsing and redaction behavior in `tests/test_parameter_host_diff.py` and
`tests/test_effect_capture_compare.py`.
