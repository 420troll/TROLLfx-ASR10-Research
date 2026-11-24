import math
import pathlib
import struct
import subprocess
import tempfile
import unittest
import wave

ROOT = pathlib.Path(__file__).resolve().parents[1]
BIN = ROOT / "build/experimental-audio-host/trollfx-audio-host"
RATE = 48000


def write_pcm16(path, rate, frames):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"".join(struct.pack("<hh", *pair) for pair in frames))


def read_pcm16(path):
    with wave.open(str(path), "rb") as wav:
        spec = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes())
        raw = wav.readframes(wav.getnframes())
    return spec, struct.unpack("<" + "h" * (len(raw) // 2), raw)


class ExperimentalAudioHostCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["sh", str(ROOT / "tools/build_experimental_audio_host.sh")], check=True,
                       cwd=ROOT, capture_output=True, text=True)

    def invoke(self, source, output, *args):
        args = list(args)
        if "--backend" not in args:
            args = ["--backend", "mock", *args]
        return subprocess.run([str(BIN), str(source), str(output), *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_silence_and_determinism_and_block_independence(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = root / "silence.wav"
            write_pcm16(source, RATE, [(0, 0)] * 5003)
            before = source.read_bytes()
            a, b, c = (root / x for x in ("a.wav", "b.wav", "c.wav"))
            self.assertEqual(self.invoke(source, a, "--block", "127").returncode, 0)
            self.assertEqual(self.invoke(source, b, "--block", "127").returncode, 0)
            self.assertEqual(self.invoke(source, c, "--block", "512").returncode, 0)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(a.read_bytes(), c.read_bytes())
            spec, samples = read_pcm16(a)
            self.assertEqual(spec, (2, 2, RATE, 5003))
            self.assertTrue(all(x == 0 for x in samples))
            self.assertEqual(source.read_bytes(), before)

    def test_generated_audio_matrix_and_reported_measurements(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            size = 4096
            signals = {
                "impulse": [(12000 if i == 0 else 0, -9000 if i == 0 else 0) for i in range(size)],
                "sine": [(int(9000 * math.sin(2 * math.pi * 440 * i / RATE)),
                          int(7000 * math.sin(2 * math.pi * 440 * i / RATE + 0.4))) for i in range(size)],
                "sweep": [(int(7000 * math.sin(2 * math.pi * (100 + 8000 * i / size) * i / RATE)),
                           int(7000 * math.sin(2 * math.pi * (150 + 7000 * i / size) * i / RATE))) for i in range(size)],
                "noise": [],
                "stereo_phase": [(int(7000 * math.sin(2 * math.pi * 997 * i / RATE)),
                                  -int(7000 * math.sin(2 * math.pi * 997 * i / RATE))) for i in range(size)],
            }
            state = 0x13579BDF
            for _ in range(size):
                state = (1664525 * state + 1013904223) & 0xffffffff
                left = ((state >> 16) - 32768) // 6
                state = (1664525 * state + 1013904223) & 0xffffffff
                right = ((state >> 16) - 32768) // 6
                signals["noise"].append((left, right))
            for name, frames in signals.items():
                source, output = root / f"{name}.wav", root / f"{name}-out.wav"
                write_pcm16(source, RATE, frames)
                result = self.invoke(source, output, "--effect", "hall", "--block", "257")
                self.assertEqual(result.returncode, 0, result.stderr)
                spec, samples = read_pcm16(output)
                self.assertEqual(spec, (2, 2, RATE, size))
                self.assertTrue(all(-32768 <= x <= 32767 for x in samples))
                self.assertLess(max(abs(x) for x in samples), 32767)
                self.assertIn("processing_ms=", result.stdout)
                self.assertIn("estimated_memory_bytes=", result.stdout)
                self.assertIn("backend=mock", result.stdout)

    def test_input_resampling_to_48khz_preserves_duration_and_stereo(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source, output = root / "44100.wav", root / "out.wav"
            frames = [(int(8000 * math.sin(i * 0.07)), -int(5000 * math.sin(i * 0.07))) for i in range(4410)]
            write_pcm16(source, 44100, frames)
            result = self.invoke(source, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            spec, samples = read_pcm16(output)
            self.assertEqual(spec, (2, 2, 48000, 4800))
            self.assertTrue(any(samples[::2]))
            self.assertTrue(any(samples[1::2]))

    def test_high_gain_saturates_safely(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source, output = root / "hot.wav", root / "hot-out.wav"
            frames = [(30000, -30000)] * 4096
            write_pcm16(source, RATE, frames)
            result = self.invoke(source, output, "--wet", "0", "--input-gain-db", "24")
            self.assertEqual(result.returncode, 0, result.stderr)
            spec, samples = read_pcm16(output)
            self.assertEqual(spec, (2, 2, RATE, len(frames)))
            self.assertTrue(all(-32768 <= x <= 32767 for x in samples))

    def test_switch_hall_rom02_hall_on_sustained_audio(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source, plain, switched = root / "tone.wav", root / "plain.wav", root / "switch.wav"
            frames = [(int(8000 * math.sin(2 * math.pi * 330 * i / RATE)),
                       int(8000 * math.sin(2 * math.pi * 330 * i / RATE + 0.6))) for i in range(RATE)]
            write_pcm16(source, RATE, frames)
            control = self.invoke(source, plain)
            switching = self.invoke(source, switched, "--switch-at", "0.2:rom02", "--switch-at", "0.6:hall")
            self.assertEqual(control.returncode, 0, control.stderr)
            self.assertEqual(switching.returncode, 0, switching.stderr)
            self.assertIn("switches=2", switching.stdout)
            self.assertIn("final_effect=hall", switching.stdout)
            plain_spec, plain_samples = read_pcm16(plain)
            switch_spec, switch_samples = read_pcm16(switched)
            self.assertEqual(plain_spec, switch_spec)
            self.assertEqual(len(plain_samples), len(switch_samples))
            self.assertNotEqual(plain_samples, switch_samples)

    def test_runtime_backend_fails_clearly_without_runtime_or_assets(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source, output = root / "input.wav", root / "out.wav"
            write_pcm16(source, RATE, [(0, 0)] * 32)
            result = self.invoke(source, output, "--backend", "runtime")
            self.assertEqual(result.returncode, 2)
            self.assertIn("runtime requires manifest, checkpoint", result.stderr)
            missing = self.invoke(source, output, "--backend", "runtime",
                                  "--hall-checkpoint", str(root / "missing-hall.esp"),
                                  "--hall-manifest", str(root / "missing-hall.json"),
                                  "--hall-reference-dir", str(root / "missing-hall-ref"),
                                  "--hall-events", str(root / "missing-hall-events.csv"),
                                  "--rom02-checkpoint", str(root / "missing-rom02.esp"),
                                  "--rom02-manifest", str(root / "missing-rom02.json"),
                                  "--rom02-reference-dir", str(root / "missing-rom02-ref"),
                                  "--rom02-events", str(root / "missing-rom02-events.csv"))
            self.assertEqual(missing.returncode, 2)
            self.assertIn("private factory package validation failed", missing.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
