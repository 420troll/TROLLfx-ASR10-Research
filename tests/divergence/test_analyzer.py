import importlib.util, json, pathlib, tempfile, unittest
P=pathlib.Path(__file__).resolve().parents[2]/'tools/divergence/analyzer.py'
spec=importlib.util.spec_from_file_location('analyzer',P); a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
def trace(name,events,rate=44100,complete=None,initial=None):
 t=a.new_trace(name,name,rate,events=events,complete_event_types=complete or ['instruction','register_write','ram_write','serial_input','serial_output','firmware_write','state_transition'],metadata={'clock_frame_basis':'synthetic'})
 t['initial_state']=initial; t['coverage']['observed_event_types']=sorted({e['event_type'] for e in events}); return t
def ev(frame,typ,**kw): return {'frame':frame,'event_type':typ,**kw}
class TraceAnalyzerTests(unittest.TestCase):
 def test_identical(self):
  x=trace('x',[ev(0,'instruction',instruction_index=0,program_counter=0,instruction_word='abc'),ev(0,'register_write',instruction_index=0,register=4,value=8)],initial={})
  r=a.compare(x,json.loads(json.dumps(x))); self.assertEqual(r['classification'],'no_observed_divergence')
 def test_missing_gpr_update(self):
  x=trace('x',[ev(0,'register_write',instruction_index=1,register=8,value=3)]); y=trace('y',[])
  r=a.compare(x,y); self.assertEqual(r['earliest_confirmed_divergence']['kind'],'extra_or_missing_event'); self.assertEqual(r['earliest_confirmed_divergence']['category'],'register_write_ordering')
 def test_one_frame_write_offset(self):
  x=trace('x',[ev(4,'register_write',instruction_index=1,register=8,value=3)]); y=trace('y',[ev(5,'register_write',instruction_index=1,register=8,value=3)])
  r=a.compare(x,y); self.assertIn('frame_offset',[f['kind'] for f in r['findings']]); self.assertEqual(r['earliest_confirmed_divergence']['frame'],4)
 def test_same_frame_order_mismatch(self):
  x=trace('x',[ev(0,'register_write',event_order=1,register=8,value=3),ev(0,'register_write',event_order=2,register=9,value=4)])
  y=trace('y',[ev(0,'register_write',event_order=1,register=9,value=4),ev(0,'register_write',event_order=2,register=8,value=3)])
  self.assertIn('same_frame_event_order',[f['kind'] for f in a.compare(x,y)['findings']])
 def test_ram_pipeline_divergence(self):
  x=trace('x',[ev(0,'ram_write',instruction_index=2,address=99,value=2)],complete=['ram_write']); y=trace('y',[ev(0,'ram_write',instruction_index=2,address=98,value=2)],complete=['ram_write'])
  r=a.compare(x,y); self.assertEqual(r['earliest_confirmed_divergence']['category'],'ram_address_data_differences')
 def test_serial_input_misalignment(self):
  x=trace('x',[ev(3,'serial_input',sample_index=4,value=100)],complete=['serial_input']); y=trace('y',[ev(3,'serial_input',sample_index=4,value=99)],complete=['serial_input'])
  self.assertEqual(a.compare(x,y)['earliest_confirmed_divergence']['category'],'serial_input_output_alignment')
 def test_different_sample_rates(self):
  r=a.compare(trace('x',[],44100),trace('y',[],48000)); self.assertEqual(r['earliest_confirmed_divergence']['kind'],'timing_basis_mismatch')
 def test_incomplete_fields_are_unknown_not_equal_claim(self):
  x=trace('x',[ev(0,'instruction',instruction_index=0,program_counter=0)]); y=trace('y',[ev(0,'instruction',instruction_index=0,program_counter=0,instruction_word='abc')])
  r=a.compare(x,y); self.assertTrue(r['unknown_comparisons']); self.assertIsNone(r['earliest_confirmed_divergence'])
 def test_instruction_sequence_mismatch(self):
  x=trace('x',[ev(0,'instruction',instruction_index=0,program_counter=0,instruction_word='aaa')]); y=trace('y',[ev(0,'instruction',instruction_index=0,program_counter=1,instruction_word='bbb')])
  self.assertEqual(a.compare(x,y)['earliest_confirmed_divergence']['category'],'arithmetic_or_execution_differences')
 def test_initial_state_mismatch_classified(self):
  r=a.compare(trace('x',[],initial={'gpr_4':1}),trace('y',[],initial={'gpr_4':2})); self.assertEqual(r['earliest_confirmed_divergence']['category'],'initialization_state_differences')
 def test_missing_firmware_write(self):
  x=trace('x',[ev(2,'firmware_write',register=4,value=5,source='os')]); y=trace('y',[])
  r=a.compare(x,y); self.assertEqual(r['earliest_confirmed_divergence']['category'],'missing_firmware_events')
 def test_cycle_offset_not_derived_from_frame(self):
  x=trace('x',[ev(0,'firmware_write',cycle=40,register=4,value=5,source='os')]); y=trace('y',[ev(0,'firmware_write',cycle=41,register=4,value=5,source='os')])
  f=a.compare(x,y)['earliest_confirmed_divergence']; self.assertEqual(f['kind'],'instruction_cycle_offset'); self.assertEqual(f['frame'],0)
 def test_write_phase_order_is_explicit_when_supplied(self):
  x=trace('x',[ev(0,'firmware_write',register=4,value=5,source='os',timing_phase='before_consumer')]); y=trace('y',[ev(0,'firmware_write',register=4,value=5,source='os',timing_phase='after_consumer')])
  self.assertEqual(a.compare(x,y)['earliest_confirmed_divergence']['kind'],'write_phase_mismatch')
 def test_serial_sample_counter_offset(self):
  x=trace('x',[ev(0,'serial_input',sample_index=7,value=1)],complete=['serial_input']); y=trace('y',[ev(0,'serial_input',sample_index=8,value=1)],complete=['serial_input'])
  self.assertIn('serial_sample_index_mismatch',[f['kind'] for f in a.compare(x,y)['findings']])
 def test_boundary_shift_and_selected_register_isolation(self):
  x=trace('x',[ev(0,'instruction',instruction_index=0),ev(0,'register_write',instruction_index=0,register=8,value=1),ev(0,'register_write',instruction_index=1,register=9,value=2)])
  shifted=a.transform(x,[{'kind':'shift_event_boundary','event_index':1,'boundaries':1}]); self.assertEqual(shifted['events'][1]['instruction_index'],1)
  isolated=a.transform(x,[{'kind':'only_gpr_writes','registers':[9]}]); self.assertEqual([e.get('register') for e in isolated['events'] if e['event_type']=='register_write'],[9])
 def test_order_swap_transform_is_diagnostic_only(self):
  x=trace('x',[ev(0,'register_write',event_order=1,register=8,value=1),ev(0,'register_write',event_order=2,register=9,value=2)])
  y=a.transform(x,[{'kind':'swap_event_order','frame':0,'first_index':0,'second_index':1}])
  self.assertNotEqual([e['register'] for e in x['events']],[e['register'] for e in y['events']]); self.assertIn('diagnostic hypothesis',y['trace_id'])
 def test_initial_state_only_removes_runtime_events(self):
  x=trace('x',[ev(0,'state_transition',state='RUN'),ev(1,'firmware_write',register=8,value=1,source='os')],initial={'gpr_8':0})
  y=a.transform(x,[{'kind':'initial_state_only'}]); self.assertEqual([e['event_type'] for e in y['events']],['state_transition'])
 def test_boundary_shift_requires_explicit_boundary(self):
  x=trace('x',[ev(0,'serial_frame',input_left=1)])
  with self.assertRaisesRegex(ValueError,'no instruction-boundary observation'):
   a.transform(x,[{'kind':'shift_event_boundary','event_index':0,'boundaries':1}])
 def test_timing_hypothesis_is_labeled_and_nonmutating(self):
  x=trace('x',[ev(1,'register_write',register=8,value=2)]); y=a.transform(x,[{'kind':'shift_gpr_frame','register':8,'frames':1}])
  self.assertEqual(x['events'][0]['frame'],1); self.assertEqual(y['events'][0]['frame'],2); self.assertIn('diagnostic hypothesis',y['trace_id'])
 def test_csv_import_existing_trace(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'t.csv'; p.write_text('I,0,00,000000000001\nRQ,0,00,0,0,00000000\nW,0,00,008,000123\nEND,0,02\nROUTE,0,1,2,3,4,20\n')
   t=a.import_csv(p,'csv','original'); self.assertFalse(a.valid_trace(t)); self.assertIn('instruction',t['coverage']['complete_event_types']); self.assertEqual(t['metadata']['serial_frame_scope'],'first frame only')
if __name__=='__main__': unittest.main()
