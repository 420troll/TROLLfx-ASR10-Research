#include "es5510.h"
#include "mame_es5510_standalone.hpp"

#include <cstdint>
#include <cstdio>
#include <stdexcept>

static void instruction(ES5510& e, unsigned a, std::uint64_t v) {
    for(unsigned b=0;b<6;++b)e.host_w(3+b,static_cast<std::uint8_t>(v>>((5-b)*8)));
    e.host_w(0xc0,static_cast<std::uint8_t>(a));
}
static void gpr(ES5510& e,unsigned a,std::uint32_t v) {
    e.host_w(0,static_cast<std::uint8_t>(v>>16));e.host_w(1,static_cast<std::uint8_t>(v>>8));
    e.host_w(2,static_cast<std::uint8_t>(v));e.host_w(0xa0,static_cast<std::uint8_t>(a));
}

int main() try {
    ES5510 source;source.set_halt(true);instruction(source,0,0x00000000f000ULL);
    gpr(source,0x10,0x123456);source.host_w(0x18,0x48);
    source.ser_w(4,1234);source.ser_w(5,-1234);
    FILE* f=std::tmpfile();if(!f)throw std::runtime_error("tmpfile failed");
    if(!source.write_capture(f))throw std::runtime_error("capture write failed");std::rewind(f);
    ES5510 native;if(!native.load_capture_after_pipeline_reset(f))throw std::runtime_error("native capture load failed");
    std::rewind(f);trollfx::esp::MameES5510 mame;
    if(!mame.prepare()||!mame.loadCaptureAfterPipelineReset(f))throw std::runtime_error("MAME capture load failed");
    std::fclose(f);
    for(unsigned r=0;r<256;++r)if(native.register_value(static_cast<std::uint8_t>(r))!=mame.registerValue(static_cast<std::uint8_t>(r)))
        throw std::runtime_error("capture engines disagree before execution");
    native.set_halt(false);native.ser_w(4,1234);native.ser_w(5,-1234);
    native.run_frame();mame.runFrameWithSerialState({0,0,0,0,1234,-1234,0,0});
    for(unsigned i=0;i<8;++i){
        static constexpr unsigned reg[8]={235,234,237,236,239,238,241,240};
        const auto v=mame.registerValue(static_cast<std::uint8_t>(reg[i]));
        int sample=static_cast<int>((v>>8)&0xffffu);if(sample&0x8000)sample-=65536;
        if(native.ser_r(static_cast<int>(i))!=sample)throw std::runtime_error("captured engines disagree after execution");
    }
    std::puts("ES5510 boundary capture load/execute: ok");return 0;
}catch(const std::exception&e){std::fprintf(stderr,"%s\n",e.what());return 1;}
