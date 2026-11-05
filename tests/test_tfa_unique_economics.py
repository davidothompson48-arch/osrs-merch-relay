import unittest
import build_tfa_unique_economics as m

CFG = {
    "team_unique_base_denominator": 14,
    "additional_player_bonus_beyond_two_pct": 4,
    "included_group_sizes": [1, 2, 4, 8],
    "unique_rewards": [
        {"name":"Rondache", "id":1, "weight":5},
        {"name":"Zorya's tome (uncharged)", "id":2, "weight":4},
        {"name":"Horn of Bran", "id":3, "weight":3},
        {"name":"Ascension crossbows", "id":4, "weight":2},
        {"name":"Obligator (uncharged)", "id":5, "weight":1},
    ],
}
TAX = {"rate": 0.02, "cap_gp_per_item": 5_000_000, "exempt_items": []}


class TfaEconomicsTests(unittest.TestCase):
    def market(self, now=18000000):
        prices={1:14_000_000,2:24_000_000,3:330_000_000,4:282_000_000,5:2_910_000_000}
        return {str(i):{
            "current":{"high":p+100,"low":p,"highTime":now-120,"lowTime":now-90},
            "24h":{"highPriceVolume":20,"lowPriceVolume":15}
        } for i,p in prices.items()}

    def test_group_bonus_is_multiplicative_not_absolute_4_points(self):
        self.assertAlmostEqual(m.team_probability(2, CFG), 1/14)
        self.assertAlmostEqual(m.team_probability(4, CFG), 1.08/14)
        self.assertAlmostEqual(m.team_probability(8, CFG), 1.24/14)
        self.assertAlmostEqual(m.team_probability(1, CFG), 1/14)
        with self.assertRaises(ValueError): m.team_probability(9, CFG)

    def test_unique_weights_redistribute_expected_supply(self):
        observed=m.expected_uniques_per_n_team_completions(2, 1000, CFG)
        self.assertAlmostEqual(observed["Rondache"], 1000/14*5/15, places=2)
        self.assertAlmostEqual(observed["Obligator (uncharged)"], 1000/14*1/15, places=2)

    def test_values_use_after_tax_latest_low(self):
        now=18000000
        result=m.analyze(CFG,TAX,self.market(now),now)
        self.assertEqual(result["status"],"READY")
        prices={x["item"]:x for x in result["rewards"]}
        self.assertEqual(prices["Obligator (uncharged)"]["net_after_tax_sell_gp"],2_905_000_000)
        self.assertEqual(prices["Rondache"]["net_after_tax_sell_gp"],13_720_000)
        self.assertGreater(prices["Obligator (uncharged)"]["share_of_total_expected_unique_gp_pct"],60)
        self.assertEqual(len(result["groups"]),4)

    def test_missing_price_refuses_full_ev(self):
        now=18000000
        rows=self.market(now)
        del rows["5"]
        result=m.analyze(CFG,TAX,rows,now)
        self.assertEqual(result["status"],"INCOMPLETE_PRICE_TAPE")
        self.assertEqual(result["groups"],[])
        self.assertIn("Obligator (uncharged)",result["missing_or_stale"])

    def test_stale_crossed_quotes_rejected(self):
        now=18000000
        rows=self.market(now)
        rows["1"]["current"]["high"]=1
        result=m.analyze(CFG,TAX,rows,now)
        self.assertIn("Rondache",result["missing_or_stale"])
        rows=self.market(now)
        rows["1"]["current"]["lowTime"]=now-9000
        result=m.analyze(CFG,TAX,rows,now)
        self.assertIn("Rondache",result["missing_or_stale"])


if __name__=="__main__":
    unittest.main()
