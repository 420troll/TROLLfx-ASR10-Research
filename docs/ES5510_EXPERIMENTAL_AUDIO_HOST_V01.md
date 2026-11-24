# TROLLfx ES5510 Experimental Audio Host V0.1

The WAV host and native factory runtime are integrated. The full private-state
requirements, invocation examples, runtime validation, playable files,
measurements, and limitations are documented in
[`ES5510_EXPERIMENTAL_INTEGRATED_V01.md`](ES5510_EXPERIMENTAL_INTEGRATED_V01.md).

Build and run the synthetic backend tests:

```sh
sh tools/build_experimental_audio_host.sh
sh tools/test_experimental_audio_host.sh
```

The executable requires an explicit backend. `--backend runtime` uses the
validated private ROM-01 HALL or ROM-02 checkpoint, replay-derived post-RUN
firmware events, and the existing native ES5510 implementation at experimental
48 kHz. `--backend mock` is deterministic synthetic delay audio for interface
tests and is not an authentic factory effect. Runtime mode fails closed when
any checkpoint, manifest, two-boot reference, or event schedule is missing or
invalid.

The host keeps processor state between blocks, limits callback work to fixed
stack buffers and preloaded processor state, and performs effect reloads from
the control service between blocks. Effect transitions fade out and fade in
over five milliseconds with a reload gap. Runtime wet/dry mixes align the dry
signal to the reported two-frame algorithmic latency. Input WAV rates other
than 48 kHz are converted at the host boundary; the DSP runs at 48 kHz in this
experimental release.
