// Headless runner for the ASR-10 emulator: boots, optionally plays MIDI events,
// renders audio to a WAV file and prints the display.
#include "asr10.h"
#include "efe_disk.h"
#include <cstdio>
#include <chrono>
#if defined(__has_include)
#if __has_include(<valgrind/callgrind.h>)
#include <valgrind/callgrind.h>
#define ESP_BENCH_START() CALLGRIND_START_INSTRUMENTATION
#define ESP_BENCH_STOP() CALLGRIND_STOP_INSTRUMENTATION
#endif
#endif
#ifndef ESP_BENCH_START
#define ESP_BENCH_START()
#define ESP_BENCH_STOP()
#endif
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <sstream>
#include <algorithm>
extern "C" {
#include "m68k.h"
}

static void write_wav(const char *path, const std::vector<float> &a, int rate) {
    FILE *f = fopen(path, "wb"); if (!f) return;
    uint32_t n = (uint32_t)a.size();
    uint32_t datasz = n * 2;
    auto w32 = [&](uint32_t v) { fwrite(&v, 4, 1, f); };
    auto w16 = [&](uint16_t v) { fwrite(&v, 2, 1, f); };
    fwrite("RIFF", 1, 4, f); w32(36 + datasz); fwrite("WAVEfmt ", 1, 8, f);
    w32(16); w16(1); w16(2); w32(rate); w32(rate * 4); w16(4); w16(16);
    fwrite("data", 1, 4, f); w32(datasz);
    for (float x : a) { int v = (int)(x * 32767.0f); if (v > 32767) v = 32767; if (v < -32768) v = -32768; w16((uint16_t)(int16_t)v); }
    fclose(f);
}

int main(int argc, char **argv) {
    std::string rom_dir = "roms"; bool lo_set = false, hi_set = false;
    std::string lo = "roms/asr_lo.bin", hi = "roms/asr_hi.bin", disk, wav, aux_wav, esp_dump, esp_rom_dir;
    bool m_aux_flag[3] = { true, true, true };   // AUX1-3 mixed into the main outputs
    double seconds = 10;
    bool write_back = false;
    std::vector<std::string> scsi_dirs, scsi_specs; bool scsi_log = false, no_scsi = false;
    std::vector<std::pair<int,int>> analog_init;
    std::vector<std::pair<double,std::pair<int,int>>> patchev;
    std::vector<std::pair<double, std::pair<int,int>>> analog_at;
    bool trace_io = false, trace_esp_io = false, panel_log = false, fdc_log = false, trap_log = false, pc_hist = false;
    bool log_rom_select = false;
    std::vector<std::pair<double, std::vector<uint8_t>>> midi;   // time, bytes
    std::vector<std::pair<double, std::pair<int,int>>> buttons;  // time, (code, down)
    std::vector<std::pair<double, std::string>> parameter_marks;
    struct PanelAction {
        enum class Kind { TapOnChange, TapOnDisplay, MarkOnDisplay, WalkRight, SearchRight, ProbeControl, ProbeRange } kind;
        double after = 0.0, timeout = 0.0, pressed_at = 0.0, phase_time = 0.0;
        std::string needle, id, target, last_match, before_display, control_baseline;
        int code = 0, revert_code = 11, match_stable = 0, change_stable = 0, remaining_steps = 0, step_index = 0;
        int repetitions = 0, iteration = 0, phase = 0, range_steps_up = 0, range_steps_down = 0;
        int range_steps_origin = 0, range_steps_return = 0;
        bool down_sent = false, started = false, done = false, probe_key_released = false;
    };
    std::vector<PanelAction> panel_actions;
    bool panel_action_failed = false;
    int ram_mb = 16;   // maximum memory expansion (2 MB = base unit)
    std::vector<std::pair<uint32_t, int>> trace_pcs;
    std::vector<uint32_t> breaks;
    std::vector<std::pair<double, std::pair<int,int>>> keys;
    std::vector<std::pair<double, std::string>> inserts;
    std::vector<std::pair<double, std::pair<int,int>>> raws;
    double trace_after = 0;
    uint32_t trace_pc = 0xffffffff; int trace_cnt = 0; bool tracing = false;
    std::string dump_ram; bool rack_panel = false;
    bool esp_list = false, otto_dump = false;
    uint32_t dis_addr = 0; int dis_n = 0;
    uint32_t hex_addr = 0; int hex_len = 0;
    struct Tone { double t, f, amp, dur; char side; };
    std::vector<Tone> tones;
    struct DTone { double t, f, amp, dur, rate; };
    std::vector<DTone> dtones;
    bool di10 = false;
    std::string dig_wav;
    std::string in_wav; double in_wav_t = 0;
    bool dac_ideal = false;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        auto next = [&]() { return std::string(i + 1 < argc ? argv[++i] : ""); };
        if (a == "--lo") { lo = next(); lo_set = true; }
        else if (a == "--hi") { hi = next(); hi_set = true; }
        else if (a == "--roms") rom_dir = next();
        else if (a == "--disk") disk = next();
        else if (a == "--seconds") seconds = atof(next().c_str());
        else if (a == "--aux-wav") { aux_wav = next(); for (auto &x : m_aux_flag) x = false; }
        else if (a == "--wav") wav = next();
        else if (a == "--dac") dac_ideal = next() == "ideal";   // tda1541a (default) | ideal
        else if (a == "--ram") ram_mb = atoi(next().c_str());
        else if (a == "--trace-io") trace_io = true;
        else if (a == "--trace-esp-io") trace_esp_io = true;
        else if (a == "--write-back") write_back = true;
        else if (a == "--scsi-dir") scsi_dirs.push_back(next());
        else if (a == "--scsi") scsi_specs.push_back(next());     // id:path[:cd]
        else if (a == "--scsi-log") scsi_log = true;
        else if (a == "--no-scsi") no_scsi = true;
        else if (a == "--analog-at") { double t; int ch, v; if (sscanf(next().c_str(), "%lf:%d:%d", &t, &ch, &v) == 3 && ch >= 0 && ch < 8) analog_at.push_back({t, {ch, v}}); }
        else if (a == "--analog") { int ch, v; if (sscanf(next().c_str(), "%d:%d", &ch, &v) == 2 && ch >= 0 && ch < 8) analog_init.push_back({ch, v}); }
        else if (a == "--panel-log") panel_log = true;
        else if (a == "--log-rom-select") log_rom_select = true;
        else if (a == "--fdc-log") fdc_log = true;
        else if (a == "--trap-log") trap_log = true;
        else if (a == "--dump-ram") dump_ram = next();
        else if (a == "--esp-list") esp_list = true;
        else if (a == "--esp-dump") esp_dump = next();
        else if (a == "--esp-snapshot-rom-dir") esp_rom_dir = next(); // snapshot each stable ROM display ID once
        else if (a == "--rack") rack_panel = true;
        else if (a == "--otto-dump") otto_dump = true;
        else if (a == "--dis") { dis_addr = strtoul(next().c_str(), 0, 16); dis_n = atoi(next().c_str()); }
        else if (a == "--pc-hist") pc_hist = true;
        else if (a == "--input-tone") {  // t:freq:amp:dur[:L|R]  sine into the audio input
            std::string v = next(); double t, f, am, d; char side = 'B';
            if (sscanf(v.c_str(), "%lf:%lf:%lf:%lf:%c", &t, &f, &am, &d, &side) >= 4) tones.push_back({t, f, am, d, side});
        }
        else if (a == "--di10") di10 = true;       // DI-10 Digital I/O board fitted
        else if (a == "--digital-tone") {  // t:freq:amp:dur[:rate]  sine into the S/PDIF input (DI-10)
            std::string v = next(); DTone d{0, 0, 0, 0, 48000};
            if (sscanf(v.c_str(), "%lf:%lf:%lf:%lf:%lf", &d.t, &d.f, &d.amp, &d.dur, &d.rate) >= 4) dtones.push_back(d);
            di10 = true;
        }
        else if (a == "--digital-wav") { dig_wav = next(); di10 = true; }   // S/PDIF output to a WAV file
        else if (a == "--input-wav") {   // t:file.wav (16-bit PCM)
            std::string v = next(); size_t c = v.find(':');
            if (c != std::string::npos) { in_wav_t = atof(v.substr(0, c).c_str()); in_wav = v.substr(c + 1); }
        }
        else if (a == "--hexdump") { hex_addr = strtoul(next().c_str(), 0, 16); hex_len = atoi(next().c_str()); }
        else if (a == "--break") breaks.push_back(strtoul(next().c_str(), 0, 16));
        else if (a == "--trace-after") trace_after = atof(next().c_str());
        else if (a == "--trace-from") { trace_pc = strtoul(next().c_str(), 0, 16); trace_cnt = atoi(next().c_str()); }
        else if (a == "--note") {   // --note time:note:vel:dur
            double t; int n, v, ch = 1; double d;
            if (sscanf(next().c_str(), "%lf:%d:%d:%lf:%d", &t, &n, &v, &d, &ch) >= 4) {   // [:channel]
                midi.push_back({t, {(uint8_t)(0x90 | ((ch - 1) & 15)), (uint8_t)n, (uint8_t)v}});
                midi.push_back({t + d, {(uint8_t)(0x80 | ((ch - 1) & 15)), (uint8_t)n, 0x40}});
            }
        } else if (a == "--patch") {   // --patch time:0|1:down  Patch Select left/right
            double t; int i, d; if (sscanf(next().c_str(), "%lf:%d:%d", &t, &i, &d) == 3) patchev.push_back({t, {i, d}});
        } else if (a == "--cc") {      // --cc time:controller:value[:channel]  MIDI control change
            double t; int c, v, ch = 1;
            if (sscanf(next().c_str(), "%lf:%d:%d:%d", &t, &c, &v, &ch) >= 3) midi.push_back({t, {(uint8_t)(0xb0 | ((ch - 1) & 15)), (uint8_t)c, (uint8_t)v}});
        } else if (a == "--key") {   // --key time:note:vel:dur (panel keyboard, note 36..96)
            double t; int n, v; double d;
            if (sscanf(next().c_str(), "%lf:%d:%d:%lf", &t, &n, &v, &d) == 4) {
                keys.push_back({t, {n, v}}); keys.push_back({t + d, {n, -v}});
            }
        } else if (a == "--insert") {  // time:path  (disk inserted while running)
            std::string v = next(); size_t c = v.find(':');
            if (c != std::string::npos) inserts.push_back({atof(v.substr(0, c).c_str()), v.substr(c + 1)});
        } else if (a == "--panel-raw") {  // time:b1:b2 (hex) raw panel->CPU message
            double t; unsigned b1, b2;
            if (sscanf(next().c_str(), "%lf:%x:%x", &t, &b1, &b2) == 3) raws.push_back({t, {(int)b1, (int)b2}});
        } else if (a == "--eject") {
            inserts.push_back({atof(next().c_str()), ""});
        } else if (a == "--button") {  // time:code:down
            double t; int c, d;
            if (sscanf(next().c_str(), "%lf:%d:%d", &t, &c, &d) == 3) buttons.push_back({t, {c, d}});
        } else if (a == "--param-mark") { // time:label
            std::string v = next(); size_t c = v.find(':');
            if (c != std::string::npos) parameter_marks.push_back({atof(v.substr(0, c).c_str()), v.substr(c + 1)});
        } else if (a == "--panel-tap-on-change" || a == "--panel-tap-on-display" || a == "--panel-mark-on-display" || a == "--panel-walk-right" || a == "--panel-search-right" || a == "--panel-probe-control" || a == "--panel-probe-range") {
            const bool tap = a == "--panel-tap-on-change" || a == "--panel-tap-on-display";
            const bool walk = a == "--panel-walk-right";
            const bool search = a == "--panel-search-right";
            const bool probe = a == "--panel-probe-control";
            const bool range = a == "--panel-probe-range";
            std::stringstream fields(next()); std::vector<std::string> part; std::string field;
            while (std::getline(fields, field, ',')) part.push_back(field);
            const size_t expected = probe ? (part.size() == 6 ? 6 : 5) : (tap || walk) ? 5 : search ? 6 : 4;
            if (part.size() != expected) { fprintf(stderr, "invalid %s field count\n", a.c_str()); return 2; }
            PanelAction action; action.kind = a == "--panel-tap-on-change" ? PanelAction::Kind::TapOnChange :
                a == "--panel-tap-on-display" ? PanelAction::Kind::TapOnDisplay :
                a == "--panel-walk-right" ? PanelAction::Kind::WalkRight :
                search ? PanelAction::Kind::SearchRight :
                probe ? PanelAction::Kind::ProbeControl : range ? PanelAction::Kind::ProbeRange : PanelAction::Kind::MarkOnDisplay;
            action.after = atof(part[0].c_str()); action.timeout = atof(part[1].c_str());
            if (action.after < 0.0 || action.timeout <= 0.0) { fprintf(stderr, "invalid %s time\n", a.c_str()); return 2; }
            if (tap) {
                action.code = atoi(part[2].c_str()); action.needle = part[3]; action.id = part[4];
                if (action.code < 0 || action.code > 41) { fprintf(stderr, "invalid panel button code\n"); return 2; }
            } else if (walk) {
                action.remaining_steps = atoi(part[2].c_str()); action.needle = part[3]; action.id = part[4];
                if (action.remaining_steps < 1 || action.remaining_steps > 256) { fprintf(stderr, "invalid panel walk count\n"); return 2; }
            } else if (search) {
                action.remaining_steps = atoi(part[2].c_str()); action.needle = part[3]; action.target = part[4]; action.id = part[5];
                if (action.remaining_steps < 1 || action.remaining_steps > 256 || action.target.empty()) { fprintf(stderr, "invalid panel search target/count\n"); return 2; }
            } else if (probe) {
                action.repetitions = atoi(part[2].c_str()); action.needle = part[3]; action.id = part[4];
                if (action.repetitions < 0 || action.repetitions > 4) { fprintf(stderr, "invalid panel probe repetitions\n"); return 2; }
                if (part.size() == 6) action.revert_code = atoi(part[5].c_str());
                if (action.revert_code < 0 || action.revert_code > 41) { fprintf(stderr, "invalid panel probe revert button\n"); return 2; }
            } else { action.needle = part[2]; action.id = part[3]; }
            if (action.needle.empty() || action.id.empty()) { fprintf(stderr, "empty panel condition/action id\n"); return 2; }
            panel_actions.push_back(std::move(action));
        }
    }
    Asr10 m;
    m.dac.set_model(dac_ideal ? DacOut::IDEAL : DacOut::TDA1541A);
    m.set_ram_mb(ram_mb);
    for (int i = 0; i < 3; i++) m.aux_to_main[i] = m_aux_flag[i];
    bool rom_ok = (lo_set || hi_set) ? m.load_rom(lo, hi) : (m.load_rom_dir(rom_dir) || m.load_rom(lo, hi));
    if (!rom_ok) { fprintf(stderr, "cannot load ROM %s / %s\n", lo.c_str(), hi.c_str()); return 1; }
    if (!disk.empty() && !m.fdc.load(disk)) { fprintf(stderr, "cannot load disk %s\n", disk.c_str()); return 1; }
    m.trace_io = trace_io;
    m.trace_esp_io = trace_esp_io;
    m.panel.log = panel_log;
    m.panel.rack = rack_panel;
    m.fdc.log = fdc_log;
    m.di10 = di10;
    m.reset();
    m.scsi_fitted = !no_scsi;
    m.scsi.log = scsi_log;
    for (auto &d : scsi_dirs) fprintf(stderr, "%s", m.scsi.attach_dir(d).c_str());
    for (auto &sp : scsi_specs) {
        int id = atoi(sp.c_str()); size_t c = sp.find(':');
        std::string path = c == std::string::npos ? "" : sp.substr(c + 1);
        bool cd = path.size() > 3 && path.substr(path.size() - 3) == ":cd";
        if (cd) path.resize(path.size() - 3);
        if (!m.scsi.attach(id, path, cd ? ScsiDevice::CD : ScsiDevice::HD)) fprintf(stderr, "cannot attach SCSI %s\n", sp.c_str());
        else fprintf(stderr, "SCSI ID %d: %s\n", id, m.scsi.dev[id]->describe().c_str());
    }
    for (auto &a : analog_init) m.analog[a.first] = a.second;
    // optional WAV for the audio input
    std::vector<float> wav_in; double wav_in_rate = 44100; size_t wav_in_pos = 0;
    if (!in_wav.empty()) {
        FILE *f = fopen(in_wav.c_str(), "rb");
        if (f) {
            std::vector<uint8_t> d; uint8_t buf[65536]; size_t n;
            while ((n = fread(buf, 1, sizeof buf, f)) > 0) d.insert(d.end(), buf, buf + n);
            fclose(f);
            size_t p = 12; int chn = 2, bits = 16;
            while (p + 8 <= d.size()) {
                uint32_t sz = d[p+4] | d[p+5] << 8 | d[p+6] << 16 | (uint32_t)d[p+7] << 24;
                if (!memcmp(&d[p], "fmt ", 4)) { chn = d[p+10] | d[p+11] << 8; wav_in_rate = d[p+12] | d[p+13] << 8 | d[p+14] << 16; bits = d[p+22]; }
                if (!memcmp(&d[p], "data", 4) && bits == 16) {
                    for (size_t i = p + 8; i + 2 * chn <= p + 8 + sz && i + 2 * chn <= d.size(); i += 2 * chn) {
                        int16_t l = (int16_t)(d[i] | d[i+1] << 8), r = chn > 1 ? (int16_t)(d[i+2] | d[i+3] << 8) : l;
                        wav_in.push_back(l / 32768.0f); wav_in.push_back(r / 32768.0f);
                    }
                }
                p += 8 + sz + (sz & 1);
            }
            fprintf(stderr, "input wav: %zu frames at %.0f Hz\n", wav_in.size() / 2, wav_in_rate);
        } else fprintf(stderr, "cannot open %s\n", in_wav.c_str());
    }
    std::map<uint32_t, uint64_t> hist;
    static uint32_t ring[64]; static int rp = 0;
    if (trap_log || pc_hist || !breaks.empty() || trace_cnt) m.on_instr = [&](uint32_t pc) {
        pc &= 0xffffff;
        if ((pc == trace_pc || trace_pc == 1) && m.cycles() / m.cpu_clock >= trace_after) tracing = true;
        if (tracing && trace_cnt > 0) {
            char buf[128]; m68k_disassemble(buf, pc, M68K_CPU_TYPE_68000);
            fprintf(stderr, "T %06x: %-40s D0=%08x D1=%08x D2=%08x D3=%08x A0=%08x\n", pc, buf, m68k_get_reg(NULL, M68K_REG_D0), m68k_get_reg(NULL, M68K_REG_D1), m68k_get_reg(NULL, M68K_REG_D2), m68k_get_reg(NULL, M68K_REG_D3), m68k_get_reg(NULL, M68K_REG_A0));
            if (--trace_cnt == 0) tracing = false;
        }
        ring[rp++ & 63] = pc;
        for (auto b : breaks) if (pc == b && m.cycles() / m.cpu_clock >= trace_after) {
            fprintf(stderr, "[BREAK] %06x t=%.4f SR=%04x SP=%08x USP=%08x\n", pc, m.cycles() / m.cpu_clock, m68k_get_reg(NULL, M68K_REG_SR), m68k_get_reg(NULL, M68K_REG_SP), m68k_get_reg(NULL, M68K_REG_USP));
            for (int r = 0; r < 8; r++) fprintf(stderr, "  D%d=%08x A%d=%08x\n", r, m68k_get_reg(NULL, (m68k_register_t)(M68K_REG_D0 + r)), r, m68k_get_reg(NULL, (m68k_register_t)(M68K_REG_A0 + r)));
            uint32_t sp = m68k_get_reg(NULL, M68K_REG_SP);
            fprintf(stderr, "  stack:"); for (int k = 0; k < 16; k++) fprintf(stderr, " %04x", m.read(sp + k * 2, 2)); fprintf(stderr, "\n");
            uint32_t usp = m68k_get_reg(NULL, M68K_REG_USP);
            fprintf(stderr, "  ustack:"); for (int k = 0; k < 24; k++) fprintf(stderr, " %04x", m.read(usp + k * 2, 2)); fprintf(stderr, "\n");
            fprintf(stderr, "  recent pcs:"); for (int k = 0; k < 64; k++) fprintf(stderr, " %06x", ring[(rp + k) & 63]); fprintf(stderr, "\n");
        }
        if (pc_hist && m.cycles() / m.cpu_clock >= trace_after) hist[pc & ~0xf]++;
        if (trap_log) {
            uint16_t op = m.read(pc, 2);
            if ((op & 0xfff0) == 0x4e40 && (op & 15) == 0)
                fprintf(stderr, "[TRAP0] pc=%06x D0=%08x t=%.3f\n", pc, m68k_get_reg(NULL, M68K_REG_D0), m.cycles() / m.cpu_clock);
        }
    };
    m.midi_out = [](uint8_t b) { fprintf(stderr, "[MIDI OUT] %02x\n", b); };
    std::sort(midi.begin(), midi.end(), [](auto &x, auto &y) { return x.first < y.first; });
    size_t mi = 0, bi = 0, ki = 0, pmi = 0;
    std::sort(keys.begin(), keys.end(), [](auto &x, auto &y) { return x.first < y.first; });
    const int64_t slice = 16000;  // 1 ms
    int64_t total = (int64_t)(seconds * m.cpu_clock);
    std::string last0, last1;
    int stable_display_slices = 0;
    std::set<int> rom_snapshots;
    std::string last_rom_selection;
    const long experiment_capture_id = std::getenv("ESP_EXPERIMENT_CAPTURE_ROM_ID")
        ? std::strtol(std::getenv("ESP_EXPERIMENT_CAPTURE_ROM_ID"), nullptr, 10) : -1;
    std::set<long> experiment_capture_ids;
    if (const char *ids = std::getenv("ESP_EXPERIMENT_CAPTURE_ROM_IDS")) {
        std::stringstream values(ids); std::string value;
        while (std::getline(values, value, ',')) {
            char *end = nullptr; long id = std::strtol(value.c_str(), &end, 10);
            if (end != value.c_str() && *end == '\0' && id > 0 && id <= 999) experiment_capture_ids.insert(id);
        }
    }
    if (experiment_capture_id > 0) experiment_capture_ids.insert(experiment_capture_id);
    const uint32_t experiment_capture_words = std::getenv("ESP_EXPERIMENT_CAPTURE_WORDS")
        ? (uint32_t)std::strtoul(std::getenv("ESP_EXPERIMENT_CAPTURE_WORDS"), nullptr, 10) : 0;
    long experiment_capture_armed_id = -1;
    std::set<long> experiment_capture_completed_ids;
    for (int64_t t = 0; t < total; t += slice) {
        double now = t / m.cpu_clock;
        while (mi < midi.size() && midi[mi].first <= now) { for (auto b : midi[mi].second) m.midi_in(b); mi++; }
        while (ki < keys.size() && keys[ki].first <= now) { auto &k = keys[ki].second; m.panel.key(k.first - 36, k.second < 0 ? -k.second : k.second, k.second > 0); ki++; }
        while (bi < buttons.size() && buttons[bi].first <= now) {
            int idx = buttons[bi].second.first;
            if (idx == 40 || idx == 41) m.audio_button[idx - 40] = buttons[bi].second.second;   // Audio Track A/B
            else m.panel.button(idx, buttons[bi].second.second);
            bi++;
        }
        while (pmi < parameter_marks.size() && parameter_marks[pmi].first <= now) {
            fprintf(stderr, "PARAMMARK label=%s cycles=%llu frame=%llu\n", parameter_marks[pmi].second.c_str(),
                    (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
            ++pmi;
        }
        for (auto &ins : inserts) if (ins.first >= 0 && ins.first <= now) {
            if (!ins.second.empty() && efe::is_single_file(ins.second)) {   // .efa/.efe: on a temporary floppy
                std::string path, label, err = efe::make_disk_file({ ins.second }, true, "asr10-cli-", path, label);
                if (!err.empty()) fprintf(stderr, "%s\n", err.c_str()); else ins.second = path;
            }
            if (ins.second.empty()) m.eject_disk(); else m.insert_disk(ins.second);
            ins.first = -1;
        }
        {   // audio input for this slice
            double sl = slice / m.cpu_clock;
            static double in_acc = 0;
            in_acc += 44100 * sl;
            int nfr = (int)in_acc; in_acc -= nfr;
            static std::vector<float> buf; buf.assign(nfr * 2, 0.0f);
            bool any = false;
            for (auto &tn : tones) if (now >= tn.t && now < tn.t + tn.dur) {
                any = true;
                for (int i = 0; i < nfr; i++) {
                    double tt = now - tn.t + i / 44100.0;
                    float v = (float)(tn.amp * sin(2 * M_PI * tn.f * tt));
                    if (tn.side != 'R') buf[i * 2] += v;
                    if (tn.side != 'L') buf[i * 2 + 1] += v;
                }
            }
            if (!wav_in.empty() && now >= in_wav_t) {
                int nw = (int)(wav_in_rate * sl + 0.5);
                if (wav_in_pos < wav_in.size()) {
                    size_t take = std::min((size_t)nw * 2, wav_in.size() - wav_in_pos);
                    m.feed_input(&wav_in[wav_in_pos], take / 2, wav_in_rate);
                    wav_in_pos += take;
                }
            } else if (any) m.feed_input(buf.data(), nfr, 44100);
            for (auto &d : dtones) if (now >= d.t && now < d.t + d.dur) {   // S/PDIF input
                static double dacc = 0; static double ph = 0;
                dacc += d.rate * sl;
                int n = (int)dacc; dacc -= n;
                std::vector<float> db((size_t)n * 2);
                for (int i = 0; i < n; i++) { float v = (float)(std::floor(d.amp * sin(ph) * 32767 + 0.5) / 32768.0); ph += 2 * M_PI * d.f / d.rate; db[i * 2] = v; db[i * 2 + 1] = -v; }
                m.feed_digital(db.data(), (size_t)n, d.rate);
            }
        }
        for (auto &pe : patchev) if (pe.first >= 0 && pe.first <= now) { m.set_patch_select(pe.second.first, pe.second.second != 0); pe.first = -1; }
        for (auto &a2 : analog_at) if (a2.first >= 0 && a2.first <= now) { m.analog[a2.second.first] = a2.second.second; a2.first = -1; }
        for (auto &r : raws) if (r.first >= 0 && r.first <= now) { m.duart.rx_byte(1, r.second.first); m.duart.rx_byte(1, r.second.second); r.first = -1; }
        m.esp.set_hostlog_time(now);
        m.run(slice);
        uint64_t experiment_capture_frame = 0;
        if (m.esp.take_experiment_run_capture_complete(experiment_capture_frame)) {
            if (experiment_capture_armed_id > 0) {
                experiment_capture_completed_ids.insert(experiment_capture_armed_id);
                fprintf(stderr, "ESP_EXPERIMENT_CAPTURE_COMPLETE id=%02ld frame=%llu\n",
                        experiment_capture_armed_id, (unsigned long long)experiment_capture_frame);
            }
            experiment_capture_armed_id = -1;
        }
        std::string d0 = m.panel.text(), d1 = m.panel.attr_line(0), dc = m.panel.attr_line(1);
        for (auto &action : panel_actions) {
            if (action.done || now < action.after) continue;
            if (now > action.after + action.timeout) {
                fprintf(stderr, "PANEL_ACTION_TIMEOUT id=%s kind=%s expected=%s observed=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                        action.id.c_str(), action.kind == PanelAction::Kind::MarkOnDisplay ? "mark" :
                        action.kind == PanelAction::Kind::WalkRight ? "walk-right" :
                        action.kind == PanelAction::Kind::SearchRight ? "search-right" :
                        action.kind == PanelAction::Kind::ProbeControl ? "probe" :
                        action.kind == PanelAction::Kind::ProbeRange ? "range" : "tap",
                        action.needle.c_str(), d0.c_str(), now, (unsigned long long)m.cycles(),
                        (unsigned long long)m.esp.host_frame_count());
                action.done = true; panel_action_failed = true; continue;
            }
            if (action.kind == PanelAction::Kind::WalkRight || action.kind == PanelAction::Kind::SearchRight) {
                if (!action.started) {
                    const bool matches = d0.find(action.needle) != std::string::npos;
                    if (matches && d0 == action.last_match) ++action.match_stable;
                    else { action.match_stable = matches ? 1 : 0; action.last_match = matches ? d0 : std::string(); }
                    if (action.match_stable < 20) continue;
                    action.started = true;
                    action.control_baseline = d0;
                    fprintf(stderr, "PANEL_WALK_BEGIN id=%s count=%d display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), action.remaining_steps, d0.c_str(), now,
                            (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                    if (action.kind == PanelAction::Kind::SearchRight && d0.find(action.target) != std::string::npos) {
                        fprintf(stderr, "PANEL_SEARCH_FOUND id=%s target=%s display=\"%.22s\" steps=0 time=%.6f cycles=%llu frame=%llu\n",
                                action.id.c_str(), action.target.c_str(), d0.c_str(), now,
                                (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                        action.done = true;
                        continue;
                    }
                }
                if (!action.down_sent) {
                    action.before_display = d0;
                    action.down_sent = true;
                    action.change_stable = 0;
                    m.panel.button(17, true);
                    fprintf(stderr, "PANEL_WALK_STEP_BEGIN id=%s step=%d display=\"%.22s\" time=%.6f\n",
                            action.id.c_str(), action.step_index + 1, d0.c_str(), now);
                } else {
                    if (d0 != action.before_display) ++action.change_stable;
                    else action.change_stable = 0;
                    if (action.change_stable >= 20) {
                        m.panel.button(17, false);
                        ++action.step_index;
                        --action.remaining_steps;
                        fprintf(stderr, "PANEL_WALK_STEP_DONE id=%s step=%d before=\"%.22s\" after=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                                action.id.c_str(), action.step_index, action.before_display.c_str(), d0.c_str(), now,
                                (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                        action.down_sent = false;
                        if (action.kind == PanelAction::Kind::SearchRight && d0.find(action.target) != std::string::npos) {
                            fprintf(stderr, "PANEL_SEARCH_FOUND id=%s target=%s display=\"%.22s\" steps=%d time=%.6f cycles=%llu frame=%llu\n",
                                    action.id.c_str(), action.target.c_str(), d0.c_str(), action.step_index, now,
                                    (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                            action.done = true;
                        } else if (action.kind == PanelAction::Kind::SearchRight &&
                                   (action.remaining_steps == 0 || d0 == action.control_baseline)) {
                            fprintf(stderr, "PANEL_SEARCH_NOT_FOUND id=%s target=%s final=\"%.22s\" steps=%d\n",
                                    action.id.c_str(), action.target.c_str(), d0.c_str(), action.step_index);
                            action.done = true; panel_action_failed = true;
                        } else if (action.kind == PanelAction::Kind::WalkRight && action.remaining_steps == 0) action.done = true;
                    }
                }
                continue;
            }
            if (action.kind == PanelAction::Kind::ProbeRange) {
                if (action.phase == 0) {
                    const bool matches = d0.find(action.needle) != std::string::npos;
                    if (matches && d0 == action.last_match) ++action.match_stable;
                    else { action.match_stable = matches ? 1 : 0; action.last_match = matches ? d0 : std::string(); }
                    if (action.match_stable < 20) continue;
                    action.control_baseline = d0;
                    action.before_display = d0;
                    action.phase_time = now;
                    action.phase = 1;
                    fprintf(stderr, "PANEL_RANGE_FOUND id=%s display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), d0.c_str(), now, (unsigned long long)m.cycles(),
                            (unsigned long long)m.esp.host_frame_count());
                } else if (action.phase == 1) {
                    if (d0 != action.control_baseline) {
                        fprintf(stderr, "PANEL_RANGE_IDLE_UNSTABLE id=%s before=\"%.22s\" after=\"%.22s\"\n",
                                action.id.c_str(), action.control_baseline.c_str(), d0.c_str());
                        action.done = true; panel_action_failed = true; continue;
                    }
                    if (now - action.phase_time < 0.5) continue;
                    action.phase = 2; // scan upward to the observed upper endpoint
                    action.last_match.clear(); action.match_stable = 0;
                    fprintf(stderr, "PANEL_RANGE_IDLE_END id=%s display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), d0.c_str(), now, (unsigned long long)m.cycles(),
                            (unsigned long long)m.esp.host_frame_count());
                } else {
                    const int button = (action.phase == 2 || action.phase == 5) ? 10 : 11;
                    if (!action.down_sent) {
                        action.before_display = d0;
                        action.down_sent = true;
                        action.probe_key_released = false;
                        action.pressed_at = now;
                        action.last_match.clear();
                        action.match_stable = 0;
                        m.panel.button(button, true);
                        const int next_step = action.phase == 2 ? action.range_steps_up + 1 :
                                              action.phase == 3 ? action.range_steps_origin + 1 :
                                              action.phase == 4 ? action.range_steps_down + 1 :
                                                                  action.range_steps_return + 1;
                        const char* segment = action.phase == 2 ? "to_max" : action.phase == 3 ? "to_origin" :
                                              action.phase == 4 ? "to_min" : "restore";
                        fprintf(stderr, "PANEL_RANGE_STEP_BEGIN id=%s segment=%s direction=%s step=%d display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                                action.id.c_str(), segment, button == 10 ? "up" : "down", next_step,
                                d0.c_str(), now, (unsigned long long)m.cycles(),
                                (unsigned long long)m.esp.host_frame_count());
                    } else {
                        if (!action.probe_key_released) {
                            m.panel.button(button, false);
                            action.probe_key_released = true;
                        }
                        if (d0 != action.before_display) {
                            if (d0 == action.last_match) ++action.match_stable;
                            else { action.match_stable = 1; action.last_match = d0; }
                        } else { action.last_match.clear(); action.match_stable = 0; }
                        if (action.match_stable >= 20) {
                            const int from_phase = action.phase;
                            action.down_sent = false;
                            if (from_phase == 2) ++action.range_steps_up;
                            if (from_phase == 3) ++action.range_steps_origin;
                            if (from_phase == 4) ++action.range_steps_down;
                            if (from_phase == 5) ++action.range_steps_return;
                            const int completed_step = from_phase == 2 ? action.range_steps_up :
                                                       from_phase == 3 ? action.range_steps_origin :
                                                       from_phase == 4 ? action.range_steps_down :
                                                                         action.range_steps_return;
                            const char* segment = from_phase == 2 ? "to_max" : from_phase == 3 ? "to_origin" :
                                                  from_phase == 4 ? "to_min" : "restore";
                            fprintf(stderr, "PANEL_RANGE_STEP_DONE id=%s segment=%s direction=%s step=%d before=\"%.22s\" after=\"%.22s\" cycles=%llu frame=%llu\n",
                                    action.id.c_str(), segment, button == 10 ? "up" : "down", completed_step,
                                    action.before_display.c_str(), d0.c_str(),
                                    (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                            if (from_phase == 3 && d0 == action.control_baseline) {
                                action.phase = 4; action.range_steps_down = 0;
                                fprintf(stderr, "PANEL_RANGE_ORIGIN_RESTORED id=%s display=\"%.22s\"\n",
                                        action.id.c_str(), d0.c_str());
                            } else if (from_phase == 5 && d0 == action.control_baseline) {
                                fprintf(stderr, "PANEL_RANGE_RESTORE id=%s display=\"%.22s\" baseline=\"%.22s\" exact=1 up_steps=%d down_steps=%d cycles=%llu frame=%llu\n",
                                        action.id.c_str(), d0.c_str(), action.control_baseline.c_str(),
                                        action.range_steps_up, action.range_steps_down,
                                        (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                                action.done = true;
                            }
                        } else if (now - action.pressed_at >= 0.30 && d0 == action.before_display) {
                            const int stopped_phase = action.phase;
                            action.down_sent = false;
                            if (stopped_phase == 2) {
                                action.phase = 3;
                                fprintf(stderr, "PANEL_RANGE_MAX id=%s display=\"%.22s\" up_steps=%d time=%.6f cycles=%llu frame=%llu\n",
                                        action.id.c_str(), d0.c_str(), action.range_steps_up, now,
                                        (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                            } else if (stopped_phase == 4) {
                                action.phase = 5;
                                fprintf(stderr, "PANEL_RANGE_MIN id=%s display=\"%.22s\" down_steps=%d time=%.6f cycles=%llu frame=%llu\n",
                                        action.id.c_str(), d0.c_str(), action.range_steps_down, now,
                                        (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                            } else {
                                fprintf(stderr, "PANEL_RANGE_RETURN_FAILED id=%s phase=%d display=\"%.22s\" baseline=\"%.22s\"\n",
                                        action.id.c_str(), stopped_phase, d0.c_str(), action.control_baseline.c_str());
                                action.done = true; panel_action_failed = true;
                            }
                        }
                        if (action.range_steps_up > 1024 || action.range_steps_down > 1024) {
                            fprintf(stderr, "PANEL_RANGE_STEP_LIMIT id=%s display=\"%.22s\"\n", action.id.c_str(), d0.c_str());
                            action.done = true; panel_action_failed = true;
                        }
                    }
                }
                continue;
            }
            if (action.kind == PanelAction::Kind::ProbeControl) {
                if (action.phase == 0) {
                    const bool matches = d0.find(action.needle) != std::string::npos;
                    if (matches && d0 == action.last_match) ++action.match_stable;
                    else { action.match_stable = matches ? 1 : 0; action.last_match = matches ? d0 : std::string(); }
                    if (action.match_stable < 20) continue;
                    action.before_display = d0;
                    action.control_baseline = d0;
                    action.phase_time = now;
                    action.phase = 1;
                    fprintf(stderr, "PANEL_PROBE_FOUND id=%s display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), d0.c_str(), now, (unsigned long long)m.cycles(),
                            (unsigned long long)m.esp.host_frame_count());
                    fprintf(stderr, "PANEL_PROBE_IDLE_BEGIN id=%s display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), d0.c_str(), now, (unsigned long long)m.cycles(),
                            (unsigned long long)m.esp.host_frame_count());
                } else if (action.phase == 1) {
                    if (d0 != action.before_display) {
                        fprintf(stderr, "PANEL_PROBE_IDLE_UNSTABLE id=%s before=\"%.22s\" after=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                                action.id.c_str(), action.before_display.c_str(), d0.c_str(), now,
                                (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                        action.done = true; panel_action_failed = true; continue;
                    }
                    if (now - action.phase_time < 0.5) continue;
                    fprintf(stderr, "PANEL_PROBE_IDLE_END id=%s display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), d0.c_str(), now, (unsigned long long)m.cycles(),
                            (unsigned long long)m.esp.host_frame_count());
                    if (action.repetitions == 0) { action.done = true; continue; }
                    action.iteration = 1;
                    action.phase = 2;
                } else if (action.phase == 2) {
                    action.before_display = d0;
                    action.change_stable = 0;
                    action.phase = 3;
                    action.phase_time = now;
                    m.panel.button(10, true); // Up
                    fprintf(stderr, "PANEL_PROBE_UP_BEGIN id=%s iteration=%d display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), action.iteration, d0.c_str(), now,
                            (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                } else if (action.phase == 3) {
                    // Panel value controls autorepeat quickly. Release after the
                    // first emulated slice so this is a single press, then wait
                    // for the complete display update without holding the key.
                    if (!action.probe_key_released) {
                        m.panel.button(10, false);
                        action.probe_key_released = true;
                    }
                    if (d0 != action.before_display) ++action.change_stable;
                    else action.change_stable = 0;
                    if (action.change_stable < 20) continue;
                    action.last_match = d0;
                    action.phase_time = now;
                    action.phase = 4;
                    fprintf(stderr, "PANEL_PROBE_UP_DISPLAY id=%s iteration=%d before=\"%.22s\" after=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), action.iteration, action.before_display.c_str(), d0.c_str(), now,
                            (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                } else if (action.phase == 4) {
                    if (d0 != action.last_match) {
                        fprintf(stderr, "PANEL_PROBE_UP_UNSTABLE id=%s iteration=%d display=\"%.22s\"\n",
                                action.id.c_str(), action.iteration, d0.c_str());
                        action.done = true; panel_action_failed = true; continue;
                    }
                    if (now - action.phase_time < 0.25) continue;
                    action.before_display = d0;
                    action.change_stable = 0;
                    action.phase = 5;
                    action.phase_time = now;
                    action.probe_key_released = false;
                    m.panel.button(action.revert_code, true);
                    fprintf(stderr, "PANEL_PROBE_REVERT_BEGIN id=%s button=%d iteration=%d display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), action.revert_code, action.iteration, d0.c_str(), now,
                            (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                    fprintf(stderr, "PANEL_PROBE_DOWN_BEGIN id=%s iteration=%d display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), action.iteration, d0.c_str(), now,
                            (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                } else if (action.phase == 5) {
                    if (!action.probe_key_released) {
                        m.panel.button(action.revert_code, false);
                        action.probe_key_released = true;
                    }
                    if (d0 != action.before_display) ++action.change_stable;
                    else action.change_stable = 0;
                    if (action.change_stable < 20) continue;
                    action.last_match = d0;
                    action.phase_time = now;
                    action.phase = 6;
                    fprintf(stderr, "PANEL_PROBE_DOWN_DISPLAY id=%s iteration=%d before=\"%.22s\" after=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), action.iteration, action.before_display.c_str(), d0.c_str(), now,
                            (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                } else if (action.phase == 6) {
                    if (d0 != action.last_match) {
                        fprintf(stderr, "PANEL_PROBE_DOWN_UNSTABLE id=%s iteration=%d display=\"%.22s\"\n",
                                action.id.c_str(), action.iteration, d0.c_str());
                        action.done = true; panel_action_failed = true; continue;
                    }
                    if (now - action.phase_time < 0.25) continue;
                    const bool restored = d0 == action.control_baseline;
                    fprintf(stderr, "PANEL_PROBE_RESTORE id=%s iteration=%d display=\"%.22s\" baseline=\"%.22s\" exact=%d time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), action.iteration, d0.c_str(), action.control_baseline.c_str(),
                            restored ? 1 : 0, now, (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                    if (!restored) { action.done = true; panel_action_failed = true; continue; }
                    if (action.iteration >= action.repetitions) { action.done = true; continue; }
                    ++action.iteration;
                    action.phase = 2;
                    action.probe_key_released = false;
                }
                continue;
            }
            if (!action.down_sent) {
                const bool matches = d0.find(action.needle) != std::string::npos;
                if (matches && d0 == action.last_match) ++action.match_stable;
                else { action.match_stable = matches ? 1 : 0; action.last_match = matches ? d0 : std::string(); }
                if (action.match_stable < 20) continue;
                if (action.kind == PanelAction::Kind::MarkOnDisplay) {
                    fprintf(stderr, "PANEL_STATE id=%s display=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), d0.c_str(), now, (unsigned long long)m.cycles(),
                            (unsigned long long)m.esp.host_frame_count());
                    fprintf(stderr, "PARAMMARK label=%s cycles=%llu frame=%llu display=\"%.22s\"\n",
                            action.id.c_str(), (unsigned long long)m.cycles(),
                            (unsigned long long)m.esp.host_frame_count(), d0.c_str());
                    action.done = true;
                } else {
                    action.before_display = d0;
                    action.down_sent = true;
                    action.pressed_at = now;
                    action.change_stable = 0;
                    m.panel.button(action.code, true);
                    fprintf(stderr, "PANEL_TAP_BEGIN id=%s button=%d before=\"%.22s\" time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), action.code, d0.c_str(), now,
                            (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                }
            } else {
                if (d0 != action.before_display) ++action.change_stable;
                else action.change_stable = 0;
                if (action.change_stable >= 20 ||
                    (action.kind == PanelAction::Kind::TapOnDisplay && now - action.pressed_at >= 0.2)) {
                    m.panel.button(action.code, false);
                    fprintf(stderr, "PANEL_TAP_DONE id=%s button=%d before=\"%.22s\" after=\"%.22s\" release_reason=%s time=%.6f cycles=%llu frame=%llu\n",
                            action.id.c_str(), action.code, action.before_display.c_str(), d0.c_str(),
                            action.change_stable >= 20 ? "display_changed" : "minimum_key_hold",
                            now,
                            (unsigned long long)m.cycles(), (unsigned long long)m.esp.host_frame_count());
                    action.done = true;
                }
            }
        }
        for (int k = 0; k < Panel::COLS; k++) if (dc[k] != ' ') d1[k] = dc[k];
        std::string inds; for (int i = 0; i < 16; i++) inds += " *B"[m.panel.ind[i] % 3];
        d1 += " [" + inds + "]";
        { std::string at = "A:"; at += m.audio_led(0) ? 'Y' : '-'; at += m.audio_led(2) ? 'R' : '-';
          at += " B:"; at += m.audio_led(1) ? 'Y' : '-'; at += m.audio_led(3) ? 'R' : '-'; d1 += " {" + at + "}"; }
        d1 += " <" + m.panel.annunciators() + ">";
        if (!esp_rom_dir.empty() || !experiment_capture_ids.empty() || log_rom_select) {
            const std::string marker = "FX=ROM-";
            size_t pos = d0.find(marker);
            if (pos != std::string::npos && d0 == last0) ++stable_display_slices;
            else stable_display_slices = 0;
            if (pos != std::string::npos && stable_display_slices >= 100) {
                const char *digits = d0.c_str() + pos + marker.size();
                char *end = nullptr;
                long id = strtol(digits, &end, 10);
                if (id > 0 && id <= 999) {
                    std::string selection = d0.substr(pos);
                    if (selection != last_rom_selection) {
                        fprintf(stderr, "ESP_ROM_SELECT id=%02ld time=%.6f cycles=%llu frame=%llu dsp_rate_hz=%.3f otto_clock_hz=%.0f active_voices=%d host_output_rate_hz=%.0f display=%s\n",
                                id, now, (unsigned long long)m.cycles(),
                                (unsigned long long)m.esp.host_frame_count(),
                                m.otto.sample_rate(m.otto_master()), m.otto_master(),
                                m.otto.active_voices(), m.out_rate, selection.c_str());
                        last_rom_selection = selection;
                    }
                    if (experiment_capture_armed_id < 0 && experiment_capture_ids.count(id) &&
                        !experiment_capture_completed_ids.count(id) && experiment_capture_words <= 160) {
                        m.esp.arm_experiment_run_capture(experiment_capture_words);
                        experiment_capture_armed_id = id;
                        fprintf(stderr, "ESP_EXPERIMENT_CAPTURE_ARM id=%02ld words=%u cycles=%llu frame=%llu\n",
                                id, experiment_capture_words, (unsigned long long)m.cycles(),
                                (unsigned long long)m.esp.host_frame_count());
                    }
                }
                if (!esp_rom_dir.empty() && id > 0 && id <= 999 && rom_snapshots.insert((int)id).second) {
                    char path[2048];
                    snprintf(path, sizeof(path), "%s/ROM-%02ld.esp", esp_rom_dir.c_str(), id);
                    FILE *existing = fopen(path, "rb");
                    if (existing) {
                        fclose(existing);
                        fprintf(stderr, "ESP_ROM_CAPTURE_EXISTS id=%02ld time=%.6f display=%s path=%s\n", id, now, d0.c_str() + pos, path);
                    } else if (FILE *f = fopen(path, "wb")) {
                        fprintf(stderr, "ESP_ROM_STATE id=%02ld time=%.6f frame=%llu dsp_rate_hz=%.3f cycles=%llu host_output_rate_hz=%.0f\n", id, now,
                                (unsigned long long)m.esp.host_frame_count(), m.otto.sample_rate(m.otto_master()),
                                (unsigned long long)m.cycles(), m.out_rate);
                        bool ok = m.esp.write_capture(f);
                        if (fclose(f) != 0) ok = false;
                        if (ok) fprintf(stderr, "ESP_ROM_CAPTURE id=%02ld time=%.6f display=%s path=%s\n", id, now, d0.c_str() + pos, path);
                        else fprintf(stderr, "ESP_ROM_CAPTURE_ERROR id=%02ld time=%.6f path=%s\n", id, now, path);
                    } else {
                        fprintf(stderr, "ESP_ROM_CAPTURE_ERROR id=%02ld time=%.6f cannot-open=%s\n", id, now, path);
                    }
                }
            } else if (pos == std::string::npos) last_rom_selection.clear();
        }
        if (d0 != last0 || d1 != last1) {
            fprintf(stderr, "[%7.3fs] |%s|\n           |%s|\n", now, d0.c_str(), d1.c_str());
            last0 = d0; last1 = d1;
        }
    }
    fprintf(stderr, "end pc=%06x\n", m.last_pc());
    fprintf(stderr, "FINAL |%s|\n", m.panel.text().c_str());
    for (const auto &action : panel_actions) if (!action.done) panel_action_failed = true;
    if (pc_hist) {
        std::vector<std::pair<uint64_t,uint32_t>> v; for (auto &x : hist) v.push_back({x.second, x.first});
        std::sort(v.rbegin(), v.rend());
        for (size_t i = 0; i < v.size() && i < 25; i++) fprintf(stderr, "  %06x: %llu\n", v[i].second, (unsigned long long)v[i].first);
    }
    for (int k = 0; k < dis_n; k++) {
        char buf[128]; int l = m68k_disassemble(buf, dis_addr, M68K_CPU_TYPE_68000);
        fprintf(stderr, "%06X: %s\n", dis_addr, buf); dis_addr += l;
    }
    for (int k = 0; k < hex_len; k += 16) {
        fprintf(stderr, "%06X:", hex_addr + k);
        for (int j = 0; j < 16 && k + j < hex_len; j++) fprintf(stderr, " %02x", m.read(hex_addr + k + j, 1));
        fprintf(stderr, "\n");
    }
    if (esp_list) m.esp.list_program(stderr);
    if (!esp_dump.empty()) {
        FILE *f = fopen(esp_dump.c_str(), "wb");
        if (!f) { fprintf(stderr, "cannot open ESP capture %s\n", esp_dump.c_str()); return 1; }
        bool ok = m.esp.write_capture(f);
        if (fclose(f) != 0) ok = false;
        if (!ok) { fprintf(stderr, "failed writing ESP capture %s\n", esp_dump.c_str()); return 1; }
        fprintf(stderr, "ES5510 capture written: %s\n", esp_dump.c_str());
    }
    if (otto_dump) m.otto.dump(stderr);
    if (const char *f = getenv("ASR_DUMP_HI")) {   // the 512 KB at $F80000 (OS code), through the CPU map
        FILE *o = fopen(f, "wb");
        for (uint32_t a = 0xf80000; a < 0x1000000; a++) { uint8_t b = (uint8_t)m.read(a, 1); fwrite(&b, 1, 1, o); }
        fclose(o);
    }
    if (!dump_ram.empty()) { FILE *f = fopen(dump_ram.c_str(), "wb"); fwrite(m.ram.data(), 1, m.ram.size(), f); fclose(f); }
    if (write_back && m.fdc.dirty) { if (m.fdc.save()) fprintf(stderr, "disk image written back\n"); }
    if (const char *eb = getenv("ESP_BENCH")) {    // debug: time the effect processor alone on its state at the end
        ES5510 e = m.esp; const long n = atol(eb); uint64_t sum = 0;
        auto t0 = std::chrono::steady_clock::now();
        ESP_BENCH_START();
        for (long i = 0; i < n; i++) { for (int c = 0; c < 8; c++) e.ser_w(c, (int16_t)(i * (c + 3))); e.run_frame(); for (int c = 0; c < 8; c++) sum = sum * 31 + (uint16_t)e.ser_r(c); }
        ESP_BENCH_STOP();
        double dt = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        fprintf(stderr, "ESP_BENCH %ld frames: %.1f ns/frame, checksum %016llx\n", n, dt / n * 1e9, (unsigned long long)sum);
    }
    if (!wav.empty()) write_wav(wav.c_str(), m.audio, (int)m.out_rate);
    if (!dig_wav.empty()) write_wav(dig_wav.c_str(), m.audio_dig, (int)m.out_rate);
    if (!aux_wav.empty()) {                 // AUX1-3 (Output Expander) summed to one stereo file
        std::vector<float> st(m.audio_aux.size() / 3);
        for (size_t i = 0; i + 5 < m.audio_aux.size(); i += 6) {
            st[i / 3] = m.audio_aux[i] + m.audio_aux[i + 2] + m.audio_aux[i + 4];
            st[i / 3 + 1] = m.audio_aux[i + 1] + m.audio_aux[i + 3] + m.audio_aux[i + 5];
        }
        write_wav(aux_wav.c_str(), st, (int)m.out_rate);
    }
    return panel_action_failed ? 2 : 0;
}
