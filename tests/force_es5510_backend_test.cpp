#include "ES5510DSPBackend.h"
#include <array>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <new>
#include <thread>

static thread_local bool track_alloc=false;
static std::atomic<unsigned> allocations{0};
void* operator new(std::size_t n) { if(track_alloc) allocations.fetch_add(1); if(void*p=std::malloc(n))return p;throw std::bad_alloc(); }
void* operator new[](std::size_t n) { if(track_alloc) allocations.fetch_add(1); if(void*p=std::malloc(n))return p;throw std::bad_alloc(); }
void operator delete(void*p)noexcept{std::free(p);} void operator delete[](void*p)noexcept{std::free(p);}
void operator delete(void*p,std::size_t)noexcept{std::free(p);} void operator delete[](void*p,std::size_t)noexcept{std::free(p);}

using namespace trollfx::es5510;
class TestProvider final:public IValidatedFactoryPackageProvider {
public:
    ValidatedEffectPackage packages[2];
    const ValidatedEffectPackage* package_for_slot(EffectSlot s)const noexcept override{return s==1?&packages[0]:s==2?&packages[1]:nullptr;}
};
static ValidatedEffectPackage make_package(unsigned slot,unsigned words,double rate,const char* path) {
    ValidatedEffectPackage p;
    p.validation_receipt_valid=p.initialization_state_valid=p.program_identity_valid=p.pipeline_reset_valid=p.routing_valid=true;
    auto& d=p.descriptor; d.slot=slot; d.factory_name=slot==1?"ROM-01 HALL REVERB":"ROM-02 44KHZ REVERB";
    d.active_program_words=words; d.end_word=words-1; d.program_sha256=std::string(64,'a');
    d.factory_reference_rate_hz=rate; d.routing.host_serial_mode=0x48; d.routing.input_port=2; d.routing.output_port=1;
    d.run_checkpoint_path=path; d.run_checkpoint_sha256=std::string(64,'b'); return p;
}
static void process_block(ES5510DSPBackend& b,const float*l,const float*r,float*ol,float*or_,std::size_t n) {
    const float* in[2]={l,r}; float*out[2]={ol,or_}; auto before=allocations.load(); track_alloc=true;
    b.process(in,out,n); track_alloc=false; assert(allocations.load()==before);
}
int main(int argc,char**argv) {
    assert(argc==3); TestProvider provider;
    provider.packages[0]=make_package(1,89,29761.89453125,argv[1]);
    provider.packages[1]=make_package(2,60,44100.0,argv[2]);
    ES5510DSPBackend backend(&provider); assert(backend.prepare(1,48000.0));
    assert(backend.status()==ES5510BackendStatus::Ready); assert(backend.latency_frames()>0&&backend.latency_frames()<64);
    backend.set_mix(1.0f,0.0f,0.0f,false);
    constexpr std::size_t N=256; std::array<float,N> l{},r{},ol{},orr{}; l[0]=0.8f;r[0]=-0.6f;
    double energy=0,diff=0; auto start=std::chrono::steady_clock::now();
    for(unsigned b=0;b<32;++b){process_block(backend,l.data(),r.data(),ol.data(),orr.data(),N);for(unsigned i=0;i<N;++i){energy+=ol[i]*ol[i]+orr[i]*orr[i];diff+=std::abs(ol[i]-l[i])+std::abs(orr[i]-r[i]);}l.fill(0);r.fill(0);}
    auto elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    assert(energy>1e-6&&diff>1.0&&backend.dsp_frames()==32*N);
    std::printf("HALL %llu frames, %.3f s, %.1fx realtime\n",(unsigned long long)backend.dsp_frames(),elapsed,(32.0*N/48000.0)/elapsed);
    backend.request_effect(2); bool switched=false;
    for(unsigned n=0;n<5000;++n){process_block(backend,l.data(),r.data(),ol.data(),orr.data(),N);if(backend.active_slot()==2){switched=true;break;}std::this_thread::yield();}
    assert(switched&&backend.status()==ES5510BackendStatus::Ready); l[0]=r[0]=0.5f;energy=0;
    for(unsigned b=0;b<32;++b){process_block(backend,l.data(),r.data(),ol.data(),orr.data(),N);for(unsigned i=0;i<N;++i)energy+=ol[i]*ol[i]+orr[i]*orr[i];l.fill(0);r.fill(0);}
    assert(energy>1e-6);std::puts("ROM-02 playback and asynchronous 5 ms switch: PASS");
    std::array<float,239> short_l{},short_r{},short_ol{},short_or{};
    backend.request_effect(1);
    process_block(backend,short_l.data(),short_r.data(),short_ol.data(),short_or.data(),short_l.size());
    assert(backend.active_slot()==2);
    float one_l=0,one_r=0,one_ol=0,one_or=0;
    process_block(backend,&one_l,&one_r,&one_ol,&one_or,1);
    assert(backend.active_slot()==2);
    for(unsigned n=0;n<5000&&backend.active_slot()!=1;++n) {
        process_block(backend,l.data(),r.data(),ol.data(),orr.data(),N);
        std::this_thread::yield();
    }
    assert(backend.active_slot()==1);

    ES5510DSPBackend rate_test(&provider);
    assert(rate_test.prepare(1,96000.0));
    std::array<float,256> rate_l{},rate_r{},rate_ol{},rate_or{};
    process_block(rate_test,rate_l.data(),rate_r.data(),rate_ol.data(),rate_or.data(),256);
    assert(rate_test.dsp_frames()==128);
    assert(rate_test.latency_frames()==3);

    ES5510DSPBackend alignment(&provider);
    assert(alignment.prepare(1,48000.0));
    alignment.set_mix(0.0f,0.0f,0.0f,true);
    for(unsigned i=0;i<256;++i){rate_l[i]=static_cast<float>(i)/512.0f;rate_r[i]=-rate_l[i];}
    process_block(alignment,rate_l.data(),rate_r.data(),rate_ol.data(),rate_or.data(),256);
    for(unsigned i=alignment.latency_frames();i<256;++i){
        assert(std::abs(rate_ol[i]-rate_l[i-alignment.latency_frames()])<1e-7f);
        assert(std::abs(rate_or[i]-rate_r[i-alignment.latency_frames()])<1e-7f);
    }
    ES5510DSPBackend unavailable(nullptr);assert(!unavailable.prepare(1,48000));l.fill(.25f);r.fill(-.25f);
    process_block(unavailable,l.data(),r.data(),ol.data(),orr.data(),N);
    for(unsigned i=0;i<N;++i)assert(ol[i]==0&&orr[i]==0);
    std::puts("unavailable effect fail-closed; callback allocations: 0");
}
