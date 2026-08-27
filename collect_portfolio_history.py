#!/usr/bin/env python3
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

BASE = "https://prices.runescape.wiki/api/v1/osrs"
USER_AGENT = "osrs-merch-relay-portfolio-history/1.0 (contact: davidothompson48@gmail.com)"
LEDGER = "project/portfolio_ledger.json"
OUT = "portfolio_history.json"
MAX_WORKERS = 6


def fetch_json(path, params=None, retries=2, timeout=12):
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
    return {"_error": last_error}


def points(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def midpoint(high, low):
    vals = [x for x in (high, low) if isinstance(x, (int, float)) and x > 0]
    return sum(vals) / len(vals) if vals else None


def avg_mid(row):
    return midpoint(row.get("avgHighPrice"), row.get("avgLowPrice")) if isinstance(row, dict) else None


def valid_mids(rows):
    return [x for x in (avg_mid(row) for row in rows) if isinstance(x, (int, float)) and x > 0]


def pct(new, old):
    if new is None or old in (None, 0):
        return None
    return round((new / old - 1) * 100, 3)


def change(rows, lookback):
    mids = valid_mids(rows)
    if len(mids) < 2:
        return None
    idx = max(0, len(mids) - 1 - lookback)
    return pct(mids[-1], mids[idx])


def volume(rows, count):
    subset = rows[-count:] if len(rows) > count else rows
    high = sum(int(x.get("highPriceVolume") or 0) for x in subset)
    low = sum(int(x.get("lowPriceVolume") or 0) for x in subset)
    return {"high": high, "low": low, "total": high + low}


def fetch_item(item):
    item_id = item["item_id"]
    ts1 = points(fetch_json("timeseries", {"id": item_id, "timestep": "1h"}, retries=1))
    ts6 = points(fetch_json("timeseries", {"id": item_id, "timestep": "6h"}, retries=1))
    return item_id, {
        "id": item_id,
        "name": item.get("item"),
        "movementPct": {
            "1h": change(ts1, 1),
            "6h": change(ts1, 6),
            "24h": change(ts1, 24),
            "7d": change(ts1, 168),
            "30d": change(ts6, 120),
        },
        "volume": {
            "1h": volume(ts1, 1),
            "6h": volume(ts1, 6),
            "24h": volume(ts1, 24),
            "7d": volume(ts1, 168),
        },
        "historyPoints": {"1h": len(ts1), "6h": len(ts6)},
        "history_complete": bool(ts1 and ts6),
    }


def main():
    with open(LEDGER, "r", encoding="utf-8") as f:
        ledger = json.load(f)
    items = [x for x in ledger.get("active_positions", []) if isinstance(x.get("item_id"), int)]

    rows = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_item, item): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                item_id, row = future.result()
                rows[str(item_id)] = row
            except Exception as exc:
                rows[str(item["item_id"])] = {
                    "id": item["item_id"], "name": item.get("item"), "history_complete": False,
                    "error": f"{type(exc).__name__}: {exc}"
                }

    out = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_unix": int(time.time()),
        "source": "prices.runescape.wiki OSRS RuneLite real-time API",
        "scan_mode": "parallel_timeseries",
        "max_workers": MAX_WORKERS,
        "position_count": len(items),
        "positions": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
        f.write("\n")
    print(f"Wrote {OUT} for {len(items)} active positions")


if __name__ == "__main__":
    main()
