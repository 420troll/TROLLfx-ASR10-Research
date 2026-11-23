// license:BSD-3-Clause
// Copyright Christian Brunschen and MAMEdev contributors.
// Standalone adapter portions follow MAME src/devices/cpu/es5510/es5510.cpp.
// See THIRD_PARTY_NOTICES.md for the full redistribution terms.
#include "mame_es5510_standalone.hpp"

#include <algorithm>
#include <cstring>
#include <limits>

namespace trollfx::esp {

const std::array<MameES5510::Select, 16> MameES5510::kSelect = {{
    {Reg,Reg,Reg,Reg}, {Reg,Reg,Reg,Delay}, {Reg,Reg,Reg,Both}, {Reg,Reg,Delay,Reg},
    {Reg,Reg,Delay,Both}, {Reg,Delay,Reg,Reg}, {Reg,Delay,Delay,Reg}, {Reg,Both,Reg,Reg},
    {Reg,Both,Delay,Reg}, {Delay,Reg,Reg,Reg}, {Delay,Reg,Reg,Delay}, {Delay,Reg,Reg,Both},
    {Delay,Reg,Delay,Reg}, {Delay,Reg,Delay,Both}, {Delay,Both,Reg,Reg}, {Delay,Both,Delay,Reg}
}};

bool MameES5510::prepare() {
    try { dram_.assign(kDramWords, 0); }
    catch (...) { return false; }
    reset();
    return true;
}

void MameES5510::reset() noexcept {
    resetExecutionState();
    std::fill(dram_.begin(), dram_.end(), 0);
}

void MameES5510::resetExecutionState() noexcept {
    gpr_.fill(0); instructions_.fill(0); serial_.fill(0); mac_ = 0;
    macOverflow_ = false; dil_ = 0; memMask_ = 0; memIncrement_ = 0x01000000;
    memShift_ = 24; ccr_ = cmr_ = hostSerial_ = 0; dLength_ = aBase_ = bBase_ = dBase_ = sigReg_ = 0;
    dol_.fill(0); dolCount_ = 0; ram_ = {}; ramP_ = {}; ramPP_ = {};
    alu_ = {}; alu_.op = 15; macPipe_ = {}; halted_ = true;
    frames_ = instructionsExecuted_ = 0;
}

bool MameES5510::loadProgram(const std::uint64_t* words, std::size_t count) noexcept {
    if (!words || count == 0 || count > kInstructionCount) return false;
    bool hasEnd = false;
    for (std::size_t i=0; i<count; ++i) hasEnd = hasEnd || (((words[i] >> 12) & 15u) == 15u);
    if (!hasEnd) return false;
    instructions_.fill(0);
    for (std::size_t i = 0; i < count; ++i) instructions_[i] = words[i] & 0xffffffffffffULL;
    halted_ = true;
    return true;
}

bool MameES5510::setDramWord(std::uint32_t address, std::int16_t value) noexcept {
    if (dram_.size() != kDramWords || address >= kDramWords) return false;
    dram_[address] = value;
    return true;
}

std::int32_t MameES5510::sign24(std::uint32_t value) noexcept {
    value &= 0x00ffffffu;
    return (value & 0x00800000u) ? static_cast<std::int32_t>(value | 0xff000000u)
                                  : static_cast<std::int32_t>(value);
}

std::int64_t MameES5510::sign48(std::uint64_t value) noexcept {
    value &= 0x0000ffffffffffffULL;
    return (value & 0x0000800000000000ULL)
        ? static_cast<std::int64_t>(value | 0xffff000000000000ULL)
        : static_cast<std::int64_t>(value);
}

std::uint32_t MameES5510::readReg(std::uint8_t reg) const noexcept {
    if (reg < 0xc0) return gpr_[reg] & 0xffffffu;
    switch (reg) {
    case 234: return static_cast<std::uint32_t>(static_cast<std::uint16_t>(serial_[1])) << 8;
    case 235: return static_cast<std::uint32_t>(static_cast<std::uint16_t>(serial_[0])) << 8;
    case 236: return static_cast<std::uint32_t>(static_cast<std::uint16_t>(serial_[3])) << 8;
    case 237: return static_cast<std::uint32_t>(static_cast<std::uint16_t>(serial_[2])) << 8;
    case 238: return static_cast<std::uint32_t>(static_cast<std::uint16_t>(serial_[5])) << 8;
    case 239: return static_cast<std::uint32_t>(static_cast<std::uint16_t>(serial_[4])) << 8;
    case 240: return static_cast<std::uint32_t>(static_cast<std::uint16_t>(serial_[7])) << 8;
    case 241: return static_cast<std::uint32_t>(static_cast<std::uint16_t>(serial_[6])) << 8;
    case 242: return macOverflow_ ? (mac_ < 0 ? 0u : 0xffffffu) : static_cast<std::uint32_t>(mac_) & 0xffffffu;
    case 243: return macOverflow_ ? (mac_ < 0 ? 0x800000u : 0x7fffffu) : static_cast<std::uint32_t>(static_cast<std::uint64_t>(mac_) >> 24) & 0xffffffu;
    case 244: return static_cast<std::uint32_t>(static_cast<std::uint16_t>(dil_)) << 8;
    case 245: return dLength_ & 0xffffffu;
    case 246: return aBase_ & 0xffffffu;
    case 247: return bBase_ & 0xffffffu;
    case 248: return dBase_ & 0xffffffu;
    case 249: return sigReg_ & 0xffffffu;
    case 250: return static_cast<std::uint32_t>(ccr_) << 16;
    case 251: return static_cast<std::uint32_t>(cmr_) << 16;
    case 252: return 0xffffffu;
    case 253: return 0x800000u;
    case 254: return 0x7fffffu;
    default: return 0;
    }
}

void MameES5510::setRegister(std::uint8_t reg, std::uint32_t value) noexcept { writeReg(reg, value); }
std::uint32_t MameES5510::registerValue(std::uint8_t reg) const noexcept { return readReg(reg); }

void MameES5510::writeReg(std::uint8_t reg, std::uint32_t value) noexcept {
    value &= 0xffffffu;
    if (reg < 0xc0) { gpr_[reg] = value; return; }
    switch (reg) {
    case 234: serial_[1] = static_cast<std::int16_t>(value >> 8); break;
    case 235: serial_[0] = static_cast<std::int16_t>(value >> 8); break;
    case 236: serial_[3] = static_cast<std::int16_t>(value >> 8); break;
    case 237: serial_[2] = static_cast<std::int16_t>(value >> 8); break;
    case 238: serial_[5] = static_cast<std::int16_t>(value >> 8); break;
    case 239: serial_[4] = static_cast<std::int16_t>(value >> 8); break;
    case 240: serial_[7] = static_cast<std::int16_t>(value >> 8); break;
    case 241: serial_[6] = static_cast<std::int16_t>(value >> 8); break;
    case 242: mac_ = sign48((static_cast<std::uint64_t>(mac_) & 0xffffff000000ULL) | value); break;
    case 243: mac_ = sign48((static_cast<std::uint64_t>(value) << 24) | (static_cast<std::uint64_t>(mac_) & 0xffffffULL)); macOverflow_ = false; break;
    case 244: {
        unsigned lowOnes = 0;
        while (lowOnes < 24 && ((value >> lowOnes) & 1u)) ++lowOnes;
        memShift_ = static_cast<std::uint8_t>(lowOnes);
        const std::uint32_t memSize = 0xffffffu >> (24u - lowOnes);
        memMask_ = 0xffffffu & ~memSize;
        memIncrement_ = 1u << lowOnes;
        dBase_ &= memMask_;
        break;
    }
    case 245: dLength_ = value; break;
    case 246: aBase_ = value; break;
    case 247: bBase_ = value; break;
    case 248: dBase_ = value; break;
    case 249: sigReg_ = value; break;
    case 250: ccr_ = static_cast<std::uint8_t>((value >> 16) & kFlagMask); break;
    case 251: cmr_ = static_cast<std::uint8_t>((value >> 16) & (kFlagMask | kFlagNot)); break;
    default: break;
    }
}

std::int16_t MameES5510::round24To16(std::uint32_t value) noexcept {
    // MAME's current DOL_ROUND_TOWARDS_ZERO=0 behavior: arithmetic shift
    // discards low bits toward negative infinity.
    return static_cast<std::int16_t>(sign24(value) >> 8);
}

void MameES5510::writeDol(std::uint32_t value) noexcept {
    const auto sample = round24To16(value);
    if (dolCount_ >= 2) { dol_[0] = dol_[1]; dol_[1] = sample; }
    else dol_[dolCount_++] = sample;
}

void MameES5510::ejectDol() noexcept {
    dol_[0] = dol_[1];
    if (dolCount_ > 0) --dolCount_;
}

std::int32_t MameES5510::ramAddress(std::uint8_t access, std::uint32_t offset) const noexcept {
    std::uint32_t address = offset;
    if (access == 0) {
        const std::uint32_t length = dLength_ + memIncrement_;
        address = length ? (dBase_ + offset) % length : 0;
    } else if (access == 1) address += aBase_;
    else if (access == 2) address += bBase_;
    else return static_cast<std::int32_t>(offset & 0xfffff0u);
    return static_cast<std::int32_t>(((address & memMask_) >> memShift_) & (kDramWords - 1));
}

static void setFlag(std::uint8_t& flags, std::uint8_t flag, bool value) noexcept {
    flags = value ? static_cast<std::uint8_t>(flags | flag)
                  : static_cast<std::uint8_t>(flags & static_cast<std::uint8_t>(~flag));
}

static std::uint32_t add24(std::uint32_t a, std::uint32_t b, std::uint8_t& flags) noexcept {
    const std::uint32_t sum = (a & 0xffffffu) + (b & 0xffffffu);
    const bool as = (a & 0x800000u) != 0, bs = (b & 0x800000u) != 0, rs = (sum & 0x800000u) != 0;
    const bool overflow = as == bs && as != rs;
    setFlag(flags, MameES5510::kFlagC, (sum & 0x1000000u) != 0);
    setFlag(flags, MameES5510::kFlagN, rs);
    setFlag(flags, MameES5510::kFlagZ, (sum & 0xffffffu) == 0);
    setFlag(flags, MameES5510::kFlagV, overflow);
    setFlag(flags, MameES5510::kFlagLt, (overflow && !rs) || (!overflow && rs));
    return sum & 0xffffffu;
}

static std::uint32_t negate24(std::uint32_t v) noexcept { return ((v ^ 0xffffffu) + 1u) & 0xffffffu; }

std::uint32_t MameES5510::alu(std::uint8_t op, std::uint32_t a, std::uint32_t b, std::uint8_t& flags) noexcept {
    std::uint32_t r;
    switch (op) {
    case 0: r = add24(a,b,flags); if (flags & kFlagV) { setFlag(flags,kFlagN,(a & 0x800000u)!=0); setFlag(flags,kFlagZ,false); return (a & 0x800000u)?0x800000u:0x7fffffu; } return r;
    case 1: r = add24(a,negate24(b),flags); if (flags & kFlagV) { setFlag(flags,kFlagN,(a & 0x800000u)!=0); setFlag(flags,kFlagZ,false); return (a & 0x800000u)?0x800000u:0x7fffffu; } return r;
    case 2: return add24(a,b,flags);
    case 3: return add24(a,negate24(b),flags);
    case 4: (void)add24(a,negate24(b),flags); return a;
    case 5: r=a&b; setFlag(flags,kFlagN,(r&0x800000u)!=0); setFlag(flags,kFlagZ,r==0); return r;
    case 6: r=a|b; setFlag(flags,kFlagN,(r&0x800000u)!=0); setFlag(flags,kFlagZ,r==0); return r;
    case 7: r=a^b; setFlag(flags,kFlagN,(r&0x800000u)!=0); setFlag(flags,kFlagZ,r==0); return r;
    case 8: setFlag(flags,kFlagN,false); setFlag(flags,kFlagC,(b&0x800000u)!=0); r=(b&0x800000u)?(0xffffffu^b):b; setFlag(flags,kFlagZ,(r&0xffffffu)==0); return r;
    case 9: return b;
    case 10:
    case 11: {
        const unsigned shift=op==10?2u:8u; const std::int64_t x=static_cast<std::int64_t>(sign24(b))*(std::int64_t(1)<<shift);
        const bool ov=x>0x7fffffLL || x< -0x800000LL;
        r=ov?(x<0?0x800000u:0x7fffffu):static_cast<std::uint32_t>(x)&0xffffffu;
        setFlag(flags,kFlagC,((b&0xffffffu)>>(24u-shift)&1u)!=0); setFlag(flags,kFlagV,ov); setFlag(flags,kFlagN,(r&0x800000u)!=0); setFlag(flags,kFlagZ,r==0); return r;
    }
    case 12: setFlag(flags,kFlagN,false); setFlag(flags,kFlagC,(b&0x800000u)!=0); return (b<<15)&0x7fffffu;
    case 13: return add24(0x7fffffu,negate24(b),flags);
    case 14: setFlag(flags,kFlagN,(b&0x800000u)!=0); setFlag(flags,kFlagC,(b&1u)!=0); return (b>>1)|(b&0x800000u);
    default: return 0;
    }
}

void MameES5510::processFrame(const std::array<std::int16_t, 6>& inputs,
                              std::array<std::int16_t, 2>& outputs) noexcept {
    for (unsigned port=0; port<3; ++port) {
        if ((hostSerial_ & (0x04u << port)) == 0) {
            serial_[port*2]=inputs[port*2]; serial_[port*2+1]=inputs[port*2+1];
        }
    }
    executeOneFrame();
    outputs[0]=(hostSerial_&0x20u)?serial_[6]:0;
    outputs[1]=(hostSerial_&0x20u)?serial_[7]:0;
}

void MameES5510::executeOneFrame() noexcept {
    halted_=false; // MAME pump's HALT pulse starts the program at PC 0 for a frame.
    for (std::size_t pc=0; pc<kInstructionCount; ++pc) {
        const std::uint64_t instr=instructions_[pc];
        ramPP_=ramP_; ramP_=ram_;
        if (ramPP_.cycle != RamWrite) dil_ = ramPP_.io ? 0 : dram_[static_cast<std::size_t>(ramPP_.address)&(kDramWords-1)];
        const std::uint8_t ramControl=static_cast<std::uint8_t>((instr>>3)&7u);
        const std::uint8_t ramAccess=ramControl==0||ramControl==1||ramControl==5?0:
            ramControl==2||ramControl==3?1:ramControl==4?2:3;
        ram_.cycle=ramControl==1||ramControl==3||ramControl==7?RamWrite:
                   ramControl==5?RamDump:RamRead;
        ram_.io=ramAccess==3;
        ram_.address=ramAddress(ramAccess,gpr_[pc]);

        const Select select=kSelect[(instr>>8)&15u];
        const bool skippable=((instr>>7)&1u)!=0;
        bool condition=(ccr_&cmr_&kFlagMask)!=0;
        if(cmr_&kFlagNot) condition=!condition;
        const bool skip=skippable&&condition;

        if(macPipe_.writeResult) {
            const unsigned shift=(sigReg_&0x400000u)?1u:2u;
            const std::int64_t product=static_cast<std::int64_t>(sign24(static_cast<std::uint32_t>(macPipe_.cValue))) *
                                       static_cast<std::int64_t>(sign24(static_cast<std::uint32_t>(macPipe_.dValue))) *
                                       (std::int64_t(1)<<shift);
            macPipe_.product=product;
            macPipe_.result=macPipe_.accumulate?product+mac_:product;
            macOverflow_=macPipe_.result<-(std::int64_t(1)<<47)||macPipe_.result>=(std::int64_t(1)<<47);
            // MAME retains the full intermediate in machl and separately
            // tracks values that exceed its architecturally visible 48 bits.
            mac_=macPipe_.result;
            const std::uint32_t value=macOverflow_?(mac_<0?0x800000u:0x7fffffu):
                static_cast<std::uint32_t>(static_cast<std::uint64_t>(macPipe_.result)>>24)&0xffffffu;
            if(macPipe_.dst&Reg) writeReg(macPipe_.cReg,value);
            if(macPipe_.dst&Delay) writeDol(value);
        }
        macPipe_.cReg=static_cast<std::uint8_t>((instr>>32)&255u); macPipe_.dReg=static_cast<std::uint8_t>((instr>>40)&255u);
        macPipe_.src=select.macSrc; macPipe_.dst=select.macDst; macPipe_.accumulate=((instr>>6)&1u)!=0; macPipe_.writeResult=!skip;
        macPipe_.cValue=macPipe_.src==Reg?static_cast<std::int32_t>(readReg(macPipe_.cReg)):static_cast<std::int32_t>(static_cast<std::uint16_t>(dil_))<<8;
        macPipe_.dValue=static_cast<std::int32_t>(readReg(macPipe_.dReg));

        if(alu_.writeResult) {
            std::uint8_t flags=ccr_; alu_.result=static_cast<std::int32_t>(alu(alu_.op,static_cast<std::uint32_t>(alu_.aValue),static_cast<std::uint32_t>(alu_.bValue),flags));
            if(alu_.op!=4) { if(alu_.dst&Reg) writeReg(alu_.aReg,static_cast<std::uint32_t>(alu_.result)); if(alu_.dst&Delay) writeDol(static_cast<std::uint32_t>(alu_.result)); }
            if(alu_.updateCcr) ccr_=flags;
        }
        alu_.aReg=static_cast<std::uint8_t>((instr>>16)&255u); alu_.bReg=static_cast<std::uint8_t>((instr>>24)&255u);
        alu_.op=static_cast<std::uint8_t>((instr>>12)&15u); alu_.src=select.aluSrc; alu_.dst=select.aluDst;
        alu_.writeResult=!skip||alu_.op==4; alu_.updateCcr=!skippable||alu_.op==4;
        const bool end=alu_.op==15;
        if(!end) {
            if(alu_.op>=8) alu_.bValue=alu_.src==Reg?static_cast<std::int32_t>(readReg(alu_.bReg)):static_cast<std::int32_t>(static_cast<std::uint16_t>(dil_))<<8;
            else { alu_.aValue=alu_.src==Reg?static_cast<std::int32_t>(readReg(alu_.aReg)):static_cast<std::int32_t>(static_cast<std::uint16_t>(dil_))<<8; alu_.bValue=static_cast<std::int32_t>(readReg(alu_.bReg)); }
        }
        if(ramP_.cycle!=RamRead) {
            if(ramP_.cycle==RamWrite&&!ramP_.io&&dolCount_>0) dram_[static_cast<std::size_t>(ramP_.address)&(kDramWords-1)]=dol_[0];
            ejectDol();
        }
        ++instructionsExecuted_;
        if(end) {
            const std::int64_t next=static_cast<std::int64_t>(dBase_)-memIncrement_;
            dBase_=next<0?dLength_:static_cast<std::uint32_t>(next);
            halted_=true; break;
        }
    }
    ++frames_;
}

} // namespace trollfx::esp
