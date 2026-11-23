# ES5510 ROM-01 HALL cold-load evidence

## Result

The redacted [partial manifest](ES5510_FACTORY_COLDLOAD_PARTIAL_V1.json) records a verified OS 3.53 ROM-01 HALL REVERB selection and a post-selection ES5510 snapshot. It is **not** a cold-load image and the standalone adapter replay is blocked. It does not establish factory initialization accuracy.

At the stable `FX=ROM-01 HALL REVERB` display, the native CLI recorded selection time 26.114 s, host frame counter 849885, and OTTO-reported ES5510 rate 29,761.895 Hz. The frame counter is an emulator counter; it is not an audio-file frame index. The public manifest contains event counts and unknowns only. Raw host writes, firmware, EFE bytes, snapshots, and audio remain under the private results directory.

The EFE comparator matched all 89 active HALL instruction commits and all 86 paired GPR initializers to the private ROM-01 EFE source. The remaining three instruction commits are instruction-only records. This confirms program identity and source correlation, not that all GPRs or SPRs were initialized by that load. Through the snapshot marker, the trace contained 4,240 GPR records (including paired commits), 861 instruction records (including paired commits), and no host RAM records. It also contained 38,423 reads / 31,547 writes to the ESP host interface. Host I/O counts include firmware polling and the selector scan, so they are not a per-effect write count.

The phase logger observed 11 HALT pipeline-reset events, 11 DRAM-clear events, and 7 transitions from halted to run before the snapshot. In the adapter source, the HALT host-control operation clears pending ALU/MAC writes, three RAM pipeline slots, and the DOL count; DRAM clear is reported only while halted. The last observed run-start preceded the snapshot. These events span boot and the selector scan; the exact HALL load window is unresolved. No host-side DADR delay-RAM transactions were present in the selected setup logs. DSP-managed delay-RAM writes and its pre-load contents remain unknown.

## Initialization model and unresolved state

The original OS effect loader, including the referenced “Agent 5” loader, was not present in the inspected research branches, source, or documentation. The available native capture reports the active program and runtime state, but does not give an isolated transaction boundary for ROM-01 load. No distinct HALT transition was identified at the stable ROM-01 display. A late snapshot therefore cannot establish cold GPR/SPR values, the complete memory configuration and initialization order, DRAM contents, serial routing at load, DOL state, or in-flight ALU/MAC/RAM state.

The HALL selection and the standalone test harness also do not share a verified first input-frame boundary. Consequently, no deterministic cold-load replay was run, and no HALL-versus-adapter audio difference or first divergent frame can be reported. `factory_manifest.py --require-replay-ready` was exercised against the partial manifest; it deterministically refuses replay with status 2. This gate prevents an incomplete runtime snapshot from being treated as complete state.

## Reproduction

Use private OS 3.53 ROM and disk paths. The repository capture workflow requires the selector sweep to start from a fresh emulator boot; selector raw values depend on the preceding ascending sweep. Output paths below must stay outside the checkout.

```sh
ESP_PIPELOG=1 python3 tools/capture_asr10_rom_effects.py capture-sweep \
  --rom-dir /private/asr10/roms/asr10booth \
  --os-image /private/asr10/floppies/os353.img \
  --output /private/results/es5510-coldload-run \
  --inventory /private/results/asr10-rom50-run/inventory.json \
  --start 16 --raw-first 8 --raw-last 90 --interval 0.15 --tail 2
```

The sweep records the 440 Hz synthetic input and route configured by the existing capture tool. It presses the OS effect-page control, changes one selector value at each interval, and snapshots stable ROM displays without overwriting existing captures. The revised workflow also requests timestamped ESP I/O events; `ESP_PIPELOG=1` enables HALT, DRAM-clear, and run-start diagnostics.

Run the redacting summary tool against the private log. A detailed event ledger contains register addresses and values, so save it only outside Git:

```sh
python3 tools/factory_coldload_trace.py \
  /private/results/es5510-coldload-run/selector-sweep.log \
  --effect-id 1 \
  --private-ledger /private/results/es5510-coldload-run/private-ledger.json \
  --manifest /private/results/es5510-coldload-run/partial-manifest.json
```

Compare the private ROM-01 EFE object, snapshot, and log with `tools/compare_asr10_effect_capture.py ... --snapshot-id 1`. This cuts at the exact `ESP_ROM_STATE` line instead of relying on millisecond timestamps; the selector sweep continues and subsequently writes ROM-02. Expected redacted comparator findings are 89/89 instruction matches and 86/86 paired GPR source matches. `--at-time 26.114` remains available for older traces without a snapshot marker. Validate this committed manifest with:

```sh
python3 tools/audio_validation/factory_manifest.py docs/ES5510_FACTORY_COLDLOAD_PARTIAL_V1.json
python3 tools/audio_validation/factory_manifest.py --require-replay-ready docs/ES5510_FACTORY_COLDLOAD_PARTIAL_V1.json
```

The first command returns valid partial evidence. The second intentionally exits 2 because replay readiness is false.
