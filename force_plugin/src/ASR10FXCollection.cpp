// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 TROLLfx contributors
#include "mpc_plugin.h"
#include "ES5510DSPBackend.h"
#include "ES5510FactoryPackageProvider.h"
#include "trollfx/es5510_factory_parameter_control_v01.hpp"
#include "trollfx/es5510_factory_parameter_discovery_v02.hpp"
#include "trollfx/es5510_factory_editor_v03.hpp"
#include "trollfx/es5510_factory_editor_v04.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <iterator>
#include <string>
#include <vector>

namespace {
constexpr const auto& kEffectNames = trollfx::es5510::factory_editor_v03::kEffectNames;

std::size_t verifiedControlCount(std::uint8_t slot) noexcept;

std::vector<std::string> effectChoices(const IValidatedFactoryPackageProvider* provider) {
    std::vector<std::string> choices;
    choices.reserve(50);
    for (std::uint8_t slot = 1; slot <= 50; ++slot) {
        const bool available = provider && provider->package_for_slot(slot);
        const auto controls = verifiedControlCount(slot);
        choices.emplace_back(std::string(kEffectNames[slot - 1]) +
                             (available ? "  [READY]" : "  [UNAVAILABLE]") +
                             (controls ? "  [" + std::to_string(controls) + " EDIT]" : "  [NO EDIT]"));
    }
    return choices;
}

std::vector<std::string> numericChoices(int first, int second) {
    return {std::to_string(first) + " BUS", std::to_string(second) + " BUS"};
}

const IValidatedFactoryPackageProvider* resolveProvider() {
    const auto* injected = TROLLfx_GetValidatedFactoryPackageProvider();
    return injected ? injected : TROLLfx_GetProductionFactoryPackageProvider();
}

int choiceAt(const mpc::Plugin& plugin, int index) noexcept {
    return plugin.getInt(index);
}

using trollfx::es5510::factory_editor_v03::FactoryControl;
constexpr const auto& kFactoryControls = trollfx::es5510::factory_editor_v03::kControls;
constexpr std::size_t kLegacyControlCount = trollfx::es5510::factory_editor_v03::kLegacyControlCount;
constexpr std::size_t kV2ControlCount = std::size(kFactoryControls) - kLegacyControlCount;
constexpr const auto& kV4Controls = trollfx::es5510::factory_editor_v04::kControls;
constexpr std::size_t kV4ControlCount = std::size(kV4Controls);
constexpr std::size_t kDynamicEditSlotCount = 8;
constexpr std::size_t editBankCountForControls(std::size_t count) noexcept {
    return count <= kDynamicEditSlotCount ? 1 :
        (count + kDynamicEditSlotCount - 1) / kDynamicEditSlotCount;
}

const trollfx::es5510::factory_editor_v04::Control* dynamicEditControl(
    std::uint8_t slot, std::size_t ordinal) noexcept {
    for (const auto& control : kV4Controls) {
        if (control.slot != slot) continue;
        if (ordinal-- == 0) return &control;
    }
    return nullptr;
}

std::size_t dynamicEditControlCount(std::uint8_t slot) noexcept {
    std::size_t count = 0;
    for (const auto& control : kV4Controls) count += control.slot == slot ? 1u : 0u;
    return count;
}

std::size_t dynamicEditBankCount(std::uint8_t slot) noexcept {
    return editBankCountForControls(dynamicEditControlCount(slot));
}

std::vector<std::string> dynamicEditBankChoices() {
    std::size_t max_banks = 2;
    for (std::uint8_t slot = 1; slot <= 50; ++slot)
        max_banks = std::max(max_banks, dynamicEditBankCount(slot));
    std::vector<std::string> choices;
    choices.reserve(max_banks);
    for (std::size_t i = 0; i < max_banks; ++i)
        choices.emplace_back("EDIT " + std::to_string(i + 1));
    return choices;
}

std::size_t verifiedControlCount(std::uint8_t slot) noexcept {
    std::size_t count = 0;
    for (const auto& control : kFactoryControls) count += control.slot == slot ? 1u : 0u;
    return count;
}

const trollfx::es5510::VerifiedParameterDefinition* findParameter(
    const IValidatedFactoryPackageProvider* provider, std::uint8_t slot, const char* id) noexcept {
    const auto* package = provider ? provider->package_for_slot(slot) : nullptr;
    if (!package || !id) return nullptr;
    const auto& parameters = package->descriptor.parameters;
    const auto it = std::find_if(parameters.begin(), parameters.end(),
        [id](const auto& parameter) { return parameter.id == id; });
    return it == parameters.end() ? nullptr : &*it;
}

std::vector<std::string> parameterChoices(
    const IValidatedFactoryPackageProvider* provider, std::uint8_t slot,
    const char* id, bool& supported) {
    const bool has_package = provider && provider->package_for_slot(slot);
    const auto* parameter = findParameter(provider, slot, id);
    trollfx::es5510::EffectDescriptor fallback;
    if (!parameter && !has_package) {
        fallback.slot = slot;
        trollfx::es5510::parameter_discovery_v02::append_verified_parameters(fallback);
        const auto it = std::find_if(fallback.parameters.begin(), fallback.parameters.end(),
            [id](const auto& candidate) { return candidate.id == id; });
        if (it != fallback.parameters.end()) parameter = &*it;
    }
    supported = parameter && parameter->verified_points.size() == 2;
    if (!supported) return {"UNVERIFIED"};
    std::vector<std::string> choices;
    choices.reserve(parameter->verified_points.size() + 1);
    choices.emplace_back("UNCHANGED");
    for (const auto& point : parameter->verified_points) {
        choices.push_back(point.display_text.empty() ? std::to_string(point.display_value)
                                                     : point.display_text);
    }
    return choices;
}
} // namespace

class ASR10FXCollection final : public mpc::Plugin {
    enum ParamIndex { Fx = 0, Wet, In, Out, Bypass, Status,
                      LegacyBus1, LegacyBus2, HallBus1, HallBus2, Rom02Bus1, Rom02Bus2 };

    static mpc::PluginInfo makeInfo() {
        mpc::PluginInfo info;
        info.name = "ASR10 FX Collection";
        info.vendor = "TROLLfx";
        info.uniqueId = MPC_FOURCC('T', 'f', 'x', 'F');
        info.version = 1000;
        info.isInstrument = false;
        info.numInputs = 2;
        info.numOutputs = 2;
        return info;
    }

public:
    ASR10FXCollection()
        : mpc::Plugin(makeInfo()), provider_(resolveProvider()),
          backend_(provider_) {
        applied_control_values_.fill(-1);
        using namespace mpc;
        addParam(choiceParam("effect_slot", "FX Slot", effectChoices(provider_), 0));
        addParam(floatParam("host_wet", "Wet / Dry", 0, 100, 100, "%", 0));
        addParam(floatParam("host_input_gain", "Input Gain", -24, 24, 0, "dB", 1));
        addParam(floatParam("host_output_gain", "Output Gain", -24, 24, 0, "dB", 1));
        addParam(boolParam("host_bypass", "Host Bypass", false));
        addParam(choiceParam("load_status", "Load Status",
            {"Package required", "Unavailable", "Ready", "Load failed", "Loading"}, 0));
        // Retain IDs and choice ordering from the previous candidate so saved
        // VST chunks remain readable. These legacy selectors are intentionally
        // absent from the skin; only the new verified controls affect DSP.
        addParam(choiceParam("reverb_bus1", "Reverb BUS1",
            {"HALL 28", "HALL 29", "ROM02 25", "ROM02 26"}, 0));
        addParam(choiceParam("reverb_bus2", "Reverb BUS2",
            {"HALL 28", "HALL 29", "ROM02 25", "ROM02 26"}, 0));
        addParam(choiceParam("hall_bus1", "REVERB MIX BUS1 (HALL)", numericChoices(28, 29), 0));
        addParam(choiceParam("hall_bus2", "REVERB MIX BUS2 (HALL)", numericChoices(28, 29), 0));
        addParam(choiceParam("rom02_bus1", "REVERB MIX BUS1 (44KHZ)", numericChoices(25, 26), 0));
        addParam(choiceParam("rom02_bus2", "REVERB MIX BUS2 (44KHZ)", numericChoices(25, 26), 0));
        for (std::size_t i = kLegacyControlCount; i < std::size(kFactoryControls); ++i) {
            const auto& control = kFactoryControls[i];
            bool supported = false;
            auto choices = parameterChoices(provider_, control.slot, control.id, supported);
            control_supported_[i - kLegacyControlCount] = supported;
            std::string id = "factory_";
            id += control.id;
            id += "_slot";
            id += std::to_string(control.slot);
            addParam(choiceParam(id.c_str(), control.label, std::move(choices), 0));
        }
        // V4 controls are append-only, have stable effect-qualified IDs, and
        // expose only directly verified display points. Existing IDs/order
        // remain intact for VST automation and saved host chunks.
        for (const auto& control : kV4Controls) {
            std::vector<std::string> choices;
            choices.reserve(control.point_count);
            for (std::size_t p = 0; p < control.point_count; ++p) choices.emplace_back(control.labels[p]);
            addParam(choiceParam(control.parameter_id, control.host_name, std::move(choices), 0));
        }
        // V4.1 appends stable routing parameters after every existing ID. Their
        // names stay generic in the stock SDK; formatValue() supplies the active
        // factory label/value and the audio thread routes each slot by FX Slot.
        for (std::size_t i = 0; i < kDynamicEditSlotCount; ++i) {
            const auto number = std::to_string(i + 1);
            const auto id = "factory_edit_slot_" + number;
            const auto name = "EDIT SLOT " + number;
            edit_slot_parameter_indices_[i] = addParam(floatParam(id.c_str(), name.c_str(), 0.0f, 1.0f, 0.0f, "", 3));
        }
        edit_bank_parameter_index_ = addParam(choiceParam("factory_edit_bank", "EDIT BANK", dynamicEditBankChoices(), 0));
        for (std::size_t i = 0; i < kDynamicEditSlotCount; ++i) {
            const auto number = std::to_string(i + 1);
            const auto id = "edit_slot_" + number + "_available";
            const auto name = "SLOT " + number + " ON";
            auto available = boolParam(id.c_str(), name.c_str(), false);
            available.automatable = false;
            edit_slot_available_indices_[i] = addParam(available);
        }
        auto bank_available = boolParam("edit_bank_available", "BANK SELECT ON", false);
        bank_available.automatable = false;
        edit_bank_available_index_ = addParam(bank_available);
        for (auto& changed : v4_control_changed_) changed.store(false, std::memory_order_relaxed);
        for (auto& changed : edit_slot_changed_) changed.store(false, std::memory_order_relaxed);
        refreshDynamicEditWorkspace(false);
    }

    void prepare(double rate, int) override {
        const auto selected = static_cast<std::uint8_t>(std::clamp(getInt(Fx), 0, 49) + 1);
        backend_.prepare(selected, rate);
        applied_slot_ = 0;
    }

    void reset() override { applied_slot_ = 0; }

    void parameterChanged(int index, float) override {
        if (syncing_edit_workspace_.load(std::memory_order_acquire)) return;
        if (index == Fx) {
            refreshDynamicEditWorkspace(true);
            return;
        }
        if (index == edit_bank_parameter_index_) {
            refreshDynamicEditWorkspace(true);
            return;
        }
        for (std::size_t i = 0; i < kDynamicEditSlotCount; ++i) {
            if (edit_slot_parameter_indices_[i] == index) {
                edit_slot_changed_[i].store(true, std::memory_order_release);
                return;
            }
        }
        for (std::size_t i = 0; i < kV4ControlCount; ++i) {
            if (kV4Controls[i].parameter_index == index) {
                v4_control_changed_[i].store(true, std::memory_order_release);
                const auto selected = static_cast<std::uint8_t>(std::clamp(getInt(Fx), 0, 49) + 1);
                if (kV4Controls[i].slot == selected &&
                    !applying_routed_edit_slot_.load(std::memory_order_acquire)) {
                    for (std::size_t ordinal = 0; ordinal < kDynamicEditSlotCount; ++ordinal) {
                        if (dynamicEditControl(selected, ordinal) != &kV4Controls[i]) continue;
                        syncEditSlotFromControl(ordinal, kV4Controls[i]);
                        break;
                    }
                }
                return;
            }
        }
    }

    bool formatValue(int index, float plain, std::string& out) override {
        const auto status = backend_.status();
        if (index == Status) {
            switch (status) {
                case ES5510BackendStatus::NoProvider: out = "MISSING"; break;
                case ES5510BackendStatus::Unavailable: out = "UNAVAIL"; break;
                case ES5510BackendStatus::Loading: out = "LOADING"; break;
                case ES5510BackendStatus::Ready: out = "READY"; break;
                case ES5510BackendStatus::Failed: out = "LOAD ERR"; break;
            }
            return true;
        }
        for (std::size_t i = 0; i < kDynamicEditSlotCount; ++i) {
            if (index != edit_slot_parameter_indices_[i]) continue;
            const auto slot = static_cast<std::uint8_t>(std::clamp(getInt(Fx), 0, 49) + 1);
            const auto bank = static_cast<std::size_t>(std::clamp(getInt(edit_bank_parameter_index_), 0, 255));
            const auto* control = dynamicEditControl(slot, bank * kDynamicEditSlotCount + i);
            if (!control || control->point_count == 0) {
                out = "NO VERIFIED CONTROL";
                return true;
            }
            const auto point = static_cast<std::size_t>(std::clamp(
                static_cast<int>(std::lround(plain * static_cast<float>(control->point_count - 1))),
                0, static_cast<int>(control->point_count - 1)));
            out = std::string(control->label) + ": " + control->labels[point];
            return true;
        }
        if (index != Fx) return false;
        const int slot_index = std::clamp(static_cast<int>(plain), 0, 49);
        const auto slot = static_cast<std::uint8_t>(slot_index + 1);
        const auto* package = provider_ ? provider_->package_for_slot(slot) : nullptr;
        const char* state = "UNAVAILABLE";
        if (!provider_) state = "PACKAGE REQUIRED";
        else if (!package) state = "UNAVAILABLE";
        else if (status == ES5510BackendStatus::Loading) state = "LOADING";
        else if (status == ES5510BackendStatus::Failed) state = "LOAD FAILED";
        else if (backend_.active_slot() == slot && status == ES5510BackendStatus::Ready)
            state = "READY";
        else state = "SELECTED";
        out = std::string(kEffectNames[slot_index]) + " / " + state;
        out += verifiedControlCount(slot) ? " / VERIFIED EDIT" : " / NO VERIFIED EDIT";
        return true;
    }

    void process(mpc::ProcessContext& context) override {
        const auto selected = static_cast<std::uint8_t>(std::clamp(getInt(Fx), 0, 49) + 1);
        backend_.request_effect(selected);
        backend_.set_mix(get(Wet) / 100.0f, get(In), get(Out), getInt(Bypass) != 0);

        // Parameter controls are consumed on the owning audio thread and only
        // after the target package has become active. setRegister is bounded,
        // frame-scheduled, and does not allocate.
        const auto active = backend_.active_slot();
        if (active != applied_slot_) {
            applied_slot_ = active;
            applied_control_values_.fill(-1);
        }
        applyVerifiedControls(active);
        applyRoutedEditSlots(active, selected);
        applyV4Controls(active);

        const float* inputs[2] = {context.inputs ? context.inputs[0] : nullptr,
                                  context.inputs ? context.inputs[1] : nullptr};
        float* outputs[2] = {context.outputs ? context.outputs[0] : nullptr,
                             context.outputs ? context.outputs[1] : nullptr};
        backend_.process(inputs, outputs,
                         static_cast<std::size_t>(std::max(0, context.numFrames)));
    }

private:
    void refreshDynamicEditWorkspace(bool update_display) {
        if (syncing_edit_workspace_.exchange(true, std::memory_order_acq_rel)) {
            return;
        }
        const auto slot = static_cast<std::uint8_t>(std::clamp(getInt(Fx), 0, 49) + 1);
        auto bank = static_cast<std::size_t>(std::clamp(getInt(edit_bank_parameter_index_), 0, 255));
        const auto bank_count = dynamicEditBankCount(slot);
        if (bank >= bank_count) {
            bank = 0;
            set(edit_bank_parameter_index_, 0.0f);
        }
        if (getNormalised(edit_bank_available_index_) != (bank_count > 1 ? 1.0f : 0.0f))
            setNormalised(edit_bank_available_index_, bank_count > 1 ? 1.0f : 0.0f);
        for (std::size_t i = 0; i < kDynamicEditSlotCount; ++i) {
            const auto* control = dynamicEditControl(slot, bank * kDynamicEditSlotCount + i);
            const float available = control ? 1.0f : 0.0f;
            if (getNormalised(edit_slot_available_indices_[i]) != available)
                setNormalised(edit_slot_available_indices_[i], available);
            const float value = control ? getNormalised(control->parameter_index) : 0.0f;
            if (std::abs(getNormalised(edit_slot_parameter_indices_[i]) - value) > 1e-6f)
                setNormalised(edit_slot_parameter_indices_[i], value);
        }
        syncing_edit_workspace_.store(false, std::memory_order_release);
        if (update_display) requestDisplayUpdate();
    }

    void syncEditSlotFromControl(std::size_t ordinal,
        const trollfx::es5510::factory_editor_v04::Control& control) {
        if (syncing_edit_workspace_.exchange(true, std::memory_order_acq_rel)) return;
        setNormalised(edit_slot_parameter_indices_[ordinal], getNormalised(control.parameter_index));
        syncing_edit_workspace_.store(false, std::memory_order_release);
        requestDisplayUpdate();
    }

    void applyRoutedEditSlots(std::uint8_t active, std::uint8_t selected) noexcept {
        if (active == 0 || active != selected) return;
        for (std::size_t i = 0; i < kDynamicEditSlotCount; ++i) {
            if (!edit_slot_changed_[i].exchange(false, std::memory_order_acq_rel)) continue;
            const auto bank = static_cast<std::size_t>(std::clamp(getInt(edit_bank_parameter_index_), 0, 255));
            const auto* control = dynamicEditControl(active, bank * kDynamicEditSlotCount + i);
            if (!control || control->point_count == 0) continue;
            const float norm = getNormalised(edit_slot_parameter_indices_[i]);
            const auto point = static_cast<int>(std::lround(norm * static_cast<float>(control->point_count - 1)));
            applying_routed_edit_slot_.store(true, std::memory_order_release);
            set(control->parameter_index, static_cast<float>(std::clamp(point, 0,
                static_cast<int>(control->point_count - 1))));
            applying_routed_edit_slot_.store(false, std::memory_order_release);
        }
    }

    void applyVerifiedControls(std::uint8_t active) noexcept {
        for (std::size_t i = 0; i < std::size(kFactoryControls); ++i) {
            const auto& control = kFactoryControls[i];
            if (control.slot != active) continue;
            if (i >= kLegacyControlCount && !control_supported_[i - kLegacyControlCount]) continue;
            const int selected_point = choiceAt(*this, control.parameter_index);
            if (selected_point == applied_control_values_[i]) continue;
            if (i >= kLegacyControlCount && selected_point == 0) {
                applied_control_values_[i] = 0; // explicit no-write choice; not a factory default/reset
                continue;
            }
            const int catalog_point = i >= kLegacyControlCount ? selected_point - 1 : selected_point;
            const auto* definition = findParameter(provider_, active, control.id);
            if (!definition || catalog_point < 0 ||
                static_cast<std::size_t>(catalog_point) >= definition->verified_points.size()) continue;
            const auto display_value = definition->verified_points[static_cast<std::size_t>(catalog_point)].display_value;
            if (backend_.set_verified_parameter(active, control.id, display_value))
                applied_control_values_[i] = selected_point;
        }
    }

    void applyV4Controls(std::uint8_t active) noexcept {
        for (std::size_t i = 0; i < kV4ControlCount; ++i) {
            const auto& control = kV4Controls[i];
            if (control.slot != active || !v4_control_changed_[i].exchange(false, std::memory_order_acq_rel)) continue;
            const auto selected = static_cast<std::size_t>(std::max(0, choiceAt(*this, control.parameter_index)));
            if (selected >= control.point_count) continue;
            if (backend_.set_verified_parameter(active, control.id, control.values[selected])) continue;
            // Keep the change pending until the selected package is active and
            // the bounded runtime write is accepted.
            v4_control_changed_[i].store(true, std::memory_order_release);
        }
    }

    const IValidatedFactoryPackageProvider* provider_ = nullptr;
    ES5510DSPBackend backend_;
    std::uint8_t applied_slot_ = 0; // audio thread only
    std::array<int, sizeof(kFactoryControls) / sizeof(kFactoryControls[0])> applied_control_values_{};
    std::array<bool, kV2ControlCount> control_supported_{};
    std::array<std::atomic<bool>, kV4ControlCount> v4_control_changed_{};
    std::array<int, kDynamicEditSlotCount> edit_slot_parameter_indices_{};
    std::array<int, kDynamicEditSlotCount> edit_slot_available_indices_{};
    int edit_bank_parameter_index_ = -1;
    int edit_bank_available_index_ = -1;
    std::array<std::atomic<bool>, kDynamicEditSlotCount> edit_slot_changed_{};
    std::atomic<bool> syncing_edit_workspace_{false};
    std::atomic<bool> applying_routed_edit_slot_{false};
};

#ifndef TROLLFX_FORCE_PLUGIN_TEST
MPC_PLUGIN_ENTRY(ASR10FXCollection)
#endif
