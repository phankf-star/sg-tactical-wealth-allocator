
# macro_rate_diagnostics_lab.py
# Global20Engine Rate Diagnostics Lab v2 - SG MAS + JP BOJ deep diagnostics

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

USER_AGENT = "Mozilla/5.0 Global20Engine-RateDiagnosticsLab/2.0"
TIMEOUT = 30

MAS_RESOURCE_ID = "9a0bf149-308c-4bd2-832d-76c8e6cb47ed"
MAS_URLS = [
    "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "5000"}),
    "https://secure.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "5000"}),
    "https://secure.mas.gov.sg/api/APIDescPage.aspx?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID}),
]

BOJ_BASE = "https://www.stat-search.boj.or.jp/api/v1"
BOJ_FM01_CODES = [
    "STRDCLUCON",   # confirmed by metadata: Call Rate, Uncollateralized Overnight, Average (Daily)
    "STRDCLUCONH",  # highest daily, for diagnostics only
    "STRDCLUCONL",  # lowest daily, for diagnostics only
]


def request_text(url, label, accept="*/*"):
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "identity"})
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


def flatten_json(obj, path="$"):
    out = []
    if isinstance(obj, dict):
        out.append({"path": path, "type": "dict", "keys": list(obj.keys()), "sample": str(obj)[:800]})
        for k, v in obj.items():
            out.extend(flatten_json(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        out.append({"path": path, "type": "list", "keys": [], "sample": str(obj[:3])[:800]})
        for i, v in enumerate(obj[:5000]):
            out.extend(flatten_json(v, f"{path}[{i}]"))
    else:
        out.append({"path": path, "type": type(obj).__name__, "keys": [], "sample": str(obj)[:300]})
    return out


# ---------------- SG MAS ----------------
def classify_mas_html(text):
    t = (text or "").lower()
    if "maintenance" in t or "service is currently unavailable" in t:
        return "HTML maintenance/unavailable page"
    if "doctype html" in t or "<html" in t:
        return "HTML page, not JSON"
    return "non-JSON response"


def run_mas_deep():
    rows = []
    samples = []
    parsed = []
    for url in MAS_URLS:
        r = request_text(url, "MAS endpoint", accept="application/json,text/html,*/*")
        d = {k: v for k, v in r.items() if k != "text"}
        d["classification"] = classify_mas_html(r["text"]) if r["ok"] and "json" not in r.get("content_type", "").lower() else ""
        rows.append(d)
        samples.append({"url": url, "sample": r["text"][:3000]})
        if r["ok"] and "json" in r.get("content_type", "").lower():
            try:
                payload = json.loads(r["text"])
                recs = payload.get("result", {}).get("records", [])
                df = pd.DataFrame(recs)
                if not df.empty:
                    date_cols = [c for c in df.columns if str(c).lower() in {"end_of_day", "date", "timestamp"} or "date" in str(c).lower()]
                    for vc in ["sora", "SORA", "sora_rate", "SORA_RATE", "comp_sora_1m", "comp_sora_3m", "comp_sora_6m"]:
                        if vc in df.columns:
                            dc = date_cols[0] if date_cols else None
                            tmp = df[[dc, vc]].copy() if dc else df[[vc]].copy()
                            tmp["date"] = tmp[dc].apply(parse_date_any) if dc else pd.NaT
                            tmp["value"] = tmp[vc].map(clean_number)
                            tmp["field"] = vc
                            tmp["source_url"] = url
                            parsed.append(tmp.dropna(subset=["value"]))
            except Exception as e:
                samples.append({"url": url, "sample": f"JSON parse error: {e!r}"})
    parsed_df = pd.concat(parsed, ignore_index=True) if parsed else pd.DataFrame()
    return pd.DataFrame(rows), pd.DataFrame(samples), parsed_df


# ---------------- JP BOJ ----------------
def json_schema(text):
    try:
        payload = json.loads(text)
    except Exception as e:
        return pd.DataFrame([{"error": repr(e)}]), None
    return pd.DataFrame(flatten_json(payload)[:1000]), payload


def extract_boj_candidates_from_json(payload):
    candidates = []
    def walk(x, path="$"):
        if isinstance(x, dict):
            scalars = {k: v for k, v in x.items() if not isinstance(v, (dict, list))}
            if len(scalars) >= 2:
                row = dict(scalars); row["__path"] = path; candidates.append(row)
            for k, v in x.items():
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x[:10000]):
                walk(v, f"{path}[{i}]")
    walk(payload)
    return pd.DataFrame(candidates)


def parse_boj_csv(text, target_code="STRDCLUCON"):
    """BOJ CSV observed layout:
    STATUS,200,...
    PARAMETER,STARTDATE,YYYYMM
    SERIES_CODE,...,TIME_PERIOD,VALUE...
    STRDCLUCON,"Call Rate...",...,20241201,<value>...
    The date is the first 8-digit field after metadata columns; value is the first numeric field after that date.
    """
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
        value_col_idx = None
        for k in range(date_idx + 1, len(row)):
            n = clean_number(row[k])
            if n is not None:
                value = n
                value_col_idx = k
                break
        if pd.notna(date) and value is not None:
            recs.append({"line_no": i, "code": target_code, "date": date, "value": value, "value_col_idx": value_col_idx, "raw": ",".join(row[:min(len(row), date_idx+5)])})
    return pd.DataFrame(recs)


def run_boj_deep():
    diag = []
    samples = []
    schemas = []
    candidates = []
    parsed_all = []

    meta_url = f"{BOJ_BASE}/getMetadata?" + urllib.parse.urlencode({"format": "json", "lang": "en", "db": "FM01"})
    rmeta = request_text(meta_url, "BOJ FM01 metadata", accept="application/json,*/*")
    diag.append({k: v for k, v in rmeta.items() if k != "text"})
    samples.append({"label": "metadata", "code": "FM01", "format": "json", "sample": rmeta["text"][:3000]})
    if rmeta["ok"]:
        sdf, payload = json_schema(rmeta["text"])
        sdf["source"] = "metadata"
        schemas.append(sdf)
        if payload is not None:
            cdf = extract_boj_candidates_from_json(payload)
            cdf["source"] = "metadata"
            candidates.append(cdf)

    start = (pd.Timestamp.today() - pd.DateOffset(months=18)).strftime("%Y%m")
    for code in BOJ_FM01_CODES:
        for fmt in ["json", "csv"]:
            url = f"{BOJ_BASE}/getDataCode?" + urllib.parse.urlencode({"format": fmt, "lang": "en", "db": "FM01", "startDate": start, "code": code})
            r = request_text(url, f"BOJ FM01 {code} {fmt}", accept="application/json,text/csv,*/*")
            d = {k: v for k, v in r.items() if k != "text"}; d["code"] = code; d["format"] = fmt
            if r["ok"] and fmt == "csv":
                parsed = parse_boj_csv(r["text"], target_code=code)
                d["parsed_rows"] = len(parsed)
                if not parsed.empty:
                    parsed_all.append(parsed)
            elif r["ok"] and fmt == "json":
                sdf, payload = json_schema(r["text"])
                sdf["source"] = f"data {code} json"
                schemas.append(sdf)
                if payload is not None:
                    cdf = extract_boj_candidates_from_json(payload)
                    cdf["source"] = f"data {code} json"
                    candidates.append(cdf)
            diag.append(d)
            samples.append({"label": "data", "code": code, "format": fmt, "sample": r["text"][:3000]})

    parsed_df = pd.concat(parsed_all, ignore_index=True) if parsed_all else pd.DataFrame()
    result_row = None
    if not parsed_df.empty:
        parsed_df = parsed_df.sort_values("date")
        latest = parsed_df[parsed_df["code"].eq("STRDCLUCON")].sort_values("date").iloc[-1]
        result_row = {"market":"JP","indicator":"Rates","date":latest["date"].strftime("%Y-%m-%d"),"value":float(latest["value"]),"unit":"%","source":"BOJ FM01 Uncollateralized Overnight Call Rate Average Daily (STRDCLUCON)","source_type":"Official / API Lab","notes":"Parsed from BOJ getDataCode CSV; code=STRDCLUCON; first numeric value after daily date."}

    return result_row, pd.DataFrame(diag), pd.DataFrame(samples), pd.concat(schemas, ignore_index=True) if schemas else pd.DataFrame(), pd.concat(candidates, ignore_index=True) if candidates else pd.DataFrame(), parsed_df


st.title("Global20Engine Rate Diagnostics Lab")
st.caption("Deep diagnostics for SG MAS SORA and JP BOJ FM01 before production adapter changes.")

c1, c2 = st.columns(2)
with c1:
    run_sg = st.button("Run SG MAS deep diagnostic", use_container_width=True)
with c2:
    run_jp = st.button("Run JP BOJ deep diagnostic", use_container_width=True)

if run_sg:
    st.header("SG MAS deep diagnostic")
    diag, samples, parsed = run_mas_deep()
    st.subheader("Endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("Parsed SORA rows")
    st.dataframe(parsed.tail(100), use_container_width=True)
    with st.expander("Raw MAS response samples", expanded=True):
        st.dataframe(samples, use_container_width=True)

if run_jp:
    st.header("JP BOJ deep diagnostic")
    result_row, diag, samples, schemas, candidates, parsed = run_boj_deep()
    if result_row:
        st.success("JP BOJ FM01 parsed successfully.")
        st.dataframe(pd.DataFrame([result_row]), use_container_width=True)
    else:
        st.error("JP BOJ FM01 still not parsed.")
    st.subheader("Endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("Parsed BOJ CSV observations")
    st.dataframe(parsed.tail(100), use_container_width=True)
    st.subheader("JSON schema preview")
    st.dataframe(schemas.head(1000), use_container_width=True)
    st.subheader("Candidate scalar rows from BOJ JSON")
    st.dataframe(candidates.head(1000), use_container_width=True)
    with st.expander("Raw BOJ response samples", expanded=False):
        st.dataframe(samples, use_container_width=True)

st.markdown("""
### Read this result
- SG: if MAS returns `text/html`, the MAS endpoint is not serving JSON to the app environment.
- JP: code `STRDCLUCON` is the BOJ metadata-confirmed average daily uncollateralised overnight call rate.
""")
