#include "wav_io.h"
#include "experimental_audio_host.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <limits>

namespace trollfx::audio {
namespace {
uint16_t u16(const uint8_t* p) { return static_cast<uint16_t>(p[0] | (uint16_t(p[1]) << 8)); }
uint32_t u32(const uint8_t* p) { return uint32_t(p[0]) | (uint32_t(p[1]) << 8) |
                                      (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24); }
void put16(std::ostream& f, uint16_t v) { char b[2] = {char(v), char(v >> 8)}; f.write(b, 2); }
void put32(std::ostream& f, uint32_t v) { char b[4] = {char(v), char(v >> 8), char(v >> 16), char(v >> 24)}; f.write(b, 4); }
float signed_pcm(const uint8_t* p, uint16_t bits) {
    if (bits == 16) return static_cast<int16_t>(u16(p)) / 32768.0f;
    if (bits == 24) {
        int32_t x = int32_t(p[0]) | (int32_t(p[1]) << 8) | (int32_t(p[2]) << 16);
        if (x & 0x800000) x |= ~0xffffff;
        return static_cast<float>(x) / 8388608.0f;
    }
    return static_cast<int32_t>(u32(p)) / 2147483648.0f;
}
}

bool read_stereo_wav(const std::string& path, WavData& wav, std::string& error) {
    std::ifstream f(path, std::ios::binary | std::ios::ate);
    if (!f) { error = "cannot open input WAV: " + path; return false; }
    const auto end = f.tellg();
    if (end < 12 || static_cast<uint64_t>(end) > (1ull << 34)) { error = "invalid or oversized WAV"; return false; }
    std::vector<uint8_t> bytes(static_cast<size_t>(end));
    f.seekg(0); f.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    if (!f || std::memcmp(bytes.data(), "RIFF", 4) || std::memcmp(bytes.data() + 8, "WAVE", 4)) {
        error = "input must be a little-endian RIFF/WAVE file"; return false;
    }
    uint16_t format = 0, channels = 0, bits = 0, align = 0;
    uint32_t rate = 0;
    const uint8_t* data = nullptr; size_t data_size = 0;
    size_t off = 12;
    while (off + 8 <= bytes.size()) {
        const uint8_t* h = bytes.data() + off;
        const uint32_t size = u32(h + 4);
        const size_t start = off + 8;
        if (size > bytes.size() - start) { error = "WAV chunk extends past end of file"; return false; }
        if (!std::memcmp(h, "fmt ", 4)) {
            if (size < 16) { error = "WAV fmt chunk is too short"; return false; }
            format = u16(bytes.data() + start); channels = u16(bytes.data() + start + 2);
            rate = u32(bytes.data() + start + 4); align = u16(bytes.data() + start + 12);
            bits = u16(bytes.data() + start + 14);
            if (format == 0xfffe && size >= 40) format = u16(bytes.data() + start + 24);
        } else if (!std::memcmp(h, "data", 4)) {
            data = bytes.data() + start; data_size = size;
        }
        const size_t padded = static_cast<size_t>(size) + (size & 1u);
        if (padded > bytes.size() - start) break;
        off = start + padded;
    }
    if (!data || !rate || channels != 2 || (format != 1 && format != 3)) {
        error = "input WAV must contain stereo PCM or IEEE float samples"; return false;
    }
    if (!((format == 1 && (bits == 16 || bits == 24 || bits == 32)) || (format == 3 && bits == 32))) {
        error = "supported WAV encodings are PCM16/24/32 and IEEE float32"; return false;
    }
    const uint16_t bytes_per_sample = bits / 8;
    if (align != bytes_per_sample * 2 || data_size % align) { error = "invalid WAV block alignment or data length"; return false; }
    const size_t count = data_size / align;
    wav.sample_rate = rate; wav.format = format; wav.bits_per_sample = bits;
    wav.frames.resize(count);
    for (size_t i = 0; i < count; ++i) {
        const uint8_t* p = data + i * align;
        float l, r;
        if (format == 3) {
            std::memcpy(&l, p, 4); std::memcpy(&r, p + 4, 4);
            if (!std::isfinite(l)) l = 0.0f;
            if (!std::isfinite(r)) r = 0.0f;
        } else {
            l = signed_pcm(p, bits); r = signed_pcm(p + bytes_per_sample, bits);
        }
        wav.frames[i] = {l, r};
    }
    return true;
}

bool write_stereo_pcm16_wav(const std::string& path, uint32_t rate,
                            const std::vector<StereoFrame>& frames, std::string& error) {
    if (!rate || frames.size() > (std::numeric_limits<uint32_t>::max() - 36u) / 4u) {
        error = "output WAV exceeds RIFF PCM16 size limit"; return false;
    }
    std::ofstream f(path, std::ios::binary | std::ios::trunc);
    if (!f) { error = "cannot open output WAV: " + path; return false; }
    const uint32_t data_bytes = static_cast<uint32_t>(frames.size() * 4);
    f.write("RIFF", 4); put32(f, 36 + data_bytes); f.write("WAVEfmt ", 8);
    put32(f, 16); put16(f, 1); put16(f, 2); put32(f, rate);
    put32(f, rate * 4); put16(f, 4); put16(f, 16); f.write("data", 4); put32(f, data_bytes);
    for (const auto& frame : frames) {
        put16(f, static_cast<uint16_t>(float_to_pcm16(frame.left)));
        put16(f, static_cast<uint16_t>(float_to_pcm16(frame.right)));
    }
    if (!f) { error = "failed while writing output WAV"; return false; }
    return true;
}
} // namespace trollfx::audio
