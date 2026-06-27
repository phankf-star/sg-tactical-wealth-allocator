# Global20Engine manual macro seed parser block
# Paste this block into g20_macro_fetcher.py after imports/helper functions.

from pathlib import Path
import csv
import re
import pandas as pd

SEED_DIR = Path("macro_seed_inputs")


def _clean_num(x):
    if x is None:
        return None
    s = str(x).strip().replace(",", "").replace("%", "")
    if s == "" or s.lower() in {"na", "n.a.", "nan", "none", "null", "-", "--", "…"}:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _month_to_num(m):
    m = str(m).strip()[:3].lower()
    return {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }.get(m)


def _standard_row(market, indicator, date, value, unit, source, frequency, notes=""):
    return {
        "market": market,
        "indicator": indicator,
        "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
        "value": float(value),
        "unit": unit,
        "source": source,
        "source_type": "Manual official seed",
        "frequency": frequency,
        "notes": notes,
    }


# ---------- SG Rates: MAS daily SORA ----------
def parse_seed_sg_rates(path=SEED_DIR / "sg_rates_sora_daily.csv"):
    if not Path(path).exists():
        return pd.DataFrame()
    rows = []
    cur_year = None
    cur_month = None
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        for raw in reader:
            cells = [c.strip() for c in raw]
            if not cells or all(c == "" for c in cells):
                continue
            if any("SORA Value Date" in c for c in cells):
                continue
            # Expected shape after cleaned upload:
            # Year, Month, Day, SORA Publication Date, SORA
            while len(cells) < 5:
                cells.append("")
            year, month, day, pub_date, sora = cells[:5]
            if re.fullmatch(r"20\d{2}", year):
                cur_year = int(year)
            if month:
                cur_month = month
            if not cur_year or not cur_month:
                continue
            if not re.fullmatch(r"\d{1,2}", day):
                continue
            month_num = _month_to_num(cur_month)
            val = _clean_num(sora)
            if not month_num or val is None:
                continue
            dt = pd.Timestamp(year=cur_year, month=month_num, day=int(day))
            rows.append(_standard_row(
                "SG", "Rates", dt, val, "%",
                "MAS Domestic Interest Rates manual export - SORA",
                "daily",
                "Manual official MAS SORA daily seed; Year/Month forward-filled by parser",
            ))
    return pd.DataFrame(rows)


# ---------- JP Rates: BOJ daily call rate ----------
def parse_seed_jp_rates(path=SEED_DIR / "jp_rates_call_overnight_daily.csv"):
    if not Path(path).exists():
        return pd.DataFrame()
    rows = []
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        for cells in reader:
            if len(cells) < 2:
                continue
            d = str(cells[0]).strip()
            v = _clean_num(cells[1])
            dt = pd.to_datetime(d, errors="coerce")
            if pd.isna(dt) or v is None:
                continue
            rows.append(_standard_row(
                "JP", "Rates", dt, v, "%",
                "BOJ Time-Series Data Search manual export - FM01 STRDCLUCON",
                "daily",
                "Dropped NA/weekend/blank future rows",
            ))
    return pd.DataFrame(rows)


# ---------- SG CPI: monthly YoY ----------
def _read_csv_from_header(path, header_keyword="Data Series"):
    # Handles both clean GitHub preview CSV and raw SingStat export with metadata lines.
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()
    header_idx = 0
    for i, line in enumerate(lines):
        if header_keyword in line:
            header_idx = i
            break
    return pd.read_csv(path, encoding="utf-8-sig", skiprows=header_idx)


def _parse_month_label(label):
    s = str(label).strip().replace("  ", " ")
    # examples: 2026 May, 2026 May , Jan. 2025, May-25
    m = re.match(r"^(20\d{2})\s+([A-Za-z]{3,9})", s)
    if m:
        return pd.Timestamp(year=int(m.group(1)), month=_month_to_num(m.group(2)), day=1)
    m = re.match(r"^([A-Za-z]{3})\. ?(20\d{2})$", s)
    if m:
        return pd.Timestamp(year=int(m.group(2)), month=_month_to_num(m.group(1)), day=1)
    m = re.match(r"^([A-Za-z]{3})-(\d{2})$", s)
    if m:
        return pd.Timestamp(year=2000 + int(m.group(2)), month=_month_to_num(m.group(1)), day=1)
    return pd.NaT


def parse_seed_sg_cpi(path=SEED_DIR / "sg_cpi_yoy_monthly.csv"):
    if not Path(path).exists():
        return pd.DataFrame()
    df = _read_csv_from_header(path, "Data Series")
    first_col = df.columns[0]
    row = df[df[first_col].astype(str).str.strip().str.lower().eq("all items")]
    if row.empty:
        return pd.DataFrame()
    row = row.iloc[0]
    rows = []
    for col in df.columns[1:]:
        dt = _parse_month_label(col)
        val = _clean_num(row[col])
        if pd.isna(dt) or val is None:
            continue
        rows.append(_standard_row(
            "SG", "Inflation", dt, val, "% YoY",
            "SingStat CPI YoY manual export - All Items",
            "monthly",
            "Percent change in CPI over corresponding period of previous year",
        ))
    return pd.DataFrame(rows)


# ---------- JP CPI: monthly index, calculate YoY ----------
def parse_seed_jp_cpi(path=SEED_DIR / "jp_cpi_index_monthly.csv"):
    if not Path(path).exists():
        return pd.DataFrame()
    raw = pd.read_csv(path, encoding="utf-8-sig")
    if raw.shape[1] < 2:
        return pd.DataFrame()
    date_col, value_col = raw.columns[:2]
    tmp = raw[[date_col, value_col]].copy()
    tmp["date"] = pd.to_datetime(tmp[date_col].astype(str).str.extract(r"(\d{6})", expand=False) + "01", format="%Y%m%d", errors="coerce")
    tmp["index"] = pd.to_numeric(tmp[value_col], errors="coerce")
    tmp = tmp.dropna(subset=["date", "index"]).sort_values("date")
    tmp["prev_year_index"] = tmp.set_index("date")["index"].shift(12).values
    tmp["yoy"] = (tmp["index"] / tmp["prev_year_index"] - 1.0) * 100.0
    rows = []
    for r in tmp.dropna(subset=["yoy"]).itertuples(index=False):
        rows.append(_standard_row(
            "JP", "Inflation", r.date, float(r.yoy), "% YoY",
            "Japan Statistics Bureau CPI manual export - All items less imputed rent",
            "monthly",
            "YoY calculated from CPI index by parser",
        ))
    return pd.DataFrame(rows)


# ---------- SG unemployment: quarterly SA ----------
def _quarter_to_month_start(q):
    s = str(q).strip().replace(" ", "")
    m = re.match(r"^(20\d{2})([1-4])Q$", s)
    if not m:
        return pd.NaT
    year, qn = int(m.group(1)), int(m.group(2))
    month = {1: 1, 2: 4, 3: 7, 4: 10}[qn]
    return pd.Timestamp(year=year, month=month, day=1)


def parse_seed_sg_unemployment(path=SEED_DIR / "sg_unemployment_quarterly.csv", monthly_step_fill=True):
    if not Path(path).exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    first_col = df.columns[0]
    row = df[df[first_col].astype(str).str.contains("Total Unemployment Rate", case=False, na=False)]
    if row.empty:
        return pd.DataFrame()
    row = row.iloc[0]
    points = []
    for col in df.columns[1:]:
        dt = _quarter_to_month_start(col)
        val = _clean_num(row[col])
        if pd.isna(dt) or val is None:
            continue
        points.append((dt, val))
    if not points:
        return pd.DataFrame()
    qdf = pd.DataFrame(points, columns=["date", "value"]).sort_values("date")
    if monthly_step_fill:
        idx = pd.date_range(qdf["date"].min(), qdf["date"].max() + pd.DateOffset(months=2), freq="MS")
        qdf = qdf.set_index("date").reindex(idx).ffill().reset_index().rename(columns={"index": "date"})
    rows = []
    for r in qdf.itertuples(index=False):
        rows.append(_standard_row(
            "SG", "Unemployment", r.date, float(r.value), "%",
            "SingStat/MOM unemployment manual export - Total SA",
            "monthly_step_fill_from_quarterly" if monthly_step_fill else "quarterly",
            "Quarterly seasonally adjusted series; parser forward-fills to monthly for chart continuity",
        ))
    return pd.DataFrame(rows)


# ---------- JP unemployment: monthly ----------
def parse_seed_jp_unemployment(path=SEED_DIR / "jp_unemployment_monthly.csv"):
    if not Path(path).exists():
        return pd.DataFrame()
    # Locate actual table header row.
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()
    header_idx = 0
    for i, line in enumerate(lines):
        if "Labour force status" in line and "Time (Monthly)" in line and "Both sexes" in line:
            header_idx = i
            break
    df = pd.read_csv(path, encoding="utf-8-sig", skiprows=header_idx)
    required = ["Labour force status", "Area", "Time (Monthly)", "Both sexes"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()
    filt = (
        df["Labour force status"].astype(str).str.strip().eq("Unemployed person")
        & df["Area"].astype(str).str.strip().eq("All Japan")
    )
    sub = df.loc[filt, ["Time (Monthly)", "Both sexes"]].copy()
    rows = []
    for _, r in sub.iterrows():
        dt = _parse_month_label(r["Time (Monthly)"])
        val = _clean_num(r["Both sexes"])
        if pd.isna(dt) or val is None:
            continue
        rows.append(_standard_row(
            "JP", "Unemployment", dt, val, "%",
            "Japan Labour Force Survey manual export - unemployment rate, All Japan, Both sexes",
            "monthly",
            "Filtered Labour force status=Unemployed person, Area=All Japan, Sex=Both sexes",
        ))
    return pd.DataFrame(rows)


# ---------- Load all manual seed data ----------
def load_manual_macro_seed():
    parts = [
        parse_seed_sg_rates(),
        parse_seed_jp_rates(),
        parse_seed_sg_cpi(),
        parse_seed_jp_cpi(),
        parse_seed_sg_unemployment(),
        parse_seed_jp_unemployment(),
    ]
    parts = [p for p in parts if p is not None and not p.empty]
    if not parts:
        return pd.DataFrame(columns=["market", "indicator", "date", "value", "unit", "source", "source_type", "frequency", "notes"])
    out = pd.concat(parts, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["market", "indicator", "date", "value"])
    out = out.sort_values(["market", "indicator", "date"])
    out = out.drop_duplicates(["market", "indicator", "date"], keep="last")
    return out


def split_manual_seed_for_outputs(manual_df=None):
    if manual_df is None:
        manual_df = load_manual_macro_seed()
    if manual_df.empty:
        return manual_df, manual_df
    rates = manual_df[manual_df["indicator"].eq("Rates")].copy()
    macro = manual_df[~manual_df["indicator"].eq("Rates")].copy()
    # Latest 252 daily rows for rates; latest 12 rows for monthly/quarterly macro indicators.
    if not rates.empty:
        rates["_dt"] = pd.to_datetime(rates["date"], errors="coerce")
        rates = rates.dropna(subset=["_dt"]).sort_values(["market", "indicator", "_dt"])
        rates = rates.groupby(["market", "indicator"], group_keys=False).tail(252).drop(columns=["_dt"])
    if not macro.empty:
        macro["_dt"] = pd.to_datetime(macro["date"], errors="coerce")
        macro = macro.dropna(subset=["_dt"]).sort_values(["market", "indicator", "_dt"])
        macro = macro.groupby(["market", "indicator"], group_keys=False).tail(12).drop(columns=["_dt"])
    return macro, rates


# ---------- Integration helper ----------
def merge_manual_seed(existing_macro_df=None, existing_rates_df=None):
    manual = load_manual_macro_seed()
    manual_macro, manual_rates = split_manual_seed_for_outputs(manual)

    if existing_macro_df is not None and not existing_macro_df.empty:
        macro_out = pd.concat([existing_macro_df, manual_macro], ignore_index=True)
    else:
        macro_out = manual_macro.copy()

    if existing_rates_df is not None and not existing_rates_df.empty:
        rates_out = pd.concat([existing_rates_df, manual_rates], ignore_index=True)
    else:
        rates_out = manual_rates.copy()

    for df in [macro_out, rates_out]:
        if df is not None and not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df.dropna(subset=["market", "indicator", "date", "value"], inplace=True)
            df.sort_values(["market", "indicator", "date"], inplace=True)
            df.drop_duplicates(["market", "indicator", "date"], keep="last", inplace=True)

    return macro_out, rates_out
