#!/usr/bin/env python3
import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = "https://prices.runescape.wiki/api/v1/osrs"
USER_AGENT = "osrs-merch-relay/1.0 (contact: davidothompson48@gmail.com)"
OUT = "snapshot.json"

TRACKED = {
    21880: "Wrath rune",
    21079: "Arcane prayer scroll",
    21034: "Dexterous prayer scroll",
    24419: "Inquisitor's great helm",
    24420: "Inquisitor's hauberk",
    24421: "Inquisitor's plateskirt",
    24417: "Inquisitor's mace",
    1727: "Amulet of magic",
    21024: "Ancestral robe bottom",
    536: "Dragon bones",
}

# Current OSRS GE convenience-fee rules as of this relay version.
TAX_RATE = 0.02
TAX_CAP = 5_000_000
TAX_EXEMPT = {
    "Old school bond", "Energy potion(1)", "Energy potion(2)", "Energy potion(3)", "Energy potion(4)",
    "Bronze arrow", "Bronze dart", "Iron arrow", "Iron dart", "Mind rune", "Steel arrow", "Steel dart",
    "Bass", "Bread", "Cake", "Cooked chicken", "Cooked meat", "Herring", "Lobster", "Mackerel",
    "Meat pie", "Pike", "Salmon", "Shrimps", "Tuna", "Ardougne teleport", "Camelot teleport",
    "Civitas illa fortis teleport", "Falador teleport", "Games necklace(8)", "Kourend castle teleport",
    "Lumbridge teleport", "Ring of dueling(8)", "Teleport to house", "Varrock teleport", "Chisel",
    "Gardening trowel", "Glassblowing pipe", "Hammer", "Needle", "Pestle and mortar", "Rake", "Saw",
    "Secateurs", "Seed dibber", "Shears", "Spade", "Watering can(0)"
}


def fetch_json(path, params=None, required=False, retries=3):
    url = f"{BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1.5 * (attempt + 1))
    if required:
        raise RuntimeError(f"Required endpoint failed: {url}: {last_error}")
    return {"_error": last_error, "_url": url}


def extract_data(payload):
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def midpoint(high, low):
    vals = [x for x in (high, low) if isinstance(x, (int, float)) and x > 0]
    return sum(vals) / len(vals) if vals else None


def avg_mid(row):
    if not isinstance(row, dict):
        return None
    return midpoint(row.get("avgHighPrice"), row.get("avgLowPrice"))


def pct_change(new, old):
    if new is None or old in (None, 0):
        return None
    return round((new / old - 1) * 100, 3)


def ge_tax(name, sell_price):
    if not isinstance(sell_price, (int, float)) or sell_price <= 0:
        return None
    if name in TAX_EXEMPT:
        return 0
    return min(math.floor(sell_price * TAX_RATE), TAX_CAP)


def timeseries_points(payload):
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def point_mid(p):
    return avg_mid(p)


def nearest_change(points, lookback_points):
    if len(points) < 2:
        return None
    newest = point_mid(points[-1])
    idx = max(0, len(points) - 1 - lookback_points)
    old = point_mid(points[idx])
    return pct_change(newest, old)


def sum_volume(points, count):
    if not points:
        return {"high": 0, "low": 0, "total": 0}
    subset = points[-count:] if len(points) >= count else points
    hv = sum(int(p.get("highPriceVolume") or 0) for p in subset)
    lv = sum(int(p.get("lowPriceVolume") or 0) for p in subset)
    return {"high": hv, "low": lv, "total": hv + lv}


def row_for(data, item_id):
    return data.get(str(item_id)) or data.get(item_id) or {}


def load_previous():
    if not os.path.exists(OUT):
        return {}
    try:
        with open(OUT, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def pressure(high_vol, low_vol):
    total = (high_vol or 0) + (low_vol or 0)
    if total <= 0:
        return None
    return round((high_vol or 0) / total, 4)


def liquidity_label(value_per_hour):
    if value_per_hour >= 500_000_000:
        return "VERY LIQUID"
    if value_per_hour >= 100_000_000:
        return "LIQUID"
    if value_per_hour >= 20_000_000:
        return "MODERATE"
    if value_per_hour >= 2_000_000:
        return "THIN"
    return "VERY THIN"


def main():
    now = int(time.time())
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    previous = load_previous()

    mapping_payload = fetch_json("mapping", required=True)
    mapping_list = mapping_payload if isinstance(mapping_payload, list) else mapping_payload.get("data", [])
    meta = {}
    for x in mapping_list:
        if isinstance(x, dict) and isinstance(x.get("id"), int):
            meta[x["id"]] = x

    latest = extract_data(fetch_json("latest", required=True))
    p5m = extract_data(fetch_json("prices/5m"))
    p1h = extract_data(fetch_json("prices/1h", required=True))
    p6h = extract_data(fetch_json("prices/6h"))
    p24h = extract_data(fetch_json("prices/24h"))

    portfolio = {}
    for item_id, fallback_name in TRACKED.items():
        m = meta.get(item_id, {})
        name = m.get("name") or fallback_name
        cur = row_for(latest, item_id)
        one = row_for(p1h, item_id)
        five = row_for(p5m, item_id)
        six = row_for(p6h, item_id)
        day = row_for(p24h, item_id)

        ts1 = timeseries_points(fetch_json("timeseries", {"timestep": "1h", "id": item_id}))
        ts6 = timeseries_points(fetch_json("timeseries", {"timestep": "6h", "id": item_id}))

        high = cur.get("high")
        low = cur.get("low")
        high_time = cur.get("highTime")
        low_time = cur.get("lowTime")
        raw_spread = high - low if isinstance(high, (int, float)) and isinstance(low, (int, float)) else None
        tax = ge_tax(name, high)
        net_spread = high - tax - low if raw_spread is not None and tax is not None else None
        net_roi = round(net_spread / low * 100, 3) if net_spread is not None and low else None

        hv = int(one.get("highPriceVolume") or 0)
        lv = int(one.get("lowPriceVolume") or 0)
        one_mid = avg_mid(one)
        value_per_hour = int((hv + lv) * one_mid) if one_mid else 0

        prev_item = ((previous.get("portfolio") or {}).get(str(item_id)) or {})
        prev_cur = prev_item.get("current") or {}

        portfolio[str(item_id)] = {
            "id": item_id,
            "name": name,
            "buy_limit": m.get("limit"),
            "members": m.get("members"),
            "current": {
                "high": high,
                "low": low,
                "highTime": high_time,
                "lowTime": low_time,
                "highAgeSeconds": now - high_time if isinstance(high_time, int) else None,
                "lowAgeSeconds": now - low_time if isinstance(low_time, int) else None,
                "rawSpread": raw_spread,
                "geTaxAtHigh": tax,
                "afterTaxSpread": net_spread,
                "afterTaxSpreadRoiPct": net_roi,
            },
            "averages": {
                "5m": five,
                "1h": one,
                "6h": six,
                "24h": day,
            },
            "movementPct": {
                "1h": nearest_change(ts1, 1),
                "6h": nearest_change(ts1, 6),
                "24h": nearest_change(ts1, 24),
                "7d": nearest_change(ts1, 168),
                "30d": nearest_change(ts6, 120),
            },
            "volume": {
                "1h": sum_volume(ts1, 1),
                "6h": sum_volume(ts1, 6),
                "24h": sum_volume(ts1, 24),
                "7d": sum_volume(ts1, 168),
                "highSideShare1h": pressure(hv, lv),
                "estimatedGpTraded1h": value_per_hour,
            },
            "liquidity": liquidity_label(value_per_hour),
            "previousRelaySnapshot": {
                "generatedAt": previous.get("generated_at"),
                "high": prev_cur.get("high"),
                "low": prev_cur.get("low"),
                "highTime": prev_cur.get("highTime"),
                "lowTime": prev_cur.get("lowTime"),
            },
        }

    # Pre-screen the full market. These are candidates, not trade recommendations.
    candidates = []
    momentum = []
    selloffs = []
    unexplained = []
    for key, cur in latest.items():
        try:
            item_id = int(key)
        except Exception:
            continue
        m = meta.get(item_id, {})
        name = m.get("name")
        if not name:
            continue
        high, low = cur.get("high"), cur.get("low")
        ht, lt = cur.get("highTime"), cur.get("lowTime")
        if not all(isinstance(x, (int, float)) and x > 0 for x in (high, low)):
            continue
        if not isinstance(ht, int) or not isinstance(lt, int) or now - ht > 7200 or now - lt > 7200:
            continue
        one = row_for(p1h, item_id)
        five = row_for(p5m, item_id)
        day = row_for(p24h, item_id)
        hv, lv = int(one.get("highPriceVolume") or 0), int(one.get("lowPriceVolume") or 0)
        total_vol = hv + lv
        if total_vol <= 0:
            continue
        one_mid = avg_mid(one)
        five_mid = avg_mid(five)
        day_mid = avg_mid(day)
        traded_gp = int(total_vol * one_mid) if one_mid else 0
        tax = ge_tax(name, high)
        net = high - tax - low
        roi = net / low * 100 if low else -999
        liq = liquidity_label(traded_gp)
        buy_pressure = pressure(hv, lv)
        rec = {
            "id": item_id,
            "name": name,
            "high": high,
            "low": low,
            "highTime": ht,
            "lowTime": lt,
            "buyLimit": m.get("limit"),
            "oneHourVolume": total_vol,
            "highPriceVolume": hv,
            "lowPriceVolume": lv,
            "highSideShare": buy_pressure,
            "estimatedGpTraded1h": traded_gp,
            "liquidity": liq,
            "afterTaxSpreadGp": net,
            "afterTaxSpreadRoiPct": round(roi, 3),
            "fiveMinVsOneHourPct": pct_change(five_mid, one_mid),
            "oneHourVs24hPct": pct_change(one_mid, day_mid),
        }
        if net > 0 and traded_gp >= 2_000_000 and roi >= 0.15:
            # Weight ROI by liquidity while avoiding giant illiquid-spread domination.
            score = min(roi, 6.0) * 10 + min(math.log10(max(traded_gp, 1)), 10) * 4
            rec["screenScore"] = round(score, 2)
            candidates.append(rec)
        if five_mid and one_mid and traded_gp >= 5_000_000:
            move = pct_change(five_mid, one_mid)
            if move is not None and abs(move) >= 1.0:
                momentum.append(rec)
        if one_mid and day_mid and traded_gp >= 5_000_000:
            move24 = pct_change(one_mid, day_mid)
            if move24 is not None and move24 <= -3.0:
                selloffs.append(rec)
        if traded_gp >= 20_000_000 and buy_pressure is not None and (buy_pressure >= 0.8 or buy_pressure <= 0.2):
            unexplained.append(rec)

    candidates.sort(key=lambda x: (x.get("screenScore", 0), x.get("estimatedGpTraded1h", 0)), reverse=True)
    momentum.sort(key=lambda x: abs(x.get("fiveMinVsOneHourPct") or 0), reverse=True)
    selloffs.sort(key=lambda x: x.get("oneHourVs24hPct") or 0)
    unexplained.sort(key=lambda x: abs((x.get("highSideShare") or 0.5) - 0.5), reverse=True)

    output = {
        "schema_version": 1,
        "generated_at": generated_at,
        "generated_unix": now,
        "source": "prices.runescape.wiki OSRS RuneLite real-time API",
        "source_policy": "All market prices and volumes in this file originate only from prices.runescape.wiki.",
        "source_endpoints": {
            "latest": f"{BASE}/latest",
            "5m": f"{BASE}/prices/5m",
            "1h": f"{BASE}/prices/1h",
            "6h": f"{BASE}/prices/6h",
            "24h": f"{BASE}/prices/24h",
            "mapping": f"{BASE}/mapping",
            "timeseries": f"{BASE}/timeseries",
        },
        "tax_model": {
            "rate": TAX_RATE,
            "cap_gp_per_item": TAX_CAP,
            "note": "2% GE convenience fee, capped at 5m per item; known exempt items are handled by name.",
        },
        "portfolio": portfolio,
        "market_scan": {
            "note": "Machine-generated screening only; ChatGPT must validate thesis, liquidity, catalyst and downside before recommending a trade.",
            "top_after_tax_spread_candidates": candidates[:60],
            "short_term_momentum": momentum[:40],
            "oversold_candidates": selloffs[:40],
            "extreme_one_hour_order_flow": unexplained[:40],
        },
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, sort_keys=False)
        f.write("\n")

    print(f"Wrote {OUT} at {generated_at}; {len(candidates)} spread candidates screened.")


if __name__ == "__main__":
    main()
