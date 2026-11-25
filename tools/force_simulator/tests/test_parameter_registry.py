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
        self.assertEqual(len(pitch['controls']),12)
        self.assertIsNone(next(c for c in pitch['controls'] if c['id']=='vc_1_semi_1')['route'])
        self.assertIsNotNone(next(c for c in pitch['controls'] if c['id']=='quality_1')['route'])

    def test_vst_registry_identity_order_remains_append_only(self):
        rows=_load_vst_controls()
        self.assertEqual(len(rows),19)
        self.assertEqual(rows[(1,'decay_time')]['canonical_identity'],'factory_v4_slot1_decay_time')
        self.assertEqual(rows[(1,'decay_time')]['host_parameter_index'],48)

if __name__=='__main__': unittest.main(verbosity=2)
