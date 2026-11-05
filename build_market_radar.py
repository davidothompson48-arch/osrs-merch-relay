#!/usr/bin/env python3
"""Market-only cross-sector radar using RuneLite/Wiki relay data; no price forecasts."""
import glob
import json
import math
import os
import time
from datetime import datetime, timezone, timedelta

SOURCE = 'prices.runescape.wiki OSRS RuneLite via repository market_universe'
SECTORS = {
    'legacy_pvm_gear': ['Bandos chestplate','Bandos tassets','Torva platebody','Soulreaper axe','Masori body','Dragon hunter crossbow','Dragon hunter lance','Inquisitor\'s mace','Scythe of Vitur (uncharged)'],
    'pvm_consumables': ['Super restore(4)','Prayer potion(4)','Saradomin brew(4)','Ranarr weed','Stamina potion(4)','Zulrah\'s scales','Shark','Manta ray'],
    'runes': ['Nature rune','Death rune','Soul rune','Wrath rune','Blood rune'],
    'raid4_rewards': ['Rondache',"Zorya's tome (uncharged)",'Ascension crossbows','Horn of Bran','Obligator (uncharged)','Ascension shards'],
    'gems': ['Diamond','Uncut diamond','Ruby','Uncut ruby','Red topaz','Uncut red topaz'],
    'dragonbane': ['Dragon hunter lance','Dragon hunter crossbow','Dragon hunter wand'],
}
HISTORY = 'history/market_regime_daily.jsonl'
OUT = 'market_radar.json'


def read_json(path, default=None):
    try:
        with open(path, encoding='utf8') as f: return json.load(f)
    except (OSError, ValueError): return default


def price_pair(row):
    cur = row.get('current') or {}
    hi, lo = cur.get('high'), cur.get('low')
    if not all(isinstance(x, (int, float)) and x > 0 for x in (hi, lo)) or hi < lo:
        return None
    if not all(isinstance(cur.get(x), int) for x in ('highTime','lowTime')):
        return None
    return (hi + lo) / 2


def valid_price(row, generated_unix):
    mid = price_pair(row)
    cur = row.get('current') or {}
    if mid is None or max(max(0, generated_unix-cur[x]) for x in ('highTime','lowTime')) > 7200:
        return None
    return mid


def average_24h(row):
    day = row.get('24h') or {}
    a,b = day.get('avgHighPrice'), day.get('avgLowPrice')
    return (a+b)/2 if all(isinstance(x,(int,float)) and x>0 for x in (a,b)) else None


def geom_ratio(current, previous):
    comparable = [current[k] / previous[k] for k in current.keys() & previous.keys() if current[k]>0 and previous[k]>0]
    if len(comparable) < 3: return None, len(comparable)
    return round((math.exp(sum(math.log(x) for x in comparable)/len(comparable))-1)*100, 3), len(comparable)


def load_history(path):
    if not os.path.exists(path): return []
    rows=[]
    with open(path, encoding='utf8') as f:
        for line in f:
            try:
                val=json.loads(line)
                if isinstance(val,dict) and 'date' in val and 'midpoints' in val: rows.append(val)
            except ValueError: pass
    return rows[-120:]


def compute(rows, generated_unix, history):
    valid={k:v for k,v in rows.items() if valid_price(v,generated_unix) is not None}
    current={k:valid_price(v,generated_unix) for k,v in valid.items()}
    ref24={k:average_24h(v) for k,v in valid.items()}
    sector_reports=[]
    for name, names in SECTORS.items():
        member={k:current[k] for k in names if k in current}
        before={k:ref24[k] for k in names if ref24.get(k)}
        pct,n=geom_ratio(member,before)
        sector_reports.append({'sector':name,'constituents':len(member),'comparable_24h':n,'current_vs_24h_avg_pct':pct,'price_level_index_24h_reference_100':round(100*(1+pct/100),3) if pct is not None else None})

    day=datetime.fromtimestamp(generated_unix,timezone.utc).date()
    historical=[]
    for lag in (7,30):
        cutoff=(day-timedelta(days=lag)).isoformat()
        candidates=[x for x in history if x['date']<=cutoff]
        past=max(candidates,key=lambda x:x['date']) if candidates else None
        basket=list(dict.fromkeys(SECTORS['legacy_pvm_gear']+SECTORS['pvm_consumables']+SECTORS['runes']))
        now={k:current[k] for k in basket if k in current}
        prior={k:past['midpoints'][k] for k in basket if past and k in past['midpoints']}
        pct,n=geom_ratio(now,prior)
        historical.append({'target_days':lag,'baseline_date':past['date'] if past else None,'items_compared':n,'item_price_index_change_pct':pct,'cash_purchasing_power_proxy_change_pct':round((1/(1+pct/100)-1)*100,3) if pct is not None else None})

    moves=[]
    for name,row in valid.items():
        mid=current[name]; ref=ref24.get(name)
        daydata=row.get('24h') or {}
        volume=int(daydata.get('highPriceVolume') or 0)+int(daydata.get('lowPriceVolume') or 0)
        if not ref or volume < 200 or ref*volume < 1_000_000_000: continue
        pct=(mid/ref-1)*100
        if abs(pct)<8: continue
        hi,lo=row['current']['high'],row['current']['low']
        tax=min(int(lo*0.02),5_000_000)
        moves.append({'item':name,'item_id':row.get('id'),'high':hi,'low':lo,'24h_volume':volume,'current_vs_24h_avg_pct':round(pct,2),'round_trip_friction_gp':hi-lo+tax,'round_trip_friction_pct_of_buy':round((hi-lo+tax)/hi*100,2)})
    moves=sorted(moves,key=lambda x:abs(x['current_vs_24h_avg_pct']),reverse=True)[:25]
    return {'schema_version':1,'source':SOURCE,'generated_at':datetime.now(timezone.utc).isoformat(),'market_universe_unix':generated_unix,'data_age_seconds':max(0,int(time.time())-generated_unix),'status':'READY' if int(time.time())-generated_unix<3600 else 'STALE','items_with_fresh_two_sided_prints':len(valid),'sectors':sector_reports,'multi_day_selected_basket':historical,'unusual_moves':moves,'notes':['A sector index of 100 is its 24-hour average reference, NOT a historical inflation index.','A 7d/30d cash purchasing-power proxy becomes available only after enough DAILY samples of an unchanged basket.','Low/high prints are asynchronous; crossed prints, stale quotes and shallow volume are rejected.','Prices and volumes originate only from the OSRS Wiki RuneLite API via GitHub; event and community claims are not sourced from market data.']},current,day.isoformat()


def main():
    index=read_json('market_universe/index.json',{})
    stamp=index.get('generated_unix')
    if not isinstance(stamp,int): raise SystemExit('Missing market universe timestamp')
    rows={}
    for path in glob.glob('market_universe/*.json'):
        if path.endswith('index.json'): continue
        for item in (read_json(path,{}) or {}).get('items',[]):
            if item.get('name'): rows[item['name']]=item
    history=load_history(HISTORY)
    report, midpoints, day=compute(rows,stamp,history)
    os.makedirs('history',exist_ok=True)
    if report['status']=='READY':
        today={'date':day,'midpoints':{k:midpoints[k] for names in SECTORS.values() for k in names if k in midpoints}}
        history=[h for h in history if h['date']!=day]+[today]
        history=sorted(history,key=lambda x:x['date'])[-120:]
        with open(HISTORY,'w',encoding='utf8') as f:
            for h in history: f.write(json.dumps(h,separators=(',',':'))+'\n')
    with open(OUT,'w',encoding='utf8') as f: json.dump(report,f,separators=(',',':'));f.write('\n')
    print('Market radar:', report['status'], report['items_with_fresh_two_sided_prints'],'items',len(report['unusual_moves']),'unusual moves')

if __name__=='__main__': main()
