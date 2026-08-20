#!/usr/bin/env python3
import json
import time
import urllib.request
from datetime import datetime, timezone

BASE = "https://prices.runescape.wiki/api/v1/osrs"
USER_AGENT = "osrs-merch-relay-related/1.1 (contact: davidothompson48@gmail.com)"
UNIVERSE_FILE = "project/related_items.json"
OUT = "related_watch.json"


def fetch_json(path, required=True, retries=3, timeout=20):
    url = f"{BASE}/{path}"
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
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


def get_row(block, item_id):
    return block.get(str(item_id)) or block.get(item_id) or {}


def main():
    with open(UNIVERSE_FILE, "r", encoding="utf-8") as f:
        universe = json.load(f)

    mapping_payload = fetch_json("mapping", required=True, retries=4)
    mapping_rows = mapping_payload if isinstance(mapping_payload, list) else mapping_payload.get("data", [])
    by_name = {x.get("name"): x for x in mapping_rows if isinstance(x, dict) and x.get("name")}

    latest = normalize(fetch_json("latest", required=True, retries=4))
    one_hour = normalize(fetch_json("1h", required=True, retries=4))
    day = normalize(fetch_json("24h", required=False, retries=2, timeout=15))

    if not latest or not one_hour:
        raise RuntimeError("Wiki API returned no usable latest/1h data for related watch")

    now = int(time.time())
    out_groups = {}
    unresolved = []

    for group, names in (universe.get("groups") or {}).items():
        rows = []
        seen = set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            meta = by_name.get(name)
            if not meta:
                unresolved.append({"group": group, "name": name})
                continue
            item_id = meta.get("id")
            cur = get_row(latest, item_id)
            h1 = get_row(one_hour, item_id)
            d1 = get_row(day, item_id)
            high = cur.get("high")
            low = cur.get("low")
            high_time = cur.get("highTime")
            low_time = cur.get("lowTime")
            rows.append({
                "id": item_id,
                "name": name,
                "buyLimit": meta.get("limit"),
                "members": meta.get("members"),
                "current": {
                    "high": high,
                    "low": low,
                    "highTime": high_time,
                    "lowTime": low_time,
                    "highAgeSeconds": now - high_time if isinstance(high_time, int) else None,
                    "lowAgeSeconds": now - low_time if isinstance(low_time, int) else None,
                },
                "oneHour": {
                    "avgHighPrice": h1.get("avgHighPrice"),
                    "avgLowPrice": h1.get("avgLowPrice"),
                    "highPriceVolume": int(h1.get("highPriceVolume") or 0),
                    "lowPriceVolume": int(h1.get("lowPriceVolume") or 0),
                },
                "twentyFourHour": {
                    "avgHighPrice": d1.get("avgHighPrice"),
                    "avgLowPrice": d1.get("avgLowPrice"),
                    "highPriceVolume": int(d1.get("highPriceVolume") or 0),
                    "lowPriceVolume": int(d1.get("lowPriceVolume") or 0),
                },
            })
        out_groups[group] = rows

    output = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_unix": now,
        "source": "prices.runescape.wiki OSRS RuneLite real-time API",
        "source_policy": "All market fields in this file originate only from prices.runescape.wiki.",
        "freshness_policy": "mapping/latest/1h are required; 24h is fail-soft.",
        "groups": out_groups,
        "unresolved_names": unresolved,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
        f.write("\n")
    print(f"Wrote {OUT} with {sum(len(v) for v in out_groups.values())} related-item rows")


if __name__ == "__main__":
    main()
