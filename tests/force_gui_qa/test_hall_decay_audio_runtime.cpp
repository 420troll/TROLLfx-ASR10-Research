#include "trollfx/es5510_factory_runtime.hpp"
#include "es5510.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace trollfx::es5510;

struct Metrics {
    std::size_t frames = 0;
    std::size_t finite = 0;
    double sum_l = 0, sum_r = 0, sum_diff = 0;
    float peak = 0, max_step = 0;
    std::uint64_t hash = 1469598103934665603ULL;
    std::vector<double> rms_windows;
};
using Group = std::array<std::uint32_t,5>; // 6E, 5B, 03, 04, 05

static constexpr double kRate = 29761.89453125;
static constexpr std::array<std::uint8_t,5> kRegs{0x6e,0x5b,0x03,0x04,0x05};

static void write_gpr(ES5510& dsp, std::uint8_t index, std::uint32_t value) {
    value &= 0xffffffu;
    dsp.host_w(0, static_cast<std::uint8_t>(value >> 16));
    dsp.host_w(1, static_cast<std::uint8_t>(value >> 8));
    dsp.host_w(2, static_cast<std::uint8_t>(value));
    dsp.host_w(0xa0, index);
}

static std::string seed_capture(const std::string& source, const std::string& out,
                                const Group& group) {
    ES5510 dsp;
    FILE* in = std::fopen(source.c_str(), "rb");
    if (!in || !dsp.load_capture_after_pipeline_reset(in)) throw std::runtime_error("cannot load authenticated RUN checkpoint");
    std::fclose(in);
    for (std::size_t i=0;i<kRegs.size();++i) write_gpr(dsp,kRegs[i],group[i]);
    if (dsp.register_value(0x6e) != group[0]) throw std::runtime_error("seed GPR 6E did not apply");
    FILE* f = std::fopen(out.c_str(), "wb");
    if (!f || !dsp.write_capture(f)) throw std::runtime_error("cannot write temporary seeded checkpoint");
    std::fclose(f);
    return out;
}

static std::array<Group,128> read_table(const std::string& path) {
    std::array<Group,128> table{}; std::array<bool,128> seen{};
    std::ifstream in(path); if(!in) throw std::runtime_error("cannot open OS-derived GPR matrix");
    std::string line;
    while(std::getline(in,line)) {
        std::istringstream ss(line); unsigned raw,g6e,g5b,g03,g04,g05; char comma;
        if(!(ss>>raw>>comma>>std::hex>>g6e>>comma>>g5b>>comma>>g03>>comma>>g04>>comma>>g05)) continue;
        if(raw>127) throw std::runtime_error("OS raw code out of range");
        table[raw]={g6e,g5b,g03,g04,g05}; seen[raw]=true;
    }
    for(bool x:seen) if(!x) throw std::runtime_error("OS evidence missing at least one raw code");
    return table;
}

static ValidatedEffectPackage package(const std::string& checkpoint,const std::string& schedule,
                                     const std::string& program_hash,const std::string& checkpoint_hash) {
    ValidatedEffectPackage p; auto& d=p.descriptor;
    d.slot=1; d.factory_name="HALL REVERB"; d.factory_variation=1; d.active_program_words=89; d.end_word=88;
    d.program_sha256=program_hash; d.factory_reference_rate_hz=kRate; d.routing={0x48,2,1,true};
    d.run_checkpoint_path=checkpoint; d.run_checkpoint_sha256=checkpoint_hash; d.firmware_event_schedule_path=schedule;
    std::ifstream f(schedule); std::string line; if(!std::getline(f,line))throw std::runtime_error("empty firmware schedule");
    while(std::getline(f,line)){std::istringstream ss(line);std::string frame,event,cycles,gpr,value;
        std::getline(ss,frame,',');std::getline(ss,event,',');std::getline(ss,cycles,',');std::getline(ss,gpr,',');std::getline(ss,value,',');
        d.firmware_event_schedule.push_back({std::stoull(frame),static_cast<std::uint8_t>(std::stoul(gpr,nullptr,16)),static_cast<std::uint32_t>(std::stoul(value,nullptr,16))});
    }
    p.validation_receipt_valid=p.initialization_state_valid=p.program_identity_valid=p.pipeline_reset_valid=p.routing_valid=true;
    return p;
}
static FactoryRuntime load(const std::string& checkpoint,const std::string& schedule,
                           const std::string& program_hash,const std::string& checkpoint_hash) {
    FactoryRuntime runtime;
    if(!runtime.loadEffect(package(checkpoint,schedule,program_hash,checkpoint_hash),RateMode::FactoryReference))
        throw std::runtime_error(std::string("runtime load rejected checkpoint: ")+runtime.getStatus().message);
    return runtime;
}
static FactoryRuntime load_legacy_seed(const std::string& checkpoint) {
    EffectPackage p; p.effect=EffectId::Rom01Hall; p.checkpoint_path=checkpoint;
    p.active_program_words=89; p.factory_processing_rate_hz=kRate;
    p.pipeline_reset_acknowledged=p.package_provenance_validated=p.serial_route_validated=true;
    p.factory_variation=1;
    FactoryRuntime runtime;
    if(!runtime.loadEffect(p,RateMode::FactoryReference))
        throw std::runtime_error(std::string("legacy seeded state rejected: ")+runtime.getStatus().message);
    return runtime;
}
static void set_group(FactoryRuntime& runtime,const Group& g,std::uint64_t frame) {
    for(std::size_t i=0;i<kRegs.size();++i)
        if(!runtime.setRegister(kRegs[i],g[i],frame)) throw std::runtime_error(std::string("setRegister failed: ")+runtime.getStatus().message);
}
static void settle_firmware(FactoryRuntime& runtime) {
    std::array<float,1024> in{},out{};
    if(!runtime.processStereo(in.data(),out.data(),512,kRate))
        throw std::runtime_error("firmware post-RUN settling failed");
}

static std::uint64_t noise_bits(std::uint64_t n, std::uint64_t lane) {
    std::uint64_t x=n*0x9e3779b97f4a7c15ULL + lane*0xd1b54a32d192ed03ULL + 0x5510A551ULL;
    x^=x>>30; x*=0xbf58476d1ce4e5b9ULL; x^=x>>27; x*=0x94d049bb133111ebULL; x^=x>>31;
    return x;
}
static std::pair<float,float> stimulus(std::uint64_t n,bool tail=false) {
    if(tail) return n==0?std::pair<float,float>{0.5f,-0.31f}:std::pair<float,float>{0,0};
    const auto nl=static_cast<float>((noise_bits(n,0)>>40)&0xffffff)/8388607.5f-1.0f;
    const auto nr=static_cast<float>((noise_bits(n,1)>>40)&0xffffff)/8388607.5f-1.0f;
    constexpr double tau=6.2831853071795864769;
    const double t=static_cast<double>(n)/kRate;
    return {static_cast<float>((n==0?0.40:0.0)+0.045*std::sin(tau*440*t)+0.025*nl),
            static_cast<float>((n==0?-0.27:0.0)+0.041*std::sin(tau*997*t+0.37)+0.025*nr)};
}

static Metrics render(FactoryRuntime& runtime,std::size_t frames,bool tail=false,
                      std::size_t offset=0,std::vector<float>* captured=nullptr) {
    constexpr int pattern[]={127,256,64,193}; constexpr int maxblock=256;
    std::array<float,maxblock*2> input{},output{}; Metrics m; float prev_l=0,prev_r=0; bool have=false;
    if(captured) captured->clear();
    std::size_t remaining=frames; int block_index=0; std::vector<double> window(8,0.0); std::vector<std::size_t> window_counts(8,0);
    while(remaining) {
        const std::size_t n=std::min<std::size_t>(pattern[block_index++%4],remaining);
        for(std::size_t i=0;i<n;++i){auto [l,r]=stimulus(offset+i,tail);input[2*i]=l;input[2*i+1]=r;}
        if(!runtime.processStereo(input.data(),output.data(),n,kRate)) throw std::runtime_error(std::string("processStereo failed: ")+runtime.getStatus().message);
        for(std::size_t i=0;i<n;++i){
            const float l=output[2*i],r=output[2*i+1];
            if(!std::isfinite(l)||!std::isfinite(r)) throw std::runtime_error("non-finite output");
            ++m.finite; ++m.frames; m.peak=std::max({m.peak,std::abs(l),std::abs(r)});
            m.sum_l+=double(l)*l;m.sum_r+=double(r)*r;m.sum_diff+=double(l-r)*(l-r);
            if(have)m.max_step=std::max({m.max_step,std::abs(l-prev_l),std::abs(r-prev_r)});
            prev_l=l;prev_r=r;have=true;
            const auto wi=std::min<std::size_t>(7,(m.frames-1)/8192);
            window[wi]+=double(l)*l+double(r)*r;window_counts[wi]+=2;
            std::uint32_t bits_l,bits_r;std::memcpy(&bits_l,&l,4);std::memcpy(&bits_r,&r,4);
            for(auto bits:{bits_l,bits_r}){for(int b=0;b<4;++b){m.hash^=(bits>>(8*b))&255u;m.hash*=1099511628211ULL;}}
            if(captured){captured->push_back(l);captured->push_back(r);}
        }
        remaining-=n;offset+=n;
    }
    for(std::size_t i=0;i<window.size();++i) if(window_counts[i])m.rms_windows.push_back(std::sqrt(window[i]/window_counts[i]));
    return m;
}
static void print_metric(const char* kind,unsigned raw,const Metrics&m) {
    std::cout<<"METRIC kind="<<kind<<" raw="<<raw<<" frames="<<m.frames<<" finite="<<m.finite
             <<" rms_l="<<std::setprecision(10)<<std::sqrt(m.sum_l/m.frames)
             <<" rms_r="<<std::sqrt(m.sum_r/m.frames)<<" stereo_diff_rms="<<std::sqrt(m.sum_diff/m.frames)
             <<" peak="<<m.peak<<" max_step="<<m.max_step<<" hash="<<std::hex<<m.hash<<std::dec<<" windows=";
    for(std::size_t i=0;i<m.rms_windows.size();++i){if(i)std::cout<<",";std::cout<<m.rms_windows[i];}
    std::cout<<"\n";
}

int main(int argc,char**argv) try {
    if(argc!=8) throw std::runtime_error("usage: test_hall_decay_audio_runtime checkpoint expected.csv output_dir timing.csv firmware.csv program_sha256 checkpoint_sha256");
    const std::string authentic=argv[1], expected_path=argv[2], output_dir=argv[3], timing_path=argv[4], schedule=argv[5], program_hash=argv[6], checkpoint_hash=argv[7];
    std::filesystem::create_directories(output_dir);
    auto groups=read_table(expected_path);
    std::array<bool,128> raw_seen{};

    // Probe the authentic RUN checkpoint without forcing an invented raw/display seed.
    auto authentic_runtime=load(authentic,schedule,program_hash,checkpoint_hash); const auto auth_status=authentic_runtime.getStatus();
    std::cout<<"AUTHENTIC_SEED available="<<auth_status.hall_decay_step_available
             <<" raw="<<unsigned(auth_status.hall_decay_raw_code)<<" display="<<auth_status.hall_decay_display_value
             <<" gpr6e="<<std::hex<<authentic_runtime.qaReadRegister(0x6e)<<std::dec<<"\n";

    // Apply exact OS-observed final register groups from the authentic HALL RUN checkpoint.
    for(unsigned raw=0;raw<128;++raw){
        auto runtime=load(authentic,schedule,program_hash,checkpoint_hash); settle_firmware(runtime);
        set_group(runtime,groups[raw],runtime.getStatus().processed_dsp_frames);
        auto m=render(runtime,8192,false);
        if(runtime.getStatus().scheduled_writes_applied<5) throw std::runtime_error("stable raw group did not apply");
        for(std::size_t j=0;j<kRegs.size();++j)
            if(runtime.qaReadRegister(kRegs[j])!=groups[raw][j]) throw std::runtime_error("stable group GPR readback mismatch");
        raw_seen[raw]=true; print_metric("full_range",raw,m);
    }
    for(bool x:raw_seen) if(!x) throw std::runtime_error("full-range audio run missed a raw code");

    // Long impulse tails at short, duplicate, mid, and long settings.
    for(unsigned raw:{0u,1u,44u,51u,52u,53u,76u,127u}){
        auto runtime=load(authentic,schedule,program_hash,checkpoint_hash); settle_firmware(runtime);
        set_group(runtime,groups[raw],runtime.getStatus().processed_dsp_frames);
        auto m=render(runtime,65536,true);
        print_metric("impulse_tail",raw,m);
    }

    // Fresh-repeat exact hashes at representative low, duplicate, middle, and high points.
    for(unsigned raw:{0u,44u,51u,52u,53u,127u}){
        auto a=load(authentic,schedule,program_hash,checkpoint_hash);settle_firmware(a);set_group(a,groups[raw],a.getStatus().processed_dsp_frames);auto ma=render(a,8192,false);
        auto b=load(authentic,schedule,program_hash,checkpoint_hash);settle_firmware(b);set_group(b,groups[raw],b.getStatus().processed_dsp_frames);auto mb=render(b,8192,false);
        if(ma.hash!=mb.hash||ma.frames!=mb.frames)throw std::runtime_error("stable setting is not repeatable");
        std::cout<<"REPEAT raw="<<raw<<" exact="<<(ma.hash==mb.hash)<<" hash="<<std::hex<<ma.hash<<std::dec<<"\n";
    }

    // Make explicit validated raw seeds from the authentic program/state for step API checks.
    auto seed0=seed_capture(authentic,output_dir+"/seed-raw0.esp",groups[0]);
    // The generic production package correctly disables stepping when its real
    // post-RUN schedule writes GPR 6E. Exercise the public stepping API on an
    // authenticated, OS-seeded variation-1 checkpoint without that schedule.
    auto api=load_legacy_seed(seed0);
    if(!api.getStatus().hall_decay_step_available||api.getStatus().hall_decay_display_value!=0)throw std::runtime_error("seeded variation-1 state was not exposed");
    std::array<bool,128> api_raw_seen{}; api_raw_seen[api.getStatus().hall_decay_raw_code]=true;
    std::array<float,2> zero_in{},zero_out{}; std::size_t api_steps=0;
    auto api_step=[&](int dir){auto frame=api.getStatus().processed_dsp_frames;if(!api.stepHallDecayTime(dir,frame))throw std::runtime_error(std::string("step API rejected seeded state: ")+api.getStatus().message);++api_steps;
        auto s=api.getStatus();const auto raw=s.hall_decay_raw_code;api_raw_seen[raw]=true;
        if(s.hall_decay_display_value<0||s.hall_decay_display_value>99)throw std::runtime_error("step API displayed value out of range");
        if(!api.processStereo(zero_in.data(),zero_out.data(),1,kRate))throw std::runtime_error("step render failed");
        for(std::size_t i=0;i<kRegs.size();++i)if(api.qaReadRegister(kRegs[i])!=groups[raw][i])throw std::runtime_error("step API applied GPR differs from OS observations");
    };
    for(int i=0;i<99;++i)api_step(+1);
    if(api.getStatus().hall_decay_raw_code!=127||api.getStatus().hall_decay_display_value!=99)throw std::runtime_error("up traversal endpoint mismatch");
    for(int i=0;i<99;++i)api_step(-1);
    if(api.getStatus().hall_decay_raw_code!=0||api.getStatus().hall_decay_display_value!=0)throw std::runtime_error("down traversal endpoint mismatch");
    for(bool x:api_raw_seen)if(!x)throw std::runtime_error("step API did not visit all OS raw codes");
    std::cout<<"API_SWEEP lcd_steps="<<api_steps<<" up=99 down=99 raw_codes=128 ordered_gpr_writes_checked=990 result=PASS\n";
    if(!api.reset()||!api.getStatus().hall_decay_step_available||api.getStatus().hall_decay_raw_code!=0)throw std::runtime_error("reset did not restore seeded raw-code state");

    // 40->41 route, after common warm state. Compare API's batched five writes
    // against exact OS stagger offsets supplied from the independent trace.
    unsigned raw53=53;Group transition=groups[raw53];std::array<unsigned,5> offsets{};
    {std::ifstream f(timing_path);if(!f)throw std::runtime_error("cannot read original-OS write timing");for(auto&x:offsets)if(!(f>>x))throw std::runtime_error("incomplete OS write timing");}
    if(offsets!=std::array<unsigned,5>{0,3,6,8,11})throw std::runtime_error("OS timing offsets differ from asserted 40->41 evidence");
    const auto seed51=seed_capture(authentic,output_dir+"/seed-raw51.esp",groups[51]);
    auto batched=load(seed51,schedule,program_hash,checkpoint_hash), staggered=load(seed51,schedule,program_hash,checkpoint_hash);
    auto warm_a=render(batched,32768,false),warm_b=render(staggered,32768,false);
    if(warm_a.hash!=warm_b.hash)throw std::runtime_error("timing twins diverged before the edit");
    const auto writes_before_batch=batched.getStatus().scheduled_writes_applied;
    const auto writes_before_stagger=staggered.getStatus().scheduled_writes_applied;
    const auto f0=batched.getStatus().processed_dsp_frames;
    for(std::size_t i=0;i<kRegs.size();++i)if(!batched.setRegister(kRegs[i],transition[i],f0))throw std::runtime_error("batched five-write scheduling failed");
    for(std::size_t i=0;i<kRegs.size();++i)if(!staggered.setRegister(kRegs[i],transition[i],f0+offsets[i]))throw std::runtime_error("staggered OS write scheduling failed");
    std::vector<float> out_a,out_b; auto ma=render(batched,65536,true,0,&out_a);auto mb=render(staggered,65536,true,0,&out_b);
    double diff_sum[4]={},energy_a[4]={},energy_b[4]={};float diff_peak[4]={},adj_a[4]={},adj_b[4]={};std::size_t counts[4]={};
    float prev_a_l=0,prev_a_r=0,prev_b_l=0,prev_b_r=0;
    for(std::size_t i=0;i<ma.frames;++i){std::size_t w=i<16?0:i<128?1:i<4096?2:3;float al=out_a[2*i],ar=out_a[2*i+1],bl=out_b[2*i],br=out_b[2*i+1];
        for(auto v:{al,ar,bl,br})if(!std::isfinite(v))throw std::runtime_error("non-finite in timing comparison");
        const double dl=double(al)-bl,dr=double(ar)-br;diff_sum[w]+=dl*dl+dr*dr;energy_a[w]+=double(al)*al+double(ar)*ar;energy_b[w]+=double(bl)*bl+double(br)*br;diff_peak[w]=std::max({diff_peak[w],static_cast<float>(std::abs(dl)),static_cast<float>(std::abs(dr))});
        if(i){adj_a[w]=std::max({adj_a[w],std::abs(al-prev_a_l),std::abs(ar-prev_a_r)});adj_b[w]=std::max({adj_b[w],std::abs(bl-prev_b_l),std::abs(br-prev_b_r)});}prev_a_l=al;prev_a_r=ar;prev_b_l=bl;prev_b_r=br;++counts[w];}
    for(int w=0;w<4;++w)std::cout<<"TIMING window="<<w<<" frames="<<counts[w]<<" diff_rms="<<std::sqrt(diff_sum[w]/(2*counts[w]))<<" diff_peak="<<diff_peak[w]<<" batch_rms="<<std::sqrt(energy_a[w]/(2*counts[w]))<<" stagger_rms="<<std::sqrt(energy_b[w]/(2*counts[w]))<<" batch_max_step="<<adj_a[w]<<" stagger_max_step="<<adj_b[w]<<"\n";
    if(batched.getStatus().scheduled_writes_applied!=writes_before_batch+5||staggered.getStatus().scheduled_writes_applied!=writes_before_stagger+5)throw std::runtime_error("timing write counts did not settle at five parameter writes");
    for(std::size_t i=0;i<kRegs.size();++i)if(batched.qaReadRegister(kRegs[i])!=transition[i]||staggered.qaReadRegister(kRegs[i])!=transition[i])throw std::runtime_error("timing final GPR state mismatch");
    std::cout<<"TIMING_FINAL batch_hash="<<std::hex<<ma.hash<<" stagger_hash="<<mb.hash<<std::dec<<" finite="<<ma.finite+mb.finite<<"\n";

    // Rapid edits: 1,000 alternating display steps at 32-frame spacing.
    auto rapid=load_legacy_seed(seed51);Metrics rapid_metrics;std::size_t accepted=0;
    for(int i=0;i<1000;++i){int direction=(i%2==0)?+1:-1;auto frame=rapid.getStatus().processed_dsp_frames;if(!rapid.stepHallDecayTime(direction,frame))throw std::runtime_error("rapid-edit API rejected edit");++accepted;auto m=render(rapid,32,false,static_cast<std::size_t>(i)*32);rapid_metrics.frames+=m.frames;rapid_metrics.finite+=m.finite;rapid_metrics.peak=std::max(rapid_metrics.peak,m.peak);rapid_metrics.max_step=std::max(rapid_metrics.max_step,m.max_step);}
    std::cout<<"RAPID edits="<<accepted<<" spacing_frames=32 processed="<<rapid_metrics.frames<<" finite="<<rapid_metrics.finite<<" peak="<<rapid_metrics.peak<<" max_step="<<rapid_metrics.max_step<<" raw="<<unsigned(rapid.getStatus().hall_decay_raw_code)<<" display="<<rapid.getStatus().hall_decay_display_value<<"\n";
    return 0;
} catch(const std::exception&e){std::cerr<<"HALL_AUDIO_QA_FAIL: "<<e.what()<<"\n";return 1;}
