
# macro_rate_diagnostics_lab.py
# Global20Engine Rate Diagnostics Lab v4 - SG MAS + Trading Economics fallback test + JP BOJ confirmation

import csv
import io
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Global20Engine Rate Diagnostics Lab", layout="wide")

USER_AGENT = "Mozilla/5.0 Global20Engine-RateDiagnosticsLab/4.0"
TIMEOUT = 30

MAS_RESOURCE_ID = "9a0bf149-308c-4bd2-832d-76c8e6cb47ed"

MAS_URLS = [
    {"label": "MAS generic eservices route", "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "5000"})},
    {"label": "MAS GitHub open-source exact route - comp_sora_1m", "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "100", "fields": "end_of_day,comp_sora_1m", "sort": "end_of_day desc"})},
    {"label": "MAS GitHub open-source broad SORA fields", "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "100", "fields": "end_of_day,sora,sora_index,comp_sora_1m,comp_sora_3m,comp_sora_6m", "sort": "end_of_day desc"})},
    {"label": "MAS secure datastore route", "url": "https://secure.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "5000"})},
    {"label": "MAS secure API description page", "url": "https://secure.mas.gov.sg/api/APIDescPage.aspx?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID})},
]

TE_INDICATOR_CANDIDATES = [
    "sora",
    "singapore overnight rate average",
    "compounded sora",
    "interest rate",
    "interbank rate",
]


def request_text(url, label, accept="*/*"):
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            return {"label": label, "ok": True, "status": getattr(resp, "status", ""), "content_type": resp.headers.get("Content-Type", ""), "bytes": len(raw), "started_utc": started, "url": url, "text": raw.decode("utf-8", errors="replace"), "error": ""}
    except Exception as e:
        return {"label": label, "ok": False, "status": "", "content_type": "", "bytes": 0, "started_utc": started, "url": url, "text": "", "error": repr(e)}


def clean_number(x):
    if x is None:
        return None
    s = str(x).strip().strip('"').strip("'")
    if not s or s.upper() in {"N.A.", "N/A", "NA", "NULL", "NONE", "-", "--", "."}:
        return None
    s = re.sub(r"\[[^\]]*\]", "", s).replace("+", "").replace("%", "").replace(",", "").replace("−", "-").replace("–", "-")
    try:
        return float(s)
    except Exception:
        return None


def parse_date_any(x):
    s = str(x).strip().strip('"').strip("'")
    if re.fullmatch(r"\d{8}", s):
        return pd.to_datetime(f"{s[:4]}-{s[4:6]}-{s[6:8]}", errors="coerce")
    if re.fullmatch(r"\d{6}", s):
        return pd.to_datetime(f"{s[:4]}-{s[4:6]}-01", errors="coerce")
    return pd.to_datetime(s, errors="coerce")


def classify_non_json(text):
    t = (text or "").lower()
    if "maintenance" in t or "service is currently unavailable" in t:
        return "HTML maintenance/unavailable page"
    if "doctype html" in t or "<html" in t:
        return "HTML page, not JSON"
    if not text:
        return "empty response"
    return "non-JSON response"


# ---------------- SG MAS official-route diagnostics ----------------
def parse_mas_records(payload, source_label, source_url):
    recs = payload.get("result", {}).get("records", [])
    df = pd.DataFrame(recs)
    if df.empty:
        return df, pd.DataFrame(), "JSON returned but result.records empty"

    date_cols = [c for c in df.columns if str(c).lower() in {"end_of_day", "date", "timestamp"} or "date" in str(c).lower()]
    value_priority = ["sora", "SORA", "sora_rate", "SORA_RATE", "comp_sora_1m", "comp_sora_3m", "comp_sora_6m"]
    candidate_rows = []
    for vc in value_priority:
        if vc not in df.columns:
            continue
        dc = date_cols[0] if date_cols else None
        tmp = df[[dc, vc]].copy() if dc else df[[vc]].copy()
        tmp["date"] = tmp[dc].apply(parse_date_any) if dc else pd.NaT
        tmp["value"] = tmp[vc].map(clean_number)
        tmp["field"] = vc
        tmp["route"] = source_label
        tmp["source_url"] = source_url
        tmp = tmp.dropna(subset=["value"])
        if not tmp.empty:
            candidate_rows.append(tmp[["date", "value", "field", "route", "source_url"]])
    candidates = pd.concat(candidate_rows, ignore_index=True) if candidate_rows else pd.DataFrame()
    return df, candidates, "ok" if not candidates.empty else "records returned but no SORA numeric field parsed"


def run_mas_deep():
    diagnostics, samples, parsed_all, records_previews = [], [], [], []
    for route in MAS_URLS:
        label, url = route["label"], route["url"]
        r = request_text(url, label, accept="application/json,text/html,*/*")
        d = {k: v for k, v in r.items() if k != "text"}
        d["route_label"] = label
        d["classification"] = ""
        if not r["ok"]:
            d["parse_result"] = "request failed"
        elif "json" not in r.get("content_type", "").lower():
            d["classification"] = classify_non_json(r["text"])
            d["parse_result"] = "not JSON"
        else:
            try:
                payload = json.loads(r["text"])
                recs_df, candidates, msg = parse_mas_records(payload, label, url)
                d["parse_result"] = msg
                d["records"] = len(recs_df)
                d["columns"] = ", ".join(map(str, recs_df.columns)) if not recs_df.empty else ""
                if not recs_df.empty:
                    rp = recs_df.head(30).copy(); rp["route_label"] = label; records_previews.append(rp)
                if not candidates.empty:
                    parsed_all.append(candidates)
            except Exception as e:
                d["parse_result"] = f"JSON parse error: {e!r}"
        diagnostics.append(d)
        samples.append({"route_label": label, "url": url, "sample": r["text"][:3000]})
    parsed = pd.concat(parsed_all, ignore_index=True) if parsed_all else pd.DataFrame()
    records_preview = pd.concat(records_previews, ignore_index=True) if records_previews else pd.DataFrame()
    result_row = None
    if not parsed.empty:
        parsed = parsed.dropna(subset=["date"]).sort_values("date")
        latest = parsed.iloc[-1]
        result_row = {"market": "SG", "indicator": "Rates", "date": latest["date"].strftime("%Y-%m-%d"), "value": float(latest["value"]), "unit": "%", "source": f"MAS Domestic Interest Rates {latest['field']}", "source_type": "Official / API Lab", "notes": f"Parsed from route={latest['route']}; resource_id={MAS_RESOURCE_ID}; field={latest['field']}."}
    return result_row, pd.DataFrame(diagnostics), pd.DataFrame(samples), records_preview, parsed


# ---------------- Trading Economics fallback diagnostics ----------------
def parse_te_payload(text):
    try:
        payload = json.loads(text)
    except Exception as e:
        return pd.DataFrame(), f"JSON parse error: {e!r}"
    if isinstance(payload, dict):
        if "message" in {str(k).lower() for k in payload.keys()}:
            return pd.DataFrame([payload]), "JSON dict response; inspect message"
        return pd.DataFrame([payload]), "JSON dict response"
    if isinstance(payload, list):
        return pd.DataFrame(payload), "JSON list response"
    return pd.DataFrame(), f"unexpected JSON type {type(payload).__name__}"


def extract_te_candidates(df, route_label, url):
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    # Standard TE indicator historical fields include Country, Category, DateTime, Value, Frequency, HistoricalDataSymbol, LastUpdate.
    # Some endpoints use Close instead of Value.
    date_col = next((c for c in out.columns if str(c).lower() in {"datetime", "date", "latestvaluedate"} or "date" in str(c).lower()), None)
    value_col = next((c for c in out.columns if str(c).lower() in {"value", "close", "latestvalue"}), None)
    cat_col = next((c for c in out.columns if str(c).lower() in {"category", "indicator", "name"}), None)
    if not value_col:
        return pd.DataFrame()
    out["date"] = out[date_col].apply(parse_date_any) if date_col else pd.NaT
    out["value"] = out[value_col].map(clean_number)
    out["category_text"] = out[cat_col].astype(str) if cat_col else ""
    out["route"] = route_label
    out["source_url"] = url
    out = out.dropna(subset=["value"])
    # Do not force exact SORA here; expose all returned candidates, and mark exactness.
    if not out.empty:
        out["sora_match"] = out["category_text"].str.lower().str.contains("sora|singapore overnight rate average|compounded sora", regex=True, na=False)
        cols = [c for c in ["date", "value", "category_text", "sora_match", "route", "source_url", "Country", "Category", "Frequency", "HistoricalDataSymbol", "LastUpdate"] if c in out.columns]
        return out[cols]
    return pd.DataFrame()


def run_te_deep(te_key_secret):
    diagnostics, samples, records, candidates_all = [], [], [], []
    cred = (te_key_secret or "").strip()
    if not cred:
        return None, pd.DataFrame([{"route_label": "Trading Economics", "parse_result": "missing key:secret input"}]), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Endpoint patterns supported by TE docs: historical/country/{country}/indicator/{indicator}?c={key}&f=json
    # Also test snapshot country/indicator route because it is useful for latest values.
    routes = []
    for indicator in TE_INDICATOR_CANDIDATES:
        enc = urllib.parse.quote(indicator, safe="")
        routes.append({"label": f"TE historical Singapore / {indicator}", "url": f"https://api.tradingeconomics.com/historical/country/singapore/indicator/{enc}?" + urllib.parse.urlencode({"c": cred, "f": "json"})})
        routes.append({"label": f"TE snapshot Singapore / {indicator}", "url": f"https://api.tradingeconomics.com/country/singapore/indicator/{enc}?" + urllib.parse.urlencode({"c": cred, "f": "json"})})

    for route in routes:
        label, url = route["label"], route["url"]
        # Hide credential in displayed URL/sample table.
        display_url = url.replace(cred, "***")
        r = request_text(url, label, accept="application/json,text/html,*/*")
        d = {k: v for k, v in r.items() if k not in {"text", "url"}}
        d["url"] = display_url
        d["route_label"] = label
        if not r["ok"]:
            d["parse_result"] = "request failed"
        elif "json" not in r.get("content_type", "").lower():
            d["classification"] = classify_non_json(r["text"])
            d["parse_result"] = "not JSON"
        else:
            df, msg = parse_te_payload(r["text"])
            d["parse_result"] = msg
            d["records"] = len(df)
            d["columns"] = ", ".join(map(str, df.columns)) if not df.empty else ""
            if not df.empty:
                tmp = df.head(30).copy(); tmp["route_label"] = label; records.append(tmp)
                cand = extract_te_candidates(df, label, display_url)
                if not cand.empty:
                    candidates_all.append(cand)
        diagnostics.append(d)
        samples.append({"route_label": label, "url": display_url, "sample": r["text"][:1500].replace(cred, "***")})

    rec_df = pd.concat(records, ignore_index=True) if records else pd.DataFrame()
    cand_df = pd.concat(candidates_all, ignore_index=True) if candidates_all else pd.DataFrame()
    result_row = None
    if not cand_df.empty:
        # Prefer exact SORA matches. If none, do not auto-promote generic interest rate.
        exact = cand_df[cand_df.get("sora_match", False).eq(True)] if "sora_match" in cand_df.columns else pd.DataFrame()
        chosen_pool = exact if not exact.empty else pd.DataFrame()
        if not chosen_pool.empty:
            chosen_pool = chosen_pool.dropna(subset=["date"]).sort_values("date") if "date" in chosen_pool.columns else chosen_pool
            latest = chosen_pool.iloc[-1]
            result_row = {"market": "SG", "indicator": "Rates", "date": latest["date"].strftime("%Y-%m-%d") if pd.notna(latest.get("date")) else "Latest", "value": float(latest["value"]), "unit": "%", "source": "Trading Economics SORA candidate", "source_type": "Fallback / API Lab", "notes": f"Only acceptable if category is explicit SORA/Compounded SORA. category={latest.get('category_text','')}"}
    return result_row, pd.DataFrame(diagnostics), pd.DataFrame(samples), rec_df, cand_df


# ---------------- JP BOJ confirmation ----------------
def parse_boj_csv(text, target_code="STRDCLUCON"):
    recs = []
    for i, row in enumerate(csv.reader(io.StringIO(text))):
        if not row or row[0] != target_code:
            continue
        date_idx = None
        for j, cell in enumerate(row):
            if re.fullmatch(r"\d{8}", str(cell).strip()):
                date_idx = j; break
        if date_idx is None:
            continue
        date = parse_date_any(row[date_idx])
        value = None
        for k in range(date_idx + 1, len(row)):
            n = clean_number(row[k])
            if n is not None:
                value = n; break
        if pd.notna(date) and value is not None:
            recs.append({"line_no": i, "code": target_code, "date": date, "value": value, "raw": ",".join(row[:min(len(row), date_idx + 5)])})
    return pd.DataFrame(recs)


def run_boj_confirm():
    start = (pd.Timestamp.today() - pd.DateOffset(months=18)).strftime("%Y%m")
    url = "https://www.stat-search.boj.or.jp/api/v1/getDataCode?" + urllib.parse.urlencode({"format": "csv", "lang": "en", "db": "FM01", "startDate": start, "code": "STRDCLUCON"})
    r = request_text(url, "BOJ FM01 STRDCLUCON csv", accept="text/csv,*/*")
    diag = {k: v for k, v in r.items() if k != "text"}
    parsed = parse_boj_csv(r["text"], "STRDCLUCON") if r["ok"] else pd.DataFrame()
    row = None
    if not parsed.empty:
        latest = parsed.sort_values("date").iloc[-1]
        row = {"market": "JP", "indicator": "Rates", "date": latest["date"].strftime("%Y-%m-%d"), "value": float(latest["value"]), "unit": "%", "source": "BOJ FM01 STRDCLUCON", "source_type": "Official / API Lab", "notes": "BOJ FM01 Uncollateralized Overnight Call Rate Average Daily."}
    return row, pd.DataFrame([diag]), pd.DataFrame([{"url": url, "sample": r["text"][:3000]}]), parsed


st.title("Global20Engine Rate Diagnostics Lab")
st.caption("SG MAS route test + Trading Economics fallback test + JP BOJ confirmation.")

with st.sidebar:
    st.header("Trading Economics credential")
    st.caption("Enter as key:secret. Not saved by this app.")
    te_credential = st.text_input("TE key:secret", value="", type="password")

c1, c2, c3 = st.columns(3)
with c1:
    run_sg = st.button("Run SG MAS route diagnostic", use_container_width=True)
with c2:
    run_te = st.button("Run SG Trading Economics test", use_container_width=True)
with c3:
    run_jp = st.button("Confirm JP BOJ parser", use_container_width=True)

if run_sg:
    st.header("SG MAS route diagnostic")
    row, diag, samples, records_preview, parsed = run_mas_deep()
    if row:
        st.success("SG SORA parsed successfully from one of the MAS routes.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.error("SG SORA still not parsed from MAS routes.")
    st.subheader("Endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("MAS records preview, if any JSON route worked")
    st.dataframe(records_preview, use_container_width=True)
    st.subheader("Parsed SORA candidate rows")
    st.dataframe(parsed.tail(100), use_container_width=True)
    with st.expander("Raw MAS response samples", expanded=True):
        st.dataframe(samples, use_container_width=True)

if run_te:
    st.header("SG Trading Economics fallback diagnostic")
    row, diag, samples, records, candidates = run_te_deep(te_credential)
    if row:
        st.success("Trading Economics returned an explicit SORA/Compounded SORA candidate.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.warning("No explicit SORA/Compounded SORA candidate was promoted. Inspect returned categories before using as fallback.")
    st.subheader("TE endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("TE records preview")
    st.dataframe(records, use_container_width=True)
    st.subheader("TE numeric candidates")
    st.dataframe(candidates, use_container_width=True)
    with st.expander("Raw TE response samples", expanded=False):
        st.dataframe(samples, use_container_width=True)

if run_jp:
    st.header("JP BOJ parser confirmation")
    row, diag, samples, parsed = run_boj_confirm()
    if row:
        st.success("JP BOJ parser confirmed.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.error("JP BOJ parser did not return a row in this run.")
    st.subheader("Endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("Parsed observations")
    st.dataframe(parsed.tail(100), use_container_width=True)
    with st.expander("Raw BOJ sample", expanded=False):
        st.dataframe(samples, use_container_width=True)

st.markdown("""
### Source-governance interpretation
- MAS remains the official primary SG source.
- Trading Economics is tested only as fallback/sanity-check.
- Promote Trading Economics only if the returned category is explicitly SORA / Singapore Overnight Rate Average / Compounded SORA.
- If Trading Economics only returns generic `Interest Rate`, treat it as proxy, not as the SG SORA card source.
""")
