import unittest

import real_execution_learning as learning


class RealizedPerformanceDashboardTests(unittest.TestCase):
    def test_dashboard_uses_only_confirmed_round_trip_economics(self):
        order_map = {
            "b1": {"item": "Item A", "engine": "fast_flip", "avg_fill_price_gp_each": 100, "filled_quantity": 10, "filled_at_utc": "2026-01-01T00:00:00Z"},
            "s1": {"item": "Item A", "engine": "fast_flip", "avg_fill_price_gp_each": 120, "filled_quantity": 10, "filled_at_utc": "2026-01-01T01:00:00Z"},
            "b2": {"item": "Item B", "engine": "evergreen", "avg_fill_price_gp_each": 100, "filled_quantity": 10, "filled_at_utc": "2026-01-01T02:00:00Z"},
            "s2": {"item": "Item B", "engine": "evergreen", "avg_fill_price_gp_each": 90, "filled_quantity": 10, "filled_at_utc": "2026-01-01T03:00:00Z"},
        }
        round_trips = [
            {"entry_order_id": "b1", "exit_order_id": "s1", "quantity": 10},
            {"entry_order_id": "b2", "exit_order_id": "s2", "quantity": 10},
        ]
        cfg = {"phase4": {"realized_performance_dashboard": {
            "minimum_round_trips_before_strategy_ranking": 2,
            "minimum_timed_round_trips_before_gp_hour_authority": 2,
        }}}

        stats = learning.round_trip_stats(round_trips, order_map, {"rate": 0.02, "cap_gp_per_item": 5_000_000}, cfg)
        dashboard = stats["performance_dashboard"]

        self.assertEqual(dashboard["completed_round_trips"], 2)
        self.assertEqual(dashboard["wins"], 1)
        self.assertEqual(dashboard["losses"], 1)
        self.assertEqual(dashboard["realized_net_profit_gp"], 70)
        self.assertEqual(dashboard["capital_deployed_gp"], 2_000)
        self.assertEqual(dashboard["realized_roi_pct"], 3.5)
        self.assertEqual(dashboard["aggregate_realized_gp_per_slot_hour"], 35)
        self.assertTrue(dashboard["strategy_ranking_authoritative"])

    def test_unknown_timestamps_never_create_realized_gp_per_hour(self):
        order_map = {
            "b": {"item": "Item", "engine": "evergreen", "avg_fill_price_gp_each": 100, "filled_quantity": 1, "filled_at_utc": None},
            "s": {"item": "Item", "engine": "evergreen", "avg_fill_price_gp_each": 110, "filled_quantity": 1, "filled_at_utc": None},
        }
        cfg = {"phase4": {"realized_performance_dashboard": {}}}

        stats = learning.round_trip_stats([{"entry_order_id": "b", "exit_order_id": "s"}], order_map, {"rate": 0.02}, cfg)

        self.assertEqual(stats["timed_round_trips"], 0)
        self.assertIsNone(stats["performance_dashboard"]["aggregate_realized_gp_per_slot_hour"])

    def test_untimed_profit_is_excluded_from_gp_per_slot_hour(self):
        order_map = {
            "timed_buy": {"item": "Item", "engine": "evergreen", "avg_fill_price_gp_each": 100, "filled_quantity": 10, "filled_at_utc": "2026-01-01T00:00:00Z"},
            "timed_sell": {"item": "Item", "engine": "evergreen", "avg_fill_price_gp_each": 120, "filled_quantity": 10, "filled_at_utc": "2026-01-01T01:00:00Z"},
            "untimed_buy": {"item": "Item", "engine": "evergreen", "avg_fill_price_gp_each": 100, "filled_quantity": 10, "filled_at_utc": None},
            "untimed_sell": {"item": "Item", "engine": "evergreen", "avg_fill_price_gp_each": 1_000, "filled_quantity": 10, "filled_at_utc": None},
        }
        round_trips = [
            {"entry_order_id": "timed_buy", "exit_order_id": "timed_sell"},
            {"entry_order_id": "untimed_buy", "exit_order_id": "untimed_sell"},
        ]

        stats = learning.round_trip_stats(round_trips, order_map, {"rate": 0.02}, {"phase4": {"realized_performance_dashboard": {}}})
        dashboard = stats["performance_dashboard"]

        self.assertEqual(dashboard["realized_net_profit_gp"], 8_980)
        self.assertEqual(dashboard["timed_realized_net_profit_gp"], 180)
        self.assertEqual(dashboard["aggregate_realized_gp_per_slot_hour"], 180)
        self.assertEqual(dashboard["by_item"]["Item"]["realized_gp_per_slot_hour"], 180)


if __name__ == "__main__":
    unittest.main()
