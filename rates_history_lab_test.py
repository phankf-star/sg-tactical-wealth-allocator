#!/usr/bin/env python3
"""
rates_history_lab_test.py

Focused lab test for Global20Engine macro-fetcher rates history design.

Goal
----
Fetch rates history from live/official sources where available, then write:
  macro_pack_latest/rates_history_252d.csv
  macro_pack_latest/rates_history_diagnostics.csv

Design rule
-----------
- Rates are treated as daily where source supports daily observations.
- Keep latest 252 observations per market.
- Policy-rate markets may be represented as policy-step series.
- Base app should read this CSV only; base app should not build rates history itself.

Run from repo root:
  python rates_history_lab_test.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime

import pandas as pd

OUT_DIR = Path("macro_pack_latest")
OUT_DIR.mkdir(parents=True, exist_ok=True)
RATES_OUT = OUT_DIR / "rates_history_252d.csv"
DIAG_OUT = OUT_DIR / "rates_history_diagnostics.csv"

USER_AGENT = "Global20Engine-rates-history-lab/1.0"


def request_text(url: str, headers: dict | None = None, timeout: int = 25) -> tuple[str, str]:
    h = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/csv,text/plain,text/html,*/*",
        "Accept-Encoding": "identity",
    }
    if headers:
        h.update(headers)
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return raw.decode("utf-8-sig", errors="replace"), ""
    except Exception as exc:
        return "", str(exc)


def clean_number(v):
    try:
        if v is None:
            return None
        s = str(v).replace(",", "").replace("%", "").replace("+", "").strip()
        if s in ["", "na", "n.a.", "N.A.", "-", "--", "—", "."]:
            return None
        return float(s)
    except Exception:
        return None


def parse_date(dt_raw, dayfirst=False):
    if not dt_raw or not str(dt_raw).strip():
        return pd.NaT
    s = str(dt_raw).strip()
    if re.fullmatch(r"\d{8}", s):
        return pd.to_datetime(s, format="%Y%m%d", errors="coerce")
    if dayfirst and re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", s):
        return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    return pd.to_datetime(s, errors="coerce", dayfirst=dayfirst)


def mk_row(market, date, value, source, source_type="Official API", frequency="daily", notes=""):
    return {
        "market": market,
        "indicator": "Rates",
        "date": pd.Timestamp(date).strftime("%Y-%m-%d") if pd.notna(date) else "",
        "value": value,
        "unit": "%",
        "source": source,
        "source_type": source_type,
        "frequency": frequency,
        "notes": notes,
    }


def mk_diag(market, adapter, endpoint, status, rows=0, latest="", reason=""):
    return {
        "market": market,
        "adapter": adapter,
        "endpoint": endpoint,
        "status": status,
        "rows": int(rows or 0),
        "latest": latest,
        "reason": reason,
        "tested_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def fetch_us_dgs10():
    market = "US"
    adapter = "FRED DGS10 daily"
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
    txt, err = request_text(url)
    if not txt:
        return [], [mk_diag(market, adapter, url, "failed", reason=err)]
    try:
        df = pd.read_csv(io.StringIO(txt), parse_dates=["DATE"])
        if "DGS10" not in df.columns:
            return [], [mk_diag(market, adapter, url, "failed", reason=f"Columns returned: {list(df.columns)}")]
        df["value"] = pd.to_numeric(df["DGS10"], errors="coerce")
        df = df.dropna(subset=["DATE", "value"]).sort_values("DATE").tail(252)
        rows = [mk_row(market, r.DATE, float(r.value), "FRED DGS10", "Official API", "daily") for r in df.itertuples(index=False)]
        latest = "" if df.empty else f"{df.DATE.iloc[-1].date()}={df.value.iloc[-1]}"
        return rows, [mk_diag(market, adapter, url, "accepted", len(rows), latest)]
    except Exception as exc:
        return [], [mk_diag(market, adapter, url, "failed", reason=str(exc))]


def fetch_hk_hibor():
    market = "HK"
    adapter = "HKMA daily HIBOR"
    url = "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily?pagesize=1000&sortby=end_of_day&sortorder=desc"
    txt, err = request_text(url)
    if not txt:
        return [], [mk_diag(market, adapter, url, "failed", reason=err)]
    try:
        payload = json.loads(txt)
        records = payload.get("result", {}).get("records") or payload.get("result", {}).get("data") or []
        out = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            dt = parse_date(rec.get("end_of_day") or rec.get("date"))
            val = None
            used_key = ""
            for key in ["hibor_1m", "ir_1m", "one_month", "1m", "overnight", "ir_overnight", "value"]:
                if key in rec:
                    val = clean_number(rec.get(key))
                    used_key = key
                    if val is not None:
                        break
            if pd.notna(dt) and val is not None:
                out.append(mk_row(market, dt, val, f"HKMA HIBOR daily ({used_key})", "Official API", "daily"))
        df = pd.DataFrame(out)
        if df.empty:
            return [], [mk_diag(market, adapter, url, "failed", rows=len(records), reason="No recognised daily HIBOR/rate value parsed")]
        df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date_dt"]).sort_values("date_dt").drop_duplicates(["market", "indicator", "date"], keep="last").tail(252)
        rows = df.drop(columns=["date_dt"]).to_dict("records")
        latest = f"{df.date.iloc[-1]}={df.value.iloc[-1]}" if not df.empty else ""
        return rows, [mk_diag(market, adapter, url, "accepted", len(rows), latest)]
    except Exception as exc:
        return [], [mk_diag(market, adapter, url, "failed", reason=str(exc))]


def json_records_from_payload(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for path in [("result", "records"), ("result", "data"), ("data",), ("records",)]:
        cur = payload
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and isinstance(cur, list):
            return cur
    return []


def fetch_my_bnm_opr():
    market = "MY"
    adapter = "BNM OPR policy-step"
    headers = {"Accept": "application/vnd.BNM.API.v1+json"}
    urls = [
        "https://api.bnm.gov.my/public/opr",
        f"https://api.bnm.gov.my/public/opr/year/{pd.Timestamp.today().year}",
        f"https://api.bnm.gov.my/public/opr?year={pd.Timestamp.today().year}",
    ]
    diagnostics = []
    policy_points = []
    for url in urls:
        txt, err = request_text(url, headers=headers)
        if not txt:
            diagnostics.append(mk_diag(market, adapter, url, "failed", reason=err))
            continue
        try:
            records = json_records_from_payload(json.loads(txt))
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                dt_raw = rec.get("date") or rec.get("effective_date") or rec.get("Date")
                dt = parse_date(dt_raw, dayfirst=True)
                val = None
                for key in ["rate", "opr", "OPR", "value"]:
                    if key in rec:
                        val = clean_number(rec.get(key))
                        if val is not None:
                            break
                if pd.notna(dt) and val is not None:
                    policy_points.append((dt, val))
            diagnostics.append(mk_diag(market, adapter, url, "reached", rows=len(records), reason="Parsed candidate policy records"))
        except Exception as exc:
            diagnostics.append(mk_diag(market, adapter, url, "failed", reason=str(exc)))
    if not policy_points:
        diagnostics.append(mk_diag(market, adapter, " | ".join(urls), "failed", reason="No BNM OPR policy points parsed"))
        return [], diagnostics
    policy = pd.DataFrame(policy_points, columns=["date", "value"]).dropna().sort_values("date").drop_duplicates("date", keep="last")
    # Expand to business-day step line for latest 252 business days.
    start = min(policy.date.min(), pd.Timestamp.today() - pd.offsets.BDay(320))
    idx = pd.bdate_range(start=start, end=pd.Timestamp.today().normalize())
    step = policy.set_index("date").reindex(idx).ffill().dropna().tail(252)
    rows = [mk_row(market, dt, float(row.value), "BNM OpenAPI Overnight Policy Rate (OPR)", "Official API", "policy_step", "Expanded to business-day step series from official policy dates") for dt, row in step.iterrows()]
    latest = "" if step.empty else f"{step.index[-1].date()}={step.value.iloc[-1]}"
    diagnostics.append(mk_diag(market, adapter, " | ".join(urls), "accepted", len(rows), latest))
    return rows, diagnostics


def parse_boj_csv(txt):
    out = []
    for raw in csv.reader(io.StringIO(txt)):
        if not raw:
            continue
        date_idx = None
        dt = pd.NaT
        for i, cell in enumerate(raw):
            s = str(cell).strip()
            if not s:
                continue
            if re.fullmatch(r"\d{8}", s):
                cand = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
            elif re.fullmatch(r"\d{6}", s):
                cand = pd.to_datetime(s + "01", format="%Y%m%d", errors="coerce")
            else:
                cand = pd.to_datetime(s, errors="coerce")
            if pd.notna(cand) and 1990 <= cand.year <= pd.Timestamp.today().year + 1:
                date_idx = i
                dt = cand
                break
        if date_idx is None:
            continue
        for cell in raw[date_idx + 1:]:
            val = clean_number(cell)
            if val is not None and -2 <= val <= 25:
                out.append((pd.Timestamp(dt), val))
                break
    return out


def fetch_jp_boj_call_rate():
    market = "JP"
    adapter = "BOJ FM01 STRDCLUCON daily"
    start = (pd.Timestamp.today() - pd.DateOffset(months=18)).strftime("%Y%m")
    diagnostics = []
    for code in ["STRDCLUCON", "STRDCLUCON@D", "FM01.STRDCLUCON", "FM01.STRDCLUCON@D"]:
        url = "https://www.stat-search.boj.or.jp/api/v1/getDataCode?" + urllib.parse.urlencode({
            "format": "csv", "lang": "en", "db": "FM01", "startDate": start, "code": code
        })
        txt, err = request_text(url, headers={"Accept": "text/csv,*/*"})
        if not txt:
            diagnostics.append(mk_diag(market, adapter, url, "failed", reason=err))
            continue
        parsed = parse_boj_csv(txt)
        if parsed:
            df = pd.DataFrame(parsed, columns=["date", "value"]).dropna().sort_values("date").drop_duplicates("date", keep="last").tail(252)
            rows = [mk_row(market, r.date, float(r.value), f"BOJ FM01 STRDCLUCON CSV ({code})", "Official API", "daily") for r in df.itertuples(index=False)]
            latest = "" if df.empty else f"{df.date.iloc[-1].date()}={df.value.iloc[-1]}"
            diagnostics.append(mk_diag(market, adapter, url, "accepted", len(rows), latest))
            return rows, diagnostics
        diagnostics.append(mk_diag(market, adapter, url, "failed", reason="CSV reached but no date/value rows parsed"))
    return [], diagnostics


def fetch_sg_sora_placeholder():
    # Existing production decision uses live redistributor-only path for latest SG SORA.
    # This lab intentionally records the gap: SG daily 252D history requires a validated history source.
    return [], [mk_diag(
        "SG",
        "SG SORA daily history",
        "redistributor/latest-value path",
        "needs_validation",
        rows=0,
        reason="Current production SG SORA adapter is latest-value redistributor-only; daily 252D history source still needs validation.",
    )]


def merge_and_trim(new_rows):
    df_new = pd.DataFrame(new_rows)
    if df_new.empty:
        return df_new
    if RATES_OUT.exists():
        try:
            df_old = pd.read_csv(RATES_OUT)
            df = pd.concat([df_old, df_new], ignore_index=True)
        except Exception:
            df = df_new
    else:
        df = df_new
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["market", "indicator", "date_dt", "value"])
    df = df.sort_values(["market", "indicator", "date_dt"])
    df = df.drop_duplicates(["market", "indicator", "date"], keep="last")
    df = df.groupby(["market", "indicator"], group_keys=False).tail(252)
    df = df.drop(columns=["date_dt"])
    columns = ["market", "indicator", "date", "value", "unit", "source", "source_type", "frequency", "notes"]
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    return df[columns]


def main():
    all_rows = []
    all_diag = []
    for fetcher in [fetch_us_dgs10, fetch_hk_hibor, fetch_my_bnm_opr, fetch_jp_boj_call_rate, fetch_sg_sora_placeholder]:
        rows, diag = fetcher()
        all_rows.extend(rows)
        all_diag.extend(diag)
    final_df = merge_and_trim(all_rows)
    final_df.to_csv(RATES_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame(all_diag).to_csv(DIAG_OUT, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(final_df)} row(s) to {RATES_OUT}")
    print(f"Wrote {len(all_diag)} diagnostic row(s) to {DIAG_OUT}")
    if not final_df.empty:
        print(final_df.groupby("market").size().to_string())


if __name__ == "__main__":
    main()
