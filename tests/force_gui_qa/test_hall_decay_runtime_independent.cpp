#include "trollfx/es5510_factory_runtime.hpp"
#include "es5510.h"

#include <array>
#include <cassert>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

using namespace trollfx::es5510;

static std::string make_synthetic_capture() {
    auto path = (std::filesystem::temp_directory_path() / "qa-hall-decay-runtime.esp").string();
    ES5510 dsp;
    for (unsigned i = 0; i < 89; ++i) {
        const std::uint64_t instruction = i == 88 ? 0x00000000f000ULL : 0;
        for (unsigned b = 0; b < 6; ++b)
            dsp.host_w(3 + b, static_cast<std::uint8_t>(instruction >> (40 - 8 * b)));
        dsp.host_w(0xc0, static_cast<std::uint8_t>(i));
    }
    dsp.host_w(0x18, 0x48);
    FILE* f = std::fopen(path.c_str(), "wb");
    assert(f && dsp.write_capture(f));
    std::fclose(f);
    return path;
}

static std::uint8_t display_from_os_table_route(unsigned raw) {
    // Duplicate positions were independently counted from the OS 3.53 table dump.
    constexpr std::array<unsigned, 28> duplicate_upper = {
        2,6,11,16,20,25,29,34,38,43,47,52,57,61,
        66,70,75,80,84,89,93,98,102,107,111,116,121,125
    };
    unsigned duplicates = 0;
    for (auto code : duplicate_upper) duplicates += code <= raw;
    return static_cast<std::uint8_t>(raw - duplicates);
}

#ifdef TROLLFX_QA_REGISTER_ACCESS
int main(int argc, char** argv) {
    assert(argc == 2);
    std::array<std::array<std::uint32_t, 5>, 128> os_expected{};
    std::array<bool, 128> os_seen{};
    std::array<bool, 128> runtime_raw_seen{};
    std::ifstream expected_file(argv[1]);
    assert(expected_file.good());
    std::string line;
    while (std::getline(expected_file, line)) {
        std::istringstream row(line);
        unsigned raw, g6e, g5b, g03, g04, g05;
        char comma;
        if (!(row >> raw >> comma >> std::hex >> g6e >> comma >> g5b >> comma >> g03 >> comma >> g04 >> comma >> g05)) continue;
        assert(raw < 128);
        os_expected[raw] = {g6e, g5b, g03, g04, g05};
        os_seen[raw] = true;
    }
    for (bool seen : os_seen) assert(seen);
#else
int main() {
#endif
    const auto path = make_synthetic_capture();
    EffectPackage pkg{EffectId::Rom01Hall, path, 89, 29761.89453125, true, true, true, 1};
    FactoryRuntime runtime;
    assert(runtime.loadEffect(pkg, RateMode::FactoryReference));
    auto status = runtime.getStatus();
    assert(status.hall_decay_step_available && status.hall_decay_raw_code == 0 &&
           status.hall_decay_display_value == 0);
    assert(!runtime.stepHallDecayTime(0, 0));
    runtime_raw_seen[status.hall_decay_raw_code] = true;

    std::array<float, 128> in{}, out{};
    std::size_t accepted = 0;
    auto step = [&](int direction) {
        const auto frame = runtime.getStatus().processed_dsp_frames;
        assert(runtime.stepHallDecayTime(direction, frame));
        ++accepted;
        status = runtime.getStatus();
        assert(status.hall_decay_step_available);
        assert(status.hall_decay_display_value == display_from_os_table_route(status.hall_decay_raw_code));
        runtime_raw_seen[status.hall_decay_raw_code] = true;
        assert(runtime.processStereo(in.data(), out.data(), in.size()/2, 48000.0));
        assert(runtime.getStatus().scheduled_writes_applied == accepted * 5);
#ifdef TROLLFX_QA_REGISTER_ACCESS
        const auto raw = runtime.getStatus().hall_decay_raw_code;
        constexpr std::array<std::uint8_t, 5> registers = {0x6e, 0x5b, 0x03, 0x04, 0x05};
        for (std::size_t i = 0; i < registers.size(); ++i)
            assert(runtime.qaReadRegister(registers[i]) == os_expected[raw][i]);
#endif
    };

    // Full UI domain and both duplicate-bucket routes, checked against the raw
    // lookup table's independently derived state model.
    // UI steps skip duplicate raw codes so each accepted event advances one
    // displayed value. 99 clicks cover 0->99 (raw 0->127).
    for (int i = 0; i < 99; ++i) step(+1);
    assert(runtime.getStatus().hall_decay_raw_code == 127);
    assert(runtime.getStatus().hall_decay_display_value == 99);
    for (int i = 0; i < 99; ++i) step(-1);
    assert(runtime.getStatus().hall_decay_raw_code == 0);
    assert(runtime.getStatus().hall_decay_display_value == 0);
    for (bool seen : runtime_raw_seen) assert(seen);

    // Unknown raw state fails closed after any direct GPR 6E write.
    assert(runtime.setRegister(0x6e, 0x010000, runtime.getStatus().processed_dsp_frames));
    assert(!runtime.getStatus().hall_decay_step_available);
    assert(!runtime.stepHallDecayTime(+1, runtime.getStatus().processed_dsp_frames));
    assert(runtime.reset());
    assert(runtime.getStatus().hall_decay_step_available);
    assert(runtime.getStatus().hall_decay_raw_code == 0 &&
           runtime.getStatus().hall_decay_display_value == 0);

    // No variation is inferred from the slot number.
    pkg.factory_variation = 0;
    assert(runtime.loadEffect(pkg, RateMode::FactoryReference));
    assert(!runtime.getStatus().hall_decay_step_available);
    assert(!runtime.stepHallDecayTime(+1, 0));
    pkg.factory_variation = 2;
    assert(runtime.loadEffect(pkg, RateMode::FactoryReference));
    assert(!runtime.getStatus().hall_decay_step_available);
    assert(!runtime.stepHallDecayTime(+1, 0));
    std::filesystem::remove(path);
    std::puts("independent HALL decay runtime API: 198 LCD steps, 99 each direction, PASS");
}
