#!/usr/bin/env python3
import glob
import json
import math
import time

PACKET = "desk_packet.json"
CFG = "project/speculative_parks.json"
OUT = "speculative_park_snapshot.json"


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


def midpoint(high, low):
    vals = [x for x in (high, low) if isinstance(x, (int, float)) and x > 0]
    return sum(vals) / len(vals) if vals else None


def avg_mid(row):
    if not isinstance(row, dict):
        return None
    return midpoint(row.get("avgHighPrice"), row.get("avgLowPrice"))


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def market_map():
    by_id = {}
    for path in glob.glob("market_universe/*.json"):
        if path.endswith("index.json"):
            continue
        payload = load_json(path)
        for row in payload.get("items", []):
            item_id = row.get("id")
            if item_id is not None:
                by_id[str(item_id)] = row
    return by_id


def freshness(row, now):
    cur = row.get("current") or {}
    ages = []
    for key in ("highTime", "lowTime"):
        value = cur.get(key)
        if isinstance(value, int):
            ages.append(max(0, now - value))
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


def effective_probability(model, scenario_weights):
    if not isinstance(model, dict):
        return None
    total = 0.0
    scenarios = model.get("scenarios") or []
    for raw_index, weight in (scenario_weights or {}).items():
        try:
            idx = int(raw_index)
            w = float(weight)
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(scenarios):
            continue
        probability = scenarios[idx].get("probability_pct")
        if isinstance(probability, (int, float)):
            total += probability * clamp(w, 0.0, 1.0)
    return round(clamp(total, 0.0, 100.0), 2)


def liquidity_score(row):
    day = row.get("24h") or {}
    mid = avg_mid(day)
    volume = int(day.get("highPriceVolume") or 0) + int(day.get("lowPriceVolume") or 0)
    if not isinstance(mid, (int, float)) or mid <= 0 or volume <= 0:
        return 25.0, None, volume
    gp = mid * volume
    if gp >= 1_000_000_000:
        score = 100.0
    elif gp >= 250_000_000:
        score = 85.0
    elif gp >= 50_000_000:
        score = 70.0
    elif gp >= 10_000_000:
        score = 55.0
    elif gp >= 2_000_000:
        score = 40.0
    else:
        score = 25.0
    return score, int(gp), volume


def price_opportunity(row, candidate, policy):
    cur = row.get("current") or {}
    current_mid = midpoint(cur.get("high"), cur.get("low"))
    day_mid = avg_mid(row.get("24h") or {})
    if not isinstance(current_mid, (int, float)) or not isinstance(day_mid, (int, float)) or day_mid <= 0:
        return {
            "score": 35.0,
            "current_mid": current_mid,
            "twenty_four_hour_mid": day_mid,
            "current_vs_24h_pct": None,
            "ideal_entry_gp": None,
            "entry_zone_high_gp": None,
            "do_not_chase_gp": None,
        }
    discount = float(candidate.get("preferred_discount_to_24h_avg_pct") or 5.0)
    premium = float(candidate.get(
        "do_not_chase_premium_to_24h_avg_pct",
        policy.get("default_do_not_chase_premium_to_24h_avg_pct") or 1.5
    ))
    ideal = day_mid * (1 - discount / 100)
    zone_high = day_mid * (1 - (discount / 2) / 100)
    chase = day_mid * (1 + premium / 100)
    current_vs = (current_mid / day_mid - 1) * 100
    if current_mid <= ideal:
        score = 100.0
    elif current_mid <= zone_high:
        score = 82.0
    elif current_mid <= day_mid:
        score = 66.0
    elif current_mid <= chase:
        score = 48.0
    else:
        score = 22.0
    return {
        "score": score,
        "current_mid": round(current_mid, 2),
        "twenty_four_hour_mid": round(day_mid, 2),
        "current_vs_24h_pct": round(current_vs, 3),
        "ideal_entry_gp": int(round(ideal)),
        "entry_zone_high_gp": int(round(zone_high)),
        "do_not_chase_gp": int(round(chase)),
    }


def rank_candidate(candidate, row, model, cfg, now):
    policy = cfg.get("policy") or {}
    weights = cfg.get("score_weights") or {}
    eff_prob = effective_probability(model, candidate.get("scenario_weights") or {})
    if eff_prob is None:
        eff_prob = 0.0
    conviction = float(candidate.get("base_conviction_0_100") or 0)
    asymmetry = float(candidate.get("asymmetric_upside_0_100") or 0)
    price = price_opportunity(row, candidate, policy)
    liq_score, gp_traded_24h, volume_24h = liquidity_score(row)
    fresh = freshness(row, now)

    score = (
        eff_prob * float(weights.get("effective_catalyst_probability") or 0.30)
        + conviction * float(weights.get("base_conviction") or 0.20)
        + asymmetry * float(weights.get("asymmetric_upside") or 0.20)
        + float(price["score"]) * float(weights.get("price_opportunity") or 0.15)
        + liq_score * float(weights.get("liquidity") or 0.15)
    )
    if fresh == "STALEISH":
        score -= 8
    elif fresh in ("STALE", "INCOMPLETE"):
        score -= 20
    score = round(clamp(score, 0.0, 100.0), 1)

    minimum_prob = float(policy.get("minimum_effective_catalyst_probability_pct") or 35)
    park_now = float(policy.get("park_now_score") or 67)
    deep_bid = float(policy.get("deep_bid_score") or 55)
    current_mid = price.get("current_mid")
    entry_zone_high = price.get("entry_zone_high_gp")
    chase = price.get("do_not_chase_gp")

    if fresh in ("STALE", "INCOMPLETE"):
        status = "WATCH_STALE"
    elif isinstance(current_mid, (int, float)) and isinstance(chase, int) and current_mid > chase:
        status = "WATCH_CROWDED"
    elif eff_prob < minimum_prob:
        status = "WATCH_LOW_CATALYST_PROBABILITY"
    elif score >= park_now and isinstance(current_mid, (int, float)) and isinstance(entry_zone_high, int) and current_mid <= entry_zone_high:
        status = "PARK_NOW"
    elif score >= deep_bid:
        status = "DEEP_BID"
    else:
        status = "WATCH"

    cur = row.get("current") or {}
    one = row.get("1h") or {}
    day = row.get("24h") or {}
    return {
        "rank_score": score,
        "status": status,
        "item_id": candidate.get("item_id"),
        "name": candidate.get("name"),
        "theme": candidate.get("theme"),
        "correlation_bucket": candidate.get("correlation_bucket"),
        "probability_model_id": candidate.get("probability_model_id"),
        "effective_catalyst_probability_pct": eff_prob,
        "base_conviction_0_100": conviction,
        "asymmetric_upside_0_100": asymmetry,
        "max_position_pct_of_liquid_gp": candidate.get("max_position_pct_of_liquid_gp"),
        "expected_horizon_days": candidate.get("expected_horizon_days"),
        "thesis": candidate.get("thesis"),
        "invalidation": candidate.get("invalidation"),
        "entry": {
            "ideal_gp": price.get("ideal_entry_gp"),
            "zone_high_gp": price.get("entry_zone_high_gp"),
            "do_not_chase_gp": price.get("do_not_chase_gp"),
            "preferred_discount_to_24h_avg_pct": candidate.get("preferred_discount_to_24h_avg_pct"),
        },
        "market": {
            "high": cur.get("high"),
            "low": cur.get("low"),
            "freshness": fresh,
            "current_mid": price.get("current_mid"),
            "twenty_four_hour_mid": price.get("twenty_four_hour_mid"),
            "current_vs_24h_pct": price.get("current_vs_24h_pct"),
            "one_hour_avg_high": one.get("avgHighPrice"),
            "one_hour_avg_low": one.get("avgLowPrice"),
            "twenty_four_hour_avg_high": day.get("avgHighPrice"),
            "twenty_four_hour_avg_low": day.get("avgLowPrice"),
            "twenty_four_hour_volume": volume_24h,
            "estimated_gp_traded_24h": gp_traded_24h,
            "liquidity_score_0_100": liq_score,
        },
    }


def main():
    cfg = load_json(CFG)
    packet = load_json(PACKET)
    if not cfg.get("enabled"):
        save_json(OUT, {
            "schema_version": 1,
            "enabled": False,
            "rollout_status": cfg.get("rollout_status"),
            "allocation_authoritative": False,
            "candidates": [],
        })
        return

    by_id = market_map()
    models = {
        row.get("id"): row
        for row in ((packet.get("catalyst_state") or {}).get("probability_models") or [])
        if row.get("id")
    }
    now = int(time.time())
    ranked = []
    missing_market = []
    for candidate in cfg.get("candidates", []):
        item_id = candidate.get("item_id")
        row = by_id.get(str(item_id))
        if not row:
            missing_market.append({"item_id": item_id, "name": candidate.get("name")})
            continue
        model = models.get(candidate.get("probability_model_id"))
        ranked.append(rank_candidate(candidate, row, model, cfg, now))

    ranked.sort(key=lambda x: (x.get("rank_score") or 0, x.get("market", {}).get("estimated_gp_traded_24h") or 0), reverse=True)
    policy = cfg.get("policy") or {}
    max_lite = int(policy.get("max_candidates_in_lite_packet") or 10)
    actionable = [x for x in ranked if x.get("status") in ("PARK_NOW", "DEEP_BID")]
    theme_caps = {}
    for row in ranked:
        bucket = row.get("correlation_bucket")
        pct = row.get("max_position_pct_of_liquid_gp")
        if bucket and isinstance(pct, (int, float)):
            theme_caps.setdefault(bucket, 0)
            theme_caps[bucket] += pct
    total_cap = float(policy.get("total_speculative_cap_pct_of_liquid_gp") or 30)
    configured_theme_cap = float(policy.get("max_single_theme_pct_of_liquid_gp") or 18)
    payload = {
        "schema_version": 1,
        "generated_at": packet.get("generated_at"),
        "generated_unix": packet.get("generated_unix"),
        "source": "prices.runescape.wiki OSRS RuneLite data via market_universe + cached catalyst_state",
        "enabled": True,
        "rollout_status": cfg.get("rollout_status"),
        "allocation_authoritative": bool(cfg.get("allocation_authoritative")),
        "cash_competes": bool(policy.get("cash_competes", True)),
        "objective": cfg.get("objective"),
        "portfolio_policy": {
            "total_speculative_cap_pct_of_liquid_gp": total_cap,
            "max_single_theme_pct_of_liquid_gp": configured_theme_cap,
            "rule": policy.get("rule"),
        },
        "actionable_count": len(actionable),
        "candidate_count": len(ranked),
        "missing_market_rows": missing_market,
        "top_candidates": ranked[:max_lite],
        "all_candidates": ranked,
        "configured_theme_position_pct_sums": theme_caps,
        "allocation_note": "Suggested item sizing is a maximum percentage of liquid GP, not a target. Apply the lower of item and theme caps; leave the remainder in cash when entries are not met."
    }
    save_json(OUT, payload)
    print(f"Wrote {OUT}; candidates={len(ranked)}; actionable={len(actionable)}")


if __name__ == "__main__":
    main()
