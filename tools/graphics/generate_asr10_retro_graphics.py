#!/usr/bin/env python3
"""Generate the ASR-10 retro graphics pack using Pillow and the official SDK kit renderer."""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "force_plugin/graphics/v3"
W, H = 1280, 628
GRID_X = [23, 343, 663, 983]
GRID_Y = [45, 196, 346, 497]
ACCENT = (0, 199, 194, 255)
PALE_LCD = (201, 242, 185, 255)
INK = (15, 20, 23, 255)
GRAPHITE = (27, 34, 38, 255)
MID = (48, 59, 64, 255)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill, outline=None, width: int = 1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def card_image(size=(278, 107), state="normal") -> Image.Image:
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if state == "disabled":
        outer, top, bottom, accent = (94, 103, 106, 150), (39, 45, 48, 210), (22, 26, 28, 210), (120, 130, 132, 190)
    elif state == "unavailable":
        outer, top, bottom, accent = (179, 118, 54, 220), (45, 40, 33, 238), (24, 26, 27, 238), (220, 163, 84, 255)
    elif state == "active":
        outer, top, bottom, accent = (0, 199, 194, 235), (43, 58, 62, 250), (20, 29, 33, 250), ACCENT
    else:
        outer, top, bottom, accent = (69, 82, 87, 255), (41, 49, 53, 255), (22, 27, 30, 255), (0, 147, 147, 255)
    rounded(d, (0, 0, size[0]-1, size[1]-1), 10, outer)
    rounded(d, (2, 2, size[0]-3, size[1]-3), 9, top)
    d.line((12, 2, size[0]-12, 2), fill=(177, 194, 196, 80), width=1)
    d.rounded_rectangle((5, 6, 8, size[1]-7), radius=1, fill=accent)
    d.line((14, size[1]-6, size[0]-13, size[1]-6), fill=(0, 0, 0, 180), width=1)
    if state in ("disabled", "unavailable"):
        overlay = Image.new("RGBA", size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        if state == "disabled":
            od.rectangle((10, 10, size[0]-10, size[1]-10), fill=(80, 86, 87, 72))
        else:
            for x in range(-size[1], size[0], 12):
                od.line((x, 10, x+size[1]-20, size[1]-10), fill=(230, 170, 83, 38), width=3)
        im = Image.alpha_composite(im, overlay)
    return im


def draw_brushed_background() -> Image.Image:
    im = Image.new("RGBA", (W, H), (18, 23, 26, 255))
    px = im.load()
    rng = random.Random(5510)
    for y in range(H):
        base = 18 + int(8 * y / H)
        grain = rng.choice((-2, -1, 0, 0, 0, 1, 2))
        row = (base + grain, base + 5 + grain, base + 8 + grain, 255)
        for x in range(W):
            px[x, y] = row
    d = ImageDraw.Draw(im)
    rounded(d, (8, 7, W-9, H-8), 14, None, (73, 91, 96, 255), 2)
    d.line((22, 39, W-22, 39), fill=ACCENT, width=2)
    d.text((28, 11), "TROLLfx", font=font(19, True), fill=(221, 236, 232, 255))
    d.text((133, 14), "ASR-10 FX COLLECTION", font=font(12, True), fill=(149, 178, 177, 255))
    im.alpha_composite(make_lcd_frame((440, 30)), (640, 4))
    d.text((1095, 15), "48 kHz", font=font(10, True), fill=(109, 148, 150, 255))
    # A recessed page frame sits behind SDK-native controls in its fixed 4 x 4 grid.
    for y in GRID_Y:
        for x in GRID_X:
            tile = card_image()
            im.alpha_composite(tile, (x, y))
    # Subtle chassis screws at the four corners.
    for x, y in ((18, 18), (W-19, 18), (18, H-19), (W-19, H-19)):
        d.ellipse((x-4, y-4, x+4, y+4), fill=(67, 79, 82, 255), outline=(10, 14, 16, 255), width=1)
        d.line((x-2, y, x+2, y), fill=(16, 21, 23, 255), width=1)
    return im


def make_lcd_frame(size=(520, 82)) -> Image.Image:
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w, h = size
    rounded(d, (0, 0, w-1, h-1), 9, (15, 20, 22, 255), (91, 110, 111, 255), 3)
    rounded(d, (7, 7, w-8, h-8), 5, (51, 67, 59, 255), (5, 10, 10, 255), 2)
    rounded(d, (12, 12, w-13, h-13), 3, (119, 152, 115, 255), (88, 119, 89, 255), 1)
    # Fine horizontal LCD texture; the real value/name stays in native SDK text widgets.
    for y in range(16, h-15, 4):
        d.line((15, y, w-16, y), fill=(208, 244, 193, 24), width=1)
    return im


def make_program_display(size=(640, 100)) -> Image.Image:
    return make_lcd_frame(size)


def make_brand(size=(420, 82)) -> Image.Image:
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((0, 0), "TROLL", font=font(48, True), fill=(211, 228, 225, 255), stroke_width=1, stroke_fill=(30, 43, 46, 255))
    x = d.textbbox((0, 0), "TROLL", font=font(48, True))[2] + 8
    d.text((x, 7), "fx", font=font(40, True), fill=ACCENT)
    d.line((2, 65, min(size[0]-3, x+65), 65), fill=ACCENT, width=3)
    d.text((x+79, 48), "ASR-10 FX COLLECTION", font=font(10, True), fill=(155, 182, 181, 255))
    return im


def make_led(color, size=20) -> Image.Image:
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((2, 2, size-3, size-3), fill=(10, 14, 15, 255), outline=(83, 98, 99, 255), width=1)
    c = {"active": (183, 239, 151, 255), "standby": (0, 199, 194, 255), "warning": (232, 164, 72, 255), "off": (62, 75, 76, 255)}[color]
    d.ellipse((5, 5, size-6, size-6), fill=c)
    d.ellipse((6, 5, size//2, size//2), fill=(255, 255, 255, 75))
    return im


def make_tab(name, active=False) -> Image.Image:
    im = Image.new("RGBA", (144, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = (24, 54, 57, 255) if active else (34, 41, 44, 245)
    edge = ACCENT if active else (76, 91, 94, 230)
    rounded(d, (1, 1, 142, 38), 6, fill, edge, 2 if active else 1)
    d.text((72, 20), name, font=font(13, True), fill=(206, 240, 224, 255) if active else (158, 174, 174, 255), anchor="mm")
    return im


def make_qlink(n: int) -> Image.Image:
    im = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((3, 3, 68, 68), fill=(25, 32, 35, 255), outline=(91, 110, 112, 255), width=2)
    d.arc((9, 9, 62, 62), 205, 335, fill=ACCENT, width=4)
    d.ellipse((27, 27, 45, 45), fill=(14, 19, 21, 255), outline=(46, 63, 65, 255), width=1)
    d.text((36, 54), f"Q{n}", font=font(11, True), fill=(205, 236, 224, 255), anchor="mm")
    return im


def render_assets(asset_dir: Path) -> list[dict]:
    asset_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    static: dict[str, tuple[Image.Image, str, str]] = {
        "panel_background.png": (draw_brushed_background(), "SDK backgroundImage: whole 1280x628 page; fixed card wells align to native 4x4 control grid.", "sdk_background"),
        "parameter_card.png": (card_image(), "Reusable frame reference; incorporated into panel_background because SDK has no arbitrary image widget.", "concept_component"),
        "parameter_card_active.png": (card_image(state="active"), "Active-state reference; SDK skin generator does not dynamically swap card backgrounds.", "concept_component"),
        "parameter_card_disabled.png": (card_image(state="disabled"), "Disabled-state reference; requires runtime/widget state support beyond static SDK backgrounds.", "concept_only"),
        "parameter_card_unavailable.png": (card_image(state="unavailable"), "Unavailable-state reference with amber hatching; not a dynamic SDK widget skin.", "concept_only"),
        "lcd_frame.png": (make_lcd_frame(), "Reusable recessed LCD frame; preview/integration reference; dynamic text must use native labels.", "concept_component"),
        "factory_program_display_frame.png": (make_program_display(), "Blank recessed program display frame; dynamic name and slot text must be native SDK labels.", "concept_component"),
        "trollfx_asr10_wordmark.png": (make_brand(), "Brand lockup; used in page background and preview. No Ensoniq logo or firmware artwork.", "sdk_background_and_preview"),
        "separator.png": (Image.new("RGBA", (320, 3), (0, 0, 0, 0)), "Thin cyan separator; can be included in background artwork.", "sdk_background_component"),
        "status_led_active.png": (make_led("active"), "Pale-green active indicator; static/background use unless represented by a native bool widget.", "concept_component"),
        "status_led_standby.png": (make_led("standby"), "Cyan ready indicator; static/background use unless represented by a native bool widget.", "concept_component"),
        "status_led_warning.png": (make_led("warning"), "Amber unavailable/error indicator; state must be supplied by native UI logic.", "concept_component"),
        "status_led_off.png": (make_led("off"), "Unlit indicator reference.", "concept_component"),
    }
    for name, (im, _, _) in static.items():
        p = asset_dir / name
        im.save(p, optimize=True)
        generated.append(p)
    for name in ("BROWSE", "EDIT", "MIX", "INFO"):
        for active in (False, True):
            p = asset_dir / f"tab_{name.lower()}_{'active' if active else 'inactive'}.png"
            make_tab(name, active).save(p, optimize=True)
            generated.append(p)
    for q in range(1, 9):
        p = asset_dir / f"qlink_q{q}.png"
        make_qlink(q).save(p, optimize=True)
        generated.append(p)
    return [{"path": p.name, "use": static[p.name][1] if p.name in static else
             ("Preview/concept tab badge; the MPC renders editable native function-key tab labels." if p.name.startswith("tab_") else
              "Preview/concept Q-Link assignment badge; the SDK Q-Link map is native JSON and custom badge placement is unsupported."),
             "integration": static[p.name][2] if p.name in static else "concept_only"} for p in generated]


def render_preview(asset_dir: Path, preview_path: Path) -> None:
    panel = Image.open(asset_dir / "panel_background.png").convert("RGBA")
    # Representative dynamic display overlay: native text, not baked into the background asset.
    lcd = make_lcd_frame((440, 30))
    panel.alpha_composite(lcd, (640, 4))
    pd = ImageDraw.Draw(panel)
    pd.text((651, 11), "02   44KHZ REVERB", font=font(13, True), fill=(27, 51, 35, 255))
    # Representative native labels and SDK knob film-strip frames.
    knob = Image.open(asset_dir / "knob_uni.png").convert("RGBA")
    frame = knob.crop((0, 90 * 52, 90, 90 * 53)).resize((82, 82), Image.Resampling.LANCZOS)
    # 90-pixel SDK film strip is sampled once at frame 52; image is only for mockup compositing.
    for i, (title, value) in enumerate((("FX SLOT", "44KHZ REVERB"), ("PARAM 01", "VALUE"), ("PARAM 02", "VALUE"), ("HOST WET / DRY", "72 %"))):
        x, y = GRID_X[i], GRID_Y[0]
        pd.text((x+16, y+11), title, font=font(11, True), fill=(130, 164, 166, 255))
        if i in (0, 1, 2):
            pd.text((x+16, y+45), value, font=font(15, True), fill=PALE_LCD)
        else:
            panel.alpha_composite(frame, (x+12, y+20))
            pd.text((x+105, y+47), value, font=font(14, True), fill=(222, 235, 231, 255))
    # SDK-native tab names are shown as plain labels in this concept, not custom tab PNGs.
    tabs = ImageDraw.Draw(panel)
    for i, name in enumerate(("BROWSE", "EDIT", "MIX", "INFO")):
        tabs.text((24 + i*88, 607), name, font=font(10, True), fill=(0, 225, 218, 255) if i == 0 else (135, 158, 158, 255))
    # The outside annotations explicitly separate usable SDK resources from conceptual assets.
    canvas = Image.new("RGB", (1660, 850), (14, 19, 22))
    canvas.paste(panel.convert("RGB"), (24, 66))
    d = ImageDraw.Draw(canvas)
    d.text((24, 20), "TROLLfx / ASR-10 FX COLLECTION — RETRO GRAPHICS CONCEPT", font=font(21, True), fill=(224, 239, 234))
    x0 = 1332
    d.text((x0, 80), "SDK-SUPPORTED", font=font(15, True), fill=ACCENT)
    supported = ["1280 x 628 whole-page background", "Transparent PNG film-strip knobs", "Native value/name labels", "Native editable function tabs", "PNG button states + Q-Link JSON", "Fixed 4 x 4 controls (278 x 107 slots)"]
    y = 112
    for line in supported:
        d.text((x0, y), "• " + line, font=font(12), fill=(205, 220, 216))
        y += 31
    d.text((x0, y+10), "CONCEPT-ONLY ASSETS", font=font(15, True), fill=(228, 174, 96))
    y += 42
    for line in ["Independent LCD/card layers", "Custom image tab badges", "Dynamic Q1-Q8 image badges", "Per-control disabled/unavailable skin", "The SDK has no arbitrary image widget"]:
        d.text((x0, y), "• " + line, font=font(12), fill=(205, 220, 216))
        y += 31
    y += 6
    d.text((x0, y), "REFERENCE TAB ART (CONCEPT ONLY)", font=font(11, True), fill=(177, 194, 191))
    y += 20
    for i, name in enumerate(("browse", "edit", "mix", "info")):
        tab = Image.open(asset_dir / f"tab_{name}_{'active' if i == 0 else 'inactive'}.png").convert("RGBA")
        tab_preview = tab.resize((72, 20), Image.Resampling.LANCZOS)
        canvas.paste(tab_preview, (x0 + i*76, y), tab_preview)
    y += 32
    d.text((x0, y), "Q1–Q8 REFERENCE BADGES (NOT THE SDK MAP)", font=font(10, True), fill=(177, 194, 191))
    y += 16
    for q in range(1, 9):
        badge = Image.open(asset_dir / f"qlink_q{q}.png").convert("RGBA")
        x = x0 + ((q-1) % 4) * 42
        by = y + ((q-1) // 4) * 40
        badge_preview = badge.resize((36, 36), Image.Resampling.LANCZOS)
        canvas.paste(badge_preview, (x, by), badge_preview)
    d.text((24, 718), "Mock parameter labels and values are illustrative; Codex 2 owns final layout, parameter bindings and Q-Link assignments.", font=font(13), fill=(156, 175, 174))
    d.text((24, 744), "Not a screenshot of the Force. The background and film-strip assets are generated for SDK-supported image paths; hardware fit still requires host review.", font=font(12), fill=(128, 149, 148))
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(preview_path, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sdk", type=Path, required=True, help="Official AkaiForceSDK checkout")
    args = ap.parse_args()
    kit_generator = args.sdk / "tools/make_ui_kit.py"
    if not kit_generator.is_file():
        ap.error(f"SDK UI kit generator not found: {kit_generator}")
    assets = OUT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    kit = ["knob_uni", "knob_bi", "knob_small_uni", "knob_small_bi", "fader_h_uni", "fader_h_bi",
           "toggle_on", "toggle_off", "button_on", "button_off", "seg2_on", "seg2_off", "seg3_on",
           "seg3_off", "seg4_on", "seg4_off"]
    subprocess.run([sys.executable, str(kit_generator), "--out", str(assets), "--theme", "cyan",
                    "--accent", "ff00c7c2", "--only", ",".join(kit), "--quiet"], check=True)
    custom = render_assets(assets)
    kit_json = json.loads((assets / "kit.json").read_text())
    manifest_items = []
    for item in custom:
        p = assets / item["path"]
        with Image.open(p) as im:
            item.update({"width_px": im.width, "height_px": im.height, "format": im.format,
                         "mode": im.mode, "transparency": "alpha" if "A" in im.getbands() and im.getextrema()[-1][0] < 255 else "opaque"})
        manifest_items.append(item)
    for name in kit:
        p = assets / f"{name}.png"
        with Image.open(p) as im:
            kit_entry = kit_json["assets"][name]
            if name.startswith("knob_"):
                integration, kind = "sdk_filmstrip", "rotary knob"
            elif name.startswith("fader_"):
                integration, kind = "sdk_filmstrip", "horizontal fader"
            else:
                integration, kind = "sdk_button", "stateful button / choice segment"
            manifest_items.append({"path": p.name, "width_px": im.width, "height_px": im.height,
                "format": im.format, "mode": im.mode, "transparency": "alpha" if "A" in im.getbands() and im.getextrema()[-1][0] < 255 else "opaque",
                "frames": kit_entry["frames"], "frame_width_px": kit_entry["width"], "frame_height_px": kit_entry["height"],
                "use": f"Official SDK-generated {kind}; see kit.json for the theme colors.",
                "integration": integration})
    manifest = {"schema": "trollfx-asr10-graphics-manifest-v1", "canvas_px": {"width": W, "height": H},
                "png_color_model": "RGBA PNG; alpha stored in PNG samples", "ui_color_format": "ARGB hex string (alpha first), e.g. ff00c7c2",
                "palette": {"graphite": "#12171A", "teal": "#00C7C2", "pale_lcd": "#C9F2B9", "warm_unavailable": "#E6A448"},
                "sdk_generator": "Official AkaiForceSDK tools/make_ui_kit.py; no SDK files modified",
                "kit_metadata": kit_json, "assets": manifest_items}
    (OUT / "asset-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    render_preview(assets, OUT / "preview/retro-interface-concept.png")
    print(f"wrote {len(manifest_items)} asset records under {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
