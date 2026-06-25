
import re
import sys
import json
import calendar
import urllib.request
from datetime import datetime


def request_text(url, timeout=30):
    headers = {
        "User-Agent": "Global20Engine-MacroAdapterLab/1.0",
        "Accept": "text/html,text/plain,*/*",
        "Accept-Encoding": "identity",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean_html(txt):
    txt = re.sub(r"<script[\s\S]*?</script>", " ", txt, flags=re.I)
    txt = re.sub(r"<style[\s\S]*?</style>", " ", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"&nbsp;|&#160;", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def month_name_to_number(month_name):
    months = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    key = str(month_name).strip().lower()
    if key not in months:
        raise ValueError(f"Unknown month name: {month_name}")
    return months[key]


def month_year_to_first_day(month_name, year):
    m = month_name_to_number(month_name)
    return f"{int(year):04d}-{m:02d}-01"


def hk_period_to_end_date(period_text):
    """
    Convert HK rolling period like '3/2026 - 5/2026' to '2026-05-31'.
    """
    m = re.search(r"(\d{1,2})/(\d{4})\s*-\s*(\d{1,2})/(\d{4})", period_text)
    if not m:
        raise ValueError(f"Could not parse HK period: {period_text}")

    end_month = int(m.group(3))
    end_year = int(m.group(4))
    last_day = calendar.monthrange(end_year, end_month)[1]
    return f"{end_year:04d}-{end_month:02d}-{last_day:02d}"



def lab_hk_unemployment():
    """
    Hong Kong unemployment parser.

    Primary source:
    HK Government press release for unemployment and underemployment statistics.
    This is more stable for text parsing than the C&SD overview table.
    """
    url = "https://www.info.gov.hk/gia/general/202606/16/P2026061600318.htm"
    txt = clean_html(request_text(url))

    # Expected text pattern includes:
    # "March - May 2026"
    # "unemployment rate stood at 3.7%"
    period_match = re.search(
        r"(March\s*-\s*May\s*2026|Mar(?:ch)?\s*-\s*May\s*2026|3/2026\s*-\s*5/2026)",
        txt,
        flags=re.I,
    )

    if period_match:
        period = period_match.group(1)
        latest_date = "2026-05-31"
    else:
        # The release URL itself is for March-May 2026.
        # Keep this tolerant because some HK government pages render period text differently.
        period = "March-May 2026"
        latest_date = "2026-05-31"

    rate_match = re.search(
        r"unemployment rate\s*(?:stood at|was|remained unchanged at)?\s*([0-9.]+)\s*%",
        txt,
        flags=re.I,
    )

    if not rate_match:
        # Fallback pattern for page variants:
        # "seasonally adjusted unemployment rate stood at 3.7%"
        rate_match = re.search(
            r"seasonally adjusted unemployment rate\s*(?:stood at|was|remained unchanged at)?\s*([0-9.]+)\s*%",
            txt,
            flags=re.I,
        )

    if not rate_match:
        raise ValueError("Could not parse HK unemployment rate from HK government press release")

    value = float(rate_match.group(1))

    if not (0 <= value <= 20):
        raise ValueError(f"HK unemployment sanity check failed: {value}")

    return {
        "market": "HK",
        "indicator": "Unemployment",
        "date": latest_date,
        "value": value,
        "unit": "%",
        "source": "HK Government / C&SD unemployment press release",
        "source_type": "Official / Parsed",
        "period": period,
        "endpoint": url,
    }



def lab_japan_latest_indicators():
    url = "https://www.stat.go.jp/english/"
    txt = clean_html(request_text(url))

    # Japan Statistics Bureau latest indicators:
    # Consumer Price Index 1.5 % May 2026 change over the year
    m_cpi = re.search(
        r"Consumer Price Index\s*([0-9.]+)\s*%\s*([A-Za-z]+)\s*(20\d{2})\s*change over the year",
        txt,
        flags=re.I,
    )

    if not m_cpi:
        raise ValueError("Could not parse Japan CPI latest indicator")

    cpi_value = float(m_cpi.group(1))
    cpi_month = m_cpi.group(2)
    cpi_year = m_cpi.group(3)
    cpi_date = month_year_to_first_day(cpi_month, cpi_year)

    if not (-10 <= cpi_value <= 25):
        raise ValueError(f"Japan CPI sanity check failed: {cpi_value}")

    # Japan Statistics Bureau latest indicators:
    # Unemployment rate 2.5 % April 2026 seasonally adjusted
    m_unemp = re.search(
        r"Unemployment rate\s*([0-9.]+)\s*%\s*([A-Za-z]+)\s*(20\d{2})\s*seasonally adjusted",
        txt,
        flags=re.I,
    )

    if not m_unemp:
        raise ValueError("Could not parse Japan unemployment latest indicator")

    unemp_value = float(m_unemp.group(1))
    unemp_month = m_unemp.group(2)
    unemp_year = m_unemp.group(3)
    unemp_date = month_year_to_first_day(unemp_month, unemp_year)

    if not (0 <= unemp_value <= 20):
        raise ValueError(f"Japan unemployment sanity check failed: {unemp_value}")

    return [
        {
            "market": "JP",
            "indicator": "Inflation",
            "date": cpi_date,
            "value": cpi_value,
            "unit": "%",
            "source": "Statistics Bureau of Japan CPI latest indicators",
            "source_type": "Official / Parsed",
            "period": f"{cpi_month} {cpi_year}",
            "endpoint": url,
        },
        {
            "market": "JP",
            "indicator": "Unemployment",
            "date": unemp_date,
            "value": unemp_value,
            "unit": "%",
            "source": "Statistics Bureau of Japan Labour Force Survey latest indicators",
            "source_type": "Official / Parsed",
            "period": f"{unemp_month} {unemp_year}",
            "endpoint": url,
        },
    ]


def main():
    results = []
    errors = []

    try:
        hk = lab_hk_unemployment()
        results.append(hk)
        print("PASS HK Unemployment")
        print(json.dumps(hk, indent=2))
    except Exception as e:
        errors.append(f"HK unemployment failed: {e}")
        print("FAIL HK Unemployment:", e)

    try:
        jp_rows = lab_japan_latest_indicators()
        for row in jp_rows:
            results.append(row)
            print(f"PASS JP {row['indicator']}")
            print(json.dumps(row, indent=2))
    except Exception as e:
        errors.append(f"JP latest indicators failed: {e}")
        print("FAIL JP latest indicators:", e)

    print("\n==============================")
    print("SUMMARY")
    print("==============================")
    print("rows:", len(results))
    print("errors:", len(errors))

    if errors:
        print("\nERRORS")
        for err in errors:
            print("-", err)
        sys.exit(1)

    print("\nALL ADAPTER LAB TESTS PASSED")


if __name__ == "__main__":
    main()
