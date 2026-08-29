#!/usr/bin/env python3
import json
import statistics
import time
from datetime import datetime, timezone

PACKET = "desk_packet.json"
CFG = "project/profit_engine.json"
STATE = "spread_persistence.json"


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


def current_observation(row, now, cfg):
    high = row.get("high")
    low = row.get("low")
    edge = row.get("afterTaxSpreadGp")
    roi = row.get("afterTaxSpreadRoiPct")
    high_time = row.get("highTime")
    low_time = row.get("lowTime")
    high_age = now - high_time if isinstance(high_time, int) else None
    low_age = now - low_time if isinstance(low_time, int) else None
    high_vol = int(row.get("highPriceVolume") or 0)
    low_vol = int(row.get("lowPriceVolume") or 0)
    volume = int(row.get("oneHourVolume") or (high_vol + low_vol))
    high_share = row.get("highSideShare")
    if not isinstance(high_share, (int, float)) and volume > 0:
        high_share = high_vol / volume

    max_age = int(cfg.get("max_high_low_age_seconds") or 900)
    min_volume = int(cfg.get("minimum_one_hour_volume") or 20)
    min_side_share = float(cfg.get("minimum_each_side_share") or 0.05)
    fresh_sides = high_age is not None and low_age is not None and max(high_age, low_age) <= max_age
    two_sided = isinstance(high_share, (int, float)) and min_side_share <= high_share <= (1 - min_side_share) and high_vol > 0 and low_vol > 0
    positive_edge = all(isinstance(v, (int, float)) and v > 0 for v in (high, low, edge, roi)) and high > low
    enough_volume = volume >= min_volume
    qualified = bool(fresh_sides and two_sided and positive_edge and enough_volume)

    return {
        "ts": now,
        "high": high,
        "low": low,
        "after_tax_spread_gp": edge,
        "after_tax_roi_pct": roi,
        "high_age_seconds": high_age,
        "low_age_seconds": low_age,
        "one_hour_volume": volume,
        "high_price_volume": high_vol,
        "low_price_volume": low_vol,
        "high_side_share": round(high_share, 4) if isinstance(high_share, (int, float)) else None,
        "fresh_sides": fresh_sides,
        "two_sided": two_sided,
        "positive_edge": positive_edge,
        "enough_volume": enough_volume,
        "qualified": qualified,
    }


def consecutive_chain(observations, max_gap_seconds):
    if not observations:
        return []
    obs = sorted(observations, key=lambda x: x.get("ts") or 0)
    chain = [obs[-1]]
    for prior in reversed(obs[:-1]):
        newest = chain[-1]
        if (newest.get("ts") or 0) - (prior.get("ts") or 0) > max_gap_seconds:
            break
        chain.append(prior)
    return list(reversed(chain))


def classify(observations, cfg):
    if not observations:
        return {"classification": "UNKNOWN", "auto_allocation_eligible": False}
    max_gap = int(cfg.get("maximum_snapshot_gap_seconds") or 720)
    chain = consecutive_chain(observations, max_gap)
    current = chain[-1]
    if not current.get("qualified"):
        return {
            "classification": "INVALID_SPREAD",
            "auto_allocation_eligible": False,
            "consecutive_snapshots": len(chain),
            "duration_minutes": round(((chain[-1]["ts"] - chain[0]["ts"]) / 60), 1) if len(chain) > 1 else 0.0,
            "qualified_ratio": round(sum(1 for x in chain if x.get("qualified")) / len(chain), 3),
            "reason": "Current spread fails freshness, two-sided flow, positive-edge, or minimum-volume validation.",
        }

    duration = ((chain[-1]["ts"] - chain[0]["ts"]) / 60) if len(chain) > 1 else 0.0
    qualified_ratio = sum(1 for x in chain if x.get("qualified")) / len(chain)
    rois = [float(x.get("after_tax_roi_pct")) for x in chain if x.get("qualified") and isinstance(x.get("after_tax_roi_pct"), (int, float)) and x.get("after_tax_roi_pct") > 0]
    median_roi = statistics.median(rois) if rois else None
    min_retention = float(cfg.get("minimum_roi_retention_vs_median") or 0.45)
    stable = bool(rois and median_roi and min(rois) >= median_roi * min_retention)

    min_snapshots = int(cfg.get("minimum_snapshots_persistent") or 3)
    min_minutes = float(cfg.get("minimum_minutes_persistent") or 10)
    persistent_ratio = float(cfg.get("minimum_qualified_ratio_persistent") or 0.67)
    repeat_snapshots = int(cfg.get("minimum_snapshots_repeatable") or 6)
    repeat_minutes = float(cfg.get("minimum_minutes_repeatable") or 30)
    repeat_ratio = float(cfg.get("minimum_qualified_ratio_repeatable") or 0.75)

    common = {
        "consecutive_snapshots": len(chain),
        "duration_minutes": round(duration, 1),
        "qualified_ratio": round(qualified_ratio, 3),
        "median_after_tax_roi_pct": round(median_roi, 3) if median_roi is not None else None,
        "minimum_after_tax_roi_pct": round(min(rois), 3) if rois else None,
        "spread_stable": stable,
    }

    if len(chain) < min_snapshots or duration < min_minutes:
        return {**common, "classification": "FLASH_SPREAD", "auto_allocation_eligible": False, "reason": "Insufficient consecutive snapshots or persistence duration."}
    if qualified_ratio < persistent_ratio or not stable:
        return {**common, "classification": "UNSTABLE_SPREAD", "auto_allocation_eligible": False, "reason": "Spread persisted in time but failed edge-retention or qualified-snapshot stability."}
    if len(chain) >= repeat_snapshots and duration >= repeat_minutes and qualified_ratio >= repeat_ratio:
        return {**common, "classification": "REPEATABLE_MARKET", "auto_allocation_eligible": True, "reason": "Repeated two-sided positive edge across the configured persistence window."}
    return {**common, "classification": "PERSISTENT_SPREAD", "auto_allocation_eligible": True, "reason": "At least three consecutive, two-sided qualified snapshots across the minimum persistence window."}


def main():
    now = int(time.time())
    packet = load_json(PACKET)
    cfg = (load_json(CFG).get("spread_persistence") or {})
    state = load_json(STATE, {"schema_version": 1, "items": {}})
    items = state.get("items") or {}
    lookback_seconds = int(float(cfg.get("lookback_minutes") or 120) * 60)
    retention_seconds = int(float(cfg.get("state_retention_hours") or 6) * 3600)
    max_obs = int(cfg.get("maximum_observations_per_item") or 30)

    current_rows = ((packet.get("engines") or {}).get("fast_flip_screen") or [])
    current_ids = set()
    for row in current_rows:
        item_id = row.get("id")
        if item_id is None:
            continue
        key = str(item_id)
        current_ids.add(key)
        record = items.get(key) or {"id": item_id, "name": row.get("name"), "observations": []}
        record["name"] = row.get("name") or record.get("name")
        observations = [x for x in (record.get("observations") or []) if isinstance(x.get("ts"), int) and now - x["ts"] <= lookback_seconds]
        observations.append(current_observation(row, now, cfg))
        record["observations"] = observations[-max_obs:]
        record["last_seen_ts"] = now
        record.update(classify(record["observations"], cfg))
        items[key] = record

    for key in list(items.keys()):
        last_seen = int(items[key].get("last_seen_ts") or 0)
        if last_seen and now - last_seen > retention_seconds:
            del items[key]
        elif key not in current_ids:
            observations = [x for x in (items[key].get("observations") or []) if isinstance(x.get("ts"), int) and now - x["ts"] <= lookback_seconds]
            items[key]["observations"] = observations[-max_obs:]
            items[key].update(classify(items[key]["observations"], cfg))

    counts = {}
    for row in items.values():
        label = row.get("classification") or "UNKNOWN"
        counts[label] = counts.get(label, 0) + 1

    output = {
        "schema_version": 1,
        "updated_at": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_unix": now,
        "snapshot_interval_target_seconds": 300,
        "class_counts": counts,
        "items": items,
        "rule": "Fast flips are not automatic-allocation eligible until a spread persists across at least three consecutive snapshots and the minimum time window with fresh HIGH/LOW prints, both sides trading, adequate volume and retained positive edge. REPEATABLE_MARKET requires a longer observation chain.",
    }
    save_json(STATE, output)
    print(f"Spread persistence: tracked={len(items)} classes={counts}")


if __name__ == "__main__":
    main()
