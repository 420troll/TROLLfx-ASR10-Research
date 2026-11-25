#include "trollfx/es5510_audio_test_backend.hpp"

#include "es5510.h"
#include "wav_io.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace trollfx::es5510::audio_test {
namespace {
using trollfx::audio::StereoFrame;
using trollfx::audio::WavData;

bool load_mono_stereo_input(const std::string& path, std::vector<float>& interleaved,
                            std::uint64_t& content_frames, AudioMetrics& metrics,
                            std::string& error) {
    WavData wav;
    if (!trollfx::audio::read_stereo_wav(path, wav, error)) return false;
    if (wav.frames.empty() || !wav.sample_rate) { error = "input WAV is empty or has an invalid sample rate"; return false; }
    constexpr double target_rate = 48000.0;
    const auto converted = static_cast<std::size_t>(std::llround(wav.frames.size() * target_rate / wav.sample_rate));
    if (!converted) { error = "input WAV is too short to resample"; return false; }
    interleaved.resize(converted * 2);
    for (std::size_t i=0; i<converted; ++i) {
        const double source = static_cast<double>(i) * wav.sample_rate / target_rate;
        const auto i0 = std::min(static_cast<std::size_t>(source), wav.frames.size()-1);
        const auto i1 = std::min(i0+1, wav.frames.size()-1);
        const float f=static_cast<float>(source-i0);
        interleaved[2*i]=wav.frames[i0].left+(wav.frames[i1].left-wav.frames[i0].left)*f;
        interleaved[2*i+1]=wav.frames[i0].right+(wav.frames[i1].right-wav.frames[i0].right)*f;
    }
    content_frames=converted;
    metrics=measureAudio(interleaved);
    return true;
}

std::vector<StereoFrame> to_frames(const std::vector<float>& interleaved) {
    std::vector<StereoFrame> out(interleaved.size()/2);
    for (std::size_t i=0;i<out.size();++i) out[i]={interleaved[2*i],interleaved[2*i+1]};
    return out;
}

bool write_float_wav(const std::string& path,const std::vector<float>& interleaved,std::string& error) {
    return trollfx::audio::write_stereo_pcm16_wav(path,48000,to_frames(interleaved),error);
}

bool render_loaded(const EffectRegistry& registry,EffectSlot slot,
                   const std::vector<float>& input,std::uint64_t content_frames,
                   const std::vector<ParameterChange>& events,const RenderOptions& options,
                   std::vector<float>& output,RenderReport& report,std::string& error) {
    if (!options.block_frames || options.block_frames>1048576) { error="block size must be 1..1048576 frames"; return false; }
    if (options.rate_mode!=RateMode::Experimental48000 || std::fabs(options.host_rate_hz-48000.0)>0.001) {
        error="offline WAV runner currently uses experimental 48 kHz processing"; return false;
    }
    if (slot<1 || slot>50) { error="factory slot must be in 1..50"; return false; }
    for (std::size_t i=0;i<events.size();++i) {
        if (i && events[i].dsp_frame<events[i-1].dsp_frame) { error="parameter events must be ordered by DSP frame"; return false; }
        if (events[i].dsp_frame>=content_frames+options.tail_frames) { error="parameter event is outside the rendered frames"; return false; }
    }

    FactoryAudioTestBackend backend(registry);
    if (!backend.selectEffect(slot,options.rate_mode)) { error=backend.status().message; return false; }
    const std::size_t total=static_cast<std::size_t>(content_frames)+options.tail_frames;
    output.assign(total*2,0.0f);
    std::vector<float> input_with_tail(total*2,0.0f);
    std::copy(input.begin(),input.end(),input_with_tail.begin());
    std::vector<float> in_block(options.block_frames*2),out_block(options.block_frames*2);
    std::size_t cursor=0,event_index=0;
    while (cursor<total) {
        const auto dsp_frame=backend.status().processed_dsp_frames;
        while(event_index<events.size() && events[event_index].dsp_frame==dsp_frame) {
            const auto& e=events[event_index++];
            if(!backend.setParameter(e.parameter_id,e.display_value,e.dsp_frame)) {
                error=backend.status().message; return false;
            }
        }
        if(event_index<events.size() && events[event_index].dsp_frame<dsp_frame) {
            error="parameter event fell behind the processed DSP frame"; return false;
        }
        std::size_t n=std::min(options.block_frames,total-cursor);
        if(event_index<events.size() && events[event_index].dsp_frame>dsp_frame)
            n=std::min<std::size_t>(n,events[event_index].dsp_frame-dsp_frame);
        if(!n) { error="event scheduler made no forward progress"; return false; }
        std::copy_n(input_with_tail.data()+cursor*2,n*2,in_block.data());
        if(!backend.process(in_block.data(),out_block.data(),n,options.host_rate_hz)) {
            error=backend.status().message; return false;
        }
        std::copy_n(out_block.data(),n*2,output.data()+cursor*2);
        cursor+=n;
    }
    if(event_index!=events.size()) { error="not all parameter events were applied"; return false; }
    const auto status=backend.status();
    report.slot=slot; report.dsp_frames=status.processed_dsp_frames;
    report.writes_applied=status.scheduled_writes_applied;
    report.latency_frames=status.algorithmic_latency_host_frames;
    report.output=measureAudio(output);
    report.parameter_writes=backend.parameterWriteLog();
    return true;
}

std::vector<float> latency_aligned_dry(const std::vector<float>& input,
                                       std::uint64_t content_frames,
                                       std::size_t tail_frames,std::uint32_t latency) {
    const auto frames=static_cast<std::size_t>(content_frames)+tail_frames;
    std::vector<float> dry(frames*2,0.0f);
    for(std::size_t i=latency;i<frames;++i) {
        const auto source=i-latency;
        if(source>=content_frames) continue;
        dry[2*i]=input[2*source]; dry[2*i+1]=input[2*source+1];
    }
    return dry;
}
} // namespace

FactoryAudioTestBackend::FactoryAudioTestBackend(const EffectRegistry& registry) noexcept
    : registry_(registry) {}

bool FactoryAudioTestBackend::selectEffect(EffectSlot slot,RateMode mode) {
    const auto* package=registry_.find(slot);
    if(!package) return false;
    if(!runtime_.loadEffect(*package,mode)) { package_=nullptr; active_slot_=0; return false; }
    package_=package; active_slot_=slot; writes_.clear(); return true;
}

bool FactoryAudioTestBackend::reset() {
    if(!package_ || !runtime_.reset()) return false;
    writes_.clear(); return true;
}

bool FactoryAudioTestBackend::setParameter(const std::string& id,std::int32_t value,std::uint64_t frame) {
    if(!package_) return false;
    const auto& d=package_->descriptor;
    const VerifiedParameterDefinition* definition=nullptr;
    const ParameterPoint* selected=nullptr;
    for(const auto& p:d.parameters) if(p.id==id) {
        definition=&p;
        for(const auto& point:p.verified_points) if(point.display_value==value) { selected=&point; break; }
        break;
    }
    if(!definition || !selected) return false;
    if(!runtime_.setParameter(d,id,value,frame)) return false;
    if(selected->ordered_writes.empty()) {
        writes_.push_back({frame,0,id,value,selected->gpr,selected->value24});
    } else {
        for(std::size_t i=0;i<selected->ordered_writes.size();++i) {
            const auto& w=selected->ordered_writes[i];
            writes_.push_back({frame,static_cast<std::uint16_t>(i),id,value,w.gpr,w.value24});
        }
    }
    return true;
}

bool FactoryAudioTestBackend::process(const float* input,float* output,std::size_t frames,double rate) noexcept {
    if(!package_) return false;
    return runtime_.processStereo(input,output,frames,rate);
}

RuntimeStatus FactoryAudioTestBackend::status() const noexcept { return runtime_.getStatus(); }
std::size_t FactoryAudioTestBackend::memoryBytes() const noexcept { return ES5510::DRAM_SIZE*sizeof(std::int16_t)+128u*1024u; }

WavAudioTestRunner::WavAudioTestRunner(const EffectRegistry& registry) noexcept : registry_(registry) {}

bool WavAudioTestRunner::render(const std::string& input_path,const std::string& output_path,
                               EffectSlot slot,const std::vector<ParameterChange>& events,
                               const RenderOptions& options,RenderReport& report,std::string& error) const {
    std::vector<float> input,output; std::uint64_t content_frames=0; AudioMetrics in_metrics;
    if(!load_mono_stereo_input(input_path,input,content_frames,in_metrics,error)) return false;
    if(!render_loaded(registry_,slot,input,content_frames,events,options,output,report,error)) return false;
    report.input=in_metrics;
    return write_float_wav(output_path,output,error);
}

bool WavAudioTestRunner::renderWetDryAB(const std::string& input_path,const std::string& processed_path,
                                        const std::string& bypass_path,EffectSlot slot,
                                        const std::vector<ParameterChange>& events,const RenderOptions& options,
                                        ABReport& report,std::string& error) const {
    std::vector<float> input,processed; std::uint64_t content_frames=0; AudioMetrics input_metrics;
    if(!load_mono_stereo_input(input_path,input,content_frames,input_metrics,error)) return false;
    if(!render_loaded(registry_,slot,input,content_frames,events,options,processed,report.render,error)) return false;
    auto bypass=latency_aligned_dry(input,content_frames,options.tail_frames,report.render.latency_frames);
    if(!write_float_wav(processed_path,processed,error) || !write_float_wav(bypass_path,bypass,error)) return false;
    report.bypass=measureAudio(bypass); report.processed=measureAudio(processed);
    report.difference=measureDifference(processed,bypass); report.render.input=input_metrics;
    return true;
}

bool WavAudioTestRunner::renderParameterAB(const std::string& input_path,const std::string& baseline_path,
                                           const std::string& changed_path,EffectSlot slot,
                                           const std::vector<ParameterChange>& base_events,
                                           const std::vector<ParameterChange>& changed_events,
                                           const RenderOptions& options,DifferenceMetrics& difference,
                                           RenderReport& baseline_report,RenderReport& changed_report,
                                           std::string& error) const {
    std::vector<float> input,base,changed; std::uint64_t content_frames=0; AudioMetrics input_metrics;
    if(!load_mono_stereo_input(input_path,input,content_frames,input_metrics,error)) return false;
    if(!render_loaded(registry_,slot,input,content_frames,base_events,options,base,baseline_report,error)) return false;
    if(!render_loaded(registry_,slot,input,content_frames,changed_events,options,changed,changed_report,error)) return false;
    if(!write_float_wav(baseline_path,base,error) || !write_float_wav(changed_path,changed,error)) return false;
    difference=measureDifference(base,changed);
    baseline_report.input=changed_report.input=input_metrics;
    return true;
}

AudioMetrics measureAudio(const std::vector<float>& pcm) noexcept {
    AudioMetrics m; m.frames=pcm.size()/2;
    double left=0,right=0;
    for(std::size_t i=0;i+1<pcm.size();i+=2) {
        const float l=pcm[i],r=pcm[i+1];
        if(!std::isfinite(l)||!std::isfinite(r)) continue;
        m.finite_samples+=2; left+=double(l)*l; right+=double(r)*r;
        m.peak_left=std::max(m.peak_left,std::fabs(l)); m.peak_right=std::max(m.peak_right,std::fabs(r));
    }
    if(m.finite_samples>=2) {
        const double channel_samples=static_cast<double>(m.finite_samples/2);
        m.rms_left=std::sqrt(left/channel_samples); m.rms_right=std::sqrt(right/channel_samples);
    }
    return m;
}

DifferenceMetrics measureDifference(const std::vector<float>& a,const std::vector<float>& b) noexcept {
    DifferenceMetrics m;
    const std::size_t n=std::min(a.size(),b.size()); double left=0,right=0;
    for(std::size_t i=0;i+1<n;i+=2) {
        if(!std::isfinite(a[i])||!std::isfinite(a[i+1])||!std::isfinite(b[i])||!std::isfinite(b[i+1])) continue;
        const float l=a[i]-b[i],r=a[i+1]-b[i+1];
        ++m.finite_samples; left+=double(l)*l; right+=double(r)*r;
        m.difference_peak=std::max({m.difference_peak,std::fabs(l),std::fabs(r)});
    }
    if(m.finite_samples) {
        m.difference_rms_left=std::sqrt(left/m.finite_samples);
        m.difference_rms_right=std::sqrt(right/m.finite_samples);
    }
    return m;
}

} // namespace trollfx::es5510::audio_test
