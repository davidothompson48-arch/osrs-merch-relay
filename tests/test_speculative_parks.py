import unittest

import build_speculative_parks as sp
import inject_speculative_parks as injector


class SpeculativeParkTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "policy": {
                "minimum_effective_catalyst_probability_pct": 35,
                "park_now_score": 67,
                "deep_bid_score": 55,
                "default_do_not_chase_premium_to_24h_avg_pct": 1.5,
            },
            "score_weights": {
                "effective_catalyst_probability": 0.30,
                "base_conviction": 0.20,
                "asymmetric_upside": 0.20,
                "price_opportunity": 0.15,
                "liquidity": 0.15,
            },
        }
        self.model = {
            "scenarios": [
                {"probability_pct": 50},
                {"probability_pct": 40},
                {"probability_pct": 10},
            ]
        }
        self.candidate = {
            "item_id": 1,
            "name": "Test item",
            "theme": "test",
            "correlation_bucket": "test",
            "probability_model_id": "test_model",
            "scenario_weights": {"0": 1.0, "1": 0.5},
            "base_conviction_0_100": 80,
            "asymmetric_upside_0_100": 80,
            "preferred_discount_to_24h_avg_pct": 10,
            "max_position_pct_of_liquid_gp": 5,
            "expected_horizon_days": 30,
            "thesis": "test thesis",
            "invalidation": "test invalidation",
        }

    def market_row(self, current=90, day=100, now=1_000_000):
        return {
            "current": {
                "high": current,
                "low": current,
                "highTime": now - 30,
                "lowTime": now - 30,
            },
            "1h": {
                "avgHighPrice": current,
                "avgLowPrice": current,
                "highPriceVolume": 1000,
                "lowPriceVolume": 1000,
            },
            "24h": {
                "avgHighPrice": day,
                "avgLowPrice": day,
                "highPriceVolume": 5_000_000,
                "lowPriceVolume": 5_000_000,
            },
        }

    def test_effective_probability_supports_partial_scenarios(self):
        self.assertEqual(sp.effective_probability(self.model, {"0": 1.0, "1": 0.5}), 70.0)

    def test_price_opportunity_builds_patient_entry(self):
        row = self.market_row(current=100, day=100)
        price = sp.price_opportunity(row, self.candidate, self.cfg["policy"])
        self.assertEqual(price["ideal_entry_gp"], 90)
        self.assertEqual(price["entry_zone_high_gp"], 95)
        self.assertEqual(price["do_not_chase_gp"], 102)

    def test_deep_discount_can_promote_park_now(self):
        now = 1_000_000
        row = self.market_row(current=90, day=100, now=now)
        ranked = sp.rank_candidate(self.candidate, row, self.model, self.cfg, now)
        self.assertEqual(ranked["status"], "PARK_NOW")
        self.assertGreaterEqual(ranked["rank_score"], 67)

    def test_crowded_price_blocks_action(self):
        now = 1_000_000
        row = self.market_row(current=110, day=100, now=now)
        ranked = sp.rank_candidate(self.candidate, row, self.model, self.cfg, now)
        self.assertEqual(ranked["status"], "WATCH_CROWDED")

    def test_injector_compacts_full_snapshot(self):
        snapshot = {
            "schema_version": 1,
            "generated_at": "x",
            "generated_unix": 1,
            "source": "source",
            "enabled": True,
            "rollout_status": "ADVISORY",
            "allocation_authoritative": False,
            "cash_competes": True,
            "objective": "objective",
            "portfolio_policy": {"total_speculative_cap_pct_of_liquid_gp": 30},
            "actionable_count": 1,
            "candidate_count": 2,
            "missing_market_rows": [],
            "top_candidates": [{"name": "A"}],
            "all_candidates": [{"name": "A"}, {"name": "B"}],
            "allocation_note": "note",
        }
        block = injector.compact(snapshot)
        self.assertIn("top_candidates", block)
        self.assertNotIn("all_candidates", block)
        self.assertFalse(block["allocation_authoritative"])


if __name__ == "__main__":
    unittest.main()
