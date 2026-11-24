#include "trollfx/es5510_factory_parameter_control_v01.hpp"

#include <cassert>
#include <cstdint>
#include <vector>

using namespace trollfx::es5510::factory_parameters_v01;

struct MockRuntime {
    struct Event { std::uint8_t gpr; std::uint32_t value; std::uint64_t frame; };
    std::vector<Event> events;
    bool accept = true;
    bool setRegister(std::uint8_t gpr, std::uint32_t value, std::uint64_t frame) {
        if (!accept) return false;
        events.push_back({gpr, value, frame});
        return true;
    }
};

static void check_encoding(FactoryEffect effect, Parameter parameter,
                           int display, std::uint8_t expected_gpr,
                           std::uint32_t expected_value) {
    const auto result = encode(effect, parameter, display);
    assert(result.status == EncodeStatus::Encoded);
    assert(result.write.gpr == expected_gpr);
    assert(result.write.value24 == expected_value);
}

int main() {
    check_encoding(FactoryEffect::Rom01Hall, Parameter::ReverbMixBus1, 28, 0x7c, 0x3d0000);
    check_encoding(FactoryEffect::Rom01Hall, Parameter::ReverbMixBus1, 29, 0x7c, 0x3f0000);
    check_encoding(FactoryEffect::Rom01Hall, Parameter::ReverbMixBus2, 28, 0x7a, 0x3d0000);
    check_encoding(FactoryEffect::Rom01Hall, Parameter::ReverbMixBus2, 29, 0x7a, 0x3f0000);
    check_encoding(FactoryEffect::Rom02Reverb44k, Parameter::ReverbMixBus1, 25, 0x7c, 0x350000);
    check_encoding(FactoryEffect::Rom02Reverb44k, Parameter::ReverbMixBus1, 26, 0x7c, 0x370000);
    check_encoding(FactoryEffect::Rom02Reverb44k, Parameter::ReverbMixBus2, 25, 0x7a, 0x350000);
    check_encoding(FactoryEffect::Rom02Reverb44k, Parameter::ReverbMixBus2, 26, 0x7a, 0x370000);

    assert(encode(FactoryEffect::Rom01Hall, Parameter::ReverbMixBus2, 27).status ==
           EncodeStatus::UnverifiedDisplayValue);
    assert(encode(FactoryEffect::Rom02Reverb44k, Parameter::ReverbMixBus1, 27).status ==
           EncodeStatus::UnverifiedDisplayValue);
    assert(encode(static_cast<FactoryEffect>(49), Parameter::ReverbMixBus2, 25).status ==
           EncodeStatus::UnknownEffectOrParameter);

    MockRuntime runtime;
    assert(schedule(runtime, FactoryEffect::Rom02Reverb44k, Parameter::ReverbMixBus2, 26, 4096) ==
           EncodeStatus::Encoded);
    assert(runtime.events.size() == 1);
    assert(runtime.events[0].gpr == 0x7a && runtime.events[0].value == 0x370000 &&
           runtime.events[0].frame == 4096);
    assert(schedule(runtime, FactoryEffect::Rom02Reverb44k, Parameter::ReverbMixBus2, 27, 4100) ==
           EncodeStatus::UnverifiedDisplayValue);
    assert(runtime.events.size() == 1); // unsupported values never reach the runtime
    runtime.accept = false;
    assert(schedule(runtime, FactoryEffect::Rom01Hall, Parameter::ReverbMixBus1, 29, 4101) ==
           EncodeStatus::RuntimeRejected);
}
