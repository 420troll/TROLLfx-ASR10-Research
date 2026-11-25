import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hall_decay_adapter import HallDecayRuntimeAdapter


class FakeFactoryRuntime:
    def __init__(self, raw=51, display=40, accept=True):
        self.raw = raw
        self.display = display
        self.accept = accept
        self.calls = []

    def getStatus(self):
        return SimpleNamespace(hall_decay_step_available=True,
            hall_decay_raw_code=self.raw, hall_decay_display_value=self.display,
            processed_dsp_frames=300)

    def stepHallDecayTime(self, direction, frame):
        self.calls.append((direction, frame))
        if not self.accept:
            return False
        self.raw += direction
        self.display += direction
        return True


class HallDecayAdapterTests(unittest.TestCase):
    def test_runtime_raw_state_is_not_reconstructed_from_display_value(self):
        up_path = HallDecayRuntimeAdapter(FakeFactoryRuntime(raw=51, display=40))
        down_path = HallDecayRuntimeAdapter(FakeFactoryRuntime(raw=52, display=40))
        up, down = up_path.snapshot(1, 1), down_path.snapshot(1, 1)
        self.assertEqual((up.display_value, up.raw_code), (40, 51))
        self.assertEqual((down.display_value, down.raw_code), (40, 52))

    def test_direct_numeric_entry_is_pending_and_preserves_raw_state(self):
        runtime = FakeFactoryRuntime(raw=52, display=40)
        adapter = HallDecayRuntimeAdapter(runtime)
        state = adapter.stage_display_value(1, 1, 87)
        self.assertEqual(state.pending_value, 87)
        self.assertEqual((state.display_value, state.raw_code, state.applied_value), (40, 52, 40))
        self.assertFalse(runtime.calls)
        blocked = adapter.step(1, 1, +1)
        self.assertEqual((blocked.display_value, blocked.raw_code), (40, 52))
        self.assertFalse(runtime.calls)

    def test_numeric_entry_rejects_fractional_and_out_of_range_values(self):
        adapter = HallDecayRuntimeAdapter(FakeFactoryRuntime())
        with self.assertRaises(ValueError):
            adapter.stage_display_value(1, 1, 40.5)
        with self.assertRaises(ValueError):
            adapter.stage_display_value(1, 1, 100)

    def test_unaccepted_mapping_never_calls_native_step(self):
        runtime = FakeFactoryRuntime()
        state = HallDecayRuntimeAdapter(runtime).step(1, 1, +1)
        self.assertEqual(state.mapping_status, "PENDING_INDEPENDENT_QA")
        self.assertFalse(runtime.calls)

    def test_variation_and_atomic_failure_fail_closed(self):
        runtime = FakeFactoryRuntime(raw=52, display=40)
        adapter = HallDecayRuntimeAdapter(runtime, independent_qa_accepted=True)
        other_variation = adapter.step(1, 2, +1)
        self.assertEqual(other_variation.mapping_status, "UNSUPPORTED_CONTEXT")
        self.assertFalse(runtime.calls)
        runtime.accept = False
        rejected = adapter.step(1, 1, +1, frame=301)
        self.assertEqual((rejected.raw_code, rejected.display_value, rejected.applied_value), (52, 40, 40))
        self.assertEqual(runtime.calls, [(1, 301)])

    def test_accepted_step_delegates_direction_and_scheduled_frame(self):
        runtime = FakeFactoryRuntime(raw=52, display=40)
        state = HallDecayRuntimeAdapter(runtime, independent_qa_accepted=True).step(1, 1, -1)
        self.assertEqual(runtime.calls, [(-1, 300)])
        self.assertEqual((state.raw_code, state.display_value, state.applied_value), (51, 39, 39))


if __name__ == "__main__":
    unittest.main()
