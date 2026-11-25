# ASR-10 V4 Independent GUI and Q-Link QA

## Result summary

| Area | Result | Evidence |
|---|---|---|
| V3 package/skin SDK structural validation | PASS | SDK `validate.py --strict`: 0 errors, 0 warnings; V3 ARM32/ARM64 binaries, VST entry points, tabs, referenced art and Q-Link values accepted |
| V3 source-level GUI usability | FAIL / warnings | User reports physical touchscreen/Q-Link usability failure; independent static inspection found 7 likely overflowing strings and 19 static Q-Link assignments for conditional controls |
| V3 parameter-to-Q-Link grid position | PASS | All generated V3 bindings agree with SDK's 4×4 Q-Link slot rule |
| V3 internal register writes from host Q-Link events | NOT TESTED | Existing binary harness proves VST parameter/display round-trip only; it has no internal parameter/register trace |
| V3 physical touchscreen and physical Q-Link events | NOT TESTED independently | No new hardware interaction performed |
| Factory parameter coverage | 50 effects / 594 manual entries / 19 register mappings / 0 end-to-end Q-Link verified | Machine matrix is `qa-v3/factory-parameter-coverage.json` and CSV |
| V2/V3 audio response | 11 total reported changed controls | V2 reports 10/16 aggregate with no public per-control attribution; V3 specifically reports PITCH SHIFT QUALITY changed. Per-effect V2 counts remain unknown. |
| Physical audio/CPU effect matrix | NOT TESTED | Use read-only sampler and procedure in acceptance doc |
| V4 comparison | PENDING | No Codex 2 V4 editor branch is currently published |
| V1 rollback | PRESERVED | No access or changes to `/media/SSD250g/TROLLfx/ASR10/rollback-v1-20261125/` |

The installed plugin was left untouched. Only read-only SSH hash inspection was performed. No restart, mount change, install, or Force file write occurred.

## Reproduction

Read-only source tree: `/mnt/c/Users/Gamer/research/TROLLfx-ASR10-V3-ReadOnly`, detached at `3466ad2ff72908dba94f1fa2512fe6a73a020bd6`. The installed V3 ARMv7 binary hash is `18b5272b5c0b5656bb1f81a24d81490b0283b5c7a4397142375595685d0f771c` (read-only device hash and local V3 artifact matched). Installed `TUI.json`, `Q-Links.json` and panel background hashes also matched the local bundle; see the root-cause report for exact digests.

Independent skin analysis (all paths should point at the candidate tree):

```sh
python3 tools/force_gui_qa/inspect_skin.py \
  --ui /path/to/candidate/force_plugin/ui.json \
  --tui "/path/to/candidate/force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/Plugin Skins/TUI.json" \
  --qlinks "/path/to/candidate/force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/Plugin Skins/Q-Links.json" \
  --assets "/path/to/candidate/force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/Plugin Skins" \
  --registry-header /path/to/candidate/include/trollfx/es5510_factory_editor_v03.hpp \
  --out /tmp/skin-inspection.json --preview-dir /tmp/skin-preview
```

The optional preview is an approximate placement overlay, not an SDK or Force screenshot. Warnings are not silently converted to passes.

Generate the 50-effect coverage matrix using the V3 public evidence files:

```sh
python3 tools/force_gui_qa/make_parameter_coverage.py \
  --catalog /path/to/docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json \
  --recovery-v2 /path/to/docs/ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json \
  --recovery-v3 /path/to/docs/ASR10_FACTORY_PARAMETER_RECOVERY_V03.json \
  --registry /path/to/docs/ASR10_FACTORY_EDITOR_REGISTRY_V03.json \
  --out /tmp/factory-parameter-coverage.json
```

Validate a separately recorded, binary-bound Q-Link trace with `python3 tools/force_gui_qa/validate_qlink_trace.py TRACE.json`. The gate rejects missing host-event, internal-state, intended register-group, unrelated-state, reversal, repeat, save/reload, availability or provenance evidence. It is a validator, not a trace recorder. The current V3 host harness does not emit that evidence.

Focused QA tests:

```sh
python3 -m unittest tests.test_force_gui_qa -v
```

SDK structural validation was run read-only against the V3 package using `/mnt/c/Users/Gamer/research/AkaiForceSDK/tools/validate.py --strict <V3 plugin package>` and returned `0 errors, 0 warnings`. This validator result does not include visibility/Q-Link semantics or live screen rendering.

## Evidence limits

- Physical symptom report is the user's observation; this task did not reproduce it on the touchscreen.
- Static Q-Link/visibility mismatch is source-confirmed. The user-visible stale Q-Link label and any register write failure still need physical event logging.
- Text overflow findings are estimated from authored 30 px font size and 278 px width. Exact Titillium Web glyph metrics and MPC clipping are not available in the local SDK renderer.
- Existing V3 binary test checks choice/display values, wet output and other package behavior. It does not prove the 19 controls' intended DSP write groups.
- The per-effect matrix distinguishes manual documentation, observed mappings, audio response, runtime availability, GUI exposure and physical verification. Do not claim that all 594 manual parameters are editable.
- No proprietary package data, ROM, checkpoint, firmware, capture, audio or private state is included.
