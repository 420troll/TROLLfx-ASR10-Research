// Ensoniq ES5510 ESP - see es5510.h for attribution.
#include "es5510.h"
#include "es5510_capture.h"
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <vector>
#include <algorithm>

#if defined(__GNUC__) || defined(__clang__)
#define ESP_INLINE __attribute__((always_inline)) inline
#else
#define ESP_INLINE inline
#endif

namespace {
constexpr uint8_t FLAG_N = 1 << 7, FLAG_C = 1 << 6, FLAG_V = 1 << 5, FLAG_LT = 1 << 4, FLAG_Z = 1 << 3, FLAG_NOT = 1 << 2;
constexpr uint8_t FLAG_MASK = FLAG_N | FLAG_C | FLAG_V | FLAG_LT | FLAG_Z;
inline uint8_t setFlagTo(uint8_t ccr, uint8_t f, bool s) { return s ? (ccr | f) : (ccr & ~f); }
inline bool isFlagSet(uint8_t ccr, uint8_t f) { return (ccr & f) != 0; }
inline int32_t sext24(int32_t v) { return (int32_t)((uint32_t)v << 8) >> 8; }
inline int64_t sext48(int64_t v) { return (int64_t)((uint64_t)v << 16) >> 16; }

inline int32_t add(int32_t a, int32_t b, uint8_t &flags) {
    // (branch-free) C = carry out of bit 23, N = sign, Z = zero, V = signed overflow, LT = N xor V
    const uint32_t r = (uint32_t)a + (uint32_t)b;
    const uint32_t c = (r >> 24) & 1, n = (r >> 23) & 1, z = (r & 0x00ffffff) == 0;
    const uint32_t v = ((~((uint32_t)a ^ (uint32_t)b) & ((uint32_t)a ^ r)) >> 23) & 1;
    flags = (uint8_t)((flags & ~(FLAG_C | FLAG_N | FLAG_Z | FLAG_V | FLAG_LT)) | (c << 6) | (n << 7) | (z << 3) | (v << 5) | ((n ^ v) << 4));
    return (int32_t)(r & 0x00ffffff);
}
inline int16_t round_24_to_16(int32_t v) { return (int16_t)(v >> 8); }
inline int32_t saturate(int32_t value, uint8_t &flags, bool negative) {
    if (isFlagSet(flags, FLAG_V)) {
        flags = setFlagTo(flags, FLAG_N, negative);
        flags &= ~FLAG_Z;
        return negative ? 0x00800000 : 0x007fffff;
    }
    return value;
}
inline int32_t negate(int32_t v) { return ((v ^ 0x00ffffff) + 1) & 0x00ffffff; }
inline int32_t asl(int32_t value, int shift, uint8_t &flags) {
    int32_t src24 = value & 0x00ffffff;
    bool carry = (src24 >> (24 - shift)) & 1;
    // Multiplication expresses the intended two's-complement shift without
    // invoking undefined behavior when src24 is negative.
    int64_t shifted = (int64_t)sext24(src24) * (int64_t(1) << shift);
    bool overflow = (shifted > 0x007fffffLL) || (shifted < -0x00800000LL);
    int32_t result = overflow ? ((shifted < 0) ? 0x00800000 : 0x007fffff) : ((int32_t)shifted & 0x00ffffff);
    (void)carry;   // ASL2/ASL8: C unchanged (datasheet 3.3.3)
    flags = setFlagTo(flags, FLAG_V, overflow);
    flags = setFlagTo(flags, FLAG_N, (result & 0x00800000) != 0);
    flags = setFlagTo(flags, FLAG_Z, (result & 0x00ffffff) == 0);
    return result;
}
int8_t countLowOnes(int32_t x) { int8_t n = 0; while ((x & 1) == 1) { ++n; x >>= 1; } return n; }
}

const int ES5510::ALU_OPERANDS[16] = { 2,2,2,2,2,2,2,2,1,1,1,1,1,1,1,0 };
const ES5510::OpSel ES5510::OPSEL[16] = {
    { REG, REG, REG, REG }, { REG, REG, REG, DELAY }, { REG, REG, REG, BOTH }, { REG, REG, DELAY, REG },
    { REG, REG, DELAY, BOTH }, { REG, DELAY, REG, REG }, { REG, DELAY, DELAY, REG }, { REG, BOTH, REG, REG },
    { REG, BOTH, DELAY, REG }, { DELAY, REG, REG, REG }, { DELAY, REG, REG, DELAY }, { DELAY, REG, REG, BOTH },
    { DELAY, REG, DELAY, REG }, { DELAY, REG, DELAY, BOTH }, { DELAY, BOTH, REG, REG }, { DELAY, BOTH, DELAY, REG },
};
const ES5510::RamCtl ES5510::RAMCTL[8] = {
    { READ, A_DELAY }, { WRITE, A_DELAY }, { READ, A_TABLE_A }, { WRITE, A_TABLE_A },
    { READ, A_TABLE_B }, { DUMP, A_DELAY }, { READ, A_IO }, { WRITE, A_IO },
};

ES5510::ES5510() : dram(DRAM_SIZE) {
    hostlog = getenv("ESP_HOSTLOG") != nullptr;
    pipelog = getenv("ESP_PIPELOG") != nullptr;
    const char *frame_log = getenv("ESP_FRAMELOG");
    if (frame_log) frame_trace_limit = (uint32_t)std::clamp(atoll(frame_log), 0LL, 32768LL);
    if (const char *start = getenv("ESP_FRAMELOG_START_FRAME")) frame_trace_start_frame = strtoull(start, nullptr, 10);
    if (const char *frame = getenv("ESP_RUN_SNAPSHOT_FRAME")) run_snapshot_frame = strtoull(frame, nullptr, 10);
    if (const char *dir = getenv("ESP_RUN_SNAPSHOT_DIR")) run_snapshot_dir = dir;
    reset();
}

void ES5510::set_halt(bool h) {
    if (pipelog && h != halt_asserted)
        fprintf(stderr, "ESPPHASE kind=pa4_%s frame=%llu cycles=%llu host_pc=%06x\n",
                h ? "halt_assert" : "run_release", (unsigned long long)frame_count,
                (unsigned long long)host_cycles, host_pc);
    halt_asserted = h;
}

void ES5510::reset() {
    host_cycles = host_event = frame_count = 0;
    host_pc = 0;
    pc = 0;
    memset(gpr, 0, sizeof(gpr));
    memset(instr, 0, sizeof(instr));
    for (int i = 0; i < 160; i++) decode(i);
    memset(ser, 0, sizeof(ser));
    std::fill(dram.begin(), dram.end(), 0);
    state = RUNNING;
    dil_latch = dol_latch = gpr_latch = 0; dadr_latch = 0;
    instr_latch = 0; ram_ctl = 0; host_control = 0x04; host_serial = 0;
    sigreg = 0; mulshift = 2;
    ram = ram_p = ram_pp = Ram{};
    alu = Alu{}; mulacc = Mac{};
    machl = 0; mac_overflow = false; dil = 0;
    memsiz = 0xffffff; memmask = 0; memincrement = 0x1000000; memshift = 24;
    dlength = abase = bbase = dbase = 0; ccr = cmr = 0; dol[0] = dol[1] = 0; dol_count = 0;
    sync_spr();
    trace_first_instruction = trace_output_pending = false;
    trace_selected_frame = false;
    frame_trace_remaining = frame_trace_index = 0;
    load_transaction_seen = false; load_instruction_commits = load_gpr_commits = 0;
    load_instruction_addresses.fill(false);
}

void ES5510::sync_spr() {
    for (int r = 234; r < 256; r++) gpr[r] = read_reg((uint8_t)r);
    gpr[DIL_SRC] = (int32_t)((uint32_t)(uint16_t)dil << 8);
}

uint8_t ES5510::host_r(int offset) {
    switch (offset) {
    case 0x00: return (gpr_latch >> 16) & 0xff;
    case 0x01: return (gpr_latch >> 8) & 0xff;
    case 0x02: return gpr_latch & 0xff;
    case 0x03: return (instr_latch >> 40) & 0xff;
    case 0x04: return (instr_latch >> 32) & 0xff;
    case 0x05: return (instr_latch >> 24) & 0xff;
    case 0x06: return (instr_latch >> 16) & 0xff;
    case 0x07: return (instr_latch >> 8) & 0xff;
    case 0x08: return instr_latch & 0xff;
    case 0x09: return (dil_latch >> 16) & 0xff;
    case 0x0a: return (dil_latch >> 8) & 0xff;
    case 0x0b: return 0;
    case 0x0c: return (dol_latch >> 16) & 0xff;
    case 0x0d: return (dol_latch >> 8) & 0xff;
    case 0x0e: return 0xff;
    case 0x0f: return (dadr_latch >> 16) & 0xff;
    case 0x10: return (dadr_latch >> 8) & 0xff;
    case 0x11: return dadr_latch & 0xff;
    case 0x12: return (host_control & ~0x04) | (read_pending >= 0 ? 0x04 : 0);   // bit 2 = transfer pending
    case 0x16:   // while halted the PC register counts through refresh cycles (datasheet 5.1.5)
        if (state == HALTED) { refresh_pc = (refresh_pc + 23) % 160; return refresh_pc; }
        return pc;
    case 0x17: return refresh_pc ^ 0x80;
    }
    return 0;
}

void ES5510::host_w(int offset, uint8_t data) {
    switch (offset) {
    case 0x00: gpr_latch = (gpr_latch & 0x00ffff) | (data << 16); break;
    case 0x01: gpr_latch = (gpr_latch & 0xff00ff) | (data << 8); break;
    case 0x02: gpr_latch = (gpr_latch & 0xffff00) | data; break;
    case 0x03: instr_latch = (instr_latch & 0x00ffffffffffULL) | ((uint64_t)data << 40); break;
    case 0x04: instr_latch = (instr_latch & 0xff00ffffffffULL) | ((uint64_t)data << 32); break;
    case 0x05: instr_latch = (instr_latch & 0xffff00ffffffULL) | ((uint64_t)data << 24); break;
    case 0x06: instr_latch = (instr_latch & 0xffffff00ffffULL) | ((uint64_t)data << 16); break;
    case 0x07: instr_latch = (instr_latch & 0xffffffff00ffULL) | ((uint64_t)data << 8); break;
    case 0x08: instr_latch = (instr_latch & 0xffffffffff00ULL) | (uint64_t)data; break;
    case 0x0c: dol_latch = (dol_latch & 0x00ffff) | (data << 16); break;
    case 0x0d: dol_latch = (dol_latch & 0xff00ff) | (data << 8); break;
    case 0x0e: dol_latch = (dol_latch & 0xffff00) | data; break;
    case 0x0f: {   // writing DADR HI starts the transfer; DADR is left-justified like the GPR offsets
        dadr_latch = (dadr_latch & 0x00ffff) | (data << 16);
        int a = (dadr_latch & memmask) >> memshift;
        if (hostlog) fprintf(stderr, "ESPHOST event=%llu cycles=%llu frame=%llu pc=%06x ram %s ctl=%02x dadr=%06x -> word %05x dol=%04x t=%.6f\n",
                             (unsigned long long)++host_event, (unsigned long long)host_cycles,
                             (unsigned long long)frame_count, host_pc, (ram_ctl & 0x80) ? "rd" : "wr",
                             ram_ctl, dadr_latch, a, (dol_latch >> 8) & 0xffff, hostlog_time);
        if (!(ram_ctl & 0x40)) { if (ram_ctl & 0x80) dil_latch = 0; }       // I/O space: nothing attached
        else if (ram_ctl & 0x80) dil_latch = (int32_t)((uint32_t)(uint16_t)dram_r(a) << 8);
        else dram_w(a, dol_latch >> 8);
        break;
    }
    case 0x10: dadr_latch = (dadr_latch & 0xff00ff) | (data << 8); break;
    case 0x11: dadr_latch = (dadr_latch & 0xffff00) | data; break;
    case 0x12:
        host_control = (host_control & 0x4) | (data & 0x3);
        if (host_control & 2) {
            if (state == HALTED) {
                std::fill(dram.begin(), dram.end(), 0);
                if (pipelog) fprintf(stderr, "ESPPHASE kind=host_dram_clear frame=%llu cycles=%llu pc=%06x halted=1\n",
                                     (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc);
            } else if (pipelog) {
                fprintf(stderr, "ESPPHASE kind=host_dram_clear_ignored frame=%llu cycles=%llu pc=%06x halted=0\n",
                        (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc);
            }
            host_control &= ~2;
        }
        break;
    case 0x14: ram_ctl = data; break;
    case 0x18:
        host_serial = data;
        if (pipelog) fprintf(stderr, "ESPPHASE kind=serial_config frame=%llu cycles=%llu pc=%06x value=%02x\n",
                             (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc, data);
        break;
    case 0x1f:   // Halt Enable: immediate halt when HALT is asserted (pending pipeline work is lost)
        if (halt_asserted) {
            if (pipelog) fprintf(stderr, "ESPPHASE kind=halt frame=%llu cycles=%llu pc=%06x host_control=%02x\n",
                                 (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc, host_control);
            state = HALTED; host_control &= ~0x04;
            load_transaction_seen = false;
            load_instruction_commits = load_gpr_commits = 0;
            load_instruction_addresses.fill(false);
            mulacc.write_result = alu.write_result = false;
            ram = ram_p = ram_pp = Ram{}; dol_count = 0;
            if (pipelog) fprintf(stderr, "ESPPHASE kind=host_halt_pipeline_reset frame=%llu cycles=%llu pc=%06x alu_pending=0 mac_pending=0 ram_slots_cleared=3 dol_count=0\n",
                                 (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc);
        }
        break;
    case 0x80:
        if (data < 0xa0) instr_latch = instr[data];
        if (data < 0xc0 && defer_gpr_reads && state == RUNNING) read_pending = data;   // served by the next frame
        else if (data < 0xc0) gpr_latch = gpr[data] & 0xffffff;
        else if (data >= 0xea) {
            // host read-back of the special registers: unimplemented bits read as 1
            // (the OS effect-download verify masks exactly these bits)
            int32_t v = read_reg(data);
            if (data >= 0xf5 && data <= 0xf7) v |= 0x0f;          // DLENGTH/ABASE/BBASE: 20 bits, left justified
            else if (data == 0xf9) v |= 0x3f0000;                  // SIGREG
            else if (data == 0xfa) v |= 0x070000;                  // CCR
            else if (data == 0xfb) v |= 0x030000;                  // CMR
            else if (data == 0xf0 || data == 0xf1) v |= 0xff;      // SER3
            gpr_latch = v & 0xffffff;
        }
        break;
    case 0xa0:
        if (hostlog) fprintf(stderr, "ESPHOST event=%llu cycles=%llu frame=%llu pc=%06x gpr %02x <- %06x t=%.6f\n", (unsigned long long)++host_event, (unsigned long long)host_cycles, (unsigned long long)frame_count, host_pc, data, gpr_latch & 0xffffff, hostlog_time);
        if (state == HALTED) ++load_gpr_commits;
        write_reg(data, gpr_latch); break;
    case 0xc0:
        if (hostlog) fprintf(stderr, "ESPHOST event=%llu cycles=%llu frame=%llu pc=%06x instr %02x <- %012llx t=%.6f\n", (unsigned long long)++host_event, (unsigned long long)host_cycles, (unsigned long long)frame_count, host_pc, data, (unsigned long long)instr_latch, hostlog_time);
        if (data < 0xa0) {
            if (state == HALTED) {
                if (!load_transaction_seen) {
                    load_transaction_seen = true;
                    if (pipelog) fprintf(stderr, "ESPPHASE kind=instruction_upload_start frame=%llu cycles=%llu pc=%06x address=%02x\n",
                                         (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc, data);
                }
                ++load_instruction_commits; load_instruction_addresses[data] = true;
            }
            instr[data] = instr_latch & 0xffffffffffffULL; decode(data);
        }
        break;
    case 0xe0:
        if (hostlog) fprintf(stderr, "ESPHOST event=%llu cycles=%llu frame=%llu pc=%06x both %02x <- %012llx / %06x t=%.6f\n", (unsigned long long)++host_event, (unsigned long long)host_cycles, (unsigned long long)frame_count, host_pc, data, (unsigned long long)instr_latch, gpr_latch & 0xffffff, hostlog_time);
        if (data < 0xa0) {
            if (state == HALTED) {
                if (!load_transaction_seen) {
                    load_transaction_seen = true;
                    if (pipelog) fprintf(stderr, "ESPPHASE kind=instruction_upload_start frame=%llu cycles=%llu pc=%06x address=%02x\n",
                                         (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc, data);
                }
                ++load_instruction_commits; load_instruction_addresses[data] = true;
            }
            instr[data] = instr_latch; decode(data);
        }
        if (state == HALTED) ++load_gpr_commits;
        write_reg(data, gpr_latch);
        break;
    }
}

int32_t ES5510::read_reg(uint8_t reg) {
    if (reg < 0xc0) return gpr[reg];
    switch (reg) {
    case 234: return (int32_t)((uint32_t)(uint16_t)ser[1] << 8);   // SER0R
    case 235: return (int32_t)((uint32_t)(uint16_t)ser[0] << 8);   // SER0L
    case 236: return (int32_t)((uint32_t)(uint16_t)ser[3] << 8);
    case 237: return (int32_t)((uint32_t)(uint16_t)ser[2] << 8);
    case 238: return (int32_t)((uint32_t)(uint16_t)ser[5] << 8);
    case 239: return (int32_t)((uint32_t)(uint16_t)ser[4] << 8);
    case 240: return (int32_t)((uint32_t)(uint16_t)ser[7] << 8);
    case 241: return (int32_t)((uint32_t)(uint16_t)ser[6] << 8);
    case 242: return mac_overflow ? (machl < 0 ? 0x00000000 : 0x00ffffff) : (int32_t)(machl & 0x00ffffff);
    case 243: return mac_overflow ? (machl < 0 ? 0x00800000 : 0x007fffff) : (int32_t)((machl >> 24) & 0x00ffffff);
    case 244: return (int32_t)((uint32_t)(uint16_t)dil << 8);
    case 245: return dlength;
    case 246: return abase;
    case 247: return bbase;
    case 248: return dbase;
    case 249: return sigreg;
    case 250: return ccr << 16;
    case 251: return cmr << 16;
    case 252: return 0x00ffffff;
    case 253: return 0x00800000;
    case 254: return 0x007fffff;
    case 255: return 0;
    }
    return 0;
}

void ES5510::write_reg(uint8_t reg, int32_t value) {
    value &= 0x00ffffff;
    if (reg < 0xc0) { gpr[reg] = value; return; }
    switch (reg) {
    case 234: ser[1] = (value >> 8) & 0xffff; break;
    case 235: ser[0] = (value >> 8) & 0xffff; break;
    case 236: ser[3] = (value >> 8) & 0xffff; break;
    case 237: ser[2] = (value >> 8) & 0xffff; break;
    case 238: ser[5] = (value >> 8) & 0xffff; break;
    case 239: ser[4] = (value >> 8) & 0xffff; break;
    case 240: ser[7] = (value >> 8) & 0xffff; break;
    case 241: ser[6] = (value >> 8) & 0xffff; break;
    case 242: {
        int64_t masked = machl & ((int64_t)0x00ffffff << 24);
        machl = sext48(masked | (int64_t)(value & 0x00ffffff));
        break;
    }
    case 243: {
        int64_t masked = machl & (int64_t)0x00ffffff;
        machl = sext48(masked | ((int64_t)(value & 0x00ffffff) << 24));
        mac_overflow = false;
        break;
    }
    case 244:
        memshift = countLowOnes(value);
        memsiz = 0x00ffffff >> (24 - memshift);
        memmask = 0x00ffffff & ~memsiz;
        memincrement = 1 << memshift;
        dbase &= memmask;
        break;
    case 245: dlength = value; break;
    case 246: abase = value; break;
    case 247: bbase = value; break;
    case 248: dbase = value; break;
    case 249: sigreg = value; mulshift = ((sigreg >> 22) & 1) ? 1 : 2; break;
    case 250: ccr = (value >> 16) & FLAG_MASK; break;
    case 251: cmr = (value >> 16) & (FLAG_MASK | FLAG_NOT); break;
    }
    // the copies in gpr[] of what changed
    if (reg >= 234 && reg <= 241) gpr[reg] = read_reg(reg);
    else if (reg == 242 || reg == 243) { gpr[242] = read_reg(242); gpr[243] = read_reg(243); }
    else if (reg >= 244 && reg <= 251) { gpr[248] = dbase; gpr[reg] = read_reg(reg); }
}

ESP_INLINE void ES5510::write_to_dol(int32_t value) {
    int16_t d = round_24_to_16(value);
    if (dol_count >= 2) { dol[0] = dol[1]; dol[1] = d; }
    else dol[dol_count++] = d;
}

void ES5510::alu_operation_end() {
    if (halt_asserted) { state = HALTED; host_control &= ~0x04; }
    dbase -= memincrement;
    if (dbase < 0) dbase = dlength;
    gpr[248] = dbase;
}

ESP_INLINE int32_t ES5510::alu_operation(uint8_t op, int32_t a, int32_t b, uint8_t &flags) {
    int32_t tmp;
    switch (op) {
    case 0x0: tmp = add(a, b, flags); return saturate(tmp, flags, (a & 0x00800000) != 0);
    case 0x1: tmp = add(a, negate(b), flags); return saturate(tmp, flags, (a & 0x00800000) != 0);
    case 0x2: return add(a, b, flags);
    case 0x3: return add(a, negate(b), flags);
    case 0x4: add(a, negate(b), flags); return a;
    case 0x5: a &= b; flags = setFlagTo(flags, FLAG_N, (a & 0x00800000) != 0); flags = setFlagTo(flags, FLAG_Z, a == 0); return a;
    case 0x6: a |= b; flags = setFlagTo(flags, FLAG_N, (a & 0x00800000) != 0); flags = setFlagTo(flags, FLAG_Z, a == 0); return a;
    case 0x7: a ^= b; flags = setFlagTo(flags, FLAG_N, (a & 0x00800000) != 0); flags = setFlagTo(flags, FLAG_Z, a == 0); return a;
    case 0x8: {
        flags &= ~FLAG_N;
        bool neg = (b & 0x00800000) != 0;
        flags = setFlagTo(flags, FLAG_C, neg);
        return neg ? (0x00ffffff ^ b) : b;   // ABS: N=0, C=sign, others unchanged
    }
    case 0x9: return b;
    case 0xa: return asl(b, 2, flags);
    case 0xb: return asl(b, 8, flags);
    case 0xc: flags &= ~FLAG_N; flags = setFlagTo(flags, FLAG_C, (b & 0x100) != 0); return (b << 15) & 0x007fffff;   // C = bit shifted into the sign position
    case 0xd: return add(0x007fffff, negate(b), flags);
    case 0xe: flags = setFlagTo(flags, FLAG_N, (b & 0x00800000) != 0); flags = setFlagTo(flags, FLAG_C, (b & 1) != 0); return (b >> 1) | (b & 0x00800000);
    }
    return 0;
}

ESP_INLINE void ES5510::mul_writeback() {
    if (!mulacc.write_result) return;
    mulacc.write_result = false;
    // A signed left shift of a negative MAC product is undefined in C++.
    // The ES5510 scaling factor is a power of two and this product fits int64.
    mulacc.product = ((int64_t)sext24(mulacc.cValue) * (int64_t)sext24(mulacc.dValue)) * (int64_t(1) << mulshift);
    mulacc.result = mulacc.accumulate ? mulacc.product + machl : mulacc.product;
    mac_overflow = (mulacc.result < -((int64_t)1 << 47) || mulacc.result >= ((int64_t)1 << 47));
    machl = mulacc.result;
    int32_t tmp = mac_overflow ? (machl < 0 ? 0x00800000 : 0x007fffff) : (int32_t)((mulacc.result & 0x0000ffffff000000ULL) >> 24);
    if (itrace) fprintf(stderr, "  pc%02x MUL c=%06x d=%06x acc=%d -> %06x machl=%012llx\n", pc, mulacc.cValue & 0xffffff, mulacc.dValue & 0xffffff, mulacc.accumulate, tmp & 0xffffff, (unsigned long long)(machl & 0xffffffffffffULL));
    if (mulacc.dst & REG) wr(mulacc.cReg, tmp);
    if (mulacc.dst & DELAY) write_to_dol(tmp);
}

ESP_INLINE void ES5510::alu_writeback() {
    if (!alu.write_result) return;
    alu.write_result = false;
    if (alu.op == 0xf) return;      // END: no ALU result
    uint8_t flags = ccr;
    alu.result = alu_operation(alu.op, alu.aValue, alu.bValue, flags);
    if (itrace) fprintf(stderr, "  pc%02x ALU op=%x a=%06x b=%06x -> %06x ccr=%02x dil=%04x\n", pc, alu.op, alu.aValue & 0xffffff, alu.bValue & 0xffffff, alu.result & 0xffffff, flags, dil & 0xffff);
    bool wrote_ccr = false;
    if (alu.op != 4) {
        if (alu.dst & REG) { wr(alu.aReg, alu.result); wrote_ccr = alu.aReg == 0xfa; }
        if (alu.dst & DELAY) write_to_dol(alu.result);
    }
    // a MOV into CCR sets the flags explicitly (the EPS-16 Plus sampling program alternates
    // them this way): the result flags must not overwrite the value just written
    if (alu.update_ccr && !(wrote_ccr && ccr_write_wins)) ccr = flags;
}

ESP_INLINE void ES5510::ram_write_cycle(const Ram &r) {
    if (r.cycle != READ) {
        if (r.cycle == WRITE && !r.io) {
            if (pipelog && frame_trace_remaining > 0)
                fprintf(stderr, "ESPRAM event=%llu kind=write frame=%llu pc=%02x io=0 address=%08x data=%04x\n",
                        (unsigned long long)++ram_trace_event, (unsigned long long)frame_count,
                        pc, (unsigned)r.address, (unsigned)(uint16_t)dol[0]);
            dram_w(r.address, dol[0]);
        }
        dol[0] = dol[1];
        if (dol_count > 0) --dol_count;
    }
}

// Halt at END: the ESP finishes the END instruction before stopping, so the machine is left
// in a known state (datasheet 5.3.1); halting also resets the DOL FIFO pointers (3.5.3).
void ES5510::drain_pipeline() {
    mul_writeback();
    alu_writeback();
    ram_write_cycle(ram);
    ram = ram_p = ram_pp = Ram{};
    dol_count = 0;
    sync_spr();
}

void ES5510::decode(int i) {
    const uint64_t in = instr[i];
    Dec &d = dec[i];
    const OpSel &os = OPSEL[(in >> 8) & 0x0f];
    const RamCtl &rc = RAMCTL[(in >> 3) & 7];
    d.aReg = (in >> 16) & 0xff; d.bReg = (in >> 24) & 0xff; d.cReg = (in >> 32) & 0xff; d.dReg = (in >> 40) & 0xff;
    d.op = (in >> 12) & 0x0f;
    d.alu_src = os.alu_src; d.alu_dst = os.alu_dst; d.mac_src = os.mac_src; d.mac_dst = os.mac_dst;
    d.ram_cycle = (uint8_t)rc.cycle; d.ram_access = (uint8_t)rc.access;
    d.acc = ((in >> 6) & 1) != 0;
    d.skippable = (in & 0x80) != 0;
    d.one_operand = ALU_OPERANDS[d.op] == 1;
    d.c_src = d.mac_src == REG ? d.cReg : DIL_SRC;
    d.a_src = d.alu_src == REG ? d.aReg : DIL_SRC;
    d.b1_src = d.alu_src == REG ? d.bReg : DIL_SRC;
    // where the results go: a register, or nowhere (also for the registers that ignore writes:
    // the unused ones and the constants ZERO, MAX, MIN, M1)
    auto target = [](uint8_t r) -> uint16_t { return (r < 0xc0 || (r >= 234 && r <= 251)) ? r : TRASH; };
    d.mac_w = (d.mac_dst & REG) ? target(d.cReg) : TRASH;
    d.alu_w = ((d.alu_dst & REG) && d.op != 4) ? target(d.aReg) : TRASH;     // (CMP writes no result)
    finish_dec(d);
}

void ES5510::finish_dec(Dec &d) {
    d.ram_io = d.ram_access == A_IO;
    d.mac_spec = d.mac_w >= 0xc0 && d.mac_w < 0x100;
    d.alu_spec = d.alu_w >= 0xc0 && d.alu_w < 0x100;
    d.aupd = !d.skippable || d.op == 4;
    d.upd[0] = d.aupd;
    d.upd[1] = d.aupd && d.alu_w != 0xfa;
}

void ES5510::run_frame() {
    ++frame_count;
    struct ServeRead { ES5510 *e; ~ServeRead() { if (e->read_pending >= 0) { e->gpr_latch = e->gpr[e->read_pending] & 0xffffff; e->read_pending = -1; } } } serve{ this };
    static const char *trace = getenv("ESP_TRACE");     // debug: "every,reg,reg,..." (hex GPR numbers)
    static long frames = 0;
    if (trace && state == RUNNING) {
        ++frames;
        int every = atoi(trace);
        if (every > 0 && (frames % every) == 0) {
            fprintf(stderr, "ESP f=%ld", frames);
            for (const char *p = strchr(trace, ','); p; p = strchr(p + 1, ','))
                fprintf(stderr, " %02lx=%06x", strtol(p + 1, nullptr, 16), read_reg((uint8_t)strtol(p + 1, nullptr, 16)) & 0xffffff);
            fprintf(stderr, " machl=%012llx\n", (unsigned long long)(machl & 0xffffffffffffULL));
        }
        static long itf = getenv("ESP_ITRACE") ? atol(getenv("ESP_ITRACE")) : -1;
        itrace = (itf >= 0 && frames >= itf && frames < itf + 2);
    }
    if (state == HALTED) {
        if (halt_asserted) { host_control &= ~0x04; return; }
        state = RUNNING; host_control |= 0x04; pc = 0;
        const bool selected_run = frame_trace_start_frame == 0 || frame_count == frame_trace_start_frame;
        trace_first_instruction = pipelog && selected_run;
        trace_selected_frame = pipelog && selected_run;
        frame_trace_remaining = selected_run ? frame_trace_limit : 0;
        frame_trace_index = 0;
        trace_output_pending = selected_run && frame_trace_remaining > 0;
        if (pipelog) {
            uint32_t unique = 0; int end_index = -1;
            for (int i = 0; i < 160; ++i) {
                if (load_instruction_addresses[i]) ++unique;
                if (end_index < 0 && ((instr[i] >> 12) & 0xf) == 0xf) end_index = i;
            }
            fprintf(stderr, "ESPPHASE kind=program_upload_summary frame=%llu cycles=%llu pc=%06x commits=%u unique_addresses=%u first_end=%d gpr_commits=%u\n",
                    (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc,
                    load_instruction_commits, unique, end_index, load_gpr_commits);
            fprintf(stderr, "ESPPHASE kind=run_start frame=%llu cycles=%llu host_pc=%06x pc=00 alu_pending=%u mac_pending=%u host_serial=%02x memshift=%d memsiz=%06x memmask=%06x memincrement=%06x dlength=%06x abase=%06x bbase=%06x dbase=%06x sigreg=%06x\n",
                    (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc,
                    (unsigned)alu.write_result, (unsigned)mulacc.write_result, host_serial, memshift,
                    memsiz & 0xffffff, memmask & 0xffffff, memincrement & 0xffffff, dlength & 0xffffff,
                    abase & 0xffffff, bbase & 0xffffff, dbase & 0xffffff, sigreg & 0xffffff);
        }
        if (run_snapshot_frame != 0 && frame_count == run_snapshot_frame && !run_snapshot_dir.empty()) {
            char path[4096];
            snprintf(path, sizeof(path), "%s/run-frame-%llu.esp", run_snapshot_dir.c_str(),
                     (unsigned long long)frame_count);
            FILE *capture = fopen(path, "wb");
            const bool ok = capture && write_capture(capture);
            if (capture) fclose(capture);
            if (pipelog)
                fprintf(stderr, "ESPPHASE kind=run_snapshot frame=%llu cycles=%llu host_pc=%06x pc=%02x ok=%u path=%s\n",
                        (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc, pc,
                        (unsigned)ok, path);
        }
    }
    const uint64_t trace_frame = diagnostic_frame++;
    if (pipelog && frame_trace_remaining > 0) {
        fprintf(stderr, "ESPPFRAME kind=input index=%u frame=%llu cycles=%llu host_pc=%06x serial=%02x lanes=%04x,%04x,%04x,%04x,%04x,%04x,%04x,%04x\n",
                frame_trace_index, (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc, host_serial,
                (uint16_t)ser[0], (uint16_t)ser[1], (uint16_t)ser[2], (uint16_t)ser[3],
                (uint16_t)ser[4], (uint16_t)ser[5], (uint16_t)ser[6], (uint16_t)ser[7]);
    }
    // Execute until END (bounded to the 160-instruction program store). One instruction cycle:
    // the RAM read issued two cycles ago lands in DIL; the previous instruction's multiplier
    // result is written; this instruction's multiplier operands are read; the previous
    // instruction's ALU result is written (and its flags); the skip test; this instruction's
    // ALU operands are read; the RAM cycle issued last cycle is done. The pipeline (pending
    // results, RAM cycles) is kept in local variables for the whole frame, and every register
    // read is one load from gpr[] (the special registers are kept there as copies).
    Ram r0 = ram, r1 = ram_p, r2 = ram_pp;
    // the pending multiplier and ALU operations: the dynamic part in locals, the rest is the decoded
    // instruction they came from (pm, pa); at the start of a frame, from the saved state
    bool mw = mulacc.write_result, aw = alu.write_result;
    int32_t mc = mulacc.cValue, md = mulacc.dValue, aa = alu.aValue, ab = alu.bValue;
    Dec pm0{}, pa0{};
    auto target = [](uint8_t r) -> uint16_t { return (r < 0xc0 || (r >= 234 && r <= 251)) ? r : TRASH; };
    auto from_saved = [&]() {
        pm0.cReg = mulacc.cReg; pm0.mac_dst = mulacc.dst; pm0.acc = mulacc.accumulate;
        pm0.mac_w = (pm0.mac_dst & REG) ? target(pm0.cReg) : TRASH;
        pa0.aReg = alu.aReg; pa0.op = alu.op; pa0.alu_dst = alu.dst;
        pa0.alu_w = ((pa0.alu_dst & REG) && pa0.op != 4) ? target(pa0.aReg) : TRASH;
        finish_dec(pm0); finish_dec(pa0);
        pa0.aupd = alu.update_ccr; pa0.upd[0] = pa0.aupd; pa0.upd[1] = pa0.aupd && pa0.alu_w != 0xfa;
    };
    from_saved();
    const Dec *pm = &pm0, *pa = &pa0;
    const int cww = ccr_write_wins ? 1 : 0;
    auto store = [&]() {
        ram = r0; ram_p = r1; ram_pp = r2;
        mulacc.write_result = mw; mulacc.accumulate = pm->acc; mulacc.cValue = mc; mulacc.dValue = md; mulacc.dst = pm->mac_dst; mulacc.cReg = pm->cReg;
        alu.write_result = aw; alu.update_ccr = pa->aupd; alu.op = pa->op; alu.dst = pa->alu_dst; alu.aReg = pa->aReg; alu.aValue = aa; alu.bValue = ab;
    };
    auto load = [&]() {
        r0 = ram; r1 = ram_p; r2 = ram_pp;
        mw = mulacc.write_result; mc = mulacc.cValue; md = mulacc.dValue;
        aw = alu.write_result; aa = alu.aValue; ab = alu.bValue;
        from_saved(); pm = &pm0; pa = &pa0;
    };
    // a result into a special register: the serial outputs inline (the common case), the others
    // through write_reg()
#define ESP_WRITE_SPECIAL(r, v) do { const uint16_t r_ = (r); \
        if (r_ >= 234 && r_ <= 241) { const int k_ = (r_ - 234) ^ 1; ser[k_] = (int16_t)((((v) & 0x00ffffff) >> 8) & 0xffff); gpr[r_] = (int32_t)((uint32_t)(uint16_t)ser[k_] << 8); } \
        else if (r_ == 242 || r_ == 243) { \
            if (r_ == 242) machl = sext48((machl & ((int64_t)0x00ffffff << 24)) | (int64_t)((v) & 0x00ffffff)); \
            else { machl = sext48((machl & (int64_t)0x00ffffff) | ((int64_t)((v) & 0x00ffffff) << 24)); mac_overflow = false; } \
            gpr[242] = mac_overflow ? (machl < 0 ? 0x00000000 : 0x00ffffff) : (int32_t)(machl & 0x00ffffff); \
            gpr[243] = mac_overflow ? (machl < 0 ? 0x00800000 : 0x007fffff) : (int32_t)((machl >> 24) & 0x00ffffff); } \
        else write_reg((uint8_t)r_, (v)); } while (0)
    for (int i = 0; i < 160 + 2; i++) {
        const uint8_t trace_pc = pc;
        const Dec &d = dec[pc];
        if (pipelog && trace_first_instruction) {
            fprintf(stderr, "ESPPHASE kind=first_instruction frame=%llu cycles=%llu host_pc=%06x pc=%02x word=%012llx\n",
                    (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc,
                    pc, (unsigned long long)(instr[pc] & 0xffffffffffffULL));
            trace_first_instruction = false;
        }
        int32_t trace_before[0x104];
        if (diagnostic_trace) {
            for (int ri = 0; ri < 0x104; ++ri) trace_before[ri] = gpr[ri];
            fprintf(diagnostic_trace, "I,%llu,%02x,%012llx\n", (unsigned long long)trace_frame,
                    pc, (unsigned long long)(instr[pc] & 0xffffffffffffULL));
        }
        // the RAM pipeline: the read issued two cycles ago arrives in DIL
        r2 = r1; r1 = r0;
        if (r2.cycle != WRITE) {
            dil = r2.io ? 0 : dram_r(r2.address);
            if (pipelog && frame_trace_remaining > 0)
                fprintf(stderr, "ESPRAM event=%llu kind=read frame=%llu pc=%02x io=%u address=%08x data=%04x\n",
                        (unsigned long long)++ram_trace_event, (unsigned long long)frame_count,
                        pc, (unsigned)r2.io, (unsigned)r2.address, (unsigned)(uint16_t)dil);
            gpr[244] = (int32_t)((uint32_t)(uint16_t)dil << 8);
            gpr[DIL_SRC] = (int32_t)((uint32_t)(uint16_t)dil << 8);
        }
        r0.cycle = (RamCycle)d.ram_cycle;
        r0.io = d.ram_io;
        const int32_t offset = gpr[pc];
        switch (d.ram_access) {           // (see step())
        case A_DELAY: {
            uint32_t len = ((uint32_t)dlength >> memshift) + 1;
            uint32_t w = ((uint32_t)dbase >> memshift) + ((uint32_t)(offset & 0x00ffffff) >> memshift);
            if (w >= len) { w -= len; if (w >= len) w %= len; }
            r0.address = (int32_t)w & (memmask >> memshift);
            break;
        }
        case A_TABLE_A: r0.address = (((abase & memmask) + offset) & memmask) >> memshift; break;
        case A_TABLE_B: r0.address = (((bbase & memmask) + offset) & memmask) >> memshift; break;
        default: r0.address = offset & 0x00fffff0; break;
        }
        if (diagnostic_trace) {
            fprintf(diagnostic_trace, "RQ,%llu,%02x,%u,%u,%08x\n", (unsigned long long)trace_frame,
                    pc, (unsigned)d.ram_cycle, (unsigned)d.ram_access, (unsigned)r0.address);
            if (r2.cycle != WRITE) fprintf(diagnostic_trace, "RR,%llu,%02x,%u,%08x,%04x\n",
                    (unsigned long long)trace_frame, pc, (unsigned)r2.io, (unsigned)r2.address,
                    (unsigned)(uint16_t)dil);
        }
        // the previous instruction's multiplier result
        if (mw) {
            mw = false;
            const int64_t prod = ((int64_t)sext24(mc) * (int64_t)sext24(md)) * (int64_t(1) << mulshift);
            const int64_t res = pm->acc ? prod + machl : prod;
            mac_overflow = (res < -((int64_t)1 << 47) || res >= ((int64_t)1 << 47));
            machl = res;
            const int32_t tmp = mac_overflow ? (machl < 0 ? 0x00800000 : 0x007fffff) : (int32_t)((res & 0x0000ffffff000000ULL) >> 24);
            gpr[242] = mac_overflow ? (machl < 0 ? 0x00000000 : 0x00ffffff) : (int32_t)(machl & 0x00ffffff);
            gpr[243] = tmp;
            if (!pm->mac_spec) gpr[pm->mac_w] = tmp & 0x00ffffff;   // (a GPR, or nowhere)
            else ESP_WRITE_SPECIAL(pm->mac_w, tmp);
            if (pm->mac_dst & DELAY) write_to_dol(tmp);
        }
        // this instruction's multiplier operands
        pm = &d;
        mc = gpr[d.c_src];
        md = gpr[d.dReg];
        // the previous instruction's ALU result
        if (aw) {
            aw = false;
            if (pa->op != 0xf) {
                uint8_t flags = ccr;
                const int32_t res = alu_operation(pa->op, aa, ab, flags);
                if (!pa->alu_spec) gpr[pa->alu_w] = res & 0x00ffffff;
                else ESP_WRITE_SPECIAL(pa->alu_w, res);
                if (pa->op != 4 && (pa->alu_dst & DELAY)) write_to_dol(res);
                if (pa->upd[cww]) { ccr = flags; gpr[250] = ccr << 16; }
            }
        }
        // the skip test, with the CCR the previous instruction left
        bool skip = false;
        if (d.skippable) {
            bool cond = (ccr & cmr & FLAG_MASK) != 0;
            if (isFlagSet(cmr, FLAG_NOT)) cond = !cond;
            skip = cond;
        }
        mw = !skip;
        pa = &d;
        aw = !skip || d.op == 4;
        if (d.op == 0xf) {
            if (trace_selected_frame)
                fprintf(stderr, "ESPPHASE kind=first_end frame=%llu cycles=%llu host_pc=%06x pc=%02x instructions=%u\n",
                        (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc,
                        trace_pc, (unsigned)(trace_pc + 1));
            alu_operation_end();
            if (diagnostic_trace && r1.cycle == WRITE && !r1.io && dol_count > 0)
                fprintf(diagnostic_trace, "RW,%llu,%02x,%08x,%04x\n", (unsigned long long)trace_frame,
                        pc, (unsigned)r1.address, (unsigned)(uint16_t)dol[0]);
            ram_write_cycle(r1);
            pc = 0;
            if (state == HALTED) { store(); drain_pipeline(); load(); }
            if (diagnostic_trace) {
                for (int ri = 0; ri < 0x104; ++ri) if (trace_before[ri] != gpr[ri])
                    fprintf(diagnostic_trace, "W,%llu,%02x,%03x,%06x\n", (unsigned long long)trace_frame,
                            trace_pc, ri, (unsigned)gpr[ri] & 0xffffff);
                fprintf(diagnostic_trace, "END,%llu,%02x\n", (unsigned long long)trace_frame, trace_pc);
            }
            break;                        // (END)
        }
        if (d.one_operand) ab = gpr[d.b1_src];
        else { aa = gpr[d.a_src]; ab = gpr[d.bReg]; }
        if (diagnostic_trace && r1.cycle == WRITE && !r1.io && dol_count > 0)
            fprintf(diagnostic_trace, "RW,%llu,%02x,%08x,%04x\n", (unsigned long long)trace_frame,
                    pc, (unsigned)r1.address, (unsigned)(uint16_t)dol[0]);
        ram_write_cycle(r1);
        if (diagnostic_trace) for (int ri = 0; ri < 0x104; ++ri) if (trace_before[ri] != gpr[ri])
            fprintf(diagnostic_trace, "W,%llu,%02x,%03x,%06x\n", (unsigned long long)trace_frame,
                    pc, ri, (unsigned)gpr[ri] & 0xffffff);
        if (++pc >= 160) pc = 0;
    }
#undef ESP_WRITE_SPECIAL
    if (trace_selected_frame) {
        fprintf(stderr, "ESPPHASE kind=first_frame_complete frame=%llu cycles=%llu host_pc=%06x pc=%02x\n",
                (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc, pc);
        trace_selected_frame = false;
    }
    store();
    if (pipelog && trace_output_pending) {
        fprintf(stderr, "ESPPFRAME kind=output index=%u frame=%llu cycles=%llu host_pc=%06x serial=%02x lanes=%04x,%04x,%04x,%04x,%04x,%04x,%04x,%04x\n",
                frame_trace_index, (unsigned long long)frame_count, (unsigned long long)host_cycles, host_pc, host_serial,
                (uint16_t)ser[0], (uint16_t)ser[1], (uint16_t)ser[2], (uint16_t)ser[3],
                (uint16_t)ser[4], (uint16_t)ser[5], (uint16_t)ser[6], (uint16_t)ser[7]);
        if (frame_trace_remaining > 0) --frame_trace_remaining;
        ++frame_trace_index;
        trace_output_pending = frame_trace_remaining > 0;
    }
}

// ---------------------------------------------------------------- debug listing
static const char *regname(uint8_t r, char *buf) {
    static const char *spr[] = { "SER0R","SER0L","SER1R","SER1L","SER2R","SER2L","SER3R","SER3L","MACL","MACH","DIL","DLEN","ABASE","BBASE","DBASE","SIGREG","CCR","CMR","M1","MIN","MAX","ZERO" };
    if (r < 0xc0) { snprintf(buf, 16, "g%02x", r); return buf; }
    if (r >= 234) return spr[r - 234];
    snprintf(buf, 16, "?%02x", r); return buf;
}
void ES5510::list_program(FILE *f) {
    static const char *alu[16] = { "ADD","SUB","ADDU","SUBU","CMP","AND","OR","XOR","ABS","MOV","ASL2","ASL8","LS15","DIFF","ASR","END" };
    static const char *ramc[8] = { "rdD","wrD","rdA","wrA","rdB","dumpD","rdIO","wrIO" };
    for (int pc = 0; pc < 160; pc++) {
        uint64_t in = instr[pc];
        char a[16], b[16], c[16], d[16], ad[16], cd[16];
        uint8_t op = (in >> 12) & 15, sel = (in >> 8) & 15;
        const OpSel &os = OPSEL[sel];
        fprintf(f, "%02x: %012llx gpr=%06x  %s %s%s,%s -> %s%s | MAC%s %s%s*%s -> %s%s | %s%s\n", pc, (unsigned long long)in, gpr[pc] & 0xffffff,
            alu[op], os.alu_src == DELAY ? "DIL" : "", os.alu_src == DELAY ? "" : regname((in >> 16) & 0xff, a), regname((in >> 24) & 0xff, b),
            (os.alu_dst & REG) ? regname((in >> 16) & 0xff, ad) : "", (os.alu_dst & DELAY) ? "+DOL" : "",
            ((in >> 6) & 1) ? "+" : "", os.mac_src == DELAY ? "DIL" : "", os.mac_src == DELAY ? "" : regname((in >> 32) & 0xff, c), regname((in >> 40) & 0xff, d),
            (os.mac_dst & REG) ? regname((in >> 32) & 0xff, cd) : "", (os.mac_dst & DELAY) ? "+DOL" : "",
            ramc[(in >> 3) & 7], (in & 0x80) ? " skip" : "");
        if (op == 15) break;
    }
    fprintf(f, "GPRs:");
    for (int i = 0; i < 0xc0; i++) { if (i % 16 == 0) fprintf(f, "\n  %02x:", i); fprintf(f, " %06x", gpr[i] & 0xffffff); }
    fprintf(f, "\nSER: 0L=%04x 0R=%04x 1L=%04x 1R=%04x 2L=%04x 2R=%04x 3L=%04x 3R=%04x ccr=%02x cmr=%02x machl=%012llx\n",
            ser[0] & 0xffff, ser[1] & 0xffff, ser[2] & 0xffff, ser[3] & 0xffff, ser[4] & 0xffff, ser[5] & 0xffff, ser[6] & 0xffff, ser[7] & 0xffff,
            ccr, cmr, (unsigned long long)(machl & 0xffffffffffffULL));
    {
        std::map<int16_t, int> h; for (auto v : dram) h[v]++;
        std::vector<std::pair<int, int16_t>> top; for (auto &kv : h) top.push_back({kv.second, kv.first});
        std::sort(top.rbegin(), top.rend());
        fprintf(f, "DRAM top values:"); for (size_t i = 0; i < top.size() && i < 8; i++) fprintf(f, " %04x x%d", (uint16_t)top[i].second, top[i].first);
        fprintf(f, "\n");
    }
    fprintf(f, "dlength=%06x memsiz shift=%d abase=%06x bbase=%06x dbase=%06x sigreg=%06x halted=%d host_serial=%02x\n", dlength, memshift, abase, bbase, dbase, sigreg, state == HALTED, host_serial);
}

// T551CAP v1. The file is a research snapshot, not a complete resumable CPU
// save state: it captures the full program, GPRs, special registers, host
// latches/control, serial/MAC state and the entire external ESP DRAM.
bool ES5510::write_capture(FILE *f) {
    if (!f || dram.size() > UINT32_MAX) return false;
    const uint32_t state_bytes = 74;
    const uint32_t payload_bytes = 160u * 6u + 192u * 3u + 22u * 3u + state_bytes +
        static_cast<uint32_t>(dram.size() * 2u);
    auto bytes = [&](const uint8_t *p, size_t n) { return fwrite(p, 1, n, f) == n; };
    auto u32le = [&](uint32_t v) {
        const uint8_t b[4] = { uint8_t(v), uint8_t(v >> 8), uint8_t(v >> 16), uint8_t(v >> 24) };
        return bytes(b, sizeof b);
    };
    auto u24be = [&](uint32_t v) {
        const uint8_t b[3] = { uint8_t(v >> 16), uint8_t(v >> 8), uint8_t(v) };
        return bytes(b, sizeof b);
    };
    auto u48be = [&](uint64_t v) {
        const uint8_t b[6] = { uint8_t(v >> 40), uint8_t(v >> 32), uint8_t(v >> 24),
                               uint8_t(v >> 16), uint8_t(v >> 8), uint8_t(v) };
        return bytes(b, sizeof b);
    };
    const uint8_t magic[8] = { 'E','S','5','5','1','0','C',0 };
    if (!bytes(magic, sizeof magic) || !u32le(1) || !u32le(44) || !u32le(160) ||
        !u32le(192) || !u32le(22) || !u32le(static_cast<uint32_t>(dram.size())) ||
        !u32le(1) || !u32le(state_bytes) || !u32le(payload_bytes)) return false;

    // Program words follow the exact six-byte host latch order, most-significant first.
    for (uint64_t word : instr) if (!u48be(word)) return false;
    for (int i = 0; i < 192; ++i) if (!u24be(static_cast<uint32_t>(gpr[i]))) return false;
    for (int i = 234; i < 256; ++i) if (!u24be(static_cast<uint32_t>(read_reg(static_cast<uint8_t>(i))))) return false;

    const uint8_t control[7] = { host_control, host_serial, ram_ctl,
        static_cast<uint8_t>(state == HALTED), static_cast<uint8_t>(halt_asserted), pc, refresh_pc };
    const uint8_t memory_config[4] = { static_cast<uint8_t>(memshift), 0, 0, 0 };
    if (!bytes(control, sizeof control) || !u32le(static_cast<uint32_t>(memsiz)) ||
        !u32le(static_cast<uint32_t>(memmask)) || !u32le(static_cast<uint32_t>(memincrement)) ||
        !u32le(dram_mask) || !bytes(memory_config, sizeof memory_config) ||
        !u24be(static_cast<uint32_t>(gpr_latch)) ||
        !u48be(instr_latch) || !u24be(dadr_latch) || !u24be(static_cast<uint32_t>(dol_latch)) ||
        !u24be(static_cast<uint32_t>(dil_latch))) return false;
    const uint32_t pending = static_cast<uint32_t>(read_pending);
    if (!u32le(pending)) return false;
    for (int16_t sample : ser) {
        const uint16_t v = static_cast<uint16_t>(sample);
        const uint8_t b[2] = { uint8_t(v), uint8_t(v >> 8) };
        if (!bytes(b, sizeof b)) return false;
    }
    const uint16_t dil_value = static_cast<uint16_t>(dil);
    const uint8_t dil_bytes[2] = { uint8_t(dil_value), uint8_t(dil_value >> 8) };
    const uint8_t overflow = mac_overflow ? 1 : 0;
    if (!bytes(dil_bytes, sizeof dil_bytes) || !u48be(static_cast<uint64_t>(machl)) ||
        !bytes(&overflow, 1)) return false;

    for (int16_t sample : dram) {
        const uint16_t v = static_cast<uint16_t>(sample);
        const uint8_t b[2] = { uint8_t(v), uint8_t(v >> 8) };
        if (!bytes(b, sizeof b)) return false;
    }
    return fflush(f) == 0;
}

bool ES5510::load_capture_after_pipeline_reset(FILE *f) {
    es5510_capture::State s;
    if (!es5510_capture::read(f, s)) return false;
    // The format omits in-flight ALU/MAC/RAM/DOL slots. This API therefore
    // always starts from the pipeline-reset state; callers must validate the
    // corresponding external HALT/reset evidence before using it.
    reset();
    for (int i=0; i<160; ++i) { instr[i]=s.instructions[i]; decode(i); }
    for (int i=0; i<192; ++i) gpr[i]=static_cast<int32_t>(s.gpr[i]);
    for (int i=234; i<256; ++i) gpr[i]=static_cast<int32_t>(s.spr[i-234]);
    const uint8_t* r=s.runtime.data();
    host_control=r[0]; host_serial=r[1]; ram_ctl=r[2];
    halt_asserted=r[4]!=0; state=r[3]?HALTED:RUNNING; pc=r[5]; refresh_pc=r[6];
    memsiz=static_cast<int32_t>(r[7] | (uint32_t(r[8])<<8) | (uint32_t(r[9])<<16) | (uint32_t(r[10])<<24));
    memmask=static_cast<int32_t>(r[11] | (uint32_t(r[12])<<8) | (uint32_t(r[13])<<16) | (uint32_t(r[14])<<24));
    memincrement=static_cast<int32_t>(r[15] | (uint32_t(r[16])<<8) | (uint32_t(r[17])<<16) | (uint32_t(r[18])<<24));
    dram_mask=r[19] | (uint32_t(r[20])<<8) | (uint32_t(r[21])<<16) | (uint32_t(r[22])<<24);
    memshift=static_cast<int8_t>(r[23]);
    auto be24=[&](int off) { return int32_t((uint32_t(r[off])<<16)|(uint32_t(r[off+1])<<8)|r[off+2]); };
    auto be48=[&](int off) { uint64_t v=0; for (int i=0;i<6;++i) v=(v<<8)|r[off+i]; return v; };
    gpr_latch=be24(27); instr_latch=be48(30); dadr_latch=be24(36); dol_latch=be24(39); dil_latch=be24(42);
    read_pending=static_cast<int32_t>(r[45] | (uint32_t(r[46])<<8) | (uint32_t(r[47])<<16) | (uint32_t(r[48])<<24));
    for (int i=0;i<8;++i) ser[i]=static_cast<int16_t>(uint16_t(r[49+2*i]) | (uint16_t(r[50+2*i])<<8));
    dil=static_cast<int16_t>(uint16_t(r[65]) | (uint16_t(r[66])<<8));
    machl=sext48(static_cast<int64_t>(be48(67))); mac_overflow=r[73]!=0;
    dlength=s.spr[245-234]; abase=s.spr[246-234]; bbase=s.spr[247-234]; dbase=s.spr[248-234];
    sigreg=s.spr[249-234]; mulshift=((sigreg>>22)&1)?1:2;
    ccr=static_cast<uint8_t>((s.spr[250-234]>>16)&FLAG_MASK);
    cmr=static_cast<uint8_t>((s.spr[251-234]>>16)&(FLAG_MASK|FLAG_NOT));
    for (std::size_t i=0;i<dram.size();++i) dram[i]=s.dram[i];
    ram=ram_p=ram_pp=Ram{}; alu=Alu{}; mulacc=Mac{}; dol[0]=dol[1]=0; dol_count=0;
    gpr[DIL_SRC]=static_cast<int32_t>((uint32_t)(uint16_t)dil<<8);
    return true;
}
