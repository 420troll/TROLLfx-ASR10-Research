#!/usr/bin/env python3
"""Validate the generated image pack against its manifest and SDK frame geometry."""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "force_plugin/graphics/v3"
ASSETS = PACK / "assets"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    manifest = json.loads((PACK / "asset-manifest.json").read_text())
    assets = manifest["assets"]
    names = [item["path"] for item in assets]
    check(len(names) == len(set(names)), "duplicate asset manifest entries")
    check(len(assets) == 45, f"expected 45 generated assets, got {len(assets)}")
    check(manifest["canvas_px"] == {"width": 1280, "height": 628}, "unexpected page canvas")
    expected_sizes = {
        "panel_background.png": (1280, 628), "parameter_card.png": (278, 107),
        "parameter_card_active.png": (278, 107), "parameter_card_disabled.png": (278, 107),
        "parameter_card_unavailable.png": (278, 107), "lcd_frame.png": (520, 82),
        "factory_program_display_frame.png": (640, 100), "trollfx_asr10_wordmark.png": (420, 82),
        "separator.png": (320, 3), "status_led_active.png": (20, 20),
        "status_led_standby.png": (20, 20), "status_led_warning.png": (20, 20),
        "status_led_off.png": (20, 20), "knob_uni.png": (90, 90*127),
        "knob_bi.png": (90, 90*127), "knob_small_uni.png": (56, 56*127),
        "knob_small_bi.png": (56, 56*127), "fader_h_uni.png": (248, 36*127),
        "fader_h_bi.png": (248, 36*127), "toggle_on.png": (64, 32), "toggle_off.png": (64, 32),
        "button_on.png": (120, 44), "button_off.png": (120, 44),
        "seg2_on.png": (122, 40), "seg2_off.png": (122, 40),
        "seg3_on.png": (80, 40), "seg3_off.png": (80, 40),
        "seg4_on.png": (58, 40), "seg4_off.png": (58, 40),
    }
    for n in range(1, 9):
        expected_sizes[f"qlink_q{n}.png"] = (72, 72)
    for tab in ("browse", "edit", "mix", "info"):
        expected_sizes[f"tab_{tab}_active.png"] = (144, 40)
        expected_sizes[f"tab_{tab}_inactive.png"] = (144, 40)
    by_name = {item["path"]: item for item in assets}
    check(set(expected_sizes).issubset(by_name), "expected reusable asset missing from manifest")
    for item in assets:
        path = ASSETS / item["path"]
        check(path.is_file(), f"manifest file missing: {path}")
        with Image.open(path) as image:
            check(image.format == "PNG", f"not PNG: {path.name}")
            check((image.width, image.height) == (item["width_px"], item["height_px"]),
                  f"dimension mismatch: {path.name}")
            if path.name in expected_sizes:
                check((image.width, image.height) == expected_sizes[path.name],
                      f"target resolution mismatch: {path.name}")
            check(image.mode == item["mode"], f"mode mismatch: {path.name}")
            if item.get("frames"):
                check(image.height == item["frames"] * item["frame_height_px"],
                      f"film-strip frame count mismatch: {path.name}")
                check(image.width == item["frame_width_px"], f"film-strip width mismatch: {path.name}")
            actual_transparency = "alpha" if "A" in image.getbands() and image.getextrema()[-1][0] < 255 else "opaque"
            check(actual_transparency == item["transparency"], f"alpha metadata mismatch: {path.name}")
    check((ASSETS / "panel_background.png").stat().st_size > 0, "background image is empty")
    check((PACK / "preview/retro-interface-concept.png").is_file(), "concept preview missing")
    print(f"PASS: {len(assets)} PNG assets, dimensions, alpha and frame metadata")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
