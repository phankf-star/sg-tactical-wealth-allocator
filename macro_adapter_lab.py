
# macro_rate_diagnostics_lab.py
# Global20Engine Rate Diagnostics Lab v1 - SG MAS + JP BOJ deep diagnostics

import io
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Global20Engine Rate Diagnostics Lab", layout="wide")

USER_AGENT = "Mozilla/5.0 Global20Engine-RateDiagnosticsLab/1.0"
TIMEOUT = 30

MAS_RESOURCE_ID = "9a0bf149-308c-4bd2-832d-76c8e6cb47ed"
MAS_URLS = [
    "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "5000"}),
    "https://secure.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "5000"}),
    "https://secure.mas.gov.sg/api/APIDescPage.aspx?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID}),
]

BOJ_BASE = "https://www.stat-search.boj.or.jp/api/v1"
BOJ_FM01_CODES = [
    "STRDCLUCON", "STRDCLUCON@D", "FM01.STRDCLUCON", "FM01.STRDCLUCON@D",
    "STRDCLACD", "STRDCLACD@D", "STRDCLUCONA", "STRDCLUCONA@D",
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
    s = str(x).strip()
    if not s or s.upper() in {"N.A.", "N/A", "NA", "NULL", "NONE", "-", "--", "."}:
        return None
    s = re.sub(r"\[[^\]]*\]", "", s).replace("+", "").replace("%", "").replace(",", "").replace("−", "-").replace("–", "-")
    try:
        return float(s)
    except Exception:
        return None


def parse_date_any(x):
    s = str(x).strip()
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


def run_mas_deep():
    rows = []
    samples = []
    parsed = []
    for url in MAS_URLS:
        r = request_text(url, "MAS endpoint", accept="application/json,text/html,*/*")
        rows.append({k: v for k, v in r.items() if k != "text"})
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
            # capture all dicts with scalar fields for inspection
            scalars = {k: v for k, v in x.items() if not isinstance(v, (dict, list))}
            if len(scalars) >= 2:
                row = dict(scalars); row["__path"] = path; candidates.append(row)
            for k, v in x.items(): walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x[:10000]): walk(v, f"{path}[{i}]")
    walk(payload)
    return pd.DataFrame(candidates)


def run_boj_deep():
    diag = []
    samples = []
    schemas = []
    candidates = []
    parsed = []
    # metadata first
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
    # data code candidates
    start = (pd.Timestamp.today() - pd.DateOffset(months=18)).strftime("%Y%m")
    for code in BOJ_FM01_CODES:
        for fmt in ["json", "csv"]:
            url = f"{BOJ_BASE}/getDataCode?" + urllib.parse.urlencode({"format": fmt, "lang": "en", "db": "FM01", "startDate": start, "code": code})
            r = request_text(url, f"BOJ FM01 {code} {fmt}", accept="application/json,text/csv,*/*")
            d = {k: v for k, v in r.items() if k != "text"}; d["code"] = code; d["format"] = fmt
            diag.append(d)
            samples.append({"label": "data", "code": code, "format": fmt, "sample": r["text"][:3000]})
            if r["ok"] and fmt == "json":
                sdf, payload = json_schema(r["text"])
                sdf["source"] = f"data {code} json"
                schemas.append(sdf)
                if payload is not None:
                    cdf = extract_boj_candidates_from_json(payload)
                    cdf["source"] = f"data {code} json"
                    candidates.append(cdf)
            elif r["ok"] and fmt == "csv":
                # BOJ CSV may include metadata lines before observation table; show lines and attempt loose parsing
                lines = r["text"].splitlines()
                for i, line in enumerate(lines[:50]):
                    parts = [p.strip() for p in line.split(",")]
                    nums = [clean_number(p) for p in parts]
                    dates = [parse_date_any(p) for p in parts]
                    if any(pd.notna(dte) for dte in dates) and any(n is not None for n in nums):
                        parsed.append({"code": code, "line_no": i, "line": line[:500]})
    return (pd.DataFrame(diag), pd.DataFrame(samples), pd.concat(schemas, ignore_index=True) if schemas else pd.DataFrame(), pd.concat(candidates, ignore_index=True) if candidates else pd.DataFrame(), pd.DataFrame(parsed))


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
    diag, samples, schemas, candidates, parsed_lines = run_boj_deep()
    st.subheader("Endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("JSON schema preview")
    st.dataframe(schemas.head(1000), use_container_width=True)
    st.subheader("Candidate scalar rows from BOJ JSON")
    st.dataframe(candidates.head(1000), use_container_width=True)
    st.subheader("Loose parsed CSV lines")
    st.dataframe(parsed_lines, use_container_width=True)
    with st.expander("Raw BOJ response samples", expanded=True):
        st.dataframe(samples, use_container_width=True)

st.markdown("""
### How to use this output
- For SG, if endpoint diagnostics show `text/html`, inspect raw MAS response. A live adapter cannot parse SORA until a JSON endpoint returns records.
- For JP, inspect metadata/candidate rows to identify the exact BOJ FM01 series code and response field names.
""")
