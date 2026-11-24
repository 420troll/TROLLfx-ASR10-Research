#include "trollfx/es5510_factory_runtime.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

using namespace trollfx::es5510;

namespace {
std::vector<ScheduledGprWrite> read_events(const std::string& path, std::uint64_t run_frame) {
    std::ifstream f(path);
    std::string line;
    if (!std::getline(f, line)) throw std::runtime_error("missing ROM-02 firmware event CSV header");
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line != "boundary_frame,event_id,cpu_cycles,dsp_frame,host_pc,index,value")
        throw std::runtime_error("unexpected ROM-02 firmware event CSV header");
    std::vector<ScheduledGprWrite> events;
    while (std::getline(f, line)) {
        std::stringstream s(line);
        std::array<std::string, 7> c;
        for (auto& x : c) if (!std::getline(s, x, ',')) throw std::runtime_error("malformed firmware event row");
        const auto absolute = std::stoull(c[0]);
        const auto reg = static_cast<unsigned>(std::stoul(c[5], nullptr, 16));
        const auto value = static_cast<std::uint32_t>(std::stoul(c[6], nullptr, 16));
        if (absolute < run_frame || reg >= 0xc0 || value > 0xffffff)
            throw std::runtime_error("firmware event outside validated ROM-02 bounds");
        events.push_back({absolute - run_frame, static_cast<std::uint8_t>(reg), value});
    }
    return events;
}

std::vector<float> make_signal(const std::string& signal, const std::string& route,
                              std::size_t frames, double rate) {
    std::vector<float> x(frames * 2, 0.0f);
    std::mt19937 rng(0x5510a502u);
    std::uniform_real_distribution<float> noise(-0.18f, 0.18f);
    for (std::size_t i = 0; i < frames; ++i) {
        float l = 0.0f, r = 0.0f;
        if (signal == "impulse") {
            if (i == 0) { l = 0.8f; r = 0.73f; }
        } else if (signal == "noise") {
            l = noise(rng); r = noise(rng);
        } else {
            l = 0.31f * std::sin(2.0 * M_PI * 223.0 * i / rate) +
                0.17f * std::sin(2.0 * M_PI * 701.0 * i / rate);
            r = 0.27f * std::sin(2.0 * M_PI * 317.0 * i / rate) -
                0.13f * std::sin(2.0 * M_PI * 997.0 * i / rate);
        }
        if (route == "left") r = 0.0f;
        else if (route == "right") l = 0.0f;
        x[2 * i] = l; x[2 * i + 1] = r;
    }
    return x;
}

std::vector<float> render(const std::string& checkpoint, const std::vector<ScheduledGprWrite>& events,
                          bool factory_rate, std::uint8_t reg, std::uint32_t value,
                          const std::vector<float>& audio) {
    ValidatedEffectPackage p;
    auto& d = p.descriptor;
    d.slot = 2; d.factory_name = "44KHZ REVERB"; d.active_program_words = 60; d.end_word = 59;
    d.program_sha256 = "12119e86d4d232ab7d7ab4278e9c9dbed9db19a6b6eb352bfb29441181da4486";
    d.factory_reference_rate_hz = 44100.0; d.routing = {0x48, 2, 1, true};
    d.run_checkpoint_path = checkpoint; d.run_checkpoint_sha256 = "validated-by-driver";
    d.firmware_event_schedule = events;
    p.validation_receipt_valid = p.initialization_state_valid = p.program_identity_valid =
        p.pipeline_reset_valid = p.routing_valid = true;
    FactoryRuntime runtime;
    const auto mode = factory_rate ? RateMode::FactoryReference : RateMode::Experimental48000;
    if (!runtime.loadEffect(p, mode)) throw std::runtime_error(std::string("ROM-02 load failed: ") + runtime.getStatus().message);

    const double dsp_rate = factory_rate ? 44100.0 : 48000.0;
    constexpr double observed_os_edit_seconds = 177123.0 / 44100.0;
    const auto warmup_frames = static_cast<std::size_t>(std::llround(observed_os_edit_seconds * dsp_rate));
    auto warmup = make_signal("sustained", "stereo", warmup_frames, dsp_rate);
    std::vector<float> warmup_out(warmup.size());
    if (!runtime.processStereo(warmup.data(), warmup_out.data(), warmup.size() / 2, dsp_rate))
        throw std::runtime_error("ROM-02 firmware-schedule warmup failed");
    const auto target_frame = runtime.getStatus().processed_dsp_frames;
    if (!runtime.setRegister(reg, value, target_frame))
        throw std::runtime_error(std::string("ROM-02 BUS register schedule failed: ") + runtime.getStatus().message);
    const auto companion = static_cast<std::uint8_t>(reg + 1);
    if (!runtime.setRegister(companion, 0x7fff00, target_frame))
        throw std::runtime_error("ROM-02 observed companion register write failed");
    if (reg == 0x7c) {
        if (!runtime.setRegister(reg, value, target_frame + 456) ||
            !runtime.setRegister(companion, 0x7fff00, target_frame + 456))
            throw std::runtime_error("ROM-02 repeated BUS1 transaction failed");
    }

    std::vector<float> out(audio.size());
    for (std::size_t offset = 0; offset < audio.size() / 2; offset += 257) {
        const auto count = std::min<std::size_t>(257, audio.size() / 2 - offset);
        if (!runtime.processStereo(audio.data() + 2 * offset, out.data() + 2 * offset, count, dsp_rate))
            throw std::runtime_error("ROM-02 processing failed");
    }
    for (float x : out) if (!std::isfinite(x)) throw std::runtime_error("non-finite ROM-02 output");
    const auto expected_writes = events.size() + (reg == 0x7c ? 4u : 2u);
    if (runtime.getStatus().scheduled_writes_applied != expected_writes)
        throw std::runtime_error("not all firmware and host parameter writes were applied");
    return out;
}

struct Metrics { std::size_t differing = 0; double rms = 0, peak = 0, left_rms = 0, right_rms = 0, early_rms = 0, late_rms = 0; };
Metrics compare(const std::vector<float>& a, const std::vector<float>& b) {
    Metrics m; double e = 0, le = 0, re = 0;
    for (std::size_t i = 0; i < a.size(); ++i) {
        const double d = static_cast<double>(b[i]) - a[i];
        if (d != 0.0) ++m.differing;
        m.peak = std::max(m.peak, std::abs(d)); e += d * d;
        (i % 2 ? re : le) += d * d;
    }
    const auto frames = a.size() / 2;
    m.rms = std::sqrt(e / a.size()); m.left_rms = std::sqrt(le / frames); m.right_rms = std::sqrt(re / frames);
    constexpr std::size_t window = 4096;
    double early = 0, late = 0;
    for (std::size_t i = 0; i < std::min(window, frames); ++i)
        for (unsigned ch = 0; ch < 2; ++ch) { const double d = double(b[2*i+ch]) - a[2*i+ch]; early += d*d; }
    for (std::size_t i = frames - std::min(window, frames); i < frames; ++i)
        for (unsigned ch = 0; ch < 2; ++ch) { const double d = double(b[2*i+ch]) - a[2*i+ch]; late += d*d; }
    m.early_rms = std::sqrt(early / (2 * std::min(window, frames)));
    m.late_rms = std::sqrt(late / (2 * std::min(window, frames)));
    return m;
}
}

int main(int argc, char** argv) try {
    if (argc != 4) { std::cerr << "usage: rom02_parameter_response CHECKPOINT EVENTS RUN_FRAME\n"; return 2; }
    const std::string checkpoint = argv[1];
    const auto run_frame = std::stoull(argv[3]);
    const auto events = read_events(argv[2], run_frame);
    std::size_t last_bus1 = 0, last_bus2 = 0, first_bus1 = 0, first_bus2 = 0, bus1_count = 0, bus2_count = 0;
    for (const auto& e : events) {
        if (e.gpr == 0x7c) { if (!bus1_count) first_bus1 = e.relative_dsp_frame; last_bus1 = e.relative_dsp_frame; ++bus1_count; }
        if (e.gpr == 0x7a) { if (!bus2_count) first_bus2 = e.relative_dsp_frame; last_bus2 = e.relative_dsp_frame; ++bus2_count; }
    }
    if (last_bus1 >= 177123 || last_bus2 >= 177123) throw std::runtime_error("OS-matched edit window precedes the final firmware parameter write");

    std::cout << "{\"schedule\":{\"events\":" << events.size() << ",\"bus1_last_write_frame\":" << last_bus1
              << ",\"bus1_first_write_frame\":" << first_bus1 << ",\"bus1_write_count\":" << bus1_count
              << ",\"bus1_last_value\":\"0x350000\",\"bus2_last_write_frame\":" << last_bus2
              << ",\"bus2_first_write_frame\":" << first_bus2 << ",\"bus2_write_count\":" << bus2_count
              << ",\"bus2_last_value\":\"0x350000\",\"os_edit_offset_seconds\":" << (177123.0/44100.0)
              << ",\"factory_edit_frame\":177123,\"experimental_48000_edit_frame\":" << std::llround((177123.0/44100.0)*48000.0)
              << ",\"warmup_signal\":\"sustained stereo\"},\"comparisons\":[";
    bool first = true;
    for (bool factory : {true, false}) {
        const double rate = factory ? 44100.0 : 48000.0;
        for (const auto& control : {std::string("BUS1"), std::string("BUS2")}) {
            const std::uint8_t reg = control == "BUS1" ? 0x7c : 0x7a;
            for (const auto& route : {std::string("left"), std::string("right"), std::string("stereo")}) {
                for (const auto& signal : {std::string("impulse"), std::string("noise"), std::string("sustained")}) {
                    const std::size_t frames = control == "BUS1" ? 262144 : 16384;
                    const auto input = make_signal(signal, route, frames, rate);
                    const auto a = render(checkpoint, events, factory, reg, 0x350000, input);
                    const auto b = render(checkpoint, events, factory, reg, 0x370000, input);
                    const auto same = render(checkpoint, events, factory, reg, 0x350000, input);
                    const auto m = compare(a, b); const auto determinism = compare(a, same);
                    if (determinism.differing) throw std::runtime_error("same ROM-02 setting was not repeatable");
                    if (control == "BUS2" && m.differing == 0)
                        throw std::runtime_error("verified ROM-02 BUS2 change produced no measurable response");
                    if (!first) std::cout << ',';
                    first = false;
                    std::cout << "{\"rate_hz\":" << rate << ",\"mode\":\"" << (factory ? "factory-44100" : "experimental-48000")
                              << "\",\"control\":\"" << control << "\",\"register\":\"0x" << std::hex << unsigned(reg) << std::dec
                              << "\",\"writes\":[\"0x350000\",\"0x370000\"],\"route\":\"" << route << "\",\"signal\":\"" << signal
                              << "\",\"edit_frame\":" << (factory ? 177123 : 192787)
                              << ",\"primary_write_frames\":[" << (factory ? 177123 : 192787)
                              << (control == "BUS1" ? std::string(",") + std::to_string(factory ? 177579 : 193243) : std::string()) << "]"
                              << ",\"companion_register\":\"0x" << std::hex << unsigned(reg + 1) << "=0x7fff00\"" << std::dec
                              << ",\"frames\":" << frames << ",\"different_samples\":" << m.differing << ",\"rms_difference\":" << m.rms
                              << ",\"early_rms_difference\":" << m.early_rms << ",\"late_rms_difference\":" << m.late_rms
                              << ",\"left_rms_difference\":" << m.left_rms << ",\"right_rms_difference\":" << m.right_rms
                              << ",\"peak_difference\":" << m.peak << ",\"deterministic_repeat\":true}";
                }
            }
        }
    }
    std::cout << "]}\n";
    return 0;
} catch (const std::exception& e) { std::cerr << "rom02_parameter_response: " << e.what() << '\n'; return 1; }
