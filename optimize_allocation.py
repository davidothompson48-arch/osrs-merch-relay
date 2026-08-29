#!/usr/bin/env python3
import json

PACKET = "desk_packet.json"
CFG = "project/profit_engine.json"
BOOK = "opportunity_book.json"
REAL = "real_execution_summary.json"
LIFECYCLE = "project/position_lifecycle.json"


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


def repeatability_config(cfg):
    return ((cfg.get("phase3") or {}).get("repeatability_multiplier") or {})


def opportunity_book_data_sufficient(book, cfg, real):
    book_cfg = ((cfg.get("phase3") or {}).get("persistent_opportunity_book") or {})
    repeat_cfg = repeatability_config(cfg)
    minimum_cycles = int(book_cfg.get("minimum_cycles_before_review") or 12)
    minimum_observations = int(book_cfg.get("minimum_candidate_observations_before_review") or 50)
    minimum_round_trips = int(repeat_cfg.get("minimum_real_round_trips_before_authority") or 20)
    completed = int(((real.get("round_trips") or {}).get("completed_round_trips") or 0))
    return (
        int(book.get("cycles_observed") or 0) >= minimum_cycles
        and int(book.get("total_candidate_observations") or 0) >= minimum_observations
        and completed >= minimum_round_trips
    )


def repeatability_authoritative(cfg, book, real):
    repeat_cfg = repeatability_config(cfg)
    return (
        bool(repeat_cfg.get("enabled"))
        and repeat_cfg.get("rollout_status") == "ALLOCATION_AUTHORITATIVE"
        and opportunity_book_data_sufficient(book, cfg, real)
    )


def annotate_repeatability(row, cfg, book, real):
    repeat_cfg = repeatability_config(cfg)
    if not repeat_cfg.get("enabled"):
        return row
    key = f"{row.get('engine')}::{row.get('item_or_strategy')}"
    record = (book.get("records") or {}).get(key) or {}
    classification = record.get("repeatability_class") or "UNOBSERVED"
    multipliers = repeat_cfg.get("advisory_multiplier_by_class") or {}
    configured_multiplier = float(multipliers.get(classification, multipliers.get("UNOBSERVED", 1.0)))
    item_summary = ((real.get("by_item") or {}).get(row.get("item_or_strategy")) or {})
    real_orders = int(item_summary.get("orders_total") or 0)
    realized_item = ((((real.get("performance_dashboard") or {}).get("by_item") or {}).get(row.get("item_or_strategy"))) or {})
    real_round_trips = int(realized_item.get("round_trips") or 0)
    real_profit = int(realized_item.get("realized_net_profit_gp") or 0)
    real_win_rate = realized_item.get("win_rate_pct")
    minimum_item_round_trips = int(repeat_cfg.get("minimum_item_round_trips_before_bonus") or 3)
    minimum_item_win_rate = float(repeat_cfg.get("minimum_item_win_rate_pct_before_bonus") or 50)
    realized_bonus_confirmed = (
        real_round_trips >= minimum_item_round_trips
        and real_profit > 0
        and isinstance(real_win_rate, (int, float))
        and real_win_rate >= minimum_item_win_rate
    )
    multiplier = configured_multiplier
    if configured_multiplier > 1.0 and not realized_bonus_confirmed:
        multiplier = 1.0
    authority = repeatability_authoritative(cfg, book, real)
    prior_adjustment = row.get("pre_repeatability_adjustment") or {}
    profit = int(prior_adjustment.get("expected_profit_at_capacity_gp") or row.get("expected_profit_at_capacity_gp") or 0)
    gph = int(prior_adjustment.get("expected_gp_per_hour") or row.get("expected_gp_per_hour") or 0)
    row.update({
        "repeatability_class": classification,
        "repeatability_score": record.get("repeatability_score"),
        "repeatability_observations": int(record.get("observations") or 0),
        "repeatability_qualified_ratio": record.get("qualified_ratio"),
        "repeatability_configured_multiplier": configured_multiplier,
        "repeatability_multiplier_advisory": multiplier,
        "repeatability_adjusted_profit_gp_advisory": int(profit * multiplier),
        "repeatability_adjusted_gp_per_hour_advisory": int(gph * multiplier),
        "repeatability_real_execution_orders": real_orders,
        "repeatability_real_completed_round_trips": real_round_trips,
        "repeatability_realized_net_profit_gp": real_profit,
        "repeatability_realized_win_rate_pct": real_win_rate,
        "repeatability_bonus_real_execution_confirmed": realized_bonus_confirmed,
        "repeatability_allocation_authority": authority,
    })
    if authority:
        row["pre_repeatability_adjustment"] = {
            "expected_profit_at_capacity_gp": profit,
            "expected_gp_per_hour": gph,
            "profit_efficiency_score": row.get("profit_efficiency_score"),
        }
        row["expected_profit_at_capacity_gp"] = int(profit * multiplier)
        row["expected_gp_per_hour"] = int(gph * multiplier)
        row["gp_per_ge_slot_hour"] = int(gph * multiplier)
        if isinstance(row.get("profit_efficiency_score"), (int, float)):
            row["profit_efficiency_score"] = round(min(100, row["profit_efficiency_score"] * multiplier), 1)
    return row


def sanitized_rows(profit, cfg, book=None, real=None):
    book = book or {}
    real = real or {}
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
                "player_time_attention": x.get("player_time_attention"),
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
            row = annotate_repeatability(row, cfg, book, real)
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
    multiplier = 1.0
    attention_cfg = attention_modes_config(cfg)
    if attention_cfg.get("rollout_status") == "ALLOCATION_AUTHORITATIVE":
        mode = str(attention_cfg.get("current_mode") or "NORMAL").upper()
        mode_cfg = (attention_cfg.get("modes") or {}).get(mode) or {}
        multiplier = float(mode_cfg.get("absolute_profit_hurdle_multiplier") or 1.0)
    return [
        x for x in rows
        if float(x.get("expected_profit_at_capacity_gp") or 0)
        >= float(x.get("minimum_absolute_profit_hurdle_gp") or 0) * multiplier
    ]


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


def repeatability_summary(rows, cfg, book, real):
    repeat_cfg = repeatability_config(cfg)
    counts = {}
    for row in rows:
        label = row.get("repeatability_class") or "UNOBSERVED"
        counts[label] = counts.get(label, 0) + 1
    ranked = sorted(
        rows,
        key=lambda x: (x.get("repeatability_score") or -1, x.get("expected_gp_per_hour") or 0),
        reverse=True,
    )
    return {
        "enabled": bool(repeat_cfg.get("enabled")),
        "rollout_status": repeat_cfg.get("rollout_status") or "DISABLED",
        "allocation_authoritative": repeatability_authoritative(cfg, book, real),
        "authority_data_sufficient": opportunity_book_data_sufficient(book, cfg, real),
        "class_counts": counts,
        "book_cycles_observed": int(book.get("cycles_observed") or 0),
        "book_candidate_observations": int(book.get("total_candidate_observations") or 0),
        "real_completed_round_trips": int(((real.get("round_trips") or {}).get("completed_round_trips") or 0)),
        "candidates": [{
            "engine": x.get("engine"),
            "item_or_strategy": x.get("item_or_strategy"),
            "repeatability_class": x.get("repeatability_class"),
            "repeatability_score": x.get("repeatability_score"),
            "observations": x.get("repeatability_observations"),
            "qualified_ratio": x.get("repeatability_qualified_ratio"),
            "advisory_multiplier": x.get("repeatability_multiplier_advisory"),
            "advisory_expected_gp_per_hour": x.get("repeatability_adjusted_gp_per_hour_advisory"),
            "real_completed_round_trips": x.get("repeatability_real_completed_round_trips"),
            "realized_net_profit_gp": x.get("repeatability_realized_net_profit_gp"),
            "bonus_real_execution_confirmed": x.get("repeatability_bonus_real_execution_confirmed"),
        } for x in ranked[:10]],
        "rule": repeat_cfg.get("rule"),
    }


def attention_rank(label):
    return {"PASSIVE": 0, "NEGLIGIBLE": 1, "LOW": 2, "MEDIUM": 3, "HIGH": 4}.get(str(label or "MEDIUM").upper(), 3)


def effective_attention(row, cfg):
    explicit = row.get("player_time_attention")
    if explicit:
        return str(explicit).upper()
    if float(row.get("player_time_hours") or 0) <= 0:
        return "PASSIVE"
    return str((cfg.get("player_time") or {}).get("default_manual_attention") or "MEDIUM").upper()


def attention_modes_config(cfg):
    return ((cfg.get("phase4") or {}).get("attention_modes") or {})


def attention_mode_rows(rows, cfg):
    attention_cfg = attention_modes_config(cfg)
    if not attention_cfg.get("enabled") or attention_cfg.get("rollout_status") != "ALLOCATION_AUTHORITATIVE":
        return list(rows)
    mode = str(attention_cfg.get("current_mode") or "NORMAL").upper()
    mode_cfg = (attention_cfg.get("modes") or {}).get(mode) or {}
    max_attention = attention_rank(mode_cfg.get("maximum_player_time_attention") or "MEDIUM")
    hurdle_multiplier = float(mode_cfg.get("absolute_profit_hurdle_multiplier") or 1.0)
    allowed_buckets = set(mode_cfg.get("allowed_slot_buckets") or ["ACTIVE", "PARKING", "FLEXIBLE"])
    return [
        row for row in rows
        if row.get("slot_bucket") in allowed_buckets
        and attention_rank(effective_attention(row, cfg)) <= max_attention
        and row.get("expected_profit_at_capacity_gp", 0) >= float(row.get("minimum_absolute_profit_hurdle_gp") or 0) * hurdle_multiplier
    ]


def build_attention_modes(rows, cfg):
    attention_cfg = attention_modes_config(cfg)
    scenarios = {}
    for mode, mode_cfg in (attention_cfg.get("modes") or {}).items():
        max_attention = attention_rank(mode_cfg.get("maximum_player_time_attention") or "MEDIUM")
        hurdle_multiplier = float(mode_cfg.get("absolute_profit_hurdle_multiplier") or 1.0)
        allowed_buckets = set(mode_cfg.get("allowed_slot_buckets") or ["ACTIVE", "PARKING", "FLEXIBLE"])
        eligible = []
        for row in rows:
            hurdle = float(row.get("minimum_absolute_profit_hurdle_gp") or 0) * hurdle_multiplier
            if row.get("slot_bucket") not in allowed_buckets:
                continue
            if attention_rank(effective_attention(row, cfg)) > max_attention:
                continue
            if float(row.get("expected_profit_at_capacity_gp") or 0) < hurdle:
                continue
            eligible.append(row)
        eligible.sort(key=lambda x: (x.get("profit_efficiency_score") or 0, x.get("expected_gp_per_hour") or 0), reverse=True)
        scenarios[mode] = {
            "eligible_candidates": len(eligible),
            "maximum_player_time_attention": mode_cfg.get("maximum_player_time_attention"),
            "absolute_profit_hurdle_multiplier": hurdle_multiplier,
            "top_candidates": [{
                "engine": x.get("engine"),
                "item_or_strategy": x.get("item_or_strategy"),
                "slot_bucket": x.get("slot_bucket"),
                "expected_profit_at_capacity_gp": x.get("expected_profit_at_capacity_gp"),
                "expected_gp_per_hour": x.get("expected_gp_per_hour"),
                "player_time_attention": effective_attention(x, cfg),
            } for x in eligible[:5]],
        }
    return {
        "enabled": bool(attention_cfg.get("enabled")),
        "rollout_status": attention_cfg.get("rollout_status") or "DISABLED",
        "allocation_authoritative": attention_cfg.get("rollout_status") == "ALLOCATION_AUTHORITATIVE",
        "current_mode": attention_cfg.get("current_mode") or "NORMAL",
        "scenarios": scenarios,
        "rule": attention_cfg.get("rule"),
    }


def tax_for(price, tax_policy):
    if not isinstance(price, (int, float)) or price <= 0:
        return 0
    rate = float(tax_policy.get("rate") or 0)
    cap = int(tax_policy.get("cap_gp_per_item") or 0)
    value = int(price * rate)
    return min(value, cap) if cap > 0 else value


def build_remaining_upside_rotation(packet, rows, cfg, lifecycle):
    rotation_cfg = ((cfg.get("phase4") or {}).get("remaining_upside_capital_rotation") or {})
    tax_policy = packet.get("tax_policy") or {}
    position_cfg = lifecycle.get("positions") or {}
    minimum_multiple = float(rotation_cfg.get("minimum_velocity_advantage_multiple") or 2.0)
    minimum_advantage = int(rotation_cfg.get("minimum_expected_profit_advantage_gp") or 250000)
    alternatives = [
        x for x in rows
        if x.get("minimum_absolute_profit_hurdle_pass") is True
        and x.get("repeatability_class") not in {"INCONSISTENT"}
    ]
    alternatives.sort(key=lambda x: (x.get("expected_gp_per_hour") or 0, x.get("expected_profit_at_capacity_gp") or 0), reverse=True)
    alerts = []
    data_gaps = []
    exempt = []
    evaluated = 0
    for position in packet.get("portfolio") or []:
        item_id = str(position.get("item_id"))
        meta = position_cfg.get(item_id) or {}
        if meta.get("hold_for_use") or (position.get("capital_aging") or {}).get("exempt"):
            exempt.append(position.get("item"))
            continue
        missing = []
        target = meta.get("expected_exit_price_gp_each")
        if not isinstance(target, (int, float)) or target <= 0:
            missing.append("expected_exit_price_gp_each")
        remaining_hours = meta.get("expected_time_remaining_hours")
        if not isinstance(remaining_hours, (int, float)) or remaining_hours <= 0:
            expected = meta.get("expected_payoff_hours")
            age = (position.get("capital_aging") or {}).get("tracking_age_hours")
            if isinstance(expected, (int, float)) and isinstance(age, (int, float)):
                remaining_hours = max(1.0, expected - age)
            else:
                missing.append("expected_time_remaining_hours")
        current_low = (position.get("current") or {}).get("low")
        quantity = position.get("quantity")
        if not isinstance(current_low, (int, float)) or current_low <= 0:
            missing.append("fresh_current_low")
        if not isinstance(quantity, (int, float)) or quantity <= 0:
            missing.append("quantity")
        if missing:
            data_gaps.append({"item": position.get("item"), "missing": sorted(set(missing))})
            continue
        evaluated += 1
        liquidation_net = (current_low - tax_for(current_low, tax_policy)) * quantity
        future_net = (target - tax_for(target, tax_policy)) * quantity
        remaining_profit = future_net - liquidation_net
        holding_gph = remaining_profit / remaining_hours
        if not alternatives or liquidation_net <= 0:
            continue
        alternative = alternatives[0]
        deployable = min(liquidation_net, float(alternative.get("capacity_gp") or 0))
        if deployable <= 0:
            continue
        alt_scale = deployable / float(alternative.get("capacity_gp") or 1)
        holding_scale = deployable / liquidation_net
        alternative_profit = float(alternative.get("expected_profit_at_capacity_gp") or 0) * alt_scale
        alternative_gph = float(alternative.get("expected_gp_per_hour") or 0) * alt_scale
        comparable_holding_gph = holding_gph * holding_scale
        hold = float(alternative.get("expected_hold_hours") or 0)
        holding_profit_over_alt_horizon = comparable_holding_gph * hold
        advantage_gp = alternative_profit - holding_profit_over_alt_horizon
        multiple = alternative_gph / max(abs(comparable_holding_gph), 1)
        if multiple >= minimum_multiple and advantage_gp >= minimum_advantage:
            alerts.append({
                "reduce_item": position.get("item"),
                "rotate_to": alternative.get("item_or_strategy"),
                "deployable_gp": int(deployable),
                "holding_remaining_profit_gp": int(remaining_profit * holding_scale),
                "holding_remaining_hours": round(remaining_hours, 2),
                "alternative_expected_profit_gp": int(alternative_profit),
                "alternative_expected_hold_hours": hold,
                "expected_profit_advantage_gp": int(advantage_gp),
                "velocity_advantage_multiple": round(multiple, 2),
                "rotation_is_advisory": True,
            })
    alerts.sort(key=lambda x: (x.get("expected_profit_advantage_gp") or 0, x.get("velocity_advantage_multiple") or 0), reverse=True)
    return {
        "enabled": bool(rotation_cfg.get("enabled")),
        "rollout_status": rotation_cfg.get("rollout_status") or "DISABLED",
        "allocation_authoritative": False,
        "evaluated_positions": evaluated,
        "data_gap_positions": len(data_gaps),
        "hold_for_use_exempt_positions": len(exempt),
        "hold_for_use_exempt_items": exempt,
        "data_gaps": data_gaps,
        "rotation_alerts": alerts[:10],
        "minimum_velocity_advantage_multiple": minimum_multiple,
        "minimum_expected_profit_advantage_gp": minimum_advantage,
        "rule": rotation_cfg.get("rule"),
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
    book = load(BOOK)
    real = load(REAL)
    lifecycle = load(LIFECYCLE)
    profit = packet.get("profit_layer") or {}
    rows = sanitized_rows(profit, cfg, book, real)
    hurdle_summary = minimum_profit_hurdle_summary(rows, cfg)
    repeat_summary = repeatability_summary(rows, cfg, book, real)
    attention_summary = build_attention_modes(rows, cfg)
    frontier_rows = allocation_rows(rows, cfg)
    frontier_rows = attention_mode_rows(frontier_rows, cfg)

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
    profit["repeatability_multiplier"] = repeat_summary
    profit["attention_modes"] = attention_summary
    profit["remaining_upside_capital_rotation"] = build_remaining_upside_rotation(packet, frontier_rows, cfg, lifecycle)

    state = profit.get("execution_upgrade_state") or {}
    state.update({
        "optimal_entry_exit_price_optimizer": "ACTIVE",
        "gp_per_ge_slot_hour_optimizer": "ACTIVE",
        "active_vs_parking_slot_buckets": "ACTIVE",
        "minimum_absolute_profit_hurdles": hurdle_summary.get("rollout_status"),
        "repeatability_multiplier": repeat_summary.get("rollout_status"),
        "attention_modes": attention_summary.get("rollout_status"),
        "remaining_upside_capital_rotation": profit["remaining_upside_capital_rotation"].get("rollout_status"),
    })
    profit["execution_upgrade_state"] = state

    packet["profit_layer"] = profit
    save(PACKET, packet)
    print(
        f"Optimized allocation frontiers: valid={len(rows)} authoritative={len(frontier_rows)} "
        f"marginal={len(ladder)} slot_ranked={len(slot_ranked)} "
        f"hurdle={hurdle_summary.get('rollout_status')} failed={hurdle_summary.get('failed_candidates')} "
        f"repeatability={repeat_summary.get('rollout_status')} attention={attention_summary.get('current_mode')}"
    )


if __name__ == "__main__":
    main()
