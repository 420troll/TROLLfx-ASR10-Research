#pragma once

/*
 * Standalone ES5510 execution engine, adapted from the MAME ES5510 device.
 * Copyright Christian Brunschen and MAMEdev contributors.
 * See THIRD_PARTY_NOTICES.md for the BSD-3-Clause terms.
 *
 * This adapter intentionally contains only the state and host/audio path
 * needed by the WAV harness. It preserves MAME's parallel ALU/MAC pipeline,
 * delayed RAM operations, 24-bit registers, 48-bit MAC, serial registers and
 * END/HALT frame lifecycle. MAME's unimplemented I/O-memory callbacks remain
 * unimplemented here too.
 */

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace trollfx::esp {

class MameES5510 {
public:
    static constexpr std::size_t kInstructionCount = 160;
    static constexpr std::size_t kDramWords = 1u << 20;
    static constexpr std::uint8_t kFlagN = 0x80, kFlagC = 0x40,
        kFlagV = 0x20, kFlagLt = 0x10, kFlagZ = 0x08,
        kFlagNot = 0x04, kFlagMask = 0xf8;

    bool prepare();
    void reset() noexcept;
    // Clear execution/register pipelines while preserving external DRAM.
    // Useful for bounded microprogram changes in a real-time host.
    void resetExecutionState() noexcept;
    bool loadProgram(const std::uint64_t* words, std::size_t count) noexcept;
    bool setDramWord(std::uint32_t address, std::int16_t value) noexcept;
    void setRegister(std::uint8_t reg, std::uint32_t value) noexcept;
    std::uint32_t registerValue(std::uint8_t reg) const noexcept;
    void setHostSerial(std::uint8_t value) noexcept { hostSerial_ = value; }
    std::uint8_t hostSerial() const noexcept { return hostSerial_; }
    std::uint64_t frames() const noexcept { return frames_; }
    std::uint64_t instructionsExecuted() const noexcept { return instructionsExecuted_; }

    // MAME esq_5505_5510_pump routing: input stereo pairs occupy serial ports
    // 0..2 and output is serial port 3. Sixteen-bit bus samples are used.
    void processFrame(const std::array<std::int16_t, 6>& inputs,
                      std::array<std::int16_t, 2>& outputs) noexcept;

    static constexpr std::uint64_t encode(unsigned a, unsigned b, unsigned c,
                                          unsigned d, unsigned aluOp,
                                          unsigned operandSelect = 0,
                                          unsigned ramControl = 0,
                                          bool skip = false,
                                          bool macAccumulate = false) noexcept {
        return (std::uint64_t(d & 255u) << 40) |
               (std::uint64_t(c & 255u) << 32) |
               (std::uint64_t(b & 255u) << 24) |
               (std::uint64_t(a & 255u) << 16) |
               (std::uint64_t(aluOp & 15u) << 12) |
               (std::uint64_t(operandSelect & 15u) << 8) |
               (std::uint64_t(skip) << 7) |
               (std::uint64_t(macAccumulate) << 6) |
               (std::uint64_t(ramControl & 7u) << 3);
    }

private:
    enum : std::uint8_t { Reg = 1, Delay = 2, Both = 3 };
    enum : std::uint8_t { RamRead = 0, RamWrite = 1, RamDump = 2 };
    struct Select { std::uint8_t aluSrc, aluDst, macSrc, macDst; };
    struct RamOp { std::int32_t address = 0; bool io = false; std::uint8_t cycle = RamRead; };
    struct AluPipe {
        std::uint8_t aReg = 0, bReg = 0, src = Reg, dst = Reg, op = 15;
        std::int32_t aValue = 0, bValue = 0, result = 0;
        bool updateCcr = false, writeResult = false;
    };
    struct MacPipe {
        std::uint8_t cReg = 0, dReg = 0, src = Reg, dst = Reg;
        bool accumulate = false, writeResult = false;
        std::int32_t cValue = 0, dValue = 0;
        std::int64_t product = 0, result = 0;
    };

    static const std::array<Select, 16> kSelect;
    static std::int32_t sign24(std::uint32_t) noexcept;
    static std::int64_t sign48(std::uint64_t) noexcept;
    static std::uint32_t alu(std::uint8_t, std::uint32_t, std::uint32_t,
                             std::uint8_t&) noexcept;
    static std::int16_t round24To16(std::uint32_t) noexcept;
    std::uint32_t readReg(std::uint8_t) const noexcept;
    void writeReg(std::uint8_t, std::uint32_t) noexcept;
    void writeDol(std::uint32_t) noexcept;
    void ejectDol() noexcept;
    std::int32_t ramAddress(std::uint8_t access, std::uint32_t offset) const noexcept;
    void executeOneFrame() noexcept;

    std::array<std::uint32_t, 192> gpr_{};
    std::array<std::uint64_t, kInstructionCount> instructions_{};
    std::vector<std::int16_t> dram_;
    std::array<std::int16_t, 8> serial_{};
    std::int64_t mac_ = 0;
    bool macOverflow_ = false;
    std::int16_t dil_ = 0;
    std::uint32_t memMask_ = 0, memIncrement_ = 0x01000000;
    std::uint8_t memShift_ = 24, ccr_ = 0, cmr_ = 0, hostSerial_ = 0;
    std::uint32_t dLength_ = 0, aBase_ = 0, bBase_ = 0, dBase_ = 0, sigReg_ = 0;
    std::array<std::int16_t, 2> dol_{};
    unsigned dolCount_ = 0;
    RamOp ram_{}, ramP_{}, ramPP_{};
    AluPipe alu_{};
    MacPipe macPipe_{};
    bool halted_ = true;
    std::uint64_t frames_ = 0, instructionsExecuted_ = 0;
};

} // namespace trollfx::esp
