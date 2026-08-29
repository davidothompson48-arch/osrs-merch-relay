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
            "repeatability_class": "EARLY_SAMPLE",
            "repeatability_multiplier_advisory": 0.95,
        }
        summary = {
            "rollout_status": "OBSERVATION_ONLY",
            "advisory_failures": [{"item_or_strategy": "candidate"}],
        }

        compact_row = build_desk_lite.compact_frontier_row(row)
        compact_summary = build_desk_lite.compact_hurdle_summary(summary)

        self.assertNotIn("minimum_absolute_profit_hurdle_gp", compact_row)
        self.assertNotIn("minimum_absolute_profit_hurdle_pass", compact_row)
        self.assertNotIn("repeatability_class", compact_row)
        self.assertEqual(compact_summary["advisory_failures"], [{"item_or_strategy": "candidate"}])

    def test_repeatability_is_advisory_until_explicit_authority_and_data_thresholds(self):
        cfg = config()
        cfg["phase3"]["repeatability_multiplier"] = {
            "enabled": True,
            "rollout_status": "OBSERVATION_ONLY",
            "minimum_real_round_trips_before_authority": 1,
            "advisory_multiplier_by_class": {"INCONSISTENT": 0.75, "UNOBSERVED": 1.0},
        }
        cfg["phase3"]["persistent_opportunity_book"] = {
            "minimum_cycles_before_review": 1,
            "minimum_candidate_observations_before_review": 1,
        }
        row = {
            "engine": "fast_flip",
            "item_or_strategy": "Test item",
            "expected_profit_at_capacity_gp": 100_000,
            "expected_gp_per_hour": 50_000,
            "gp_per_ge_slot_hour": 50_000,
            "profit_efficiency_score": 70,
        }
        book = {
            "cycles_observed": 1,
            "total_candidate_observations": 1,
            "records": {"fast_flip::Test item": {"repeatability_class": "INCONSISTENT", "observations": 3}},
        }
        real = {"round_trips": {"completed_round_trips": 1}}

        observed = allocation.annotate_repeatability(dict(row), cfg, book, real)

        self.assertFalse(observed["repeatability_allocation_authority"])
        self.assertEqual(observed["expected_profit_at_capacity_gp"], 100_000)
        self.assertEqual(observed["repeatability_adjusted_profit_gp_advisory"], 75_000)

        cfg["phase3"]["repeatability_multiplier"]["rollout_status"] = "ALLOCATION_AUTHORITATIVE"
        authoritative = allocation.annotate_repeatability(dict(row), cfg, book, real)

        self.assertTrue(authoritative["repeatability_allocation_authority"])
        self.assertEqual(authoritative["expected_profit_at_capacity_gp"], 75_000)
        self.assertEqual(authoritative["expected_gp_per_hour"], 37_500)

    def test_repeatability_bonus_requires_profitable_item_round_trips(self):
        cfg = config()
        cfg["phase3"]["repeatability_multiplier"] = {
            "enabled": True,
            "rollout_status": "OBSERVATION_ONLY",
            "minimum_item_round_trips_before_bonus": 3,
            "minimum_item_win_rate_pct_before_bonus": 50,
            "advisory_multiplier_by_class": {"REPEATABLE": 1.1, "UNOBSERVED": 1.0},
        }
        row = {
            "engine": "evergreen", "item_or_strategy": "Test item",
            "expected_profit_at_capacity_gp": 100_000, "expected_gp_per_hour": 10_000,
        }
        book = {"records": {"evergreen::Test item": {"repeatability_class": "REPEATABLE", "observations": 8}}}
        without_realized_sample = allocation.annotate_repeatability(dict(row), cfg, book, {})

        self.assertEqual(without_realized_sample["repeatability_configured_multiplier"], 1.1)
        self.assertEqual(without_realized_sample["repeatability_multiplier_advisory"], 1.0)
        self.assertFalse(without_realized_sample["repeatability_bonus_real_execution_confirmed"])

        real = {"performance_dashboard": {"by_item": {"Test item": {
            "round_trips": 3, "win_rate_pct": 66.67, "realized_net_profit_gp": 50_000,
        }}}}
        with_realized_sample = allocation.annotate_repeatability(dict(row), cfg, book, real)

        self.assertEqual(with_realized_sample["repeatability_multiplier_advisory"], 1.1)
        self.assertTrue(with_realized_sample["repeatability_bonus_real_execution_confirmed"])

    def test_attention_modes_change_advisory_candidate_eligibility(self):
        cfg = config()
        cfg["phase4"] = {"attention_modes": {
            "enabled": True,
            "rollout_status": "ADVISORY",
            "current_mode": "NORMAL",
            "modes": {
                "PASSIVE": {"maximum_player_time_attention": "NEGLIGIBLE", "absolute_profit_hurdle_multiplier": 1.0},
                "ACTIVE": {"maximum_player_time_attention": "HIGH", "absolute_profit_hurdle_multiplier": 0.75},
            },
        }}
        rows = [
            {"engine": "evergreen", "item_or_strategy": "Passive", "slot_bucket": "PARKING", "expected_profit_at_capacity_gp": 300_000, "expected_gp_per_hour": 10_000, "minimum_absolute_profit_hurdle_gp": 250_000, "player_time_hours": 0, "profit_efficiency_score": 50},
            {"engine": "conversion", "item_or_strategy": "Manual", "slot_bucket": "FLEXIBLE", "expected_profit_at_capacity_gp": 60_000, "expected_gp_per_hour": 20_000, "minimum_absolute_profit_hurdle_gp": 75_000, "player_time_attention": "HIGH", "profit_efficiency_score": 60},
        ]

        summary = allocation.build_attention_modes(rows, cfg)

        self.assertEqual(summary["scenarios"]["PASSIVE"]["eligible_candidates"], 1)
        self.assertEqual(summary["scenarios"]["ACTIVE"]["eligible_candidates"], 2)
        self.assertFalse(summary["allocation_authoritative"])

    def test_rotation_exempts_use_gear_and_refuses_to_invent_remaining_upside(self):
        packet = {
            "tax_policy": {"rate": 0.02, "cap_gp_per_item": 5_000_000},
            "portfolio": [
                {"item": "Use gear", "item_id": 1, "quantity": 1, "current": {"low": 1_000_000}, "capital_aging": {"exempt": True}},
                {"item": "Merch", "item_id": 2, "quantity": 10, "current": {"low": 100_000}, "capital_aging": {"tracking_age_hours": 10}},
            ],
        }
        lifecycle = {"positions": {"1": {"hold_for_use": True}, "2": {"hold_for_use": False, "expected_payoff_hours": 100}}}
        cfg = {"phase4": {"remaining_upside_capital_rotation": {"enabled": True, "rollout_status": "ADVISORY"}}}
        alternatives = [{"item_or_strategy": "Alternative", "minimum_absolute_profit_hurdle_pass": True, "repeatability_class": "REPEATABLE", "expected_gp_per_hour": 100_000, "expected_profit_at_capacity_gp": 500_000, "capacity_gp": 1_000_000, "expected_hold_hours": 4}]

        summary = allocation.build_remaining_upside_rotation(packet, alternatives, cfg, lifecycle)

        self.assertEqual(summary["hold_for_use_exempt_items"], ["Use gear"])
        self.assertEqual(summary["data_gap_positions"], 1)
        self.assertEqual(summary["rotation_alerts"], [])
        self.assertFalse(summary["allocation_authoritative"])


if __name__ == "__main__":
    unittest.main()
