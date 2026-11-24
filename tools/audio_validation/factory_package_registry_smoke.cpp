#include "trollfx/es5510_factory_runtime.hpp"
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace trollfx::es5510;

int main(int argc,char**argv) try {
    if(argc!=9) throw std::runtime_error("usage: smoke SLOT NAME WORDS PROGRAM_SHA CHECKPOINT CHECKPOINT_SHA RATE SCHEDULE.csv");
    EffectDescriptor d; d.slot=static_cast<EffectSlot>(std::stoi(argv[1])); d.factory_name=argv[2];
    d.active_program_words=static_cast<std::uint32_t>(std::stoul(argv[3])); d.end_word=d.active_program_words-1;
    d.program_sha256=argv[4]; d.run_checkpoint_path=argv[5]; d.run_checkpoint_sha256=argv[6];
    d.factory_reference_rate_hz=std::stod(argv[7]); d.routing={0x48,2,1,true};
    std::string schedule_path=argv[8];
    if(!schedule_path.empty()){
        std::ifstream in(schedule_path); std::string line; std::getline(in,line);
        while(std::getline(in,line)){std::stringstream ss(line);std::string frame,event,cycles,gpr,value;
            std::getline(ss,frame,',');std::getline(ss,event,',');std::getline(ss,cycles,',');std::getline(ss,gpr,',');std::getline(ss,value,',');
            d.firmware_event_schedule.push_back({std::stoull(frame),static_cast<std::uint8_t>(std::stoul(gpr,nullptr,16)),static_cast<std::uint32_t>(std::stoul(value,nullptr,16))});}
    }
    // The caller only invokes this executable from a descriptor emitted by the
    // fail-closed private manifest/checkpoint validator.
    ValidatedEffectPackage p; p.descriptor=std::move(d); p.validation_receipt_valid=true;
    p.initialization_state_valid=true; p.program_identity_valid=true; p.pipeline_reset_valid=true; p.routing_valid=true;
    EffectRegistry registry; std::string error;
    if(!registry.register_validated(std::move(p),&error)) throw std::runtime_error("registry rejected package: "+error);
    FactoryRuntime fx; if(!fx.loadEffect(*registry.find(static_cast<EffectSlot>(std::stoi(argv[1]))))) throw std::runtime_error(fx.getStatus().message);
    constexpr std::size_t n=4096; std::vector<float> in(n*2),out(n*2);
    for(std::size_t i=0;i<n;++i){const float x=i==0?0.5f:0.15f*std::sin(float(2.0*3.141592653589793*330.0*i/48000.0));in[2*i]=x;in[2*i+1]=-x;}
    if(!fx.processStereo(in.data(),out.data(),n,48000.0)) throw std::runtime_error(fx.getStatus().message);
    double energy=0; std::size_t finite=0; float peak=0;
    for(float x:out){if(std::isfinite(x)){++finite;energy+=double(x)*x;peak=std::max(peak,std::fabs(x));}}
    if(finite!=out.size()) throw std::runtime_error("runtime produced non-finite stereo output");
    const auto status=fx.getStatus();
    std::cout<<"slot="<<unsigned(status.effect)<<" frames="<<n<<" dsp_frames="<<status.processed_dsp_frames
             <<" finite="<<finite<<" rms="<<std::sqrt(energy/out.size())<<" peak="<<peak
             <<" schedule_applied="<<status.scheduled_writes_applied<<"\n";
    return 0;
} catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
