#include "experimental_audio_host.h"
#include "factory_runtime_audio_adapter.h"
#include "wav_io.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

using trollfx::audio::AudioHost;
using trollfx::audio::Controls;
using trollfx::audio::Effect;
using trollfx::audio::FactoryRuntimeProcessor;
using trollfx::audio::IProcessor;
using trollfx::audio::MockProcessor;
using trollfx::audio::PrivateFactoryPackagePaths;
using trollfx::audio::StereoFrame;
using trollfx::audio::WavData;
using trollfx::es5510::factory_parameters_v01::Parameter;

namespace {
struct Switch { size_t frame; Effect effect; };
struct ParameterEvent { size_t frame; Effect effect; Parameter parameter; int value; };
Effect effect_from(const std::string& value) {
    if (value == "hall") return Effect::Hall;
    if (value == "rom02") return Effect::Rom02;
    throw std::invalid_argument("effect must be hall or rom02");
}
const char* effect_name(Effect e) { return e == Effect::Hall ? "hall" : "rom02"; }
double number(const std::string& text, const char* what) {
    size_t used = 0; double x = std::stod(text, &used);
    if (used != text.size() || !std::isfinite(x)) throw std::invalid_argument(std::string("invalid ") + what);
    return x;
}
size_t seconds_to_frame(const std::string& text) {
    const double seconds=number(text,"event time");
    if(seconds<0.0||seconds>86400.0)throw std::invalid_argument("event time out of range");
    return static_cast<size_t>(std::llround(seconds*48000.0));
}
Switch parse_switch(const std::string& text) {
    const size_t colon = text.find(':');
    if (colon == std::string::npos) throw std::invalid_argument("switch must be seconds:hall|rom02");
    return {seconds_to_frame(text.substr(0, colon)), effect_from(text.substr(colon + 1))};
}
ParameterEvent parse_parameter(const std::string& text) {
    std::vector<std::string> p; size_t start=0;
    while(start<=text.size()){const size_t c=text.find(':',start);p.push_back(text.substr(start,c==std::string::npos?c:c-start));if(c==std::string::npos)break;start=c+1;}
    if(p.size()!=4)throw std::invalid_argument("parameter event must be SEC:EFFECT:BUS1|BUS2:DISPLAY_VALUE");
    const auto effect=effect_from(p[1]);
    Parameter parameter;
    if(p[2]=="bus1")parameter=Parameter::ReverbMixBus1;
    else if(p[2]=="bus2")parameter=Parameter::ReverbMixBus2;
    else throw std::invalid_argument("parameter must be bus1 or bus2");
    const double raw=number(p[3],"parameter display value");
    if(std::floor(raw)!=raw)throw std::invalid_argument("parameter display value must be an integer");
    return {seconds_to_frame(p[0]),effect,parameter,static_cast<int>(raw)};
}
void usage() {
    std::cout << "Usage: trollfx-audio-host INPUT.wav OUTPUT.wav --backend runtime|mock [options]\n"
                 "  runtime requires validated private inputs for BOTH effects:\n"
                 "    --hall-checkpoint PATH --hall-manifest PATH --hall-reference-dir DIR --hall-events CSV\n"
                 "    --rom02-checkpoint PATH --rom02-manifest PATH --rom02-reference-dir DIR --rom02-events CSV\n"
                 "  --effect hall|rom02       initial effect (default hall)\n"
                 "  --wet 0..1                host wet/dry blend (default 0.65)\n"
                 "  --input-gain-db DB        input gain (default 0 dB)\n"
                 "  --output-gain-db DB       output gain (default 0 dB)\n"
                 "  --block N                 processing block frames (default 256)\n"
                 "  --tail-seconds SEC        append silence to render reverb tail (default 0)\n"
                 "  --switch-at SEC:EFFECT    schedule a 5 ms fade/reload/fade transition; repeatable\n"
                 "  --bus1 VALUE --bus2 VALUE set observed initial-effect BUS value at frame 0\n"
                 "  --set-at SEC:EFFECT:BUS1|BUS2:VALUE schedule a verified BUS change\n";
}

PrivateFactoryPackagePaths package_args(const std::string& manifest,const std::string& checkpoint,const std::string& refs,const std::string& events) {
    return {manifest,checkpoint,refs,events};
}
}

int main(int argc, char** argv) {
    if (argc == 2 && (std::string(argv[1]) == "--help" || std::string(argv[1]) == "-h")) { usage(); return 0; }
    if (argc < 3) { usage(); return 2; }
    try {
        const std::string input_path = argv[1], output_path = argv[2];
        Effect initial = Effect::Hall;
        std::string backend;
        std::string hall_checkpoint,hall_manifest,hall_refs,hall_events,rom02_checkpoint,rom02_manifest,rom02_refs,rom02_events;
        double wet = 0.65, in_db = 0.0, out_db = 0.0, tail_seconds=0.0;
        size_t block = 256;
        std::vector<Switch> switches;
        std::vector<ParameterEvent> parameter_events;
        std::vector<std::pair<Parameter,int>> initial_parameters;
        for (int i = 3; i < argc; ++i) {
            const std::string arg = argv[i];
            auto value = [&]() -> std::string { if (++i >= argc) throw std::invalid_argument("missing value after " + arg); return argv[i]; };
            if (arg == "--backend") backend = value();
            else if (arg == "--hall-checkpoint") hall_checkpoint=value();
            else if (arg == "--hall-manifest") hall_manifest=value();
            else if (arg == "--hall-reference-dir") hall_refs=value();
            else if (arg == "--hall-events") hall_events=value();
            else if (arg == "--rom02-checkpoint") rom02_checkpoint=value();
            else if (arg == "--rom02-manifest") rom02_manifest=value();
            else if (arg == "--rom02-reference-dir") rom02_refs=value();
            else if (arg == "--rom02-events") rom02_events=value();
            else if (arg == "--effect") initial = effect_from(value());
            else if (arg == "--wet") wet = number(value(), "wet value");
            else if (arg == "--input-gain-db") in_db = number(value(), "input gain");
            else if (arg == "--output-gain-db") out_db = number(value(), "output gain");
            else if (arg == "--tail-seconds") tail_seconds=number(value(),"tail duration");
            else if (arg == "--bus1" || arg == "--bus2") {
                const double n=number(value(),"BUS display value");if(std::floor(n)!=n)throw std::invalid_argument("BUS display value must be an integer");
                initial_parameters.emplace_back(arg=="--bus1"?Parameter::ReverbMixBus1:Parameter::ReverbMixBus2,static_cast<int>(n));
            } else if (arg == "--set-at") parameter_events.push_back(parse_parameter(value()));
            else if (arg == "--block") {
                const double n = number(value(), "block size");
                if (n < 1 || n > 1048576 || std::floor(n) != n) throw std::invalid_argument("block size must be 1..1048576");
                block = static_cast<size_t>(n);
            } else if (arg == "--switch-at") switches.push_back(parse_switch(value()));
            else throw std::invalid_argument("unknown option: " + arg);
        }
        if (backend != "mock" && backend != "runtime")
            throw std::invalid_argument("--backend runtime or --backend mock is required; mock output is synthetic, not a factory effect");
        if (wet < 0.0 || wet > 1.0) throw std::invalid_argument("wet must be in 0..1");
        if (in_db < -96 || in_db > 24 || out_db < -96 || out_db > 24) throw std::invalid_argument("gain range is -96..24 dB");
        if (tail_seconds < 0.0 || tail_seconds > 60.0) throw std::invalid_argument("tail duration must be 0..60 seconds");
        if ((backend=="mock") && (!initial_parameters.empty() || !parameter_events.empty()))
            throw std::invalid_argument("factory BUS controls require --backend runtime");

        std::unique_ptr<IProcessor> processor;
        FactoryRuntimeProcessor* factory=nullptr;
        if(backend=="runtime") {
            const auto validator=std::filesystem::current_path()/"tools/audio_validation/validate_factory_runtime_package.py";
            if(!std::filesystem::is_regular_file(validator))throw std::runtime_error("run from the repository root or provide the validator in the current checkout");
            auto runtime=std::make_unique<FactoryRuntimeProcessor>(
                package_args(hall_manifest,hall_checkpoint,hall_refs,hall_events),
                package_args(rom02_manifest,rom02_checkpoint,rom02_refs,rom02_events),validator.string());
            factory=runtime.get();processor=std::move(runtime);
        } else processor=std::make_unique<MockProcessor>();

        WavData wav; std::string error;
        if (!trollfx::audio::read_stereo_wav(input_path, wav, error)) throw std::runtime_error(error);
        if (wav.frames.empty()) throw std::invalid_argument("input WAV contains no frames");
        constexpr uint32_t rate = 48000;
        const size_t program_frames = static_cast<size_t>(std::llround(static_cast<double>(wav.frames.size()) * rate / wav.sample_rate));
        const size_t tail_frames = static_cast<size_t>(std::llround(tail_seconds*rate));
        const size_t output_frames = program_frames+tail_frames;
        if (!program_frames) throw std::invalid_argument("input WAV is too short to produce an output frame at 48 kHz");
        std::vector<StereoFrame> input48(output_frames), output48(output_frames);
        if (wav.sample_rate == rate) std::copy(wav.frames.begin(),wav.frames.end(),input48.begin());
        else {
            for (size_t i = 0; i < program_frames; ++i) {
                const double source = static_cast<double>(i) * wav.sample_rate / rate;
                const size_t i0 = std::min(static_cast<size_t>(source), wav.frames.size() - 1);
                const size_t i1 = std::min(i0 + 1, wav.frames.size() - 1);
                const float frac = static_cast<float>(source - i0);
                input48[i] = {wav.frames[i0].left + (wav.frames[i1].left - wav.frames[i0].left) * frac,
                              wav.frames[i0].right + (wav.frames[i1].right - wav.frames[i0].right) * frac};
            }
        }
        std::sort(switches.begin(), switches.end(), [](const Switch& a, const Switch& b) { return a.frame < b.frame; });
        std::sort(parameter_events.begin(),parameter_events.end(),[](const auto&a,const auto&b){return a.frame<b.frame;});
        for(size_t i=0;i<switches.size();++i){
            if(switches[i].frame>=program_frames)throw std::invalid_argument("switch time must fall within program audio, before tail");
            if(i&&switches[i].frame==switches[i-1].frame)throw std::invalid_argument("switch times must be unique");
        }
        for(size_t i=0;i<parameter_events.size();++i){
            auto&e=parameter_events[i];if(e.frame>=program_frames)throw std::invalid_argument("parameter time must fall within program audio, before tail");
            if(i&&e.frame==parameter_events[i-1].frame)throw std::invalid_argument("parameter event times must be unique");
            if(backend!="runtime")throw std::invalid_argument("factory BUS events require runtime backend");
        }
        for(const auto&sw:switches)for(const auto&ev:parameter_events)
            if(ev.frame>=sw.frame&&ev.frame<sw.frame+480)throw std::invalid_argument("parameter event overlaps the 10 ms effect transition");
        for(const auto&sw:switches)for(const auto&other:switches)
            if(&sw!=&other&&other.frame>sw.frame&&other.frame<sw.frame+480)throw std::invalid_argument("effect switches must be separated by at least 10 ms");

        AudioHost host(*processor,rate,rate,5,initial);
        host.set_controls({static_cast<float>(wet), trollfx::audio::db_to_linear(static_cast<float>(in_db)),
                           trollfx::audio::db_to_linear(static_cast<float>(out_db))});
        if(factory)for(const auto&[parameter,value]:initial_parameters){
            const auto status=factory->set_bus_parameter(initial,parameter,value);
            if(status!=trollfx::es5510::factory_parameters_v01::EncodeStatus::Encoded)
                throw std::invalid_argument("initial BUS value is unverified or runtime rejected it");
        }
        std::vector<float> in_block(block * 2), out_block(block * 2);
        const auto begin = std::chrono::steady_clock::now();
        size_t cursor = 0, si=0,pi=0;size_t parameter_count=initial_parameters.size();
        while (cursor < output_frames) {
            host.service_control();
            while(si<switches.size()&&switches[si].frame==cursor){
                if(host.switch_pending())throw std::runtime_error("switch requested while prior transition is pending");
                host.request_effect(switches[si++].effect);
            }
            while(pi<parameter_events.size()&&parameter_events[pi].frame==cursor){
                const auto&e=parameter_events[pi++];
                if(host.switch_pending())throw std::runtime_error("BUS event reached during an effect transition");
                if(host.active_effect()!=e.effect)throw std::runtime_error("BUS event effect is not active at its scheduled time");
                const auto status=factory->set_bus_parameter(e.effect,e.parameter,e.value);
                if(status!=trollfx::es5510::factory_parameters_v01::EncodeStatus::Encoded)
                    throw std::runtime_error("BUS event value is outside the evidence-bounded mapping or was rejected");
                ++parameter_count;
            }
            size_t n=std::min(block,output_frames-cursor);
            if(si<switches.size()&&switches[si].frame>cursor)n=std::min(n,switches[si].frame-cursor);
            if(pi<parameter_events.size()&&parameter_events[pi].frame>cursor)n=std::min(n,parameter_events[pi].frame-cursor);
            if(!n)continue;
            for(size_t i=0;i<n;++i){in_block[2*i]=input48[cursor+i].left;in_block[2*i+1]=input48[cursor+i].right;}
            host.process(in_block.data(),2,out_block.data(),2,n);
            for(size_t i=0;i<n;++i)output48[cursor+i]={out_block[2*i],out_block[2*i+1]};
            cursor+=n;
        }
        const auto end = std::chrono::steady_clock::now();
        if (!trollfx::audio::write_stereo_pcm16_wav(output_path, rate, output48, error)) throw std::runtime_error(error);
        const double ms = std::chrono::duration<double, std::milli>(end - begin).count();
        const double audio_seconds = static_cast<double>(output_frames) / rate;
        const double ratio = audio_seconds > 0 ? (ms / 1000.0) / audio_seconds : 0.0;
        const size_t memory_estimate = (wav.frames.capacity() + input48.capacity() + output48.capacity()) * sizeof(StereoFrame) +
                                       in_block.capacity() * sizeof(float) + out_block.capacity() * sizeof(float) + host.memory_bytes();
        std::cout << "backend="<<(backend=="runtime"?"runtime (authentic factory microprogram; experimental emulator core)":"mock (synthetic; not authentic factory processing)")<<"\n"
                  << "initial_effect=" << effect_name(initial) << " final_effect=" << effect_name(host.active_effect()) << "\n"
                  << "input_rate_hz=" << wav.sample_rate << " dsp_rate_hz=" << host.dsp_rate()
                  << " output_rate_hz=" << rate << "\n"
                  << "input_frames=" << wav.frames.size() << " output_frames=" << output_frames
                  << " block_frames=" << block << " switches=" << switches.size() << " parameters=" << parameter_count << "\n"
                  << "processing_ms=" << ms << " realtime_ratio=" << ratio
                  << " estimated_memory_bytes=" << memory_estimate << " processor_latency_frames=" << host.latency_frames() << "\n";
        if(factory)std::cout<<"runtime_status="<<factory->status_message()<<"\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "trollfx-audio-host: " << e.what() << "\n";
        return 2;
    }
}
