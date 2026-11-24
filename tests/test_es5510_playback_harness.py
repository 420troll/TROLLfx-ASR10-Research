import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"tools/audio_validation/run_es5510_playback_harness.py"
spec=importlib.util.spec_from_file_location("es5510_harness",SCRIPT)
harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)

class PlaybackHarnessHelpers(unittest.TestCase):
    def test_only_importer_eligible_descriptors_are_mapped(self):
        self.assertIsNone(harness.package_from_importer({"registry_eligible":False,"descriptor":None},Path("/tmp")))

    def test_package_mapping_and_ordered_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);checkpoint=root/"run.esp";checkpoint.write_bytes(b"test")
            item={"registry_eligible":True,"descriptor":{
                "slot":7,"factory_name":"Synthetic","active_program_words":3,"end_word":2,
                "program_sha256":"a"*64,"factory_reference_rate_hz":32000,
                "routing":{"host_serial_mode":72,"input_port":2,"output_port":1},
                "run_checkpoint_path":str(checkpoint),"run_checkpoint_sha256":"b"*64,
                "package_manifest_path":str(root/"manifest.json"),
                "firmware_event_schedule":[{"relative_dsp_frame":0,"gpr":1,"value24":12}]}}
            pkg=harness.package_from_importer(item,root)
            self.assertEqual(pkg["slot"],7)
            self.assertEqual(harness.schedule_rows(pkg["schedule"]),[(0,1,12)])

    def test_absolute_events_are_relative_to_run_boundary_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"events.csv"
            path.write_text("boundary_frame,event_id,cpu_cycles,dsp_frame,host_pc,index,value\n"
                            "100,1,0,0,0,01,00000c\n102,2,1,2,0,02,00abcd\n")
            self.assertEqual(harness.read_schedule_csv(path,100),[(0,1,12),(2,2,0xabcd)])
            path.write_text("boundary_frame,event_id,cpu_cycles,dsp_frame,host_pc,index,value\n"
                            "99,1,0,0,0,01,00000c\n")
            with self.assertRaises(ValueError):harness.read_schedule_csv(path,100)

    def test_reference_samples_are_written_only_to_requested_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"io.csv";a=root/"in.f32";b=root/"out.f32"
            source.write_text("frame,lane4,lane5,reference_left,reference_right\n"
                              "50,16384,-16384,8192,-8192\n51,0,0,1,-1\n")
            count=harness.dump_reference_csv(source,source,50,a,b)
            self.assertEqual(count,2)
            self.assertEqual(a.stat().st_size,16)
            self.assertEqual(b.stat().st_size,16)

if __name__=="__main__":unittest.main()
