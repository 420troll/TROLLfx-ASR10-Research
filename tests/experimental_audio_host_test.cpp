#include "experimental_audio_host.h"

#include <atomic>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <new>
#include <stdexcept>
#include <vector>

namespace {
std::atomic<bool> count_allocations{false};
std::atomic<unsigned> allocation_count{0};
}

void* operator new(std::size_t n) {
    if (count_allocations.load(std::memory_order_relaxed)) allocation_count.fetch_add(1, std::memory_order_relaxed);
    if (void* p = std::malloc(n)) return p;
    throw std::bad_alloc();
}
void* operator new[](std::size_t n) {
    if (count_allocations.load(std::memory_order_relaxed)) allocation_count.fetch_add(1, std::memory_order_relaxed);
    if (void* p = std::malloc(n)) return p;
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }

class PassThrough final : public trollfx::audio::IProcessor {
public:
    void prepare(trollfx::audio::Effect e, uint32_t rate) override { effect = e; sample_rate = rate; ++prepares; }
    void process(const float* in, float* out, size_t n) noexcept override {
        for (size_t i = 0; i < n * 2; ++i) out[i] = in[i] * (effect == trollfx::audio::Effect::Hall ? 0.5f : 0.75f);
    }
    uint32_t latency_frames() const noexcept override { return latency; }
    size_t memory_bytes() const noexcept override { return 0; }
    trollfx::audio::Effect effect = trollfx::audio::Effect::Hall;
    uint32_t sample_rate = 0, prepares = 0, latency = 0;
};

using namespace trollfx::audio;

int main() {
    assert(float_to_pcm16(-2.0f) == -32768);
    assert(float_to_pcm16(2.0f) == 32767);
    assert(float_to_pcm16(std::numeric_limits<float>::quiet_NaN()) == 0);
    assert(std::abs(db_to_linear(0.0f) - 1.0f) < 1e-6f);

    // Silence remains silent through the stateful mock over irregular blocks.
    MockProcessor mock;
    AudioHost silent_host(mock);
    float zeros[2 * 600]{};
    float silent_out[2 * 600];
    for (size_t n : {size_t(1), size_t(511), size_t(512), size_t(513), size_t(600)}) {
        silent_host.process(zeros, 2, silent_out, 2, n);
        for (size_t i = 0; i < 2 * n; ++i) assert(silent_out[i] == 0.0f);
    }

    // Mono input duplicates to stereo; stereo dry blend preserves L/R routing.
    PassThrough pass;
    AudioHost dry(pass);
    dry.set_controls({0.0f, 1.0f, 1.0f});
    float mono[4] = {0.25f, -0.5f};
    float stereo[4]{};
    dry.process(mono, 1, stereo, 2, 2);
    assert(stereo[0] == 0.25f && stereo[1] == 0.25f);
    assert(stereo[2] == -0.5f && stereo[3] == -0.5f);
    float mono_out[2]{};
    dry.process(stereo, 2, mono_out, 1, 2);
    assert(std::abs(mono_out[0] - 0.25f) < 1e-6f && std::abs(mono_out[1] + 0.5f) < 1e-6f);

    // The host delays the dry path to match a processor's reported algorithmic latency.
    PassThrough delayed_pass; delayed_pass.latency=2;
    AudioHost delayed_host(delayed_pass); delayed_host.set_controls({0.0f,1.0f,1.0f});
    float delayed_input[8]={0.1f,0.2f,0.3f,0.4f,0.5f,0.6f,0.7f,0.8f};
    float delayed_output[8]{};
    delayed_host.process(delayed_input,2,delayed_output,2,4);
    assert(delayed_output[0]==0.0f && delayed_output[1]==0.0f);
    assert(std::abs(delayed_output[4]-0.1f)<1e-6f && std::abs(delayed_output[5]-0.2f)<1e-6f);

    // The callback path handles arbitrary buffer sizes without heap activity.
    std::vector<float> callback_in(2 * 2049, 0.1f), callback_out(2 * 2049);
    allocation_count.store(0);
    count_allocations.store(true);
    dry.process(callback_in.data(), 2, callback_out.data(), 2, 2049);
    count_allocations.store(false);
    assert(allocation_count.load() == 0);

    // Switching fades down, reinitializes once on control thread, then fades up.
    PassThrough switching_processor;
    AudioHost switching(switching_processor, 48000, 48000, 5);
    std::vector<float> switch_in(2 * 512, 1.0f), switch_out(2 * 512);
    switching.request_effect(Effect::Rom02);
    switching.process(switch_in.data(), 2, switch_out.data(), 2, 512);
    assert(switching.switch_pending());
    assert(switch_out[2 * 239] == 0.0f); // fade ends at silence; no click-free claim
    switching.service_control();
    assert(switching.active_effect() == Effect::Rom02 && switching_processor.prepares == 2);
    switching.process(switch_in.data(), 2, switch_out.data(), 2, 512);
    assert(!switching.switch_pending());
    assert(switch_out[0] == 0.0f && switch_out[2 * 239] > 0.0f);

    switching.request_effect(Effect::Hall);
    switching.process(switch_in.data(), 2, switch_out.data(), 2, 512);
    switching.service_control();
    switching.process(switch_in.data(), 2, switch_out.data(), 2, 512);
    assert(switching.active_effect() == Effect::Hall && !switching.switch_pending());

    bool rejected_rate = false;
    try { AudioHost invalid(pass, 44100, 48000); }
    catch (const std::invalid_argument&) { rejected_rate = true; }
    assert(rejected_rate);
    std::cout << "experimental audio host callback tests passed\n";
}
