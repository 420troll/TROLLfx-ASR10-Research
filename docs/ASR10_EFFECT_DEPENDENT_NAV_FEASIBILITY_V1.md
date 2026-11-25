# ASR-10 Effect-Dependent Navigation Feasibility

**Candidate examined:** `feature/asr10-force-dynamic-editor-v4`, commit `285123fe` (editor implementation `48ca618`). The V4 tree was checked out detached in a separate read-only worktree. The QA branch is the only branch changed.

## Feasibility matrix

| Capability | Status | Finding |
|---|---|---|
| Hide/show whole TUI tabs from FX Slot | **UNSUPPORTED** | The SDK's `ui.json` page model is a fixed ordered list. Generated TUI tabs contain a fixed name and function-key indices; conditional enabling is attached to individual component bounds, not tabs. The inspected generator has no tab visibility field or runtime tab callback. |
| Automatically navigate to the selected effect's EDIT tab | **UNSUPPORTED** | The plugin API exposes parameter/audio callbacks and display refresh, but no host tab-selection/navigation call. V4's FX Slot path does not request navigation. `audioMasterUpdateDisplay` requests a display refresh, not tab selection. |
| Reassign the same Q-Links as FX Slot changes while remaining on one page | **UNSUPPORTED** | The generated Q-Link map is static by tab and maps fixed parameter indices. The SDK emits a map for each page; it does not bind a Q-Link to “the active effect's parameter.” |
| Use effect-specific static Q-Link maps on separate EDIT tabs | **SUPPORTED** | This is the V4 design. HALL EDIT Q1–Q4 map to parameter indices 27–30; ROOM EDIT Q1–Q3 map to 33–35. Manual page navigation selects each static map. The generated HALL/ROOM page-to-Q-Link contract passed the independent smoke test. |
| Dynamic displayed parameter values | **SUPPORTED** | SDK `formatValue()` can provide parameter value text; choice parameters also expose their fixed choice labels. This changes value text only. |
| Dynamic parameter names/labels on a single control | **UNSUPPORTED** in the shipped SDK wrapper | `effGetParamName` returns the fixed `Param.name`. The VST2 wrapper has no dynamic-name callback. V4's effect-qualified, fixed parameter names and one page per effect are the supported workaround. |
| Serialize more than six pages | **SUPPORTED** up to 32 | `gen_ui.py` accepts at most 32 pages and `validate.py` accepts at most 32 tabs. |
| Reach more than six pages on the original Force | **UNKNOWN** | SDK source warns that tabs beyond the six physical function keys are untested. It does not establish whether MPC/Force offers another navigation gesture for the remaining tabs. V4 emits 15 tabs with function-key indices 0–14. No Force navigation test was run. |
| Custom VST editor through the stock SDK framework | **UNSUPPORTED** | The supplied VST2 dispatcher returns 0 for `effEditGetRect`, `effEditOpen`, `effEditClose`, and `effEditIdle`. The SDK's supported editor mechanism is its TUI skin. Whether the Force host can display an independently implemented editor is **UNKNOWN** from the inspected SDK and simulator. |
| Static Q-Link banks/groups | **SUPPORTED** | The SDK documents 16 physical Q-Links arranged in banks/groups of four and emits fixed assignments for each TUI page. A page can assign up to eight static controls across Q1–Q8. This does not provide effect-driven remapping without a page change. |
| Plugin-controlled dynamic Q-Link bank/page switching | **UNSUPPORTED** by the inspected SDK API | Q-Link JSON has fixed per-tab maps; the generator sets `SubTab` to 1 and exposes no plugin callback to choose a bank. Hardware behavior for hand-authored undocumented subtab variants is **UNKNOWN**. |

`UNSUPPORTED` means the feature is absent from the inspected official SDK/API path, not a claim that proprietary MPC firmware could never implement it. `UNKNOWN` means source evidence is insufficient to establish the physical host behavior.

## Independent V4 inspection

The V4 authored `ui.json`, generated `TUI.json` and `Q-Links.json` contain **15 fixed pages**: BROWSE, MIX and 13 effect-specific EDIT pages. All are present regardless of FX Slot. For example, `01 EDIT` and `03 EDIT` are simultaneously present. The tab names identify slots numerically (`01 EDIT`, `03 EDIT`), rather than using short effect names such as `HALL` and `ROOM`. The 37 effects without promoted controls have no matching page, but their selection does not hide the other 13 EDIT pages. Therefore V4 avoids reusing hidden controls' Q-Link maps when the user manually changes pages, but it does **not** implement “show only the active effect's page,” automatic navigation, or the BROWSE+MIX-only view for effects without controls.

The V4 candidate release manifest is still `playable: false`; its Force editor validation status is `NOT_RUN`. Its release report lists a native host simulator parameter dump, but the simulator source only loads VST2, queries/sets parameter values, processes audio and tests state. It does not load `TUI.json`/`Q-Links.json`, render tabs, or provide navigation actions. A host-simulator test cannot establish tab switching.

Independent static test:

```sh
python3 tools/force_gui_qa/test_v4_static_pages.py \
  /mnt/c/Users/Gamer/research/TROLLfx-ASR10-V4-Feasibility/force_plugin
```

Result: **PASS** for authored/generated page order and HALL/ROOM-specific parameter-to-Q-Link mappings. HALL Q1–Q4 target parameter indices 27–30; ROOM Q1–Q3 target indices 33–35. This is a skin serialization/contract test, not a navigation test. The official SDK validator also passed against the V4 package: **15 tabs, 15 Q-Link maps, 0 errors, 0 warnings**. The independent layout heuristic flags eight likely text overflows in the BROWSE and MIX static text cells; the SDK has no renderer, so these remain screen-scale warnings, not confirmed Force clipping. The inspection bundle (including approximate previews, not SDK screenshots) is `qa-v4/`.

The V4 candidate release manifest identifies implementation source commit `48ca6182b9343ff86a8425081febcac9c26537ff`, has `playable: false`, and marks Force editor validation `NOT_RUN`. The packaged ARM32 candidate SHA-256 is `f4d21c09a83f13554107cfd3b73aaf19836aad13414ed8c646c3e7114084ff28`; the desktop native validation report records `cec4b055f9f21dd484ee7833c11704b5d0db7baf2f66a8bb4676d09305017ccd`. These are source/release provenance only; no candidate binary was installed or tested on the Force.

No candidate binary was installed, no MPC service was changed, and no hardware UI was operated. The detached V4 worktree remained unchanged.

## SDK source evidence

Inspected `/mnt/c/Users/Gamer/research/AkaiForceSDK` at commit `4521c247a2deae30efb9e93d53fc8f9390c51e81`:

- `tools/gen_ui.py:332–347`: authored UI has a static `pages` list; maximum 32.
- `tools/gen_ui.py:603–619`: visibility conditions become `IndexedEnabling` invalidators on controls.
- `tools/gen_ui.py:689–702`: each page becomes a TUI tab with a fixed `tabName`, `fnKeyIndex`, and `fnKeySubIndex`.
- `tools/gen_ui.py:705–721`: Q-Link maps are compiled from page grid positions to fixed parameter indices; `SubTab` is always 1.
- `tools/gen_ui.py:791–792`: tabs after six function keys are explicitly described as untested.
- `tools/validate.py:35, 451–469`: structural limit is 32; validation checks fixed tab entries and duplicate function-key coordinates, not runtime visibility/navigation.
- `docs/SDK_COMPATIBILITY.md:77–96`: documents supported widgets, per-tab parameter-index Q-Link maps, and groups of four.
- `framework/mpc_plugin.h:350–358, 390–395, 563–568`: plugin callbacks include `parameterChanged`, `formatValue`, and display refresh; display refresh does not select a TUI tab.
- `framework/mpc_plugin.h:668–676`: parameter value text and parameter name are separate dispatcher calls; name is read from the fixed `Param.name`.
- `framework/mpc_plugin.h:713`: stock editor open/close/rectangle/idle opcodes return 0.
- `tools/host-sim/host_sim.cpp` and its README: simulator supports VST load, audio processing, parameter dump/sweep and state round-trip. It has no skin parser or TUI navigation model.

Relevant candidate source is in V4 `force_plugin/ui.json`, generated `Plugin Skins/TUI.json` and `Q-Links.json`, and `force_plugin/src/ASR10FXCollection.cpp` (`parameterChanged` only marks V4 control changes; `formatValue` formats values; neither selects a page). Candidate V4 already documents the static-page tradeoff; this report reaches the feasibility result independently from SDK source and generated artifacts.

## Recommended architecture

For the existing SDK, the simplest reliable architecture is V4's **static effect-specific EDIT tabs with effect-qualified parameter IDs and per-tab Q-Link maps**, with BROWSE and MIX always present. Keep unavailable effects' controls absent. Give each editor tab a short, recognizable static effect name. Do not claim that tabs are hidden by FX Slot or that selection automatically opens the matching page. Before release, physically verify how the Force navigates all 15 tabs; if it cannot reach tabs beyond six, reduce the page count or hold the release.

If the product requirement strictly requires only one active effect EDIT page to exist/be accessible and requires automatic navigation, the current TUI/Q-Link interface cannot satisfy it. The clean solution is a supported host-side feature for conditional tabs plus selected-tab control (and effect-aware Q-Link maps), or a separately supported custom editor. Do not approximate this by leaving unrelated static pages exposed or by making hidden controls silently map to the active effect.
