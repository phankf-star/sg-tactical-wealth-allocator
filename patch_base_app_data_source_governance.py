#!/usr/bin/env python3
"""
Global20Engine Base App Data-Source Governance Patch - active runtime/scope repair
Use as the existing active file:
  patch_base_app_data_source_governance.py

Purpose:
- Fix pmi_res NameError caused by pmi_res being inserted in the wrong scope near _curve().
- Keep workflow unchanged.
- Macro fetcher/workflows untouched.
"""
from pathlib import Path
import re, sys, py_compile

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('sg_tactical_wealth_allocator.py')
if not TARGET.exists():
    raise SystemExit(f"Target file not found: {TARGET}")

text = TARGET.read_text(encoding='utf-8', errors='replace')
backup = TARGET.with_suffix(TARGET.suffix + '.bak_pmi_scope_repair')
backup.write_text(text, encoding='utf-8')
changes=[]

# 1) Repair the _curve + pmi_res scope block.
# The app error means pmi_res is visually present but not in the same executable scope
# as _pmi_pack_value. This normalises the section so pmi_res is directly above
# _pmi_pack_value at top-level app flow.
pattern = r"def _curve\(v\):.*?_pmi_pack_value\s*=\s*pmi_res\.get\('value'\) if isinstance\(pmi_res,dict\) else None"
replacement = """def _curve(v):
    try:
        if v is None or pd.isna(v): return 'N/A'
        return f'{float(v):.2f}%'
    except Exception: return 'N/A'
pmi_res=resolve_macro_value(index_label,'PMI')
_pmi_pack_value = pmi_res.get('value') if isinstance(pmi_res,dict) else None"""
text2, n = re.subn(pattern, replacement, text, count=1, flags=re.S)
if n:
    text = text2
    changes.append('repair _curve / pmi_res scope')
    print('OK: repair _curve / pmi_res scope')
else:
    print('SKIP: _curve / pmi_res scope block not found')

# 2) Defensive cleanup if duplicate pmi_res line appears immediately after repair.
text2, n2 = re.subn(
    r"pmi_res=resolve_macro_value\(index_label,'PMI'\)\n\s*pmi_res=resolve_macro_value\(index_label,'PMI'\)",
    "pmi_res=resolve_macro_value(index_label,'PMI')",
    text,
    count=1
)
if n2:
    text = text2
    changes.append('remove duplicate pmi_res resolver')
    print('OK: remove duplicate pmi_res resolver')

TARGET.write_text(text, encoding='utf-8')

# Compile check
py_compile.compile(str(TARGET), doraise=True)
print('PASS - Compile check')

# Verification checks
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
