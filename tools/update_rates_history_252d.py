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
    """Malaysia BNM OPR history1+json"}    """Malaysia BNM OPR history. BNM dates are day-first when slash-formatted."""

    urls = [
        "https://api.bnm.gov.my/public/opr",
        f"https://api.bnm.gov.my/public/opr/year/{TODAY.year}",
        f"https://api.bnm.gov.my/public/opr?year={TODAY.year}",
        f"https://api.bnm.gov.my/public/opr/year/{TODAY.year - 1}",
        f"https://api.bnm.gov.my/public/opr?year={TODAY.year - 1}",
        f"https://api.bnm.gov.my/public/opr/year/{TODAY.year - 2}",
        f"https://api.bnm.gov.my/public/opr?year={TODAY.year - 2}",
    ]

    rows = []

    def flatten_json(obj):
        out = []
        if isinstance(obj, dict):
            out.append(obj)
            for v in obj.values():
                out.extend(flatten_json(v))
        elif isinstance(obj, list):
            for v in obj:
                out.extend(flatten_json(v))
        return out

    for url in urls:
        try:
            txt = request_text(url, headers=headers)
            payload = json.loads(txt)

            records = flatten_json(payload)
            parsed_here = 0

            for r in records:
                if not isinstance(r, dict):
                    continue

                # BNM can use several date/rate key variants.
                dt_raw = (
                    r.get("date")
                    or r.get("effective_date")
                    or r.get("effectiveDate")
                    or r.get("Date")
                    or r.get("meeting_date")
                    or r.get("year_dt")
                )

                val = np.nan
                for k in [
                    "rate",
                    "opr",
                    "OPR",
                    "value",
                    "new_opr",
                    "overnight_policy_rate",
                    "overnight policy rate",
                ]:
                    if k in r:
                        val = clean_number(r.get(k))
                        if not pd.isna(val):
                            break

                # Secondary fallback: scan numeric values if key names differ.
                if pd.isna(val):
                    for k, v in r.items():
                        kk = str(k).lower()
                        if any(token in kk for token in ["opr", "rate", "value"]):
                            val = clean_number(v)
                            if not pd.isna(val):
                                break

                dt = normalise_date(dt_raw, dayfirst=True)

                if pd.notna(dt) and pd.notna(val) and -2 <= float(val) <= 25:
                    rows.append({"date": dt, "value": float(val)})
                    parsed_here += 1

            print(f"MY BNM parsed {parsed_here} candidate policy records from {url}")

        except Exception as e:
            print(f"WARNING: BNM OPR fetch failed for {url}: {e}")

    if rows:
        events = pd.DataFrame(rows)
        events = events.drop_duplicates(["date", "value"]).sort_values("date")
        return daily_step_from_events(
            events,
            "MY",
            "BNM OpenAPI Overnight Policy Rate (OPR)",
            f"Policy-rate event history forward-filled to daily 252D chart; policy points parsed={len(events)}"
        )

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

    def latest_macro_rate_step(market):
        """
        Build a flat 252D daily step series from latest macro_data.csv Rates value.
        Used only as fallback when official/history fetch fails.
        """
        latest_file = Path("macro_pack_latest/macro_data.csv")
        if not latest_file.exists():
            return pd.DataFrame(columns=COLUMNS)

        try:
            df = pd.read_csv(latest_file)
            df.columns = [str(c).strip().lower() for c in df.columns]

            if not {"market", "indicator", "date", "value"}.issubset(set(df.columns)):
                return pd.DataFrame(columns=COLUMNS)

            df["market"] = df["market"].astype(str).str.upper()
            df["indicator"] = df["indicator"].astype(str).str.title()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")

            aliases = {market.upper()}

            if market.upper() == "US":
                aliases.update({"S&P 500", "NASDAQ", "DJIA"})
            elif market.upper() == "MY":
                aliases.update({"KLSE"})
            elif market.upper() == "HK":
                aliases.update({"HSI"})
            elif market.upper() == "SG":
                aliases.update({"STI"})
            elif market.upper() == "JP":
                aliases.update({"NIKKEI 225"})

            sub = df[
                df["market"].isin(aliases)
                & df["indicator"].eq("Rates")
            ].dropna(subset=["date", "value"]).sort_values("date")

            if sub.empty:
                return pd.DataFrame(columns=COLUMNS)

            latest = sub.iloc[-1]
            idx = pd.date_range(START, TODAY, freq="D")
            flat = pd.DataFrame({
                "date": idx,
                "value": float(latest["value"]),
            })

            return make_rows(
                market,
                flat,
                "macro_data.csv latest Rates fallback",
                "Flat 252D step fallback from latest monthly macro pack Rates value"
            )

        except Exception as e:
            print(f"WARNING: latest macro rate fallback failed for {market}: {e}")
            return pd.DataFrame(columns=COLUMNS)

    def choose_market_result(market, df, min_rows=20):
        """
        Guarded output selector:
        1. Use fetched/seed data if enough rows.
        2. Else preserve existing market history.
        3. Else use latest macro_data.csv flat fallback.
        """
        try:
            if df is not None and not df.empty and len(df) >= min_rows:
                print(f"{market}: accepted {len(df)} rows")
                return df

            if df is not None and not df.empty:
                print(f"WARNING: {market}: only {len(df)} rows; trying preserved/fallback history")
            else:
                print(f"WARNING: {market}: no rows; trying preserved/fallback history")

            preserved = preserve_existing_market(market)
            if preserved is not None and not preserved.empty and len(preserved) >= min_rows:
                print(f"{market}: preserved existing {len(preserved)} rows")
                return preserved

            fallback = latest_macro_rate_step(market)
            if fallback is not None and not fallback.empty:
                print(f"{market}: fallback using {len(fallback)} rows")
                return fallback

            return pd.DataFrame(columns=COLUMNS)

        except Exception as e:
            print(f"WARNING: choose_market_result failed for {market}: {e}")
            return pd.DataFrame(columns=COLUMNS)

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
            selected = choose_market_result(market, df, min_rows=20)
            if selected is not None and not selected.empty:
                results.append(selected)
        except Exception as e:
            print(f"WARNING: {market}: fetch failed: {e}")
            selected = choose_market_result(market, pd.DataFrame(columns=COLUMNS), min_rows=20)
            if selected is not None and not selected.empty:
                results.append(selected)

    # SG: prefer repo seed/existing because live MAS/SORA daily history is unreliable in hosted runtime.
    sg_seed = load_optional_seed_file(
        "SG",
        ["sg_rates_sora_daily.csv", "SG Domestic Interest Rates 2026-06-26.csv"],
        "SG SORA daily seed / repo CSV",
        dayfirst=True,
    )
    sg_selected = choose_market_result("SG", sg_seed, min_rows=20)
    if sg_selected is not None and not sg_selected.empty:
        results.append(sg_selected)
    else:
        print("WARNING: SG: no usable seed/existing/fallback rows found")

    # JP: prefer repo seed/existing because BOJ live history can return only partial rows.
    jp_seed = load_optional_seed_file(
        "JP",
        ["jp_rates_call_overnight_daily.csv", "JP Rates.csv", "jp_rates.csv"],
        "BOJ overnight call rate daily seed / repo CSV",
        dayfirst=False,
    )
    jp_selected = choose_market_result("JP", jp_seed, min_rows=20)
    if jp_selected is not None and not jp_selected.empty:
        results.append(jp_selected)
    else:
        print("WARNING: JP: no usable seed/existing/fallback rows found")

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
