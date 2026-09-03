#!/usr/bin/env python3
"""Turn live portfolio gains and catalyst realization into explicit exit plans.

The rest of the profit stack is intentionally strongest at ranking new uses of GP.
This module closes the lifecycle loop for positions already owned.  It never treats
a thin HIGH print as instantly realizable: thin tape changes the order style and
fill window, while sufficiently strong profit/catalyst evidence can still require
a patient staged sell.
"""

import json
import math
import time
from datetime import datetime, timezone


PACKET = "desk_packet.json"
CFG = "project/profit_engine.json"
LIFECYCLE = "project/position_lifecycle.json"


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {} if default is None else default


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
        handle.write("\n")


def valid_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def tax_for(item, price, tax_policy):
    if not valid_number(price):
        return None
    if item in set(tax_policy.get("exempt_items") or []):
        return 0
    rate = float(tax_policy.get("rate") or 0)
    cap = int(tax_policy.get("cap_gp_per_item") or 0)
    tax = math.floor(price * rate)
    return min(tax, cap) if cap > 0 else tax


def net_unit_value(item, price, tax_policy):
    tax = tax_for(item, price, tax_policy)
    return price - tax if tax is not None else None


def after_tax_roi_pct(item, price, basis_each, tax_policy):
    net = net_unit_value(item, price, tax_policy)
    if not valid_number(net) or not valid_number(basis_each):
        return None
    return (net / basis_each - 1) * 100


def round_price_down(price):
    """Round an order floor to a practical GE price without rounding it upward."""
    if not valid_number(price):
        return None
    if price >= 100_000_000:
        step = 100_000
    elif price >= 10_000_000:
        step = 25_000
    elif price >= 1_000_000:
        step = 5_000
    elif price >= 100_000:
        step = 500
    elif price >= 10_000:
        step = 100
    elif price >= 1_000:
        step = 25
    elif price >= 100:
        step = 5
    else:
        step = 1
    return max(step, int(math.floor(price / step) * step))


def quantity_step(quantity):
    if quantity >= 10_000:
        return 500
    if quantity >= 1_000:
        return 100
    if quantity >= 100:
        return 10
    return 1


def round_quantity_up(quantity, total_quantity):
    step = quantity_step(total_quantity)
    return int(math.ceil(quantity / step) * step)


def minimum_price_for_net_proceeds(item, quantity, target_net_gp, tax_policy):
    """Find the lowest integer GE price whose after-tax proceeds meet a target."""
    if not valid_number(quantity) or not valid_number(target_net_gp):
        return None
    required_each = target_net_gp / quantity
    rate = float(tax_policy.get("rate") or 0)
    estimate = max(1, int(math.floor(required_each / max(1 - rate, 0.000001))))
    low = max(1, estimate - 10)
    high = max(low + 1, estimate + 10)
    while (net_unit_value(item, high, tax_policy) or 0) * quantity < target_net_gp:
        high *= 2
    while low < high:
        mid = (low + high) // 2
        if (net_unit_value(item, mid, tax_policy) or 0) * quantity >= target_net_gp:
            high = mid
        else:
            low = mid + 1
    return low


def parse_day(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except Exception:
            return None


def realized_catalysts(policy, catalyst_state, now):
    configured = set(policy.get("realization_catalyst_ids") or [])
    if not configured:
        return []
    maximum_age_days = int(policy.get("maximum_realization_age_days") or 7)
    today = datetime.fromtimestamp(now, timezone.utc).date()
    matches = []
    for record in catalyst_state.get("records") or []:
        if record.get("id") not in configured:
            continue
        if str(record.get("credibility") or "").upper() != "CONFIRMED":
            continue
        evidence_day = parse_day(record.get("latest_evidence_date"))
        if evidence_day is None:
            continue
        age_days = (today - evidence_day).days
        if 0 <= age_days <= maximum_age_days:
            matches.append({
                "id": record.get("id"),
                "latest_evidence_date": record.get("latest_evidence_date"),
                "age_days": age_days,
                "status": record.get("status"),
                "credibility": record.get("credibility"),
            })
    return matches


def market_inputs(position):
    current = position.get("current") or {}
    averages = position.get("averages") or {}
    one_hour = averages.get("1h") or {}
    volume = position.get("volume") or {}
    one_hour_volume = volume.get("1h") or {}
    high_volume = one_hour.get("highPriceVolume")
    low_volume = one_hour.get("lowPriceVolume")
    if not isinstance(high_volume, (int, float)):
        high_volume = one_hour_volume.get("high")
    if not isinstance(low_volume, (int, float)):
        low_volume = one_hour_volume.get("low")
    total_volume = None
    if isinstance(high_volume, (int, float)) or isinstance(low_volume, (int, float)):
        total_volume = max(0, high_volume or 0) + max(0, low_volume or 0)
    if not valid_number(total_volume):
        total_volume = one_hour_volume.get("total")
    return {
        "high": current.get("high"),
        "low": current.get("low"),
        "high_age_seconds": current.get("highAgeSeconds"),
        "low_age_seconds": current.get("lowAgeSeconds"),
        "one_hour_high": one_hour.get("avgHighPrice"),
        "one_hour_low": one_hour.get("avgLowPrice"),
        "one_hour_high_volume": high_volume,
        "one_hour_low_volume": low_volume,
        "one_hour_total_volume": total_volume,
    }


def patient_reference_price(market):
    high = market.get("high")
    one_hour_high = market.get("one_hour_high")
    if valid_number(high) and valid_number(one_hour_high):
        return min(high, one_hour_high)
    return one_hour_high if valid_number(one_hour_high) else high


def data_gate(position, market, cfg):
    missing = []
    if not valid_number(position.get("quantity")):
        missing.append("quantity")
    if not valid_number(position.get("basis_each")):
        missing.append("basis_each")
    if not valid_number(position.get("basis_total")):
        missing.append("basis_total")
    for field in ("high", "low"):
        if not valid_number(market.get(field)):
            missing.append(f"current_{field}")
    if missing:
        return "INSUFFICIENT_DATA", missing
    crossed = market["high"] < market["low"]
    maximum_age = int(cfg.get("maximum_actionable_print_age_seconds") or 1800)
    ages = [market.get("high_age_seconds"), market.get("low_age_seconds")]
    if any(not isinstance(age, (int, float)) for age in ages):
        return "MISSING_PRINT_AGES", []
    if max(ages) > maximum_age:
        return "STALE_PRINTS", []
    if not valid_number(patient_reference_price(market)):
        return "MISSING_PATIENT_REFERENCE", []
    return ("ASYNC_CROSSED_PATIENT_ONLY" if crossed else "CLEAR"), []


def evaluate_position(position, policy, catalyst_state, cfg, tax_policy, now):
    item = position.get("item")
    market = market_inputs(position)
    gate, missing = data_gate(position, market, cfg)
    base = {
        "item": item,
        "item_id": position.get("item_id"),
        "status": "NO_ACTION",
        "action": "HOLD",
        "data_gate": gate,
    }
    if missing:
        base["missing"] = missing
    if gate not in {"CLEAR", "ASYNC_CROSSED_PATIENT_ONLY"}:
        base["reason"] = "Exit action withheld until fresh, usable RuneLite price and volume references are available."
        return base
    if policy.get("basis_recovery_completed") is True:
        base.update({
            "action": "HOLD_RUNNER",
            "reason": "The configured basis-recovery sale is already user-confirmed; do not repeatedly trim the runner.",
        })
        return base

    basis_each = float(position["basis_each"])
    quantity = int(position["quantity"])
    basis_total = float(position["basis_total"])
    patient_ref = patient_reference_price(market)
    immediate_ref = market["low"]
    patient_roi = after_tax_roi_pct(item, patient_ref, basis_each, tax_policy)
    immediate_roi = after_tax_roi_pct(item, immediate_ref, basis_each, tax_policy)
    one_hour_low_ref = market.get("one_hour_low")
    one_hour_low_roi = after_tax_roi_pct(item, one_hour_low_ref, basis_each, tax_policy)
    movement_24h = (position.get("movementPct") or {}).get("24h")
    movement_7d = (position.get("movementPct") or {}).get("7d")
    high_volume = market.get("one_hour_high_volume")
    total_volume = market.get("one_hour_total_volume")
    high_share = (
        max(0, high_volume) / total_volume
        if isinstance(high_volume, (int, float)) and valid_number(total_volume)
        else None
    )
    catalyst_matches = realized_catalysts(policy, catalyst_state, now)

    recover_cfg = cfg.get("recover_basis") or {}
    patient_trigger = float(policy.get("minimum_patient_after_tax_roi_pct", recover_cfg.get("minimum_patient_after_tax_roi_pct", 80)))
    immediate_trigger = float(policy.get("minimum_immediate_after_tax_roi_pct", recover_cfg.get("minimum_immediate_after_tax_roi_pct", 25)))
    momentum_trigger = float(policy.get("minimum_24h_gain_pct", recover_cfg.get("minimum_24h_gain_pct", 20)))
    weekly_trigger = float(policy.get("minimum_7d_gain_pct", recover_cfg.get("minimum_7d_gain_pct", 50)))
    preferred_share = float(policy.get(
        "preferred_high_side_share",
        policy.get(
            "minimum_high_side_share",
            recover_cfg.get("preferred_high_side_share", recover_cfg.get("minimum_high_side_share", 0.45)),
        ),
    ))
    minimum_volume = int(policy.get("minimum_one_hour_volume", recover_cfg.get("minimum_one_hour_volume", 20)))
    conservative_profit_cleared = (
        immediate_roi is not None and immediate_roi >= immediate_trigger
    ) or (
        one_hour_low_roi is not None and one_hour_low_roi >= immediate_trigger
    )
    momentum_cleared = (
        isinstance(movement_24h, (int, float)) and movement_24h >= momentum_trigger
    ) or (
        isinstance(movement_7d, (int, float)) and movement_7d >= weekly_trigger
    )
    buyer_flow_observed = isinstance(high_share, (int, float))
    buyer_flow_supportive = buyer_flow_observed and high_share >= preferred_share
    catalyst_trigger = (
        policy.get("mode") == "CATALYST_BASIS_RECOVERY"
        and bool(catalyst_matches)
        and patient_roi is not None and patient_roi >= patient_trigger
        and conservative_profit_cleared
        and momentum_cleared
        and valid_number(total_volume) and total_volume >= minimum_volume
        and buyer_flow_observed
    )

    extreme_cfg = cfg.get("extreme_profit_lock") or {}
    extreme_trigger = (
        bool(extreme_cfg.get("enabled", True))
        and patient_roi is not None
        and patient_roi >= float(extreme_cfg.get("minimum_patient_after_tax_roi_pct") or 150)
        and immediate_roi is not None
        and immediate_roi >= float(extreme_cfg.get("minimum_immediate_after_tax_roi_pct") or 50)
    )

    base["metrics"] = {
        "patient_reference_gp": int(patient_ref),
        "immediate_reference_gp": int(immediate_ref),
        "patient_after_tax_roi_pct": round(patient_roi, 2) if patient_roi is not None else None,
        "immediate_after_tax_roi_pct": round(immediate_roi, 2) if immediate_roi is not None else None,
        "one_hour_low_reference_gp": int(one_hour_low_ref) if valid_number(one_hour_low_ref) else None,
        "one_hour_low_after_tax_roi_pct": round(one_hour_low_roi, 2) if one_hour_low_roi is not None else None,
        "movement_24h_pct": movement_24h,
        "movement_7d_pct": movement_7d,
        "high_side_share_1h": round(high_share, 4) if isinstance(high_share, (int, float)) else None,
        "preferred_high_side_share_1h": preferred_share,
        "buyer_flow_supportive": buyer_flow_supportive,
        "one_hour_volume": int(total_volume) if valid_number(total_volume) else None,
    }
    if not (catalyst_trigger or extreme_trigger):
        return base

    runner_fraction = float(policy.get("runner_fraction", recover_cfg.get("default_runner_fraction", 0.5)))
    runner_fraction = max(0.1, min(0.9, runner_fraction))
    maximum_trim_fraction = float(policy.get("maximum_trim_fraction", recover_cfg.get("maximum_trim_fraction", 0.75)))
    maximum_trim_quantity = max(1, int(math.floor(quantity * maximum_trim_fraction)))
    planned_quantity = round_quantity_up(quantity * (1 - runner_fraction), quantity)
    planned_quantity = min(maximum_trim_quantity, max(1, planned_quantity))

    discount = float(policy.get("patient_limit_discount_pct", recover_cfg.get("patient_limit_discount_pct", 2.0)))
    limit_price = round_price_down(patient_ref * (1 - discount / 100))
    net_at_limit = net_unit_value(item, limit_price, tax_policy)
    required_quantity = math.ceil(basis_total / net_at_limit) if valid_number(net_at_limit) else quantity
    required_quantity = round_quantity_up(required_quantity, quantity)
    if required_quantity <= maximum_trim_quantity:
        planned_quantity = max(planned_quantity, required_quantity)
    planned_quantity = min(planned_quantity, maximum_trim_quantity, quantity)

    recovery_minimum = minimum_price_for_net_proceeds(item, planned_quantity, basis_total, tax_policy)
    if valid_number(recovery_minimum) and limit_price < recovery_minimum and recovery_minimum <= market["high"]:
        limit_price = recovery_minimum
        net_at_limit = net_unit_value(item, limit_price, tax_policy)

    net_proceeds = int(net_at_limit * planned_quantity)
    allocated_basis = int(round(basis_each * planned_quantity))
    locked_profit = net_proceeds - allocated_basis
    runner_quantity = quantity - planned_quantity
    basis_recovery_pct = net_proceeds / basis_total * 100 if basis_total else None
    liquidity = str(position.get("liquidity") or "UNKNOWN").upper()
    spread_pct = (market["high"] - market["low"]) / market["low"] * 100
    weak_buyer_flow = buyer_flow_observed and not buyer_flow_supportive
    thin_tape = (
        liquidity in {"THIN", "VERY THIN"}
        or spread_pct >= float(cfg.get("thin_spread_pct") or 8)
        or weak_buyer_flow
    )
    demand_volume = high_volume if valid_number(high_volume) else total_volume
    minimum_fill_hours = planned_quantity / demand_volume if valid_number(demand_volume) else None
    minimum_fill_hours = max(float(recover_cfg.get("minimum_patient_window_hours") or 4), minimum_fill_hours or 0)

    reason_codes = []
    if catalyst_trigger:
        reason_codes.extend(["CATALYST_REALIZED", "PROFIT_THRESHOLD_CLEARED", "RECOVER_ORIGINAL_BASIS"])
    if extreme_trigger:
        reason_codes.append("EXTREME_AFTER_TAX_GAIN")
    if str(policy.get("supply_elasticity") or "").upper() == "HIGH":
        reason_codes.append("HIGH_SUPPLY_ELASTICITY")
    if thin_tape:
        reason_codes.append("THIN_TAPE_PATIENT_EXECUTION")
    if weak_buyer_flow:
        reason_codes.append("WEAK_BUYER_FLOW_PATIENT_EXIT")
    if gate == "ASYNC_CROSSED_PATIENT_ONLY":
        reason_codes.append("ASYNC_PRINTS_USE_CONSERVATIVE_PATIENT_REFERENCE")
    if (
        catalyst_trigger
        and immediate_roi is not None and immediate_roi < immediate_trigger
        and one_hour_low_roi is not None and one_hour_low_roi >= immediate_trigger
    ):
        reason_codes.append("FLASH_LOW_PRINT_DOES_NOT_VETO_PATIENT_EXIT")

    basis_recovered = net_proceeds >= basis_total
    if planned_quantity == quantity:
        action = "EXIT_LOCK_PROFIT"
        recommended_rating = "EXIT / LOCK PROFIT"
    elif basis_recovered:
        action = "TRIM_RECOVER_BASIS"
        recommended_rating = "TRIM / RECOVER BASIS"
    else:
        action = "TRIM_LOCK_PROFIT"
        recommended_rating = "TRIM / LOCK PROFIT"
    if catalyst_trigger:
        outcome = (
            "Recover the original position basis while retaining a runner."
            if basis_recovered and runner_quantity > 0
            else "Lock available profit with the configured staged limit."
        )
        flow_note = (
            "Buyer flow is supportive."
            if buyer_flow_supportive
            else "Buyer flow is below the preferred threshold, so use patient staged execution instead of cancelling the exit."
        )
        reason = (
            "The configured catalyst has been realized and the position cleared after-tax profit, momentum, "
            f"and volume thresholds. {flow_note} {outcome}"
        )
    else:
        outcome = "while retaining a runner" if runner_quantity > 0 else "because the position cannot be split"
        reason = (
            f"The position cleared the extreme after-tax gain threshold. Lock profit with a staged limit {outcome}."
        )

    return {
        **base,
        "status": "ACTION_REQUIRED",
        "action": action,
        "recommended_rating": recommended_rating,
        "urgency": "PLACE_PATIENT_LIMIT_NOW",
        "sell_quantity": planned_quantity,
        "runner_quantity": runner_quantity,
        "recommended_limit_price_gp": int(limit_price),
        "minimum_basis_recovery_price_gp": int(recovery_minimum) if recovery_minimum is not None else None,
        "expected_net_proceeds_at_limit_gp": net_proceeds,
        "expected_locked_profit_at_limit_gp": locked_profit,
        "original_basis_recovered_pct": round(basis_recovery_pct, 1) if basis_recovery_pct is not None else None,
        "basis_recovered_if_filled": basis_recovered,
        "execution_style": "PATIENT_STAGED_LIMIT" if thin_tape else "PATIENT_LIMIT",
        "market_dump_prohibited": thin_tape,
        "estimated_minimum_fill_hours": round(minimum_fill_hours, 2),
        "reassess_after_hours": max(4, int(math.ceil(minimum_fill_hours))),
        "cancel_or_reprice_if": "Fresh patient reference remains below the limit through the reassessment window or prints become stale; never chase a falling bid.",
        "reason_codes": sorted(set(reason_codes)),
        "realized_catalysts": catalyst_matches,
        "metrics": {
            **base["metrics"],
            "current_high_gp": int(market["high"]),
            "current_low_gp": int(market["low"]),
            "current_spread_pct": round(spread_pct, 2),
            "position_to_one_hour_volume_multiple": round(quantity / total_volume, 2) if valid_number(total_volume) else None,
        },
        "reason": reason,
    }


def build_exit_engine(packet, cfg, lifecycle, now=None):
    now = int(now if now is not None else time.time())
    engine_cfg = cfg.get("portfolio_exit_engine") or {}
    enabled = bool(engine_cfg.get("enabled"))
    position_cfg = lifecycle.get("positions") or {}
    catalyst_state = packet.get("catalyst_state") or {}
    tax_policy = packet.get("tax_policy") or {}
    market_data_ready = (packet.get("quality") or {}).get("ready") is True
    actions = []
    data_gaps = []
    exempt_items = []
    evaluated = 0

    # Make repeated builds deterministic and never leave yesterday's dynamic sell
    # attached when current data no longer clears the engine's gates.
    for position in packet.get("portfolio") or []:
        static_rating = position.pop("static_rating_before_exit_engine", None)
        if static_rating is not None:
            position["rating"] = static_rating
        position.pop("exit_signal", None)

    if enabled and market_data_ready:
        for position in packet.get("portfolio") or []:
            meta = position_cfg.get(str(position.get("item_id"))) or {}
            if meta.get("hold_for_use") or (position.get("capital_aging") or {}).get("exempt"):
                exempt_items.append(position.get("item"))
                continue
            evaluated += 1
            signal = evaluate_position(
                position,
                meta.get("exit_policy") or {},
                catalyst_state,
                engine_cfg,
                tax_policy,
                now,
            )
            if signal.get("data_gate") == "INSUFFICIENT_DATA":
                data_gaps.append({"item": position.get("item"), "missing": signal.get("missing") or []})
            if signal.get("status") == "ACTION_REQUIRED":
                prior_rating = position.get("rating")
                position["static_rating_before_exit_engine"] = prior_rating
                position["rating"] = signal.get("recommended_rating")
                position["exit_signal"] = signal
                actions.append(signal)

    actions.sort(key=lambda row: (
        row.get("urgency") == "PLACE_PATIENT_LIMIT_NOW",
        (row.get("metrics") or {}).get("patient_after_tax_roi_pct") or 0,
        row.get("expected_locked_profit_at_limit_gp") or 0,
    ), reverse=True)
    summary = {
        "schema_version": 1,
        "generated_at": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
        "enabled": enabled,
        "rollout_status": engine_cfg.get("rollout_status") or "DISABLED",
        "recommendation_authoritative": bool(engine_cfg.get("recommendation_authoritative")),
        "market_data_ready": market_data_ready,
        "data_status": "READY" if market_data_ready else "LIVE RUNELITE DATA UNAVAILABLE",
        "action_required": bool(actions),
        "actionable_count": len(actions),
        "evaluated_positions": evaluated,
        "data_gap_positions": data_gaps,
        "hold_for_use_exempt_items": exempt_items,
        "priority_actions": actions[:10],
        "precedence_rule": (
            "ACTION_REQUIRED exit signals override static runtime HOLD ratings and must be reported before new GP deployment."
        ),
        "thin_tape_rule": (
            "Thin or asynchronous tape changes the execution method and sizing; it does not by itself cancel a validated profit-taking signal."
        ),
        "rule": engine_cfg.get("rule"),
    }
    packet["portfolio_exit_engine"] = summary

    profit = packet.get("profit_layer") or {}
    slots = profit.get("ge_slot_optimizer") or {}
    slots["recommended_exit_slot_priority"] = [{
        "item": row.get("item"),
        "action": row.get("action"),
        "sell_quantity": row.get("sell_quantity"),
        "recommended_limit_price_gp": row.get("recommended_limit_price_gp"),
        "execution_style": row.get("execution_style"),
    } for row in actions]
    slots["new_buy_orders_are_subordinate_to_exit_actions"] = bool(actions)
    profit["ge_slot_optimizer"] = slots
    profit["portfolio_exit_engine"] = summary
    packet["profit_layer"] = profit
    return summary


def main():
    packet = load_json(PACKET)
    if not packet:
        raise RuntimeError("desk_packet.json missing")
    cfg = load_json(CFG)
    lifecycle = load_json(LIFECYCLE)
    summary = build_exit_engine(packet, cfg, lifecycle)
    save_json(PACKET, packet)
    print(
        f"Portfolio exit engine: evaluated={summary['evaluated_positions']} "
        f"actionable={summary['actionable_count']} status={summary['rollout_status']}"
    )


if __name__ == "__main__":
    main()
