
from pathlib import Path

FETCHER_FILE = Path("g20_macro_fetcher.py")

if not FETCHER_FILE.exists():
    print("Repo root Python files found:")
    for f in sorted(Path(".").glob("*.py")):
        print(" -", f)
    raise FileNotFoundError(f"Fetcher file not found: {FETCHER_FILE}")

print(f"Using fetcher file: {FETCHER_FILE}")

text = FETCHER_FILE.read_text(encoding="utf-8")


# ------------------------------------------------------------
# Helper: insert code before a marker
# ------------------------------------------------------------
def insert_before_marker(text, marker, block, label):
    if block.strip() in text:
        print(f"{label}: already present.")
        return text, False

    idx = text.find(marker)
    if idx == -1:
        print(f"WARNING: marker not found for {label}: {marker}")
        return text, False

    text = text[:idx] + block.rstrip() + "\n\n" + text[idx:]
    print(f"Inserted: {label}")
    return text, True


# ------------------------------------------------------------
# PATCH 1: Add macro_history_12m helpers
# ------------------------------------------------------------
history_helpers = r'''
# ------------------------------------------------------------
# Macro history 12M updater
# Keeps a rolling monthly history for dashboard mini charts.
# Input: latest macro_data.csv rows.
# Output: macro_pack_latest/macro_history_12m.csv
# ------------------------------------------------------------
MACRO_HISTORY_12M_FILE = Path("macro_pack_latest/macro_history_12m.csv")

def _normalise_macro_history_input(df):
    required = ["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"]
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    for c in required:
        if c not in df.columns:
            df[c] = ""

    df["market"] = df["market"].astype(str).str.strip()
    df["indicator"] = df["indicator"].astype(str).str.strip().str.title()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    df = df.dropna(subset=["date", "value"])
    df = df[df["market"].ne("")]
    df = df[df["indicator"].ne("")]

    # Monthly normalisation: one observation per market/indicator/month.
    df["date"] = df["date"].dt.to_period("M").dt.to_timestamp()

    return df[required]


def update_macro_history_12m(latest_macro_df, history_file=MACRO_HISTORY_12M_FILE):
    latest = _normalise_macro_history_input(latest_macro_df)

    # Keep macro indicators only. Claims N/A rows are excluded automatically because value is non-numeric.
    keep_indicators = {"Inflation", "Unemployment", "Jobs", "Rates", "PMI"}
    latest = latest[latest["indicator"].isin(keep_indicators)].copy()

    if history_file.exists():
        try:
            old = pd.read_csv(history_file)
            old = _normalise_macro_history_input(old)
        except Exception:
            old = pd.DataFrame(columns=["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"])
    else:
        old = pd.DataFrame(columns=["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"])

    combined = pd.concat([old, latest], ignore_index=True)

    if combined.empty:
        history_file.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(history_file, index=False)
        print(f"macro_history_12m written: 0 rows -> {history_file}")
        return combined

    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined["value"] = pd.to_numeric(combined["value"], errors="coerce")
    combined = combined.dropna(subset=["date", "value"])

    combined["month"] = combined["date"].dt.to_period("M").astype(str)

    # Latest row wins for the same market / indicator / month.
    combined = combined.sort_values(["market", "indicator", "date"])
    combined = combined.drop_duplicates(["market", "indicator", "month"], keep="last")

    # Rolling 12 months per market + indicator.
    combined = combined.sort_values(["market", "indicator", "date"])
    combined = combined.groupby(["market", "indicator"], group_keys=False).tail(12)

    combined = combined.drop(columns=["month"], errors="ignore")
    combined = combined.sort_values(["market", "indicator", "date"])

    history_file.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(history_file, index=False)

    print(f"macro_history_12m written: {len(combined)} rows -> {history_file}")
    return combined
'''

# Insert before main execution area if common marker exists.
# If marker differs, this still leaves script unchanged and logs warning.
markers = [
    'if __name__ == "__main__":',
    "if __name__ == '__main__':",
]

inserted = False
for marker in markers:
    if marker in text:
        text, inserted = insert_before_marker(text, marker, history_helpers, "macro_history_12m helpers")
        break

if not inserted:
    # Fallback: append at end. Safe because functions are available before explicit call only if call is appended too.
    if history_helpers.strip() not in text:
        text = text.rstrip() + "\n\n" + history_helpers.rstrip() + "\n"
        print("Inserted macro_history_12m helpers at end as fallback.")


# ------------------------------------------------------------
# PATCH 2: Add history update call after macro_data.csv is written
# ------------------------------------------------------------
# This patch searches common macro_data.csv write patterns.
call_block = '''
# Update rolling 12M macro history for dashboard mini charts.
try:
    update_macro_history_12m(macro_data)
except NameError:
    try:
        update_macro_history_12m(macro_df)
    except Exception as e:
        print(f"WARNING: macro_history_12m update skipped: {e}")
except Exception as e:
    print(f"WARNING: macro_history_12m update skipped: {e}")
'''

if "update_macro_history_12m(macro_data)" in text or "update_macro_history_12m(macro_df)" in text:
    print("macro_history_12m update call already present.")
else:
    write_patterns = [
        'macro_data.to_csv("macro_pack_latest/macro_data.csv", index=False)',
        "macro_data.to_csv('macro_pack_latest/macro_data.csv', index=False)",
        'macro_df.to_csv("macro_pack_latest/macro_data.csv", index=False)',
        "macro_df.to_csv('macro_pack_latest/macro_data.csv', index=False)",
        'macro_data.to_csv(MACRO_DATA_FILE, index=False)',
        'macro_df.to_csv(MACRO_DATA_FILE, index=False)',
    ]

    patched_call = False

    for pat in write_patterns:
        idx = text.find(pat)
        if idx != -1:
            line_end = text.find("\n", idx)
            if line_end == -1:
                line_end = idx + len(pat)
            text = text[:line_end + 1] + call_block + text[line_end + 1:]
            print(f"Inserted macro_history_12m update call after: {pat}")
            patched_call = True
            break

    if not patched_call:
        print("WARNING: macro_data.csv write pattern not found. Manual insertion may be required.")


FETCHER_FILE.write_text(text, encoding="utf-8")

print("Patch completed successfully.")
print(f"Updated file: {FETCHER_FILE}")
