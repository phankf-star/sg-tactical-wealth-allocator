
from pathlib import Path
import pandas as pd

LATEST_FILE = Path("macro_pack_latest/macro_data.csv")
HISTORY_FILE = Path("macro_pack_latest/macro_history_12m.csv")

if not LATEST_FILE.exists():
    raise FileNotFoundError(f"Latest macro file not found: {LATEST_FILE}")

latest = pd.read_csv(LATEST_FILE)

required = ["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"]

latest = latest.copy()
latest.columns = [str(c).strip().lower() for c in latest.columns]

for c in required:
    if c not in latest.columns:
        latest[c] = ""

latest["market"] = latest["market"].astype(str).str.strip()
latest["indicator"] = latest["indicator"].astype(str).str.strip().str.title()
latest["date"] = pd.to_datetime(latest["date"], errors="coerce")
latest["value"] = pd.to_numeric(latest["value"], errors="coerce")

latest = latest.dropna(subset=["date", "value"])
latest = latest[latest["market"].ne("")]
latest = latest[latest["indicator"].ne("")]

keep_indicators = {"Inflation", "Unemployment", "Jobs", "Rates", "PMI"}
latest = latest[latest["indicator"].isin(keep_indicators)].copy()

latest["date"] = latest["date"].dt.to_period("M").dt.to_timestamp()

latest = latest[required]

if HISTORY_FILE.exists():
    try:
        old = pd.read_csv(HISTORY_FILE)
        old.columns = [str(c).strip().lower() for c in old.columns]

        for c in required:
            if c not in old.columns:
                old[c] = ""

        old["date"] = pd.to_datetime(old["date"], errors="coerce")
        old["value"] = pd.to_numeric(old["value"], errors="coerce")
        old = old.dropna(subset=["date", "value"])
        old = old[required]
    except Exception:
        old = pd.DataFrame(columns=required)
else:
    old = pd.DataFrame(columns=required)

combined = pd.concat([old, latest], ignore_index=True)

if combined.empty:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(HISTORY_FILE, index=False)
    print(f"macro_history_12m written: 0 rows -> {HISTORY_FILE}")
    raise SystemExit(0)

combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
combined["value"] = pd.to_numeric(combined["value"], errors="coerce")
combined = combined.dropna(subset=["date", "value"])

combined["month"] = combined["date"].dt.to_period("M").astype(str)

combined = combined.sort_values(["market", "indicator", "date"])
combined = combined.drop_duplicates(["market", "indicator", "month"], keep="last")

combined = combined.sort_values(["market", "indicator", "date"])
combined = combined.groupby(["market", "indicator"], group_keys=False).tail(12)

combined = combined.drop(columns=["month"], errors="ignore")
combined = combined.sort_values(["market", "indicator", "date"])

HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
combined.to_csv(HISTORY_FILE, index=False)

print(f"macro_history_12m written: {len(combined)} rows -> {HISTORY_FILE}")
