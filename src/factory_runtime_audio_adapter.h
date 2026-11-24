#pragma once
#include "experimental_audio_host.h"
#include "trollfx/es5510_factory_runtime.hpp"
#include "trollfx/es5510_factory_parameter_control_v01.hpp"
#include <array>
#include <string>
#include <vector>

namespace trollfx::audio {

struct PrivateFactoryPackagePaths {
    std::string manifest;
    std::string checkpoint;
    std::string two_boot_reference_root;
    std::string post_run_events;
};

// Validates both private packages on construction (control/main thread), then
// adapts the validated native runtime to the WAV host's wet-processor seam.
class FactoryRuntimeProcessor final : public IProcessor {
public:
    FactoryRuntimeProcessor(PrivateFactoryPackagePaths hall,
                            PrivateFactoryPackagePaths rom02,
                            std::string validator_script);
    void prepare(Effect effect, uint32_t dsp_rate) override;
    void process(const float* stereo_input, float* stereo_wet_output,
                 size_t frames) noexcept override;
    uint32_t latency_frames() const noexcept override;
    size_t memory_bytes() const noexcept override;

    trollfx::es5510::factory_parameters_v01::EncodeStatus set_bus_parameter(
        Effect effect, trollfx::es5510::factory_parameters_v01::Parameter parameter, int display_value);
    const char* status_message() const noexcept;

private:
    static trollfx::es5510::EffectPackage validate_and_make(
        Effect effect, const PrivateFactoryPackagePaths& paths,
        const std::string& validator_script);
    std::array<trollfx::es5510::EffectPackage,2> packages_;
    struct FirmwareWrite { std::uint64_t frame; std::uint8_t index; std::uint32_t value; };
    std::array<std::vector<FirmwareWrite>,2> firmware_writes_;
    trollfx::es5510::FactoryRuntime runtime_;
    Effect active_effect_ = Effect::Hall;
    bool prepared_ = false;
    bool process_error_ = false;
};

// Registry-backed adapter for slots 1..50. The host Effect value is the
// zero-based selection index (0..49); it reuses AudioHost's muted prepare path.
class RegistryFactoryRuntimeProcessor final : public IProcessor {
public:
    explicit RegistryFactoryRuntimeProcessor(const trollfx::es5510::EffectRegistry& registry)
        : registry_(registry) {}
    void prepare(Effect effect, uint32_t dsp_rate) override;
    void process(const float*, float*, size_t) noexcept override;
    uint32_t latency_frames() const noexcept override;
    size_t memory_bytes() const noexcept override;
private:
    const trollfx::es5510::EffectRegistry& registry_;
    trollfx::es5510::FactoryRuntime runtime_;
    bool prepared_ = false;
};

} // namespace trollfx::audio
