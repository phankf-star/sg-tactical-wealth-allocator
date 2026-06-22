#!/usr/bin/env python3
"""
Global20Engine external macro/performance fetcher
Version: v38 external-fetch draft

Purpose
-------
Run outside Streamlit so the Streamlit app becomes a display/decision layer only.
Recommended runtime: GitHub Actions monthly/scheduled/manual run.

Outputs
-------
- macro_data.csv
- diagnostics.csv
- manual_required.csv
- manual_input_template.csv
- source_links.csv
- source_catalogue.csv
- README.csv
- macro_pack_csv_bundle.zip
- macro_pack.xlsx if openpyxl is available

Notes
-----
This script intentionally uses Python standard library + pandas only.
It prioritises official CSV/API-style sources where practical, and records every failure
in diagnostics/manual_required instead of silently failing inside Streamlit.
"""

from __future__ import annotations

import io
import json
import math
import zipfile
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

OUT = Path("macro_pack_latest")
OUT.mkdir(exist_ok=True)

PACK_MONTH = datetime.now().strftime("%Y-%m")
GEN_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

SOURCE_LINKS = [
    {"market":"US","indicator":"Inflation","source_name":"FRED CPIAUCSL","url":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL","manual_role":"fallback/check only"},
    {"market":"US","indicator":"Unemployment","source_name":"FRED UNRATE","url":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNRATE","manual_role":"fallback/check only"},
    {"market":"US","indicator":"Claims","source_name":"FRED ICSA","url":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=ICSA","manual_role":"fallback/check only"},
    {"market":"US","indicator":"Rates","source_name":"FRED DGS10","url":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10","manual_role":"fallback/check only"},
    {"market":"US","indicator":"PMI","source_name":"FRED NAPM / ISM Manufacturing PMI","url":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=NAPM","manual_role":"fallback/check only"},
    {"market":"SG","indicator":"Inflation","source_name":"SingStat CPI table","url":"https://tablebuilder.singstat.gov.sg/","manual_role":"official check if adapter fails"},
    {"market":"SG","indicator":"Unemployment","source_name":"SingStat / MOM unemployment","url":"https://tablebuilder.singstat.gov.sg/","manual_role":"official check if adapter fails"},
    {"market":"SG","indicator":"Rates","source_name":"MAS domestic rates / SORA","url":"https://eservices.mas.gov.sg/statistics/","manual_role":"official check if adapter fails"},
    {"market":"SG","indicator":"PMI","source_name":"SIPMM Singapore Manufacturing PMI","url":"https://sipmm.edu.sg/resources/singapore-pmi/","manual_role":"official check if calendar source fails"},
    {"market":"HK","indicator":"Inflation","source_name":"HKMA / C&SD CPI","url":"https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/financial/economic-statistics","manual_role":"validation check"},
    {"market":"HK","indicator":"Unemployment","source_name":"HKMA unemployment","url":"https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/financial/economic-statistics","manual_role":"fallback/check only"},
    {"market":"HK","indicator":"Rates","source_name":"HKMA interest rates","url":"https://www.hkma.gov.hk/eng/data-publications-and-research/data-and-statistics/","manual_role":"official check if adapter fails"},
    {"market":"HK","indicator":"PMI","source_name":"S&P Global Hong Kong SAR PMI","url":"https://tradingeconomics.com/hong-kong/manufacturing-pmi","manual_role":"calendar fallback"},
    {"market":"CN","indicator":"Inflation","source_name":"NBS China CPI","url":"https://www.stats.gov.cn/english/PressRelease/","manual_role":"validation mode"},
    {"market":"CN","indicator":"Unemployment","source_name":"NBS surveyed unemployment","url":"https://www.stats.gov.cn/english/PressRelease/","manual_role":"validation mode"},
    {"market":"CN","indicator":"Rates","source_name":"PBC / CFETS Loan Prime Rate","url":"https://www.chinamoney.com.cn/english/","manual_role":"validation mode"},
    {"market":"CN","indicator":"PMI","source_name":"NBS Manufacturing PMI","url":"https://www.stats.gov.cn/english/PressRelease/","manual_role":"official source"},
    {"market":"MY","indicator":"PMI","source_name":"S&P Global Malaysia Manufacturing PMI","url":"https://www.pmi.spglobal.com/","manual_role":"official/calendar check"},
    {"market":"JP","indicator":"PMI","source_name":"au Jibun Bank Japan Manufacturing PMI","url":"https://www.pmi.spglobal.com/","manual_role":"official/calendar check"},
]

PMI_SEEDS = {
    "US": ("ISM Manufacturing PMI", 54.0),
    "SG": ("SIPMM Singapore Manufacturing PMI", 51.0),
    "HK": ("S&P Global Hong Kong SAR PMI", 50.4),
    "CN": ("NBS Manufacturing PMI", 50.0),
    "MY": ("S&P Global Malaysia Manufacturing PMI", 49.9),
    "JP": ("au Jibun Bank Japan Manufacturing PMI", 50.4),
}

DIAG = []
MANUAL = []
ROWS = []


def diag(market, indicator, source_name, status, value="", reason="", endpoint=""):
    DIAG.append({
        "market": market,
        "indicator": indicator,
        "source_name": source_name,
        "status": status,
        "value": value,
        "reason": reason,
        "endpoint": endpoint,
        "generated_at": GEN_AT,
    })


def manual(market, indicator, reason, suggested_action="Review latest official value"):
    MANUAL.append({
        "market": market,
        "indicator": indicator,
        "reason": reason,
        "suggested_action": suggested_action,
    })


def row(market, indicator, date, value, unit, source, source_type, notes=""):
    ROWS.append({
        "market": market,
        "indicator": indicator,
        "date": date,
        "value": value,
        "unit": unit,
        "source": source,
        "source_type": source_type,
        "notes": notes,
    })


def fetch_fred(series_id: str) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        body = resp.read().decode("utf-8-sig", errors="replace")
    df = pd.read_csv(io.StringIO(body), parse_dates=["DATE"])
    if series_id not in df.columns:
        raise ValueError(f"{series_id} column not found")
    df = df.rename(columns={series_id: "value"}).dropna()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna()


def latest_fred(series_id: str):
    df = fetch_fred(series_id)
    last = df.iloc[-1]
    return pd.Timestamp(last["DATE"]).strftime("%Y-%m-%d"), float(last["value"])


def add_us_rows():
    # Inflation YoY from CPIAUCSL
    try:
        df = fetch_fred("CPIAUCSL")
        latest = float(df["value"].iloc[-1]); prior = float(df["value"].iloc[-13])
        yoy = (latest / prior - 1) * 100
        dt = pd.Timestamp(df["DATE"].iloc[-1]).strftime("%Y-%m-%d")
        row("US", "Inflation", dt, round(yoy, 3), "%", "FRED CPIAUCSL YoY", "Official / External Pack", "Generated outside Streamlit")
        diag("US", "Inflation", "FRED CPIAUCSL", "accepted", round(yoy, 3), endpoint="FRED CSV")
    except Exception as e:
        diag("US", "Inflation", "FRED CPIAUCSL", "failed", reason=str(e), endpoint="FRED CSV")
        manual("US", "Inflation", "FRED CPI adapter returned no usable value")

    for indicator, series, unit, source in [
        ("Unemployment", "UNRATE", "%", "FRED UNRATE"),
        ("Claims", "ICSA", "k", "FRED ICSA"),
        ("Rates", "DGS10", "%", "FRED DGS10"),
    ]:
        try:
            dt, val = latest_fred(series)
            if indicator == "Claims":
                val = val / 1000.0
            row("US", indicator, dt, round(val, 3), unit, source, "Official / External Pack", "Generated outside Streamlit")
            diag("US", indicator, source, "accepted", round(val, 3), endpoint="FRED CSV")
        except Exception as e:
            diag("US", indicator, source, "failed", reason=str(e), endpoint="FRED CSV")
            manual("US", indicator, f"{source} adapter returned no usable value")

    # PMI: try FRED NAPM; if not available, seed with explicit review note
    try:
        dt, val = latest_fred("NAPM")
        row("US", "PMI", dt, round(val, 1), "index", "FRED NAPM / ISM Manufacturing PMI", "Official / External Pack", "Generated outside Streamlit")
        diag("US", "PMI", "FRED NAPM", "accepted", round(val, 1), endpoint="FRED CSV")
    except Exception as e:
        name, val = PMI_SEEDS["US"]
        dt = f"{PACK_MONTH}-01"
        row("US", "PMI", dt, val, "index", name, "Seed / External Pack", "Seed fallback; review before saving as active pack")
        diag("US", "PMI", "FRED NAPM", "failed", reason=str(e), endpoint="FRED CSV")
        manual("US", "PMI", "Live PMI source failed; seed fallback used", "Review PMI before relying on generated pack")


def add_seed_pmi_and_claims_na(market: str):
    if market != "US":
        row(market, "Claims", "N/A", "", "", "Not applicable", "N/A", "Claims is US-only in current model")
    if market in PMI_SEEDS:
        name, val = PMI_SEEDS[market]
        row(market, "PMI", f"{PACK_MONTH}-01", val, "index", name, "Seed / External Pack", "Seed fallback; review before saving as active pack")
        diag(market, "PMI", name, "seed", val, reason="External fetcher uses reviewed seed unless official adapter is added")
        manual(market, "PMI", "Seed fallback used", "Review PMI before relying on generated pack")


def add_non_us_placeholders(market: str):
    for indicator in ["Inflation", "Unemployment", "Rates"]:
        manual(market, indicator, f"{market} {indicator} external adapter not yet promoted", "Add official adapter or fill manual_input_template")
    add_seed_pmi_and_claims_na(market)


def build_outputs():
    add_us_rows()
    for market in ["SG", "HK", "CN", "MY", "JP"]:
        add_non_us_placeholders(market)

    macro_data = pd.DataFrame(ROWS)
    diagnostics = pd.DataFrame(DIAG)
    manual_required = pd.DataFrame(MANUAL)
    source_links = pd.DataFrame(SOURCE_LINKS)

    source_catalogue = []
    for m in ["US", "SG", "HK", "CN", "MY", "JP"]:
        for ind in ["Inflation", "Unemployment", "Claims", "Rates", "PMI"]:
            match = source_links[(source_links["market"] == m) & (source_links["indicator"] == ind)]
            src = match["source_name"].iloc[0] if not match.empty else "Awaiting official mapping"
            source_catalogue.append({
                "market": m,
                "indicator": ind,
                "primary_source": src,
                "fallback_policy": "External fetcher → official/calendar check → manual_input_template exception",
                "manual_allowed": "Exception only" if ind == "PMI" else ("N/A" if ind == "Claims" and m != "US" else "Fallback only"),
            })
    source_catalogue = pd.DataFrame(source_catalogue)

    manual_input_template = pd.DataFrame(columns=["market","indicator","date","value","unit","source","source_type","notes"])
    if not manual_required.empty:
        temp_rows = []
        for _, r in manual_required.iterrows():
            ind = r["indicator"]
            unit = "%" if ind in ["Inflation", "Unemployment", "Rates"] else "k" if ind == "Claims" else "index" if ind == "PMI" else ""
            temp_rows.append({
                "market": r["market"],
                "indicator": ind,
                "date": f"{PACK_MONTH}-01",
                "value": "",
                "unit": unit,
                "source": "Owner-reviewed official value",
                "source_type": "Owner-uploaded",
                "notes": f"{r['reason']} | {r['suggested_action']}",
            })
        manual_input_template = pd.DataFrame(temp_rows)

    readme = pd.DataFrame([
        {"field": "pack_month", "value": PACK_MONTH},
        {"field": "generated_at", "value": GEN_AT},
        {"field": "generator_version", "value": "Global20Engine v38 external fetcher draft"},
        {"field": "source_policy", "value": "External scheduled fetcher → committed macro_pack_latest files → Streamlit display/read layer"},
        {"field": "design_note", "value": "Streamlit should not be responsible for primary macro/performance fetching."},
    ])

    outputs = {
        "macro_data": macro_data,
        "diagnostics": diagnostics,
        "manual_required": manual_required,
        "manual_input_template": manual_input_template,
        "source_links": source_links,
        "source_catalogue": source_catalogue,
        "README": readme,
    }

    for name, df in outputs.items():
        df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")

    try:
        with pd.ExcelWriter(OUT / "macro_pack.xlsx", engine="openpyxl") as writer:
            for name, df in outputs.items():
                df.to_excel(writer, sheet_name=name[:31], index=False)
    except Exception as e:
        diag("PACK", "Excel", "openpyxl", "failed", reason=str(e))

    with zipfile.ZipFile(OUT / "macro_pack_csv_bundle.zip", "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in outputs:
            zf.write(OUT / f"{name}.csv", arcname=f"{name}.csv")

    print(f"Generated external macro pack in {OUT.resolve()}")


if __name__ == "__main__":
    build_outputs()
