
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "etf_master.csv"

REQUIRED_COLUMNS = [
    "ticker",
    "exchange",
    "yahoo_symbol",
    "etf_name",
    "asset_class",
    "region",
    "market",
    "trade_currency",
    "cpf_oa_eligible",
    "srs_eligible",
    "status",
]

ALLOWED_ELIGIBILITY = {"TRUE", "FALSE", "UNKNOWN"}
ALLOWED_STATUS = {"ACTIVE", "WATCH", "DELISTED", "MANUAL_REVIEW"}


def fail(message: str) -> None:
    print(f"[ETF MASTER VALIDATION ERROR] {message}")
    sys.exit(1)


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
        ticker = row.get("ticker", "").strip()
        exchange = row.get("exchange", "").strip()
        yahoo_symbol = row.get("yahoo_symbol", "").strip()
        cpf_value = row.get("cpf_oa_eligible", "").strip().upper()
        srs_value = row.get("srs_eligible", "").strip().upper()
        status = row.get("status", "").strip().upper()

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

        if cpf_value not in ALLOWED_ELIGIBILITY:
            fail(
                f"Row {i}: cpf_oa_eligible must be TRUE, FALSE, or UNKNOWN. "
                f"Found: {cpf_value}"
            )

        if srs_value not in ALLOWED_ELIGIBILITY:
            fail(
                f"Row {i}: srs_eligible must be TRUE, FALSE, or UNKNOWN. "
                f"Found: {srs_value}"
            )

        if status not in ALLOWED_STATUS:
            fail(
                f"Row {i}: status must be one of {sorted(ALLOWED_STATUS)}. "
                f"Found: {status}"
            )

    print(f"[OK] ETF master validation passed. Records: {len(rows)}")


if __name__ == "__main__":
    main()

