#!/usr/bin/env python3
"""
Global20Engine — Global Macro Regime Fetcher

Generates:
  macro_pack_latest/global_macro_regime_latest.csv
  macro_pack_latest/global_macro_regime_diagnostics.csv

Locked regime design:
  Credit     = Chicago Fed NFCI via FRED series NFCI
  Liquidity  = US Net Liquidity proxy = WALCL - WDTGAL - RRPONTSYD
  Growth     = Global PMI composite from available PMI inputs / fallback app defaults
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

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

# Existing Global20Engine PMI defaults, used only when no local macro-pack PMI file is found.
# These match the current app's PMI proxy design and keep the executive page auditable.
DEFAULT_PMI_VALUES = {
    "US ISM Manufacturing PMI": {"value": 54.0, "date": "2026-05", "source": "App default / FRED ISM proxy"},
    "China Caixin Manufacturing PMI": {"value": 50.0, "date": "2026-06", "source": "App default / NBS-Caixin proxy"},
    "Singapore S&P Global PMI": {"value": 51.0, "date": "2026-06", "source": "App default / SIPMM-S&P proxy"},
    "Malaysia Manufacturing PMI": {"value": 49.9, "date": "2026-06", "source": "App default / S&P Global proxy"},
    "Japan Jibun Bank Manufacturing PMI": {"value": 50.4, "date": "2026-06", "source": "App default / Jibun-S&P proxy"},
}


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


def load_pmi_from_local_files() -> list[dict]:
    """Try to discover PMI rows from macro_pack_latest CSV files.

    This is intentionally flexible because prior macro pack schemas may differ.
    Expected-ish columns may include: indicator, value, date/month, source.
    """
    rows = []
    for p in OUT_DIR.glob("*.csv"):
        if p.name in {LATEST_OUT.name, DIAG_OUT.name}:
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        lower_cols = {c.lower(): c for c in df.columns}
        # Find rows where any text column mentions PMI.
        text_cols = [c for c in df.columns if df[c].dtype == object]
        if not text_cols:
            continue
        mask = pd.Series(False, index=df.index)
        for c in text_cols:
            mask = mask | df[c].astype(str).str.contains("PMI", case=False, na=False)
        sub = df[mask].copy()
        if sub.empty:
            continue
        value_col = None
        for candidate in ["value", "latest", "actual", "pmi", "reading"]:
            if candidate in lower_cols:
                value_col = lower_cols[candidate]
                break
        if value_col is None:
            # fallback: first numeric column
            num_cols = [c for c in sub.columns if pd.api.types.is_numeric_dtype(sub[c])]
            if num_cols:
                value_col = num_cols[0]
        if value_col is None:
            continue
        for _, r in sub.iterrows():
            val = pd.to_numeric(r.get(value_col), errors="coerce")
            if pd.isna(val) or float(val) <= 0:
                continue
            label = None
            for c in text_cols:
                txt = str(r.get(c, ""))
                if "PMI" in txt.upper():
                    label = txt[:80]
                    break
            date_val = None
            for candidate in ["date", "month", "period", "as_of"]:
                if candidate in lower_cols:
                    date_val = str(r.get(lower_cols[candidate], ""))
                    break
            source_val = None
            for candidate in ["source", "provider"]:
                if candidate in lower_cols:
                    source_val = str(r.get(lower_cols[candidate], ""))
                    break
            rows.append({"label": label or "PMI", "value": float(val), "date": date_val or "", "source": source_val or f"local macro pack: {p.name}"})
    return rows


def build_growth_pmi() -> tuple[float, str, str, str, str]:
    local = load_pmi_from_local_files()
    if local:
        vals = [r["value"] for r in local if 35 <= r["value"] <= 70]
        if vals:
            pmi = sum(vals) / len(vals)
            dates = sorted({r.get("date", "") for r in local if r.get("date")})
            latest_date = dates[-1] if dates else "local macro pack"
            return pmi, classify_pmi(pmi), "Local macro pack composite", latest_date, f"Composite from {len(vals)} PMI rows discovered in macro_pack_latest"

    vals = [v["value"] for v in DEFAULT_PMI_VALUES.values()]
    pmi = sum(vals) / len(vals)
    latest_date = sorted({v["date"] for v in DEFAULT_PMI_VALUES.values()})[-1]
    return pmi, classify_pmi(pmi), "App PMI defaults composite", latest_date, "Fallback composite from existing app PMI defaults; replace with official PMI fetch when licensed/public source is settled"


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
            "coverage": "OK" if "Fallback" not in pmi_remarks else "FALLBACK",
            "remarks": pmi_remarks,
        })
        diag("growth_pmi", "OK", "PMI composite", f"{pmi:.1f}", pmi_date, source_url="local macro_pack_latest or app defaults")
    except Exception as e:
        latest_rows.append({"indicator": "Growth", "value": "N/A", "numeric_value": "", "status": "Unavailable", "trend": "Unavailable", "source": "PMI composite", "source_series": "PMI", "last_updated": "", "coverage": "ERROR", "remarks": str(e)})
        diag("growth_pmi", "ERROR", "PMI composite", error=str(e), source_url="local macro_pack_latest or app defaults")

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
