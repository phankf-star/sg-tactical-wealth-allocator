
# ─────────────────────────────────────────────────────────────────────────────
# Global20Engine Macro Pack Fetcher
# v38aa — MY inflation OpenDOSM CSV-primary macro fetcher
#
# Output folder:
#   macro_pack_latest/
#
# Files generated:
#   macro_data.csv
#   diagnostics.csv
#   manual_required.csv
#   source_catalogue.csv
#   README.csv
#   macro_pack.xlsx
#   macro_pack_csv_bundle.zip
#
# Policy:
#   - Monthly macro pack is primary for monthly indicators.
#   - MY Inflation uses OpenDOSM official CSV:
#       storage.dosm.gov.my/cpi/cpi_2d_inflation.csv
#     Filter: division == overall
#     Value: inflation_yoy
#   - SG Rates / SORA intentionally excluded from macro pack active fetch path.
#     SG Rates is live redistributor-only in main app.
#   - JP Rates intentionally excluded from macro pack active fetch path.
#     JP Rates is live BOJ FM01 STRDCLUCON CSV in main app.
# ─────────────────────────────────────────────────────────────────────────────

import csv
import io
import json
import math
import os
import re
import zipfile
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Output config
# ─────────────────────────────────────────────────────────────────────────────

OUT_DIR = Path("macro_pack_latest")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MACRO_ROWS = []
DIAGNOSTIC_ROWS = []
MANUAL_ROWS = []
SOURCE_ROWS = []


# ─────────────────────────────────────────────────────────────────────────────
# Generic helpers
# ─────────────────────────────────────────────────────────────────────────────

def now_utc_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def request_text(url, accept="application/json,text/csv,text/plain,*/*", timeout=30):
    headers = {
        "User-Agent": "Global20Engine-MacroFetcher/1.0",
        "Accept": accept,
        "Accept-Encoding": "identity",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8-sig", errors="replace")


def safe_float(x):
    try:
        if x is None:
            return None
        s = str(x).strip()
        if not s or s.lower() in {"na", "nan", "none", "null", "-", ""}:
            return None
        s = s.replace(",", "").replace("%", "")
        v = float(s)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def row(market, indicator, date, value, unit, source, source_type, notes="", **kwargs):
    """
    Canonical macro_data row.
    Keep remarks in notes; dashboard should display notes as tooltip where possible.
    """
    MACRO_ROWS.append({
        "market": market,
        "indicator": indicator,
        "date": date,
        "value": value,
        "unit": unit,
        "source": source,
        "source_type": source_type,
        "notes": notes or kwargs.get("reason", ""),
    })


def diag(market, indicator, source, status, value=None, reason="", endpoint=""):
    DIAGNOSTIC_ROWS.append({
        "run_utc": now_utc_iso(),
        "market": market,
        "indicator": indicator,
        "source": source,
        "status": status,
        "value": value,
        "reason": reason,
        "endpoint": endpoint,
    })


def manual(market, indicator, reason):
    MANUAL_ROWS.append({
        "run_utc": now_utc_iso(),
        "market": market,
        "indicator": indicator,
        "reason": reason,
    })


def source_catalogue(market, indicator, source, source_type, endpoint="", notes=""):
    SOURCE_ROWS.append({
        "market": market,
        "indicator": indicator,
        "source": source,
        "source_type": source_type,
        "endpoint": endpoint,
        "notes": notes,
    })


def write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in columns})


# ─────────────────────────────────────────────────────────────────────────────
# FRED keyless helpers for US macro rows
# Uses fredgraph CSV endpoints; no API key required.
# ─────────────────────────────────────────────────────────────────────────────

def fetch_fred_graph_series(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={urllib.parse.quote(series_id)}"
    txt = request_text(url, accept="text/csv,text/plain,*/*")
    df = pd.read_csv(io.StringIO(txt))
    if df.empty:
        raise ValueError(f"FRED {series_id} returned empty CSV")

    # FRED graph CSV usually columns: observation_date, SERIESID
    df.columns = [str(c).strip() for c in df.columns]
    date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
    value_col = series_id if series_id in df.columns else df.columns[-1]

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=[date_col, value_col]).sort_values(date_col)

    if df.empty:
        raise ValueError(f"FRED {series_id} has no usable rows")

    return df[[date_col, value_col]].rename(columns={date_col: "date", value_col: "value"}), url


def add_us_inflation():
    source = "FRED CPIAUCSL YoY"
    try:
        df, endpoint = fetch_fred_graph_series("CPIAUCSL")
        latest = df.iloc[-1]
        latest_date = latest["date"]
        latest_value = float(latest["value"])

        # Find CPI approximately 12 months earlier.
        prior_target = latest_date - pd.DateOffset(months=12)
        prior_df = df[df["date"] <= prior_target].copy()
        if prior_df.empty:
            raise ValueError("Could not find CPI value about 12 months earlier")

        prior_value = float(prior_df.iloc[-1]["value"])
        yoy = round(((latest_value / prior_value) - 1.0) * 100.0, 3)

        row(
            "US",
            "Inflation",
            latest_date.strftime("%Y-%m-%d"),
            yoy,
            "%",
            source,
            "Official / API",
            "Computed from latest CPI index versus CPI about 12 months earlier.",
        )
        diag("US", "Inflation", source, "success", value=yoy, reason="Computed CPI YoY from FRED CPIAUCSL", endpoint=endpoint)
    except Exception as e:
        diag("US", "Inflation", source, "failed", reason=str(e))
        manual("US", "Inflation", f"FRED CPIAUCSL YoY fetch failed: {e}")


def add_us_unemployment():
    source = "FRED UNRATE"
    try:
        df, endpoint = fetch_fred_graph_series("UNRATE")
        latest = df.iloc[-1]
        value = round(float(latest["value"]), 3)
        row("US", "Unemployment", latest["date"].strftime("%Y-%m-%d"), value, "%", source, "Official / API", "US unemployment rate.")
        diag("US", "Unemployment", source, "success", value=value, reason="Fetched FRED UNRATE", endpoint=endpoint)
    except Exception as e:
        diag("US", "Unemployment", source, "failed", reason=str(e))
        manual("US", "Unemployment", f"FRED UNRATE fetch failed: {e}")


def add_us_claims():
    source = "FRED ICSA"
    try:
        df, endpoint = fetch_fred_graph_series("ICSA")
        latest = df.iloc[-1]
        value_k = round(float(latest["value"]) / 1000.0, 3)
        row("US", "Claims", latest["date"].strftime("%Y-%m-%d"), value_k, "k", source, "Official / API", "US initial claims; converted to thousands.")
        diag("US", "Claims", source, "success", value=value_k, reason="Fetched FRED ICSA and converted to thousands", endpoint=endpoint)
    except Exception as e:
        diag("US", "Claims", source, "failed", reason=str(e))
        manual("US", "Claims", f"FRED ICSA fetch failed: {e}")


def add_us_rates():
    source = "FRED DGS10"
    try:
        df, endpoint = fetch_fred_graph_series("DGS10")
        latest = df.iloc[-1]
        value = round(float(latest["value"]), 3)
        row("US", "Rates", latest["date"].strftime("%Y-%m-%d"), value, "%", source, "Official / API", "US 10-year Treasury constant maturity rate.")
        diag("US", "Rates", source, "success", value=value, reason="Fetched FRED DGS10", endpoint=endpoint)
    except Exception as e:
        diag("US", "Rates", source, "failed", reason=str(e))
        manual("US", "Rates", f"FRED DGS10 fetch failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Singapore monthly macro rows
# Note: SG Rates is intentionally not fetched here.
# ─────────────────────────────────────────────────────────────────────────────

def add_singapore_reviewed_monthly_rows():
    """
    These rows are retained as reviewed monthly rows / seed rows until full
    official monthly integration is added. SG SORA rates are handled live in
    main app, not macro pack.
    """
    row(
        "SG",
        "Inflation",
        "2026-05-01",
        1.8,
        "%",
        "SingStat CPI",
        "Official / Reviewed",
        "Reviewed static row pending full SingStat macro-pack integration.",
    )
    diag("SG", "Inflation", "SingStat CPI", "reviewed", value=1.8, reason="Reviewed static row")

    row(
        "SG",
        "Unemployment",
        "2026-03-01",
        2.0,
        "%",
        "MOM / SingStat unemployment",
        "Official / Reviewed",
        "Singapore overall unemployment rate for Mar-26 / 1Q 2026; reviewed row.",
    )
    diag("SG", "Unemployment", "MOM / SingStat unemployment", "reviewed", value=2.0, reason="Reviewed static row")


# ─────────────────────────────────────────────────────────────────────────────
# Hong Kong inflation
# Keep tolerant. If current C&SD JSON changes, manual row captures failure.
# ─────────────────────────────────────────────────────────────────────────────

def add_hk_inflation_reviewed_or_live():
    """
    This keeps the currently validated HK inflation output path simple.
    If you already have a working C&SD JSON function elsewhere, replace this
    function with that tested implementation.
    """
    try:
        row(
            "HK",
            "Inflation",
            "2026-05-01",
            2.0,
            "%",
            "C&SD Table 510-60001 Composite CPI YoY",
            "Official / Reviewed",
            "Reviewed row. Replace with live C&SD Table 510-60001 fetch when confirmed in macro fetcher runtime.",
        )
        diag("HK", "Inflation", "C&SD Table 510-60001 Composite CPI YoY", "reviewed", value=2.0, reason="Reviewed row")
    except Exception as e:
        diag("HK", "Inflation", "C&SD Table 510-60001 Composite CPI YoY", "failed", reason=str(e))
        manual("HK", "Inflation", f"C&SD Table 510-60001 fetch failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Malaysia inflation — FIXED CSV-primary implementation
# ─────────────────────────────────────────────────────────────────────────────

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
            "Fetched Malaysia headline CPI inflation YoY from OpenDOSM official CSV; filtered division=overall.",
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


# ─────────────────────────────────────────────────────────────────────────────
# Malaysia unemployment — OpenDOSM live if available, tolerant fallback
# ─────────────────────────────────────────────────────────────────────────────

def add_opendosm_malaysia_unemployment():
    """
    Tolerant unemployment helper.
    Uses OpenDOSM API if available. If unavailable, writes manual-required row.
    """
    source = "OpenDOSM unemployment"
    url = "https://api.data.gov.my/opendosm?id=lfs_month&limit=50000"

    try:
        txt = request_text(url, accept="application/json,text/plain,*/*")
        payload = json.loads(txt)

        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = payload.get("data") or payload.get("records") or payload.get("result", {}).get("records") or []
        else:
            records = []

        if not records:
            raise ValueError("OpenDOSM unemployment API returned no records")

        df = pd.DataFrame(records)
        df.columns = [str(c).strip().lower() for c in df.columns]

        date_col = "date" if "date" in df.columns else None
        value_col = None

        for c in df.columns:
            lc = c.lower()
            if "unemployment" in lc and ("rate" in lc or "percent" in lc or "pct" in lc):
                value_col = c
                break

        if date_col is None or value_col is None:
            raise ValueError(f"Could not identify unemployment date/value columns; columns={list(df.columns)[:30]}")

        df["date"] = pd.to_datetime(df[date_col], errors="coerce")
        df["_value"] = pd.to_numeric(df[value_col], errors="coerce")
        df = df.dropna(subset=["date", "_value"]).sort_values("date")
        df = df[(df["_value"] >= 0) & (df["_value"] <= 20)]

        if df.empty:
            raise ValueError("No usable unemployment rows after filtering")

        latest = df.iloc[-1]
        value = round(float(latest["_value"]), 3)
        date_txt = latest["date"].strftime("%Y-%m-%d")

        row("MY", "Unemployment", date_txt, value, "%", source, "Official / API", "Malaysia unemployment rate from OpenDOSM.")
        diag("MY", "Unemployment", source, "success", value=value, reason="Fetched Malaysia unemployment from OpenDOSM", endpoint=url)

    except Exception as e:
        diag("MY", "Unemployment", source, "failed", reason=str(e), endpoint=url)
        manual("MY", "Unemployment", f"OpenDOSM unemployment fetch failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Malaysia rates — BNM OPR
# If this is already handled in main live app, this macro row can be omitted.
# ─────────────────────────────────────────────────────────────────────────────

def add_malaysia_rates_manual_or_reviewed():
    """
    Keep MY rates out of monthly macro pack if your policy is live API only.
    This function deliberately does not add MY Rates to macro_data.
    """
    diag(
        "MY",
        "Rates",
        "BNM OPR",
        "skipped",
        reason="Policy: Malaysia rates handled by live adapter, not monthly macro pack.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# PMI seed rows
# ─────────────────────────────────────────────────────────────────────────────

def add_pmi_seed_rows():
    seeds = [
        ("US", "PMI", "2026-06-01", 54.0, "index", "ISM Manufacturing PMI / seed fallback"),
        ("SG", "PMI", "2026-06-01", 51.0, "index", "SIPMM Singapore Manufacturing PMI"),
        ("HK", "PMI", "2026-06-01", 50.4, "index", "S&P Global Hong Kong SAR PMI"),
        ("CN", "PMI", "2026-06-01", 50.0, "index", "NBS Manufacturing PMI"),
        ("MY", "PMI", "2026-06-01", 49.9, "index", "S&P Global Malaysia Manufacturing PMI"),
        ("JP", "PMI", "2026-06-01", 50.4, "index", "au Jibun Bank Japan Manufacturing PMI"),
    ]

    for market, indicator, date, value, unit, source in seeds:
        row(
            market,
            indicator,
            date,
            value,
            unit,
            source,
            "Seed",
            "Seed fallback; review before active use.",
        )
        diag(market, indicator, source, "seed", value=value, reason="Seed fallback row")


# ─────────────────────────────────────────────────────────────────────────────
# Source catalogue
# ─────────────────────────────────────────────────────────────────────────────

def build_source_catalogue():
    source_catalogue("US", "Inflation", "FRED CPIAUCSL YoY", "Official / API", "https://fred.stlouisfed.org/series/CPIAUCSL", "Computed YoY from CPI index")
    source_catalogue("US", "Unemployment", "FRED UNRATE", "Official / API", "https://fred.stlouisfed.org/series/UNRATE", "US unemployment rate")
    source_catalogue("US", "Claims", "FRED ICSA", "Official / API", "https://fred.stlouisfed.org/series/ICSA", "US initial claims")
    source_catalogue("US", "Rates", "FRED DGS10", "Official / API", "https://fred.stlouisfed.org/series/DGS10", "US 10-year Treasury")
    source_catalogue("SG", "Inflation", "SingStat CPI", "Official / Reviewed", "", "Reviewed static row pending full integration")
    source_catalogue("SG", "Unemployment", "MOM / SingStat unemployment", "Official / Reviewed", "", "Reviewed static row")
    source_catalogue("SG", "Rates", "SG SORA live redistributor only", "Live app only", "", "Excluded from macro pack")
    source_catalogue("HK", "Inflation", "C&SD Table 510-60001 Composite CPI YoY", "Official / Reviewed", "", "Reviewed/live integration dependent")
    source_catalogue("MY", "Inflation", "OpenDOSM storage CSV cpi_2d_inflation", "Official CSV", "https://storage.dosm.gov.my/cpi/cpi_2d_inflation.csv", "Filter division=overall; use inflation_yoy")
    source_catalogue("MY", "Unemployment", "OpenDOSM unemployment", "Official / API", "https://api.data.gov.my/opendosm", "Tolerant helper; manual if unavailable")
    source_catalogue("MY", "Rates", "BNM OPR", "Live app only", "", "Excluded from macro pack if live policy applies")
    source_catalogue("JP", "Rates", "BOJ FM01 STRDCLUCON CSV", "Live app only", "", "Excluded from macro pack")
    source_catalogue("PMI", "PMI", "Seed rows", "Seed", "", "Review before active use")


# ─────────────────────────────────────────────────────────────────────────────
# Build macro pack
# ─────────────────────────────────────────────────────────────────────────────

def build_macro_pack():
    # Source catalogue first
    build_source_catalogue()

    # US
    add_us_inflation()
    add_us_unemployment()
    add_us_claims()
    add_us_rates()

    # Singapore monthly rows; SG rates excluded
    add_singapore_reviewed_monthly_rows()

    # Hong Kong
    add_hk_inflation_reviewed_or_live()

    # Malaysia
    add_opendosm_malaysia_cpi()              # IMPORTANT: this is the fixed MY Inflation row
    add_opendosm_malaysia_unemployment()
    add_malaysia_rates_manual_or_reviewed()

    # PMI seeds
    add_pmi_seed_rows()

    # Write CSV outputs
    macro_cols = ["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"]
    diag_cols = ["run_utc", "market", "indicator", "source", "status", "value", "reason", "endpoint"]
    manual_cols = ["run_utc", "market", "indicator", "reason"]
    source_cols = ["market", "indicator", "source", "source_type", "endpoint", "notes"]

    write_csv(OUT_DIR / "macro_data.csv", MACRO_ROWS, macro_cols)
    write_csv(OUT_DIR / "diagnostics.csv", DIAGNOSTIC_ROWS, diag_cols)
    write_csv(OUT_DIR / "manual_required.csv", MANUAL_ROWS, manual_cols)
    write_csv(OUT_DIR / "source_catalogue.csv", SOURCE_ROWS, source_cols)

    readme_rows = [{
        "generated_utc": now_utc_iso(),
        "notes": (
            "Global20Engine macro pack generated. "
            "MY Inflation uses OpenDOSM official CSV cpi_2d_inflation, division=overall, inflation_yoy. "
            "SG and JP rates are excluded from macro pack active monthly fetch path and handled by live adapters in main app."
        ),
    }]
    write_csv(OUT_DIR / "README.csv", readme_rows, ["generated_utc", "notes"])

    # Excel output
    try:
        with pd.ExcelWriter(OUT_DIR / "macro_pack.xlsx", engine="openpyxl") as writer:
            pd.DataFrame(MACRO_ROWS).to_excel(writer, sheet_name="macro_data", index=False)
            pd.DataFrame(DIAGNOSTIC_ROWS).to_excel(writer, sheet_name="diagnostics", index=False)
            pd.DataFrame(MANUAL_ROWS).to_excel(writer, sheet_name="manual_required", index=False)
            pd.DataFrame(SOURCE_ROWS).to_excel(writer, sheet_name="source_catalogue", index=False)
            pd.DataFrame(readme_rows).to_excel(writer, sheet_name="README", index=False)
    except Exception as e:
        diag("PACK", "Excel", "openpyxl", "failed", reason=str(e))
        write_csv(OUT_DIR / "diagnostics.csv", DIAGNOSTIC_ROWS, diag_cols)

    # ZIP bundle
    zip_path = OUT_DIR / "macro_pack_csv_bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in [
            "macro_data.csv",
            "diagnostics.csv",
            "manual_required.csv",
            "source_catalogue.csv",
            "README.csv",
        ]:
            p = OUT_DIR / name
            if p.exists():
                z.write(p, arcname=name)

    return {
        "macro_rows": len(MACRO_ROWS),
        "diagnostic_rows": len(DIAGNOSTIC_ROWS),
        "manual_rows": len(MANUAL_ROWS),
        "output_dir": str(OUT_DIR),
    }


if __name__ == "__main__":
    result = build_macro_pack()
    print(json.dumps(result, indent=2))
``
