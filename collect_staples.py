#!/usr/bin/env python3
import json
import statistics
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

BASE = "https://prices.runescape.wiki/api/v1/osrs"
USER_AGENT = "osrs-merch-relay-staples/1.1 (contact: davidothompson48@gmail.com)"
UNIVERSE_FILE = "project/evergreen_staples.json"
OUT = "staples_watch.json"
MAX_WORKERS = 6


def fetch_json(path, params=None, required=True, retries=3, timeout=20):
    url = f"{BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt + 1 < retries:
                time.sleep(1.0 * (attempt + 1))
    if required:
        raise RuntimeError(f"Required endpoint failed: {url}: {last_error}")
    return {"_error": last_error, "_url": url}


def normalize(payload):
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {str(x.get("id")): x for x in data if isinstance(x, dict) and x.get("id") is not None}
    return {}


def timeseries_points(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def row_for(block, item_id):
    return block.get(str(item_id)) or block.get(item_id) or {}


def midpoint(high, low):
    vals = [x for x in (high, low) if isinstance(x, (int, float)) and x > 0]
    return sum(vals) / len(vals) if vals else None


def avg_mid(row):
    return midpoint(row.get("avgHighPrice"), row.get("avgLowPrice")) if isinstance(row, dict) else None


def pct_change(new, old):
    if new is None or old in (None, 0):
        return None
    return round((new / old - 1) * 100, 3)


def valid_mids(points, count=None):
    subset = points[-count:] if count and len(points) > count else points
    mids = [avg_mid(x) for x in subset]
    return [x for x in mids if isinstance(x, (int, float)) and x > 0]


def median_mid(points, count=None):
    mids = valid_mids(points, count)
    return statistics.median(mids) if mids else None


def percentile_rank(value, values):
    if value is None or not values:
        return None
    return round(100 * sum(1 for x in values if x <= value) / len(values), 1)


def series_change(points, lookback_points):
    mids = valid_mids(points)
    if len(mids) < 2:
        return None
    newest = mids[-1]
    idx = max(0, len(mids) - 1 - lookback_points)
    return pct_change(newest, mids[idx])


def score_candidate(discount30, percentile30, gp24, high_share, current_vs_24h, spread_pct):
    score = 0.0
    if gp24 >= 1_000_000_000:
        score += 25
    elif gp24 >= 250_000_000:
        score += 22
    elif gp24 >= 100_000_000:
        score += 19
    elif gp24 >= 25_000_000:
        score += 15
    elif gp24 >= 10_000_000:
        score += 10

    if isinstance(discount30, (int, float)) and discount30 < 0:
        score += min(25, abs(discount30) * 2.0)
    if isinstance(percentile30, (int, float)):
        score += 10 if percentile30 <= 10 else 8 if percentile30 <= 20 else 5 if percentile30 <= 35 else 0

    if isinstance(high_share, (int, float)):
        score += 10 if high_share >= 0.65 else 7 if high_share >= 0.55 else 3 if high_share >= 0.45 else 0
    if isinstance(current_vs_24h, (int, float)):
        score += 8 if current_vs_24h >= 0 else 4 if current_vs_24h >= -1.0 else 0
    if isinstance(spread_pct, (int, float)):
        score += 7 if spread_pct <= 0.75 else 4 if spread_pct <= 1.5 else 2 if spread_pct <= 3.0 else 0
    return round(min(score, 85.0), 1)


def fetch_series(item_id, timestep):
    payload = fetch_json("timeseries", {"id": item_id, "timestep": timestep}, required=False, retries=1, timeout=12)
    return timeseries_points(payload)


def parallel_series(item_ids, timestep):
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_series, item_id, timestep): item_id for item_id in item_ids}
        for future in as_completed(futures):
            item_id = futures[future]
            try:
                results[item_id] = future.result()
            except Exception:
                results[item_id] = []
    return results


def main():
    with open(UNIVERSE_FILE, "r", encoding="utf-8") as f:
        universe = json.load(f)

    policy = universe.get("screening_policy") or {}
    min_gp24 = int(policy.get("minimum_24h_gp_traded") or 10_000_000)
    target_discount = float(policy.get("preferred_discount_to_30d_median_pct") or -5.0)
    target_percentile = float(policy.get("preferred_30d_percentile_max") or 35.0)
    max_age = int(policy.get("fresh_print_max_age_seconds") or 3600)

    mapping_payload = fetch_json("mapping", required=True, retries=4)
    mapping_rows = mapping_payload if isinstance(mapping_payload, list) else mapping_payload.get("data", [])
    by_name = {x.get("name"): x for x in mapping_rows if isinstance(x, dict) and x.get("name")}

    latest = normalize(fetch_json("latest", required=True, retries=4))
    one_hour = normalize(fetch_json("1h", required=True, retries=4))
    day = normalize(fetch_json("24h", required=False, retries=2, timeout=15))
    if not latest or not one_hour:
        raise RuntimeError("Wiki API returned no usable latest/1h data for staple scan")

    names = []
    categories_for_name = {}
    for category, category_names in (universe.get("categories") or {}).items():
        for name in category_names:
            if name not in names:
                names.append(name)
            categories_for_name.setdefault(name, []).append(category)

    resolved = []
    unresolved = []
    for name in names:
        meta = by_name.get(name)
        if meta and isinstance(meta.get("id"), int):
            resolved.append((name, meta))
        else:
            unresolved.append(name)

    # The old scanner performed these network calls one at a time. Fetching a
    # small curated staple universe concurrently cuts an hourly scan from minutes
    # to seconds while keeping concurrency deliberately low for the Wiki API.
    ts6_by_id = parallel_series([meta["id"] for _, meta in resolved], "6h")

    now = int(time.time())
    prelim_rows = []
    prelim_ids = []
    for name, meta in resolved:
        item_id = meta["id"]
        cur = row_for(latest, item_id)
        h1 = row_for(one_hour, item_id)
        d1 = row_for(day, item_id)
        ts6 = ts6_by_id.get(item_id, [])

        high, low = cur.get("high"), cur.get("low")
        high_time, low_time = cur.get("highTime"), cur.get("lowTime")
        current_mid = midpoint(high, low)
        d1_mid = avg_mid(d1)
        high_vol_1h = int(h1.get("highPriceVolume") or 0)
        low_vol_1h = int(h1.get("lowPriceVolume") or 0)
        total_1h = high_vol_1h + low_vol_1h
        high_share = round(high_vol_1h / total_1h, 4) if total_1h else None
        day_volume = int(d1.get("highPriceVolume") or 0) + int(d1.get("lowPriceVolume") or 0)
        gp24 = int(day_volume * d1_mid) if d1_mid else 0

        mids30 = valid_mids(ts6, 120)
        med30 = statistics.median(mids30) if mids30 else None
        med7 = median_mid(ts6, 28)
        discount30 = pct_change(current_mid, med30)
        discount7 = pct_change(current_mid, med7)
        percentile30 = percentile_rank(current_mid, mids30)
        move7d = series_change(ts6, 28)
        move30d = series_change(ts6, 120)
        current_vs_24h = pct_change(current_mid, d1_mid)
        spread_pct = round(abs(high - low) / current_mid * 100, 3) if current_mid and isinstance(high, (int, float)) and isinstance(low, (int, float)) else None
        high_age = now - high_time if isinstance(high_time, int) else None
        low_age = now - low_time if isinstance(low_time, int) else None
        fresh = high_age is not None and low_age is not None and high_age <= max_age and low_age <= max_age
        enough_history = len(mids30) >= 20

        prelim_oversold = (
            fresh and enough_history and gp24 >= min_gp24 and
            ((isinstance(discount30, (int, float)) and discount30 <= target_discount) or
             (isinstance(move7d, (int, float)) and move7d <= -6.0)) and
            (percentile30 is None or percentile30 <= max(target_percentile, 40.0))
        )
        if prelim_oversold:
            prelim_ids.append(item_id)

        prelim_rows.append({
            "id": item_id,
            "name": name,
            "categories": categories_for_name.get(name, []),
            "buyLimit": meta.get("limit"),
            "current": {"high": high, "low": low, "highAgeSeconds": high_age, "lowAgeSeconds": low_age,
                        "mid": round(current_mid, 3) if current_mid is not None else None, "spreadPct": spread_pct},
            "demand": {"oneHourVolume": total_1h, "highSideShare1h": high_share,
                       "twentyFourHourVolume": day_volume, "estimatedGpTraded24h": gp24},
            "range": {"sevenDayMedian": round(med7, 3) if med7 is not None else None,
                      "thirtyDayMedian": round(med30, 3) if med30 is not None else None,
                      "discountTo7dMedianPct": discount7, "discountTo30dMedianPct": discount30,
                      "thirtyDayPercentile": percentile30, "historyPoints6h": len(mids30)},
            "movementPct": {"1h": None, "6h": None, "24h": None, "7d": move7d, "30d": move30d,
                            "currentVs24hAvg": current_vs_24h},
            "oversoldCandidate": prelim_oversold,
            "_score_inputs": [discount30, percentile30, gp24, high_share, current_vs_24h, spread_pct]
        })

    ts1_by_id = parallel_series(prelim_ids, "1h") if prelim_ids else {}
    rows = []
    for row in prelim_rows:
        item_id = row["id"]
        if row["oversoldCandidate"]:
            ts1 = ts1_by_id.get(item_id, [])
            row["movementPct"]["1h"] = series_change(ts1, 1)
            row["movementPct"]["6h"] = series_change(ts1, 6)
            row["movementPct"]["24h"] = series_change(ts1, 24)

        move6h = row["movementPct"]["6h"]
        high_share = row["demand"]["highSideShare1h"]
        current_vs_24h = row["movementPct"]["currentVs24hAvg"]
        falling_knife = bool(row["oversoldCandidate"] and isinstance(move6h, (int, float)) and move6h <= -2.0 and
                             isinstance(high_share, (int, float)) and high_share < 0.45)
        stabilized = bool(row["oversoldCandidate"] and not falling_knife and (
            (isinstance(move6h, (int, float)) and move6h >= -0.5) or
            (isinstance(high_share, (int, float)) and high_share >= 0.55) or
            (isinstance(current_vs_24h, (int, float)) and current_vs_24h >= -0.5)))
        score = score_candidate(*row.pop("_score_inputs"))
        status = "FALLING_KNIFE" if falling_knife else "BUY_ZONE_CANDIDATE" if row["oversoldCandidate"] and stabilized and score >= 60 else "WATCH_REVERSAL" if row["oversoldCandidate"] else "NOT_OVERSOLD"
        row.update({"stabilized": stabilized, "fallingKnife": falling_knife, "status": status,
                    "mechanicalScoreBeforeStructuralCheck": score, "structuralCheckRequired": True})
        rows.append(row)

    candidates = [x for x in rows if x.get("oversoldCandidate")]
    candidates.sort(key=lambda x: (x.get("status") == "BUY_ZONE_CANDIDATE", x.get("mechanicalScoreBeforeStructuralCheck") or 0), reverse=True)

    output = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_unix": now,
        "source": "prices.runescape.wiki OSRS RuneLite real-time API",
        "source_policy": "All market fields originate only from prices.runescape.wiki. Staple classification is curated in project/evergreen_staples.json.",
        "scan_mode": "parallel_timeseries",
        "max_workers": MAX_WORKERS,
        "candidate_count": len(candidates),
        "top_candidates": candidates[:12],
        "all_staples": rows,
        "unresolved_names": unresolved,
        "warning": "Mechanical score stops at 85. The desk must perform the final structural-supply/demand bear check before recommending capital."
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, separators=(",", ":"))
        f.write("\n")
    print(f"Wrote {OUT} with {len(rows)} staples and {len(candidates)} oversold candidates")


if __name__ == "__main__":
    main()
