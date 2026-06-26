#!/usr/bin/env python3
"""
rates_history_lab_test_v4.py

Global20Engine rates-history lab v4.

Purpose
-------
1) Keep proven v2/v3 outputs for US, HK and MY.
2) Improve JP by using BOJ Time-Series API with pagination + wider JSON/CSV parsers.
3) Improve SG by keeping redistributor daily SORA history and adding a separate
   SingStat/data.gov.sg monthly backtesting file. SingStat monthly matrix is NOT
   treated as daily SORA; it is a low-frequency backtesting supplement.

Outputs
-------
macro_pack_latest/rates_history_252d.csv
macro_pack_latest/rates_history_diagnostics.csv
macro_pack_latest/sg_rates_backtest_monthly.csv
macro_pack_latest/jp_boj_raw_preview.txt          # only when JP still low-row
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
SG_MONTHLY_OUT = OUT_DIR / "sg_rates_backtest_monthly.csv"
JP_PREVIEW_OUT = OUT_DIR / "jp_boj_raw_preview.txt"
USER_AGENT = "Global20Engine-rates-history-lab/4.0"


def request_text(url, headers=None, timeout=90):
    h = {"User-Agent": USER_AGENT, "Accept":"application/json,text/csv,text/plain,text/html,*/*", "Accept-Encoding":"identity"}
    if headers: h.update(headers)
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8-sig", errors="replace"), ""
    except Exception as exc:
        return "", str(exc)


def clean_number(v):
    try:
        if v is None: return None
        s = str(v).replace(",", "").replace("%", "").replace("+", "").strip()
        if s in ["", "na", "n.a.", "N.A.", "-", "--", "—", ".", "None", "null"]: return None
        return float(s)
    except Exception:
        return None


def parse_date(x, dayfirst=False):
    if x is None or not str(x).strip(): return pd.NaT
    s = str(x).strip()
    if re.fullmatch(r"\d{8}", s): return pd.to_datetime(s, format="%Y%m%d", errors="coerce")
    if re.fullmatch(r"\d{6}", s): return pd.to_datetime(s + "01", format="%Y%m%d", errors="coerce")
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", s): return pd.to_datetime(s, errors="coerce")
    if re.fullmatch(r"20\d{2}\s+[A-Za-z]{3,9}", s): return pd.to_datetime(s, errors="coerce")
    if re.fullmatch(r"[A-Za-z]{3,9}\s+20\d{2}", s): return pd.to_datetime("01 " + s, errors="coerce")
    if dayfirst and re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", s): return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    return pd.to_datetime(s, errors="coerce", dayfirst=dayfirst)


def mk_row(market, date, value, source, source_type="Official API", frequency="daily", notes=""):
    return {"market":market,"indicator":"Rates","date":pd.Timestamp(date).strftime("%Y-%m-%d") if pd.notna(date) else "","value":value,"unit":"%","source":source,"source_type":source_type,"frequency":frequency,"notes":notes}


def mk_diag(market, adapter, endpoint, status, rows=0, latest="", reason=""):
    return {"market":market,"adapter":adapter,"endpoint":endpoint,"status":status,"rows":int(rows or 0),"latest":latest,"reason":reason,"tested_at":datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}


def flatten_record(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list)): out.update(flatten_record(v, key))
            else: out[key] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            key = f"{prefix}.{i}" if prefix else str(i)
            if isinstance(v, (dict, list)): out.update(flatten_record(v, key))
            else: out[key] = v
    return out

# ---------------------------------------------------------------------------
# US
# ---------------------------------------------------------------------------
def fetch_us_yahoo_tnx():
    market="US"; adapter="Yahoo ^TNX daily fallback"
    url="https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=1y&interval=1d"
    txt, err = request_text(url, headers={"Accept":"application/json,*/*"})
    if not txt: return [], mk_diag(market, adapter, url, "failed", reason=err)
    try:
        res = (json.loads(txt).get("chart", {}).get("result") or [None])[0]
        if not res: return [], mk_diag(market, adapter, url, "failed", reason="No Yahoo chart result")
        ts = res.get("timestamp") or []
        closes = (((res.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
        rows=[]
        for t,c in zip(ts, closes):
            val=clean_number(c)
            if val is None: continue
            dt=pd.to_datetime(int(t),unit="s",utc=True).tz_convert(None).normalize()
            rows.append(mk_row(market,dt,val,"Yahoo Finance ^TNX","Market data","daily","Fallback when FRED DGS10 times out"))
        df=pd.DataFrame(rows)
        if df.empty: return [], mk_diag(market,adapter,url,"failed",reason="No usable ^TNX values")
        df["date_dt"]=pd.to_datetime(df["date"],errors="coerce")
        df=df.dropna(subset=["date_dt"]).sort_values("date_dt").drop_duplicates(["market","indicator","date"],keep="last").tail(252)
        return df.drop(columns=["date_dt"]).to_dict("records"), mk_diag(market,adapter,url,"accepted",len(df),f"{df.date.iloc[-1]}={df.value.iloc[-1]}")
    except Exception as exc: return [], mk_diag(market,adapter,url,"failed",reason=str(exc))


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

# ---------------------------------------------------------------------------
# HK
# ---------------------------------------------------------------------------
def fetch_hk_hibor():
    market="HK"; adapter="HKMA daily HIBOR"
    url="https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily?pagesize=1000&sortby=end_of_day&sortorder=desc"
    txt,err=request_text(url)
    if not txt: return [],[mk_diag(market,adapter,url,"failed",reason=err)]
    try:
        payload=json.loads(txt); records=payload.get("result",{}).get("records") or payload.get("result",{}).get("data") or []
        rows=[]
        for rec in records:
            if not isinstance(rec,dict): continue
            dt=parse_date(rec.get("end_of_day") or rec.get("date")); val=None; used=""
            for k in ["hibor_1m","ir_1m","one_month","1m","overnight","ir_overnight","value"]:
                if k in rec:
                    val=clean_number(rec.get(k)); used=k
                    if val is not None: break
            if pd.notna(dt) and val is not None: rows.append(mk_row(market,dt,val,f"HKMA HIBOR daily ({used})","Official API","daily"))
        df=pd.DataFrame(rows)
        if df.empty: return [],[mk_diag(market,adapter,url,"failed",rows=len(records),reason="No recognised HIBOR value parsed")]
        df["date_dt"]=pd.to_datetime(df["date"],errors="coerce")
        df=df.dropna(subset=["date_dt"]).sort_values("date_dt").drop_duplicates(["market","indicator","date"],keep="last").tail(252)
        return df.drop(columns=["date_dt"]).to_dict("records"),[mk_diag(market,adapter,url,"accepted",len(df),f"{df.date.iloc[-1]}={df.value.iloc[-1]}")]
    except Exception as exc: return [],[mk_diag(market,adapter,url,"failed",reason=str(exc))]

# ---------------------------------------------------------------------------
# MY
# ---------------------------------------------------------------------------
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


def parse_bnm_policy_points(records):
    value_keys=["new_opr_level","new_opr","opr_level","opr","OPR","rate","interest_rate","value"]
    pts=[]
    for rec in records:
        if not isinstance(rec,dict): continue
        flat=flatten_record(rec); dt=pd.NaT; val=None
        for k,v in flat.items():
            if "date" in k.split(".")[-1].lower():
                cand=parse_date(v,dayfirst=True)
                if pd.notna(cand): dt=cand; break
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
    for y in years: urls += [f"https://api.bnm.gov.my/public/opr/year/{y}", f"https://api.bnm.gov.my/public/opr?year={y}"]
    diags=[]; pts=[]
    for url in urls:
        txt,err=request_text(url,headers=headers)
        if not txt: diags.append(mk_diag(market,adapter,url,"failed",reason=err)); continue
        try:
            records=json_records_from_payload(json.loads(txt)); got=parse_bnm_policy_points(records); pts+=got
            diags.append(mk_diag(market,adapter,url,"reached",rows=len(records),reason=f"Parsed {len(got)} candidate policy records"))
        except Exception as exc: diags.append(mk_diag(market,adapter,url,"failed",reason=str(exc)))
    if not pts: return [], diags+[mk_diag(market,adapter," | ".join(urls[:3]),"failed",reason="No BNM OPR policy points parsed")]
    policy=pd.DataFrame(pts,columns=["date","value"]).dropna().sort_values("date").drop_duplicates("date",keep="last")
    start=min(policy.date.min(), pd.Timestamp.today()-pd.offsets.BDay(320)); idx=pd.bdate_range(start=start,end=pd.Timestamp.today().normalize())
    step=policy.set_index("date").reindex(idx).ffill().dropna().tail(252)
    rows=[mk_row(market,dt,float(r.value),"BNM OpenAPI Overnight Policy Rate (OPR)","Official API","policy_step","Expanded to business-day step series from official policy dates") for dt,r in step.iterrows()]
    latest="" if step.empty else f"{step.index[-1].date()}={step.value.iloc[-1]}"
    return rows,diags+[mk_diag(market,adapter," | ".join(urls[:3]),"accepted",len(rows),latest,f"Policy points parsed={len(policy)}")]

# ---------------------------------------------------------------------------
# JP v4: BOJ API pagination + wide parser
# ---------------------------------------------------------------------------
def extract_pairs_from_nested_lists(obj):
    """Pairs any date-like list with numeric list of similar length."""
    date_lists=[]; num_lists=[]
    def collect(x,path=""):
        if isinstance(x,list):
            dates=[]; nums=[]
            for item in x:
                d=parse_date(item); n=clean_number(item)
                if pd.notna(d): dates.append(pd.Timestamp(d))
                if n is not None and -2 <= n <= 25: nums.append(float(n))
            if len(dates)>=20: date_lists.append((path,dates))
            if len(nums)>=20: num_lists.append((path,nums))
            for i,v in enumerate(x): collect(v,f"{path}.{i}")
        elif isinstance(x,dict):
            for k,v in x.items(): collect(v,f"{path}.{k}" if path else str(k))
    collect(obj)
    pairs=[]
    for _,dates in date_lists:
        for _,nums in num_lists:
            if abs(len(dates)-len(nums)) <= 2:
                n=min(len(dates),len(nums)); pairs += list(zip(dates[:n],nums[:n])); return pairs
    return pairs


def extract_pairs_record_style(obj):
    pairs=[]; date_keys={"TIME_PERIOD","time_period","date","Date","time","period","TIME"}; value_keys={"OBS_VALUE","obs_value","value","Value","rate","Rate"}
    def walk(x):
        if isinstance(x,dict):
            flat=flatten_record(x); dt=pd.NaT; val=None
            for k,v in flat.items():
                kk=k.split(".")[-1]
                if kk in date_keys or kk.lower() in {z.lower() for z in date_keys}:
                    cand=parse_date(v)
                    if pd.notna(cand): dt=cand; break
            for k,v in flat.items():
                kk=k.split(".")[-1]
                if kk in value_keys or kk.lower() in {z.lower() for z in value_keys}:
                    vv=clean_number(v)
                    if vv is not None and -2 <= vv <= 25: val=vv; break
            if pd.notna(dt) and val is not None: pairs.append((pd.Timestamp(dt),float(val)))
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            if len(x)>=2:
                d=parse_date(x[0]); v=clean_number(x[1])
                if pd.notna(d) and v is not None and -2 <= v <= 25: pairs.append((pd.Timestamp(d),float(v)))
            for v in x: walk(v)
    walk(obj); return pairs


def parse_boj_csv_wide(txt):
    rows=list(csv.reader(io.StringIO(txt)))
    pairs=[]
    # vertical rows: date + value in same row
    for raw in rows:
        dt_idx=None; dt=pd.NaT
        for i,cell in enumerate(raw):
            cand=parse_date(cell)
            if pd.notna(cand) and 1990 <= cand.year <= pd.Timestamp.today().year+1: dt_idx=i; dt=cand; break
        if dt_idx is not None:
            for cell in raw[dt_idx+1:]:
                val=clean_number(cell)
                if val is not None and -2 <= val <= 25: pairs.append((pd.Timestamp(dt),float(val))); break
    if len(pairs)>=20: return pairs
    # wide rows: one row has many dates; following row has aligned values
    for i,raw in enumerate(rows):
        dates=[]; positions=[]
        for j,cell in enumerate(raw):
            d=parse_date(cell)
            if pd.notna(d) and 1990 <= d.year <= pd.Timestamp.today().year+1:
                dates.append(pd.Timestamp(d)); positions.append(j)
        if len(dates)>=20:
            for next_row in rows[i+1:i+6]:
                vals=[]
                for pos in positions:
                    val=clean_number(next_row[pos] if pos < len(next_row) else None)
                    vals.append(val)
                good=sum(v is not None and -2 <= v <= 25 for v in vals)
                if good>=20:
                    for d,v in zip(dates,vals):
                        if v is not None and -2 <= v <= 25: pairs.append((d,float(v)))
                    return pairs
    return pairs


def fetch_boj_json_page(code,start,start_position=None):
    params={"format":"json","lang":"en","db":"FM01","startDate":start,"code":code}
    if start_position is not None: params["startPosition"]=str(start_position)
    url="https://www.stat-search.boj.or.jp/api/v1/getDataCode?"+urllib.parse.urlencode(params)
    txt,err=request_text(url,headers={"Accept":"application/json,*/*"})
    return url,txt,err


def find_next_position(payload):
    flat=flatten_record(payload)
    for k,v in flat.items():
        if "NEXTPOSITION" in k.upper() or "NEXT_POSITION" in k.upper() or k.upper().endswith("NEXTPOSITION"):
            n=clean_number(v)
            if n is not None and n > 0: return int(n)
    return None


def fetch_jp_boj_call_rate():
    market="JP"; adapter="BOJ FM01 STRDCLUCON daily v4"
    start=(pd.Timestamp.today()-pd.DateOffset(months=36)).strftime("%Y%m")
    diags=[]; code_candidates=["STRDCLUCON","STRDCLUCON@D"]
    for code in code_candidates:
        all_pairs=[]; next_pos=None; page=0; last_url=""
        while page < 5:
            url,txt,err=fetch_boj_json_page(code,start,next_pos); last_url=url; page+=1
            if not txt: diags.append(mk_diag(market,adapter,url,"failed",reason=err)); break
            try:
                payload=json.loads(txt)
                pairs=extract_pairs_record_style(payload) + extract_pairs_from_nested_lists(payload)
                all_pairs += pairs
                next_pos=find_next_position(payload)
                if not next_pos: break
            except Exception as exc:
                diags.append(mk_diag(market,adapter,url,"failed",reason=str(exc))); break
        if all_pairs:
            df=pd.DataFrame(all_pairs,columns=["date","value"]).dropna().sort_values("date").drop_duplicates("date",keep="last").tail(252)
            rows=[mk_row(market,r.date,float(r.value),f"BOJ FM01 STRDCLUCON JSON ({code})","Official API","daily") for r in df.itertuples(index=False)]
            latest="" if df.empty else f"{df.date.iloc[-1].date()}={df.value.iloc[-1]}"
            status="accepted" if len(rows)>=20 else "partial"
            reason="Low row count; JP raw preview written" if status=="partial" else f"Pages parsed={page}"
            if status=="partial": JP_PREVIEW_OUT.write_text(str(all_pairs[:10]) + "\n\nLast URL:\n" + last_url, encoding="utf-8")
            diags.append(mk_diag(market,adapter,last_url,status,len(rows),latest,reason)); return rows,diags
        diags.append(mk_diag(market,adapter,last_url or code,"failed",reason="JSON reached but no date/value rows parsed"))
    # CSV fallback
    for code in code_candidates:
        url="https://www.stat-search.boj.or.jp/api/v1/getDataCode?"+urllib.parse.urlencode({"format":"csv","lang":"en","db":"FM01","startDate":start,"code":code})
        txt,err=request_text(url,headers={"Accept":"text/csv,*/*"})
        if not txt: diags.append(mk_diag(market,adapter,url,"failed",reason=err)); continue
        pairs=parse_boj_csv_wide(txt)
        if pairs:
            df=pd.DataFrame(pairs,columns=["date","value"]).dropna().sort_values("date").drop_duplicates("date",keep="last").tail(252)
            rows=[mk_row(market,r.date,float(r.value),f"BOJ FM01 STRDCLUCON CSV ({code})","Official API","daily") for r in df.itertuples(index=False)]
            latest="" if df.empty else f"{df.date.iloc[-1].date()}={df.value.iloc[-1]}"
            status="accepted" if len(rows)>=20 else "partial"
            reason="Low row count; JP CSV raw preview written" if status=="partial" else "CSV wide/vertical parser"
            if status=="partial": JP_PREVIEW_OUT.write_text(txt[:4000], encoding="utf-8")
            diags.append(mk_diag(market,adapter,url,status,len(rows),latest,reason)); return rows,diags
        diags.append(mk_diag(market,adapter,url,"failed",reason="CSV reached but no vertical/wide date/value rows parsed"))
    return [],diags

# ---------------------------------------------------------------------------
# SG daily SORA + SingStat/data.gov.sg monthly backtest supplement
# ---------------------------------------------------------------------------
def extract_sora_rows_from_html(html, source_label, url):
    rows=[]; text=re.sub(r"<[^>]+>"," ",html); text=re.sub(r"\s+"," ",text)
    for m in re.finditer(r"(20\d{2}-\d{2}-\d{2})\s+(-?\d+(?:\.\d+)?)\s*%", text):
        dt=parse_date(m.group(1)); val=clean_number(m.group(2))
        if pd.notna(dt) and val is not None and -5 <= val <= 20: rows.append(mk_row("SG",dt,val,source_label,"Redistributor","daily",f"Parsed from {url}"))
    for m in re.finditer(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2})\s+(-?\d+(?:\.\d+)?)\s*%", text):
        dt=parse_date(m.group(1)); val=clean_number(m.group(2))
        if pd.notna(dt) and val is not None and -5 <= val <= 20: rows.append(mk_row("SG",dt,val,source_label,"Redistributor","daily",f"Parsed from {url}"))
    return rows


def fetch_sg_sora_history():
    market="SG"; adapter="SG SORA daily redistributor history"
    urls=[("StraitsData MAS SORA","https://straitsdata.com/finance/mas"),("ToolSG SORA Monitor","https://www.toolsg.com/en/sora-index"),("DailySORA","https://dailysora.org/")]
    diags=[]; all_rows=[]
    for label,url in urls:
        txt,err=request_text(url,headers={"Accept":"text/html,*/*"})
        if not txt: diags.append(mk_diag(market,adapter,url,"failed",reason=err)); continue
        rows=extract_sora_rows_from_html(txt,label,url); all_rows.extend(rows)
        diags.append(mk_diag(market,adapter,url,"reached",rows=len(rows),reason=f"Parsed {len(rows)} SORA candidate rows"))
    if not all_rows:
        diags.append(mk_diag(market,adapter," | ".join(u for _,u in urls),"needs_validation",0,"","No SG daily SORA rows parsed")); return [],diags
    df=pd.DataFrame(all_rows); df["date_dt"]=pd.to_datetime(df["date"],errors="coerce"); df["value"]=pd.to_numeric(df["value"],errors="coerce")
    df=df.dropna(subset=["date_dt","value"]).sort_values("date_dt").drop_duplicates(["market","indicator","date"],keep="last").tail(252)
    status="accepted" if len(df)>=20 else "partial"; latest=f"{df.date.iloc[-1]}={df.value.iloc[-1]}" if not df.empty else ""
    reason="Redistributor-only due MAS secure endpoint runtime failures" if status=="accepted" else "Daily SORA redistributor history below 20 rows"
    diags.append(mk_diag(market,adapter," | ".join(u for _,u in urls),status,len(df),latest,reason))
    return df.drop(columns=["date_dt"]).to_dict("records"),diags


def fetch_sg_singstat_monthly_backtest():
    """Low-frequency SG backtesting supplement, not daily SORA replacement."""
    market="SG"; adapter="SingStat/data.gov.sg monthly interest-rate matrix"
    url="https://data.gov.sg/api/action/datastore_search?resource_id=d_5fe5a4bb4a1ecc4d8a56a095832e2b24&limit=100"
    txt,err=request_text(url,headers={"Accept":"application/json,*/*"})
    if not txt: return [], [mk_diag(market,adapter,url,"failed",reason=err)]
    try:
        payload=json.loads(txt); records=payload.get("result",{}).get("records") or []
        rows=[]
        for rec in records:
            label=str(rec.get("Data Series") or rec.get("data_series") or rec.get("DataSeries") or "")
            if not label: continue
            # Prefer broad market/bank rate rows when no SORA row exists in this monthly table.
            if not any(tok.lower() in label.lower() for tok in ["prime", "fixed deposits 3 months", "savings deposits", "sora", "interbank"]): continue
            for k,v in rec.items():
                dt=parse_date(k)
                val=clean_number(v)
                if pd.notna(dt) and val is not None:
                    rows.append({"market":market,"indicator":"Rates","date":pd.Timestamp(dt).strftime("%Y-%m-%d"),"value":val,"unit":"%","source":f"SingStat/data.gov.sg monthly matrix - {label}","source_type":"Official data portal","frequency":"monthly_end_period","notes":"Backtesting supplement; not daily SORA"})
        df=pd.DataFrame(rows)
        if df.empty:
            return [], [mk_diag(market,adapter,url,"failed",rows=len(records),reason="No recognised monthly interest-rate rows parsed")]
        df=df.sort_values(["source","date"]).drop_duplicates(["source","date"],keep="last")
        df.to_csv(SG_MONTHLY_OUT,index=False,encoding="utf-8-sig")
        latest=f"{df.date.iloc[-1]}={df.value.iloc[-1]}" if not df.empty else ""
        return df.to_dict("records"), [mk_diag(market,adapter,url,"accepted",len(df),latest,"Written to sg_rates_backtest_monthly.csv only")]
    except Exception as exc:
        return [], [mk_diag(market,adapter,url,"failed",reason=str(exc))]

# ---------------------------------------------------------------------------
# Merge/write
# ---------------------------------------------------------------------------
def merge_and_trim(new_rows):
    df_new=pd.DataFrame(new_rows)
    if df_new.empty: return df_new
    if RATES_OUT.exists():
        try: df=pd.concat([pd.read_csv(RATES_OUT),df_new],ignore_index=True)
        except Exception: df=df_new
    else: df=df_new
    df["date_dt"]=pd.to_datetime(df["date"],errors="coerce"); df["value"]=pd.to_numeric(df["value"],errors="coerce")
    df=df.dropna(subset=["market","indicator","date_dt","value"])
    df=df.sort_values(["market","indicator","date_dt"]).drop_duplicates(["market","indicator","date"],keep="last")
    df=df.groupby(["market","indicator"],group_keys=False).tail(252).drop(columns=["date_dt"])
    cols=["market","indicator","date","value","unit","source","source_type","frequency","notes"]
    for c in cols:
        if c not in df.columns: df[c]=""
    return df[cols]


def main():
    all_rows=[]; all_diag=[]
    for fetcher in [fetch_us_dgs10,fetch_hk_hibor,fetch_my_bnm_opr,fetch_jp_boj_call_rate,fetch_sg_sora_history]:
        rows,diag=fetcher(); all_rows.extend(rows); all_diag.extend(diag)
    # SG monthly matrix is an additional output; do not mix it into daily 252D rates file.
    _, sg_monthly_diag = fetch_sg_singstat_monthly_backtest(); all_diag.extend(sg_monthly_diag)
    final_df=merge_and_trim(all_rows)
    final_df.to_csv(RATES_OUT,index=False,encoding="utf-8-sig")
    pd.DataFrame(all_diag).to_csv(DIAG_OUT,index=False,encoding="utf-8-sig")
    print(f"Wrote {len(final_df)} row(s) to {RATES_OUT}")
    print(f"Wrote {len(all_diag)} diagnostic row(s) to {DIAG_OUT}")
    if SG_MONTHLY_OUT.exists(): print(f"Wrote SG monthly backtest file to {SG_MONTHLY_OUT}")
    if JP_PREVIEW_OUT.exists(): print(f"Wrote JP raw preview to {JP_PREVIEW_OUT}")
    if not final_df.empty: print(final_df.groupby("market").size().to_string())

if __name__ == "__main__": main()
