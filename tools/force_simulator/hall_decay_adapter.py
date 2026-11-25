"""Fail-closed adapter contract for Codex 1's stateful HALL runtime API.

This deliberately does not bind the editor's existing VST parameter IDs to the
experimental FactoryRuntime. A native binding can be supplied after independent
QA accepts the complete ordered register group. Numeric display edits never
guess a raw code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class HallDecaySnapshot:
    effect_slot: int
    variation: int
    display_value: int | None
    raw_code: int | None
    mapping_status: str
    applied_value: int | None
    pending_value: int | None = None
    reason: str = ""


class HallDecayRuntimeAdapter:
    CONTROL_ID = "ASR10:ROM-01:decay_time"
    DISPLAY_MIN = 0
    DISPLAY_MAX = 99

    def __init__(self, runtime: Any, *, independent_qa_accepted: bool = False):
        self.runtime = runtime
        self.independent_qa_accepted = independent_qa_accepted
        self.pending_value: int | None = None
        self.applied_value: int | None = None
        self.reason = ""

    def snapshot(self, effect_slot: int, variation: int) -> HallDecaySnapshot:
        if effect_slot != 1 or variation != 1:
            return HallDecaySnapshot(
                effect_slot=effect_slot,
                variation=variation,
                display_value=None,
                raw_code=None,
                mapping_status="UNSUPPORTED_CONTEXT",
                applied_value=self.applied_value,
                pending_value=self.pending_value,
                reason="Native HALL decay stepping is supported only for factory slot 1, Variation 1.",
            )
        status = self.runtime.getStatus()
        available = bool(status.hall_decay_step_available)
        display = int(status.hall_decay_display_value) if available else None
        raw = int(status.hall_decay_raw_code) if available else None
        if display is not None:
            self.applied_value = display
        return HallDecaySnapshot(
            effect_slot=effect_slot,
            variation=variation,
            display_value=display,
            raw_code=raw,
            mapping_status="VERIFIED_STEP_API" if self.independent_qa_accepted and available else "PENDING_INDEPENDENT_QA",
            applied_value=self.applied_value,
            pending_value=self.pending_value,
            reason=self.reason or ("Codex 3 found unresolved full-range register mismatches; native stepping remains gated." if not self.independent_qa_accepted else ""),
        )

    def stage_display_value(self, effect_slot: int, variation: int, value: int) -> HallDecaySnapshot:
        if effect_slot != 1:
            raise ValueError("HALL DECAY TIME adapter only supports factory slot 1")
        numeric = int(value)
        if float(value) != numeric:
            raise ValueError("HALL DECAY TIME requires an integer display value")
        if not self.DISPLAY_MIN <= numeric <= self.DISPLAY_MAX:
            raise ValueError("HALL DECAY TIME display value must be in 0..99")
        # A display number is not a unique raw coefficient. Preserve the last
        # runtime raw/display pair and keep direct entry as an explicit draft.
        self.pending_value = numeric
        self.reason = "Direct display entry has no validated raw-code destination; retained as a PC-only pending draft."
        return self.snapshot(effect_slot, variation)

    def discard_pending(self) -> None:
        self.pending_value = None
        self.reason = ""

    def step(self, effect_slot: int, variation: int, direction: int, frame: int | None = None) -> HallDecaySnapshot:
        if direction not in (-1, 1):
            raise ValueError("step direction must be -1 or +1")
        before = self.snapshot(effect_slot, variation)
        if effect_slot != 1 or variation != 1:
            self.reason = "Native HALL decay step requires factory slot 1, Variation 1."
            return self.snapshot(effect_slot, variation)
        if self.pending_value is not None:
            self.reason = "Discard or apply the pending numeric draft before stepping from runtime raw state."
            return self.snapshot(effect_slot, variation)
        if not self.independent_qa_accepted:
            self.reason = "Independent QA has not accepted the complete HALL register transition; no runtime call was made."
            return self.snapshot(effect_slot, variation)
        if not bool(getattr(self.runtime.getStatus(), "hall_decay_step_available", False)):
            self.reason = "Runtime has no validated HALL raw-code state; reload a validated Variation 1 checkpoint."
            return self.snapshot(effect_slot, variation)
        status = self.runtime.getStatus()
        scheduled_frame = int(status.processed_dsp_frames) if frame is None else int(frame)
        if not self.runtime.stepHallDecayTime(direction, scheduled_frame):
            self.reason = "Runtime rejected the atomic HALL step; applied raw/display state was retained."
            return self.snapshot(effect_slot, variation)
        after = self.snapshot(effect_slot, variation)
        if after.raw_code is None or after.display_value is None:
            self.reason = "Runtime accepted the step but did not return a valid raw/display state; edit is not promoted."
            after.mapping_status = "REJECTED_RUNTIME_STATE"
            after.applied_value = before.applied_value
            return after
        self.applied_value = after.display_value
        self.pending_value = None
        self.reason = ""
        after.applied_value = self.applied_value
        after.pending_value = None
        return after
