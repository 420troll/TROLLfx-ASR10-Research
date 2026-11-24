#include "experimental_audio_host.h"
#include "wav_io.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using trollfx::audio::AudioHost;
using trollfx::audio::Controls;
using trollfx::audio::Effect;
using trollfx::audio::MockProcessor;
using trollfx::audio::StereoFrame;
using trollfx::audio::WavData;

namespace {
struct Switch { size_t frame; Effect effect; };
Effect effect_from(const std::string& value) {
    if (value == "hall") return Effect::Hall;
    if (value == "rom02") return Effect::Rom02;
    throw std::invalid_argument("effect must be hall or rom02");
}
const char* effect_name(Effect e) { return e == Effect::Hall ? "hall" : "rom02"; }
double number(const std::string& text, const char* what) {
    size_t used = 0; double x = std::stod(text, &used);
    if (used != text.size() || !std::isfinite(x)) throw std::invalid_argument(std::string("invalid ") + what);
    return x;
}
Switch parse_switch(const std::string& text) {
    const size_t colon = text.find(':');
    if (colon == std::string::npos) throw std::invalid_argument("switch must be seconds:hall|rom02");
    const double seconds = number(text.substr(0, colon), "switch time");
    if (seconds < 0.0 || seconds > 86400.0) throw std::invalid_argument("switch time out of range");
    return {static_cast<size_t>(std::llround(seconds * 48000.0)), effect_from(text.substr(colon + 1))};
}
void usage() {
    std::cout << "Usage: trollfx-audio-host INPUT.wav OUTPUT.wav [options]\n"
                 "  --backend mock|runtime    runtime is unavailable in this build\n"
                 "  --factory-state PATH      private state package required by runtime backend\n"
                 "  --effect hall|rom02       initial mock effect (default hall)\n"
                 "  --wet 0..1                host wet/dry blend (default 0.35)\n"
                 "  --input-gain-db DB        host input gain (default 0 dB)\n"
                 "  --output-gain-db DB       host output gain (default 0 dB)\n"
                 "  --block N                 processing block frames (default 256)\n"
                 "  --switch-at SEC:EFFECT    schedule an offline transition; repeatable\n";
}
}

int main(int argc, char** argv) {
    if (argc == 2 && (std::string(argv[1]) == "--help" || std::string(argv[1]) == "-h")) { usage(); return 0; }
    if (argc < 3) { usage(); return 2; }
    try {
        const std::string input_path = argv[1], output_path = argv[2];
        Effect initial = Effect::Hall;
        std::string backend = "mock";
        std::string factory_state;
        double wet = 0.35, in_db = 0.0, out_db = 0.0;
        size_t block = 256;
        std::vector<Switch> switches;
        for (int i = 3; i < argc; ++i) {
            const std::string arg = argv[i];
            auto value = [&]() -> std::string { if (++i >= argc) throw std::invalid_argument("missing value after " + arg); return argv[i]; };
            if (arg == "--backend") backend = value();
            else if (arg == "--factory-state") factory_state = value();
            else if (arg == "--effect") initial = effect_from(value());
            else if (arg == "--wet") wet = number(value(), "wet value");
            else if (arg == "--input-gain-db") in_db = number(value(), "input gain");
            else if (arg == "--output-gain-db") out_db = number(value(), "output gain");
            else if (arg == "--block") {
                const double n = number(value(), "block size");
                if (n < 1 || n > 1048576 || std::floor(n) != n) throw std::invalid_argument("block size must be 1..1048576");
                block = static_cast<size_t>(n);
            } else if (arg == "--switch-at") switches.push_back(parse_switch(value()));
            else throw std::invalid_argument("unknown option: " + arg);
        }
        if (backend != "mock") {
            if (backend == "runtime") {
                if (factory_state.empty())
                    throw std::runtime_error("runtime backend requires --factory-state pointing to an authorized private state package");
                if (!std::filesystem::is_regular_file(factory_state))
                    throw std::runtime_error("factory state package does not exist or is not a file");
                throw std::runtime_error("reusable ES5510 runtime adapter is not available yet; factory state was not opened");
            }
            throw std::invalid_argument("backend must be mock or runtime");
        }
        if (wet < 0.0 || wet > 1.0) throw std::invalid_argument("wet must be in 0..1");
        if (in_db < -96 || in_db > 24 || out_db < -96 || out_db > 24)
            throw std::invalid_argument("gain range is -96..24 dB");

        WavData wav; std::string error;
        if (!trollfx::audio::read_stereo_wav(input_path, wav, error)) throw std::runtime_error(error);
        if (wav.frames.empty()) throw std::invalid_argument("input WAV contains no frames");
        constexpr uint32_t rate = 48000;
        const size_t output_frames = static_cast<size_t>(std::llround(
            static_cast<double>(wav.frames.size()) * rate / wav.sample_rate));
        if (!output_frames) throw std::invalid_argument("input WAV is too short to produce an output frame at 48 kHz");
        std::vector<StereoFrame> input48(output_frames), output48(output_frames);
        if (wav.sample_rate == rate) input48 = wav.frames;
        else {
            for (size_t i = 0; i < output_frames; ++i) {
                const double source = static_cast<double>(i) * wav.sample_rate / rate;
                const size_t i0 = std::min(static_cast<size_t>(source), wav.frames.size() - 1);
                const size_t i1 = std::min(i0 + 1, wav.frames.size() - 1);
                const float frac = static_cast<float>(source - i0);
                input48[i] = {wav.frames[i0].left + (wav.frames[i1].left - wav.frames[i0].left) * frac,
                              wav.frames[i0].right + (wav.frames[i1].right - wav.frames[i0].right) * frac};
            }
        }
        std::sort(switches.begin(), switches.end(), [](const Switch& a, const Switch& b) { return a.frame < b.frame; });
        for (size_t i = 0; i < switches.size(); ++i) {
            if (switches[i].frame >= output_frames) throw std::invalid_argument("switch time is past the output duration");
            if (i && switches[i].frame == switches[i - 1].frame) throw std::invalid_argument("switch times must be unique");
        }

        MockProcessor mock;
        AudioHost host(mock, rate, rate, 5, initial);
        host.set_controls({static_cast<float>(wet), trollfx::audio::db_to_linear(static_cast<float>(in_db)),
                           trollfx::audio::db_to_linear(static_cast<float>(out_db))});
        std::vector<float> in_block(block * 2), out_block(block * 2);
        const auto begin = std::chrono::steady_clock::now();
        size_t cursor = 0, event = 0;
        while (cursor < output_frames) {
            host.service_control();
            if (event < switches.size() && switches[event].frame == cursor) {
                if (host.switch_pending()) throw std::invalid_argument("switch events overlap the 10 ms switch transition");
                host.request_effect(switches[event++].effect);
            }
            size_t n = std::min(block, output_frames - cursor);
            if (event < switches.size() && switches[event].frame > cursor)
                n = std::min(n, switches[event].frame - cursor);
            if (!n) continue;
            for (size_t i = 0; i < n; ++i) {
                in_block[2 * i] = input48[cursor + i].left;
                in_block[2 * i + 1] = input48[cursor + i].right;
            }
            host.process(in_block.data(), 2, out_block.data(), 2, n);
            for (size_t i = 0; i < n; ++i) output48[cursor + i] = {out_block[2 * i], out_block[2 * i + 1]};
            cursor += n;
        }
        const auto end = std::chrono::steady_clock::now();
        if (!trollfx::audio::write_stereo_pcm16_wav(output_path, rate, output48, error)) throw std::runtime_error(error);
        const double ms = std::chrono::duration<double, std::milli>(end - begin).count();
        const double audio_seconds = static_cast<double>(output_frames) / rate;
        const double ratio = audio_seconds > 0 ? (ms / 1000.0) / audio_seconds : 0.0;
        const size_t memory_estimate = (wav.frames.capacity() + input48.capacity() + output48.capacity()) * sizeof(StereoFrame) +
                                       in_block.capacity() * sizeof(float) + out_block.capacity() * sizeof(float) + host.memory_bytes();
        std::cout << "backend=mock (experimental; not authentic factory processing)\n"
                  << "initial_effect=" << effect_name(initial) << " final_effect=" << effect_name(host.active_effect()) << "\n"
                  << "input_rate_hz=" << wav.sample_rate << " dsp_rate_hz=" << host.dsp_rate()
                  << " output_rate_hz=" << rate << "\n"
                  << "input_frames=" << wav.frames.size() << " output_frames=" << output_frames
                  << " block_frames=" << block << " switches=" << switches.size() << "\n"
                  << "processing_ms=" << ms << " realtime_ratio=" << ratio
                  << " estimated_memory_bytes=" << memory_estimate << " processor_latency_frames=" << host.latency_frames() << "\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "trollfx-audio-host: " << e.what() << "\n";
        return 2;
    }
}
