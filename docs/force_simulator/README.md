# PC Force interface simulator

See [the complete simulator guide](../ASR10_FORCE_INTERFACE_SIMULATOR.md) for the one-command launch, requirements, test command, fidelity boundaries, hardware Q-Link investigation, and license notes.

The simulator reads the generated V4.1 `TUI.json`, `Q-Links.json`, and PNGs; it loads the actual plugin's native VST2 entry point and local validated factory packages. The browser offers page navigation, touchscreen-style control gestures, eight Q-Link dials, an event/DSP trace, stereo 48 kHz WAV wet/bypass processing, and layout warnings.

The committed screenshots and redacted reports are under this directory. They represent the SDK's 1280 × 628 plugin tab content region. The SDK describes that region inside a 1280 × 800 Force display; its outer host chrome is not simulated.

## Browser QA

Install the browser-test dependency and managed Chromium once, then run the real pointer interaction tests:

```sh
cd tools/force_simulator
npm ci
npx playwright install chromium
npm run test:browser
```

The tests cover BROWSE / EDIT / MIX navigation, HALL and ROOM selection, and mouse drags on HALL Q3 and ROOM Q1 through the native VST and applied-register trace. Their report is generated locally under `tools/force_simulator/test-results/` and summarized in `verification-report.json`.

The SDK build path applies the same readable text profile through `compact_skin.py` after skin generation. It changes only heading/name/value font heights and the value-label bounds inside the existing knob cell; it leaves parameter indices and Q-Link maps intact. Run `python3 -m unittest discover -s tools/force_simulator/tests -p test_skin_layout.py -v` to check zero clipping/overlap warnings and profile idempotence.
