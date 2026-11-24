// SPDX-License-Identifier: GPL-3.0-only
#include "ES5510FactoryPackageProvider.h"
#include <algorithm>
#include <array>
#include <cerrno>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <vector>
#if defined(__linux__)
#include <dlfcn.h>
#endif

namespace {
using namespace trollfx::es5510;
constexpr std::array<std::uint32_t,64> K={
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
inline std::uint32_t rr(std::uint32_t x,unsigned n){return (x>>n)|(x<<(32-n));}
class Sha256 {
public:
 void update(const unsigned char* p,std::size_t n){total_+=n;while(n){auto take=std::min(n,64-used_);std::memcpy(buf_.data()+used_,p,take);used_+=take;p+=take;n-=take;if(used_==64){block(buf_.data());used_=0;}}}
 std::string finish(){const std::uint64_t bits=static_cast<std::uint64_t>(total_)*8;unsigned char pad=0x80;update(&pad,1);unsigned char zero=0;while(used_!=56)update(&zero,1);unsigned char len[8];for(int i=0;i<8;++i)len[7-i]=static_cast<unsigned char>(bits>>(i*8));update(len,8);std::ostringstream o;o<<std::hex<<std::setfill('0');for(auto x:h_)o<<std::setw(8)<<x;return o.str();}
private:
 void block(const unsigned char*p){std::uint32_t w[64];for(int i=0;i<16;++i)w[i]=(std::uint32_t(p[4*i])<<24)|(std::uint32_t(p[4*i+1])<<16)|(std::uint32_t(p[4*i+2])<<8)|p[4*i+3];for(int i=16;i<64;++i){auto a=rr(w[i-15],7)^rr(w[i-15],18)^(w[i-15]>>3);auto b=rr(w[i-2],17)^rr(w[i-2],19)^(w[i-2]>>10);w[i]=w[i-16]+a+w[i-7]+b;}auto a=h_[0],b=h_[1],c=h_[2],d=h_[3],e=h_[4],f=h_[5],g=h_[6],h=h_[7];for(int i=0;i<64;++i){auto s1=rr(e,6)^rr(e,11)^rr(e,25);auto ch=(e&f)^(~e&g);auto t1=h+s1+ch+K[i]+w[i];auto s0=rr(a,2)^rr(a,13)^rr(a,22);auto maj=(a&b)^(a&c)^(b&c);auto t2=s0+maj;h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;}h_[0]+=a;h_[1]+=b;h_[2]+=c;h_[3]+=d;h_[4]+=e;h_[5]+=f;h_[6]+=g;h_[7]+=h;}
 std::array<std::uint32_t,8> h_{{0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19}};
 std::array<unsigned char,64> buf_{};std::size_t used_=0,total_=0;
};
std::string hash_file(const std::filesystem::path&p){std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("cannot open asset");Sha256 s;std::array<unsigned char,65536>b{};while(f){f.read(reinterpret_cast<char*>(b.data()),b.size());auto n=f.gcount();if(n>0)s.update(b.data(),static_cast<std::size_t>(n));}if(!f.eof())throw std::runtime_error("asset read failed");return s.finish();}
bool hex64(const std::string&s){return s.size()==64&&std::all_of(s.begin(),s.end(),[](unsigned char c){return std::isxdigit(c)!=0;});}
std::vector<std::string> split_tabs(const std::string&s){std::vector<std::string>v;std::size_t a=0;for(;;){auto b=s.find('\t',a);v.push_back(s.substr(a,b==std::string::npos?b:b-a));if(b==std::string::npos)break;a=b+1;}return v;}
std::uint64_t decimal(const std::string&s){if(s.empty()||!std::all_of(s.begin(),s.end(),[](unsigned char c){return c>='0'&&c<='9';}))throw std::runtime_error("invalid decimal field");return std::stoull(s);}
std::uint32_t hex32(const std::string&s){if(s.empty()||s.size()>8||!std::all_of(s.begin(),s.end(),[](unsigned char c){return std::isxdigit(c)!=0;}))throw std::runtime_error("invalid hexadecimal event field");return static_cast<std::uint32_t>(std::stoul(s,nullptr,16));}
std::filesystem::path asset_path(const std::filesystem::path&root,const std::string&rel){
 std::filesystem::path r(rel);
 if(r.empty()||r.is_absolute())throw std::runtime_error("asset path must be relative");
 for(auto part=r.begin();part!=r.end();++part)if(*part=="..")throw std::runtime_error("asset path escapes collection");
 auto p=std::filesystem::canonical(root/r);auto ri=std::filesystem::canonical(root);auto pi=p.begin(),pe=p.end();
 for(auto rp=ri.begin();rp!=ri.end();++rp){if(pi==pe||*pi!=*rp)throw std::runtime_error("asset path escapes collection root");++pi;}
 if(!std::filesystem::is_regular_file(p))throw std::runtime_error("asset is not a regular file");
 return p;
}
std::vector<ScheduledGprWrite> read_schedule(const std::filesystem::path&p,std::size_t expected){std::ifstream f(p);if(!f)throw std::runtime_error("cannot read firmware schedule");std::string line;if(!std::getline(f,line))throw std::runtime_error("firmware schedule is empty");if(!line.empty()&&line.back()=='\r')line.pop_back();if(line!="relative_dsp_frame,event_id,cpu_cycles,gpr,value24")throw std::runtime_error("firmware schedule schema mismatch");std::vector<ScheduledGprWrite> out;std::uint64_t prior_frame=0,prior_event=0;bool first=true;while(std::getline(f,line)){if(!line.empty()&&line.back()=='\r')line.pop_back();std::array<std::string,5> cols;std::size_t a=0;for(int i=0;i<4;++i){auto b=line.find(',',a);if(b==std::string::npos)throw std::runtime_error("firmware schedule row is malformed");cols[i]=line.substr(a,b-a);a=b+1;}if(line.find(',',a)!=std::string::npos)throw std::runtime_error("firmware schedule has extra columns");cols[4]=line.substr(a);auto frame=decimal(cols[0]),event=decimal(cols[1]);(void)decimal(cols[2]);auto gpr=hex32(cols[3]),value=hex32(cols[4]);if(frame>=32768||gpr>=0xc0||value>0xffffff||(!first&&(frame<prior_frame||event<=prior_event)))throw std::runtime_error("firmware schedule ordering or bounds are invalid");out.push_back({frame,static_cast<std::uint8_t>(gpr),value});first=false;prior_frame=frame;prior_event=event;if(out.size()>EffectRegistry::kMaxFirmwareEvents)throw std::runtime_error("firmware schedule exceeds bounded runtime capacity");}if(out.size()!=expected)throw std::runtime_error("firmware schedule event count mismatch");return out;}
struct Row {std::vector<std::string> c;std::uint8_t slot=0;};
}

ES5510FactoryPackageProvider& ES5510FactoryPackageProvider::instance(){static ES5510FactoryPackageProvider p;return p;}
ES5510FactoryPackageProvider::ES5510FactoryPackageProvider(){root_=discover_asset_root();load_index();}
const IValidatedFactoryPackageProvider* TROLLfx_GetProductionFactoryPackageProvider(){auto&p=ES5510FactoryPackageProvider::instance();TROLLfx_InstallValidatedFactoryPackageProvider(&p);return &p;}
const trollfx::es5510::ValidatedEffectPackage* ES5510FactoryPackageProvider::package_for_slot(std::uint8_t slot)const noexcept{return registry_.find(slot);}
const char* ES5510FactoryPackageProvider::slot_error(std::uint8_t slot)const noexcept{return slot<errors_.size()?errors_[slot].c_str():"invalid factory slot";}
std::filesystem::path ES5510FactoryPackageProvider::discover_asset_root()const{
 const char* env=std::getenv("TROLLFX_FACTORY_PACKAGES_DIR");if(env&&*env)return std::filesystem::path(env);
 std::filesystem::path module;
#if defined(__linux__)
 Dl_info info{};if(dladdr(reinterpret_cast<void*>(&TROLLfx_GetProductionFactoryPackageProvider),&info)&&info.dli_fname)module=std::filesystem::absolute(info.dli_fname);
#endif
 auto plugin_dir=module.empty()?std::filesystem::current_path():module.parent_path().parent_path();
 auto config=plugin_dir/"factory-assets-path.txt";std::ifstream c(config);std::string configured;if(c&&std::getline(c,configured)&&!configured.empty()){std::filesystem::path p(configured);return p.is_absolute()?p:plugin_dir/p;}
 return plugin_dir/"FactoryAssets";
}
void ES5510FactoryPackageProvider::load_index(){
 for(std::uint8_t i=1;i<=50;++i)errors_[i]="no validated package index";
 try{
  if(!std::filesystem::is_directory(root_)){for(std::uint8_t i=1;i<=50;++i)errors_[i]="factory asset directory is missing";std::fprintf(stderr,"TROLLfx factory assets unavailable: configured directory is missing\n");return;}
  auto index=std::filesystem::canonical(root_/"provider-index.tsv");std::ifstream f(index);if(!f)throw std::runtime_error("provider-index.tsv is missing");std::string line;if(!std::getline(f,line)||line!="TROLLFX_FORCE_ASSETS\t1")throw std::runtime_error("provider index schema/version mismatch");std::vector<Row> rows;std::map<unsigned,unsigned> occurrences;
  while(std::getline(f,line)){auto c=split_tabs(line);Row r;r.c=std::move(c);try{if(r.c.size()!=15)throw std::runtime_error("provider row has wrong field count");auto slot=decimal(r.c[0]);if(slot<1||slot>50)throw std::runtime_error("slot is outside 1..50");r.slot=static_cast<std::uint8_t>(slot);++occurrences[slot];rows.push_back(std::move(r));}catch(const std::exception&e){std::fprintf(stderr,"TROLLfx provider index row rejected: %s\n",e.what());}}
  for(const auto&r:rows){const auto slot=r.slot;if(occurrences[slot]!=1){errors_[slot]="duplicate slot in provider index";continue;}try{
    const auto&c=r.c;ValidatedEffectPackage p;auto&d=p.descriptor;d.slot=slot;d.factory_name=c[1];d.active_program_words=static_cast<std::uint32_t>(decimal(c[2]));d.end_word=static_cast<std::uint32_t>(decimal(c[3]));d.program_sha256=c[4];d.factory_reference_rate_hz=std::stod(c[5]);if(!std::isfinite(d.factory_reference_rate_hz))throw std::runtime_error("invalid factory processing rate");
    d.routing={0x48,2,1,true};auto manifest=asset_path(root_,c[6]),checkpoint=asset_path(root_,c[8]),history=asset_path(root_,c[10]),schedule=asset_path(root_,c[12]);
    if(!hex64(c[4])||!hex64(c[7])||!hex64(c[9])||!hex64(c[11])||!hex64(c[13]))throw std::runtime_error("malformed SHA-256 identity");
    if(hash_file(manifest)!=c[7])throw std::runtime_error("package manifest digest mismatch");
    if(hash_file(checkpoint)!=c[9])throw std::runtime_error("RUN checkpoint digest mismatch");
    if(hash_file(history)!=c[11])throw std::runtime_error("firmware event history digest mismatch");
    if(hash_file(schedule)!=c[13])throw std::runtime_error("firmware schedule digest mismatch");
    d.package_manifest_path=manifest.string();d.initialization_manifest_path=manifest.string();d.run_checkpoint_path=checkpoint.string();d.run_checkpoint_sha256=c[9];d.firmware_event_schedule_path=schedule.string();d.firmware_event_schedule_sha256=c[13];d.firmware_event_schedule=read_schedule(schedule,static_cast<std::size_t>(decimal(c[14])));
    p.validation_receipt_valid=true;p.initialization_state_valid=true;p.program_identity_valid=true;p.pipeline_reset_valid=true;p.routing_valid=true;
    std::string error;if(!registry_.register_validated(std::move(p),&error))throw std::runtime_error(std::string("universal registry rejected descriptor: ")+error);
    errors_[slot].clear();
   }catch(const std::exception&e){errors_[slot]=e.what();std::fprintf(stderr,"TROLLfx factory slot %u unavailable: %s\n",unsigned(slot),e.what());}}
  std::fprintf(stderr,"TROLLfx factory packages: %zu/50 validated from local assets\n",registry_.size());
 }catch(const std::exception&e){for(std::uint8_t i=1;i<=50;++i)if(errors_[i].empty())errors_[i]=e.what();std::fprintf(stderr,"TROLLfx factory package index rejected: %s\n",e.what());}
}
