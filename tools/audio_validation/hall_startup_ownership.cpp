#include "trollfx/es5510_factory_runtime.hpp"
#include "trollfx/es5510_factory_parameter_discovery_v02.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace trollfx::es5510;

static EffectDescriptor read_descriptor(const char* checkpoint, const char* schedule,
                                        const char* program_hash, const char* checkpoint_hash,
                                        double factory_rate) {
    EffectDescriptor descriptor;
    descriptor.slot = 1;
    descriptor.factory_name = "HALL REVERB";
    descriptor.active_program_words = 89;
    descriptor.end_word = 88;
    descriptor.program_sha256 = program_hash;
    descriptor.run_checkpoint_path = checkpoint;
    descriptor.run_checkpoint_sha256 = checkpoint_hash;
    descriptor.factory_reference_rate_hz = factory_rate;
    descriptor.routing = {0x48, 2, 1, true};

    std::ifstream input(schedule);
    std::string line;
    if (!std::getline(input, line)) throw std::runtime_error("empty firmware schedule");
    while (std::getline(input, line)) {
        std::stringstream row(line);
        std::string frame, event_id, cycles, gpr, value;
        std::getline(row, frame, ',');
        std::getline(row, event_id, ',');
        std::getline(row, cycles, ',');
        std::getline(row, gpr, ',');
        std::getline(row, value, ',');
        descriptor.firmware_event_schedule.push_back({
            std::stoull(frame), static_cast<std::uint8_t>(std::stoul(gpr, nullptr, 16)),
            static_cast<std::uint32_t>(std::stoul(value, nullptr, 16))});
    }
    if (!input.eof()) throw std::runtime_error("failed to read firmware schedule");
    parameter_discovery_v02::append_verified_parameters(descriptor);
    return descriptor;
}

static float input_sample(std::size_t frame, unsigned channel) {
    const double frequency = channel ? 997.0 : 431.0;
    float sample = (channel ? 0.17f : 0.20f) * static_cast<float>(
        std::sin(2.0 * 3.141592653589793 * frequency * frame / 48000.0));
    if (frame == 0) sample += channel ? -0.4f : 0.7f;
    return sample;
}

static void process_one(FactoryRuntime& runtime, std::size_t& host_frame,
                        double host_rate) {
    const float input[2] = {input_sample(host_frame, 0), input_sample(host_frame, 1)};
    float output[2]{};
    if (!runtime.processStereo(input, output, 1, host_rate))
        throw std::runtime_error(runtime.getStatus().message);
    ++host_frame;
}

static void advance_to(FactoryRuntime& runtime, std::size_t& host_frame,
                       std::uint64_t dsp_frame, double host_rate) {
    while (runtime.getStatus().processed_dsp_frames < dsp_frame)
        process_one(runtime, host_frame, host_rate);
}

static void print_registers(const char* label, std::uint64_t event_frame,
                            unsigned event_gpr, std::uint32_t event_value,
                            FactoryRuntime& runtime) {
    std::printf("REG owner=%s event_frame=%llu event_gpr=%02x event_value=%06x dsp_frame=%llu "
                "writes=%llu 6e=%06x 5b=%06x 03=%06x 04=%06x 05=%06x\n",
        label, static_cast<unsigned long long>(event_frame), event_gpr, event_value,
        static_cast<unsigned long long>(runtime.getStatus().processed_dsp_frames),
        static_cast<unsigned long long>(runtime.getStatus().scheduled_writes_applied),
        runtime.qaReadRegister(0x6e), runtime.qaReadRegister(0x5b),
        runtime.qaReadRegister(0x03), runtime.qaReadRegister(0x04),
        runtime.qaReadRegister(0x05));
}

struct Metrics {
    double rms40 = 0.0, rms41 = 0.0, difference_rms = 0.0;
    float difference_peak = 0.0f;
    std::size_t finite_samples = 0;
};

static Metrics render_pair(FactoryRuntime& a, FactoryRuntime& b,
                           std::size_t& host_frame_a, std::size_t& host_frame_b,
                           double host_rate) {
    constexpr std::size_t frames = 65536;
    constexpr std::size_t block = 256;
    std::array<float, block * 2> input{}, output_a{}, output_b{};
    double energy_a = 0.0, energy_b = 0.0, energy_delta = 0.0;
    float peak_delta = 0.0f;
    std::size_t finite = 0;
    for (std::size_t offset = 0; offset < frames; offset += block) {
        for (std::size_t i = 0; i < block; ++i) {
            input[2 * i] = input_sample(host_frame_a + i, 0);
            input[2 * i + 1] = input_sample(host_frame_a + i, 1);
        }
        if (host_frame_a != host_frame_b)
            throw std::runtime_error("A/B instances have different host input positions");
        if (!a.processStereo(input.data(), output_a.data(), block, host_rate) ||
            !b.processStereo(input.data(), output_b.data(), block, host_rate))
            throw std::runtime_error("wet output processing failed");
        for (std::size_t i = 0; i < output_a.size(); ++i) {
            if (!std::isfinite(output_a[i]) || !std::isfinite(output_b[i]))
                throw std::runtime_error("non-finite wet output");
            energy_a += double(output_a[i]) * output_a[i];
            energy_b += double(output_b[i]) * output_b[i];
            const double delta = double(output_a[i]) - output_b[i];
            energy_delta += delta * delta;
            peak_delta = std::max(peak_delta, static_cast<float>(std::abs(delta)));
            ++finite;
        }
        host_frame_a += block;
        host_frame_b += block;
    }
    return {std::sqrt(energy_a / finite), std::sqrt(energy_b / finite),
            std::sqrt(energy_delta / finite), peak_delta, finite};
}

static void run_pair(const EffectDescriptor& descriptor, RateMode mode,
                     bool edit_before_startup) {
    EffectRegistry registry;
    ValidatedEffectPackage package;
    package.descriptor = descriptor;
    // The Python driver checks the local audit eligibility and checkpoint and
    // schedule SHA-256 values before invoking this test-only utility.
    package.validation_receipt_valid = package.initialization_state_valid = true;
    package.program_identity_valid = package.pipeline_reset_valid = package.routing_valid = true;
    std::string error;
    if (!registry.register_validated(package, &error)) throw std::runtime_error(error);
    const auto* accepted = registry.find(1);
    FactoryRuntime value40, value41;
    if (!value40.loadEffect(*accepted, mode) || !value41.loadEffect(*accepted, mode))
        throw std::runtime_error("validated HALL package load failed");
    const double host_rate = 48000.0;
    const std::uint64_t complete_frame = 1 + std::max_element(
        descriptor.firmware_event_schedule.begin(), descriptor.firmware_event_schedule.end(),
        [](const auto& left, const auto& right) {
            return left.relative_dsp_frame < right.relative_dsp_frame;
        })->relative_dsp_frame;
    std::printf("PAIR mode=%s timing=%s completion_frame=%llu initial_gprs="
                "6e:%06x,5b:%06x,03:%06x,04:%06x,05:%06x\n",
        mode == RateMode::Experimental48000 ? "experimental-48000" : "factory-reference",
        edit_before_startup ? "edit-queued-before-startup" : "edit-after-startup",
        static_cast<unsigned long long>(complete_frame),
        value40.qaReadRegister(0x6e), value40.qaReadRegister(0x5b),
        value40.qaReadRegister(0x03), value40.qaReadRegister(0x04),
        value40.qaReadRegister(0x05));

    if (edit_before_startup) {
        if (!value40.setParameter(accepted->descriptor, "decay_time", 40, 0) ||
            !value41.setParameter(accepted->descriptor, "decay_time", 41, 0))
            throw std::runtime_error("early HALL edit request was rejected");
        const auto a = value40.getStatus(), b = value41.getStatus();
        std::printf("EDIT owner=A value=40 accepted=1 applied=%d pending=%u target_frame=%llu\n",
            a.last_parameter_write_applied, a.parameter_writes_pending,
            static_cast<unsigned long long>(a.initialization_complete_frame));
        std::printf("EDIT owner=B value=41 accepted=1 applied=%d pending=%u target_frame=%llu\n",
            b.last_parameter_write_applied, b.parameter_writes_pending,
            static_cast<unsigned long long>(b.initialization_complete_frame));
    }

    std::size_t host_a = 0, host_b = 0;
    std::vector<ScheduledGprWrite> observed;
    for (const auto& event : descriptor.firmware_event_schedule) {
        if (event.gpr == 0x03 || event.gpr == 0x04 || event.gpr == 0x05 ||
            event.gpr == 0x5b || event.gpr == 0x6e)
            observed.push_back(event);
    }
    for (const auto& event : observed) {
        advance_to(value40, host_a, event.relative_dsp_frame + 1, host_rate);
        advance_to(value41, host_b, event.relative_dsp_frame + 1, host_rate);
        print_registers("A40", event.relative_dsp_frame, event.gpr, event.value24, value40);
        print_registers("B41", event.relative_dsp_frame, event.gpr, event.value24, value41);
    }
    advance_to(value40, host_a, complete_frame, host_rate);
    advance_to(value41, host_b, complete_frame, host_rate);
    const auto initialized_a = value40.getStatus(), initialized_b = value41.getStatus();
    std::printf("INIT owner=A complete=%d frame=%llu firmware_pending=%u parameter_pending=%u\n",
        initialized_a.initialization_schedule_complete,
        static_cast<unsigned long long>(initialized_a.processed_dsp_frames),
        initialized_a.firmware_writes_pending, initialized_a.parameter_writes_pending);
    std::printf("INIT owner=B complete=%d frame=%llu firmware_pending=%u parameter_pending=%u\n",
        initialized_b.initialization_schedule_complete,
        static_cast<unsigned long long>(initialized_b.processed_dsp_frames),
        initialized_b.firmware_writes_pending, initialized_b.parameter_writes_pending);

    if (!edit_before_startup) {
        if (!value40.setParameter(accepted->descriptor, "decay_time", 40, complete_frame) ||
            !value41.setParameter(accepted->descriptor, "decay_time", 41, complete_frame))
            throw std::runtime_error("post-startup HALL edit request was rejected");
    }
    advance_to(value40, host_a, complete_frame + 1, host_rate);
    advance_to(value41, host_b, complete_frame + 1, host_rate);
    const auto applied_a = value40.getStatus(), applied_b = value41.getStatus();
    if (!applied_a.last_parameter_write_applied || !applied_b.last_parameter_write_applied ||
        applied_a.parameter_writes_pending || applied_b.parameter_writes_pending)
        throw std::runtime_error("parameter edit did not reach the DSP before measurement");
    print_registers("A40-applied", complete_frame, 0xff, 0, value40);
    print_registers("B41-applied", complete_frame, 0xff, 0, value41);
    const auto metrics = render_pair(value40, value41, host_a, host_b, host_rate);
    std::printf("WET mode=%s timing=%s frames=65536 finite=%zu rms40=%.9g rms41=%.9g "
                "difference_rms=%.9g difference_peak=%.9g\n",
        mode == RateMode::Experimental48000 ? "experimental-48000" : "factory-reference",
        edit_before_startup ? "early-deferred" : "post-initialization",
        metrics.finite_samples, metrics.rms40, metrics.rms41,
        metrics.difference_rms, metrics.difference_peak);
}

static void run_overwritten_early_pair(const EffectDescriptor& descriptor, RateMode mode) {
    EffectRegistry registry;
    ValidatedEffectPackage package;
    package.descriptor=descriptor;
    package.validation_receipt_valid=package.initialization_state_valid=true;
    package.program_identity_valid=package.pipeline_reset_valid=package.routing_valid=true;
    std::string error;
    if(!registry.register_validated(package,&error))throw std::runtime_error(error);
    const auto* accepted=registry.find(1);
    FactoryRuntime a,b;
    if(!a.loadEffect(*accepted,mode)||!b.loadEffect(*accepted,mode))
        throw std::runtime_error("validated HALL package load failed");
    const std::array<std::array<std::uint8_t,2>,5> regs{{
        {{0x6e,0x00}},{{0x5b,0x00}},{{0x03,0x00}},{{0x04,0x00}},{{0x05,0x00}}}};
    const std::array<std::uint32_t,5> group40{{0x330000,0x080033,0x330000,0xcd0000,0x6badff}};
    const std::array<std::uint32_t,5> group41{{0x350000,0x080035,0x350000,0xcb0000,0x6a0dff}};
    for(std::size_t i=0;i<regs.size();++i){
        if(!a.setRegister(regs[i][0],group40[i],0)||!b.setRegister(regs[i][0],group41[i],0))
            throw std::runtime_error("test-only early GPR write was rejected");
    }
    const auto terminal=1+std::max_element(descriptor.firmware_event_schedule.begin(),
        descriptor.firmware_event_schedule.end(),[](const auto&x,const auto&y){return x.relative_dsp_frame<y.relative_dsp_frame;})->relative_dsp_frame;
    const double host_rate=48000.0;
    std::size_t host_a=0,host_b=0;
    auto silence_to=[&](FactoryRuntime& runtime,std::size_t& host){
        std::array<float,512> zeros{},out{};
        while(runtime.getStatus().processed_dsp_frames<terminal){
            const auto before=runtime.getStatus().processed_dsp_frames;
            if(!runtime.processStereo(zeros.data(),out.data(),256,host_rate))
                throw std::runtime_error("startup silence processing failed");
            host+=256;
            if(runtime.getStatus().processed_dsp_frames==before)
                throw std::runtime_error("host-rate stepping made no DSP progress");
        }
    };
    silence_to(a,host_a);silence_to(b,host_b);
    if(a.getStatus().scheduled_writes_applied!=descriptor.firmware_event_schedule.size()+5||
       b.getStatus().scheduled_writes_applied!=descriptor.firmware_event_schedule.size()+5)
        throw std::runtime_error("legacy early test did not execute the full schedule and five early writes");
    const auto sa=a.getStatus(),sb=b.getStatus();
    std::printf("PAIR mode=%s timing=legacy-early-overwritten completion_frame=%llu\n",
        mode==RateMode::Experimental48000?"experimental-48000":"factory-reference",
        static_cast<unsigned long long>(terminal));
    std::printf("INIT owner=A complete=%d frame=%llu firmware_pending=%u parameter_pending=%u\n",
        sa.initialization_schedule_complete,static_cast<unsigned long long>(sa.processed_dsp_frames),
        sa.firmware_writes_pending,sa.parameter_writes_pending);
    std::printf("INIT owner=B complete=%d frame=%llu firmware_pending=%u parameter_pending=%u\n",
        sb.initialization_schedule_complete,static_cast<unsigned long long>(sb.processed_dsp_frames),
        sb.firmware_writes_pending,sb.parameter_writes_pending);
    print_registers("legacy-A-after-startup",terminal,0xff,0,a);
    print_registers("legacy-B-after-startup",terminal,0xff,0,b);
    auto metrics=render_pair(a,b,host_a,host_b,host_rate);
    std::printf("WET mode=%s timing=legacy-early-overwritten frames=65536 finite=%zu rms40=%.9g rms41=%.9g difference_rms=%.9g difference_peak=%.9g\n",
        mode==RateMode::Experimental48000?"experimental-48000":"factory-reference",
        metrics.finite_samples,metrics.rms40,metrics.rms41,metrics.difference_rms,metrics.difference_peak);
}

int main(int argc, char** argv) try {
    if (argc != 6) throw std::runtime_error("usage: hall_startup_ownership CHECKPOINT SCHEDULE.csv PROGRAM_SHA CHECKPOINT_SHA FACTORY_RATE");
    const auto descriptor = read_descriptor(argv[1], argv[2], argv[3], argv[4], std::stod(argv[5]));
    run_pair(descriptor, RateMode::Experimental48000, true);
    run_pair(descriptor, RateMode::Experimental48000, false);
    run_overwritten_early_pair(descriptor,RateMode::Experimental48000);
    run_pair(descriptor, RateMode::FactoryReference, true);
    run_pair(descriptor, RateMode::FactoryReference, false);
    run_overwritten_early_pair(descriptor,RateMode::FactoryReference);
    return 0;
} catch (const std::exception& error) {
    std::fprintf(stderr, "hall startup ownership QA failed: %s\n", error.what());
    return 1;
}
