#!/usr/bin/env python3
import json

SRC = "desk_packet.json"
OUT = "desk_packet_lite.json"


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compact_avg(row):
    if not isinstance(row, dict):
        return {}
    return {k: row.get(k) for k in ("avgHighPrice", "avgLowPrice", "highPriceVolume", "lowPriceVolume")}


def compact_portfolio(row):
    vol = row.get("volume") or {}
    one = vol.get("1h") or {}
    return {
        "item": row.get("item"), "item_id": row.get("item_id"), "quantity": row.get("quantity"),
        "basis_each": row.get("basis_each"), "basis_total": row.get("basis_total"),
        "current": row.get("current"), "freshness": row.get("freshness"),
        "1h": compact_avg((row.get("averages") or {}).get("1h")),
        "24h": compact_avg((row.get("averages") or {}).get("24h")),
        "movementPct": row.get("movementPct") or {},
        "highSideShare1h": vol.get("highSideShare1h") if "highSideShare1h" in vol else (one.get("high") / one.get("total") if one.get("total") else None),
        "oneHourVolume": one.get("total"), "liquidity": row.get("liquidity"), "buy_limit": row.get("buy_limit"),
        "gross_pnl_high": row.get("gross_pnl_high"), "modeled_after_tax_pnl_high": row.get("modeled_after_tax_pnl_high"),
        "rating": row.get("rating"), "history_complete": row.get("history_complete")
    }


def compact_sector(rows):
    out = []
    for x in rows:
        one = x.get("oneHour") or {}
        cur = x.get("current") or {}
        out.append({
            "id": x.get("id"), "name": x.get("name"),
            "high": cur.get("high"), "low": cur.get("low"),
            "highAgeSeconds": cur.get("highAgeSeconds"), "lowAgeSeconds": cur.get("lowAgeSeconds"),
            "1hHigh": one.get("avgHighPrice"), "1hLow": one.get("avgLowPrice"),
            "1hHighVol": one.get("highPriceVolume"), "1hLowVol": one.get("lowPriceVolume")
        })
    return out


def main():
    p = load(SRC)
    tax = p.get("tax_policy") or {}
    engines = p.get("engines") or {}
    catalyst = p.get("catalyst_state") or {}
    sectors = p.get("sectors") or {}

    lite = {
        "schema_version": 1,
        "generated_at": p.get("generated_at"), "generated_unix": p.get("generated_unix"),
        "source": p.get("source"), "quality": p.get("quality"),
        "tax_policy": {"verified_at_utc": tax.get("verified_at_utc"), "rate": tax.get("rate"),
                       "cap_gp_per_item": tax.get("cap_gp_per_item"), "rounding": tax.get("rounding"), "source": tax.get("source")},
        "portfolio": [compact_portfolio(x) for x in p.get("portfolio", [])],
        "portfolio_summary": p.get("portfolio_summary"),
        "open_offers_unconfirmed": p.get("open_offers_unconfirmed"),
        "engines": {
            "fast_flip_screen": (engines.get("fast_flip_screen") or [])[:8],
            "short_term_momentum": (engines.get("short_term_momentum") or [])[:5],
            "broad_oversold_screen": (engines.get("broad_oversold_screen") or [])[:5],
            "extreme_flow_screen": (engines.get("extreme_flow_screen") or [])[:5],
            "evergreen_staples": {
                "generated_at": (engines.get("evergreen_staples") or {}).get("generated_at"),
                "candidate_count": (engines.get("evergreen_staples") or {}).get("candidate_count"),
                "top_candidates": ((engines.get("evergreen_staples") or {}).get("top_candidates") or [])[:8]
            },
            "conversions": (engines.get("conversions") or [])[:4]
        },
        "sectors": {
            key: compact_sector(sectors.get(key) or [])
            for key in ("breaker_competing_runes", "fractured_archive_ranged", "prayer", "cox_rewards", "crush_inquisitor", "elemental_magic")
            if sectors.get(key)
        },
        "previous_runtime": p.get("previous_runtime"),
        "catalyst_state": {
            "watch_last_checked_utc": catalyst.get("watch_last_checked_utc"),
            "watch_last_material_change_utc": catalyst.get("watch_last_material_change_utc"),
            "watch_status": catalyst.get("watch_status"),
            "database_updated_at_utc": catalyst.get("database_updated_at_utc"),
            "records": catalyst.get("records") or [],
            "probability_models": catalyst.get("probability_models") or []
        },
        "deep_packet": "desk_packet.json",
        "rule": "Routine desk runs should use this lite packet only. Fetch the deep packet solely for missing fields or a user-requested deep dive."
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(lite, f, separators=(",", ":"))
        f.write("\n")
    print(f"Wrote {OUT}; portfolio={len(lite['portfolio'])}; fast={len(lite['engines']['fast_flip_screen'])}")


if __name__ == "__main__":
    main()
