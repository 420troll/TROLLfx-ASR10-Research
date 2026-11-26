// PC-side adapter for the stateful HALL DECAY runtime API.
// Promotion to the shipped editor remains disabled until independent runtime,
// audio and VST compatibility gates all pass.
#pragma once

#include "trollfx/es5510_factory_runtime.hpp"

namespace trollfx::es5510 {

enum class HallDecayAdapterResult {
    Applied, Pending, FeatureDisabled, UnsupportedContext, UnknownRawState,
    PendingNumericDraft, RuntimeRejected
};

struct HallDecayEditorState {
    std::uint8_t effect_slot = 1;
    std::uint8_t variation = 0;
    std::int16_t applied_display_value = -1;
    std::uint8_t applied_raw_code = 0;
    std::int16_t pending_display_value = -1;
    std::uint8_t pending_raw_code = 0;
    bool raw_state_available = false;
    bool has_pending_step = false;
    bool has_pending_numeric = false;
    const char* status = "not initialized";
};

class HallDecayNativeAdapter final {
public:
    static constexpr std::int32_t kMinimum = 0;
    static constexpr std::int32_t kMaximum = 99;

    // Stages only a PC draft. It never maps an LCD value to a raw code.
    bool stageNumeric(std::int32_t display_value) noexcept;
    void discardNumeric() noexcept;
    HallDecayAdapterResult requestStep(FactoryRuntime& runtime, std::uint8_t slot,
                                      std::uint8_t variation, int direction) noexcept;
    HallDecayAdapterResult reset(FactoryRuntime& runtime, std::uint8_t slot,
                                 std::uint8_t variation) noexcept;
    HallDecayEditorState refresh(FactoryRuntime& runtime, std::uint8_t slot,
                                 std::uint8_t variation) noexcept;

private:
    std::int16_t applied_display_ = -1;
    std::uint8_t applied_raw_ = 0;
    std::int16_t pending_display_ = -1;
    std::uint8_t pending_raw_ = 0;
    std::int16_t pending_numeric_ = -1;
    std::uint64_t writes_before_pending_ = 0;
    std::uint64_t target_frame_ = 0;
    bool raw_available_ = false;
    bool pending_step_ = false;
};

} // namespace trollfx::es5510
