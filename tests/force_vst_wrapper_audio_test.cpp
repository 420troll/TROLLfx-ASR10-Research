#define TROLLFX_FORCE_PLUGIN_TEST
#include "../force_plugin/src/ASR10FXCollection.cpp"
#include "validated_test_packages.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>

int main() {
    auto provider=trollfx_test::make_provider();
    TROLLfx_InstallValidatedFactoryPackageProvider(nullptr);
    ASR10FXCollection missing_plugin;
    missing_plugin.prepare(48000.0,256);
    assert(missing_plugin.displayText(5)=="UNAVAIL"); // status is rendered from backend state, not serialized parameter state
    constexpr int N=256; std::array<float,N> l{},r{},ol{},orr{};
    l.fill(0.25f); r.fill(-0.25f);
    const float* inputs[2]={l.data(),r.data()}; float* outputs[2]={ol.data(),orr.data()};
    mpc::ProcessContext ctx; ctx.inputs=inputs; ctx.outputs=outputs; ctx.numInputs=2; ctx.numOutputs=2; ctx.numFrames=N; ctx.sampleRate=48000.0;
    missing_plugin.process(ctx);
    for(int i=0;i<N;++i)assert(ol[i]==0.0f&&orr[i]==0.0f);
    TROLLfx_InstallValidatedFactoryPackageProvider(&provider);
    {
        ES5510DSPBackend parameter_backend(&provider);
        assert(parameter_backend.prepare(2,48000.0));
        using namespace trollfx::es5510::factory_parameters_v01;
        assert(parameter_backend.set_verified_bus(FactoryEffect::Rom02Reverb44k,
            Parameter::ReverbMixBus1,26)==EncodeStatus::Encoded);
    }
    ASR10FXCollection plugin;
    assert(plugin.numParams()==24); // legacy IDs 0..11 retained; V2 controls append at 12..23
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
    std::printf("VST wrapper HALL energy %.9g (BUS delta %.9g); ROM-02 energy %.9g (BUS1 observation delta %.9g); selection and audio paths PASS\n",hall_energy,hall_parameter_delta,rom02_energy,rom02_parameter_delta);
}
