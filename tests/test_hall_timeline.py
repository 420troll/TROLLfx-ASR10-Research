import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hall_timeline", ROOT / "tools/audio_validation/hall_timeline.py")
timeline = importlib.util.module_from_spec(spec); spec.loader.exec_module(timeline)


class HallTimelineTests(unittest.TestCase):
    def fixture(self, mismatched=False):
        tmp = tempfile.TemporaryDirectory(); root = Path(tmp.name)
        gpr = bytearray(192 * 3)
        if mismatched: gpr[144*3:145*3] = (123).to_bytes(3, "big")
        spr = bytearray(22 * 3)
        for i, v in ((18, 0xffffff), (19, 0x800000), (20, 0x7fffff)):
            spr[i*3:i*3+3] = v.to_bytes(3, "big")
        (root/"gpr.bin").write_bytes(gpr); (root/"spr.bin").write_bytes(spr)
        capture = root/"snapshot.esp"
        capture.write_bytes(b"ES5510C\0" + bytes(44 + 160*6 + 192*3 + 22*3 + 74))
        manifest = {"capture":{"run_frame":20,"snapshot_sha256":__import__("hashlib").sha256(capture.read_bytes()).hexdigest()},
                    "gpr":{"path":"gpr.bin"},"special_registers":{"path":"spr.bin"}}
        (root/"manifest.json").write_text(json.dumps(manifest))
        rows = [
            [1, 10, 18, "0.01", "fff00000", "PA4", "HALT", "prior_state=running"],
            [2, 10, 18, "0.01", "fff00001", "PIPELINE_CLEARED", "reason=halt_enable"],
            [3, 11, 19, "0.02", "fff00002", "DRAM_CLEAR", "words=1048576"],
            [4, 12, 19, "0.02", "fff00003", "INSTR_COMMIT", "index=00", "word=000000000000"],
            [5, 13, 19, "0.02", "fff00004", "GPR_COMMIT", "index=00", "value=000000"],
            [6, 14, 19, "0.02", "fff00005", "PROGRAM_READY", "active_words=1"],
            [7, 15, 20, "0.03", "fff00006", "PA4", "RUN", "prior_state=halted"],
            [8, 15, 20, "0.03", "fff00007", "DSP_RUN", "program_ready=1"],
            [9, 15, 20, "0.03", "fff00007", "RUN_SNAPSHOT", f"path={capture}"],
            [10, 15, 20, "0.03", "fff00007", "AUDIO_PRE", "input=observed"],
            [11, 15, 20, "0.03", "fff00007", "DSP_FIRST_END", "pc=58"],
            [12, 16, 21, "0.04", "fff00008", "GPR_COMMIT", "index=7f", "value=000001"],
        ]
        events = root/"events.csv"
        with events.open("w", newline="") as f:
            w=csv.writer(f); w.writerow(("event","host_cycles","dsp_frame","host_seconds","cpu_pc","type","fields...")); w.writerows(rows)
        return tmp, root, manifest, events

    def test_checkpoint_timeline_and_strict_state_diagnostic(self):
        tmp, root, _, events = self.fixture()
        with tmp:
            report = timeline.analyze(events, root/"manifest.json")
            self.assertTrue(report["selected_checkpoint"]["selection_valid"])
            self.assertTrue(report["halted_commit_summary"]["manifest_state_gate_pass"])
            self.assertEqual([x["event"] for x in report["timeline"]][-3:],
                             ["first_instruction_start", "first_input_frame", "first_frame_end"])
            self.assertEqual(report["halted_commit_summary"]["post_checkpoint_commit_count"], 1)

    def test_nonmatching_checkpoint_cannot_use_manifest_state(self):
        tmp, root, _, events = self.fixture()
        with tmp, self.assertRaisesRegex(ValueError, "does not select exactly one DSP_RUN"):
            timeline.analyze(events, root/"manifest.json", checkpoint_frame=19)

    def test_untouched_register_mismatch_remains_a_gate_failure(self):
        tmp, root, _, events = self.fixture(mismatched=True)
        with tmp:
            report = timeline.analyze(events, root/"manifest.json")
            state = report["halted_commit_summary"]
            self.assertFalse(state["manifest_state_gate_pass"])
            self.assertEqual(state["mismatches_without_halted_write"], [144])


if __name__ == "__main__": unittest.main()
