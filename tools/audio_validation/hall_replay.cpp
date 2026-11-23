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
    while (std::getline(ss, v, ',')) out.push_back(v);
    return out;
}
static void native_gpr(ES5510& e, unsigned r, std::uint32_t v) {
    e.host_w(0, (v >> 16) & 255); e.host_w(1, (v >> 8) & 255); e.host_w(2, v & 255); e.host_w(0xa0, r);
}
static void native_instr(ES5510& e, unsigned a, std::uint64_t w) {
    for (unsigned b=0;b<6;++b) e.host_w(3+b, (w >> ((5-b)*8)) & 255);
    e.host_w(0xc0, a);
}
static void native_set(ES5510& e, unsigned r, std::uint32_t v) {
    e.host_w(0, (v >> 16) & 255); e.host_w(1, (v >> 8) & 255); e.host_w(2, v & 255); e.host_w(0xa0, r);
}
static void native_both(ES5510& e, unsigned a, std::uint64_t w, std::uint32_t v) {
    for (unsigned b=0;b<6;++b) e.host_w(3+b, (w >> ((5-b)*8)) & 255);
    e.host_w(0, (v >> 16) & 255); e.host_w(1, (v >> 8) & 255); e.host_w(2, v & 255);
    e.host_w(0xe0, a);
}

int main(int argc, char** argv) try {
    if (argc != 6) { std::cerr << "usage: hall-replay LOAD-COMMITS UPDATES IO OUTPUT\n"; return 2; }
    ES5510 native; native.set_halt(true); native.host_w(0x1f,0); native.host_w(0x12,2);
    trollfx::esp::MameES5510 mame; if (!mame.prepare()) throw std::runtime_error("MAME initialization failed");
    std::ifstream commits(argv[1]); if(!commits) throw std::runtime_error("cannot open load commit stream");
    std::string line; std::getline(commits,line); if(!line.empty() && line.back()=='\r') line.pop_back();
    if(line!="kind,address,value,second_value") throw std::runtime_error("unexpected load commit header");
    unsigned gprCommits=0,instrCommits=0;
    while(std::getline(commits,line)) {
        auto c=split(line); if(c.size()!=4) throw std::runtime_error("malformed load commit");
        unsigned a=std::stoul(c[1],nullptr,16); std::uint64_t v=std::stoull(c[2],nullptr,16);
        if(c[0]=="gpr") { native_gpr(native,a,static_cast<std::uint32_t>(v)); mame.setRegister(static_cast<std::uint8_t>(a),static_cast<std::uint32_t>(v)); ++gprCommits; }
        else if(c[0]=="instr") { native_instr(native,a,v); if(!mame.writeInstruction(a,v)) throw std::runtime_error("bad instruction address"); ++instrCommits; }
        else if(c[0]=="both") { auto g=std::stoul(c[3],nullptr,16); native_both(native,a,v,g); if(!mame.writeInstruction(a,v)) throw std::runtime_error("bad instruction address"); mame.setRegister(static_cast<std::uint8_t>(a),g); ++gprCommits; ++instrCommits; }
        else throw std::runtime_error("unsupported load commit type");
    }
    if(gprCommits!=342 || instrCommits!=89) throw std::runtime_error("load transaction commit count mismatch");
    native.host_w(0x18,0x48); native.set_halt(false); mame.setHostSerial(0x48);

    std::ifstream updates(argv[2]), io(argv[3]); std::ofstream out(argv[4]);
    if (!updates||!io||!out) throw std::runtime_error("cannot open replay stream");
    std::getline(updates,line); auto uh=split(line);
    if (uh.size()<8 || uh[0]!="frame_before_process") throw std::runtime_error("unexpected update CSV header");
    std::getline(io,line); auto ih=split(line);
    if (ih.size()!=17 || ih[0]!="frame") throw std::runtime_error("unexpected IO CSV header");
    out << "frame"; for (unsigned p=0;p<4;++p) out << ",native"<<p<<"l,native"<<p<<"r,mame"<<p<<"l,mame"<<p<<"r";
    for (unsigned p=0;p<4;++p) out << ",recorded"<<p<<"l,recorded"<<p<<"r"; out << '\n';
    std::getline(io,line); std::vector<std::string> row; std::size_t updateCount=0, frames=0;
    std::string updateLine;
    bool haveUpdate=static_cast<bool>(std::getline(updates,updateLine)); auto u=haveUpdate?split(updateLine):std::vector<std::string>{};
    while (true) {
        row=split(line); if (row.size()!=17) throw std::runtime_error("malformed IO row");
        const auto frame=std::stoull(row[0]);
        while (haveUpdate && std::stoull(u[0])<=frame) {
            if (u.size()<8) throw std::runtime_error("malformed update row");
            unsigned reg=std::stoul(u[6],nullptr,16); std::uint32_t val=std::stoul(u[7],nullptr,16);
            native_set(native,reg,val); mame.setRegister(static_cast<std::uint8_t>(reg),val); ++updateCount;
            haveUpdate=static_cast<bool>(std::getline(updates,updateLine)); if(haveUpdate)u=split(updateLine);
        }
        std::array<std::int16_t,8> input{};
        for(unsigned i=0;i<8;++i) input[i]=static_cast<std::int16_t>(std::stoi(row[1+i]));
        for(unsigned i=0;i<8;++i) native.ser_w(i,input[i]);
        native.run_frame();
        std::array<std::int16_t,6> mi{}; for(unsigned i=0;i<6;++i) mi[i]=input[i];
        std::array<std::int16_t,2> ignored{}; mame.processFrame(mi,ignored);
        out << frame;
        for(unsigned p=0;p<4;++p) {
            int nl=native.ser_r(p*2), nr=native.ser_r(p*2+1);
            int ml=int(mame.registerValue(static_cast<std::uint8_t>(p==0?235:p==1?237:p==2?239:241))>>8);
            int mr=int(mame.registerValue(static_cast<std::uint8_t>(p==0?234:p==1?236:p==2?238:240))>>8);
            if(ml&0x8000) ml-=65536; if(mr&0x8000) mr-=65536;
            out << ','<<nl<<','<<nr<<','<<ml<<','<<mr;
        }
        out << ","; for(unsigned i=9;i<17;++i) out << (i==9?"":",") << row[i]; out << '\n';
        ++frames;
        if(!std::getline(io,line)) break;
    }
    std::cerr << "replayed_frames="<<frames<<" ordered_updates="<<updateCount<<"\n";
} catch (const std::exception& e) { std::cerr << e.what()<<'\n'; return 1; }
