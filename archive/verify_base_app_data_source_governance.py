#!/usr/bin/env python3
from pathlib import Path
import re, sys, py_compile
p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('sg_tactical_wealth_allocator.py')
text = p.read_text(encoding='utf-8', errors='replace')
get_pmi = re.search(r"def get_pmi_df\(chosen,latest_in\):(.*?)(?=\ndef render_trend_channel\()", text, flags=re.S)
checks = [
    ('No Macro Risk Score fallback to passed-in PMI', 'try: pmi_v=float(pmi_value)' not in text),
    ('PMI card does not mark missing pack data as Seed', "else 'Seed'" not in text),
    ('No simulated PMI trend caption', 'Simulated PMI trend' not in text),
    ('get_pmi_df body does not use DEFAULT_PMI_HISTORY', bool(get_pmi and 'DEFAULT_PMI_HISTORY' not in get_pmi.group(1))),
    ('macro_data.csv source path still present', 'macro_pack_latest/macro_data.csv' in text),
    ('macro_history_12m.csv source path still present', 'macro_pack_latest/macro_history_12m.csv' in text),
    ('rates_history_252d.csv source path still present', 'macro_pack_latest/rates_history_252d.csv' in text),
]
compile_ok = True
try:
    py_compile.compile(str(p), doraise=True)
except Exception as e:
    compile_ok = False
    print('CHECK - Compile check:', e)
for name, ok in checks:
    print(('PASS' if ok else 'CHECK') + ' - ' + name)
print(('PASS' if compile_ok else 'CHECK') + ' - Compile check')
if all(ok for _, ok in checks) and compile_ok:
    print('RESULT: PASS')
else:
    print('RESULT: REVIEW REQUIRED')
    sys.exit(1)
