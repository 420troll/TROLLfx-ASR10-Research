// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>

// Simulator-only diagnostics. These exports are compiled only into the local
// traced VST2 test build and are not part of the distributable plugin API.
struct TROLLfxVst2RuntimeStatus {
    std::uint64_t dsp_frames;
    std::uint64_t writes_applied;
    std::uint64_t initialization_complete_frame;
    std::uint32_t firmware_writes_pending;
    std::uint32_t parameter_writes_pending;
    std::uint8_t initialization_complete;
    std::uint8_t last_parameter_write_applied;
    std::uint8_t hall_state_provenance;
    std::uint8_t hall_raw_code;
    std::int16_t hall_display_value;
    std::uint8_t factory_variation;
};
