#!/usr/bin/env python3
"""Download public Polymarket SPX daily price-history safely, no trading keys.

Research-only. Does NOT fetch historical bid/ask (not exposed by public price
history). Writes raw timestamps + provenance and a compact 4-time evaluation.
"""
import csv
import datetime as dt
import json
import pathlib
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT=pathlib.Path("pm_public_nov_2026")
ROOT.mkdir(exist_ok=True)
NY=ZoneInfo("America/New_York")
DAYS=[4,5,6,9,10,11,12,13,16,17,18,19,20]
TIMES=["10:30","11:45","13:00","14:30"]
UA={"User-Agent":"Mozilla/5.0 quant-research-lab/1.0","Accept":"application/json"}

def fetch(base,params=None):
    url=base+("?" + urllib.parse.urlencode(params) if params else "")
    for tries in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=18) as r:
                raw=r.read(12_000_000)
                return json.loads(raw),r.status,""
        except Exception as e:
            err=repr(e)
            if tries<2:time.sleep(1+tries)
    return None,0,err[:280]

def points(response):
    if isinstance(response,dict):
        for key in ("history","data","prices","items"):
            if key in response:
                val=response[key]
                if isinstance(val,dict):
                    for k in ("history","prices","data"):
                        if k in val and isinstance(val[k],list): return val[k]
                if isinstance(val,list):return val
    if isinstance(response,list):return response
    return []

def tokens(market):
    a=market.get("clobTokenIds") or market.get("clob_token_ids")
    b=market.get("outcomes")
    if isinstance(a,str):
        try:a=json.loads(a)
        except:pass
    if isinstance(b,str):
        try:b=json.loads(b)
        except:pass
    if not isinstance(a,list) or len(a)<2:return {}
    if not isinstance(b,list) or len(b)!=len(a):return {}
    return {str(x).strip().upper():str(t) for x,t in zip(b,a)}

meta=[];rows=[];samples=[];status=[]
for day in DAYS:
    date=f"2026-11-{day:02d}"
    slug=f"spx-up-or-down-on-november-{day}-2026"
    market=None;discover_errors=[]
    for path in ("markets","events"):
        res,code,err=fetch(f"https://gamma-api.polymarket.com/{path}",{"slug":slug})
        if code==200 and isinstance(res,list) and res:
            entry=res[0]
            arr=entry.get("markets") if path=="events" else [entry]
            candidates=[i for i in (arr or []) if i.get("slug")==slug]
            market=(candidates or arr or [None])[0]
            if market:break
        discover_errors.append(f"{path}:{code}:{err[:100]}")
    if not market:
        status.append({"date":date,"slug":slug,"result":"NO_MARKET_METADATA","details":";".join(discover_errors)})
        continue
    tkn=tokens(market)
    meta.append({"date":date,"slug":slug,"condition_id":str(market.get("conditionId")),
                 "gamma_market_id":str(market.get("id")),"tokens":tkn,
                 "resolution_prices":market.get("outcomePrices"),"closed":market.get("closed")})
    if not tkn:
        status.append({"date":date,"slug":slug,"result":"NO_CLOB_TOKENS","details":str(list(market)[:30])})
        continue
    start=int(dt.datetime(2026,11,day,9,0,tzinfo=NY).timestamp())
    end=int(dt.datetime(2026,11,day,17,0,tzinfo=NY).timestamp())
    for outcome,token in tkn.items():
        data,code,err=fetch("https://data-api.polymarket.com/v2/prices-history",
                       {"token_id":token,"start":start,"end":end,"fidelity":1})
        pts=points(data) if code==200 else []
        method="DataAPI_v2"
        if not pts:
            data2,code2,err2=fetch("https://clob.polymarket.com/prices-history",
                                  {"market":token,"startTs":start,"endTs":end,"fidelity":1})
            p2=points(data2) if code2==200 else []
            if p2:pts=p2;method="CLOB_price_history"
            else:err+=f";fallback_code={code2}:{err2[:80]}"
        count=0
        for p in pts:
            try:
                ts=int(p.get("t",p.get("timestamp",p.get("time"))))
                price=float(p.get("p",p.get("price")))
                if not (start<=ts<=end and 0<=price<=1):continue
                rows.append({"date":date,"slug":slug,"outcome":outcome,
                            "ts_utc":ts,"price":price,"provider":method,
                            "price_type":"historical_print_or_mid_NOT_orderbook_ask"})
                count+=1
            except Exception:pass
        status.append({"date":date,"slug":slug,"outcome":outcome,"result":"OK" if count else "NO_POINTS",
                       "points":count,"method":method,"http_status":code,"details":err[:250]})
        time.sleep(.25)
    for tm in TIMES:
        t=dt.datetime.fromisoformat(f"{date}T{tm}:00").replace(tzinfo=NY).timestamp()
        for outcome in tkn:
            item=min((r for r in rows if r["date"]==date and r["outcome"]==outcome and r["ts_utc"]<=t),
                     key=lambda r:t-r["ts_utc"],default=None)
            samples.append({"date":date,"time_et":tm,"outcome":outcome,
                            "price":item["price"] if item and t-item["ts_utc"]<=120 else "",
                            "price_ts_utc":item["ts_utc"] if item else "",
                            "age_s":round(t-item["ts_utc"]) if item else "",
                            "source":item["provider"] if item else "",
                            "historical_bid_ask":False})

def writecsv(name,items):
    if not items:return
    all_cols=list(dict.fromkeys(c for r in items for c in r.keys()))
    with open(ROOT/name,"w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=all_cols);w.writeheader();w.writerows(items)

writecsv("price_history_raw.csv",rows)
writecsv("sampled_price_history_4times.csv",samples)
writecsv("download_status.csv",status)
(ROOT/"market_metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2))
(ROOT/"SUMMARY.json").write_text(json.dumps({
    "markets_found":len(meta),"price_history_rows":len(rows),
    "dates":len(DAYS),"status":status,
    "disclaimer":"No historical Bid/Ask. Price history is NOT an executable price or validated implied probability."
},ensure_ascii=False,indent=2))
print("RESULT_SUMMARY",json.dumps({"markets_found":len(meta),"rows":len(rows),
                                  "days_with_prices":len(set(r["date"] for r in rows)),
                                  "nonempty_outcome_series":sum(r.get("points",0)>0 for r in status)}))
for r in status:print("RESULT_LINE",r["date"],r.get("outcome","-"),r["result"],r.get("points",""),r.get("details","")[:95])
