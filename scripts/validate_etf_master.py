
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "etf_master.csv"

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

ALLOWED_ELIGIBILITY = {"TRUE", "FALSE", "UNKNOWN"}
ALLOWED_ACTIVE = {"TRUE", "FALSE"}
ALLOWED_STATUS = {"ACTIVE", "WATCH", "DELISTED", "MANUAL_REVIEW"}


def fail(message: str) -> None:
    print(f"[ETF MASTER VALIDATION ERROR] {message}")
    sys.exit(1)


def parse_number(value, row_no, field_name):
    try:
        return float(str(value).strip())
    except Exception:
        fail(f"Row {row_no}: {field_name} must be numeric. Found: {value}")


def main() -> None:
    if not CSV_PATH.exists():
        fail(f"Missing file: {CSV_PATH}")

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    missing = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
    if missing:
        fail(f"Missing required columns: {missing}")

    if not rows:
        fail("ETF master CSV has no data rows.")

    seen_yahoo = set()
    seen_ticker_exchange = set()

    for i, row in enumerate(rows, start=2):
        market = row.get("market", "").strip()
        ticker = row.get("ticker", "").strip()
        exchange = row.get("exchange", "").strip()
        yahoo_symbol = row.get("yahoo_symbol", "").strip()
        active = row.get("active", "").strip().upper()
        status = row.get("status", "").strip().upper()
        cpf_value = row.get("cpf_oa_eligible", "").strip().upper()
        srs_value = row.get("srs_eligible", "").strip().upper()

        if not market:
            fail(f"Row {i}: market is blank.")

        if not ticker:
            fail(f"Row {i}: ticker is blank.")

        if not exchange:
            fail(f"Row {i}: exchange is blank.")

        if not yahoo_symbol:
            fail(f"Row {i}: yahoo_symbol is blank.")

        if yahoo_symbol in seen_yahoo:
            fail(f"Row {i}: duplicate yahoo_symbol found: {yahoo_symbol}")
        seen_yahoo.add(yahoo_symbol)

        ticker_exchange_key = f"{ticker}|{exchange}"
        if ticker_exchange_key in seen_ticker_exchange:
            fail(f"Row {i}: duplicate ticker/exchange found: {ticker_exchange_key}")
        seen_ticker_exchange.add(ticker_exchange_key)

        rank = parse_number(row.get("rank"), i, "rank")
        if rank < 0:
            fail(f"Row {i}: rank cannot be negative.")

        score = parse_number(row.get("implementation_fit_score"), i, "implementation_fit_score")
        if score < 0 or score > 100:
            fail(f"Row {i}: implementation_fit_score must be between 0 and 100.")

        if active not in ALLOWED_ACTIVE:
            fail(f"Row {i}: active must be TRUE or FALSE. Found: {active}")

        if cpf_value not in ALLOWED_ELIGIBILITY:
            fail(f"Row {i}: cpf_oa_eligible must be TRUE, FALSE, or UNKNOWN. Found: {cpf_value}")

        if srs_value not in ALLOWED_ELIGIBILITY:
            fail(f"Row {i}: srs_eligible must be TRUE, FALSE, or UNKNOWN. Found: {srs_value}")

        if status not in ALLOWED_STATUS:
            fail(f"Row {i}: status must be one of {sorted(ALLOWED_STATUS)}. Found: {status}")

    print(f"[OK] ETF master validation passed. Records: {len(rows)}")


if __name__ == "__main__":
    main()
