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
#include <limits>
#include <new>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

static thread_local bool in_audio=false;
static std::atomic<unsigned long long> callback_allocations{0};
void* operator new(std::size_t n){if(in_audio)callback_allocations.fetch_add(1);if(void*p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){if(in_audio)callback_allocations.fetch_add(1);if(void*p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void operator delete(void*p)noexcept{std::free(p);}void operator delete[](void*p)noexcept{std::free(p);}
void operator delete(void*p,std::size_t)noexcept{std::free(p);}void operator delete[](void*p,std::size_t)noexcept{std::free(p);}

namespace {
constexpr int kRate=48000,kMaxBlock=256,kStatusParam=5,kEffectParam=0;
struct AbiParam { const char* id; const char* name; };
constexpr AbiParam kExpectedAbi[] = {
 {"effect_slot","FX Slot"},{"host_wet","Wet / Dry"},{"host_input_gain","Input Gain"},{"host_output_gain","Output Gain"},
 {"host_bypass","Host Bypass"},{"load_status","Load Status"},{"reverb_bus1","Reverb BUS1"},{"reverb_bus2","Reverb BUS2"},
 {"hall_bus1","REVERB MIX BUS1 (HALL)"},{"hall_bus2","REVERB MIX BUS2 (HALL)"},
 {"rom02_bus1","REVERB MIX BUS1 (44KHZ)"},{"rom02_bus2","REVERB MIX BUS2 (44KHZ)"},
 {"factory_decay_time_slot1","DECAY TIME (HALL)"},{"factory_hi_freq_damping_slot1","HI FREQ DAMPING (HALL)"},
 {"factory_decay_time_slot3","DECAY TIME (ROOM)"},{"factory_diffusion_slot3","DIFFUSION"},
 {"factory_hi_freq_damping_slot3","HI FREQ DAMPING (ROOM)"},{"factory_delay_time_l_slot4","BS1 TIME L"},
 {"factory_chorus_rate_slot6","CHORUS RATE"},{"factory_phase_rate_slot7","PHASE RATE"},
 {"factory_preamp_gain_slot28","PREAMP GAIN"},{"factory_voice1_fine_slot41","VOICE1 FINE"},
 {"factory_comp_ratio_slot42","COMP RATIO"},{"factory_bass_fc_slot49","BASS FC"},
 {"factory_delay_time_l_slot5","BS1 TIME L (44KHZ DELAYS)"},{"factory_flange_rate_slot8","FLANGE RATE"},
 {"factory_quality_slot39","QUALITY"},
 {"factory_v4_slot1_reverb_mix_bus1","REVERB MIX BUS1 @ 01"},
 {"factory_v4_slot1_reverb_mix_bus2","REVERB MIX BUS2 @ 01"},
 {"factory_v4_slot1_decay_time","DECAY TIME @ 01"},
 {"factory_v4_slot1_hi_freq_damping","HI FREQ DAMPING @ 01"},
 {"factory_v4_slot2_reverb_mix_bus1","REVERB MIX BUS1 @ 02"},
 {"factory_v4_slot2_reverb_mix_bus2","REVERB MIX BUS2 @ 02"},
 {"factory_v4_slot3_decay_time","DECAY TIME @ 03"},{"factory_v4_slot3_diffusion","DIFFUSION @ 03"},
 {"factory_v4_slot3_hi_freq_damping","HI FREQ DAMPING @ 03"},
 {"factory_v4_slot4_delay_time_l","BS1 TIME L @ 04"},{"factory_v4_slot5_delay_time_l","BS1 TIME L @ 05"},
 {"factory_v4_slot6_chorus_rate","CHORUS RATE @ 06"},{"factory_v4_slot7_phase_rate","PHASE RATE @ 07"},
 {"factory_v4_slot8_flange_rate","FLANGE RATE @ 08"},{"factory_v4_slot28_preamp_gain","PREAMP GAIN @ 28"},
 {"factory_v4_slot39_quality","QUALITY @ 39"},{"factory_v4_slot41_voice1_fine","VOICE1 FINE @ 41"},
 {"factory_v4_slot42_comp_ratio","COMP RATIO @ 42"},{"factory_v4_slot49_bass_fc","BASS FC @ 49"},
 {"factory_edit_slot_1","EDIT SLOT 1"},{"factory_edit_slot_2","EDIT SLOT 2"},
 {"factory_edit_slot_3","EDIT SLOT 3"},{"factory_edit_slot_4","EDIT SLOT 4"},
 {"factory_edit_slot_5","EDIT SLOT 5"},{"factory_edit_slot_6","EDIT SLOT 6"},
 {"factory_edit_slot_7","EDIT SLOT 7"},{"factory_edit_slot_8","EDIT SLOT 8"},
 {"factory_edit_bank","EDIT BANK"},
 {"edit_slot_1_available","SLOT 1 ON"},{"edit_slot_2_available","SLOT 2 ON"},
 {"edit_slot_3_available","SLOT 3 ON"},{"edit_slot_4_available","SLOT 4 ON"},
 {"edit_slot_5_available","SLOT 5 ON"},{"edit_slot_6_available","SLOT 6 ON"},
 {"edit_slot_7_available","SLOT 7 ON"},{"edit_slot_8_available","SLOT 8 ON"},
 {"edit_bank_available","BANK SELECT ON"}
};
struct Host{double rate=kRate;int block=kMaxBlock;AEffect* effect=nullptr;} host;
VstIntPtr host_callback(AEffect*,VstInt32 op,VstInt32,VstIntPtr,void*,float){
 switch(op){case audioMasterVersion:return 2400;case audioMasterGetSampleRate:return static_cast<VstIntPtr>(host.rate);case audioMasterGetBlockSize:return host.block;case audioMasterGetVendorVersion:return 0x0101;default:return 0;}
}
using Entry=AEffect*(*)(audioMasterCallback);
struct Plugin {
 void* library=nullptr;AEffect* effect=nullptr;
 explicit Plugin(const std::string&path,bool start=true){library=dlopen(path.c_str(),RTLD_NOW|RTLD_LOCAL);if(!library)throw std::runtime_error(dlerror());auto entry=reinterpret_cast<Entry>(dlsym(library,"VSTPluginMain"));if(!entry)throw std::runtime_error("VSTPluginMain missing from packaged binary");effect=entry(host_callback);if(!effect||effect->magic!=kEffectMagic||effect->resvd2!=0||!effect->object||effect->numInputs!=2||effect->numOutputs!=2||!effect->processReplacing)throw std::runtime_error("VST entry/ABI initialization failed");host.effect=effect;effect->dispatcher(effect,effOpen,0,0,nullptr,0);effect->dispatcher(effect,effSetSampleRate,0,0,nullptr,float(kRate));effect->dispatcher(effect,effSetBlockSize,0,kMaxBlock,nullptr,0);if(start)activate();}
 void activate(){effect->dispatcher(effect,effMainsChanged,0,1,nullptr,0);}
 void deactivate(){effect->dispatcher(effect,effMainsChanged,0,0,nullptr,0);}
 ~Plugin(){if(effect){effect->dispatcher(effect,effMainsChanged,0,0,nullptr,0);effect->dispatcher(effect,effClose,0,0,nullptr,0);}if(library)dlclose(library);host.effect=nullptr;}
 int plain_status(){char text[64]{};effect->dispatcher(effect,effGetParamDisplay,kStatusParam,0,text,0);if(std::strcmp(text,"READY")==0)return 3;if(std::strcmp(text,"LOADING")==0)return 2;if(std::strcmp(text,"UNAVAIL")==0)return 1;if(std::strcmp(text,"MISSING")==0)return 0;if(std::strcmp(text,"LOAD ERR")==0)return 4;return -1;}
 bool selected_effect_ready(){char text[64]{};effect->dispatcher(effect,effGetParamDisplay,kEffectParam,0,text,0);return std::strstr(text,"/ READY")!=nullptr;}
 bool selected_effect_unavailable(){char text[64]{};effect->dispatcher(effect,effGetParamDisplay,kEffectParam,0,text,0);return std::strstr(text,"UNAVAILABLE")||std::strstr(text,"PACKAGE REQUIRED")||std::strstr(text,"LOAD FAILED");}
 std::string parameter_name(int index)const{char text[128]{};effect->dispatcher(effect,effGetParamName,index,0,text,0);return text;}
 void select(unsigned slot){effect->setParameter(effect,kEffectParam,float(slot-1)/49.0f);}
 void set(int index,float normalized){effect->setParameter(effect,index,normalized);}
 float get(int index)const{return effect->getParameter(effect,index);}
};
void callback(Plugin&p,const float*il,const float*ir,float*ol,float*orr,int n){float*inputs[2]={const_cast<float*>(il),const_cast<float*>(ir)};float*outputs[2]={ol,orr};auto before=callback_allocations.load();in_audio=true;p.effect->processReplacing(p.effect,inputs,outputs,n);in_audio=false;if(callback_allocations.load()!=before)throw std::runtime_error("allocation occurred in packaged VST callback");}
struct Stimulus{std::vector<float> data;std::size_t frames=0;explicit Stimulus(const std::string&path){std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("input stimulus missing");f.seekg(0,std::ios::end);auto size=f.tellg();if(size<=0||size%(2*sizeof(float)))throw std::runtime_error("input stimulus must be stereo float32");frames=static_cast<std::size_t>(size)/(2*sizeof(float));data.resize(frames*2);f.seekg(0);f.read(reinterpret_cast<char*>(data.data()),size);if(!f)throw std::runtime_error("cannot read input stimulus");}};
struct BlockResult{std::vector<float> output;unsigned long long callbacks=0;std::size_t frames=0;};
void process_frames(Plugin&p,const Stimulus&s,std::size_t total,std::size_t&cursor,std::vector<float>*capture,BlockResult*stats){constexpr int pattern[]={127,256,64,193};std::array<float,kMaxBlock> il{},ir{},ol{},orr{};int bi=0;std::vector<float> temp;if(capture)capture->clear();while(total){int n=std::min<std::size_t>(total,pattern[bi++%4]);for(int i=0;i<n;++i){auto pos=((cursor+i)%s.frames)*2;il[i]=s.data[pos];ir[i]=s.data[pos+1];}callback(p,il.data(),ir.data(),ol.data(),orr.data(),n);if(capture){for(int i=0;i<n;++i){capture->push_back(ol[i]);capture->push_back(orr[i]);}}if(stats){for(int i=0;i<n;++i){if(!std::isfinite(ol[i])||!std::isfinite(orr[i]))throw std::runtime_error("non-finite plugin output");stats->output.push_back(ol[i]);stats->output.push_back(orr[i]);}stats->frames+=n;}cursor=(cursor+n)%s.frames;total-=n;}}
bool wait_ready(Plugin&p,unsigned slot,const Stimulus&s,std::size_t&cursor,std::size_t&elapsed){p.select(slot);for(unsigned i=0;i<20000;++i){process_frames(p,s,kMaxBlock,cursor,nullptr,nullptr);elapsed+=kMaxBlock;if(p.selected_effect_ready())return true;if(p.selected_effect_unavailable())return false;std::this_thread::yield();}return false;}
void save_raw(const std::string&path,const std::vector<float>&v){std::ofstream f(path,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),static_cast<std::streamsize>(v.size()*sizeof(float)));if(!f)throw std::runtime_error("failed to write test render");}
std::uint32_t read_u32(const unsigned char* p){return std::uint32_t(p[0])|(std::uint32_t(p[1])<<8)|(std::uint32_t(p[2])<<16)|(std::uint32_t(p[3])<<24);}
std::vector<unsigned char> get_chunk(Plugin& p){void* ptr=nullptr;auto bytes=p.effect->dispatcher(p.effect,effGetChunk,0,0,&ptr,0);if(bytes<=0||!ptr)throw std::runtime_error("plugin did not provide state chunk");return {static_cast<unsigned char*>(ptr),static_cast<unsigned char*>(ptr)+bytes};}
void verify_64_parameter_abi(Plugin& p){
 if(p.effect->numParams!=64||sizeof(kExpectedAbi)/sizeof(kExpectedAbi[0])!=64)throw std::runtime_error("candidate must expose exactly 64 parameters");
 for(int i=0;i<64;++i){const auto actual=p.parameter_name(i);if(actual!=kExpectedAbi[i].name)throw std::runtime_error("VST2 parameter name/index mismatch at "+std::to_string(i)+": expected "+kExpectedAbi[i].name+", got "+actual);}
 auto chunk=get_chunk(p);if(chunk.size()<16||std::memcmp(chunk.data(),"MPCP",4)!=0||read_u32(chunk.data()+4)!=2||read_u32(chunk.data()+8)!=64)throw std::runtime_error("saved chunk does not contain the expected version-2 64-parameter ABI");
 std::size_t pos=12;std::vector<std::string> ids;ids.reserve(64);
 for(int i=0;i<64;++i){if(pos>=chunk.size())throw std::runtime_error("state chunk truncated before parameter identity");const auto n=chunk[pos++];if(pos+n+8>chunk.size())throw std::runtime_error("state chunk parameter entry is truncated");std::string id(reinterpret_cast<const char*>(chunk.data()+pos),n);pos+=n;pos+=8;if(id!=kExpectedAbi[i].id)throw std::runtime_error("stable chunk ID/index mismatch at "+std::to_string(i)+": expected "+kExpectedAbi[i].id+", got "+id);ids.push_back(id);}
 if(pos+4>chunk.size())throw std::runtime_error("state chunk lacks extra-state length");
 const auto extra=read_u32(chunk.data()+pos);
 pos+=4;
 if(pos+extra!=chunk.size())throw std::runtime_error("state chunk extra-state length mismatch");
 std::cout<<"ABI_PASS params=64 names=64 stable_ids=64 chunk_version=2\n";
}
}

int main(int argc,char**argv)try{
 if(argc<5||argc>6){std::cerr<<"usage: vst_binary_test PLUGIN ASSET_ROOT STIMULUS OUTPUT_DIR [missing|nan-parameter|nan-audio]\n";return 2;}
 if(setenv("TROLLFX_FACTORY_PACKAGES_DIR",argv[2],1)!=0)throw std::runtime_error("cannot set local factory asset root");
 Stimulus stimulus(argv[3]);std::filesystem::create_directories(argv[4]);
 // Exercise the actual VST2 setParameter callback before the first audio
 // callback/startup request. Multiple queued values must settle to the last
 // host value after the factory runtime becomes ready.
 Plugin plugin(argv[1],false);verify_64_parameter_abi(plugin);
 plugin.select(1);plugin.set(8,0.0f);plugin.set(8,1.0f);plugin.set(8,0.0f);plugin.set(9,0.0f);plugin.set(9,1.0f);plugin.set(9,0.0f);
 if(!std::isfinite(plugin.get(8))||std::abs(plugin.get(8))>1e-4f||std::abs(plugin.get(9))>1e-4f)throw std::runtime_error("pre-startup VST setParameter did not retain final value");
 plugin.activate();
 if(argc==6&&std::string(argv[5])=="nan-parameter"){
  plugin.set(1,std::numeric_limits<float>::quiet_NaN());
  if(!std::isfinite(plugin.get(1)))throw std::runtime_error("non-finite VST parameter was retained");
  std::cout<<"NAN_PARAMETER_PASS\n";return 0;
 }
 if(argc==6&&std::string(argv[5])=="missing"){
  std::size_t cursor=0;BlockResult render;process_frames(plugin,stimulus,2048,cursor,nullptr,&render);
  if(plugin.plain_status()!=1||!plugin.selected_effect_unavailable())throw std::runtime_error("empty local collection was not reported unavailable");
  for(float x:render.output)if(x!=0.0f)throw std::runtime_error("missing package did not fail closed to silence");
  std::cout<<"MISSING_PASS status=Unavailable frames=2048 output=silence\n";return 0;
 }
 if(argc==6&&std::string(argv[5])=="nan-audio"){
  std::size_t cursor=0,elapsed=0;if(!wait_ready(plugin,1,stimulus,cursor,elapsed))throw std::runtime_error("cannot prepare HALL for non-finite input test");
  std::array<float,kMaxBlock> il{},ir{},ol{},orr{};il.fill(std::numeric_limits<float>::quiet_NaN());ir.fill(0.1f);
  callback(plugin,il.data(),ir.data(),ol.data(),orr.data(),kMaxBlock);
  for(int i=0;i<kMaxBlock;++i)if(!std::isfinite(ol[i])||!std::isfinite(orr[i]))throw std::runtime_error("non-finite input produced non-finite VST output");
  std::cout<<"NAN_AUDIO_PASS frames="<<kMaxBlock<<"\n";return 0;
 }
 // Native host simulator has no package injection hook; this binary-bound
 // harness instead supplies only the external local asset root.
 std::size_t cursor=0,transition_frames=0;
 // Start one slot, redirect the effect while startup is pending, then require
 // the requested effect to become ready. This remains callback-level and
 // does not call FactoryRuntime directly.
 plugin.select(1);process_frames(plugin,stimulus,127,cursor,nullptr,nullptr);
 plugin.set(8,1.0f);plugin.set(8,0.0f);plugin.set(8,1.0f);plugin.select(2);
 std::size_t pending_elapsed=0;if(!wait_ready(plugin,2,stimulus,cursor,pending_elapsed))throw std::runtime_error("effect switch during pending startup failed");
 std::size_t return_elapsed=0;if(!wait_ready(plugin,1,stimulus,cursor,return_elapsed))throw std::runtime_error("return to HALL after pending switch failed");
 for(unsigned slot=1;slot<=50;++slot){
  std::size_t elapsed=0;if(!wait_ready(plugin,slot,stimulus,cursor,elapsed))throw std::runtime_error("VST could not prepare selected factory slot "+std::to_string(slot));
  if(slot>1&&elapsed<480)throw std::runtime_error("effect switch completed before the required 5 ms fade-out/fade-in span");
  transition_frames+=elapsed;
  if(slot==1){plugin.set(8,1.0f);plugin.set(9,1.0f);if(plugin.get(8)<0.999f||plugin.get(9)<0.999f)throw std::runtime_error("HALL BUS parameter values did not round-trip");}
  if(slot==2){plugin.set(10,1.0f);plugin.set(11,1.0f);if(plugin.get(10)<0.999f||plugin.get(11)<0.999f)throw std::runtime_error("ROM-02 BUS parameter values did not round-trip");}
  BlockResult render;process_frames(plugin,stimulus,8192,cursor,nullptr,&render);
  double energy_l=0,energy_r=0;float peak=0;for(std::size_t i=0;i<render.output.size();i+=2){auto l=render.output[i],r=render.output[i+1];energy_l+=double(l)*l;energy_r+=double(r)*r;peak=std::max(peak,std::max(std::abs(l),std::abs(r)));}
  double rms_l=std::sqrt(energy_l/8192),rms_r=std::sqrt(energy_r/8192);
  const std::string out=std::string(argv[4])+"/slot-"+(slot<10?"0":"")+std::to_string(slot)+".f32";save_raw(out,render.output);
  std::cout<<"SLOT "<<slot<<" READY frames=8192 rms_l="<<rms_l<<" rms_r="<<rms_r<<" peak="<<peak<<" transition_frames="<<elapsed<<" status="<<plugin.plain_status()<<"\n";
  if(rms_l<=0.0||rms_r<=0.0)throw std::runtime_error("selected package produced no stereo wet output at slot "+std::to_string(slot));
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
 // Reset/restart after an edit, then prove host parameter storage survives
 // and the effect becomes active again through processReplacing.
 plugin.set(8,1.0f);plugin.deactivate();plugin.activate();std::size_t restart_elapsed=0;
 if(!wait_ready(plugin,1,stimulus,cursor,restart_elapsed))throw std::runtime_error("VST restart after edit failed to initialize");
 if(std::abs(plugin.get(8)-1.0f)>1e-4f)throw std::runtime_error("VST restart lost edited host parameter state");
 // Save and restore the selected effect, host controls, and verified ROM-02
 // BUS values through the exact packaged VST chunk interface.
 plugin.select(2);plugin.set(10,1.0f);plugin.set(11,0.0f);plugin.set(1,0.75f);plugin.set(2,0.6f);plugin.set(3,0.4f);plugin.set(4,1.0f);
 void* chunk=nullptr;auto bytes=plugin.effect->dispatcher(plugin.effect,effGetChunk,0,0,&chunk,0);if(bytes<=0||!chunk)throw std::runtime_error("plugin did not provide state chunk");
 std::vector<unsigned char> saved(static_cast<unsigned char*>(chunk),static_cast<unsigned char*>(chunk)+bytes);
 plugin.select(1);plugin.set(10,0.0f);plugin.set(11,1.0f);plugin.set(1,0.0f);plugin.set(2,0.5f);plugin.set(3,0.5f);plugin.set(4,0.0f);
 plugin.effect->dispatcher(plugin.effect,effSetChunk,0,bytes,saved.data(),0);
 if(std::abs(plugin.get(kEffectParam)-float(1.0/49.0))>1e-4f||std::abs(plugin.get(10)-1.0f)>1e-4f||std::abs(plugin.get(11))>1e-4f||std::abs(plugin.get(1)-0.75f)>1e-4f||std::abs(plugin.get(2)-0.6f)>1e-4f||std::abs(plugin.get(3)-0.4f)>1e-4f||std::abs(plugin.get(4)-1.0f)>1e-4f)throw std::runtime_error("state restore missed effect, host, or verified parameter values");
 // Robustness probes run after state coverage so an expected rejection still
 // leaves the functional callback and chunk tests visible in the log.
 for(float invalid:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),-std::numeric_limits<float>::infinity()}){
  plugin.set(1,invalid);if(!std::isfinite(plugin.get(1)))throw std::runtime_error("non-finite VST parameter was retained");
 }
 plugin.set(1,1.0f);std::array<float,kMaxBlock> bad_l{},bad_r{},bad_ol{},bad_or{};
 bad_l.fill(std::numeric_limits<float>::quiet_NaN());bad_r.fill(0.1f);
 callback(plugin,bad_l.data(),bad_r.data(),bad_ol.data(),bad_or.data(),kMaxBlock);
 for(int i=0;i<kMaxBlock;++i)if(!std::isfinite(bad_ol[i])||!std::isfinite(bad_or[i]))throw std::runtime_error("non-finite input produced non-finite VST output");
 std::cout<<"BINARY_PASS entry=VSTPluginMain slots=50 callbacks_allocations="<<callback_allocations.load()<<" transition_frames="<<transition_frames<<" wet_dry=gain=bypass=PASS state_roundtrip=PASS\n";
 return 0;
}catch(const std::exception&e){std::cerr<<"BINARY_FAIL "<<e.what()<<"\n";return 1;}
