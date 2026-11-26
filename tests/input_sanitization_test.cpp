#include "input_level.h"

#include <cassert>
#include <cmath>
#include <limits>

int main() {
    const float nan = std::numeric_limits<float>::quiet_NaN();
    const float inf = std::numeric_limits<float>::infinity();
    assert(finite_audio_sample_or_zero(nan) == 0.0f);
    assert(finite_audio_sample_or_zero(inf) == 0.0f);
    assert(finite_audio_sample_or_zero(-inf) == 0.0f);
    assert(finite_audio_sample_or_zero(0.25f) == 0.25f);

    const double old_volume = 0.73;
    assert(finite_clamp(nan, 0.0, 1.0, old_volume) == old_volume);
    assert(finite_clamp(inf, 0.0, 1.0, old_volume) == old_volume);
    assert(finite_clamp(-inf, 0.0, 1.0, old_volume) == old_volume);
    assert(finite_clamp(-0.2, 0.0, 1.0, old_volume) == 0.0);
    assert(finite_clamp(1.2, 0.0, 1.0, old_volume) == 1.0);
    assert(std::isfinite(input_level_gain(nan)));
}
