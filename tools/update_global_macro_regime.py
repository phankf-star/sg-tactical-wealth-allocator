#!/usr/bin/env python3
"""
Global20Engine — Global Macro Regime Fetcher

Generates:
  macro_pack_latest/global_macro_regime_latest.csv
  macro_pack_latest/global_macro_regime_diagnostics.csv

Locked regime design:
  Credit     = Chicago Fed NFCI via FRED series NFCI
  Liquidity  = US Net Liquidity proxy = WALCL - WDTGAL - RRPONTSYD
  Growth     = Global PMI composite from strict macro_pack_latest/macro_data.csv PMI rows
  Volatility = VIX via FRED series VIXCLS

No FRED API key required. Uses FRED graph CSV endpoint.
"""

from __future__ import annotations

import csv
import io
import math
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

OUT_DIR = Path("macro_pack_latest")
OUT_DIR.mkdir(parents=True, exist_ok=True)

LATEST_OUT = OUT_DIR / "global_macro_regime_latest.csv"
DIAG_OUT = OUT_DIR / "global_macro_regime_diagnostics.csv"
MACRO_DATA_FILE = OUT_DIR / "macro_data.csv"
PMI_AUDIT_OUT = OUT_DIR / "pmi_source_audit.csv"

REQUIRED_PMI_MARKETS = ("US", "SG", "HK", "MY", "JP")
PMI_REQUIRED_COLUMNS = ("market", "indicator", "date", "value", "source", "source_type", "notes")
PMI_FORBIDDEN_SOURCE_TERMS = ("fallback", "default", "seed", "manual")

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"



def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_fred_series(series_id: str) -> pd.DataFrame:
    """Fetch FRED series by graph CSV endpoint."""
    url = FRED_CSV.format(series_id=series_id)
    with urllib.request.urlopen(url, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    df = pd.read_csv(io.StringIO(raw))
    if df.empty or "observation_date" not in df.columns or series_id not in df.columns:
        raise ValueError(f"Unexpected FRED CSV format for {series_id}")
    df = df.rename(columns={"observation_date": "date", series_id: "value"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"].replace(".", pd.NA), errors="coerce")
    df = df.dropna(subset=["date", "value"]).sort_values("date")
    if df.empty:
        raise ValueError(f"No usable observations for {series_id}")
    return df


def latest_value(df: pd.DataFrame) -> tuple[float, str]:
    row = df.dropna(subset=["value"]).iloc[-1]
    return float(row["value"]), pd.Timestamp(row["date"]).strftime("%Y-%m-%d")


def classify_vix(v: float) -> str:
    if v < 15:
        return "Calm"
    if v < 20:
        return "Normal"
    if v < 30:
        return "Elevated"
    return "Stress"


def classify_nfci(v: float) -> str:
    if v < -0.50:
        return "Easy"
    if v < 0.00:
        return "Neutral"
    if v <= 0.50:
        return "Moderately Tight"
    return "Stress"


def classify_pmi(v: float) -> str:
    if v > 53:
        return "Strong"
    if v >= 50:
        return "Moderate"
    if v >= 48:
        return "Slowing"
    return "Contraction"


def trend_from_series(values: pd.Series, periods: int = 4, flat_band: float = 0.02) -> str:
    vals = values.dropna()
    if len(vals) <= periods:
        return "Insufficient history"
    change = float(vals.iloc[-1] - vals.iloc[-1 - periods])
    if change > flat_band:
        return "Rising"
    if change < -flat_band:
        return "Falling"
    return "Stable"


def classify_liquidity(net_df: pd.DataFrame) -> tuple[str, str, float, float, str]:
    """Return status, trend label, latest net liquidity, 4w change, latest date."""
    net_df = net_df.dropna(subset=["net_liquidity"]).sort_values("date")
    latest = float(net_df["net_liquidity"].iloc[-1])
    latest_date = pd.Timestamp(net_df["date"].iloc[-1]).strftime("%Y-%m-%d")
    if len(net_df) >= 14:
        chg4 = latest - float(net_df["net_liquidity"].iloc[-5])
        chg13 = latest - float(net_df["net_liquidity"].iloc[-14])
    elif len(net_df) >= 5:
        chg4 = latest - float(net_df["net_liquidity"].iloc[-5])
        chg13 = 0.0
    else:
        chg4 = 0.0
        chg13 = 0.0

    # Units are millions USD. Thresholds below are intentionally broad to avoid overfitting noise.
    strong = 150_000.0  # USD150bn
    mild = 25_000.0     # USD25bn

    if chg4 > strong and chg13 > strong:
        return "Abundant", "Rising strongly", latest, chg4, latest_date
    if chg4 > mild or chg13 > mild:
        return "Supportive", "Rising", latest, chg4, latest_date
    if chg4 < -strong and chg13 < -strong:
        return "Restrictive", "Falling rapidly", latest, chg4, latest_date
    if chg4 < -mild or chg13 < -mild:
        return "Tightening", "Falling", latest, chg4, latest_date
    return "Neutral", "Stable", latest, chg4, latest_date


def _normalise_text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _pmi_rejection_reason(row: pd.Series) -> str:
    joined = " ".join(
        _normalise_text(row.get(col, ""))
        for col in ("source", "source_type", "notes")
    ).lower()
    hits = [term for term in PMI_FORBIDDEN_SOURCE_TERMS if term in joined]
    return "Forbidden PMI source wording: " + ", ".join(hits) if hits else ""


def _load_macro_data_pmi_rows() -> pd.DataFrame:
    """Load production PMI rows from macro_pack_latest/macro_data.csv only."""
    if not MACRO_DATA_FILE.exists():
        raise FileNotFoundError(f"Missing macro data file: {MACRO_DATA_FILE}")

    df = pd.read_csv(MACRO_DATA_FILE)
    missing_cols = [col for col in PMI_REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError("macro_data.csv missing required PMI columns: " + ", ".join(missing_cols))

    pmi = df[df["indicator"].astype(str).str.upper().str.strip().eq("PMI")].copy()
    if pmi.empty:
        raise ValueError("No PMI rows found in macro_data.csv")

    pmi["market"] = pmi["market"].astype(str).str.upper().str.strip()
    pmi["date"] = pd.to_datetime(pmi["date"], errors="coerce")
    pmi["value"] = pd.to_numeric(pmi["value"], errors="coerce")
    pmi = pmi.dropna(subset=["market", "date", "value"])
    pmi = pmi[(pmi["value"] >= 35) & (pmi["value"] <= 70)]
    if pmi.empty:
        raise ValueError("No usable PMI rows found in macro_data.csv")

    # Keep the latest usable PMI row per market before strict source checks.
    return pmi.sort_values(["market", "date"]).groupby("market", as_index=False).tail(1)


def build_growth_pmi_strict() -> tuple[float, str, str, str, str, pd.DataFrame]:
    """Build production Global PMI from macro_data.csv with no default or fallback path."""
    pmi = _load_macro_data_pmi_rows()

    audit_rows = []
    safe_rows = []
    for _, row in pmi.iterrows():
        market = _normalise_text(row.get("market", "")).upper()
        reason = _pmi_rejection_reason(row)
        if market not in REQUIRED_PMI_MARKETS:
            reason = "Non-required PMI market"
        coverage = "OK" if not reason else "REJECTED"

        audit_rows.append({
            "market": market,
            "indicator": _normalise_text(row.get("indicator", "PMI")),
            "date": pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
            "value": float(row["value"]),
            "source": _normalise_text(row.get("source", "")),
            "source_type": _normalise_text(row.get("source_type", "")),
            "coverage": coverage,
            "reason": reason,
        })
        if coverage == "OK":
            safe_rows.append(row)

    audit = pd.DataFrame(audit_rows)
    PMI_AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(PMI_AUDIT_OUT, index=False)

    safe_markets = {str(row["market"]).upper().strip() for row in safe_rows}
    missing = [m for m in REQUIRED_PMI_MARKETS if m not in safe_markets]
    if missing:
        raise ValueError("Missing production-safe PMI rows: " + ", ".join(missing))

    safe = pd.DataFrame(safe_rows)
    pmi_value = float(safe["value"].mean())
    latest_date = pd.Timestamp(safe["date"].max()).strftime("%Y-%m-%d")
    remarks = (
        f"Strict composite from {len(safe)} production-safe PMI rows in "
        f"{MACRO_DATA_FILE.as_posix()}; required markets: "
        + ", ".join(REQUIRED_PMI_MARKETS)
    )
    return (pmi_value, classify_pmi(pmi_value), "Monthly macro pack PMI composite", latest_date, remarks, audit)


def build_growth_pmi() -> tuple[float, str, str, str, str]:
    """Compatibility wrapper for the production Growth row."""
    pmi, status, source, latest_date, remarks, _audit = build_growth_pmi_strict()
    return pmi, status, source, latest_date, remarks


def main() -> int:
    diagnostics = []
    latest_rows = []

    def diag(adapter, status, series, last_value="", last_date="", error="", source_url=""):
        diagnostics.append({
            "adapter": adapter,
            "status": status,
            "series": series,
            "last_value": last_value,
            "last_date": last_date,
            "error": error,
            "source_url": source_url,
            "run_utc": _now_iso(),
        })

    # Credit: NFCI
    try:
        nfci_df = fetch_fred_series("NFCI")
        nfci, nfci_date = latest_value(nfci_df)
        latest_rows.append({
            "indicator": "Credit",
            "value": f"NFCI {nfci:+.3f}",
            "numeric_value": nfci,
            "status": classify_nfci(nfci),
            "trend": trend_from_series(nfci_df["value"], periods=4, flat_band=0.05),
            "source": "FRED / Chicago Fed NFCI",
            "source_series": "NFCI",
            "last_updated": nfci_date,
            "coverage": "OK",
            "remarks": "Positive NFCI indicates tighter-than-average financial conditions; negative indicates looser-than-average.",
        })
        diag("credit_nfci", "OK", "NFCI", f"{nfci:+.3f}", nfci_date, source_url=FRED_CSV.format(series_id="NFCI"))
    except Exception as e:
        latest_rows.append({"indicator": "Credit", "value": "N/A", "numeric_value": "", "status": "Unavailable", "trend": "Unavailable", "source": "FRED / Chicago Fed NFCI", "source_series": "NFCI", "last_updated": "", "coverage": "ERROR", "remarks": str(e)})
        diag("credit_nfci", "ERROR", "NFCI", error=str(e), source_url=FRED_CSV.format(series_id="NFCI"))

    # Liquidity: WALCL - WDTGAL - RRPONTSYD
    try:
        walcl = fetch_fred_series("WALCL").rename(columns={"value": "WALCL"})
        wdtgal = fetch_fred_series("WDTGAL").rename(columns={"value": "WDTGAL"})
        rrp = fetch_fred_series("RRPONTSYD").rename(columns={"value": "RRPONTSYD"})
        net = walcl.merge(wdtgal, on="date", how="inner").merge(rrp, on="date", how="inner")
        if net.empty:
            # RRP is daily; try nearest weekly alignment by forward fill on a daily date index.
            all_dates = pd.DataFrame({"date": pd.date_range(min(walcl.date.min(), wdtgal.date.min(), rrp.date.min()), max(walcl.date.max(), wdtgal.date.max(), rrp.date.max()), freq="D")})
            net = all_dates.merge(walcl, on="date", how="left").merge(wdtgal, on="date", how="left").merge(rrp, on="date", how="left")
            net[["WALCL", "WDTGAL", "RRPONTSYD"]] = net[["WALCL", "WDTGAL", "RRPONTSYD"]].ffill()
            net = net.dropna(subset=["WALCL", "WDTGAL", "RRPONTSYD"])
        net["net_liquidity"] = net["WALCL"] - net["WDTGAL"] - net["RRPONTSYD"]
        status, trend, latest_net, chg4, net_date = classify_liquidity(net)
        latest_rows.append({
            "indicator": "Liquidity",
            "value": f"US Net Liquidity {latest_net/1_000_000:.2f}T",
            "numeric_value": latest_net,
            "status": status,
            "trend": trend,
            "source": "FRED",
            "source_series": "WALCL-WDTGAL-RRPONTSYD",
            "last_updated": net_date,
            "coverage": "OK",
            "remarks": f"US net liquidity proxy in USD millions. 4W change: {chg4/1_000:.1f}bn. Formula: Fed assets minus TGA minus overnight reverse repo.",
        })
        diag("liquidity_net", "OK", "WALCL-WDTGAL-RRPONTSYD", f"{latest_net/1_000_000:.2f}T", net_date, source_url="FRED graph CSV endpoints")
    except Exception as e:
        latest_rows.append({"indicator": "Liquidity", "value": "N/A", "numeric_value": "", "status": "Unavailable", "trend": "Unavailable", "source": "FRED", "source_series": "WALCL-WDTGAL-RRPONTSYD", "last_updated": "", "coverage": "ERROR", "remarks": str(e)})
        diag("liquidity_net", "ERROR", "WALCL-WDTGAL-RRPONTSYD", error=str(e), source_url="FRED graph CSV endpoints")

    # Growth: PMI composite
    try:
        pmi, pmi_status, pmi_source, pmi_date, pmi_remarks = build_growth_pmi()
        latest_rows.append({
            "indicator": "Growth",
            "value": f"Global PMI {pmi:.1f}",
            "numeric_value": round(pmi, 3),
            "status": pmi_status,
            "trend": "See PMI history",
            "source": pmi_source,
            "source_series": "PMI composite excluding N/A",
            "last_updated": pmi_date,
            "coverage": "OK",
            "remarks": pmi_remarks,
        })
        diag("growth_pmi", "OK", "PMI composite", f"{pmi:.1f}", pmi_date, source_url=str(MACRO_DATA_FILE))
    except Exception as e:
        latest_rows.append({"indicator": "Growth", "value": "N/A", "numeric_value": "", "status": "Unavailable", "trend": "Unavailable", "source": "PMI composite", "source_series": "PMI", "last_updated": "", "coverage": "ERROR", "remarks": str(e)})
        diag("growth_pmi", "ERROR", "PMI composite", error=str(e), source_url=str(MACRO_DATA_FILE))

    # Volatility: VIXCLS
    try:
        vix_df = fetch_fred_series("VIXCLS")
        vix, vix_date = latest_value(vix_df)
        latest_rows.append({
            "indicator": "Volatility",
            "value": f"VIX {vix:.1f}",
            "numeric_value": vix,
            "status": classify_vix(vix),
            "trend": trend_from_series(vix_df["value"], periods=20, flat_band=1.0),
            "source": "FRED / CBOE VIX",
            "source_series": "VIXCLS",
            "last_updated": vix_date,
            "coverage": "OK",
            "remarks": "VIX used as broad US equity volatility and market stress proxy.",
        })
        diag("volatility_vix", "OK", "VIXCLS", f"{vix:.1f}", vix_date, source_url=FRED_CSV.format(series_id="VIXCLS"))
    except Exception as e:
        latest_rows.append({"indicator": "Volatility", "value": "N/A", "numeric_value": "", "status": "Unavailable", "trend": "Unavailable", "source": "FRED / CBOE VIX", "source_series": "VIXCLS", "last_updated": "", "coverage": "ERROR", "remarks": str(e)})
        diag("volatility_vix", "ERROR", "VIXCLS", error=str(e), source_url=FRED_CSV.format(series_id="VIXCLS"))

    pd.DataFrame(latest_rows).to_csv(LATEST_OUT, index=False)
    pd.DataFrame(diagnostics).to_csv(DIAG_OUT, index=False)

    print(f"Wrote {LATEST_OUT}")
    print(f"Wrote {DIAG_OUT}")
    print(pd.DataFrame(latest_rows).to_string(index=False))

    # Non-zero exit only if all adapters failed. Partial data is acceptable but visible in diagnostics.
    ok_count = sum(1 for d in diagnostics if d["status"] == "OK")
    return 0 if ok_count > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
