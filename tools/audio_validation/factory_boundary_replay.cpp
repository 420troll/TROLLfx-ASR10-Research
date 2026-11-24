#include "es5510.h"
#include "mame_es5510_standalone.hpp"

#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

static std::vector<std::string> split(const std::string& s) {
    std::vector<std::string> out; std::stringstream ss(s); std::string v;
    while (std::getline(ss,v,',')) out.push_back(v);
    return out;
}
static void native_set(ES5510& e, unsigned r, std::uint32_t v) {
    e.host_w(0,(v>>16)&255); e.host_w(1,(v>>8)&255); e.host_w(2,v&255); e.host_w(0xa0,r);
}
static int lane(const trollfx::esp::MameES5510& e, unsigned i) {
    static constexpr unsigned reg[8]={235,234,237,236,239,238,241,240};
    std::uint32_t v=e.registerValue(static_cast<std::uint8_t>(reg[i]));
    int x=static_cast<int>((v>>8)&0xffffu); return x&0x8000?x-65536:x;
}

int main(int argc,char**argv) try {
    if(argc!=6&&argc!=8){std::cerr<<"usage: factory-boundary-replay SNAPSHOT UPDATES IO OUTPUT STATE-CHECKS [DIAGNOSTIC-FRAME TRACE-PREFIX]\n";return 2;}
    const std::uint64_t diagnosticFrame=argc==8?std::stoull(argv[6]):UINT64_MAX;
    FILE* f=std::fopen(argv[1],"rb"); if(!f)throw std::runtime_error("cannot open checkpoint");
    ES5510 native; if(!native.load_capture_after_pipeline_reset(f)){std::fclose(f);throw std::runtime_error("invalid or incomplete ES5510 checkpoint");} std::fclose(f);
    f=std::fopen(argv[1],"rb"); if(!f)throw std::runtime_error("cannot reopen checkpoint");
    trollfx::esp::MameES5510 mame; if(!mame.prepare()||!mame.loadCaptureAfterPipelineReset(f)){std::fclose(f);throw std::runtime_error("MAME checkpoint load failed");} std::fclose(f);

    std::ifstream updates(argv[2]),io(argv[3]); std::ofstream out(argv[4]),stateOut(argv[5]);
    if(!updates||!io||!out||!stateOut)throw std::runtime_error("cannot open private replay streams");
    stateOut<<"phase,boundary_frame,event_id,cpu_cycles,mismatching_registers,first_address\n";
    unsigned initialDiffs=0,initialFirst=0;
    for(unsigned r=0;r<256;++r)if(native.register_value(static_cast<std::uint8_t>(r))!=mame.registerValue(static_cast<std::uint8_t>(r))){if(!initialDiffs)initialFirst=r;++initialDiffs;}
    stateOut<<"initial,0,0,0,"<<initialDiffs<<','<<(initialDiffs?std::to_string(initialFirst):"")<<'\n';
    std::string line; std::getline(updates,line); if(!line.empty()&&line.back()=='\r')line.pop_back();
    if(line!="boundary_frame,event_id,cpu_cycles,dsp_frame,host_pc,index,value")throw std::runtime_error("unexpected update schedule header");
    std::getline(io,line); if(!line.empty()&&line.back()=='\r')line.pop_back();
    if(line!="frame,cycles,host_pc,lane0,lane1,lane2,lane3,lane4,lane5,lane6,lane7,reference_left,reference_right")throw std::runtime_error("unexpected serial input header");
    out<<"frame";for(unsigned i=0;i<8;++i)out<<",native"<<i;for(unsigned i=0;i<8;++i)out<<",mame"<<i;out<<",reference_left,reference_right\n";
    std::string updateLine; bool have=static_cast<bool>(std::getline(updates,updateLine));
    std::vector<std::string> u=have?split(updateLine):std::vector<std::string>{};
    std::uint64_t frames=0,applied=0;
    while(std::getline(io,line)){
        auto row=split(line);if(row.size()!=13)throw std::runtime_error("malformed serial input row");
        const auto frame=std::stoull(row[0]);
        while(have&&std::stoull(u[0])<=frame){
            if(u.size()!=7)throw std::runtime_error("malformed scheduled firmware write");
            const unsigned reg=std::stoul(u[5],nullptr,16);const auto value=std::stoul(u[6],nullptr,16);
            native.set_host_context(std::stoull(u[2]),std::stoul(u[4],nullptr,16));
            native_set(native,reg,value);mame.setRegister(static_cast<std::uint8_t>(reg),value);++applied;
            unsigned diffs=0,first=0;
            for(unsigned r=0;r<256;++r)if(native.register_value(static_cast<std::uint8_t>(r))!=mame.registerValue(static_cast<std::uint8_t>(r))){if(!diffs)first=r;++diffs;}
            stateOut<<"firmware,"<<u[0]<<','<<u[1]<<','<<u[2]<<','<<diffs<<','<<(diffs?std::to_string(first):"")<<'\n';
            have=static_cast<bool>(std::getline(updates,updateLine));if(have)u=split(updateLine);
        }
        std::array<std::int16_t,8> input{};
        native.set_frame_context(std::stoull(row[1]),std::stoul(row[2],nullptr,16));
        for(unsigned i=0;i<8;++i)input[i]=static_cast<std::int16_t>(std::stoi(row[3+i]));
        unsigned beforeDiffs=0,beforeFirst=0;
        for(unsigned r=0;r<256;++r)if(native.register_value(static_cast<std::uint8_t>(r))!=mame.registerValue(static_cast<std::uint8_t>(r))){if(!beforeDiffs)beforeFirst=r;++beforeDiffs;}
        if(beforeDiffs)stateOut<<"frame_start,"<<frame<<",0,0,"<<beforeDiffs<<','<<beforeFirst<<'\n';
        for(unsigned i=0;i<8;++i)native.ser_w(i,input[i]);
        FILE *nativeTrace=nullptr,*mameTrace=nullptr;
        if(frame==diagnosticFrame){
            const std::string prefix=argv[7];
            nativeTrace=std::fopen((prefix+".native.csv").c_str(),"wb");
            mameTrace=std::fopen((prefix+".mame.csv").c_str(),"wb");
            if(!nativeTrace||!mameTrace)throw std::runtime_error("cannot open private first-divergence traces");
            native.set_diagnostic_trace(nativeTrace);mame.setDiagnosticTrace(mameTrace);
        }
        native.run_frame();mame.runFrameWithSerialState(input);
        if(nativeTrace){native.set_diagnostic_trace(nullptr);mame.setDiagnosticTrace(nullptr);std::fclose(nativeTrace);std::fclose(mameTrace);}
        unsigned afterDiffs=0,afterFirst=0;
        for(unsigned r=0;r<256;++r)if(native.register_value(static_cast<std::uint8_t>(r))!=mame.registerValue(static_cast<std::uint8_t>(r))){if(!afterDiffs)afterFirst=r;++afterDiffs;}
        if(afterDiffs)stateOut<<"frame_end,"<<frame<<",0,0,"<<afterDiffs<<','<<afterFirst<<'\n';
        out<<frame;for(unsigned i=0;i<8;++i)out<<','<<native.ser_r(i);for(unsigned i=0;i<8;++i)out<<','<<lane(mame,i);
        out<<','<<row[11]<<','<<row[12]<<'\n';++frames;
    }
    if(have)throw std::runtime_error("scheduled firmware updates extend beyond selected input interval");
    std::cerr<<"replayed_frames="<<frames<<" scheduled_updates_applied="<<applied<<" initial_register_differences="<<initialDiffs<<"\n";
    return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
