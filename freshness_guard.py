#!/usr/bin/env python3
"""Single source of truth for OSRS relay freshness and execution eligibility."""
import argparse
import json
import time
from datetime import datetime, timezone

SNAPSHOT = "snapshot.json"
UNIVERSE = "market_universe/index.json"
HEALTH = "relay_health.json"
OUT = "market_freshness.json"


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def iso_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def age(now, ts):
    return max(0, now - ts) if isinstance(ts, int) else None


def classify(max_age):
    if max_age is None:
        return "MISSING"
    if max_age <= 120:
        return "LIVE"
    if max_age <= 300:
        return "USABLE"
    if max_age <= 600:
        return "STALE_WARNING"
    return "STALE"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-seconds", type=int, default=600)
    parser.add_argument("--require-fresh", action="store_true")
    args = parser.parse_args()

    now = int(time.time())
    snapshot = read_json(SNAPSHOT)
    universe = read_json(UNIVERSE)
    health = read_json(HEALTH)

    snapshot_ts = snapshot.get("generated_unix")
    universe_ts = universe.get("generated_unix")
    snapshot_age = age(now, snapshot_ts)
    universe_age = age(now, universe_ts)
    ages = [x for x in (snapshot_age, universe_age) if isinstance(x, int)]
    oldest_age = max(ages) if len(ages) == 2 else None
    drift = abs(snapshot_ts - universe_ts) if isinstance(snapshot_ts, int) and isinstance(universe_ts, int) else None

    reasons = []
    if not snapshot:
        reasons.append("SNAPSHOT_MISSING")
    if not universe:
        reasons.append("MARKET_UNIVERSE_MISSING")
    if health.get("success") is not True:
        reasons.append("RELAY_HEALTH_FAILED")
    if oldest_age is None:
        reasons.append("TIMESTAMP_MISSING")
    elif oldest_age > args.max_age_seconds:
        reasons.append("MARKET_DATA_TOO_OLD")
    if isinstance(drift, int) and drift > 180:
        reasons.append("SNAPSHOT_UNIVERSE_DRIFT_OVER_180S")

    execution_allowed = not reasons
    status = classify(oldest_age)
    if not execution_allowed and status in ("LIVE", "USABLE", "STALE_WARNING"):
        status = "DEGRADED"

    payload = {
        "schema_version": 1,
        "checked_at": iso_now(),
        "checked_unix": now,
        "source": "prices.runescape.wiki OSRS RuneLite relay",
        "snapshot_generated_unix": snapshot_ts,
        "market_universe_generated_unix": universe_ts,
        "snapshot_age_seconds": snapshot_age,
        "market_universe_age_seconds": universe_age,
        "oldest_market_data_age_seconds": oldest_age,
        "snapshot_universe_drift_seconds": drift,
        "max_execution_age_seconds": args.max_age_seconds,
        "status": status,
        "execution_allowed": execution_allowed,
        "reasons": reasons,
        "policy": {
            "LIVE": "0-120 seconds",
            "USABLE": "121-300 seconds",
            "STALE_WARNING": "301-600 seconds",
            "STALE": ">600 seconds",
            "rule": "No trade recommendation or automated allocation may be published when execution_allowed is false."
        }
    }
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")

    print(f"Freshness: {status}; oldest={oldest_age}s; execution_allowed={execution_allowed}")
    if args.require_fresh and not execution_allowed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
