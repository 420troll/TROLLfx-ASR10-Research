"""Versioned PC-only draft migration; separate from native VST state chunks."""
from __future__ import annotations

SCHEMA = "trollfx-asr10-pc-drafts-v1"


def migrate_drafts(document, valid_controls_by_slot):
    if not isinstance(document, dict):
        raise ValueError("draft document must be an object")
    version = int(document.get("schema_version", 0))
    if version not in (0, 1):
        raise ValueError(f"unsupported PC draft schema version {version}")
    rows = document.get("drafts", document if version == 0 else None)
    if not isinstance(rows, dict):
        raise ValueError("draft document has no drafts object")
    migrated, orphaned = {}, []
    for key, values in rows.items():
        if not isinstance(values, dict):
            orphaned.append({"draft_key": key, "values": values, "reason": "draft values are not an object"})
            continue
        try:
            slot_text, variation_text = str(key).split(":", 1)
            slot, variation = int(slot_text), int(variation_text)
        except (TypeError, ValueError):
            orphaned.append({"draft_key": key, "values": values, "reason": "invalid slot:variation key"})
            continue
        if not 1 <= variation <= 4 or slot not in valid_controls_by_slot:
            orphaned.append({"draft_key": key, "values": values, "reason": "unknown effect slot or variation"})
            continue
        valid = valid_controls_by_slot[slot]
        kept = {}
        for control_id, value in values.items():
            if control_id in valid:
                kept[control_id] = value
            else:
                orphaned.append({"draft_key": key, "control_id": control_id, "value": value,
                                 "reason": "identity no longer present; preserved for manual migration"})
        migrated[f"{slot}:{variation}"] = kept
    return {"schema": SCHEMA, "schema_version": 1, "drafts": migrated, "orphaned": orphaned}
