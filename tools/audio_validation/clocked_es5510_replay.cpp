#include "es5510.h"
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

static std::vector<std::string> split(const std::string &s) {
    std::vector<std::string> out; std::stringstream ss(s); std::string v;
    while (std::getline(ss,v,',')) out.push_back(v);
    return out;
}
int main(int argc,char **argv) try {
    if(argc!=5) { std::cerr<<"usage: clocked-es5510-replay CHECKPOINT INPUT-FRAMES RATE-HZ OUTPUT-CSV\n"; return 2; }
    const double rate=std::stod(argv[3]); if(rate<=0.0) throw std::runtime_error("rate must be positive");
    FILE *capture=std::fopen(argv[1],"rb"); if(!capture) throw std::runtime_error("cannot open checkpoint");
    ES5510 esp; const bool loaded=esp.load_capture_after_pipeline_reset(capture); std::fclose(capture);
    if(!loaded) throw std::runtime_error("checkpoint is not a validated pipeline-reset capture");
    std::ifstream in(argv[2]); std::ofstream out(argv[4]);
    if(!in||!out) throw std::runtime_error("cannot open serial input or output CSV");
    std::string line; if(!std::getline(in,line)) throw std::runtime_error("missing input CSV header");
    if(!line.empty() && line.back()=='\r') line.pop_back();
    if(line!="frame,absolute_frame,cycles,host_pc,lane0,lane1,lane2,lane3,lane4,lane5,lane6,lane7") throw std::runtime_error("unexpected input CSV header");
    out<<"frame,seconds,ser1_left,ser1_right\n";
    std::uint64_t expected=0;
    while(std::getline(in,line)) {
        if(!line.empty() && line.back()=='\r') line.pop_back();
        const auto row=split(line); if(row.size()!=12) throw std::runtime_error("malformed eight-lane input row");
        const auto frame=std::stoull(row[0]); if(frame!=expected++) throw std::runtime_error("input frame sequence is discontinuous");
        std::array<std::int16_t,8> lanes{};
        for(unsigned i=0;i<8;i++) { const int sample=std::stoi(row[4+i]); if(sample < -32768 || sample > 32767) throw std::runtime_error("serial sample outside PCM16"); lanes[i]=static_cast<std::int16_t>(sample); esp.ser_w(i,lanes[i]); }
        esp.run_frame();
        out<<frame<<','<<static_cast<double>(frame)/rate<<','<<esp.ser_r(2)<<','<<esp.ser_r(3)<<'\n';
    }
    if(!expected) throw std::runtime_error("no serial input frames");
    std::cerr<<"frames="<<expected<<" rate_hz="<<rate<<" clock_used_only_for_time_mapping=1\n";
    return 0;
} catch(const std::exception &e) { std::cerr<<e.what()<<'\n'; return 1; }
