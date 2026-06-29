#!/usr/bin/env python3
"""
Global20Engine Base App Data-Source Governance Patch - final _curve indentation repair
Use as existing active file:
  patch_base_app_data_source_governance.py

Purpose:
- Repair current runtime/compile issue: def _curve(v): has unindented try block.
- Keep existing governance patch results intact.
- Macro fetcher/workflows untouched.
"""
from pathlib import Path
import re, sys, py_compile

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('sg_tactical_wealth_allocator.py')
if not TARGET.exists():
    raise SystemExit(f"Target file not found: {TARGET}")

text = TARGET.read_text(encoding='utf-8', errors='replace')
backup = TARGET.with_suffix(TARGET.suffix + '.bak_curve_indent_final')
backup.write_text(text, encoding='utf-8')
changes=[]

# Replace the entire _curve block up to _pmi_pack_value with a clean, correctly indented block.
pattern = r"def _curve\(v\):\s*try:\s*if v is None or pd\.isna\(v\): return 'N/A'\s*return f'\{float\(v\):\.2f\}%'\s*except Exception: return 'N/A'\s*pmi_res=resolve_macro_value\(index_label,'PMI'\)\s*_pmi_pack_value\s*=\s*pmi_res\.get\('value'\) if isinstance\(pmi_res,dict\) else None"
replacement = """def _curve(v):
    try:
        if v is None or pd.isna(v):
            return 'N/A'
        return f'{float(v):.2f}%'
    except Exception:
        return 'N/A'

pmi_res=resolve_macro_value(index_label,'PMI')
_pmi_pack_value = pmi_res.get('value') if isinstance(pmi_res,dict) else None"""
text2, n = re.subn(pattern, replacement, text, count=1, flags=re.S)
if n:
    text = text2
    changes.append('repair _curve indentation and pmi_res scope')
    print('OK: repair _curve indentation and pmi_res scope')
else:
    # Fallback: handle line-broken variants between def _curve and pmi_res.
    pattern2 = r"def _curve\(v\):.*?pmi_res=resolve_macro_value\(index_label,'PMI'\)\s*_pmi_pack_value\s*=\s*pmi_res\.get\('value'\) if isinstance\(pmi_res,dict\) else None"
    text2, n2 = re.subn(pattern2, replacement, text, count=1, flags=re.S)
    if n2:
        text = text2
        changes.append('repair _curve block fallback')
        print('OK: repair _curve block fallback')
    else:
        print('CHECK: _curve block not found')

TARGET.write_text(text, encoding='utf-8')

# Compile and governance checks
py_compile.compile(str(TARGET), doraise=True)
print('PASS - Compile check')

get_pmi = re.search(r"def get_pmi_df\(chosen,latest_in\):(.*?)(?=\ndef render_trend_channel\()", text, flags=re.S)
checks = [
    ('pmi_res resolver is directly before _pmi_pack_value', "pmi_res=resolve_macro_value(index_label,'PMI')\n_pmi_pack_value" in text),
    ('No Macro Risk Score fallback to passed-in PMI', 'try: pmi_v=float(pmi_value)' not in text),
    ('PMI card does not mark missing pack data as Seed', "else 'Seed'" not in text),
    ('No simulated PMI trend caption', 'Simulated PMI trend' not in text),
    ('get_pmi_df body does not use DEFAULT_PMI_HISTORY', bool(get_pmi and 'DEFAULT_PMI_HISTORY' not in get_pmi.group(1))),
    ('macro_data.csv source path still present', 'macro_pack_latest/macro_data.csv' in text),
    ('macro_history_12m.csv source path still present', 'macro_pack_latest/macro_history_12m.csv' in text),
    ('rates_history_252d.csv source path still present', 'macro_pack_latest/rates_history_252d.csv' in text),
]
for name, ok in checks:
    print(('PASS' if ok else 'CHECK') + ' - ' + name)
if all(ok for _, ok in checks):
    print('RESULT: PASS')
else:
    print('RESULT: REVIEW REQUIRED')
    raise SystemExit(1)
print(f'Backup created: {backup}')
print(f'Patched file: {TARGET}')
print('Changes applied:', ', '.join(changes) if changes else 'none')
