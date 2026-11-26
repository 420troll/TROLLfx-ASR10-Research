// Thin desktop VST2 host shim for the Force interface simulator.
// The simulator talks to the real native VSTPluginMain entry point.
#include "mpc_vst2_abi.h"
#include "ASR10VST2TestAPI.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <new>
#include <string>

namespace {
constexpr int kSampleRate = 48000;
constexpr int kMaxBlock = 1024;
struct HostState { AEffect* effect = nullptr; };
thread_local HostState* active_host = nullptr;
using Entry = AEffect* (*)(audioMasterCallback);
using TraceLatestFn = std::uint64_t (*)() noexcept;
struct SimTraceWrite { std::uint64_t sequence, dsp_frame; std::uint32_t slot, gpr, value24; };
using TraceCopyFn = std::size_t (*)(std::uint64_t, SimTraceWrite*, std::size_t) noexcept;
using TraceResetFn = void (*)() noexcept;
using TestSetHallRawFn = int (*)(AEffect*, int);
using TestEnableRawOverrideFn = int (*)(AEffect*);
using TestRuntimeStatusFn = int (*)(AEffect*, TROLLfxVst2RuntimeStatus*);
using TestStepHallDecayFn = int (*)(AEffect*, int, int);

VstIntPtr audio_master(AEffect*, VstInt32 opcode, VstInt32, VstIntPtr, void*, float) {
    switch (opcode) {
        case audioMasterVersion: return 2400;
        case audioMasterGetSampleRate: return kSampleRate;
        case audioMasterGetBlockSize: return kMaxBlock;
        case audioMasterGetVendorVersion: return 0x0101;
        default: return 0;
    }
}

struct Host {
    void* library = nullptr;
    AEffect* effect = nullptr;
    HostState state{};
    TraceLatestFn trace_latest = nullptr;
    TraceCopyFn trace_copy = nullptr;
    TraceResetFn trace_reset = nullptr;
    TestSetHallRawFn test_set_hall_raw = nullptr;
    TestEnableRawOverrideFn test_enable_raw_override = nullptr;
    TestRuntimeStatusFn test_runtime_status = nullptr;
    TestStepHallDecayFn test_step_hall_decay = nullptr;
    std::array<float, kMaxBlock> silence{};
    std::array<float, kMaxBlock> left{}, right{}, out_left{}, out_right{};

    Host(const char* plugin_path, const char* assets_path) {
        if (!plugin_path || !assets_path || setenv("TROLLFX_FACTORY_PACKAGES_DIR", assets_path, 1) != 0)
            throw std::bad_alloc();
        library = dlopen(plugin_path, RTLD_NOW | RTLD_LOCAL);
        if (!library) throw std::bad_alloc();
        auto entry = reinterpret_cast<Entry>(dlsym(library, "VSTPluginMain"));
        if (!entry) throw std::bad_alloc();
        active_host = &state;
        effect = entry(audio_master);
        if (!effect || effect->magic != kEffectMagic || !effect->object ||
            effect->numInputs != 2 || effect->numOutputs != 2 || !effect->processReplacing) throw std::bad_alloc();
        state.effect = effect;
        effect->dispatcher(effect, effOpen, 0, 0, nullptr, 0.0f);
        effect->dispatcher(effect, effSetSampleRate, 0, 0, nullptr, static_cast<float>(kSampleRate));
        effect->dispatcher(effect, effSetBlockSize, 0, kMaxBlock, nullptr, 0.0f);
        effect->dispatcher(effect, effMainsChanged, 0, 1, nullptr, 0.0f);
        trace_latest = reinterpret_cast<TraceLatestFn>(dlsym(library, "TROLLfx_SimTraceLatest"));
        trace_copy = reinterpret_cast<TraceCopyFn>(dlsym(library, "TROLLfx_SimTraceCopy"));
        trace_reset = reinterpret_cast<TraceResetFn>(dlsym(library, "TROLLfx_SimTraceReset"));
        test_set_hall_raw = reinterpret_cast<TestSetHallRawFn>(dlsym(library, "TROLLfx_VST2TestSetHallRaw"));
        test_enable_raw_override = reinterpret_cast<TestEnableRawOverrideFn>(dlsym(library, "TROLLfx_VST2TestEnableRawOverride"));
        test_runtime_status = reinterpret_cast<TestRuntimeStatusFn>(dlsym(library, "TROLLfx_VST2TestRuntimeStatus"));
        test_step_hall_decay = reinterpret_cast<TestStepHallDecayFn>(dlsym(library, "TROLLfx_VST2TestStepHallDecay"));
    }
    ~Host() {
        if (effect) {
            effect->dispatcher(effect, effMainsChanged, 0, 0, nullptr, 0.0f);
            effect->dispatcher(effect, effClose, 0, 0, nullptr, 0.0f);
        }
        if (library) dlclose(library);
        active_host = nullptr;
    }
    void pump(int frames) {
        while (frames > 0) {
            const int n = std::min(frames, kMaxBlock);
            float* ins[2] = {silence.data(), silence.data()};
            float* outs[2] = {out_left.data(), out_right.data()};
            effect->processReplacing(effect, ins, outs, n);
            frames -= n;
        }
    }
};
}

extern "C" {
void* trollfx_vst_create(const char* plugin_path, const char* assets_path) {
    try { return new Host(plugin_path, assets_path); } catch (...) { return nullptr; }
}
void trollfx_vst_destroy(void* p) { delete static_cast<Host*>(p); }
int trollfx_vst_num_params(void* p) { auto* h=static_cast<Host*>(p); return h&&h->effect?h->effect->numParams:0; }
float trollfx_vst_get(void* p, int i) { auto* h=static_cast<Host*>(p); return h&&h->effect&&i>=0&&i<h->effect->numParams?h->effect->getParameter(h->effect,i):0.0f; }
void trollfx_vst_set(void* p, int i, float v) { auto* h=static_cast<Host*>(p); if(h&&h->effect&&i>=0&&i<h->effect->numParams)h->effect->setParameter(h->effect,i,v); }
int trollfx_vst_text(void* p, int i, int name, char* out, int cap) {
    auto* h=static_cast<Host*>(p); if(!h||!h->effect||i<0||i>=h->effect->numParams||!out||cap<2)return 0;
    out[0]=0; const int op=name?effGetParamName:effGetParamDisplay;
    h->effect->dispatcher(h->effect,op,i,0,out,0.0f); out[cap-1]=0; return 1;
}
void trollfx_vst_pump(void* p, int frames) { if(p&&frames>0)static_cast<Host*>(p)->pump(frames); }
int trollfx_vst_process(void* p, const float* in, float* out, int frames, int block) {
    auto* h=static_cast<Host*>(p); if(!h||!h->effect||!in||!out||frames<0)return 0;
    const int max_block=std::clamp(block,1,kMaxBlock);
    int cursor=0;
    while(cursor<frames){const int n=std::min(max_block,frames-cursor);
      for(int i=0;i<n;++i){h->left[i]=in[2*(cursor+i)];h->right[i]=in[2*(cursor+i)+1];}
      float* ins[2]={h->left.data(),h->right.data()};float* outs[2]={h->out_left.data(),h->out_right.data()};
      h->effect->processReplacing(h->effect,ins,outs,n);
      for(int i=0;i<n;++i){out[2*(cursor+i)]=h->out_left[i];out[2*(cursor+i)+1]=h->out_right[i];}
      cursor+=n;
    }
    return 1;
}
std::size_t trollfx_vst_state(void* p, std::uint8_t* bytes, std::size_t capacity) {
    auto* h=static_cast<Host*>(p);if(!h||!h->effect)return 0;void* ptr=nullptr;
    const auto size=static_cast<std::size_t>(h->effect->dispatcher(h->effect,effGetChunk,0,0,&ptr,0.0f));
    if(!ptr||!size)return 0;if(!bytes||capacity<size)return size;std::memcpy(bytes,ptr,size);return size;
}
int trollfx_vst_restore(void* p, const std::uint8_t* bytes, std::size_t size) {
    auto* h=static_cast<Host*>(p);return h&&h->effect&&bytes&&size?static_cast<int>(h->effect->dispatcher(h->effect,effSetChunk,0,static_cast<VstIntPtr>(size),const_cast<std::uint8_t*>(bytes),0.0f)):0;
}
std::uint64_t trollfx_vst_trace_latest(void* p) { auto* h=static_cast<Host*>(p);return h&&h->trace_latest?h->trace_latest():0; }
std::size_t trollfx_vst_trace_copy(void* p,std::uint64_t after,SimTraceWrite* out,std::size_t cap) { auto* h=static_cast<Host*>(p);return h&&h->trace_copy?h->trace_copy(after,out,cap):0; }
void trollfx_vst_trace_reset(void* p) { auto* h=static_cast<Host*>(p);if(h&&h->trace_reset)h->trace_reset(); }
int trollfx_vst_trace_available(void* p) { auto* h=static_cast<Host*>(p);return h&&h->trace_latest&&h->trace_copy&&h->trace_reset; }
int trollfx_vst_test_set_hall_raw(void* p,int raw) { auto* h=static_cast<Host*>(p);return h&&h->test_set_hall_raw?h->test_set_hall_raw(h->effect,raw):0; }
int trollfx_vst_test_enable_raw_override(void* p) { auto* h=static_cast<Host*>(p);return h&&h->test_enable_raw_override?h->test_enable_raw_override(h->effect):0; }
int trollfx_vst_test_runtime_status(void* p,TROLLfxVst2RuntimeStatus* out) { auto* h=static_cast<Host*>(p);return h&&h->test_runtime_status?h->test_runtime_status(h->effect,out):0; }
int trollfx_vst_test_step_hall_decay(void* p,int variation,int direction) { auto* h=static_cast<Host*>(p);return h&&h->test_step_hall_decay?h->test_step_hall_decay(h->effect,variation,direction):-1; }
}
