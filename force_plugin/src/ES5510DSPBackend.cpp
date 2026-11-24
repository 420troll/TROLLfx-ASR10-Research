// SPDX-License-Identifier: GPL-3.0-only
#include "ES5510DSPBackend.h"
#include <algorithm>
#include <chrono>
#include <cmath>

namespace {
std::atomic<const IValidatedFactoryPackageProvider*> g_provider{nullptr};
constexpr std::size_t kChunk = 256;
}

void TROLLfx_InstallValidatedFactoryPackageProvider(
    const IValidatedFactoryPackageProvider* provider) noexcept {
    g_provider.store(provider, std::memory_order_release);
}
const IValidatedFactoryPackageProvider* TROLLfx_GetValidatedFactoryPackageProvider() noexcept {
    return g_provider.load(std::memory_order_acquire);
}

ES5510DSPBackend::ES5510DSPBackend(const IValidatedFactoryPackageProvider* provider)
    : provider_(provider), worker_(&ES5510DSPBackend::worker_loop, this) {
    if (!provider_) status_.store(ES5510BackendStatus::NoProvider, std::memory_order_release);
}

ES5510DSPBackend::~ES5510DSPBackend() {
    stop_worker_.store(true, std::memory_order_release);
    if (worker_.joinable()) worker_.join();
}

float ES5510DSPBackend::db_gain(float db) noexcept {
    if (!std::isfinite(db)) return 1.0f;
    return std::pow(10.0f, std::clamp(db, -48.0f, 24.0f) / 20.0f);
}

bool ES5510DSPBackend::prepare(std::uint8_t slot, double host_rate) {
    auto* provider=provider_.load(std::memory_order_acquire);
    if (!provider) {
        provider=TROLLfx_GetValidatedFactoryPackageProvider();
        provider_.store(provider,std::memory_order_release);
    }
    if (!provider || slot < 1 || slot > 50 || !std::isfinite(host_rate) || host_rate < 8000.0 || host_rate > 192000.0)
        return false;
    const auto* package = provider->package_for_slot(slot);
    if (!package) { status_.store(ES5510BackendStatus::Unavailable, std::memory_order_release); return false; }
    if (!runtime_[0].loadEffect(*package, trollfx::es5510::RateMode::Experimental48000)) {
        status_.store(ES5510BackendStatus::Failed, std::memory_order_release); return false;
    }
    host_rate_ = host_rate;
    latency_frames_ = static_cast<std::uint32_t>(std::ceil(host_rate_ / 48000.0) + 1.0);
    if (latency_frames_ >= dry_delay_[0].size()) return false;
    fade_frames_ = std::max<std::uint32_t>(1, static_cast<std::uint32_t>(std::ceil(host_rate_ * 0.005)));
    requested_slot_.store(slot, std::memory_order_release);
    active_slot_.store(slot, std::memory_order_release);
    active_index_.store(0, std::memory_order_release);
    for (auto& ch : dry_delay_) ch.fill(0.0f);
    dry_pos_ = 0; phase_ = Phase::Running; fade_level_ = 1.0f;
    status_.store(ES5510BackendStatus::Ready, std::memory_order_release);
    return true;
}

void ES5510DSPBackend::request_effect(std::uint8_t slot) noexcept {
    requested_slot_.store(slot, std::memory_order_release);
}

void ES5510DSPBackend::set_mix(float wet, float in_db, float out_db, bool bypass) noexcept {
    wet_.store(std::clamp(std::isfinite(wet) ? wet : 0.0f, 0.0f, 1.0f), std::memory_order_relaxed);
    input_gain_db_.store(std::clamp(std::isfinite(in_db) ? in_db : 0.0f, -48.0f, 24.0f), std::memory_order_relaxed);
    output_gain_db_.store(std::clamp(std::isfinite(out_db) ? out_db : 0.0f, -48.0f, 24.0f), std::memory_order_relaxed);
    bypass_.store(bypass, std::memory_order_relaxed);
}

trollfx::es5510::factory_parameters_v01::EncodeStatus
ES5510DSPBackend::set_verified_bus(
    trollfx::es5510::factory_parameters_v01::FactoryEffect effect,
    trollfx::es5510::factory_parameters_v01::Parameter parameter,
    int display_value) noexcept {
    using namespace trollfx::es5510::factory_parameters_v01;
    const auto expected_slot = static_cast<std::uint8_t>(effect);
    if (active_slot_.load(std::memory_order_acquire) != expected_slot ||
        status_.load(std::memory_order_acquire) != ES5510BackendStatus::Ready)
        return EncodeStatus::RuntimeRejected;
    auto& runtime = runtime_[active_index_.load(std::memory_order_acquire)];
    const auto frame = runtime.getStatus().processed_dsp_frames;
    return schedule(runtime, effect, parameter, display_value, frame);
}

bool ES5510DSPBackend::set_verified_parameter(
    std::uint8_t slot, const char* parameter_id, std::int32_t display_value) noexcept {
    if (!parameter_id || active_slot_.load(std::memory_order_acquire) != slot ||
        status_.load(std::memory_order_acquire) != ES5510BackendStatus::Ready)
        return false;
    const auto* provider = provider_.load(std::memory_order_acquire);
    const auto* package = provider ? provider->package_for_slot(slot) : nullptr;
    if (!package) return false;
    const auto& descriptor = package->descriptor;
    const auto found = std::find_if(descriptor.parameters.begin(), descriptor.parameters.end(),
        [parameter_id](const auto& parameter) { return parameter.id == parameter_id; });
    if (found == descriptor.parameters.end()) return false;
    auto& runtime = runtime_[active_index_.load(std::memory_order_acquire)];
    const auto frame = runtime.getStatus().processed_dsp_frames;
    return runtime.setParameter(descriptor, found->id, display_value, frame);
}

void ES5510DSPBackend::worker_loop() noexcept {
    while (!stop_worker_.load(std::memory_order_acquire)) {
        const auto generation=request_generation_.load(std::memory_order_acquire);
        if (generation==0 || generation==ready_generation_.load(std::memory_order_acquire)) {
            std::this_thread::sleep_for(std::chrono::milliseconds(1)); continue;
        }
        const auto slot=load_slot_.load(std::memory_order_acquire);
        const unsigned inactive=1u-active_index_.load(std::memory_order_acquire);
        auto* provider=provider_.load(std::memory_order_acquire);
        const auto* package=provider ? provider->package_for_slot(slot) : nullptr;
        status_.store(package ? ES5510BackendStatus::Loading : ES5510BackendStatus::Unavailable,
                      std::memory_order_release);
        bool ok=package && runtime_[inactive].loadEffect(*package,
            trollfx::es5510::RateMode::Experimental48000);
        if (generation==request_generation_.load(std::memory_order_acquire)) {
            if (ok) ready_index_.store(inactive, std::memory_order_release);
            status_.store(ok ? ES5510BackendStatus::Ready : ES5510BackendStatus::Failed,
                          std::memory_order_release);
            ready_generation_.store(generation, std::memory_order_release);
        }
    }
}

void ES5510DSPBackend::process(const float* const* inputs, float* const* outputs,
                               std::size_t frames) noexcept {
    if (!outputs || !outputs[0] || !outputs[1]) return;
    const float in_gain=db_gain(input_gain_db_.load(std::memory_order_relaxed));
    const float out_gain=db_gain(output_gain_db_.load(std::memory_order_relaxed));
    const float wet=wet_.load(std::memory_order_relaxed);
    const bool bypass=bypass_.load(std::memory_order_relaxed);
    const auto wanted=requested_slot_.load(std::memory_order_acquire);
    if (phase_==Phase::Running && wanted!=active_slot_.load(std::memory_order_relaxed)) {
        phase_=Phase::FadeOut; fade_pos_=0;
    }
    if (phase_==Phase::Silent && wanted>=1 && wanted<=50 &&
        provider_.load(std::memory_order_acquire)) {
        load_slot_.store(wanted,std::memory_order_release);
        observed_generation_=request_generation_.fetch_add(1,std::memory_order_acq_rel)+1;
        phase_=Phase::Waiting;
    }
    for (std::size_t base=0;base<frames;base+=kChunk) {
        if (phase_==Phase::Waiting) {
            const auto desired=requested_slot_.load(std::memory_order_acquire);
            if (desired!=load_slot_.load(std::memory_order_relaxed)) {
                load_slot_.store(desired,std::memory_order_release);
                observed_generation_=request_generation_.fetch_add(1,std::memory_order_acq_rel)+1;
                ready_index_.store(2,std::memory_order_release);
            }
            const auto gen=ready_generation_.load(std::memory_order_acquire);
            if (gen==observed_generation_ && ready_index_.load(std::memory_order_acquire)<2) {
                active_index_.store(ready_index_.load(std::memory_order_relaxed),std::memory_order_release);
                active_slot_.store(requested_slot_.load(std::memory_order_acquire),std::memory_order_release);
                ready_index_.store(2,std::memory_order_release); fade_pos_=0; phase_=Phase::FadeIn;
                for(auto& channel:dry_delay_) channel.fill(0.0f);
                dry_pos_=0;
            }
        }
        const std::size_t n=std::min(kChunk,frames-base);
        std::array<float,kChunk*2> input{}, effected{};
        for (std::size_t i=0;i<n;++i) {
            input[2*i]=(inputs&&inputs[0]?inputs[0][base+i]:0.0f)*in_gain;
            input[2*i+1]=(inputs&&inputs[1]?inputs[1][base+i]:0.0f)*in_gain;
        }
        const unsigned index=active_index_.load(std::memory_order_acquire);
        const bool has_active=phase_!=Phase::Silent && status_.load(std::memory_order_acquire)!=ES5510BackendStatus::NoProvider &&
                              status_.load(std::memory_order_relaxed)!=ES5510BackendStatus::Unavailable &&
                              status_.load(std::memory_order_relaxed)!=ES5510BackendStatus::Failed;
        if (has_active) runtime_[index].processStereo(input.data(),effected.data(),n,host_rate_);
        for (std::size_t i=0;i<n;++i) {
            const std::size_t read_pos=(dry_pos_+dry_delay_[0].size()-
                (latency_frames_%dry_delay_[0].size()))%dry_delay_[0].size();
            const float dry_l=latency_frames_ ? dry_delay_[0][read_pos] : input[2*i];
            const float dry_r=latency_frames_ ? dry_delay_[1][read_pos] : input[2*i+1];
            dry_delay_[0][dry_pos_]=input[2*i]; dry_delay_[1][dry_pos_]=input[2*i+1];
            dry_pos_=(dry_pos_+1)%dry_delay_[0].size();
            float level=fade_level_;
            if (phase_==Phase::FadeOut) {
                level=1.0f-static_cast<float>(++fade_pos_)/fade_frames_;
                if (fade_pos_>=fade_frames_) {
                    level=0.0f; fade_level_=0.0f; phase_=Phase::Waiting;
                    const auto next=requested_slot_.load(std::memory_order_acquire);
                    if (next>=1 && next<=50 && provider_.load(std::memory_order_acquire)) {
                        load_slot_.store(next,std::memory_order_release);
                        observed_generation_=request_generation_.fetch_add(1,std::memory_order_acq_rel)+1;
                        requested_slot_.store(next,std::memory_order_release);
                    } else status_.store(ES5510BackendStatus::Unavailable,std::memory_order_release);
                }
            } else if (phase_==Phase::FadeIn) {
                level=static_cast<float>(++fade_pos_)/fade_frames_;
                if (fade_pos_>=fade_frames_) { level=1.0f; phase_=Phase::Running; }
                fade_level_=level;
            }
            const float wet_l=effected[2*i], wet_r=effected[2*i+1];
            const float mix_wet=bypass?0.0f:wet;
            const float mix_dry=bypass?1.0f:1.0f-wet;
            outputs[0][base+i]=has_active ? ((dry_l*mix_dry+wet_l*mix_wet)*level)*out_gain : 0.0f;
            outputs[1][base+i]=has_active ? ((dry_r*mix_dry+wet_r*mix_wet)*level)*out_gain : 0.0f;
        }
    }
}

std::uint64_t ES5510DSPBackend::dsp_frames() const noexcept {
    return runtime_[active_index_.load(std::memory_order_acquire)].getStatus().processed_dsp_frames;
}
