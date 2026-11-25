#!/usr/bin/env python3
"""Check catalog effect names/range strings against a user-provided manual PDF.

Requires optional `pypdf`. The report retains page/status/hash metadata only,
not extracted manual text. Use the owner's local manual copy; do not commit it.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from audit_factory_parameter_spec import MANUAL_PAGES, ROOT, SOURCE


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--output", type=Path, default=ROOT / "docs/qa-v4/manual-pdf-audit.json")
    a = ap.parse_args()
    from pypdf import PdfReader

    reader = PdfReader(str(a.pdf))
    pages = [page.extract_text() or "" for page in reader.pages]
    catalog = json.loads((SOURCE / "ASR10_FACTORY_PARAMETER_CATALOG_V1.json").read_text())
    report_rows = []
    counts = {"EXACT_RANGE_TEXT_FOUND": 0, "SHARED_VARIATION_TEXT_FOUND": 0,
              "RANGE_ENDPOINTS_FOUND_UNITS_IN_PROSE": 0, "NOT_FOUND_REVIEW": 0}
    known_unit_spelled_in_prose = {4: {"0 to 2000 ms": "0 to 2000"},
                                   5: {"0 to 1300 ms": "0 to 1300"}}
    intro = norm(" ".join(pages[97:100]))
    for e in catalog["effects"]:
        slot = e["slot"]
        page = MANUAL_PAGES[slot]
        local = norm(" ".join(pages[max(0, page - 2):min(len(pages), page + 3)]))
        for p in e["parameters"]:
            r = p.get("documented_range")
            if not r:
                status = "NOT_FOUND_REVIEW"
            elif p["id"] == "effect_variation" and "four effect variations" in intro:
                status = "SHARED_VARIATION_TEXT_FOUND"
            elif norm(r) in local:
                status = "EXACT_RANGE_TEXT_FOUND"
            elif r in known_unit_spelled_in_prose.get(slot, {}) and norm(known_unit_spelled_in_prose[slot][r]) in local:
                status = "RANGE_ENDPOINTS_FOUND_UNITS_IN_PROSE"
            else:
                status = "NOT_FOUND_REVIEW"
            counts[status] += 1
            report_rows.append({"slot": slot, "effect_name": e["factory_name"],
                                "parameter_id": p["id"], "catalog_range": r,
                                "catalog_units": p.get("units"),
                                "manual_pdf_page_window_center": page,
                                "manual_text_check": status})
    # Check all effect identifiers/names against the ordered ROM heading list.
    headers = []
    for pageno, text in enumerate(pages, start=1):
        for m in re.finditer(r"(?m)^ROM-(\d{2})\s+([^\n]+)", text):
            slot = int(m.group(1))
            if 1 <= slot <= 50:
                headers.append({"slot": slot, "name": m.group(2).strip(), "page": pageno})
    ordered = []
    want = 1
    for h in headers:
        if h["slot"] == want:
            ordered.append(h)
            want += 1
            if want == 51:
                break
    names_ok = len(ordered) == 50 and all(
        re.sub(r"[^A-Z0-9]", "", ordered[i]["name"].upper()) ==
        re.sub(r"[^A-Z0-9]", "", catalog["effects"][i]["factory_name"].upper())
        for i in range(50))
    h = hashlib.sha256(a.pdf.read_bytes()).hexdigest()
    out = {"schema": "asr10-manual-pdf-text-audit-v1", "manual_sha256": h,
           "manual_pages": len(pages), "effect_headers_found": len(ordered),
           "all_effect_names_match_after_punctuation_normalization": names_ok,
           "range_status_counts": counts,
           "limits": ["Exact text presence is a transcription check, not a determination that a descriptor is one independent control.",
                      "Ranges do not establish OS visibility or DSP behavior; grouped fields are tracked separately."],
           "parameters": report_rows}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "parameters"}, indent=2))


if __name__ == "__main__":
    main()
