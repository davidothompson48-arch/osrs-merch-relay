#!/usr/bin/env python3
"""Crafting margins from OSRS Wiki live high/low transactions; standard library only."""
import json, math, os, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://prices.runescape.wiki/api/v2/osrs"
USER_AGENT = os.environ.get("OSRS_USER_AGENT", "osrs-merch-relay crafting-scanner (github.com/davidothompson48-arch/osrs-merch-relay)")
XP_TARGET = 13034431
XP_START_89 = 4842295
RECIPES = [
    {"name":"Amethyst dart tips","xp":60,"inputs":{"Amethyst":1},"outputs":{"Amethyst dart tip":8}},
    {"name":"Amethyst arrowtips","xp":60,"inputs":{"Amethyst":1},"outputs":{"Amethyst arrowtips":15}},
    {"name":"Air battlestaves","xp":137.5,"inputs":{"Battlestaff":1,"Air orb":1},"outputs":{"Air battlestaff":1}},
    {"name":"Water battlestaves","xp":100,"inputs":{"Battlestaff":1,"Water orb":1},"outputs":{"Water battlestaff":1}},
    {"name":"Earth battlestaves","xp":112.5,"inputs":{"Battlestaff":1,"Earth orb":1},"outputs":{"Earth battlestaff":1}},
    {"name":"Fire battlestaves","xp":125,"inputs":{"Battlestaff":1,"Fire orb":1},"outputs":{"Fire battlestaff":1}},
    {"name":"Red d'hide bodies","xp":234,"inputs":{"Red dragon leather":3},"outputs":{"Red d'hide body":1}},
    {"name":"Black d'hide bodies","xp":258,"inputs":{"Black dragon leather":3},"outputs":{"Black d'hide body":1}},
    {"name":"Blue d'hide bodies","xp":210,"inputs":{"Blue dragon leather":3},"outputs":{"Blue d'hide body":1}},
    {"name":"Green d'hide bodies","xp":186,"inputs":{"Green dragon leather":3},"outputs":{"Green d'hide body":1}},
]
def fetch(path):
    req=urllib.request.Request(BASE+"/"+path,headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=35) as response:
        return json.load(response)
def tax(price):
    # OSRS GE tax is 2%, rounded down; sales below 50gp exempt; 5m cap per item.
    return min(5000000, int(price*0.02)) if price>=50 else 0
def main():
    mapping=fetch("mapping")
    latest=fetch("latest")["data"]
    hourly=fetch("1h")["data"]
    by_name={x["name"].casefold():x for x in mapping}
    output=[]
    for recipe in RECIPES:
        components={}
        missing=[]
        for name in set(recipe["inputs"])|set(recipe["outputs"]):
            item=by_name.get(name.casefold())
            quote=latest.get(str(item["id"]),{}) if item else {}
            h=hourly.get(str(item["id"]),{}) if item else {}
            if not item or quote.get("high") is None or quote.get("low") is None:
                missing.append(name)
                continue
            components[name]={"id":item["id"],"high":quote["high"],"low":quote["low"],
                "highTime":quote.get("highTime"),"lowTime":quote.get("lowTime"),
                "buyLimit":item.get("limit"),"hourlyHighVolume":h.get("highPriceVolume"),
                "hourlyLowVolume":h.get("lowPriceVolume")}
        result={"name":recipe["name"],"xpPerAction":recipe["xp"],"inputs":recipe["inputs"],
                "outputs":recipe["outputs"],"components":components,"missing":missing}
        if not missing:
            # Buy materials at observed instant-buy (high), sell outputs at observed
            # instant-sell (low): conservative immediately executable direction.
            spend=sum(components[n]["high"]*q for n,q in recipe["inputs"].items())
            gross=sum(components[n]["low"]*q for n,q in recipe["outputs"].items())
            fees=sum(tax(components[n]["low"])*q for n,q in recipe["outputs"].items())
            net=gross-fees-spend
            actions=math.ceil((XP_TARGET-XP_START_89)/recipe["xp"])
            result.update({"inputGpPerAction":spend,"outputGpPerAction":gross,
                "taxGpPerAction":fees,"netGpPerAction":net,"netGpPerXp":round(net/recipe["xp"],4),
                "actions89To99":actions,"projectedNetGp89To99":net*actions,
                "projectedInputGp89To99":spend*actions,
                "pricingMode":"instant-buy inputs / instant-sell outputs; not guaranteed fills"})
        output.append(result)
    output.sort(key=lambda x:(bool(x["missing"]),-x.get("netGpPerXp",-1e12)))
    payload={"generated_at":datetime.now(timezone.utc).isoformat(),"source":BASE,
        "levelStart":89,"xpStart":XP_START_89,"xpTarget":XP_TARGET,
        "remainingXp":XP_TARGET-XP_START_89,"recipes":output,
        "notes":["Thread costs for dragonhide bodies are excluded (usually small).",
        "Trade quotes may be stale; check component timestamps and volumes.",
        "GE buy limits and market depth may constrain large batches.",
        "Amethyst dart tips yield 8 per amethyst; arrowtips yield 15.",
        "Selling tax is applied per finished item; item-specific exemptions not modeled."]}
    dest=Path("crafting_margins.json")
    dest.write_text(json.dumps(payload,indent=2)+"\n")
    print("Wrote",dest)
    for r in output:
        print(r["name"], "MISSING "+",".join(r["missing"]) if r["missing"] else f'{r["netGpPerXp"]:+.2f} gp/xp | {r["projectedNetGp89To99"]:+,} gp to 99')
if __name__=="__main__":
    main()
