#include "experimental_audio_host.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace trollfx::audio {

namespace {
float finite_or_zero(float x) noexcept { return std::isfinite(x) ? x : 0.0f; }
float clamp_gain(float x) noexcept { return std::clamp(finite_or_zero(x), 0.0f, 16.0f); }
}

MockProcessor::MockProcessor() : left_(kDelayCapacity, 0.0f), right_(kDelayCapacity, 0.0f) {
    prepare(Effect::Hall, kDefaultRate);
}

void MockProcessor::prepare(Effect effect, uint32_t dsp_rate) {
    if (dsp_rate == 0) throw std::invalid_argument("DSP rate must be positive");
    rate_ = dsp_rate;
    std::fill(left_.begin(), left_.end(), 0.0f);
    std::fill(right_.begin(), right_.end(), 0.0f);
    position_ = 0;
    if (effect == Effect::Hall) {
        delay_l_ = 1901; delay_r_ = 2309; feedback_ = 0.68f; cross_ = 0.13f;
    } else {
        delay_l_ = 1379; delay_r_ = 1667; feedback_ = 0.57f; cross_ = 0.21f;
    }
    // Keep configured values within the fixed ring regardless of future rate use.
    delay_l_ = std::min<uint32_t>(delay_l_, static_cast<uint32_t>(kDelayCapacity - 1));
    delay_r_ = std::min<uint32_t>(delay_r_, static_cast<uint32_t>(kDelayCapacity - 1));
}

void MockProcessor::process(const float* input, float* wet, size_t frames) noexcept {
    if (!input || !wet) return;
    for (size_t i = 0; i < frames; ++i) {
        const float in_l = finite_or_zero(input[2 * i]);
        const float in_r = finite_or_zero(input[2 * i + 1]);
        const size_t read_l = (position_ + kDelayCapacity - delay_l_) % kDelayCapacity;
        const size_t read_r = (position_ + kDelayCapacity - delay_r_) % kDelayCapacity;
        const float tap_l = left_[read_l];
        const float tap_r = right_[read_r];
        wet[2 * i] = in_l * 0.18f + tap_l * 0.72f + tap_r * 0.10f;
        wet[2 * i + 1] = in_r * 0.18f + tap_r * 0.72f + tap_l * 0.10f;
        left_[position_] = in_l + tap_l * feedback_ + tap_r * cross_;
        right_[position_] = in_r + tap_r * feedback_ + tap_l * cross_;
        position_ = (position_ + 1) % kDelayCapacity;
    }
}

size_t MockProcessor::memory_bytes() const noexcept {
    return (left_.capacity() + right_.capacity()) * sizeof(float);
}

AudioHost::AudioHost(IProcessor& processor, uint32_t host_rate,
                     uint32_t dsp_rate, uint32_t switch_fade_ms, Effect initial_effect)
    : processor_(processor), host_rate_(host_rate), dsp_rate_(dsp_rate),
      fade_frames_(std::max<uint32_t>(2, (host_rate * switch_fade_ms + 999) / 1000)) {
    if (!host_rate_ || !dsp_rate_) throw std::invalid_argument("host and DSP rates must be positive");
    if (host_rate_ != dsp_rate_)
        throw std::invalid_argument("V0.1 direct mode requires matching host and DSP rates");
    processor_.prepare(initial_effect, dsp_rate_);
    active_effect_.store(initial_effect, std::memory_order_relaxed);
    target_effect_ = initial_effect;
}

void AudioHost::set_controls(Controls c) noexcept {
    wet_.store(std::clamp(finite_or_zero(c.wet), 0.0f, 1.0f), std::memory_order_relaxed);
    input_gain_.store(clamp_gain(c.input_gain), std::memory_order_relaxed);
    output_gain_.store(clamp_gain(c.output_gain), std::memory_order_relaxed);
}

void AudioHost::request_effect(Effect effect) noexcept {
    if (effect == active_effect_.load(std::memory_order_acquire)) return;
    bool expected = false;
    if (!switch_busy_.compare_exchange_strong(expected, true, std::memory_order_acq_rel)) return;
    request_.store(static_cast<int>(effect), std::memory_order_release);
}

void AudioHost::service_control() {
    if (!needs_prepare_.exchange(false, std::memory_order_acq_rel)) return;
    // The callback has returned in Muted phase and does not touch processor_;
    // memory clearing and runtime initialization therefore stay off audio thread.
    processor_.prepare(target_effect_, dsp_rate_);
    active_effect_.store(target_effect_, std::memory_order_release);
    prepared_.store(true, std::memory_order_release);
}

void AudioHost::process(const float* input, int input_channels, float* output,
                        int output_channels, size_t frames) noexcept {
    if (!output) return;
    if (output_channels < 1) return;
    if (output_channels > 2 || input_channels < 0 || input_channels > 2) {
        std::fill(output, output + frames * static_cast<size_t>(output_channels), 0.0f);
        return;
    }

    const int requested = request_.exchange(-1, std::memory_order_acq_rel);
    if (requested >= 0 && phase_ == Phase::Running) {
        target_effect_ = static_cast<Effect>(requested);
        phase_ = Phase::FadeOut;
        phase_frame_ = 0;
    }
    if (phase_ == Phase::Muted && prepared_.exchange(false, std::memory_order_acq_rel)) {
        phase_ = Phase::FadeIn;
        phase_frame_ = 0;
    }

    const float wet_mix = wet_.load(std::memory_order_relaxed);
    const float in_gain = input_gain_.load(std::memory_order_relaxed);
    const float out_gain = output_gain_.load(std::memory_order_relaxed);
    constexpr size_t kChunkFrames = 512;
    float in_scratch[kChunkFrames * 2];
    float wet_scratch[kChunkFrames * 2];
    for (size_t offset = 0; offset < frames; offset += kChunkFrames) {
        const size_t n = std::min(kChunkFrames, frames - offset);
        for (size_t i = 0; i < n; ++i) {
            float l = 0.0f, r = 0.0f;
            if (input && input_channels == 1) l = r = finite_or_zero(input[offset + i]);
            else if (input && input_channels == 2) {
                l = finite_or_zero(input[2 * (offset + i)]);
                r = finite_or_zero(input[2 * (offset + i) + 1]);
            }
            in_scratch[2 * i] = l * in_gain;
            in_scratch[2 * i + 1] = r * in_gain;
        }
        processor_.process(in_scratch, wet_scratch, n);
        for (size_t i = 0; i < n; ++i) {
            float transition = 1.0f;
            if (phase_ == Phase::FadeOut) {
                transition = phase_frame_ + 1 >= fade_frames_ ? 0.0f :
                    1.0f - static_cast<float>(phase_frame_) / static_cast<float>(fade_frames_ - 1);
            } else if (phase_ == Phase::FadeIn) {
                transition = static_cast<float>(phase_frame_) / static_cast<float>(fade_frames_ - 1);
            } else if (phase_ == Phase::Muted) {
                transition = 0.0f;
            }

            const size_t frame = offset + i;
            const float current_dry_l = in_scratch[2 * i], current_dry_r = in_scratch[2 * i + 1];
            const uint32_t requested_latency = processor_.latency_frames();
            const size_t dry_latency = std::min<size_t>(requested_latency, kDryDelayCapacity - 1);
            dry_history_left_[dry_history_pos_] = current_dry_l;
            dry_history_right_[dry_history_pos_] = current_dry_r;
            const size_t dry_read = (dry_history_pos_ + kDryDelayCapacity - dry_latency) % kDryDelayCapacity;
            const float dry_l = dry_latency ? dry_history_left_[dry_read] : current_dry_l;
            const float dry_r = dry_latency ? dry_history_right_[dry_read] : current_dry_r;
            dry_history_pos_ = (dry_history_pos_ + 1) % kDryDelayCapacity;
            const float wet_l = finite_or_zero(wet_scratch[2 * i]);
            const float wet_r = finite_or_zero(wet_scratch[2 * i + 1]);
            float left = ((1.0f - wet_mix) * dry_l + wet_mix * wet_l) * out_gain * transition;
            float right = ((1.0f - wet_mix) * dry_r + wet_mix * wet_r) * out_gain * transition;
            left = std::clamp(finite_or_zero(left), -1.0f, 1.0f);
            right = std::clamp(finite_or_zero(right), -1.0f, 1.0f);
            if (output_channels == 1) output[frame] = 0.5f * (left + right);
            else { output[2 * frame] = left; output[2 * frame + 1] = right; }

            if (phase_ == Phase::FadeOut || phase_ == Phase::FadeIn) {
                if (++phase_frame_ >= fade_frames_) {
                    phase_frame_ = 0;
                    if (phase_ == Phase::FadeOut) {
                        phase_ = Phase::Muted;
                        needs_prepare_.store(true, std::memory_order_release);
                    } else {
                        phase_ = Phase::Running;
                        switch_busy_.store(false, std::memory_order_release);
                    }
                }
            }
        }
    }
}

float db_to_linear(float db) noexcept {
    if (!std::isfinite(db)) return 1.0f;
    return std::clamp(std::pow(10.0f, db / 20.0f), 0.0f, 16.0f);
}

int16_t float_to_pcm16(float sample) noexcept {
    sample = std::clamp(finite_or_zero(sample), -1.0f, 1.0f);
    const float scaled = sample < 0.0f ? sample * 32768.0f : sample * 32767.0f;
    return static_cast<int16_t>(std::lrint(scaled));
}

} // namespace trollfx::audio
