import unittest
from datetime import datetime, timezone

import build_desk_lite
import portfolio_exit_engine as exits


NOW = int(datetime(2026, 9, 3, 4, 36, tzinfo=timezone.utc).timestamp())


def config():
    return {
        "portfolio_exit_engine": {
            "enabled": True,
            "rollout_status": "ACTIVE",
            "recommendation_authoritative": True,
            "maximum_actionable_print_age_seconds": 1800,
            "thin_spread_pct": 8,
            "recover_basis": {
                "minimum_patient_after_tax_roi_pct": 80,
                "minimum_immediate_after_tax_roi_pct": 25,
                "minimum_24h_gain_pct": 20,
                "minimum_7d_gain_pct": 50,
                "minimum_high_side_share": 0.45,
                "minimum_one_hour_volume": 20,
                "default_runner_fraction": 0.5,
                "maximum_trim_fraction": 0.75,
                "patient_limit_discount_pct": 2,
                "minimum_patient_window_hours": 4,
            },
            "extreme_profit_lock": {
                "enabled": True,
                "minimum_patient_after_tax_roi_pct": 150,
                "minimum_immediate_after_tax_roi_pct": 50,
            },
            "rule": "test",
        }
    }


def amulet_position():
    return {
        "item": "Amulet of magic",
        "item_id": 1727,
        "quantity": 3000,
        "basis_each": 515,
        "basis_total": 1_545_000,
        "current": {
            "high": 1400,
            "low": 600,
            "highAgeSeconds": 95,
            "lowAgeSeconds": 111,
        },
        "averages": {
            "1h": {
                "avgHighPrice": 1123,
                "avgLowPrice": 870,
                "highPriceVolume": 592,
                "lowPriceVolume": 242,
            }
        },
        "movementPct": {"24h": 56.565, "7d": 120.243},
        "liquidity": "VERY THIN",
        "rating": "HOLD / NO ADD",
        "capital_aging": {"exempt": False},
    }


def lifecycle(hold_for_use=False, with_policy=True):
    row = {"hold_for_use": hold_for_use}
    if with_policy:
        row["exit_policy"] = {
            "mode": "CATALYST_BASIS_RECOVERY",
            "realization_catalyst_ids": ["elemental_amulets_implemented_sep2"],
            "maximum_realization_age_days": 7,
            "supply_elasticity": "HIGH",
            "runner_fraction": 0.5,
            "maximum_trim_fraction": 0.75,
            "minimum_patient_after_tax_roi_pct": 60,
        }
    return {"positions": {"1727": row}}


def packet(include_catalyst=True):
    catalysts = []
    if include_catalyst:
        catalysts.append({
            "id": "elemental_amulets_implemented_sep2",
            "latest_evidence_date": "2026-09-02",
            "status": "NEW",
            "credibility": "CONFIRMED",
        })
    return {
        "quality": {"ready": True},
        "portfolio": [amulet_position()],
        "tax_policy": {"rate": 0.02, "cap_gp_per_item": 5_000_000},
        "catalyst_state": {"records": catalysts},
        "profit_layer": {"ge_slot_optimizer": {"modeled_free_slots_upper_bound": 7}},
    }


class PortfolioExitEngineTests(unittest.TestCase):
    def test_realized_catalyst_spike_overrides_static_hold_and_recovers_basis(self):
        desk = packet()

        summary = exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)

        self.assertTrue(summary["action_required"])
        self.assertTrue(summary["recommendation_authoritative"])
        self.assertEqual(summary["actionable_count"], 1)
        action = summary["priority_actions"][0]
        self.assertEqual(action["item"], "Amulet of magic")
        self.assertEqual(action["action"], "TRIM_RECOVER_BASIS")
        self.assertEqual(action["sell_quantity"], 1500)
        self.assertEqual(action["runner_quantity"], 1500)
        self.assertEqual(action["recommended_limit_price_gp"], 1100)
        self.assertEqual(action["minimum_basis_recovery_price_gp"], 1051)
        self.assertEqual(action["expected_net_proceeds_at_limit_gp"], 1_617_000)
        self.assertEqual(action["expected_locked_profit_at_limit_gp"], 844_500)
        self.assertTrue(action["basis_recovered_if_filled"])
        self.assertEqual(action["execution_style"], "PATIENT_STAGED_LIMIT")
        self.assertTrue(action["market_dump_prohibited"])
        self.assertIn("HIGH_SUPPLY_ELASTICITY", action["reason_codes"])
        self.assertIn("FLASH_LOW_PRINT_DOES_NOT_VETO_PATIENT_EXIT", action["reason_codes"])
        self.assertLess(action["metrics"]["immediate_after_tax_roi_pct"], 25)
        self.assertGreater(action["metrics"]["one_hour_low_after_tax_roi_pct"], 25)

        position = desk["portfolio"][0]
        self.assertEqual(position["static_rating_before_exit_engine"], "HOLD / NO ADD")
        self.assertEqual(position["rating"], "TRIM / RECOVER BASIS")
        self.assertTrue(position["exit_signal"]["status"] == "ACTION_REQUIRED")
        slot = desk["profit_layer"]["ge_slot_optimizer"]
        self.assertTrue(slot["new_buy_orders_are_subordinate_to_exit_actions"])
        self.assertEqual(slot["recommended_exit_slot_priority"][0]["sell_quantity"], 1500)

    def test_thin_tape_changes_execution_instead_of_suppressing_signal(self):
        desk = packet()

        exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)
        action = desk["portfolio_exit_engine"]["priority_actions"][0]

        self.assertGreater(action["metrics"]["current_spread_pct"], 90)
        self.assertEqual(action["execution_style"], "PATIENT_STAGED_LIMIT")
        self.assertGreaterEqual(action["estimated_minimum_fill_hours"], 4)

    def test_weak_buyer_flow_changes_execution_instead_of_suppressing_basis_recovery(self):
        desk = packet()
        position = desk["portfolio"][0]
        position["current"].update({"high": 904, "low": 904})
        position["averages"]["1h"].update({
            "avgHighPrice": 1233,
            "avgLowPrice": 723,
            "highPriceVolume": 390,
            "lowPriceVolume": 705,
        })
        position["movementPct"] = {"24h": 48.519, "7d": 83.146}

        summary = exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)
        action = summary["priority_actions"][0]

        self.assertTrue(summary["action_required"])
        self.assertEqual(action["action"], "TRIM_RECOVER_BASIS")
        self.assertEqual(action["sell_quantity"], 1800)
        self.assertEqual(action["runner_quantity"], 1200)
        self.assertEqual(action["recommended_limit_price_gp"], 885)
        self.assertFalse(action["metrics"]["buyer_flow_supportive"])
        self.assertIn("WEAK_BUYER_FLOW_PATIENT_EXIT", action["reason_codes"])
        self.assertEqual(action["execution_style"], "PATIENT_STAGED_LIMIT")
        self.assertTrue(action["market_dump_prohibited"])

    def test_unrealized_or_missing_configured_catalyst_does_not_trigger_normal_gain(self):
        desk = packet(include_catalyst=False)

        summary = exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)

        self.assertFalse(summary["action_required"])
        self.assertEqual(desk["portfolio"][0]["rating"], "HOLD / NO ADD")
        self.assertNotIn("exit_signal", desk["portfolio"][0])

    def test_extreme_profit_can_trigger_without_item_specific_catalyst_policy(self):
        desk = packet(include_catalyst=False)
        position = desk["portfolio"][0]
        position["current"].update({"high": 2200, "low": 1100})
        position["averages"]["1h"].update({"avgHighPrice": 2000, "avgLowPrice": 1300})

        summary = exits.build_exit_engine(desk, config(), lifecycle(with_policy=False), now=NOW)

        self.assertTrue(summary["action_required"])
        self.assertIn("EXTREME_AFTER_TAX_GAIN", summary["priority_actions"][0]["reason_codes"])

    def test_single_unit_extreme_gain_becomes_exit_instead_of_claiming_a_runner(self):
        desk = packet(include_catalyst=False)
        position = desk["portfolio"][0]
        position.update({"quantity": 1, "basis_total": 515})
        position["current"].update({"high": 2200, "low": 1100})
        position["averages"]["1h"].update({"avgHighPrice": 2000, "avgLowPrice": 1300})

        summary = exits.build_exit_engine(desk, config(), lifecycle(with_policy=False), now=NOW)
        action = summary["priority_actions"][0]

        self.assertEqual(action["action"], "EXIT_LOCK_PROFIT")
        self.assertEqual(action["runner_quantity"], 0)
        self.assertEqual(action["recommended_rating"], "EXIT / LOCK PROFIT")

    def test_hold_for_use_is_always_exempt(self):
        desk = packet()

        summary = exits.build_exit_engine(desk, config(), lifecycle(hold_for_use=True), now=NOW)

        self.assertFalse(summary["action_required"])
        self.assertEqual(summary["hold_for_use_exempt_items"], ["Amulet of magic"])

    def test_unready_packet_never_emits_an_exit_from_stale_tape(self):
        desk = packet()
        desk["quality"]["ready"] = False

        summary = exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)

        self.assertFalse(summary["action_required"])
        self.assertFalse(summary["market_data_ready"])
        self.assertEqual(summary["data_status"], "LIVE RUNELITE DATA UNAVAILABLE")

    def test_confirmed_basis_recovery_does_not_retrim_runner(self):
        desk = packet()
        state = lifecycle()
        state["positions"]["1727"]["exit_policy"]["basis_recovery_completed"] = True

        summary = exits.build_exit_engine(desk, config(), state, now=NOW)

        self.assertFalse(summary["action_required"])
        self.assertEqual(desk["portfolio"][0]["rating"], "HOLD / NO ADD")

    def test_crossed_prints_force_patient_reference_without_suppressing_action(self):
        desk = packet()
        desk["portfolio"][0]["current"].update({"high": 1100, "low": 1101})

        summary = exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)

        self.assertTrue(summary["action_required"])
        action = summary["priority_actions"][0]
        self.assertEqual(action["data_gate"], "ASYNC_CROSSED_PATIENT_ONLY")
        self.assertEqual(action["metrics"]["patient_reference_gp"], 1100)
        self.assertTrue(action["market_dump_prohibited"])
        self.assertIn("ASYNC_PRINTS_USE_CONSERVATIVE_PATIENT_REFERENCE", action["reason_codes"])

    def test_stale_crossed_prints_are_still_rejected(self):
        desk = packet()
        desk["portfolio"][0]["current"].update({
            "high": 1100,
            "low": 1101,
            "highAgeSeconds": 4000,
            "lowAgeSeconds": 4000,
        })

        summary = exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)

        self.assertFalse(summary["action_required"])

    def test_post_spike_pullback_adapts_quantity_to_recover_basis(self):
        desk = packet()
        desk["portfolio"][0]["current"].update({"high": 904, "low": 905})

        summary = exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)
        action = summary["priority_actions"][0]

        self.assertEqual(action["metrics"]["patient_reference_gp"], 904)
        self.assertEqual(action["recommended_limit_price_gp"], 885)
        self.assertEqual(action["sell_quantity"], 1800)
        self.assertEqual(action["runner_quantity"], 1200)
        self.assertEqual(action["minimum_basis_recovery_price_gp"], 876)
        self.assertTrue(action["basis_recovered_if_filled"])

    def test_minimum_recovery_price_accounts_for_ge_tax_rounding(self):
        price = exits.minimum_price_for_net_proceeds(
            "Amulet of magic",
            quantity=1500,
            target_net_gp=1_545_000,
            tax_policy={"rate": 0.02, "cap_gp_per_item": 5_000_000},
        )

        self.assertEqual(price, 1051)
        self.assertEqual(exits.net_unit_value("Amulet of magic", price, {"rate": 0.02}), 1030)

    def test_lite_packet_keeps_exit_precedence_and_consistent_current_volume(self):
        desk = packet()
        summary = exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)

        compact_summary = build_desk_lite.compact_exit_engine(summary)
        compact_position = build_desk_lite.compact_portfolio(desk["portfolio"][0])

        self.assertTrue(compact_summary["action_required"])
        self.assertEqual(compact_summary["priority_actions"][0]["sell_quantity"], 1500)
        self.assertTrue(compact_position["exit_action_required"])
        self.assertEqual(compact_position["oneHourVolume"], 834)

    def test_rerun_clears_old_dynamic_signal_when_current_gate_no_longer_passes(self):
        desk = packet()
        exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)
        self.assertIn("exit_signal", desk["portfolio"][0])

        desk["catalyst_state"]["records"] = []
        summary = exits.build_exit_engine(desk, config(), lifecycle(), now=NOW)

        self.assertFalse(summary["action_required"])
        self.assertEqual(desk["portfolio"][0]["rating"], "HOLD / NO ADD")
        self.assertNotIn("exit_signal", desk["portfolio"][0])
        self.assertNotIn("static_rating_before_exit_engine", desk["portfolio"][0])


if __name__ == "__main__":
    unittest.main()
