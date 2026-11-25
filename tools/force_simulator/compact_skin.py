"""Apply the project's readable text profile to SDK-generated TUI JSON."""
from __future__ import annotations

import json
from pathlib import Path


def _bounds(raw: str) -> tuple[int, int, int, int]:
    values = tuple(int(float(value)) for value in str(raw).split())
    if len(values) != 4:
        raise ValueError(f"invalid SDK bounds {raw!r}")
    return values


def compact_skin(path: Path) -> dict[str, int]:
    """Compact generated labels without moving controls or changing SDK indices.

    The SDK generator gives knob value labels 30 px text in a 156 px column.
    Long verified labels and the unmapped message are then clipped by the stock
    label bounds. The profile changes only font heights and the value-label
    width inside the existing 276 px knob cell.
    """
    path = Path(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    page_data = document["pageData"]
    definitions = list(page_data["componentDefinitions"]["localComponentDefinitions"])
    definitions.extend({"key": tab["tabName"], "value": tab["componentDefinition"]}
                      for tab in page_data.get("tabs", []) if tab.get("componentDefinition"))
    counts = {"headings": 0, "names": 0, "values": 0, "value_widths": 0}
    for definition in definitions:
        key = definition.get("key", "")
        for entry in definition.get("value", {}).get("componentsData", []):
            component = entry.get("componentData", {})
            if component.get("type") != "Label":
                continue
            data = component.get("data", {})
            style = data.get("textStyle", {})
            font = style.get("font", {})
            label_type = data.get("type")
            if label_type == "Text":
                font["height"] = 20.0
                if data.get("text") == "TROLLfx / ASR-10 FACTORY FX":
                    data["text"] = "ASR-10 FACTORY FX"
                elif data.get("text") == "ACTIVE FACTORY PARAMETERS":
                    data["text"] = "FACTORY EDIT"
                counts["headings"] += 1
            elif label_type == "Name":
                font["height"] = 18.0
                counts["names"] += 1
            elif label_type == "Value":
                font["height"] = 15.0
                counts["values"] += 1
                if key in ("knobUni", "knobBi"):
                    x, y, width, height = _bounds(entry["bounds"]["bounds"])
                    if width < 166:
                        entry["bounds"]["bounds"] = f"{x} {y} 166 {height}"
                        counts["value_widths"] += 1
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return counts


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tui_json", type=Path)
    args = parser.parse_args()
    print(json.dumps(compact_skin(args.tui_json), sort_keys=True))
