#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
g20_macro_fetcher.py
Global20Engine monthly macro-pack generator.

Policy locked 2026-06-25:
- APAC Rates are live-API decisions and must NOT be exported as active macro_data rows:
  SG Rates, MY Rates, HK Rates, JP Rates.
- HK Inflation is monthly CPI data and is dynamically fetched from C&SD Table 510-60001.
- HK Inflation parser proven in macro_adapter_lab.py:
  sv = CC_CM_1920, period = YYYYMM, value = figure.

Outputs written to macro_pack_latest/:
- macro_data.csv
- diagnostics.csv
- manual_required.csv
- source_catalogue.csv
- source_links.csv
- README.csv
- macro_pack.xlsx, if openpyxl is available
- macro_pack_csv_bundle.zip
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import sys
import time
import zipfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

OUT_DIR = Path("macro_pack_latest")
OUT_DIR.mkdir(parents=True, exist_ok=True)

GEN_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
USER_AGENT = "Global20Engine-MacroFetcher/2026.06.25"
TIMEOUT = 30

STANDARD_COLS = ["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"]
DIAG_COLS = ["market", "indicator", "source_name", "status", "value", "reason", "endpoint", "generated_at"]
MANUAL_COLS = ["market", "indicator", "reason", "suggested_action"]

# Live-first source policy. These must not appear as active rows in macro_data.csv.
APAC_LIVE_RATE_KEYS = {("SG", "Rates"), ("MY", "Rates"), ("HK", "Rates"), ("JP", "Rates")}

# Confirmed in Macro Adapter Lab from C&SD Table 510-60001 API.
HK_CSD_CPI_URL = "https://www.censtatd.gov.hk/api/get.php?id=510-60001&lang=en&full_series=1"
HK_COMPOSITE_CPI_YOY_SV = "CC_CM_1920"

ROWS: list[dict] = []
DIAG: list[dict] = []
MANUAL: list[dict] = []


def request_text(url: str, *, accept: str = "*/*") -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


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
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def period_yyyymm_to_date(period: str) -> pd.Timestamp:
    s = str(period).strip()
    if not re.fullmatch(r"\d{6}", s):
        return pd.NaT
    y = int(s[:4])
    m = int(s[4:6])
    if not (1 <= m <= 12):
        return pd.NaT
    return pd.Timestamp(y, m, 1)


def diag(market: str, indicator: str, source_name: str, status: str, value="", reason="", endpoint=""):
    DIAG.append(
        {
            "market": market,
            "indicator": indicator,
            "source_name": source_name,
            "status": status,
            "value": value,
            "reason": reason,
            "endpoint": endpoint,
            "generated_at": GEN_AT,
        }
    )


def manual(market: str, indicator: str, reason: str, suggested_action: str = "Review latest official value"):
    MANUAL.append(
        {
            "market": market,
            "indicator": indicator,
            "reason": reason,
            "suggested_action": suggested_action,
        }
    )


def row(market: str, indicator: str, date: str, value, unit: str, source: str, source_type: str, notes: str = ""):
    ROWS.append(
        {
            "market": market,
            "indicator": indicator,
            "date": date,
            "value": value,
            "unit": unit,
            "source": source,
            "source_type": source_type,
            "notes": notes,
        }
    )


# ---------------------------------------------------------------------
# Official source fetchers
# ---------------------------------------------------------------------

def fetch_fred_raw(series_id: str) -> pd.DataFrame:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urllib.parse.urlencode({"id": series_id})
    txt = request_text(url, accept="text/csv,*/*")
    df = pd.read_csv(io.StringIO(txt))
    # FRED usually returns DATE,<SERIES>; make this tolerant.
    cols_lower = {c.lower(): c for c in df.columns}
    date_col = cols_lower.get("date") or df.columns[0]
    value_col = series_id if series_id in df.columns else [c for c in df.columns if c != date_col][0]
    out = df[[date_col, value_col]].copy()
    out.columns = ["date", "value"]
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["date", "value"]).sort_values("date")
    if out.empty:
        raise ValueError(f"FRED {series_id} returned no usable rows")
    return out


def add_fred_latest(series_id: str, market: str, indicator: str, unit: str, source: str, notes: str = ""):
    endpoint = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        df = fetch_fred_raw(series_id)
        latest = df.iloc[-1]
        value = float(latest["value"])
        date = latest["date"].strftime("%Y-%m-%d")
        if indicator == "Claims":
            value = round(value / 1000.0, 3)
        row(market, indicator, date, value, unit, source, "Official / API", notes)
        diag(market, indicator, source, "success", value=value, reason=f"{date} = {value}{unit}", endpoint=endpoint)
    except Exception as e:
        diag(market, indicator, source, "failed", reason=str(e), endpoint=endpoint)
        manual(market, indicator, f"{source} fetch failed: {e}")


def add_us_cpi_yoy():
    endpoint = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"
    try:
        df = fetch_fred_raw("CPIAUCSL")
        latest = df.iloc[-1]
        prior_date = latest["date"] - pd.DateOffset(months=12)
        prior_candidates = df[df["date"] <= prior_date].sort_values("date")
        if prior_candidates.empty:
            raise ValueError("No CPI row at least 12 months before latest")
        prior = prior_candidates.iloc[-1]
        yoy = (float(latest["value"]) / float(prior["value"]) - 1.0) * 100.0
        value = round(yoy, 3)
        date = latest["date"].strftime("%Y-%m-%d")
        row("US", "Inflation", date, value, "%", "FRED CPIAUCSL YoY", "Official / API", "Computed from latest CPI index versus CPI about 12 months earlier.")
        diag("US", "Inflation", "FRED CPIAUCSL YoY", "success", value=f"{value}%", reason=f"{date} = {value}%", endpoint=endpoint)
    except Exception as e:
        diag("US", "Inflation", "FRED CPIAUCSL YoY", "failed", reason=str(e), endpoint=endpoint)
        manual("US", "Inflation", f"FRED CPIAUCSL YoY failed: {e}")


def fetch_hk_csd_composite_cpi_yoy() -> dict:
    """
    Fetch HK Composite CPI YoY from C&SD Table 510-60001.

    Confirmed in Macro Adapter Lab:
    - sv = CC_CM_1920 is Composite CPI YoY.
    - period is YYYYMM.
    - figure is the YoY percentage value.
    """
    payload = json.loads(request_text(HK_CSD_CPI_URL, accept="application/json,text/plain,*/*"))
    data = payload.get("dataSet", [])
    df = pd.DataFrame(data)
    if df.empty:
        raise ValueError("C&SD Table 510-60001 returned empty dataSet")
    required = {"period", "sv", "figure"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"C&SD Table 510-60001 missing required columns: {sorted(missing)}")
    target = df[df["sv"].astype(str).str.strip().eq(HK_COMPOSITE_CPI_YOY_SV)].copy()
    if target.empty:
        raise ValueError(f"C&SD Table 510-60001 target sv not found: {HK_COMPOSITE_CPI_YOY_SV}")
    target["date"] = target["period"].apply(period_yyyymm_to_date)
    target["value"] = target["figure"].map(clean_number)
    target = target.dropna(subset=["date", "value"])
    target = target[(target["value"] > -10) & (target["value"] < 20)]
    if target.empty:
        raise ValueError("C&SD Table 510-60001 target sv had no valid numeric figure")
    latest = target.sort_values("date").iloc[-1]
    return {
        "market": "HK",
        "indicator": "Inflation",
        "date": latest["date"].strftime("%Y-%m-%d"),
        "value": float(latest["value"]),
        "unit": "%",
        "source": "C&SD Table 510-60001 Composite CPI YoY",
        "source_type": "Official / API",
        "notes": f"Fetched from C&SD Table 510-60001 JSON API; sv={HK_COMPOSITE_CPI_YOY_SV}; period={latest['period']}; figure column.",
    }


def add_hk_inflation():
    try:
        hk = fetch_hk_csd_composite_cpi_yoy()
        row(hk["market"], hk["indicator"], hk["date"], hk["value"], hk["unit"], hk["source"], hk["source_type"], hk["notes"])
        diag("HK", "Inflation", "C&SD Table 510-60001 Composite CPI YoY", "success", value=f"{hk['value']}%", reason=f"Fetched dynamically for {hk['date']}", endpoint=HK_CSD_CPI_URL)
    except Exception as e:
        diag("HK", "Inflation", "C&SD Table 510-60001 Composite CPI YoY", "failed", reason=str(e), endpoint=HK_CSD_CPI_URL)
        manual("HK", "Inflation", f"C&SD Table 510-60001 fetch failed: {e}", "Review C&SD Table 510-60001 Composite CPI YoY manually")


# Optional / regional helpers. These are deliberately tolerant. If a source fails, diagnostics/manual rows capture it.

def add_opendosm_malaysia_cpi():
    url = "https://storage.dosm.gov.my/cpi/cpi_2d_inflation.csv"

    try:
        txt = request_text(url, accept="text/csv,text/plain,*/*")
        df = pd.read_csv(io.StringIO(txt))

        if df.empty:
            raise ValueError("OpenDOSM CPI inflation CSV returned empty payload")

        df.columns = [str(c).strip().lower() for c in df.columns]

        required = {"date", "division", "inflation_yoy"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"OpenDOSM CPI inflation CSV missing columns: {sorted(missing)}")

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["inflation_yoy"] = pd.to_numeric(df["inflation_yoy"], errors="coerce")

        got = df[df["division"].astype(str).str.lower().str.strip().eq("overall")].copy()
        got = got.dropna(subset=["date", "inflation_yoy"]).sort_values("date")
        got = got[(got["inflation_yoy"] > -10) & (got["inflation_yoy"] < 25)]

        if got.empty:
            raise ValueError("Could not identify usable division=overall inflation_yoy rows from OpenDOSM CSV")

        latest = got.iloc[-1]
        value = round(float(latest["inflation_yoy"]), 3)
        date_txt = latest["date"].strftime("%Y-%m-%d")

        row(
            "MY",
            "Inflation",
            date_txt,
            value,
            "%",
            "OpenDOSM storage CSV cpi_2d_inflation",
            "success",
            value=value,
            reason="Fetched Malaysia headline CPI inflation YoY from OpenDOSM official CSV; filtered division=overall",
        )

        diag(
            "MY",
            "Inflation",
            "OpenDOSM storage CSV cpi_2d_inflation",
            "success",
            value=value,
            reason=f"Latest division=overall inflation_yoy = {value} for {date_txt}",
            endpoint=url,
        )

    except Exception as e:
        diag(
            "MY",
            "Inflation",
            "OpenDOSM storage CSV cpi_2d_inflation",
            "failed",
            reason=str(e),
            endpoint=url,
        )
        manual("MY", "Inflation", f"OpenDOSM CPI inflation CSV fetch failed: {e}")



# ---------------------------------------------------------------------
# Static reviewed rows / seed rows retained from the current workbook policy
# ---------------------------------------------------------------------

def add_static_reviewed_rows():
    # These rows preserve the currently reviewed monthly pack values where official dynamic source is not yet migrated.
    row("SG", "Inflation", "2026-05-01", 1.8, "%", "SingStat CPI", "Official / Reviewed", "Reviewed static row pending full SingStat macro-pack integration.")
    diag("SG", "Inflation", "SingStat CPI", "reviewed_static", value="1.8%", reason="Reviewed row retained", endpoint="")

    row("SG", "Unemployment", "2026-03-01", 2.0, "%", "MOM / SingStat unemployment", "Official / Reviewed", "Singapore overall unemployment rate for Mar-26 / 1Q 2026; reviewed static row.")
    diag("SG", "Unemployment", "MOM / SingStat unemployment", "reviewed_static", value="2.0%", reason="Reviewed row retained", endpoint="")


def add_pmi_seeds():
    seeds = [
        ("US", "PMI", "2026-06-01", 54.0, "index", "ISM Manufacturing PMI / seed fallback", "Seed", "Seed fallback; review before active use."),
        ("SG", "PMI", "2026-06-01", 51.0, "index", "SIPMM Singapore Manufacturing PMI", "Seed", "Seed fallback; review before active use."),
        ("HK", "PMI", "2026-06-01", 50.4, "index", "S&P Global Hong Kong SAR PMI", "Seed", "Seed fallback; review before active use."),
        ("CN", "PMI", "2026-06-01", 50.0, "index", "NBS Manufacturing PMI", "Seed", "Seed fallback; review before active use."),
        ("MY", "PMI", "2026-06-01", 49.9, "index", "S&P Global Malaysia Manufacturing PMI", "Seed", "Seed fallback; review before active use."),
        ("JP", "PMI", "2026-06-01", 50.4, "index", "au Jibun Bank Japan Manufacturing PMI", "Seed", "Seed fallback; review before active use."),
    ]
    for args in seeds:
        row(*args)
        diag(args[0], args[1], args[5], "seed", value=args[3], reason=args[7], endpoint="")


# ---------------------------------------------------------------------
# Final policy guards and export
# ---------------------------------------------------------------------

def remove_apac_live_rate_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    mask = df.apply(
        lambda r: (
            str(r.get("market", "")).strip().upper(),
            str(r.get("indicator", "")).strip().title(),
        ) in APAC_LIVE_RATE_KEYS,
        axis=1,
    )
    return df.loc[~mask].copy()


def standardise_macro_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=STANDARD_COLS)
    out = df.copy()
    for c in STANDARD_COLS:
        if c not in out.columns:
            out[c] = ""
    out = out[STANDARD_COLS + [c for c in out.columns if c not in STANDARD_COLS]]
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["value"])
    return out


def source_catalogue_df() -> pd.DataFrame:
    rows = [
        {"market":"SG","indicator":"Rates","source":"MAS SORA","endpoint_or_url":"MAS open search/API route in Streamlit live adapter","frequency":"Daily","role":"Live API only","notes":"Decision 1; excluded from active macro_data.csv."},
        {"market":"MY","indicator":"Rates","source":"BNM OPR","endpoint_or_url":"BNM OpenAPI live adapter","frequency":"Policy/daily availability","role":"Live API only","notes":"Decision 2; excluded from active macro_data.csv."},
        {"market":"HK","indicator":"Rates","source":"HKMA HIBOR / HKD rates","endpoint_or_url":"HKMA Open API live adapter","frequency":"Daily","role":"Live API only","notes":"Decision 3; excluded from active macro_data.csv."},
        {"market":"JP","indicator":"Rates","source":"BOJ FM01 overnight call rate","endpoint_or_url":"BOJ Time-Series API live adapter","frequency":"Daily","role":"Live API only","notes":"Decision 4; excluded from active macro_data.csv."},
        {"market":"MY","indicator":"Unemployment","source":"OpenDOSM u_rate","endpoint_or_url":"OpenDOSM API live adapter","frequency":"Monthly","role":"Live API exception","notes":"Decision 5; live API due unreliable monthly pack route."},
        {"market":"JP","indicator":"Unemployment","source":"DBnomics / STATJP","endpoint_or_url":"DBnomics API live adapter","frequency":"Monthly","role":"Live API exception","notes":"Decision 6; live API due unreliable monthly pack route."},
        {"market":"JP","indicator":"Inflation","source":"DBnomics / STATJP CPI","endpoint_or_url":"DBnomics API live adapter","frequency":"Monthly","role":"Live API exception","notes":"Decision 7; live API due unreliable monthly pack route."},
        {"market":"HK","indicator":"Inflation","source":"C&SD Table 510-60001 Composite CPI YoY","endpoint_or_url":HK_CSD_CPI_URL,"frequency":"Monthly","role":"Macro pack official API","notes":"sv=CC_CM_1920; period=YYYYMM; value=figure."},
        {"market":"US","indicator":"Inflation","source":"FRED CPIAUCSL YoY","endpoint_or_url":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL","frequency":"Monthly","role":"Macro pack official API","notes":"Computed YoY from CPI index."},
        {"market":"US","indicator":"Unemployment","source":"FRED UNRATE","endpoint_or_url":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNRATE","frequency":"Monthly","role":"Macro pack official API","notes":"Latest value."},
        {"market":"US","indicator":"Claims","source":"FRED ICSA","endpoint_or_url":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=ICSA","frequency":"Weekly","role":"Macro pack official API","notes":"Converted to thousands."},
        {"market":"US","indicator":"Rates","source":"FRED DGS10","endpoint_or_url":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10","frequency":"Daily","role":"Macro pack official API","notes":"US 10-year Treasury constant maturity."},
    ]
    return pd.DataFrame(rows)


def source_links_df() -> pd.DataFrame:
    return source_catalogue_df()[["market", "indicator", "source", "endpoint_or_url", "role", "notes"]]


def readme_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"item":"generated_at", "detail":GEN_AT},
            {"item":"policy", "detail":"APAC Rates SG/MY/HK/JP are live API only and removed from active macro_data.csv."},
            {"item":"hk_inflation", "detail":"HK Inflation fetched dynamically from C&SD Table 510-60001 JSON API using sv=CC_CM_1920."},
            {"item":"decisions_5_7", "detail":"MY unemployment, JP unemployment, JP inflation remain live API exceptions due unreliable monthly macro pack route."},
        ]
    )


def write_outputs(macro_df: pd.DataFrame):
    macro_df = standardise_macro_df(remove_apac_live_rate_rows(macro_df))
    diag_df = pd.DataFrame(DIAG, columns=DIAG_COLS)
    manual_df = pd.DataFrame(MANUAL, columns=MANUAL_COLS)
    catalogue_df = source_catalogue_df()
    links_df = source_links_df()
    readme = readme_df()

    macro_df.to_csv(OUT_DIR / "macro_data.csv", index=False)
    diag_df.to_csv(OUT_DIR / "diagnostics.csv", index=False)
    manual_df.to_csv(OUT_DIR / "manual_required.csv", index=False)
    catalogue_df.to_csv(OUT_DIR / "source_catalogue.csv", index=False)
    links_df.to_csv(OUT_DIR / "source_links.csv", index=False)
    readme.to_csv(OUT_DIR / "README.csv", index=False)

    with zipfile.ZipFile(OUT_DIR / "macro_pack_csv_bundle.zip", "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in ["macro_data.csv", "diagnostics.csv", "manual_required.csv", "source_catalogue.csv", "source_links.csv", "README.csv"]:
            z.write(OUT_DIR / name, arcname=name)

    try:
        with pd.ExcelWriter(OUT_DIR / "macro_pack.xlsx", engine="openpyxl") as writer:
            macro_df.to_excel(writer, sheet_name="macro_data", index=False)
            diag_df.to_excel(writer, sheet_name="diagnostics", index=False)
            manual_df.to_excel(writer, sheet_name="manual_required", index=False)
            catalogue_df.to_excel(writer, sheet_name="source_catalogue", index=False)
            links_df.to_excel(writer, sheet_name="source_links", index=False)
            readme.to_excel(writer, sheet_name="README", index=False)
    except Exception as e:
        diag("PACK", "Excel", "openpyxl", "failed", reason=str(e), endpoint="")
        pd.DataFrame(DIAG, columns=DIAG_COLS).to_csv(OUT_DIR / "diagnostics.csv", index=False)

    print(f"Generated {OUT_DIR / 'macro_data.csv'} with {len(macro_df)} rows")
    print(f"Generated {OUT_DIR / 'diagnostics.csv'} with {len(DIAG)} rows")
    if len(manual_df):
        print(f"Manual review items: {len(manual_df)}")


def build_pack():
    # US official sources.
    add_us_cpi_yoy()
    add_fred_latest("UNRATE", "US", "Unemployment", "%", "FRED UNRATE", "US unemployment rate.")
    add_fred_latest("ICSA", "US", "Claims", "k", "FRED ICSA", "US initial claims; converted to thousands.")
    add_fred_latest("DGS10", "US", "Rates", "%", "FRED DGS10", "US 10-year Treasury constant maturity rate.")

    # APAC / monthly sources.
    add_static_reviewed_rows()
    add_opendosm_malaysia_cpi()
    add_hk_inflation()
    add_pmi_seeds()

    write_outputs(pd.DataFrame(ROWS))


if __name__ == "__main__":
    build_pack()
