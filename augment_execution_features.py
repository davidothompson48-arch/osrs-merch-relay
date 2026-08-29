#!/usr/bin/env python3
import json
import math
from datetime import datetime, timezone

PACKET = "desk_packet.json"
CFG = "project/profit_engine.json"
REAL = "real_execution_summary.json"
PERSISTENCE = "spread_persistence.json"


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def curve_probability(anchor_probability, horizon_minutes, anchor_hours):
    p = clamp(float(anchor_probability or 0), 0.0001, 0.999)
    anchor_minutes = max(float(anchor_hours) * 60.0, 1.0)
    exponent = max(float(horizon_minutes), 0.0) / anchor_minutes
    return clamp(1.0 - ((1.0 - p) ** exponent), 0.0, 0.999)


def expected_wait_hours(anchor_probability, anchor_hours, maximum_hours):
    p = clamp(float(anchor_probability or 0), 0.0001, 0.999)
    rate = -math.log(1.0 - p) / max(float(anchor_hours), 0.01)
    if rate <= 0:
        return float(maximum_hours)
    return min(float(maximum_hours), 1.0 / rate)


def empirical_source(real, item, side, horizon_key, cfg):
    item_min = int(cfg.get("item_min_samples_before_blend") or 8)
    engine_min = int(cfg.get("engine_min_samples_before_blend") or 20)
    item_row = ((real.get("by_item") or {}).get(item) or {}).get(side) or {}
    n = int((item_row.get("sample_n_by_horizon") or {}).get(horizon_key) or 0)
    p = (item_row.get("fill_probability_by_horizon") or {}).get(horizon_key)
    if n >= item_min and isinstance(p, (int, float)):
        return float(p), n, "ITEM"
    engine_row = ((real.get("by_engine") or {}).get("fast_flip") or {}).get(side) or {}
    n = int((engine_row.get("sample_n_by_horizon") or {}).get(horizon_key) or 0)
    p = (engine_row.get("fill_probability_by_horizon") or {}).get(horizon_key)
    if n >= engine_min and isinstance(p, (int, float)):
        return float(p), n, "ENGINE"
    return None, 0, None


def blend_probability(model_p, empirical_p, sample_n, cfg):
    if empirical_p is None or sample_n <= 0:
        return model_p, 0.0
    prior_strength = float(cfg.get("prior_strength_samples") or 12)
    max_weight = float(cfg.get("maximum_empirical_weight") or 0.75)
    weight = min(max_weight, sample_n / max(sample_n + prior_strength, 1.0))
    blended = (1.0 - weight) * model_p + weight * empirical_p
    return clamp(blended, 0.001, 0.999), weight


def profit_score(gph, roi, capacity_gp, exec_prob, passive_factor, learn_adj=0):
    gph = max(0.0, float(gph or 0))
    roi = max(0.0, float(roi or 0))
    capacity_gp = max(0.0, float(capacity_gp or 0))
    exec_prob = clamp(float(exec_prob or 0), 0, 1)
    passive_factor = clamp(float(passive_factor or 0), 0, 1)
    gph_pts = 35 * (1 - math.exp(-gph / 1_000_000))
    roi_pts = min(20, roi * 4)
    cap_pts = 15 * (1 - math.exp(-capacity_gp / 20_000_000))
    exec_pts = 20 * exec_prob
    time_pts = 10 * passive_factor
    return round(clamp(gph_pts + roi_pts + cap_pts + exec_pts + time_pts + learn_adj, 0, 100), 1)


def persistence_row(state, row):
    items = state.get("items") or {}
    item_id = row.get("id")
    record = items.get(str(item_id)) if item_id is not None else None
    if not record:
        return {
            "classification": "UNKNOWN",
            "auto_allocation_eligible": False,
            "consecutive_snapshots": 0,
            "duration_minutes": 0,
            "qualified_ratio": None,
        }
    return record


def augment_fast_row(row, cfg, real, persistence):
    exec_cfg = cfg.get("execution_model") or {}
    real_cfg = cfg.get("real_execution_learning") or {}
    persist_cfg = cfg.get("spread_persistence") or {}
    horizons = exec_cfg.get("fast_flip_horizons_minutes") or real_cfg.get("horizons_minutes") or [5, 15, 60, 120, 240]
    horizons = sorted({int(x) for x in horizons if isinstance(x, (int, float)) and x > 0})
    anchor_hours = float(exec_cfg.get("fast_flip_curve_anchor_hours") or 2.0)
    max_cycle = float(exec_cfg.get("fast_flip_max_modeled_cycle_hours") or 24.0)
    freshness_map = exec_cfg.get("freshness_factor") or {}

    entry_factor = float(row.get("modeled_entry_fill_factor") or 0.5)
    exit_factor = float(row.get("modeled_exit_factor") or 0.5)
    fresh_factor = float(freshness_map.get(row.get("freshness"), 0.45))
    instability = float(row.get("tape_instability_factor") or 1.0)
    shared = math.sqrt(max(0.01, fresh_factor * instability))
    entry_anchor = clamp(entry_factor * shared, 0.02, 0.97)
    exit_anchor = clamp(exit_factor * shared, 0.02, 0.97)

    item = row.get("name")
    entry_curve = {}
    exit_curve = {}
    learning_sources = set()
    empirical_weights = []
    for horizon in horizons:
        key = str(horizon)
        model_entry = curve_probability(entry_anchor, horizon, anchor_hours)
        model_exit = curve_probability(exit_anchor, horizon, anchor_hours)
        emp_entry, n_entry, src_entry = empirical_source(real, item, "entry", key, real_cfg)
        emp_exit, n_exit, src_exit = empirical_source(real, item, "exit", key, real_cfg)
        blended_entry, w_entry = blend_probability(model_entry, emp_entry, n_entry, real_cfg)
        blended_exit, w_exit = blend_probability(model_exit, emp_exit, n_exit, real_cfg)
        entry_curve[key] = round(blended_entry, 4)
        exit_curve[key] = round(blended_exit, 4)
        if src_entry:
            learning_sources.add(f"ENTRY_{src_entry}")
        if src_exit:
            learning_sources.add(f"EXIT_{src_exit}")
        empirical_weights.extend([w_entry, w_exit])

    anchor_key = str(int(round(anchor_hours * 60)))
    if anchor_key in entry_curve:
        entry_anchor_blended = entry_curve[anchor_key]
        exit_anchor_blended = exit_curve[anchor_key]
    else:
        emp_entry, n_entry, src_entry = empirical_source(real, item, "entry", anchor_key, real_cfg)
        emp_exit, n_exit, src_exit = empirical_source(real, item, "exit", anchor_key, real_cfg)
        entry_anchor_blended, w_entry = blend_probability(entry_anchor, emp_entry, n_entry, real_cfg)
        exit_anchor_blended, w_exit = blend_probability(exit_anchor, emp_exit, n_exit, real_cfg)
        empirical_weights.extend([w_entry, w_exit])
        if src_entry:
            learning_sources.add(f"ENTRY_{src_entry}")
        if src_exit:
            learning_sources.add(f"EXIT_{src_exit}")

    persist = persistence_row(persistence, row)
    persist_class = persist.get("classification") or "UNKNOWN"
    multipliers = persist_cfg.get("execution_multiplier") or {}
    persistence_multiplier = float(multipliers.get(persist_class, multipliers.get("UNKNOWN", 0.5)))
    eligible_classes = set(persist_cfg.get("auto_allocation_eligible_classes") or ["PERSISTENT_SPREAD", "REPEATABLE_MARKET"])
    auto_eligible = bool(persist.get("auto_allocation_eligible")) and persist_class in eligible_classes

    round_trip_anchor = clamp(entry_anchor_blended * exit_anchor_blended * persistence_multiplier, 0.0, 0.95)
    entry_wait = expected_wait_hours(entry_anchor_blended, anchor_hours, max_cycle)
    exit_wait = expected_wait_hours(exit_anchor_blended, anchor_hours, max_cycle)
    cycle_hours = min(max_cycle, max(0.25, entry_wait + exit_wait))

    theoretical_profit = row.get("theoretical_profit_at_capacity_gp")
    if not isinstance(theoretical_profit, (int, float)):
        theoretical_profit = 0
    expected_profit = theoretical_profit * round_trip_anchor
    capacity = float(row.get("capacity_gp") or 0)
    expected_roi = expected_profit / capacity * 100 if capacity > 0 else None
    expected_gph = expected_profit / cycle_hours if cycle_hours > 0 else 0
    raw_roi = row.get("raw_after_tax_roi_pct")
    learn = int(row.get("learning_adjustment_points") or 0)

    validation_flag = row.get("validation_flag")
    if not auto_eligible:
        if persist_class == "FLASH_SPREAD":
            validation_flag = "SPREAD_NOT_PERSISTENT"
        elif persist_class == "UNSTABLE_SPREAD":
            validation_flag = "SPREAD_UNSTABLE"
        elif persist_class == "INVALID_SPREAD":
            validation_flag = "SPREAD_INVALID"
        else:
            validation_flag = "SPREAD_PERSISTENCE_UNKNOWN"

    row.update({
        "execution_model_version": 2,
        "execution_curve_anchor_hours": anchor_hours,
        "entry_fill_probability_by_horizon": entry_curve,
        "exit_fill_probability_by_horizon": exit_curve,
        "entry_fill_probability_at_anchor": round(entry_anchor_blended, 4),
        "exit_fill_probability_at_anchor": round(exit_anchor_blended, 4),
        "execution_probability_heuristic": round(round_trip_anchor, 4),
        "expected_cycle_hours": round(cycle_hours, 3),
        "expected_hold_hours": round(cycle_hours, 3),
        "expected_profit_at_capacity_gp": int(expected_profit),
        "expected_after_tax_roi_pct": round(expected_roi, 3) if expected_roi is not None else None,
        "expected_gp_per_hour": int(expected_gph),
        "slot_efficiency_gp_per_hour": int(expected_gph),
        "player_time_adjusted_profit_gp": int(expected_profit),
        "spread_persistence_class": persist_class,
        "spread_persistence_snapshots": persist.get("consecutive_snapshots"),
        "spread_persistence_minutes": persist.get("duration_minutes"),
        "spread_qualified_ratio": persist.get("qualified_ratio"),
        "spread_persistence_multiplier": persistence_multiplier,
        "auto_allocation_eligible": auto_eligible,
        "validation_flag": validation_flag,
        "real_execution_learning_applied": bool(learning_sources),
        "real_execution_learning_sources": sorted(learning_sources),
        "real_execution_empirical_weight_max": round(max(empirical_weights), 3) if empirical_weights else 0.0,
    })
    row["profit_efficiency_score"] = profit_score(expected_gph, raw_roi, capacity, round_trip_anchor, 1.0, learn)
    return row


def main():
    packet = load_json(PACKET)
    if not packet:
        raise RuntimeError("desk_packet.json missing")
    cfg = load_json(CFG)
    real = load_json(REAL)
    persistence = load_json(PERSISTENCE)
    profit = packet.get("profit_layer") or {}
    fast = profit.get("fast_flip_capacity_velocity") or []
    fast = [augment_fast_row(dict(x), cfg, real, persistence) for x in fast]
    fast.sort(key=lambda x: (x.get("profit_efficiency_score") or 0, x.get("expected_gp_per_hour") or 0), reverse=True)
    profit["fast_flip_capacity_velocity"] = fast
    profit["real_execution_learning"] = {
        "generated_at": real.get("generated_at"),
        "orders_total": real.get("orders_total"),
        "timed_orders_total": real.get("timed_orders_total"),
        "user_confirmed_orders_total": real.get("user_confirmed_orders_total"),
        "round_trips": real.get("round_trips"),
        "minimum_samples_before_item_blend": real.get("minimum_samples_before_item_blend"),
        "minimum_samples_before_engine_blend": real.get("minimum_samples_before_engine_blend"),
        "rule": real.get("rule"),
    }
    profit["spread_persistence"] = {
        "updated_at": persistence.get("updated_at"),
        "class_counts": persistence.get("class_counts") or {},
        "rule": persistence.get("rule"),
    }
    profit["execution_upgrade_state"] = {
        "real_execution_learning": "ACTIVE",
        "multi_horizon_fill_curves": "ACTIVE",
        "spread_persistence_validation": "ACTIVE",
        "future_phases": "project/profit_engine_roadmap.json",
    }
    profit["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    packet["profit_layer"] = profit
    save_json(PACKET, packet)
    print(f"Execution features augmented: fast={len(fast)} persistence={profit['spread_persistence']['class_counts']} real_orders={real.get('orders_total', 0)}")


if __name__ == "__main__":
    main()
