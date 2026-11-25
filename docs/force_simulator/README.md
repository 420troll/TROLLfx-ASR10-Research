# PC Force interface simulator

See [the complete simulator guide](../ASR10_FORCE_INTERFACE_SIMULATOR.md) for the one-command launch, requirements, test command, fidelity boundaries, hardware Q-Link investigation, and license notes.

The full catalog-driven PC editor and its mapping/state rules are documented in [ASR-10 full-parameter PC editor](../ASR10_PC_FULL_PARAMETER_EDITOR.md). Current editor captures: [HALL](screenshots/pc-editor-hall-bank-1.png), [ROOM](screenshots/pc-editor-room-bank-1.png), [PITCH SHIFT bank 1](screenshots/pc-editor-pitch-bank-1.png), [PITCH SHIFT bank 2](screenshots/pc-editor-pitch-bank-2.png).

The simulator reads the generated V4.1 `TUI.json`, `Q-Links.json`, and PNGs; it loads the actual plugin's native VST2 entry point and local validated factory packages. The PC editor reads all 594 catalog descriptors, supports eight virtual Q-Links per effect-dependent bank, retains local per-effect drafts, and sends only exact values from the current native VST registry. It also provides the separate SDK skin preview, an event/DSP trace, stereo 48 kHz WAV wet/bypass processing, and layout diagnostics.

The committed screenshots and redacted reports are under this directory. They represent the SDK's 1280 × 628 plugin tab content region. The SDK describes that region inside a 1280 × 800 Force display; its outer host chrome is not simulated.

## Browser QA

Install the browser-test dependency and managed Chromium once, then run the real pointer interaction tests:

```sh
cd tools/force_simulator
npm ci
npx playwright install chromium
npm run test:browser
```

The tests cover documented-range inspection, exact-point VST writes versus unsupported drafts, observed enumerations, HALL/ROOM/PITCH selection and state retention, bank selection, mouse Q-Link drags, SDK preview navigation, and card overlap. They also capture the four screenshots above. Their report is generated locally under `tools/force_simulator/test-results/`.

The SDK build path applies the same readable text profile through `compact_skin.py` after skin generation. It changes only heading/name/value font heights and the value-label bounds inside the existing knob cell; it leaves parameter indices and Q-Link maps intact. Run `python3 -m unittest discover -s tools/force_simulator/tests -p test_skin_layout.py -v` to check zero clipping/overlap warnings and profile idempotence.
