#!/usr/bin/env python3
"""Quick scanner for Global20Engine base-app data-source governance."""
from pathlib import Path
import re, sys
p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('sg_tactical_wealth_allocator.py')
text = p.read_text(encoding='utf-8', errors='replace')
checks = [
    ('No Macro Risk Score fallback to passed-in PMI', 'try: pmi_v=float(pmi_value)' not in text),
    ('PMI card does not mark missing pack data as Seed', "else 'Seed'" not in text),
    ('No simulated PMI trend caption', 'Simulated PMI trend' not in text),
    ('get_pmi_df does not use DEFAULT_PMI_HISTORY', not re.search(r'def get_pmi_df[\s\S]*?DEFAULT_PMI_HISTORY', text)),
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
