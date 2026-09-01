#!/usr/bin/env python3
import json

SNAPSHOT = "speculative_park_snapshot.json"
DEEP = "desk_packet.json"
LITE = "desk_packet_lite.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")


def sanitize_candidate(row):
    row = dict(row)
    market = dict(row.get("market") or {})
    high = market.get("high")
    low = market.get("low")
    fresh = market.get("freshness")
    crossed = isinstance(high, (int, float)) and isinstance(low, (int, float)) and high < low

    if crossed:
        row["status"] = "WATCH_ASYNC_PRINTS"
        row["execution_gate"] = "REJECT_ASYNC_CROSSED_PRINTS"
    elif row.get("status") == "PARK_NOW" and fresh != "FRESH":
        row["status"] = "DEEP_BID"
        row["execution_gate"] = "NO_MARKET_BUY_WITHOUT_FRESH_PRINTS"
    else:
        row["execution_gate"] = "CLEAR" if row.get("status") in ("PARK_NOW", "DEEP_BID") else "WATCH_ONLY"
    row["market"] = market
    return row


def sanitize_snapshot(snapshot):
    snapshot = dict(snapshot)
    snapshot["top_candidates"] = [sanitize_candidate(x) for x in (snapshot.get("top_candidates") or [])]
    snapshot["all_candidates"] = [sanitize_candidate(x) for x in (snapshot.get("all_candidates") or [])]
    snapshot["actionable_count"] = sum(
        1 for x in snapshot["all_candidates"] if x.get("status") in ("PARK_NOW", "DEEP_BID")
    )
    snapshot["execution_rule"] = "PARK_NOW requires fresh, non-crossed RuneLite prints. Crossed/asynchronous current prints are watch-only; staleish candidates may remain patient deep bids but not market buys."
    return snapshot


def compact(snapshot):
    return {
        "schema_version": snapshot.get("schema_version"),
        "generated_at": snapshot.get("generated_at"),
        "generated_unix": snapshot.get("generated_unix"),
        "source": snapshot.get("source"),
        "enabled": snapshot.get("enabled"),
        "rollout_status": snapshot.get("rollout_status"),
        "allocation_authoritative": snapshot.get("allocation_authoritative"),
        "cash_competes": snapshot.get("cash_competes"),
        "objective": snapshot.get("objective"),
        "portfolio_policy": snapshot.get("portfolio_policy"),
        "execution_rule": snapshot.get("execution_rule"),
        "actionable_count": snapshot.get("actionable_count"),
        "candidate_count": snapshot.get("candidate_count"),
        "missing_market_rows": snapshot.get("missing_market_rows") or [],
        "top_candidates": snapshot.get("top_candidates") or [],
        "allocation_note": snapshot.get("allocation_note"),
    }


def main():
    snapshot = sanitize_snapshot(load_json(SNAPSHOT))
    save_json(SNAPSHOT, snapshot)
    block = compact(snapshot)
    for path in (DEEP, LITE):
        packet = load_json(path)
        packet["speculative_park"] = block
        if path == LITE:
            packet["rule"] = (
                (packet.get("rule") or "")
                + " Speculative parks are advisory catalyst-backed parking ideas; cash remains valid and the speculative layer has no allocation authority unless explicitly promoted."
            ).strip()
        save_json(path, packet)
    print(f"Injected speculative_park into {DEEP} and {LITE}; top={len(block['top_candidates'])}; actionable={block['actionable_count']}")


if __name__ == "__main__":
    main()
