# FX Collection VST2 factory runtime integration

Candidate source: `feature/asr10-force-pc-gui-simulator` (built in this worktree).
Runtime references: Codex 1 commits `1984744` and `64d893f`; independent QA:
Codex 3 `b800d78`.

## Integration plan and boundaries

The actual callback path remains `VST2 processReplacing` →
`ASR10FXCollection::process` → `ES5510DSPBackend::process` → the active
`FactoryRuntime::processStereo`. Package discovery, hash verification,
checkpoint loading and schedule parsing stay on the existing provider/control
and worker paths. The audio callback performs no file access, package loading,
allocation or blocking lock acquisition.

Transferred from `1984744`: fixed-capacity timestamped firmware/parameter
events, terminal-frame-derived initialization status, queued atomic parameter
groups and deferral of verified edits until the first safe frame. The separate
standalone audio adapter and CLI were not copied: the VST2 provider already
attaches its validated schedule to the descriptor consumed by `FactoryRuntime`.

Transferred from `64d893f`: editor raw state is unknown until the complete
validated startup schedule finishes and all five live GPRs (`6E/5B/03/04/05`)
match an OS-observed group. A checkpoint GPR alone cannot seed this state.
Variation 1 metadata is attached only to the validated slot-1, 89-word HALL
program with SHA-256
`34eec2eb04319c0d167a4110608e1e99f2aa13d8b7908f79852c2be3c0aefd4c`.
All other package variations stay unknown. If a queued host write overlaps one
of the five decay GPRs at startup, editor-state matching fails closed; unrelated
queued BUS writes do not invalidate the tuple.

The SDK's normal setter passed NaN through its comparison-based clamp. The
VST2 entry installs a plugin-local setter that rejects non-finite values
without changing the current parameter. Audio inputs and output values are
also sanitized at the DSP backend boundary. Finite values retain SDK setter
semantics and parameter IDs/chunks remain unchanged.

## HALL callback evidence

The simulator-only traced VST binary was loaded through its `VSTPluginMain`
entry. Tests invoke the real VST2 `setParameter` and `processReplacing`
callbacks. The validated package contains 213 ordered startup writes; its
terminal event is DSP frame 12,983 and the first safe edit frame is 12,984.
Pre-startup edits remain queued until that boundary. The VST test adapter
exposes read-only runtime status and original OS Up/Down stepping only in the
local test build; it adds no host parameter and is absent from the release API.

HALL DECAY's original display is not a unique raw-code identity. In particular,
raw 51 and raw 52 both display 40. The verified factory Variation 1 startup
group resolves to raw 52 / display 40. OS stepping skips duplicate display
buckets: Down from raw 52 reaches raw 50 / display 39; Up reaches raw 51 /
display 40; Up again skips raw 52 and reaches raw 53 / display 41. Raw 51 and
raw 52 therefore remain distinct even though both display 40. The existing
verified VST route for display 40 uses its captured raw 52 group.
The separate full-range raw-group diagnostic is test-only and does not enable
a general user-facing HALL DECAY VST parameter.

The startup writes are checked in-order against the validated local schedule,
including their exact frames, GPR indices and 24-bit values. Candidate
register traces and AUDIO LAB bundles are stored under the user's local cache;
no package, checkpoint, ROM, or WAV is included in Git.

Measured actual VST2 output for the deterministic 48 kHz stereo noise test:

| Comparison | Raw codes | Frames | A−B RMS | A−B peak |
|---|---:|---:|---:|---:|
| HALL 40/41 | 52/53 | 32,769 | 0.000259008565 | 0.00119018555 |
| HALL 10/90 | 13/115 | 480,000 | 0.00813245297 | 0.0782165527 |
| HALL 0/99 | 0/127 | 480,000 | 0.0155422813 | 0.0981750488 |

For 10/90 and 0/99, both individual A/B RMS values and the A−B RMS/peak
matched Codex 3's independent standalone-runtime results exactly at the
reported precision. This establishes callback-path output and register-group
behavior for the tested package; the standalone WAVs remain reference output,
not actual VST audio. The 40/41 pair is the existing exact verified host route.

The unmodified Codex 3 binary harness was designed for a 12-parameter VST ABI;
this candidate keeps the current 64-parameter registry. Running it against the
candidate reports `BINARY_FAIL unexpected plugin parameter ABI` before its
other callback cases. Its source was copied to `/tmp` and only the stale
`numParams` expectation was changed from 12 to 64. That adjusted harness passed
all 50 effects, effect-switch/startup races,
restart, state chunks, wet/dry/gain/bypass, zero callback allocations and
non-finite parameter/audio cases. Separate API tests also reject NaN and both
infinities on every VST parameter index without mutation.

Automated results: Python simulator suite 46/46 passed; browser suite 22 passed
with one real-private-bundle test skipped because its browser fixture was not
configured; C++ FactoryRuntime and native HALL adapter tests passed. The suite
logs include the SDK's existing `snprintf` truncation warning and the test's
custom allocation-hook `new`/`delete` warning; neither caused a test failure.

## Acceptance status

Completed callback checks (as of this revision):

- HALL DECAY 40/41 output comparison through VST2 callbacks; both output
  streams are finite and their difference RMS is nonzero.
- Startup schedule count/order, terminal frame, deferred write counts and
  completion status; expected five-GPR groups and application frames.
- HALL 10/90 and 0/99 test-only raw groups through the actual VST2 path;
  measurements reconciled against Codex 3 standalone references at 48 kHz,
  wet 100%, unity input/output gain, no normalization, and the recorded
  two-frame runtime latency. These raw-group test renders are VST output;
  the comparison references remain standalone output.
- HALL raw-state resolution to Variation 1 raw 52 after startup and OS-style
  Up/Down stepping with raw/display state kept separate.
- Non-finite parameter rejection for NaN and both infinities; non-finite
  stereo input produces finite output. Existing chunks and the 19 verified
  routes are covered by the simulator regression suites.

The adjusted Codex 3 harness passed again against the SDK-built production
x86-64 binary: `BINARY_PASS`, 50/50 slots, state round-trip, switch/restart and
startup races, wet/dry/gain/bypass, zero callback allocations, NaN/±infinity
parameter rejection, and non-finite audio handling. A focused production-binary
HALL 40/41 test used VST2 parameter index 29 (`DECAY TIME`), the actual
`setParameter` callback, and `processReplacing` after startup; its 32,768-frame
stereo output difference RMS was `0.000150020285`.

The SDK `build.py --target all` completed from source commit `9ef73e6` with zero
validation errors and warnings. Native host simulation and both ARM package
targets were produced. The native/ARM32 SHA-256 values are also bound in
`/tmp/asr10-vst2-packaged-qa.json`; ARM64 was SDK-built and ABI-validated.

| Binary | SHA-256 |
|---|---|
| x86-64 native VST2 | `dd5f964ecc8f856ece67793a8154e1881a50a9f465f292144a1725bf41782e26` |
| ARMv7 hard-float VST2 | `4af2be5d75515c89e83be798e2133cd60bc9640a5dcd26b48c5d2ef1d027868f` |
| AArch64 VST2 | `2b99e3f7d9dd21d23adc3331231ddf407981b61f231b267422e0ca897a6ef105` |

`force_plugin/tools/test_packaged_vst.py` passed all 50 slots, missing-package
silence, SDK host simulation, and callback allocation checks against the
x86-64 binary. `force_plugin/tools/test_es5510_backend.sh` passed its private
package backend and VST-wrapper HALL/ROOM/ROM-02 checks. ARMv7 ELF32/ARM,
ARMv7-A, and hard-float ABI attributes were verified. ARM QEMU execution was
not run because `qemu-arm` is not available in this environment. No binary was
installed on a Force.

Still gated or requiring further evidence:

- No general full-range HALL VST host parameter is enabled. The diagnostic raw
  override is not a production route; the stable public parameter list and
  saved-state layout are unchanged.
- The exact original VST2 independent harness at Codex 3 commit `b800d78`
  asserts a 12-parameter ABI, while this editor candidate exposes 64 stable
  parameters. Run an ABI-adjusted temporary copy for callback/state coverage;
  record the unmodified harness result as blocked at its stale parameter-count
  assertion.
- ARMv7 QEMU and physical Force behavior remain untested; `qemu-arm` is absent
  and nothing was installed on a Force.
- The candidate has no accepted same-state original-OS WAV versus VST2 audio
  comparison. Standalone reference reconciliation is not hardware-equivalence
  proof.

## Reproduction

```sh
export AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK
export TROLLFX_FACTORY_PACKAGES_DIR=/home/gamer/asr10-force-assets-v1
export TROLLFX_HALL_DECAY_NATIVE_GATE=1  # simulator/test binary only
python3 tools/force_simulator/build.py --force --sdk "$AKAI_FORCE_SDK"
python3 -m unittest discover -s tools/force_simulator/tests -v
bash tools/audio_validation/test_factory_runtime.sh
```

Keep the private package root local. The simulator build and the test gate do
not install or alter any Force assets.
