#include <trollfx/es5510_factory_runtime.hpp>
#include <array>
#include <cmath>
#include <iostream>
#include <string>

// Demonstration only: the caller must first validate the private checkpoint,
// active image/source correlation, route, and HALT pipeline-reset evidence.
int main(int argc,char**argv) {
    using namespace trollfx::es5510;
    if(argc!=3 || (std::string(argv[1])!="hall" && std::string(argv[1])!="rom02")) {
        std::cerr<<"usage: runtime-example hall|rom02 PRIVATE-RUN-CHECKPOINT\n"; return 2;
    }
    const bool hall=std::string(argv[1])=="hall";
    EffectPackage pkg{hall?EffectId::Rom01Hall:EffectId::Rom02Reverb44k,argv[2],
                      hall?89u:60u,hall?29761.89453125:44100.0,true,true,true};
    FactoryRuntime fx;
    if(!fx.loadEffect(pkg,RateMode::Experimental48000)) {
        std::cerr<<"load rejected: "<<fx.getStatus().message<<'\n'; return 1;
    }
    std::array<float,1024> input{},output{}; // 512 stereo frames, interleaved
    for(std::size_t i=0;i<512;++i) {
        const float x=0.2f*std::sin(float(2.0*3.141592653589793*440.0*i/48000.0));
        input[2*i]=input[2*i+1]=x;
    }
    if(!fx.processStereo(input.data(),output.data(),512,48000.0)) {
        std::cerr<<"process failed: "<<fx.getStatus().message<<'\n'; return 1;
    }
    const auto s=fx.getStatus();
    std::cout<<"DSP frames: "<<s.processed_dsp_frames<<" at "<<s.processing_rate_hz<<" Hz; "
             <<"host rate: "<<s.host_rate_hz<<" Hz\n";
}
