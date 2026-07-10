
import csv
import json
import math
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "etf_master.csv"
CONFIG_PATH = ROOT / "data" / "etf_config.json"

DEFAULT_WEIGHTS = {
    "liquidity": 0.30,
    "aum": 0.25,
    "expense_ratio": 0.20,
    "market_fit": 0.15,
    "data_availability": 0.10,
}

REQUIRED_COLUMNS = [
    "market",
    "rank",
    "role",
    "instrument",
    "ticker",
    "yahoo_symbol",
    "exchange",
    "trade_currency",
    "asset_class",
    "aum",
    "aum_currency",
    "market_cap",
    "turnover",
    "expense_ratio",
    "dividend_yield",
    "premium_discount",
    "implementation_fit_score",
    "use_case",
    "cpf_oa_eligible",
    "srs_eligible",
    "cpf_note",
    "srs_note",
    "source",
    "source_url",
    "data_as_of",
    "active",
    "status",
]


def clean_text(value):
    return "" if value is None else str(value).strip()


def parse_float(value, default=0.0):
    try:
        text = clean_text(value).replace(",", "")
        if text == "":
            return default
        return float(text)
    except Exception:
        return default


def parse_bool_text(value):
    return clean_text(value).upper() == "TRUE"


def load_config():
    if not CONFIG_PATH.exists():
        return {
            "max_options_per_market": 10,
            "ranking_method": "rank_then_implementation_fit_score",
            "score_weights": DEFAULT_WEIGHTS,
        }

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"score_weights": DEFAULT_WEIGHTS}

        weights = data.get("score_weights", DEFAULT_WEIGHTS)
        if not isinstance(weights, dict):
            weights = DEFAULT_WEIGHTS

        merged = dict(data)
        merged["score_weights"] = {**DEFAULT_WEIGHTS, **weights}
        return merged
    except Exception:
        return {"score_weights": DEFAULT_WEIGHTS}


def yahoo_chart_fetch(symbol):
    """
    Lightweight Yahoo chart fetch using standard library only.
    Returns latest price, latest volume, average volume over available period.

    Missing data is not fatal; caller assigns lower data-availability score.
    """
    symbol = clean_text(symbol)
    if not symbol:
        return {
            "price": None,
            "latest_volume": None,
            "avg_volume": None,
            "ok": False,
            "reason": "blank symbol",
        }

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.request.pathname2url(symbol)
        + "?range=3mo&interval=1d"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 ETFMasterV3/1.0",
        "Accept": "application/json,text/plain,*/*",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        result = payload.get("chart", {}).get("result", [])
        if not result:
            return {
                "price": None,
                "latest_volume": None,
                "avg_volume": None,
                "ok": False,
                "reason": "empty Yahoo result",
            }

        meta = result[0].get("meta", {}) or {}
        quote = result[0].get("indicators", {}).get("quote", [{}])[0] or {}

        closes = [x for x in quote.get("close", []) if isinstance(x, (int, float))]
        volumes = [x for x in quote.get("volume", []) if isinstance(x, (int, float))]

        price = meta.get("regularMarketPrice")
        if price is None and closes:
            price = closes[-1]

        latest_volume = volumes[-1] if volumes else None
        avg_volume = statistics.mean(volumes) if volumes else None

        return {
            "price": float(price) if price is not None else None,
            "latest_volume": float(latest_volume) if latest_volume is not None else None,
            "avg_volume": float(avg_volume) if avg_volume is not None else None,
            "ok": price is not None,
            "reason": "",
        }

    except Exception as e:
        return {
            "price": None,
            "latest_volume": None,
            "avg_volume": None,
            "ok": False,
            "reason": str(e)[:160],
        }


def percentile_score(value, values):
    """
    Convert value into 0-100 percentile score within available market peer group.
    """
    value = parse_float(value, 0.0)
    values = [parse_float(v, 0.0) for v in values if parse_float(v, 0.0) > 0]

    if value <= 0 or not values:
        return 35.0

    values = sorted(values)
    below = sum(1 for v in values if v <= value)
    return max(35.0, min(100.0, below / len(values) * 100.0))


def expense_score(expense_ratio):
    """
    Lower expense ratio = higher score.
    If missing/zero, use neutral score because many current seed rows are blank.
    """
    er = parse_float(expense_ratio, 0.0)

    if er <= 0:
        return 60.0
    if er <= 0.05:
        return 100.0
    if er <= 0.10:
        return 95.0
    if er <= 0.20:
        return 85.0
    if er <= 0.35:
        return 75.0
    if er <= 0.60:
        return 60.0
    if er <= 1.00:
        return 45.0
    return 30.0


def market_fit_score(row):
    """
    Manual implementation relevance layer.
    This is intentionally light-touch and transparent.
    """
    role = clean_text(row.get("role")).lower()
    use_case = clean_text(row.get("use_case")).lower()
    asset_class = clean_text(row.get("asset_class")).lower()

    score = 75.0

    if role == "core":
        score += 15
    elif role == "defensive":
        score += 8
    elif role == "satellite":
        score += 4

    if "broad" in use_case or "core" in use_case:
        score += 6

    if asset_class in {"equity", "bond", "commodity", "crypto"}:
        score += 2

    return max(0.0, min(100.0, score))


def data_availability_score(row, market_fetch):
    score = 0.0

    if market_fetch.get("ok"):
        score += 45
    if parse_float(market_fetch.get("avg_volume"), 0.0) > 0:
        score += 25
    if parse_float(row.get("aum"), 0.0) > 0:
        score += 10
    if parse_float(row.get("expense_ratio"), 0.0) > 0:
        score += 10
    if parse_float(row.get("dividend_yield"), 0.0) > 0:
        score += 5
    if clean_text(row.get("data_as_of")):
        score += 5

    return max(20.0, min(100.0, score))


def calculate_score(row, market_fetch, peer_context, weights):
    liquidity = percentile_score(
        market_fetch.get("avg_volume"),
        peer_context.get("avg_volumes", []),
    )

    aum = percentile_score(
        row.get("aum"),
        peer_context.get("aums", []),
    )

    expense = expense_score(row.get("expense_ratio"))
    fit = market_fit_score(row)
    data_score = data_availability_score(row, market_fetch)

    total = (
        liquidity * weights.get("liquidity", 0.30)
        + aum * weights.get("aum", 0.25)
        + expense * weights.get("expense_ratio", 0.20)
        + fit * weights.get("market_fit", 0.15)
        + data_score * weights.get("data_availability", 0.10)
    )

    return round(max(0.0, min(100.0, total)), 1)


def main():
    config = load_config()
    weights = config.get("score_weights", DEFAULT_WEIGHTS)

    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing ETF master CSV: {CSV_PATH}")

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise ValueError(f"ETF master CSV missing columns: {missing}")

    # Fetch market data.
    fetch_cache = {}

    for row in rows:
        symbol = clean_text(row.get("yahoo_symbol")) or clean_text(row.get("ticker"))
        active = parse_bool_text(row.get("active"))
        status = clean_text(row.get("status")).upper()

        if active and status == "ACTIVE":
            fetch_cache[symbol] = yahoo_chart_fetch(symbol)
            time.sleep(0.15)
        else:
            fetch_cache[symbol] = {
                "price": None,
                "latest_volume": None,
                "avg_volume": None,
                "ok": False,
                "reason": "inactive",
            }

    # Build peer groups by market.
    market_context = {}

    for row in rows:
        market = clean_text(row.get("market"))
        symbol = clean_text(row.get("yahoo_symbol")) or clean_text(row.get("ticker"))
        fetch = fetch_cache.get(symbol, {})

        market_context.setdefault(market, {"avg_volumes": [], "aums": []})

        avg_volume = parse_float(fetch.get("avg_volume"), 0.0)
        if avg_volume > 0:
            market_context[market]["avg_volumes"].append(avg_volume)

        aum = parse_float(row.get("aum"), 0.0)
        if aum > 0:
            market_context[market]["aums"].append(aum)

    # Score active rows.
    now_date = datetime.now(timezone.utc).date().isoformat()

    for row in rows:
        symbol = clean_text(row.get("yahoo_symbol")) or clean_text(row.get("ticker"))
        market = clean_text(row.get("market"))
        fetch = fetch_cache.get(symbol, {})

        active = parse_bool_text(row.get("active"))
        status = clean_text(row.get("status")).upper()

        if active and status == "ACTIVE":
            score = calculate_score(
                row=row,
                market_fetch=fetch,
                peer_context=market_context.get(market, {}),
                weights=weights,
            )
            row["implementation_fit_score"] = str(score)

            avg_volume = parse_float(fetch.get("avg_volume"), 0.0)
            latest_volume = parse_float(fetch.get("latest_volume"), 0.0)

            # Use turnover column as average volume proxy for now.
            # Later we can split into avg_volume / value_traded if needed.
            if avg_volume > 0:
                row["turnover"] = str(round(avg_volume, 0))

            if latest_volume > 0 and parse_float(row.get("market_cap"), 0.0) <= 0:
                # Keep market_cap untouched if already manually supplied.
                row["market_cap"] = clean_text(row.get("market_cap"))

            row["data_as_of"] = now_date

        else:
            row["implementation_fit_score"] = clean_text(
                row.get("implementation_fit_score")
            ) or "0"

    # Re-rank within each market.
    grouped = {}

    for row in rows:
        market = clean_text(row.get("market"))
        grouped.setdefault(market, []).append(row)

    for market, group in grouped.items():
        active_group = [
            r
            for r in group
            if parse_bool_text(r.get("active"))
            and clean_text(r.get("status")).upper() == "ACTIVE"
        ]

        active_group.sort(
            key=lambda r: (
                -parse_float(r.get("implementation_fit_score"), 0.0),
                parse_float(r.get("rank"), 999),
                clean_text(r.get("instrument")),
            )
        )

        for idx, row in enumerate(active_group, start=1):
            row["rank"] = str(idx)

    # Preserve column order.
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] ETF v3 scores refreshed. Records: {len(rows)}")
    print("[OK] Ranking method: implementation_fit_score then rank within market")
    print("[NOTE] AUM / expense ratio / dividend yield remain manual unless supplied in CSV.")


if __name__ == "__main__":
    main()

