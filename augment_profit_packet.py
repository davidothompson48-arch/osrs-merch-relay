#!/usr/bin/env python3
import glob
import json
import math
import statistics
import time
from datetime import datetime, timezone

PACKET = "desk_packet.json"
CFG = "project/profit_engine.json"
LIFECYCLE = "project/position_lifecycle.json"
SHADOW = "shadow_book_summary.json"
CONVERSIONS = "project/known_conversions.json"


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


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def midpoint(high, low):
    vals = [x for x in (high, low) if isinstance(x, (int, float)) and x > 0]
    return sum(vals) / len(vals) if vals else None


def avg_mid(row):
    if not isinstance(row, dict):
        return None
    return midpoint(row.get("avgHighPrice"), row.get("avgLowPrice"))


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def tax_for(name, price, tax_policy):
    if not isinstance(price, (int, float)) or price <= 0:
        return None
    if name in set(tax_policy.get("exempt_items") or []):
        return 0
    rate = float(tax_policy.get("rate") or 0)
    cap = int(tax_policy.get("cap_gp_per_item") or 0)
    value = math.floor(price * rate)
    return min(value, cap) if cap > 0 else value


def market_maps():
    by_name, by_id = {}, {}
    for path in glob.glob("market_universe/*.json"):
        if path.endswith("index.json"):
            continue
        p = load_json(path)
        for row in p.get("items", []):
            if row.get("name"):
                by_name[row["name"]] = row
            if row.get("id") is not None:
                by_id[str(row["id"])] = row
    return by_name, by_id


def freshness_from_times(row, now):
    hi = row.get("highTime")
    lo = row.get("lowTime")
    ages = [now - x for x in (hi, lo) if isinstance(x, int)]
    if len(ages) < 2:
        return "INCOMPLETE"
    worst = max(ages)
    if worst <= 300:
        return "FRESH"
    if worst <= 1800:
        return "USABLE"
    if worst <= 7200:
        return "STALEISH"
    return "STALE"


def slippage_label(participation_pct, cfg):
    labels = cfg.get("capacity_model", {}).get("slippage_labels") or {}
    low = float(labels.get("LOW_max_participation_pct") or 5)
    med = float(labels.get("MEDIUM_max_participation_pct") or 10)
    if participation_pct <= low:
        return "LOW"
    if participation_pct <= med:
        return "MEDIUM"
    return "HIGH"


def learning_adjustment(shadow, engine):
    row = (shadow.get("score_adjustments") or {}).get(engine) or {}
    return int(row.get("score_adjustment_points") or 0)


def profit_score(gph, roi, capacity_gp, exec_prob, passive_factor, learn_adj=0):
    gph = max(0.0, float(gph or 0))
    roi = max(0.0, float(roi or 0))
    capacity_gp = max(0.0, float(capacity_gp or 0))
    exec_prob = clamp(float(exec_prob or 0), 0, 1)
    passive_factor = clamp(float(passive_factor or 0), 0, 1)
    gph_pts = 35 * (1 - math.exp(-gph / 1_000_000))
    roi_pts = min(20, roi * 4)
    cap_pts = 15 * (1 - math.exp(-capacity_gp / 20_000_000))
    exec_pts = 20 * exec_prob
    time_pts = 10 * passive_factor
    return round(clamp(gph_pts + roi_pts + cap_pts + exec_pts + time_pts + learn_adj, 0, 100), 1)


def fast_profit_rows(packet, cfg, shadow, now):
    rows = []
    participation_map = cfg.get("capacity_model", {}).get("participation_fraction_of_1h_volume_by_liquidity") or {}
    fresh_factor_map = cfg.get("execution_model", {}).get("freshness_factor") or {}
    base_hold = float(cfg.get("execution_model", {}).get("fast_flip_base_hold_hours") or 2)
    for x in ((packet.get("engines") or {}).get("fast_flip_screen") or []):
        high, low = x.get("high"), x.get("low")
        if not all(isinstance(v, (int, float)) and v > 0 for v in (high, low)):
            continue
        edge = x.get("afterTaxSpreadGp")
        roi = x.get("afterTaxSpreadRoiPct")
        vol = int(x.get("oneHourVolume") or 0)
        if not isinstance(edge, (int, float)) or edge <= 0 or vol <= 0:
            continue
        liquidity = x.get("liquidity") or "UNKNOWN"
        frac = float(participation_map.get(liquidity, participation_map.get("UNKNOWN", 0.03)))
        units = max(1, math.floor(vol * frac))
        limit = x.get("buyLimit")
        if isinstance(limit, int) and limit > 0:
            units = min(units, limit)
        cap_gp = units * low
        participation_pct = 100 * units / vol if vol else 0
        high_share = x.get("highSideShare")
        if not isinstance(high_share, (int, float)):
            high_share = 0.5
        seller_share = 1 - high_share
        entry_fill = clamp(0.22 + 1.15 * seller_share, 0.18, 0.90)
        exit_fill = clamp(0.22 + 1.00 * high_share, 0.18, 0.94)
        fresh = freshness_from_times(x, now)
        fresh_factor = float(fresh_factor_map.get(fresh, 0.45))
        execution = clamp(entry_fill * exit_fill * fresh_factor, 0, 0.9)
        theoretical_profit = edge * units
        expected_profit = theoretical_profit * execution
        expected_gph = expected_profit / max(base_hold, 0.25)
        expected_roi = expected_profit / cap_gp * 100 if cap_gp else None
        learn = learning_adjustment(shadow, "fast_flip")
        score = profit_score(expected_gph, roi, cap_gp, execution, 1.0, learn)
        rows.append({"engine":"fast_flip","id":x.get("id"),"name":x.get("name"),"current_high":high,"current_low":low,"raw_after_tax_roi_pct":roi,"modeled_capacity_units":units,"capacity_gp":int(cap_gp),"market_participation_pct_1h":round(participation_pct,2),"slippage_risk":slippage_label(participation_pct,cfg),"modeled_entry_fill_factor":round(entry_fill,3),"modeled_exit_factor":round(exit_fill,3),"freshness":fresh,"execution_probability_heuristic":round(execution,3),"theoretical_profit_at_capacity_gp":int(theoretical_profit),"expected_profit_at_capacity_gp":int(expected_profit),"expected_after_tax_roi_pct":round(expected_roi,3) if expected_roi is not None else None,"expected_hold_hours":base_hold,"expected_gp_per_hour":int(expected_gph),"slot_efficiency_gp_per_hour":int(expected_gph),"player_time_hours":0,"player_time_adjusted_profit_gp":int(expected_profit),"learning_adjustment_points":learn,"profit_efficiency_score":score,"source_candidate":x})
    rows.sort(key=lambda r: (r["profit_efficiency_score"], r["expected_gp_per_hour"]), reverse=True)
    return rows


def evergreen_profit_rows(packet, cfg, shadow):
    rows = []
    tax_policy = packet.get("tax_policy") or {}
    fraction = float(cfg.get("capacity_model", {}).get("evergreen_fraction_of_24h_volume") or 0.015)
    hold = float(cfg.get("execution_model", {}).get("evergreen_base_hold_hours") or 72)
    for x in (((packet.get("engines") or {}).get("evergreen_staples") or {}).get("top_candidates") or []):
        cur = x.get("current") or {}
        rng = x.get("range") or {}
        demand = x.get("demand") or {}
        entry = cur.get("high") or cur.get("mid")
        target = rng.get("thirtyDayMedian") or rng.get("sevenDayMedian")
        if not isinstance(entry, (int, float)) or not isinstance(target, (int, float)) or entry <= 0:
            continue
        tax = tax_for(x.get("name"), target, tax_policy)
        if tax is None:
            continue
        net_target = target - tax
        profit_unit = net_target - entry
        vol24 = int(demand.get("twentyFourHourVolume") or 0)
        units = max(1, math.floor(vol24 * fraction)) if vol24 else 1
        limit = x.get("buyLimit")
        if isinstance(limit, int) and limit > 0:
            units = min(units, limit)
        cap_gp = units * entry
        status = x.get("status")
        confidence = 0.68 if status == "BUY_ZONE_CANDIDATE" else 0.42
        if x.get("fallingKnife"):
            confidence *= 0.35
        if x.get("stabilized"):
            confidence = min(0.82, confidence + 0.10)
        raw_roi = profit_unit / entry * 100
        expected_profit = max(0, profit_unit * units * confidence)
        expected_gph = expected_profit / max(hold, 1)
        expected_roi = expected_profit / cap_gp * 100 if cap_gp else None
        learn = learning_adjustment(shadow, "evergreen")
        score = profit_score(expected_gph, max(0, raw_roi), cap_gp, confidence, 1.0, learn)
        rows.append({"engine":"evergreen","id":x.get("id"),"name":x.get("name"),"status":status,"current_entry_reference":entry,"target_30d_or_7d_median":target,"raw_mean_reversion_roi_after_tax_pct":round(raw_roi,3),"modeled_capacity_units":units,"capacity_gp":int(cap_gp),"execution_probability_heuristic":round(confidence,3),"expected_profit_at_capacity_gp":int(expected_profit),"expected_after_tax_roi_pct":round(expected_roi,3) if expected_roi is not None else None,"expected_hold_hours":hold,"expected_gp_per_hour":int(expected_gph),"slot_efficiency_gp_per_hour":int(expected_gph),"player_time_hours":0,"player_time_adjusted_profit_gp":int(expected_profit),"learning_adjustment_points":learn,"profit_efficiency_score":score,"discount_to_30d_median_pct":rng.get("discountTo30dMedianPct"),"thirty_day_percentile":rng.get("thirtyDayPercentile"),"source_candidate":x})
    rows.sort(key=lambda r: (r["profit_efficiency_score"], r["expected_gp_per_hour"]), reverse=True)
    return rows


def conversion_key(row):
    inputs = row.get("inputs") or []
    return "+".join(f"{x.get('quantity',1)}x{x.get('item')}" for x in inputs) + f"->{row.get('output')}"


def conversion_config_map():
    cfg = load_json(CONVERSIONS)
    out = {}
    for row in cfg.get("conversions", []):
        inputs = row.get("inputs")
        if not inputs:
            inputs = [{"item": row.get("input"), "quantity": row.get("input_quantity", 1)}]
        key = "+".join(f"{x.get('quantity',1)}x{x.get('item')}" for x in inputs) + f"->{row.get('output')}"
        out[key] = row
    return out, cfg.get("sets") or []


def conversion_profit_rows(packet, cfg, shadow, by_name):
    rows = []
    configs, _ = conversion_config_map()
    frac = float(cfg.get("capacity_model", {}).get("conversion_output_fraction_of_24h_volume") or 0.03)
    shadow_rate = float(cfg.get("player_time", {}).get("shadow_value_gp_per_hour") or 0)
    attention_map = cfg.get("player_time", {}).get("attention_factors") or {}
    default_attention = cfg.get("player_time", {}).get("default_manual_attention") or "MEDIUM"
    base_exit = float(cfg.get("execution_model", {}).get("conversion_base_exit_hours") or 4)
    held = {x.get("item"): int(x.get("quantity") or 0) for x in packet.get("portfolio", [])}
    for x in ((packet.get("engines") or {}).get("conversions") or []):
        key = conversion_key(x)
        meta = configs.get(key) or {}
        patient = x.get("patient") or {}
        immediate = x.get("immediate") or {}
        patient_roi = patient.get("roi_pct")
        immediate_roi = immediate.get("roi_pct")
        if not isinstance(patient_roi, (int, float)) and not isinstance(immediate_roi, (int, float)):
            continue
        output = x.get("output")
        output_qty = int(x.get("output_quantity") or 1)
        out_row = by_name.get(output) or {}
        day = out_row.get("24h") or {}
        out_vol24 = int(day.get("highPriceVolume") or 0) + int(day.get("lowPriceVolume") or 0)
        units_by_output = max(1, math.floor(out_vol24 * frac / max(output_qty, 1))) if out_vol24 else 1
        input_caps = []
        for inp in x.get("inputs") or []:
            name = inp.get("item")
            qty = int(inp.get("quantity") or 1)
            m = by_name.get(name) or {}
            limit = m.get("buyLimit")
            held_units = held.get(name, 0)
            if isinstance(limit, int) and limit > 0:
                input_caps.append((limit + held_units) // max(qty, 1))
            elif held_units:
                input_caps.append(held_units // max(qty, 1))
        capacity_units = units_by_output
        if input_caps:
            capacity_units = min(capacity_units, max(1, min(input_caps)))
        capacity_units = max(1, capacity_units)
        if isinstance(immediate_roi, (int, float)) and immediate_roi > 0:
            mode = "IMMEDIATE"; profit_per = immediate.get("profit_gp") or 0; input_cost_per = immediate.get("input_cost") or 0; execution = 0.86
        else:
            mode = "PATIENT"; profit_per = patient.get("profit_gp") or 0; input_cost_per = patient.get("input_cost") or 0; execution = 0.58
        raw_profit = float(profit_per) * capacity_units
        capacity_gp = float(input_cost_per) * capacity_units
        process_seconds = meta.get("process_time_seconds_approx")
        active_hours = (float(process_seconds) * capacity_units / 3600) if isinstance(process_seconds, (int, float)) and process_seconds > 0 else 0.0
        attention = meta.get("player_time_attention") or default_attention
        attention_factor = float(attention_map.get(attention, attention_map.get(default_attention, 0.6)))
        player_cost = active_hours * shadow_rate * attention_factor
        expected_raw = raw_profit * execution
        adjusted = expected_raw - player_cost
        elapsed = max(base_exit, active_hours if active_hours > 0 else 0)
        gph = adjusted / max(elapsed, 0.25)
        adjusted_roi = adjusted / capacity_gp * 100 if capacity_gp else None
        learn = learning_adjustment(shadow, "conversion")
        score = profit_score(max(0,gph), max(0,adjusted_roi or 0), capacity_gp, execution, 1-attention_factor, learn)
        rows.append({"engine":"conversion","strategy":key,"type":x.get("type"),"output":output,"ranking_mode":mode,"patient_roi_pct":patient_roi,"immediate_roi_pct":immediate_roi,"modeled_capacity_conversion_units":capacity_units,"capacity_gp":int(capacity_gp),"raw_profit_at_capacity_gp":int(raw_profit),"execution_probability_heuristic":execution,"expected_profit_before_player_time_gp":int(expected_raw),"player_time_attention":attention,"player_time_hours":round(active_hours,3),"player_time_shadow_cost_gp":int(player_cost),"player_time_adjusted_profit_gp":int(adjusted),"expected_after_tax_roi_pct":round(adjusted_roi,3) if adjusted_roi is not None else None,"expected_hold_hours":round(elapsed,3),"expected_gp_per_hour":int(gph),"slot_efficiency_gp_per_hour":int(gph),"learning_adjustment_points":learn,"profit_efficiency_score":score,"mechanics_source":x.get("mechanics_source")})
    rows.sort(key=lambda r:(r["profit_efficiency_score"],r["expected_gp_per_hour"]),reverse=True)
    return rows


def set_edges(packet, by_name):
    tax_policy = packet.get("tax_policy") or {}
    _, sets = conversion_config_map()
    rows = []
    for s in sets:
        set_name = s.get("set")
        set_row = by_name.get(set_name) or {}
        set_cur = set_row.get("current") or {}
        set_high, set_low = set_cur.get("high"), set_cur.get("low")
        comps = []
        valid = True
        for name in s.get("components") or []:
            row = by_name.get(name) or {}; cur = row.get("current") or {}
            if not isinstance(cur.get("high"),(int,float)) or not isinstance(cur.get("low"),(int,float)):
                valid=False; break
            comps.append((name,row))
        if not valid or not isinstance(set_high,(int,float)) or not isinstance(set_low,(int,float)):
            continue
        buy_set=set_high; sell_comps_net=0
        for name,row in comps:
            low=row.get("current",{}).get("low"); t=tax_for(name,low,tax_policy); sell_comps_net += low-(t or 0)
        set_to_parts_profit=sell_comps_net-buy_set
        buy_parts=sum(row.get("current",{}).get("high") for _,row in comps)
        set_tax=tax_for(set_name,set_low,tax_policy); sell_set_net=set_low-(set_tax or 0); parts_to_set_profit=sell_set_net-buy_parts
        rows.extend([{"strategy":f"{set_name}->components","type":"set_unpack","immediate_profit_gp":int(set_to_parts_profit),"input_cost_gp":int(buy_set),"roi_pct":round(set_to_parts_profit/buy_set*100,3) if buy_set else None,"source":s.get("source")},{"strategy":f"components->{set_name}","type":"set_pack","immediate_profit_gp":int(parts_to_set_profit),"input_cost_gp":int(buy_parts),"roi_pct":round(parts_to_set_profit/buy_parts*100,3) if buy_parts else None,"source":s.get("source")}])
    rows.sort(key=lambda r:r.get("roi_pct") or -999,reverse=True)
    return rows


def market_regime(cfg, by_id):
    threshold=int(cfg.get("regime_model",{}).get("minimum_liquid_item_gp_per_hour") or 20000000); moves=[]
    for row in by_id.values():
        one=row.get("1h") or {}; day=row.get("24h") or {}; one_mid=avg_mid(one); day_mid=avg_mid(day); vol=int(one.get("highPriceVolume") or 0)+int(one.get("lowPriceVolume") or 0)
        if not one_mid or not day_mid or vol*one_mid<threshold: continue
        moves.append((one_mid/day_mid-1)*100)
    if not moves: return {"label":"MIXED","sample_size":0}
    up=100*sum(1 for x in moves if x>0)/len(moves); down=100-up; med=statistics.median(moves); med_abs=statistics.median(abs(x) for x in moves); rcfg=cfg.get("regime_model",{}); breadth=float(rcfg.get("risk_on_breadth_pct") or 62); threshold_move=float(rcfg.get("median_move_threshold_pct") or 0.75)
    if up>=breadth and med>=threshold_move: label="BROAD_RISK_ON"
    elif down>=float(rcfg.get("risk_off_breadth_pct") or 62) and med<=-threshold_move: label="BROAD_RISK_OFF"
    elif med_abs>=3: label="HIGH_DISPERSION"
    else: label="MIXED"
    return {"label":label,"sample_size":len(moves),"breadth_up_pct":round(up,1),"breadth_down_pct":round(down,1),"median_1h_vs_24h_pct":round(med,3),"median_absolute_move_pct":round(med_abs,3)}


def apply_capital_aging(packet,cfg,now):
    life=load_json(LIFECYCLE); default_start=parse_iso(life.get("default_tracking_started_at_utc")); pos_cfg=life.get("positions") or {}; aging_cfg=cfg.get("capital_aging") or {}; per_half=int(aging_cfg.get("score_penalty_per_half_life_overdue") or 4); max_pen=int(aging_cfg.get("maximum_score_penalty") or 20)
    for row in packet.get("portfolio",[]):
        meta=pos_cfg.get(str(row.get("item_id"))) or {}
        if meta.get("hold_for_use"):
            row["capital_aging"]={"exempt":True,"reason":"hold_for_use"}; continue
        start=parse_iso(meta.get("tracking_started_at_utc")) or default_start; expected=meta.get("expected_payoff_hours")
        if start is None or not isinstance(expected,(int,float)) or expected<=0:
            row["capital_aging"]={"exempt":False,"scored":False}; continue
        age_h=max(0,(now-start)/3600); multiple=age_h/expected; penalty=0
        if multiple>1: penalty=min(max_pen,int(math.floor((multiple-1)/0.5+1))*per_half)
        row["capital_aging"]={"exempt":False,"scored":True,"tracking_age_hours":round(age_h,1),"expected_payoff_hours":expected,"payoff_window_multiple":round(multiple,2),"deployment_score_penalty":penalty}


def slot_optimizer(packet,cfg,fast,evergreen,conversions):
    total=int(cfg.get("ge_slots",{}).get("total_slots") or 8); known_open=len(packet.get("open_offers_unconfirmed") or []); free_upper=max(0,total-known_open); minimum=int(cfg.get("ge_slots",{}).get("minimum_slot_efficiency_gp_per_hour") or 50000); pool=[]
    for collection in (fast,evergreen,conversions):
        for x in collection:
            gph=x.get("slot_efficiency_gp_per_hour")
            if not isinstance(gph,(int,float)) or gph<minimum: continue
            name=x.get("name") or x.get("strategy"); pool.append({"engine":x.get("engine"),"item_or_strategy":name,"slot_efficiency_gp_per_hour":int(gph),"capacity_gp":x.get("capacity_gp"),"expected_profit_at_capacity_gp":x.get("expected_profit_at_capacity_gp") if x.get("expected_profit_at_capacity_gp") is not None else x.get("player_time_adjusted_profit_gp"),"profit_efficiency_score":x.get("profit_efficiency_score")})
    pool.sort(key=lambda x:(x["slot_efficiency_gp_per_hour"],x.get("profit_efficiency_score") or 0),reverse=True); selected=[]; seen=set()
    for x in pool:
        key=(x["engine"],x["item_or_strategy"])
        if key in seen: continue
        seen.add(key); selected.append(x)
        if len(selected)>=free_upper: break
    return {"total_ge_slots":total,"known_desk_open_offer_slots":known_open,"modeled_free_slots_upper_bound":free_upper,"actual_free_slots_unknown":True,"recommended_slot_priority":selected}


def main():
    now=int(time.time()); packet=load_json(PACKET)
    if not packet: raise RuntimeError("desk_packet.json missing")
    cfg=load_json(CFG); shadow=load_json(SHADOW); by_name,by_id=market_maps(); apply_capital_aging(packet,cfg,now); fast=fast_profit_rows(packet,cfg,shadow,now); evergreen=evergreen_profit_rows(packet,cfg,shadow); conversions=conversion_profit_rows(packet,cfg,shadow,by_name); sets=set_edges(packet,by_name); regime=market_regime(cfg,by_id); slots=slot_optimizer(packet,cfg,fast,evergreen,conversions); frontier=[]
    for rows in (fast[:8],conversions[:8],evergreen[:8]):
        for x in rows:
            frontier.append({"engine":x.get("engine"),"item_or_strategy":x.get("name") or x.get("strategy"),"profit_efficiency_score":x.get("profit_efficiency_score"),"expected_gp_per_hour":x.get("expected_gp_per_hour"),"expected_profit_at_capacity_gp":x.get("expected_profit_at_capacity_gp") if x.get("expected_profit_at_capacity_gp") is not None else x.get("player_time_adjusted_profit_gp"),"capacity_gp":x.get("capacity_gp"),"expected_after_tax_roi_pct":x.get("expected_after_tax_roi_pct"),"player_time_hours":x.get("player_time_hours")})
    frontier.sort(key=lambda x:(x.get("profit_efficiency_score") or 0,x.get("expected_gp_per_hour") or -10**18),reverse=True)
    packet["profit_layer"]={"schema_version":1,"generated_at":datetime.fromtimestamp(now,timezone.utc).isoformat().replace("+00:00","Z"),"objective":cfg.get("objective"),"market_regime":regime,"capital_frontier":frontier[:15],"fast_flip_capacity_velocity":fast[:15],"evergreen_capacity_velocity":evergreen[:12],"conversion_capacity_velocity":conversions[:12],"hard_value_set_edges":sets[:10],"ge_slot_optimizer":slots,"shadow_learning":{"signals_total":shadow.get("signals_total",0),"graded_observations":shadow.get("graded_observations",0),"by_engine":shadow.get("by_engine") or {},"score_adjustments":shadow.get("score_adjustments") or {},"warning":shadow.get("warning")},"player_time_shadow_value_gp_per_hour":(cfg.get("player_time") or {}).get("shadow_value_gp_per_hour"),"capacity_model_note":(cfg.get("capacity_model") or {}).get("rule"),"allocation_note":"Exact GP allocation is intentionally not optimized when current liquid cash is unknown; the capital frontier ranks opportunities by expected GP velocity, capacity and execution quality."}
    save_json(PACKET,packet); print(f"Augmented profit layer: fast={len(fast)} evergreen={len(evergreen)} conversions={len(conversions)} regime={regime.get('label')}")


if __name__=="__main__":
    main()
