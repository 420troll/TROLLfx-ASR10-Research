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
        self.assertEqual(visible['dual_bus1_delay_time_r']['independent_classification'],'PARTIAL')
        self.assertEqual(visible['dual_bus1_delay_time_r']['dsp_evidence']['mapping']['observed_setting_points'][0]['display_value'],700)
        env={c['name']:c for c in effects[22]['controls'] if c['name'].startswith('ENV LEVEL')}
        self.assertEqual(sum(c.get('editor_visible',True) for c in env.values()),5)
        self.assertTrue(all(not env[f'ENV LEVEL {n}']['editor_visible'] for n in range(6,10)))
        self.assertIn('five values',effects[22]['manual_group_warnings'][0])
        self.assertEqual(sum(c.get('editor_visible',True) for c in effects[14]['controls'] if c['name'].startswith('POSITN BAL')),3)
        self.assertEqual(sum(c.get('editor_visible',True) for c in effects[17]['controls'] if c['name'].startswith('ER LEVEL')),4)

    def test_independent_qa_crosswalk_preserves_ids_and_separates_evidence_layers(self):
        import json
        adapter=json.loads((HERE/'data/ASR10_EDITOR_EVIDENCE_ADAPTER_V1.json').read_text())
        self.assertEqual(adapter['schema'],'trollfx-asr10-pc-editor-evidence-adapter-v1')
        self.assertEqual(adapter['coverage']['manual_descriptors'],594)
        self.assertEqual(adapter['coverage']['additional_recovered_controls'],13)
        self.assertEqual(adapter['coverage']['dsp_classification'],{'UNKNOWN':51,'PARTIAL':36,'UNMAPPED':507})
        self.assertEqual(adapter['coverage']['full_range_implemented'],0)
        self.assertEqual(len(adapter['provenance']['validation_matrix_sha256']),64)
        for effect in self.effects:
            ids=[c['id'] for c in effect['controls']]
            identities=[c['canonical_identity'] for c in effect['controls']]
            self.assertEqual(len(ids),len(set(ids)),f"duplicate editor IDs in slot {effect['slot']}")
            self.assertEqual(len(identities),len(set(identities)),f"duplicate stable identities in slot {effect['slot']}")
            self.assertTrue(all('original_os_evidence' in c and 'dsp_evidence' in c for c in effect['controls']))
            audited={p['id'] for p in next(e for e in adapter['effects'] if e['slot']==effect['slot'])['parameters']}
            attached={c.get('original_parameter_id') for c in effect['controls']}
            self.assertTrue(audited.issubset(attached),f"unattached manual identities in slot {effect['slot']}: {audited-attached}")
        hall=self.effects[0]
        self.assertEqual(next(c for c in hall['controls'] if c['id']=='decay_time_1')['canonical_identity'],'ASR10:ROM-01:decay_time_1')
        self.assertEqual(next(c for c in hall['controls'] if c['id']=='decay_time_1')['route']['canonical_identity'],'factory_v4_slot1_decay_time')
        mix=next(c for c in hall['controls'] if c['id']=='reverb_mix_bus1')
        self.assertEqual(mix['independent_classification'],'PARTIAL')
        self.assertEqual(mix['original_os_evidence']['labels'],['REVERB MIX BUS1'])
        self.assertTrue(mix['dsp_evidence']['mapping']['observed_setting_points'])
        self.assertFalse(mix['mapping_evidence_mismatch'])
        self.assertEqual(mix['route']['point_values'],[28,29])

    def test_os_inventory_deferred_and_corrected_composite_groups_are_explicit(self):
        byslot={e['slot']:e for e in self.effects}
        self.assertEqual(byslot[2]['os_scan_status'],'deferred')
        self.assertFalse(next(c for c in byslot[2]['controls'] if c['id']=='decay_time_1')['original_os_evidence']['observed'])
        for slot in (14,15,16):
            effect=byslot[slot]
            self.assertEqual(sum(c.get('editor_visible',True) for c in effect['controls'] if c['name']=='DECAY TIME'),1)
        self.assertTrue(all(c['original_parameter_id']=='positn_bal_1_to_3_1' for c in byslot[14]['controls'] if c['id'].startswith('manual_positn_bal_')))

    def test_manual_range_exceptions_follow_selected_room_or_plate_algorithm(self):
        for slot,expected in [(14,[.2,100.0]),(15,[.2,150.0]),(16,[.7,250.0]),(17,[.2,100.0]),(18,[.4,140.0])]:
            effect=self.effects[slot-1]
            decay=next(c for c in effect['controls'] if c['name']=='DECAY TIME' and c.get('editor_visible',True))
            self.assertEqual(decay['range'],expected)

    def test_corrected_manual_reverb_decay_boundaries_and_precision(self):
        expected={15:([.20,150.0],"0.20 to 150.0 sec."),
                  16:([.70,250.0],"0.70 to 250.0 sec."),
                  18:([.4,140.0],"0.4 to 140.0 sec.")}
        for slot,(bounds,source_format) in expected.items():
            effect=self.effects[slot-1]
            decay=next(c for c in effect['controls'] if c['name']=='DECAY TIME' and c.get('editor_visible',True))
            self.assertEqual(decay['range'],bounds)
            self.assertEqual(decay['range_text'],source_format)
            self.assertEqual(decay['units'],'sec')
            self.assertEqual(decay['range'][0],bounds[0])
            self.assertEqual(decay['range'][1],bounds[1])

    def test_generated_schema_exposes_corrected_ranges_as_manual_metadata(self):
        import json
        schema=json.loads((HERE/'data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json').read_text())
        expected={15:([.20,150.0],"0.20 to 150.0 sec."),
                  16:([.70,250.0],"0.70 to 250.0 sec."),
                  18:([.4,140.0],"0.4 to 140.0 sec.")}
        for slot,(bounds,range_text) in expected.items():
            effect=next(e for e in schema['effects'] if e['slot']==slot)
            decay=next(c for c in effect['editable_controls'] if c['name']=='DECAY TIME' and c.get('editor_visible',True))
            self.assertEqual(decay['range'],bounds)
            self.assertEqual(decay['range_text'],range_text)
            self.assertEqual(decay['units'],'sec')

    def test_four_serialized_manual_entries_match_correction_contract(self):
        import json
        schema=json.loads((HERE/'data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json').read_text())
        targets=[(15,'decay_time_small_room_1','DECAY TIME — Large Room','0.20 to 150.0 sec.',[.2,150.0]),
                 (16,'decay_time_small_room_1','DECAY TIME — Hall Reverb2','0.70 to 250.0 sec.',[.7,250.0]),
                 (18,'decay_time_small_plate_1','DECAY TIME — Large Plate','0.4 to 140.0 sec.',[.4,140.0]),
                 (18,'predelay_time_small_plate_1','PREDELAY TIME — Large Plate','0 to 430 ms',[0,430])]
        for slot,parameter_id,label,text,bounds in targets:
            effect=next(e for e in schema['effects'] if e['slot']==slot)
            entry=next(p for p in effect['parameters'] if p['id']==parameter_id)
            manual=entry['manual']
            self.assertEqual(manual['display_name'],label)
            self.assertEqual(manual['documented_range'],text)
            self.assertEqual([manual['documented_numeric_domain']['minimum'],manual['documented_numeric_domain']['maximum']],bounds)
            self.assertTrue(manual['range_correction']['citation']['pdf_page'] in (107,110))

    def test_os2_44khz_appendix_stays_in_separate_manual_namespace(self):
        import json
        schema=json.loads((HERE/'data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json').read_text())
        ns=next(x for x in schema['separate_manual_namespaces'] if x['namespace']=='OS2_44KHZ_APPENDIX')
        self.assertEqual(ns['algorithm_count'],12)
        self.assertFalse(ns['integrated_into_50_factory_effects'])
        self.assertEqual(ns['runtime_relationship'],'unverified; manual-only appendix namespace')
        appendix=json.loads((HERE/'data'/ns['path']).read_text())
        self.assertEqual(len(appendix['effects']),12)
        self.assertEqual(len(schema['effects']),50)

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
