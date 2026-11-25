// V5 OS 3.53 factory-editor mappings. These are exact, reversible adjacent
// display points observed through the factory editor. No curve is implied.
#pragma once

#include "trollfx/es5510_factory_registry.hpp"

#include <algorithm>
#include <initializer_list>
#include <string>
#include <utility>
#include <vector>

namespace trollfx::es5510::parameter_discovery_v05 {

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
                                              std::uint32_t order,
                                              std::initializer_list<ParameterPoint> points) {
    VerifiedParameterDefinition p;
    p.id = id;
    p.ui_label = label;
    p.units = units;
    p.display_format = format;
    p.display_order = order;
    p.evidence = "OS 3.53 exact LCD, two repeated reversible edits, and ordered host GPR writes; exact points only";
    p.verified_points.assign(points.begin(), points.end());
    return p;
}

inline bool append_verified_parameters(EffectDescriptor& d) {
    std::vector<VerifiedParameterDefinition> recovered;
    switch (d.slot) {
    case 1:
        recovered = {
            parameter("low_freq_decay", "LOW FREQ DECAY", "display steps", "signed_integer", 5,
                {point(6, "+6", {{0x5b,0x080034}}), point(7, "+7", {{0x5b,0x090034}})}),
            parameter("diffusion", "DIFFUSION", "display steps", "integer", 6,
                {point(78, "78", {{0x07,0x640000},{0x09,0x9c0000},{0x0a,0x31dfff},{0x0b,0x4fb000},{0x0c,0xb05000},{0x14,0x4e63cd}}),
                 point(79, "79", {{0x07,0x650000},{0x09,0x9b0000},{0x0a,0x304dff},{0x0b,0x507c00},{0x0c,0xaf8400},{0x14,0x4d6487}})}),
            parameter("detune_rate", "DETUNE RATE", "display steps", "integer", 9,
                {point(26, "26", {{0x6a,0x000873}}), point(27, "27", {{0x6a,0x000937}})}),
            parameter("detune_amount", "DETUNE AMT", "display steps", "integer", 10,
                {point(9, "9", {{0x68,0x000600}}), point(10, "10", {{0x68,0x000680}})}),
            parameter("pre_delay_time", "PRE-DELAY TIME", "ms", "integer", 11,
                {point(30, "30", {{0x01,0x4dec00},{0x08,0x888600}}),
                 point(31, "31", {{0x01,0x4e0a00},{0x08,0x88a400}})})
        };
        break;
    case 3:
        recovered = {
            parameter("low_freq_decay", "LOW FREQ DECAY", "display steps", "signed_integer", 5,
                {point(6, "+6", {{0x5b,0x080000}}), point(7, "+7", {{0x5b,0x090000}})}),
            parameter("hi_freq_bandwidth", "HI FREQ BANDWIDTH", "display steps", "integer", 8,
                {point(84, "84", {{0x02,0x6c0000},{0x00,0x13ffff}}),
                 point(85, "85", {{0x02,0x6d0000},{0x00,0x12ffff}})}),
            parameter("detune_rate", "DETUNE RATE", "display steps", "integer", 9,
                {point(26, "26", {{0x6a,0x000873}}), point(27, "27", {{0x6a,0x000937}})}),
            parameter("detune_amount", "DETUNE AMT", "display steps", "integer", 10,
                {point(8, "8", {{0x68,0x000580}}), point(9, "9", {{0x68,0x000600}})}),
            parameter("pre_delay_time", "PRE-DELAY TIME", "ms", "integer", 11,
                {point(1, "1", {{0x01,0x164300},{0x08,0x50dd00}}),
                 point(2, "2", {{0x01,0x166100},{0x08,0x50fb00}})})
        };
        break;
    case 4:
        recovered = {
            parameter("dual_bs1_time_r", "BS1 TIME R", "ms", "integer", 3,
                {point(700, "700", {{0x0c,0x520900}}), point(701, "701", {{0x0c,0x522700}})}),
            parameter("dual_bus2_feedback", "BUS2 FEEDBACK", "display steps", "integer", 6,
                {point(25, "25", {{0x07,0xdfdfe0}}), point(26, "26", {{0x07,0xdededf}})}),
            parameter("dual_bs2_time_l", "BS2 TIME L", "ms", "integer", 7,
                {point(50, "50", {{0x0f,0xf03e00}}), point(51, "51", {{0x0f,0xf05c00}})})
        };
        break;
    case 6:
        recovered = {
            parameter("reverb_decay_time", "REVERB DECAY TIME", "display steps", "integer", 3,
                {point(24, "24", {{0x6e,0x1f0000},{0x6c,0x07001f},{0x71,0x1f0000},{0x72,0xe10000},{0x73,0x787dff}}),
                 point(25, "25", {{0x6e,0x200000},{0x6c,0x070020},{0x71,0x200000},{0x72,0xe00000},{0x73,0x77ffff}})}),
            parameter("diffusion", "DIFFUSION", "display steps", "integer", 5,
                {point(50, "50", {{0x5a,0x400000},{0x5b,0xc00000},{0x5c,0x5fffff}}),
                 point(51, "51", {{0x5a,0x410000},{0x5b,0xbf0000},{0x5c,0x5efdff}})}),
            parameter("bus1_rev_after_chor", "BUS1 REV AFTER CHOR", "display steps", "integer", 1,
                {point(25, "25", {{0x7c,0x350000}}), point(26, "26", {{0x7c,0x370000}})}),
            parameter("chorus_feedback", "CHORUS FEEDBACK", "display steps", "signed_integer", 14,
                {point(9, "+9", {{0x86,0x0c0000}}), point(10, "+10", {{0x86,0x0d0000}})}),
            parameter("chorus_rate_amount", "CHORUS RATE AMT", "display steps", "integer", 12,
                {point(39, "39", {{0x8d,0x001900}}), point(40, "40", {{0x8d,0x001980}})})
        };
        break;
    case 8:
        recovered = {
            parameter("flange_center", "FLANGE CENTER", "display steps", "integer", 11,
                {point(19, "19", {{0x68,0x006400},{0x67,0x006400},{0x64,0x085500},{0x63,0x085500}}),
                 point(20, "20", {{0x68,0x006800},{0x67,0x006800},{0x64,0x085900},{0x63,0x085900}})}),
            parameter("flange_width", "FLANGE WIDTH", "display steps", "integer", 13,
                {point(19, "19", {{0x8d,0x003232},{0x8e,0x003232}}), point(20, "20", {{0x8d,0x003434},{0x8e,0x003434}})}),
            parameter("flange_depth", "FLANGE DEPTH", "display steps", "integer", 15,
                {point(98, "98", {{0x88,0x7e7e7e}}), point(99, "99", {{0x88,0x7f7f7f}})})
        };
        break;
    case 38:
        recovered = {
            parameter("lfo_rate", "LFO RATE", "display steps", "integer", 3,
                {point(5, "5", {{0x90,0x00033c},{0x91,0x00051a},{0x92,0x000366},{0x93,0x0003ce},{0x94,0x0004a5},{0x95,0x0004c3},{0x96,0x000555},{0x97,0x000423}}),
                 point(6, "6", {{0x90,0x00037c},{0x91,0x00057f},{0x92,0x0003a9},{0x93,0x000419},{0x94,0x000500},{0x95,0x000520},{0x96,0x0005be},{0x97,0x000475}})}),
            parameter("lfo_width", "LFO RATE WIDTH", "display steps", "integer", 3,
                {point(80, "80", {{0x8d,0x006700}}), point(81, "81", {{0x8d,0x006800}})}),
            parameter("chorus_regen", "CHORUS REGEN", "display steps", "integer", 6,
                {point(13, "13", {{0x8a,0xeeeeef}}), point(14, "14", {{0x8a,0xededee}})}),
            parameter("l_regen_time", "L REGEN TIME", "ms", "integer", 7,
                {point(300, "300", {{0x45,0x233000}}), point(301, "301", {{0x45,0x234e00}})}),
            parameter("r_regen_time", "R REGEN TIME", "ms", "integer", 8,
                {point(300, "300", {{0x43,0xa32900}}), point(301, "301", {{0x43,0xa34700}})}),
            parameter("delay_regen", "DELAY REGEN", "display steps", "integer", 9,
                {point(47, "47", {{0x89,0xc2c2c3}}), point(48, "48", {{0x89,0xc1c1c2}})})
        };
        break;
    case 39:
        recovered = {
            parameter("lfo_rate", "LFO RATE", "display steps", "integer", 12,
                {point(30, "30", {{0x90,0x00012f}}), point(31, "31", {{0x90,0x000145}})}),
            parameter("vc1_semitone", "VC1 SEMI", "semitones", "signed_integer", 3,
                {point(0, "+0", {{0x60,0xff9b75}}), point(1, "+1", {{0x60,0x072f94}})}),
            parameter("vc1_fine", "VC1 FINE", "display steps", "signed_integer", 3,
                {point(-5, "-5", {{0x60,0xff9b75}}), point(-4, "-4", {{0x60,0xffa9d2}})})
        };
        break;
    default:
        return false;
    }

    for (auto& p : recovered) {
        const auto found = std::find_if(d.parameters.begin(), d.parameters.end(),
            [&](const auto& existing) { return existing.id == p.id; });
        if (found == d.parameters.end()) d.parameters.push_back(std::move(p));
    }
    return true;
}

} // namespace trollfx::es5510::parameter_discovery_v05
