#!/usr/bin/env python3
"""
Global20Engine surgical fix for the current post-governance patch error.

Current known issue:
    IndentationError around def _curve(v): / try:

This file intentionally does NOT re-run the earlier broad regex governance patch.
It only repairs the malformed _curve block and verifies governance checks.
"""
from pathlib import Path
import re, sys, py_compile

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sg_tactical_wealth_allocator.py")
if not TARGET.exists():
    raise SystemExit(f"Target file not found: {TARGET}")

text = TARGET.read_text(encoding="utf-8", errors="replace")
backup = TARGET.with_suffix(TARGET.suffix + ".bak_curve_surgical_fix")
backup.write_text(text, encoding="utf-8")

replacement = (
    "def _curve(v):\n"
    "    try:\n"
    "        if v is None or pd.isna(v):\n"
    "            return 'N/A'\n"
    "        return f'{float(v):.2f}%'\n"
    "    except Exception:\n"
    "        return 'N/A'\n"
    "\n"
    "pmi_res=resolve_macro_value(index_label,'PMI')\n"
    "_pmi_pack_value = pmi_res.get('value') if isinstance(pmi_res,dict) else None"
)

# Replace only the broken section: from def _curve(v): through _pmi_pack_value assignment.
pattern = r"def _curve\(v\):[\s\S]*?_pmi_pack_value\s*=\s*pmi_res\.get\('value'\) if isinstance\(pmi_res,dict\) else None"
new_text, n = re.subn(pattern, replacement, text, count=1)
if n != 1:
    raise SystemExit("Could not find exactly one _curve/_pmi_pack_value block to repair. No file was changed.")

TARGET.write_text(new_text, encoding="utf-8")

# Compile first. If this fails, stop immediately.
py_compile.compile(str(TARGET), doraise=True)
print("PASS - Compile check")

# Governance checks that should already be true after the previous successful patch.
get_pmi = re.search(r"def get_pmi_df\(chosen,latest_in\):([\s\S]*?)(?=
def render_trend_channel\()", new_text)
checks = [
    ("pmi_res resolver directly before _pmi_pack_value", "pmi_res=resolve_macro_value(index_label,'PMI')\n_pmi_pack_value" in new_text),
    ("No Macro Risk Score fallback to passed-in PMI", "try: pmi_v=float(pmi_value)" not in new_text),
    ("PMI card does not mark missing pack data as Seed", "else 'Seed'" not in new_text),
    ("No simulated PMI trend caption", "Simulated PMI trend" not in new_text),
    ("get_pmi_df body does not use DEFAULT_PMI_HISTORY", bool(get_pmi and "DEFAULT_PMI_HISTORY" not in get_pmi.group(1))),
    ("macro_data.csv source path still present", "macro_pack_latest/macro_data.csv" in new_text),
    ("macro_history_12m.csv source path still present", "macro_pack_latest/macro_history_12m.csv" in new_text),
    ("rates_history_252d.csv source path still present", "macro_pack_latest/rates_history_252d.csv" in new_text),
]

for name, ok in checks:
    print(("PASS" if ok else "CHECK") + " - " + name)

if all(ok for _, ok in checks):
    print("RESULT: PASS")
else:
    print("RESULT: REVIEW REQUIRED")
    raise SystemExit(1)

print(f"Backup created: {backup}")
print(f"Patched file: {TARGET}")
