#include "es5510.h"

#include <cassert>
#include <cstdint>
#include <cstdio>

namespace {
std::uint32_t readReg(ES5510& esp, std::uint8_t reg) {
    esp.host_w(0x80, reg);
    return (std::uint32_t(esp.host_r(0)) << 16) |
           (std::uint32_t(esp.host_r(1)) << 8) | esp.host_r(2);
}

std::uint32_t capturedSpr(ES5510& esp, std::uint8_t reg) {
    FILE *f = std::tmpfile();
    assert(f && esp.write_capture(f));
    const long offset = 44 + 160 * 6 + 192 * 3 + (reg - 234) * 3;
    assert(std::fseek(f, offset, SEEK_SET) == 0);
    const int a = std::fgetc(f), b = std::fgetc(f), c = std::fgetc(f);
    std::fclose(f);
    assert(a >= 0 && b >= 0 && c >= 0);
    return (std::uint32_t(a) << 16) | (std::uint32_t(b) << 8) | std::uint32_t(c);
}

void writeReg(ES5510& esp, std::uint8_t reg, std::uint32_t value) {
    esp.host_w(0x00, static_cast<std::uint8_t>(value >> 16));
    esp.host_w(0x01, static_cast<std::uint8_t>(value >> 8));
    esp.host_w(0x02, static_cast<std::uint8_t>(value));
    esp.host_w(0xa0, reg);
}

void writeInstruction(ES5510& esp, std::uint8_t address, std::uint64_t word) {
    for (unsigned byte = 0; byte < 6; ++byte)
        esp.host_w(0x03 + byte, static_cast<std::uint8_t>(word >> (40 - byte * 8)));
    esp.host_w(0xc0, address);
}

std::uint64_t instruction(std::uint8_t a, std::uint8_t b, std::uint8_t c,
                          std::uint8_t d, std::uint8_t op) {
    return (std::uint64_t(d) << 40) | (std::uint64_t(c) << 32) |
           (std::uint64_t(b) << 24) | (std::uint64_t(a) << 16) |
           (std::uint64_t(op) << 12);
}

}

int main() {
    // Serial input delivery and host/DSP aliases are left-justified in the SPR view.
    {
        ES5510 esp;
        esp.ser_w(4, static_cast<std::int16_t>(0xe90d)); // SER2L lane
        esp.ser_w(5, static_cast<std::int16_t>(0xe90d)); // SER2R lane
        assert(readReg(esp, 0xef) == 0xe90d00);
        assert(readReg(esp, 0xee) == 0xe90d00);
        writeReg(esp, 0xef, 0x123456);
        assert(readReg(esp, 0xef) == 0x123400);
        assert(esp.ser_r(4) == 0x1234);
    }

    // F4 configures memory addressing and aligns DBASE; its host readback is DIL.
    {
        ES5510 esp;
        writeReg(esp, 0xf8, 0x123456);
        writeReg(esp, 0xf4, 0x0000ff);
        assert(readReg(esp, 0xf8) == 0x123400);
        assert(readReg(esp, 0xf4) == 0);

        // Seed DRAM word 16 through the public host port, then read it through the
        // two-cycle delayed-RAM pipeline (DBASE=0x1000, MEMSHIFT=8).
        writeReg(esp, 0xf5, 0xffffff);
        writeReg(esp, 0xf8, 0x001000);
        esp.host_w(0x14, 0x40); // external DRAM
        esp.host_w(0x0c, 0x12); esp.host_w(0x0d, 0x34); esp.host_w(0x0e, 0x00);
        esp.host_w(0x10, 0x10); esp.host_w(0x11, 0x00); esp.host_w(0x0f, 0x00);
        writeReg(esp, 0x00, 0); writeReg(esp, 0x01, 0); writeReg(esp, 0x02, 0);
        writeInstruction(esp, 0, instruction(0, 0, 0, 0, 9));
        writeInstruction(esp, 1, instruction(0, 0, 0, 0, 9));
        writeInstruction(esp, 2, instruction(0, 0, 0, 0, 15));
        esp.set_halt(false);
        esp.run_frame();
        assert(readReg(esp, 0xf4) == 0x123400); // DIL reflects the delayed read
        assert(readReg(esp, 0xf8) == 0x000f00); // END advances DBASE by MEMINCREMENT
    }

    // DSP writeback may update serial SPRs; a MAC writeback updates MACH/MACL;
    // an ALU writeback updates CCR. These are execution effects, not loader writes.
    {
        ES5510 esp;
        writeReg(esp, 0x01, 0x123456);
        writeInstruction(esp, 0, instruction(0xef, 0x01, 0, 0, 9));
        writeInstruction(esp, 1, instruction(0, 0, 0, 0, 15));
        esp.set_halt(false); esp.run_frame();
        assert(readReg(esp, 0xef) == 0x123400);
        assert(esp.ser_r(4) == 0x1234);
    }
    {
        ES5510 esp;
        writeReg(esp, 0xf3, 0x001000);
        writeReg(esp, 0x02, 0x001000);
        writeInstruction(esp, 0, instruction(0, 0, 0xf3, 0x02, 9));
        writeInstruction(esp, 1, instruction(0, 0, 0, 0, 15));
        esp.set_halt(false); esp.run_frame();
        assert(readReg(esp, 0xf3) == 0x000004);
    }
    {
        ES5510 esp;
        writeReg(esp, 0x00, 0x7fffff);
        writeReg(esp, 0x01, 0x000001);
        writeInstruction(esp, 0, instruction(0, 0x01, 0, 0, 2));
        writeInstruction(esp, 1, instruction(0, 0, 0, 0, 15));
        esp.set_halt(false); esp.run_frame();
        assert(readReg(esp, 0xfa) == 0xa70000); // host readback adds unimplemented bits
        assert(capturedSpr(esp, 0xfa) == 0xa00000); // stored CCR contains only N and V
    }

    // Reset clears serial, MAC, DIL, delay pointers and condition state.
    {
        ES5510 esp;
        esp.ser_w(4, 0xe90d);
        writeReg(esp, 0xf3, 0x123456);
        writeReg(esp, 0xf8, 0x654300);
        writeReg(esp, 0xfa, 0xff0000);
        esp.reset();
        assert(readReg(esp, 0xef) == 0);
        assert(readReg(esp, 0xf3) == 0);
        assert(readReg(esp, 0xf4) == 0);
        assert(readReg(esp, 0xf8) == 0);
        assert(readReg(esp, 0xfa) == 0x070000);
        assert(capturedSpr(esp, 0xfa) == 0);
    }

    std::puts("ES5510 hardware state transitions: PASS");
    return 0;
}
