# HALL AUDIO LAB export, V1

This export packages the existing HALL extreme-range renders for Codex 2's
AUDIO LAB. It does not regenerate DSP captures or change factory DSP code.

## Private files and import

The original 44 float32 stereo WAVs remain unchanged in the private results
directory. The AUDIO LAB bundle files and their PCM32 WAV payloads are in its
`audio-lab-export/` subdirectory. Exact local paths are provided in the task
handoff, not embedded in this public document.

The PCM32 files are private import copies at the original frame count and
sample rate. They are direct signed PCM32 encodings of the float samples, with
no gain scaling or normalization. AUDIO LAB currently rejects float WAV, so
the bundle uses those PCM32 files. Original float WAVs and proprietary package
assets are not included in Git.

In Codex 2's simulator worktree, launch its local AUDIO LAB with:

```sh
cd "$CODEX2_WORKTREE/tools/force_simulator"
python3 launch.py --sdk "$AKAI_FORCE_SDK" --assets "$ASR10_FORCE_ASSETS" --port 8765
```

Then open `http://127.0.0.1:8765`, choose **AUDIO LAB → Import comparison
bundle**, and import each of the four `hall-audio-lab-*.json` files above.
The local import/analysis endpoint is
`http://127.0.0.1:8765/api/audio-lab/import`.

The exporter validated all four bundles with Codex 2's `audio_lab.analyze_bundle`
(`PASS_FOR_ALL_FOUR_BUNDLES`). The tested module SHA-256 and Codex 2 branch
revision are in the JSON manifest. At export time that AUDIO LAB implementation
was present in Codex 2's local worktree but had uncommitted changes; this is a
local contract validation, not evidence that the published branch already
contains the importer. The validator's own seven tests also passed in that
worktree. Revalidate after importing into the final published simulator.

## Contents and evidence

The machine-readable companion
[`ASR10_HALL_AUDIO_LAB_EXPORT_V1.json`](ASR10_HALL_AUDIO_LAB_EXPORT_V1.json)
records:

- HALL REVERB, Variation 1, OS 3.53, active program, checkpoint, program,
  firmware schedule, and runtime source hashes.
- 213/213 startup schedule writes; final scheduled frame 12983 and settle
  frame 12985; identical post-schedule initial register state; stereo serial
  routing and original five-register update order.
- All 44 original float WAV names and SHA-256 hashes, plus each PCM32 import
  WAV name/hash, processing rate, stimulus, raw code/display value, duration,
  RMS/peak, stereo correlation, and tail-energy windows.
- Sixteen A/B cases: 10/90, 0/99, 25/75, and 40/41 for impulse and noise burst
  at both the factory reference clock and experimental 48 kHz. It includes
  exact A/B raw-code identities and measured RMS/peak differences.
- Four log-scale decay-envelope plot names. Additional raw 51/52 duplicate
  display and same-raw repeat comparisons remain in the QA measurements.

For display values with multiple raw encodings, the selected A/B cases use
raw 115 for display 90 and raw 51 for display 40. They are the explicitly
selected OS-observed representations recorded by the test matrix; the extra
raw 116 and 52 renders remain separately represented in the 44-render list.

## Results and scope

All 44 source renders were finite and the repeated renders were deterministic.
The four requested A/B settings produce nonzero measured differences in both
stimuli and both rates; same-state repeats are exact. Per-render measurements,
tail-energy bands, and hashes are in the manifest. The plots are available in
[`plots/`](plots/). These results establish different standalone runtime
outputs under the validated HALL package, initialized firmware schedule, and
OS-derived register groups. They do not establish complete factory-audio
equivalence or resolve the separate 40/41 VST-wrapper issue.

Processing rate and WAV header rate are distinct fields. Factory-reference
renders use the measured DSP clock of 29761.89453125 Hz; the integer WAV header
rate is 29762 Hz. The experimental renders use 48000 Hz for both.

Re-export from the QA worktree (requires the private renders and Codex 2 local
AUDIO LAB checkout):

```sh
cd "$ASR10_QA_WORKTREE"
python3 tools/force_gui_qa/export_hall_audio_lab.py
```

The export manifest is safe to publish; all embedded audio bundles and WAVs
must remain in the private results directory.
