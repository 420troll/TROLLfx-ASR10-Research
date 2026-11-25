#include "trollfx/es5510_factory_runtime.hpp"
#include "es5510.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <limits>
#if defined(TROLLFX_SIMULATOR_TRACE)
#include <atomic>
#endif

namespace trollfx::es5510 {
namespace {
constexpr std::size_t kEventCapacity = EffectRegistry::kMaxFirmwareEvents;
constexpr std::size_t kResampleHistory = 32;
constexpr std::uint8_t kDefaultInputPort = 2;
constexpr std::uint8_t kDefaultOutputPort = 1;

std::uint32_t expected_words(EffectId id) {
    switch (id) {
    case EffectId::Rom01Hall: return 89;
    case EffectId::Rom02Reverb44k: return 60;
    }
    return 0;
}

#if defined(TROLLFX_SIMULATOR_TRACE)
// Optional, fixed-size audit ring for the desktop simulator only. Records are
// written at the point where an event is applied to the ES5510 host GPR port.
constexpr std::size_t kSimulatorTraceCapacity = 4096;
struct SimulatorTraceCell {
    std::atomic<std::uint64_t> sequence{0};
    std::atomic<std::uint64_t> dsp_frame{0};
    std::atomic<std::uint32_t> slot{0};
    std::atomic<std::uint32_t> gpr{0};
    std::atomic<std::uint32_t> value24{0};
};
std::array<SimulatorTraceCell, kSimulatorTraceCapacity> g_simulator_trace{};
std::atomic<std::uint64_t> g_simulator_trace_latest{0};

void simulator_trace_write(std::uint32_t slot, std::uint64_t frame,
                           std::uint8_t gpr, std::uint32_t value24) noexcept {
    const auto seq = g_simulator_trace_latest.fetch_add(1, std::memory_order_relaxed) + 1;
    auto& cell = g_simulator_trace[(seq - 1) % kSimulatorTraceCapacity];
    cell.dsp_frame.store(frame, std::memory_order_relaxed);
    cell.slot.store(slot, std::memory_order_relaxed);
    cell.gpr.store(gpr, std::memory_order_relaxed);
    cell.value24.store(value24, std::memory_order_relaxed);
    cell.sequence.store(seq, std::memory_order_release);
}
#else
inline void simulator_trace_write(std::uint32_t, std::uint64_t,
                                  std::uint8_t, std::uint32_t) noexcept {}
#endif

double expected_factory_rate(EffectId id) {
    switch (id) {
    case EffectId::Rom01Hall: return 29761.89453125;
    case EffectId::Rom02Reverb44k: return 44100.0;
    }
    return 0.0;
}

std::int16_t to_serial(float x) noexcept {
    if (!std::isfinite(x)) return 0;
    if (x <= -1.0f) return -32768;
    if (x >= 1.0f) return 32767;
    const double scaled = static_cast<double>(x) * 32768.0;
    const long rounded = scaled >= 0.0 ? static_cast<long>(std::floor(scaled + 0.5))
                                        : static_cast<long>(std::ceil(scaled - 0.5));
    return static_cast<std::int16_t>(std::clamp<long>(rounded, -32768, 32767));
}

float from_serial(std::int16_t x) noexcept { return static_cast<float>(x) / 32768.0f; }

void host_write_gpr(ES5510& dsp, std::uint8_t index, std::uint32_t value) noexcept {
    value &= 0x00ffffffu;
    dsp.host_w(0, static_cast<std::uint8_t>(value >> 16));
    dsp.host_w(1, static_cast<std::uint8_t>(value >> 8));
    dsp.host_w(2, static_cast<std::uint8_t>(value));
    dsp.host_w(0xa0, index);
}
} // namespace

struct FactoryRuntime::Impl {
    struct Event { std::uint64_t frame = 0; std::uint64_t order = 0; std::uint8_t index = 0; std::uint32_t value = 0; };
    struct Point { double time = 0.0; float left = 0.0f; float right = 0.0f; };

    ES5510 dsp;
    EffectPackage package;
    EffectDescriptor descriptor;
    bool generic = false;
    RuntimeStatus status;
    RateMode mode = RateMode::Experimental48000;
    double dsp_rate = 48000.0;
    double host_rate = 48000.0;
    double phase = 0.0;
    double host_frame_time = 0.0;
    std::array<Event, kEventCapacity> events{};
    std::size_t event_count = 0;
    std::uint64_t event_order = 0;
    std::uint64_t dsp_frames = 0;
    std::uint64_t applied_writes = 0;
    std::array<Point, kResampleHistory> history{};
    std::size_t history_count = 0;
    std::size_t history_next = 0;
    std::int16_t previous_input_left = 0;
    std::int16_t previous_input_right = 0;
    bool have_previous_input = false;
    bool loaded = false;
    const char* message = "not loaded";

    std::uint8_t input_left() const noexcept { return static_cast<std::uint8_t>(descriptor.routing.input_port * 2); }
    std::uint8_t input_right() const noexcept { return static_cast<std::uint8_t>(descriptor.routing.input_port * 2 + 1); }
    std::uint8_t output_left() const noexcept { return static_cast<std::uint8_t>(descriptor.routing.output_port * 2); }
    std::uint8_t output_right() const noexcept { return static_cast<std::uint8_t>(descriptor.routing.output_port * 2 + 1); }

    void set_error(StatusCode code, const char* text) noexcept {
        status.code = code;
        message = text;
        status.message = text;
        status.message = message;
    }

    void clear_stream_state() noexcept {
        phase = 0.0;
        host_frame_time = 0.0;
        event_count = 0;
        event_order = 0;
        dsp_frames = 0;
        applied_writes = 0;
        history_count = history_next = 0;
        previous_input_left = previous_input_right = 0;
        have_previous_input = false;
        const Point initial{0.0, from_serial(dsp.ser_r(output_left())), from_serial(dsp.ser_r(output_right()))};
        history[0] = initial;
        history_count = 1;
        history_next = 1;
        status.processed_dsp_frames = 0;
        status.scheduled_writes_applied = 0;
    }

    void install_firmware_schedule() noexcept {
        if (!generic) return;
        event_count = 0; event_order = 0;
        for (const auto& e : descriptor.firmware_event_schedule) {
            Event event{e.relative_dsp_frame, event_order++, e.gpr, e.value24};
            std::size_t pos=event_count;
            while(pos && (events[pos-1].frame>event.frame ||
                  (events[pos-1].frame==event.frame && events[pos-1].order>event.order))) {
                events[pos]=events[pos-1]; --pos;
            }
            events[pos]=event; ++event_count;
        }
    }

    bool open_checkpoint() {
        FILE* file = std::fopen(package.checkpoint_path.c_str(), "rb");
        if (!file) { set_error(StatusCode::CaptureRejected, "cannot open private checkpoint"); return false; }
        const bool ok = dsp.load_capture_after_pipeline_reset(file);
        std::fclose(file);
        if (!ok) { set_error(StatusCode::CaptureRejected, "invalid or incomplete ES5510 checkpoint"); return false; }
        if (dsp.active_program_words() != package.active_program_words) {
            set_error(StatusCode::PackageRejected, "checkpoint active program length does not match package");
            return false;
        }
        if (generic && dsp.serial_ctl() != descriptor.routing.host_serial_mode) {
            set_error(StatusCode::PackageRejected, "checkpoint serial mode does not match package routing");
            return false;
        }
        return true;
    }

    void add_point(double time, std::int16_t l, std::int16_t r) noexcept {
        history[history_next] = {time, from_serial(l), from_serial(r)};
        history_next = (history_next + 1) % history.size();
        if (history_count < history.size()) ++history_count;
    }

    Point point_from_oldest(std::size_t logical) const noexcept {
        const std::size_t oldest = (history_next + history.size() - history_count) % history.size();
        return history[(oldest + logical) % history.size()];
    }

    void render_at(double t, float& l, float& r) const noexcept {
        Point before = point_from_oldest(0);
        if (t <= before.time) { l = before.left; r = before.right; return; }
        for (std::size_t i = 1; i < history_count; ++i) {
            const Point after = point_from_oldest(i);
            if (t <= after.time) {
                const double span = after.time - before.time;
                const float mix = span > 0.0 ? static_cast<float>((t - before.time) / span) : 0.0f;
                l = before.left + (after.left - before.left) * mix;
                r = before.right + (after.right - before.right) * mix;
                return;
            }
            before = after;
        }
        l = before.left;
        r = before.right;
    }

    void execute_dsp_frame(std::int16_t left, std::int16_t right, double time) noexcept {
        while (event_count && events[0].frame == dsp_frames) {
            simulator_trace_write(descriptor.slot, dsp_frames, events[0].index, events[0].value);
            host_write_gpr(dsp, events[0].index, events[0].value);
            for (std::size_t i = 1; i < event_count; ++i) events[i - 1] = events[i];
            --event_count;
            ++applied_writes;
        }
        dsp.ser_w(input_left(), left);
        dsp.ser_w(input_right(), right);
        dsp.run_frame();
        add_point(time, dsp.ser_r(output_left()), dsp.ser_r(output_right()));
        ++dsp_frames;
    }
};

FactoryRuntime::FactoryRuntime() : impl_(new Impl) {}
FactoryRuntime::~FactoryRuntime() = default;
FactoryRuntime::FactoryRuntime(FactoryRuntime&&) noexcept = default;
FactoryRuntime& FactoryRuntime::operator=(FactoryRuntime&&) noexcept = default;

bool FactoryRuntime::loadEffect(const EffectPackage& p, RateMode mode) {
    auto& s = *impl_;
    const auto words = expected_words(p.effect);
    const auto factory_rate = expected_factory_rate(p.effect);
    if (!words || p.active_program_words != words || !std::isfinite(p.factory_processing_rate_hz) ||
        std::fabs(p.factory_processing_rate_hz - factory_rate) > 0.01) {
        s.set_error(StatusCode::PackageRejected, "effect identity, program length, or reference rate is invalid");
        return false;
    }
    if (p.checkpoint_path.empty() || !p.pipeline_reset_acknowledged ||
        !p.package_provenance_validated || !p.serial_route_validated) {
        s.set_error(StatusCode::PackageRejected, "private package lacks RUN, pipeline-reset, provenance, or routing validation");
        return false;
    }
    s.package = p;
    s.generic = false;
    s.descriptor = {};
    s.descriptor.slot = static_cast<EffectSlot>(p.effect);
    s.descriptor.factory_name = p.effect == EffectId::Rom01Hall ? "ROM-01 HALL REVERB" : "ROM-02 44KHZ REVERB";
    s.descriptor.active_program_words = p.active_program_words;
    s.descriptor.factory_reference_rate_hz = p.factory_processing_rate_hz;
    s.descriptor.routing.input_port = kDefaultInputPort;
    s.descriptor.routing.output_port = kDefaultOutputPort;
    s.loaded = false;
    if (!s.open_checkpoint()) return false;
    s.loaded = true;
    s.mode = mode;
    s.dsp_rate = mode == RateMode::Experimental48000 ? 48000.0 : p.factory_processing_rate_hz;
    s.clear_stream_state();
    s.status.effect = p.effect;
    s.status.active_program_words = p.active_program_words;
    s.status.rate_mode = mode;
    s.status.processing_rate_hz = s.dsp_rate;
    s.status.algorithmic_latency_host_frames = static_cast<std::uint32_t>(std::ceil(48000.0 / s.dsp_rate) + 1.0);
    s.status.code = StatusCode::Ready;
    s.message = s.status.message = "ready";
    return true;
}

bool FactoryRuntime::loadEffect(const ValidatedEffectPackage& p, RateMode mode) {
    auto& s = *impl_;
    const auto& d = p.descriptor;
    if (!p.validation_receipt_valid || !p.initialization_state_valid || !p.program_identity_valid ||
        !p.pipeline_reset_valid || !p.routing_valid || d.slot < 1 || d.slot > 50 ||
        d.factory_name.empty() || d.active_program_words == 0 || d.active_program_words > 160 ||
        d.end_word + 1 != d.active_program_words || d.run_checkpoint_path.empty() ||
        !std::isfinite(d.factory_reference_rate_hz) || d.factory_reference_rate_hz < 8000.0 ||
        d.factory_reference_rate_hz > 192000.0 || d.routing.input_port > 3 || d.routing.output_port > 3 ||
        !d.routing.stereo || d.firmware_event_schedule.size() > kEventCapacity) {
        s.set_error(StatusCode::PackageRejected, "validated effect descriptor is incomplete or out of bounds"); return false;
    }
    s.package = {};
    s.package.checkpoint_path = d.run_checkpoint_path;
    s.package.active_program_words = d.active_program_words;
    s.package.factory_processing_rate_hz = d.factory_reference_rate_hz;
    s.descriptor = d;
    s.generic = true;
    s.loaded = false;
    if (!s.open_checkpoint()) return false;
    // Install the descriptor's deterministic firmware post-RUN writes at frame zero.
    s.event_count = 0; s.event_order = 0; s.dsp_frames = 0;
    for (const auto& e : d.firmware_event_schedule) {
        if (e.gpr >= 0xc0 || e.value24 > 0xffffffu || (s.event_count && e.relative_dsp_frame < s.events[s.event_count-1].frame)) {
            s.set_error(StatusCode::PackageRejected, "firmware event schedule is invalid"); return false;
        }
        s.events[s.event_count++] = {e.relative_dsp_frame, s.event_order++, e.gpr, e.value24};
    }
    s.loaded = true; s.mode = mode;
    s.dsp_rate = mode == RateMode::Experimental48000 ? 48000.0 : d.factory_reference_rate_hz;
    s.clear_stream_state();
    s.status.effect = static_cast<EffectId>(d.slot); s.status.active_program_words = d.active_program_words;
    s.status.rate_mode = mode; s.status.processing_rate_hz = s.dsp_rate;
    s.status.algorithmic_latency_host_frames = static_cast<std::uint32_t>(std::ceil(48000.0 / s.dsp_rate) + 1.0);
    s.status.code = StatusCode::Ready; s.message = s.status.message = "ready";
    // clear_stream_state resets the frame timeline; restore validated firmware writes.
    s.install_firmware_schedule();
    return true;
}

bool FactoryRuntime::reset() {
    auto& s = *impl_;
    if (!s.loaded) { s.set_error(StatusCode::Empty, "no effect is loaded"); return false; }
    if (!s.open_checkpoint()) { s.loaded = false; return false; }
    s.clear_stream_state();
    s.install_firmware_schedule();
    s.status.code = StatusCode::Ready;
    s.message = s.status.message = "reset to validated RUN checkpoint";
    return true;
}

bool FactoryRuntime::setProcessingRate(RateMode mode) {
    auto& s = *impl_;
    if (!s.loaded) { s.set_error(StatusCode::Empty, "no effect is loaded"); return false; }
    s.mode = mode;
    s.dsp_rate = mode == RateMode::Experimental48000 ? 48000.0 : s.package.factory_processing_rate_hz;
    s.phase = 0.0;
    s.status.rate_mode = mode;
    s.status.processing_rate_hz = s.dsp_rate;
    s.status.algorithmic_latency_host_frames = static_cast<std::uint32_t>(std::ceil(s.host_rate / s.dsp_rate) + 1.0);
    s.status.code = StatusCode::Ready;
    s.message = s.status.message = "processing rate changed; DSP state retained";
    return true;
}

bool FactoryRuntime::setRegister(std::uint8_t index, std::uint32_t value, std::uint64_t frame) {
    auto& s = *impl_;
    if (!s.loaded) { s.set_error(StatusCode::Empty, "no effect is loaded"); return false; }
    if (index >= 0xc0) { s.set_error(StatusCode::InvalidArgument, "only GPR indices 0x00..0xBF are schedulable"); return false; }
    if (value > 0x00ffffffu) { s.set_error(StatusCode::InvalidArgument, "GPR value exceeds the 24-bit register width"); return false; }
    if (frame < s.dsp_frames) { s.set_error(StatusCode::EventInPast, "register event is in the past"); return false; }
    if (s.event_count >= s.events.size()) { s.set_error(StatusCode::EventQueueFull, "fixed register event queue is full"); return false; }
    Impl::Event event{frame, s.event_order++, index, value};
    std::size_t pos = s.event_count;
    while (pos && (s.events[pos - 1].frame > event.frame ||
                   (s.events[pos - 1].frame == event.frame && s.events[pos - 1].order > event.order))) {
        s.events[pos] = s.events[pos - 1];
        --pos;
    }
    s.events[pos] = event;
    ++s.event_count;
    s.status.code = StatusCode::Ready;
    s.message = s.status.message = "register event scheduled";
    return true;
}

bool FactoryRuntime::setParameter(const EffectDescriptor& d, const std::string& id,
                                  std::int32_t value, std::uint64_t frame) {
    if (!impl_->loaded || d.slot != impl_->descriptor.slot) { impl_->set_error(StatusCode::PackageRejected, "parameter descriptor does not match loaded effect"); return false; }
    for (const auto& p : d.parameters) if (p.id == id) {
        for (const auto& point : p.verified_points) if (point.display_value == value) {
            if (point.ordered_writes.empty())
                return setRegister(point.gpr, point.value24, frame);
            auto& s = *impl_;
            if (frame < s.dsp_frames) { s.set_error(StatusCode::EventInPast, "parameter event is in the past"); return false; }
            if (point.ordered_writes.size() > s.events.size() - s.event_count) {
                s.set_error(StatusCode::EventQueueFull, "fixed register event queue cannot fit the complete parameter write group");
                return false;
            }
            // Validate the whole group before modifying the fixed queue.
            for (const auto& write : point.ordered_writes) {
                if (write.gpr >= 0xc0 || write.value24 > 0x00ffffffu) {
                    s.set_error(StatusCode::InvalidArgument, "parameter write group contains an invalid GPR value");
                    return false;
                }
            }
            for (const auto& write : point.ordered_writes) {
                Impl::Event event{frame, s.event_order++, write.gpr, write.value24};
                std::size_t pos = s.event_count;
                while (pos && (s.events[pos - 1].frame > event.frame ||
                       (s.events[pos - 1].frame == event.frame && s.events[pos - 1].order > event.order))) {
                    s.events[pos] = s.events[pos - 1];
                    --pos;
                }
                s.events[pos] = event;
                ++s.event_count;
            }
            s.status.code = StatusCode::Ready;
            s.message = s.status.message = "ordered parameter write group scheduled";
            return true;
        }
        impl_->set_error(StatusCode::InvalidArgument, "parameter value is not a verified catalog point"); return false;
    }
    impl_->set_error(StatusCode::InvalidArgument, "parameter is not defined for this effect"); return false;
}

bool FactoryRuntime::processStereo(const float* input, float* output, std::size_t frames, double host_rate) {
    auto& s = *impl_;
    if (!s.loaded) { s.set_error(StatusCode::Empty, "no effect is loaded"); return false; }
    if ((!input || !output) && frames) { s.set_error(StatusCode::InvalidArgument, "audio pointers are null"); return false; }
    if (!std::isfinite(host_rate) || host_rate < 8000.0 || host_rate > 192000.0) {
        s.set_error(StatusCode::InvalidArgument, "host rate must be between 8 kHz and 192 kHz"); return false;
    }
    if (std::fabs(host_rate - s.host_rate) > 0.0001) {
        s.host_rate = host_rate;
        s.phase = 0.0;
    }
    s.status.host_rate_hz = host_rate;
    const double ratio = s.dsp_rate / host_rate;
    const double output_latency = std::ceil(host_rate / s.dsp_rate) + 1.0;
    s.status.algorithmic_latency_host_frames = static_cast<std::uint32_t>(output_latency);
    for (std::size_t i = 0; i < frames; ++i) {
        const double now = s.host_frame_time + 1.0;
        const std::int16_t current_l = to_serial(input[2 * i]);
        const std::int16_t current_r = to_serial(input[2 * i + 1]);
        const std::int16_t previous_l = s.have_previous_input ? s.previous_input_left : current_l;
        const std::int16_t previous_r = s.have_previous_input ? s.previous_input_right : current_r;
        double accumulated = s.phase + ratio;
        std::uint32_t crossing_index = 0;
        while (accumulated >= 1.0) {
            const double crossing = (1.0 - s.phase + crossing_index) / ratio;
            const double f = std::clamp(crossing, 0.0, 1.0);
            const auto in_l = static_cast<std::int16_t>(std::clamp<long>(std::lround(previous_l + (current_l - previous_l) * f), -32768, 32767));
            const auto in_r = static_cast<std::int16_t>(std::clamp<long>(std::lround(previous_r + (current_r - previous_r) * f), -32768, 32767));
            s.execute_dsp_frame(in_l, in_r, now - 1.0 + f);
            accumulated -= 1.0;
            ++crossing_index;
        }
        s.phase = accumulated;
        s.previous_input_left = current_l;
        s.previous_input_right = current_r;
        s.have_previous_input = true;
        s.host_frame_time = now;
        float left = 0.0f, right = 0.0f;
        s.render_at(now - output_latency, left, right);
        output[2 * i] = left;
        output[2 * i + 1] = right;
    }
    s.status.processed_dsp_frames = s.dsp_frames;
    s.status.scheduled_writes_applied = s.applied_writes;
    s.status.code = StatusCode::Ready;
    s.message = s.status.message = "processing";
    return true;
}

RuntimeStatus FactoryRuntime::getStatus() const noexcept {
    RuntimeStatus result = impl_->status;
    result.message = impl_->message;
    return result;
}

} // namespace trollfx::es5510

#if defined(TROLLFX_SIMULATOR_TRACE)
struct TROLLfxSimTraceWrite {
    std::uint64_t sequence;
    std::uint64_t dsp_frame;
    std::uint32_t slot;
    std::uint32_t gpr;
    std::uint32_t value24;
};

extern "C" __attribute__((visibility("default")))
std::uint64_t TROLLfx_SimTraceLatest() noexcept {
    return trollfx::es5510::g_simulator_trace_latest.load(std::memory_order_acquire);
}

extern "C" __attribute__((visibility("default")))
std::size_t TROLLfx_SimTraceCopy(std::uint64_t after, TROLLfxSimTraceWrite* out,
                                 std::size_t capacity) noexcept {
    if (!out || !capacity) return 0;
    using namespace trollfx::es5510;
    const auto latest = g_simulator_trace_latest.load(std::memory_order_acquire);
    const auto earliest = latest > kSimulatorTraceCapacity ? latest - kSimulatorTraceCapacity + 1 : 1;
    const auto first = std::max(after + 1, earliest);
    std::size_t copied = 0;
    for (auto seq = first; seq <= latest && copied < capacity; ++seq) {
        auto& cell = g_simulator_trace[(seq - 1) % kSimulatorTraceCapacity];
        if (cell.sequence.load(std::memory_order_acquire) != seq) continue;
        TROLLfxSimTraceWrite row{seq, cell.dsp_frame.load(std::memory_order_relaxed),
            cell.slot.load(std::memory_order_relaxed), cell.gpr.load(std::memory_order_relaxed),
            cell.value24.load(std::memory_order_relaxed)};
        if (cell.sequence.load(std::memory_order_acquire) == seq) out[copied++] = row;
    }
    return copied;
}

extern "C" __attribute__((visibility("default")))
void TROLLfx_SimTraceReset() noexcept {
    for (auto& cell : trollfx::es5510::g_simulator_trace)
        cell.sequence.store(0, std::memory_order_relaxed);
    trollfx::es5510::g_simulator_trace_latest.store(0, std::memory_order_release);
}
#endif
