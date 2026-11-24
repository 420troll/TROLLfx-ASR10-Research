#pragma once

#include <array>
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <utility>
#include <vector>

// Private research checkpoint format emitted by ES5510::write_capture(). It
// contains the complete DSP-visible image and runtime latches, but not a live
// instruction pipeline. Callers must independently establish pipeline reset.
namespace es5510_capture {
struct State {
    std::array<std::uint64_t, 160> instructions{};
    std::array<std::uint32_t, 192> gpr{};
    std::array<std::uint32_t, 22> spr{};
    std::array<std::uint8_t, 74> runtime{};
    std::vector<std::int16_t> dram;
};

inline bool read(FILE* f, State& out) {
    if (!f) return false;
    auto read_exact = [f](void* p, std::size_t n) { return std::fread(p, 1, n, f) == n; };
    auto u32le = [&]() -> std::uint32_t {
        std::uint8_t b[4]{};
        if (!read_exact(b, sizeof b)) return UINT32_MAX;
        return std::uint32_t(b[0]) | (std::uint32_t(b[1]) << 8) |
               (std::uint32_t(b[2]) << 16) | (std::uint32_t(b[3]) << 24);
    };
    std::uint8_t magic[8]{};
    if (!read_exact(magic, sizeof magic) ||
        magic[0] != 'E' || magic[1] != 'S' || magic[2] != '5' || magic[3] != '5' ||
        magic[4] != '1' || magic[5] != '0' || magic[6] != 'C' || magic[7] != 0) return false;
    const auto version = u32le(), header = u32le(), ni = u32le(), ng = u32le();
    const auto ns = u32le(), nd = u32le(), flags = u32le(), nr = u32le(), payload = u32le();
    const std::uint32_t expected = 160u*6u + 192u*3u + 22u*3u + 74u + (1u<<20)*2u;
    if (version != 1 || header != 44 || ni != 160 || ng != 192 || ns != 22 ||
        nd != (1u<<20) || flags != 1 || nr != 74 || payload != expected) return false;
    std::array<std::uint8_t, 160*6> ib{};
    std::array<std::uint8_t, 192*3> gb{};
    std::array<std::uint8_t, 22*3> sb{};
    State parsed;
    if (!read_exact(ib.data(), ib.size()) || !read_exact(gb.data(), gb.size()) ||
        !read_exact(sb.data(), sb.size()) || !read_exact(parsed.runtime.data(), parsed.runtime.size())) return false;
    auto u24be = [](const std::uint8_t* p) {
        return (std::uint32_t(p[0])<<16) | (std::uint32_t(p[1])<<8) | p[2];
    };
    for (std::size_t i=0; i<parsed.instructions.size(); ++i) {
        std::uint64_t v=0;
        for (unsigned j=0; j<6; ++j) v=(v<<8)|ib[i*6+j];
        parsed.instructions[i]=v;
    }
    for (std::size_t i=0; i<parsed.gpr.size(); ++i) parsed.gpr[i]=u24be(&gb[i*3]);
    for (std::size_t i=0; i<parsed.spr.size(); ++i) parsed.spr[i]=u24be(&sb[i*3]);
    try { parsed.dram.resize(nd); } catch (...) { return false; }
    std::array<std::uint8_t, 8192> chunk{};
    std::size_t pos=0;
    while (pos < nd) {
        const std::size_t words = std::min<std::size_t>(chunk.size()/2, nd-pos);
        if (!read_exact(chunk.data(), words*2)) return false;
        for (std::size_t i=0; i<words; ++i) {
            const auto u=std::uint16_t(chunk[i*2]) | (std::uint16_t(chunk[i*2+1])<<8);
            parsed.dram[pos+i]=static_cast<std::int16_t>(u);
        }
        pos += words;
    }
    if (std::fgetc(f) != EOF) return false;
    out=std::move(parsed);
    return true;
}
} // namespace es5510_capture
