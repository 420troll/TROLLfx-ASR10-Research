#include "trollfx/es5510_factory_runtime.hpp"
#include "trollfx/es5510_hall_decay_control.hpp"
#include "trollfx/hall_decay_native_adapter.hpp"
#include "es5510.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

using namespace trollfx::es5510;

struct TROLLfxSimTraceWrite {
    std::uint64_t sequence;
    std::uint64_t dsp_frame;
    std::uint32_t slot;
    std::uint32_t gpr;
    std::uint32_t value24;
};
extern "C" std::uint64_t TROLLfx_SimTraceLatest() noexcept;
extern "C" std::size_t TROLLfx_SimTraceCopy(std::uint64_t, TROLLfxSimTraceWrite*, std::size_t) noexcept;
extern "C" void TROLLfx_SimTraceReset() noexcept;

static std::string make_checkpoint() {
    const auto path = (std::filesystem::temp_directory_path() / "trollfx-hall-native-adapter.esp").string();
    ES5510 dsp;
    for (unsigned i=0; i<89; ++i) {
        const std::uint64_t ins = i==88 ? 0x00000000f000ULL
            : i==0 ? ((std::uint64_t(239)<<24)|(std::uint64_t(237)<<16)|0x9000ULL)
            : i==1 ? ((std::uint64_t(238)<<24)|(std::uint64_t(236)<<16)|0x9000ULL) : 0;
        for (unsigned b=0;b<6;++b) dsp.host_w(3+b,static_cast<std::uint8_t>(ins>>(40-8*b)));
        dsp.host_w(0xc0,static_cast<std::uint8_t>(i));
    }
    dsp.host_w(0x18,0x48);
    FILE* f=std::fopen(path.c_str(),"wb"); assert(f && dsp.write_capture(f)); std::fclose(f);
    return path;
}

static EffectPackage hall_package(const std::string& path, std::uint8_t variation=1) {
    EffectPackage p;
    p.effect=EffectId::Rom01Hall; p.checkpoint_path=path; p.active_program_words=89;
    p.factory_processing_rate_hz=29761.89453125; p.pipeline_reset_acknowledged=true;
    p.package_provenance_validated=true; p.serial_route_validated=true; p.factory_variation=variation;
    return p;
}

static std::vector<TROLLfxSimTraceWrite> trace_since(std::uint64_t after) {
    std::array<TROLLfxSimTraceWrite,128> rows{};
    const auto count=TROLLfx_SimTraceCopy(after,rows.data(),rows.size());
    return {rows.begin(),rows.begin()+static_cast<std::ptrdiff_t>(count)};
}

static void process_frames(FactoryRuntime& runtime, std::size_t frames=8) {
    std::array<float,16> in{},out{};
    for (std::size_t i=0;i<frames;++i) {
        in[2*i]=0.15f*std::sin(static_cast<float>(i)*0.17f);
        in[2*i+1]=0.12f*std::sin(static_cast<float>(i)*0.13f);
    }
    assert(runtime.processStereo(in.data(),out.data(),frames,48000.0));
    assert(std::all_of(out.begin(),out.end(),[](float x){return std::isfinite(x);}));
}

int main() {
    const auto path=make_checkpoint();
    FactoryRuntime runtime;
    assert(runtime.loadEffect(hall_package(path),RateMode::Experimental48000));
    HallDecayNativeAdapter adapter;
    auto initial=adapter.refresh(runtime,1,1);
    assert(initial.raw_state_available && initial.applied_display_value==0 && initial.applied_raw_code==0);
    assert(adapter.stageNumeric(99));
    const auto before_gate=TROLLfx_SimTraceLatest();
    const auto draft_state=adapter.refresh(runtime,1,1);
    assert(draft_state.has_pending_numeric && draft_state.pending_display_value==99);

#if TROLLFX_HALL_DECAY_NATIVE_GATE
    assert(adapter.requestStep(runtime,1,1,+1)==HallDecayAdapterResult::PendingNumericDraft);
    assert(TROLLfx_SimTraceLatest()==before_gate);
    adapter.discardNumeric();

    assert(adapter.requestStep(runtime,1,2,+1)==HallDecayAdapterResult::UnsupportedContext);
    assert(adapter.requestStep(runtime,1,1,+1)==HallDecayAdapterResult::Pending);
    auto scheduled=adapter.refresh(runtime,1,1);
    assert(scheduled.has_pending_step && scheduled.applied_raw_code==0 && scheduled.applied_display_value==0);
    assert(scheduled.pending_raw_code==1 && scheduled.pending_display_value==1);
    process_frames(runtime);
    auto applied=adapter.refresh(runtime,1,1);
    assert(!applied.has_pending_step && applied.applied_raw_code==1 && applied.applied_display_value==1);
    auto writes=trace_since(before_gate);
    const auto expected=os353::hall_decay_registers(1);
    assert(writes.size()==5);
    for (std::size_t i=0;i<expected.size();++i) {
        assert(writes[i].gpr==expected[i].gpr && writes[i].value24==expected[i].value24);
        assert(writes[i].dsp_frame==writes[0].dsp_frame);
    }

    auto cursor=TROLLfx_SimTraceLatest();
    assert(adapter.requestStep(runtime,1,1,+1)==HallDecayAdapterResult::Pending);
    process_frames(runtime);
    applied=adapter.refresh(runtime,1,1);
    assert(applied.applied_raw_code==3 && applied.applied_display_value==2); // raw 2 is duplicate LCD 1
    assert(adapter.requestStep(runtime,1,1,-1)==HallDecayAdapterResult::Pending);
    process_frames(runtime);
    applied=adapter.refresh(runtime,1,1);
    assert(applied.applied_raw_code==2 && applied.applied_display_value==1);
    assert(TROLLfx_SimTraceLatest()>cursor);

    assert(runtime.setRegister(0x6e,0x030000,runtime.getStatus().processed_dsp_frames));
    assert(!runtime.getStatus().hall_decay_step_available);
    assert(adapter.requestStep(runtime,1,1,+1)==HallDecayAdapterResult::UnknownRawState);
    assert(adapter.reset(runtime,1,1)==HallDecayAdapterResult::Applied);
    const auto restored=adapter.refresh(runtime,1,1);
    assert(restored.applied_display_value==0 && restored.applied_raw_code==0);
#else
    assert(adapter.requestStep(runtime,1,1,+1)==HallDecayAdapterResult::FeatureDisabled);
    assert(TROLLfx_SimTraceLatest()==before_gate);
    assert(adapter.requestStep(runtime,1,2,+1)==HallDecayAdapterResult::FeatureDisabled);
#endif

    assert(!adapter.stageNumeric(100));
    std::filesystem::remove(path);
    std::puts("HALL native adapter tests: PASS");
}
