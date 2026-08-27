#!/usr/bin/env python3
import glob
import json
import math
import os
import time
from datetime import datetime, timezone

PACKET = "desk_packet.json"
BOOK = "shadow_book.json"
SUMMARY = "shadow_book_summary.json"
CONFIG = "project/profit_engine.json"


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


def utc_iso(ts=None):
    if ts is None:
        ts = time.time()
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def midpoint(high, low):
    vals = [x for x in (high, low) if isinstance(x, (int, float)) and x > 0]
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


def by_id_market():
    out = {}
    for path in glob.glob("market_universe/*.json"):
        if path.endswith("index.json"):
            continue
        payload = load_json(path)
        for row in payload.get("items", []):
            item_id = row.get("id")
            if item_id is not None:
                out[str(item_id)] = row
    snap = load_json("snapshot.json")
    for key, row in (snap.get("portfolio") or {}).items():
        cur = row.get("current") or {}
        one = (row.get("averages") or {}).get("1h") or {}
        day = (row.get("averages") or {}).get("24h") or {}
        out[str(key)] = {"id": row.get("id"), "name": row.get("name"), "current": cur, "1h": one, "24h": day}
    return out


def current_metrics(item_id, market, tax_policy, name=None):
    row = market.get(str(item_id)) or {}
    cur = row.get("current") or {}
    high, low = cur.get("high"), cur.get("low")
    mid = midpoint(high, low)
    resolved_name = row.get("name") or name
    tax = tax_for(resolved_name, high, tax_policy) if high else None
    return {"high": high, "low": low, "mid": mid, "net_high": (high - tax) if isinstance(high, (int, float)) and tax is not None else None}


def recent_duplicate(signals, key, now, cooldown_hours):
    cutoff = now - int(cooldown_hours * 3600)
    for s in reversed(signals[-300:]):
        if s.get("key") == key and int(s.get("created_unix") or 0) >= cutoff:
            return True
    return False


def add_signal(signals, signal, now, cooldown_hours):
    if recent_duplicate(signals, signal["key"], now, cooldown_hours):
        return False
    signal["id"] = f"{signal['engine']}:{signal['key']}:{now}"
    signal["created_unix"] = now
    signal["created_at"] = utc_iso(now)
    signal["checkpoints"] = {}
    signal["shadow_only"] = True
    signals.append(signal)
    return True


def bucket_share(value):
    if not isinstance(value, (int, float)):
        return "NA"
    if value < 0.35:
        return "<35"
    if value < 0.50:
        return "35-50"
    if value < 0.65:
        return "50-65"
    if value < 0.80:
        return "65-80"
    return "80+"


def bucket_roi(value):
    if not isinstance(value, (int, float)):
        return "NA"
    if value < 1:
        return "<1"
    if value < 2:
        return "1-2"
    if value < 4:
        return "2-4"
    if value < 8:
        return "4-8"
    return "8+"


def grade_signals(signals, packet, market, cfg, now):
    tax_policy = packet.get("tax_policy") or {}
    checkpoints = cfg.get("shadow_learning", {}).get("checkpoints_hours") or [1, 4, 24, 72, 168]
    conversions = {}
    for row in ((packet.get("engines") or {}).get("conversions") or []):
        inputs = row.get("inputs") or []
        key = "+".join(f"{x.get('quantity',1)}x{x.get('item')}" for x in inputs) + f"->{row.get('output')}"
        conversions[key] = row

    for s in signals:
        created = int(s.get("created_unix") or 0)
        if not created:
            continue
        cp = s.setdefault("checkpoints", {})
        for hours in checkpoints:
            label = f"{hours}h"
            if label in cp or now < created + int(hours * 3600):
                continue
            if s.get("engine") == "conversion":
                row = conversions.get(s.get("strategy_key"))
                if not row:
                    continue
                patient = row.get("patient") or {}
                cp[label] = {
                    "observed_at": utc_iso(now),
                    "patient_roi_pct": patient.get("roi_pct"),
                    "margin_change_pct_points": round((patient.get("roi_pct") or 0) - (s.get("initial_patient_roi_pct") or 0), 3) if patient.get("roi_pct") is not None and s.get("initial_patient_roi_pct") is not None else None
                }
                continue
            item_id = s.get("item_id")
            m = current_metrics(item_id, market, tax_policy, s.get("item"))
            if m.get("mid") is None:
                continue
            initial_mid = s.get("signal_mid")
            entry_low = s.get("entry_low")
            market_move = round((m["mid"] / initial_mid - 1) * 100, 3) if isinstance(initial_mid, (int, float)) and initial_mid > 0 else None
            exec_ret = round((m["net_high"] / entry_low - 1) * 100, 3) if isinstance(entry_low, (int, float)) and entry_low > 0 and isinstance(m.get("net_high"), (int, float)) else None
            direction = s.get("direction", "LONG")
            directional_move = market_move if direction == "LONG" else (-market_move if market_move is not None else None)
            cp[label] = {"observed_at": utc_iso(now), "high": m.get("high"), "low": m.get("low"), "mid": m.get("mid"), "market_move_pct": market_move, "directional_move_pct": directional_move, "shadow_execution_return_pct": exec_ret}


def summarize(signals, cfg, now):
    rows = []
    for s in signals:
        for label, cp in (s.get("checkpoints") or {}).items():
            if s.get("engine") == "conversion":
                value = cp.get("patient_roi_pct")
                success = value is not None and value > 0
            else:
                value = cp.get("directional_move_pct")
                success = value is not None and value > 0
            if value is None:
                continue
            rows.append({"engine": s.get("engine"), "checkpoint": label, "value": value, "success": success, "liquidity": s.get("features", {}).get("liquidity") or "NA", "high_share_bucket": bucket_share(s.get("features", {}).get("high_side_share")), "roi_bucket": bucket_roi(s.get("features", {}).get("initial_roi_pct"))})

    def group_stats(filter_fn):
        vals = [r for r in rows if filter_fn(r)]
        if not vals:
            return {"n": 0}
        numbers = [r["value"] for r in vals]
        return {"n": len(vals), "hit_rate_pct": round(100 * sum(1 for r in vals if r["success"]) / len(vals), 1), "avg_directional_or_margin_pct": round(sum(numbers) / len(numbers), 3), "median_directional_or_margin_pct": round(sorted(numbers)[len(numbers)//2], 3)}

    by_engine = {}
    for engine in sorted(set(r["engine"] for r in rows)):
        by_engine[engine] = {}
        for checkpoint in ("1h", "4h", "24h", "72h", "168h"):
            by_engine[engine][checkpoint] = group_stats(lambda r, e=engine, c=checkpoint: r["engine"] == e and r["checkpoint"] == c)

    features = {}
    for checkpoint in ("4h", "24h"):
        for field in ("high_share_bucket", "roi_bucket", "liquidity"):
            values = sorted(set(r[field] for r in rows if r["checkpoint"] == checkpoint))
            features[f"{checkpoint}:{field}"] = {value: group_stats(lambda r, c=checkpoint, f=field, v=value: r["checkpoint"] == c and r[f] == v) for value in values}

    minimum = int(cfg.get("shadow_learning", {}).get("minimum_samples_before_score_adjustment") or 20)
    max_adj = int(cfg.get("shadow_learning", {}).get("maximum_learning_adjustment_points") or 8)
    adjustments = {}
    for engine, cps in by_engine.items():
        sample = cps.get("4h", {})
        if sample.get("n", 0) < minimum:
            sample = cps.get("24h", {})
        n = sample.get("n", 0)
        hit = sample.get("hit_rate_pct")
        adj = 0
        if n >= minimum and isinstance(hit, (int, float)):
            if hit >= 70:
                adj = min(max_adj, 5)
            elif hit >= 60:
                adj = min(max_adj, 2)
            elif hit < 35:
                adj = -min(max_adj, 8)
            elif hit < 45:
                adj = -min(max_adj, 4)
        adjustments[engine] = {"sample_n": n, "hit_rate_pct": hit, "score_adjustment_points": adj}

    return {"schema_version": 1, "generated_at": utc_iso(now), "generated_unix": now, "signals_total": len(signals), "graded_observations": len(rows), "by_engine": by_engine, "feature_buckets": features, "score_adjustments": adjustments, "minimum_samples_before_adjustment": minimum, "warning": "Shadow-book outcomes measure signal behavior, not guaranteed executable fills. User-confirmed trades remain the highest-quality evidence."}


def main():
    now = int(time.time())
    packet = load_json(PACKET)
    if not packet:
        raise RuntimeError("desk_packet.json missing")
    cfg = load_json(CONFIG)
    book = load_json(BOOK, {"schema_version": 1, "signals": []})
    signals = book.setdefault("signals", [])
    cooldown = cfg.get("shadow_learning", {}).get("signal_cooldown_hours") or {}
    engines = packet.get("engines") or {}

    for row in (engines.get("fast_flip_screen") or [])[:8]:
        roi = row.get("afterTaxSpreadRoiPct")
        if not isinstance(roi, (int, float)) or roi < 0.5 or row.get("id") is None:
            continue
        item_id = row.get("id")
        add_signal(signals, {"engine": "fast_flip", "key": f"{item_id}", "item_id": item_id, "item": row.get("name"), "direction": "LONG", "signal_mid": midpoint(row.get("high"), row.get("low")), "entry_low": row.get("low"), "initial_high": row.get("high"), "features": {"initial_roi_pct": roi, "high_side_share": row.get("highSideShare"), "liquidity": row.get("liquidity"), "one_hour_volume": row.get("oneHourVolume"), "gp_traded_1h": row.get("estimatedGpTraded1h"), "five_min_vs_1h_pct": row.get("fiveMinVsOneHourPct"), "one_hour_vs_24h_pct": row.get("oneHourVs24hPct")}}, now, float(cooldown.get("fast_flip", 8)))

    for row in (engines.get("short_term_momentum") or [])[:5]:
        move = row.get("fiveMinVsOneHourPct")
        if not isinstance(move, (int, float)) or abs(move) < 1 or row.get("id") is None:
            continue
        item_id = row.get("id")
        add_signal(signals, {"engine": "momentum", "key": f"{item_id}:{'UP' if move > 0 else 'DOWN'}", "item_id": item_id, "item": row.get("name"), "direction": "LONG" if move > 0 else "SHORT", "signal_mid": midpoint(row.get("high"), row.get("low")), "entry_low": row.get("low"), "features": {"initial_roi_pct": row.get("afterTaxSpreadRoiPct"), "high_side_share": row.get("highSideShare"), "liquidity": row.get("liquidity"), "five_min_vs_1h_pct": move, "one_hour_vs_24h_pct": row.get("oneHourVs24hPct")}}, now, float(cooldown.get("momentum", 12)))

    evergreen = (engines.get("evergreen_staples") or {}).get("top_candidates") or []
    for row in evergreen[:8]:
        if row.get("status") not in ("BUY_ZONE_CANDIDATE", "WATCH_REVERSAL") or row.get("id") is None:
            continue
        item_id = row.get("id")
        cur = row.get("current") or {}
        add_signal(signals, {"engine": "evergreen", "key": f"{item_id}:{row.get('status')}", "item_id": item_id, "item": row.get("name"), "direction": "LONG", "signal_mid": cur.get("mid") or midpoint(cur.get("high"), cur.get("low")), "entry_low": cur.get("low"), "features": {"initial_roi_pct": None, "high_side_share": (row.get("demand") or {}).get("highSideShare1h"), "liquidity": None, "discount_30d_pct": (row.get("range") or {}).get("discountTo30dMedianPct"), "percentile_30d": (row.get("range") or {}).get("thirtyDayPercentile"), "status": row.get("status")}}, now, float(cooldown.get("evergreen", 24)))

    for row in (engines.get("conversions") or [])[:6]:
        patient = row.get("patient") or {}
        roi = patient.get("roi_pct")
        if not isinstance(roi, (int, float)) or roi <= 0:
            continue
        inputs = row.get("inputs") or []
        strategy_key = "+".join(f"{x.get('quantity',1)}x{x.get('item')}" for x in inputs) + f"->{row.get('output')}"
        add_signal(signals, {"engine": "conversion", "key": strategy_key, "strategy_key": strategy_key, "item": strategy_key, "initial_patient_roi_pct": roi, "features": {"initial_roi_pct": roi, "high_side_share": None, "liquidity": None}}, now, float(cooldown.get("conversion", 12)))

    market = by_id_market()
    grade_signals(signals, packet, market, cfg, now)
    cutoff = now - 60 * 24 * 3600
    if len(signals) > 2500:
        signals[:] = [s for s in signals if int(s.get("created_unix") or 0) >= cutoff][-2500:]
    book["generated_at"] = utc_iso(now)
    book["generated_unix"] = now
    book["signals"] = signals
    summary = summarize(signals, cfg, now)
    save_json(BOOK, book)
    save_json(SUMMARY, summary)
    print(f"Updated shadow book: signals={len(signals)} graded={summary['graded_observations']}")


if __name__ == "__main__":
    main()
