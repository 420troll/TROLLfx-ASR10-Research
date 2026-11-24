#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace trollfx::audio {

struct StereoFrame { float left = 0.0f, right = 0.0f; };

struct WavData {
    uint32_t sample_rate = 0;
    uint16_t format = 0, bits_per_sample = 0;
    std::vector<StereoFrame> frames;
};

bool read_stereo_wav(const std::string& path, WavData& wav, std::string& error);
bool write_stereo_pcm16_wav(const std::string& path, uint32_t sample_rate,
                            const std::vector<StereoFrame>& frames, std::string& error);

} // namespace trollfx::audio
