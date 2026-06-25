
# macro_adapter_lab.py
# Global20Engine Macro Adapter Lab
# Purpose: test macro/rate data ideas in isolation before touching the full base app.

import io
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Global20Engine Macro Adapter Lab",
    layout="wide",
    initial_sidebar_state="expanded",
)

USER_AGENT = "Mozilla/5.0 Global20Engine-MacroAdapterLab/1.0"
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
        text = raw.decode("utf-8", errors="replace")
        return {
            "label": label,
            "ok": True,
            "status": status,
            "content_type": ctype,
            "bytes": len(raw),
            "started_utc": started,
            "url": url,
            "text": text,
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
    s = str(x).strip()
    if not s or s.upper() in {"N.A.", "NA", "N/A", "NULL", "NONE", "-"}:
        return None
    s = s.replace("+", "").replace("%", "").replace(",", "").replace("−", "-").replace("–", "-")
    s = re.sub(r"\[[^\]]*\]", "", s).strip()
    try:
        return float(s)
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
    m = s[:3].title()
    months = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    return months.get(m)


def flatten_json(obj, prefix=""):
    rows = []
    if isinstance(obj, dict):
        rows.append(obj)
        for v in obj.values():
            rows.extend(flatten_json(v, prefix))
    elif isinstance(obj, list):
        for v in obj:
            rows.extend(flatten_json(v, prefix))
    return rows


def hk_csd_51060001_from_json_api():
    """Attempt 1: parse C&SD JSON API for Composite CPI YoY."""
    url = "https://www.censtatd.gov.hk/api/get.php?id=510-60001&lang=en&full_series=1"
    r = request_text(url, "HK C&SD 510-60001 JSON API", headers={"Accept": "application/json,text/plain,*/*"})
    debug = {k: v for k, v in r.items() if k != "text"}
    if not r["ok"]:
        return None, debug, pd.DataFrame()

    text = r["text"]
    records = []
    try:
        payload = json.loads(text)
        candidates = flatten_json(payload)
        for d in candidates:
            joined_keys = " ".join(str(k) for k in d.keys()).lower()
            joined_vals = " ".join(str(v) for v in d.values() if isinstance(v, (str, int, float))).lower()
            joined = joined_keys + " " + joined_vals
            if "composite" not in joined or "consumer price" not in joined:
                continue
            if not any(t in joined for t in ["year-on-year", "year on year", "yoy", "按年"]):
                continue
            if any(t in joined for t in ["month-to-month", "month on month", "mom", "按月"]):
                continue
            year = None
            month = None
            dt = None
            for yk in ["year", "Year", "YEAR"]:
                if yk in d:
                    year = clean_number(d.get(yk))
            for mk in ["month", "Month", "MONTH"]:
                if mk in d:
                    month = d.get(mk)
            for dk in ["period", "Period", "time", "TIME_PERIOD", "date", "Date"]:
                if dk in d and str(d.get(dk, "")).strip():
                    dt = pd.to_datetime(str(d.get(dk)), errors="coerce")
                    break
            if pd.isna(dt) or dt is None:
                mnum = month_to_num(month)
                if year and mnum:
                    dt = pd.Timestamp(int(year), int(mnum), 1)
            for vk in ["value", "Value", "figure", "Figure", "obs_value", "OBS_VALUE", "data", "Data"]:
                if vk in d:
                    val = clean_number(d.get(vk))
                    if val is not None and -10 <= val <= 20:
                        records.append({"date": dt, "value": val, "field": vk, "raw": str(d)[:500]})
                        break
    except Exception as e:
        debug["json_parse_error"] = repr(e)

    df = pd.DataFrame(records)
    if df.empty:
        debug["result"] = "no JSON candidate rows parsed"
        return None, debug, df
    df = df.dropna(subset=["date"]).sort_values("date")
    if df.empty:
        debug["result"] = "candidate rows found but dates were blank"
        return None, debug, pd.DataFrame(records)
    latest = df.iloc[-1]
    row = {
        "market": "HK",
        "indicator": "Inflation",
        "date": latest["date"].strftime("%Y-%m-%d"),
        "value": float(latest["value"]),
        "unit": "%",
        "source": "C&SD Table 510-60001 Composite CPI YoY",
        "source_type": "Official / API",
        "notes": "Fetched dynamically from C&SD Table 510-60001 JSON API; Composite CPI year-on-year % change.",
    }
    debug["result"] = "ok"
    return row, debug, df


def hk_csd_51060001_from_web_text():
    """Attempt 2: parse rendered web/table text from C&SD page / search-like HTML."""
    url = "https://www.censtatd.gov.hk/en/web_table.html?id=510-60001&full_series=1"
    r = request_text(url, "HK C&SD 510-60001 web table", headers={"Accept": "text/html,*/*"})
    debug = {k: v for k, v in r.items() if k != "text"}
    if not r["ok"]:
        return None, debug, pd.DataFrame()

    text = re.sub(r"<[^>]+>", " ", r["text"])
    text = re.sub(r"\s+", " ", text)
    records = []
    # Expected displayed order: Year Month Composite Index Composite YoY Composite MoM ...
    # E.g. 2026 May 111.6 +2.0 ...
    pat = re.compile(r"(20\d{2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{1,2})\s+(\d+(?:\.\d+)?)\s+([+\-−–]?\d+(?:\.\d+)?)", re.I)
    for m in pat.finditer(text):
        year = int(m.group(1))
        mon = m.group(2)
        mnum = month_to_num(mon)
        val = clean_number(m.group(4))
        if mnum and val is not None and -10 <= val <= 20:
            records.append({"date": pd.Timestamp(year, mnum, 1), "value": val, "raw": m.group(0)})
    df = pd.DataFrame(records)
    if df.empty:
        debug["result"] = "no web text rows parsed"
        return None, debug, df
    df = df.sort_values("date")
    latest = df.iloc[-1]
    row = {
        "market": "HK",
        "indicator": "Inflation",
        "date": latest["date"].strftime("%Y-%m-%d"),
        "value": float(latest["value"]),
        "unit": "%",
        "source": "C&SD Table 510-60001 Composite CPI YoY",
        "source_type": "Official / Web Table",
        "notes": "Fetched dynamically from C&SD Table 510-60001 web table; Composite CPI year-on-year % change.",
    }
    debug["result"] = "ok"
    return row, debug, df


def hk_csd_51060001_best_effort():
    attempts = []
    for fn in [hk_csd_51060001_from_json_api, hk_csd_51060001_from_web_text]:
        row, debug, df = fn()
        attempts.append((row, debug, df))
        if row is not None:
            return row, attempts
    return None, attempts


def clean_macro_pack(df):
    df = df.copy()
    for c in STANDARD_COLS:
        if c not in df.columns:
            df[c] = ""
    mask_remove = df.apply(
        lambda r: (str(r["market"]).strip().upper(), str(r["indicator"]).strip().upper()) in APAC_RATE_KEYS,
        axis=1,
    )
    cleaned = df.loc[~mask_remove].copy()
    return cleaned[STANDARD_COLS + [c for c in cleaned.columns if c not in STANDARD_COLS]]


def append_or_update_hk_inflation(df, row):
    df = df.copy()
    for c in STANDARD_COLS:
        if c not in df.columns:
            df[c] = ""
    mask = df["market"].astype(str).str.strip().str.upper().eq("HK") & df["indicator"].astype(str).str.strip().str.upper().eq("INFLATION")
    df = df.loc[~mask].copy()
    if row is not None:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return df[STANDARD_COLS + [c for c in df.columns if c not in STANDARD_COLS]]


st.title("Global20Engine Macro Adapter Lab")
st.caption("Small isolated tester for macro source ideas before touching the full Global20Engine base file.")

with st.sidebar:
    st.header("Test controls")
    run_hk = st.button("Run HK Inflation dynamic test", use_container_width=True)
    st.markdown("---")
    uploaded = st.file_uploader("Optional: upload macro_data.csv", type=["csv"])

if run_hk:
    row, attempts = hk_csd_51060001_best_effort()
    st.subheader("HK Inflation dynamic fetch result")
    if row:
        st.success("HK Inflation parsed successfully.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.error("HK Inflation was not parsed by any current attempt.")

    st.subheader("Attempt diagnostics")
    diag_rows = []
    for i, (r, debug, df) in enumerate(attempts, start=1):
        d = dict(debug)
        d["attempt"] = i
        d["parsed_rows"] = len(df) if isinstance(df, pd.DataFrame) else 0
        d["success"] = r is not None
        diag_rows.append(d)
    st.dataframe(pd.DataFrame(diag_rows), use_container_width=True)

    for i, (r, debug, df) in enumerate(attempts, start=1):
        with st.expander(f"Attempt {i} parsed rows preview"):
            st.dataframe(df.head(30), use_container_width=True)

if uploaded is not None:
    st.subheader("Macro pack cleaner preview")
    original = pd.read_csv(uploaded)
    st.write("Original rows", len(original))
    st.dataframe(original, use_container_width=True)
    cleaned = clean_macro_pack(original)
    row, attempts = hk_csd_51060001_best_effort()
    final = append_or_update_hk_inflation(cleaned, row)
    st.write("Cleaned rows", len(final))
    st.dataframe(final, use_container_width=True)
    csv = final.to_csv(index=False).encode("utf-8")
    st.download_button("Download cleaned macro_data.csv", data=csv, file_name="macro_data_cleaned.csv", mime="text/csv", use_container_width=True)

st.markdown("""
### Recommended workflow
1. Test a source here first.
2. Confirm the parsed row and diagnostics.
3. Only then copy the proven adapter logic into the full Global20Engine app or Power Query workbook.
""")
