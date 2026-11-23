import importlib.util
import pathlib
import subprocess
import tempfile
import unittest
import hashlib
import json

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / 'tools/audio_validation/run.py'
spec = importlib.util.spec_from_file_location('audio_validation', SCRIPT)
av = importlib.util.module_from_spec(spec); spec.loader.exec_module(av)

class AudioValidationTests(unittest.TestCase):
    def test_stimuli_are_deterministic_and_cover_required_cases(self):
        a = av.stimuli(44100, 512); b = av.stimuli(44100, 512)
        self.assertEqual(set(a), {'impulse','sine','sweep','noise','stereo_phase'})
        self.assertEqual(a, b)
        self.assertTrue(any(l != r for l, r in a['stereo_phase']))
        self.assertEqual(a['impulse'][64], (24000, 0))

    def test_metrics_detect_deviation_and_alignment(self):
        ref = [[0,0],[1,-1],[2,-2],[0,0]]
        got = [[0,0],[0,0],[1,-1],[2,-2]]
        m = av.metrics(ref, got)
        self.assertEqual(m['best_alignment_lag_frames'], 1)
        self.assertFalse(m['bit_exact'])
        self.assertGreater(m['max_abs_deviation'], 0)

    def test_end_to_end_repeatability_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            out=pathlib.Path(td)
            subprocess.run(['python3',str(SCRIPT),'--out',td,'--frames','13000','--trace'],check=True,stdout=subprocess.DEVNULL)
            first=(out/'summary.json').read_bytes()
            subprocess.run(['python3',str(SCRIPT),'--out',td,'--frames','13000','--trace'],check=True,stdout=subprocess.DEVNULL)
            self.assertEqual(first,(out/'summary.json').read_bytes())
            import json
            report=json.loads(first)
            self.assertEqual(set(report['summaries']), {'impulse','sine','sweep','noise','stereo_phase'})
            self.assertIn('best_alignment_lag_frames',report['summaries']['impulse']['pass'])
            delay=report['summaries']['impulse']['delay']
            self.assertTrue(delay['bit_exact'])
            self.assertEqual(delay['first_divergent_frame'],None)
            for engine in ('original','mame'):
                taps=delay['impulse_response_taps'][engine]
                self.assertEqual(taps[0]['offset_from_input_frames'],0)
                self.assertEqual(taps[1]['offset_from_input_frames'],11025)
                self.assertEqual(taps[1]['left'],13199)
                trace=(out/f'impulse-delay-{engine}.trace.csv').read_text()
                self.assertIn('I,0,00,',trace)
                self.assertIn('ROUTE,0,',trace)

    def test_factory_manifest_requires_complete_cold_load_and_verifies_payloads(self):
        from importlib.util import spec_from_file_location, module_from_spec
        modspec=spec_from_file_location('factory_manifest', SCRIPT.parent/'factory_manifest.py')
        fm=module_from_spec(modspec); modspec.loader.exec_module(fm)
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            payloads={'program.bin':bytes.fromhex('00000000f000'),'gpr.bin':b'\x00'*576,'special.bin':b'\x00'*66}
            for name,data in payloads.items(): (root/name).write_bytes(data)
            def ref(name,data,count=None):
                row={'path':name,'sha256':hashlib.sha256(data).hexdigest()}
                if count is not None: row['count']=count
                return row
            doc={
                'schema':fm.SCHEMA,'initialization_basis':'cold_load',
                'provenance':{'effect_id':'test-only','effect_name':'synthetic','os_version':'fixture','selection_evidence':'synthetic fixture'},
                'sample_rate_hz':44100,
                'program':{**ref('program.bin',payloads['program.bin']),'format':'es5510-six-byte-big-endian','active_words':1,'end_word':0},
                'gpr':ref('gpr.bin',payloads['gpr.bin'],192),'special_registers':ref('special.bin',payloads['special.bin'],22),
                'dram':{'mode':'zeroed','word_count':1<<20},
                'memory':{'memsiz':0,'memmask':0xffffff,'memincrement':1,'memshift':0,'dlength':0,'abase':0,'bbase':0,'dbase':0,'sigreg':0},
                'serial':{'host_serial':0,'input_ports':[0,1],'output_ports':[3]},
                'lifecycle':{'halt_before_load':True,'run_after_load':True,'initialization_order':['halt','memory','program','gpr','special_registers','dram','reset_pipeline','run']},
                'pipeline':{'status':'reset_after_load','complete':True}}
            manifest=root/'state.json'; manifest.write_text(json.dumps(doc))
            self.assertTrue(fm.validate(manifest)['valid'])
            doc['initialization_basis']='runtime_snapshot'; manifest.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError, 'runtime snapshots are not accepted'):
                fm.validate(manifest)

if __name__ == '__main__': unittest.main()
