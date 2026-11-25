#include "trollfx/es5510_factory_parameter_discovery_v03.hpp"

#include <cassert>
#include <cstdint>

using namespace trollfx::es5510;

static EffectDescriptor descriptor(std::uint32_t slot) {
    EffectDescriptor d;
    d.slot = static_cast<EffectSlot>(slot);
    return d;
}

int main() {
    auto delay = descriptor(5);
    assert(parameter_discovery_v03::append_verified_parameters(delay));
    assert(delay.parameters.size() == 1 && delay.parameters[0].id == "delay_time_l");
    assert(delay.parameters[0].verified_points[0].gpr == 0x0b);
    assert(delay.parameters[0].verified_points[1].value24 == 0x3c5500);

    auto flange = descriptor(8);
    assert(parameter_discovery_v03::append_verified_parameters(flange));
    assert(flange.parameters[0].verified_points[1].ordered_writes.size() == 2);
    assert(flange.parameters[0].verified_points[1].ordered_writes[0].gpr == 0x84);
    assert(flange.parameters[0].verified_points[1].ordered_writes[1].gpr == 0x85);

    auto pitch = descriptor(39);
    assert(parameter_discovery_v03::append_verified_parameters(pitch));
    assert(pitch.parameters[0].verified_points[0].display_text == "LONG/SMOOTHER");
    assert(pitch.parameters[0].verified_points[1].ordered_writes.size() == 6);

    auto unknown = descriptor(2);
    assert(!parameter_discovery_v03::append_verified_parameters(unknown));
}
