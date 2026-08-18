#!/usr/bin/env python3
import json
import os
import string
import time
import urllib.request
from datetime import datetime, timezone

BASE = "https://prices.runescape.wiki/api/v1/osrs"
USER_AGENT = "osrs-merch-relay-universe/1.1 (contact: davidothompson48@gmail.com)"
OUT_DIR = "market_universe"


def fetch_json(path):
    url = f"{BASE}/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.load(resp)


def normalize(payload):
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {str(x.get("id")): x for x in data if isinstance(x, dict) and x.get("id") is not None}
    return {}


def row(block, item_id):
    return block.get(str(item_id)) or block.get(item_id) or {}


def shard_key(name):
    if not name:
        return "OTHER"
    first = name[0].upper()
    if first in string.ascii_uppercase:
        return first
    if first.isdigit():
        return "0-9"
    return "OTHER"


def main():
    now = int(time.time())
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    mapping_payload = fetch_json("mapping")
    mapping = mapping_payload if isinstance(mapping_payload, list) else mapping_payload.get("data", [])
    latest = normalize(fetch_json("latest"))
    p5m = normalize(fetch_json("5m"))
    p1h = normalize(fetch_json("1h"))
    p24h = normalize(fetch_json("24h"))

    shards = {}
    total = 0
    for meta in mapping:
        if not isinstance(meta, dict) or not isinstance(meta.get("id"), int):
            continue
        item_id = meta["id"]
        name = meta.get("name")
        cur = row(latest, item_id)
        five = row(p5m, item_id)
        hour = row(p1h, item_id)
        day = row(p24h, item_id)
        high_time = cur.get("highTime")
        low_time = cur.get("lowTime")
        item = {
            "id": item_id,
            "name": name,
            "members": meta.get("members"),
            "buyLimit": meta.get("limit"),
            "value": meta.get("value"),
            "highalch": meta.get("highalch"),
            "lowalch": meta.get("lowalch"),
            "current": {
                "high": cur.get("high"),
                "low": cur.get("low"),
                "highTime": high_time,
                "lowTime": low_time,
                "highAgeSeconds": now - high_time if isinstance(high_time, int) else None,
                "lowAgeSeconds": now - low_time if isinstance(low_time, int) else None
            },
            "5m": {
                "avgHighPrice": five.get("avgHighPrice"),
                "avgLowPrice": five.get("avgLowPrice"),
                "highPriceVolume": int(five.get("highPriceVolume") or 0),
                "lowPriceVolume": int(five.get("lowPriceVolume") or 0)
            },
            "1h": {
                "avgHighPrice": hour.get("avgHighPrice"),
                "avgLowPrice": hour.get("avgLowPrice"),
                "highPriceVolume": int(hour.get("highPriceVolume") or 0),
                "lowPriceVolume": int(hour.get("lowPriceVolume") or 0)
            },
            "24h": {
                "avgHighPrice": day.get("avgHighPrice"),
                "avgLowPrice": day.get("avgLowPrice"),
                "highPriceVolume": int(day.get("highPriceVolume") or 0),
                "lowPriceVolume": int(day.get("lowPriceVolume") or 0)
            }
        }
        shards.setdefault(shard_key(name), []).append(item)
        total += 1

    os.makedirs(OUT_DIR, exist_ok=True)
    wanted_files = set()
    index_shards = []
    for key in sorted(shards):
        rows = sorted(shards[key], key=lambda x: (x.get("name") or "", x.get("id") or 0))
        filename = f"{key}.json"
        wanted_files.add(filename)
        payload = {
            "schema_version": 1,
            "generated_at": generated_at,
            "generated_unix": now,
            "source": "prices.runescape.wiki OSRS RuneLite real-time API",
            "source_policy": "All market and static metadata fields in this file originate only from prices.runescape.wiki.",
            "shard": key,
            "item_count": len(rows),
            "items": rows
        }
        with open(os.path.join(OUT_DIR, filename), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        index_shards.append({"shard": key, "file": f"market_universe/{filename}", "item_count": len(rows)})

    # Remove obsolete generated shard files while preserving index.json.
    for filename in os.listdir(OUT_DIR):
        if filename.endswith(".json") and filename != "index.json" and filename not in wanted_files:
            os.remove(os.path.join(OUT_DIR, filename))

    index = {
        "schema_version": 1,
        "generated_at": generated_at,
        "generated_unix": now,
        "source": "prices.runescape.wiki OSRS RuneLite real-time API",
        "source_policy": "All market and static metadata fields in the universe shards originate only from prices.runescape.wiki.",
        "item_count": total,
        "shards": index_shards,
        "lookup_rule": "Choose the shard by the first character of the exact item name: A-Z, 0-9, or OTHER."
    }
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
        f.write("\n")

    print(f"Wrote {len(index_shards)} readable universe shards with {total} mapped items")


if __name__ == "__main__":
    main()
