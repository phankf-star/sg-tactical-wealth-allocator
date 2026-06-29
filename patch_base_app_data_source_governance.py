#!/usr/bin/env python3
# patch_base_app_data_source_governance.py
# Robust base-app macro governance patch.
# Fixes previous failures by avoiding fragile anchors:
# - no dependency on get_pmi_df()
# - no dependency on safe_float()
# - no blind restore from .bak unless backup contains a usable PMI slider candidate
# - broad PMI slider detection across formatting variations
# - compile validation before write

from pathlib import Path
import re
import sys

APP_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sg_tactical_wealth_allocator.py")
BACKUP_PATH = APP_PATH.with_suffix(APP_PATH.suffix + ".bak")
HELPER_MARKER = "# --- Macro Data Governance Helpers ---"

if not APP_PATH.exists():
    raise FileNotFoundError(f"Base app not found: {APP_PATH}")


def read(path):
    return path.read_text(encoding="utf-8")


def write(path, content):
    path.write_text(content, encoding="utf-8")


def has_pmi_slider_candidate(src):
    # Broad detection: any line assigning pmi_in to a Streamlit slider, or any Streamlit slider labelled with PMI.
    return bool(re.search(r"(?im)^\s*pmi_in\s*=\s*st\.slider\s*\(", src)) or bool(
        re.search(r"(?i)st\.slider\s*\([^\n]*(PMI|ISM)", src)
    )


def is_partial_patch(src):
    return HELPER_MARKER in src or "resolve_macro_value" in src or "pmi_source" in src


text = read(APP_PATH)

# Backup governance:
# Create backup only when absent. Restore only when the current file has a partial patch AND backup has a usable PMI slider.
if not BACKUP_PATH.exists():
    write(BACKUP_PATH, text)
    print(f"Created backup: {BACKUP_PATH}")
elif is_partial_patch(text):
    bak_text = read(BACKUP_PATH)
    if has_pmi_slider_candidate(bak_text):
        text = bak_text
        print(f"Restored clean base app from backup: {BACKUP_PATH}")
    else:
        print(f"Backup exists but has no PMI slider candidate; continuing with current app instead of blind restore: {BACKUP_PATH}")

# Preflight: must be a Streamlit + pandas app.
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
            work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
            work = work.sort_values(date_col)

        vals = pd.to_numeric(work[value_col], errors="coerce").dropna()
        if vals.empty:
            return fallback, "fallback_no_numeric_value", source_path

        return float(vals.iloc[-1]), "macro_data.csv", source_path
    except Exception as e:
        return fallback, f"fallback_error:{e}", source_path
# --- End Macro Data Governance Helpers ---
'''

# Inject helpers before first cached function; fallback after import math.
if HELPER_MARKER not in text:
    anchor_match = re.search(r"\n@st\.cache_data\([^\n]*\)\s*\ndef\s+harvest_market\s*\(", text)
    if anchor_match:
        insert_at = anchor_match.start() + 1
        text = text[:insert_at] + HELPERS + "\n" + text[insert_at:]
    else:
        idx = text.find("import math")
        if idx == -1:
            raise RuntimeError("Could not locate helper insertion anchor: harvest_market cache or import math.")
        insert_at = idx + len("import math")
        text = text[:insert_at] + "\n" + HELPERS + text[insert_at:]

# Replace any pmi_in = st.slider(...) line; prefer line containing PMI/ISM, but accept any pmi_in slider.
if "resolve_macro_value(sel_idx, 'PMI', 51.5)" not in text:
    lines = text.splitlines(keepends=True)
    target_idx = None
    for i, line in enumerate(lines):
        if re.search(r"^\s*pmi_in\s*=\s*st\.slider\s*\(", line):
            if re.search(r"PMI|ISM", line, flags=re.I):
                target_idx = i
                break
            if target_idx is None:
                target_idx = i

    if target_idx is None:
        # Diagnostics without failing blindly on a guessed anchor.
        candidates = [ln.strip() for ln in lines if re.search(r"PMI|pmi_in|ISM", ln, flags=re.I)]
        diag = " | ".join(candidates[:8]) if candidates else "no PMI-related lines found"
        raise RuntimeError("Could not locate any 'pmi_in = st.slider(...)' line. PMI diagnostics: " + diag)

    indent = re.match(r"^(\s*)", lines[target_idx]).group(1)
    replacement_lines = [
        f"{indent}pmi_default, pmi_source, pmi_path = resolve_macro_value(sel_idx, 'PMI', 51.5)\n",
        f"{indent}pmi_default = float(min(max(pmi_default if pmi_default is not None else 51.5, 40.0), 60.0))\n",
        f"{indent}pmi_in=st.slider('US ISM PMI',40.0,60.0,pmi_default)\n",
        f"{indent}st.caption(f'📡 PMI source: {{pmi_source}}' + (f' — {{pmi_path}}' if pmi_path else ''))\n",
    ]
    lines[target_idx:target_idx + 1] = replacement_lines
    text = "".join(lines)
else:
    print("PMI slider already patched; skipping PMI replacement.")

text = text.replace("No free API.", "PMI loaded from macro_data.csv when available.")

compile(text, str(APP_PATH), "exec")
write(APP_PATH, text)
print("✅ Base app data-source governance patch applied successfully.")
print(f"Target: {APP_PATH}")
print(f"Backup: {BACKUP_PATH}")
