// Additional OS 3.53 controls recovered after the V2 parameter catalog.
// The points are display-driven, reversible host-write observations. Only the
// listed values are accepted; no interpolation is implied.
#pragma once

#include "trollfx/es5510_factory_registry.hpp"

#include <algorithm>
#include <initializer_list>
#include <string>
#include <utility>
#include <vector>

namespace trollfx::es5510::parameter_discovery_v03 {

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
    p.evidence = "OS 3.53 exact 22-character LCD and repeated reversible host GPR observations; discrete verified points only";
    p.verified_points.assign(points.begin(), points.end());
    return p;
}

inline bool append_verified_parameters(EffectDescriptor& d) {
    std::vector<VerifiedParameterDefinition> recovered;
    switch (d.slot) {
    case 5:
        recovered = {parameter("delay_time_l", "BS1 TIME L", "display steps", "integer",
            {point(350, "350", {{0x0b,0x3c2900}}), point(351, "351", {{0x0b,0x3c5500}})})};
        break;
    case 8:
        recovered = {parameter("flange_rate", "FLANGE RATE", "display steps", "integer",
            {point(20, "20", {{0x84,0x0003d7},{0x85,0x0003d7}}),
             point(21, "21", {{0x84,0x00049c},{0x85,0x00049c}})})};
        break;
    case 39:
        recovered = {parameter("quality", "QUALITY", "mode", "text",
            {point(0, "LONG/SMOOTHER", {{0x04,0x0667de},{0x07,0x0667de},{0x0a,0x002f1f},
                                         {0x61,0x044446},{0x64,0x044446},{0xa0,0x7fffee}}),
             point(1, "SHORT/COARSER", {{0x04,0x03cfe1},{0x07,0x03cfe1},{0x0a,0x004f40},
                                         {0x61,0x028978},{0x64,0x028978},{0xa0,0x7fffcf}})})};
        break;
    default:
        return false;
    }

    for (auto& p : recovered) {
        if (d.slot == 5) p.display_order = 3;
        else if (d.slot == 8) p.display_order = 4;
        else if (d.slot == 39) p.display_order = 9;
        const auto found = std::find_if(d.parameters.begin(), d.parameters.end(),
            [&](const auto& existing) { return existing.id == p.id; });
        if (found == d.parameters.end()) d.parameters.push_back(std::move(p));
    }
    return true;
}

} // namespace trollfx::es5510::parameter_discovery_v03
