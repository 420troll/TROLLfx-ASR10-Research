#!/usr/bin/env python3
"""Run the official SDK TUI generator against a temporary graphics-pack fixture."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "force_plugin/graphics/v3"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sdk", required=True, type=Path, help="Official AkaiForceSDK checkout")
    args = ap.parse_args()
    generator = args.sdk / "tools/gen_ui.py"
    if not generator.is_file():
        ap.error(f"SDK skin generator not found: {generator}")
    params_data = {"params": [
        {"index": 0, "name": "FX Slot", "kind": "choice", "choices": ["HALL REVERB", "44KHZ REVERB"], "default": 0},
        {"index": 1, "name": "Wet / Dry", "kind": "float", "default": 0.5, "display": "50 %"},
    ]}
    ui_data = {
        "backgroundImage": "panel_background.png",
        "kit": {"theme": "cyan", "accent": "ff00c7c2"},
        "style": {"background": "ff15191c", "accent": "ff00c7c2", "text": "fff4f8fa", "muted": "ff85949a"},
        "pages": [{"name": "BROWSE", "controls": [
            {"param": "Wet / Dry", "widget": "knob"},
            {"param": "FX Slot", "widget": "slider", "overlay": "menu"},
        ]}],
    }
    with tempfile.TemporaryDirectory(prefix="asr10-graphics-sdk-smoke-") as temp:
        base = Path(temp)
        params, ui, out = base / "params.json", base / "ui.json", base / "Plugin Skins"
        params.write_text(json.dumps(params_data))
        ui.write_text(json.dumps(ui_data))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        subprocess.run([sys.executable, str(generator), "--params", str(params), "--ui", str(ui),
                        "--out", str(out), "--assets-dir", str(PACK / "assets"), "--quiet"],
                       check=True, env=env)
        # SDK build.py copies the project's assets/ tree after gen_ui.py runs.
        shutil.copy2(PACK / "assets/panel_background.png", out / "panel_background.png")
        tui = (out / "TUI.json").read_text()
        qlinks = json.loads((out / "Q-Links.json").read_text())
        count = tui.count("panel_background.png")
        if count < 2:
            raise RuntimeError(f"expected focused/unfocused panel background references, found {count}")
        if not (out / "knob_uni.png").is_file():
            raise RuntimeError("SDK kit knob image was not generated/copied")
        if len(qlinks["Screen Mode Q-Links"]["map"]) != 1:
            raise RuntimeError("expected one generated screen-mode Q-Link map")
        if not (out / "panel_background.png").is_file():
            raise RuntimeError("panel background was not copied into Plugin Skins")
    print(f"PASS: SDK generated TUI/Q-Links and {count} focused/unfocused background references")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
