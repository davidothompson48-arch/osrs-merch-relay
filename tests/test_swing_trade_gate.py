import unittest
import build_swing_trade_gate as g

TAX = {"rate": 0.02, "cap_gp_per_item": 5_000_000, "exempt_items": ["Mind rune"]}


class SwingTradeGateTests(unittest.TestCase):
    def candidate(self, status="DEEP_BID", high=10_000_000, low=9_700_000,
                  freshness="FRESH", ceiling=9_800_000):
        return {
            "name": "Test blade", "item_id": 999, "status": status,
            "execution_gate": "CLEAR", "rank_score": 80,
            "entry": {"ideal_gp": 9_000_000, "zone_high_gp": ceiling},
            "market": {
                "high": high, "low": low,
                "freshness": freshness,
                "twenty_four_hour_mid": 11_000_000,
                "twenty_four_hour_volume": 350,
            }
        }

    def test_exact_after_tax_breakeven(self):
        price = g.minimum_exit(10_000_000, "Test blade", TAX, 0)
        self.assertEqual(price, 10_204_082)
        self.assertGreaterEqual(g.net_sale(price, "Test blade", TAX), 10_000_000)
        self.assertLess(g.net_sale(price-1, "Test blade", TAX), 10_000_000)

    def test_ge_tax_cap_and_exemptions(self):
        self.assertEqual(g.tax(400_000_000, "Test blade", TAX), 5_000_000)
        self.assertEqual(g.tax(100, "Mind rune", TAX), 0)
        self.assertEqual(g.tax(49, "Test blade", TAX), 0)

    def test_5pct_profit_is_after_tax(self):
        target = g.minimum_exit(37_000_000, "Dragon hunter lance", TAX, 5)
        self.assertGreaterEqual(g.net_sale(target, "Dragon hunter lance", TAX), 38_850_000)
        self.assertLess(g.net_sale(target-1, "Dragon hunter lance", TAX), 38_850_000)

    def test_crowded_candidate_not_promoted(self):
        row = g.evaluate(self.candidate(status="WATCH_CROWDED"), TAX)
        self.assertEqual(row["execution_action"], "WATCH_ONLY")
        self.assertIsNone(row["after_tax_scenarios"])
        self.assertIn("NOT_AN_ENTRY_CANDIDATE", row["rejection_reasons"])

    def test_stale_and_crossed_quotes_not_promoted(self):
        row = g.evaluate(self.candidate(freshness="STALEISH"), TAX)
        self.assertIn("QUOTES_NOT_FRESH_ENOUGH", row["rejection_reasons"])
        row = g.evaluate(self.candidate(high=9_000_000, low=9_100_000), TAX)
        self.assertIn("CROSSED_OR_ASYNCHRONOUS_QUOTES", row["rejection_reasons"])

    def test_patient_bid_price_ceiling_blocks_instant_buy(self):
        row = g.evaluate(self.candidate(), TAX, radar_status="READY")
        self.assertEqual(row["execution_action"], "WAIT_OR_RESEARCH_ONLY")
        self.assertIn("INSTANT_BUY_ABOVE_PATIENT_ENTRY_CEILING", row["rejection_reasons"])
        self.assertIn("HOLDINGS_AND_CASH_UNRECONCILED", row["rejection_reasons"])
        self.assertIsNotNone(row["after_tax_scenarios"]["breakeven_exit_gp"])
        self.assertFalse(row["cash_sizing_authorized"])

    def test_no_unconfirmed_fill_claim(self):
        row = g.evaluate(self.candidate(high=9_700_000), TAX, ledger_stale=False, radar_status="READY")
        self.assertFalse(row["cash_sizing_authorized"])
        self.assertEqual(row["execution_action"], "RESEARCH_ONLY_NO_CASH_AUTHORITY")
        self.assertFalse(any("filled" in str(v).lower() for v in row.values()))


if __name__ == "__main__":
    unittest.main()
