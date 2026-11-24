// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 TROLLfx contributors
#include "mpc_plugin.h"
#include "ES5510DSPBackend.h"
#include "trollfx/es5510_factory_parameter_control_v01.hpp"

#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>

namespace {
constexpr const char* kEffectNames[] = {
    "01 HALL REVERB", "02 44KHZ REVERB", "03 ROOM REVERB", "04 DUAL DELAYS",
    "05 44KHZ DELAYS", "06 CHORUS+REVRB", "07 PHASER+REVRB", "08 FLANGER+REV",
    "09 ROT.SPKR+REV", "10 CHOR+REV+DDL", "11 CMP+DIST+REV", "12 DIST+CHO+REV",
    "13 WAH+DIST+REV", "14 SMALL ROOM", "15 LARGE ROOM", "16 HALL REVERB2",
    "17 SMALL PLATE", "18 LARGE PLATE", "19 REVRSE REVRB", "20 REVRSE REVB2",
    "21 GATED REVERB", "22 NLIN REVRB 1", "23 NLIN REVRB 2", "24 NLIN REVRB 3",
    "25 MULTITAP DDL", "26 EQ+DELAY LFO", "27 VCF+DISTORT", "28 GUITAR AMP1",
    "29 GUITAR AMP2", "30 GUITAR AMP3", "31 SPKR CABINET", "32 TUNABLE SPKR",
    "33 EQ+CHOR+DDL", "34 EQ+VIBR+DDL", "35 EQ+FLNGR+DDL", "36 EQ+TREM+DDL",
    "37 PHASER+DDL", "38 8-VOICE CHOR", "39 PITCH SHIFT", "40 PITCH+DDL",
    "41 FAST PITCHSH", "42 EQ+CMPRESSOR", "43 EXPANDER", "44 KEYED EXPNDR",
    "45 INVRS EXPNDR", "46 DE-ESSER", "47 DUCKER", "48 RUMBLE FILTR",
    "49 PARAM EQ", "50 VAN DER POL"
};

std::vector<std::string> effectChoices(const IValidatedFactoryPackageProvider* provider) {
    std::vector<std::string> choices;
    choices.reserve(50);
    for (std::uint8_t slot = 1; slot <= 50; ++slot) {
        const bool available = provider && provider->package_for_slot(slot);
        choices.emplace_back(std::string(kEffectNames[slot - 1]) +
                             (available ? "  [READY]" : "  [UNAVAILABLE]"));
    }
    return choices;
}

std::vector<std::string> numericChoices(int first, int second) {
    return {std::to_string(first) + " BUS", std::to_string(second) + " BUS"};
}

int choiceAt(const mpc::Plugin& plugin, int index) noexcept {
    return plugin.getInt(index);
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
        : mpc::Plugin(makeInfo()), provider_(TROLLfx_GetValidatedFactoryPackageProvider()),
          backend_(provider_) {
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
        addParam(choiceParam("hall_bus1", "HALL BUS1", numericChoices(28, 29), 0));
        addParam(choiceParam("hall_bus2", "HALL BUS2", numericChoices(28, 29), 0));
        addParam(choiceParam("rom02_bus1", "ROM02 BUS1", numericChoices(25, 26), 0));
        addParam(choiceParam("rom02_bus2", "ROM02 BUS2", numericChoices(25, 26), 0));
    }

    void prepare(double rate, int) override {
        const auto selected = static_cast<std::uint8_t>(std::clamp(getInt(Fx), 0, 49) + 1);
        const bool loaded = backend_.prepare(selected, rate);
        updateStatus(loaded);
        applied_slot_ = 0;
    }

    void reset() override { applied_slot_ = 0; }

    bool formatValue(int index, float plain, std::string& out) override {
        if (index != Fx) return false;
        const int slot_index = std::clamp(static_cast<int>(plain), 0, 49);
        const auto slot = static_cast<std::uint8_t>(slot_index + 1);
        const auto* package = provider_ ? provider_->package_for_slot(slot) : nullptr;
        const auto status = backend_.status();
        const char* state = "UNAVAILABLE";
        if (!provider_) state = "PACKAGE REQUIRED";
        else if (!package) state = "UNAVAILABLE";
        else if (status == ES5510BackendStatus::Loading) state = "LOADING";
        else if (status == ES5510BackendStatus::Failed) state = "LOAD FAILED";
        else if (backend_.active_slot() == slot && status == ES5510BackendStatus::Ready)
            state = "READY";
        else state = "SELECTED";
        out = std::string(kEffectNames[slot_index]) + " / " + state;
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
            applied_bus1_ = applied_bus2_ = -1;
        }
        if (active == 1) {
            applyBus(active, 1, HallBus1, applied_bus1_);
            applyBus(active, 2, HallBus2, applied_bus2_);
        } else if (active == 2) {
            applyBus(active, 1, Rom02Bus1, applied_bus1_);
            applyBus(active, 2, Rom02Bus2, applied_bus2_);
        }

        const float* inputs[2] = {context.inputs ? context.inputs[0] : nullptr,
                                  context.inputs ? context.inputs[1] : nullptr};
        float* outputs[2] = {context.outputs ? context.outputs[0] : nullptr,
                             context.outputs ? context.outputs[1] : nullptr};
        backend_.process(inputs, outputs,
                         static_cast<std::size_t>(std::max(0, context.numFrames)));
        reflectStatus();
    }

private:
    void applyBus(std::uint8_t effect_slot, int bus, int parameter_index,
                  int& previously_applied) noexcept {
        const int value = choiceAt(*this, parameter_index);
        if (value == previously_applied) return;
        using namespace trollfx::es5510::factory_parameters_v01;
        const auto effect = effect_slot == 1 ? FactoryEffect::Rom01Hall
                                              : FactoryEffect::Rom02Reverb44k;
        const auto parameter = bus == 1 ? Parameter::ReverbMixBus1
                                         : Parameter::ReverbMixBus2;
        const int display_value = value == 0
            ? (effect_slot == 1 ? 28 : 25)
            : (effect_slot == 1 ? 29 : 26);
        const auto result = backend_.set_verified_bus(effect, parameter, display_value);
        if (result == EncodeStatus::Encoded) previously_applied = value;
    }

    void updateStatus(bool loaded) noexcept {
        if (!provider_) set(Status, 0.0f);
        else if (loaded) set(Status, 2.0f);
        else if (backend_.status() == ES5510BackendStatus::Unavailable) set(Status, 1.0f);
        else if (backend_.status() == ES5510BackendStatus::Loading) set(Status, 4.0f);
        else if (backend_.status() == ES5510BackendStatus::Failed) set(Status, 3.0f);
        else set(Status, 1.0f);
    }

    void reflectStatus() noexcept {
        switch (backend_.status()) {
            case ES5510BackendStatus::NoProvider: set(Status, 0.0f); break;
            case ES5510BackendStatus::Unavailable: set(Status, 1.0f); break;
            case ES5510BackendStatus::Loading: set(Status, 4.0f); break;
            case ES5510BackendStatus::Ready: set(Status, 2.0f); break;
            case ES5510BackendStatus::Failed: set(Status, 3.0f); break;
        }
    }

    const IValidatedFactoryPackageProvider* provider_ = nullptr;
    ES5510DSPBackend backend_;
    std::uint8_t applied_slot_ = 0; // audio thread only
    int applied_bus1_ = -1, applied_bus2_ = -1;
};

#ifndef TROLLFX_FORCE_PLUGIN_TEST
MPC_PLUGIN_ENTRY(ASR10FXCollection)
#endif
