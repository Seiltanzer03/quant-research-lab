#!/usr/bin/env python3
"""Read-only public historical Polymarket SPX Up/Down prices BEFORE NYSE open.
No trading credentials, no secrets, no orders, no Seiltanzer connections.
Preserve raw source times and acknowledge that price history != bid/ask.
"""
import csv
import datetime as dt
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
NY=ZoneInfo("America/New_York")
OUT=Path("pm_spx_2026_preopen_public")
OUT.mkdir(exist_ok=True)
HEADER={"Accept":"application/json","User-Agent":"SeiltanzerQuantResearchLab/1.0 (historical-public-read-only)"}
CLOCKS=["12:00","14:00","15:00","16:00"]
def http(url,params=None):
    path=url + ("?" + urlencode(params) if params else "")
    msg=""
    for t in range(3):
        try:
            with urlopen(Request(path,headers=HEADER),timeout=18) as r:
                return json.loads(r.read(10_000_000)),r.status,""
        except Exception as e:
            msg=repr(e)
            if t<2:time.sleep(1+t)
    return None,0,msg[:260]
def parse(a):
    if isinstance(a,str):
        try:return json.loads(a)
        except:return a
    return a
def extract_quotes(obj):
    if isinstance(obj,list):return obj
    if not isinstance(obj,dict):return []
    for key in ("history","data","prices","items"):
        v=obj.get(key)
        if isinstance(v,list):return v
        if isinstance(v,dict):
            for key2 in ("history","data","prices"):
                if isinstance(v.get(key2),list):return v[key2]
    return []
def save_csv(filename,items):
    if not items:return
    keys=list(dict.fromkeys(k for r in items for k in r))
    with open(OUT/filename,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(items)
def begin_end(day):
    from_d=dt.datetime.combine(day,dt.time(0),tzinfo=NY)
    until=dt.datetime.combine(day,dt.time(9),tzinfo=NY)
    return int(from_d.timestamp()),int(until.timestamp())
def sample_point(qs,ts,max_age=600):
    v=[q for q in qs if q["unix"]<=ts and ts-q["unix"]<=max_age]
    return max(v,key=lambda x:x["unix"]) if v else None
date=dt.date(2026,9,22);end=dt.date(2026,11,20)
raw=[];status=[];summary=[];sample=[];metas=[]
while date<=end:
    if date.weekday()<5:
        day=date.isoformat()
        slug=f"spx-up-or-down-on-{date.strftime('%B').lower()}-{date.day}-2026"
        e=None;details=[]
        for path in ("events","markets"):
            d,c,err=http(f"https://gamma-api.polymarket.com/{path}",{"slug":slug})
            if isinstance(d,list) and d:
                x=d[0]
                opts=x.get("markets") if path=="events" else [x]
                e=next((m for m in (opts or []) if m.get("slug")==slug), (opts or [None])[0])
                if e:break
            details.append(f"{path}:{c}:{err}")
        if not e:
            status.append({"date":day,"slug":slug,"result":"NO_GAMMA_MARKET","error":" | ".join(details)})
            date+=dt.timedelta(days=1);continue
        tokens=parse(e.get("clobTokenIds") or e.get("clob_token_ids"))
        labels=parse(e.get("outcomes"))
        if not isinstance(tokens,list) or not isinstance(labels,list) or len(tokens)!=2 or len(labels)!=2:
            status.append({"date":day,"slug":slug,"result":"NO_TOKEN_PAIR"})
            date+=dt.timedelta(days=1);continue
        endpts={str(l).upper():str(token) for l,token in zip(labels,tokens)}
        if not {"UP","DOWN"}.issubset(endpts):
            status.append({"date":day,"slug":slug,"result":"UNEXPECTED_LABELS","error":str(endpts)})
            date+=dt.timedelta(days=1);continue
        metas.append({"date":day,"slug":slug,"market_id":e.get("id"),
                      "conditionId":e.get("conditionId"),"token_ids":endpts,
                      "outcomePrices":e.get("outcomePrices"),"closed":e.get("closed")})
        start,stop=begin_end(date)
        daily={}
        for outcome,token in endpts.items():
            obj,code,err=http("https://data-api.polymarket.com/v2/prices-history",
                              {"token_id":token,"start":start,"end":stop,"fidelity":1})
            points=extract_quotes(obj)
            source="official_data_api_v2"
            if not points:
                obj2,c2,er2=http("https://clob.polymarket.com/prices-history",
                                 {"market":token,"startTs":start,"endTs":stop,"fidelity":1})
                points=extract_quotes(obj2)
                source="official_clob_price_history" if points else "none"
                err=f"{err}; clob_code={c2} {er2}"
            cleaned=[]
            for point in points:
                try:
                    ts=int(point.get("t",point.get("timestamp",point.get("time"))))
                    pr=float(point.get("p",point.get("price")))
                    if start<=ts<=stop and 0<=pr<=1:
                        cleaned.append({"date":day,"slug":slug,"outcome":outcome,
                                        "unix":ts,"price":pr,"source":source,
                                        "price_kind":"public_historical_price_not_orderbook_ask"})
                except (ValueError,TypeError):continue
            cleaned.sort(key=lambda r:r["unix"])
            raw.extend(cleaned);daily[outcome]=cleaned
            status.append({"date":day,"slug":slug,"outcome":outcome,
                           "result":"OK" if cleaned else "NO_HISTORY","points":len(cleaned),
                           "provider":source,"http_code":code,"error":err[:180]})
            time.sleep(.15)
        for clock in CLOCKS:
            local=dt.datetime.combine(date,dt.time.fromisoformat(clock),tzinfo=dt.timezone(dt.timedelta(hours=3)))
            ts=int(local.timestamp())
            rec={"date":day,"time_msk":clock,"time_et":local.astimezone(NY).isoformat(),
                 "time_utc":local.astimezone(dt.timezone.utc).isoformat(),
                 "market_slug":slug,"price_type":"historical_NOT_ASK_BID"}
            for outcome in ("UP","DOWN"):
                val=sample_point(daily.get(outcome,[]),ts)
                rec[outcome.lower()+"_price"]=val["price"] if val else None
                rec[outcome.lower()+"_ts_unix"]=val["unix"] if val else None
                rec[outcome.lower()+"_age_sec"]=ts-val["unix"] if val else None
            sample.append(rec)
        summary.append({"date":day,"slug":slug,
                        "up_points":len(daily.get("UP",[])),"down_points":len(daily.get("DOWN",[])),
                        "earliest_UTC":min([q["unix"] for q in daily.get("UP",[])]+[q["unix"] for q in daily.get("DOWN",[])],default=None)})
        print("DAY",day,"up",len(daily.get("UP",[])),"down",len(daily.get("DOWN",[])),flush=True)
    date+=dt.timedelta(days=1)
save_csv("price_history_raw_preopen.csv",raw)
save_csv("daily_source_coverage.csv",summary)
save_csv("status.csv",status)
save_csv("fixed_times_MSK.csv",sample)
(OUT/"market_metadata.json").write_text(json.dumps(metas,indent=2))
(OUT/"SUMMARY.json").write_text(json.dumps({
    "requested_trading_weekdays":len([s for s in status if s.get("outcome")=="UP"]),
    "markets_with_any_points":sum(1 for s in summary if s["up_points"]+s["down_points"]>0),
    "raw_price_points":len(raw),"sample_rows":len(sample),
    "sample_times_with_both_prices":sum(1 for s in sample if s.get("up_price") is not None and s.get("down_price") is not None),
    "warning":"Public price history does not establish executable bid/ask, as-of latency or market depth. Missing values not filled."},indent=2))
