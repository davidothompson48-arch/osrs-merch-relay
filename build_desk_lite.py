#!/usr/bin/env python3
import json

SRC = "desk_packet.json"
OUT = "desk_packet_lite.json"


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compact_avg(row):
    if not isinstance(row, dict):
        return {}
    return {k: row.get(k) for k in ("avgHighPrice", "avgLowPrice", "highPriceVolume", "lowPriceVolume")}


def compact_portfolio(row):
    vol = row.get("volume") or {}; one = vol.get("1h") or {}
    return {"item":row.get("item"),"item_id":row.get("item_id"),"quantity":row.get("quantity"),"basis_each":row.get("basis_each"),"basis_total":row.get("basis_total"),"current":row.get("current"),"freshness":row.get("freshness"),"1h":compact_avg((row.get("averages") or {}).get("1h")),"24h":compact_avg((row.get("averages") or {}).get("24h")),"movementPct":row.get("movementPct") or {},"highSideShare1h":vol.get("highSideShare1h") if "highSideShare1h" in vol else (one.get("high")/one.get("total") if one.get("total") else None),"oneHourVolume":one.get("total"),"liquidity":row.get("liquidity"),"buy_limit":row.get("buy_limit"),"gross_pnl_high":row.get("gross_pnl_high"),"modeled_after_tax_pnl_high":row.get("modeled_after_tax_pnl_high"),"rating":row.get("rating"),"history_complete":row.get("history_complete"),"capital_aging":row.get("capital_aging")}


def compact_sector(rows):
    out=[]
    for x in rows:
        one=x.get("oneHour") or {}; cur=x.get("current") or {}
        out.append({"id":x.get("id"),"name":x.get("name"),"high":cur.get("high"),"low":cur.get("low"),"highAgeSeconds":cur.get("highAgeSeconds"),"lowAgeSeconds":cur.get("lowAgeSeconds"),"1hHigh":one.get("avgHighPrice"),"1hLow":one.get("avgLowPrice"),"1hHighVol":one.get("highPriceVolume"),"1hLowVol":one.get("lowPriceVolume")})
    return out


def compact_profit_row(x):
    return {
        "engine":x.get("engine"),"id":x.get("id"),"name":x.get("name"),"strategy":x.get("strategy"),
        "profit_efficiency_score":x.get("profit_efficiency_score"),"expected_gp_per_hour":x.get("expected_gp_per_hour"),
        "slot_efficiency_gp_per_hour":x.get("slot_efficiency_gp_per_hour"),
        "expected_profit_at_capacity_gp":x.get("expected_profit_at_capacity_gp") if x.get("expected_profit_at_capacity_gp") is not None else x.get("player_time_adjusted_profit_gp"),
        "capacity_gp":x.get("capacity_gp"),"expected_after_tax_roi_pct":x.get("expected_after_tax_roi_pct"),"raw_after_tax_roi_pct":x.get("raw_after_tax_roi_pct"),
        "patient_roi_pct":x.get("patient_roi_pct"),"immediate_roi_pct":x.get("immediate_roi_pct"),"modeled_capacity_units":x.get("modeled_capacity_units"),
        "modeled_capacity_conversion_units":x.get("modeled_capacity_conversion_units"),"execution_probability_heuristic":x.get("execution_probability_heuristic"),
        "slippage_risk":x.get("slippage_risk"),"player_time_hours":x.get("player_time_hours"),"player_time_attention":x.get("player_time_attention"),
        "player_time_shadow_cost_gp":x.get("player_time_shadow_cost_gp"),"current_high":x.get("current_high"),"current_low":x.get("current_low"),
        "current_entry_reference":x.get("current_entry_reference"),"target_30d_or_7d_median":x.get("target_30d_or_7d_median"),
        "discount_to_30d_median_pct":x.get("discount_to_30d_median_pct"),"thirty_day_percentile":x.get("thirty_day_percentile"),"status":x.get("status"),
        "expected_hold_hours":x.get("expected_hold_hours"),"expected_cycle_hours":x.get("expected_cycle_hours"),"learning_adjustment_points":x.get("learning_adjustment_points"),
        "validation_flag":x.get("validation_flag"),"auto_allocation_eligible":x.get("auto_allocation_eligible"),"execution_model_version":x.get("execution_model_version"),
        "entry_fill_probability_by_horizon":x.get("entry_fill_probability_by_horizon"),"exit_fill_probability_by_horizon":x.get("exit_fill_probability_by_horizon"),
        "entry_fill_probability_at_anchor":x.get("entry_fill_probability_at_anchor"),"exit_fill_probability_at_anchor":x.get("exit_fill_probability_at_anchor"),
        "spread_persistence_class":x.get("spread_persistence_class"),"spread_persistence_snapshots":x.get("spread_persistence_snapshots"),
        "spread_persistence_minutes":x.get("spread_persistence_minutes"),"spread_qualified_ratio":x.get("spread_qualified_ratio"),
        "real_execution_learning_applied":x.get("real_execution_learning_applied"),"real_execution_learning_sources":x.get("real_execution_learning_sources"),
        "real_execution_empirical_weight_max":x.get("real_execution_empirical_weight_max"),
        "optimal_execution":x.get("optimal_execution"),"optimal_entry_price_gp":x.get("optimal_entry_price_gp"),
        "optimal_exit_price_gp":x.get("optimal_exit_price_gp"),"do_not_chase_price_gp":x.get("do_not_chase_price_gp"),
        "price_optimizer_validation":x.get("price_optimizer_validation"),"price_optimizer_version":x.get("price_optimizer_version"),
        "price_optimizer_learning_basis":x.get("price_optimizer_learning_basis"),"price_optimizer_allocation_authority":x.get("price_optimizer_allocation_authority")
    }


def compact_frontier_row(row):
    if not isinstance(row, dict):
        return {}
    return {
        k: v for k, v in row.items()
        if not k.startswith("minimum_absolute_profit_")
        and not k.startswith("repeatability_")
        and k != "pre_repeatability_adjustment"
    }


def compact_hurdle_summary(row):
    if not isinstance(row, dict):
        return {}
    return {k: row.get(k) for k in (
        "enabled", "rollout_status", "allocation_authoritative", "evaluation_basis",
        "thresholds_gp_by_slot_bucket", "evaluated_candidates", "passed_candidates",
        "failed_candidates", "would_change_current_frontiers", "by_slot_bucket",
        "advisory_failures", "promotion_rule", "cumulative_observation_cycles",
        "cumulative_candidate_observations", "promotion_data_sufficient"
    )}


def compact_repeatability_summary(row):
    if not isinstance(row, dict):
        return {}
    out = {k: row.get(k) for k in (
        "enabled", "rollout_status", "allocation_authoritative", "authority_data_sufficient",
        "class_counts", "book_cycles_observed", "book_candidate_observations",
        "real_completed_round_trips", "rule"
    )}
    out["candidates"] = (row.get("candidates") or [])[:5]
    return out


def compact_opportunity_book(row):
    if not isinstance(row, dict):
        return {}
    out = {k: row.get(k) for k in (
        "status", "state_updated_this_run", "cycles_observed", "total_candidate_observations",
        "active_records", "class_counts", "review_data_sufficient",
        "minimum_cycles_before_review", "minimum_candidate_observations_before_review", "rule"
    )}
    out["top_repeatability_records"] = (row.get("top_repeatability_records") or [])[:5]
    return out


def compact_attention_modes(row):
    if not isinstance(row, dict):
        return {}
    scenarios = {}
    for mode, details in (row.get("scenarios") or {}).items():
        scenarios[mode] = {
            "eligible_candidates": details.get("eligible_candidates"),
            "maximum_player_time_attention": details.get("maximum_player_time_attention"),
            "absolute_profit_hurdle_multiplier": details.get("absolute_profit_hurdle_multiplier"),
            "top_candidates": (details.get("top_candidates") or [])[:3],
        }
    return {
        "enabled": row.get("enabled"),
        "rollout_status": row.get("rollout_status"),
        "allocation_authoritative": row.get("allocation_authoritative"),
        "current_mode": row.get("current_mode"),
        "scenarios": scenarios,
        "rule": row.get("rule"),
    }


def compact_rotation(row):
    if not isinstance(row, dict):
        return {}
    return {k: row.get(k) for k in (
        "enabled", "rollout_status", "allocation_authoritative", "evaluated_positions",
        "data_gap_positions", "hold_for_use_exempt_positions", "hold_for_use_exempt_items",
        "rotation_alerts", "minimum_velocity_advantage_multiple",
        "minimum_expected_profit_advantage_gp", "rule"
    )}


def compact_performance_dashboard(row):
    if not isinstance(row, dict):
        return {}
    return {k: row.get(k) for k in (
        "status", "strategy_ranking_authoritative", "completed_round_trips", "wins", "losses",
        "breakeven", "win_rate_pct", "realized_net_profit_gp", "capital_deployed_gp",
        "realized_roi_pct", "timed_round_trips", "timed_realized_net_profit_gp",
        "aggregate_realized_gp_per_slot_hour",
        "median_cycle_hours", "average_profit_per_round_trip_gp", "best_trade", "worst_trade",
        "by_engine", "data_gaps", "rule"
    )}


def main():
    p=load(SRC); tax=p.get("tax_policy") or {}; engines=p.get("engines") or {}; catalyst=p.get("catalyst_state") or {}; sectors=p.get("sectors") or {}; profit=p.get("profit_layer") or {}
    lite={
        "schema_version":7,"generated_at":p.get("generated_at"),"generated_unix":p.get("generated_unix"),"source":p.get("source"),"quality":p.get("quality"),
        "tax_policy":{"verified_at_utc":tax.get("verified_at_utc"),"rate":tax.get("rate"),"cap_gp_per_item":tax.get("cap_gp_per_item"),"rounding":tax.get("rounding"),"source":tax.get("source")},
        "portfolio":[compact_portfolio(x) for x in p.get("portfolio",[])],"portfolio_summary":p.get("portfolio_summary"),"open_offers_unconfirmed":p.get("open_offers_unconfirmed"),
        "engines":{"fast_flip_screen":(engines.get("fast_flip_screen") or [])[:8],"short_term_momentum":(engines.get("short_term_momentum") or [])[:5],"broad_oversold_screen":(engines.get("broad_oversold_screen") or [])[:5],"extreme_flow_screen":(engines.get("extreme_flow_screen") or [])[:5],"evergreen_staples":{"generated_at":(engines.get("evergreen_staples") or {}).get("generated_at"),"candidate_count":(engines.get("evergreen_staples") or {}).get("candidate_count"),"top_candidates":((engines.get("evergreen_staples") or {}).get("top_candidates") or [])[:8]},"conversions":(engines.get("conversions") or [])[:6]},
        "profit_layer":{"objective":profit.get("objective"),"market_regime":profit.get("market_regime"),"capital_frontier":[compact_frontier_row(x) for x in (profit.get("capital_frontier") or [])[:10]],"absolute_velocity_frontier":[compact_frontier_row(x) for x in (profit.get("absolute_velocity_frontier") or [])[:10]],"marginal_capital_frontier":[compact_frontier_row(x) for x in (profit.get("marginal_capital_frontier") or [])[:10]],"ge_slot_hour_frontier":[compact_frontier_row(x) for x in (profit.get("ge_slot_hour_frontier") or [])[:10]],"capital_allocation_ladder":[compact_frontier_row(x) for x in (profit.get("capital_allocation_ladder") or [])[:10]],"allocation_rule":profit.get("allocation_rule"),"fast_flip_capacity_velocity":[compact_profit_row(x) for x in (profit.get("fast_flip_capacity_velocity") or [])[:6]],"evergreen_capacity_velocity":[compact_profit_row(x) for x in (profit.get("evergreen_capacity_velocity") or [])[:6]],"conversion_capacity_velocity":[compact_profit_row(x) for x in (profit.get("conversion_capacity_velocity") or [])[:6]],"hard_value_set_edges":(profit.get("hard_value_set_edges") or [])[:6],"ge_slot_optimizer":profit.get("ge_slot_optimizer"),"minimum_absolute_profit_hurdles":compact_hurdle_summary(profit.get("minimum_absolute_profit_hurdles")),"repeatability_multiplier":compact_repeatability_summary(profit.get("repeatability_multiplier")),"persistent_opportunity_book":compact_opportunity_book(profit.get("persistent_opportunity_book")),"attention_modes":compact_attention_modes(profit.get("attention_modes")),"remaining_upside_capital_rotation":compact_rotation(profit.get("remaining_upside_capital_rotation")),"realized_performance_dashboard":compact_performance_dashboard(profit.get("realized_performance_dashboard")),"shadow_learning":{"signals_total":(profit.get("shadow_learning") or {}).get("signals_total"),"graded_observations":(profit.get("shadow_learning") or {}).get("graded_observations"),"score_adjustments":(profit.get("shadow_learning") or {}).get("score_adjustments")},"real_execution_learning":profit.get("real_execution_learning"),"spread_persistence":profit.get("spread_persistence"),"execution_upgrade_state":profit.get("execution_upgrade_state"),"phase2_generated_at":profit.get("phase2_generated_at"),"player_time_shadow_value_gp_per_hour":profit.get("player_time_shadow_value_gp_per_hour"),"allocation_note":profit.get("allocation_note")},
        "sectors":{key:compact_sector(sectors.get(key) or []) for key in ("breaker_competing_runes","fractured_archive_ranged","prayer","cox_rewards","crush_inquisitor","elemental_magic") if sectors.get(key)},
        "previous_runtime":p.get("previous_runtime"),
        "catalyst_state":{"watch_last_checked_utc":catalyst.get("watch_last_checked_utc"),"watch_last_material_change_utc":catalyst.get("watch_last_material_change_utc"),"watch_status":catalyst.get("watch_status"),"database_updated_at_utc":catalyst.get("database_updated_at_utc"),"records":catalyst.get("records") or [],"probability_models":catalyst.get("probability_models") or []},
        "deep_packet":"desk_packet.json","rule":"Routine desk runs should use this lite packet only. Use the marginal-capital ladder for incremental GP, the absolute-velocity frontier for total GP/hour, the GE-slot-hour frontier for scarce slot allocation, and the balanced frontier for final risk-adjusted ranking. Fast flips require spread persistence before allocation. Profit hurdles, repeatability, attention modes and capital rotation remain staged unless their allocation_authoritative field is true. Fetch the deep packet solely for missing fields or a user-requested deep dive."
    }
    with open(OUT,"w",encoding="utf-8") as f:
        json.dump(lite,f,separators=(",",":")); f.write("\n")
    print(f"Wrote {OUT}; portfolio={len(lite['portfolio'])}; fast={len(lite['engines']['fast_flip_screen'])}; frontier={len(lite['profit_layer']['capital_frontier'])}")


if __name__=="__main__":
    main()
