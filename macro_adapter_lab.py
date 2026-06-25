
# macro_rate_diagnostics_lab.py
# Global20Engine Rate Diagnostics Lab v5 - SG MAS HTML scrape probe + MAS/TE/JP tests

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

USER_AGENT = "Mozilla/5.0 Global20Engine-RateDiagnosticsLab/5.0"
TIMEOUT = 30

MAS_RESOURCE_ID = "9a0bf149-308c-4bd2-832d-76c8e6cb47ed"
MAS_DIR_URL = "https://eservices.mas.gov.sg/statistics/dir/domesticinterestrates.aspx"

MAS_URLS = [
    {"label": "MAS generic eservices route", "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "5000"})},
    {"label": "MAS GitHub open-source exact route - comp_sora_1m", "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "100", "fields": "end_of_day,comp_sora_1m", "sort": "end_of_day desc"})},
    {"label": "MAS GitHub open-source broad SORA fields", "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "100", "fields": "end_of_day,sora,sora_index,comp_sora_1m,comp_sora_3m,comp_sora_6m", "sort": "end_of_day desc"})},
]

TE_INDICATOR_CANDIDATES = ["sora", "singapore overnight rate average", "compounded sora", "interest rate", "interbank rate"]


def request_text(url, label, accept="*/*", data=None, method=None, headers_extra=None):
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "identity"}
        if headers_extra:
            headers.update(headers_extra)
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
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
    if "domestic interest rates" in t and "sora" in t:
        return "MAS Domestic Interest Rates form page"
    if "doctype html" in t or "<html" in t:
        return "HTML page, not JSON"
    if not text:
        return "empty response"
    return "non-JSON response"


# ---------------- MAS JSON route diagnostic ----------------
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
    return pd.DataFrame(diagnostics), pd.DataFrame(samples), records_preview, parsed


# ---------------- MAS HTML scrape probe ----------------
def extract_input_fields(html):
    # Lightweight regex extractor. Purpose: diagnostics only, not a full HTML parser.
    inputs = []
    for m in re.finditer(r"<input\b[^>]*>", html, flags=re.I | re.S):
        tag = m.group(0)
        attrs = {}
        for a in re.finditer(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(['\"])(.*?)\2", tag, flags=re.S):
            attrs[a.group(1)] = a.group(3)
        inputs.append(attrs)
    return pd.DataFrame(inputs)


def extract_selects(html):
    selects = []
    for m in re.finditer(r"<select\b[^>]*>(.*?)</select>", html, flags=re.I | re.S):
        tag_start = re.search(r"<select\b[^>]*>", m.group(0), flags=re.I | re.S).group(0)
        name = ""
        idv = ""
        nm = re.search(r"name\s*=\s*(['\"])(.*?)\1", tag_start, flags=re.I | re.S)
        im = re.search(r"id\s*=\s*(['\"])(.*?)\1", tag_start, flags=re.I | re.S)
        if nm: name = nm.group(2)
        if im: idv = im.group(2)
        opts = []
        for om in re.finditer(r"<option\b[^>]*value\s*=\s*(['\"])(.*?)\1[^>]*>(.*?)</option>", m.group(1), flags=re.I | re.S):
            opts.append({"value": om.group(2), "text": re.sub(r"<[^>]+>", "", om.group(3)).strip()})
        selects.append({"name": name, "id": idv, "options_count": len(opts), "options_sample": str(opts[:10])})
    return pd.DataFrame(selects)


def run_mas_html_probe():
    r = request_text(MAS_DIR_URL, "MAS Domestic Interest Rates HTML page", accept="text/html,*/*")
    diag = {k: v for k, v in r.items() if k != "text"}
    diag["classification"] = classify_non_json(r["text"])
    html = r["text"] if r["ok"] else ""

    table_summaries = []
    parsed_tables = []
    try:
        tables = pd.read_html(io.StringIO(html)) if html else []
        for i, t in enumerate(tables):
            table_summaries.append({"table_index": i, "rows": len(t), "cols": len(t.columns), "columns": ", ".join(map(str, t.columns))[:500], "contains_sora": t.astype(str).apply(lambda col: col.str.contains("SORA|sora|Compounded", regex=True, na=False)).any().any()})
            tt = t.copy(); tt["__table_index"] = i; parsed_tables.append(tt.head(50))
    except Exception as e:
        table_summaries.append({"table_index": "error", "rows": 0, "cols": 0, "columns": "", "contains_sora": False, "error": repr(e)})

    inputs = extract_input_fields(html)
    selects = extract_selects(html)
    # Regex clues: hidden AJAX endpoints, __doPostBack, download/display buttons, SORA checkboxes.
    clue_patterns = [
        r"__doPostBack\([^)]*\)",
        r"WebResource\.axd[^'\"]+",
        r"ScriptResource\.axd[^'\"]+",
        r"[A-Za-z0-9_./-]+\.ashx[^'\"]*",
        r"[A-Za-z0-9_./-]+\.aspx[^'\"]*",
        r"SORA",
        r"comp_sora_1m|comp_sora_3m|comp_sora_6m|sora_index",
    ]
    clues = []
    for pat in clue_patterns:
        matches = re.findall(pat, html, flags=re.I)
        clues.append({"pattern": pat, "matches_count": len(matches), "sample": str(matches[:20])[:1000]})

    result_row = None
    candidate_rows = []
    # If read_html sees actual data tables with dates and numeric SORA, promote only if robust.
    for t in parsed_tables:
        text_cols = [c for c in t.columns if t[c].astype(str).str.contains("SORA|sora|Compounded", regex=True, na=False).any()]
        if text_cols:
            candidate_rows.append(t)
    candidates = pd.concat(candidate_rows, ignore_index=True) if candidate_rows else pd.DataFrame()

    return pd.DataFrame([diag]), pd.DataFrame(table_summaries), pd.concat(parsed_tables, ignore_index=True) if parsed_tables else pd.DataFrame(), inputs, selects, pd.DataFrame(clues), pd.DataFrame([{"url": MAS_DIR_URL, "sample": html[:5000]}]), candidates, result_row


# ---------------- Trading Economics fallback diagnostics ----------------
def parse_te_payload(text):
    try:
        payload = json.loads(text)
    except Exception as e:
        return pd.DataFrame(), f"JSON parse error: {e!r}"
    if isinstance(payload, dict):
        return pd.DataFrame([payload]), "JSON dict response"
    if isinstance(payload, list):
        return pd.DataFrame(payload), "JSON list response"
    return pd.DataFrame(), f"unexpected JSON type {type(payload).__name__}"


def extract_te_candidates(df, route_label, url):
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
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
    routes = []
    for indicator in TE_INDICATOR_CANDIDATES:
        enc = urllib.parse.quote(indicator, safe="")
        routes.append({"label": f"TE historical Singapore / {indicator}", "url": f"https://api.tradingeconomics.com/historical/country/singapore/indicator/{enc}?" + urllib.parse.urlencode({"c": cred, "f": "json"})})
        routes.append({"label": f"TE snapshot Singapore / {indicator}", "url": f"https://api.tradingeconomics.com/country/singapore/indicator/{enc}?" + urllib.parse.urlencode({"c": cred, "f": "json"})})
    for route in routes:
        label, url = route["label"], route["url"]
        display_url = url.replace(cred, "***")
        r = request_text(url, label, accept="application/json,text/html,*/*")
        d = {k: v for k, v in r.items() if k not in {"text", "url"}}
        d["url"] = display_url; d["route_label"] = label
        if not r["ok"]:
            d["parse_result"] = "request failed"
        elif "json" not in r.get("content_type", "").lower():
            d["classification"] = classify_non_json(r["text"]); d["parse_result"] = "not JSON"
        else:
            df, msg = parse_te_payload(r["text"])
            d["parse_result"] = msg; d["records"] = len(df); d["columns"] = ", ".join(map(str, df.columns)) if not df.empty else ""
            if not df.empty:
                tmp = df.head(30).copy(); tmp["route_label"] = label; records.append(tmp)
                cand = extract_te_candidates(df, label, display_url)
                if not cand.empty: candidates_all.append(cand)
        diagnostics.append(d); samples.append({"route_label": label, "url": display_url, "sample": r["text"][:1500].replace(cred, "***")})
    rec_df = pd.concat(records, ignore_index=True) if records else pd.DataFrame()
    cand_df = pd.concat(candidates_all, ignore_index=True) if candidates_all else pd.DataFrame()
    result_row = None
    if not cand_df.empty and "sora_match" in cand_df.columns:
        exact = cand_df[cand_df["sora_match"].eq(True)]
        if not exact.empty:
            exact = exact.dropna(subset=["date"]).sort_values("date") if "date" in exact.columns else exact
            latest = exact.iloc[-1]
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
        if date_idx is None: continue
        date = parse_date_any(row[date_idx])
        value = None
        for k in range(date_idx + 1, len(row)):
            n = clean_number(row[k])
            if n is not None: value = n; break
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
st.caption("SG MAS route test + SG MAS HTML scrape probe + Trading Economics fallback test + JP BOJ confirmation.")

with st.sidebar:
    st.header("Trading Economics credential")
    st.caption("Enter as key:secret. Not saved by this app.")
    te_credential = st.text_input("TE key:secret", value="", type="password")

c1, c2, c3, c4 = st.columns(4)
with c1:
    run_sg = st.button("Run SG MAS route diagnostic", use_container_width=True)
with c2:
    run_html = st.button("Run SG MAS HTML scrape probe", use_container_width=True)
with c3:
    run_te = st.button("Run SG Trading Economics test", use_container_width=True)
with c4:
    run_jp = st.button("Confirm JP BOJ parser", use_container_width=True)

if run_sg:
    st.header("SG MAS route diagnostic")
    diag, samples, records_preview, parsed = run_mas_deep()
    st.subheader("Endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("MAS records preview, if any JSON route worked")
    st.dataframe(records_preview, use_container_width=True)
    st.subheader("Parsed SORA candidate rows")
    st.dataframe(parsed.tail(100), use_container_width=True)
    with st.expander("Raw MAS response samples", expanded=True):
        st.dataframe(samples, use_container_width=True)

if run_html:
    st.header("SG MAS HTML scrape probe")
    diag, table_summaries, parsed_tables, inputs, selects, clues, sample, candidates, result_row = run_mas_html_probe()
    st.subheader("HTML endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("pandas.read_html table summaries")
    st.dataframe(table_summaries, use_container_width=True)
    st.subheader("Parsed HTML table previews")
    st.dataframe(parsed_tables, use_container_width=True)
    st.subheader("Input fields discovered")
    st.dataframe(inputs, use_container_width=True)
    st.subheader("Select fields discovered")
    st.dataframe(selects, use_container_width=True)
    st.subheader("HTML clue scan")
    st.dataframe(clues, use_container_width=True)
    st.subheader("Candidate SORA tables/text rows")
    st.dataframe(candidates, use_container_width=True)
    with st.expander("Raw MAS HTML first 5,000 characters", expanded=False):
        st.dataframe(sample, use_container_width=True)

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
- MAS HTML scrape is only a controlled official-page fallback probe, not production until a clean date/value row is proven.
- Trading Economics is tested only as fallback/sanity-check.
- Promote Trading Economics only if the returned category is explicitly SORA / Singapore Overnight Rate Average / Compounded SORA.
""")
