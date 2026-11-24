// Evidence-bounded OS 3.53 factory parameter mappings, interface v0.1.
#pragma once

#include <cstdint>

namespace trollfx::es5510::factory_parameters_v01 {

enum class FactoryEffect : std::uint8_t {
    Rom01Hall = 1,
    Rom02Reverb44k = 2,
};

enum class Parameter : std::uint8_t {
    ReverbMixBus1 = 1,
    ReverbMixBus2 = 2,
};

enum class EncodeStatus : std::uint8_t {
    Encoded,
    UnknownEffectOrParameter,
    UnverifiedDisplayValue,
    RuntimeRejected,
};

struct RegisterWrite {
    std::uint8_t gpr = 0;
    std::uint32_t value24 = 0;
};

struct EncodedParameter {
    EncodeStatus status = EncodeStatus::UnknownEffectOrParameter;
    RegisterWrite write{};
};

// v0.1 deliberately accepts only display values observed in reversible
// factory-OS experiments. It does not extrapolate a scale or invent endpoints.
constexpr EncodedParameter encode(FactoryEffect effect, Parameter parameter,
                                  int display_value) noexcept {
    if (parameter == Parameter::ReverbMixBus1 || parameter == Parameter::ReverbMixBus2) {
        const std::uint8_t gpr = parameter == Parameter::ReverbMixBus1 ? 0x7c : 0x7a;
        if (effect == FactoryEffect::Rom01Hall) {
            if (display_value == 28) return {EncodeStatus::Encoded, {gpr, 0x3d0000}};
            if (display_value == 29) return {EncodeStatus::Encoded, {gpr, 0x3f0000}};
            return {EncodeStatus::UnverifiedDisplayValue, {}};
        }
        if (effect == FactoryEffect::Rom02Reverb44k) {
            if (display_value == 25) return {EncodeStatus::Encoded, {gpr, 0x350000}};
            if (display_value == 26) return {EncodeStatus::Encoded, {gpr, 0x370000}};
            return {EncodeStatus::UnverifiedDisplayValue, {}};
        }
    }
    return {EncodeStatus::UnknownEffectOrParameter, {}};
}

// Compatible with FactoryRuntime::setRegister(index, value, absolute_frame).
// Call between processStereo blocks on the runtime's owning audio thread.
// v0.1 performs one exact state write; it does not implement the OS update
// service's repeated writes/intermediate values or claim click-free changes.
template <class Runtime>
EncodeStatus schedule(Runtime& runtime, FactoryEffect effect, Parameter parameter,
                      int display_value, std::uint64_t absolute_dsp_frame) noexcept {
    const auto encoded = encode(effect, parameter, display_value);
    if (encoded.status != EncodeStatus::Encoded) return encoded.status;
    return runtime.setRegister(encoded.write.gpr, encoded.write.value24, absolute_dsp_frame)
        ? EncodeStatus::Encoded : EncodeStatus::RuntimeRejected;
}

} // namespace trollfx::es5510::factory_parameters_v01
