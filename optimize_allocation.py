#!/usr/bin/env python3
import json

PACKET = "desk_packet.json"
CFG = "project/profit_engine.json"


def load(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def save(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")


def positive(x):
    return isinstance(x, (int, float)) and x > 0


def row_key(x):
    return (x.get("engine"), x.get("name") or x.get("strategy") or x.get("item_or_strategy"))


def slot_bucket_for(engine, hold_hours, phase2_cfg):
    slot_cfg = phase2_cfg.get("slot_architecture") or {}
    active_max = float(slot_cfg.get("active_max_expected_hold_hours") or 6)
    if engine == "fast_flip":
        return "ACTIVE"
    if engine == "evergreen":
        return "PARKING"
    if engine == "conversion":
        if isinstance(hold_hours, (int, float)) and hold_hours <= active_max:
            return "FLEXIBLE"
        return "PARKING"
    return "FLEXIBLE"


def minimum_profit_hurdle_config(cfg):
    return ((cfg.get("phase3") or {}).get("minimum_absolute_profit_hurdles") or {})


def minimum_profit_hurdle_authoritative(cfg):
    hurdle_cfg = minimum_profit_hurdle_config(cfg)
    return bool(hurdle_cfg.get("enabled")) and hurdle_cfg.get("rollout_status") == "ALLOCATION_AUTHORITATIVE"


def annotate_minimum_profit_hurdle(row, cfg):
    hurdle_cfg = minimum_profit_hurdle_config(cfg)
    if not hurdle_cfg.get("enabled"):
        return row
    thresholds = hurdle_cfg.get("minimum_expected_profit_gp_by_slot_bucket") or {}
    bucket = row.get("slot_bucket") or "FLEXIBLE"
    hurdle_gp = thresholds.get(bucket)
    profit_gp = row.get("expected_profit_at_capacity_gp")
    if not isinstance(hurdle_gp, (int, float)) or hurdle_gp < 0:
        row["minimum_absolute_profit_hurdle_pass"] = None
        row["minimum_absolute_profit_hurdle_reason"] = "NO_BUCKET_THRESHOLD"
        return row
    passed = isinstance(profit_gp, (int, float)) and profit_gp >= hurdle_gp
    row.update({
        "minimum_absolute_profit_hurdle_gp": int(hurdle_gp),
        "minimum_absolute_profit_hurdle_pass": passed,
        "minimum_absolute_profit_shortfall_gp": max(0, int(hurdle_gp - profit_gp)) if isinstance(profit_gp, (int, float)) else None,
    })
    return row


def sanitized_rows(profit, cfg):
    phase2_cfg = cfg.get("phase2") or {}
    rows = []
    for group in ("fast_flip_capacity_velocity", "evergreen_capacity_velocity", "conversion_capacity_velocity"):
        for x in profit.get(group) or []:
            profit_gp = x.get("expected_profit_at_capacity_gp")
            if profit_gp is None:
                profit_gp = x.get("player_time_adjusted_profit_gp")
            gph = x.get("expected_gp_per_hour")
            roi = x.get("expected_after_tax_roi_pct")
            hold = x.get("expected_hold_hours")
            capacity = x.get("capacity_gp")
            if not positive(profit_gp) or not positive(gph) or not positive(capacity) or not positive(hold):
                continue
            if x.get("auto_allocation_eligible") is False:
                continue
            validation = x.get("validation_flag")
            if validation in {
                "ANOMALOUS_PATIENT_MARGIN_REQUIRES_VALIDATION",
                "SPREAD_NOT_PERSISTENT",
                "SPREAD_UNSTABLE",
                "SPREAD_INVALID",
                "SPREAD_PERSISTENCE_UNKNOWN",
            }:
                continue
            if x.get("type") == "dose_decant":
                max_raw = max(v for v in (x.get("patient_roi_pct"), x.get("immediate_roi_pct"), 0) if isinstance(v, (int, float)))
                if max_raw > 15:
                    continue
            roi_per_hour = (roi / hold) if isinstance(roi, (int, float)) else None
            engine = x.get("engine")
            bucket = slot_bucket_for(engine, hold, phase2_cfg)
            row = {
                "engine": engine,
                "item_or_strategy": x.get("name") or x.get("strategy"),
                "profit_efficiency_score": x.get("profit_efficiency_score"),
                "capacity_gp": int(capacity),
                "expected_profit_at_capacity_gp": int(profit_gp),
                "expected_gp_per_hour": int(gph),
                "gp_per_ge_slot_hour": int(gph),
                "expected_after_tax_roi_pct": roi,
                "expected_hold_hours": hold,
                "expected_roi_per_capital_hour_pct": round(roi_per_hour, 5) if roi_per_hour is not None else None,
                "execution_probability_heuristic": x.get("execution_probability_heuristic"),
                "slippage_risk": x.get("slippage_risk"),
                "player_time_hours": x.get("player_time_hours"),
                "spread_persistence_class": x.get("spread_persistence_class"),
                "expected_cycle_hours": x.get("expected_cycle_hours"),
                "real_execution_learning_applied": x.get("real_execution_learning_applied"),
                "optimal_entry_price_gp": x.get("optimal_entry_price_gp"),
                "optimal_exit_price_gp": x.get("optimal_exit_price_gp"),
                "do_not_chase_price_gp": x.get("do_not_chase_price_gp"),
                "price_optimizer_allocation_authority": x.get("price_optimizer_allocation_authority"),
                "slot_bucket": bucket,
                "source_key": row_key(x),
            }
            rows.append(annotate_minimum_profit_hurdle(row, cfg))
    best = {}
    for x in rows:
        key = x["source_key"]
        prior = best.get(key)
        if prior is None or x["expected_gp_per_hour"] > prior["expected_gp_per_hour"]:
            best[key] = x
    return list(best.values())


def allocation_rows(rows, cfg):
    if not minimum_profit_hurdle_authoritative(cfg):
        return list(rows)
    return [x for x in rows if x.get("minimum_absolute_profit_hurdle_pass") is True]


def minimum_profit_hurdle_summary(rows, cfg):
    hurdle_cfg = minimum_profit_hurdle_config(cfg)
    enabled = bool(hurdle_cfg.get("enabled"))
    rollout = hurdle_cfg.get("rollout_status") or "DISABLED"
    evaluated = [x for x in rows if x.get("minimum_absolute_profit_hurdle_pass") is not None]
    passed = [x for x in evaluated if x.get("minimum_absolute_profit_hurdle_pass") is True]
    failed = [x for x in evaluated if x.get("minimum_absolute_profit_hurdle_pass") is False]
    by_bucket = {}
    for bucket in ("ACTIVE", "PARKING", "FLEXIBLE"):
        bucket_rows = [x for x in evaluated if x.get("slot_bucket") == bucket]
        by_bucket[bucket] = {
            "evaluated": len(bucket_rows),
            "passed": sum(1 for x in bucket_rows if x.get("minimum_absolute_profit_hurdle_pass") is True),
            "failed": sum(1 for x in bucket_rows if x.get("minimum_absolute_profit_hurdle_pass") is False),
        }
    advisory_failures = sorted(
        failed,
        key=lambda x: (x.get("profit_efficiency_score") or 0, x.get("expected_gp_per_hour") or 0),
        reverse=True,
    )
    return {
        "enabled": enabled,
        "rollout_status": rollout,
        "allocation_authoritative": minimum_profit_hurdle_authoritative(cfg),
        "evaluation_basis": hurdle_cfg.get("evaluation_basis"),
        "thresholds_gp_by_slot_bucket": hurdle_cfg.get("minimum_expected_profit_gp_by_slot_bucket") or {},
        "evaluated_candidates": len(evaluated),
        "passed_candidates": len(passed),
        "failed_candidates": len(failed),
        "would_change_current_frontiers": bool(failed),
        "by_slot_bucket": by_bucket,
        "advisory_failures": [{
            "engine": x.get("engine"),
            "item_or_strategy": x.get("item_or_strategy"),
            "slot_bucket": x.get("slot_bucket"),
            "expected_profit_at_capacity_gp": x.get("expected_profit_at_capacity_gp"),
            "minimum_absolute_profit_hurdle_gp": x.get("minimum_absolute_profit_hurdle_gp"),
            "minimum_absolute_profit_shortfall_gp": x.get("minimum_absolute_profit_shortfall_gp"),
        } for x in advisory_failures[:10]],
        "promotion_rule": hurdle_cfg.get("promotion_rule"),
    }


def known_offer_bucket_counts(packet):
    counts = {"ACTIVE": 0, "PARKING": 0, "FLEXIBLE": 0}
    for offer in packet.get("open_offers_unconfirmed") or []:
        bucket = str(offer.get("slot_bucket") or "PARKING").upper()
        if bucket not in counts:
            bucket = "PARKING"
        counts[bucket] += 1
    return counts


def build_slot_optimizer(packet, rows, cfg):
    ge_cfg = cfg.get("ge_slots") or {}
    phase2_cfg = cfg.get("phase2") or {}
    slot_cfg = phase2_cfg.get("slot_architecture") or {}

    total_slots = int(ge_cfg.get("total_slots") or 8)
    known_counts = known_offer_bucket_counts(packet)
    known_total = sum(known_counts.values())
    free_upper = max(0, total_slots - known_total)
    minimum_slot_gph = int(ge_cfg.get("minimum_slot_efficiency_gp_per_hour") or 50000)

    targets = {
        "ACTIVE": int(slot_cfg.get("active_target_slots") or 4),
        "PARKING": int(slot_cfg.get("parking_target_slots") or 3),
        "FLEXIBLE": int(slot_cfg.get("flexible_reserve_slots") or 1),
    }

    ranked = sorted(rows, key=lambda x: (x.get("gp_per_ge_slot_hour") or 0, x.get("expected_profit_at_capacity_gp") or 0), reverse=True)
    meaningful = [x for x in ranked if (x.get("gp_per_ge_slot_hour") or 0) >= minimum_slot_gph]

    bucket_recommendations = {}
    for bucket in ("ACTIVE", "PARKING", "FLEXIBLE"):
        remaining_target = max(0, targets[bucket] - known_counts.get(bucket, 0))
        candidates = [x for x in meaningful if x.get("slot_bucket") == bucket]
        bucket_recommendations[bucket] = [{
            "engine": x["engine"],
            "item_or_strategy": x["item_or_strategy"],
            "gp_per_ge_slot_hour": x["gp_per_ge_slot_hour"],
            "capacity_gp": x["capacity_gp"],
            "expected_profit_at_capacity_gp": x["expected_profit_at_capacity_gp"],
            "expected_hold_hours": x.get("expected_hold_hours"),
            "optimal_entry_price_gp": x.get("optimal_entry_price_gp"),
            "optimal_exit_price_gp": x.get("optimal_exit_price_gp"),
            "spread_persistence_class": x.get("spread_persistence_class"),
        } for x in candidates[:remaining_target]]

    global_priority = [{
        "engine": x["engine"],
        "item_or_strategy": x["item_or_strategy"],
        "slot_bucket": x["slot_bucket"],
        "gp_per_ge_slot_hour": x["gp_per_ge_slot_hour"],
        "capacity_gp": x["capacity_gp"],
        "expected_profit_at_capacity_gp": x["expected_profit_at_capacity_gp"],
        "profit_efficiency_score": x.get("profit_efficiency_score"),
        "expected_hold_hours": x.get("expected_hold_hours"),
        "optimal_entry_price_gp": x.get("optimal_entry_price_gp"),
        "optimal_exit_price_gp": x.get("optimal_exit_price_gp"),
        "spread_persistence_class": x.get("spread_persistence_class"),
    } for x in meaningful[:free_upper]]

    return {
        "total_ge_slots": total_slots,
        "known_desk_open_offer_slots": known_total,
        "known_bucket_usage": known_counts,
        "modeled_free_slots_upper_bound": free_upper,
        "actual_free_slots_unknown": True,
        "minimum_slot_efficiency_gp_per_hour": minimum_slot_gph,
        "slot_bucket_targets": targets,
        "bucket_recommendations": bucket_recommendations,
        "recommended_slot_priority": global_priority,
        "metric": "probability-weighted GP per GE-slot-hour after modeled execution, tax, slippage and player-time adjustments",
        "rule": "ACTIVE is reserved for short-cycle velocity, PARKING for patient evergreen/crash-catcher capital, and FLEXIBLE for relative-value or opportunistic use. Targets are soft architecture, not rigid caps; actual free-slot counts remain upper bounds until user-confirmed.",
    }


def main():
    packet = load(PACKET)
    cfg = load(CFG)
    profit = packet.get("profit_layer") or {}
    rows = sanitized_rows(profit, cfg)
    hurdle_summary = minimum_profit_hurdle_summary(rows, cfg)
    frontier_rows = allocation_rows(rows, cfg)

    absolute = sorted(frontier_rows, key=lambda x: (x.get("expected_gp_per_hour") or 0, x.get("expected_profit_at_capacity_gp") or 0), reverse=True)
    marginal = sorted(frontier_rows, key=lambda x: (x.get("expected_roi_per_capital_hour_pct") or -999, x.get("expected_gp_per_hour") or 0), reverse=True)
    balanced = sorted(frontier_rows, key=lambda x: (x.get("profit_efficiency_score") or 0, x.get("expected_gp_per_hour") or 0), reverse=True)
    slot_ranked = sorted(frontier_rows, key=lambda x: (x.get("gp_per_ge_slot_hour") or 0, x.get("expected_profit_at_capacity_gp") or 0), reverse=True)

    cumulative = 0
    ladder = []
    for rank, x in enumerate(marginal, 1):
        cumulative += x["capacity_gp"]
        ladder.append({**x, "rank": rank, "cumulative_capacity_gp": cumulative})

    for rank, x in enumerate(slot_ranked, 1):
        x["ge_slot_hour_rank"] = rank

    profit["absolute_velocity_frontier"] = absolute[:15]
    profit["marginal_capital_frontier"] = marginal[:15]
    profit["capital_allocation_ladder"] = ladder[:15]
    profit["capital_frontier"] = balanced[:15]
    profit["ge_slot_hour_frontier"] = slot_ranked[:15]
    profit["allocation_rule"] = (
        "With unknown liquid cash, deploy incrementally down the marginal-capital ladder to modeled capacity. "
        "Fast flips require persistent-spread validation before allocation. Phase-2 fast flips use the price pair "
        "that maximizes modeled probability-weighted GP/hour; GE slots are ranked separately by GP per slot-hour. "
        "Phase-3 minimum absolute-profit hurdles remain observation-only until their promotion rule is satisfied."
    )
    profit["ge_slot_optimizer"] = build_slot_optimizer(packet, frontier_rows, cfg)
    profit["minimum_absolute_profit_hurdles"] = hurdle_summary

    state = profit.get("execution_upgrade_state") or {}
    state.update({
        "optimal_entry_exit_price_optimizer": "ACTIVE",
        "gp_per_ge_slot_hour_optimizer": "ACTIVE",
        "active_vs_parking_slot_buckets": "ACTIVE",
        "minimum_absolute_profit_hurdles": hurdle_summary.get("rollout_status"),
    })
    profit["execution_upgrade_state"] = state

    packet["profit_layer"] = profit
    save(PACKET, packet)
    print(
        f"Optimized allocation frontiers: valid={len(rows)} authoritative={len(frontier_rows)} "
        f"marginal={len(ladder)} slot_ranked={len(slot_ranked)} "
        f"hurdle={hurdle_summary.get('rollout_status')} failed={hurdle_summary.get('failed_candidates')}"
    )


if __name__ == "__main__":
    main()
