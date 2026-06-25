
import json
import urllib.request
import pandas as pd
import io

def request_text(url, timeout=25):
    headers = {
        "User-Agent": "Global20Engine/1.0",
        "Accept": "application/json,text/csv,text/plain,*/*",
        "Accept-Encoding": "identity",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8-sig", errors="replace")

def parse_my_inflation_df(df, source):
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    if "date" not in df.columns:
        raise ValueError(f"{source}: missing date column")

    if "inflation_yoy" not in df.columns:
        raise ValueError(f"{source}: missing inflation_yoy column")

    if "division" in df.columns:
        df = df[df["division"].astype(str).str.lower().str.strip().eq("overall")].copy()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["inflation_yoy"] = pd.to_numeric(df["inflation_yoy"], errors="coerce")
    df = df.dropna(subset=["date", "inflation_yoy"]).sort_values("date")

    if df.empty:
        raise ValueError(f"{source}: no usable overall inflation rows")

    latest = df.iloc[-1]
    return {
        "source": source,
        "date": latest["date"].strftime("%Y-%m-%d"),
        "month_label": latest["date"].strftime("%b %Y"),
        "inflation_yoy": float(latest["inflation_yoy"]),
    }

def test_opendosm_my_inflation():
    tests = []

    # API candidates
    for dataset_id in ["cpi_2d_inflation", "cpi_headline_inflation"]:
        url = f"https://api.data.gov.my/opendosm?id={dataset_id}&limit=50000"
        try:
            txt = request_text(url)
            payload = json.loads(txt)

            if isinstance(payload, list):
                records = payload
            elif isinstance(payload, dict):
                records = (
                    payload.get("data")
                    or payload.get("records")
                    or payload.get("result", {}).get("records")
                    or []
                )
            else:
                records = []

            if records:
                result = parse_my_inflation_df(pd.DataFrame(records), f"OpenDOSM API {dataset_id}")
                tests.append(("PASS", url, result))
            else:
                tests.append(("FAIL", url, "No records returned"))
        except Exception as e:
            tests.append(("FAIL", url, str(e)))

    # Official CSV fallback
    csv_url = "https://storage.dosm.gov.my/cpi/cpi_2d_inflation.csv"
    try:
        txt = request_text(csv_url)
        df = pd.read_csv(io.StringIO(txt))
        result = parse_my_inflation_df(df, "OpenDOSM storage CSV cpi_2d_inflation")
        tests.append(("PASS", csv_url, result))
    except Exception as e:
        tests.append(("FAIL", csv_url, str(e)))

    return tests

if __name__ == "__main__":
    for status, url, result in test_opendosm_my_inflation():
        print(status, url, result)
