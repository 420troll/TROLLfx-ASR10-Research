// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 TROLLfx contributors
#include "mpc_plugin.h"
#include "ES5510DSPBackend.h"
#include "ES5510FactoryPackageProvider.h"
#include "trollfx/es5510_factory_parameter_control_v01.hpp"
#include "trollfx/es5510_factory_parameter_discovery_v02.hpp"
#include "trollfx/es5510_factory_editor_v03.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
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
    }

    void prepare(double rate, int) override {
        const auto selected = static_cast<std::uint8_t>(std::clamp(getInt(Fx), 0, 49) + 1);
        backend_.prepare(selected, rate);
        applied_slot_ = 0;
    }

    void reset() override { applied_slot_ = 0; }

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

        const float* inputs[2] = {context.inputs ? context.inputs[0] : nullptr,
                                  context.inputs ? context.inputs[1] : nullptr};
        float* outputs[2] = {context.outputs ? context.outputs[0] : nullptr,
                             context.outputs ? context.outputs[1] : nullptr};
        backend_.process(inputs, outputs,
                         static_cast<std::size_t>(std::max(0, context.numFrames)));
    }

private:
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

    const IValidatedFactoryPackageProvider* provider_ = nullptr;
    ES5510DSPBackend backend_;
    std::uint8_t applied_slot_ = 0; // audio thread only
    std::array<int, sizeof(kFactoryControls) / sizeof(kFactoryControls[0])> applied_control_values_{};
    std::array<bool, kV2ControlCount> control_supported_{};
};

#ifndef TROLLFX_FORCE_PLUGIN_TEST
MPC_PLUGIN_ENTRY(ASR10FXCollection)
#endif
