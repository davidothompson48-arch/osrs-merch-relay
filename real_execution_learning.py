#!/usr/bin/env python3
import csv
import json
import math
import time
from datetime import datetime, timezone

LEDGER = "project/execution_ledger.json"
TRADE_JOURNAL = "project/trade_journal.csv"
CFG = "project/profit_engine.json"
TAX = "project/tax_policy.json"
OUT = "real_execution_summary.json"


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")


def empirical_fill_stats(orders, side, horizons_minutes, now):
    rows = [x for x in orders if str(x.get("side", "")).lower() == side and parse_iso(x.get("placed_at_utc")) is not None]
    fill_minutes = []
    price_improvement_bps = []
    for row in rows:
        placed = parse_iso(row.get("placed_at_utc"))
        filled = parse_iso(row.get("filled_at_utc"))
        if placed is not None and filled is not None and filled >= placed:
            fill_minutes.append((filled - placed) / 60.0)
        limit_price = row.get("limit_price_gp_each")
        fill_price = row.get("avg_fill_price_gp_each")
        if isinstance(limit_price, (int, float)) and limit_price > 0 and isinstance(fill_price, (int, float)) and fill_price > 0:
            if side == "buy":
                improvement = (limit_price - fill_price) / limit_price * 10000
            else:
                improvement = (fill_price - limit_price) / limit_price * 10000
            price_improvement_bps.append(improvement)

    probabilities = {}
    samples = {}
    successes = {}
    for horizon in horizons_minutes:
        eligible = 0
        success = 0
        cutoff_seconds = float(horizon) * 60.0
        for row in rows:
            placed = parse_iso(row.get("placed_at_utc"))
            filled = parse_iso(row.get("filled_at_utc"))
            cancelled = parse_iso(row.get("cancelled_at_utc"))
            if placed is None:
                continue
            if filled is not None and filled >= placed and (filled - placed) <= cutoff_seconds:
                eligible += 1
                success += 1
                continue
            observed_end = filled or cancelled
            if observed_end is None and str(row.get("status", "")).upper() in ("OPEN", "PLACED", "PARTIAL"):
                observed_end = now
            if observed_end is not None and observed_end >= placed and (observed_end - placed) >= cutoff_seconds:
                eligible += 1
        key = str(int(horizon))
        samples[key] = eligible
        successes[key] = success
        probabilities[key] = round(success / eligible, 4) if eligible else None

    fill_minutes_sorted = sorted(fill_minutes)
    median_fill = None
    if fill_minutes_sorted:
        n = len(fill_minutes_sorted)
        mid = n // 2
        median_fill = fill_minutes_sorted[mid] if n % 2 else (fill_minutes_sorted[mid - 1] + fill_minutes_sorted[mid]) / 2

    avg_improvement = sum(price_improvement_bps) / len(price_improvement_bps) if price_improvement_bps else None
    return {
        "orders_with_placed_timestamp": len(rows),
        "timed_fills": len(fill_minutes),
        "fill_probability_by_horizon": probabilities,
        "sample_n_by_horizon": samples,
        "success_n_by_horizon": successes,
        "median_fill_minutes": round(median_fill, 2) if median_fill is not None else None,
        "average_price_improvement_bps": round(avg_improvement, 2) if avg_improvement is not None else None,
    }


def tax_for(price, tax_policy):
    if not isinstance(price, (int, float)) or price <= 0:
        return 0
    rate = float(tax_policy.get("rate") or 0.02)
    cap = int(tax_policy.get("cap_gp_per_item") or 5000000)
    value = math.floor(price * rate)
    return min(value, cap) if cap > 0 else value


def round_trip_stats(round_trips, order_map, tax_policy):
    realized = []
    for row in round_trips:
        entry = order_map.get(row.get("entry_order_id"))
        exit_order = order_map.get(row.get("exit_order_id"))
        if not entry or not exit_order:
            continue
        buy = entry.get("avg_fill_price_gp_each")
        sell = exit_order.get("avg_fill_price_gp_each")
        qty = row.get("quantity") or min(entry.get("filled_quantity") or 0, exit_order.get("filled_quantity") or 0)
        if not all(isinstance(v, (int, float)) and v > 0 for v in (buy, sell, qty)):
            continue
        tax = tax_for(sell, tax_policy)
        net_each = sell - tax - buy
        profit = net_each * qty
        entry_fill = parse_iso(entry.get("filled_at_utc"))
        exit_fill = parse_iso(exit_order.get("filled_at_utc"))
        cycle_hours = None
        if entry_fill is not None and exit_fill is not None and exit_fill >= entry_fill:
            cycle_hours = (exit_fill - entry_fill) / 3600.0
        realized.append({
            "item": entry.get("item"),
            "engine": entry.get("engine"),
            "quantity": qty,
            "buy_gp_each": buy,
            "sell_gp_each": sell,
            "net_profit_gp": int(profit),
            "cycle_hours": round(cycle_hours, 3) if cycle_hours is not None else None,
            "realized_gp_per_hour": int(profit / cycle_hours) if cycle_hours and cycle_hours > 0 else None,
        })
    gp = sum(x["net_profit_gp"] for x in realized)
    timed = [x for x in realized if isinstance(x.get("realized_gp_per_hour"), int)]
    return {
        "completed_round_trips": len(realized),
        "realized_net_profit_gp": int(gp),
        "timed_round_trips": len(timed),
        "average_realized_gp_per_hour": int(sum(x["realized_gp_per_hour"] for x in timed) / len(timed)) if timed else None,
        "recent": realized[-20:],
    }


def legacy_journal_count():
    try:
        with open(TRADE_JOURNAL, "r", encoding="utf-8", newline="") as f:
            return sum(1 for _ in csv.DictReader(f))
    except Exception:
        return 0


def group_summary(orders, horizons, now):
    return {
        "orders_total": len(orders),
        "confirmed_source_orders": sum(1 for x in orders if str(x.get("source", "")).lower() == "user_confirmed"),
        "entry": empirical_fill_stats(orders, "buy", horizons, now),
        "exit": empirical_fill_stats(orders, "sell", horizons, now),
    }


def main():
    now = time.time()
    ledger = load_json(LEDGER, {"orders": [], "round_trips": []})
    cfg = load_json(CFG)
    tax_policy = load_json(TAX)
    learn_cfg = cfg.get("real_execution_learning") or {}
    horizons = learn_cfg.get("horizons_minutes") or [5, 15, 60, 120, 240]
    horizons = sorted({int(x) for x in horizons if isinstance(x, (int, float)) and x > 0})
    orders = ledger.get("orders") or []
    order_map = {x.get("order_id"): x for x in orders if x.get("order_id")}

    by_item = {}
    for item in sorted({x.get("item") for x in orders if x.get("item")}):
        by_item[item] = group_summary([x for x in orders if x.get("item") == item], horizons, now)

    by_engine = {}
    for engine in sorted({x.get("engine") or "UNKNOWN" for x in orders}):
        by_engine[engine] = group_summary([x for x in orders if (x.get("engine") or "UNKNOWN") == engine], horizons, now)

    summary = {
        "schema_version": 1,
        "generated_at": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
        "horizons_minutes": horizons,
        "orders_total": len(orders),
        "timed_orders_total": sum(1 for x in orders if parse_iso(x.get("placed_at_utc")) is not None),
        "user_confirmed_orders_total": sum(1 for x in orders if str(x.get("source", "")).lower() == "user_confirmed"),
        "legacy_trade_journal_records": legacy_journal_count(),
        "by_item": by_item,
        "by_engine": by_engine,
        "round_trips": round_trip_stats(ledger.get("round_trips") or [], order_map, tax_policy),
        "minimum_samples_before_item_blend": int(learn_cfg.get("item_min_samples_before_blend") or 8),
        "minimum_samples_before_engine_blend": int(learn_cfg.get("engine_min_samples_before_blend") or 20),
        "rule": "Real user-confirmed orders outrank shadow observations. Fill-time curves use only orders with known placement timestamps and only horizons with enough observation time; unknown timestamps never become negative samples.",
    }
    save_json(OUT, summary)
    print(f"Real execution learning: orders={len(orders)} timed={summary['timed_orders_total']} round_trips={summary['round_trips']['completed_round_trips']}")


if __name__ == "__main__":
    main()
