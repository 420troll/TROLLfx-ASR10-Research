import base64
import io
import json
import math
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audio_lab import analyze_bundle


def make_wav(values, rate=48000):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate)
        w.writeframes(b''.join(struct.pack('<hh',int(a*32767),int(b*32767)) for a,b in values))
    return base64.b64encode(out.getvalue()).decode()


def fixture_bundle():
    a=[(0.5,0.25),(0.25,-0.25),(0.0,0.0),(0.0,0.0)]
    b=[(0.25,0.125),(0.125,-0.125),(0.0,0.0),(0.0,0.0)]
    def render(value,raw,samples,frame):
        return {'display_value':value,'raw_code':raw,'raw_code_basis':'runtime_state',
            'wav_base64':make_wav(samples),'dsp_status':'applied','runtime_status':'ready','firmware_status':'initialized','processing_rate_hz':48000,
            'package_provenance':'validated_factory_checkpoint','provenance_id':'fixture-hall-v1',
            'source_commit':'abcdef1','register_updates':[{'frame':frame,'register':'0x6E'}]}
    return {'schema':'trollfx-asr10-hall-audio-artifacts-v1','source':'ui_fixture','effect_slot':1,
        'effect_name':'HALL REVERB','variation':1,'cases':[{'case_id':'10_vs_90_impulse','stimulus':'impulse',
        'a':render(10,17,a,1),'b':render(90,113,b,2)}]}


class HallAudioLabTests(unittest.TestCase):
    def test_labels_raw_codes_metrics_wave_and_register_timing(self):
        result=analyze_bundle(fixture_bundle())
        case=result['cases'][0]
        self.assertEqual([case['a']['display_value'],case['b']['display_value']],[10,90])
        self.assertEqual([case['a']['raw_code'],case['b']['raw_code']],[17,113])
        self.assertEqual(case['a']['raw_code_basis'],'runtime_state')
        self.assertEqual(case['a']['register_updates'][0],{'frame':1,'register':'0X6E'})
        self.assertEqual(case['a']['sample_rate_hz'],48000)
        self.assertAlmostEqual(case['a']['metrics']['left']['peak'],0.5,places=3)
        self.assertAlmostEqual(case['a']['metrics']['right']['peak'],0.25,places=3)
        self.assertGreater(case['difference']['rms'],0)
        self.assertEqual(len(case['a']['waveform']['left']),4)
        self.assertAlmostEqual(case['a']['envelope'][0][1],math.sqrt((.5**2+.25**2+.25**2+.25**2)/8),places=3)

    def test_result_is_deterministic_and_report_contains_no_audio_or_paths(self):
        bundle=fixture_bundle();a=analyze_bundle(bundle);b=analyze_bundle(bundle)
        self.assertEqual(a['measurement_report'],b['measurement_report'])
        serialized=json.dumps(a['measurement_report'])
        self.assertNotIn('wav_base64',serialized);self.assertNotIn('Users/',serialized)
        self.assertNotIn('home/',serialized);self.assertNotIn('checkpoint_path',serialized)
        self.assertNotIn('private',serialized.lower())

    def test_unreported_raw_code_is_never_derived_from_display(self):
        bundle=fixture_bundle();bundle['cases'][0]['a']['raw_code']=None;bundle['cases'][0]['a']['raw_code_basis']='not_reported'
        result=analyze_bundle(bundle)
        self.assertIsNone(result['cases'][0]['a']['raw_code'])
        self.assertIsNone(result['measurement_report']['cases'][0]['raw_codes'][0])

    def test_vst_and_reference_sources_remain_explicit_and_no_write_status_is_retained(self):
        for source in ('actual_vst_audio','original_os_reference','standalone_experimental_runtime'):
            bundle=fixture_bundle();bundle['source']=source;bundle['cases'][0]['a']['dsp_status']='no_write'
            result=analyze_bundle(bundle)
            self.assertEqual(result['source'],source)
            self.assertEqual(result['measurement_report']['cases'][0]['dsp_status'][0],'no_write')

    def test_private_fields_and_mismatched_audio_are_rejected(self):
        bundle=fixture_bundle();bundle['private_checkpoint_path']='/private/rom.chk'
        with self.assertRaisesRegex(ValueError,'bundle fields'):
            analyze_bundle(bundle)
        bundle=fixture_bundle();bundle['cases'][0]['a']['local_path']='/secret'
        with self.assertRaisesRegex(ValueError,'unsupported metadata'):
            analyze_bundle(bundle)
        bundle=fixture_bundle();bundle['cases'][0]['b']['wav_base64']=make_wav([(0,0)],44100)
        with self.assertRaisesRegex(ValueError,'identical sample rate'):
            analyze_bundle(bundle)

    def test_effect_and_unverified_raw_basis_are_rejected(self):
        bundle=fixture_bundle();bundle['effect_slot']=3;bundle['effect_name']='ROOM REVERB'
        with self.assertRaisesRegex(ValueError,'HALL REVERB'):
            analyze_bundle(bundle)
        bundle=fixture_bundle();bundle['cases'][0]['a']['raw_code_basis']='display_value_inferred'
        with self.assertRaisesRegex(ValueError,'raw-code basis'):
            analyze_bundle(bundle)

    def test_packer_embeds_only_path_free_render_metadata_and_wav_bytes(self):
        from pathlib import Path
        from audio_lab import SCHEMA
        with tempfile.TemporaryDirectory(prefix='hall-audio-lab-pack-') as td:
            root=Path(td);wa=base64.b64decode(make_wav([(0.1,0.2)]));wb=base64.b64decode(make_wav([(0.2,0.3)]))
            (root/'a.wav').write_bytes(wa);(root/'b.wav').write_bytes(wb)
            render={'display_value':10,'raw_code':None,'raw_code_basis':'not_reported','dsp_status':'applied',
                'runtime_status':'ready','firmware_status':'initialized','processing_rate_hz':48000,'package_provenance':'validated_factory_checkpoint',
                'provenance_id':'approved-entry','source_commit':'abcdef1','register_updates':[]}
            meta={'source':'standalone_experimental_runtime','variation':1,'stimulus':'impulse','case_id':'10_vs_90',
                'a':render,'b':{**render,'display_value':90}}
            (root/'metadata.json').write_text(json.dumps(meta))
            out=root/'bundle.json'
            subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'audio_lab_pack.py'),
                '--metadata',str(root/'metadata.json'),'--a-wav',str(root/'a.wav'),'--b-wav',str(root/'b.wav'),
                '--output',str(out)],check=True,capture_output=True,text=True)
            bundle=json.loads(out.read_text())
            self.assertEqual(bundle['schema'],SCHEMA)
            self.assertEqual([bundle['cases'][0][k]['display_value'] for k in ('a','b')],[10,90])
            self.assertNotIn(str(root),out.read_text())
            self.assertEqual(analyze_bundle(bundle)['measurement_report']['cases'][0]['display_values'],[10,90])


if __name__=='__main__':unittest.main(verbosity=2)
