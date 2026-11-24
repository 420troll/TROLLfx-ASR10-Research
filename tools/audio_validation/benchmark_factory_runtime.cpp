#include "trollfx/es5510_factory_runtime.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace trollfx::es5510;
int main(int argc,char**argv) try {
    if(argc!=3){std::cerr<<"usage: benchmark-factory-runtime hall|rom02 PRIVATE-CHECKPOINT\n";return 2;}
    const std::string id=argv[1];
    const bool hall=id=="hall"; if(!hall&&id!="rom02")throw std::runtime_error("unknown effect profile");
    EffectPackage pkg{hall?EffectId::Rom01Hall:EffectId::Rom02Reverb44k,argv[2],hall?89u:60u,
                      hall?29761.89453125:44100.0,true,true,true};
    FactoryRuntime fx; if(!fx.loadEffect(pkg,RateMode::Experimental48000))throw std::runtime_error(fx.getStatus().message);
    constexpr std::size_t frames=48000;
    std::vector<float> in(frames*2),out(frames*2);
    for(std::size_t i=0;i<frames;++i){const float x=0.25f*std::sin(float(2.0*3.141592653589793*440.0*i/48000.0));in[2*i]=x;in[2*i+1]=x;}
    const std::size_t blocks[]={1,7,64,128,256,512,1024};
    const auto start=std::chrono::steady_clock::now();
    std::size_t offset=0,bi=0;
    while(offset<frames){const auto n=std::min(blocks[bi++%7],frames-offset);if(!fx.processStereo(in.data()+2*offset,out.data()+2*offset,n,48000.0))throw std::runtime_error(fx.getStatus().message);offset+=n;}
    const auto end=std::chrono::steady_clock::now();
    double sq=0;float peak=0;for(float v:out){sq+=double(v)*v;peak=std::max(peak,std::fabs(v));}
    const double seconds=std::chrono::duration<double>(end-start).count();const auto s=fx.getStatus();
    std::cout<<"effect="<<id<<" frames="<<frames<<" dsp_frames="<<s.processed_dsp_frames<<" wall_seconds="<<seconds<<" realtime_factor="<<(frames/48000.0/seconds)<<" output_rms="<<std::sqrt(sq/out.size())<<" output_peak="<<peak<<"\n";
    return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
