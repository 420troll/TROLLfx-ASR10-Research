# HALL Audio Comparison Lab (desktop)

The desktop simulator has an **AUDIO LAB** workspace for comparing already rendered HALL REVERB pairs. It accepts explicit PCM output artifacts; it does not start the ES5510 runtime, touch the native VST, access factory packages, or convert displayed DECAY values to raw codes. The full-range production gate and existing VST identities/routes are unchanged.

## Data source and available pairs

Use the pair artifacts exported by Codex 3's independent runner or another reviewed diagnostic runner. The importer requires a pair to share one source class, HALL slot, variation, stimulus, sample rate and frame count. It keeps these source labels separate:

- `standalone_experimental_runtime`
- `actual_vst_audio`
- `original_os_reference`
- `ui_fixture` (synthetic UI tests only; never ASR-10 audio evidence)

The lab offers the suggested `10 vs 90`, `0 vs 99`, `25 vs 75`, and `40 vs 41` cases only when an imported bundle contains them. Stimulus choices come from those artifacts. Duration reports the rendered length; the slider changes the analysis window only. The processing rate, WAV sample rate, Variation, package/checkpoint provenance state, runtime state, and register update frames are displayed from the bundle.

The current public Codex 3 summary reports a nonzero difference for HALL 40/41 but marks its WAVs as user-local. It does not provide 10/90 audio or an importable WAV bundle. Therefore there is no public/committed 10-vs-90 render yet. The browser screenshot `screenshots/pc-editor-audio-lab-fixture.png` is explicitly labeled **UI TEST FIXTURE · synthetic only** and demonstrates layout, plots, playback and export—not ASR-10 behavior.

## Artifact contract

The machine-readable bundle schema is [hall-audio-artifact.schema.json](../../tools/force_simulator/data/hall-audio-artifact.schema.json); the packer's path-free sidecar schema is [hall-audio-pair-metadata.schema.json](../../tools/force_simulator/data/hall-audio-pair-metadata.schema.json). Each `cases[]` row carries a `case_id`, stimulus kind, and A/B renders. Each render includes a displayed value, optional raw code with an explicit evidence basis, WAV PCM bytes (Base64), DSP/runtime/firmware-initialization status, processing rate, path-free package provenance state/ID/commit, and register/frame observations. The provenance shown is what the artifact reports; the viewer does not revalidate private packages. The raw code is never inferred from the displayed value. Register values and local file paths are intentionally not accepted.

To package two WAV files produced by a runner, create a metadata sidecar (no paths) with this shape:

```json
{
  "source": "standalone_experimental_runtime",
  "variation": 1,
  "stimulus": "sine_sweep",
  "case_id": "10_vs_90_sweep",
  "a": {
    "display_value": 10,
    "raw_code": null,
    "raw_code_basis": "not_reported",
    "dsp_status": "applied",
    "runtime_status": "ready",
    "firmware_status": "initialized",
    "processing_rate_hz": 48000,
    "package_provenance": "validated_factory_checkpoint",
    "provenance_id": "approved-provider-entry-id",
    "source_commit": "ce4bfdaa",
    "register_updates": []
  },
  "b": {
    "display_value": 90,
    "raw_code": null,
    "raw_code_basis": "not_reported",
    "dsp_status": "applied",
    "runtime_status": "ready",
    "firmware_status": "initialized",
    "processing_rate_hz": 48000,
    "package_provenance": "validated_factory_checkpoint",
    "provenance_id": "approved-provider-entry-id",
    "source_commit": "ce4bfdaa",
    "register_updates": []
  }
}
```

Then run from `tools/force_simulator`:

```sh
python3 audio_lab_pack.py --metadata pair-metadata.json \
  --a-wav setting-a.wav --b-wav setting-b.wav --output hall-pair.json
```

Import `hall-pair.json` in the AUDIO LAB. The packer copies only WAV bytes and the allowlisted metadata into the bundle; its input/output paths are command-line arguments and are not serialized. WAVs must be uncompressed stereo integer PCM, 16/24/32 bit, at a matching sample rate and duration.

## Measurements and exports

The lab computes per-channel and stereo RMS/peak, A−B difference RMS/peak, stereo waveform min/max traces, 20 ms RMS tail envelopes, and register timing marks. A/B and difference WAVs can be downloaded and played by the browser audio controls. The report export contains measurements, source/evidence labels, hashes of the WAVs, and register/frame timing; it excludes WAV payloads, original filenames, filesystem paths and package contents. Uploaded bundle metadata is allowlisted and invalid/private path fields are rejected.

## Validation

The committed run summary is [audio-lab-test-results.json](audio-lab-test-results.json).

From the repository root:

```sh
python3 -m unittest discover -s tools/force_simulator/tests -v
cd tools/force_simulator && npm run test:browser
```

The `test_audio_lab.py` suite checks deterministic metrics, raw-code non-inference, stereo audio integrity, exact plot-data bins, source separation, private-field rejection and mismatched-pair rejection. The Playwright test imports a labeled synthetic fixture, checks setting labels and plot colors, decodes and plays WAV audio in Chromium, exercises stimulus/duration selection and report download, and verifies the AUDIO LAB sends no `/api/control` or `/api/set` requests. Existing browser tests continue to exercise the editor and VST routes.

## Codex 3 real HALL artifact validation

The real-artifact Playwright test accepts local paths through `TROLLFX_HALL_AUDIO_LAB_BUNDLE_DIR` and `TROLLFX_HALL_AUDIO_LAB_QA_REPORT`; these paths are not embedded in the test output. It imports all four Codex 3 bundles (experimental 48 kHz and factory-reference processing rate, each with impulse and noise-burst stimuli), checks the supplied bundle SHA-256 values, effect/variation, display/raw pairs, runtime/firmware/register status, and reconciles browser-decoded A/B and difference measurements plus 8–10 second tail RMS against Codex 3's independent report. It also verifies both WAV elements decode to their full duration and can play in Chromium, both stereo waveforms and envelopes render, the difference plot is visible, repeated PCM32 hashes match, and no VST control-write request occurs.

Run it with:

```sh
TROLLFX_HALL_AUDIO_LAB_BUNDLE_DIR=/path/to/audio-lab-export \
TROLLFX_HALL_AUDIO_LAB_QA_REPORT=/path/to/ASR10_HALL_AUDIO_LAB_EXPORT_V1.json \
npx playwright test -c playwright.config.js -g 'imports Codex 3 real HALL'
```

The verified browser report is [`real-audio-lab-browser-results.json`](real-audio-lab-browser-results.json). Four screenshots capture the real data: [experimental 48 kHz impulse](screenshots/pc-editor-audio-lab-real-experimental48000-impulse.png), [experimental 48 kHz noise burst](screenshots/pc-editor-audio-lab-real-experimental48000-noise_burst.png), [factory-reference impulse](screenshots/pc-editor-audio-lab-real-factoryreference-impulse.png), and [factory-reference noise burst](screenshots/pc-editor-audio-lab-real-factoryreference-noise_burst.png). The displayed source is the **standalone experimental native ES5510 runtime** in both processing-rate modes; it is not audio captured from the native VST or the physical Force, and “factory reference” identifies the runtime's processing-rate mode, not original-OS reference audio. The synthetic fixture remains explicitly labeled synthetic.

Playback was verified in Chromium through WAV metadata decode and successful `HTMLAudioElement.play()` state. This verifies simulator/browser playback only; it says nothing about physical Force audio or whether a setting affects the DSP.

No Force SDK package was built or installed. ARMv7 and physical-device behavior remain outside this desktop lab.
