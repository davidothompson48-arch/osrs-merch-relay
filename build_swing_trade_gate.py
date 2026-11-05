#!/usr/bin/env python3
"""Risk-first long-horizon swing trade audit, NOT an automated order generator.

Reads only RuneLite-backed data from speculative_park_snapshot.json and an
OSRS Wiki-derived GE tax policy. Separates historical market observations from
hypothetical fills and exits. Cash/position availability is never inferred.
"""
import json
import math
import time
from datetime import datetime, timezone

SPEC = "speculative_park_snapshot.json"
TAX = "project/tax_policy.json"
LEDGER = "project/portfolio_ledger.json"
RADAR = "market_radar.json"
OUT = "swing_trade_gate.json"
PACKETS = ("desk_packet.json", "desk_packet_lite.json")


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if default is None else default


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))
        f.write("\n")


def tax(price, name, config):
    price = int(price)
    if price <= 0:
        return 0
    if name in set(config.get("exempt_items") or []):
        return 0
    rate = float(config.get("rate", 0.02))
    cap = int(config.get("cap_gp_per_item", 5000000))
    amount = math.floor(price * rate)
    return min(amount, cap) if cap > 0 else amount


def net_sale(exit_price, name, config):
    price = max(0, int(exit_price))
    return price - tax(price, name, config)


def minimum_exit(buy_price, name, tax_config, desired_net_roi_pct=0):
    """Exact lowest integer sell price meeting an after-tax ROI hurdle."""
    buy_price = int(buy_price)
    target = math.ceil(buy_price * (1 + float(desired_net_roi_pct) / 100))
    lo = 1
    hi = max(2, target * 2 + 1)
    while net_sale(hi, name, tax_config) < target:
        hi *= 2
    while lo < hi:
        mid = (lo + hi) // 2
        if net_sale(mid, name, tax_config) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def pnl_if_exit(entry, target_exit, name, tax_config):
    if not isinstance(target_exit, (int, float)) or target_exit <= 0:
        return None
    sale = int(round(target_exit))
    net = net_sale(sale, name, tax_config)
    return {
        "hypothetical_exit_gp": sale,
        "tax_gp": sale - net,
        "profit_gp": net - entry,
        "net_roi_pct": round((net / entry - 1) * 100, 3),
    }


def evaluate(candidate, tax_config, ledger_stale=True, snapshot_age_seconds=0, radar_status="UNKNOWN"):
    name = candidate.get("name")
    market = candidate.get("market") or {}
    entry = candidate.get("entry") or {}
    high = market.get("high")
    low = market.get("low")
    status = candidate.get("status") or "WATCH"
    freshness = market.get("freshness") or "INCOMPLETE"
    gate = candidate.get("execution_gate") or "UNKNOWN"
    errors = []
    if not all(isinstance(p, (int, float)) and 0 < p < 10**12 for p in (high, low)):
        errors.append("MISSING_QUOTES")
    elif high < low:
        errors.append("CROSSED_OR_ASYNCHRONOUS_QUOTES")
    if freshness not in ("FRESH", "USABLE"):
        errors.append("QUOTES_NOT_FRESH_ENOUGH")
    if isinstance(snapshot_age_seconds, (int, float)) and snapshot_age_seconds > 1800:
        errors.append("SNAPSHOT_OVER_30_MINUTES")
    if status not in ("PARK_NOW", "DEEP_BID"):
        errors.append("NOT_AN_ENTRY_CANDIDATE")
    if gate in ("REJECT_ASYNC_CROSSED_PRINTS", "WATCH_ONLY"):
        errors.append("SOURCE_GATE_BLOCKED")
    if radar_status != "READY":
        errors.append("RADAR_UNAVAILABLE_OR_STALE")

    result = {
        "item_id": candidate.get("item_id"),
        "name": name,
        "theme": candidate.get("theme"),
        "correlation_bucket": candidate.get("correlation_bucket"),
        "model_status": status,
        "source_execution_gate": gate,
        "freshness": freshness,
        "volume_24h_transactions_both_sides": market.get("twenty_four_hour_volume"),
        "hypothetical_immediate_buy_gp": int(high) if isinstance(high, (int, float)) and high > 0 else None,
        "observed_instant_sell_gp": int(low) if isinstance(low, (int, float)) and low > 0 else None,
        "preferred_patient_entry_gp": entry.get("ideal_gp"),
        "patient_entry_zone_ceiling_gp": entry.get("zone_high_gp"),
        "model_price_score": candidate.get("rank_score"),
        "reported_model_probability_pct": candidate.get("effective_catalyst_probability_pct"),
        "model_probability_is_subjective": True,
        "max_position_pct_of_liquid_gp": candidate.get("max_position_pct_of_liquid_gp"),
        "expected_horizon_days": candidate.get("expected_horizon_days"),
        "invalidation": candidate.get("invalidation"),
        "rejection_reasons": errors,
        "after_tax_scenarios": None,
        "execution_action": "WATCH_ONLY",
        "cash_sizing_authorized": False,
    }

    if not errors and isinstance(high, (int, float)):
        high = int(high)
        low = int(low)
        recommended_ceiling = entry.get("zone_high_gp")
        premium = (
            round(100 * (high / recommended_ceiling - 1), 2)
            if isinstance(recommended_ceiling, (int, float)) and recommended_ceiling > 0 else None
        )
        reference_mid = market.get("twenty_four_hour_mid")
        latest_high_exits = {
            "at_24h_reference_mid": pnl_if_exit(high, reference_mid, name, tax_config),
            "at_plus_10pct_gross_price": pnl_if_exit(high, high * 1.10, name, tax_config),
            "at_minus_10pct_gross_price": pnl_if_exit(high, high * .90, name, tax_config),
        }
        result["after_tax_scenarios"] = {
            "entry_basis": "Observed instant-buy HIGH transaction; fill at this price is not guaranteed",
            "breakeven_exit_gp": minimum_exit(high, name, tax_config, 0),
            "minimum_exit_for_5pct_net_gain_gp": minimum_exit(high, name, tax_config, 5),
            "minimum_exit_for_10pct_net_gain_gp": minimum_exit(high, name, tax_config, 10),
            "market_round_trip_friction_gp": high - low + tax(low, name, tax_config),
            "market_round_trip_friction_pct": round((high - low + tax(low, name, tax_config)) / high * 100, 3),
            "instant_buy_vs_patient_entry_ceiling_pct": premium,
            "hypothetical_outcomes": latest_high_exits,
        }
        reasons = []
        if not isinstance(recommended_ceiling, (int, float)) or recommended_ceiling <= 0:
            reasons.append("MISSING_PATIENT_ENTRY_REFERENCE")
        elif high > recommended_ceiling:
            reasons.append("INSTANT_BUY_ABOVE_PATIENT_ENTRY_CEILING")
        if market.get("twenty_four_hour_volume", 0) < 150:
            reasons.append("LOW_24H_TRANSACTION_COUNT")
        if result["after_tax_scenarios"]["market_round_trip_friction_pct"] > 4:
            reasons.append("HIGH_AFTER_TAX_ROUND_TRIP_FRICTION")
        if ledger_stale:
            reasons.append("HOLDINGS_AND_CASH_UNRECONCILED")
        result["rejection_reasons"].extend(reasons)
        result["execution_action"] = (
            "RESEARCH_ONLY_NO_CASH_AUTHORITY"
            if not reasons else "WAIT_OR_RESEARCH_ONLY"
        )
    return result


def main():
    snapshot = read_json(SPEC)
    cfg = read_json(TAX)
    ledger = read_json(LEDGER)
    radar = read_json(RADAR)
    if not snapshot.get("all_candidates"):
        raise RuntimeError("Missing speculative snapshot candidates; cannot fabricate trade analysis")
    if not isinstance(cfg.get("rate"), (int, float)):
        raise RuntimeError("Missing explicit GE tax configuration")
    ts = snapshot.get("generated_unix")
    age = max(0, int(time.time()) - ts) if isinstance(ts, int) else None
    acct = ledger.get("account_context") or {}
    stale = (
        acct.get("reconciliation_required") is not False
        or not isinstance(acct.get("current_liquid_gp"), int)
        or acct.get("current_liquid_gp", 0) <= 0
    )
    radar_status = radar.get("status", "UNKNOWN")
    rows = [
        evaluate(x, cfg, ledger_stale=stale, snapshot_age_seconds=age, radar_status=radar_status)
        for x in snapshot["all_candidates"]
    ]
    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "OSRS Wiki RuneLite-derived GitHub relay; official GE tax config",
        "status": "READY" if isinstance(age, int) and age <= 1800 and radar_status == "READY" else "STALE_OR_PARTIAL",
        "snapshot_age_seconds": age,
        "portfolio_reconciliation_required": stale,
        "cash_sizing_authorized": False,
        "buy_orders_placed": 0,
        "advisory_only": True,
        "entries": rows,
        "decision_rules": [
            "HIGH is a historical instant-buy transaction and LOW is a historical instant-sell transaction; neither is a standing quote.",
            "All displayed exit prices are hypotheticals calculated from an instant-buy reference, not forecasts or limit orders.",
            "A modeled patient bid is not a guaranteed fill; this report never authorizes buying above the planned entry ceiling.",
            "No realized P&L, buy quantity or GP allocation can be inferred until the user confirms current cash and holdings.",
            "Reject crossed, stale, crowded and low-liquidity examples before considering order placement.",
        ],
    }
    write_json(OUT, result)
    for path in PACKETS:
        try:
            packet = read_json(path)
            if not packet:
                continue
            packet["swing_trade_gate"] = {
                "status": result["status"],
                "generated_at": result["generated_at"],
                "portfolio_reconciliation_required": stale,
                "cash_sizing_authorized": False,
                "entries": rows[:8],
                "full_report": OUT,
                "advisory_only": True,
            }
            write_json(path, packet)
        except (OSError, ValueError):
            # Auxiliary injection must not obscure the produced standalone report.
            continue
    print(f"Swing-trade gate: {result['status']}; evaluated={len(rows)}; buy_orders=0")


if __name__ == "__main__":
    main()
