import unittest
from build_desk_lite import compact_market_radar


class LiteMarketRadarTests(unittest.TestCase):
    def test_missing_is_explicit(self):
        self.assertEqual(compact_market_radar({})['status'], None)
        self.assertEqual(compact_market_radar(None)['status'], 'MISSING')

    def test_retains_sector_and_history_and_caps_moves(self):
        source = {
            'status': 'READY',
            'market_universe_unix': 12345,
            'sectors': [{'sector': 'dragonbane', 'current_vs_24h_avg_pct': -3.68}],
            'multi_day_selected_basket': [{'target_days': 7, 'item_price_index_change_pct': None}],
            'unusual_moves': [{'item': str(i)} for i in range(30)]
        }
        result = compact_market_radar(source)
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(len(result['unusual_moves']), 12)
        self.assertEqual(result['sectors'][0]['sector'], 'dragonbane')
        self.assertIsNone(result['multi_day_selected_basket'][0]['item_price_index_change_pct'])


if __name__ == '__main__':
    unittest.main()
