
# Global20Engine v37f -> v37g patcher
# Creates Global20Engine_v37g.py from Global20Engine_v37f.py.
from pathlib import Path
import re
import sys

DEFAULT_INPUT = 'Global20Engine_v37f.py'
DEFAULT_OUTPUT = 'Global20Engine_v37g.py'

LOCAL_FRED_HELPER = r'''
# ─────────────────────────────────────────────────────────────────────────────
# v37g quick-fix: local CSV-first FRED adapter for monthly macro pack workflow
# ─────────────────────────────────────────────────────────────────────────────
def _candidate_local_macro_paths(series_id):
    names = [f"{series_id}.csv", f"{series_id.lower()}.csv", f"FRED_{series_id}.csv"]
    roots = [Path.cwd(), Path(__file__).resolve().parent]
    home = Path.home()
    roots += [home / "Downloads", home / "Desktop"]
    seen, out = set(), []
    for root in roots:
        try:
            if not root.exists():
                continue
            for nm in names:
                p = root / nm
                if p.exists() and p not in seen:
                    seen.add(p); out.append(p)
            for nm in names:
                for p in root.glob(f"*/{nm}"):
                    if p.exists() and p not in seen:
                        seen.add(p); out.append(p)
        except Exception:
            pass
    return out

def fetch_local_fred_csv_series(series_id):
    adapter = f"{series_id} local file"
    for path in _candidate_local_macro_paths(series_id):
        try:
            df = pd.read_csv(path)
            if df is None or df.empty:
                _diag(adapter, str(path), True, 0, "empty file", "", "Local file exists but has no rows")
                continue
            cols = {str(c).strip().lower(): c for c in df.columns}
            date_col = cols.get("date") or cols.get("observation_date") or cols.get("time")
            value_col = None
            for key in [series_id.lower(), "value", "val", "close"]:
                if key in cols:
                    value_col = cols[key]
                    break
            if value_col is None:
                non_date = [c for c in df.columns if c != date_col]
                value_col = non_date[-1] if non_date else None
            if date_col is None or value_col is None:
                _diag(adapter, str(path), True, len(df), "columns not matched", "", f"Columns: {list(df.columns)}")
                continue
            out = pd.DataFrame({
                "DATE": pd.to_datetime(df[date_col], errors="coerce"),
                "Value": pd.to_numeric(df[value_col], errors="coerce"),
            }).dropna().set_index("DATE").sort_index()
            if not out.empty:
                _diag(adapter, str(path), True, len(out), "local CSV parsed", f"{out.index[-1].date()}={out['Value'].iloc[-1]}", "")
                return out
            _diag(adapter, str(path), True, 0, "no numeric values", "", "Date/value columns found but no usable numeric rows")
        except Exception as e:
            _diag(adapter, str(path), True, 0, "parser error", "", str(e))
    _diag(adapter, "local search", False, 0, "file not found", "", f"Expected {series_id}.csv in script folder, Downloads, Desktop, or one-level subfolders")
    return pd.DataFrame()
'''

FETCH_FRED_REPLACEMENT = r'''
@st.cache_data(ttl=21600)
def fetch_fred_series(series_id):
    # Priority: local FRED CSV -> FRED graph CSV -> FRED /data -> DBnomics mirror.
    local_df = fetch_local_fred_csv_series(series_id)
    if local_df is not None and not local_df.empty:
        return local_df
    url=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
    adapter=f'FRED {series_id}'
    txt,err,row=_request_text(url,adapter,capture_global=True)
    if txt:
        try:
            df=pd.read_csv(io.StringIO(txt),parse_dates=['DATE'])
            if not df.empty and series_id in df.columns:
                df=df.rename(columns={series_id:'Value'}).set_index('DATE')
                df['Value']=pd.to_numeric(df['Value'],errors='coerce')
                df=df.dropna()
                if not df.empty:
                    _diag(adapter,url,True,len(df),'series column matched',f"{df.index[-1].date()}={df['Value'].iloc[-1]}",'')
                    return df
        except Exception as e:
            _diag(adapter,url,True,0,'parser error','',f'CSV parse error: {e}; trying fallback')
    df=fetch_fred_data_page_series(series_id)
    if df is not None and not df.empty:
        return df
    return fetch_dbnomics_fred_mirror(series_id)
'''

EXEC_FIX_REPLACEMENT = r'''
trend_below = bool(close < m.get(sel, {}).get('ma200', close))

# v37g quick-fix: restore Executive Centre variables after line-1369 corruption.
pmi_label = st.session_state.get('pmi_proxy_label', pmi_proxy_default.get('label', 'N/A'))
latest_pmi = float(st.session_state.get('latest_pmi_value', pmi_proxy_default.get('default', 0.0)))
pmi_applicable = sel not in PMI_NA_MARKETS
score_pmi = 0.0 if not pmi_applicable else latest_pmi
live_score, alert, vix_s, curve_s, pmi_s, dd_s, trend_s = calc_market_scores_by_asset(sel, score_pmi, dd, trend_below, vix, curve_spread)
conf_score = confidence_score(dd, live_score, trend_below)
conf_label = confidence_label(conf_score)
try:
    exec_tc = build_trend_channel(ud, 2040, model='Expanding Window', rolling_years=15)
except Exception:
    exec_tc = None
exec_z_score = exec_tc.get('z_score') if isinstance(exec_tc, dict) else None
exec_valuation_zone, exec_valuation_colour = valuation_status(exec_z_score)
display_dd = dd
decision_line = f"Deploy {fmt_sgd(deploy)} using staged tranches." if deploy > 0 else "No deployment; capital preserved until next trigger."
next_trigger = compact_next_trigger_label(zone)
structural_tip = tooltip_html(
    'Structural Drawdown',
    [('Basis', ref), ('Peak Date', struct_peak_date.strftime('%Y-%m-%d') if pd.notna(struct_peak_date) else 'N/A'), ('Current Date', struct_current_date.strftime('%Y-%m-%d') if pd.notna(struct_current_date) else 'N/A'), ('Formula', '(current close - structural peak) / structural peak')],
    'Primary deployment signal. Secondary drawdown lenses remain diagnostic only.'
)
'''

def patch_source(src: str) -> str:
    src = src.replace('Global20Engine v37f', 'Global20Engine v37g')
    src = src.replace("generator_version','value':'Global20Engine v37f web macro pack generator'", "generator_version','value':'Global20Engine v37g web macro pack generator'")
    src = re.sub(r"@st\.cache_data\(ttl=21600\)\s+@st\.cache_data\(ttl=21600\)", "@st.cache_data(ttl=21600)\n", src)

    if 'def fetch_local_fred_csv_series(series_id):' not in src:
        pos = src.find('def fetch_fred_series(series_id):')
        if pos != -1:
            pre = src.rfind('@st.cache_data', 0, pos)
            insert_at = pre if pre != -1 and pos - pre < 140 else pos
            src = src[:insert_at] + LOCAL_FRED_HELPER + '\n' + src[insert_at:]

    patterns = [
        re.compile(r"@st\.cache_data\(ttl=21600\)\s*\ndef fetch_fred_series\(series_id\):.*?(?=@st\.cache_data\(ttl=21600\)\s*\ndef us_macro_dashboard_data\(\):)", re.S),
        re.compile(r"@st\.cache_data\(ttl=21600\)\s*def fetch_fred_series\(series_id\):.*?(?=@st\.cache_data\(ttl=21600\)\s*def us_macro_dashboard_data\(\):)", re.S),
    ]
    for pat in patterns:
        src, n = pat.subn(FETCH_FRED_REPLACEMENT + '\n', src, count=1)
        if n:
            break

    corrupt_patterns = [
        r"trend_below\s*=\s*close\(current close − structural peak\) ÷ structural peak'\)",
        r"trend_below\s*=\s*close\(current close .*? structural peak.*?\)",
    ]
    replaced = False
    for pat in corrupt_patterns:
        src, n = re.subn(pat, EXEC_FIX_REPLACEMENT, src, count=1, flags=re.S)
        if n:
            replaced = True
            break
    if not replaced and 'v37g quick-fix: restore Executive Centre variables' not in src:
        curve_pat = r"curve_spread=\(tnx-irx\) if \(tnx is not None and irx is not None\) else None"
        src = re.sub(curve_pat, r"\g<0>\n" + EXEC_FIX_REPLACEMENT, src, count=1)
    return src

def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_INPUT)
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(DEFAULT_OUTPUT)
    if not input_path.exists():
        raise FileNotFoundError(f'Input file not found: {input_path}')
    patched = patch_source(input_path.read_text(encoding='utf-8'))
    output_path.write_text(patched, encoding='utf-8')
    print(f'Patched file written: {output_path}')
    print('Recommended launch: streamlit run ' + str(output_path))

if __name__ == '__main__':
    main()
