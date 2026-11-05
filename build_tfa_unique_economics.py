#!/usr/bin/env python3
"""Fractured Archive unique supply scenarios and after-tax reward EV.

Uses Jagex mechanics configured in project/tfa_unique_mechanics.json and
RuneLite/OSRS Wiki item prices from market_universe. This is NOT a projection
of how many raids the playerbase will complete, or an hourly income figure.
"""
import glob
import json
import time
from datetime import datetime, timezone
from build_swing_trade_gate import tax

CONFIG = "project/tfa_unique_mechanics.json"
TAX = "project/tax_policy.json"
OUT = "tfa_unique_economics.json"


def read_json(path):
    with open(path, encoding="utf8") as f:
        return json.load(f)


def write_json(path, obj):
    with open(path, "w", encoding="utf8") as f:
        json.dump(obj, f, separators=(",", ":"))
        f.write("\n")


def team_probability(group_size, config):
    if not isinstance(group_size, int) or not 1 <= group_size <= 8:
        raise ValueError("Team size must be 1 through 8")
    bonus = 1 + float(config["additional_player_bonus_beyond_two_pct"]) / 100 * max(0, group_size-2)
    return min(1, bonus / float(config["team_unique_base_denominator"]))


def expected_uniques_per_n_team_completions(team_size, completions, config):
    if completions < 0:
        raise ValueError("completions must be nonnegative")
    p = team_probability(team_size, config)
    total_weight = sum(x["weight"] for x in config["unique_rewards"])
    return {
        x["name"]: round(completions * p * x["weight"] / total_weight, 3)
        for x in config["unique_rewards"]
    }


def analyze(config, tax_config, item_rows, now):
    unique_items = config.get("unique_rewards") or []
    assert unique_items and sum(x["weight"] for x in unique_items) == 15, "Unexpected TFA unique weightings"
    values = []
    incomplete = []
    for item in unique_items:
        row = item_rows.get(str(item["id"])) or {}
        cur = row.get("current") or {}
        high, low, when_low = cur.get("high"), cur.get("low"), cur.get("lowTime")
        when_high = cur.get("highTime")
        is_valid = (
            isinstance(high, (int, float)) and isinstance(low, (int, float))
            and 0 < low <= high
            and isinstance(when_low, int) and isinstance(when_high, int)
            and 0 <= now - when_low <= 7200 and 0 <= now - when_high <= 7200
        )
        if not is_valid:
            incomplete.append(item["name"])
            continue
        after_tax_low = int(low) - tax(int(low), item["name"], tax_config)
        values.append({
            "item": item["name"],
            "item_id": item["id"],
            "unique_weight": item["weight"],
            "weight_share_pct": round(item["weight"] / 15 * 100, 3),
            "latest_instant_sell_gp": int(low),
            "net_after_tax_sell_gp": after_tax_low,
            "quote_low_age_seconds": now - when_low,
            "total_24h_transactions_both_sides": int(((row.get("24h") or {}).get("highPriceVolume") or 0)+((row.get("24h") or {}).get("lowPriceVolume") or 0)),
        })
    if incomplete:
        return {"status": "INCOMPLETE_PRICE_TAPE", "missing_or_stale": incomplete, "rewards": values, "groups": []}

    ev_weighted = sum(x["unique_weight"] * x["net_after_tax_sell_gp"] for x in values)/15
    groups = []
    for team_size in config["included_group_sizes"]:
        p = team_probability(team_size, config)
        groups.append({
            "team_size": team_size,
            "deathless_team_unique_probability_pct": round(p * 100, 4),
            "implied_team_raids_per_unique": round(1/p, 3),
            "team_expected_unique_gp_per_raid_after_tax": round(ev_weighted * p),
            "illustrative_even_split_unique_gp_per_player_per_raid": round(ev_weighted * p / team_size),
            "expected_uniques_per_1000_team_completions": expected_uniques_per_n_team_completions(team_size, 1000, config),
        })
    total_weighted_value = sum(x["unique_weight"] * x["net_after_tax_sell_gp"] for x in values)
    for x in values:
        x["share_of_total_expected_unique_gp_pct"] = round(
            x["unique_weight"] * x["net_after_tax_sell_gp"] / total_weighted_value * 100, 2
        ) if total_weighted_value else 0
    return {
        "status": "READY",
        "missing_or_stale": [],
        "weighted_unique_net_value_gp": round(ev_weighted),
        "rewards": values,
        "groups": groups,
    }


def main():
    config = read_json(CONFIG)
    tax_config = read_json(TAX)
    now = int(time.time())
    mapping = {}
    for path in glob.glob("market_universe/*.json"):
        if path.endswith("index.json"):
            continue
        block = read_json(path)
        for x in block.get("items", []):
            if x.get("id") is not None:
                mapping[str(x["id"])] = x
    analyzed = analyze(config, tax_config, mapping, now)
    output = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_mechanics": config["source"],
        "source_prices": "prices.runescape.wiki OSRS RuneLite via GitHub market_universe",
        "mechanics_as_of": config["mechanics_as_of"],
        "balance_change_pending": True,
        "not_trade_advice": True,
        "notes": config["assumptions"],
        **analyzed,
    }
    write_json(OUT, output)
    for path in ("desk_packet.json", "desk_packet_lite.json"):
        try:
            packet = read_json(path)
            packet["tfa_unique_economics"] = {
                "status": output["status"],
                "generated_at": output["generated_at"],
                "mechanics_as_of": output["mechanics_as_of"],
                "balance_change_pending": True,
                "groups": output.get("groups") or [],
                "rewards": output.get("rewards") or [],
                "full_report": OUT,
                "notes": output["notes"],
            }
            write_json(path, packet)
        except (OSError, ValueError):
            pass
    print("TFA unique economics:", output["status"], "rewards", len(output["rewards"]))


if __name__ == "__main__":
    main()
