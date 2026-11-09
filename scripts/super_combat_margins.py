#!/usr/bin/env python3
"""Super combat potion margin scanner: live Wiki high/low, conservative and patient."""
import json, os, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE="https://prices.runescape.wiki/api/v2/osrs"
UA=os.environ.get("OSRS_USER_AGENT","osrs-merch-relay/1.0 (github.com/davidothompson48-arch/osrs-merch-relay)")
RECIPES=[
 {"name":"Super combat (torstol)","inputs":{"Super attack(4)":1,"Super strength(4)":1,"Super defence(4)":1,"Torstol":1},"outputs":{"Super combat potion(4)":1,"Vial":2}},
 {"name":"Super combat (torstol unf)","inputs":{"Super attack(4)":1,"Super strength(4)":1,"Super defence(4)":1,"Torstol potion (unf)":1},"outputs":{"Super combat potion(4)":1,"Vial":2}},
]
def fetch(endpoint):
 req=urllib.request.Request(BASE+"/"+endpoint,headers={"User-Agent":UA,"Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=35) as r:return json.load(r)
def tax(price):return min(5000000,int(price*.02)) if price>=50 else 0
def main():
 mapping={v["name"].casefold():v for v in fetch("mapping")}
 latest=fetch("latest")["data"]
 hourly=fetch("1h")["data"]
 results=[]
 for recipe in RECIPES:
  names=set(recipe["inputs"])|set(recipe["outputs"])
  components={};missing=[]
  for name in names:
   item=mapping.get(name.casefold())
   quote=latest.get(str(item["id"]),{}) if item else {}
   vol=hourly.get(str(item["id"]),{}) if item else {}
   if not item or quote.get("high") is None or quote.get("low") is None:missing.append(name);continue
   components[name]={"id":item["id"],"high":quote["high"],"low":quote["low"],"highTime":quote.get("highTime"),"lowTime":quote.get("lowTime"),"buyLimit":item.get("limit"),"hourlyHighVolume":vol.get("highPriceVolume"),"hourlyLowVolume":vol.get("lowPriceVolume")}
  out={"name":recipe["name"],"xpPerPotion":150,"requiredHerblore":90,"inputs":recipe["inputs"],"outputs":recipe["outputs"],"components":components,"missing":missing}
  if not missing:
   for label,buy,sell in [("instant","high","low"),("patient","low","high")]:
    input_cost=sum(components[n][buy]*q for n,q in recipe["inputs"].items())
    revenue=sum(components[n][sell]*q for n,q in recipe["outputs"].items())
    fees=sum(tax(components[n][sell])*q for n,q in recipe["outputs"].items())
    net=revenue-fees-input_cost
    out[label]={"inputCostGp":input_cost,"saleRevenueGp":revenue,"geTaxGp":fees,"netGpPerPotion":net,"netGpPerXp":round(net/150,4),"netGpPer1000":net*1000,"netGpPer2100":net*2100}
   # Prescription goggles save the torstol secondary on 10% of crafts.
   secondary="Torstol" if "Torstol" in recipe["inputs"] else "Torstol potion (unf)"
   for label,buy in [("instant","high"),("patient","low")]:
    out[label]["expectedNetWithGogglesGpPerPotion"]=round(out[label]["netGpPerPotion"]+.1*components[secondary][buy],2)
    out[label]["expectedNetWithGogglesGpPer2100"]=round(2100*(out[label]["netGpPerPotion"]+.1*components[secondary][buy]))
  results.append(out)
 payload={"generated_at":datetime.now(timezone.utc).isoformat(),"source":BASE,"recipes":results,
  "notes":["Instant = buy materials at high, sell finished potion at low, after 2% GE tax.",
           "Patient = buy materials at low, sell finished potion at high; hypothetical limit fills.",
           "Goggles: expected 10% secondary savings; does not guarantee any specific batch outcome.",
           "Each super combat creation returns two empty vials; scanner credits their sale value.",
           "Prices and GE volumes are point-in-time observations, not guaranteed executable size."]}
 Path("super_combat_margins.json").write_text(json.dumps(payload,indent=2)+"\n")
 for r in results:
  print(r["name"],"MISSING "+",".join(r["missing"]) if r["missing"] else f'instant {r["instant"]["netGpPerPotion"]:+,} gp/pot | patient {r["patient"]["netGpPerPotion"]:+,} gp/pot')
if __name__=="__main__":main()
