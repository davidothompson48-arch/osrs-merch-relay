import unittest

import build_desk_lite
import optimize_allocation as allocation


def config(rollout_status="OBSERVATION_ONLY"):
    return {
        "phase2": {
            "slot_architecture": {
                "active_max_expected_hold_hours": 6,
            }
        },
        "phase3": {
            "minimum_absolute_profit_hurdles": {
                "enabled": True,
                "rollout_status": rollout_status,
                "minimum_expected_profit_gp_by_slot_bucket": {
                    "ACTIVE": 50_000,
                    "PARKING": 250_000,
                    "FLEXIBLE": 75_000,
                },
                "evaluation_basis": "test",
                "promotion_rule": "test",
            }
        },
    }


def candidate(engine, name, profit_gp, hold_hours, **extra):
    row = {
        "engine": engine,
        "name": name,
        "expected_profit_at_capacity_gp": profit_gp,
        "expected_gp_per_hour": max(1, int(profit_gp / hold_hours)),
        "expected_after_tax_roi_pct": 1.0,
        "expected_hold_hours": hold_hours,
        "capacity_gp": 1_000_000,
        "profit_efficiency_score": 70,
    }
    row.update(extra)
    return row


class MinimumAbsoluteProfitHurdleTests(unittest.TestCase):
    def test_bucket_thresholds_are_annotated_without_filtering_observation_mode(self):
        profit = {
            "fast_flip_capacity_velocity": [
                candidate("fast_flip", "Active fail", 49_999, 2, auto_allocation_eligible=True),
            ],
            "evergreen_capacity_velocity": [
                candidate("evergreen", "Parking pass", 250_000, 72),
            ],
            "conversion_capacity_velocity": [
                candidate("conversion", "Flexible pass", 75_000, 4),
            ],
        }

        rows = allocation.sanitized_rows(profit, config())
        by_name = {row["item_or_strategy"]: row for row in rows}

        self.assertEqual(len(rows), 3)
        self.assertFalse(by_name["Active fail"]["minimum_absolute_profit_hurdle_pass"])
        self.assertEqual(by_name["Active fail"]["minimum_absolute_profit_shortfall_gp"], 1)
        self.assertTrue(by_name["Parking pass"]["minimum_absolute_profit_hurdle_pass"])
        self.assertTrue(by_name["Flexible pass"]["minimum_absolute_profit_hurdle_pass"])
        self.assertEqual(len(allocation.allocation_rows(rows, config())), 3)

    def test_hurdles_filter_only_after_explicit_allocation_authority(self):
        rows = [
            allocation.annotate_minimum_profit_hurdle({
                "item_or_strategy": "fail",
                "slot_bucket": "ACTIVE",
                "expected_profit_at_capacity_gp": 10_000,
            }, config("ALLOCATION_AUTHORITATIVE")),
            allocation.annotate_minimum_profit_hurdle({
                "item_or_strategy": "pass",
                "slot_bucket": "ACTIVE",
                "expected_profit_at_capacity_gp": 50_000,
            }, config("ALLOCATION_AUTHORITATIVE")),
        ]

        filtered = allocation.allocation_rows(rows, config("ALLOCATION_AUTHORITATIVE"))

        self.assertEqual([row["item_or_strategy"] for row in filtered], ["pass"])

    def test_unvalidated_fast_flip_cannot_bypass_existing_persistence_gate(self):
        profit = {
            "fast_flip_capacity_velocity": [
                candidate("fast_flip", "Flash spread", 1_000_000, 2, auto_allocation_eligible=False),
            ]
        }

        rows = allocation.sanitized_rows(profit, config())

        self.assertEqual(rows, [])

    def test_conversion_hurdle_uses_player_time_adjusted_profit(self):
        row = candidate("conversion", "Manual conversion", 100_000, 4)
        row.pop("expected_profit_at_capacity_gp")
        row["player_time_adjusted_profit_gp"] = 74_000
        profit = {"conversion_capacity_velocity": [row]}

        rows = allocation.sanitized_rows(profit, config())

        self.assertEqual(rows[0]["expected_profit_at_capacity_gp"], 74_000)
        self.assertFalse(rows[0]["minimum_absolute_profit_hurdle_pass"])
        self.assertEqual(rows[0]["minimum_absolute_profit_shortfall_gp"], 1_000)

    def test_summary_is_advisory_and_reports_bucket_counts(self):
        rows = [
            allocation.annotate_minimum_profit_hurdle({
                "engine": "fast_flip",
                "item_or_strategy": "fail",
                "slot_bucket": "ACTIVE",
                "expected_profit_at_capacity_gp": 10_000,
                "profit_efficiency_score": 80,
            }, config()),
            allocation.annotate_minimum_profit_hurdle({
                "engine": "evergreen",
                "item_or_strategy": "pass",
                "slot_bucket": "PARKING",
                "expected_profit_at_capacity_gp": 300_000,
                "profit_efficiency_score": 70,
            }, config()),
        ]

        summary = allocation.minimum_profit_hurdle_summary(rows, config())

        self.assertFalse(summary["allocation_authoritative"])
        self.assertTrue(summary["would_change_current_frontiers"])
        self.assertEqual(summary["evaluated_candidates"], 2)
        self.assertEqual(summary["passed_candidates"], 1)
        self.assertEqual(summary["failed_candidates"], 1)
        self.assertEqual(summary["by_slot_bucket"]["ACTIVE"]["failed"], 1)

    def test_lite_packet_does_not_repeat_hurdle_detail_across_frontiers(self):
        row = {
            "item_or_strategy": "candidate",
            "minimum_absolute_profit_hurdle_gp": 50_000,
            "minimum_absolute_profit_hurdle_pass": False,
            "minimum_absolute_profit_shortfall_gp": 40_000,
        }
        summary = {
            "rollout_status": "OBSERVATION_ONLY",
            "advisory_failures": [{"item_or_strategy": "candidate"}],
        }

        compact_row = build_desk_lite.compact_frontier_row(row)
        compact_summary = build_desk_lite.compact_hurdle_summary(summary)

        self.assertNotIn("minimum_absolute_profit_hurdle_gp", compact_row)
        self.assertNotIn("minimum_absolute_profit_hurdle_pass", compact_row)
        self.assertEqual(compact_summary["advisory_failures"], [{"item_or_strategy": "candidate"}])


if __name__ == "__main__":
    unittest.main()
