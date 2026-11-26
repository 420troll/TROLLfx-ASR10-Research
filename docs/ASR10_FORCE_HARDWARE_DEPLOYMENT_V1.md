# TROLLfx ASR-10 FX Collection V1 — Force Deployment Report

Date: 2026-11-26
Deployment branch: `deploy/asr10-force-fx-collection-v1`
Candidate source: `f58f21fc052ce143d9ec31b2b70d7e6b6cb4b40a`
Candidate package: `TROLLfx - VST - ASR10 FX Collection`
Release classification: experimental controlled hardware smoke; independent T2 acceptance remains incomplete.

## Result

The candidate was installed on the original Akai Force and the supported MPC host service was restarted. The Force returned online, the candidate remains installed with the expected hash, and the host service is active. The user then confirmed that the plugin appears on the Force and HALL audio works.

The user confirmed physical plugin discovery, HALL audio, and bypass. The touchscreen/editor was also evaluated and **failed usability acceptance**: expected effect-editing controls were missing or inaccessible, and the screen was cluttered. Individual Q-Link knob behavior remains **not tested**. The candidate is not accepted as a release: the editor usability failure is a blocker, and the updated test policy also requires full ABI and non-finite-input checks bound to the exact binary. Desktop checks against an equivalent rebuild passed, but the matching native build artifact was not retained; an ARM test harness attempt crashed before completing its assertions.

## Candidate and build identity

| Item | Value |
|---|---|
| Source commit | `f58f21fc052ce143d9ec31b2b70d7e6b6cb4b40a` |
| Source inputs SHA-256 | `d8087eddf9f507249cf8a025e75c086c5d6439294164de1dd9d97cf38255e7d1` |
| Akai Force SDK commit | `4521c247a2deae30efb9e93d53fc8f9390c51e81` |
| Toolchain | Zig Python package 0.17.1 |
| Build command | `force_plugin/tools/build_candidate.sh --toolchain auto --no-zip` |
| ARMv7 hard-float VST2 SHA-256 | `4af2be5d75515c89e83be798e2133cd60bc9640a5dcd26b48c5d2ef1d027868f` |
| AArch64 VST2 SHA-256 | `2b99e3f7d9dd21d23adc3331231ddf407981b61f231b267422e0ca897a6ef105` |
| Candidate native x86-64 VST2 SHA-256 | `adce9bf02bced4ed2b7c611d7a2c3a479bc256df5b4fe8d985a42e4a06a8b2f6` |
| VST parameter layout | 64 entries; SHA-256 `0ee1bf05ea85f1a848ca5854cb743eb4f7b8359e2bb0e552a2fe5d7faef02ddf` |
| ARM ABI | ELF32 ARMv7-A, hard-float/VFP; GLIBC requirement at most 2.27 |
| QEMU | `NOT_RUN`; `qemu-arm` is unavailable. The historical QEMU hash was stale and was not reused. |

The packaged candidate manifest says the exact ARM binary is playable and records its checksum. That marker reflects audio/package validation; it does not override the later physical editor usability failure recorded here.

## Asset path and package validation

The plugin reads the authorized local package collection at:

`/media/SSD250g/TROLLfx/ASR10/factory-effects`

The device `provider-index.tsv` SHA-256 is `8bbb71d362529d39f94305ec5c927cb7c93477eb6cdcf627afaf90de464b8267`.

All 50 local package entries were validated by the packaged VST test. The factory payloads remain external and were not copied into the repository or release archive. The packaged `factory-assets-path.txt` contains only the device path.

## Installation and rollback

The Force was observed as ARMv7 Linux (`armv7l`), kernel `6.18.44-az01-2026-08-10-rt6`, with the SSD mounted at `/media/SSD250g`. At preflight the SSD had about 175.6 GB free. The current host service is `acvs.service` and the MPC process remained alive after restart.

Installed plugin directory:

`/media/SSD250g/VST2 Plugins/TROLLfx - VST - ASR10 FX Collection`

External rollback copy:

`/media/SSD250g/TROLLfx/ASR10/rollback-v1-20261126/TROLLfx - VST - ASR10 FX Collection`

The old installed ARM binary hash was `badefa8fa322b812adbf82166d9782e17d770d4453cb06f428b2f9ed98a3cab4`. Candidate and rollback directory checksum manifests were checked after installation: 34 candidate files and 30 backup files passed. Only one `TfxF` plugin directory is in the scan directory.

The restart used the supported service manager command:

```sh
ssh akai-force 'systemctl restart acvs.service'
```

The service returned active and the device reconnected. Post-restart SHA-256 of the installed ARM binary still matches the candidate. A tested package rollback script is available at `tools/force_hardware/rollback_package_device.sh`; it keeps the failed candidate outside the scan directory and restores the prior directory from the external backup.

## Test records and status

Results are recorded separately by evidence scope. No result is promoted across different binary or asset-index hashes.

| Test | Tier | Status | Identity / result |
|---|---|---|---|
| SDK compile and validation | T2 | PASS | Candidate source above; SDK validator reported 0 errors and 0 warnings; ARMv7 and ARM64 artifacts produced. |
| Candidate package/hash/playable-marker validation | T2 | PASS | Packaged directory checksum validation passed; `INTEGRATION_STATUS` binds the exact ARMv7 hash above. |
| Packaged native VST2 50-slot smoke | T2 | PASS | Exact packaged native hash `adce9bf0…a8b2f6`, ARM hash `4af2be5d…d027868f`, asset index hash above; 50/50 slots, 409,600 DSP frames, finite stereo output, 0 callback allocations, missing-package fail-closed, switching and state round-trip. Report SHA-256 `289e1cc40714ab9f42ed01f29855a560707fb4be12b36d86c544070f3ec65aa4`. |
| Updated 64-parameter ABI and chunk assertions | T2 | PASS, source-matched rebuild only | Codex 3 worktree harness had uncommitted changes at test-source SHA `6f92b034da5c661a20631d77a27c54a4fef60162550aa6bc21682c3ca18b273f`. It passed all 64 names, stable IDs, and chunk version 2 on a rebuild of the same source/SDK. That rebuilt native binary was SHA `883e825d71feff17376cbe303c46618b641e59144a28a5b2bc2de337279facab`, not the packaged candidate native hash; therefore this is not candidate-binary acceptance. |
| Updated non-finite parameter and audio probes | T2 | PASS, source-matched rebuild only | `NAN_PARAMETER_PASS` and `NAN_AUDIO_PASS frames=256` on rebuilt native hash `883e825d…279facab`; same harness-source identity as above. Not reused for the installed ARM binary. |
| Source-matched native VST 50-slot callback run | T2 | PASS, source-matched rebuild only | 50 slots ready; finite stereo; wet/dry, gain, bypass and state round-trip passed; 0 callback allocations. Same rebuilt native hash and asset index SHA above. |
| Auxiliary empty-package branch in updated QA harness | T1 | FAIL (harness expectation mismatch; product result inconclusive) | It expected a particular `UNAVAILABLE` status and stopped with `empty local collection was not reported unavailable`. The candidate package test separately passed its own missing-package fail-closed check. No test was weakened. |
| Exact ARM candidate under temporary Zig-built QA harness | T2 | FAIL (harness/tool ABI; product result inconclusive) | The temporary ARM harness had ELF32/ARMv7/hard-float flags but lacked the candidate library's `Tag_ABI_VFP_args: VFP registers` attribute. It segfaulted after loading the package index, before emitting ABI or DSP assertions. The MPC service remained active; installed candidate hash remained unchanged. Temporary files were removed. No 50-slot loop was run on the device. |
| Physical Force plugin discovery | T3 | PASS (user observed) | User confirmed the plugin appears in the Force plugin list. |
| Physical Force HALL audio | T3 | PASS (user observed) | User confirmed HALL audio works. This is not an audio capture or a measured reference comparison. |
| Physical bypass | T3 | PASS (user observed) | User confirmed bypass works on the Force. |
| Physical touchscreen/editor usability | T3 | FAIL | User observed expected effect-editing controls missing or inaccessible and a cluttered screen. |
| Individual physical Q-Link knobs | T3 | NOT_TESTED | No individual knob behavior was tested. |
| Physical save/recall, other effects, CPU/xruns | T3 | NOT_TESTED | These interactions were not observed or measured. |
| Original-OS or DSP research | T3 | NOT_APPLICABLE | No DSP arithmetic, factory package, or OS mapping was changed in this deployment. |
| Full repository suite | T0/T1 | PASS, historical run | `python3 -m unittest discover -s tests -v`: 80 tests passed in 65.853 s before the deployment-only package scripts were added. Relevant packaging and rollback tests were then run separately. No full suite was repeated after the policy update. |
| Release infrastructure tests | T0/T1 | PASS | `AKAI_FORCE_SDK=... PYTHONPATH=... python3 -m unittest discover -s force_plugin/tests -p test_release_infrastructure.py -v`: 9 passed. |
| Device rollback tests | T1 | PASS | `python3 -m unittest discover -s tests/force_hardware -v`: 2 passed; a disposable local install/rollback simulation also passed. |
| QEMU execution | T2 | NOT_RUN | `qemu-arm` unavailable. No older QEMU pass was reused because it referred to another ARM binary. |

The exact-source QA harness was built and run from the separate Codex 3 worktree without modifying it. Because the updated test source was dirty and the rebuilt native plugin hash differed from the candidate native hash, the 64-layout and NaN results above are explicitly not treated as candidate-bound PASS evidence. The ARM harness crash is likewise not attributed to the candidate VST; the physical HALL check is the direct evidence that the installed plugin processes audio on the Force.

## Reproduction commands

Build the package with the same local SDK and authorized private collection:

```sh
PYTHONPATH=/tmp/trollfx-force-zig \
AKAI_FORCE_SDK=/mnt/c/Users/Gamer/research/AkaiForceSDK \
TROLLFX_FACTORY_PACKAGE_COLLECTION=/home/gamer/research/private-results/asr10-all-50-effects/validated-packages \
TROLLFX_FORCE_ASSET_ROOT=/media/SSD250g/TROLLfx/ASR10/factory-effects \
sh force_plugin/tools/build_candidate.sh --toolchain auto --no-zip
```

The supported host restart is `systemctl restart acvs.service`. Use the deployment scripts with an external, verified backup before replacing an installed package. No Force firmware, MockbaMod files, unrelated plugins, or user projects were changed.

## Remaining release gates

- Obtain candidate-binary-bound ABI/chunk and NaN/Inf test results. Use a correctly ABI-tagged ARM test harness or retain the exact native candidate artifact during packaging and rerun the independent harness against that hash.
- Resolve the touchscreen/editor usability failure in the next editor candidate, then verify physical Q-Link routing, project state recall, effect switching, and at least one additional effect on the Force.
- Measure CPU load, memory, xruns, and longer-run stability on device.
- Keep the release labeled experimental until these gates are closed and independent T2 acceptance is recorded.
