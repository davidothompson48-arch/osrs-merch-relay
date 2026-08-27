#!/usr/bin/env python3
import glob
import json
import math
import os
import time
from datetime import datetime, timezone

OUT = "desk_packet.json"


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def age_seconds(payload, now):
    ts = payload.get("generated_unix") if isinstance(payload, dict) else None
    return now - ts if isinstance(ts, int) else None


def compact_current(row):
    cur = row.get("current") or {}
    return {
        "high": cur.get("high"), "low": cur.get("low"),
        "highTime": cur.get("highTime"), "lowTime": cur.get("lowTime"),
        "highAgeSeconds": cur.get("highAgeSeconds"), "lowAgeSeconds": cur.get("lowAgeSeconds")
    }


def normalize_universe(row):
    if not isinstance(row, dict):
        return {}
    return {
        "id": row.get("id"), "name": row.get("name"), "buy_limit": row.get("buyLimit"),
        "current": compact_current(row),
        "averages": {"5m": row.get("5m") or {}, "1h": row.get("1h") or {}, "24h": row.get("24h") or {}},
        "movementPct": {}, "volume": {}, "liquidity": None,
        "source_block": "market_universe"
    }


def normalize_related(row, groups):
    if not isinstance(row, dict):
        return {}
    return {
        "id": row.get("id"), "name": row.get("name"), "buy_limit": row.get("buyLimit"),
        "current": compact_current(row),
        "averages": {"1h": row.get("oneHour") or {}, "24h": row.get("twentyFourHour") or {}},
        "movementPct": {}, "volume": {}, "liquidity": None,
        "related_groups": sorted(groups), "source_block": "related_watch"
    }


def normalize_snapshot(row):
    if not isinstance(row, dict):
        return {}
    return {
        "id": row.get("id"), "name": row.get("name"), "buy_limit": row.get("buy_limit"),
        "current": row.get("current") or {}, "averages": row.get("averages") or {},
        "movementPct": row.get("movementPct") or {}, "volume": row.get("volume") or {},
        "liquidity": row.get("liquidity"), "history_complete": row.get("history_complete"),
        "source_block": "snapshot"
    }


def market_mid(row, side_pair=("high", "low")):
    cur = row.get("current") or {}
    vals = [cur.get(k) for k in side_pair]
    vals = [x for x in vals if isinstance(x, (int, float)) and x > 0]
    return sum(vals) / len(vals) if vals else None


def avg_mid(row):
    if not isinstance(row, dict):
        return None
    vals = [row.get("avgHighPrice"), row.get("avgLowPrice")]
    vals = [x for x in vals if isinstance(x, (int, float)) and x > 0]
    return sum(vals) / len(vals) if vals else None


def tax_for(name, price, tax_policy):
    if not isinstance(price, (int, float)) or price <= 0:
        return None
    if name in set(tax_policy.get("exempt_items") or []):
        return 0
    rate = float(tax_policy.get("rate") or 0)
    cap = int(tax_policy.get("cap_gp_per_item") or 0)
    value = math.floor(price * rate)
    return min(value, cap) if cap > 0 else value


def freshness_quality(row):
    cur = row.get("current") or {}
    ages = [cur.get("highAgeSeconds"), cur.get("lowAgeSeconds")]
    ages = [x for x in ages if isinstance(x, (int, float))]
    if len(ages) < 2:
        return "INCOMPLETE"
    worst = max(ages)
    if worst <= 300:
        return "FRESH"
    if worst <= 1800:
        return "USABLE"
    if worst <= 7200:
        return "STALEISH"
    return "STALE"


def conversion_market_row(name, by_name):
    return by_name.get(name) or {}


def calc_conversion(conv, by_name, tax_policy):
    inputs = conv.get("inputs")
    if not inputs:
        inputs = [{"item": conv.get("input"), "quantity": conv.get("input_quantity", 1)}]
    output_name = conv.get("output")
    output_qty = conv.get("output_quantity", 1)
    if not output_name:
        return None

    input_rows = []
    for x in inputs:
        row = conversion_market_row(x.get("item"), by_name)
        if not row:
            return None
        input_rows.append((x, row))
    output_row = conversion_market_row(output_name, by_name)
    if not output_row:
        return None

    immediate_cost = 0
    patient_cost = 0
    freshness = []
    for x, row in input_rows:
        cur = row.get("current") or {}
        qty = x.get("quantity", 1)
        high, low = cur.get("high"), cur.get("low")
        if not isinstance(high, (int, float)) or not isinstance(low, (int, float)):
            return None
        immediate_cost += high * qty
        patient_cost += low * qty
        freshness.append(freshness_quality(row))

    out_cur = output_row.get("current") or {}
    out_high, out_low = out_cur.get("high"), out_cur.get("low")
    if not isinstance(out_high, (int, float)) or not isinstance(out_low, (int, float)):
        return None
    immediate_tax = tax_for(output_name, out_low, tax_policy)
    patient_tax = tax_for(output_name, out_high, tax_policy)
    immediate_net = (out_low - immediate_tax) * output_qty if immediate_tax is not None else None
    patient_net = (out_high - patient_tax) * output_qty if patient_tax is not None else None
    if immediate_net is None or patient_net is None:
        return None
    immediate_profit = immediate_net - immediate_cost
    patient_profit = patient_net - patient_cost
    freshness.append(freshness_quality(output_row))

    return {
        "type": conv.get("type"), "inputs": inputs, "output": output_name, "output_quantity": output_qty,
        "immediate": {
            "input_cost": immediate_cost, "net_output_value": immediate_net, "profit_gp": immediate_profit,
            "roi_pct": round(immediate_profit / immediate_cost * 100, 3) if immediate_cost else None
        },
        "patient": {
            "input_cost": patient_cost, "net_output_value": patient_net, "profit_gp": patient_profit,
            "roi_pct": round(patient_profit / patient_cost * 100, 3) if patient_cost else None
        },
        "freshness": freshness,
        "mechanics_source": conv.get("source")
    }


def main():
    now = int(time.time())
    snapshot = load_json("snapshot.json")
    related = load_json("related_watch.json")
    staples = load_json("staples_watch.json")
    portfolio_history = load_json("portfolio_history.json")
    ledger = load_json("project/portfolio_ledger.json")
    runtime = load_json("project/desk_runtime_state.json")
    conversions_cfg = load_json("project/known_conversions.json")
    tax_policy = load_json("project/tax_policy.json")

    by_id = {}
    by_name = {}

    # Local shard reads are cheap and replace many remote per-item fetches during a desk run.
    universe_generated = None
    for path in glob.glob("market_universe/*.json"):
        if path.endswith("index.json"):
            continue
        payload = load_json(path)
        if universe_generated is None:
            universe_generated = payload.get("generated_unix")
        for row in payload.get("items", []):
            norm = normalize_universe(row)
            if norm.get("id") is not None:
                by_id[str(norm["id"])] = norm
            if norm.get("name"):
                by_name[norm["name"]] = norm

    related_groups_by_id = {}
    related_rows = {}
    for group, rows in (related.get("groups") or {}).items():
        for row in rows:
            key = str(row.get("id"))
            related_groups_by_id.setdefault(key, set()).add(group)
            related_rows[key] = row
    for key, row in related_rows.items():
        norm = normalize_related(row, related_groups_by_id.get(key, set()))
        by_id[key] = {**by_id.get(key, {}), **norm}
        if norm.get("name"):
            by_name[norm["name"]] = by_id[key]

    for key, row in (snapshot.get("portfolio") or {}).items():
        norm = normalize_snapshot(row)
        by_id[str(key)] = {**by_id.get(str(key), {}), **norm}
        if norm.get("name"):
            by_name[norm["name"]] = by_id[str(key)]

    history_positions = portfolio_history.get("positions") or {}
    ratings = runtime.get("portfolio_ratings") or {}
    portfolio_rows = []
    gross_basis_total = 0
    gross_mark_high_total = 0
    modeled_after_tax_high_total = 0
    basis_mark_count = 0

    for pos in ledger.get("active_positions", []):
        item_id = pos.get("item_id")
        market = by_id.get(str(item_id), {})
        hist = history_positions.get(str(item_id)) or {}
        movement = dict(market.get("movementPct") or {})
        movement.update({k: v for k, v in (hist.get("movementPct") or {}).items() if v is not None})
        volume = dict(market.get("volume") or {})
        if hist.get("volume"):
            volume.update(hist["volume"])
        cur = market.get("current") or {}
        high, low = cur.get("high"), cur.get("low")
        qty = pos.get("quantity")
        basis_each = pos.get("cost_basis_gp_each")
        basis_total = pos.get("cost_basis_gp_total_approx")
        gross_high = high * qty if isinstance(high, (int, float)) and isinstance(qty, (int, float)) else None
        gross_low = low * qty if isinstance(low, (int, float)) and isinstance(qty, (int, float)) else None
        tax_each_high = tax_for(market.get("name") or pos.get("item"), high, tax_policy)
        after_tax_high = (high - tax_each_high) * qty if gross_high is not None and tax_each_high is not None else None
        gross_pnl_high = gross_high - basis_total if gross_high is not None and isinstance(basis_total, (int, float)) else None
        after_tax_pnl_high = after_tax_high - basis_total if after_tax_high is not None and isinstance(basis_total, (int, float)) else None
        if isinstance(basis_total, (int, float)):
            gross_basis_total += basis_total
        if gross_high is not None and isinstance(basis_total, (int, float)):
            gross_mark_high_total += gross_high
            basis_mark_count += 1
        if after_tax_high is not None and isinstance(basis_total, (int, float)):
            modeled_after_tax_high_total += after_tax_high

        portfolio_rows.append({
            "item": pos.get("item"), "item_id": item_id, "quantity": qty,
            "basis_each": basis_each, "basis_total": basis_total,
            "current": cur, "freshness": freshness_quality(market),
            "averages": market.get("averages") or {}, "movementPct": movement, "volume": volume,
            "liquidity": market.get("liquidity"), "buy_limit": market.get("buy_limit"),
            "gross_mark_high": gross_high, "gross_mark_low": gross_low,
            "gross_pnl_high": gross_pnl_high, "modeled_after_tax_pnl_high": after_tax_pnl_high,
            "rating": ratings.get(pos.get("item")) or ratings.get(market.get("name")),
            "note": pos.get("note"), "adversarial_note": pos.get("adversarial_note"),
            "market_source_block": market.get("source_block"), "history_complete": hist.get("history_complete") or market.get("history_complete")
        })

    open_offers = []
    for offer in ledger.get("open_offers_unconfirmed", []):
        market = by_id.get(str(offer.get("item_id")), {})
        open_offers.append({**offer, "market": {"current": market.get("current"), "movementPct": market.get("movementPct"),
                                               "freshness": freshness_quality(market)}})

    conversion_rows = []
    for conv in conversions_cfg.get("conversions", []):
        row = calc_conversion(conv, by_name, tax_policy)
        if row:
            conversion_rows.append(row)
    conversion_rows.sort(key=lambda x: max(x["immediate"].get("roi_pct") or -999, x["patient"].get("roi_pct") or -999), reverse=True)

    market_scan = snapshot.get("market_scan") or {}
    fast_candidates = (market_scan.get("top_after_tax_spread_candidates") or [])[:15]
    momentum = (market_scan.get("short_term_momentum") or [])[:10]
    oversold = (market_scan.get("oversold_candidates") or [])[:10]
    extreme_flow = (market_scan.get("extreme_one_hour_order_flow") or [])[:10]
    staple_candidates = (staples.get("top_candidates") or [])[:12]

    # Keep a compact sector block for attribution checks without forcing a second repo read.
    sector_rows = {}
    for group, rows in (related.get("groups") or {}).items():
        sector_rows[group] = [{
            "id": x.get("id"), "name": x.get("name"), "current": x.get("current"),
            "oneHour": x.get("oneHour"), "twentyFourHour": x.get("twentyFourHour")
        } for x in rows]

    core_age = age_seconds(snapshot, now)
    related_age = age_seconds(related, now)
    staples_age = age_seconds(staples, now)
    history_age = age_seconds(portfolio_history, now)
    universe_age = now - universe_generated if isinstance(universe_generated, int) else None
    ready = isinstance(core_age, int) and core_age <= 900

    output = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_unix": now,
        "source": "prices.runescape.wiki OSRS RuneLite real-time API via repository relay",
        "purpose": "Single-read fast-path packet for the OSRS Merch Desk. Fetch deeper repo files only when a packet field is missing or a candidate needs special validation.",
        "quality": {
            "ready": ready, "core_age_seconds": core_age, "related_age_seconds": related_age,
            "staples_age_seconds": staples_age, "portfolio_history_age_seconds": history_age,
            "universe_age_seconds": universe_age,
            "staples_available": bool(staples.get("all_staples")),
            "portfolio_history_available": bool(history_positions)
        },
        "tax_policy": tax_policy,
        "portfolio": portfolio_rows,
        "portfolio_summary": {
            "known_basis_gp": gross_basis_total,
            "gross_mark_high_gp": gross_mark_high_total,
            "gross_pnl_high_gp": gross_mark_high_total - gross_basis_total if basis_mark_count else None,
            "modeled_after_tax_mark_high_gp": modeled_after_tax_high_total,
            "modeled_after_tax_pnl_high_gp": modeled_after_tax_high_total - gross_basis_total if basis_mark_count else None,
            "risk_buckets_pct_known_merch_basis": runtime.get("risk_buckets_pct_known_merch_basis") or {}
        },
        "open_offers_unconfirmed": open_offers,
        "engines": {
            "fast_flip_screen": fast_candidates,
            "short_term_momentum": momentum,
            "broad_oversold_screen": oversold,
            "extreme_flow_screen": extreme_flow,
            "evergreen_staples": {"generated_at": staples.get("generated_at"), "candidate_count": staples.get("candidate_count"), "top_candidates": staple_candidates},
            "conversions": conversion_rows
        },
        "sectors": sector_rows,
        "previous_runtime": {
            "last_successful_run_utc": runtime.get("last_successful_run_utc"),
            "top_deployment_board": runtime.get("top_deployment_board") or [],
            "material_change_flags": runtime.get("material_change_flags") or [],
            "active_trade_recommendations": runtime.get("active_trade_recommendations") or [],
            "pre_catalyst_radar": runtime.get("pre_catalyst_radar") or []
        },
        "fast_path_rules": {
            "first_read": "desk_packet.json only",
            "deep_fetch_only_if": ["packet stale or incomplete", "specific recommended candidate requires missing history", "new catalyst changes probability model", "user asks for deep dive on one item"],
            "news_policy": "Use one grouped catalyst web sweep, not many sequential searches; skip repeated background research when no new material catalyst appears.",
            "output_policy": "Delta-first. Do not rewrite unchanged thesis prose."
        }
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, separators=(",", ":"))
        f.write("\n")
    print(f"Wrote {OUT}; ready={ready}; portfolio={len(portfolio_rows)}; staple_candidates={len(staple_candidates)}; conversions={len(conversion_rows)}")


if __name__ == "__main__":
    main()
