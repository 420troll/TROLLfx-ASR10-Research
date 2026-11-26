# Agent 1 — Akai Force deployment, rollback and device evidence

**State at transition: HOLD / IDLE.** Read [coordinator](00_COORDINATOR.md), original [hardware deployment report](https://github.com/420troll/TROLLfx-ASR10-Research/blob/deploy/asr10-force-fx-collection-v1/docs/ASR10_FORCE_HARDWARE_DEPLOYMENT_V1.md), [test policy](../TROLLFX_ASR10_TEST_POLICY_V1.md). Do not modify the live Force while Agent 2 builds or Agent 3 audits.

## Known installed baseline (2026-11-26)

- Branch: `deploy/asr10-force-fx-collection-v1`; user reported latest commit `1da5dd9`; source commit `f58f21fc052ce143d9ec31b2b70d7e6b6cb4b40a`.
- Installed ARMv7 hard-float VST2 SHA-256 `4af2be5d75515c89e83be798e2133cd60bc9640a5dcd26b48c5d2ef1d027868f`; native packaged candidate SHA-256 `adce9bf02bced4ed2b7c611d7a2c3a479bc256df5b4fe8d985a42e4a06a8b2f6`.
- 64-parameter layout SHA-256 `0ee1bf05ea85f1a848ca5854cb743eb4f7b8359e2bb0e552a2fe5d7faef02ddf`.
- Source inputs digest `d8087eddf9f507249cf8a025e75c086c5d6439294164de1dd9d97cf38255e7d1`; SDK commit `4521c247a2deae30efb9e93d53fc8f9390c51e81`.
- Factory private index SHA-256 `8bbb71d362529d39f94305ec5c927cb7c93477eb6cdcf627afaf90de464b8267`.
- Plugin path: `/media/SSD250g/VST2 Plugins/TROLLfx - VST - ASR10 FX Collection`; private assets: `/media/SSD250g/TROLLfx/ASR10/factory-effects`; external verified rollback: `/media/SSD250g/TROLLfx/ASR10/rollback-v1-20261126/TROLLfx - VST - ASR10 FX Collection`.
- Service `acvs.service`; device `armv7l`, kernel `6.18.44-az01-2026-08-10-rt6`. Previously supported restart command `ssh akai-force 'systemctl restart acvs.service'` **only if reauthorized and not during a performance**. Device rollout script `tools/force_hardware/rollback_package_device.sh` has disposable simulation tests but must be inspected before each live operation.
- Existing candidate and backup passed folder checksum manifests (34 and 30 files respectively); plugin scan directory had one `TfxF` plugin.

## User observations / correct evidence labels

PASS: plugin discovery, HALL audio, touchscreen bypass. PROVISIONAL touchscreen gain/volume response. FAIL touchscreen usability, missing/inaccessible edit controls, high-frequency damping audible response. INCONCLUSIVE delay-time adjustment (too narrow). 40/41 decay limited by old prototype. Physical **individual Q-Link knob response NOT VERIFIED**. Project recall, other effects, performance/CPU/xruns NOT TESTED. Never erase these distinctions or claim all hardware Q-Links were untested when touch UI was evaluated.

The packaged 50-slot desktop VST2 audio test passes. New 64-param/chunk and NaN tests passed against a *different* native rebuild hash, not exact package. ARM temporary QA harness crashed before its own assertions with suspected ABI tagging mismatch, not during normal MPC use; no QEMU for that exact candidate. Clearly distinguish tool crash from plugin crash.

## Before next installation (wait for approval)

1. Receive Agent 2 immutable release candidate: commit, ARM and native SHA-256, exact manifest and `SHA256SUMS`, 64-index identity report, generated UI `TUI.json` + `Q-Links.json`, private asset-index digest and migration plan; no source branch head aliases.
2. Receive Agent 3 **independent** candidate-bound QA verdict with same exact digests. If any required gate is FAIL/BLOCKED, do not install; ask coordinator. UI validation in SDK is not actual Force touchscreen proof, so a controlled UI-hardware candidate may be approved with explicit remaining T3 checks.
3. Get **new explicit user authorization to install** and restart; prior V1 authorization is not permission to auto-install any later candidate. Ensure device not in an active show.
4. Verify live architecture, service status, available disk, package integrity, plugin UID uniqueness, library ABI, existing asset index/digest, readable local `factory-assets-path.txt` and no scanner-visible backups. Never modify private ES5510 packages, firmware, MockbaMod, projects or other VSTs.
5. Preserve currently installed package in **new immutable external** verified backup; do not overwrite prior fallback. Confirm rollback readiness first.
6. Install exactly approved package and verify hash post-copy. Use supported, controlled service restart/reconnect only after preflight.
7. Check plugin discovery; request user test of MAIN/EFFECT page legibility, visible HALL 0–99, physical Q-Link knob movement distinctly from touch UI, wet/dry, bypass, input/output, sound changes at several decay values, project save/recall, selected other effects. Collect xrun/CPU logs when safe. Leave device running if healthy; roll back promptly on load or severe audio regression.
8. Publish result with exact binary+asset hashes, actions and PASS/FAIL/BLOCKED/NOT_TESTED, rollback status and evidence. Never report device tests the user did not perform.

## Avoid repeating prior pitfalls

- `factory-assets-path.txt` must be included **before** generating package file inventory, else checksums break.
- Old `QEMU PASS` reports belong to different binary hashes; mark NOT_RUN for unmatched candidates.
- `install_package.py` can reject an older customized installation. Don't delete/overwrite on validation failure; use verified backup and a documented recovery procedure.
- Do not call host service status alone proof of DSP audio quality or Q-Link mapping.
- Preserve exact candidate artifacts for independent testing; don't rely on a rebuild of the same source.

## Response to coordinator

Report `HOLD` until approval. After approval supply preflight, candidate hashes, backup path/hash, installation/restart, hardware user observations, outcome, rollback steps. Never self-activate from a GitHub branch update.
