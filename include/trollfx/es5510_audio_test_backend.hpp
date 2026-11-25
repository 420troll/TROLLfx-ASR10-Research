// Offline and streaming test interface over the native ES5510 FactoryRuntime.
#pragma once

#include "trollfx/es5510_factory_runtime.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace trollfx::es5510::audio_test {

struct ParameterChange {
    std::uint64_t dsp_frame = 0;
    std::string parameter_id;
    std::int32_t display_value = 0;
};

struct RegisterWriteRecord {
    std::uint64_t dsp_frame = 0;
    std::uint16_t order_in_group = 0;
    std::string parameter_id;
    std::int32_t display_value = 0;
    std::uint8_t gpr = 0;
    std::uint32_t value24 = 0;
};

struct AudioMetrics {
    std::uint64_t frames = 0;
    std::uint64_t finite_samples = 0;
    double rms_left = 0.0;
    double rms_right = 0.0;
    float peak_left = 0.0f;
    float peak_right = 0.0f;
};

struct DifferenceMetrics {
    std::uint64_t finite_samples = 0;
    double difference_rms_left = 0.0;
    double difference_rms_right = 0.0;
    float difference_peak = 0.0f;
};

struct RenderOptions {
    std::size_t block_frames = 256;
    std::size_t tail_frames = 0;
    RateMode rate_mode = RateMode::Experimental48000;
    double host_rate_hz = 48000.0;
};

struct RenderReport {
    EffectSlot slot = 0;
    std::uint64_t dsp_frames = 0;
    std::uint64_t writes_applied = 0;
    std::uint32_t latency_frames = 0;
    AudioMetrics input;
    AudioMetrics output;
    std::vector<RegisterWriteRecord> parameter_writes;
};

struct ABReport {
    AudioMetrics bypass;
    AudioMetrics processed;
    DifferenceMetrics difference;
    RenderReport render;
};

// Streaming bridge for Codex 2's host. Registry/package validation and effect
// loading happen on the control thread. process() preserves DSP/DRAM state and
// delegates to FactoryRuntime::processStereo(). Parameter calls must occur
// between process blocks. The write log records the validated mapping's exact
// scheduled GPR writes; it is not a probe of internal DSP writes.
class FactoryAudioTestBackend final {
public:
    explicit FactoryAudioTestBackend(const EffectRegistry& registry) noexcept;
    bool selectEffect(EffectSlot slot, RateMode mode = RateMode::Experimental48000);
    bool reset();
    bool setParameter(const std::string& parameter_id, std::int32_t display_value,
                      std::uint64_t dsp_frame);
    bool process(const float* input_interleaved, float* output_interleaved,
                 std::size_t frames, double host_rate_hz = 48000.0) noexcept;
    RuntimeStatus status() const noexcept;
    EffectSlot activeSlot() const noexcept { return active_slot_; }
    const std::vector<RegisterWriteRecord>& parameterWriteLog() const noexcept { return writes_; }
    void clearParameterWriteLog() noexcept { writes_.clear(); }
    std::size_t memoryBytes() const noexcept;

private:
    const EffectRegistry& registry_;
    const ValidatedEffectPackage* package_ = nullptr;
    FactoryRuntime runtime_;
    EffectSlot active_slot_ = 0;
    std::vector<RegisterWriteRecord> writes_;
};

// Reusable offline WAV layer. WAV I/O and resampling happen outside DSP
// processing; each render starts from the package's validated checkpoint.
class WavAudioTestRunner final {
public:
    explicit WavAudioTestRunner(const EffectRegistry& registry) noexcept;

    bool render(const std::string& input_wav, const std::string& output_wav,
                EffectSlot slot, const std::vector<ParameterChange>& events,
                const RenderOptions& options, RenderReport& report,
                std::string& error) const;

    // Render effect output and a latency-aligned dry bypass from identical input.
    bool renderWetDryAB(const std::string& input_wav, const std::string& processed_wav,
                        const std::string& bypass_wav, EffectSlot slot,
                        const std::vector<ParameterChange>& events,
                        const RenderOptions& options, ABReport& report,
                        std::string& error) const;

    // Render two independent checkpoint-identical runs and compare their output.
    bool renderParameterAB(const std::string& input_wav, const std::string& baseline_wav,
                           const std::string& changed_wav, EffectSlot slot,
                           const std::vector<ParameterChange>& baseline_events,
                           const std::vector<ParameterChange>& changed_events,
                           const RenderOptions& options, DifferenceMetrics& difference,
                           RenderReport& baseline_report, RenderReport& changed_report,
                           std::string& error) const;

private:
    const EffectRegistry& registry_;
};

AudioMetrics measureAudio(const std::vector<float>& interleaved_stereo) noexcept;
DifferenceMetrics measureDifference(const std::vector<float>& a,
                                    const std::vector<float>& b) noexcept;

} // namespace trollfx::es5510::audio_test
