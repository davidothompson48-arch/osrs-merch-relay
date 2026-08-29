#!/usr/bin/env python3
import json
import math
from datetime import datetime, timezone

PACKET = "desk_packet.json"
CFG = "project/profit_engine.json"


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


def expected_wait_hours(anchor_probability, anchor_hours, maximum_hours):
    p = clamp(float(anchor_probability or 0), 0.0001, 0.999)
    rate = -math.log(1.0 - p) / max(float(anchor_hours), 0.01)
    if rate <= 0:
        return float(maximum_hours)
    return min(float(maximum_hours), 1.0 / rate)


def boost_probability(base_probability, aggressiveness_fraction, odds_multiplier_at_full):
    p = clamp(float(base_probability or 0), 0.001, 0.999)
    frac = clamp(float(aggressiveness_fraction or 0), 0.0, 1.0)
    odds = p / max(1.0 - p, 1e-9)
    boosted_odds = odds * (float(odds_multiplier_at_full) ** frac)
    return clamp(boosted_odds / (1.0 + boosted_odds), 0.001, 0.999)


def ge_tax_per_item(price, tax_policy):
    price = max(0, int(price))
    rate = float(tax_policy.get("rate") or 0.0)
    cap = int(tax_policy.get("cap_gp_per_item") or 0)
    tax = math.floor(price * rate)
    if cap > 0:
        tax = min(tax, cap)
    return max(0, tax)


def score(gph, roi, capacity_gp, exec_prob, learn_adj=0):
    gph = max(0.0, float(gph or 0))
    roi = max(0.0, float(roi or 0))
    capacity_gp = max(0.0, float(capacity_gp or 0))
    exec_prob = clamp(float(exec_prob or 0), 0, 1)
    gph_pts = 35 * (1 - math.exp(-gph / 1_000_000))
    roi_pts = min(20, roi * 4)
    cap_pts = 15 * (1 - math.exp(-capacity_gp / 20_000_000))
    exec_pts = 20 * exec_prob
    time_pts = 10
    return round(clamp(gph_pts + roi_pts + cap_pts + exec_pts + time_pts + int(learn_adj or 0), 0, 100), 1)


def candidate_prices(low, high, entry_fracs, exit_fracs):
    spread = high - low
    entries = sorted({int(round(low + spread * float(f))) for f in entry_fracs})
    exits = sorted({int(round(high - spread * float(f))) for f in exit_fracs}, reverse=True)
    return entries, exits


def optimize_fast_row(row, cfg, tax_policy):
    price_cfg = ((cfg.get("phase2") or {}).get("order_price_optimizer") or {})
    if not price_cfg.get("enabled", True):
        return row

    low = row.get("current_low")
    high = row.get("current_high")
    units = row.get("modeled_capacity_units")
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)) or high <= low:
        row["price_optimizer_validation"] = "NO_POSITIVE_CURRENT_SPREAD"
        return row
    if not isinstance(units, (int, float)) or units <= 0:
        row["price_optimizer_validation"] = "NO_MODELED_CAPACITY_UNITS"
        return row

    low = int(low)
    high = int(high)
    units = int(units)
    spread = high - low
    base_entry_p = float(row.get("entry_fill_probability_at_anchor") or 0.0)
    base_exit_p = float(row.get("exit_fill_probability_at_anchor") or 0.0)
    if base_entry_p <= 0 or base_exit_p <= 0:
        row["price_optimizer_validation"] = "MISSING_ENTRY_EXIT_PROBABILITIES"
        return row

    entry_fracs = price_cfg.get("entry_aggression_fractions") or [0.0, 0.15, 0.30, 0.50]
    exit_fracs = price_cfg.get("exit_concession_fractions") or [0.0, 0.15, 0.30, 0.50]
    odds_mult = float(price_cfg.get("odds_multiplier_at_full_spread") or 3.0)
    anchor_hours = float(row.get("execution_curve_anchor_hours") or ((cfg.get("execution_model") or {}).get("fast_flip_curve_anchor_hours") or 2.0))
    max_cycle = float((cfg.get("execution_model") or {}).get("fast_flip_max_modeled_cycle_hours") or 24.0)
    persistence_multiplier = float(row.get("spread_persistence_multiplier") or 1.0)
    slip_mults = price_cfg.get("slippage_objective_multiplier") or {"LOW": 1.0, "MEDIUM": 0.9, "HIGH": 0.75}
    slippage_multiplier = float(slip_mults.get(row.get("slippage_risk"), slip_mults.get("UNKNOWN", 0.9)))
    min_net_per_unit = int(price_cfg.get("minimum_net_profit_per_unit_gp") or 1)

    entries, exits = candidate_prices(low, high, entry_fracs, exit_fracs)
    best = None
    for entry in entries:
        entry_frac = (entry - low) / spread if spread else 0.0
        entry_p = boost_probability(base_entry_p, entry_frac, odds_mult)
        entry_wait = expected_wait_hours(entry_p, anchor_hours, max_cycle)
        for exit_price in exits:
            exit_frac = (high - exit_price) / spread if spread else 0.0
            exit_p = boost_probability(base_exit_p, exit_frac, odds_mult)
            tax = ge_tax_per_item(exit_price, tax_policy)
            net_per_unit = exit_price - tax - entry
            if net_per_unit < min_net_per_unit:
                continue
            raw_profit = net_per_unit * units
            exit_wait = expected_wait_hours(exit_p, anchor_hours, max_cycle)
            cycle_hours = min(max_cycle, max(0.25, entry_wait + exit_wait))
            round_trip_p = clamp(entry_p * exit_p * persistence_multiplier, 0.0, 0.95)
            expected_profit = raw_profit * round_trip_p * slippage_multiplier
            capacity_gp = entry * units
            expected_roi = expected_profit / capacity_gp * 100 if capacity_gp > 0 else 0.0
            expected_gph = expected_profit / cycle_hours if cycle_hours > 0 else 0.0
            candidate = {
                "entry_price_gp": entry,
                "exit_price_gp": exit_price,
                "entry_aggression_fraction_of_spread": round(entry_frac, 4),
                "exit_concession_fraction_of_spread": round(exit_frac, 4),
                "entry_fill_probability_at_anchor": round(entry_p, 4),
                "exit_fill_probability_at_anchor": round(exit_p, 4),
                "round_trip_completion_probability": round(round_trip_p, 4),
                "expected_cycle_hours": round(cycle_hours, 3),
                "raw_after_tax_profit_at_capacity_gp": int(raw_profit),
                "probability_weighted_profit_at_capacity_gp": int(expected_profit),
                "capacity_gp": int(capacity_gp),
                "expected_after_tax_roi_pct": round(expected_roi, 3),
                "expected_gp_per_hour": int(expected_gph),
                "ge_tax_per_item_gp": tax,
                "slippage_objective_multiplier": slippage_multiplier,
                "objective_gp_per_hour": expected_gph,
            }
            if best is None or candidate["objective_gp_per_hour"] > best["objective_gp_per_hour"]:
                best = candidate

    if best is None:
        row["price_optimizer_validation"] = "NO_PROFITABLE_PRICE_PAIR"
        return row

    pre = {
        "expected_gp_per_hour": row.get("expected_gp_per_hour"),
        "expected_profit_at_capacity_gp": row.get("expected_profit_at_capacity_gp"),
        "expected_after_tax_roi_pct": row.get("expected_after_tax_roi_pct"),
        "expected_hold_hours": row.get("expected_hold_hours"),
        "execution_probability_heuristic": row.get("execution_probability_heuristic"),
        "capacity_gp": row.get("capacity_gp"),
        "profit_efficiency_score": row.get("profit_efficiency_score"),
    }
    do_not_chase = int(round(low + spread * float(price_cfg.get("do_not_chase_fraction_of_spread") or 0.65)))
    do_not_chase = min(do_not_chase, high - 1)

    row["pre_price_optimization"] = pre
    row["optimal_execution"] = {k: v for k, v in best.items() if k != "objective_gp_per_hour"}
    row["optimal_entry_price_gp"] = best["entry_price_gp"]
    row["optimal_exit_price_gp"] = best["exit_price_gp"]
    row["do_not_chase_price_gp"] = do_not_chase
    row["price_optimizer_validation"] = "OPTIMIZED"
    row["price_optimizer_version"] = 1
    row["price_optimizer_learning_basis"] = "EMPIRICAL_BLEND" if row.get("real_execution_learning_applied") else "MODEL_PRIOR_ONLY"

    if row.get("auto_allocation_eligible") is True:
        row["entry_fill_probability_at_anchor"] = best["entry_fill_probability_at_anchor"]
        row["exit_fill_probability_at_anchor"] = best["exit_fill_probability_at_anchor"]
        row["execution_probability_heuristic"] = best["round_trip_completion_probability"]
        row["expected_cycle_hours"] = best["expected_cycle_hours"]
        row["expected_hold_hours"] = best["expected_cycle_hours"]
        row["expected_profit_at_capacity_gp"] = best["probability_weighted_profit_at_capacity_gp"]
        row["expected_after_tax_roi_pct"] = best["expected_after_tax_roi_pct"]
        row["expected_gp_per_hour"] = best["expected_gp_per_hour"]
        row["slot_efficiency_gp_per_hour"] = best["expected_gp_per_hour"]
        row["capacity_gp"] = best["capacity_gp"]
        row["player_time_adjusted_profit_gp"] = best["probability_weighted_profit_at_capacity_gp"]
        row["profit_efficiency_score"] = score(
            best["expected_gp_per_hour"],
            best["expected_after_tax_roi_pct"],
            best["capacity_gp"],
            best["round_trip_completion_probability"],
            row.get("learning_adjustment_points"),
        )
        row["price_optimizer_allocation_authority"] = True
    else:
        row["price_optimizer_allocation_authority"] = False

    return row


def main():
    packet = load_json(PACKET)
    if not packet:
        raise RuntimeError("desk_packet.json missing")
    cfg = load_json(CFG)
    profit = packet.get("profit_layer") or {}
    fast = profit.get("fast_flip_capacity_velocity") or []
    tax_policy = packet.get("tax_policy") or {}
    fast = [optimize_fast_row(dict(x), cfg, tax_policy) for x in fast]
    fast.sort(key=lambda x: (x.get("profit_efficiency_score") or 0, x.get("expected_gp_per_hour") or 0), reverse=True)
    profit["fast_flip_capacity_velocity"] = fast

    state = profit.get("execution_upgrade_state") or {}
    state.update({
        "optimal_entry_exit_price_optimizer": "ACTIVE",
        "gp_per_ge_slot_hour_optimizer": "ACTIVE",
        "active_vs_parking_slot_buckets": "ACTIVE",
        "phase2_rollout": "PERSISTENT_SPREADS_HAVE_PRICE_OPTIMIZER_ALLOCATION_AUTHORITY",
    })
    profit["execution_upgrade_state"] = state
    profit["phase2_generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    packet["profit_layer"] = profit
    save_json(PACKET, packet)
    optimized = sum(1 for x in fast if x.get("price_optimizer_validation") == "OPTIMIZED")
    authoritative = sum(1 for x in fast if x.get("price_optimizer_allocation_authority"))
    print(f"Phase-2 price optimizer: optimized={optimized} allocation_authority={authoritative}")


if __name__ == "__main__":
    main()
