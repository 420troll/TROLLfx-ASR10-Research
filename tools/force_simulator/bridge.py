"""ctypes wrapper for the test-instrumented, real native VST2 plugin."""
from __future__ import annotations
import ctypes
from dataclasses import dataclass
from pathlib import Path

class TraceWrite(ctypes.Structure):
    _fields_ = [("sequence", ctypes.c_uint64), ("dsp_frame", ctypes.c_uint64),
                ("slot", ctypes.c_uint32), ("gpr", ctypes.c_uint32), ("value24", ctypes.c_uint32)]

class VSTBridge:
    def __init__(self, host_library: Path, plugin: Path, assets: Path):
        self.lib = ctypes.CDLL(str(host_library))
        self.lib.trollfx_vst_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self.lib.trollfx_vst_create.restype = ctypes.c_void_p
        self.handle = self.lib.trollfx_vst_create(str(plugin).encode(), str(assets).encode())
        if not self.handle:
            raise RuntimeError("native VST host could not load VSTPluginMain; check native build and local factory assets")
        self.lib.trollfx_vst_destroy.argtypes = [ctypes.c_void_p]
        self.lib.trollfx_vst_num_params.argtypes = [ctypes.c_void_p]
        self.lib.trollfx_vst_num_params.restype = ctypes.c_int
        self.lib.trollfx_vst_get.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.lib.trollfx_vst_get.restype = ctypes.c_float
        self.lib.trollfx_vst_set.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_float]
        self.lib.trollfx_vst_text.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        self.lib.trollfx_vst_pump.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.lib.trollfx_vst_process.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.c_int]
        self.lib.trollfx_vst_process.restype = ctypes.c_int
        self.lib.trollfx_vst_state.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
        self.lib.trollfx_vst_state.restype = ctypes.c_size_t
        self.lib.trollfx_vst_restore.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
        self.lib.trollfx_vst_restore.restype = ctypes.c_int
        self.lib.trollfx_vst_trace_latest.argtypes = [ctypes.c_void_p]
        self.lib.trollfx_vst_trace_latest.restype = ctypes.c_uint64
        self.lib.trollfx_vst_trace_copy.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(TraceWrite), ctypes.c_size_t]
        self.lib.trollfx_vst_trace_copy.restype = ctypes.c_size_t
        self.lib.trollfx_vst_trace_reset.argtypes = [ctypes.c_void_p]
        self.lib.trollfx_vst_trace_available.argtypes = [ctypes.c_void_p]
        self.lib.trollfx_vst_trace_available.restype = ctypes.c_int

    def close(self):
        if self.handle:
            self.lib.trollfx_vst_destroy(self.handle)
            self.handle = None

    @property
    def num_params(self) -> int:
        return int(self.lib.trollfx_vst_num_params(self.handle))

    def get(self, index: int) -> float:
        return float(self.lib.trollfx_vst_get(self.handle, index))

    def set(self, index: int, value: float):
        self.lib.trollfx_vst_set(self.handle, index, float(value))

    def text(self, index: int, name=False) -> str:
        buf = ctypes.create_string_buffer(256)
        if not self.lib.trollfx_vst_text(self.handle, index, int(name), buf, len(buf)):
            return ""
        return buf.value.decode("utf-8", "replace")

    def pump(self, frames=256):
        self.lib.trollfx_vst_pump(self.handle, int(frames))

    def process(self, interleaved, frames: int, block=256):
        arr_type = ctypes.c_float * len(interleaved)
        inp = arr_type(*interleaved)
        out = arr_type()
        if not self.lib.trollfx_vst_process(self.handle, inp, out, frames, block):
            raise RuntimeError("VST processReplacing failed")
        return list(out)

    def save_state(self) -> bytes:
        size = int(self.lib.trollfx_vst_state(self.handle, None, 0))
        if not size:
            raise RuntimeError("VST effGetChunk returned no state")
        data = (ctypes.c_uint8 * size)()
        got = int(self.lib.trollfx_vst_state(self.handle, data, size))
        if got != size:
            raise RuntimeError("VST state chunk size changed while saving")
        return bytes(data)

    def restore_state(self, state: bytes):
        arr = (ctypes.c_uint8 * len(state)).from_buffer_copy(state)
        if not self.lib.trollfx_vst_restore(self.handle, arr, len(state)):
            raise RuntimeError("VST effSetChunk rejected saved state")

    def trace_latest(self) -> int:
        return int(self.lib.trollfx_vst_trace_latest(self.handle))

    def trace_since(self, sequence: int):
        rows = (TraceWrite * 4096)()
        count = int(self.lib.trollfx_vst_trace_copy(self.handle, sequence, rows, len(rows)))
        return [dict(sequence=rows[i].sequence, dsp_frame=rows[i].dsp_frame, slot=rows[i].slot,
                     gpr=rows[i].gpr, value24=rows[i].value24) for i in range(count)]

    def reset_trace(self):
        self.lib.trollfx_vst_trace_reset(self.handle)

    @property
    def has_trace(self) -> bool:
        return bool(self.lib.trollfx_vst_trace_available(self.handle))
