// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "trollfx/es5510_factory_runtime.hpp"
#include "trollfx/es5510_factory_parameter_control_v01.hpp"
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <thread>

// Implemented by the trusted local package importer. Returned objects must
// remain immutable/alive for the backend lifetime. No parsing or trust decision
// is made by this audio adapter.
class IValidatedFactoryPackageProvider {
public:
    virtual ~IValidatedFactoryPackageProvider() = default;
    virtual const trollfx::es5510::ValidatedEffectPackage* package_for_slot(
        trollfx::es5510::EffectSlot slot) const noexcept = 0;
};

enum class ES5510BackendStatus : std::uint8_t {
    NoProvider, Unavailable, Loading, Ready, Failed
};

// Owns two native runtime instances. The worker loads only the inactive one;
// the process callback swaps at silence after the approved 5 ms fade-out.
class ES5510DSPBackend final {
public:
    explicit ES5510DSPBackend(const IValidatedFactoryPackageProvider* provider);
    ~ES5510DSPBackend();
    ES5510DSPBackend(const ES5510DSPBackend&) = delete;
    ES5510DSPBackend& operator=(const ES5510DSPBackend&) = delete;

    bool prepare(std::uint8_t slot, double host_rate_hz); // control thread only
    void request_effect(std::uint8_t slot) noexcept;
    void set_mix(float wet, float input_gain_db, float output_gain_db,
                 bool bypass) noexcept;
    trollfx::es5510::factory_parameters_v01::EncodeStatus set_verified_bus(
        trollfx::es5510::factory_parameters_v01::FactoryEffect effect,
        trollfx::es5510::factory_parameters_v01::Parameter parameter,
        int display_value) noexcept;
    // Schedules one verified discrete point (or its complete ordered GPR
    // write group) for the currently active factory package.
    bool set_verified_parameter(std::uint8_t slot, const char* parameter_id,
                                std::int32_t display_value) noexcept;
    void process(const float* const* inputs, float* const* outputs,
                 std::size_t frames) noexcept;
    ES5510BackendStatus status() const noexcept { return status_.load(std::memory_order_acquire); }
    std::uint8_t active_slot() const noexcept { return active_slot_.load(std::memory_order_acquire); }
    std::uint32_t latency_frames() const noexcept { return latency_frames_; }
    std::uint64_t dsp_frames() const noexcept;

private:
    void worker_loop() noexcept;
    static float db_gain(float db) noexcept;
    std::atomic<const IValidatedFactoryPackageProvider*> provider_;
    std::array<trollfx::es5510::FactoryRuntime, 2> runtime_;
    double host_rate_ = 48000.0;
    std::uint32_t latency_frames_ = 0;
    std::array<std::array<float, 64>, 2> dry_delay_{};
    std::size_t dry_pos_ = 0;
    std::uint32_t fade_frames_ = 240, fade_pos_ = 0;
    enum class Phase : std::uint8_t { Silent, Running, FadeOut, Waiting, FadeIn };
    Phase phase_ = Phase::Silent; // audio thread only
    float fade_level_ = 0.0f;
    std::atomic<float> wet_{1.0f}, input_gain_db_{0.0f}, output_gain_db_{0.0f};
    std::atomic<bool> bypass_{false};
    std::atomic<std::uint8_t> requested_slot_{0}, active_slot_{0};
    std::atomic<std::uint8_t> load_slot_{0};
    std::atomic<unsigned> active_index_{0}, ready_index_{2};
    std::atomic<std::uint64_t> request_generation_{0}, ready_generation_{0};
    std::atomic<bool> stop_worker_{false};
    std::atomic<ES5510BackendStatus> status_{ES5510BackendStatus::NoProvider};
    std::thread worker_;
    std::uint64_t observed_generation_ = 0; // audio thread only
};

// The host/importer calls this before instantiating the plugin. A null provider
// keeps all effects unavailable and the plugin outputs silence (never fake DSP).
void TROLLfx_InstallValidatedFactoryPackageProvider(
    const IValidatedFactoryPackageProvider* provider) noexcept;
const IValidatedFactoryPackageProvider* TROLLfx_GetValidatedFactoryPackageProvider() noexcept;
