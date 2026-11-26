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

static ValidatedEffectPackage hall_validated_package(const std::string& path,
                                                      std::uint8_t raw=52) {
    ValidatedEffectPackage p;
    p.validation_receipt_valid=p.initialization_state_valid=p.program_identity_valid=
        p.pipeline_reset_valid=p.routing_valid=true;
    auto& d=p.descriptor;
    d.slot=1; d.factory_name="ROM-01 HALL REVERB"; d.active_program_words=89;
    d.end_word=88; d.program_sha256=std::string(64,'a');
    d.factory_reference_rate_hz=29761.89453125; d.factory_variation=1;
    d.routing.host_serial_mode=0x48; d.routing.input_port=2; d.routing.output_port=1;
    d.routing.stereo=true; d.run_checkpoint_path=path; d.run_checkpoint_sha256=std::string(64,'b');
    for (const auto& write : os353::hall_decay_registers(raw))
        d.firmware_event_schedule.push_back({0,write.gpr,write.value24});
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
    assert(runtime.loadEffect(hall_validated_package(path),RateMode::Experimental48000));
    HallDecayNativeAdapter adapter;
    const auto before_startup=adapter.refresh(runtime,1,1);
    assert(!before_startup.raw_state_available && before_startup.applied_display_value==-1);
    process_frames(runtime,1);
    auto initial=adapter.refresh(runtime,1,1);
    assert(initial.raw_state_available && initial.applied_display_value==40 && initial.applied_raw_code==52);
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
    assert(scheduled.has_pending_step && scheduled.applied_raw_code==52 && scheduled.applied_display_value==40);
    assert(scheduled.pending_raw_code==53 && scheduled.pending_display_value==41);
    process_frames(runtime);
    auto applied=adapter.refresh(runtime,1,1);
    assert(!applied.has_pending_step && applied.applied_raw_code==53 && applied.applied_display_value==41);
    auto writes=trace_since(before_gate);
    const auto expected=os353::hall_decay_registers(53);
    assert(writes.size()==5);
    for (std::size_t i=0;i<expected.size();++i) {
        if (writes[i].gpr!=expected[i].gpr || writes[i].value24!=expected[i].value24)
            std::fprintf(stderr,"step write %zu got GPR %02X=%06X expected %02X=%06X\n",i,
                unsigned(writes[i].gpr),unsigned(writes[i].value24),unsigned(expected[i].gpr),unsigned(expected[i].value24));
        assert(writes[i].gpr==expected[i].gpr && writes[i].value24==expected[i].value24);
        assert(writes[i].dsp_frame==writes[0].dsp_frame);
    }

    auto cursor=TROLLfx_SimTraceLatest();
    assert(adapter.requestStep(runtime,1,1,+1)==HallDecayAdapterResult::Pending);
    process_frames(runtime);
    applied=adapter.refresh(runtime,1,1);
    assert(applied.applied_raw_code==54 && applied.applied_display_value==42);
    assert(adapter.requestStep(runtime,1,1,-1)==HallDecayAdapterResult::Pending);
    process_frames(runtime);
    applied=adapter.refresh(runtime,1,1);
    assert(applied.applied_raw_code==53 && applied.applied_display_value==41);
    assert(TROLLfx_SimTraceLatest()>cursor);

    assert(runtime.setRegister(0x6e,0x030000,runtime.getStatus().processed_dsp_frames));
    assert(!runtime.getStatus().hall_decay_step_available);
    assert(adapter.requestStep(runtime,1,1,+1)==HallDecayAdapterResult::UnknownRawState);
    assert(adapter.reset(runtime,1,1)==HallDecayAdapterResult::UnknownRawState);
    process_frames(runtime,1);
    const auto restored=adapter.refresh(runtime,1,1);
    assert(restored.applied_display_value==40 && restored.applied_raw_code==52);
#else
    assert(adapter.requestStep(runtime,1,1,+1)==HallDecayAdapterResult::FeatureDisabled);
    assert(TROLLfx_SimTraceLatest()==before_gate);
    assert(adapter.requestStep(runtime,1,2,+1)==HallDecayAdapterResult::FeatureDisabled);
#endif

    assert(!adapter.stageNumeric(100));
    std::filesystem::remove(path);
    std::puts("HALL native adapter tests: PASS");
}
