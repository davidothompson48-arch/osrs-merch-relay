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
        "actionable_count": snapshot.get("actionable_count"),
        "candidate_count": snapshot.get("candidate_count"),
        "missing_market_rows": snapshot.get("missing_market_rows") or [],
        "top_candidates": snapshot.get("top_candidates") or [],
        "allocation_note": snapshot.get("allocation_note"),
    }


def main():
    snapshot = load_json(SNAPSHOT)
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
    print(f"Injected speculative_park into {DEEP} and {LITE}; top={len(block['top_candidates'])}")


if __name__ == "__main__":
    main()
