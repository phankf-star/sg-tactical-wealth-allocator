#!/usr/bin/env python3
"""
rates_history_lab_test_v3.py

Focused lab test for Global20Engine rates history.

v3 patch focus
--------------
- SG: add redistributor-based daily SORA history parser candidates.
- JP: use BOJ JSON API first with generic daily date/value extraction, CSV fallback second.
- Keep successful US / HK / MY v2 logic.

Outputs
-------
  macro_pack_latest/rates_history_252d.csv
  macro_pack_latest/rates_history_diagnostics.csv
"""
from __future__ import annotations

import csv, io, json, re, urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime
import pandas as pd

OUT_DIR = Path("macro_pack_latest")
OUT_DIR.mkdir(parents=True, exist_ok=True)
RATES_OUT = OUT_DIR / "rates_history_252d.csv"
DIAG_OUT = OUT_DIR / "rates_history_diagnostics.csv"
USER_AGENT = "Global20Engine-rates-history-lab/3.0"


def request_text(url, headers=None, timeout=75):
    h = {"User-Agent": USER_AGENT, "Accept":"application/json,text/csv,text/plain,text/html,*/*", "Accept-Encoding":"identity"}
    if headers: h.update(headers)
    try:
        req=urllib.request.Request(url,headers=h)
        with urllib.request.urlopen(req,timeout=timeout) as resp:
            return resp.read().decode("utf-8-sig",errors="replace"), ""
    except Exception as exc:
        return "", str(exc)


def clean_number(v):
    try:
        if v is None: return None
        s=str(v).replace(",","").replace("%","").replace("+","").strip()
        if s in ["","na","n.a.","N.A.","-","--","—",".","None","null"]: return None
        return float(s)
    except Exception:
        return None


def parse_date(x, dayfirst=False):
    if x is None or not str(x).strip(): return pd.NaT
    s=str(x).strip()
    if re.fullmatch(r"\d{8}",s): return pd.to_datetime(s,format="%Y%m%d",errors="coerce")
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}",s): return pd.to_datetime(s,errors="coerce")
    if dayfirst and re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}",s): return pd.to_datetime(s,format="%d/%m/%Y",errors="coerce")
    return pd.to_datetime(s,errors="coerce",dayfirst=dayfirst)


def mk_row(market,date,value,source,source_type="Official API",frequency="daily",notes=""):
    return {"market":market,"indicator":"Rates","date":pd.Timestamp(date).strftime("%Y-%m-%d") if pd.notna(date) else "","value":value,"unit":"%","source":source,"source_type":source_type,"frequency":frequency,"notes":notes}

def mk_diag(market,adapter,endpoint,status,rows=0,latest="",reason=""):
    return {"market":market,"adapter":adapter,"endpoint":endpoint,"status":status,"rows":int(rows or 0),"latest":latest,"reason":reason,"tested_at":datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}

# ---------- US ----------
def fetch_us_yahoo_tnx():
    market="US"; adapter="Yahoo ^TNX daily fallback"
    url="https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=1y&interval=1d"
    txt,err=request_text(url,headers={"Accept":"application/json,*/*"})
    if not txt: return [], mk_diag(market,adapter,url,"failed",reason=err)
    try:
        res=(json.loads(txt).get("chart",{}).get("result") or [None])[0]
        if not res: return [], mk_diag(market,adapter,url,"failed",reason="No Yahoo chart result")
        ts=res.get("timestamp") or []
        closes=(((res.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
        rows=[]
        for t,c in zip(ts,closes):
            val=clean_number(c)
            if val is None: continue
            dt=pd.to_datetime(int(t),unit="s",utc=True).tz_convert(None).normalize()
            rows.append(mk_row(market,dt,val,"Yahoo Finance ^TNX","Market data","daily","Fallback when FRED DGS10 times out"))
        df=pd.DataFrame(rows)
        if df.empty: return [], mk_diag(market,adapter,url,"failed",reason="No usable ^TNX values")
        df["date_dt"]=pd.to_datetime(df["date"],errors="coerce")
        df=df.dropna(subset=["date_dt"]).sort_values("date_dt").drop_duplicates(["market","indicator","date"],keep="last").tail(252)
        latest=f"{df.date.iloc[-1]}={df.value.iloc[-1]}" if not df.empty else ""
        return df.drop(columns=["date_dt"]).to_dict("records"), mk_diag(market,adapter,url,"accepted",len(df),latest)
    except Exception as exc:
        return [], mk_diag(market,adapter,url,"failed",reason=str(exc))

def fetch_us_dgs10():
    market="US"; adapter="FRED DGS10 daily"; url="https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
    txt,err=request_text(url,timeout=90); diags=[]
    if txt:
        try:
            df=pd.read_csv(io.StringIO(txt),parse_dates=["DATE"])
            if "DGS10" in df.columns:
                df["value"]=pd.to_numeric(df["DGS10"],errors="coerce")
                df=df.dropna(subset=["DATE","value"]).sort_values("DATE").tail(252)
                rows=[mk_row(market,r.DATE,float(r.value),"FRED DGS10","Official API","daily") for r in df.itertuples(index=False)]
                latest="" if df.empty else f"{df.DATE.iloc[-1].date()}={df.value.iloc[-1]}"
                return rows,[mk_diag(market,adapter,url,"accepted",len(rows),latest)]
            diags.append(mk_diag(market,adapter,url,"failed",reason=f"Columns returned: {list(df.columns)}"))
        except Exception as exc: diags.append(mk_diag(market,adapter,url,"failed",reason=str(exc)))
    else: diags.append(mk_diag(market,adapter,url,"failed",reason=err))
    rows,diag=fetch_us_yahoo_tnx(); diags.append(diag); return rows,diags

# ---------- HK ----------
def fetch_hk_hibor():
    market="HK"; adapter="HKMA daily HIBOR"
    url="https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily?pagesize=1000&sortby=end_of_day&sortorder=desc"
    txt,err=request_text(url)
    if not txt: return [],[mk_diag(market,adapter,url,"failed",reason=err)]
    try:
        records=json.loads(txt).get("result",{}).get("records") or json.loads(txt).get("result",{}).get("data") or []
        rows=[]
        for rec in records:
            if not isinstance(rec,dict): continue
            dt=parse_date(rec.get("end_of_day") or rec.get("date"))
            val=None; used=""
            for k in ["hibor_1m","ir_1m","one_month","1m","overnight","ir_overnight","value"]:
                if k in rec:
                    val=clean_number(rec.get(k)); used=k
                    if val is not None: break
            if pd.notna(dt) and val is not None: rows.append(mk_row(market,dt,val,f"HKMA HIBOR daily ({used})","Official API","daily"))
        df=pd.DataFrame(rows)
        if df.empty: return [],[mk_diag(market,adapter,url,"failed",rows=len(records),reason="No recognised HIBOR value parsed")]
        df["date_dt"]=pd.to_datetime(df["date"],errors="coerce")
        df=df.dropna(subset=["date_dt"]).sort_values("date_dt").drop_duplicates(["market","indicator","date"],keep="last").tail(252)
        latest=f"{df.date.iloc[-1]}={df.value.iloc[-1]}" if not df.empty else ""
        return df.drop(columns=["date_dt"]).to_dict("records"),[mk_diag(market,adapter,url,"accepted",len(df),latest)]
    except Exception as exc: return [],[mk_diag(market,adapter,url,"failed",reason=str(exc))]

# ---------- MY ----------
def json_records_from_payload(payload):
    if isinstance(payload,list): return payload
    if not isinstance(payload,dict): return []
    for path in [("result","records"),("result","data"),("data",),("records",)]:
        cur=payload; ok=True
        for key in path:
            if isinstance(cur,dict) and key in cur: cur=cur[key]
            else: ok=False; break
        if ok and isinstance(cur,list): return cur
    return []

def flatten_record(obj,prefix=""):
    out={}
    if isinstance(obj,dict):
        for k,v in obj.items():
            key=f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v,(dict,list)): out.update(flatten_record(v,key))
            else: out[key]=v
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            key=f"{prefix}.{i}" if prefix else str(i)
            if isinstance(v,(dict,list)): out.update(flatten_record(v,key))
            else: out[key]=v
    return out

def parse_bnm_policy_points(records):
    value_keys=["new_opr_level","new_opr","opr_level","opr","OPR","rate","interest_rate","value"]
    pts=[]
    for rec in records:
        if not isinstance(rec,dict): continue
        flat=flatten_record(rec)
        dt=pd.NaT
        for k,v in flat.items():
            if "date" in k.split(".")[-1].lower():
                cand=parse_date(v,dayfirst=True)
                if pd.notna(cand): dt=cand; break
        val=None
        for pref in value_keys:
            for k,v in flat.items():
                if k.split(".")[-1] == pref:
                    vv=clean_number(v)
                    if vv is not None and -2 <= vv <= 25: val=vv; break
            if val is not None: break
        if val is None:
            for k,v in flat.items():
                if any(tok in k.lower() for tok in ["opr","rate","level"]):
                    vv=clean_number(v)
                    if vv is not None and -2 <= vv <= 25: val=vv; break
        if pd.notna(dt) and val is not None: pts.append((dt,val))
    return pts

def fetch_my_bnm_opr():
    market="MY"; adapter="BNM OPR policy-step"; headers={"Accept":"application/vnd.BNM.API.v1+json"}
    years=[pd.Timestamp.today().year,pd.Timestamp.today().year-1,pd.Timestamp.today().year-2]
    urls=["https://api.bnm.gov.my/public/opr"]
    for y in years:
        urls += [f"https://api.bnm.gov.my/public/opr/year/{y}", f"https://api.bnm.gov.my/public/opr?year={y}"]
    diags=[]; pts=[]
    for url in urls:
        txt,err=request_text(url,headers=headers)
        if not txt: diags.append(mk_diag(market,adapter,url,"failed",reason=err)); continue
        try:
            records=json_records_from_payload(json.loads(txt)); got=parse_bnm_policy_points(records); pts += got
            diags.append(mk_diag(market,adapter,url,"reached",rows=len(records),reason=f"Parsed {len(got)} candidate policy records"))
        except Exception as exc: diags.append(mk_diag(market,adapter,url,"failed",reason=str(exc)))
    if not pts: return [], diags+[mk_diag(market,adapter," | ".join(urls[:3]),"failed",reason="No BNM OPR policy points parsed")]
    policy=pd.DataFrame(pts,columns=["date","value"]).dropna().sort_values("date").drop_duplicates("date",keep="last")
    start=min(policy.date.min(), pd.Timestamp.today()-pd.offsets.BDay(320))
    idx=pd.bdate_range(start=start,end=pd.Timestamp.today().normalize())
    step=policy.set_index("date").reindex(idx).ffill().dropna().tail(252)
    rows=[mk_row(market,dt,float(r.value),"BNM OpenAPI Overnight Policy Rate (OPR)","Official API","policy_step","Expanded to business-day step series from official policy dates") for dt,r in step.iterrows()]
    latest="" if step.empty else f"{step.index[-1].date()}={step.value.iloc[-1]}"
    return rows,diags+[mk_diag(market,adapter," | ".join(urls[:3]),"accepted",len(rows),latest,f"Policy points parsed={len(policy)}")]

# ---------- JP ----------
def extract_date_value_pairs_from_obj(obj, source_name=""):
    pairs=[]
    date_keys=["TIME_PERIOD","time_period","date","Date","time","period","TIME"]
    value_keys=["OBS_VALUE","obs_value","value","Value","rate","Rate"]
    def walk(x):
        if isinstance(x,dict):
            # record-style parse
            flat=flatten_record(x)
            dt=pd.NaT; val=None
            for k,v in flat.items():
                kk=k.split(".")[-1]
                if kk in date_keys or kk.lower() in [z.lower() for z in date_keys]:
                    cand=parse_date(v)
                    if pd.notna(cand): dt=cand; break
            for k,v in flat.items():
                kk=k.split(".")[-1]
                if kk in value_keys or kk.lower() in [z.lower() for z in value_keys]:
                    vv=clean_number(v)
                    if vv is not None and -2 <= vv <= 25: val=vv; break
            if pd.notna(dt) and val is not None: pairs.append((dt,val))
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            # pair-style parse e.g. [date,value]
            if len(x)>=2:
                d=parse_date(x[0]); v=clean_number(x[1])
                if pd.notna(d) and v is not None and -2 <= v <= 25: pairs.append((d,v))
            for v in x: walk(v)
    walk(obj)
    return pairs

def parse_boj_csv(txt):
    pairs=[]
    for raw in csv.reader(io.StringIO(txt)):
        if not raw: continue
        # Case A: row contains one date and one value
        dt_idx=None; dt=pd.NaT
        for i,cell in enumerate(raw):
            cand=parse_date(cell)
            if pd.notna(cand) and 1990 <= cand.year <= pd.Timestamp.today().year+1: dt_idx=i; dt=cand; break
        if dt_idx is not None:
            for cell in raw[dt_idx+1:]:
                val=clean_number(cell)
                if val is not None and -2 <= val <= 25: pairs.append((pd.Timestamp(dt),val)); break
        # Case B: wide format: alternating date/value or many dates in header is handled poorly; skip here.
    return pairs

def fetch_jp_boj_call_rate():
    market="JP"; adapter="BOJ FM01 STRDCLUCON daily"
    start=(pd.Timestamp.today()-pd.DateOffset(months=24)).strftime("%Y%m")
    diags=[]
    code_candidates=["STRDCLUCON","STRDCLUCON@D","FM01'STRDCLUCON","FM01.STRDCLUCON"]
    for code in code_candidates:
        url="https://www.stat-search.boj.or.jp/api/v1/getDataCode?"+urllib.parse.urlencode({"format":"json","lang":"en","db":"FM01","startDate":start,"code":code})
        txt,err=request_text(url,headers={"Accept":"application/json,*/*"})
        if not txt: diags.append(mk_diag(market,adapter,url,"failed",reason=err)); continue
        try:
            payload=json.loads(txt); pairs=extract_date_value_pairs_from_obj(payload,"BOJ JSON")
            if pairs:
                df=pd.DataFrame(pairs,columns=["date","value"]).dropna().sort_values("date").drop_duplicates("date",keep="last").tail(252)
                rows=[mk_row(market,r.date,float(r.value),f"BOJ FM01 STRDCLUCON JSON ({code})","Official API","daily") for r in df.itertuples(index=False)]
                latest="" if df.empty else f"{df.date.iloc[-1].date()}={df.value.iloc[-1]}"
                status="accepted" if len(rows)>=20 else "partial"
                reason="Low row count; parser/source needs refinement" if status=="partial" else ""
                diags.append(mk_diag(market,adapter,url,status,len(rows),latest,reason)); return rows,diags
            diags.append(mk_diag(market,adapter,url,"failed",reason="JSON reached but no generic date/value rows parsed"))
        except Exception as exc: diags.append(mk_diag(market,adapter,url,"failed",reason=str(exc)))
    # CSV fallback
    for code in code_candidates:
        url="https://www.stat-search.boj.or.jp/api/v1/getDataCode?"+urllib.parse.urlencode({"format":"csv","lang":"en","db":"FM01","startDate":start,"code":code})
        txt,err=request_text(url,headers={"Accept":"text/csv,*/*"})
        if not txt: diags.append(mk_diag(market,adapter,url,"failed",reason=err)); continue
        pairs=parse_boj_csv(txt)
        if pairs:
            df=pd.DataFrame(pairs,columns=["date","value"]).dropna().sort_values("date").drop_duplicates("date",keep="last").tail(252)
            rows=[mk_row(market,r.date,float(r.value),f"BOJ FM01 STRDCLUCON CSV ({code})","Official API","daily") for r in df.itertuples(index=False)]
            latest="" if df.empty else f"{df.date.iloc[-1].date()}={df.value.iloc[-1]}"
            status="accepted" if len(rows)>=20 else "partial"
            reason="Low row count; parser/source needs refinement" if status=="partial" else ""
            diags.append(mk_diag(market,adapter,url,status,len(rows),latest,reason)); return rows,diags
        diags.append(mk_diag(market,adapter,url,"failed",reason="CSV reached but no date/value rows parsed"))
    return [],diags

# ---------- SG ----------
def extract_sora_rows_from_html(html, source_label, url):
    rows=[]
    # Pattern: 2026-06-17 0.8169% ... or Wed, 24 Jun 2026 1.1553%
    text=re.sub(r"<[^>]+>"," ",html)
    text=re.sub(r"\s+"," ",text)
    # ISO date + SORA value nearby
    for m in re.finditer(r"(20\d{2}-\d{2}-\d{2})\s+(-?\d+(?:\.\d+)?)\s*%", text):
        dt=parse_date(m.group(1)); val=clean_number(m.group(2))
        if pd.notna(dt) and val is not None and -5 <= val <= 20:
            rows.append(mk_row("SG",dt,val,source_label,"Redistributor","daily",f"Parsed from {url}"))
    # Human date + SORA value nearby
    for m in re.finditer(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2})\s+(-?\d+(?:\.\d+)?)\s*%", text):
        dt=parse_date(m.group(1)); val=clean_number(m.group(2))
        if pd.notna(dt) and val is not None and -5 <= val <= 20:
            rows.append(mk_row("SG",dt,val,source_label,"Redistributor","daily",f"Parsed from {url}"))
    return rows

def fetch_sg_sora_history():
    market="SG"; adapter="SG SORA daily redistributor history"
    urls=[
        ("StraitsData MAS SORA", "https://straitsdata.com/finance/mas"),
        ("ToolSG SORA Monitor", "https://www.toolsg.com/en/sora-index"),
        ("DailySORA", "https://dailysora.org/"),
    ]
    diags=[]; all_rows=[]
    for label,url in urls:
        txt,err=request_text(url,headers={"Accept":"text/html,*/*"})
        if not txt:
            diags.append(mk_diag(market,adapter,url,"failed",reason=err)); continue
        rows=extract_sora_rows_from_html(txt,label,url)
        all_rows.extend(rows)
        diags.append(mk_diag(market,adapter,url,"reached",rows=len(rows),reason=f"Parsed {len(rows)} SORA candidate rows"))
    if not all_rows:
        diags.append(mk_diag(market,adapter," | ".join(u for _,u in urls),"needs_validation",0,"","No SG SORA daily history rows parsed from redistributor candidates"))
        return [],diags
    df=pd.DataFrame(all_rows)
    df["date_dt"]=pd.to_datetime(df["date"],errors="coerce")
    df["value"]=pd.to_numeric(df["value"],errors="coerce")
    df=df.dropna(subset=["date_dt","value"]).sort_values("date_dt").drop_duplicates(["market","indicator","date"],keep="last").tail(252)
    rows=df.drop(columns=["date_dt"]).to_dict("records")
    latest=f"{df.date.iloc[-1]}={df.value.iloc[-1]}" if not df.empty else ""
    status="accepted" if len(df)>=20 else "partial"
    reason="Redistributor history below 20 rows; keep latest-card fallback if needed" if status=="partial" else "Redistributor-only due MAS secure endpoint runtime failures"
    diags.append(mk_diag(market,adapter," | ".join(u for _,u in urls),status,len(df),latest,reason))
    return rows,diags

# ---------- merge ----------
def merge_and_trim(new_rows):
    df_new=pd.DataFrame(new_rows)
    if df_new.empty: return df_new
    if RATES_OUT.exists():
        try: df=pd.concat([pd.read_csv(RATES_OUT),df_new],ignore_index=True)
        except Exception: df=df_new
    else: df=df_new
    df["date_dt"]=pd.to_datetime(df["date"],errors="coerce")
    df["value"]=pd.to_numeric(df["value"],errors="coerce")
    df=df.dropna(subset=["market","indicator","date_dt","value"])
    df=df.sort_values(["market","indicator","date_dt"])
    df=df.drop_duplicates(["market","indicator","date"],keep="last")
    df=df.groupby(["market","indicator"],group_keys=False).tail(252)
    df=df.drop(columns=["date_dt"])
    cols=["market","indicator","date","value","unit","source","source_type","frequency","notes"]
    for c in cols:
        if c not in df.columns: df[c]=""
    return df[cols]

def main():
    all_rows=[]; all_diag=[]
    for fetcher in [fetch_us_dgs10,fetch_hk_hibor,fetch_my_bnm_opr,fetch_jp_boj_call_rate,fetch_sg_sora_history]:
        rows,diag=fetcher(); all_rows.extend(rows); all_diag.extend(diag)
    final_df=merge_and_trim(all_rows)
    final_df.to_csv(RATES_OUT,index=False,encoding="utf-8-sig")
    pd.DataFrame(all_diag).to_csv(DIAG_OUT,index=False,encoding="utf-8-sig")
    print(f"Wrote {len(final_df)} row(s) to {RATES_OUT}")
    print(f"Wrote {len(all_diag)} diagnostic row(s) to {DIAG_OUT}")
    if not final_df.empty: print(final_df.groupby("market").size().to_string())

if __name__ == "__main__": main()
