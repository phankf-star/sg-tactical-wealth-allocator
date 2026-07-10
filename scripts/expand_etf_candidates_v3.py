
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "etf_master.csv"

HEADERS = [
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

DATA_AS_OF = "2026-07-10"
SOURCE = "ETF master v3 candidate expansion"
SOURCE_URL = "internal:cde_etf_v3_candidate_universe"

CPF_FALSE_NOTE = "CPF-OA not marked eligible because this is not verified as a CPFIS-OA instrument in current master scope"
CPF_UNKNOWN_NOTE = "CPF-OA eligibility requires verification before trade"
SRS_NOTE = "SRS eligibility to be verified with broker or platform before trade"


def row(
    market,
    rank,
    role,
    instrument,
    ticker,
    yahoo_symbol,
    exchange,
    currency,
    asset_class,
    use_case,
    cpf_oa="FALSE",
):
    return {
        "market": market,
        "rank": str(rank),
        "role": role,
        "instrument": instrument,
        "ticker": ticker,
        "yahoo_symbol": yahoo_symbol,
        "exchange": exchange,
        "trade_currency": currency,
        "asset_class": asset_class,
        "aum": "",
        "aum_currency": currency,
        "market_cap": "",
        "turnover": "",
        "expense_ratio": "",
        "dividend_yield": "",
        "premium_discount": "",
        "implementation_fit_score": "0",
        "use_case": use_case,
        "cpf_oa_eligible": cpf_oa,
        "srs_eligible": "UNKNOWN",
        "cpf_note": CPF_FALSE_NOTE if cpf_oa == "FALSE" else CPF_UNKNOWN_NOTE,
        "srs_note": SRS_NOTE,
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "data_as_of": DATA_AS_OF,
        "active": "TRUE",
        "status": "ACTIVE",
    }


CANDIDATES = [
    # STI / Singapore
    row("STI", 1, "Core", "SPDR Straits Times Index ETF", "ES3", "ES3.SI", "SGX", "SGD", "Equity", "Broad STI exposure", "TRUE"),
    row("STI", 2, "Core", "Nikko AM Singapore STI ETF", "G3B", "G3B.SI", "SGX", "SGD", "Equity", "Alternative STI exposure", "TRUE"),
    row("STI", 3, "Defensive", "ABF Singapore Bond Index Fund", "A35", "A35.SI", "SGX", "SGD", "Bond", "Singapore bond exposure", "TRUE"),
    row("STI", 4, "Satellite", "Lion-Phillip S-REIT ETF", "CLR", "CLR.SI", "SGX", "SGD", "REIT", "Singapore REIT satellite exposure", "UNKNOWN"),
    row("STI", 5, "Satellite", "NikkoAM-StraitsTrading Asia ex Japan REIT ETF", "CFA", "CFA.SI", "SGX", "SGD", "REIT", "Asia ex Japan REIT satellite exposure", "UNKNOWN"),

    # S&P 500
    row("S&P 500", 1, "Core", "SPDR S&P 500 ETF Trust", "SPY", "SPY", "NYSE Arca", "USD", "Equity", "Broad US large-cap exposure"),
    row("S&P 500", 2, "Core", "Vanguard S&P 500 ETF", "VOO", "VOO", "NYSE Arca", "USD", "Equity", "Low-cost S&P 500 exposure"),
    row("S&P 500", 3, "Core", "iShares Core S&P 500 ETF", "IVV", "IVV", "NYSE Arca", "USD", "Equity", "Broad S&P 500 exposure"),
    row("S&P 500", 4, "Core", "SPDR Portfolio S&P 500 ETF", "SPLG", "SPLG", "NYSE Arca", "USD", "Equity", "Low-cost S&P 500 alternative"),
    row("S&P 500", 5, "Core", "iShares Core S&P 500 UCITS ETF", "CSPX", "CSPX.L", "LSE", "USD", "Equity", "UCITS S&P 500 accumulating exposure"),
    row("S&P 500", 6, "Core", "Vanguard S&P 500 UCITS ETF", "VUAA", "VUAA.L", "LSE", "USD", "Equity", "UCITS S&P 500 accumulating alternative"),
    row("S&P 500", 7, "Core", "iShares S&P 500 UCITS ETF", "IUSA", "IUSA.L", "LSE", "USD", "Equity", "UCITS S&P 500 distributing exposure"),

    # Nasdaq
    row("Nasdaq", 1, "Core", "Invesco QQQ Trust", "QQQ", "QQQ", "NASDAQ", "USD", "Equity", "Nasdaq 100 exposure"),
    row("Nasdaq", 2, "Core", "Invesco NASDAQ 100 ETF", "QQQM", "QQQM", "NASDAQ", "USD", "Equity", "Nasdaq 100 lower-fee alternative"),
    row("Nasdaq", 3, "Core", "iShares NASDAQ 100 UCITS ETF", "CNDX", "CNDX.L", "LSE", "USD", "Equity", "UCITS Nasdaq 100 accumulating exposure"),
    row("Nasdaq", 4, "Core", "Invesco EQQQ NASDAQ-100 UCITS ETF", "EQQQ", "EQQQ.L", "LSE", "USD", "Equity", "UCITS Nasdaq 100 distributing exposure"),
    row("Nasdaq", 5, "Satellite", "Invesco NASDAQ Next Gen 100 ETF", "QQQJ", "QQQJ", "NASDAQ", "USD", "Equity", "Nasdaq next generation satellite exposure"),
    row("Nasdaq", 6, "Satellite", "First Trust NASDAQ-100 Equal Weighted ETF", "QQEW", "QQEW", "NASDAQ", "USD", "Equity", "Equal-weight Nasdaq 100 satellite"),
    row("Nasdaq", 7, "Satellite", "First Trust NASDAQ-100 Technology Sector ETF", "QTEC", "QTEC", "NASDAQ", "USD", "Equity", "Nasdaq technology satellite"),

    # HSI / Hong Kong
    row("HSI", 1, "Core", "Tracker Fund of Hong Kong", "2800", "2800.HK", "HKEX", "HKD", "Equity", "Broad HSI exposure"),
    row("HSI", 2, "Core", "iShares Core Hang Seng Index ETF", "3115", "3115.HK", "HKEX", "HKD", "Equity", "Alternative HSI exposure"),
    row("HSI", 3, "Satellite", "iShares Hang Seng TECH ETF", "3067", "3067.HK", "HKEX", "HKD", "Equity", "Hang Seng technology satellite exposure"),
    row("HSI", 4, "Satellite", "CSOP Hang Seng TECH Index ETF", "3033", "3033.HK", "HKEX", "HKD", "Equity", "Hang Seng technology alternative"),
    row("HSI", 5, "Satellite", "Hang Seng China Enterprises Index ETF", "2828", "2828.HK", "HKEX", "HKD", "Equity", "China enterprises exposure"),
    row("HSI", 6, "Satellite", "iShares FTSE China A50 ETF", "2823", "2823.HK", "HKEX", "HKD", "Equity", "China A50 satellite exposure"),

    # Nikkei / Japan
    row("Nikkei 225", 1, "Core", "NEXT FUNDS Nikkei 225 ETF", "1321", "1321.T", "TSE", "JPY", "Equity", "Nikkei 225 exposure"),
    row("Nikkei 225", 2, "Core", "iShares MSCI Japan ETF", "EWJ", "EWJ", "NYSE Arca", "USD", "Equity", "Broad Japan equity exposure"),
    row("Nikkei 225", 3, "Core", "NEXT FUNDS TOPIX ETF", "1306", "1306.T", "TSE", "JPY", "Equity", "Broad Japan TOPIX exposure"),
    row("Nikkei 225", 4, "Satellite", "WisdomTree Japan Hedged Equity Fund", "DXJ", "DXJ", "NYSE Arca", "USD", "Equity", "Currency-hedged Japan satellite"),
    row("Nikkei 225", 5, "Core", "JPMorgan BetaBuilders Japan ETF", "BBJP", "BBJP", "Cboe", "USD", "Equity", "Broad Japan low-cost exposure"),
    row("Nikkei 225", 6, "Core", "iShares Core Nikkei 225 ETF", "1329", "1329.T", "TSE", "JPY", "Equity", "Nikkei 225 alternative"),

    # KLSE / Malaysia
    row("KLSE", 1, "Core", "FTSE Bursa Malaysia KLCI ETF", "0820EA", "0820EA.KL", "Bursa Malaysia", "MYR", "Equity", "Broad Malaysia exposure"),
    row("KLSE", 2, "Core", "iShares MSCI Malaysia ETF", "EWM", "EWM", "NYSE Arca", "USD", "Equity", "Malaysia USD-listed proxy"),
    row("KLSE", 3, "Satellite", "Franklin FTSE Malaysia ETF", "FLMY", "FLMY", "NYSE Arca", "USD", "Equity", "Malaysia alternative proxy"),

    # A-Share / China
    row("A-Share", 1, "Core", "Xtrackers Harvest CSI 300 China A-Shares ETF", "ASHR", "ASHR", "NYSE Arca", "USD", "Equity", "China A-share exposure"),
    row("A-Share", 2, "Satellite", "KraneShares Bosera MSCI China A 50 Connect ETF", "KBA", "KBA", "NYSE Arca", "USD", "Equity", "China A-share alternative"),
    row("A-Share", 3, "Satellite", "iShares MSCI China A ETF", "CNYA", "CNYA", "Cboe", "USD", "Equity", "MSCI China A exposure"),
    row("A-Share", 4, "Satellite", "VanEck ChiNext ETF", "CNXT", "CNXT", "NYSE Arca", "USD", "Equity", "China growth board satellite"),
    row("A-Share", 5, "Core", "ChinaAMC CSI 300 Index ETF", "3188", "3188.HK", "HKEX", "HKD", "Equity", "HK-listed CSI 300 exposure"),
    row("A-Share", 6, "Core", "CSOP CSI 300 Index ETF", "2822", "2822.HK", "HKEX", "HKD", "Equity", "HK-listed China A-share exposure"),

    # DJIA
    row("DJIA", 1, "Core", "SPDR Dow Jones Industrial Average ETF Trust", "DIA", "DIA", "NYSE Arca", "USD", "Equity", "Blue-chip US exposure"),
    row("DJIA", 2, "Satellite", "iShares Dow Jones US ETF", "IYY", "IYY", "NYSE Arca", "USD", "Equity", "Broad Dow Jones US market proxy"),
    row("DJIA", 3, "Satellite", "SPDR Portfolio Dow Jones Industrial Average ETF", "DJD", "DJD", "NYSE Arca", "USD", "Equity", "Dividend-weighted Dow exposure"),

    # Gold
    row("Gold", 1, "Defensive", "SPDR Gold Shares", "GLD", "GLD", "NYSE Arca", "USD", "Commodity", "Physical gold ETF"),
    row("Gold", 2, "Defensive", "iShares Gold Trust", "IAU", "IAU", "NYSE Arca", "USD", "Commodity", "Lower-cost gold ETF"),
    row("Gold", 3, "Defensive", "abrdn Physical Gold Shares ETF", "SGOL", "SGOL", "NYSE Arca", "USD", "Commodity", "Physical gold alternative"),
    row("Gold", 4, "Defensive", "SPDR Gold MiniShares Trust", "GLDM", "GLDM", "NYSE Arca", "USD", "Commodity", "Low-cost physical gold exposure"),
    row("Gold", 5, "Defensive", "iShares Physical Gold ETC", "SGLN", "SGLN.L", "LSE", "USD", "Commodity", "LSE-listed physical gold exposure"),
    row("Gold", 6, "Satellite", "VanEck Gold Miners ETF", "GDX", "GDX", "NYSE Arca", "USD", "Equity", "Gold miners satellite exposure"),

    # Bitcoin
    row("Bitcoin", 1, "Satellite", "iShares Bitcoin Trust", "IBIT", "IBIT", "NASDAQ", "USD", "Crypto", "Spot Bitcoin ETF"),
    row("Bitcoin", 2, "Satellite", "Fidelity Wise Origin Bitcoin Fund", "FBTC", "FBTC", "Cboe", "USD", "Crypto", "Spot Bitcoin ETF alternative"),
    row("Bitcoin", 3, "Satellite", "ARK 21Shares Bitcoin ETF", "ARKB", "ARKB", "Cboe", "USD", "Crypto", "Spot Bitcoin ETF alternative"),
    row("Bitcoin", 4, "Satellite", "Bitwise Bitcoin ETF", "BITB", "BITB", "NYSE Arca", "USD", "Crypto", "Spot Bitcoin ETF alternative"),
    row("Bitcoin", 5, "Satellite", "Grayscale Bitcoin Trust", "GBTC", "GBTC", "NYSE Arca", "USD", "Crypto", "Bitcoin trust"),
]


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing ETF master CSV: {CSV_PATH}")

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        existing_rows = list(reader)
        fieldnames = reader.fieldnames or HEADERS

    missing = [c for c in HEADERS if c not in fieldnames]
    if missing:
        raise ValueError(f"ETF master CSV missing columns: {missing}")

    by_symbol = {
        str(row.get("yahoo_symbol", "")).strip().upper(): row
        for row in existing_rows
        if str(row.get("yahoo_symbol", "")).strip()
    }

    added = 0
    updated = 0

    for candidate in CANDIDATES:
        key = candidate["yahoo_symbol"].strip().upper()

        if key in by_symbol:
            existing = by_symbol[key]

            # Preserve current rank / score / fetched fields where already present.
            # Only fill missing static descriptors.
            for col in [
                "market",
                "role",
                "instrument",
                "ticker",
                "exchange",
                "trade_currency",
                "asset_class",
                "use_case",
                "cpf_note",
                "srs_note",
                "source",
                "source_url",
                "active",
                "status",
            ]:
                if not str(existing.get(col, "")).strip():
                    existing[col] = candidate[col]
                    updated += 1

            # Do not overwrite CPF TRUE/FALSE decisions already in master.
            if not str(existing.get("cpf_oa_eligible", "")).strip():
                existing["cpf_oa_eligible"] = candidate["cpf_oa_eligible"]
                updated += 1

            if not str(existing.get("srs_eligible", "")).strip():
                existing["srs_eligible"] = candidate["srs_eligible"]
                updated += 1

        else:
            new_row = {h: candidate.get(h, "") for h in fieldnames}
            existing_rows.append(new_row)
            by_symbol[key] = new_row
            added += 1

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)

    print(f"[OK] ETF candidate expansion v3 completed.")
    print(f"[OK] Existing records after expansion: {len(existing_rows)}")
    print(f"[OK] Added new candidate rows: {added}")
    print(f"[OK] Filled missing descriptor fields: {updated}")
    print("[NEXT] Run validate -> refresh_etf_v3_scores -> validate -> build_etf_master")


if __name__ == "__main__":
    main()
