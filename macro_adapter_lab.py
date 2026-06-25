
# macro_adapter_lab.py
# Global20Engine Macro Adapter Lab v5 - HK CPI + SG/JP Rates diagnostics

import csv
import io
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Global20Engine Macro Adapter Lab", layout="wide", initial_sidebar_state="expanded")

USER_AGENT = "Mozilla/5.0 Global20Engine-MacroAdapterLab/5.0"
TIMEOUT = 30

STANDARD_COLS = ["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"]
APAC_RATE_KEYS = {("SG", "RATES"), ("MY", "RATES"), ("HK", "RATES"), ("JP", "RATES")}

HK_CSD_CPI_URL = "https://www.censtatd.gov.hk/api/get.php?id=510-60001&lang=en&full_series=1"
HK_COMPOSITE_CPI_YOY_SV = "CC_CM_1920"

MAS_SORA_RESOURCE_ID = "9a0bf149-308c-4bd2-832d-76c8e6cb47ed"
MAS_SORA_URL = "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_SORA_RESOURCE_ID, "limit": "5000"})

BOJ_API_BASE = "https://www.stat-search.boj.or.jp/api/v1"
BOJ_FM01_CODES = [
    "STRDCLUCON", "STRDCLUCON@D", "FM01.STRDCLUCON", "FM01.STRDCLUCON@D",
    "STRDCLACD", "STRDCLACD@D", "STRDCLUCONA", "STRDCLUCONA@D",
]


def request_text(url, label="request", headers=None):
    h = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "identity"}
    if headers:
        h.update(headers)
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            return {
                "label": label,
                "ok": True,
                "status": getattr(resp, "status", ""),
                "content_type": resp.headers.get("Content-Type", ""),
                "bytes": len(raw),
                "started_utc": started,
                "url": url,
                "text": raw.decode("utf-8", errors="replace"),
                "error": "",
            }
    except Exception as e:
        return {"label": label, "ok": False, "status": "", "content_type": "", "bytes": 0, "started_utc": started, "url": url, "text": "", "error": repr(e)}


def clean_number(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s or s.upper() in {"N.A.", "NA", "N/A", "NULL", "NONE", "-", "--", "."}:
        return None
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = s.replace("+", "").replace("%", "").replace(",", "").replace("−", "-").replace("–", "-")
    try:
        v = float(s.strip())
        return v
    except Exception:
        return None


def parse_date_any(x):
    s = str(x).strip()
    if re.fullmatch(r"\d{8}", s):
        return pd.to_datetime(f"{s[:4]}-{s[4:6]}-{s[6:8]}", errors="coerce")
    if re.fullmatch(r"\d{6}", s):
        return pd.to_datetime(f"{s[:4]}-{s[4:6]}-01", errors="coerce")
    return pd.to_datetime(s, errors="coerce")


# -------------------- HK Inflation proven parser --------------------
def fetch_hk_csd_composite_cpi_yoy():
    r = request_text(HK_CSD_CPI_URL, "HK C&SD 510-60001 JSON API", headers={"Accept": "application/json,text/plain,*/*"})
    debug = {k: v for k, v in r.items() if k != "text"}
    if not r["ok"]:
        return None, debug, pd.DataFrame()
    payload = json.loads(r["text"])
    df = pd.DataFrame(payload.get("dataSet", []))
    debug["dataset_rows"] = len(df)
    debug["dataset_cols"] = ", ".join(df.columns) if not df.empty else ""
    if df.empty or not {"period", "sv", "figure"}.issubset(df.columns):
        debug["result"] = "missing dataSet/period/sv/figure"
        return None, debug, df
    target = df[df["sv"].astype(str).str.strip().eq(HK_COMPOSITE_CPI_YOY_SV)].copy()
    target["date"] = target["period"].apply(parse_date_any)
    target["value"] = target["figure"].map(clean_number)
    valid = target.dropna(subset=["date", "value"])
    valid = valid[(valid["value"] > -10) & (valid["value"] < 20)].sort_values("date")
    if valid.empty:
        debug["result"] = "target sv found but no valid figure"
        return None, debug, target.tail(50)
    latest = valid.iloc[-1]
    row = {"market":"HK","indicator":"Inflation","date":latest["date"].strftime("%Y-%m-%d"),"value":float(latest["value"]),"unit":"%","source":"C&SD Table 510-60001 Composite CPI YoY","source_type":"Official / API Lab","notes":f"sv={HK_COMPOSITE_CPI_YOY_SV}; period={latest['period']}; figure column."}
    debug["result"] = "ok"
    return row, debug, valid.tail(50)


# -------------------- SG MAS SORA diagnostics --------------------
def fetch_sg_mas_sora_lab():
    r = request_text(MAS_SORA_URL, "SG MAS SORA datastore/search.json", headers={"Accept": "application/json,text/plain,*/*"})
    debug = {k: v for k, v in r.items() if k != "text"}
    if not r["ok"]:
        return None, debug, pd.DataFrame(), pd.DataFrame()
    try:
        payload = json.loads(r["text"])
        result = payload.get("result", {})
        records = result.get("records", [])
        df = pd.DataFrame(records)
        debug["records"] = len(df)
        debug["columns"] = ", ".join(df.columns.astype(str)) if not df.empty else ""
    except Exception as e:
        debug["result"] = f"json parse error: {e!r}"
        return None, debug, pd.DataFrame(), pd.DataFrame()

    if df.empty:
        debug["result"] = "no records returned"
        return None, debug, df, pd.DataFrame()

    date_cols = [c for c in df.columns if str(c).lower() in {"end_of_day", "date", "timestamp"} or "date" in str(c).lower()]
    value_priority = ["sora", "SORA", "sora_rate", "SORA_RATE", "comp_sora_1m", "comp_sora_3m", "comp_sora_6m"]
    candidate_rows = []
    for vc in value_priority:
        if vc not in df.columns:
            continue
        dc = date_cols[0] if date_cols else None
        temp = df[[dc, vc]].copy() if dc else df[[vc]].copy()
        temp["date"] = temp[dc].apply(parse_date_any) if dc else pd.NaT
        temp["value"] = temp[vc].map(clean_number)
        temp["field"] = vc
        temp = temp.dropna(subset=["value"])
        if not temp.empty:
            candidate_rows.append(temp[["date", "value", "field"]].copy())
    candidates = pd.concat(candidate_rows, ignore_index=True) if candidate_rows else pd.DataFrame()
    if candidates.empty:
        debug["result"] = "records returned but no SORA numeric field parsed"
        return None, debug, df.head(50), candidates
    candidates = candidates.dropna(subset=["date"]).sort_values("date") if "date" in candidates.columns else candidates
    latest = candidates.iloc[-1]
    row = {"market":"SG","indicator":"Rates","date":latest["date"].strftime("%Y-%m-%d") if pd.notna(latest["date"]) else "Latest","value":float(latest["value"]),"unit":"%","source":f"MAS Domestic Interest Rates {latest['field']}","source_type":"Official / API Lab","notes":f"resource_id={MAS_SORA_RESOURCE_ID}; field={latest['field']}"}
    debug["result"] = "ok"
    return row, debug, df.head(50), candidates.tail(50)


# -------------------- JP BOJ FM01 diagnostics --------------------
def parse_boj_json_or_csv(text, fmt, code):
    rows = []
    if fmt == "json":
        try:
            payload = json.loads(text)
        except Exception as e:
            return pd.DataFrame(), f"json parse error: {e!r}"
        # recursively find dicts with date/period/time and value-like fields
        def walk(x):
            if isinstance(x, dict):
                keys = {str(k).lower(): k for k in x.keys()}
                date_key = next((keys[k] for k in keys if k in {"date", "time", "period", "time_period"} or "date" in k or "period" in k), None)
                val_key = next((keys[k] for k in keys if k in {"value", "val", "obs_value", "figure"}), None)
                if date_key and val_key:
                    rows.append({"date_raw": x.get(date_key), "value_raw": x.get(val_key), "code": code})
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(payload)
        df = pd.DataFrame(rows)
    else:
        try:
            df0 = pd.read_csv(io.StringIO(text))
        except Exception as e:
            return pd.DataFrame(), f"csv parse error: {e!r}"
        date_cols = [c for c in df0.columns if str(c).lower() in {"date", "time", "period", "time_period"} or "date" in str(c).lower() or "period" in str(c).lower()]
        val_cols = [c for c in df0.columns if c not in date_cols]
        recs = []
        for _, r in df0.iterrows():
            date_raw = r[date_cols[0]] if date_cols else ""
            for vc in val_cols:
                val = clean_number(r.get(vc))
                if val is not None:
                    recs.append({"date_raw": date_raw, "value_raw": val, "value_col": vc, "code": code})
                    break
        df = pd.DataFrame(recs)
    if df.empty:
        return df, "no date/value rows parsed"
    df["date"] = df["date_raw"].apply(parse_date_any)
    df["value"] = df["value_raw"].map(clean_number)
    df = df.dropna(subset=["value"])
    return df, "ok" if not df.empty else "no numeric value parsed"


def fetch_jp_boj_fm01_lab():
    start = (pd.Timestamp.today() - pd.DateOffset(months=18)).strftime("%Y%m")
    diagnostics = []
    parsed_all = []
    raw_samples = []
    for code in BOJ_FM01_CODES:
        for fmt in ["json", "csv"]:
            url = f"{BOJ_API_BASE}/getDataCode?" + urllib.parse.urlencode({"format": fmt, "lang": "en", "db": "FM01", "startDate": start, "code": code})
            r = request_text(url, f"JP BOJ FM01 {code} {fmt}", headers={"Accept": "application/json,text/csv,*/*"})
            d = {k: v for k, v in r.items() if k != "text"}
            d["code"] = code; d["format"] = fmt
            if r["ok"]:
                parsed, msg = parse_boj_json_or_csv(r["text"], fmt, code)
                d["parse_result"] = msg
                d["parsed_rows"] = len(parsed)
                if not parsed.empty:
                    parsed_all.append(parsed)
                raw_samples.append({"code": code, "format": fmt, "sample": r["text"][:1000]})
            diagnostics.append(d)
    diag_df = pd.DataFrame(diagnostics)
    parsed_df = pd.concat(parsed_all, ignore_index=True) if parsed_all else pd.DataFrame()
    if parsed_df.empty:
        return None, diag_df, parsed_df, pd.DataFrame(raw_samples)
    parsed_df = parsed_df.dropna(subset=["date"]).sort_values("date") if "date" in parsed_df.columns else parsed_df
    latest = parsed_df.iloc[-1]
    row = {"market":"JP","indicator":"Rates","date":latest["date"].strftime("%Y-%m-%d") if pd.notna(latest["date"]) else "Latest","value":float(latest["value"]),"unit":"%","source":f"BOJ FM01 Uncollateralized Overnight Call Rate ({latest['code']})","source_type":"Official / API Lab","notes":"Parsed from BOJ Time-Series Data Search API getDataCode."}
    return row, diag_df, parsed_df.tail(100), pd.DataFrame(raw_samples)


def clean_macro_pack(df):
    df = df.copy()
    for c in STANDARD_COLS:
        if c not in df.columns:
            df[c] = ""
    mask_remove = df.apply(lambda r: (str(r["market"]).strip().upper(), str(r["indicator"]).strip().upper()) in APAC_RATE_KEYS, axis=1)
    cleaned = df.loc[~mask_remove].copy()
    return cleaned[STANDARD_COLS + [c for c in cleaned.columns if c not in STANDARD_COLS]]


st.title("Global20Engine Macro Adapter Lab")
st.caption("Isolated tester for macro/rate source ideas before production updates.")

with st.sidebar:
    st.header("Test controls")
    run_hk = st.button("Run HK Inflation test", use_container_width=True)
    run_sg = st.button("Run SG MAS SORA test", use_container_width=True)
    run_jp = st.button("Run JP BOJ FM01 test", use_container_width=True)
    run_all = st.button("Run all current tests", use_container_width=True)
    uploaded = st.file_uploader("Optional: upload macro_data.csv", type=["csv"])

if run_all:
    run_hk = run_sg = run_jp = True

if run_hk:
    st.header("HK Inflation dynamic fetch result")
    row, debug, parsed = fetch_hk_csd_composite_cpi_yoy()
    if row:
        st.success("HK Inflation parsed successfully.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.error("HK Inflation not parsed.")
    st.subheader("HK diagnostics")
    st.dataframe(pd.DataFrame([debug]), use_container_width=True)
    st.subheader("HK parsed rows preview")
    st.dataframe(parsed, use_container_width=True)

if run_sg:
    st.header("SG MAS SORA diagnostic result")
    row, debug, records_preview, candidates = fetch_sg_mas_sora_lab()
    if row:
        st.success("SG SORA parsed successfully.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.error("SG SORA not parsed.")
    st.subheader("SG diagnostics")
    st.dataframe(pd.DataFrame([debug]), use_container_width=True)
    st.subheader("MAS records preview")
    st.dataframe(records_preview, use_container_width=True)
    st.subheader("SORA parsed candidate rows")
    st.dataframe(candidates, use_container_width=True)

if run_jp:
    st.header("JP BOJ FM01 diagnostic result")
    row, diag_df, parsed_df, raw_df = fetch_jp_boj_fm01_lab()
    if row:
        st.success("JP BOJ FM01 parsed successfully.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.error("JP BOJ FM01 not parsed by current candidate codes.")
    st.subheader("JP diagnostics by code/format")
    st.dataframe(diag_df, use_container_width=True)
    st.subheader("JP parsed rows")
    st.dataframe(parsed_df, use_container_width=True)
    with st.expander("BOJ raw response samples", expanded=False):
        st.dataframe(raw_df, use_container_width=True)

if uploaded is not None:
    st.header("Macro pack cleaner preview")
    original = pd.read_csv(uploaded)
    cleaned = clean_macro_pack(original)
    st.write("Original rows", len(original), "Cleaned rows", len(cleaned))
    st.dataframe(cleaned, use_container_width=True)
    st.download_button("Download cleaned macro_data.csv", data=cleaned.to_csv(index=False).encode("utf-8"), file_name="macro_data_cleaned.csv", mime="text/csv", use_container_width=True)

st.markdown("""
### Current source policy
- HK Inflation: proven dynamic C&SD Table 510-60001 parser using `sv=CC_CM_1920`.
- SG Rates: diagnose MAS Domestic Interest Rates resource `9a0bf149-308c-4bd2-832d-76c8e6cb47ed`.
- JP Rates: diagnose BOJ Time-Series Data Search API `FM01` with candidate codes.
""")
