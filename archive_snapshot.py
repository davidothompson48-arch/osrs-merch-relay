#!/usr/bin/env python3
import json
import os

SNAPSHOT = "snapshot.json"
RELATED = "related_watch.json"
OUT = "history/market_history.jsonl"
RECENT_OUT = "history/recent_history.json"
MAX_RECORDS = 24 * 120  # roughly 120 days at hourly cadence
RECENT_RECORDS = 72      # compact last ~3 days for desk comparisons


def compact_portfolio(snapshot):
    out = {}
    for item_id, row in (snapshot.get("portfolio") or {}).items():
        current = row.get("current") or {}
        movement = row.get("movementPct") or {}
        volume = row.get("volume") or {}
        out[item_id] = {
            "name": row.get("name"),
            "high": current.get("high"),
            "low": current.get("low"),
            "highTime": current.get("highTime"),
            "lowTime": current.get("lowTime"),
            "afterTaxSpread": current.get("afterTaxSpread"),
            "afterTaxSpreadRoiPct": current.get("afterTaxSpreadRoiPct"),
            "move1hPct": movement.get("1h"),
            "move24hPct": movement.get("24h"),
            "move7dPct": movement.get("7d"),
            "move30dPct": movement.get("30d"),
            "volume1h": (volume.get("1h") or {}).get("total"),
            "highSideShare1h": volume.get("highSideShare1h"),
            "liquidity": row.get("liquidity"),
        }
    return out


def compact_related(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    groups = {}
    for group, rows in (data.get("groups") or {}).items():
        groups[group] = [
            {
                "id": x.get("id"),
                "name": x.get("name"),
                "high": (x.get("current") or {}).get("high"),
                "low": (x.get("current") or {}).get("low"),
                "h1HighVol": (x.get("oneHour") or {}).get("highPriceVolume"),
                "h1LowVol": (x.get("oneHour") or {}).get("lowPriceVolume"),
            }
            for x in rows
        ]
    return groups


def main():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        snapshot = json.load(f)

    record = {
        "generated_at": snapshot.get("generated_at"),
        "generated_unix": snapshot.get("generated_unix"),
        "portfolio": compact_portfolio(snapshot),
        "top_spread_candidates": (snapshot.get("market_scan") or {}).get("top_after_tax_spread_candidates", [])[:15],
        "extreme_order_flow": (snapshot.get("market_scan") or {}).get("extreme_one_hour_order_flow", [])[:10],
        "related": compact_related(RELATED),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    existing = []
    if os.path.exists(OUT):
        with open(OUT, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing.append(json.loads(line))
                except Exception:
                    pass

    timestamp = record.get("generated_unix")
    existing = [x for x in existing if x.get("generated_unix") != timestamp]
    existing.append(record)
    existing.sort(key=lambda x: x.get("generated_unix") or 0)
    existing = existing[-MAX_RECORDS:]

    with open(OUT, "w", encoding="utf-8") as f:
        for row in existing:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")

    recent = {
        "schema_version": 1,
        "source": "Derived only from this relay's prices.runescape.wiki snapshots",
        "record_count": min(len(existing), RECENT_RECORDS),
        "records": existing[-RECENT_RECORDS:],
    }
    with open(RECENT_OUT, "w", encoding="utf-8") as f:
        json.dump(recent, f, indent=2)
        f.write("\n")

    print(f"Archived market snapshot; retained {len(existing)} records; wrote {RECENT_OUT}")


if __name__ == "__main__":
    main()
