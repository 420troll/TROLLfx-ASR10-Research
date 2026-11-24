import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.audio_validation.replay_hall_from_boundary import parse_bundle, compare_instruction_traces

ROOT = Path(__file__).resolve().parents[2]


class HallBoundaryReplayTests(unittest.TestCase):
    def test_post_run_commit_is_scheduled_between_observed_frames(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);boot=root/"boot-a";boot.mkdir();(boot/"snapshots").mkdir()
            metadata={"firmware_load":{"instruction_commits":89,"gpr_spr_commit_count":342},
                      "timeline":[{"frame":"855973"}]}
            (boot/"capture-metadata.json").write_text(json.dumps(metadata))
            (boot/"session.log").write_text("\n".join([
                "ESPPHASE kind=host_halt_pipeline_reset frame=855972 cycles=1 host_pc=fff977b8",
                "ESPPHASE kind=run_start frame=855973 cycles=2 host_pc=fff97638",
                "ESPPHASE kind=run_snapshot frame=855973 cycles=2 host_pc=fff97638",
                "ESPPFRAME kind=input index=0 frame=855973 cycles=2 host_pc=fff97638 serial=48 lanes=0000,0000,0000,0000,0001,0001,0000,0000",
                "ESPPHASE kind=first_instruction frame=855973 cycles=2 host_pc=fff97638 pc=00",
                "ESPPFRAME kind=output index=0 frame=855973 cycles=2 host_pc=fff97638 serial=48 lanes=0000,0000,0000,0000,0001,0001,0000,0000",
                "ESPHOST event=8 cycles=3 frame=855973 pc=fff97792 gpr 7f <- 123456 t=0",
                "ESPPFRAME kind=input index=1 frame=855974 cycles=4 host_pc=fff977a0 serial=48 lanes=0000,0000,0000,0000,0002,0002,0000,0000",
                "ESPPFRAME kind=output index=1 frame=855974 cycles=4 host_pc=fff977a0 serial=48 lanes=0000,0000,0000,0000,0002,0002,0000,0000",
            ])+"\n")
            result=parse_bundle(boot,855973,2)
            self.assertEqual(len(result["writes"]),1)
            self.assertEqual(result["writes"][0]["boundary_frame"],855974)
            self.assertEqual(result["writes"][0]["event_id"],8)

    def test_instruction_diagnostic_ignores_nonarchitectural_dil_shadow(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a=root/"native.csv";b=root/"mame.csv"
            a.write_text("I,0,00,000000000000\nW,0,00,100,123456\nI,0,02,000000000000\nRQ,0,02,0,0,000001\n")
            b.write_text("I,0,00,000000000000\nI,0,02,000000000000\nRQ,0,02,0,0,000002\n")
            result=compare_instruction_traces(a,b,855973)
            self.assertEqual(result["status"],"diverged")
            self.assertEqual(result["absolute_dsp_frame"],855973)
            self.assertEqual(result["event_type"],"RQ")
            self.assertEqual(result["program_counter"],"02")
            self.assertEqual(result["field"],"ram_request_address")

    def test_native_and_mame_load_same_pipeline_reset_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            exe=Path(td)/"capture-roundtrip"
            subprocess.run(["c++","-std=c++17","-O2","-Isrc","-Ithird_party/trollfx_mame_es5510",
                            "src/es5510.cpp","third_party/trollfx_mame_es5510/mame_es5510_standalone.cpp",
                            "tests/es5510_capture_roundtrip.cpp","-o",str(exe)],cwd=ROOT,check=True)
            run=subprocess.run([str(exe)],cwd=ROOT,capture_output=True,text=True,check=True)
            self.assertIn("capture load/execute: ok",run.stdout)


if __name__=="__main__":unittest.main()
