#include "trollfx/es5510_factory_runtime.hpp"

#include <algorithm>
#include <array>
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
using Group = std::array<std::uint32_t,5>; // 6E, 5B, 03, 04, 05
static constexpr double kFactoryRate=29761.89453125;
static constexpr std::array<std::uint8_t,5> kRegisters{0x6e,0x5b,0x03,0x04,0x05};
static constexpr std::array<unsigned,10> kRawCodes{0,13,32,51,52,53,96,115,116,127};
static constexpr std::array<const char*,2> kStimuli{"impulse","noise_burst"};
static constexpr std::array<double,2> kRates{kFactoryRate,48000.0};
static constexpr std::uint32_t kNoiseSeed=0x5eed5510u;

static void put_u16(std::ofstream& f,std::uint16_t x){char b[2]={char(x),char(x>>8)};f.write(b,2);}
static void put_u32(std::ofstream& f,std::uint32_t x){char b[4]={char(x),char(x>>8),char(x>>16),char(x>>24)};f.write(b,4);}
static void write_float_wav(const std::string& path,const std::vector<float>& samples,std::uint32_t rate){
    std::ofstream f(path,std::ios::binary);if(!f)throw std::runtime_error("cannot create private WAV render");
    const std::uint32_t bytes=static_cast<std::uint32_t>(samples.size()*sizeof(float));
    f.write("RIFF",4);put_u32(f,36+bytes);f.write("WAVEfmt ",8);put_u32(f,16);put_u16(f,3);put_u16(f,2);put_u32(f,rate);put_u32(f,rate*2*4);put_u16(f,8);put_u16(f,32);f.write("data",4);put_u32(f,bytes);
    f.write(reinterpret_cast<const char*>(samples.data()),static_cast<std::streamsize>(bytes));
    if(!f)throw std::runtime_error("failed writing private WAV render");
}
static std::uint32_t xorshift(std::uint32_t& x){x^=x<<13;x^=x>>17;x^=x<<5;return x;}
static std::pair<float,float> input_sample(const char* stimulus,std::size_t frame,double rate){
    if(std::strcmp(stimulus,"impulse")==0)return frame==0?std::pair<float,float>{0.75f,0.42f}:std::pair<float,float>{0.0f,0.0f};
    const auto burst=static_cast<std::size_t>(std::llround(rate*0.5));
    if(frame>=burst)return {0.0f,0.0f};
    std::uint32_t l=kNoiseSeed+static_cast<std::uint32_t>(frame)*2u+1u;
    std::uint32_t r=kNoiseSeed+static_cast<std::uint32_t>(frame)*2u+2u;
    const float a=static_cast<float>(xorshift(l)&0xffffffu)/8388607.5f-1.0f;
    const float b=static_cast<float>(xorshift(r)&0xffffffu)/8388607.5f-1.0f;
    return {a*0.12f,b*0.12f};
}
static std::array<Group,128> read_table(const std::string& path){
    std::array<Group,128> table{};std::array<bool,128> seen{};std::ifstream f(path);std::string line;if(!f)throw std::runtime_error("cannot read private OS register table");
    while(std::getline(f,line)){std::istringstream s(line);unsigned raw;char comma;std::uint32_t a,b,c,d,e;
        if(!(s>>raw>>comma>>std::hex>>a>>comma>>b>>comma>>c>>comma>>d>>comma>>e))continue;
        if(raw>127)throw std::runtime_error("raw code out of range");table[raw]={a,b,c,d,e};seen[raw]=true;}
    for(bool x:seen)if(!x)throw std::runtime_error("expected register table does not cover all raw values");return table;
}
static std::string hex_group(const Group& g){std::ostringstream s;s<<'[';for(std::size_t i=0;i<g.size();++i){if(i)s<<',';s<<"\"0x"<<std::hex<<std::setw(6)<<std::setfill('0')<<g[i]<<"\"";}s<<']';return s.str();}
static ValidatedEffectPackage make_package(const std::string& checkpoint,const std::string& schedule,const std::string& program_hash,const std::string& checkpoint_hash,std::size_t& event_count,std::uint64_t& last_event_frame){
    ValidatedEffectPackage p;auto& d=p.descriptor;d.slot=1;d.factory_name="HALL REVERB";d.factory_variation=1;d.active_program_words=89;d.end_word=88;d.program_sha256=program_hash;d.factory_reference_rate_hz=kFactoryRate;d.routing={0x48,2,1,true};d.run_checkpoint_path=checkpoint;d.run_checkpoint_sha256=checkpoint_hash;d.firmware_event_schedule_path=schedule;
    std::ifstream f(schedule);std::string line;if(!std::getline(f,line))throw std::runtime_error("empty firmware schedule");
    while(std::getline(f,line)){std::istringstream s(line);std::string frame,event,cycles,gpr,value;std::getline(s,frame,',');std::getline(s,event,',');std::getline(s,cycles,',');std::getline(s,gpr,',');std::getline(s,value,',');if(frame.empty())continue;
        const auto n=static_cast<std::uint64_t>(std::stoull(frame));const auto reg=static_cast<std::uint8_t>(std::stoul(gpr,nullptr,16));const auto val=static_cast<std::uint32_t>(std::stoul(value,nullptr,16));d.firmware_event_schedule.push_back({n,reg,val});last_event_frame=std::max(last_event_frame,n);}
    event_count=d.firmware_event_schedule.size();p.validation_receipt_valid=p.initialization_state_valid=p.program_identity_valid=p.pipeline_reset_valid=p.routing_valid=true;return p;
}
static FactoryRuntime load_runtime(const ValidatedEffectPackage& p,RateMode mode){FactoryRuntime r;if(!r.loadEffect(p,mode))throw std::runtime_error(std::string("validated HALL runtime load failed: ")+r.getStatus().message);if(!r.reset())throw std::runtime_error(std::string("validated HALL runtime reset failed: ")+r.getStatus().message);return r;}
static void write_group(FactoryRuntime& r,const Group& g){const auto frame=r.getStatus().processed_dsp_frames;for(std::size_t i=0;i<g.size();++i)if(!r.setRegister(kRegisters[i],g[i],frame))throw std::runtime_error(std::string("cannot schedule test-only OS group: ")+r.getStatus().message);std::array<float,2> z{},o{};if(!r.processStereo(z.data(),o.data(),1,r.getStatus().processing_rate_hz))throw std::runtime_error("test-only register group application failed");}
struct Summary{std::size_t frames=0,finite=0;double rms=0,corr=0;float peak=0;std::vector<double>windows;std::vector<float>audio;};
static Summary render(FactoryRuntime& runtime,const char* stimulus,double rate,std::size_t frames){
    Summary m;m.frames=frames;m.audio.resize(frames*2);const std::size_t win=static_cast<std::size_t>(std::llround(rate*0.1));std::vector<double> energy((frames+win-1)/win),cross(energy.size()),left(energy.size()),right(energy.size());std::vector<std::size_t> count(energy.size());double all=0;
    constexpr std::array<std::size_t,4> blocks{127,256,64,193};std::array<float,512> in{},out{};std::size_t cursor=0,block=0;
    while(cursor<frames){const auto n=std::min(blocks[block++%blocks.size()],frames-cursor);for(std::size_t i=0;i<n;++i){auto v=input_sample(stimulus,cursor+i,rate);in[2*i]=v.first;in[2*i+1]=v.second;}
        if(!runtime.processStereo(in.data(),out.data(),n,rate))throw std::runtime_error("runtime audio processing failed");
        for(std::size_t i=0;i<n;++i){const float l=out[2*i],r=out[2*i+1];if(!std::isfinite(l)||!std::isfinite(r))throw std::runtime_error("non-finite wet output");m.finite+=2;all+=double(l)*l+double(r)*r;m.peak=std::max({m.peak,std::abs(l),std::abs(r)});const auto w=(cursor+i)/win;energy[w]+=double(l)*l+double(r)*r;left[w]+=double(l)*l;right[w]+=double(r)*r;cross[w]+=double(l)*r;++count[w];m.audio[2*(cursor+i)]=l;m.audio[2*(cursor+i)+1]=r;}cursor+=n;}
    m.rms=std::sqrt(all/(2*frames));m.windows.reserve(energy.size());double c=0,l=0,r=0;for(std::size_t i=0;i<energy.size();++i){m.windows.push_back(count[i]?std::sqrt(energy[i]/(2*count[i])):0);c+=cross[i];l+=left[i];r+=right[i];}m.corr=(l>0&&r>0)?c/std::sqrt(l*r):0;return m;
}
static void print_windows(const std::vector<double>& w){std::cout<<'[';for(std::size_t i=0;i<w.size();++i){if(i)std::cout<<',';std::cout<<std::setprecision(10)<<w[i];}std::cout<<']';}
int main(int argc,char**argv) try {
    if(argc!=8)throw std::runtime_error("usage: test_hall_extreme_range_audio checkpoint register-table output-dir schedule program-sha checkpoint-sha duration-seconds");
    const std::string checkpoint=argv[1],table_path=argv[2],outdir=argv[3],schedule=argv[4],program_hash=argv[5],checkpoint_hash=argv[6];
    const auto requested_seconds=std::stod(argv[7]);if(requested_seconds<8.0||requested_seconds>12.0)throw std::runtime_error("render duration must be 8..12 seconds");
    const auto groups=read_table(table_path);std::filesystem::create_directories(outdir);
    std::size_t scheduled_events=0;std::uint64_t last_event=0;const auto pkg=make_package(checkpoint,schedule,program_hash,checkpoint_hash,scheduled_events,last_event);
    std::cout<<"{\"schema\":\"trollfx-asr10-hall-extreme-audio-v1\",\"schedule_events\":"<<scheduled_events<<",\"last_schedule_frame\":"<<last_event<<",\"duration_seconds\":"<<requested_seconds<<",\"runs\":[\n";
    bool first=true;
    for(std::size_t ri=0;ri<kRates.size();++ri){const auto rate=kRates[ri];const auto mode=ri==0?RateMode::FactoryReference:RateMode::Experimental48000;const auto frames=static_cast<std::size_t>(std::llround(rate*requested_seconds));
        for(std::size_t si=0;si<kStimuli.size();++si)for(unsigned raw:kRawCodes){auto runtime=load_runtime(pkg,mode);const auto settle_frames=static_cast<std::size_t>(last_event+2);std::vector<float> zeros(settle_frames*2),settle_out(settle_frames*2);
            // Initialize and consume every validated post-RUN firmware event before editing.
            constexpr std::size_t max_chunk=256;for(std::size_t p=0;p<settle_frames;p+=max_chunk){const auto n=std::min(max_chunk,settle_frames-p);if(!runtime.processStereo(zeros.data()+2*p,settle_out.data()+2*p,n,rate))throw std::runtime_error("firmware schedule settling failed");}
            const auto settled=runtime.getStatus();if(settled.scheduled_writes_applied!=scheduled_events)throw std::runtime_error("firmware schedule did not complete exactly");
            Group before{};for(std::size_t i=0;i<5;++i)before[i]=runtime.qaReadRegister(kRegisters[i]);
            write_group(runtime,groups[raw]);Group applied{};for(std::size_t i=0;i<5;++i)applied[i]=runtime.qaReadRegister(kRegisters[i]);if(applied!=groups[raw])throw std::runtime_error("OS register group failed readback before audio");
            const auto metrics=render(runtime,kStimuli[si],rate,frames);Group after{};for(std::size_t i=0;i<5;++i)after[i]=runtime.qaReadRegister(kRegisters[i]);if(after!=applied)throw std::runtime_error("selected registers changed during tail render");
            const auto writes_after=runtime.getStatus().scheduled_writes_applied;if(writes_after!=scheduled_events+5)throw std::runtime_error("unexpected scheduled write count after parameter group");
            const auto wav_rate=static_cast<std::uint32_t>(std::llround(rate));const auto file=std::string(outdir)+"/hall_"+(ri==0?"factory29762":"experimental48000")+"_"+kStimuli[si]+"_raw"+std::to_string(raw)+".wav";write_float_wav(file,metrics.audio,wav_rate);
            if(!first)std::cout<<",\n";
            first=false;
            std::cout<<"{\"rate_hz\":"<<std::setprecision(12)<<rate<<",\"rate_mode\":\""<<(ri==0?"FactoryReference":"Experimental48000")<<"\",\"stimulus\":\""<<kStimuli[si]<<"\",\"seed\":"<<kNoiseSeed<<",\"raw\":"<<raw<<",\"frames\":"<<frames<<",\"wav\":\""<<std::filesystem::path(file).filename().string()<<"\",\"rms\":"<<metrics.rms<<",\"peak\":"<<metrics.peak<<",\"stereo_cosine_correlation_uncentered\":"<<metrics.corr<<",\"finite_samples\":"<<metrics.finite<<",\"schedule_writes_applied\":"<<scheduled_events<<",\"writes_after_edit\":"<<writes_after<<",\"registers_before_edit\":"<<hex_group(before)<<",\"registers_before_render\":"<<hex_group(applied)<<",\"registers_after_render\":"<<hex_group(after)<<",\"rms_100ms\":";print_windows(metrics.windows);std::cout<<'}';
        }
        for(std::size_t si=0;si<kStimuli.size();++si){const unsigned raw=51;auto runtime=load_runtime(pkg,mode);const auto settle_frames=static_cast<std::size_t>(last_event+2);std::vector<float> zeros(settle_frames*2),o(settle_frames*2);for(std::size_t p=0;p<settle_frames;p+=256){auto n=std::min<std::size_t>(256,settle_frames-p);if(!runtime.processStereo(zeros.data()+2*p,o.data()+2*p,n,rate))throw std::runtime_error("repeat schedule settling failed");}if(runtime.getStatus().scheduled_writes_applied!=scheduled_events)throw std::runtime_error("repeat firmware events incomplete");write_group(runtime,groups[raw]);auto m=render(runtime,kStimuli[si],rate,frames);
            const auto file=std::string(outdir)+"/hall_"+(ri==0?"factory29762":"experimental48000")+"_"+kStimuli[si]+"_raw51_repeat.wav";write_float_wav(file,m.audio,static_cast<std::uint32_t>(std::llround(rate)));if(!first)std::cout<<",\n";
            first=false;
            std::cout<<"{\"rate_hz\":"<<std::setprecision(12)<<rate<<",\"rate_mode\":\""<<(ri==0?"FactoryReference":"Experimental48000")<<"\",\"stimulus\":\""<<kStimuli[si]<<"\",\"seed\":"<<kNoiseSeed<<",\"raw\":51,\"repeat\":true,\"frames\":"<<frames<<",\"wav\":\""<<std::filesystem::path(file).filename().string()<<"\",\"rms\":"<<m.rms<<",\"peak\":"<<m.peak<<",\"stereo_cosine_correlation_uncentered\":"<<m.corr<<",\"finite_samples\":"<<m.finite<<",\"schedule_writes_applied\":"<<scheduled_events<<",\"writes_after_edit\":"<<runtime.getStatus().scheduled_writes_applied<<",\"registers_before_render\":"<<hex_group(groups[raw])<<",\"registers_after_render\":"<<hex_group(groups[raw])<<",\"rms_100ms\":";print_windows(m.windows);std::cout<<'}';
        }
    }
    std::cout<<"\n]}\n";return 0;
} catch(const std::exception&e){std::cerr<<"HALL_EXTREME_AUDIO_FAIL: "<<e.what()<<'\n';return 1;}
