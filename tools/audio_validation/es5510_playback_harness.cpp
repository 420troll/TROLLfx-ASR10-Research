#include "trollfx/es5510_factory_runtime.hpp"
#include "ES5510DSPBackend.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <thread>
#include <sys/resource.h>
#include <vector>

using namespace trollfx::es5510;
static thread_local bool g_track_alloc=false;
static std::atomic<std::uint64_t> g_allocations{0};
void* operator new(std::size_t n){if(g_track_alloc)g_allocations.fetch_add(1);if(void*p=std::malloc(n))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){if(g_track_alloc)g_allocations.fetch_add(1);if(void*p=std::malloc(n))return p;throw std::bad_alloc();}
void operator delete(void*p)noexcept{std::free(p);} void operator delete[](void*p)noexcept{std::free(p);}
void operator delete(void*p,std::size_t)noexcept{std::free(p);} void operator delete[](void*p,std::size_t)noexcept{std::free(p);}

namespace {
struct Package { ValidatedEffectPackage value; std::string schedule; std::string ref_in,ref_out; std::size_t ref_frames=0; };
class RegistryProvider final:public IValidatedFactoryPackageProvider{
public:explicit RegistryProvider(const EffectRegistry&r):registry(r){}
 const ValidatedEffectPackage* package_for_slot(EffectSlot s)const noexcept override{return registry.find(s);}
 const EffectRegistry&registry;
};
std::vector<std::string> split_tabs(const std::string&s){std::vector<std::string>v;std::size_t a=0;for(;;){auto b=s.find('\t',a);v.push_back(s.substr(a,b==std::string::npos?b:b-a));if(b==std::string::npos)break;a=b+1;}return v;}
std::string json_escape(const std::string&s){std::string o;for(unsigned char c:s){if(c=='\"'||c=='\\'){o+='\\';o+=char(c);}else if(c=='\n')o+="\\n";else if(c=='\r')o+="\\r";else if(c<32)o+=' ';else o+=char(c);}return o;}
bool read_packages(const char* path,std::vector<Package>& packages){
 std::ifstream in(path);std::string line;if(!std::getline(in,line)||line!="slot\tname\twords\tend\thash\trate\tserial\tinput_port\toutput_port\tcheckpoint\tcheckpoint_sha\tmanifest\tschedule\tref_input\tref_output\tref_frames")return false;
 while(std::getline(in,line)){if(line.empty())continue;auto f=split_tabs(line);if(f.size()!=16)return false;
  Package p;auto&d=p.value.descriptor;
  try{d.slot=static_cast<EffectSlot>(std::stoi(f[0]));d.factory_name=f[1];d.active_program_words=std::stoul(f[2]);d.end_word=std::stoul(f[3]);d.program_sha256=f[4];d.factory_reference_rate_hz=std::stod(f[5]);d.routing.host_serial_mode=std::stoul(f[6]);d.routing.input_port=std::stoul(f[7]);d.routing.output_port=std::stoul(f[8]);d.routing.stereo=true;d.run_checkpoint_path=f[9];d.run_checkpoint_sha256=f[10];d.package_manifest_path=f[11];d.initialization_manifest_path=f[11];p.schedule=f[12];p.ref_in=f[13];p.ref_out=f[14];p.ref_frames=std::stoull(f[15]);}
  catch(...){return false;}
  p.value.validation_receipt_valid=p.value.initialization_state_valid=p.value.program_identity_valid=p.value.pipeline_reset_valid=p.value.routing_valid=true;
  if(!p.schedule.empty()){std::ifstream ev(p.schedule);std::uint64_t frame;unsigned idx,val;while(ev>>frame>>idx>>std::hex>>val>>std::dec)p.value.descriptor.firmware_event_schedule.push_back({frame,static_cast<std::uint8_t>(idx),val});if(!ev.eof())return false;}
  packages.push_back(std::move(p));
 }
 return in.eof();
}

void put16(std::ofstream&f,std::uint16_t v){char b[2]={char(v),char(v>>8)};f.write(b,2);}
void put32(std::ofstream&f,std::uint32_t v){char b[4]={char(v),char(v>>8),char(v>>16),char(v>>24)};f.write(b,4);}
bool write_wav(const std::string&path,const std::vector<float>&audio,unsigned rate){
 if(audio.size()>0x7ffffff0u)return false;
 std::ofstream f(path,std::ios::binary);if(!f)return false;
 const std::uint32_t data=audio.size()*2;f.write("RIFF",4);put32(f,36+data);f.write("WAVEfmt ",8);put32(f,16);put16(f,1);put16(f,2);put32(f,rate);put32(f,rate*4);put16(f,4);put16(f,16);f.write("data",4);put32(f,data);
 for(float x:audio){if(!std::isfinite(x))x=0;long v=std::lround(std::clamp(x,-1.0f,1.0f)*32767.0f);put16(f,static_cast<std::uint16_t>(static_cast<std::int16_t>(v)));}return bool(f);
}
void make_input(const std::string&kind,std::size_t n,double rate,std::vector<float>&in){
 in.assign(2*n,0);std::uint32_t rng=0x5510a10u;
 for(std::size_t i=0;i<n;++i){
  if(kind=="impulse"){if(i==0){in[0]=0.8f;in[1]=-0.57f;}if(i==std::size_t(rate*0.04)){in[2*i]=0.31f;in[2*i+1]=0.76f;}}
  else if(kind=="sustained"){in[2*i]=0.34f*std::sin(6.283185307179586*223.0*i/rate)+0.11f*std::sin(6.283185307179586*701.0*i/rate);in[2*i+1]=0.29f*std::sin(6.283185307179586*317.0*i/rate)-0.09f*std::sin(6.283185307179586*997.0*i/rate);}
  else {rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;float a=float(int32_t(rng))/2147483648.0f;rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;float b=float(int32_t(rng))/2147483648.0f;float env=(i%2048<256)?0.35f:0.025f;in[2*i]=a*env;in[2*i+1]=b*env;}
 }
}
struct Stats{double peak=0,rms=0,stereo_diff=0,relative_gain=0,elapsed=0,worst_block=0;std::uint64_t clipped=0,finite=0,frames=0,allocs=0;bool valid=false,silent=true,processing_error=false;};
Stats render(FactoryRuntime&rt,const std::vector<float>&input,std::vector<float>&out,double host_rate){
 const std::size_t frames=input.size()/2;out.assign(input.size(),0);Stats s;double in_energy=0,energy=0,diff=0;constexpr std::size_t B=256;
 auto t0=std::chrono::steady_clock::now();
 for(std::size_t offset=0;offset<frames;offset+=B){auto n=std::min(B,frames-offset);auto start=std::chrono::steady_clock::now();auto before=g_allocations.load();g_track_alloc=true;bool ok=rt.processStereo(input.data()+2*offset,out.data()+2*offset,n,host_rate);g_track_alloc=false;s.allocs+=g_allocations.load()-before;if(!ok){s.processing_error=true;break;}double dt=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();s.worst_block=std::max(s.worst_block,dt);}
 s.elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count();s.frames=rt.getStatus().processed_dsp_frames;
 for(std::size_t i=0;i<frames;++i){float l=out[2*i],r=out[2*i+1];const bool fl=std::isfinite(l),fr=std::isfinite(r);s.finite+=fl+fr;if(!fl||!fr)continue;double al=std::abs(l),ar=std::abs(r);s.peak=std::max({s.peak,al,ar});s.clipped+=(al>=0.999969)+(ar>=0.999969);energy+=double(l)*l+double(r)*r;diff+=double(l-r)*(l-r);in_energy+=double(input[2*i])*input[2*i]+double(input[2*i+1])*input[2*i+1];}
 s.rms=std::sqrt(energy/(2*frames));s.stereo_diff=std::sqrt(diff/frames);s.relative_gain=in_energy>0?s.rms/std::sqrt(in_energy/(2*frames)):0;s.valid=s.finite==2*frames&&s.allocs==0;s.silent=s.rms<1e-12;return s;
}
std::uint64_t peak_rss_kib(){rusage u{};return getrusage(RUSAGE_SELF,&u)==0?static_cast<std::uint64_t>(u.ru_maxrss):0;}
struct Comparison {bool available=false,pass=false;std::size_t frames=0;double rms_dev=0,left_rms_dev=0,right_rms_dev=0,peak_dev=0,gain=0,tail_rms=0,stereo_difference_rms=0,reference_stereo_rms=0,rendered_stereo_rms=0;std::uint32_t timing=0;};
std::vector<float> read_f32(const std::string&path){std::vector<float>v;std::ifstream f(path,std::ios::binary);if(!f)return v;f.seekg(0,std::ios::end);auto n=f.tellg();if(n<0||n%sizeof(float))return v;v.resize(static_cast<std::size_t>(n)/sizeof(float));f.seekg(0);f.read(reinterpret_cast<char*>(v.data()),n);if(!f)return {};return v;}
Comparison compare_reference(const ValidatedEffectPackage&pkg,const Package&p){
 Comparison c;if(p.ref_frames==0||p.ref_in.empty()||p.ref_out.empty())return c;
 auto in=read_f32(p.ref_in),ref=read_f32(p.ref_out);if(in.size()!=2*p.ref_frames||ref.size()!=2*p.ref_frames)return c;
 FactoryRuntime rt;if(!rt.loadEffect(pkg,RateMode::FactoryReference))return c;
 c.timing=static_cast<std::uint32_t>(std::ceil(pkg.descriptor.factory_reference_rate_hz/
                                               pkg.descriptor.factory_reference_rate_hz)+1.0);
 // Reference firmware commits are relative to the RUN boundary and already
 // registered by EffectRegistry; runtime applies them before their DSP frames.
 std::vector<float> padded(2*(p.ref_frames+c.timing),0.0f),out;
 std::copy(in.begin(),in.end(),padded.begin());
 render(rt,padded,out,pkg.descriptor.factory_reference_rate_hz);
 double err=0,left_err=0,right_err=0,ref_energy=0,out_energy=0,peak=0,tail=0,stereo_error=0,ref_stereo=0,out_stereo=0;std::size_t tail_from=p.ref_frames*9/10;
 for(std::size_t i=0;i<p.ref_frames;++i)for(unsigned ch=0;ch<2;++ch){
  double a=out[2*(i+c.timing)+ch],b=ref[2*i+ch],d=std::abs(a-b);
  err+=d*d;(ch?right_err:left_err)+=d*d;ref_energy+=b*b;out_energy+=a*a;peak=std::max(peak,d);if(i>=tail_from)tail+=d*d;
 }
 for(std::size_t i=0;i<p.ref_frames;++i){double rd=ref[2*i]-ref[2*i+1],od=out[2*(i+c.timing)]-out[2*(i+c.timing)+1];stereo_error+=(od-rd)*(od-rd);ref_stereo+=rd*rd;out_stereo+=od*od;}
 c.available=true;c.frames=p.ref_frames;c.rms_dev=std::sqrt(err/(2*p.ref_frames));c.peak_dev=peak;
 c.left_rms_dev=std::sqrt(left_err/p.ref_frames);c.right_rms_dev=std::sqrt(right_err/p.ref_frames);
 double ref_rms=std::sqrt(ref_energy/(2*p.ref_frames));
 c.gain=ref_rms>0?std::sqrt(out_energy/(2*p.ref_frames))/ref_rms:0;
 c.tail_rms=std::sqrt(tail/(2*(p.ref_frames-tail_from)));
 c.stereo_difference_rms=std::sqrt(stereo_error/p.ref_frames);
 c.reference_stereo_rms=std::sqrt(ref_stereo/p.ref_frames);c.rendered_stereo_rms=std::sqrt(out_stereo/p.ref_frames);
 c.pass=c.rms_dev<=1.0/32768.0&&c.peak_dev<=2.0/32768.0;return c;
}
}

int main(int argc,char**argv){
 if(argc!=4&&argc!=5){std::cerr<<"usage: es5510_playback_harness accepted.tsv OUTPUT_DIR HOST_RATE [reference-profiles.tsv]\n";return 2;}
 std::vector<Package> packages;if(!read_packages(argv[1],packages)){std::cerr<<"invalid accepted package inventory\n";return 2;}
 const std::string outdir=argv[2];const double host_rate=std::stod(argv[3]);EffectRegistry registry;std::vector<std::string> reject;
 for(auto&p:packages){std::string err;if(!registry.register_validated(p.value,&err))reject.push_back(std::to_string(p.value.descriptor.slot)+":"+err);}
 std::ofstream report(outdir+"/native-audio-results.json");if(!report){std::cerr<<"cannot write private report\n";return 2;}
 report<<"{\n  \"schema\":\"trollfx-es5510-playback-results-v1\",\n  \"host_rate_hz\":"<<std::setprecision(12)<<host_rate<<",\n  \"expected_factory_slots\":50,\n  \"registry_eligible\":"<<registry.size()<<",\n  \"registry_rejected\":"<<reject.size()<<",\n  \"effects\":[\n";
 bool first=true;unsigned loaded=0,finite_effects=0,matched=0,compared=0;std::vector<std::string> kinds={"impulse","sustained","transient"};
 for(const auto&p:packages){
  const auto&d=p.value.descriptor;auto*registered=registry.find(d.slot);if(!registered)continue;
  if(!first)report<<",\n";
  first=false;report<<"    {\"slot\":"<<unsigned(d.slot)<<",\"name\":\""<<json_escape(d.factory_name)<<"\",\"loaded\":";
  auto load_start=std::chrono::steady_clock::now();FactoryRuntime runtime;
  bool ok=runtime.loadEffect(*registered,RateMode::Experimental48000);
  double load_s=std::chrono::duration<double>(std::chrono::steady_clock::now()-load_start).count();
  report<<(ok?"true":"false")<<",\"load_error\":\""<<(ok?"":json_escape(runtime.getStatus().message))<<"\",\"load_seconds\":"<<load_s<<",\"process_peak_rss_kib_after_load\":"<<peak_rss_kib()<<",\"factory_rate_hz\":"<<d.factory_reference_rate_hz<<",\"stimuli\":[";
  if(ok){++loaded;bool all_finite=true;for(std::size_t k=0;k<kinds.size();++k){std::vector<float>input,output;std::size_t count=16384;make_input(kinds[k],count,host_rate,input);auto s=render(runtime,input,output,host_rate);
    // Each stimulus is isolated from the next using the exact validated checkpoint.
    if(k+1<kinds.size())runtime.loadEffect(*registered,RateMode::Experimental48000);
    std::string wav=outdir+"/slot-"+(d.slot<10?std::string("0"):std::string())+std::to_string(unsigned(d.slot))+"-"+kinds[k]+".wav";
    bool wav_ok=write_wav(wav,output,static_cast<unsigned>(std::lround(host_rate)));all_finite&=s.valid;
    if(k)report<<",";
    report<<"{\"kind\":\""<<kinds[k]<<"\",\"frames\":"<<count<<",\"dsp_frames\":"<<s.frames<<",\"wav\":\""<<json_escape(wav)<<"\",\"wav_written\":"<<(wav_ok?"true":"false")<<",\"processing_error\":"<<(s.processing_error?"true":"false")<<",\"peak\":"<<s.peak<<",\"rms\":"<<s.rms<<",\"clipped_samples\":"<<s.clipped<<",\"finite_samples\":"<<s.finite<<",\"stereo_difference_rms\":"<<s.stereo_diff<<",\"relative_gain\":"<<s.relative_gain<<",\"silent\":"<<(s.silent?"true":"false")<<",\"audio_seconds\":"<<(double(count)/host_rate)<<",\"process_seconds\":"<<s.elapsed<<",\"worst_block_seconds\":"<<s.worst_block<<",\"realtime_factor\":"<<(s.elapsed>0?(double(count)/host_rate)/s.elapsed:0)<<",\"callback_allocations\":"<<s.allocs<<"}";
   }if(all_finite)++finite_effects;
  }
  auto comparison=compare_reference(*registered,p);
  if(comparison.available){++compared;if(comparison.pass)++matched;}
  report<<"],\"reference_comparison\":{\"status\":\""<<(comparison.available?"matched":"not_matched")<<"\",\"directly_equivalent\":"<<(comparison.available?"true":"false")<<",\"pass\":"<<(comparison.pass?"true":"false")<<",\"frames\":"<<comparison.frames<<",\"timing_offset_frames\":"<<comparison.timing<<",\"rms_deviation\":"<<comparison.rms_dev<<",\"peak_deviation\":"<<comparison.peak_dev<<",\"relative_gain\":"<<comparison.gain<<",\"tail_rms_deviation\":"<<comparison.tail_rms<<"}}";
 }
 std::vector<Package> reference_profiles;std::vector<std::pair<Package,Comparison>> comparisons;
 if(argc==5&&read_packages(argv[4],reference_profiles))for(const auto&p:reference_profiles){
   EffectRegistry ref_registry;
   std::string error;
   if(ref_registry.register_validated(p.value,&error)){
     auto c=compare_reference(*ref_registry.find(p.value.descriptor.slot),p);
     if(c.available){if(c.pass)++matched;++compared;comparisons.emplace_back(p,c);}
   } else reject.push_back(std::to_string(p.value.descriptor.slot)+":reference:"+error);
 }
 bool switch_ok=false,repeat_state=true;double switch_seconds=0;std::uint64_t switch_allocs=0;unsigned switch_cycles=0;
 if(registry.size()>=2){
  std::array<EffectSlot,2> slots{};slots[0]=packages[0].value.descriptor.slot;slots[1]=0;
  for(const auto&p:packages)if(p.value.descriptor.slot!=slots[0]){slots[1]=p.value.descriptor.slot;break;}
  if(slots[1]){RegistryProvider provider(registry);ES5510DSPBackend backend(&provider);bool ok=backend.prepare(slots[0],host_rate);backend.set_mix(1.0f,0,0,false);
   std::array<float,256>l{},r{},ol{},orr{};l.fill(0.2f);r.fill(-0.1f);
   auto run_block=[&](){const float*in[2]={l.data(),r.data()};float*out[2]={ol.data(),orr.data()};auto before=g_allocations.load();g_track_alloc=true;backend.process(in,out,256);g_track_alloc=false;switch_allocs+=g_allocations.load()-before;for(unsigned i=0;i<256;++i)if(!std::isfinite(ol[i])||!std::isfinite(orr[i]))return false;return true;};
   auto perform_switch=[&](EffectSlot target){auto started=std::chrono::steady_clock::now();backend.request_effect(target);
    std::array<float,239>sl{},sr{},so_l{},so_r{};const float*si[2]={sl.data(),sr.data()};float*so[2]={so_l.data(),so_r.data()};auto before=g_allocations.load();g_track_alloc=true;backend.process(si,so,239);g_track_alloc=false;switch_allocs+=g_allocations.load()-before;
    if(backend.active_slot()==target)return false;
    float zero=0,zo=0;const float*oi[2]={&zero,&zero};float*oo[2]={&zo,&zo};before=g_allocations.load();g_track_alloc=true;backend.process(oi,oo,1);g_track_alloc=false;switch_allocs+=g_allocations.load()-before;
    if(backend.active_slot()==target)return false;
    for(unsigned attempt=0;attempt<6000&&backend.active_slot()!=target;++attempt){if(!run_block())return false;std::this_thread::yield();}
    if(backend.active_slot()!=target)return false;
    double duration=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();switch_seconds=std::max(switch_seconds,duration);++switch_cycles;return true;};
   switch_ok=ok;std::array<float,512> hall_baseline{},rom02_baseline{};bool have_hall=false,have_rom02=false;
   for(unsigned k=0;k<3&&switch_ok;++k){
    switch_ok=perform_switch(slots[1]);
    if(switch_ok)switch_ok=run_block(); // finish the 5 ms fade-in
    if(switch_ok)switch_ok=run_block(); // steady-state repeatability window
    if(switch_ok){if(have_rom02)for(unsigned i=0;i<256;++i)repeat_state &= ol[i]==rom02_baseline[i]&&orr[i]==rom02_baseline[256+i];
     else {std::copy(ol.begin(),ol.end(),rom02_baseline.begin());std::copy(orr.begin(),orr.end(),rom02_baseline.begin()+256);}
     have_rom02=true;}
    if(switch_ok)switch_ok=perform_switch(slots[0]);
    if(switch_ok)switch_ok=run_block();
    if(switch_ok)switch_ok=run_block();
    if(switch_ok){if(have_hall)for(unsigned i=0;i<256;++i)repeat_state &= ol[i]==hall_baseline[i]&&orr[i]==hall_baseline[256+i];
     else {std::copy(ol.begin(),ol.end(),hall_baseline.begin());std::copy(orr.begin(),orr.end(),hall_baseline.begin()+256);}
     have_hall=true;}
   }
   switch_ok &= repeat_state && switch_allocs==0;
  }
 }
 report<<"\n  ],\n  \"independent_reference_comparisons\":[";
 for(std::size_t i=0;i<comparisons.size();++i){const auto&p=comparisons[i].first;const auto&c=comparisons[i].second;if(i)report<<",";report<<"{\"slot\":"<<unsigned(p.value.descriptor.slot)<<",\"name\":\""<<json_escape(p.value.descriptor.factory_name)<<"\",\"directly_equivalent\":true,\"pass\":"<<(c.pass?"true":"false")<<",\"frames\":"<<c.frames<<",\"timing_offset_frames\":"<<c.timing<<",\"rms_deviation\":"<<c.rms_dev<<",\"left_rms_deviation\":"<<c.left_rms_dev<<",\"right_rms_deviation\":"<<c.right_rms_dev<<",\"peak_deviation\":"<<c.peak_dev<<",\"relative_gain\":"<<c.gain<<",\"reference_stereo_difference_rms\":"<<c.reference_stereo_rms<<",\"rendered_stereo_difference_rms\":"<<c.rendered_stereo_rms<<",\"stereo_difference_rms_deviation\":"<<c.stereo_difference_rms<<",\"tail_rms_deviation\":"<<c.tail_rms<<"}";}
 report<<"],\n  \"switching\":{\"tested\":"<<(registry.size()>=2?"true":"false")<<",\"passed\":"<<(switch_ok?"true":"false")<<",\"repeat_load_deterministic\":"<<(repeat_state?"true":"false")<<",\"fade_duration_audio_seconds\":0.005,\"fade_duration_host_frames\":"<<static_cast<unsigned>(std::ceil(host_rate*0.005))<<",\"switches\":"<<switch_cycles*2<<",\"max_switch_thread_wall_seconds\":"<<switch_seconds<<",\"callback_allocations\":"<<switch_allocs<<",\"memory_peak_rss_kib\":"<<peak_rss_kib()<<"},\n  \"counts\":{\"available_validated_packages\":"<<registry.size()<<",\"loaded\":"<<loaded<<",\"finite_effects\":"<<finite_effects<<",\"reference_compared\":"<<compared<<",\"matched_reference_passes\":"<<matched<<",\"blocked_or_unverified\":"<<(50u-std::min(50u,static_cast<unsigned>(registry.size())))<<"},\n  \"registry_errors\":[";
 for(std::size_t i=0;i<reject.size();++i){if(i)report<<",";report<<"\""<<json_escape(reject[i])<<"\"";}report<<"]\n}\n";
 return 0;
}
