
# macro_adapter_lab.py
# Global20Engine Macro Adapter Lab v3
# Purpose: inspect official macro APIs and prove parser logic before production updates.

import json
import re
import urllib.request
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Global20Engine Macro Adapter Lab", layout="wide", initial_sidebar_state="expanded")

USER_AGENT = "Mozilla/5.0 Global20Engine-MacroAdapterLab/3.0"
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
            "label": label,
            "ok": True,
            "status": status,
            "content_type": ctype,
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
    s = str(x).strip()
    if not s or s.upper() in {"N.A.", "NA", "N/A", "NULL", "NONE", "-", "--"}:
        return None
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = s.replace("+", "").replace("%", "").replace(",", "").replace("−", "-").replace("–", "-")
    try:
        return float(s.strip())
    except Exception:
        return None


def period_to_date(period):
    s = str(period).strip()
    if re.fullmatch(r"20\d{4}", s) or re.fullmatch(r"19\d{4}", s):
        y = int(s[:4]); m = int(s[4:6])
        if 1 <= m <= 12:
            return pd.Timestamp(y, m, 1)
    if re.fullmatch(r"20\d{2}", s) or re.fullmatch(r"19\d{2}", s):
        return pd.Timestamp(int(s), 1, 1)
    return pd.NaT


def flatten_json(obj, path="$"):
    rows = []
    if isinstance(obj, dict):
        rows.append({"path": path, "type": "dict", "keys": list(obj.keys()), "value": obj})
        for k, v in obj.items():
            rows.extend(flatten_json(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        rows.append({"path": path, "type": "list", "keys": [], "value": obj})
        for i, v in enumerate(obj[:10000]):
            rows.extend(flatten_json(v, f"{path}[{i}]"))
    else:
        rows.append({"path": path, "type": type(obj).__name__, "keys": [], "value": obj})
    return rows


def schema_preview_from_json_text(text, max_rows=500):
    try:
        payload = json.loads(text)
    except Exception as e:
        return pd.DataFrame([{"error": repr(e)}]), None
    recs = []
    for item in flatten_json(payload)[:max_rows]:
        v = item["value"]
        recs.append({
            "path": item["path"],
            "type": item["type"],
            "keys": ", ".join(map(str, item["keys"][:30])) if item["keys"] else "",
            "sample": str(v)[:600].replace("\n", " "),
        })
    return pd.DataFrame(recs), payload


def extract_dataset(payload):
    if isinstance(payload, dict) and isinstance(payload.get("dataSet"), list):
        return pd.DataFrame(payload["dataSet"])
    return pd.DataFrame()


def extract_code_dictionaries(payload):
    """Find likely metadata/code-description dictionaries so we can map sv codes to labels."""
    rows = []
    for item in flatten_json(payload):
        v = item["value"]
        if isinstance(v, dict):
            keys = {str(k).lower(): k for k in v.keys()}
            code_key = None
            desc_key = None
            for cand in ["code", "id", "name", "sv", "value"]:
                if cand in keys:
                    code_key = keys[cand]
                    break
            for cand in ["description", "desc", "label", "title", "name", "value"]:
                if cand in keys and keys[cand] != code_key:
                    desc_key = keys[cand]
                    break
            if code_key is not None and desc_key is not None:
                rows.append({"path": item["path"], "code": v.get(code_key), "description": v.get(desc_key), "keys": ", ".join(map(str, v.keys()))})
    if not rows:
        return pd.DataFrame(columns=["path", "code", "description", "keys"])
    return pd.DataFrame(rows).drop_duplicates()


def make_sv_summary(ds):
    if ds.empty or "sv" not in ds.columns:
        return pd.DataFrame()
    df = ds.copy()
    if "period" in df.columns:
        df["period_date"] = df["period"].apply(period_to_date)
    value_candidates = []
    for c in df.columns:
        if c in {"period_date"}:
            continue
        # treat any column with at least some numeric values as candidate value column
        nums = df[c].map(clean_number)
        if nums.notna().sum() > 0:
            value_candidates.append(c)
            df[f"__num_{c}"] = nums
    rows = []
    for sv, g in df.groupby("sv", dropna=False):
        latest_period = g["period"].iloc[-1] if "period" in g.columns and len(g) else ""
        latest_date = None
        if "period_date" in g.columns and g["period_date"].notna().any():
            latest_date = g["period_date"].max()
        row = {"sv": sv, "rows": len(g), "latest_period": latest_period, "latest_date": latest_date.strftime("%Y-%m-%d") if pd.notna(latest_date) else ""}
        for c in value_candidates:
            gg = g.copy()
            if "period_date" in gg.columns:
                gg = gg.sort_values("period_date")
            val = gg[f"__num_{c}"].dropna()
            row[f"latest_numeric_{c}"] = val.iloc[-1] if len(val) else None
        rows.append(row)
    return pd.DataFrame(rows)


def pick_hk_inflation_from_dataset(ds, sv_summary, dictionaries):
    """Best effort parser for C&SD Table 510-60001.
    Prefer a series whose metadata says Composite CPI + YoY; otherwise expose candidate rows, do not guess silently.
    """
    if ds.empty or "sv" not in ds.columns or "period" not in ds.columns:
        return None, pd.DataFrame(), "missing sv/period columns"

    # Build sv -> description map from metadata if available.
    desc_map = {}
    if dictionaries is not None and not dictionaries.empty:
        for _, r in dictionaries.iterrows():
            code = str(r.get("code", ""))
            desc = str(r.get("description", ""))
            if code and code != "None" and desc and desc != "None":
                desc_map[code] = desc

    value_cols = []
    for c in ds.columns:
        nums = ds[c].map(clean_number)
        if nums.notna().sum() > 10 and c not in {"period"}:
            value_cols.append(c)

    candidate_svs = []
    for sv in ds["sv"].dropna().astype(str).unique():
        desc = desc_map.get(sv, "")
        text = f"{sv} {desc}".lower()
        if ("composite" in text or "綜合" in text or "cc" in sv.lower()) and any(t in text for t in ["year-on-year", "year on year", "yoy", "按年", "yr-on-yr"]):
            candidate_svs.append((sv, desc, "metadata match"))

    # If metadata did not reveal it, produce safe candidates but do not hard-pick unless user can inspect.
    if not candidate_svs:
        # Use latest values by sv as diagnostic candidates. Do not return final row.
        cand = sv_summary.copy() if sv_summary is not None else pd.DataFrame()
        return None, cand, "no Composite CPI YoY series identified from metadata"

    records = []
    for sv, desc, basis in candidate_svs:
        g = ds[ds["sv"].astype(str) == sv].copy()
        g["period_date"] = g["period"].apply(period_to_date)
        for c in value_cols:
            g["value_num"] = g[c].map(clean_number)
            valid = g[g["period_date"].notna() & g["value_num"].notna()].copy()
            valid = valid[(valid["value_num"] > -10) & (valid["value_num"] < 20)]
            if not valid.empty:
                valid = valid.sort_values("period_date")
                latest = valid.iloc[-1]
                records.append({"sv": sv, "description": desc, "basis": basis, "value_col": c, "date": latest["period_date"], "value": latest["value_num"]})
    parsed = pd.DataFrame(records)
    if parsed.empty:
        return None, parsed, "metadata series found but no numeric latest value parsed"
    parsed = parsed.sort_values("date")
    latest = parsed.iloc[-1]
    row = {
        "market": "HK",
        "indicator": "Inflation",
        "date": latest["date"].strftime("%Y-%m-%d"),
        "value": float(latest["value"]),
        "unit": "%",
        "source": "C&SD Table 510-60001 Composite CPI YoY",
        "source_type": "Official / API Lab",
        "notes": f"Parsed via sv={latest['sv']}; {latest.get('description','')}; value_col={latest['value_col']}",
    }
    return row, parsed, "ok"


def hk_csd_51060001_json_explore():
    url = "https://www.censtatd.gov.hk/api/get.php?id=510-60001&lang=en&full_series=1"
    r = request_text(url, "HK C&SD 510-60001 JSON API", headers={"Accept": "application/json,text/plain,*/*"})
    debug = {k: v for k, v in r.items() if k != "text"}
    if not r["ok"]:
        return None, debug, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), ""
    schema_df, payload = schema_preview_from_json_text(r["text"], max_rows=800)
    if payload is None:
        debug["result"] = "json load failed"
        return None, debug, schema_df, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), r["text"][:5000]
    ds = extract_dataset(payload)
    dictionaries = extract_code_dictionaries(payload)
    sv_summary = make_sv_summary(ds)
    row, parsed_df, parse_result = pick_hk_inflation_from_dataset(ds, sv_summary, dictionaries)
    debug["result"] = parse_result
    debug["dataset_rows"] = len(ds)
    debug["dataset_cols"] = ", ".join(map(str, ds.columns)) if not ds.empty else ""
    debug["sv_count"] = ds["sv"].nunique() if not ds.empty and "sv" in ds.columns else 0
    return row, debug, schema_df, ds, dictionaries, sv_summary, parsed_df, r["text"][:5000]


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
    row, debug, schema_df, ds, dictionaries, sv_summary, parsed_df, raw_preview = hk_csd_51060001_json_explore()
    last_row = row
    if row:
        st.success("HK Inflation parsed successfully.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.error("HK Inflation was not parsed automatically. Inspect sv summary and dictionaries below.")

    st.subheader("Attempt diagnostics")
    st.dataframe(pd.DataFrame([debug]), use_container_width=True)

    with st.expander("Dataset columns and first 100 rows", expanded=True):
        st.dataframe(ds.head(100), use_container_width=True)
    with st.expander("SV summary - most important table", expanded=True):
        st.write("This groups the C&SD dataSet by `sv`. We need to identify which `sv` means Composite CPI YoY.")
        st.dataframe(sv_summary, use_container_width=True)
    with st.expander("Code dictionaries / metadata", expanded=True):
        st.dataframe(dictionaries.head(500), use_container_width=True)
    with st.expander("Parsed candidate rows", expanded=True):
        st.dataframe(parsed_df.head(500), use_container_width=True)
    with st.expander("JSON schema preview", expanded=False):
        st.dataframe(schema_df, use_container_width=True)
    with st.expander("Raw JSON first 5,000 characters", expanded=False):
        st.code(raw_preview)

if uploaded is not None:
    st.subheader("Macro pack cleaner preview")
    original = pd.read_csv(uploaded)
    st.write("Original rows", len(original))
    st.dataframe(original, use_container_width=True)
    cleaned = clean_macro_pack(original)
    if last_row is None:
        last_row, *_ = hk_csd_51060001_json_explore()
    final = append_or_update_hk_inflation(cleaned, last_row)
    st.write("Cleaned rows", len(final))
    st.dataframe(final, use_container_width=True)
    st.download_button("Download cleaned macro_data.csv", data=final.to_csv(index=False).encode("utf-8"), file_name="macro_data_cleaned.csv", mime="text/csv", use_container_width=True)

st.markdown("""
### Recommended workflow
1. Identify the correct `sv` code for Composite CPI YoY in **SV summary** or **Code dictionaries**.
2. Lock that `sv` code in this lab.
3. Only then copy the proven adapter logic into the full Global20Engine app or macro fetcher.
""")
