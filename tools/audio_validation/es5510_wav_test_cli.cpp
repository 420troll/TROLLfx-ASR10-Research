#include "trollfx/es5510_audio_test_backend.hpp"
#include "trollfx/es5510_factory_parameter_discovery_v02.hpp"
#include "trollfx/es5510_factory_parameter_discovery_v03.hpp"
#include "trollfx/es5510_factory_parameter_discovery_v05.hpp"

#include <charconv>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace trollfx::es5510;
using namespace trollfx::es5510::audio_test;

namespace {
std::uint64_t integer(const std::string& s,int base=10) {
    std::uint64_t n=0;auto r=std::from_chars(s.data(),s.data()+s.size(),n,base);
    if(r.ec!=std::errc{}||r.ptr!=s.data()+s.size())
        throw std::runtime_error("invalid integer argument");
    return n;
}
std::vector<std::string> split(const std::string&s,char c) {
    std::vector<std::string> out;std::size_t p=0;
    while(p<=s.size()){auto q=s.find(c,p);out.push_back(s.substr(p,q==std::string::npos?q:q-p));if(q==std::string::npos)break;p=q+1;}
    return out;
}
void load_schedule(EffectDescriptor&d,const std::string&path) {
    std::ifstream in(path);if(!in)throw std::runtime_error("cannot read private firmware schedule");
    std::string line;if(!std::getline(in,line))
        throw std::runtime_error("unexpected firmware schedule header");
    if(!line.empty()&&line.back()=='\r')line.pop_back();
    if(line!="relative_dsp_frame,event_id,cpu_cycles,gpr,value24")
        throw std::runtime_error("unexpected firmware schedule header");
    std::uint64_t previous=0;bool first=true;
    while(std::getline(in,line)){
        if(!line.empty()&&line.back()=='\r')line.pop_back();
        if(line.empty())continue;
        auto f=split(line,',');
        if(f.size()!=5)throw std::runtime_error("malformed firmware schedule row");
        const auto frame=integer(f[0]),gpr=integer(f[3],16),value=integer(f[4],16);
        if(gpr>=0xc0||value>0xffffff||(!first&&frame<previous))throw std::runtime_error("invalid firmware schedule bounds/order");
        d.firmware_event_schedule.push_back({frame,static_cast<std::uint8_t>(gpr),static_cast<std::uint32_t>(value)});
        previous=frame;first=false;
    }
}
ValidatedEffectPackage package_from_args(char**argv) {
    EffectDescriptor d;d.slot=static_cast<EffectSlot>(integer(argv[1]));d.factory_name=argv[2];
    d.active_program_words=static_cast<std::uint32_t>(integer(argv[3]));d.end_word=d.active_program_words-1;
    d.program_sha256=argv[4];d.run_checkpoint_path=argv[5];d.run_checkpoint_sha256=argv[6];
    d.factory_reference_rate_hz=std::stod(argv[7]);d.routing={0x48,2,1,true};load_schedule(d,argv[8]);
    parameter_discovery_v02::append_verified_parameters(d);
    parameter_discovery_v03::append_verified_parameters(d);
    parameter_discovery_v05::append_verified_parameters(d);
    // Only the Python wrapper calls this constructor after consuming an
    // importer-produced descriptor and rechecking checkpoint/schedule hashes.
    ValidatedEffectPackage p;p.descriptor=std::move(d);
    p.validation_receipt_valid=p.initialization_state_valid=p.program_identity_valid=
        p.pipeline_reset_valid=p.routing_valid=true;
    return p;
}
void print_report(const RenderReport&r) {
    std::cout<<"slot="<<unsigned(r.slot)<<" dsp_frames="<<r.dsp_frames<<" writes_applied="<<r.writes_applied
             <<" latency_frames="<<r.latency_frames<<" output_rms_l="<<r.output.rms_left
             <<" output_rms_r="<<r.output.rms_right<<" output_peak_l="<<r.output.peak_left
             <<" output_peak_r="<<r.output.peak_right<<" finite_samples="<<r.output.finite_samples<<"\n";
    for(const auto&w:r.parameter_writes)
        std::cout<<"PARAM_GPR frame="<<w.dsp_frame<<" order="<<w.order_in_group<<" id="<<w.parameter_id
                 <<" display="<<w.display_value<<" gpr="<<unsigned(w.gpr)<<" value24="<<std::hex<<w.value24<<std::dec<<"\n";
}
}

int main(int argc,char**argv) try {
    if(argc<11)throw std::runtime_error("usage: cli SLOT NAME WORDS PROGRAM_SHA CHECKPOINT CHECKPOINT_SHA RATE SCHEDULE.csv INPUT.wav OUTPUT.wav [--factory-variation 0..4] [--block N] [--tail N] [--bypass DRY.wav] [--event FRAME:PARAM_ID:VALUE]... [--compare PARAM_ID VALUE FRAME PREFIX]");
    auto pkg=package_from_args(argv);
    for(int i=11;i<argc;++i)if(std::string(argv[i])=="--factory-variation"){
        if(i+1>=argc)throw std::runtime_error("missing factory variation value");
        const auto variation=integer(argv[++i]);
        if(variation>4)throw std::runtime_error("factory variation must be 0..4");
        pkg.descriptor.factory_variation=static_cast<std::uint8_t>(variation);
    }
    EffectRegistry registry;std::string registry_error;
    if(!registry.register_validated(std::move(pkg),&registry_error))throw std::runtime_error("registry rejected imported package: "+registry_error);
    RenderOptions options;std::vector<ParameterChange> events;std::string bypass_path;
    bool compare=false;std::string compare_id,prefix;std::int32_t compare_value=0;std::uint64_t compare_frame=0;
    for(int i=11;i<argc;++i){const std::string arg=argv[i];auto value=[&](){if(++i>=argc)throw std::runtime_error("missing option value");return std::string(argv[i]);};
        if(arg=="--factory-variation")(void)value();
        else if(arg=="--block")options.block_frames=integer(value());
        else if(arg=="--tail")options.tail_frames=integer(value());
        else if(arg=="--bypass")bypass_path=value();
        else if(arg=="--event") {auto f=split(value(),':');if(f.size()!=3)throw std::runtime_error("event must be FRAME:PARAM_ID:VALUE");events.push_back({integer(f[0]),f[1],static_cast<std::int32_t>(std::stol(f[2]))});}
        else if(arg=="--compare") {compare=true;compare_id=value();compare_value=static_cast<std::int32_t>(std::stol(value()));compare_frame=integer(value());prefix=value();}
        else throw std::runtime_error("unknown option: "+arg);
    }
    WavAudioTestRunner runner(registry);std::string error;
    if(compare){
        DifferenceMetrics diff;RenderReport a,b;
        if(!runner.renderParameterAB(argv[9],prefix+"-baseline.wav",prefix+"-changed.wav",
            static_cast<EffectSlot>(integer(argv[1])),{},{{compare_frame,compare_id,compare_value}},options,diff,a,b,error))
            throw std::runtime_error(error);
        print_report(a);print_report(b);
        std::cout<<"A_B difference_frames="<<diff.finite_samples<<" difference_rms_l="<<diff.difference_rms_left
                 <<" difference_rms_r="<<diff.difference_rms_right<<" difference_peak="<<diff.difference_peak<<"\n";
    } else if(!bypass_path.empty()){
        ABReport r;if(!runner.renderWetDryAB(argv[9],argv[10],bypass_path,static_cast<EffectSlot>(integer(argv[1])),events,options,r,error))
            throw std::runtime_error(error);
        print_report(r.render);std::cout<<"AB difference_frames="<<r.difference.finite_samples
            <<" difference_rms_l="<<r.difference.difference_rms_left<<" difference_rms_r="<<r.difference.difference_rms_right
            <<" difference_peak="<<r.difference.difference_peak<<"\n";
    } else {
        RenderReport r;
        if(!runner.render(argv[9],argv[10],static_cast<EffectSlot>(integer(argv[1])),events,options,r,error))
            throw std::runtime_error(error);
        print_report(r);
    }
    return 0;
}catch(const std::exception&e){std::cerr<<"es5510_wav_test_cli: "<<e.what()<<'\n';return 2;}
