# ROM-02 existing reference and replay: independent audit

## Audit outcome

The named private result directories contain the existing ROM-02 reference
captures, replay-ready manifest, native/MAME serial outputs, firmware-event
schedule, and a second capture-script check. I audited these files in place;
the OS captures and standalone replay were not regenerated. The audit tool is
[`audit_rom02_private_results.py`](../tools/audio_validation/audit_rom02_private_results.py).

The two `rom02-replay-v1-reference` sessions both start at emulator frame 1,
have separate logs and RUN snapshot files, and contain the complete
HALT/reset/clear/load/RUN sequence. The capture script starts `boot-a` and
`boot-b` through separate CLI subprocess calls. The second
`rom02-replay-v1-capture-script-check` pair independently repeats the same
32,768-frame input/output, checkpoint, and WAV bytes. The additional
`rom02-loader-analysis-20261124` pair shows ROM-02 selection and matching
program digests in both boot captures. This supports two fresh OS-process
captures, though no per-process ID receipt was preserved.

## Independently checked reference evidence

The two main reference logs pass the checked-in ROM-02 boundary parser, and
the manifest passes `factory_manifest.py --require-replay-ready`.

| Evidence | Audit result |
|---|---|
| Factory effect | ROM-02 `44KHZ REVERB`; also observed in a separate selector sweep |
| Active program | 60 words, END at word 59; SHA-256 prefix `12119e86d4d2` |
| EFE/source correlation | Both loader-analysis captures report 60 instruction matches, 58 paired GPR matches, and the same active-program digest; raw EFE source object is absent from the named directories |
| RUN checkpoint | Frame 905028, PC 0; RUN precedes snapshot, snapshot precedes first instruction |
| Initial state | Snapshots byte-identical; full 1,048,576-word DRAM clear verified; reset counters are ALU 0, MAC 0, three RAM slots cleared, DOL 0 |
| Clock | DSP 44,100 Hz; host output 44,100 Hz, measured separately |
| Serial routing | Input SER2 L/R (lanes 4/5); effect output SER1 L/R (lanes 2/3); route `-1,-1,1,-1` |
| Firmware events | Startup/load histories match between boots; 202 post-RUN GPR updates match the replay schedule |
| Frame alignment | Both streams are compared at identical absolute frame indices beginning at 905028; no shift or resampling |
| Host output | WAV and source-position map match between OS runs; every mapped PCM value is checked against the WAV |

Exact private-file hashes and sample payloads remain outside Git. The audit
JSON in the private results directory contains redacted hash prefixes and
aggregate counts only.

## Existing standalone output audit

I compared the existing `32768/engine-output.csv` directly against the parsed
OS output frames and the existing `serial-input.csv` against both OS input
traces. All eight serial input lanes and their absolute frame numbers match.
The firmware-event CSV matches the 202 recorded OS updates, including event
order and frame boundary. For the native engine, all eight output lanes match
the OS trace at fixed indices for the 256-, 4,096-, and 32,768-frame windows:
zero differences at all three windows.

The primary replay binary is present, but its recorded hash does not match a
fresh build from this branch. The second capture-script-check binary does
match a fresh build of the checked-in runner sources byte for byte, and its
engine-output CSV is byte-identical to the primary replay output. This gives a
reproducible source path for the candidate results, while leaving the original
binary's build identity unknown.

The complete comparison gate is **not eligible**. The reference session logs
do not record the OS emulator CLI executable hash/build ID, OS ROM hashes, or
OS disk-image hash. Those artifacts are absent from the named directories, so
the authentic reference executable and firmware inputs cannot be tied to the
logs by content hash. The audit therefore records the observed native exact
sample result but does not promote it to a fully provenance-gated accuracy
claim. Per the gate rule, this report does not publish a MAME first-divergence
frame while reference executable provenance is incomplete.

The snapshot format also omits complete in-flight pipeline internals. The
HALT reset acknowledgement does record empty ALU/MAC/RAM/DOL counters before
RUN, which supports the chosen checkpoint boundary, but the snapshot is not a
complete pipeline save state. Firmware writes are scheduled between adjacent
serial frames; their exact sub-frame execution instant is not recorded. There
is no standalone DAC/host-WAV candidate, so comparison in the host PCM domain
remains open. The ROM-02 EFE source file is missing, preventing a fresh
source-to-program comparison from the original bytes.

## Reproduce the redacted audit

Build the standalone comparator once from this worktree, then run the audit.
The audit returns status 2 when provenance prevents full gate eligibility; it
still writes its redacted report outside the checkout.

```sh
c++ -std=c++17 -O2 -Isrc -Ithird_party/trollfx_mame_es5510 \
  src/es5510.cpp third_party/trollfx_mame_es5510/mame_es5510_standalone.cpp \
  tools/audio_validation/factory_boundary_replay.cpp \
  -o /tmp/rom02-audit-factory-boundary-replay

python3 tools/audio_validation/audit_rom02_private_results.py \
  --reference-root /home/gamer/research/private-results/rom02-replay-v1-reference \
  --replay-root /home/gamer/research/private-results/rom02-replay-v1-replay \
  --manifest /home/gamer/research/private-results/rom02-replay-v1-reference/replay-manifest/factory-state.json \
  --corroboration-root /home/gamer/research/private-results/rom02-replay-v1-capture-script-check \
  --loader-evidence-root /mnt/c/Users/Gamer/research/private-results/rom02-loader-analysis-20261124 \
  --selector-sweep-root /home/gamer/research/private-results/rom02-replay-v1-capture-1 \
  --reproducible-replay-binary /tmp/rom02-audit-factory-boundary-replay \
  --output /home/gamer/research/private-results/rom02-independent-audit.json
```

No private firmware, ROM, EFE, capture, microprogram, state payload, or audio is
committed.
