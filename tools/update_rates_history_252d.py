from pathlib import Path
import io
import json
import urllib.parse
import urllib.request
import pandas as pd
import numpy as np

OUT_FILE = Path("macro_pack_latest/rates_history_252d.csv")
LOOKBACK_DAYS = 420      # fetch more than 252 calendar days so there are enough trading/business observations
OUTPUT_ROWS_PER_MARKET = 252

# Output schema is intentionally simple/flexible for sg_tactical_wealth_allocator.py:
# market,date,value,indicator,unit,source,source_type,notes
COLUMNS = ["market", "date", "value", "indicator", "unit", "source", "source_type", "notes"]

MARKET_LABELS = {
    "US": "US",
    "SG": "SG",
    "HK": "HK",
    "MY": "MY",
    "JP": "JP",
}

TODAY = pd.Timestamp.today().normalize()
START = TODAY - pd.Timedelta(days=LOOKBACK_DAYS)


def request_text(url, headers=None, timeout=25):
    headers = headers or {}
    base_headers = {
        "User-Agent": "Mozilla/5.0 Global20Engine/1.0",
        "Accept": "application/json,text/csv,text/plain,*/*",
        "Accept-Encoding": "identity",
    }
    base_headers.update(headers)
    req = urllib.request.Request(url, headers=base_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("utf-8-sig", errors="replace")


def clean_number(v):
    try:
        if v is None:
            return np.nan
        s = str(v).replace(",", "").replace("%", "").replace("+", "").strip()
        if s.lower() in {"", "na", "n.a.", "nan", "none", "-", "--", "—"}:
            return np.nan
        return float(s)
    except Exception:
        return np.nan


def normalise_date(v, dayfirst=False):
    if v is None or str(v).strip() == "":
        return pd.NaT
    s = str(v).strip()
    if s.isdigit() and len(s) == 8:
        return pd.to_datetime(s, format="%Y%m%d", errors="coerce")
    return pd.to_datetime(s, errors="coerce", dayfirst=dayfirst)


def make_rows(market, df, source, notes=""):
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNS)
    tmp = df.copy()
    tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce")
    tmp["value"] = pd.to_numeric(tmp["value"], errors="coerce")
    tmp = tmp.dropna(subset=["date", "value"]).sort_values("date")
    tmp = tmp[tmp["date"] >= START]
    tmp = tmp.drop_duplicates("date", keep="last").tail(OUTPUT_ROWS_PER_MARKET)
    if tmp.empty:
        return pd.DataFrame(columns=COLUMNS)
    out = pd.DataFrame({
        "market": MARKET_LABELS.get(market, market),
        "date": tmp["date"].dt.strftime("%Y-%m-%d"),
        "value": tmp["value"].astype(float),
        "indicator": "Rates",
        "unit": "%",
        "source": source,
        "source_type": "Official / History",
        "notes": notes,
    })
    return out[COLUMNS]


def daily_step_from_events(events_df, market, source, notes=""):
    """Convert policy-rate event dates into a daily forward-filled 252D history."""
    if events_df is None or events_df.empty:
        return pd.DataFrame(columns=COLUMNS)
    ev = events_df.copy()
    ev["date"] = pd.to_datetime(ev["date"], errors="coerce")
    ev["value"] = pd.to_numeric(ev["value"], errors="coerce")
    ev = ev.dropna(subset=["date", "value"]).sort_values("date")
    if ev.empty:
        return pd.DataFrame(columns=COLUMNS)
    idx = pd.date_range(START, TODAY, freq="D")
    s = ev.set_index("date")["value"].sort_index()
    daily = s.reindex(s.index.union(idx)).sort_index().ffill().reindex(idx)
    # If all lookback values are blank because first event is after START, backfill from first available event.
    daily = daily.bfill()
    df = pd.DataFrame({"date": daily.index, "value": daily.values}).dropna()
    return make_rows(market, df, source, notes)


def fetch_us_dgs10():
    """US 10Y Treasury yield from FRED DGS10 daily CSV."""
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
    txt = request_text(url, headers={"Accept": "text/csv,*/*"})
    df = pd.read_csv(io.StringIO(txt))
    if "DATE" not in df.columns or "DGS10" not in df.columns:
        return pd.DataFrame(columns=COLUMNS)
    out = pd.DataFrame({
        "date": pd.to_datetime(df["DATE"], errors="coerce"),
        "value": pd.to_numeric(df["DGS10"], errors="coerce"),
    })
    return make_rows("US", out, "FRED DGS10 daily", "US 10-year Treasury constant maturity yield")


def fetch_hk_hibor():
    """HKD rates from HKMA HIBOR daily endpoint. Prefers 1M HIBOR when present."""
    urls = [
        "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily?pagesize=1000&sortby=end_of_day&sortorder=desc",
        "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-endperiod?pagesize=1000&sortby=end_of_month&sortorder=desc",
    ]
    for url in urls:
        try:
            txt = request_text(url)
            payload = json.loads(txt)
            records = payload.get("result", {}).get("records") or payload.get("result", {}).get("data") or []
            if not records:
                continue
            rows = []
            for r in records:
                if not isinstance(r, dict):
                    continue
                dt_raw = r.get("end_of_day") or r.get("end_of_month") or r.get("date")
                dt = normalise_date(dt_raw)
                val = np.nan
                used_key = ""
                for k in ["hibor_1m", "ir_1m", "one_month", "1m", "ir_overnight", "overnight", "value"]:
                    if k in r:
                        val = clean_number(r.get(k))
                        used_key = k
                        if not pd.isna(val):
                            break
                if pd.notna(dt) and pd.notna(val):
                    rows.append({"date": dt, "value": val, "used_key": used_key})
            if rows:
                df = pd.DataFrame(rows)
                return make_rows("HK", df, "HKMA Open API HIBOR daily", "Preferred HKMA HIBOR field used where available")
        except Exception as e:
            print(f"WARNING: HKMA rates fetch failed for {url}: {e}")
    return pd.DataFrame(columns=COLUMNS)


def fetch_bnm_opr():
    """Malaysia BNM OPR history. BNM dates are day-first when slash-formatted."""
    headers = {"Accept": "application/vnd.BNM.API.v1+json"}
    urls = [
        "https://api.bnm.gov.my/public/opr",
        f"https://api.bnm.gov.my/public/opr/year/{TODAY.year}",
        f"https://api.bnm.gov.my/public/opr/year/{TODAY.year - 1}",
    ]
    rows = []
    for url in urls:
        try:
            txt = request_text(url, headers=headers)
            payload = json.loads(txt)
            records = []
            if isinstance(payload, dict):
                for key in ["data", "records"]:
                    if isinstance(payload.get(key), list):
                        records = payload.get(key)
                        break
                if not records and isinstance(payload.get("result"), dict):
                    records = payload["result"].get("records") or payload["result"].get("data") or []
            elif isinstance(payload, list):
                records = payload
            for r in records or []:
                if not isinstance(r, dict):
                    continue
                dt_raw = r.get("date") or r.get("effective_date") or r.get("Date")
                val = np.nan
                for k in ["rate", "opr", "OPR", "value"]:
                    if k in r:
                        val = clean_number(r.get(k))
                        if not pd.isna(val):
                            break
                dt = normalise_date(dt_raw, dayfirst=True)
                if pd.notna(dt) and pd.notna(val):
                    rows.append({"date": dt, "value": val})
        except Exception as e:
            print(f"WARNING: BNM OPR fetch failed for {url}: {e}")
    if rows:
        return daily_step_from_events(pd.DataFrame(rows), "MY", "BNM OpenAPI Overnight Policy Rate (OPR)", "Policy-rate event history forward-filled to daily 252D chart")
    return pd.DataFrame(columns=COLUMNS)


def load_optional_seed_file(market, candidate_names, source, dayfirst=False):
    """Load optional manual/live seed CSVs if present in repo. Flexible column parser."""
    paths = []
    for name in candidate_names:
        paths.extend([Path(name), Path("macro_pack_latest") / name, Path("data") / name, Path("manual_seed") / name])
    existing = [p for p in paths if p.exists()]
    if not existing:
        return pd.DataFrame(columns=COLUMNS)
    frames = []
    for path in existing:
        try:
            df = pd.read_csv(path)
            df.columns = [str(c).strip().lower() for c in df.columns]
            date_col = next((c for c in ["date", "end_of_day", "time", "period"] if c in df.columns), None)
            value_col = next((c for c in ["value", "rate", "rates", "sora", "opr", "call_rate", "uncollateralized overnight call rate", "close"] if c in df.columns), None)
            if date_col is None:
                # fallback: first column that parses like dates
                for c in df.columns:
                    parsed = pd.to_datetime(df[c], errors="coerce", dayfirst=dayfirst)
                    if parsed.notna().sum() >= max(3, len(df) * 0.5):
                        date_col = c
                        break
            if value_col is None:
                # fallback: first numeric-looking column after date
                for c in df.columns:
                    if c == date_col:
                        continue
                    nums = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False), errors="coerce")
                    if nums.notna().sum() >= max(3, len(df) * 0.5):
                        value_col = c
                        break
            if date_col and value_col:
                tmp = pd.DataFrame({
                    "date": pd.to_datetime(df[date_col], errors="coerce", dayfirst=dayfirst),
                    "value": pd.to_numeric(df[value_col].astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False), errors="coerce"),
                })
                frames.append(tmp)
                print(f"Loaded {market} rates seed: {path} using date={date_col}, value={value_col}")
            else:
                print(f"WARNING: Could not identify date/value columns in {path}")
        except Exception as e:
            print(f"WARNING: Could not load seed {path}: {e}")
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    return make_rows(market, combined, source, "Optional repo seed/live rates CSV")


def preserve_existing_market(market):
    """If an existing rates_history_252d.csv already has a market, preserve it as fallback."""
    if not OUT_FILE.exists():
        return pd.DataFrame(columns=COLUMNS)
    try:
        df = pd.read_csv(OUT_FILE)
        df.columns = [str(c).strip().lower() for c in df.columns]
        if not {"market", "date", "value"}.issubset(set(df.columns)):
            return pd.DataFrame(columns=COLUMNS)
        sub = df[df["market"].astype(str).str.upper().eq(market.upper())].copy()
        if sub.empty:
            return pd.DataFrame(columns=COLUMNS)
        for c in COLUMNS:
            if c not in sub.columns:
                sub[c] = ""
        return make_rows(market, sub[["date", "value"]], "Preserved existing rates_history_252d.csv", "Fallback preserved from previous generated file")
    except Exception as e:
        print(f"WARNING: preserve existing {market} failed: {e}")
        return pd.DataFrame(columns=COLUMNS)


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    results = []

    fetchers = {
        "US": fetch_us_dgs10,
        "HK": fetch_hk_hibor,
        "MY": fetch_bnm_opr,
    }

    # Official/API fetches where stable.
    for market, fn in fetchers.items():
        try:
            df = fn()
            if df is not None and not df.empty:
                print(f"{market}: fetched {len(df)} rows")
                results.append(df)
            else:
                print(f"WARNING: {market}: no rows fetched")
        except Exception as e:
            print(f"WARNING: {market}: fetch failed: {e}")

    # SG / JP: prefer optional repo seed files because live official daily history can be unreliable in hosted runtime.
    sg_seed = load_optional_seed_file(
        "SG",
        ["sg_rates_sora_daily.csv", "SG Domestic Interest Rates 2026-06-26.csv"],
        "SG SORA daily seed / repo CSV",
        dayfirst=True,
    )
    if sg_seed.empty:
        sg_seed = preserve_existing_market("SG")
    if not sg_seed.empty:
        print(f"SG: using {len(sg_seed)} rows")
        results.append(sg_seed)
    else:
        print("WARNING: SG: no seed/existing rows found")

    jp_seed = load_optional_seed_file(
        "JP",
        ["jp_rates_call_overnight_daily.csv", "JP Rates.csv", "jp_rates.csv"],
        "BOJ overnight call rate daily seed / repo CSV",
        dayfirst=False,
    )
    if jp_seed.empty:
        jp_seed = preserve_existing_market("JP")
    if not jp_seed.empty:
        print(f"JP: using {len(jp_seed)} rows")
        results.append(jp_seed)
    else:
        print("WARNING: JP: no seed/existing rows found")

    if results:
        combined = pd.concat(results, ignore_index=True)
    else:
        combined = pd.DataFrame(columns=COLUMNS)

    # Final clean-up: one row per market/date, last wins.
    for c in COLUMNS:
        if c not in combined.columns:
            combined[c] = ""
    combined = combined[COLUMNS].copy()
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined["value"] = pd.to_numeric(combined["value"], errors="coerce")
    combined = combined.dropna(subset=["date", "value"])
    combined = combined.sort_values(["market", "date"])
    combined = combined.drop_duplicates(["market", "date"], keep="last")
    combined = combined.groupby("market", group_keys=False).tail(OUTPUT_ROWS_PER_MARKET)
    combined["date"] = combined["date"].dt.strftime("%Y-%m-%d")
    combined = combined.sort_values(["market", "date"])

    combined.to_csv(OUT_FILE, index=False)
    print(f"rates_history_252d written: {len(combined)} rows -> {OUT_FILE}")
    if not combined.empty:
        print(combined.groupby("market").size().to_string())


if __name__ == "__main__":
    main()
