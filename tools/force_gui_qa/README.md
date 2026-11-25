# Independent Force GUI QA tools

These tools operate on authored UI JSON, generated TUI/Q-Link JSON, parameter descriptors, the registry header and skin assets. They do not install or communicate with a Force.

## Skin inspection

`inspect_skin.py` checks top-level component bounds against the 1280×628 SDK canvas, per-page duplicate/unlinked parameters, Q-Link targets and their 4×4 grid positions, conditional visibility versus the editor registry's effect slot, parameter descriptor/label consistency, missing/unreferenced artwork, and likely static-text overflow. It emits JSON plus Markdown findings. Optional PNG output is an approximate overlay and never represents SDK or Force rendering.

Example:

```sh
python3 tools/force_gui_qa/inspect_skin.py \
  --ui /src/force_plugin/ui.json \
  --tui "/src/force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/Plugin Skins/TUI.json" \
  --qlinks "/src/force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/Plugin Skins/Q-Links.json" \
  --assets "/src/force_plugin/dist/TROLLfx - VST - ASR10 FX Collection/Plugin Skins" \
  --params /tmp/host-sim-params.json \
  --registry-header /src/include/trollfx/es5510_factory_editor_v04.hpp \
  --out /tmp/skin-report.json --preview-dir /tmp/skin-preview
```

Parameter descriptors may be a JSON array or host-simulator object with a `params` or `parameters` array. Registry header parsing recognizes `FactoryControl {parameter_index, slot, id, label}` rows. Omit `--registry-header` only when no source registry is available; effect ownership will then be unverified.

## Coverage matrix

`make_parameter_coverage.py` takes public manual catalog, V2/V3 recovery evidence, and registry JSON to produce JSON and CSV rows for all 50 effects. It uses minimum verified field counts and preserves unknown per-effect audio attribution as `null` while retaining the published aggregate.

`make_acceptance_matrix.py` adds an effect row for every slot and a control row for every promoted registry control. It records structural assignment findings separately from physical end-to-end status.

## Q-Link event gate

`validate_qlink_trace.py` validates independently recorded traces. It requires exact candidate source and binary provenance, an expected-control coverage list, effect/page/bank/Q-Link selection, matching physical label, host event, internal parameter before/after state, expected and observed ordered register groups, unrelated-state invariance, reverse and save/reload restoration, repeated-value stability, and availability. Each expected control must have a matching case. A host event or display update by itself does not pass the DSP-write check.

The current V3 VST test harness does not emit internal/register trace evidence; the validator does not fabricate it. Add a trace recorder only through the owning integration branch after its interface is reviewed. Do not add test-only hooks to production or DSP arithmetic as part of independent QA.
