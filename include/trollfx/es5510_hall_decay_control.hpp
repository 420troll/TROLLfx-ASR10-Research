// Evidence-derived state model for OS 3.53 ROM-01 HALL DECAY TIME editing.
// This models the original OS 3.53 HALL Variation 1 front-panel transition and
// its observed ordered coefficient writes. It is deliberately separate from
// the ES5510 arithmetic core. Variation 2 and other algorithms are not covered.
#pragma once

#include <array>
#include <cstdint>
#include <stdexcept>

namespace trollfx::es5510::os353 {

// Raw 7-bit codes which share their displayed value with the immediately
// preceding code in the original OS lookup table. The list is a compact,
// transformed representation of the private OS table, not a ROM image.
inline constexpr std::array<std::uint8_t, 28> hall_decay_duplicate_codes = {
    2, 6, 11, 16, 20, 25, 29, 34, 38, 43, 47, 52, 57, 61,
    66, 70, 75, 80, 84, 89, 93, 98, 102, 107, 111, 116, 121, 125
};

inline constexpr std::uint8_t hall_decay_display_for_raw(std::uint8_t raw) {
    unsigned duplicates = 0;
    for (const auto code : hall_decay_duplicate_codes) duplicates += code <= raw;
    return static_cast<std::uint8_t>(raw - duplicates);
}

inline constexpr std::uint8_t hall_decay_raw_step(std::uint8_t raw, int direction) {
    if (raw > 127 || (direction != -1 && direction != 1))
        throw std::invalid_argument("HALL decay raw code/direction is outside the OS editor domain");
    if ((direction < 0 && raw == 0) || (direction > 0 && raw == 127)) return raw;
    const auto adjacent = static_cast<std::uint8_t>(static_cast<int>(raw) + direction);
    // F8AE98 skips the adjacent raw code when both codes look identical on the
    // LCD; the RAM editor handler then performs its ordinary +/-1 update.
    if (hall_decay_display_for_raw(adjacent) == hall_decay_display_for_raw(raw)) {
        const int skipped = static_cast<int>(raw) + 2 * direction;
        if (skipped >= 0 && skipped <= 127) return static_cast<std::uint8_t>(skipped);
    }
    return adjacent;
}

struct HallDecayGprWrite {
    std::uint8_t gpr;
    std::uint32_t value24;
};

inline constexpr std::array<HallDecayGprWrite, 5> hall_decay_registers(std::uint8_t raw) {
    if (raw > 127) throw std::invalid_argument("HALL decay raw coefficient must be 7-bit");
    // The OS uses the raw parameter for 6E and the low byte of 5B, but clamps
    // the quadratic coefficient path to 12..76 before computing GPR 03..05.
    const auto coefficient = raw < 12 ? 12u : raw > 76 ? 76u : raw;
    const std::int32_t d2 = static_cast<std::int32_t>(coefficient) << 8;
    const std::int32_t d3 = -d2;
    const std::int32_t product = d2 * d3;
    const std::int32_t d5 = (product + 0x3fffffff) >> 7; // 68000 ASR.L #7
    const std::uint32_t gpr3 = (static_cast<std::uint32_t>(d2) << 8) & 0x00ffffffu;
    const auto tag = raw <= 119 ? 8u : 127u - raw;
    return {{{0x6e, static_cast<std::uint32_t>(raw) << 16},
             {0x5b, (tag << 16) | raw},
             {0x03, gpr3},
             {0x04, (0u - gpr3) & 0x00ffffffu},
             {0x05, static_cast<std::uint32_t>(d5) & 0x00ffffffu}}};
}

} // namespace trollfx::es5510::os353
