#!/usr/bin/env python3
import json
import time
from datetime import datetime, timezone

from optimize_allocation import annotate_repeatability, repeatability_summary

PACKET = "desk_packet.json"
CFG = "project/profit_engine.json"
STATE = "opportunity_book.json"
REAL = "real_execution_summary.json"


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


def opportunity_key(row):
    engine = str(row.get("engine") or "UNKNOWN")
    name = str(row.get("item_or_strategy") or "UNKNOWN")
    return f"{engine}::{name}"


def market_snapshot_unix(packet):
    generated = packet.get("generated_unix")
    core_age = (packet.get("quality") or {}).get("core_age_seconds")
    if isinstance(generated, int) and isinstance(core_age, (int, float)):
        return int(generated - max(0, core_age))
    return generated if isinstance(generated, int) else None


def book_config(cfg):
    return ((cfg.get("phase3") or {}).get("persistent_opportunity_book") or {})


def classify_record(record, cfg):
    repeat_cfg = ((cfg.get("phase3") or {}).get("repeatability_multiplier") or {})
    minimum = int(repeat_cfg.get("minimum_book_observations") or 6)
    minimum_consecutive = int(repeat_cfg.get("minimum_consecutive_observations") or 3)
    minimum_ratio = float(repeat_cfg.get("minimum_qualified_ratio") or 0.67)
    observations = int(record.get("observations") or 0)
    qualified = int(record.get("qualified_observations") or 0)
    consecutive = int(record.get("consecutive_observations") or 0)
    ratio = qualified / observations if observations else 0.0
    if observations < minimum:
        classification = "EARLY_SAMPLE"
    elif ratio >= minimum_ratio and consecutive >= minimum_consecutive:
        classification = "REPEATABLE"
    else:
        classification = "INCONSISTENT"
    score = min(100.0, 40 * min(1, observations / max(minimum, 1)) + 40 * ratio + 20 * min(1, consecutive / max(minimum_consecutive, 1)))
    return classification, round(score, 1), round(ratio, 4)


def update_book(state, rows, packet, cfg, now):
    state = dict(state or {})
    records = dict(state.get("records") or {})
    snapshot = market_snapshot_unix(packet)
    if snapshot is not None and snapshot == state.get("last_market_snapshot_unix"):
        return state, False

    bcfg = book_config(cfg)
    max_gap = int(bcfg.get("maximum_consecutive_gap_seconds") or 720)
    retention_seconds = float(bcfg.get("retention_hours") or 168) * 3600
    maximum_records = int(bcfg.get("maximum_records") or 500)
    seen = set()

    for row in rows:
        key = opportunity_key(row)
        seen.add(key)
        prior = dict(records.get(key) or {})
        last_snapshot = prior.get("last_snapshot_unix")
        consecutive = int(prior.get("consecutive_observations") or 0)
        if not isinstance(last_snapshot, int) or not isinstance(snapshot, int) or snapshot - last_snapshot > max_gap:
            consecutive = 0
        hurdle_pass = row.get("minimum_absolute_profit_hurdle_pass")
        qualified = hurdle_pass is True if hurdle_pass is not None else True
        observations = int(prior.get("observations") or 0) + 1
        qualified_observations = int(prior.get("qualified_observations") or 0) + int(qualified)
        hurdle_evaluations = int(prior.get("hurdle_evaluations") or 0) + int(hurdle_pass is not None)
        hurdle_passes = int(prior.get("hurdle_passes") or 0) + int(hurdle_pass is True)
        profit = int(row.get("expected_profit_at_capacity_gp") or 0)
        gph = int(row.get("expected_gp_per_hour") or 0)
        record = {
            **prior,
            "engine": row.get("engine"),
            "item_or_strategy": row.get("item_or_strategy"),
            "first_seen_unix": prior.get("first_seen_unix") or now,
            "last_seen_unix": now,
            "last_snapshot_unix": snapshot,
            "observations": observations,
            "consecutive_observations": consecutive + 1,
            "missed_snapshots": int(prior.get("missed_snapshots") or 0),
            "qualified_observations": qualified_observations,
            "hurdle_evaluations": hurdle_evaluations,
            "hurdle_passes": hurdle_passes,
            "cumulative_expected_profit_gp": int(prior.get("cumulative_expected_profit_gp") or 0) + profit,
            "cumulative_expected_gp_per_hour": int(prior.get("cumulative_expected_gp_per_hour") or 0) + gph,
            "latest": {
                "expected_profit_at_capacity_gp": profit,
                "expected_gp_per_hour": gph,
                "capacity_gp": row.get("capacity_gp"),
                "expected_hold_hours": row.get("expected_hold_hours"),
                "slot_bucket": row.get("slot_bucket"),
                "minimum_absolute_profit_hurdle_pass": hurdle_pass,
            },
        }
        classification, score, ratio = classify_record(record, cfg)
        record["repeatability_class"] = classification
        record["repeatability_score"] = score
        record["qualified_ratio"] = ratio
        record["hurdle_pass_ratio"] = round(hurdle_passes / hurdle_evaluations, 4) if hurdle_evaluations else None
        record["average_expected_profit_gp"] = int(record["cumulative_expected_profit_gp"] / observations)
        record["average_expected_gp_per_hour"] = int(record["cumulative_expected_gp_per_hour"] / observations)
        records[key] = record

    for key, record in list(records.items()):
        if key not in seen:
            record["consecutive_observations"] = 0
            record["missed_snapshots"] = int(record.get("missed_snapshots") or 0) + 1
        last_seen = record.get("last_seen_unix")
        if isinstance(last_seen, (int, float)) and now - last_seen > retention_seconds:
            records.pop(key, None)

    if len(records) > maximum_records:
        ordered = sorted(records.items(), key=lambda pair: pair[1].get("last_seen_unix") or 0, reverse=True)
        records = dict(ordered[:maximum_records])

    state.update({
        "schema_version": 1,
        "updated_at": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
        "last_market_snapshot_unix": snapshot,
        "cycles_observed": int(state.get("cycles_observed") or 0) + 1,
        "total_candidate_observations": int(state.get("total_candidate_observations") or 0) + len(rows),
        "records": records,
        "rule": "Persistent observations are keyed by engine and opportunity. Repeated packet builds from the same RuneLite market snapshot are deduplicated; user-confirmed executions remain stronger evidence.",
    })
    return state, True


def book_summary(state, cfg, updated):
    bcfg = book_config(cfg)
    records = list((state.get("records") or {}).values())
    minimum_cycles = int(bcfg.get("minimum_cycles_before_review") or 12)
    minimum_observations = int(bcfg.get("minimum_candidate_observations_before_review") or 50)
    top = sorted(records, key=lambda x: (x.get("repeatability_score") or 0, x.get("average_expected_gp_per_hour") or 0), reverse=True)
    counts = {}
    for record in records:
        label = record.get("repeatability_class") or "UNKNOWN"
        counts[label] = counts.get(label, 0) + 1
    cycles = int(state.get("cycles_observed") or 0)
    observations = int(state.get("total_candidate_observations") or 0)
    return {
        "status": bcfg.get("rollout_status") or "OBSERVATION_ONLY",
        "state_updated_this_run": updated,
        "cycles_observed": cycles,
        "total_candidate_observations": observations,
        "active_records": len(records),
        "class_counts": counts,
        "review_data_sufficient": cycles >= minimum_cycles and observations >= minimum_observations,
        "minimum_cycles_before_review": minimum_cycles,
        "minimum_candidate_observations_before_review": minimum_observations,
        "top_repeatability_records": [{
            "engine": x.get("engine"),
            "item_or_strategy": x.get("item_or_strategy"),
            "repeatability_class": x.get("repeatability_class"),
            "repeatability_score": x.get("repeatability_score"),
            "observations": x.get("observations"),
            "qualified_ratio": x.get("qualified_ratio"),
            "hurdle_pass_ratio": x.get("hurdle_pass_ratio"),
            "average_expected_profit_gp": x.get("average_expected_profit_gp"),
            "average_expected_gp_per_hour": x.get("average_expected_gp_per_hour"),
        } for x in top[:10]],
        "rule": state.get("rule"),
    }


def main():
    now = int(time.time())
    packet = load_json(PACKET)
    if not packet:
        raise RuntimeError("desk_packet.json missing")
    cfg = load_json(CFG)
    real = load_json(REAL)
    state = load_json(STATE, {"schema_version": 1, "records": {}})
    profit = packet.get("profit_layer") or {}
    rows = profit.get("capital_frontier") or []
    state, updated = update_book(state, rows, packet, cfg, now)
    summary = book_summary(state, cfg, updated)
    refreshed_rows = [annotate_repeatability(dict(row), cfg, state, real) for row in rows]
    repeat_summary = repeatability_summary(refreshed_rows, cfg, state, real)
    repeatability_by_key = {opportunity_key(row): row for row in refreshed_rows}
    for field in ("capital_frontier", "absolute_velocity_frontier", "marginal_capital_frontier", "ge_slot_hour_frontier", "capital_allocation_ladder"):
        for row in profit.get(field) or []:
            refreshed = repeatability_by_key.get(opportunity_key(row)) or {}
            for key, value in refreshed.items():
                if key.startswith("repeatability_"):
                    row[key] = value
    profit["persistent_opportunity_book"] = summary
    profit["repeatability_multiplier"] = repeat_summary
    hurdle = profit.get("minimum_absolute_profit_hurdles") or {}
    hurdle.update({
        "cumulative_observation_cycles": summary["cycles_observed"],
        "cumulative_candidate_observations": summary["total_candidate_observations"],
        "promotion_data_sufficient": summary["review_data_sufficient"],
    })
    profit["minimum_absolute_profit_hurdles"] = hurdle
    upgrade = profit.get("execution_upgrade_state") or {}
    upgrade["persistent_opportunity_book"] = summary["status"]
    profit["execution_upgrade_state"] = upgrade
    packet["profit_layer"] = profit
    save_json(STATE, state)
    save_json(PACKET, packet)
    print(
        f"Opportunity book: updated={updated} cycles={summary['cycles_observed']} "
        f"observations={summary['total_candidate_observations']} records={summary['active_records']}"
    )


if __name__ == "__main__":
    main()
