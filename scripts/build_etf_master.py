
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "etf_master.csv"
JSON_PATH = ROOT / "data" / "etf_master.json"
REFRESH_PATH = ROOT / "data" / "etf_master_last_refresh.json"

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
    "implementation_fit_score",
    "active",
    "status",
    "cpf_oa_eligible",
    "srs_eligible",
]


def clean_text(value):
    return "" if value is None else str(value).strip()


def parse_eligibility(value):
    value = clean_text(value).upper()
    if value == "TRUE":
        return True
    if value == "FALSE":
        return False
    return None


def parse_bool(value):
    return clean_text(value).upper() == "TRUE"


def parse_float(value, default=0.0):
    try:
        text = clean_text(value).replace(",", "")
        if text == "":
            return default
        return float(text)
    except Exception:
        return default


def parse_int(value, default=999):
    try:
        text = clean_text(value).replace(",", "")
        if text == "":
            return default
        return int(float(text))
    except Exception:
        return default


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing ETF master source: {CSV_PATH}")

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    missing = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
    if missing:
        raise ValueError(f"Missing required ETF master columns: {missing}")

    output = {}

    for row in rows:
        yahoo_symbol = clean_text(row.get("yahoo_symbol"))
        if not yahoo_symbol:
            continue

        enriched = {}

        for key, value in row.items():
            enriched[key] = clean_text(value)

        enriched["rank"] = parse_int(row.get("rank"), 999)
        enriched["implementation_fit_score"] = parse_float(
            row.get("implementation_fit_score"), 0.0
        )
        enriched["active"] = parse_bool(row.get("active"))
        enriched["cpf_oa_eligible"] = parse_eligibility(row.get("cpf_oa_eligible"))
        enriched["srs_eligible"] = parse_eligibility(row.get("srs_eligible"))
        enriched["status"] = clean_text(row.get("status")).upper()

        for numeric_field in [
            "aum",
            "market_cap",
            "turnover",
            "expense_ratio",
            "dividend_yield",
            "premium_discount",
        ]:
            if numeric_field in enriched:
                enriched[numeric_field] = parse_float(row.get(numeric_field), 0.0)

        output[yahoo_symbol] = enriched

    JSON_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    refresh = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": "data/etf_master.csv",
        "generated_file": "data/etf_master.json",
        "records": len(output),
        "status": "generated",
        "ranking_method": "rank_then_implementation_fit_score"
    }

    REFRESH_PATH.write_text(
        json.dumps(refresh, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[OK] ETF master JSON generated. Records: {len(output)}")


if __name__ == "__main__":
    main()
