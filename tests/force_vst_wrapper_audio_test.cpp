#define TROLLFX_FORCE_PLUGIN_TEST
#include "../force_plugin/src/ASR10FXCollection.cpp"
#include "../force_plugin/src/ES5510FactoryPackageProvider.h"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>

int main() {
    assert(editBankCountForControls(1)==1 && editBankCountForControls(8)==1);
    assert(editBankCountForControls(9)==2 && editBankCountForControls(17)==3);
    constexpr int N=256; std::array<float,N> l{},r{},ol{},orr{};
    l.fill(0.25f); r.fill(-0.25f);
    const float* inputs[2]={l.data(),r.data()}; float* outputs[2]={ol.data(),orr.data()};
    mpc::ProcessContext ctx; ctx.inputs=inputs; ctx.outputs=outputs; ctx.numInputs=2; ctx.numOutputs=2; ctx.numFrames=N; ctx.sampleRate=48000.0;
    const auto* provider=TROLLfx_GetProductionFactoryPackageProvider();
    {
        ES5510DSPBackend parameter_backend(provider);
        assert(parameter_backend.prepare(2,48000.0));
        using namespace trollfx::es5510::factory_parameters_v01;
        assert(parameter_backend.set_verified_bus(FactoryEffect::Rom02Reverb44k,
            Parameter::ReverbMixBus1,26)==EncodeStatus::Encoded);
    }
    ASR10FXCollection plugin;
    assert(plugin.numParams()==64); // old IDs 0..26, V4 controls 27..45, V4.1 routing/visibility parameters 46..63
    plugin.set(0,0.0f); // factory slot 1: HALL
    plugin.set(1,100.0f); plugin.set(2,0.0f); plugin.set(3,0.0f);
    plugin.prepare(48000.0,256);
    assert(plugin.displayText(5)=="READY");
    assert(plugin.displayText(0).find("READY") != std::string::npos);
    assert(plugin.param(6).id=="reverb_bus1" && plugin.param(7).id=="reverb_bus2");
    assert(plugin.param(12).id=="factory_decay_time_slot1");
    assert(plugin.displayText(12)=="UNCHANGED"); // no unverified factory default is written
    plugin.set(12,2.0f); // second verified HALL DECAY TIME point; choice 0 is no-write
    assert(plugin.displayText(12)=="41");
    plugin.set(8,1.0f); // verified HALL BUS1 28 -> 29
    plugin.set(9,1.0f); // verified HALL BUS2 28 -> 29
    assert(plugin.param(29).id=="factory_v4_slot1_decay_time");
    assert(plugin.displayText(29)=="40");
    assert(plugin.param(46).id=="factory_edit_slot_1");
    assert(plugin.param(54).id=="factory_edit_bank" && plugin.getInt(63)==0);
    assert(plugin.displayText(48)=="DECAY TIME: 40"); // Hall's third active EDIT slot
    plugin.set(48,1.0f); // fixed Q3 route: HALL DECAY TIME, exact verified point only
    plugin.process(ctx);
    assert(plugin.getInt(29)==1);
    assert(plugin.displayText(29)=="41");
    assert(plugin.displayText(48)=="DECAY TIME: 41");
    ASR10FXCollection hall_default;
    hall_default.set(0,0.0f); hall_default.set(1,100.0f); hall_default.set(2,0.0f); hall_default.set(3,0.0f);
    hall_default.prepare(48000.0,256);
    std::array<float,N> default_l{},default_r{};
    float* default_outputs[2]={default_l.data(),default_r.data()};
    mpc::ProcessContext default_ctx=ctx; default_ctx.outputs=default_outputs;
    l.fill(0.0f); r.fill(0.0f); ol.fill(0.0f); orr.fill(0.0f);
    double hall_energy=0.0, hall_parameter_delta=0.0;
    for(int block=0;block<24;++block) {
        for(int i=0;i<N;++i){const float x=0.25f*std::sin(float((block*N+i)*0.03125));l[i]=x;r[i]=-x;}
        plugin.process(ctx);
        hall_default.process(default_ctx);
        for(int i=0;i<N;++i){hall_energy+=ol[i]*ol[i]+orr[i]*orr[i];hall_parameter_delta+=std::abs(ol[i]-default_l[i])+std::abs(orr[i]-default_r[i]);}
    }
    assert(hall_energy>1e-8 && hall_parameter_delta>1e-8);
    ASR10FXCollection hall_v4_default;
    hall_v4_default.set(0,0.0f); hall_v4_default.set(1,100.0f); hall_v4_default.set(2,0.0f); hall_v4_default.set(3,0.0f);
    hall_v4_default.prepare(48000.0,256);
    double v4_delta=0.0;
    for(int block=0;block<24;++block) {
        for(int i=0;i<N;++i){const float x=0.25f*std::sin(float((block*N+i)*0.03125));l[i]=x;r[i]=-x;}
        plugin.process(ctx); hall_v4_default.process(default_ctx);
        for(int i=0;i<N;++i)v4_delta+=std::abs(ol[i]-default_l[i])+std::abs(orr[i]-default_r[i]);
    }
    assert(v4_delta>1e-8); // routed Q3 reaches the verified ordered DSP writes

    plugin.set(0,2.0f); // ROOM REVERB: Q1..Q3 now route to ROOM's three controls
    assert(plugin.getInt(55)==1 && plugin.getInt(56)==1 && plugin.getInt(57)==1);
    assert(plugin.getInt(58)==0 && plugin.getInt(63)==0);
    assert(plugin.displayText(46)=="DECAY TIME: 64");
    plugin.set(46,1.0f); // same Q1 now routes to ROOM DECAY TIME, not HALL BUS1
    for(int block=0;block<5000 && !(plugin.displayText(5)=="READY" && plugin.getInt(33)==1);++block) {
        plugin.process(ctx);
    }
    assert(plugin.getInt(33)==1);
    assert(plugin.displayText(46)=="DECAY TIME: 65");
    assert(plugin.getInt(29)==1); // switching effects did not overwrite HALL's saved setting
    ASR10FXCollection room_default;
    room_default.set(0,2.0f); room_default.set(1,100.0f); room_default.set(2,0.0f); room_default.set(3,0.0f);
    room_default.set(33,0.0f); // schedule the lower verified ROOM decay point
    room_default.prepare(48000.0,256);
    std::array<float,N> room_default_l{},room_default_r{};
    float* room_default_outputs[2]={room_default_l.data(),room_default_r.data()};
    mpc::ProcessContext room_default_ctx=ctx; room_default_ctx.outputs=room_default_outputs;
    double room_energy=0.0,room_parameter_delta=0.0;
    for(int block=0;block<24;++block) {
        for(int i=0;i<N;++i){const float x=0.25f*std::sin(float((block*N+i)*0.03125));l[i]=x;r[i]=-x;}
        plugin.process(ctx); room_default.process(room_default_ctx);
        for(int i=0;i<N;++i){room_energy+=ol[i]*ol[i]+orr[i]*orr[i];room_parameter_delta+=std::abs(ol[i]-room_default_l[i])+std::abs(orr[i]-room_default_r[i]);}
    }
    assert(room_energy>1e-8 && room_parameter_delta>1e-8); // ROOM Q1 mapping reached ROOM's validated package write path
    const auto saved_state=plugin.internalSaveState();
    ASR10FXCollection restored;
    assert(restored.internalLoadState(saved_state.data(),saved_state.size()));
    assert(restored.getInt(0)==2 && restored.getInt(29)==1 && restored.getInt(33)==1);
    assert(restored.displayText(46)=="DECAY TIME: 65");

    plugin.set(0,1.0f); // select ROM-02 44KHZ REVERB through the plugin parameter
    double switched_energy=0.0;
    for(int block=0;block<5000;++block) {
        for(int i=0;i<N;++i){const float x=0.25f*std::sin(float(((block+24)*N+i)*0.03125));l[i]=x;r[i]=-x;}
        plugin.process(ctx);
        for(int i=0;i<N;++i)switched_energy+=ol[i]*ol[i]+orr[i]*orr[i];
    }
    assert(switched_energy>1e-8);
    ASR10FXCollection rom02_plugin;
    rom02_plugin.set(0,1.0f); rom02_plugin.set(1,100.0f); rom02_plugin.set(2,0.0f); rom02_plugin.set(3,0.0f);
    rom02_plugin.set(10,1.0f); // verified ROM-02 BUS1 25 -> 26
    rom02_plugin.prepare(48000.0,256);
    assert(rom02_plugin.displayText(5)=="READY");
    ASR10FXCollection rom02_default;
    rom02_default.set(0,1.0f); rom02_default.set(1,100.0f); rom02_default.set(2,0.0f); rom02_default.set(3,0.0f);
    rom02_default.prepare(48000.0,256);
    double rom02_energy=0.0, rom02_parameter_delta=0.0;
    for(int block=0;block<512;++block) {
        for(int i=0;i<N;++i){const float x=0.25f*std::sin(float((block*N+i)*0.03125));l[i]=x;r[i]=-x;}
        rom02_plugin.process(ctx);
        rom02_default.process(default_ctx);
        for(int i=0;i<N;++i){rom02_energy+=ol[i]*ol[i]+orr[i]*orr[i];rom02_parameter_delta+=std::abs(ol[i]-default_l[i])+std::abs(orr[i]-default_r[i]);}
    }
    assert(rom02_energy>1e-8);
    std::printf("VST wrapper HALL energy %.9g (Q3 decay delta %.9g); ROOM energy %.9g (Q1 decay delta %.9g); ROM-02 energy %.9g; selection, register routing, and audio paths PASS\n",hall_energy,v4_delta,room_energy,room_parameter_delta,rom02_energy);
}
