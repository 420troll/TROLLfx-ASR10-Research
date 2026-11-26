// Additional evidence-bounded ASR-10 controls recovered by the OS 3.53
// display-driven probe. Populate descriptors on the control thread before
// registration; FactoryRuntime::setParameter schedules verified write groups.
#pragma once

#include "trollfx/es5510_factory_registry.hpp"

#include <initializer_list>
#include <string>
#include <utility>
#include <vector>

namespace trollfx::es5510::parameter_discovery_v02 {

using Writes = std::initializer_list<ParameterPoint::RegisterWrite>;

inline ParameterPoint point(std::int32_t value, const char* text, Writes writes) {
    ParameterPoint p;
    p.display_value = value;
    p.display_text = text;
    if (writes.size() == 1) {
        p.gpr = writes.begin()->gpr;
        p.value24 = writes.begin()->value24;
    } else {
        p.ordered_writes.assign(writes.begin(), writes.end());
    }
    return p;
}

inline VerifiedParameterDefinition parameter(const char* id, const char* label,
                                              const char* units, const char* format,
                                              std::initializer_list<ParameterPoint> points) {
    VerifiedParameterDefinition p;
    p.id = id;
    p.ui_label = label;
    p.units = units;
    p.display_format = format;
    p.evidence = "OS 3.53 live display and host GPR trace; two adjacent values, repeated Up/reverse trials";
    p.verified_points.assign(points.begin(), points.end());
    return p;
}

inline bool append_verified_parameters(EffectDescriptor& d) {
    std::vector<VerifiedParameterDefinition> recovered;
    switch (d.slot) {
    case 1:
        recovered = {
            parameter("reverb_mix_bus1", "REVERB MIX BUS1", "display steps", "integer",
                {point(28,"28",{{0x7c,0x3d0000}}), point(29,"29",{{0x7c,0x3f0000}})}),
            parameter("reverb_mix_bus2", "REVERB MIX BUS2", "display steps", "integer",
                {point(28,"28",{{0x7a,0x3d0000}}), point(29,"29",{{0x7a,0x3f0000}})}),
            parameter("decay_time", "DECAY TIME", "display steps", "integer",
                {point(40,"40",{{0x6e,0x340000},{0x5b,0x080034},{0x03,0x340000},{0x04,0xcc0000},{0x05,0x6adfff}}),
                 point(41,"41",{{0x6e,0x350000},{0x5b,0x080035},{0x03,0x350000},{0x04,0xcb0000},{0x05,0x6a0dff}})}),
            parameter("hi_freq_damping", "HI FREQ DAMPING", "display steps", "integer",
                {point(31,"31",{{0x6c,0x57ffff},{0x6d,0x280000}}),
                 point(32,"32",{{0x6c,0x56ffff},{0x6d,0x290000}})})
        };
        break;
    case 2:
        recovered = {
            parameter("reverb_mix_bus1", "REVERB MIX BUS1", "display steps", "integer",
                {point(25,"25",{{0x7c,0x350000}}), point(26,"26",{{0x7c,0x370000}})}),
            parameter("reverb_mix_bus2", "REVERB MIX BUS2", "display steps", "integer",
                {point(25,"25",{{0x7a,0x350000}}), point(26,"26",{{0x7a,0x370000}})})
        };
        break;
    case 3:
        recovered = {
            parameter("decay_time", "DECAY TIME", "display steps", "integer",
                {point(64,"64",{{0x6e,0x520000}}), point(65,"65",{{0x6e,0x530000}})}),
            parameter("diffusion", "DIFFUSION", "display steps", "integer",
                {point(50,"50",{{0x07,0x400000},{0x09,0xc00000},{0x0a,0x5fffff},{0x0b,0x330000},{0x0c,0xcd0000},{0x12,0x6badff}}),
                 point(51,"51",{{0x07,0x410000},{0x09,0xbf0000},{0x0a,0x5efdff},{0x0b,0x33cc00},{0x0c,0xcc3400},{0x12,0x6b0a2a}})}),
            parameter("hi_freq_damping", "HI FREQ DAMPING", "display steps", "integer",
                {point(9,"9",{{0x6c,0x73ffff},{0x6d,0x0c0000}}),
                 point(10,"10",{{0x6c,0x72ffff},{0x6d,0x0d0000}})})
        };
        break;
    case 4:
        recovered = {parameter("delay_time_l", "BS1 TIME L", "display steps", "integer",
            {point(350,"350",{{0x0b,0x290500}}), point(351,"351",{{0x0b,0x292300}})})};
        break;
    case 6:
        recovered = {parameter("chorus_rate", "CHORUS RATE", "display steps", "integer",
            {point(24,"24",{{0x90,0x0007f7},{0x91,0x000c91},{0x92,0x000b11}}),
             point(25,"25",{{0x90,0x000836},{0x91,0x000cf5},{0x92,0x000b69}})})};
        break;
    case 7:
        recovered = {parameter("phase_rate", "PHASE RATE", "display steps", "integer",
            {point(20,"20",{{0x8e,0x0003d7}}), point(21,"21",{{0x8e,0x00049c}})})};
        break;
    case 28:
        recovered = {parameter("preamp_gain", "PREAMP GAIN", "dB display", "signed integer",
            {point(12,"+12",{{0x70,0x020100}}), point(13,"+13",{{0x70,0x023f00}})})};
        break;
    case 41:
        recovered = {parameter("voice1_fine", "VOICE1 FINE", "display steps", "signed integer",
            {point(-11,"-11",{{0x60,0xff36ea}}), point(-10,"-10",{{0x60,0xff4547}})})};
        break;
    case 42:
        recovered = {parameter("comp_ratio", "COMP RATIO", "ratio", "N/1",
            {point(4,"4/1",{{0x8b,0x1fffff}}), point(5,"5/1",{{0x8b,0x199999}})})};
        break;
    case 49:
        recovered = {parameter("bass_fc", "BASS FC", "Hz display", "integer",
            {point(100,"100",{{0x57,0x7d5e06},{0x58,0x82a1fa}}),
             point(101,"101",{{0x57,0x7d574a},{0x58,0x82a8b6}})})};
        break;
    default:
        return false;
    }
    for (auto& p : recovered) {
        if (d.slot == 1) {
            if (p.id == "reverb_mix_bus1") p.display_order = 1;
            else if (p.id == "reverb_mix_bus2") p.display_order = 2;
            else if (p.id == "decay_time") p.display_order = 4;
            else if (p.id == "hi_freq_damping") p.display_order = 7;
        } else if (d.slot == 2) {
            if (p.id == "reverb_mix_bus1") p.display_order = 1;
            else if (p.id == "reverb_mix_bus2") p.display_order = 2;
        } else if (d.slot == 3) {
            if (p.id == "decay_time") p.display_order = 4;
            else if (p.id == "diffusion") p.display_order = 6;
            else if (p.id == "hi_freq_damping") p.display_order = 7;
        } else if (d.slot == 4) p.display_order = 3;
        else if (d.slot == 6) p.display_order = 11;
        else if (d.slot == 7) p.display_order = 12;
        else if (d.slot == 28 || d.slot == 41) p.display_order = 3;
        else if (d.slot == 42) p.display_order = 2;
        else if (d.slot == 49) p.display_order = 1;
        const auto found = std::find_if(d.parameters.begin(), d.parameters.end(),
            [&](const auto& existing) { return existing.id == p.id; });
        if (found == d.parameters.end()) d.parameters.push_back(std::move(p));
    }
    return true;
}

} // namespace trollfx::es5510::parameter_discovery_v02
