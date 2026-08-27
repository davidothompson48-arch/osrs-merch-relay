#!/usr/bin/env python3
import json
import os

PACKET = "desk_packet.json"


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")


def main():
    packet = load(PACKET)
    if not packet:
        raise RuntimeError("desk_packet.json missing")
    catalysts = load("project/catalyst_database.json")
    probabilities = load("project/probability_models.json")
    baseline = load("project/news_baseline.json")
    watch = load("project/catalyst_watch_state.json")

    packet["catalyst_state"] = {
        "watch_last_checked_utc": watch.get("last_checked_utc"),
        "watch_last_material_change_utc": watch.get("last_material_change_utc"),
        "watch_status": watch.get("status") or "UNKNOWN",
        "database_updated_at_utc": catalysts.get("updated_at_utc"),
        "records": [{
            "id": x.get("id"), "latest_evidence_date": x.get("latest_evidence_date"),
            "status": x.get("status"), "credibility": x.get("credibility"),
            "confidence_0_100": x.get("confidence_0_100"), "affected_items": x.get("affected_items"),
            "summary": x.get("summary"), "market_pricing_assessment": x.get("market_pricing_assessment")
        } for x in catalysts.get("records", [])],
        "probability_models": [{
            "id": m.get("id"), "theme": m.get("theme"), "confidence": m.get("confidence"),
            "scenarios": [{"name": s.get("name"), "probability_pct": s.get("probability_pct"),
                           "beneficiaries": s.get("beneficiaries")} for s in m.get("scenarios", [])]
        } for m in probabilities.get("models", [])],
        "baseline_updated_at_utc": baseline.get("updated_at_utc"),
        "latest_known_official": (baseline.get("known_official_items") or [])[:5]
    }
    save(PACKET, packet)
    print("Embedded compact catalyst state into desk_packet.json")


if __name__ == "__main__":
    main()
