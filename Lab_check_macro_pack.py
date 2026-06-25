
import pandas as pd
from pathlib import Path

PACK_DIR = Path("macro_pack_latest")
macro_path = PACK_DIR / "macro_data.csv"
diag_path = PACK_DIR / "diagnostics.csv"
manual_path = PACK_DIR / "manual_required.csv"

TARGETS = [
    ("HK", "Unemployment"),
    ("HSI", "Unemployment"),
    ("JP", "Inflation"),
    ("JP", "Unemployment"),
    ("Nikkei 225", "Inflation"),
    ("Nikkei 225", "Unemployment"),
]

EXPECTED = {
    ("HK", "Unemployment"): {
        "expected_value": 3.7,
        "expected_date_hint": "2026-05",
        "reason": "Hong Kong C&SD unemployment rate for 3/2026-5/2026 should be 3.7%",
    },
    ("JP", "Inflation"): {
        "expected_value": 1.5,
        "expected_date_hint": "2026-05",
        "reason": "Latest checked Japan inflation was 1.5% for May 2026",
    },
    ("JP", "Unemployment"): {
        "expected_value": 2.5,
        "expected_date_hint": "2026-04",
        "reason": "Japan unemployment was 2.5% in April 2026; 2.7% was March",
    },
}

def load_csv(path):
    if not path.exists():
        print(f"MISSING: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def show_target_rows(df):
    print("\n==============================")
    print("TARGET ROW CHECK")
    print("==============================")

    if df.empty:
        print("macro_data.csv is empty or missing")
        return

    needed_cols = {"market", "indicator", "date", "value", "unit", "source", "source_type"}
    missing = needed_cols - set(df.columns)
    if missing:
        print("macro_data.csv missing columns:", sorted(missing))
        print("Columns found:", list(df.columns))
        return

    for market, indicator in TARGETS:
        sub = df[
            df["market"].astype(str).str.strip().eq(market)
            & df["indicator"].astype(str).str.strip().eq(indicator)
        ].copy()

        print(f"\n--- {market} / {indicator} ---")

        if sub.empty:
            print("NOT FOUND")
            continue

        print(sub.to_string(index=False))

        key = (market, indicator)
        if key in EXPECTED:
            exp = EXPECTED[key]
            print("EXPECTED:", exp)

def show_duplicates(df):
    print("\n==============================")
    print("DUPLICATE MARKET/INDICATOR CHECK")
    print("==============================")

    if df.empty or not {"market", "indicator"}.issubset(df.columns):
        return

    counts = (
        df.groupby(["market", "indicator"])
        .size()
        .reset_index(name="count")
        .sort_values(["count", "market", "indicator"], ascending=[False, True, True])
    )

    dup = counts[counts["count"] > 1]

    if dup.empty:
        print("No duplicate market/indicator rows.")
    else:
        print("DUPLICATES FOUND:")
        print(dup.to_string(index=False))

def show_diag(diag):
    print("\n==============================")
    print("DIAGNOSTICS CHECK")
    print("==============================")

    if diag.empty:
        print("diagnostics.csv is empty or missing")
        return

    cols = [c for c in ["market", "indicator", "source", "status", "value", "reason", "endpoint"] if c in diag.columns]
    if not cols:
        print("Diagnostics columns not recognised:", list(diag.columns))
        return

    targets = diag[
        diag.get("indicator", "").astype(str).isin(["Inflation", "Unemployment"])
        & diag.get("market", "").astype(str).isin(["HK", "HSI", "JP", "Nikkei 225"])
    ].copy()

    if targets.empty:
        print("No HK/JP inflation/unemployment diagnostics found.")
    else:
        print(targets[cols].to_string(index=False))

def show_manual(manual):
    print("\n==============================")
    print("MANUAL REQUIRED CHECK")
    print("==============================")

    if manual.empty:
        print("manual_required.csv is empty or missing")
        return

    cols = [c for c in ["market", "indicator", "reason"] if c in manual.columns]
    if not cols:
        print("Manual columns not recognised:", list(manual.columns))
        return

    targets = manual[
        manual.get("indicator", "").astype(str).isin(["Inflation", "Unemployment"])
        & manual.get("market", "").astype(str).isin(["HK", "HSI", "JP", "Nikkei 225"])
    ].copy()

    if targets.empty:
        print("No HK/JP inflation/unemployment manual-required rows found.")
    else:
        print(targets[cols].to_string(index=False))

def infer_likely_issue(df):
    print("\n==============================")
    print("LIKELY ISSUE INFERENCE")
    print("==============================")

    if df.empty:
        print("Likely issue: macro pack not generated or macro_data.csv missing.")
        return

    def exists(m, i):
        return not df[
            df["market"].astype(str).str.strip().eq(m)
            & df["indicator"].astype(str).str.strip().eq(i)
        ].empty

    hk_unemp = exists("HK", "Unemployment")
    hsi_unemp = exists("HSI", "Unemployment")
    jp_inf = exists("JP", "Inflation")
    nikkei_inf = exists("Nikkei 225", "Inflation")
    jp_unemp = exists("JP", "Unemployment")
    nikkei_unemp = exists("Nikkei 225", "Unemployment")

    if not hk_unemp and not hsi_unemp:
        print("HK/HSI unemployment row missing from macro pack. Fix g20_macro_fetcher.py generation/call.")
    elif hk_unemp and not hsi_unemp:
        print("HK unemployment exists as market=HK. If HSI dashboard still wrong, check base app mapping HSI -> HK.")
    elif hsi_unemp:
        print("HSI unemployment exists directly. If dashboard still wrong, check duplicate/source priority/date sorting.")

    if not jp_inf and not nikkei_inf:
        print("JP/Nikkei inflation row missing from macro pack. Fix g20_macro_fetcher.py generation/call.")
    elif jp_inf and not nikkei_inf:
        print("JP inflation exists as market=JP. If Nikkei dashboard still wrong, check base app mapping Nikkei 225 -> JP.")
    elif nikkei_inf:
        print("Nikkei inflation exists directly. If dashboard still wrong, check duplicate/source priority/date sorting.")

    if not jp_unemp and not nikkei_unemp:
        print("JP/Nikkei unemployment row missing from macro pack. Fix g20_macro_fetcher.py generation/call.")
    elif jp_unemp and not nikkei_unemp:
        print("JP unemployment exists as market=JP. If Nikkei dashboard still wrong, check base app mapping Nikkei 225 -> JP.")
    elif nikkei_unemp:
        print("Nikkei unemployment exists directly. If dashboard still wrong, check duplicate/source priority/date sorting.")

if __name__ == "__main__":
    macro = load_csv(macro_path)
    diag = load_csv(diag_path)
    manual = load_csv(manual_path)

    print("macro_data path:", macro_path)
    print("macro_data rows:", len(macro))
    print("diagnostics rows:", len(diag))
    print("manual rows:", len(manual))

    show_target_rows(macro)
    show_duplicates(macro)
    show_diag(diag)
    show_manual(manual)
    infer_likely_issue(macro)
