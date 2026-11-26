#include "trollfx/hall_decay_native_adapter.hpp"

#ifndef TROLLFX_HALL_DECAY_NATIVE_GATE
#define TROLLFX_HALL_DECAY_NATIVE_GATE 0
#endif

namespace trollfx::es5510 {

bool HallDecayNativeAdapter::stageNumeric(std::int32_t value) noexcept {
    if (value < kMinimum || value > kMaximum) return false;
    pending_numeric_ = static_cast<std::int16_t>(value);
    return true;
}

void HallDecayNativeAdapter::discardNumeric() noexcept {
    pending_numeric_ = -1;
}

HallDecayAdapterResult HallDecayNativeAdapter::requestStep(
        FactoryRuntime& runtime, std::uint8_t slot, std::uint8_t variation,
        int direction) noexcept {
#if !TROLLFX_HALL_DECAY_NATIVE_GATE
    (void)runtime; (void)slot; (void)variation; (void)direction;
    return HallDecayAdapterResult::FeatureDisabled;
#else
    if (slot != 1 || variation != 1 || (direction != -1 && direction != 1))
        return HallDecayAdapterResult::UnsupportedContext;
    if (pending_numeric_ >= 0) return HallDecayAdapterResult::PendingNumericDraft;
    if (pending_step_) return HallDecayAdapterResult::Pending;
    const auto before = runtime.getStatus();
    if (!before.hall_decay_step_available || before.effect != EffectId::Rom01Hall)
        return HallDecayAdapterResult::UnknownRawState;
    const auto frame = before.processed_dsp_frames;
    writes_before_pending_ = before.scheduled_writes_applied;
    target_frame_ = frame;
    applied_display_ = before.hall_decay_display_value;
    applied_raw_ = before.hall_decay_raw_code;
    raw_available_ = true;
    if (!runtime.stepHallDecayTime(direction, frame))
        return HallDecayAdapterResult::RuntimeRejected;
    const auto scheduled = runtime.getStatus();
    if (!scheduled.hall_decay_step_available || scheduled.hall_decay_display_value < kMinimum ||
        scheduled.hall_decay_display_value > kMaximum || scheduled.hall_decay_raw_code > 127)
        return HallDecayAdapterResult::RuntimeRejected;
    pending_display_ = scheduled.hall_decay_display_value;
    pending_raw_ = scheduled.hall_decay_raw_code;
    pending_step_ = true;
    return HallDecayAdapterResult::Pending;
#endif
}

HallDecayAdapterResult HallDecayNativeAdapter::reset(
        FactoryRuntime& runtime, std::uint8_t slot, std::uint8_t variation) noexcept {
#if !TROLLFX_HALL_DECAY_NATIVE_GATE
    (void)runtime; (void)slot; (void)variation;
    return HallDecayAdapterResult::FeatureDisabled;
#else
    if (slot != 1 || variation != 1) return HallDecayAdapterResult::UnsupportedContext;
    if (!runtime.reset()) return HallDecayAdapterResult::RuntimeRejected;
    pending_step_ = false;
    pending_display_ = -1;
    pending_numeric_ = -1;
    const auto status = runtime.getStatus();
    raw_available_ = status.hall_decay_step_available;
    if (raw_available_) {
        applied_display_ = status.hall_decay_display_value;
        applied_raw_ = status.hall_decay_raw_code;
    }
    return raw_available_ ? HallDecayAdapterResult::Applied : HallDecayAdapterResult::UnknownRawState;
#endif
}

HallDecayEditorState HallDecayNativeAdapter::refresh(
        FactoryRuntime& runtime, std::uint8_t slot, std::uint8_t variation) noexcept {
    HallDecayEditorState result;
    result.effect_slot = slot;
    result.variation = variation;
    result.has_pending_numeric = pending_numeric_ >= 0;
    result.pending_display_value = pending_numeric_ >= 0 ? pending_numeric_ : pending_display_;
    result.pending_raw_code = pending_raw_;
    result.has_pending_step = pending_step_;
    result.applied_display_value = applied_display_;
    result.applied_raw_code = applied_raw_;
    result.raw_state_available = raw_available_;
    if (slot != 1 || variation != 1) {
        result.status = "unsupported effect/variation context";
        return result;
    }
    const auto runtime_status = runtime.getStatus();
    if (!pending_step_ && runtime_status.hall_decay_step_available) {
        applied_display_ = runtime_status.hall_decay_display_value;
        applied_raw_ = runtime_status.hall_decay_raw_code;
        raw_available_ = true;
    } else if (pending_step_ && runtime_status.scheduled_writes_applied >= writes_before_pending_ + 5 &&
               runtime_status.processed_dsp_frames >= target_frame_) {
        applied_display_ = pending_display_;
        applied_raw_ = pending_raw_;
        pending_step_ = false;
        raw_available_ = true;
    } else if (!runtime_status.hall_decay_step_available && !pending_step_) {
        raw_available_ = false;
    }
    result.applied_display_value = applied_display_;
    result.applied_raw_code = applied_raw_;
    result.pending_display_value = pending_numeric_ >= 0 ? pending_numeric_ : pending_step_ ? pending_display_ : -1;
    result.pending_raw_code = pending_step_ ? pending_raw_ : 0;
    result.has_pending_step = pending_step_;
    result.has_pending_numeric = pending_numeric_ >= 0;
    result.raw_state_available = raw_available_;
#if TROLLFX_HALL_DECAY_NATIVE_GATE
    result.status = pending_step_ ? "native step pending DSP application" :
        pending_numeric_ >= 0 ? "numeric entry pending; raw destination unknown" :
        raw_available_ ? "runtime raw/display state available" : "runtime raw state unknown";
#else
    result.status = pending_numeric_ >= 0 ? "numeric entry pending; native step feature disabled" :
        "native HALL full-range step feature disabled by promotion gate";
#endif
    return result;
}

} // namespace trollfx::es5510
