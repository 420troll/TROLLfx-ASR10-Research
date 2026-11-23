#include "es5510.h"

#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

namespace {
std::uint32_t le32(const std::vector<std::uint8_t>& b, std::size_t p) {
    return std::uint32_t(b[p]) | (std::uint32_t(b[p + 1]) << 8) |
           (std::uint32_t(b[p + 2]) << 16) | (std::uint32_t(b[p + 3]) << 24);
}
}

int main() {
    ES5510 esp;
    const std::uint8_t instruction[6] = {0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc};
    for (int i = 0; i < 6; ++i) esp.host_w(0x03 + i, instruction[i]);
    esp.host_w(0xc0, 0x00);

    esp.host_w(0x00, 0xab); esp.host_w(0x01, 0xcd); esp.host_w(0x02, 0xef);
    esp.host_w(0xa0, 0x00);

    esp.host_w(0x00, 0x00); esp.host_w(0x01, 0x00); esp.host_w(0x02, 0xff);
    esp.host_w(0xa0, 0xf4); // MEMSIZ write: eight low one bits -> shift 8.
    esp.host_w(0x00, 0x00); esp.host_w(0x01, 0xff); esp.host_w(0x02, 0xff);
    esp.host_w(0xa0, 0xf5); // DLENGTH
    esp.host_w(0x00, 0x00); esp.host_w(0x01, 0x00); esp.host_w(0x02, 0x00);
    esp.host_w(0x14, 0x40); // external DRAM selected
    esp.host_w(0x0c, 0x12); esp.host_w(0x0d, 0x34); esp.host_w(0x0e, 0xff);
    esp.host_w(0x10, 0); esp.host_w(0x11, 0); esp.host_w(0x0f, 0);

    FILE *f = tmpfile();
    assert(f);
    assert(esp.write_capture(f));
    assert(fseek(f, 0, SEEK_END) == 0);
    const long size = ftell(f);
    const long expected = 44 + 160 * 6 + 192 * 3 + 22 * 3 + 74 + ES5510::DRAM_SIZE * 2;
    assert(size == expected);
    assert(fseek(f, 0, SEEK_SET) == 0);
    std::vector<std::uint8_t> b(static_cast<std::size_t>(size));
    assert(fread(b.data(), 1, b.size(), f) == b.size());
    fclose(f);

    const std::uint8_t magic[8] = {'E','S','5','5','1','0','C',0};
    for (int i = 0; i < 8; ++i) assert(b[i] == magic[i]);
    assert(le32(b, 8) == 1 && le32(b, 12) == 44);
    assert(le32(b, 16) == 160 && le32(b, 20) == 192 && le32(b, 24) == 22);
    assert(le32(b, 28) == ES5510::DRAM_SIZE && le32(b, 36) == 74);
    for (int i = 0; i < 6; ++i) assert(b[44 + i] == instruction[i]);
    const std::size_t gpr0 = 44 + 160 * 6;
    assert(b[gpr0] == 0xab && b[gpr0 + 1] == 0xcd && b[gpr0 + 2] == 0xef);
    const std::size_t state = 44 + 160 * 6 + 192 * 3 + 22 * 3;
    assert(le32(b, state + 7) == 0x0000ffu);   // MEMSIZ-derived size
    assert(le32(b, state + 11) == 0xffff00u);  // address mask
    assert(le32(b, state + 15) == 0x00000100u); // address increment
    const std::size_t dram = state + 74;
    assert(b[dram] == 0x34 && b[dram + 1] == 0x12);
    assert(b[dram + 2] == 0 && b[dram + 3] == 0);
    std::puts("ES5510 capture format: PASS");
    return 0;
}
