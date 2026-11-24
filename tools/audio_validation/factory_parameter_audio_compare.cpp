#include "trollfx/es5510_factory_runtime.hpp"
#include "trollfx/es5510_factory_parameter_discovery_v02.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace trollfx::es5510;

static void u16(std::ofstream& f, std::uint16_t x) { f.put(char(x)); f.put(char(x >> 8)); }
static void u32(std::ofstream& f, std::uint32_t x) { for (int i=0;i<4;++i) f.put(char(x >> (8*i))); }
static void write_wav(const std::string& path, const std::vector<float>& pcm) {
    std::ofstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot create output WAV: " + path);
    const auto bytes=static_cast<std::uint32_t>(pcm.size()*2);
    f.write("RIFF",4); u32(f,36+bytes); f.write("WAVEfmt ",8); u32(f,16);
    u16(f,1); u16(f,2); u32(f,48000); u32(f,48000*4); u16(f,4); u16(f,16);
    f.write("data",4); u32(f,bytes);
    for(float x:pcm) {
        const float c=std::max(-1.0f,std::min(1.0f,x));
        const auto v=static_cast<std::int16_t>(std::lround(c*32767.0f));
        u16(f,static_cast<std::uint16_t>(v));
    }
}

static std::vector<float> input_signal(std::size_t frames, std::size_t offset) {
    std::vector<float> x(frames*2);
    for (std::size_t i=0;i<frames;++i) {
        const auto n=offset+i;
        float l=0.20f*std::sin(2.0*3.141592653589793*431.0*n/48000.0);
        float r=0.17f*std::sin(2.0*3.141592653589793*997.0*n/48000.0);
        if (n==0) { l+=0.7f; r-=0.4f; }
        x[2*i]=l; x[2*i+1]=r;
    }
    return x;
}

static void warm(FactoryRuntime& fx) {
    constexpr std::size_t frames=32768, block=256;
    for (std::size_t offset=0;offset<frames;offset+=block) {
        auto in=input_signal(block,offset);
        std::vector<float> out(block*2);
        if (!fx.processStereo(in.data(),out.data(),block,48000.0))
            throw std::runtime_error(fx.getStatus().message);
    }
}

static std::vector<float> render_tail(FactoryRuntime& fx) {
    constexpr std::size_t frames=8192, block=256;
    std::vector<float> out(frames*2);
    for (std::size_t offset=0;offset<frames;offset+=block) {
        auto in=input_signal(block,32768+offset);
        if (!fx.processStereo(in.data(),out.data()+offset*2,block,48000.0))
            throw std::runtime_error(fx.getStatus().message);
    }
    return out;
}

int main(int argc,char**argv) try {
    if (argc!=13) throw std::runtime_error("usage: compare SLOT NAME WORDS PROGRAM_SHA CHECKPOINT CHECKPOINT_SHA RATE SCHEDULE.csv PARAM_ID VALUE_A VALUE_B OUTPUT_PREFIX");
    EffectDescriptor d;
    d.slot=static_cast<EffectSlot>(std::stoul(argv[1])); d.factory_name=argv[2];
    d.active_program_words=static_cast<std::uint32_t>(std::stoul(argv[3])); d.end_word=d.active_program_words-1;
    d.program_sha256=argv[4]; d.run_checkpoint_path=argv[5]; d.run_checkpoint_sha256=argv[6];
    d.factory_reference_rate_hz=std::stod(argv[7]); d.routing={0x48,2,1,true};
    std::ifstream schedule(argv[8]); std::string line;
    if (!std::getline(schedule,line)) throw std::runtime_error("firmware event schedule is empty");
    while (std::getline(schedule,line)) {
        std::stringstream ss(line); std::string frame,event,cycles,gpr,value;
        std::getline(ss,frame,','); std::getline(ss,event,','); std::getline(ss,cycles,',');
        std::getline(ss,gpr,','); std::getline(ss,value,',');
        d.firmware_event_schedule.push_back({std::stoull(frame),static_cast<std::uint8_t>(std::stoul(gpr,nullptr,16)),static_cast<std::uint32_t>(std::stoul(value,nullptr,16))});
    }
    if (!parameter_discovery_v02::append_verified_parameters(d)) throw std::runtime_error("slot has no V2 recovered controls");
    ValidatedEffectPackage p; p.descriptor=std::move(d);
    // The invoking Python wrapper independently checks audit eligibility and
    // checkpoint/schedule hashes before calling this private-package utility.
    p.validation_receipt_valid=p.initialization_state_valid=p.program_identity_valid=p.pipeline_reset_valid=p.routing_valid=true;
    EffectRegistry registry; std::string error;
    if (!registry.register_validated(std::move(p),&error)) throw std::runtime_error("registry rejected package: "+error);
    const auto* accepted=registry.find(static_cast<EffectSlot>(std::stoul(argv[1])));
    FactoryRuntime a,b;
    if (!a.loadEffect(*accepted,RateMode::Experimental48000) || !b.loadEffect(*accepted,RateMode::Experimental48000))
        throw std::runtime_error("factory package load failed");
    warm(a); warm(b);
    const auto frame=a.getStatus().processed_dsp_frames;
    if (frame!=b.getStatus().processed_dsp_frames) throw std::runtime_error("warmup frame counts differ");
    if (!a.setParameter(accepted->descriptor,argv[9],std::stoi(argv[10]),frame) ||
        !b.setParameter(accepted->descriptor,argv[9],std::stoi(argv[11]),frame))
        throw std::runtime_error("runtime rejected verified point: "+std::string(a.getStatus().message)+" / "+b.getStatus().message);
    auto before=render_tail(a),after=render_tail(b);
    double eb=0,ea=0,ed=0; float peakb=0,peaka=0,peakd=0; std::size_t finite=0;
    for (std::size_t i=0;i<before.size();++i) {
        if (!std::isfinite(before[i]) || !std::isfinite(after[i])) continue;
        ++finite; eb+=double(before[i])*before[i]; ea+=double(after[i])*after[i];
        const float delta=after[i]-before[i]; ed+=double(delta)*delta;
        peakb=std::max(peakb,std::fabs(before[i])); peaka=std::max(peaka,std::fabs(after[i])); peakd=std::max(peakd,std::fabs(delta));
    }
    if (finite!=before.size()) throw std::runtime_error("non-finite output samples");
    const std::string prefix=argv[12]; write_wav(prefix+"-before.wav",before); write_wav(prefix+"-after.wav",after);
    std::cout<<"slot="<<unsigned(accepted->descriptor.slot)<<" parameter="<<argv[9]
             <<" values="<<argv[10]<<"->"<<argv[11]<<" frames="<<before.size()/2
             <<" finite="<<finite<<" rms_before="<<std::sqrt(eb/finite)<<" rms_after="<<std::sqrt(ea/finite)
             <<" difference_rms="<<std::sqrt(ed/finite)<<" difference_peak="<<peakd
             <<" peak_before="<<peakb<<" peak_after="<<peaka<<"\n";
    return 0;
} catch (const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
