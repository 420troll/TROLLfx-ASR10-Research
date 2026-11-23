# ROM-01 HALL standalone replay

`tools/audio_validation/replay_hall.py` is an offline event-stream replay harness for externally held ROM-01 HALL state and serial evidence. It requires a complete `trollfx-es5510-factory-init-v1` manifest accepted by the existing `--require-replay-ready` gate, checks payload and stream hashes, confines manifest references to the private manifest directory, checks contiguous absolute ESP frames, and keeps compiled output, frame comparisons, and reports outside this checkout.

The runner applies the 89 six-byte instruction words, 192 GPR values, 22 special-register values, 0x48 serial configuration, zeroed one-megaword DRAM, and 213 ordered post-RUN register updates to the native and standalone MAME-derived engines. It replays the 90,000-frame serial stream at the recorded 29,761.895 Hz ESP frame clock (the host renderer is 44,100 Hz), preserving the absolute frame numbers and comparing each engine's four serial ports to the recorded OS boundary. It emits no sample values. Run it with private inputs and output, for example:

```sh
python3 tools/audio_validation/replay_hall.py \
  /private/asr10/hall/state/factory-state.json \
  --load-events /private/asr10/hall/events.csv \
  --out /private/asr10/hall/replay-output
```

## Current evidence

The replay extracts the exact ordered 89 instruction and 342 GPR/SPR commits from the private event log. It also retains GPR values established by prior halted firmware transactions, because HALT and pipeline reset do not clear the GPR file. With the full recorded host-write history, the GPR state matches the manifest. The remaining state gate reports six SPR mismatches and stops before audio comparison; native-versus-MAME and OS-reference comparisons have not been made from this event transaction.

The event log also provides the subsequent 213 ordered firmware register updates and a continuous 90,000-frame serial stream beginning at ESP frame 855,973. The evidence identifies a 29,761.895 Hz ESP frame clock and separate 44,100 Hz host output rate. The runner checks frame continuity and only proceeds to comparison after the initial transaction passes state equality. The existing strict manifest gate remains unchanged; its valid full-state intake alone does not certify that a separately supplied ordered event trace corresponds to that state.

Proprietary program/register payloads, captures, serial samples, rendered audio, and engine CSVs remain external. Public output is limited to hashes, counts, frame/lane of first divergence, clock/routing metadata, and match status.
