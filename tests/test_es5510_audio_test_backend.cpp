#include "trollfx/es5510_audio_test_backend.hpp"
#include "es5510.h"
#include "wav_io.h"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

using namespace trollfx::es5510;
using namespace trollfx::es5510::audio_test;

static std::string make_checkpoint() {
    const auto path=(std::filesystem::temp_directory_path()/"es5510-audio-test-synthetic.esp").string();
    ES5510 dsp;
    for(unsigned i=0;i<3;++i) {
        const std::uint64_t instruction=i==0?((std::uint64_t(239)<<24)|(std::uint64_t(237)<<16)|0x9000ULL)
            :i==1?((std::uint64_t(238)<<24)|(std::uint64_t(236)<<16)|0x9000ULL):0xf000ULL;
        for(unsigned b=0;b<6;++b)dsp.host_w(3+b,static_cast<std::uint8_t>(instruction>>(40-8*b)));
        dsp.host_w(0xc0,static_cast<std::uint8_t>(i));
    }
    dsp.host_w(0x18,0x48);
    FILE*f=std::fopen(path.c_str(),"wb");assert(f&&dsp.write_capture(f));std::fclose(f);return path;
}

static EffectRegistry make_registry(const std::string& checkpoint) {
    EffectRegistry registry; ValidatedEffectPackage pkg;
    pkg.validation_receipt_valid=pkg.initialization_state_valid=pkg.program_identity_valid=
        pkg.pipeline_reset_valid=pkg.routing_valid=true;
    auto& d=pkg.descriptor; d.slot=1;d.factory_name="synthetic-test-only";d.active_program_words=3;d.end_word=2;
    d.program_sha256=std::string(64,'a');d.factory_reference_rate_hz=48000.0;d.routing={0x48,2,1,true};
    d.run_checkpoint_path=checkpoint;d.run_checkpoint_sha256=std::string(64,'b');
    VerifiedParameterDefinition p;p.id="test_gain";p.ui_label="Test parameter";
    ParameterPoint a;a.display_value=10;a.gpr=0x20;a.value24=0x123456;p.verified_points.push_back(a);
    ParameterPoint b;b.display_value=11;b.ordered_writes={{0x21,0x111111},{0x22,0x222222}};p.verified_points.push_back(b);
    d.parameters.push_back(p);std::string error;assert(registry.register_validated(std::move(pkg),&error));return registry;
}

int main() {
    const auto checkpoint=make_checkpoint(); auto registry=make_registry(checkpoint);
    const auto dir=std::filesystem::temp_directory_path();
    const auto input=(dir/"es5510-audio-test-input.wav").string();
    const auto output=(dir/"es5510-audio-test-output.wav").string();
    const auto wet=(dir/"es5510-audio-test-wet.wav").string();
    const auto dry=(dir/"es5510-audio-test-dry.wav").string();
    const auto base=(dir/"es5510-audio-test-base.wav").string();
    const auto changed=(dir/"es5510-audio-test-changed.wav").string();
    std::vector<trollfx::audio::StereoFrame> source(441);
    for(std::size_t i=0;i<source.size();++i){const float x=0.2f*std::sin(float(2.0*3.141592653589793*440.0*i/44100.0));source[i]={x,-x};}
    std::string error;assert(trollfx::audio::write_stereo_pcm16_wav(input,44100,source,error));
    WavAudioTestRunner runner(registry);RenderOptions options;options.block_frames=73;options.tail_frames=32;
    RenderReport rendered;
    assert(runner.render(input,output,1,{{0,"test_gain",10},{100,"test_gain",11}},options,rendered,error));
    assert(rendered.slot==1&&rendered.dsp_frames==512&&rendered.writes_applied==3);
    assert(rendered.parameter_writes.size()==3);
    assert(rendered.parameter_writes[0].gpr==0x20&&rendered.parameter_writes[1].gpr==0x21&&rendered.parameter_writes[2].gpr==0x22);
    assert(rendered.input.frames==480&&rendered.output.frames==512&&rendered.output.finite_samples==1024);
    trollfx::audio::WavData decoded;assert(trollfx::audio::read_stereo_wav(output,decoded,error));
    assert(decoded.sample_rate==48000&&decoded.frames.size()==512);

    ABReport ab;assert(runner.renderWetDryAB(input,wet,dry,1,{},options,ab,error));
    assert(ab.bypass.frames==512&&ab.processed.frames==512&&ab.difference.finite_samples==512);
    DifferenceMetrics diff;RenderReport before,after;
    assert(runner.renderParameterAB(input,base,changed,1,{},{{0,"test_gain",11}},options,diff,before,after,error));
    assert(before.dsp_frames==after.dsp_frames&&diff.finite_samples==512);

    std::filesystem::remove(checkpoint);std::filesystem::remove(input);std::filesystem::remove(output);
    std::filesystem::remove(wet);std::filesystem::remove(dry);std::filesystem::remove(base);std::filesystem::remove(changed);
    return 0;
}
