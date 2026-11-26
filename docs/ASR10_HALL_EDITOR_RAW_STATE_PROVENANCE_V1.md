# HALL Variation 1 Editor Raw-State Provenance V1

## Result

The authentic factory HALL Variation 1 startup state is OS editor raw code
`0x34` (decimal 52), displayed as `DECAY TIME=40`. The editor state is a byte
in the OS parameter structure, separate from the ES5510 checkpoint's initial
GPR 6E word. This conclusion is supported by two fresh OS 3.53 probe-process
runs, the original editor's raw memory, the displayed value, and an exact match
between the OS's five ordered writes and the validated package's post-RUN
startup schedule.

The package checkpoint alone remains insufficient to initialize the editor:
its GPR 6E value is `0x2C0831`, which is not an editor raw code. Runtime state is
now resolved only after the validated firmware schedule finishes and the full
GPR 6E/5B/03/04/05 tuple matches an OS-derived raw-code group. A match on GPR 6E
alone is never used.

## OS evidence

The bounded CPU trace around the host writes records A6 and a 32-byte memory
window spanning A6−8 through A6+23. In the Variation 1 selection, A6 was
`0x0002A6ED`; byte `A6+0` (window byte 8) was `0x34`. Subsequent copies of the
same Variation 1 state used A6 `0xFFF9B913`, with the same byte at A6+0. The
Variation 2 structure was observed at A6 `0x0002A6FB` (14 bytes after the
Variation 1 structure) with raw byte `0x00`.

| OS event | DSP frame | A6 | A6+0 | LCD/effect state |
|---|---:|---:|---:|---|
| HALL program selected; first parameter group | 426655–426666 | `0x2A6ED` | `0x34` | HALL REVERB loaded |
| HALL reselected; parameter group repeated | 755924–755938 | `0x2A6ED` | `0x34` | HALL REVERB |
| Variation 1 state restored after selection | 856335–856348 | `0xFFF9B913` | `0x34` | `VAR=1 FAVORITE REVERB` |
| Variation 1 decay field selected without Up/Down edits | 886791 | — | last observed `0x34` | `DECAY TIME=40` |
| Variation 2 selected | 886134–886147 | `0x2A6FB` | `0x00` | `DECAY TIME=0` |

At the Variation 1 baseline, the OS writes these values in order:

| Order | GPR | Value |
|---:|---:|---:|
| 1 | `6E` | `0x340000` |
| 2 | `5B` | `0x080034` |
| 3 | `03` | `0x340000` |
| 4 | `04` | `0xCC0000` |
| 5 | `05` | `0x6ADFFF` |

The five writes repeat once during the same load. The host GPR writer is at OS
PC `0xFFF97792` and the observed caller return address is `0xFFF97694`. The
original raw-step routine at OS RAM `0xF8AE98` reads `(A6)`; its duplicate-bucket
path conditionally changes `(A6)` at `0xF8AEAA` or `0xF8AEC8`. This confirms
that the logical editor byte exists independently in RAM and is subsequently
used by the step routine. The exact earlier instruction that initializes or
copies the variation structure was not recovered from these bounded windows.

The selected-field marker was emitted after navigation to the editor field:
`variation=1`, page 4, `DECAY TIME=40`, at frame 886791. No parameter Up/Down
edit was scheduled by the capture-only V1 command. A second fresh process
produced byte-identical telemetry and the same selection marker. Re-selection
within each process repeated the Variation 1 `0x34` group. Variation 2 was
separately selected and observed to use its own `0x00` state. A single-process
Variation 1 → Variation 2 → Variation 1 round trip and restoration of a user
saved value remain untested.

## Correlation to the validated factory runtime

The private ROM-01 HALL package has 89 active words and RUN frame 855973. Its
213 post-RUN events end at relative DSP frame 12983; the first safe editable
frame is 12984. The final writes for the five decay registers are:

| Order | Relative frame | GPR | Value |
|---:|---:|---:|---:|
| 1 | 364 | `6E` | `0x340000` |
| 2 | 367 | `5B` | `0x080034` |
| 3 | 370 | `03` | `0x340000` |
| 4 | 372 | `04` | `0xCC0000` |
| 5 | 375 | `05` | `0x6ADFFF` |

This is an exact ordered match to the OS Variation 1 baseline. Although the
startup schedule's terminal event is later at frame 12983, these parameter
writes are not overwritten afterward. The full schedule must still complete
before the runtime treats this register group as the initial editor state.

## Runtime change

`RuntimeStatus` now reports `HallDecayEditorStateProvenance`. `Unknown` remains
the state after checkpoint load and before startup completion. For a validated
slot 1 / Variation 1 package whose schedule contains all five relevant GPRs,
the runtime waits until the schedule terminal frame and compares all five live
registers against each of the 128 OS-derived groups. Only an exact tuple match
enables `stepHallDecayTime()`. The matched raw code and display are then
reported as `ValidatedOsStartupRegisterGroup`; successful editor steps report
`OriginalOsEquivalentStep`. Reset returns to unknown until the schedule runs
again. Variation 2 and other variations remain unsupported by this API.

This is a factory-startup initialization, not a general saved-preset decoder.
If the package's startup group does not match an OS-derived group, the editor
state stays unknown and stepping fails closed. Existing separately verified
discrete controls remain separate and are not replaced by this state resolver.
The trusted package importer now records `factory_variation: 1` only for the
validated slot 1 / 89-word HALL identity, using this OS observation. Other
effects and identities keep variation `0` (unknown). The WAV test adapter
passes this metadata into the runtime; callers must not substitute a display
slot's expected variation when the importer reports unknown.

## Additional reverb evidence

One ROOM REVERB Variation 1 sweep already in the private evidence set uses the
same original raw-step routine (`F8AE98`) and duplicate-display table. The
tested GPR 03/04/05 coefficients match the HALL conversion for all 198 observed
transitions. The GPR 5B path differs for 197 comparisons. This supports reuse
of the editor byte stepping and three coefficient calculations, but not reuse
of HALL's entire five-register mapping or runtime state rules for ROOM.

## Evidence hashes and privacy

Raw logs, OS assets, checkpoint, and event schedule remain under
`/home/gamer/research/private-results/` and are not tracked in Git. SHA-256
identifiers for the relevant local artifacts:

| Artifact | SHA-256 |
|---|---|
| Fresh Variation 1 state-only OS log (both separate runs) | `84c08521533c9613474f1f00aa0bc37e8353ec6201c15951d8626a89b8d4b98e` |
| Variation 2 selection log | `fa40923f4266df58a6b3c5c06bcaace4375410c91aa56364d3fe6905392aed43` |
| Validated HALL firmware schedule CSV | `c41e0626cf80b77e32bacdba6bbcac6a24039537070a5c447c0701d84f990452` |
| OS RAM disassembly containing `F8AE98` | `c0d62126ac630b3099419d4fde961fb48ded8aa9b2586984db26cbeea2955bea` |
| ROOM Variation 1 decay sweep log | `7dd121a00b39517dfa14fefe833858d5e3a35febc14af648fe0b717adc61c7f6` |

The identical Variation 1 hashes reflect deterministic emulator output from two
separate CLI processes. These are evidence identifiers only; the private files
are not included in the repository.

## Reproduction

Capture-only state selection (no full parameter sweep):

```sh
ESP_CALLER_TRACE=1 python3 tools/parameter_controls/run_full_parameter_range_sweep.py \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --selector-inventory /home/gamer/research/private-results/asr10-all-50-effects/inventory.json \
  --slot 1 --variation 1 --field 'DECAY TIME' \
  --output /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/state-only \
  --field-timeout 30 --state-only --monitor-stdio

python3 tools/parameter_controls/extract_os_cpu_parameter_trace.py \
  --input /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/state-only/slot-01-var1-decay-time-range.log \
  --output /home/gamer/research/private-results/asr10-full-factory-parameter-recovery/state-only/parsed-cpu-trace.json
```

The probe command only selects the editor field; it does not change its value.
Keep both raw log and parsed trace in private storage.

## Validation and remaining uncertainty

- Fresh factory selection and re-selection: raw `0x34`, LCD 40, five ordered
  writes match; repeated in two independent OS CLI processes.
- Variation-specific state: V1 raw `0x34` / display 40; V2 raw `0x00` / display
  0 in a separate capture.
- Package ready boundary: all 213 writes applied by relative DSP frame 12983;
  post-schedule matching enables editor state at frame 12984.
- Full raw stepping and duplicate-bucket behavior remain covered by the
  previously verified 128-state OS transition traces; this change does not
  alter the step/conversion tables.
- Validation passed: `bash tools/audio_validation/test_factory_runtime.sh`
  (synthetic runtime tests), root Python discovery (92 tests), parameter-control
  discovery (48 tests), and the new state-capture command test (1 test).
- The strict HALL startup-ownership QA with the refreshed private importer audit
  reports `frame=12984`, zero firmware writes pending, and editor state raw 52 /
  display 40 / `ValidatedOsStartupRegisterGroup`. Its factory-reference 40/41
  wet comparison remains finite and measurably different.
- A real private-package WAV smoke processed the full 213-event schedule and
  48,000 DSP frames; it produced finite output (`RMS L=0.123581`, `RMS
  R=0.140344`, peaks 0.197540 / 0.215424). Output and source WAV remain private.
- Still unresolved: the exact OS instruction sequence that populates the
  variation parameter structure, a same-process V1→V2→V1 return capture, and
  user-saved-value restore semantics. Those cases do not seed the factory
  runtime through this change; unsupported/mismatched states remain unknown.

Focused runtime test: `bash tools/audio_validation/test_factory_runtime.sh`.
Capture-command test: `python3 -m unittest discover -s tests/parameter_controls -p 'test_parameter_state_capture_command.py' -v`.
