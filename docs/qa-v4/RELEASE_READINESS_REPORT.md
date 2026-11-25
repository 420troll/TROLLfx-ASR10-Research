# ASR-10 Full-Parameter QA and Force Q-Link Readiness

Date: 2026-11-25  
Independent branch: `qa/asr10-v4-gui-independent`  
Candidate inspected: V4.1 source `28458b3a1fb8c1e12f5f1abbdb70772e40e129fa`; installed binary and maps checked read-only on the Force.

## Release decision

**NOT READY for a full-parameter release.** The evidence currently supports nineteen dynamically routed controls at their recovered discrete evidence points. It does not support full-range editing across the factory catalog. Physical Force Q-Link delivery remains **NOT VERIFIED**. This report does not authorize or perform a device update.

## Factory parameter coverage

The independent matrix contains 50 effects and 594 original manual-listed entries. Its conservative classification is:

| Classification | Count | Meaning |
|---|---:|---|
| VERIFIED | 0 | Complete original domain, expected register behavior, and audio behavior independently established |
| PARTIAL | 36 | Some recovered points/register groups exist; the complete original domain is not validated |
| UNMAPPED | 507 | No recovered register map in the inspected evidence |
| UNKNOWN | 51 | Range, choices, or identity remain ambiguous |

Thirteen additional recovered controls are recorded separately because they cannot yet be confidently joined to a manual row. V4.1 declares 19 canonical controls and 19 dynamic EDIT routes. All 19 expose only two recovered discrete points in this inspected registry. **Zero original parameter ranges are fully implemented and independently validated.** See [the machine-readable matrix](factory-parameter-validation-matrix.json) and its [source manifest](source/source-manifest.json).

## Register and range checks

The native V4.1 VST wrapper harness passed 114 point cases over 19 routes: two evidence endpoints, the nearest-point midpoint, low/high normalized clamping, and repeated maximum application. Ordered register-write groups and dynamic value labels matched the imported factory point evidence. The test also selected all 50 packages, checked HALL → ROOM → PITCH SHIFT → HALL routing/state retention, chunk round-trip for HALL, and an effect with no verified control. No out-of-range interpolated factory expectation was invented.

This is a **discrete-point/register integration PASS**, not a full-range PASS. Test details are in [the report](v41-register-range-test-report.json); run with:

```bash
PYTHONDONTWRITEBYTECODE=1 TROLLFX_FACTORY_PACKAGES_DIR=/home/gamer/asr10-force-assets-v1 \
  python3 tools/force_gui_qa/run_v41_parameter_sweep.py --all-50
```

The script uses a test-instrumented native wrapper and local private packages. It does not write package payloads into Git.

An invalid-input probe found that setting VST index 48 to NaN leaves NaN in the parameter state after processing. SDK `framework/mpc_plugin.h` clamps using comparisons that do not reject NaN, so it passes through. The visible display can still show a valid point, masking the internal invalid value. This is a **robustness FAIL for non-finite API input**, not an explanation for a physical encoder event that may never arrive. No product source or SDK was changed.

## Audio probes

Ten recovered adjacent-point pairs were rendered through Codex 1's FactoryRuntime with private RUN-boundary checkpoints and event schedules verified by hash. Each render used 48 kHz stereo and a 32,768-frame warmup. Initial measured tails were 65,536 frames; five pairs produced a nonzero difference. The five no-difference pairs were rerun with deterministic stereo noise and a 20 Hz–18 kHz logarithmic sweep over 262,144-frame tails; none changed in those probes.

| Effect / setting | Initial sine + impulse | Longer noise | Longer sweep |
|---|---:|---:|---:|
| HALL REVERB — decay 40→41 | changed | n/a | n/a |
| HALL REVERB — damping 31→32 | changed | n/a | n/a |
| ROOM REVERB — decay 64→65 | changed | n/a | n/a |
| ROOM REVERB — diffusion 50→51 | changed | n/a | n/a |
| CHORUS+REVRB — rate 24→25 | no difference | no difference | no difference |
| CHORUS+REVRB — rate amount 39→40 | no difference | no difference | no difference |
| FLANGER+REV — rate 20→21 | no difference | no difference | no difference |
| FLANGER+REV — depth 99→98 | no difference | no difference | no difference |
| DUAL DELAYS — bus 1 time 700→701 | no difference | no difference | no difference |
| DUAL DELAYS — bus 2 feedback 25→26 | changed | n/a | n/a |

The longer no-difference cases are unresolved and should be prioritized for write-schedule and signal-path investigation. They do **not** prove ineffectiveness. These are difference tests, not exact factory audio matches. Full statistics and test conditions: [audio report](parameter-audio-validation-report.json). WAVs and proprietary data remain user-local.

## Force Q-Link investigation

Read-only hardware inspection found:

- Installed ARMv7 VST SHA-256: `badefa8fa322b812adbf82166d9782e17d770d4453cb06f428b2f9ed98a3cab4`, matching the V4.1 candidate artifact.
- Installed `Q-Links.json` SHA-256: `206400c0a756eaee6fdddb4211756649cf83e50c3288e777d43294efe8e57f2a`, matching the candidate Q-Link map.
- Installed `TUI.json` SHA-256: `5afc7be6a265dfaed2e3132cdadb635af1b1993529580c69fde0046eb2adaa84`, which **does not match** the current V4.1 candidate TUI (`280a9e3b55213c799bdd4de1c89bf6494d6b39d597ca743d9e1f2ff75d0e2730`). The installed version uses larger title/control fonts and longer active labels. This plausibly explains clutter/cropping, but it does not explain encoder inactivity because Q-Link mappings and binary match.
- The generated EDIT map assigns Q1–Q8 to VST indices 46–53, with the bank selector at 54. The plugin declares `factory_edit_slot_1..8`; `parameterChanged(index, plain)` marks the slot changed, and the audio callback routes that normalized value through the currently selected effect's dynamic bank to a canonical control and then its verified register group. Direct native-host tests prove this software path works for those 19 mapped controls.
- The routing parameters and their `effGetParamName` names are static (`EDIT SLOT 1` … `EDIT SLOT 8`). `formatValue()` supplies changing display values, but the SDK's static Q-Link names are not effect-dependent. This is a potential labeling mismatch, not proof that physical events fail.

**Verified cause of physical inactivity: none established.** Specifically, the hardware-side event has not been observed entering VST2 `setParameter`. Remaining possibilities include host page/map dispatch, host parameter-index interpretation, or a Force-specific callback path; these are hypotheses only. The matching binary/map materially weakens “wrong binary” and “wrong Q-Link JSON” as explanations. The stale TUI is a confirmed visual discrepancy only.

### Safe diagnostic, if authorized for a later test build

Do not deploy a diagnostic build from this report. In an isolated copy of the exact V4.1 source, add lock-free atomics in `parameterChanged` to retain callback count, last parameter index, and last finite normalized/plain value. Expose these through a temporary read-only diagnostic display field or a test-only query path. Do not log or allocate in the audio callback. Build a separately named ARMv7 diagnostic package with a distinct hash and a one-command rollback to the known V1/V3 backup procedure. On hardware, turn one EDIT Q-Link at a time and record whether the count/index/value changes, then compare the active canonical value and DSP register trace. If the callback does not change, investigate host dispatch/map selection; if it changes but canonical/register state does not, investigate plugin routing. This test requires separate user authorization before deployment and is not performed here.

## PC editor validation

Codex 2's full-parameter editor branch was not available from the fetched refs during this run. The available V4.1 simulator worktree is Codex 3's earlier simulator branch and contains untracked local data; it was not treated as a published Codex 2 candidate. Therefore full 50-effect editor presentation, numeric entry, bank controls, and browser interaction are **NOT TESTED**. The native V4.1 wrapper routing tests above are not a substitute for browser/UI tests.

## Compatibility and release gates

| Gate | Result | Evidence / limitation |
|---|---|---|
| 50 package selections in native wrapper | PASS | V4.1 range report; local validated packages |
| 19 routed controls / recovered point register groups | PASS at tested points | 114 cases; no complete range claims |
| Full original catalog domains | FAIL / incomplete | 0 full-range VERIFIED; 507 manual rows unmapped |
| Non-finite parameter rejection | FAIL | NaN persisted at native VST parameter index 48 |
| Audio change on representative settings | PARTIAL | 5/10 changed; five no-difference cases unresolved |
| Exact OS-reference audio match | NOT TESTED | Difference-only tests |
| Full Codex 2 GUI regression | NOT TESTED | Candidate branch unavailable |
| Installed binary identity | PASS | Installed ARMv7 hash matches inspected V4.1 artifact |
| Installed Q-Link map identity | PASS | Installed map hash matches candidate |
| Installed skin identity | FAIL / stale | Installed TUI differs from candidate TUI |
| Physical Force Q-Link callback | NOT VERIFIED | No instrumentation/deployment authorized |
| MPC project save/restore | NOT TESTED | Native plugin chunk round-trip only |
| ARMv7 ABI | NOT REBUILT in this QA run | Existing installed ARMv7 artifact identity checked; no fresh cross-build |
| V1 rollback/V3 backup | PRESERVED | No write operations made to device or backups |

Overall result: **BLOCK RELEASE as a full-parameter editor.** Keep physical Force Q-Link behavior **NOT VERIFIED** until a controlled hardware callback trace is captured.

## Reproduction

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/force_gui_qa -v
PYTHONDONTWRITEBYTECODE=1 python3 tools/force_gui_qa/build_parameter_matrix.py
PYTHONDONTWRITEBYTECODE=1 TROLLFX_FACTORY_PACKAGES_DIR=/home/gamer/asr10-force-assets-v1 \
  python3 tools/force_gui_qa/run_v41_parameter_sweep.py --all-50
PYTHONDONTWRITEBYTECODE=1 python3 tools/force_gui_qa/run_independent_audio_pairs.py
```

Private asset and audio paths in these commands are user-local examples and are not packaged by this QA branch.
