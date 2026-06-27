from pathlib import Path
import io
import json
import urllib.request
import pandas as pd
import numpy as np

OUT_FILE = Path("macro_pack_latest/rates_history_252d.csv")
DIAG_FILE = Path("macro_pack_latest/rates_history_diagnostics.csv")
LOOKBACK_DAYS = 420
OUTPUT_ROWS_PER_MARKET = 252

COLUMNS = ["market", "date", "value", "indicator", "unit", "source", "source_type", "notes"]
DIAG_COLUMNS = ["market", "adapter", "endpoint", "status", "rows", "latest", "reason", "tested_at"]

TODAY = pd.Timestamp.today().normalize()
START = TODAY - pd.Timedelta(days=LOOKBACK_DAYS)
DIAG_ROWS = []


def diag(market, adapter, endpoint, status, rows=0, latest="", reason=""):
    DIAG_ROWS.append({
        "market": market,
        "adapter": adapter,
        "endpoint": endpoint,
        "status": status,
        "rows": int(rows or 0),
        "latest": latest or "",
        "reason": reason or "",
        "tested_at": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    })


def request_text(url, headers=None, timeout=25):
    base_headers = {
        "User-Agent": "Mozilla/5.0 Global20Engine/1.0",
        "Accept": "application/json,text/csv,text/plain,*/*",
        "Accept-Encoding": "identity",
    }
    if headers:
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
        "market": market,
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
    daily = s.reindex(s.index.union(idx)).sort_index().ffill().reindex(idx).bfill()
    df = pd.DataFrame({"date": daily.index, "value": daily.values}).dropna()
    return make_rows(market, df, source, notes)


def fetch_us_dgs10():
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
    try:
        txt = request_text(url, headers={"Accept": "text/csv,*/*"}, timeout=15)
        df = pd.read_csv(io.StringIO(txt))
        out = pd.DataFrame({
            "date": pd.to_datetime(df.get("DATE"), errors="coerce"),
            "value": pd.to_numeric(df.get("DGS10"), errors="coerce"),
        })
        res = make_rows("US", out, "FRED DGS10 daily", "US 10-year Treasury constant maturity yield")
        latest = "" if res.empty else f"{res.iloc[-1]['date']}={res.iloc[-1]['value']}"
        diag("US", "FRED DGS10 daily", url, "accepted" if not res.empty else "failed", len(res), latest, "")
        return res
    except Exception as e:
        diag("US", "FRED DGS10 daily", url, "failed", 0, "", str(e))
        return fetch_us_yahoo_tnx()


def fetch_us_yahoo_tnx():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=1y&interval=1d"
    try:
        txt = request_text(url, headers={"Accept": "application/json,*/*"}, timeout=25)
        payload = json.loads(txt)
        result = payload.get("chart", {}).get("result", [])
        if not result:
            raise ValueError("Yahoo chart result empty")
        r = result[0]
        ts = r.get("timestamp", []) or []
        quote = (r.get("indicators", {}).get("quote", []) or [{}])[0]
        close = quote.get("close", []) or []
        df = pd.DataFrame({
            "date": pd.to_datetime(ts, unit="s", errors="coerce").normalize(),
            "value": pd.to_numeric(close, errors="coerce"),
        })
        # Yahoo ^TNX is conventionally quoted as 10x yield when above 20; keep current values such as 4.37 as-is.
        df["value"] = df["value"].apply(lambda x: x / 10.0 if pd.notna(x) and x > 20 else x)
        res = make_rows("US", df, "Yahoo ^TNX daily fallback", "Fallback when FRED DGS10 times out")
        latest = "" if res.empty else f"{res.iloc[-1]['date']}={res.iloc[-1]['value']}"
        diag("US", "Yahoo ^TNX daily fallback", url, "accepted" if not res.empty else "failed", len(res), latest, "")
        return res
    except Exception as e:
        diag("US", "Yahoo ^TNX daily fallback", url, "failed", 0, "", str(e))
        return pd.DataFrame(columns=COLUMNS)


def fetch_hk_hibor():
    urls = [
        "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily?pagesize=1000&sortby=end_of_day&sortorder=desc",
        "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-endperiod?pagesize=1000&sortby=end_of_month&sortorder=desc",
    ]
    for url in urls:
        try:
            txt = request_text(url)
            payload = json.loads(txt)
            records = payload.get("result", {}).get("records") or payload.get("result", {}).get("data") or []
            rows = []
            for r in records:
                if not isinstance(r, dict):
                    continue
                dt = normalise_date(r.get("end_of_day") or r.get("end_of_month") or r.get("date"))
                val = np.nan
                for k in ["hibor_1m", "ir_1m", "one_month", "1m", "ir_overnight", "overnight", "value"]:
                    if k in r:
                        val = clean_number(r.get(k))
                        if pd.notna(val):
                            break
                if pd.notna(dt) and pd.notna(val):
                    rows.append({"date": dt, "value": val})
            res = make_rows("HK", pd.DataFrame(rows), "HKMA Open API HIBOR daily", "Preferred HKMA HIBOR field used where available")
            latest = "" if res.empty else f"{res.iloc[-1]['date']}={res.iloc[-1]['value']}"
            diag("HK", "HKMA daily HIBOR", url, "accepted" if not res.empty else "failed", len(res), latest, "")
            if not res.empty:
                return res
        except Exception as e:
            diag("HK", "HKMA daily HIBOR", url, "failed", 0, "", str(e))
    return pd.DataFrame(columns=COLUMNS)


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


def fetch_bnm_opr():
    headers = {"Accept": "application/vnd.BNM.API.v1+json"}
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
    for url in urls:
        parsed_here = 0
        try:
            txt = request_text(url, headers=headers)
            records = flatten_json(json.loads(txt))
            for r in records:
                if not isinstance(r, dict):
                    continue
                dt_raw = r.get("date") or r.get("effective_date") or r.get("effectiveDate") or r.get("Date") or r.get("meeting_date") or r.get("year_dt")
                val = np.nan
                for k in ["rate", "opr", "OPR", "value", "new_opr", "overnight_policy_rate", "overnight policy rate"]:
                    if k in r:
                        val = clean_number(r.get(k))
                        if pd.notna(val):
                            break
                if pd.isna(val):
                    for k, v in r.items():
                        kk = str(k).lower()
                        if any(token in kk for token in ["opr", "rate", "value"]):
                            val = clean_number(v)
                            if pd.notna(val):
                                break
                dt = normalise_date(dt_raw, dayfirst=True)
                if pd.notna(dt) and pd.notna(val) and -2 <= float(val) <= 25:
                    rows.append({"date": dt, "value": float(val)})
                    parsed_here += 1
            diag("MY", "BNM OPR policy-step", url, "reached", parsed_here, "", f"Parsed {parsed_here} candidate policy records")
        except Exception as e:
            diag("MY", "BNM OPR policy-step", url, "failed", 0, "", str(e))
    if rows:
        events = pd.DataFrame(rows).drop_duplicates(["date", "value"]).sort_values("date")
        res = daily_step_from_events(events, "MY", "BNM OpenAPI Overnight Policy Rate (OPR)", f"Policy-rate event history forward-filled to daily 252D chart; policy points parsed={len(events)}")
        latest = "" if res.empty else f"{res.iloc[-1]['date']}={res.iloc[-1]['value']}"
        diag("MY", "BNM OPR policy-step", " | ".join(urls[:3]), "accepted" if not res.empty else "failed", len(res), latest, f"Policy points parsed={len(events)}")
        return res
    return pd.DataFrame(columns=COLUMNS)


def load_optional_seed_file(market, candidate_names, source, dayfirst=False):
    paths = []
    for name in candidate_names:
        paths.extend([Path(name), Path("macro_pack_latest") / name, Path("data") / name, Path("manual_seed") / name, Path("macro_seed_inputs") / name])
    existing = [p for p in paths if p.exists()]
    frames = []
    for path in existing:
        try:
            df = pd.read_csv(path)
            df.columns = [str(c).strip().lower() for c in df.columns]
            date_col = next((c for c in ["date", "end_of_day", "time", "period"] if c in df.columns), None)
            value_col = next((c for c in ["value", "rate", "rates", "sora", "opr", "call_rate", "uncollateralized overnight call rate", "close"] if c in df.columns), None)
            if date_col is None:
                for c in df.columns:
                    parsed = pd.to_datetime(df[c], errors="coerce", dayfirst=dayfirst)
                    if parsed.notna().sum() >= max(3, len(df) * 0.5):
                        date_col = c
                        break
            if value_col is None:
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
        except Exception as e:
            print(f"WARNING: Could not load seed {path}: {e}")
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    return make_rows(market, pd.concat(frames, ignore_index=True), source, "Optional repo seed/live rates CSV")


def preserve_existing_market(market):
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
        return make_rows(market, sub[["date", "value"]], "Preserved existing rates_history_252d.csv", "Fallback preserved from previous generated file")
    except Exception as e:
        print(f"WARNING: preserve existing {market} failed: {e}")
        return pd.DataFrame(columns=COLUMNS)


def latest_macro_rate_step(market):
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
        aliases.update({"US": {"S&P 500", "NASDAQ", "DJIA"}, "MY": {"KLSE"}, "HK": {"HSI"}, "SG": {"STI"}, "JP": {"NIKKEI 225"}}.get(market.upper(), set()))
        sub = df[df["market"].isin(aliases) & df["indicator"].eq("Rates")].dropna(subset=["date", "value"]).sort_values("date")
        if sub.empty:
            return pd.DataFrame(columns=COLUMNS)
        latest = sub.iloc[-1]
        idx = pd.date_range(START, TODAY, freq="D")
        flat = pd.DataFrame({"date": idx, "value": float(latest["value"])})
        return make_rows(market, flat, "macro_data.csv latest Rates fallback", "Flat 252D step fallback from latest monthly macro pack Rates value")
    except Exception as e:
        print(f"WARNING: latest macro rate fallback failed for {market}: {e}")
        return pd.DataFrame(columns=COLUMNS)


def choose_market_result(market, df, min_rows=20):
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


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    results = []

    for market, fn in {"US": fetch_us_dgs10, "HK": fetch_hk_hibor, "MY": fetch_bnm_opr}.items():
        try:
            selected = choose_market_result(market, fn(), min_rows=20)
            if selected is not None and not selected.empty:
                results.append(selected)
        except Exception as e:
            print(f"WARNING: {market}: fetch failed: {e}")
            selected = choose_market_result(market, pd.DataFrame(columns=COLUMNS), min_rows=20)
            if selected is not None and not selected.empty:
                results.append(selected)

    sg_seed = load_optional_seed_file("SG", ["sg_rates_sora_daily.csv", "SG Domestic Interest Rates 2026-06-26.csv"], "SG SORA daily seed / repo CSV", dayfirst=True)
    sg_selected = choose_market_result("SG", sg_seed, min_rows=20)
    if sg_selected is not None and not sg_selected.empty:
        results.append(sg_selected)

    jp_seed = load_optional_seed_file("JP", ["jp_rates_call_overnight_daily.csv", "JP Rates.csv", "jp_rates.csv"], "BOJ overnight call rate daily seed / repo CSV", dayfirst=False)
    jp_selected = choose_market_result("JP", jp_seed, min_rows=20)
    if jp_selected is not None and not jp_selected.empty:
        results.append(jp_selected)

    combined = pd.concat(results, ignore_index=True) if results else pd.DataFrame(columns=COLUMNS)
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
    pd.DataFrame(DIAG_ROWS, columns=DIAG_COLUMNS).to_csv(DIAG_FILE, index=False)
    print(f"rates_history_252d written: {len(combined)} rows -> {OUT_FILE}")
    if not combined.empty:
        print(combined.groupby("market").size().to_string())
    print(f"rates_history_diagnostics written: {len(DIAG_ROWS)} rows -> {DIAG_FILE}")


if __name__ == "__main__":
    main()
