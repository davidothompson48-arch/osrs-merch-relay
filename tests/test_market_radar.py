import unittest
from datetime import datetime, timezone, timedelta
import build_market_radar as radar


class RadarTests(unittest.TestCase):
    now = 1_800_000_000

    def sample(self, name, price=100, before=100, vol=10000, crossed=False, stale=False):
        return {
            'id': 1, 'name': name,
            'current': {
                'high': price if not crossed else price-5,
                'low': price-1 if not crossed else price,
                'highTime': self.now-(9000 if stale else 5),
                'lowTime': self.now-5,
            },
            '24h': {
                'avgHighPrice': before, 'avgLowPrice': before,
                'highPriceVolume': vol//2, 'lowPriceVolume': vol//2,
            },
        }

    def test_fresh_only(self):
        self.assertIsNotNone(radar.valid_price(self.sample('x'), self.now))
        self.assertIsNone(radar.valid_price(self.sample('x', crossed=True), self.now))
        self.assertIsNone(radar.valid_price(self.sample('x', stale=True), self.now))

    def test_minimum_comparable_constituents(self):
        self.assertIsNone(radar.geom_ratio({'a': 90, 'b': 80}, {'a': 100, 'b': 100})[0])
        pct, n = radar.geom_ratio({'a': 90, 'b': 90, 'c': 90}, {'a': 100, 'b': 100, 'c': 100})
        self.assertEqual(n, 3)
        self.assertAlmostEqual(pct, -10)

    def test_old_daily_baseline(self):
        names = ['Bandos chestplate', 'Bandos tassets', 'Torva platebody']
        rows = {x: self.sample(x, price=90, before=100) for x in names}
        past = (datetime.fromtimestamp(self.now, timezone.utc)-timedelta(days=8)).date().isoformat()
        hist = [{'date': past, 'midpoints': {x: 100 for x in rows}}]
        result, _, _ = radar.compute(rows, self.now, hist)
        self.assertEqual(result['multi_day_selected_basket'][0]['items_compared'], 3)
        self.assertAlmostEqual(result['multi_day_selected_basket'][0]['cash_purchasing_power_proxy_change_pct'], 11.728, places=2)

    def test_no_made_up_multi_day_history(self):
        names = ['Bandos chestplate', 'Bandos tassets', 'Torva platebody']
        result, _, _ = radar.compute({x:self.sample(x) for x in names}, self.now, [])
        self.assertIsNone(result['multi_day_selected_basket'][0]['item_price_index_change_pct'])


if __name__ == '__main__':
    unittest.main()
