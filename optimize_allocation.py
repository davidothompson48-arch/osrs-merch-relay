#!/usr/bin/env python3
import json

PACKET = "desk_packet.json"


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")


def positive(x):
    return isinstance(x, (int, float)) and x > 0


def row_key(x):
    return (x.get("engine"), x.get("name") or x.get("strategy") or x.get("item_or_strategy"))


def sanitized_rows(profit):
    rows = []
    for group in ("fast_flip_capacity_velocity", "evergreen_capacity_velocity", "conversion_capacity_velocity"):
        for x in profit.get(group) or []:
            profit_gp = x.get("expected_profit_at_capacity_gp")
            if profit_gp is None:
                profit_gp = x.get("player_time_adjusted_profit_gp")
            gph = x.get("expected_gp_per_hour")
            roi = x.get("expected_after_tax_roi_pct")
            hold = x.get("expected_hold_hours")
            capacity = x.get("capacity_gp")
            if not positive(profit_gp) or not positive(gph) or not positive(capacity) or not positive(hold):
                continue
            validation = x.get("validation_flag")
            if validation == "ANOMALOUS_PATIENT_MARGIN_REQUIRES_VALIDATION":
                continue
            # Dose ratios can show enormous apparent margins from asynchronous or
            # thin 1-dose prints. Force human validation before allowing >15% into
            # the automatic allocation frontier.
            if x.get("type") == "dose_decant":
                max_raw = max(v for v in (x.get("patient_roi_pct"), x.get("immediate_roi_pct"), 0) if isinstance(v, (int, float)))
                if max_raw > 15:
                    continue
            roi_per_hour = (roi / hold) if isinstance(roi, (int, float)) else None
            rows.append({
                "engine": x.get("engine"),
                "item_or_strategy": x.get("name") or x.get("strategy"),
                "profit_efficiency_score": x.get("profit_efficiency_score"),
                "capacity_gp": int(capacity),
                "expected_profit_at_capacity_gp": int(profit_gp),
                "expected_gp_per_hour": int(gph),
                "expected_after_tax_roi_pct": roi,
                "expected_hold_hours": hold,
                "expected_roi_per_capital_hour_pct": round(roi_per_hour, 5) if roi_per_hour is not None else None,
                "execution_probability_heuristic": x.get("execution_probability_heuristic"),
                "slippage_risk": x.get("slippage_risk"),
                "player_time_hours": x.get("player_time_hours"),
                "source_key": row_key(x)
            })
    # Deduplicate same engine/strategy if a future packet includes overlapping views.
    best = {}
    for x in rows:
        key = x["source_key"]
        prior = best.get(key)
        if prior is None or x["expected_gp_per_hour"] > prior["expected_gp_per_hour"]:
            best[key] = x
    return list(best.values())


def main():
    packet = load(PACKET)
    profit = packet.get("profit_layer") or {}
    rows = sanitized_rows(profit)

    absolute = sorted(rows, key=lambda x: (x.get("expected_gp_per_hour") or 0, x.get("expected_profit_at_capacity_gp") or 0), reverse=True)
    marginal = sorted(rows, key=lambda x: (x.get("expected_roi_per_capital_hour_pct") or -999, x.get("expected_gp_per_hour") or 0), reverse=True)
    balanced = sorted(rows, key=lambda x: (x.get("profit_efficiency_score") or 0, x.get("expected_gp_per_hour") or 0), reverse=True)

    cumulative = 0
    ladder = []
    for rank, x in enumerate(marginal, 1):
        cumulative += x["capacity_gp"]
        ladder.append({**x, "rank": rank, "cumulative_capacity_gp": cumulative})

    profit["absolute_velocity_frontier"] = absolute[:15]
    profit["marginal_capital_frontier"] = marginal[:15]
    profit["capital_allocation_ladder"] = ladder[:15]
    profit["capital_frontier"] = balanced[:15]
    profit["allocation_rule"] = "With unknown liquid cash, deploy incrementally down the marginal-capital ladder: fill the highest expected return-per-capital-hour tranche only to modeled capacity, then move to the next. Absolute GP/hour is shown separately so small high-efficiency trades do not hide larger scalable opportunities."

    # Rebuild slot priority from sanitized opportunities and keep only meaningful slot users.
    slot = profit.get("ge_slot_optimizer") or {}
    free_upper = int(slot.get("modeled_free_slots_upper_bound") or 0)
    minimum_slot_gph = 50000
    slot_rows = [x for x in absolute if (x.get("expected_gp_per_hour") or 0) >= minimum_slot_gph]
    slot["recommended_slot_priority"] = [{
        "engine": x["engine"], "item_or_strategy": x["item_or_strategy"],
        "slot_efficiency_gp_per_hour": x["expected_gp_per_hour"],
        "capacity_gp": x["capacity_gp"],
        "expected_profit_at_capacity_gp": x["expected_profit_at_capacity_gp"],
        "profit_efficiency_score": x.get("profit_efficiency_score")
    } for x in slot_rows[:free_upper]]
    profit["ge_slot_optimizer"] = slot

    packet["profit_layer"] = profit
    save(PACKET, packet)
    print(f"Optimized allocation frontiers: valid={len(rows)} marginal={len(ladder)}")


if __name__ == "__main__":
    main()
