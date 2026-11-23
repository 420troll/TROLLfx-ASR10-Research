#include "es5510.h"
#include "mame_es5510_standalone.hpp"

#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>

static std::uint64_t instruction(unsigned a, unsigned b, unsigned op) {
    return (std::uint64_t(a) << 16) | (std::uint64_t(b) << 24) |
           (std::uint64_t(op) << 12);
}
static void install(ES5510& cpu, unsigned index, std::uint64_t word) {
    for (unsigned n=0; n<6; ++n)
        cpu.host_w(3 + n, static_cast<std::uint8_t>(word >> ((5-n)*8)));
    cpu.host_w(0xc0, static_cast<std::uint8_t>(index));
}
static void set_gpr(ES5510& cpu, std::uint8_t reg, std::uint32_t value) {
    cpu.host_w(0, static_cast<std::uint8_t>(value >> 16));
    cpu.host_w(1, static_cast<std::uint8_t>(value >> 8));
    cpu.host_w(2, static_cast<std::uint8_t>(value));
    cpu.host_w(0xa0, reg);
}
static void write_csv(const std::string& path, bool reference, bool delay,
                      const std::string& input, const std::string& trace_path) {
    ES5510 original;
    trollfx::esp::MameES5510 mame;
    if (!mame.prepare()) throw std::runtime_error("MAME adapter DRAM allocation failed");
    // Original TROLLfx stereo feedback delay, assembled from its documented
    // microprogram. This is diagnostic TROLLfx code, never factory firmware.
    const std::uint64_t delay_program[] = {
        0xffffef0a9000ULL, 0xffffee0b9000ULL, 0x280e000c9c30ULL,
        0x280f000d9c30ULL, 0xffff0e0a0030ULL, 0xffff0f0b0030ULL,
        0xffff0a009508ULL, 0xffff0b009508ULL, 0xffff0af19030ULL,
        0xffff0bf09030ULL, 0xfffffffff000ULL
    };
    const auto left = instruction(241, 235, 9); // SER0L -> SER3L
    const auto right = instruction(240, 234, 9); // SER0R -> SER3R
    if (reference) {
        if (delay) {
            for (unsigned i=0;i<11;++i) install(original,i,delay_program[i]);
            set_gpr(original,244,0); set_gpr(original,245,0x0d754f); set_gpr(original,248,0);
            set_gpr(original,0,0x002b11); set_gpr(original,1,0x06e5b9);
            set_gpr(original,6,0); set_gpr(original,7,0x06baa8); set_gpr(original,40,0x233333);
        } else {
            install(original, 0, left); install(original, 1, right); install(original, 2, 0xf000);
        }
        original.host_w(0x18, 0x20);
    } else {
        const std::uint64_t pass_program[] = {left, right, 0xf000};
        const auto* program=delay?delay_program:pass_program;
        const std::size_t count=delay?11:3;
        if (!mame.loadProgram(program, count)) throw std::runtime_error("program load failed");
        if(delay) {
            mame.setRegister(244,0); mame.setRegister(245,0x0d754f); mame.setRegister(248,0);
            mame.setRegister(0,0x002b11); mame.setRegister(1,0x06e5b9);
            mame.setRegister(6,0); mame.setRegister(7,0x06baa8); mame.setRegister(40,0x233333);
        }
        mame.setHostSerial(0x20);
    }
    std::ifstream in(input);
    std::ofstream out(path);
    if (!in || !out) throw std::runtime_error("cannot open stimulus or output CSV");
    FILE* trace_file = trace_path.empty() ? nullptr : std::fopen(trace_path.c_str(), "w");
    if (!trace_path.empty() && !trace_file) throw std::runtime_error("cannot open trace output");
    if (reference) original.set_diagnostic_trace(trace_file);
    else mame.setDiagnosticTrace(trace_file);
    bool trace_done = false;
    out << "in_l,in_r,out_l,out_r\n";
    int l, r;
    while (in >> l) {
        char comma;
        if (!(in >> comma) || comma != ',' || !(in >> r) || l < -32768 || l > 32767 || r < -32768 || r > 32767)
            throw std::runtime_error("malformed stereo stimulus CSV");
        if (reference) {
            original.ser_w(delay?4:0, static_cast<std::int16_t>(l));
            original.ser_w(delay?5:1, static_cast<std::int16_t>(r));
            original.run_frame();
            const auto ol = original.ser_r(6), or_ = original.ser_r(7);
            out << l << ',' << r << ',' << ol << ',' << or_ << '\n';
            if (trace_file && !trace_done) { std::fprintf(trace_file, "ROUTE,0,%d,%d,%d,%d,%02x\n", l, r, ol, or_, original.serial_ctl());
                original.set_diagnostic_trace(nullptr); trace_done = true; }
        } else {
            std::array<std::int16_t, 6> inputs{}; inputs[delay?4:0]=static_cast<std::int16_t>(l); inputs[delay?5:1]=static_cast<std::int16_t>(r);
            std::array<std::int16_t, 2> outputs{}; mame.processFrame(inputs, outputs);
            out << l << ',' << r << ',' << outputs[0] << ',' << outputs[1] << '\n';
            if (trace_file && !trace_done) { std::fprintf(trace_file, "ROUTE,0,%d,%d,%d,%d,%02x\n", l, r, outputs[0], outputs[1], mame.hostSerial());
                mame.setDiagnosticTrace(nullptr); trace_done = true; }
        }
    }
    if (!in.eof()) throw std::runtime_error("failed reading stimulus CSV");
    if (trace_file) std::fclose(trace_file);
}
int main(int argc, char** argv) {
    try {
        if (argc != 5 && argc != 6) { std::cerr << "usage: es5510-audio-compare original|mame pass|delay INPUT.csv OUTPUT.csv [TRACE.csv]\n"; return 2; }
        const std::string mode=argv[1];
        const std::string algorithm=argv[2];
        if ((mode != "original" && mode != "mame") || (algorithm!="pass" && algorithm!="delay")) return 2;
        write_csv(argv[4], mode == "original", algorithm=="delay", argv[3], argc == 6 ? argv[5] : "");
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
    return 0;
}
