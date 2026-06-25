
# macro_adapter_lab.py
# Global20Engine Macro Adapter Lab v2
# Purpose: test macro/rate data ideas in isolation before touching the full base app.

import json
import re
import urllib.request
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Global20Engine Macro Adapter Lab", layout="wide", initial_sidebar_state="expanded")

USER_AGENT = "Mozilla/5.0 Global20Engine-MacroAdapterLab/2.0"
TIMEOUT = 30
APAC_RATE_KEYS = {("SG", "RATES"), ("MY", "RATES"), ("HK", "RATES"), ("JP", "RATES")}
STANDARD_COLS = ["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"]


def request_text(url, label="request", headers=None):
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        h.update(headers)
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            status = getattr(resp, "status", "")
        return {
            "label": label, "ok": True, "status": status, "content_type": ctype,
            "bytes": len(raw), "started_utc": started, "url": url,
            "text": raw.decode("utf-8", errors="replace"), "error": ""
        }
    except Exception as e:
        return {"label": label, "ok": False, "status": "", "content_type": "", "bytes": 0,
                "started_utc": started, "url": url, "text": "", "error": repr(e)}


def clean_number(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s or s.upper() in {"N.A.", "NA", "N/A", "NULL", "NONE", "-", "--"}:
        return None
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = s.replace("+", "").replace("%", "").replace(",", "").replace("−", "-").replace("–", "-")
    try:
        return float(s.strip())
    except Exception:
        return None


def month_to_num(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    if s.isdigit():
        n = int(s)
        return n if 1 <= n <= 12 else None
    return {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}.get(s[:3].title())


def flatten_json(obj, path="$"):
    rows = []
    if isinstance(obj, dict):
        rows.append({"path": path, "type": "dict", "keys": list(obj.keys()), "value": obj})
        for k, v in obj.items():
            rows.extend(flatten_json(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        rows.append({"path": path, "type": "list", "keys": [], "value": obj})
        for i, v in enumerate(obj[:5000]):
            rows.extend(flatten_json(v, f"{path}[{i}]"))
    else:
        rows.append({"path": path, "type": type(obj).__name__, "keys": [], "value": obj})
    return rows


def schema_preview_from_json_text(text, max_rows=300):
    try:
        payload = json.loads(text)
    except Exception as e:
        return pd.DataFrame([{"error": repr(e)}]), None
    flat = flatten_json(payload)
    recs = []
    for item in flat[:max_rows]:
        v = item["value"]
        recs.append({
            "path": item["path"],
            "type": item["type"],
            "keys": ", ".join(map(str, item["keys"][:20])) if item["keys"] else "",
            "sample": str(v)[:500].replace("\n", " ")
        })
    return pd.DataFrame(recs), payload


def extract_any_csd_table_rows(payload):
    """Return table-like rows from common C&SD JSON structures.
    This is intentionally exploratory: it exposes rows for diagnostics even before final parser is locked.
    """
    table_rows = []
    flat = flatten_json(payload)
    for item in flat:
        v = item["value"]
        if isinstance(v, dict):
            # dictionaries with many scalar values are potential data rows
            scalars = {k: val for k, val in v.items() if not isinstance(val, (dict, list))}
            if len(scalars) >= 3:
                row = dict(scalars)
                row["__path"] = item["path"]
                table_rows.append(row)
        elif isinstance(v, list) and v and all(not isinstance(x, (dict, list)) for x in v[:20]):
            # list of scalar cells is potential table row
            row = {f"col_{i}": val for i, val in enumerate(v[:30])}
            row["__path"] = item["path"]
            table_rows.append(row)
    if not table_rows:
        return pd.DataFrame()
    return pd.DataFrame(table_rows)


def parse_hk_from_any_rows(df):
    if df is None or df.empty:
        return None, pd.DataFrame()
    records = []
    # Strategy A: row contains Year/Month and value columns with labels
    for _, r in df.iterrows():
        vals = [str(x).strip() for x in r.tolist() if pd.notna(x)]
        joined = " ".join(vals).lower()
        # Scan sequentially for Year Month Index YoY pattern within row values
        for i in range(len(vals)-3):
            y = clean_number(vals[i])
            m = month_to_num(vals[i+1])
            idx = clean_number(vals[i+2])
            yoy = clean_number(vals[i+3])
            if y and 2000 <= y <= 2100 and m and idx and 50 <= idx <= 200 and yoy is not None and -10 <= yoy <= 20:
                records.append({"date": pd.Timestamp(int(y), int(m), 1), "value": yoy, "basis": "row sequential Year-Month-Index-YoY", "raw": " | ".join(vals[:25])})
        # Strategy B: any dict with explicit year/month and composite/yoy/value naming
        keys = {str(k).lower(): k for k in r.index}
        year = None; month = None
        for k_lower, k in keys.items():
            if k_lower in {"year", "yr"} or k_lower.endswith("year"):
                year = clean_number(r[k])
            if k_lower in {"month", "mth"} or k_lower.endswith("month"):
                month = month_to_num(r[k])
        if year and month:
            for k_lower, k in keys.items():
                if any(t in k_lower for t in ["year-on-year", "year on year", "yoy", "按年"]):
                    val = clean_number(r[k])
                    if val is not None and -10 <= val <= 20:
                        records.append({"date": pd.Timestamp(int(year), int(month), 1), "value": val, "basis": f"explicit key {k}", "raw": str(dict(r))[:500]})
    out = pd.DataFrame(records)
    if out.empty:
        return None, out
    out = out.dropna(subset=["date"]).sort_values("date")
    if out.empty:
        return None, pd.DataFrame(records)
    latest = out.iloc[-1]
    row = {
        "market": "HK",
        "indicator": "Inflation",
        "date": latest["date"].strftime("%Y-%m-%d"),
        "value": float(latest["value"]),
        "unit": "%",
        "source": "C&SD Table 510-60001 Composite CPI YoY",
        "source_type": "Official / API Lab",
        "notes": f"Parsed in Macro Adapter Lab; basis={latest.get('basis','')}",
    }
    return row, out


def hk_csd_51060001_json_explore():
    url = "https://www.censtatd.gov.hk/api/get.php?id=510-60001&lang=en&full_series=1"
    r = request_text(url, "HK C&SD 510-60001 JSON API", headers={"Accept": "application/json,text/plain,*/*"})
    debug = {k: v for k, v in r.items() if k != "text"}
    if not r["ok"]:
        return None, debug, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), ""
    schema_df, payload = schema_preview_from_json_text(r["text"], max_rows=500)
    if payload is None:
        debug["result"] = "json load failed"
        return None, debug, schema_df, pd.DataFrame(), pd.DataFrame(), r["text"][:5000]
    rows_df = extract_any_csd_table_rows(payload)
    row, parsed_df = parse_hk_from_any_rows(rows_df)
    debug["result"] = "ok" if row else "no HK CPI row parsed"
    debug["candidate_table_rows"] = len(rows_df)
    debug["parsed_candidate_rows"] = len(parsed_df)
    return row, debug, schema_df, rows_df, parsed_df, r["text"][:5000]


def hk_csd_51060001_web_text():
    url = "https://www.censtatd.gov.hk/en/web_table.html?id=510-60001&full_series=1"
    r = request_text(url, "HK C&SD 510-60001 web table", headers={"Accept": "text/html,*/*"})
    debug = {k: v for k, v in r.items() if k != "text"}
    text = re.sub(r"<[^>]+>", " ", r.get("text", ""))
    text = re.sub(r"\s+", " ", text)
    recs = []
    pat = re.compile(r"(20\d{2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{1,2})\s+(\d+(?:\.\d+)?)\s+([+\-−–]?\d+(?:\.\d+)?)", re.I)
    for m in pat.finditer(text):
        y = int(m.group(1)); mn = month_to_num(m.group(2)); val = clean_number(m.group(4))
        if mn and val is not None and -10 <= val <= 20:
            recs.append({"date": pd.Timestamp(y, mn, 1), "value": val, "raw": m.group(0)})
    df = pd.DataFrame(recs)
    debug["result"] = "ok" if not df.empty else "no web text rows parsed"
    if df.empty:
        return None, debug, df, text[:5000]
    df = df.sort_values("date")
    latest = df.iloc[-1]
    return {"market":"HK","indicator":"Inflation","date":latest["date"].strftime("%Y-%m-%d"),"value":float(latest["value"]),"unit":"%","source":"C&SD Table 510-60001 Composite CPI YoY","source_type":"Official / Web Lab","notes":"Parsed from web text in Macro Adapter Lab."}, debug, df, text[:5000]


def clean_macro_pack(df):
    df = df.copy()
    for c in STANDARD_COLS:
        if c not in df.columns:
            df[c] = ""
    mask_remove = df.apply(lambda r: (str(r["market"]).strip().upper(), str(r["indicator"]).strip().upper()) in APAC_RATE_KEYS, axis=1)
    cleaned = df.loc[~mask_remove].copy()
    return cleaned[STANDARD_COLS + [c for c in cleaned.columns if c not in STANDARD_COLS]]


def append_or_update_hk_inflation(df, row):
    df = df.copy()
    for c in STANDARD_COLS:
        if c not in df.columns:
            df[c] = ""
    mask = df["market"].astype(str).str.strip().str.upper().eq("HK") & df["indicator"].astype(str).str.strip().str.upper().eq("INFLATION")
    df = df.loc[~mask].copy()
    if row:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return df[STANDARD_COLS + [c for c in df.columns if c not in STANDARD_COLS]]


st.title("Global20Engine Macro Adapter Lab")
st.caption("Small isolated tester for macro source ideas before touching the full Global20Engine base file.")

with st.sidebar:
    st.header("Test controls")
    run_hk = st.button("Run HK Inflation dynamic test", use_container_width=True)
    uploaded = st.file_uploader("Optional: upload macro_data.csv", type=["csv"])

last_row = None
if run_hk:
    st.subheader("HK Inflation dynamic fetch result")
    row1, debug1, schema_df, rows_df, parsed_df, raw_json_preview = hk_csd_51060001_json_explore()
    row2, debug2, web_df, raw_web_preview = hk_csd_51060001_web_text()
    last_row = row1 or row2
    if last_row:
        st.success("HK Inflation parsed successfully.")
        st.dataframe(pd.DataFrame([last_row]), use_container_width=True)
    else:
        st.error("HK Inflation was not parsed by current attempts. Inspect schema/candidate rows below.")

    st.subheader("Attempt diagnostics")
    st.dataframe(pd.DataFrame([debug1, debug2]), use_container_width=True)

    with st.expander("JSON schema preview", expanded=False):
        st.dataframe(schema_df, use_container_width=True)
    with st.expander("JSON candidate table rows", expanded=True):
        st.write("Rows extracted from JSON structures that look table-like.")
        st.dataframe(rows_df.head(200), use_container_width=True)
    with st.expander("Parsed candidate rows", expanded=True):
        st.dataframe(parsed_df.head(200), use_container_width=True)
    with st.expander("Raw JSON first 5,000 characters", expanded=False):
        st.code(raw_json_preview[:5000])
    with st.expander("Web text parsed rows", expanded=False):
        st.dataframe(web_df.head(200), use_container_width=True)
    with st.expander("Raw web text first 5,000 characters", expanded=False):
        st.code(raw_web_preview[:5000])

if uploaded is not None:
    st.subheader("Macro pack cleaner preview")
    original = pd.read_csv(uploaded)
    st.write("Original rows", len(original))
    st.dataframe(original, use_container_width=True)
    cleaned = clean_macro_pack(original)
    if last_row is None:
        row1, *_ = hk_csd_51060001_json_explore()
        row2, *_ = hk_csd_51060001_web_text()
        last_row = row1 or row2
    final = append_or_update_hk_inflation(cleaned, last_row)
    st.write("Cleaned rows", len(final))
    st.dataframe(final, use_container_width=True)
    st.download_button("Download cleaned macro_data.csv", data=final.to_csv(index=False).encode("utf-8"), file_name="macro_data_cleaned.csv", mime="text/csv", use_container_width=True)

st.markdown("""
### Recommended workflow
1. Test a source here first.
2. Inspect diagnostics/schema until the parsed row is correct.
3. Only then copy the proven adapter logic into the full Global20Engine app or Power Query workbook.
""")
