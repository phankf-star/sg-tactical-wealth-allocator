
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
from manual_seed_parser_block import load_manual_macro_seed, split_manual_seed_for_outputs

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

def clean_html_for_macro(txt):
    txt = re.sub(r"<script[\s\S]*?</script>", " ", txt, flags=re.I)
    txt = re.sub(r"<style[\s\S]*?</style>", " ", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"&nbsp;|&#160;", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def month_name_to_number(month_name):
    months = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    key = str(month_name).strip().lower()
    if key not in months:
        raise ValueError(f"Unknown month name: {month_name}")
    return months[key]


def month_year_to_first_day(month_name, year):
    m = month_name_to_number(month_name)
    return f"{int(year):04d}-{m:02d}-01"

def parse_first_float(patterns, txt, label):
    for pat in patterns:
        m = re.search(pat, txt, flags=re.I | re.S)
        if m:
            return float(m.group(1))
    raise ValueError(f"Could not parse {label}")


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


def add_hk_unemployment_live():
    """
    Hong Kong unemployment live/parser row.

    Source:
    HK Government / C&SD unemployment and underemployment press release.

    This parser fetches the official source page during the workflow run.
    If parsing fails, it writes manual_required instead of carrying stale data.
    """
    source = "HK Government / C&SD unemployment press release"
    url = "https://www.info.gov.hk/gia/general/202606/16/P2026061600318.htm"

    try:
        txt = clean_html_for_macro(request_text(url, accept="text/html,text/plain,*/*"))

        period_match = re.search(
            r"(March\s*-\s*May\s*2026|Mar(?:ch)?\s*-\s*May\s*2026|3/2026\s*-\s*5/2026)",
            txt,
            flags=re.I,
        )

        if period_match:
            period = period_match.group(1)
            date_txt = "2026-05-31"
        else:
            period = "March-May 2026"
            date_txt = "2026-05-31"

        rate_match = re.search(
            r"unemployment rate\s*(?:stood at|was|remained unchanged at)?\s*([0-9.]+)\s*%",
            txt,
            flags=re.I,
        )

        if not rate_match:
            rate_match = re.search(
                r"seasonally adjusted unemployment rate\s*(?:stood at|was|remained unchanged at)?\s*([0-9.]+)\s*%",
                txt,
                flags=re.I,
            )

        if not rate_match:
            raise ValueError("Could not parse HK unemployment rate from press release")

        value = round(float(rate_match.group(1)), 3)

        if not (0 <= value <= 20):
            raise ValueError(f"HK unemployment sanity check failed: {value}")

        row(
            "HK",
            "Unemployment",
            date_txt,
            value,
            "%",
            source,
            "Official / Parsed",
            f"Parsed from official HK unemployment press release; period={period}.",
        )

        diag(
            "HK",
            "Unemployment",
            source,
            "success",
            value=value,
            reason=f"Parsed HK unemployment {value}% for {period}",
            endpoint=url,
        )

    except Exception as e:
        diag(
            "HK",
            "Unemployment",
            source,
            "failed",
            reason=str(e),
            endpoint=url,
        )
        manual("HK", "Unemployment", f"HK unemployment parser failed: {e}")


def add_japan_latest_indicators_live():
    """
    Japan CPI and unemployment live/parser rows.

    Source:
    Statistics Bureau of Japan latest indicators page.

    This fetches latest displayed CPI and unemployment indicators during the workflow run.
    """
    source_page = "Statistics Bureau of Japan latest indicators"
    url = "https://www.stat.go.jp/english/"

    try:
        txt = clean_html_for_macro(request_text(url, accept="text/html,text/plain,*/*"))

        # Consumer Price Index 1.5 % May 2026 change over the year
        m_cpi = re.search(
            r"Consumer Price Index\s*([0-9.]+)\s*%\s*([A-Za-z]+)\s*(20\d{2})\s*change over the year",
            txt,
            flags=re.I,
        )

        if not m_cpi:
            raise ValueError("Could not parse Japan CPI latest indicator")

        cpi_value = round(float(m_cpi.group(1)), 3)
        cpi_month = m_cpi.group(2)
        cpi_year = m_cpi.group(3)
        cpi_date = month_year_to_first_day(cpi_month, cpi_year)

        if not (-10 <= cpi_value <= 25):
            raise ValueError(f"Japan CPI sanity check failed: {cpi_value}")

        row(
            "JP",
            "Inflation",
            cpi_date,
            cpi_value,
            "%",
            source_page + " / CPI",
            "Official / Parsed",
            f"Parsed Japan CPI YoY from Statistics Bureau latest indicators; period={cpi_month} {cpi_year}.",
        )

        diag(
            "JP",
            "Inflation",
            source_page + " / CPI",
            "success",
            value=cpi_value,
            reason=f"Parsed Japan CPI YoY {cpi_value}% for {cpi_month} {cpi_year}",
            endpoint=url,
        )

        # Unemployment rate 2.5 % April 2026 seasonally adjusted
        m_unemp = re.search(
            r"Unemployment rate\s*([0-9.]+)\s*%\s*([A-Za-z]+)\s*(20\d{2})\s*seasonally adjusted",
            txt,
            flags=re.I,
        )

        if not m_unemp:
            raise ValueError("Could not parse Japan unemployment latest indicator")

        unemp_value = round(float(m_unemp.group(1)), 3)
        unemp_month = m_unemp.group(2)
        unemp_year = m_unemp.group(3)
        unemp_date = month_year_to_first_day(unemp_month, unemp_year)

        if not (0 <= unemp_value <= 20):
            raise ValueError(f"Japan unemployment sanity check failed: {unemp_value}")

        row(
            "JP",
            "Unemployment",
            unemp_date,
            unemp_value,
            "%",
            source_page + " / Labour Force Survey",
            "Official / Parsed",
            f"Parsed Japan unemployment rate from Statistics Bureau latest indicators; period={unemp_month} {unemp_year}.",
        )

        diag(
            "JP",
            "Unemployment",
            source_page + " / Labour Force Survey",
            "success",
            value=unemp_value,
            reason=f"Parsed Japan unemployment {unemp_value}% for {unemp_month} {unemp_year}",
            endpoint=url,
        )

    except Exception as e:
        diag(
            "JP",
            "Inflation/Unemployment",
            source_page,
            "failed",
            reason=str(e),
            endpoint=url,
        )
        manual("JP", "Inflation", f"Japan latest indicators parser failed: {e}")
        manual("JP", "Unemployment", f"Japan latest indicators parser failed: {e}")


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


def add_pmi_parsed_rows():
    """
    PMI parsed rows.

    This replaces static PMI seed rows with source-parsed PMI rows.
    Each market is handled independently:
    - If parsing succeeds, write macro_data row and success diagnostic.
    - If parsing fails, write diagnostic + manual_required for that market only.
    """

    def emit_pmi_row(market, date_txt, value, source, source_type, period, endpoint):
        value = round(float(value), 3)

        if not (0 <= value <= 100):
            raise ValueError(f"{market} PMI sanity check failed: {value}")

        row(
            market,
            "PMI",
            date_txt,
            value,
            "index",
            source,
            source_type,
            f"Parsed PMI from source; period={period}.",
        )

        diag(
            market,
            "PMI",
            source,
            "success",
            value=value,
            reason=f"Parsed PMI {value} for {period}",
            endpoint=endpoint,
        )

    # US PMI — ISM Manufacturing PMI via release page
    try:
        market = "US"
        source = "ISM Manufacturing PMI via PRNewswire release"
        source_type = "Parsed / Release"
        period = "May 2026"
        endpoint = "https://www.prnewswire.com/news-releases/manufacturing-pmi-at-54-may-2026-ism-manufacturing-pmi-report-302786165.html"

        txt = clean_html_for_macro(request_text(endpoint, accept="text/html,text/plain,*/*"))

        value = parse_first_float(
            [
                r"Manufacturing PMI.*?registered\s*([0-9.]+)\s*percent\s*in\s*May",
                r"Manufacturing PMI.*?at\s*([0-9.]+)\s*%",
                r"PMI.*?registered\s*([0-9.]+)\s*percent",
            ],
            txt,
            "US ISM Manufacturing PMI",
        )

        emit_pmi_row(
            market,
            "2026-05-01",
            value,
            source,
            source_type,
            period,
            endpoint,
        )

    except Exception as e:
        diag(
            "US",
            "PMI",
            "ISM Manufacturing PMI via PRNewswire release",
            "failed",
            reason=str(e),
            endpoint="https://www.prnewswire.com/news-releases/manufacturing-pmi-at-54-may-2026-ism-manufacturing-pmi-report-302786165.html",
        )
        manual("US", "PMI", f"US PMI parser failed: {e}")

    # Singapore PMI — SIPMM via Trading Economics
    try:
        market = "SG"
        source = "SIPMM Singapore Manufacturing PMI via Trading Economics"
        source_type = "Parsed / Secondary"
        period = "May 2026"
        endpoint = "https://tradingeconomics.com/singapore/manufacturing-pmi"

        txt = clean_html_for_macro(request_text(endpoint, accept="text/html,text/plain,*/*"))

        value = parse_first_float(
            [
                r"Singapore.?s Manufacturing PMI rose to\s*([0-9.]+)\s*in\s*May\s*2026",
                r"Manufacturing PMI in Singapore increased to\s*([0-9.]+)\s*points\s*in\s*May",
            ],
            txt,
            "Singapore Manufacturing PMI",
        )

        emit_pmi_row(
            market,
            "2026-05-01",
            value,
            source,
            source_type,
            period,
            endpoint,
        )

    except Exception as e:
        diag(
            "SG",
            "PMI",
            "SIPMM Singapore Manufacturing PMI via Trading Economics",
            "failed",
            reason=str(e),
            endpoint="https://tradingeconomics.com/singapore/manufacturing-pmi",
        )
        manual("SG", "PMI", f"Singapore PMI parser failed: {e}")

    # Hong Kong PMI — S&P Global via Trading Economics
    try:
        market = "HK"
        source = "S&P Global Hong Kong SAR PMI via Trading Economics"
        source_type = "Parsed / Secondary"
        period = "May 2026"
        endpoint = "https://tradingeconomics.com/hong-kong/manufacturing-pmi"

        txt = clean_html_for_macro(request_text(endpoint, accept="text/html,text/plain,*/*"))

        value = parse_first_float(
            [
                r"Hong Kong SAR PMI rose to\s*([0-9.]+)\s*in\s*May\s*2026",
                r"Manufacturing PMI in Hong Kong increased to\s*([0-9.]+)\s*points\s*in\s*May",
                r"PMI rose to\s*([0-9.]+)\s*in\s*May",
            ],
            txt,
            "Hong Kong SAR PMI",
        )

        emit_pmi_row(
            market,
            "2026-05-01",
            value,
            source,
            source_type,
            period,
            endpoint,
        )

    except Exception as e:
        diag(
            "HK",
            "PMI",
            "S&P Global Hong Kong SAR PMI via Trading Economics",
            "failed",
            reason=str(e),
            endpoint="https://tradingeconomics.com/hong-kong/manufacturing-pmi",
        )
        manual("HK", "PMI", f"Hong Kong PMI parser failed: {e}")

    # Malaysia PMI — S&P Global via Trading Economics
    try:
        market = "MY"
        source = "S&P Global Malaysia Manufacturing PMI via Trading Economics"
        source_type = "Parsed / Secondary"
        period = "May 2026"
        endpoint = "https://tradingeconomics.com/malaysia/manufacturing-pmi"

        txt = clean_html_for_macro(request_text(endpoint, accept="text/html,text/plain,*/*"))

        value = parse_first_float(
            [
                r"Manufacturing PMI in Malaysia decreased to\s*([0-9.]+)\s*points\s*in\s*May",
                r"S&P Global Manufacturing PMI.*?decreased to\s*([0-9.]+)\s*points\s*in\s*May",
                r"Manufacturing PMI.*?fell to\s*([0-9.]+)\s*in\s*May",
            ],
            txt,
            "Malaysia Manufacturing PMI",
        )

        emit_pmi_row(
            market,
            "2026-05-01",
            value,
            source,
            source_type,
            period,
            endpoint,
        )

    except Exception as e:
        diag(
            "MY",
            "PMI",
            "S&P Global Malaysia Manufacturing PMI via Trading Economics",
            "failed",
            reason=str(e),
            endpoint="https://tradingeconomics.com/malaysia/manufacturing-pmi",
        )
        manual("MY", "PMI", f"Malaysia PMI parser failed: {e}")

    # Japan PMI — S&P Global via Trading Economics
    try:
        market = "JP"
        source = "S&P Global Japan Manufacturing PMI via Trading Economics"
        source_type = "Parsed / Secondary"
        endpoint = "https://tradingeconomics.com/japan/manufacturing-pmi"

        txt = clean_html_for_macro(request_text(endpoint, accept="text/html,text/plain,*/*"))

        m = re.search(
            r"Manufacturing PMI.*?increased to\s*([0-9.]+)\s*(?:points)?\s*in\s*([A-Za-z]+)\s*(20\d{2})",
            txt,
            flags=re.I | re.S,
        )

        if not m:
            raise ValueError("Could not parse Japan Manufacturing PMI")

        value = float(m.group(1))
        pmi_month = m.group(2)
        pmi_year = m.group(3)
        pmi_date = month_year_to_first_day(pmi_month, pmi_year)
        period = f"{pmi_month} {pmi_year}"

        emit_pmi_row(
            market,
            pmi_date,
            value,
            source,
            source_type,
            period,
            endpoint,
        )

    except Exception as e:
        diag(
            "JP",
            "PMI",
            "S&P Global Japan Manufacturing PMI via Trading Economics",
            "failed",
            reason=str(e),
            endpoint="https://tradingeconomics.com/japan/manufacturing-pmi",
        )
        manual("JP", "PMI", f"Japan PMI parser failed: {e}")



# ─────────────────────────────────────────────────────────────────────────────

# manual_seed_parser_block.py missing

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
    add_hk_unemployment_live()

    # Malaysia
    add_opendosm_malaysia_cpi()              # IMPORTANT: this is the fixed MY Inflation row
    add_opendosm_malaysia_unemployment()
    add_malaysia_rates_manual_or_reviewed()

    # Japan monthly macro rows
    add_japan_latest_indicators_live()

    # PMI parsed rows
    add_pmi_parsed_rows()

    # Write CSV outputs
    macro_cols = ["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"]
    diag_cols = ["run_utc", "market", "indicator", "source", "status", "value", "reason", "endpoint"]
    manual_cols = ["run_utc", "market", "indicator", "reason"]
    source_cols = ["market", "indicator", "source", "source_type", "endpoint", "notes"]

    # ------------------------------------------------------------
    # Manual macro seed integration: SG/JP rates, CPI, unemployment
    # ------------------------------------------------------------
    manual_macro_df = pd.DataFrame()
    manual_rates_df = pd.DataFrame()
    try:
        manual_seed_df = load_manual_macro_seed()
        manual_macro_df, manual_rates_df = split_manual_seed_for_outputs(manual_seed_df)

        if manual_macro_df is not None and not manual_macro_df.empty:
            for rec in manual_macro_df.to_dict("records"):
                row = {c: rec.get(c, "") for c in macro_cols}
                MACRO_ROWS.append(row)

        diag(
            "PACK",
            "Manual seed",
            "macro_seed_inputs",
            "accepted",
            reason=f"manual_macro_rows={0 if manual_macro_df is None else len(manual_macro_df)}, manual_rate_rows={0 if manual_rates_df is None else len(manual_rates_df)}",
            endpoint="macro_seed_inputs/",
        )

    except Exception as e:
        diag(
            "PACK",
            "Manual seed",
            "macro_seed_inputs",
            "failed",
            reason=str(e),
            endpoint="macro_seed_inputs/",
        )

    # Main macro output
    write_csv(OUT_DIR / "macro_data.csv", MACRO_ROWS, macro_cols)

    # 12M macro history output for Inflation / Unemployment / PMI etc.
    try:
        macro_hist_df = pd.DataFrame(MACRO_ROWS)
        if not macro_hist_df.empty:
            macro_hist_df["date"] = pd.to_datetime(macro_hist_df["date"], errors="coerce")
            macro_hist_df["value"] = pd.to_numeric(macro_hist_df["value"], errors="coerce")
            macro_hist_df = macro_hist_df.dropna(subset=["market", "indicator", "date", "value"])
            macro_hist_df = macro_hist_df.sort_values(["market", "indicator", "date"])
            macro_hist_df = macro_hist_df.drop_duplicates(["market", "indicator", "date"], keep="last")
            macro_hist_df = macro_hist_df.groupby(["market", "indicator"], group_keys=False).tail(12)
            macro_hist_df["date"] = macro_hist_df["date"].dt.strftime("%Y-%m-%d")
            write_csv(OUT_DIR / "macro_history_12m.csv", macro_hist_df.to_dict("records"), macro_cols)
        else:
            write_csv(OUT_DIR / "macro_history_12m.csv", [], macro_cols)
    except Exception as e:
        diag("PACK", "macro_history_12m.csv", "builder", "failed", reason=str(e), endpoint="macro_history_12m.csv")
        write_csv(OUT_DIR / "macro_history_12m.csv", [], macro_cols)

    # 252D rates history output from manual SG/JP rates seed
    try:
        if manual_rates_df is not None and not manual_rates_df.empty:
            manual_rates_df["date"] = pd.to_datetime(manual_rates_df["date"], errors="coerce")
            manual_rates_df["value"] = pd.to_numeric(manual_rates_df["value"], errors="coerce")
            manual_rates_df = manual_rates_df.dropna(subset=["market", "indicator", "date", "value"])
            manual_rates_df = manual_rates_df.sort_values(["market", "indicator", "date"])
            manual_rates_df = manual_rates_df.drop_duplicates(["market", "indicator", "date"], keep="last")
            manual_rates_df = manual_rates_df.groupby(["market", "indicator"], group_keys=False).tail(252)
            manual_rates_df["date"] = manual_rates_df["date"].dt.strftime("%Y-%m-%d")
            write_csv(
                OUT_DIR / "rates_history_252d.csv",
                manual_rates_df.to_dict("records"),
                list(manual_rates_df.columns),
            )
        else:
            write_csv(
                OUT_DIR / "rates_history_252d.csv",
                [],
                ["market", "indicator", "date", "value", "unit", "source", "source_type", "frequency", "notes"],
            )
    except Exception as e:
        diag("PACK", "rates_history_252d.csv", "builder", "failed", reason=str(e), endpoint="rates_history_252d.csv")
        write_csv(
            OUT_DIR / "rates_history_252d.csv",
            [],
            ["market", "indicator", "date", "value", "unit", "source", "source_type", "frequency", "notes"],
        )

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
