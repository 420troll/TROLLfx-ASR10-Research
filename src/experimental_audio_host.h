#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace trollfx::audio {

enum class Effect : uint8_t { Hall = 0, Rom02 = 1 };

struct Controls {
    float wet = 0.35f;
    float input_gain = 1.0f;
    float output_gain = 1.0f;
};

// Backend seam for Codex 1's reusable runtime. prepare() is control-thread only;
// process() must preserve state and must not allocate or block.
class IProcessor {
public:
    virtual ~IProcessor() = default;
    virtual void prepare(Effect effect, uint32_t dsp_rate) = 0;
    virtual void process(const float* stereo_input, float* stereo_wet_output,
                         size_t frames) noexcept = 0;
    virtual uint32_t latency_frames() const noexcept = 0;
    virtual size_t memory_bytes() const noexcept = 0;
};

// A deterministic delay/reverb mock. This is infrastructure validation only;
// it does not contain or reproduce either factory effect.
class MockProcessor final : public IProcessor {
public:
    static constexpr uint32_t kDefaultRate = 48000;
    MockProcessor();
    void prepare(Effect effect, uint32_t dsp_rate) override;
    void process(const float* stereo_input, float* stereo_wet_output,
                 size_t frames) noexcept override;
    uint32_t latency_frames() const noexcept override { return 0; }
    size_t memory_bytes() const noexcept override;

private:
    static constexpr size_t kDelayCapacity = 8192;
    std::vector<float> left_, right_;
    size_t position_ = 0;
    uint32_t rate_ = kDefaultRate;
    uint32_t delay_l_ = 1901, delay_r_ = 2309;
    float feedback_ = 0.68f, cross_ = 0.13f;
};

class AudioHost {
public:
    // V0.1 requires direct-rate processing. I/O WAV samples are converted to
    // 48 kHz before callbacks; factory virtual-rate support remains a seam.
    AudioHost(IProcessor& processor, uint32_t host_rate = 48000,
              uint32_t dsp_rate = 48000, uint32_t switch_fade_ms = 5,
              Effect initial_effect = Effect::Hall);

    void set_controls(Controls controls) noexcept;
    void request_effect(Effect effect) noexcept;
    // Call on a control thread between callbacks. Reinitializes the single
    // processor only after the callback has faded to silence.
    void service_control();

    // Interleaved mono/stereo float callback API. Arbitrary frame counts are
    // supported. Null input means silence; output may be mono or stereo.
    void process(const float* input, int input_channels, float* output,
                 int output_channels, size_t frames) noexcept;

    Effect active_effect() const noexcept { return active_effect_.load(std::memory_order_acquire); }
    uint32_t host_rate() const noexcept { return host_rate_; }
    uint32_t dsp_rate() const noexcept { return dsp_rate_; }
    uint32_t latency_frames() const noexcept { return processor_.latency_frames(); }
    size_t memory_bytes() const noexcept { return processor_.memory_bytes(); }
    bool switch_pending() const noexcept { return switch_busy_.load(std::memory_order_acquire); }

private:
    enum class Phase : uint8_t { Running, FadeOut, Muted, FadeIn };
    IProcessor& processor_;
    const uint32_t host_rate_, dsp_rate_, fade_frames_;
    std::atomic<float> wet_{0.35f}, input_gain_{1.0f}, output_gain_{1.0f};
    std::atomic<int> request_{-1};
    std::atomic<bool> needs_prepare_{false}, prepared_{false};
    std::atomic<bool> switch_busy_{false};
    std::atomic<Effect> active_effect_{Effect::Hall};
    Effect target_effect_ = Effect::Hall; // audio-thread owned except while muted
    Phase phase_ = Phase::Running;
    uint32_t phase_frame_ = 0;
    float fade_from_ = 1.0f;
};

float db_to_linear(float db) noexcept;
int16_t float_to_pcm16(float sample) noexcept;

} // namespace trollfx::audio
