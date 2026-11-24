# ASR-10 Factory Checkpoint Repair — RUN Boundary V1

## Result

The collection was recaptured at each effect’s observed first-instruction RUN boundary. All 50 packages pass the strict private importer, `EffectRegistry::register_validated()`, native runtime checkpoint load, and a 4,096-frame stereo finite-output smoke render. Their 32,768-frame firmware schedules contain 8,029 GPR writes; the largest schedule is 583 writes (slot 09). The runtime’s fixed schedule capacity was raised from 256 to 1,024 based on this measured set. The bound remains fixed and inputs above it are rejected.

All capture payloads, transaction logs, schedule CSVs, checkpoints, and generated audio remain under `/home/gamer/research/private-results/`. No private payload was added to Git.

## Capture and validation method

`capture_factory_run_boundaries.py` observes a stable OS `FX=ROM-NN` display and arms a capture for the next HALT-to-RUN transition. The ES5510 snapshot is written at `run_start`, before the instruction loop executes; the logger then records the first instruction. The repair tool requires the ordered HALT, pipeline-reset, DRAM-clear, upload, RUN, snapshot, and PC-0 first-instruction evidence. It compares every active instruction word against ordered host upload commits and correlates that upload with the preceding selected OS slot.

Each checkpoint carries the full program store, all 192 GPRs and 22 SPRs, the complete 1,048,576-word DRAM image, memory and delay configuration, serial state, and pipeline-reset evidence. Its schedule is derived from observed post-RUN GPR writes over the following 32,768 DSP frames. Writes retain observed order and are not truncated.

## Slot 01–03 identity resolution

The earlier collection associated a stable-display snapshot with the visible slot, but that snapshot preceded the next effect load. The new capture associates the selected display with the following loader RUN and verifies the uploaded instructions against the RUN checkpoint:

| Slot | OS display | RUN frame | Captured image | Evidence |
|---:|---|---:|---|---|
| 01 | HALL REVERB | 855973 | 89 words | Matches independently verified HALL image |
| 02 | 44KHZ REVERB | 905028 | 60 words | Exact active program digest matches independent ROM-02 replay |
| 03 | ROOM REVERB | 978327 | 89 words | Uploaded image matches checkpoint; selector-to-RUN chronology supports slot 03 |

This establishes the one-transition capture skew: old slot 02 had HALL’s image, and old slot 03 had ROM-02’s image. Packages retain the original slot numbers and displayed names. Slot 03 has direct emulator selector/upload correlation, but not a separate factory EFE payload correlation.

## Per-slot status

All rows passed package validation, registry registration, DSP loading, and the stereo runtime smoke. RMS and peak identify quiet outputs; low output in this short window is not treated as a load failure. For slots 01–49, the rate is measured at the next stable OS display after this slot’s RUN, which observes the clock after the selected program loads. Slot 50 has no following selector transition in this capture and retains the pre-RUN observed rate, marked `*`; its post-RUN clock remains unresolved. No rate is evidence that a program intrinsically requires it.

| Slot | Factory name | Words | Observed Hz* | RUN frame | GPR events | Output RMS | Peak |
|---:|---|---:|---:|---:|---:|---:|---:|
| 01 | HALL REVERB | 89 | 29761.895 | 855973 | 213 | 0.10764 | 0.172119 |
| 02 | 44KHZ REVERB | 60 | 44100.000 | 905028 | 202 | 0.101963 | 0.5 |
| 03 | ROOM REVERB | 89 | 29761.895 | 978327 | 236 | 0.11432 | 0.5 |
| 04 | DUAL DELAYS | 89 | 29761.895 | 1027461 | 121 | 0.101062 | 0.149994 |
| 05 | 44KHZ DELAYS | 60 | 44100.000 | 1076744 | 121 | 0.0989632 | 0.149994 |
| 06 | CHORUS+REVRB | 89 | 29761.895 | 1150187 | 325 | 0.101288 | 0.150024 |
| 07 | PHASER+REVRB | 89 | 29761.895 | 1199083 | 205 | 0.101239 | 0.149994 |
| 08 | FLANGER+REV | 89 | 29761.895 | 1248379 | 223 | 0.101245 | 0.150024 |
| 09 | ROT.SPKR+REV | 89 | 29761.895 | 1297813 | 583 | 0.10129 | 0.150116 |
| 10 | CHOR+REV+DDL | 89 | 29761.895 | 1347083 | 231 | 0.101266 | 0.149994 |
| 11 | CMP+DIST+REV | 89 | 29761.895 | 1396259 | 130 | 0.10125 | 0.150513 |
| 12 | DIST+CHO+REV | 89 | 29761.895 | 1445607 | 236 | 2.77509e-05 | 6.10352e-05 |
| 13 | WAH+DIST+REV | 89 | 29761.895 | 1494813 | 218 | 0.101248 | 0.150452 |
| 14 | SMALL ROOM | 89 | 29761.895 | 1544135 | 148 | 0.0741782 | 0.184143 |
| 15 | LARGE ROOM | 89 | 29761.895 | 1593273 | 148 | 0.14972 | 0.265472 |
| 16 | HALL REVERB2 | 89 | 29761.895 | 1642389 | 148 | 0.0894787 | 0.179138 |
| 17 | SMALL PLATE | 89 | 29761.895 | 1691697 | 134 | 0.103211 | 0.227692 |
| 18 | LARGE PLATE | 89 | 29761.895 | 1740979 | 134 | 0.093703 | 0.168182 |
| 19 | REVRSE REVRB | 89 | 29761.895 | 1790293 | 129 | 0.10126 | 0.149994 |
| 20 | REVRSE REVB2 | 89 | 29761.895 | 1839563 | 128 | 0.101237 | 0.150177 |
| 21 | GATED REVERB | 89 | 29761.895 | 1888857 | 136 | 0.0989177 | 0.146484 |
| 22 | NLIN REVRB 1 | 89 | 29761.895 | 1938361 | 145 | 0.0936414 | 0.199585 |
| 23 | NLIN REVRB 2 | 89 | 29761.895 | 1987341 | 145 | 0.0914307 | 0.22699 |
| 24 | NLIN REVRB 3 | 89 | 29761.895 | 2036569 | 145 | 0.104103 | 0.305206 |
| 25 | MULTITAP DDL | 89 | 29761.895 | 2085487 | 139 | 0.101282 | 0.149994 |
| 26 | EQ+DELAY LFO | 89 | 29761.895 | 2135095 | 135 | 0.156334 | 0.292084 |
| 27 | VCF+DISTORT | 89 | 29761.895 | 2184073 | 129 | 0.0407539 | 0.0604248 |
| 28 | GUITAR AMP1 | 89 | 29761.895 | 2233591 | 150 | 0.049834 | 0.0738525 |
| 29 | GUITAR AMP2 | 89 | 29761.895 | 2282899 | 150 | 0.0308498 | 0.0457153 |
| 30 | GUITAR AMP3 | 89 | 29761.895 | 2332327 | 150 | 0.0838826 | 0.124237 |
| 31 | SPKR CABINET | 89 | 29761.895 | 2381119 | 116 | 0.00102013 | 0.00216675 |
| 32 | TUNABLE SPKR | 89 | 29761.895 | 2430703 | 135 | 0.0407539 | 0.0603638 |
| 33 | EQ+CHOR+DDL | 89 | 29761.895 | 2479687 | 137 | 0.127856 | 0.287567 |
| 34 | EQ+VIBR+DDL | 89 | 29761.895 | 2529031 | 133 | 0.0958436 | 0.146576 |
| 35 | EQ+FLNGR+DDL | 89 | 29761.895 | 2578411 | 140 | 0.0844096 | 0.195892 |
| 36 | EQ+TREM+DDL | 89 | 29761.895 | 2627481 | 133 | 0.196254 | 0.296478 |
| 37 | PHASER+DDL | 89 | 29761.895 | 2676733 | 125 | 0.118414 | 0.26416 |
| 38 | 8-VOICE CHOR | 89 | 29761.895 | 2726209 | 130 | 0.0482877 | 0.137451 |
| 39 | PITCH SHIFT | 89 | 29761.895 | 2775183 | 135 | 0.0800689 | 0.149994 |
| 40 | PITCH+DDL | 89 | 29761.895 | 2824605 | 133 | 0.0675603 | 0.203674 |
| 41 | FAST PITCHSH | 89 | 29761.895 | 2873601 | 127 | 0.104272 | 0.201904 |
| 42 | EQ+CMPRESSOR | 89 | 29761.895 | 2923199 | 127 | 5.10238e-06 | 0.000274658 |
| 43 | EXPANDER | 89 | 29761.895 | 2972485 | 124 | 0.10113 | 0.151703 |
| 44 | KEYED EXPNDR | 89 | 29761.895 | 3071005 | 126 | 0.00830232 | 0.102448 |
| 45 | INVRS EXPNDR | 89 | 29761.895 | 3120311 | 124 | 4.42201e-06 | 0.000274658 |
| 46 | DE-ESSER | 89 | 29761.895 | 3218933 | 139 | 1.24298e-05 | 0.000762939 |
| 47 | DUCKER | 89 | 29761.895 | 3317495 | 141 | 0.0719907 | 0.107086 |
| 48 | RUMBLE FILTR | 89 | 29761.895 | 3415613 | 120 | 0.028245 | 0.139496 |
| 49 | PARAM EQ | 89 | 29761.895 | 3514077 | 131 | 0.0683761 | 0.15213 |
| 50 | VAN DER POL | 89 | 29761.895* | 3612657 | 116 | 0.10308 | 0.149994 |

Machine-readable non-payload status: [`ASR10_FACTORY_RUN_BOUNDARY_STATUS.json`](ASR10_FACTORY_RUN_BOUNDARY_STATUS.json).

## Reproduction commands

```bash
cd /home/gamer/worktrees/asr10-factory-package-loader
sh tools/build_research_cli.sh
python3 tools/audio_validation/capture_factory_run_boundaries.py \
  --cli build/research-cli/asr10-cli \
  --roms /home/gamer/OpenASR-run/roms/asr10booth \
  --disk /home/gamer/OpenASR-run/floppies/os353.img \
  --out /home/gamer/research/private-results/asr10-factory-run-boundary-repair/all-50 \
  --ids "$(seq -s, 1 50)" --raw-last 1023
python3 tools/audio_validation/repair_factory_collection_boundaries.py \
  --collection /home/gamer/research/private-results/asr10-all-50-effects/validated-packages \
  --capture-report /home/gamer/research/private-results/asr10-factory-run-boundary-repair/all-50/capture-report.json
python3 tools/audio_validation/import_factory_effect_collection.py \
  /home/gamer/research/private-results/asr10-all-50-effects/validated-packages \
  --output /home/gamer/research/private-results/asr10-factory-run-boundary-repair/import-audit-all.json
python3 tools/audio_validation/smoke_imported_factory_packages.py \
  --audit /home/gamer/research/private-results/asr10-factory-run-boundary-repair/import-audit-all.json \
  --output /tmp/asr10-registry-smoke-all
```

The importer emits registry descriptors only after manifest/file digests, full checkpoint state, source/upload correlation, phase order, routing, schedule order, and bounded-capacity checks succeed. The smoke runner consumes accepted descriptors and registers each with `EffectRegistry::register_validated()` before `FactoryRuntime::loadEffect()`.

## Tests and limits

The smoke signal is one stereo impulse followed by an anti-phase 330 Hz sine. Every sample was finite for all slots; several effects are unusually quiet in this short window. This establishes loading and execution, not perceptual correctness or long-tail quality. The work does not establish physical-hardware or Force behavior. Factory parameter controls were not changed or revalidated. Native DSP arithmetic and delay-RAM addressing were not modified.
