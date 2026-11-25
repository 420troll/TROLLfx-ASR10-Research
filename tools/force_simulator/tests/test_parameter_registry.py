"""Catalog merge and safe-writable-route policy checks."""
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from parameter_registry import load_registry, _load_vst_controls

class FactoryParameterRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.effects=load_registry()

    def test_all_factory_descriptors_are_available_without_gui_effect_tables(self):
        self.assertEqual(len(self.effects),50)
        self.assertEqual(sum(c['catalog_descriptor'] for e in self.effects for c in e['controls']),594)
        self.assertEqual(sum(c['route'] is not None for e in self.effects for c in e['controls']),19)
        self.assertEqual([e['name'] for e in self.effects[:3]],['HALL REVERB','44KHZ REVERB','ROOM REVERB'])

    def test_full_range_remains_separate_from_exact_vst_points(self):
        hall=self.effects[0]
        decay=next(c for c in hall['controls'] if c['id']=='decay_time_1')
        self.assertEqual(decay['range'],[0.0,99.0])
        self.assertEqual(decay['status'],'PARTIAL')
        self.assertEqual(decay['route']['point_values'],[40,41])
        self.assertEqual(decay['route']['host_parameter_index'],48)
        self.assertIsNone(next(c for c in hall['controls'] if c['id']=='low_freq_decay_1')['route'])
        self.assertIsNotNone(next(c for c in hall['controls'] if c['id']=='reverb_mix_bus1')['route'])

    def test_enumerations_use_observations_and_do_not_gain_routes(self):
        variation=self.effects[0]['controls'][0]
        self.assertEqual(variation['observed_choices'][0],'1 FAVORITE REVERB')
        self.assertEqual(variation['status'],'UNMAPPED')
        pitch=self.effects[38]
        self.assertEqual(sum(c['catalog_descriptor'] for c in pitch['controls']),12)
        self.assertEqual(sum(c.get('editor_visible',True) for c in pitch['controls']),19)
        self.assertIsNone(next(c for c in pitch['controls'] if c['id']=='vc_1_semi_1')['route'])
        self.assertIsNotNone(next(c for c in pitch['controls'] if c['id']=='quality_1')['route'])


    def test_pc_schema_covers_manual_registry_and_keeps_manual_dsp_evidence_separate(self):
        import json
        schema=json.loads((HERE/"data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json").read_text())
        self.assertEqual(schema['coverage']['factory_effects'],50)
        self.assertEqual(schema['coverage']['manual_registry_parameters'],594)
        self.assertEqual(len(schema['effects']),50)
        self.assertTrue(all('manual' in p and 'dsp_evidence' in p for e in schema['effects'] for p in e['parameters']))
        self.assertEqual(schema['manual_source']['pdf_pages'],391)
        self.assertFalse(schema['coverage']['manual_section6_has_rom50_entry'])
        hall=next(effect for effect in schema['effects'] if effect['slot']==1)
        detune=next(p for p in hall['parameters'] if p['manual']['display_name']=='DETUNE AMT')
        self.assertNotIn('PRE-DELAY TIME',detune['manual']['description'])

    def test_manual_expansions_represent_independent_bus_channel_and_repeated_controls(self):
        effects={e['slot']:e for e in self.effects}
        dual=effects[4]['controls']; visible={c['id']:c for c in dual if c.get('editor_visible',True)}
        for ident in ('dual_bus1_delay_mix','dual_bus2_delay_mix','dual_bus1_feedback','dual_bus2_feedback','delay_time_l','dual_bus1_delay_time_r','dual_bus2_delay_time_l','dual_bus2_delay_time_r'):
            self.assertIn(ident,visible)
        self.assertEqual(visible['delay_time_l']['range'],[0,2000])
        self.assertEqual(visible['dual_bus2_delay_time_l']['range'],[0,150])
        self.assertEqual(visible['delay_time_l']['route']['canonical_identity'],'factory_v4_slot4_delay_time_l')
        self.assertEqual(sum(c.get('editor_visible',True) for c in effects[22]['controls'] if c['name'].startswith('ENV LEVEL')),9)
        self.assertEqual(sum(c.get('editor_visible',True) for c in effects[14]['controls'] if c['name'].startswith('POSITN BAL')),3)
        self.assertEqual(sum(c.get('editor_visible',True) for c in effects[17]['controls'] if c['name'].startswith('ER LEVEL')),4)

    def test_manual_range_exceptions_follow_selected_room_or_plate_algorithm(self):
        for slot,expected in [(14,[.2,100.0]),(15,[.2,150.0]),(16,[.7,250.0]),(17,[.2,100.0]),(18,[.4,140.0])]:
            effect=self.effects[slot-1]
            decay=next(c for c in effect['controls'] if c['name']=='DECAY TIME' and c.get('editor_visible',True))
            self.assertEqual(decay['range'],expected)

    def test_modulation_controls_only_exist_where_section6_lists_them(self):
        byslot={e['slot']:e for e in self.effects}
        self.assertFalse(any(c['group']=='Modulation' for c in byslot[1]['controls']))
        self.assertFalse(any(c['group']=='Modulation' for c in byslot[27]['controls']))
        self.assertEqual(sum(c['group']=='Modulation' for c in byslot[14]['controls']),8)
        self.assertEqual(sum(c['group']=='Modulation' for c in byslot[49]['controls']),8)
        self.assertEqual(sum(c['group']=='Modulation' for c in byslot[50]['controls']),0)


    def test_numeric_manual_ranges_keep_units_and_mixed_unit_bounds(self):
        from parameter_registry import _numeric_domain
        self.assertEqual(_numeric_domain('1ms to 10.0s','ms'),([0.001,10.0],'s'))
        bounds,units=_numeric_domain('50µs to 100ms','ms'); self.assertAlmostEqual(bounds[0],0.00005); self.assertAlmostEqual(bounds[1],0.1); self.assertEqual(units,'s')
        self.assertEqual(_numeric_domain('100 Hz to 15 KHz','kHz'),([100.0,15000.0],'Hz'))
        self.assertEqual(_numeric_domain('1KHz to 15KHz','kHz'),([1.0,15.0],'kHz'))
        for effect in self.effects:
            for c in effect['controls']:
                if c.get('editor_visible',True) and c.get('type')=='numeric_or_continuous':
                    self.assertIsNotNone(c['range'],f"missing manual range: slot {effect['slot']} {c['name']}")
                    self.assertLessEqual(c['range'][0],c['range'][1])


    def test_cross_referenced_effect_sections_are_expanded_from_manual_not_whole_effects(self):
        byslot={e['slot']:e for e in self.effects}
        for slot,expected in {
            6:['REVERB DECAY TIME','REVERB DETUNE RATE','REVERB PRE-DELAY TIME'],
            7:['REVERB DECAY TIME','EARLY RFLECTION LEV'],
            9:['REVERB DIFFUSION'],
            10:['BUS1 REV AFTER CHOR','CHORUS FEEDBACK','REVERB LOW FREQ DECAY'],
            11:['BUS2 REVERB MIX','REVERB DETUNE AMT'],
            12:['CHORUS MIX','REVERB HI FREQ BANDWIDTH'],
            13:['COMPRESSOR THRESHLD','SYSTEM FEEDBACK','REVERB DECAY TIME']}.items():
            names={c['name'] for c in byslot[slot]['controls'] if c.get('editor_visible',True)}
            for name in expected:
                if slot==6 and name=='REVERB PRE-DELAY TIME': continue
                self.assertIn(name,names,f"ROM-{slot:02} missing manual cross-reference {name}")
        self.assertNotIn('REVERB PRE-DELAY TIME',{c['name'] for c in byslot[6]['controls'] if c.get('editor_visible',True)})
        self.assertNotIn('REVERB PRE-DELAY TIME',{c['name'] for c in byslot[7]['controls'] if c.get('editor_visible',True)})

    def test_vst_registry_identity_order_remains_append_only(self):
        rows=_load_vst_controls()
        self.assertEqual(len(rows),19)
        self.assertEqual(rows[(1,'decay_time')]['canonical_identity'],'factory_v4_slot1_decay_time')
        self.assertEqual(rows[(1,'decay_time')]['host_parameter_index'],48)

if __name__=='__main__': unittest.main(verbosity=2)
