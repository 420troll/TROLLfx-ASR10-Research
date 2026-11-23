#!/usr/bin/env python3
"""Summarize ES5510 register commits around two PARAMMARKs without exposing values by default."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MARK = re.compile(r"PARAMMARK label=([^\s]+) cycles=(\d+) frame=(\d+)")
EVENT = re.compile(r"ESPHOST event=(\d+) cycles=(\d+) frame=(\d+) pc=([0-9a-f]{6,8}) (gpr ([0-9a-f]{2}) <- ([0-9a-f]{6})|both ([0-9a-f]{2}) <- [0-9a-f]{12} / ([0-9a-f]{6}))", re.I)


def analyze(path: Path, before: str, after: str, include_values: bool = False) -> dict:
    text = path.read_text(errors="replace")
    marks = {m.group(1): (int(m.group(2)), int(m.group(3))) for m in MARK.finditer(text)}
    if before not in marks or after not in marks:
        raise ValueError("requested marker is absent from the host log")
    if marks[after][0] <= marks[before][0]:
        raise ValueError("after marker must occur later than before marker")
    events = []
    for m in EVENT.finditer(text):
        register, value = (m.group(6), m.group(7)) if m.group(6) else (m.group(8), m.group(9))
        events.append({"event": int(m.group(1)), "cycles": int(m.group(2)), "frame": int(m.group(3)),
                       "pc": int(m.group(4), 16), "register": int(register, 16), "value": int(value, 16)})
    prior = [e for e in events if e["cycles"] < marks[before][0]]
    window = [e for e in events if marks[before][0] <= e["cycles"] < marks[after][0]]
    pre_state = {e["register"]: e["value"] for e in prior}
    post_state = dict(pre_state)
    for e in window:
        post_state[e["register"]] = e["value"]
    changed = []
    for reg in sorted({e["register"] for e in window}):
        old, new = pre_state.get(reg), post_state.get(reg)
        row = {"destination_register": f"0x{reg:02x}",
               "register_class": "GPR" if reg < 0xc0 else "special register",
               "written_in_window": True,
               "changed_from_prior_value": old is None or new != old,
               "write_count": sum(e["register"] == reg for e in window),
               "first_event": next(e["event"] for e in window if e["register"] == reg),
               "last_event": next(e["event"] for e in reversed(window) if e["register"] == reg)}
        if include_values:
            row["before_value"] = None if old is None else f"0x{old:06x}"
            row["after_value"] = None if new is None else f"0x{new:06x}"
        changed.append(row)
    return {"markers": {"before": before, "after": after,
                         "cycle_delta": marks[after][0] - marks[before][0],
                         "frame_delta": marks[after][1] - marks[before][1]},
            "host_register_commits_in_window": len(window), "destinations": changed,
            "redaction": "host values omitted" if not include_values else "values included; keep this report private"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("host_log", type=Path)
    p.add_argument("--before", required=True, help="PARAMMARK label immediately before the user edit")
    p.add_argument("--after", required=True, help="PARAMMARK label after the update has settled")
    p.add_argument("--include-values", action="store_true", help="include raw 24-bit host values in private output")
    args = p.parse_args()
    try:
        print(json.dumps(analyze(args.host_log, args.before, args.after, args.include_values), indent=2))
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
