"""Read the generated Akai SDK TUI/Q-Link JSON into a small render model."""
from __future__ import annotations
import json
import re
from pathlib import Path


def _rect(raw: str) -> tuple[float, float, float, float]:
    parts = [float(x) for x in str(raw).split()]
    if len(parts) != 4:
        raise ValueError(f"invalid SDK bounds {raw!r}")
    return tuple(parts)


def _param_map(component: dict) -> dict[str, int]:
    result = {}
    for item in component.get("handle remapping", {}).get("map", []):
        match = re.fullmatch(r"Parameter (\d+)", str(item.get("value", "")))
        if match:
            result[str(item.get("key", "Data"))] = int(match.group(1))
    return result


def _conditions(bounds: dict) -> list[dict]:
    out = []
    for handle in bounds.get("additionalInvalidatingHandles", []):
        match = re.fullmatch(r"IndexedEnabling/(\d+)/(\d+)/Parameter (\d+)", handle)
        if match:
            i, n, p = map(int, match.groups())
            out.append({"parameter": p, "index": i, "count": n})
    return out


def load_skin(skin_dir: Path) -> dict:
    skin_dir = Path(skin_dir).resolve()
    tui_path = skin_dir / "TUI.json"
    qlinks_path = skin_dir / "Q-Links.json"
    tui = json.loads(tui_path.read_text(encoding="utf-8"))
    qlinks = json.loads(qlinks_path.read_text(encoding="utf-8"))
    page_data = tui["pageData"]
    definitions = {d["key"]: d["value"] for d in page_data["componentDefinitions"]["localComponentDefinitions"]}
    q_maps = qlinks.get("Screen Mode Q-Links", {}).get("map", [])
    pages = []
    referenced_images = set()
    diagnostics = []
    for page_index, tab in enumerate(page_data["tabs"]):
        definition = tab.get("componentDefinition") or definitions[tab["componentName"]]
        focused = definition.get("backgroundData", {}).get("focussed", {})
        background = focused.get("image")
        if background:
            referenced_images.add(background)
        items = []
        hitzones = []
        for top in definition.get("componentsData", []):
            cdata = top["componentData"]
            bounds = top["bounds"]
            x, y, w, h = _rect(bounds["bounds"])
            map_top = _param_map(top)
            top_param = map_top.get("Data")
            top_conditions = _conditions(bounds)
            ctype = cdata["type"]
            if ctype == "Label" and cdata.get("data", {}).get("type") == "Text":
                td = cdata["data"]
                ts = td.get("textStyle", {})
                items.append({"type": "text", "name": cdata["name"], "x": x, "y": y, "w": w, "h": h,
                    "text": td.get("text", ""), "color": ts.get("colour", "fff4f8fa"),
                    "font": ts.get("font", {}).get("name", "Titillium Web"),
                    "style": ts.get("font", {}).get("style", "Regular"),
                    "size": float(ts.get("font", {}).get("height", 24)),
                    "align": ts.get("justification", "left")})
                continue
            local = definitions.get(ctype)
            if local is None:
                diagnostics.append({"level": "warning", "code": "UNKNOWN_TOPLEVEL_WIDGET", "page": tab["tabName"], "widget": ctype})
                continue
            gesture_actions = {(a.get("onAction"), a.get("handler")) for a in local.get("actions", [])}
            parent_param = top_param
            local_type = ctype
            leaf_texts = []
            for child in local.get("componentsData", []):
                cd = child["componentData"]
                child_type = cd["type"]
                if child_type == "Focus" or child.get("bounds", {}).get("whenVisible") == "WhenFocussed":
                    continue
                cb = child["bounds"]
                cx, cy, cw, ch = _rect(cb["bounds"])
                rx, ry = x + cx, y + cy
                child_data = cd.get("data", {})
                param = _param_map(child).get(child_data.get("handleName", "Data"), parent_param)
                conditions = top_conditions + _conditions(cb)
                item = {"x": rx, "y": ry, "w": cw, "h": ch, "param": param,
                        "conditions": conditions, "parent": cdata.get("name", ctype),
                        "page": tab["tabName"]}
                if child_type == "Image" and child_data.get("image"):
                    item.update(type="image", src=child_data["image"]); referenced_images.add(child_data["image"])
                    items.append(item)
                elif child_type == "Knob" and child_data.get("knobType") == "FilmStrip":
                    src = child_data.get("filmStrip", "")
                    item.update(type="film", src=src, frames=int(child_data.get("numFrames") or 127),
                                invert=bool(child_data.get("invert", False)))
                    if src: referenced_images.add(src)
                    items.append(item)
                elif child_type == "Slider":
                    # The V4.1 slider definition supplies only a native Slider child and no
                    # artwork or geometry parameters. We draw an explicitly-marked approximation.
                    item.update(type="slider", direction=child_data.get("direction", "Horizontal"),
                                approximation=True)
                    items.append(item)
                elif child_type == "Button":
                    on = child_data.get("onImage", ""); off = child_data.get("offImage", "")
                    item.update(type="button", on=on, off=off,
                                button_id=int(child_data.get("buttonId", 1)),
                                button_count=int(child_data.get("numButtonsInGroup", 1)))
                    referenced_images.update(z for z in (on, off) if z)
                    items.append(item)
                elif child_type == "Label":
                    ts = child_data.get("textStyle", {}); font = ts.get("font", {})
                    kind = child_data.get("type", "Value")
                    text = cd.get("name", "") if kind == "Name" else ""
                    item.update(type="label", kind="name" if kind == "Name" else "value",
                                text=text, color=ts.get("colour", "fff4f8fa"),
                                font=font.get("name", "Titillium Web"), style=font.get("style", "Regular"),
                                size=float(font.get("height", 24)), align=ts.get("justification", "left"),
                                uppercase=ts.get("case") == "Upper Case")
                    if text: leaf_texts.append(text)
                    items.append(item)
                else:
                    diagnostics.append({"level": "warning", "code": "UNKNOWN_CHILD_WIDGET", "page": tab["tabName"], "widget": child_type})
            if len(leaf_texts) != len(set(leaf_texts)):
                diagnostics.append({"level": "warning", "code": "DUPLICATED_LABEL", "page": tab["tabName"], "widget": cdata.get("name")})
            if parent_param is not None:
                # The full SDK widget bounds are the touchscreen hit region. Host gestures are
                # approximated as vertical drag for knobs and horizontal drag for sliders.
                gesture = "toggle" if ("Mouse Down", "Toggle Switch") in gesture_actions or ctype == "toggle" else "drag"
                hitzones.append({"x": x, "y": y, "w": w, "h": h, "param": parent_param,
                                "gesture": gesture, "widget": cdata.get("name", ctype),
                                "conditions": top_conditions})
        q_map = q_maps[page_index].get("Q-Links", {}) if page_index < len(q_maps) else {}
        pages.append({"name": tab["tabName"], "width": int(_rect(tab.get("initialSize", "0 0 1280 628"))[2]),
                      "height": int(_rect(tab.get("initialSize", "0 0 1280 628"))[3]),
                      "background": background, "items": items, "hitzones": hitzones,
                      "qlinks": {str(i): int(q_map.get(f"Q-Link {i}", -1)) for i in range(1, 17)}})
    for name in sorted(referenced_images):
        if not (skin_dir / name).is_file():
            diagnostics.append({"level": "error", "code": "MISSING_ASSET", "asset": name})
    if len(pages) != len(q_maps):
        diagnostics.append({"level": "error", "code": "PAGE_QLINK_MAP_COUNT_MISMATCH", "pages": len(pages), "maps": len(q_maps)})
    return {"schema": "trollfx-force-ui-simulator-skin-v1", "skin_dir": str(skin_dir),
            "tui_sha256": __import__("hashlib").sha256(tui_path.read_bytes()).hexdigest(),
            "qlinks_sha256": __import__("hashlib").sha256(qlinks_path.read_bytes()).hexdigest(),
            "pages": pages, "assets": sorted(referenced_images), "diagnostics": diagnostics}
