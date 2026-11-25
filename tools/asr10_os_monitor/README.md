# ASR-10 Original OS Monitor

This local browser monitor runs an instrumented `asr10-cli` OS 3.53 session. It shows the original 22-character panel display and ES5510 host GPR writes, and sends physical panel button events back to the emulator process. The browser cannot write display values or DSP registers directly.

## Setup

Build the CLI, copy `config.example.json` to a private path, and fill in the authorized local ROM, OS disk, inventory and evidence paths. The config contains private machine paths; keep it outside Git.

```sh
bash tools/build_research_cli.sh
cp tools/asr10_os_monitor/config.example.json /home/gamer/research/private-results/asr10-os-monitor-config.json
# Edit the copied file with local paths.
python3 tools/asr10_os_monitor/monitor.py --config /home/gamer/research/private-results/asr10-os-monitor-config.json
```

Open `http://localhost:8765` in Windows or WSL. The monitor binds only to localhost. It launches its own headless OS 3.53 CLI session with `/dev/null` audio output, which keeps the observation and control path in one process. To leave, stop the monitor with Ctrl+C; it asks the child emulator to exit.

## Controls and evidence

EDIT (5), EFFECTS (9), Left (16), Right (17), Up (10), Down (11), Cancel/No (33), and Yes/Enter (35) are sent as 30 ms panel presses. The LCD is polled from the original emulated panel after each 1 ms CPU/DSP slice. Host writes are parsed into a bounded in-memory event ring; raw emulator output and local paths are never served. “Save evidence JSON” writes structured LCD/register telemetry to the configured private evidence directory.

The selected field uses the emulator's cursor/underline position when an LCD contains more than one `name=value` field. Each button action records its before/after 22-character LCD and cursor independently of whether it changed a parameter value. Register differences and ordered host writes are attached to an action when observed.

The mapping status reads V5 exact-point evidence only. It does not apply a mapping to the emulator. Unsupported controls remain OS-editable in the original session but are labeled `NO EXACT MAPPING REGISTERED` in the monitor. Set `"cpu_trace": true` in the private config to enable targeted CPU snapshots immediately before host writes for HALL decay-related GPRs. The dashboard exposes PC, stack pointer and A2/A3/A6 only; it omits raw stack and memory bytes. For private forensic exports, `tools/parameter_controls/extract_os_cpu_parameter_trace.py` parses full emulator logs and writes the expanded CPU/memory windows to the requested private JSON path.

## Interactive protocol

The CLI's optional `--monitor-stdio` mode reads nonblocking `TAP <code>`, `BUTTON <code> <0|1>`, and `QUIT` commands between emulation slices. The Python monitor currently uses `TAP`; each event is applied on the emulation thread. All display/register telemetry is read from standard error as structured lines.
