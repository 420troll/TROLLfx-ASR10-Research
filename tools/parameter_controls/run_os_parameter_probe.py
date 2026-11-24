#!/usr/bin/env python3
"""Run a recipe-driven OS 3.53 UI probe and summarize reversible host writes.

The recipe contains only local paths and timed UI actions. Its raw emulator log
and WAV should be written outside Git. No UI sequence is assumed by this tool.
"""
import argparse
import importlib.util
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIFF_SPEC = importlib.util.spec_from_file_location("parameter_host_diff", ROOT / "tools/parameter_host_diff.py")
DIFF = importlib.util.module_from_spec(DIFF_SPEC)
DIFF_SPEC.loader.exec_module(DIFF)


def validate_recipe(recipe):
    if not isinstance(recipe.get("actions"), list) or not recipe["actions"]:
        raise ValueError("recipe needs a non-empty actions list")
    last = -1.0
    labels = set()
    for action in recipe["actions"]:
        at = float(action["seconds"])
        if at < last or at < 0:
            raise ValueError("actions must have nonnegative nondecreasing times")
        last = at
        kind = action.get("type")
        if kind == "mark":
            label = action.get("label", "")
            if not label or any(c.isspace() for c in label) or label in labels:
                raise ValueError("marker labels must be unique nonempty tokens")
            labels.add(label)
        elif kind == "button":
            if not (0 <= int(action["code"]) <= 41) or int(action["down"]) not in (0, 1):
                raise ValueError("invalid panel button code/state")
        elif kind == "analog":
            if not (0 <= int(action["channel"]) < 8 and 0 <= int(action["value"]) <= 1023):
                raise ValueError("invalid analog channel/value")
        else:
            raise ValueError(f"unsupported action type: {kind}")
    if len(labels) < 2:
        raise ValueError("recipe needs at least two marker actions")
    return labels


def make_command(recipe, cli, roms, disk, wav):
    labels = validate_recipe(recipe)
    cmd = [str(cli), "--roms", str(roms), "--disk", str(disk),
           "--seconds", str(recipe.get("seconds", 40)), "--wav", str(wav), "--panel-log"]
    for action in recipe["actions"]:
        t = f"{float(action['seconds']):.6f}"
        if action["type"] == "mark":
            cmd += ["--param-mark", f"{t}:{action['label']}"]
        elif action["type"] == "button":
            cmd += ["--button", f"{t}:{int(action['code'])}:{int(action['down'])}"]
        elif action["type"] == "analog":
            cmd += ["--analog-at", f"{t}:{int(action['channel'])}:{int(action['value'])}"]
    return cmd, labels


def build_report(host_log, windows):
    results = []
    for window in windows:
        result = DIFF.analyze(host_log, window["before"], window["after"], include_values=True)
        result["action"] = window.get("action", f"{window['before']}->{window['after']}")
        results.append(result)
    by_action = {r["action"]: r for r in results}
    return {"windows": results, "repeatability_comparison": {
        "method": "compares ordered (register, before, after, write_count) rows for actions with matching destinations",
        "same_destinations_only": "repeatability is only asserted for matching reported destinations; periodic firmware activity remains unattributed",
        "identical_action_pairs": _compare_pairs(results),
    }}


def _compare_pairs(results):
    out = []
    for i, left in enumerate(results):
        for right in results[i + 1:]:
            if left["action"].split("#")[0] != right["action"].split("#")[0]:
                continue
            lrows, rrows = left["destinations"], right["destinations"]
            if [x["destination_register"] for x in lrows] == [x["destination_register"] for x in rrows]:
                out.append({"actions": [left["action"], right["action"]],
                            "same_registers_and_final_values": [(x["destination_register"], x["after_value"]) for x in lrows] == [(x["destination_register"], x["after_value"]) for x in rrows],
                            "interpretation": "host-write repeatability only; does not prove audible or factory-control equivalence"})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recipe", required=True, type=Path)
    ap.add_argument("--cli", required=True, type=Path)
    ap.add_argument("--roms", required=True, type=Path)
    ap.add_argument("--disk", required=True, type=Path)
    ap.add_argument("--wav", required=True, type=Path)
    ap.add_argument("--host-log", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    ap.add_argument("--include-values", action="store_true", help="keep raw GPR values in private report")
    args = ap.parse_args()
    recipe = json.loads(args.recipe.read_text())
    labels = validate_recipe(recipe)
    cmd, _ = make_command(recipe, args.cli.resolve(), args.roms.resolve(), args.disk.resolve(), args.wav.resolve())
    args.wav.parent.mkdir(parents=True, exist_ok=True)
    args.host_log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, ESP_HOSTLOG="1")
    with args.host_log.open("w") as log:
        run = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, check=False)
    if run.returncode:
        raise SystemExit(f"emulator exited {run.returncode}; inspect private log {args.host_log}")
    report = build_report(args.host_log, recipe.get("windows", []))
    report["recipe_id"] = recipe.get("id", "unnamed")
    report["markers"] = sorted(labels)
    report["raw_values_included"] = bool(args.include_values)
    if not args.include_values:
        for window in report["windows"]:
            for row in window["destinations"]:
                row.pop("before_value", None)
                row.pop("after_value", None)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"OS parameter probe complete: {len(report['windows'])} windows; report={args.report}")


if __name__ == "__main__":
    main()
