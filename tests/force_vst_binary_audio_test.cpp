#include "mpc_vst2_abi.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <new>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

static thread_local bool in_audio=false;
static std::atomic<unsigned long long> callback_allocations{0};
void* operator new(std::size_t n){if(in_audio)callback_allocations.fetch_add(1);if(void*p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){if(in_audio)callback_allocations.fetch_add(1);if(void*p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void operator delete(void*p)noexcept{std::free(p);}void operator delete[](void*p)noexcept{std::free(p);}
void operator delete(void*p,std::size_t)noexcept{std::free(p);}void operator delete[](void*p,std::size_t)noexcept{std::free(p);}

namespace {
constexpr int kRate=48000,kMaxBlock=256,kStatusParam=5,kEffectParam=0;
struct ParameterProbe { unsigned slot; int index; const char* lower; const char* upper; };
constexpr ParameterProbe kVerifiedParameters[] = {
 {1,12,"40","41"},{1,13,"31","32"},{3,14,"64","65"},
 {3,15,"50","51"},{3,16,"9","10"},{4,17,"350","351"},
 {6,18,"24","25"},{7,19,"20","21"},{28,20,"+12","+13"},
 {41,21,"-11","-10"},{42,22,"4/1","5/1"},{49,23,"100","101"},
 {5,24,"350","351"},{8,25,"20","21"},{39,26,"LONG/SMOOTHER","SHORT/COARSER"}
};
constexpr ParameterProbe kV4VerifiedParameters[] = {
 {1,27,"28","29"},{1,28,"28","29"},{1,29,"40","41"},{1,30,"31","32"},
 {2,31,"25","26"},{2,32,"25","26"},
 {3,33,"64","65"},{3,34,"50","51"},{3,35,"9","10"},
 {4,36,"350","351"},{5,37,"350","351"},{6,38,"24","25"},
 {7,39,"20","21"},{8,40,"20","21"},{28,41,"+12","+13"},
 {39,42,"LONG/SMOOTHER","SHORT/COARSER"},{41,43,"-11","-10"},
 {42,44,"4/1","5/1"},{49,45,"100","101"}
};
struct Host{double rate=kRate;int block=kMaxBlock;AEffect* effect=nullptr;} host;
VstIntPtr host_callback(AEffect*,VstInt32 op,VstInt32,VstIntPtr,void*,float){
 switch(op){case audioMasterVersion:return 2400;case audioMasterGetSampleRate:return static_cast<VstIntPtr>(host.rate);case audioMasterGetBlockSize:return host.block;case audioMasterGetVendorVersion:return 0x0101;default:return 0;}
}
using Entry=AEffect*(*)(audioMasterCallback);
struct Plugin {
 void* library=nullptr;AEffect* effect=nullptr;
 explicit Plugin(const std::string&path){library=dlopen(path.c_str(),RTLD_NOW|RTLD_LOCAL);if(!library)throw std::runtime_error(dlerror());auto entry=reinterpret_cast<Entry>(dlsym(library,"VSTPluginMain"));if(!entry)throw std::runtime_error("VSTPluginMain missing from packaged binary");effect=entry(host_callback);if(!effect||effect->magic!=kEffectMagic||effect->resvd2!=0||!effect->object||effect->numInputs!=2||effect->numOutputs!=2||!effect->processReplacing)throw std::runtime_error("VST entry/ABI initialization failed");host.effect=effect;effect->dispatcher(effect,effOpen,0,0,nullptr,0);effect->dispatcher(effect,effSetSampleRate,0,0,nullptr,float(kRate));effect->dispatcher(effect,effSetBlockSize,0,kMaxBlock,nullptr,0);effect->dispatcher(effect,effMainsChanged,0,1,nullptr,0);}
 ~Plugin(){if(effect){effect->dispatcher(effect,effMainsChanged,0,0,nullptr,0);effect->dispatcher(effect,effClose,0,0,nullptr,0);}if(library)dlclose(library);host.effect=nullptr;}
 int plain_status(){char text[64]{};effect->dispatcher(effect,effGetParamDisplay,kStatusParam,0,text,0);if(std::strcmp(text,"READY")==0)return 3;if(std::strcmp(text,"LOADING")==0)return 2;if(std::strcmp(text,"UNAVAIL")==0)return 1;if(std::strcmp(text,"MISSING")==0)return 0;if(std::strcmp(text,"LOAD ERR")==0)return 4;return -1;}
 bool selected_effect_ready(){char text[64]{};effect->dispatcher(effect,effGetParamDisplay,kEffectParam,0,text,0);return std::strstr(text,"/ READY")!=nullptr;}
 bool selected_effect_unavailable(){char text[64]{};effect->dispatcher(effect,effGetParamDisplay,kEffectParam,0,text,0);return std::strstr(text,"UNAVAILABLE")||std::strstr(text,"PACKAGE REQUIRED")||std::strstr(text,"LOAD FAILED");}
 void select(unsigned slot){effect->setParameter(effect,kEffectParam,float(slot-1)/49.0f);}
 void set(int index,float normalized){effect->setParameter(effect,index,normalized);}
 float get(int index)const{return effect->getParameter(effect,index);}
 std::string display(int index)const{char text[64]{};effect->dispatcher(effect,effGetParamDisplay,index,0,text,0);return text;}
};
void callback(Plugin&p,const float*il,const float*ir,float*ol,float*orr,int n){float*inputs[2]={const_cast<float*>(il),const_cast<float*>(ir)};float*outputs[2]={ol,orr};auto before=callback_allocations.load();in_audio=true;p.effect->processReplacing(p.effect,inputs,outputs,n);in_audio=false;if(callback_allocations.load()!=before)throw std::runtime_error("allocation occurred in packaged VST callback");}
struct Stimulus{std::vector<float> data;std::size_t frames=0;explicit Stimulus(const std::string&path){std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("input stimulus missing");f.seekg(0,std::ios::end);auto size=f.tellg();if(size<=0||size%(2*sizeof(float)))throw std::runtime_error("input stimulus must be stereo float32");frames=static_cast<std::size_t>(size)/(2*sizeof(float));data.resize(frames*2);f.seekg(0);f.read(reinterpret_cast<char*>(data.data()),size);if(!f)throw std::runtime_error("cannot read input stimulus");}};
struct BlockResult{std::vector<float> output;unsigned long long callbacks=0;std::size_t frames=0;};
void process_frames(Plugin&p,const Stimulus&s,std::size_t total,std::size_t&cursor,std::vector<float>*capture,BlockResult*stats){constexpr int pattern[]={127,256,64,193};std::array<float,kMaxBlock> il{},ir{},ol{},orr{};int bi=0;std::vector<float> temp;if(capture)capture->clear();while(total){int n=std::min<std::size_t>(total,pattern[bi++%4]);for(int i=0;i<n;++i){auto pos=((cursor+i)%s.frames)*2;il[i]=s.data[pos];ir[i]=s.data[pos+1];}callback(p,il.data(),ir.data(),ol.data(),orr.data(),n);if(capture){for(int i=0;i<n;++i){capture->push_back(ol[i]);capture->push_back(orr[i]);}}if(stats){for(int i=0;i<n;++i){if(!std::isfinite(ol[i])||!std::isfinite(orr[i]))throw std::runtime_error("non-finite plugin output");stats->output.push_back(ol[i]);stats->output.push_back(orr[i]);}stats->frames+=n;}cursor=(cursor+n)%s.frames;total-=n;}}
bool wait_ready(Plugin&p,unsigned slot,const Stimulus&s,std::size_t&cursor,std::size_t&elapsed){p.select(slot);for(unsigned i=0;i<20000;++i){process_frames(p,s,kMaxBlock,cursor,nullptr,nullptr);elapsed+=kMaxBlock;if(p.selected_effect_ready())return true;if(p.selected_effect_unavailable())return false;std::this_thread::yield();}return false;}
void save_raw(const std::string&path,const std::vector<float>&v){std::ofstream f(path,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),static_cast<std::streamsize>(v.size()*sizeof(float)));if(!f)throw std::runtime_error("failed to write test render");}
}

int main(int argc,char**argv)try{
 if(argc<5||argc>6){std::cerr<<"usage: vst_binary_test PLUGIN ASSET_ROOT STIMULUS OUTPUT_DIR [missing]\n";return 2;}
 if(setenv("TROLLFX_FACTORY_PACKAGES_DIR",argv[2],1)!=0)throw std::runtime_error("cannot set local factory asset root");
 Stimulus stimulus(argv[3]);std::filesystem::create_directories(argv[4]);
 Plugin plugin(argv[1]);if(plugin.effect->numParams!=46)throw std::runtime_error("unexpected plugin parameter ABI");
 if(argc==6&&std::string(argv[5])=="missing"){
  std::size_t cursor=0;BlockResult render;process_frames(plugin,stimulus,2048,cursor,nullptr,&render);
  if(plugin.plain_status()!=1||!plugin.selected_effect_unavailable())throw std::runtime_error("empty local collection was not reported unavailable");
  for(float x:render.output)if(x!=0.0f)throw std::runtime_error("missing package did not fail closed to silence");
  std::cout<<"MISSING_PASS status=Unavailable frames=2048 output=silence\n";
#if defined(TROLLFX_ARM_QEMU_NO_STATIC_EXIT)
  plugin.~Plugin(); std::cout.flush(); std::cerr.flush(); std::_Exit(0);
#else
  return 0;
#endif
 }
 // Native host simulator has no package injection hook; this binary-bound
 // harness instead supplies only the external local asset root.
 std::size_t cursor=0,transition_frames=0;
 for(unsigned slot=1;slot<=50;++slot){
  std::size_t elapsed=0;if(!wait_ready(plugin,slot,stimulus,cursor,elapsed))throw std::runtime_error("VST could not prepare selected factory slot "+std::to_string(slot));
  if(slot>1&&elapsed<480)throw std::runtime_error("effect switch completed before the required 5 ms fade-out/fade-in span");
  transition_frames+=elapsed;
  if(slot==1){plugin.set(8,1.0f);plugin.set(9,1.0f);plugin.set(29,1.0f);process_frames(plugin,stimulus,256,cursor,nullptr,nullptr);if(plugin.get(8)<0.999f||plugin.get(9)<0.999f||plugin.display(29)!="41")throw std::runtime_error("HALL Q-Link parameter values did not round-trip");}
  if(slot==2){plugin.set(10,1.0f);plugin.set(11,1.0f);if(plugin.get(10)<0.999f||plugin.get(11)<0.999f)throw std::runtime_error("ROM-02 BUS parameter values did not round-trip");}
  for(const auto& probe:kVerifiedParameters)if(probe.slot==slot){
   for(const auto& point:std::array<std::pair<float,const char*>,2>{{{0.5f,probe.lower},{1.0f,probe.upper}}}){
    plugin.set(probe.index,point.first);process_frames(plugin,stimulus,256,cursor,nullptr,nullptr);
    if(plugin.display(probe.index)!=point.second)throw std::runtime_error("verified parameter point mismatch at slot "+std::to_string(slot)+" parameter "+std::to_string(probe.index));
   }
  }
  for(const auto& probe:kV4VerifiedParameters)if(probe.slot==slot){
   for(const auto& point:std::array<std::pair<float,const char*>,2>{{{0.0f,probe.lower},{1.0f,probe.upper}}}){
    plugin.set(probe.index,point.first);process_frames(plugin,stimulus,256,cursor,nullptr,nullptr);
    if(plugin.display(probe.index)!=point.second)throw std::runtime_error("V4 static-Q-Link value mismatch at slot "+std::to_string(slot)+" parameter "+std::to_string(probe.index));
   }
  }
  BlockResult render;process_frames(plugin,stimulus,8192,cursor,nullptr,&render);
  double energy_l=0,energy_r=0;float peak=0;for(std::size_t i=0;i<render.output.size();i+=2){auto l=render.output[i],r=render.output[i+1];energy_l+=double(l)*l;energy_r+=double(r)*r;peak=std::max(peak,std::max(std::abs(l),std::abs(r)));}
  double rms_l=std::sqrt(energy_l/8192),rms_r=std::sqrt(energy_r/8192);
  const std::string out=std::string(argv[4])+"/slot-"+(slot<10?"0":"")+std::to_string(slot)+".f32";save_raw(out,render.output);
  std::cout<<"SLOT "<<slot<<" READY frames=8192 rms_l="<<rms_l<<" rms_r="<<rms_r<<" peak="<<peak<<" transition_frames="<<elapsed<<" status="<<plugin.plain_status()<<"\n";
  if(rms_l<=0.0||rms_r<=0.0)throw std::runtime_error("selected package produced no stereo wet output at slot "+std::to_string(slot));
  for(const auto& probe:kVerifiedParameters)if(probe.slot==slot&&plugin.get(probe.index)<0.999f)
      throw std::runtime_error("verified control upper point did not persist at slot "+std::to_string(slot)+" parameter "+std::to_string(probe.index));
 }
 // Bind wet/dry, gain, and bypass behavior to this same shared object.
 std::size_t elapsed=0;if(!wait_ready(plugin,1,stimulus,cursor,elapsed))throw std::runtime_error("cannot return to HALL for host-control checks");
 plugin.set(1,1.0f);plugin.set(2,0.5f);plugin.set(3,0.5f);plugin.set(4,0.0f);
 BlockResult wet;cursor=0;process_frames(plugin,stimulus,2048,cursor,nullptr,&wet);
 plugin.set(1,0.0f);BlockResult dry;cursor=0;process_frames(plugin,stimulus,2048,cursor,nullptr,&dry);
 double wet_dry_delta=0.0;for(std::size_t i=16;i<wet.output.size();++i)wet_dry_delta+=std::abs(wet.output[i]-dry.output[i]);
 if(wet_dry_delta<=1e-6)throw std::runtime_error("wet/dry control did not change packaged VST output");
 plugin.set(1,1.0f);plugin.set(4,1.0f);BlockResult bypass;cursor=0;process_frames(plugin,stimulus,2048,cursor,nullptr,&bypass);
 double bypass_delta=0.0;for(std::size_t i=16;i<dry.output.size();++i)bypass_delta+=std::abs(dry.output[i]-bypass.output[i]);
 if(bypass_delta>1e-5)throw std::runtime_error("bypass did not select latency-aligned dry audio");
 plugin.set(4,0.0f);plugin.set(1,0.0f);plugin.set(2,0.625f);plugin.set(3,0.5f);
 BlockResult input_gain;cursor=0;process_frames(plugin,stimulus,2048,cursor,nullptr,&input_gain);
 plugin.set(2,0.5f);plugin.set(3,0.625f);BlockResult output_gain;cursor=0;process_frames(plugin,stimulus,2048,cursor,nullptr,&output_gain);
 double gain_delta=0.0;for(std::size_t i=16;i<dry.output.size();++i)gain_delta+=std::abs(dry.output[i]-input_gain.output[i])+std::abs(dry.output[i]-output_gain.output[i]);
 if(gain_delta<=1e-6)throw std::runtime_error("host gain controls did not change packaged VST output");
 // Save and restore the selected effect, host controls, and verified ROM-02
 // BUS, V3 and append-only V4 parameter values through the VST chunk interface.
 plugin.select(2);plugin.set(10,1.0f);plugin.set(11,0.0f);plugin.set(1,0.75f);plugin.set(2,0.6f);plugin.set(3,0.4f);plugin.set(4,1.0f);
 plugin.set(26,1.0f);
 plugin.set(29,1.0f);
 void* chunk=nullptr;auto bytes=plugin.effect->dispatcher(plugin.effect,effGetChunk,0,0,&chunk,0);if(bytes<=0||!chunk)throw std::runtime_error("plugin did not provide state chunk");
 std::vector<unsigned char> saved(static_cast<unsigned char*>(chunk),static_cast<unsigned char*>(chunk)+bytes);
 plugin.select(1);plugin.set(10,0.0f);plugin.set(11,1.0f);plugin.set(12,0.0f);plugin.set(26,0.0f);plugin.set(29,0.0f);plugin.set(1,0.0f);plugin.set(2,0.5f);plugin.set(3,0.5f);plugin.set(4,0.0f);
 plugin.effect->dispatcher(plugin.effect,effSetChunk,0,bytes,saved.data(),0);
 if(std::abs(plugin.get(kEffectParam)-float(1.0/49.0))>1e-4f||std::abs(plugin.get(10)-1.0f)>1e-4f||std::abs(plugin.get(11))>1e-4f||std::abs(plugin.get(12)-1.0f)>1e-4f||plugin.display(12)!="41"||std::abs(plugin.get(26)-1.0f)>1e-4f||plugin.display(26)!="SHORT/COARSER"||std::abs(plugin.get(29)-1.0f)>1e-4f||plugin.display(29)!="41"||std::abs(plugin.get(1)-0.75f)>1e-4f||std::abs(plugin.get(2)-0.6f)>1e-4f||std::abs(plugin.get(3)-0.4f)>1e-4f||std::abs(plugin.get(4)-1.0f)>1e-4f)throw std::runtime_error("state restore missed effect, host, or verified parameter values");
 std::cout<<"BINARY_PASS entry=VSTPluginMain slots=50 v4_controls=19 v4_verified_points=38 callbacks_allocations="<<callback_allocations.load()<<" transition_frames="<<transition_frames<<" wet_dry=gain=bypass=PASS state_roundtrip=PASS\n";
#if defined(TROLLFX_ARM_QEMU_NO_STATIC_EXIT)
 // QEMU user-mode 8.2 faults in host-side C++ static teardown after the VST
 // has been closed and dlclose has completed. Explicitly close the plugin,
 // flush the evidence line, then bypass only host runtime global destructors.
 plugin.~Plugin();
 std::cout.flush(); std::cerr.flush();
 std::_Exit(0);
#else
 return 0;
#endif
}catch(const std::exception&e){std::cerr<<"BINARY_FAIL "<<e.what()<<"\n";return 1;}
