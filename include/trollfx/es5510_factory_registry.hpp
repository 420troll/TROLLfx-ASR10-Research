// Universal, payload-external factory package registry API v1.
#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace trollfx::es5510 {

using EffectSlot = std::uint8_t; // ASR-10 factory ROM slots 1..50

struct RoutingDescriptor {
    std::uint8_t host_serial_mode = 0;
    std::uint8_t input_port = 0;
    std::uint8_t output_port = 0;
    bool stereo = true;
};

struct ScheduledGprWrite {
    std::uint64_t relative_dsp_frame = 0; // relative to RUN checkpoint frame 0
    std::uint8_t gpr = 0;
    std::uint32_t value24 = 0;
};

struct ParameterPoint {
    std::int32_t display_value = 0;
    std::uint8_t gpr = 0;
    std::uint32_t value24 = 0;
};

struct VerifiedParameterDefinition {
    std::string id;
    std::string ui_label;
    std::vector<ParameterPoint> verified_points;
};

struct EffectDescriptor {
    EffectSlot slot = 0;
    std::string factory_name;
    std::uint32_t active_program_words = 0;
    std::uint32_t end_word = 0;
    std::string program_sha256;
    double factory_reference_rate_hz = 0.0;
    RoutingDescriptor routing;
    std::string package_manifest_path;
    std::string initialization_manifest_path;
    std::string run_checkpoint_path;
    std::string run_checkpoint_sha256;
    std::string firmware_event_schedule_path;
    std::string firmware_event_schedule_sha256;
    std::vector<ScheduledGprWrite> firmware_event_schedule;
    std::vector<VerifiedParameterDefinition> parameters;
};

// Only construct these from the manifest/checkpoint validator. The registry
// performs structural checks; its caller remains responsible for provenance
// and content hashes before setting validation_receipt_valid.
struct ValidatedEffectPackage {
    EffectDescriptor descriptor;
    bool validation_receipt_valid = false;
    bool initialization_state_valid = false;
    bool program_identity_valid = false;
    bool pipeline_reset_valid = false;
    bool routing_valid = false;
};

class EffectRegistry final {
public:
    bool register_validated(ValidatedEffectPackage package, std::string* error = nullptr) {
        const auto& d = package.descriptor;
        auto fail = [&](const char* message) {
            if (error) *error = message;
            return false;
        };
        if (!package.validation_receipt_valid || !package.initialization_state_valid ||
            !package.program_identity_valid || !package.pipeline_reset_valid || !package.routing_valid)
            return fail("package validation evidence is incomplete");
        if (d.slot < 1 || d.slot > 50 || d.factory_name.empty())
            return fail("effect slot/name is outside the ASR-10 factory registry");
        if (!d.active_program_words || d.active_program_words > 160 ||
            d.end_word + 1 != d.active_program_words || d.program_sha256.size() != 64)
            return fail("program identity or variable program geometry is invalid");
        for (const char c : d.program_sha256)
            if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')))
                return fail("program identity SHA-256 is malformed");
        if (d.factory_reference_rate_hz < 8000.0 || d.factory_reference_rate_hz > 192000.0)
            return fail("factory reference rate is outside the supported range");
        if (d.routing.input_port > 3 || d.routing.output_port > 3 || !d.routing.stereo)
            return fail("routing is not a supported stereo serial-port pair");
        if (d.run_checkpoint_path.empty() || d.run_checkpoint_sha256.size() != 64)
            return fail("RUN checkpoint reference is missing or malformed");
        if (d.firmware_event_schedule.size() > kMaxFirmwareEvents)
            return fail("firmware event schedule exceeds bounded capacity");
        std::uint64_t previous_frame = 0;
        for (const auto& event : d.firmware_event_schedule) {
            if (event.gpr >= 0xc0 || event.value24 > 0x00ffffffu ||
                event.relative_dsp_frame < previous_frame)
                return fail("firmware event schedule is malformed or unordered");
            previous_frame = event.relative_dsp_frame;
        }
        for (const auto& parameter : d.parameters) {
            if (parameter.id.empty() || parameter.verified_points.empty())
                return fail("verified parameter definition has no identifier or points");
            for (const auto& point : parameter.verified_points)
                if (point.gpr >= 0xc0 || point.value24 > 0x00ffffffu)
                    return fail("parameter point is outside the 24-bit GPR domain");
        }
        if (find(d.slot)) return fail("effect slot is already registered");
        packages_.push_back(std::move(package));
        std::sort(packages_.begin(), packages_.end(), [](const auto& a, const auto& b) {
            return a.descriptor.slot < b.descriptor.slot;
        });
        if (error) error->clear();
        return true;
    }

    const ValidatedEffectPackage* find(EffectSlot slot) const noexcept {
        const auto it = std::lower_bound(packages_.begin(), packages_.end(), slot,
            [](const auto& package, EffectSlot value) { return package.descriptor.slot < value; });
        return it != packages_.end() && it->descriptor.slot == slot ? &*it : nullptr;
    }

    std::size_t size() const noexcept { return packages_.size(); }
    static constexpr std::size_t kMaxFactorySlots = 50;
    // Covers the current importer schedules (largest observed here: 583)
    // while keeping registration and callback storage strictly bounded.
    static constexpr std::size_t kMaxFirmwareEvents = 1024;

private:
    std::vector<ValidatedEffectPackage> packages_; // registration is control-thread only
};

struct PresetParameterValue {
    std::string parameter_id;
    std::int32_t display_value = 0;
};

// A preset stores only a factory slot and user control values. It never stores
// firmware, checkpoint, program, GPR/SPR tables, or DRAM payloads.
struct UserPreset {
    std::string name;
    EffectSlot effect_slot = 0;
    std::vector<PresetParameterValue> parameters;
};

} // namespace trollfx::es5510
