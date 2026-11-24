# TROLLfx ASR-10 FX Collection — release infrastructure

The build produces a VST2 package for the original Akai Force (ARMv7 hard-float), plus AArch64 compatibility output. It is marked **candidate / not playable** until the DSP integration report passes the explicit marker gate. Build/package does not install or restart anything.

```sh
AKAI_FORCE_SDK=/path/to/AkaiForceSDK force_plugin/tools/build_candidate.sh
```

For the full commands, SDK discovery rules, package paths, marker report schema, installation safety and rollback, see [`docs/TROLLFX_ASR10_FORCE_BUILD_PACKAGING.md`](../docs/TROLLFX_ASR10_FORCE_BUILD_PACKAGING.md).

The installer accepts only a checksummed package with `INTEGRATION_STATUS` bound to its ARM32 binary. It requires an explicit package and destination path. Build candidates currently contain no DSP verification marker and must not be installed. No proprietary factory assets are bundled. Repository source is GPL-3.0-only; the compiled SDK framework notice is MIT.
