#include "trollfx/es5510_hall_decay_control.hpp"

#include <cassert>
#include <cstdint>
#include <set>
#include <vector>

using namespace trollfx::es5510::os353;

int main() {
    std::set<unsigned> displayed;
    for (unsigned raw = 0; raw <= 127; ++raw)
        displayed.insert(hall_decay_display_for_raw(static_cast<std::uint8_t>(raw)));
    assert(displayed.size() == 100);
    assert(*displayed.begin() == 0 && *displayed.rbegin() == 99);

    // A full ascending editor walk takes the lower raw code at each repeated
    // LCD bucket; a full descending walk takes its upper raw code.
    std::vector<unsigned> ascending(100), descending(100);
    std::uint8_t raw = 0;
    ascending[0] = raw;
    for (unsigned value = 1; value <= 99; ++value) {
        raw = hall_decay_raw_step(raw, +1);
        assert(hall_decay_display_for_raw(raw) == value);
        ascending[value] = raw;
    }
    raw = 127;
    descending[99] = raw;
    for (int value = 98; value >= 0; --value) {
        raw = hall_decay_raw_step(raw, -1);
        assert(hall_decay_display_for_raw(raw) == value);
        descending[static_cast<unsigned>(value)] = raw;
    }
    unsigned one_code_disagreements = 0;
    for (unsigned value = 0; value <= 99; ++value) {
        const unsigned delta = ascending[value] > descending[value]
            ? ascending[value] - descending[value] : descending[value] - ascending[value];
        if (delta) {
            assert(delta == 1);
            ++one_code_disagreements;
        }
    }
    assert(one_code_disagreements == hall_decay_duplicate_codes.size());

    const auto writes = hall_decay_registers(0x34);
    constexpr std::uint8_t expected_gprs[] = {0x6e, 0x5b, 0x03, 0x04, 0x05};
    constexpr std::uint32_t expected_values[] = {0x340000, 0x080034, 0x340000,
                                                  0xcc0000, 0x6adfff};
    for (unsigned i = 0; i < writes.size(); ++i) {
        assert(writes[i].gpr == expected_gprs[i]);
        assert(writes[i].value24 == expected_values[i]);
    }

    for (unsigned code = 0; code <= 127; ++code) {
        const auto row = hall_decay_registers(static_cast<std::uint8_t>(code));
        const unsigned coefficient = code < 12 ? 12 : code > 76 ? 76 : code;
        const unsigned tag = code <= 119 ? 8 : 127 - code;
        assert(row[0].value24 == (code << 16));
        assert(row[1].value24 == ((tag << 16) | code));
        assert(row[2].value24 == (coefficient << 16));
        assert(row[3].value24 == ((0u - row[2].value24) & 0xffffffu));
        const std::int32_t x = static_cast<std::int32_t>(coefficient) << 8;
        const std::int32_t gain = ((x * -x) + 0x3fffffff) >> 7;
        assert(row[4].value24 == (static_cast<std::uint32_t>(gain) & 0xffffffu));
    }
    return 0;
}
