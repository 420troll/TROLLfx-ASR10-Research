// TROLLfx ES5510 Experimental Runtime V0.1 public integration contract.
// Copyright (c) 2026. See repository LICENSE.
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include "trollfx/es5510_factory_registry.hpp"

namespace trollfx::es5510 {

enum class EffectId : std::uint8_t { Rom01Hall = 1, Rom02Reverb44k = 2 };
enum class RateMode : std::uint8_t { Experimental48000, FactoryReference };
enum class StatusCode : std::uint8_t {
    Empty, Ready, InvalidArgument, PackageRejected, CaptureRejected,
    UnsupportedRate, EventQueueFull, EventInPast, InternalError
};

// Describes an already-evidenced RUN-boundary package. The referenced capture
// contains the authentic 160-word image slots, 192 GPRs, 22 SPRs, runtime
// latches, memory configuration, and full DRAM image. The native capture
// loader resets omitted pipeline slots; callers must only set the reset flag
// after validating the package's HALT/pipeline-reset evidence.
struct EffectPackage {
    EffectId effect = EffectId::Rom01Hall;
    std::string checkpoint_path;      // local/private ES5510C capture; never ship it in the plugin
    std::uint32_t active_program_words = 0;
    double factory_processing_rate_hz = 0.0;
    bool pipeline_reset_acknowledged = false;
    bool package_provenance_validated = false;
    bool serial_route_validated = false;
    // Zero means unknown. Set to 1 only when the private checkpoint manifest
    // validates the HALL variation; required by the stateful HALL decay editor.
    std::uint8_t factory_variation = 0;
};

struct RuntimeStatus {
    StatusCode code = StatusCode::Empty;
    EffectId effect = EffectId::Rom01Hall;
    RateMode rate_mode = RateMode::Experimental48000;
    double processing_rate_hz = 0.0;
    double host_rate_hz = 0.0;
    std::uint64_t processed_dsp_frames = 0;
    std::uint64_t scheduled_writes_applied = 0;
    bool initialization_schedule_complete = true;
    std::uint64_t initialization_complete_frame = 0;
    std::uint16_t firmware_writes_pending = 0;
    std::uint16_t parameter_writes_pending = 0;
    bool last_parameter_write_applied = false;
    std::uint32_t active_program_words = 0;
    std::uint32_t algorithmic_latency_host_frames = 0;
    bool hall_decay_step_available = false;
    std::uint8_t hall_decay_raw_code = 0;
    std::int16_t hall_decay_display_value = -1;
    const char* message = "not loaded"; // static storage; valid until next API call
};

// Not thread-safe: load/reset/rate/event control calls must occur between
// processStereo calls on the owning audio thread in V0.1. Event scheduling is
// bounded/fixed-capacity. processStereo performs no allocation and retains DSP,
// resampler phase, and delay memory continuously across arbitrary block sizes.
class FactoryRuntime final {
public:
    FactoryRuntime();
    ~FactoryRuntime();
    FactoryRuntime(FactoryRuntime&&) noexcept;
    FactoryRuntime& operator=(FactoryRuntime&&) noexcept;
    FactoryRuntime(const FactoryRuntime&) = delete;
    FactoryRuntime& operator=(const FactoryRuntime&) = delete;

    // Loads only a validated private RUN checkpoint package. Program bytes alone
    // are insufficient: this call requires complete live state and reset evidence.
    bool loadEffect(const EffectPackage& package, RateMode mode = RateMode::Experimental48000);
    // Generic path: descriptor fields must originate from a locally validated package.
    bool loadEffect(const ValidatedEffectPackage& package, RateMode mode = RateMode::Experimental48000);
    bool reset();
    bool setProcessingRate(RateMode mode);

    // Writes a 24-bit ES5510 register (GPR indices 0x00..0xBF). Applies before
    // the DSP frame whose zero-based absolute index is scheduled_frame. Calls
    // must be made between audio blocks; events before the next unprocessed frame fail.
    bool setRegister(std::uint8_t index, std::uint32_t value, std::uint64_t scheduled_frame);
    // Queue one event from a previously validated RUN initialization schedule.
    // Parameter edits requested before all such events are applied are deferred
    // behind the final initialization frame.
    bool scheduleInitializationRegister(std::uint8_t index, std::uint32_t value,
                                        std::uint64_t scheduled_frame);
    bool setParameter(const EffectDescriptor& descriptor, const std::string& parameter_id,
                      std::int32_t display_value, std::uint64_t scheduled_frame);
    // Applies one authentic OS 3.53 ROM-01 HALL Variation 1 decay editor step.
    // direction is -1 (Down) or +1 (Up); the current raw GPR 6E code is retained
    // across calls so duplicate LCD buckets preserve the original route behavior.
    // This is not a direct display-value setter and is not supported for other
    // effects/variations. Call between processStereo blocks on the owning thread.
    bool stepHallDecayTime(int direction, std::uint64_t scheduled_frame);

    // Interleaved stereo float PCM, [-1,+1] nominal. Input/output serial lanes
    // are selected by the validated effect descriptor. Host sample rate is
    // explicit; rate conversion is outside ES5510::run_frame().
    bool processStereo(const float* input_interleaved, float* output_interleaved,
                       std::size_t frames, double host_rate_hz);

    RuntimeStatus getStatus() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace trollfx::es5510
