import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MarketCatalystConfigurationTests(unittest.TestCase):
    @staticmethod
    def load(name):
        return json.loads((ROOT / 'project' / name).read_text(encoding='utf8'))

    def test_no_resolved_raid_launch_model_is_active(self):
        data = self.load('probability_models.json')
        active = {m['id'] for m in data['models']}
        self.assertNotIn('breaker_charge_rune', active)
        self.assertNotIn('legacy_elemental_hardware', active)
        self.assertNotIn('inquisitor_crush_demand', active)
        for model in data['models']:
            self.assertAlmostEqual(sum(float(s['probability_pct']) for s in model['scenarios']), 100)

    def test_no_invalidated_wrath_park(self):
        parks = self.load('speculative_parks.json')
        models = {m['id'] for m in self.load('probability_models.json')['models']}
        self.assertNotIn('Wrath rune', {c['name'] for c in parks['candidates']})
        self.assertTrue(all(c['probability_model_id'] in models for c in parks['candidates']))
        self.assertFalse(parks['allocation_authoritative'])

    def test_dragonbane_concentration_cap(self):
        parks = self.load('speculative_parks.json')
        total = sum(c['max_position_pct_of_liquid_gp'] for c in parks['candidates']
                    if c.get('correlation_bucket') == 'gemstone_dragons_2027')
        self.assertLessEqual(total, 18)
        self.assertLessEqual(parks['policy']['total_speculative_cap_pct_of_liquid_gp'], 30)

    def test_obligator_recipe_verified_and_wrath_disproven(self):
        records = {r['id']: r for r in self.load('catalyst_database.json')['records']}
        self.assertEqual(records['fractured_archive_breaker_unspecified_rune']['status'], 'DISPROVEN')
        verified = records['obligator_live_charge_recipe_oct20']
        self.assertEqual(verified['credibility'], 'CONFIRMED')
        self.assertIn('20 Nature', verified['summary'])
        self.assertIn('20 Death', verified['summary'])


if __name__ == '__main__':
    unittest.main()
