#!/usr/bin/env python3
"""
Global20Engine Base App Data-Source Governance Patch v3
Purpose: repair v2 indentation issue and tighten verifier false-positive around DEFAULT_PMI_HISTORY.
Target: sg_tactical_wealth_allocator.py
"""
from pathlib import Path
import re, sys, py_compile

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('sg_tactical_wealth_allocator.py')
if not TARGET.exists():
    raise SystemExit(f"Target file not found: {TARGET}")

text = TARGET.read_text(encoding='utf-8', errors='replace')
backup = TARGET.with_suffix(TARGET.suffix + '.bak_data_source_governance_v3')
backup.write_text(text, encoding='utf-8')
changes = []

# 1) Fix v2 accidental top-level insertion inside render_market.
# Expected inside render_market -> with st.expander block = 8 spaces.
patterns = [
    (r"\n_local_pmi_res = resolve_macro_value\(sel,'PMI'\)\nlatest_display = 0\.0 if not pmi_app else \(_local_pmi_res\.get\('value'\) if isinstance\(_local_pmi_res,dict\) and _local_pmi_res\.get\('value'\) is not None else float\('nan'\)\)\nlocal_score,local_alert,lvix,lcurve,lpmi,ldd,ltrend=calc_market_scores_by_asset\(sel,latest_display,dd,trend_below,vix,curve_spread\)",
     "\n        _local_pmi_res = resolve_macro_value(sel,'PMI')\n        latest_display = 0.0 if not pmi_app else (_local_pmi_res.get('value') if isinstance(_local_pmi_res,dict) and _local_pmi_res.get('value') is not None else float('nan'))\n        local_score,local_alert,lvix,lcurve,lpmi,ldd,ltrend=calc_market_scores_by_asset(sel,latest_display,dd,trend_below,vix,curve_spread)",
     'indent Live Market PMI score block'),
    (r"\n\s{0,4}_local_pmi_res = resolve_macro_value\(sel,'PMI'\)\n\s{0,4}latest_display = 0\.0 if not pmi_app else \(_local_pmi_res\.get\('value'\) if isinstance\(_local_pmi_res,dict\) and _local_pmi_res\.get\('value'\) is not None else float\('nan'\)\)\n\s{0,4}local_score,local_alert,lvix,lcurve,lpmi,ldd,ltrend=calc_market_scores_by_asset\(sel,latest_display,dd,trend_below,vix,curve_spread\)",
     "\n        _local_pmi_res = resolve_macro_value(sel,'PMI')\n        latest_display = 0.0 if not pmi_app else (_local_pmi_res.get('value') if isinstance(_local_pmi_res,dict) and _local_pmi_res.get('value') is not None else float('nan'))\n        local_score,local_alert,lvix,lcurve,lpmi,ldd,ltrend=calc_market_scores_by_asset(sel,latest_display,dd,trend_below,vix,curve_spread)",
     'normalise Live Market PMI score block indent'),
]
for pat, repl, label in patterns:
    text2, n = re.subn(pat, repl, text, count=1, flags=re.S)
    if n:
        text = text2
        changes.append(label)
        print(f"OK: {label}")
        break
else:
    print('SKIP: Live Market PMI score block indent already OK or not found')

# 2) If the v2 helper was inserted inside a one-line function badly, ensure it starts at top-level.
text = text.replace(" return False\n\ndef _pack_first_macro_result", " return False\n\ndef _pack_first_macro_result")

# 3) Make sure get_pmi_df function itself has no DEFAULT_PMI_HISTORY / simulated trend.
match = re.search(r"def get_pmi_df\(chosen,latest_in\):(.*?)(?=\ndef render_trend_channel\()", text, flags=re.S)
if match:
    body = match.group(1)
    if 'DEFAULT_PMI_HISTORY' in body or 'Simulated PMI trend' in body:
        replacement = "def get_pmi_df(chosen,latest_in):\n    if sel in PMI_NA_MARKETS:\n        return pd.DataFrame()\n    pack_pmi = resolve_macro_value(sel,'PMI')\n    hist_df = macro_trend_df(sel,'PMI',pack_pmi).rename(columns={'Value':'PMI'})\n    if hist_df is not None and not hist_df.empty:\n        return hist_df.tail(12)\n    if sel in PMI_FRED_MARKETS:\n        fred=fetch_fred_pmi('NAPM')\n        if not fred.empty:\n            return fred.tail(12)\n    return pd.DataFrame()"
        text = text[:match.start()] + replacement + text[match.end():]
        changes.append('clean get_pmi_df body')
        print('OK: clean get_pmi_df body')
    else:
        print('OK: get_pmi_df body already clean')
else:
    print('CHECK: get_pmi_df function not found')

TARGET.write_text(text, encoding='utf-8')

print('\nPost-check:')
checks=[]
checks.append(('No Macro Risk Score fallback to passed-in PMI', 'try: pmi_v=float(pmi_value)' not in text))
checks.append(('PMI card does not mark missing pack data as Seed', "else 'Seed'" not in text))
checks.append(('No simulated PMI trend caption', 'Simulated PMI trend' not in text))
match = re.search(r"def get_pmi_df\(chosen,latest_in\):(.*?)(?=\ndef render_trend_channel\()", text, flags=re.S)
checks.append(('get_pmi_df body does not use DEFAULT_PMI_HISTORY', bool(match and 'DEFAULT_PMI_HISTORY' not in match.group(1))))
checks.append(('macro_data.csv source path still present', 'macro_pack_latest/macro_data.csv' in text))
checks.append(('macro_history_12m.csv source path still present', 'macro_pack_latest/macro_history_12m.csv' in text))
checks.append(('rates_history_252d.csv source path still present', 'macro_pack_latest/rates_history_252d.csv' in text))
for name, ok in checks:
    print(('PASS' if ok else 'CHECK') + ' - ' + name)
try:
    py_compile.compile(str(TARGET), doraise=True)
    print('Compile check: PASS')
except Exception as e:
    print(f'Compile check: FAIL - {e}')
    raise
print(f'Backup created: {backup}')
print(f'Patched file: {TARGET}')
print('Changes applied:', ', '.join(changes) if changes else 'none')
