#!/usr/bin/env python3
# patch_base_app_data_source_governance.py
# Robust replacement patch for sg_tactical_wealth_allocator.py
# - Restores from .bak when a previous partial governance patch is detected
# - Injects macro helpers using stable top-level anchors, not safe_float/get_pmi_df
# - Replaces the hardcoded PMI slider only
# - Performs preflight checks and compile validation before saving

from pathlib import Path
import re
import sys

APP_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sg_tactical_wealth_allocator.py")
BACKUP_PATH = APP_PATH.with_suffix(APP_PATH.suffix + ".bak")
HELPER_MARKER = "# --- Macro Data Governance Helpers ---"

if not APP_PATH.exists():
    raise FileNotFoundError(f"Base app not found: {APP_PATH}")

text = APP_PATH.read_text(encoding="utf-8")

# If a previous partial patch exists, restore clean base before re-patching.
if BACKUP_PATH.exists() and (HELPER_MARKER in text or "pmi_source" in text or "resolve_macro_value" in text):
    clean = BACKUP_PATH.read_text(encoding="utf-8")
    if clean.strip():
        text = clean
        print(f"Restored clean base app from backup: {BACKUP_PATH}")
else:
    if not BACKUP_PATH.exists():
        BACKUP_PATH.write_text(text, encoding="utf-8")
        print(f"Created backup: {BACKUP_PATH}")

original = text

# Preflight: current base app should have Streamlit and pandas imports.
if "import streamlit as st" not in text:
    raise RuntimeError("Preflight failed: app does not contain 'import streamlit as st'.")
if "import pandas as pd" not in text:
    raise RuntimeError("Preflight failed: app does not contain 'import pandas as pd'.")

HELPERS = r'''
# --- Macro Data Governance Helpers ---
@st.cache_data(ttl=3600)
def load_macro_data():
    possible_paths = [
        "macro_data.csv",
        "data/macro_data.csv",
        "macro_pack_latest/macro_data.csv",
        "docs/macro_data.csv",
    ]
    for p in possible_paths:
        try:
            df = pd.read_csv(p)
            if not df.empty:
                df.columns = [str(c).strip() for c in df.columns]
                return df, p
        except Exception:
            pass
    return pd.DataFrame(), None


def _pick_col(df, candidates):
    lower_map = {str(c).strip().lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    for col in df.columns:
        col_l = str(col).strip().lower()
        if any(c.lower() in col_l for c in candidates):
            return col
    return None


def resolve_macro_value(index_label, indicator, fallback=None):
    df, source_path = load_macro_data()
    if df.empty:
        return fallback, "fallback", None

    market_col = _pick_col(df, ["market", "country", "region", "index_label", "economy"])
    indicator_col = _pick_col(df, ["indicator", "metric", "name", "series", "field"])
    value_col = _pick_col(df, ["value", "latest_value", "actual", "observation", "last", "latest"])
    date_col = _pick_col(df, ["date", "latest_date", "as_of", "period", "timestamp"])

    if value_col is None:
        return fallback, "fallback_no_value_col", source_path

    try:
        work = df.copy()

        if indicator_col is not None:
            matched = work[work[indicator_col].astype(str).str.contains(indicator, case=False, na=False)]
            if not matched.empty:
                work = matched

        if market_col is not None:
            label = str(index_label)
            scoped = pd.DataFrame()
            if any(x in label for x in ["US", "S&P", "Nasdaq"]):
                scoped = work[work[market_col].astype(str).str.contains("US|United States|S&P|Nasdaq", case=False, na=False)]
            elif "Singapore" in label or "Straits" in label or "STI" in label:
                scoped = work[work[market_col].astype(str).str.contains("SG|Singapore|STI", case=False, na=False)]
            elif "Hong Kong" in label or "Hang Seng" in label or "HK" in label:
                scoped = work[work[market_col].astype(str).str.contains("HK|Hong Kong|Hang Seng", case=False, na=False)]
            if not scoped.empty:
                work = scoped

        if work.empty:
            return fallback, "fallback_no_matching_rows", source_path

        if date_col is not None:
            work[date_col] = pd.to_datetime(work[date_col], errors="coerce", dayfirst=False)
            work = work.sort_values(date_col)

        vals = pd.to_numeric(work[value_col], errors="coerce").dropna()
        if vals.empty:
            return fallback, "fallback_no_numeric_value", source_path

        return float(vals.iloc[-1]), "macro_data.csv", source_path
    except Exception as e:
        return fallback, f"fallback_error:{e}", source_path
# --- End Macro Data Governance Helpers ---
'''

# Inject helpers before first cached data function; this is more stable than safe_float anchoring.
if HELPER_MARKER not in text:
    anchor_match = re.search(r"\n@st\.cache_data\(ttl=14400\)\s*\ndef\s+harvest_market\s*\(", text)
    if anchor_match:
        insert_at = anchor_match.start() + 1
        text = text[:insert_at] + HELPERS + "\n" + text[insert_at:]
    else:
        # fallback: insert after the import block, before first sidebar/app logic
        import_anchor = "import math"
        idx = text.find(import_anchor)
        if idx == -1:
            raise RuntimeError("Could not locate stable insertion anchor: harvest_market cache or import math.")
        insert_at = idx + len(import_anchor)
        text = text[:insert_at] + "\n" + HELPERS + text[insert_at:]

# Replace hardcoded PMI slider inside `with r2c1:` block.
pmipattern = re.compile(
    r"(?P<indent>\s*)pmi_in\s*=\s*st\.slider\(\s*['\"]US ISM PMI['\"]\s*,\s*40\.0\s*,\s*60\.0\s*,\s*51\.5\s*\)",
    re.MULTILINE,
)

if "resolve_macro_value(sel_idx, 'PMI', 51.5)" not in text:
    m = pmipattern.search(text)
    if not m:
        raise RuntimeError("Could not locate hardcoded US ISM PMI slider. Restore clean base app and rerun.")
    indent = m.group("indent")
    replacement = (
        f"{indent}pmi_default, pmi_source, pmi_path = resolve_macro_value(sel_idx, 'PMI', 51.5)\n"
        f"{indent}pmi_default = float(min(max(pmi_default if pmi_default is not None else 51.5, 40.0), 60.0))\n"
        f"{indent}pmi_in=st.slider('US ISM PMI',40.0,60.0,pmi_default)\n"
        f"{indent}st.caption(f'📡 PMI source: {{pmi_source}}' + (f' — {{pmi_path}}' if pmi_path else ''))"
    )
    text = text[:m.start()] + replacement + text[m.end():]
else:
    print("PMI slider already patched; skipping PMI replacement.")

# Update PMI placeholder copy only; leave UI container unchanged.
text = text.replace("No free API.", "PMI loaded from macro_data.csv when available.")

# Syntax validation before write.
compile(text, str(APP_PATH), "exec")

APP_PATH.write_text(text, encoding="utf-8")
print("✅ Base app data-source governance patch applied successfully.")
print(f"Target: {APP_PATH}")
print(f"Backup: {BACKUP_PATH}")
