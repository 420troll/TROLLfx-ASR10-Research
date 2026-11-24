#include "dac_out.h"
#include <cassert>
#include <cmath>
#include <vector>

int main() {
    DacOut traced, plain;
    std::vector<float> main_a, aux_a, main_b, aux_b;
    std::vector<double> positions;
    float x[8] = {0.1f, -0.1f};
    for (int i = 0; i < 4096; ++i) {
        x[0] = std::sin(i * 0.017f) * 0.4f;
        x[1] = std::cos(i * 0.013f) * 0.3f;
        traced.push(x, false, 29761.89453125, 44100.0, main_a, aux_a, &positions);
        plain.push(x, false, 29761.89453125, 44100.0, main_b, aux_b);
    }
    assert(main_a == main_b);
    assert(aux_a == aux_b);
    assert(positions.size() == main_a.size() / 2);
    for (size_t i = 1; i < positions.size(); ++i) assert(positions[i] > positions[i-1]);
    assert(!positions.empty() && positions.front() == 0.0);
}
