#!/usr/bin/env python3
"""Local browser monitor for an instrumented OS 3.53 ASR-10 CLI session."""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[2]
HTML = Path(__file__).with_name("index.html")
LCD = re.compile(r'^PANELLCD cycles=(\d+) frame=(\d+) lcd="(.{22})" underline="(.{22})" cursor="(.{22})"')
GPR = re.compile(r'^ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-f]+)(?: caller=([0-9a-f]+))? gpr ([0-9a-f]{2}) <- ([0-9a-f]{6}) t=([0-9.]+)', re.I)
ROM = re.compile(r'^ESP_ROM_SELECT id=(\d+) .*?display=(.*)$')
CPU = re.compile(r'^ESPCALL cycles=(\d+) frame=(\d+) pc=([0-9a-f]+) sp=([0-9a-f]+) gpr=([0-9a-f]{2}) regs=([0-9a-f:]+)', re.I)
PANEL_VALUE = re.compile(r'^\s*(.{1,18}?)\s*=\s*(.*?)\s*$')


class Monitor:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.lock = threading.RLock()
        self.events = deque(maxlen=3000)
        self.registers: dict[str, str] = {}
        self.lcd = " " * 22
        self.underline = " " * 22
        self.cursor = " " * 22
        self.selected_slot = None
        self.selected_name = None
        self.variation = None
        self.process = None
        self.last_activity = None
        self.last_error = None
        self.next_id = 1
        self.pending_edit = None
        self.pending_action = None
        self.diffs = deque(maxlen=100)
        self.slot_names = self._load_slots(cfg.get("selector_inventory"))
        self.mapping_status = self._load_mapping(cfg.get("parameter_mappings"))
        self._start_cli()

    @staticmethod
    def _load_slots(path):
        if not path:
            return {}
        try:
            rows = json.loads(Path(path).read_text()).get("entries", [])
            return {int(x["id"]): str(x.get("factory_name", x.get("name", ""))) for x in rows}
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    @staticmethod
    def _load_mapping(path):
        if not path:
            return {}
        try:
            rows = json.loads(Path(path).read_text()).get("controls", [])
            return {(int(x["slot"]), str(x.get("display_name", "")).strip().upper()): {
                "status": "VERIFIED POINTS ONLY" if x.get("verified_points") else "UNRESOLVED",
                "points": [p.get("value") for p in x.get("verified_points", [])]}
                for x in rows}
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    def _event(self, event):
        with self.lock:
            event = {"id": self.next_id, "utc": datetime.now(timezone.utc).isoformat(), **event}
            self.next_id += 1
            self.events.append(event)
            self.last_activity = event["utc"]
            return event

    def _start_cli(self):
        cfg = self.cfg
        binary = Path(cfg["cli"]).resolve()
        rom_dir = Path(cfg["rom_dir"]).resolve()
        disk = Path(cfg["os_disk"]).resolve()
        for label, path in (("CLI binary", binary), ("ROM directory", rom_dir), ("OS disk", disk)):
            if not path.exists():
                raise RuntimeError(f"Configured {label} is unavailable")
        env = dict(os.environ)
        env["ESP_HOSTLOG"] = "1"
        if cfg.get("cpu_trace", False):
            env["ESP_CALLER_TRACE"] = "1"
        else:
            env.pop("ESP_CALLER_TRACE", None)
        self.process = subprocess.Popen(
            [str(binary), "--roms", str(rom_dir), "--disk", str(disk), "--wav", "/dev/null",
             "--seconds", str(int(cfg.get("emulator_seconds", 86400))), "--monitor-stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, bufsize=1, env=env)
        threading.Thread(target=self._read_cli, name="asr10-monitor-log", daemon=True).start()

    def _read_cli(self):
        try:
            for line in self.process.stderr:
                self.ingest_line(line.rstrip("\r\n"))
        except (OSError, ValueError):
            self.last_error = "Emulator output stream ended."

    def ingest_line(self, line):
        """Ingest only safe structured telemetry; arbitrary CLI text is discarded."""
        if m := LCD.match(line):
            with self.lock:
                self.lcd, self.underline, self.cursor = m[3], m[4], m[5]
                vm = re.search(r"\bVAR\s*=\s*(\d+)", m[3], re.I)
                if vm:
                    self.variation = int(vm[1])
            event = self._event({"type": "lcd", "cycles": int(m[1]), "frame": int(m[2]),
                                 "lcd": m[3], "underline": m[4], "cursor": m[5]})
            self._finish_action_if_display_changed(event)
            return
        if m := GPR.match(line):
            key, value = f"0x{int(m[6],16):02X}", f"0x{int(m[7],16):06X}"
            with self.lock:
                before = self.registers.get(key)
                self.registers[key] = value
                pending = self.pending_edit
                if pending is not None and before != value:
                    pending["write_ids"].append(self.next_id)
                    pending["writes"].append({"gpr": key, "before": before, "value": value,
                                              "pc": "0x" + m[4], "caller": None if not m[5] else "0x" + m[5],
                                              "cycles": int(m[2]), "frame": int(m[3])})
            self._event({"type": "gpr", "cycles": int(m[2]), "frame": int(m[3]),
                         "pc": "0x" + m[4], "caller": None if not m[5] else "0x" + m[5],
                         "gpr": key, "value": value})
            return
        if m := CPU.match(line):
            regs = m[6].split(":")
            # Keep only address registers useful for tracing the OS conversion
            # dispatch. The raw stack and nearby RAM are intentionally omitted.
            event = {"type": "cpu_trace", "cycles": int(m[1]), "frame": int(m[2]),
                     "pc": "0x" + m[3], "sp": "0x" + m[4],
                     "gpr": "0x" + m[5], "a2": "0x" + regs[10],
                     "a3": "0x" + regs[11], "a6": "0x" + regs[14]}
            self._event(event)
            return
        if m := ROM.match(line):
            slot = int(m[1])
            with self.lock:
                self.selected_slot, self.selected_name = slot, self.slot_names.get(slot)
            self._event({"type": "effect_select", "slot": slot,
                         "name": self.slot_names.get(slot, "name not in local inventory")})
            return
        if "PANEL_ACTION_TIMEOUT" in line or "ESP ROM" in line or "ERROR" in line:
            # Do not retain arbitrary emulator output: it can contain local paths.
            self.last_error = "Emulator reported an error; details omitted from dashboard."

    def _finish_action_if_display_changed(self, event):
        """Keep button navigation evidence distinct from value-edit evidence."""
        with self.lock:
            action = self.pending_action
            if action is None:
                return
            if (action["before_lcd"], action["before_underline"], action["before_cursor"]) == (
                    self.lcd, self.underline, self.cursor):
                return
            before = action["before_lcd"]
            after = self.lcd
            before_field, before_display_value = _selected_parameter(
                before, _active_marker(action["before_cursor"], action["before_underline"]))
            after_field, after_display_value = _selected_parameter(
                after, _active_marker(self.cursor, self.underline))
            action["after_lcd"] = after
            action["after_underline"] = self.underline
            action["after_cursor"] = self.cursor
            action["after_event_id"] = event["id"]
            action["register_diff"] = {key: {"before": action["before_registers"].get(key), "after": value}
                                        for key, value in self.registers.items()
                                        if action["before_registers"].get(key) != value}
            action["change_kind"] = ("parameter_value" if before_field == after_field and
                                      before_display_value != after_display_value else
                                      "navigation_or_page" if before_field != after_field else
                                      "selection_or_cursor" )
            self.diffs.append(action)
            self.pending_action = None
            if self.pending_edit is action:
                self.pending_edit = None

    def tap(self, code: int):
        if not 0 <= code <= 41:
            raise ValueError("button code outside 0..41")
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError("emulator is not running")
            action = {"before_lcd": self.lcd, "before_underline": self.underline,
                      "before_cursor": self.cursor, "before_registers": dict(self.registers),
                      "button": code, "writes": [], "write_ids": [],
                      "started_utc": datetime.now(timezone.utc).isoformat()}
            self.pending_action = action
            if code in (10, 11):
                self.pending_edit = action
            self._event({"type": "panel_action", "button": code,
                         "before_lcd": self.lcd, "before_cursor": self.cursor})
            self.process.stdin.write(f"TAP {code}\n")
            self.process.stdin.flush()

    def status(self):
        with self.lock:
            field, value = _selected_parameter(self.lcd, _active_marker(self.cursor, self.underline))
            slot = self.selected_slot
            mapping = self.mapping_status.get((slot, field.upper()), {}) if slot and field else {}
            return {"running": bool(self.process and self.process.poll() is None),
                    "lcd": self.lcd, "underline": self.underline, "cursor": self.cursor,
                    "selected_slot": slot, "selected_name": self.selected_name,
                    "variation": self.variation,
                    "parameter": field, "display_value": value,
                    "recovery_status": mapping.get("status", "NO EXACT MAPPING REGISTERED"),
                    "verified_values": mapping.get("points", []),
                    "register_count": len(self.registers),
                    "recent_actions": list(self.diffs)[-10:],
                    "last_activity": self.last_activity, "error": self.last_error,
                    "process_exit_code": None if not self.process else self.process.poll()}

    def event_page(self, after=0):
        with self.lock:
            return [e for e in self.events if e["id"] > after]

    def save_evidence(self, label="session"):
        out = Path(self.cfg["evidence_dir"]).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_-]+", "-", label).strip("-")[:48] or "session"
        with self.lock:
            payload = {"schema": "asr10-os-monitor-evidence-v1", "saved_utc": datetime.now(timezone.utc).isoformat(),
                       "status": self.status(), "registers": dict(self.registers),
                       "recent_edit_diffs": list(self.diffs), "events": list(self.events)}
        path = out / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{safe}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return path.name

    def stop(self):
        p = self.process
        if p and p.poll() is None:
            try:
                p.stdin.write("QUIT\n"); p.stdin.flush(); p.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                p.terminate()


def _parameter_value(text):
    m = PANEL_VALUE.match(text.rstrip())
    return (m[1].strip(), m[2].strip()) if m else None


def _active_marker(cursor, underline):
    return cursor if any(ch not in " \0" for ch in cursor) else underline


def _selected_parameter(lcd, cursor):
    """Use the OS cursor position to select a field when multiple fields share an LCD."""
    candidates = list(re.finditer(r"([A-Z][A-Z0-9 /+()&.-]*?)\s*=\s*([^ ]+(?: [^ ]+)*)", lcd.rstrip(), re.I))
    active = [i for i, ch in enumerate(cursor) if ch not in " \0"]
    if active:
        pos = active[0]
        for m in candidates:
            if m.start() <= pos < m.end():
                return m.group(1).strip(), m.group(2).strip()
    if candidates:
        m = candidates[0]
        return m.group(1).strip(), m.group(2).strip()
    return None, None


def serve(cfg):
    monitor = Monitor(cfg)

    class Handler(BaseHTTPRequestHandler):
        server_version = "ASR10LocalMonitor/1"
        def log_message(self, *_args):
            pass
        def send_json(self, payload, status=200):
            raw = json.dumps(payload).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                raw = HTML.read_bytes(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
            elif u.path == "/api/status": self.send_json(monitor.status())
            elif u.path == "/api/events":
                after = int(parse_qs(u.query).get("after", ["0"])[0]); self.send_json({"events": monitor.event_page(after)})
            else: self.send_error(404)
        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size > 4096: return self.send_json({"error": "request too large"}, 413)
                body = json.loads(self.rfile.read(size) or b"{}")
                if self.path == "/api/button":
                    monitor.tap(int(body["code"])); self.send_json({"ok": True})
                elif self.path == "/api/save": self.send_json({"ok": True, "file": monitor.save_evidence(str(body.get("label", "session")))})
                else: self.send_error(404)
            except (ValueError, KeyError, RuntimeError, OSError, json.JSONDecodeError) as e:
                self.send_json({"error": str(e)}, 400)

    host, port = cfg.get("bind", "127.0.0.1"), int(cfg.get("port", 8765))
    if host not in ("127.0.0.1", "localhost", "::1"):
        monitor.stop(); raise RuntimeError("monitor must bind to localhost")
    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError:
        monitor.stop()
        raise
    print(f"ASR-10 OS monitor: http://localhost:{port}")
    print("Use the browser to observe the live original LCD and send panel button events.")
    try: server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt: pass
    finally: server.server_close(); monitor.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    serve(cfg)


if __name__ == "__main__":
    main()
