# ASR-10 Factory Parameter Recovery V3

## Result

V3 preserves the 16 verified controls from V2 and adds three controls with repeated reversible register mappings: 44KHZ DELAYS BS1 TIME L, FLANGER+REV FLANGE RATE, and PITCH SHIFT QUALITY. The machine-readable metadata is in [ASR10_FACTORY_PARAMETER_RECOVERY_V03.json](ASR10_FACTORY_PARAMETER_RECOVERY_V03.json); it lists only observed points and does not interpolate undocumented values.

Three additional display ranges were scanned to their live OS endpoints and restored exactly. Those range findings do not establish register curves across the ranges.

At the user's direction, V3 follow-up on slot 2 is deferred pending identity confirmation. It is excluded from new V3 mappings and counts. V2 materials remain unchanged.

## New mappings

| Slot / factory name | LCD control | Verified points | Ordered GPR write group | Native audio result |
|---|---|---|---|---|
| 5 — 44KHZ DELAYS | BS1 TIME L | 350 → 351 | GPR 0x0B: 0x3C2900 → 0x3C5500 | Finite output; no sample difference in this render |
| 8 — FLANGER+REV | FLANGE RATE | 20 → 21 | GPR 0x84 and 0x85: 0x0003D7 → 0x00049C | Finite output; no sample difference in this render |
| 39 — PITCH SHIFT | QUALITY | LONG/SMOOTHER → SHORT/COARSER | GPRs 0x04, 0x07, 0x0A, 0x61, 0x64, 0xA0; see JSON | Finite output; difference RMS 0.0982591, peak difference 0.201721 |

Every mapping was observed in two forward/reverse trials, with the LCD returning to its starting value. Slot 8 GPR 0x86 varied between repeats and was excluded as modulation/background activity; only the stable 0x84/0x85 pair is included. The native renders used 32,768 warmup frames followed by 8,192 comparison frames at the experimental 48 kHz rate. A zero difference means only that the selected stimulus and window did not demonstrate an output change; it does not invalidate the LCD or register evidence.

## Live range scans

The display-driven scanner captured full 22-character LCD values, waited for stable transitions, stopped at a no-change boundary, traversed back across the origin, and restored the exact starting LCD value.

| Slot | Control | Baseline | Live minimum–maximum | Restored |
|---|---|---:|---:|---|
| 1 — HALL REVERB | DECAY TIME | 40 | 0–99 | Yes |
| 3 — ROOM REVERB | DIFFUSION | 50 | 0–99 | Yes |
| 3 — ROOM REVERB | HI FREQ DAMPING | 9 | 0–99 | Yes |

The range scanner now identifies each step by scan segment and direction. This fixes the previous trace-label defect where downward step completion markers could be numbered zero and prevents confusing the maximum-to-origin traverse with the minimum-range scan. Boundary attempts intentionally have a begin marker without a done marker because the LCD does not change at the endpoint.

## Evidence levels and remaining gaps

- **Register verified:** 19 controls total when the 16 V2 controls and the 3 V3 controls are counted together. V3 adds six display points across three controls.
- **Audio verified:** V3 measured a clear change for PITCH SHIFT QUALITY. BS1 TIME L and FLANGE RATE produced finite, bit-identical comparison windows with the chosen sustained stereo stimulus. Their audible behavior remains unverified by this signal/window.
- **Ranges verified:** Three newly reported full live ranges above. The listed points remain the only runtime-supported values for these controls.
- **Unresolved:** Complete ranges and curves for the 19 controls, multi-register behaviors for other families, and native audio response where the chosen stimulus showed no difference. Reverbs beyond the already verified V2 controls, chorus, phaser, pitch parameters other than QUALITY, dynamics, and EQ still need additional probes.
- **Slot 2:** No slot 2 V3 mapping or range claim is promoted. Further work is deferred pending the user's identity concern. Do not treat the private slot 2 trial artifacts as a new approved control descriptor.

## Reproduction

Build the panel probe CLI:

```sh
bash tools/build_research_cli.sh
```

Example full range scan for ROOM DIFFUSION (requires authorized local OS/ROMs and private inventory):

```sh
python3 tools/parameter_controls/run_display_driven_probe.py \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --inventory /home/gamer/research/private-results/asr10-all-50-effects/inventory.json \
  --slot 3 --candidate 'DIFFUSION' --mode range --seconds 55 \
  --output /home/gamer/research/private-results/asr10-parameter-discovery-v3
```

Example reversible point probe for FLANGE RATE:

```sh
python3 tools/parameter_controls/run_display_driven_probe.py \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --inventory /home/gamer/research/private-results/asr10-all-50-effects/inventory.json \
  --slot 8 --candidate 'FLANGE RATE' --mode point --seconds 55 \
  --output /home/gamer/research/private-results/asr10-parameter-discovery-v3
```

Run native audio comparisons for all new V3 point pairs (the runner checks each package checkpoint and firmware schedule against the authorized private audit before loading):

```sh
python3 tools/parameter_controls/run_v03_native_audio_validation.py \
  --audit /home/gamer/research/private-results/asr10-all-50-effects/production-provider-audit.json \
  --output /home/gamer/research/private-results/asr10-parameter-discovery-v3/native-audio-final \
  --binary /tmp/es5510-parameter-audio-v3-final
```

Private logs, WAVs, checkpoints, ROMs, and OS images remain outside Git. The V3 runtime descriptors expose only the six new observed points, and the Force plugin/install tree was not modified.
