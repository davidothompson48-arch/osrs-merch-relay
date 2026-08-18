#!/usr/bin/env python3
import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = "https://prices.runescape.wiki/api/v1/osrs"
USER_AGENT = "osrs-merch-relay/1.1 (contact: davidothompson48@gmail.com)"
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

TAX_RATE = 0.02
TAX_CAP = 5_000_000
# Known GE-tax exemptions. This only matters for the broad scanner; none of the
# core tracked positions rely on exemption status for the current calculations.
TAX_EXEMPT = {
    "Old school bond", "Energy potion(1)", "Energy potion(2)", "Energy potion(3)", "Energy potion(4)",
    "Bronze arrow", "Bronze dart", "Iron arrow", "Iron dart", "Mind rune", "Steel arrow", "Steel dart",
    "Bass", "Bread", "Cake", "Cooked chicken", "Cooked meat", "Herring", "Lobster", "Mackerel",
    "Meat pie", "Pike", "Salmon", "Shrimps", "Tuna", "Ardougne teleport", "Camelot teleport",
    "Civitas illa fortis teleport", "Falador teleport", "Games necklace(8)", "Kourend castle teleport",
    "Lumbridge teleport", "Ring of dueling(8)", "Teleport to house", "Varrock teleport", "Chisel",
    "Gardening trowel", "Glassblowing pipe", "Hammer", "Needle", "Pestle and mortar", "Rake", "Saw",
    "Secateurs", "Seed dibber", "Shears", "Spade", "Watering can(0)",
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
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1.25 * (attempt + 1))
    if required:
        raise RuntimeError(f"Required endpoint failed: {url}: {last_error}")
    return {"_error": last_error, "_url": url}


def normalize_block(payload):
    """Return {item_id_string: row} for Wiki aggregate/latest responses."""
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        out = {}
        for row in data:
            if isinstance(row, dict) and row.get("id") is not None:
                out[str(row["id"])] = row
        return out
    return {}


def timeseries_points(payload):
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def row_for(block, item_id):
    return block.get(str(item_id)) or block.get(item_id) or {}


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


def point_mid(point):
    return avg_mid(point)


def change_from_series(points, lookback_points):
    if len(points) < 2:
        return None
    newest = point_mid(points[-1])
    idx = max(0, len(points) - 1 - lookback_points)
    older = point_mid(points[idx])
    return pct_change(newest, older)


def sum_volume(points, count):
    if not points:
        return {"high": 0, "low": 0, "total": 0}
    subset = points[-count:] if len(points) >= count else points
    high = sum(int(p.get("highPriceVolume") or 0) for p in subset)
    low = sum(int(p.get("lowPriceVolume") or 0) for p in subset)
    return {"high": high, "low": low, "total": high + low}


def pressure(high_volume, low_volume):
    total = int(high_volume or 0) + int(low_volume or 0)
    if total <= 0:
        return None
    return round(int(high_volume or 0) / total, 4)


def liquidity_label(gp_per_hour):
    if gp_per_hour >= 500_000_000:
        return "VERY LIQUID"
    if gp_per_hour >= 100_000_000:
        return "LIQUID"
    if gp_per_hour >= 20_000_000:
        return "MODERATE"
    if gp_per_hour >= 2_000_000:
        return "THIN"
    return "VERY THIN"


def load_previous():
    if not os.path.exists(OUT):
        return {}
    try:
        with open(OUT, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def main():
    now = int(time.time())
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    previous = load_previous()

    mapping_payload = fetch_json("mapping", required=True)
    mapping_rows = mapping_payload if isinstance(mapping_payload, list) else mapping_payload.get("data", [])
    meta = {
        row["id"]: row
        for row in mapping_rows
        if isinstance(row, dict) and isinstance(row.get("id"), int)
    }

    # Official Wiki v1 routes are /latest, /5m, /1h, /6h and /24h.
    latest = normalize_block(fetch_json("latest", required=True))
    p5m = normalize_block(fetch_json("5m", required=True))
    p1h = normalize_block(fetch_json("1h", required=True))
    p6h = normalize_block(fetch_json("6h"))
    p24h = normalize_block(fetch_json("24h"))

    if not latest or not p1h:
        raise RuntimeError("Wiki API returned no usable latest/1h data")

    portfolio = {}
    for item_id, fallback_name in TRACKED.items():
        item_meta = meta.get(item_id, {})
        name = item_meta.get("name") or fallback_name
        current = row_for(latest, item_id)
        five = row_for(p5m, item_id)
        one = row_for(p1h, item_id)
        six = row_for(p6h, item_id)
        day = row_for(p24h, item_id)

        ts1 = timeseries_points(fetch_json("timeseries", {"id": item_id, "timestep": "1h"}, required=True))
        ts6 = timeseries_points(fetch_json("timeseries", {"id": item_id, "timestep": "6h"}, required=True))

        high = current.get("high")
        low = current.get("low")
        high_time = current.get("highTime")
        low_time = current.get("lowTime")
        raw_spread = high - low if isinstance(high, (int, float)) and isinstance(low, (int, float)) else None
        tax = ge_tax(name, high)
        after_tax_spread = high - tax - low if raw_spread is not None and tax is not None else None
        after_tax_roi = round(after_tax_spread / low * 100, 3) if after_tax_spread is not None and low else None

        high_volume = int(one.get("highPriceVolume") or 0)
        low_volume = int(one.get("lowPriceVolume") or 0)
        one_mid = avg_mid(one)
        gp_traded_1h = int((high_volume + low_volume) * one_mid) if one_mid else 0

        previous_item = ((previous.get("portfolio") or {}).get(str(item_id)) or {})
        previous_current = previous_item.get("current") or {}

        portfolio[str(item_id)] = {
            "id": item_id,
            "name": name,
            "buy_limit": item_meta.get("limit"),
            "members": item_meta.get("members"),
            "current": {
                "high": high,
                "low": low,
                "highTime": high_time,
                "lowTime": low_time,
                "highAgeSeconds": now - high_time if isinstance(high_time, int) else None,
                "lowAgeSeconds": now - low_time if isinstance(low_time, int) else None,
                "rawSpread": raw_spread,
                "geTaxAtHigh": tax,
                "afterTaxSpread": after_tax_spread,
                "afterTaxSpreadRoiPct": after_tax_roi,
            },
            "averages": {"5m": five, "1h": one, "6h": six, "24h": day},
            "movementPct": {
                "1h": change_from_series(ts1, 1),
                "6h": change_from_series(ts1, 6),
                "24h": change_from_series(ts1, 24),
                "7d": change_from_series(ts1, 168),
                "30d": change_from_series(ts6, 120),
            },
            "volume": {
                "1h": sum_volume(ts1, 1),
                "6h": sum_volume(ts1, 6),
                "24h": sum_volume(ts1, 24),
                "7d": sum_volume(ts1, 168),
                "highSideShare1h": pressure(high_volume, low_volume),
                "estimatedGpTraded1h": gp_traded_1h,
            },
            "liquidity": liquidity_label(gp_traded_1h),
            "previousRelaySnapshot": {
                "generatedAt": previous.get("generated_at"),
                "high": previous_current.get("high"),
                "low": previous_current.get("low"),
                "highTime": previous_current.get("highTime"),
                "lowTime": previous_current.get("lowTime"),
            },
        }

    # Broad machine screen. ChatGPT still has to validate thesis, liquidity and risk.
    spreads = []
    momentum = []
    selloffs = []
    extreme_flow = []

    for key, current in latest.items():
        try:
            item_id = int(key)
        except (TypeError, ValueError):
            continue
        item_meta = meta.get(item_id, {})
        name = item_meta.get("name")
        if not name or not isinstance(current, dict):
            continue

        high = current.get("high")
        low = current.get("low")
        high_time = current.get("highTime")
        low_time = current.get("lowTime")
        if not all(isinstance(x, (int, float)) and x > 0 for x in (high, low)):
            continue
        if not isinstance(high_time, int) or not isinstance(low_time, int):
            continue
        if now - high_time > 7200 or now - low_time > 7200:
            continue

        one = row_for(p1h, item_id)
        five = row_for(p5m, item_id)
        day = row_for(p24h, item_id)
        high_volume = int(one.get("highPriceVolume") or 0)
        low_volume = int(one.get("lowPriceVolume") or 0)
        total_volume = high_volume + low_volume
        one_mid = avg_mid(one)
        five_mid = avg_mid(five)
        day_mid = avg_mid(day)
        if total_volume <= 0 or one_mid is None:
            continue

        gp_traded_1h = int(total_volume * one_mid)
        tax = ge_tax(name, high)
        if tax is None:
            continue
        net = high - tax - low
        roi = net / low * 100 if low else None
        high_share = pressure(high_volume, low_volume)

        record = {
            "id": item_id,
            "name": name,
            "high": high,
            "low": low,
            "highTime": high_time,
            "lowTime": low_time,
            "buyLimit": item_meta.get("limit"),
            "oneHourVolume": total_volume,
            "highPriceVolume": high_volume,
            "lowPriceVolume": low_volume,
            "highSideShare": high_share,
            "estimatedGpTraded1h": gp_traded_1h,
            "liquidity": liquidity_label(gp_traded_1h),
            "afterTaxSpreadGp": net,
            "afterTaxSpreadRoiPct": round(roi, 3) if roi is not None else None,
            "fiveMinVsOneHourPct": pct_change(five_mid, one_mid),
            "oneHourVs24hPct": pct_change(one_mid, day_mid),
        }

        if roi is not None and net > 0 and gp_traded_1h >= 2_000_000 and roi >= 0.15:
            screen_score = min(roi, 6.0) * 10 + min(math.log10(max(gp_traded_1h, 1)), 10) * 4
            record["screenScore"] = round(screen_score, 2)
            spreads.append(record)

        short_move = record["fiveMinVsOneHourPct"]
        if short_move is not None and gp_traded_1h >= 5_000_000 and abs(short_move) >= 1.0:
            momentum.append(record)

        day_move = record["oneHourVs24hPct"]
        if day_move is not None and gp_traded_1h >= 5_000_000 and day_move <= -3.0:
            selloffs.append(record)

        if gp_traded_1h >= 20_000_000 and high_share is not None and (high_share >= 0.8 or high_share <= 0.2):
            extreme_flow.append(record)

    spreads.sort(key=lambda x: (x.get("screenScore", 0), x.get("estimatedGpTraded1h", 0)), reverse=True)
    momentum.sort(key=lambda x: abs(x.get("fiveMinVsOneHourPct") or 0), reverse=True)
    selloffs.sort(key=lambda x: x.get("oneHourVs24hPct") or 0)
    extreme_flow.sort(key=lambda x: abs((x.get("highSideShare") or 0.5) - 0.5), reverse=True)

    output = {
        "schema_version": 2,
        "generated_at": generated_at,
        "generated_unix": now,
        "source": "prices.runescape.wiki OSRS RuneLite real-time API",
        "source_policy": "All market prices and volumes in this file originate only from prices.runescape.wiki.",
        "source_endpoints": {
            "latest": f"{BASE}/latest",
            "5m": f"{BASE}/5m",
            "1h": f"{BASE}/1h",
            "6h": f"{BASE}/6h",
            "24h": f"{BASE}/24h",
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
            "top_after_tax_spread_candidates": spreads[:60],
            "short_term_momentum": momentum[:40],
            "oversold_candidates": selloffs[:40],
            "extreme_one_hour_order_flow": extreme_flow[:40],
        },
    }

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")

    print(f"Wrote {OUT} at {generated_at}; {len(spreads)} spread candidates screened.")


if __name__ == "__main__":
    main()
