import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

capture = load("capture_hall_reference", "tools/audio_validation/capture_hall_reference.py")
verifier = load("hall_replay_verify", "tools/audio_validation/hall_replay_verify.py")


class HallReferenceCaptureTests(unittest.TestCase):
    def test_serial_adapter_keeps_numeric_eight_lane_frames_and_order(self):
        lines = [
            "ESPPHASE kind=host_halt_pipeline_reset frame=14 cycles=100 pc=fff000 alu_pending=0",
            "ESPPHASE kind=program_upload_summary frame=20 cycles=110 pc=fff000 commits=89 unique_addresses=89 first_end=88 gpr_commits=342",
            "ESPPHASE kind=run_start frame=20 cycles=110 host_pc=fff000 pc=00 alu_pending=0",
            "ESPPHASE kind=run_snapshot frame=20 cycles=110 host_pc=fff000 pc=00 ok=1 path=/private/snapshot.esp",
            "ESPAUDIO kind=clock frame=20 cycles=110 otto_clock_hz=15238090 dsp_rate_hz=29761.894531250 active_voices=31 host_output_rate_hz=44100 dac_model=1 serial_route=-1,-1,1,-1 direct_mask=00",
        ]
        for i, frame in enumerate(range(20,24)):
            lanes_in = "ffff,0001,0002,0003,8000,7fff,0006,0007"
            lanes_out = "0000,0001,1234,edcc,0004,0005,0006,0007"
            lines.append(f"ESPPFRAME kind=input index={i} frame={frame} cycles={frame+100} host_pc=fff000 serial=48 lanes={lanes_in}")
            lines.append(f"ESPPFRAME kind=output index={i} frame={frame} cycles={frame+100} host_pc=fff000 serial=48 lanes={lanes_out}")
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"session.log"; path.write_text("\n".join(lines)+"\n")
            result=capture.parse_session(path,20,4)
        self.assertEqual(len(result["input"]),4)
        self.assertEqual(result["input"][0]["lanes"][4:6],[-32768,32767])
        self.assertEqual(result["output"][0]["lanes"][2:4],[0x1234,-0x1234])
        self.assertEqual(result["pipeline_reset"]["frame"],"14")

    def test_source_position_window_selects_without_shifting(self):
        rows=[{"host_frame_index":i,"source_dsp_frame_position":p} for i,p in enumerate((99.5,100,100.7,101,102.0))]
        selected=capture.select_host_window_rows(rows,100,2)
        self.assertEqual([x["host_frame_index"] for x in selected],[1,2,3])
        self.assertTrue(all(100 <= x["source_dsp_frame_position"] < 102 for x in selected))

    def test_independent_verifier_reports_exact_earliest_sample_difference(self):
        a=[{"index":i,"left":i,"right":-i} for i in range(256)]
        b=[dict(x) for x in a]; b[37]["right"] += 1
        result=verifier.compare_samples(a,b,256)
        self.assertFalse(result["samples_equal"])
        self.assertEqual(result["first_difference"]["index"],37)
        self.assertEqual(result["max_absolute_difference"],1)

    def test_dac_source_position_observer_does_not_change_samples(self):
        with tempfile.TemporaryDirectory() as td:
            exe=Path(td)/"dac-test"
            subprocess.run(["c++","-std=c++17","-O2","-I",str(ROOT/"src"),
                            str(ROOT/"src/dac_out.cpp"),str(ROOT/"tests/dac_out_source_positions.cpp"),
                            "-o",str(exe)],check=True)
            subprocess.run([str(exe)],check=True)


if __name__ == "__main__": unittest.main()
