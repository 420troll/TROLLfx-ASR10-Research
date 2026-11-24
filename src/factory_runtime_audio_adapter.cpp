#include "factory_runtime_audio_adapter.h"
#include "es5510.h"

#include <algorithm>
#include <array>
#include <charconv>
#include <cerrno>
#include <cmath>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>

namespace trollfx::audio {
namespace {
using trollfx::es5510::EffectId;
using trollfx::es5510::RateMode;
using trollfx::es5510::factory_parameters_v01::FactoryEffect;
using trollfx::es5510::factory_parameters_v01::Parameter;
using trollfx::es5510::factory_parameters_v01::EncodeStatus;

bool verify_with_python(const std::string& script, const char* effect,
                        const PrivateFactoryPackagePaths& p) {
    if (script.empty() || p.manifest.empty() || p.checkpoint.empty() || p.two_boot_reference_root.empty() || p.post_run_events.empty())
        throw std::runtime_error(std::string("runtime requires manifest, checkpoint, two-boot reference root, post-RUN schedule, and package validator (effect=")+effect+
            " manifest="+(p.manifest.empty()?"missing":"set")+" checkpoint="+(p.checkpoint.empty()?"missing":"set")+
            " references="+(p.two_boot_reference_root.empty()?"missing":"set")+" events="+(p.post_run_events.empty()?"missing":"set")+" validator="+(script.empty()?"missing":"set")+")");
    const pid_t child = fork();
    if (child < 0) throw std::runtime_error("could not start private package validator");
    if (child == 0) {
        std::vector<char*> args;
        args.push_back(const_cast<char*>("python3"));
        args.push_back(const_cast<char*>(script.c_str()));
        args.push_back(const_cast<char*>("--effect")); args.push_back(const_cast<char*>(effect));
        args.push_back(const_cast<char*>("--manifest")); args.push_back(const_cast<char*>(p.manifest.c_str()));
        args.push_back(const_cast<char*>("--checkpoint")); args.push_back(const_cast<char*>(p.checkpoint.c_str()));
        args.push_back(const_cast<char*>("--reference-root")); args.push_back(const_cast<char*>(p.two_boot_reference_root.c_str()));
        args.push_back(const_cast<char*>("--events")); args.push_back(const_cast<char*>(p.post_run_events.c_str()));
        args.push_back(nullptr);
        execvp("python3", args.data());
        _exit(127);
    }
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
        if (errno == EINTR) continue;
        throw std::runtime_error("waiting for private package validator failed");
    }
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
        throw std::runtime_error(std::string(effect) + " private factory package validation failed; runtime flags were not set");
    return true;
}

EffectId core_effect(Effect e) { return e == Effect::Hall ? EffectId::Rom01Hall : EffectId::Rom02Reverb44k; }
FactoryEffect parameter_effect(Effect e) { return e == Effect::Hall ? FactoryEffect::Rom01Hall : FactoryEffect::Rom02Reverb44k; }
}

FactoryRuntimeProcessor::FactoryRuntimeProcessor(PrivateFactoryPackagePaths hall,
        PrivateFactoryPackagePaths rom02, std::string validator_script)
    : packages_{validate_and_make(Effect::Hall,hall,validator_script),
                validate_and_make(Effect::Rom02,rom02,validator_script)} {
    const PrivateFactoryPackagePaths* paths[2]={&hall,&rom02};
    const std::uint64_t run_frames[2]={855973,905028};
    for(unsigned e=0;e<2;++e){
        std::ifstream in(paths[e]->post_run_events);
        std::string line;
        if(!std::getline(in,line))
            throw std::runtime_error("private post-RUN firmware schedule has an unexpected header");
        if(!line.empty()&&line.back()=='\r')line.pop_back();
        if(line!="boundary_frame,event_id,cpu_cycles,dsp_frame,host_pc,index,value")
            throw std::runtime_error("private post-RUN firmware schedule has an unexpected header");
        while(std::getline(in,line)){
            if(!line.empty()&&line.back()=='\r')line.pop_back();
            if(line.empty())continue;
            std::array<std::string,7> f{};size_t pos=0;
            for(unsigned i=0;i<6;++i){auto comma=line.find(',',pos);if(comma==std::string::npos)throw std::runtime_error("malformed private firmware schedule");f[i]=line.substr(pos,comma-pos);pos=comma+1;}f[6]=line.substr(pos);
            auto parse=[](const std::string&s,int base)->std::uint64_t{std::uint64_t x=0;auto r=std::from_chars(s.data(),s.data()+s.size(),x,base);if(r.ec!=std::errc{}||r.ptr!=s.data()+s.size())throw std::runtime_error("invalid private firmware schedule field");return x;};
            const auto absolute=parse(f[0],10),index=parse(f[5],16),value=parse(f[6],16);
            if(absolute<run_frames[e]||absolute-run_frames[e]>32768||index>0xbf||value>0xffffff)throw std::runtime_error("private firmware schedule is outside validated RUN bounds");
            firmware_writes_[e].push_back({absolute-run_frames[e],static_cast<std::uint8_t>(index),static_cast<std::uint32_t>(value)});
        }
        const size_t expected=e==0?213:202;
        if(!in.eof()||firmware_writes_[e].size()!=expected)throw std::runtime_error("private post-RUN firmware schedule count is not validated");
    }
}

trollfx::es5510::EffectPackage FactoryRuntimeProcessor::validate_and_make(
        Effect effect, const PrivateFactoryPackagePaths& p, const std::string& validator) {
    const char* name = effect == Effect::Hall ? "hall" : "rom02";
    (void)verify_with_python(validator,name,p);
    const bool hall = effect == Effect::Hall;
    return {core_effect(effect),p.checkpoint,hall?89u:60u,
            hall?29761.89453125:44100.0,
            true,  // set only after the validator confirms the recorded pipeline reset
            true,  // set only after manifest, digest, source identity, and two-boot checks pass
            true}; // set only after manifest/log routing evidence confirms SER2 -> SER1
}

void FactoryRuntimeProcessor::prepare(Effect effect, uint32_t dsp_rate) {
    if (dsp_rate != 48000) throw std::invalid_argument("runtime adapter currently requires experimental 48 kHz DSP mode");
    if (!runtime_.loadEffect(packages_[static_cast<unsigned>(effect)],RateMode::Experimental48000))
        throw std::runtime_error(std::string("native ES5510 checkpoint load failed: ")+runtime_.getStatus().message);
    for(const auto&w:firmware_writes_[static_cast<unsigned>(effect)])
        if(!runtime_.setRegister(w.index,w.value,w.frame))
            throw std::runtime_error("native ES5510 rejected validated post-RUN firmware schedule");
    active_effect_ = effect;
    prepared_ = true;
    process_error_ = false;
}

void FactoryRuntimeProcessor::process(const float* input,float* output,size_t frames) noexcept {
    if (!prepared_ || !output || (!input && frames)) {
        if (output) std::fill(output,output+frames*2,0.0f);
        process_error_ = true;
        return;
    }
    if (!runtime_.processStereo(input,output,frames,48000.0)) {
        std::fill(output,output+frames*2,0.0f);
        process_error_ = true;
    }
}

uint32_t FactoryRuntimeProcessor::latency_frames() const noexcept {
    return prepared_ ? runtime_.getStatus().algorithmic_latency_host_frames : 0;
}

size_t FactoryRuntimeProcessor::memory_bytes() const noexcept {
    // Dominant persistent allocation is the native core's 1 Miword int16 DRAM;
    // 128 KiB covers program, decode, event, and interpolation state approximately.
    return ES5510::DRAM_SIZE*sizeof(std::int16_t)+128u*1024u;
}

void RegistryFactoryRuntimeProcessor::prepare(Effect effect, uint32_t dsp_rate) {
    const auto index=static_cast<unsigned>(effect);
    if(index>=50) throw std::invalid_argument("factory effect selection must be in slot range 1..50");
    const auto* package=registry_.find(static_cast<trollfx::es5510::EffectSlot>(index+1));
    if(!package) throw std::runtime_error("selected factory effect package is not installed");
    const auto mode=dsp_rate==48000 ? trollfx::es5510::RateMode::Experimental48000
                                    : trollfx::es5510::RateMode::FactoryReference;
    if(dsp_rate!=48000 && std::abs(package->descriptor.factory_reference_rate_hz-dsp_rate)>0.5)
        throw std::invalid_argument("requested DSP rate does not match installed factory reference rate");
    if(!runtime_.loadEffect(*package,mode))
        throw std::runtime_error(std::string("native ES5510 package load failed: ")+runtime_.getStatus().message);
    prepared_=true;
}

void RegistryFactoryRuntimeProcessor::process(const float* input,float* output,size_t frames) noexcept {
    if(!prepared_ || !output || (!input && frames) || !runtime_.processStereo(input,output,frames,48000.0)) {
        if(output) std::fill(output,output+frames*2,0.0f);
    }
}

uint32_t RegistryFactoryRuntimeProcessor::latency_frames() const noexcept {
    return prepared_ ? runtime_.getStatus().algorithmic_latency_host_frames : 0;
}

size_t RegistryFactoryRuntimeProcessor::memory_bytes() const noexcept {
    return ES5510::DRAM_SIZE*sizeof(std::int16_t)+128u*1024u;
}

EncodeStatus FactoryRuntimeProcessor::set_bus_parameter(Effect effect,Parameter parameter,int display_value) {
    if (!prepared_ || effect != active_effect_) return EncodeStatus::RuntimeRejected;
    return trollfx::es5510::factory_parameters_v01::schedule(
        runtime_,parameter_effect(effect),parameter,display_value,runtime_.getStatus().processed_dsp_frames);
}

const char* FactoryRuntimeProcessor::status_message() const noexcept {
    return process_error_ ? "runtime processing failed; output was silenced" : runtime_.getStatus().message;
}

} // namespace trollfx::audio
