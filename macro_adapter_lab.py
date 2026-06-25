
# macro_rate_diagnostics_lab.py
# Global20Engine Rate Diagnostics Lab v3 - SG GitHub open-source route test + JP BOJ parser

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

USER_AGENT = "Mozilla/5.0 Global20Engine-RateDiagnosticsLab/3.0"
TIMEOUT = 30

MAS_RESOURCE_ID = "9a0bf149-308c-4bd2-832d-76c8e6cb47ed"

# MAS routes to test.
# Route 0 = current generic route.
# Route 1 = exact GitHub open-source route pattern from jameskohjunwei/sora-interest-rate.
# Route 2 = broad GitHub/open-source route with all common SORA fields.
# Route 3/4 = legacy secure MAS routes for confirmation.
MAS_URLS = [
    {
        "label": "MAS generic eservices route",
        "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "5000"}),
    },
    {
        "label": "MAS GitHub open-source exact route - comp_sora_1m",
        "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "100", "fields": "end_of_day,comp_sora_1m", "sort": "end_of_day desc"}),
    },
    {
        "label": "MAS GitHub open-source broad SORA fields",
        "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "100", "fields": "end_of_day,sora,sora_index,comp_sora_1m,comp_sora_3m,comp_sora_6m", "sort": "end_of_day desc"}),
    },
    {
        "label": "MAS secure datastore route",
        "url": "https://secure.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "5000"}),
    },
    {
        "label": "MAS secure API description page",
        "url": "https://secure.mas.gov.sg/api/APIDescPage.aspx?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID}),
    },
]

BOJ_BASE = "https://www.stat-search.boj.or.jp/api/v1"
BOJ_FM01_CODES = ["STRDCLUCON", "STRDCLUCONH", "STRDCLUCONL"]


def request_text(url, label, accept="*/*"):
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "identity"},
        )
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
        return {
            "label": label,
            "ok": False,
            "status": "",
            "content_type": "",
            "bytes": 0,
            "started_utc": started,
            "url": url,
            "text": "",
            "error": repr(e),
        }


def clean_number(x):
    if x is None:
        return None
    s = str(x).strip().strip('"').strip("'")
    if not s or s.upper() in {"N.A.", "N/A", "NA", "NULL", "NONE", "-", "--", "."}:
        return None
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = s.replace("+", "").replace("%", "").replace(",", "").replace("−", "-").replace("–", "-")
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
    diagnostics = []
    samples = []
    parsed_all = []
    records_previews = []

    for route in MAS_URLS:
        label = route["label"]
        url = route["url"]
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
                    rp = recs_df.head(30).copy()
                    rp["route_label"] = label
                    records_previews.append(rp)
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
        result_row = {
            "market": "SG",
            "indicator": "Rates",
            "date": latest["date"].strftime("%Y-%m-%d"),
            "value": float(latest["value"]),
            "unit": "%",
            "source": f"MAS Domestic Interest Rates {latest['field']}",
            "source_type": "Official / API Lab",
            "notes": f"Parsed from route={latest['route']}; resource_id={MAS_RESOURCE_ID}; field={latest['field']}.",
        }
    return result_row, pd.DataFrame(diagnostics), pd.DataFrame(samples), records_preview, parsed


# BOJ utilities retained for JP verification

def parse_boj_csv(text, target_code="STRDCLUCON"):
    recs = []
    for i, row in enumerate(csv.reader(io.StringIO(text))):
        if not row or row[0] != target_code:
            continue
        date_idx = None
        for j, cell in enumerate(row):
            if re.fullmatch(r"\d{8}", str(cell).strip()):
                date_idx = j
                break
        if date_idx is None:
            continue
        date = parse_date_any(row[date_idx])
        value = None
        for k in range(date_idx + 1, len(row)):
            n = clean_number(row[k])
            if n is not None:
                value = n
                break
        if pd.notna(date) and value is not None:
            recs.append({"line_no": i, "code": target_code, "date": date, "value": value, "raw": ",".join(row[:min(len(row), date_idx + 5)])})
    return pd.DataFrame(recs)


def run_boj_confirm():
    start = (pd.Timestamp.today() - pd.DateOffset(months=18)).strftime("%Y%m")
    url = f"https://www.stat-search.boj.or.jp/api/v1/getDataCode?" + urllib.parse.urlencode({"format": "csv", "lang": "en", "db": "FM01", "startDate": start, "code": "STRDCLUCON"})
    r = request_text(url, "BOJ FM01 STRDCLUCON csv", accept="text/csv,*/*")
    diag = {k: v for k, v in r.items() if k != "text"}
    parsed = parse_boj_csv(r["text"], "STRDCLUCON") if r["ok"] else pd.DataFrame()
    row = None
    if not parsed.empty:
        latest = parsed.sort_values("date").iloc[-1]
        row = {"market": "JP", "indicator": "Rates", "date": latest["date"].strftime("%Y-%m-%d"), "value": float(latest["value"]), "unit": "%", "source": "BOJ FM01 STRDCLUCON", "source_type": "Official / API Lab", "notes": "BOJ FM01 Uncollateralized Overnight Call Rate Average Daily."}
    return row, pd.DataFrame([diag]), pd.DataFrame([{"url": url, "sample": r["text"][:3000]}]), parsed


st.title("Global20Engine Rate Diagnostics Lab")
st.caption("SG MAS GitHub open-source route test + JP BOJ confirmation.")

c1, c2 = st.columns(2)
with c1:
    run_sg = st.button("Run SG MAS GitHub-route diagnostic", use_container_width=True)
with c2:
    run_jp = st.button("Confirm JP BOJ parser", use_container_width=True)

if run_sg:
    st.header("SG MAS GitHub-route diagnostic")
    row, diag, samples, records_preview, parsed = run_mas_deep()
    if row:
        st.success("SG SORA parsed successfully from one of the MAS routes.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.error("SG SORA still not parsed. If all MAS routes return HTML/non-JSON, this confirms endpoint issue.")
    st.subheader("Endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("MAS records preview, if any JSON route worked")
    st.dataframe(records_preview, use_container_width=True)
    st.subheader("Parsed SORA candidate rows")
    st.dataframe(parsed.tail(100), use_container_width=True)
    with st.expander("Raw MAS response samples", expanded=True):
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
- GitHub open-source examples are used here only to test endpoint/parameter patterns.
- Official SG data source remains MAS Domestic Interest Rates/SORA.
- If the exact GitHub open-source MAS route also returns HTML, SG is confirmed as a MAS endpoint availability/route issue in this environment, not an app parser issue.
""")
