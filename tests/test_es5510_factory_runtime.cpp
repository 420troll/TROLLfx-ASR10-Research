#include "trollfx/es5510_factory_runtime.hpp"
#include "trollfx/es5510_factory_parameter_discovery_v02.hpp"
#include "trollfx/es5510_factory_parameter_discovery_v03.hpp"
#include "es5510.h"

#include <array>
#include <atomic>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <filesystem>
#include <new>
#include <string>
#include <vector>

using namespace trollfx::es5510;
static std::atomic<bool> watch_allocations{false};
static std::atomic<unsigned> callback_allocations{0};
void* operator new(std::size_t n) {
    if (watch_allocations.load(std::memory_order_relaxed)) callback_allocations.fetch_add(1,std::memory_order_relaxed);
    if (void* p=std::malloc(n)) return p;
    throw std::bad_alloc();
}
void* operator new[](std::size_t n) {
    if (watch_allocations.load(std::memory_order_relaxed)) callback_allocations.fetch_add(1,std::memory_order_relaxed);
    if (void* p=std::malloc(n)) return p;
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p,std::size_t) noexcept { std::free(p); }
void operator delete[](void* p,std::size_t) noexcept { std::free(p); }

static std::string make_checkpoint(unsigned words) {
    const auto path = (std::filesystem::temp_directory_path() /
        ("es5510-runtime-synthetic-" + std::to_string(words) + ".esp")).string();
    ES5510 dsp;
    for (unsigned i = 0; i < words; ++i) {
        const std::uint64_t instruction = i + 1 == words ? 0x00000000f000ULL
            : i == 0 ? ((std::uint64_t(239) << 24) | (std::uint64_t(237) << 16) | 0x9000ULL)
            : i == 1 ? ((std::uint64_t(238) << 24) | (std::uint64_t(236) << 16) | 0x9000ULL)
            : 0;
        for (unsigned b = 0; b < 6; ++b)
            dsp.host_w(3 + b, static_cast<std::uint8_t>(instruction >> (40 - 8 * b)));
        dsp.host_w(0xc0, static_cast<std::uint8_t>(i));
    }
    dsp.host_w(0x18, 0x48); // captured route mode used by the factory profiles
    FILE* f = std::fopen(path.c_str(), "wb");
    assert(f && dsp.write_capture(f));
    std::fclose(f);
    return path;
}

static EffectPackage package(EffectId id, const std::string& path) {
    if (id == EffectId::Rom01Hall)
        return {id, path, 89, 29761.89453125, true, true, true};
    return {id, path, 60, 44100.0, true, true, true};
}

static ValidatedEffectPackage generic_package(std::uint8_t slot, unsigned words, const std::string& path) {
    ValidatedEffectPackage p;
    p.validation_receipt_valid = p.initialization_state_valid = p.program_identity_valid =
        p.pipeline_reset_valid = p.routing_valid = true;
    auto& d=p.descriptor;
    d.slot=slot; d.factory_name="synthetic-slot"; d.active_program_words=words;
    d.end_word=words-1; d.program_sha256=std::string(64,'a');
    d.factory_reference_rate_hz=32000.0 + slot;
    d.routing.host_serial_mode=0x48; d.routing.input_port=2; d.routing.output_port=1;
    d.run_checkpoint_path=path; d.run_checkpoint_sha256=std::string(64,'b');
    d.firmware_event_schedule.push_back({0,0x20,0x123456});
    VerifiedParameterDefinition parameter; parameter.id="test"; parameter.ui_label="Test";
    ParameterPoint single; single.display_value=7; single.gpr=0x21; single.value24=0x654321;
    parameter.verified_points.push_back(single); d.parameters.push_back(parameter);
    VerifiedParameterDefinition grouped; grouped.id="group"; grouped.ui_label="Group";
    ParameterPoint group_point; group_point.display_value=3;
    group_point.ordered_writes={{0x22,0x111111},{0x23,0x222222}};
    grouped.verified_points.push_back(group_point); d.parameters.push_back(grouped);
    return p;
}

static std::vector<float> render(FactoryRuntime& fx, const std::vector<float>& input,
                                 const std::vector<std::size_t>& blocks, double rate=48000.0) {
    std::vector<float> output(input.size(), 0.0f);
    std::size_t offset=0, bi=0;
    while (offset < input.size()/2) {
        const std::size_t n=std::min(blocks[bi++ % blocks.size()], input.size()/2-offset);
        const unsigned before=callback_allocations.load();
        watch_allocations.store(true);
        const bool ok=fx.processStereo(input.data()+2*offset, output.data()+2*offset, n, rate);
        watch_allocations.store(false);
        assert(ok);
        assert(callback_allocations.load()==before);
        offset += n;
    }
    return output;
}

int main() {
    const auto hall_path = make_checkpoint(89);
    const auto rom02_path = make_checkpoint(60);
    const auto short_path = make_checkpoint(3);
    const auto long_path = make_checkpoint(160);
    {
        FactoryRuntime fx;
        auto bad=package(EffectId::Rom01Hall,hall_path); bad.pipeline_reset_acknowledged=false;
        assert(!fx.loadEffect(bad));
        assert(fx.getStatus().code==StatusCode::PackageRejected);
        assert(fx.loadEffect(package(EffectId::Rom01Hall,hall_path)));
        assert(fx.getStatus().active_program_words==89);
        assert(fx.getStatus().processing_rate_hz==48000.0);
        assert(fx.setRegister(0x20,0x123456,0));
        assert(!fx.setRegister(0xc0,0,0));
        assert(!fx.setRegister(0x20,0x1000000,0));

        constexpr std::size_t frames=4097;
        std::vector<float> input(frames*2);
        std::uint32_t rng=0x12345678;
        for (std::size_t i=0;i<frames;++i) {
            switch ((i/513)%5) {
            case 0: input[2*i]=input[2*i+1]=0.0f; break; // silence
            case 1: input[2*i]=input[2*i+1]=(i==513?0.8f:0.0f); break; // impulse
            case 2: input[2*i]=input[2*i+1]=0.5f*std::sin(2.0*3.141592653589793*997.0*i/48000.0); break;
            case 3: input[2*i]=0.25f; input[2*i+1]=-0.25f; break; // stereo polarity
            default:
                rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
                input[2*i]=static_cast<float>(static_cast<std::int32_t>(rng))/2147483648.0f*0.2f;
                rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
                input[2*i+1]=static_cast<float>(static_cast<std::int32_t>(rng))/2147483648.0f*0.2f;
            }
        }
        const auto one_block=render(fx,input,{frames});
        assert(fx.getStatus().scheduled_writes_applied==1);
        assert(fx.reset());
        assert(fx.setRegister(0x20,0x123456,0));
        const auto variable=render(fx,input,{1,7,64,128,256,512,1024});
        assert(one_block==variable);
        auto st=fx.getStatus();
        assert(st.processed_dsp_frames==frames);
        assert(st.scheduled_writes_applied==1);
        assert(!fx.setRegister(0x20,1,st.processed_dsp_frames-1));
        assert(fx.reset());
        assert(fx.setProcessingRate(RateMode::FactoryReference));
        const auto factory_one=render(fx,input,{frames});
        assert(fx.reset());
        const auto factory_partitioned=render(fx,input,{1,7,64,128,256,512,1024});
        assert(factory_one==factory_partitioned);
        assert(fx.reset());
        assert(fx.setProcessingRate(RateMode::Experimental48000));
        const auto low_host_one=render(fx,input,{frames},32000.0);
        assert(fx.reset());
        const auto low_host_partitioned=render(fx,input,{1,7,64,128,256,512,1024},32000.0);
        assert(low_host_one==low_host_partitioned);
        for (std::size_t i=3;i<frames;++i) {
            assert(std::fabs(one_block[2*i]-input[2*(i-2)])<1.0f/32768.0f);
            assert(std::fabs(one_block[2*i+1]-input[2*(i-2)+1])<1.0f/32768.0f);
        }
        assert(fx.reset());
        assert(fx.getStatus().scheduled_writes_applied==0);
        assert(fx.setProcessingRate(RateMode::FactoryReference));
        assert(std::fabs(fx.getStatus().processing_rate_hz-29761.89453125)<0.001);
        assert(fx.reset());
        assert(fx.setRegister(0x21,0x654321,3));
        std::array<float,14> four_in{},four_out{};
        assert(fx.processStereo(four_in.data(),four_out.data(),5,48000.0));
        assert(fx.getStatus().scheduled_writes_applied==0);
        assert(fx.processStereo(four_in.data()+10,four_out.data()+10,1,48000.0));
        assert(fx.getStatus().scheduled_writes_applied==0);
        assert(fx.processStereo(four_in.data()+12,four_out.data()+12,1,48000.0));
        assert(fx.getStatus().scheduled_writes_applied==1);
        assert(!fx.setRegister(0x21,0,3));
        assert(fx.loadEffect(package(EffectId::Rom02Reverb44k,rom02_path),RateMode::FactoryReference));
        assert(fx.getStatus().effect==EffectId::Rom02Reverb44k);
        assert(fx.getStatus().active_program_words==60);
        assert(fx.getStatus().processing_rate_hz==44100.0);
    }
    {
        FactoryRuntime fx;
        assert(fx.loadEffect(package(EffectId::Rom02Reverb44k,rom02_path),RateMode::FactoryReference));
        std::array<float,2*1024> in{},out{};
        for (std::size_t i=0;i<in.size()/2;++i) {
            in[2*i]=0.2f*std::sin(2.0*3.141592653589793*431.0*i/48000.0);
            in[2*i+1]=-in[2*i];
        }
        for (std::size_t n : {1u,7u,64u,128u,256u,512u,1024u}) {
            assert(fx.reset());
            assert(fx.processStereo(in.data(),out.data(),n,48000.0));
            assert(fx.getStatus().processed_dsp_frames==static_cast<std::uint64_t>(std::floor(n*44100.0/48000.0 + 1e-9)));
        }
    }
    {
        EffectRegistry registry;
        auto short_package=generic_package(17,3,short_path);
        auto long_package=generic_package(50,160,long_path);
        assert(registry.register_validated(short_package));
        assert(registry.register_validated(long_package));
        assert(registry.size()==2 && registry.find(50));
        FactoryRuntime fx;
        assert(fx.loadEffect(*registry.find(17),RateMode::FactoryReference));
        assert(fx.getStatus().active_program_words==3);
        assert(fx.setParameter(short_package.descriptor,"test",7,0));
        assert(fx.setParameter(short_package.descriptor,"group",3,0));
        assert(!fx.setParameter(short_package.descriptor,"test",8,0));
        std::array<float,4> in{},out{};
        assert(fx.processStereo(in.data(),out.data(),2,32000.0));
        assert(fx.getStatus().scheduled_writes_applied==4); // firmware init + single + ordered two-register group
        assert(fx.loadEffect(*registry.find(50)));
        assert(fx.getStatus().active_program_words==160);
        auto invalid=generic_package(16,60,rom02_path); invalid.descriptor.routing.input_port=4;
        assert(!registry.register_validated(invalid));
        auto large_schedule=generic_package(49,3,short_path);
        for(std::uint64_t i=0;i<600;++i)
            large_schedule.descriptor.firmware_event_schedule.push_back({i/2,static_cast<std::uint8_t>(i%0x40),static_cast<std::uint32_t>(i&0xffffff)});
        assert(registry.register_validated(large_schedule));
        FactoryRuntime scheduled;
        assert(scheduled.loadEffect(*registry.find(49),RateMode::FactoryReference));
        std::array<float,2*2048> scheduled_in{},scheduled_out{};
        assert(scheduled.processStereo(scheduled_in.data(),scheduled_out.data(),2048,48000.0));
        assert(scheduled.getStatus().scheduled_writes_applied==601); // includes the package's frame-zero initialization write
        auto overflow=generic_package(48,3,short_path);
        for(std::uint64_t i=0;i<1025;++i)
            overflow.descriptor.firmware_event_schedule.push_back({i,static_cast<std::uint8_t>(i%0x40),0});
        assert(!registry.register_validated(overflow));

        auto near_full=generic_package(47,3,short_path);
        near_full.descriptor.firmware_event_schedule.clear();
        for (std::uint64_t i=0;i<1023;++i)
            near_full.descriptor.firmware_event_schedule.push_back({0,static_cast<std::uint8_t>(i%0x40),static_cast<std::uint32_t>(i&0xffffff)});
        EffectRegistry full_registry;
        assert(full_registry.register_validated(near_full));
        FactoryRuntime full_runtime;
        assert(full_runtime.loadEffect(*full_registry.find(47),RateMode::FactoryReference));
        assert(!full_runtime.setParameter(near_full.descriptor,"group",3,100)); // group must fail atomically
        assert(full_runtime.setParameter(near_full.descriptor,"test",7,100)); // the one free slot is still available
        std::vector<float> full_in(2*101),full_out(2*101);
        assert(full_runtime.processStereo(full_in.data(),full_out.data(),101,32017.0));
        assert(full_runtime.getStatus().scheduled_writes_applied==1024);
    }
    {
        const std::array<std::uint8_t,13> slots{{1,2,3,4,5,6,7,8,28,39,41,42,49}};
        std::size_t supported_controls=0;
        for (auto slot : slots) {
            auto definition=generic_package(slot,3,short_path);
            const bool has_v2 = parameter_discovery_v02::append_verified_parameters(definition.descriptor);
            assert(has_v2 == (slot==1 || slot==2 || slot==3 || slot==4 || slot==6 ||
                              slot==7 || slot==28 || slot==41 || slot==42 || slot==49));
            assert(parameter_discovery_v03::append_verified_parameters(definition.descriptor) ==
                   (slot==5 || slot==8 || slot==39));
            assert(!definition.descriptor.parameters.empty());
            for (const auto& parameter : definition.descriptor.parameters) {
                if (parameter.id=="test" || parameter.id=="group") continue;
                ++supported_controls;
                FactoryRuntime runtime;
                assert(runtime.loadEffect(definition,RateMode::FactoryReference));
                assert(runtime.setParameter(definition.descriptor,parameter.id,
                                            parameter.verified_points[1].display_value,0));
                std::array<float,4> in{},out{};
                assert(runtime.processStereo(in.data(),out.data(),2,48000.0));
                const auto writes=parameter.verified_points[1].ordered_writes.empty()
                    ? 1u : static_cast<unsigned>(parameter.verified_points[1].ordered_writes.size());
                assert(runtime.getStatus().scheduled_writes_applied==1+writes);
                assert(std::isfinite(out[0]) && std::isfinite(out[1]));
            }
        }
        assert(supported_controls==19);
    }
    {
        auto hall = generic_package(1,3,short_path);
        assert(parameter_discovery_v02::append_verified_parameters(hall.descriptor));
        auto decay = std::find_if(hall.descriptor.parameters.begin(),hall.descriptor.parameters.end(),
            [](const auto& p){return p.id=="decay_time";});
        assert(decay!=hall.descriptor.parameters.end());
        assert(decay->verified_points.size()==2);
        assert(decay->verified_points[1].display_value==41);
        assert(decay->verified_points[1].ordered_writes.size()==5);
        assert(decay->verified_points[1].ordered_writes[0].gpr==0x03);
        assert(decay->verified_points[1].ordered_writes[4].gpr==0x6e);
        EffectRegistry registry;
        assert(registry.register_validated(hall));
        FactoryRuntime fx;
        assert(fx.loadEffect(*registry.find(1),RateMode::FactoryReference));
        assert(fx.setParameter(hall.descriptor,"decay_time",41,0));
        std::array<float,4> in{},out{};
        assert(fx.processStereo(in.data(),out.data(),2,48000.0));
        assert(fx.getStatus().scheduled_writes_applied==6); // package init + five ordered writes
        auto chorus=generic_package(6,3,short_path);
        assert(parameter_discovery_v02::append_verified_parameters(chorus.descriptor));
        auto rate=std::find_if(chorus.descriptor.parameters.begin(),chorus.descriptor.parameters.end(),
            [](const auto& p){return p.id=="chorus_rate";});
        assert(rate!=chorus.descriptor.parameters.end());
        assert(rate->verified_points[0].ordered_writes.size()==3);
        assert(rate->verified_points[1].display_value==25);
        auto pitch=generic_package(41,3,short_path);
        assert(parameter_discovery_v02::append_verified_parameters(pitch.descriptor));
        auto fine=std::find_if(pitch.descriptor.parameters.begin(),pitch.descriptor.parameters.end(),
            [](const auto& p){return p.id=="voice1_fine";});
        assert(fine!=pitch.descriptor.parameters.end());
        assert(fine->verified_points[0].display_text=="-11");
        assert(fine->verified_points[1].display_value==-10);
    }
    std::filesystem::remove(hall_path);
    std::filesystem::remove(rom02_path);
    std::filesystem::remove(short_path);
    std::filesystem::remove(long_path);
    std::puts("ES5510 runtime synthetic tests: PASS");
}
