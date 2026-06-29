#!/usr/bin/env python3
# patch_base_app_data_source_governance.py
# Purpose: safely patch sg_tactical_wealth_allocator.py to resolve PMI from macro_data.csv.

from pathlib import Path
import re

APP_PATH = Path('sg_tactical_wealth_allocator.py')
BACKUP_PATH = Path('sg_tactical_wealth_allocator.py.bak')

if not APP_PATH.exists():
    raise FileNotFoundError(f'Base app not found: {APP_PATH}')

text = APP_PATH.read_text(encoding='utf-8')
original = text

if not BACKUP_PATH.exists():
    BACKUP_PATH.write_text(text, encoding='utf-8')

HELPER_MARKER = '# --- Macro Data Governance Helpers ---'
HELPERS = r'''
# --- Macro Data Governance Helpers ---
@st.cache_data(ttl=3600)
def load_macro_data():
    possible_paths = [
        'macro_data.csv',
        'data/macro_data.csv',
        'macro_pack_latest/macro_data.csv',
        'docs/macro_data.csv',
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
        return fallback, 'fallback', None

    market_col = _pick_col(df, ['market', 'country', 'region', 'index_label', 'economy'])
    indicator_col = _pick_col(df, ['indicator', 'metric', 'name', 'series'])
    value_col = _pick_col(df, ['value', 'latest_value', 'actual', 'observation', 'last'])
    date_col = _pick_col(df, ['date', 'latest_date', 'as_of', 'period', 'timestamp'])

    if value_col is None:
        return fallback, 'fallback', source_path

    try:
        work = df.copy()
        if indicator_col is not None:
            work = work[work[indicator_col].astype(str).str.contains(indicator, case=False, na=False)]

        if market_col is not None:
            label = str(index_label)
            if any(x in label for x in ['US', 'S&P', 'Nasdaq']):
                scoped = work[work[market_col].astype(str).str.contains('US|United States|S&P|Nasdaq', case=False, na=False)]
                if not scoped.empty:
                    work = scoped
            elif 'Singapore' in label or 'Straits' in label or 'STI' in label:
                scoped = work[work[market_col].astype(str).str.contains('SG|Singapore|STI', case=False, na=False)]
                if not scoped.empty:
                    work = scoped
            elif 'Hong Kong' in label or 'Hang Seng' in label or 'HK' in label:
                scoped = work[work[market_col].astype(str).str.contains('HK|Hong Kong|Hang Seng', case=False, na=False)]
                if not scoped.empty:
                    work = scoped

        if work.empty:
            return fallback, 'fallback', source_path

        if date_col is not None:
            work[date_col] = pd.to_datetime(work[date_col], errors='coerce')
            work = work.sort_values(date_col)

        vals = pd.to_numeric(work[value_col], errors='coerce').dropna()
        if vals.empty:
            return fallback, 'fallback', source_path

        return float(vals.iloc[-1]), 'macro_data.csv', source_path
    except Exception:
        return fallback, 'fallback', source_path
# --- End Macro Data Governance Helpers ---
'''

if HELPER_MARKER not in text:
    safe_float_pattern = r'(def safe_float\(v,fb=1000\.0\):[\s\S]*?except: return fb)'
    text, n = re.subn(safe_float_pattern, r'\1\n' + HELPERS, text, count=1)
    if n != 1:
        raise RuntimeError('Could not locate safe_float() block for macro governance helper injection.')

old_pmi = "pmi_in=st.slider('US ISM PMI',40.0,60.0,51.5)"
new_pmi = (
    "pmi_default, pmi_source, pmi_path = resolve_macro_value(sel_idx, 'PMI', 51.5)\n"
    "    pmi_default = float(min(max(pmi_default if pmi_default is not None else 51.5, 40.0), 60.0))\n"
    "    pmi_in=st.slider('US ISM PMI',40.0,60.0,pmi_default)\n"
    "    st.caption(f'📡 PMI source: {pmi_source}' + (f' — {pmi_path}' if pmi_path else ''))"
)

if old_pmi in text:
    text = text.replace(old_pmi, new_pmi, 1)
elif "pmi_source" in text and "resolve_macro_value(sel_idx, 'PMI'" in text:
    print('PMI slider already patched; skipping PMI replacement.')
else:
    raise RuntimeError('Could not locate the current hardcoded PMI slider block. App structure changed; no patch written.')

text = text.replace('No free API.', 'PMI loaded from macro_data.csv when available.')
compile(text, str(APP_PATH), 'exec')

if text == original:
    print('No changes required. Base app already appears patched.')
else:
    APP_PATH.write_text(text, encoding='utf-8')
    print('✅ Base app data-source governance patch applied successfully.')
    print('Backup:', BACKUP_PATH)
