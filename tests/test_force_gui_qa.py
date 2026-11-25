import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

class ForceGuiQaTests(unittest.TestCase):
    def test_static_hidden_q_link_is_flagged(self):
        m=load('skin_inspector','tools/force_gui_qa/inspect_skin.py')
        import tempfile,json
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/'bg.png').write_bytes(b'x')
            ui={'backgroundImage':'bg.png','pages':[{'name':'EDIT','controls':[{}]}]}
            comp={'componentData':{'name':'HALL PARAM','type':'slider'},'handle remapping':{'map':[{'key':'Data','value':'Parameter 8'}]},'bounds':{'bounds':'10 10 20 20','whenVisible':'Always','additionalInvalidatingHandles':['IndexedEnabling/0/50/Parameter 0']}}
            tui={'pageData':{'tabs':[{'tabName':'EDIT','fnKeyIndex':0,'componentDefinition':{'componentsData':[comp]}}],'componentDefinitions':{'localComponentDefinitions':[]}}}
            q={'Screen Mode Q-Links':{'map':[{'Q-Links':{'Q-Link 1':8}}]}}
            for fn,d in [('u.json',ui),('t.json',tui),('q.json',q)]: (p/fn).write_text(json.dumps(d))
            r=m.analyze(p/'u.json',p/'t.json',p/'q.json',p)
            self.assertTrue(any(x['code']=='STATIC_QLINK_CONDITIONAL_WIDGET' for x in r['findings']))

    def test_qlink_trace_does_not_accept_host_event_as_dsp_proof(self):
        m=load('trace_gate','tools/force_gui_qa/validate_qlink_trace.py')
        base={'effect_slot':1,'parameter_id':'reverb_mix_bus1','page':'EDIT','bank':'SubTab 1','qlink':1,'host_parameter_index':8,'physical_label':'BUS1 29','expected_label':'BUS1 29','label_matches':True,'available':True,'availability_checked':True,'host_event_seen':True,'internal_parameter_before':28,'internal_parameter_after':29,'register_writes_before':[[124,'0x3D0000']],'register_writes_after':[[124,'0x3F0000']],'expected_internal_change':True,'expected_register_write_group':[[124,'0x3F0000']],'observed_register_write_group':[[124,'0x3F0000']],'reverse_value':28,'reverse_restored':True,'reverse_register_group_restored':True,'unrelated_state_unchanged':True,'repeated_value_stable':True,'save_reload_restored':True}
        doc={'evidence_source':'independent binary-bound trace','candidate_id':'test','source_commit':'a'*40,'plugin_binary_sha256':'a'*64,'runtime_trace_sha256':'b'*64,'expected_controls':[base.copy()],'cases':[base.copy()]}
        self.assertEqual(m.validate(doc),[])
        doc['cases'][0]['observed_register_write_group']=doc['cases'][0]['register_writes_before']
        self.assertTrue(any('DSP register' in e for e in m.validate(doc)))

if __name__=='__main__': unittest.main()
