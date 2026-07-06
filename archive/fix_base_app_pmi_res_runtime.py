#!/usr/bin/env python3
"""
Global20Engine runtime fix: ensure pmi_res exists before PMI display block.
Use as active patch helper:
  python fix_base_app_pmi_res_runtime.py sg_tactical_wealth_allocator.py
"""
from pathlib import Path
import re, sys, py_compile

p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('sg_tactical_wealth_allocator.py')
if not p.exists():
    raise SystemExit(f'File not found: {p}')
text = p.read_text(encoding='utf-8', errors='replace')
backup = p.with_suffix(p.suffix + '.bak_pmi_res_runtime_fix')
backup.write_text(text, encoding='utf-8')

# If pmi_res is referenced in the production PMI display block but not defined nearby,
# insert a safe pack-first resolver immediately before the block.
marker = "_pmi_pack_value = pmi_res.get('value') if isinstance(pmi_res,dict) else None"
insert = "pmi_res=resolve_macro_value(index_label,'PMI')\n" + marker

if marker in text and insert not in text:
    text = text.replace(marker, insert, 1)
    print('OK: inserted pmi_res resolver before PMI display block')
else:
    print('OK: pmi_res resolver already present or marker not found')

p.write_text(text, encoding='utf-8')

try:
    py_compile.compile(str(p), doraise=True)
    print('PASS - Compile check')
except Exception as e:
    print('CHECK - Compile check:', e)
    raise

# Lightweight governance/runtime scan
checks = [
    ('pmi_res resolver before display block', "pmi_res=resolve_macro_value(index_label,'PMI')\n_pmi_pack_value" in text),
    ('No Macro Risk Score fallback to passed-in PMI', 'try: pmi_v=float(pmi_value)' not in text),
    ('PMI card does not mark missing pack data as Seed', "else 'Seed'" not in text),
    ('No simulated PMI trend caption', 'Simulated PMI trend' not in text),
]
for name, ok in checks:
    print(('PASS' if ok else 'CHECK') + ' - ' + name)
if all(ok for _, ok in checks):
    print('RESULT: PASS')
else:
    print('RESULT: REVIEW REQUIRED')
    raise SystemExit(1)
print(f'Backup created: {backup}')
