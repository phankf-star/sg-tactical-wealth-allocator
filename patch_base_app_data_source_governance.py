#!/usr/bin/env python3
"""
Global20Engine Base App Data-Source Governance Patch - ACTIVE CLEAN VERSION
Use this as the only active patch file: patch_base_app_data_source_governance.py

Base app only. Macro fetcher/workflows untouched.
Includes known indentation repairs from prior partial patch runs.
"""
from pathlib import Path
import re, sys, py_compile

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('sg_tactical_wealth_allocator.py')
if not TARGET.exists():
    raise SystemExit(f"Target file not found: {TARGET}")

text = TARGET.read_text(encoding='utf-8', errors='replace')
backup = TARGET.with_suffix(TARGET.suffix + '.bak_data_source_governance_clean')
backup.write_text(text, encoding='utf-8')
changes=[]

def apply_sub(pattern, repl, label, flags=re.S):
    global text
    text2, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n:
        text = text2
        changes.append(label)
        print('OK:', label)
    else:
        print('SKIP:', label)
    return n

text = text.replace('Global Drawdown Allocation Engine v38ac', 'Global Drawdown Allocation Engine v38ad Data-Source Governance', 1)
text = text.replace('Global20Engine v38ac', 'Global20Engine v38ad', 1)

if '_pack_first_macro_result' not in text:
    apply_sub(
        r"(def _uploaded_result\(uploaded\):.*?return _source_result\([^\n]+\))",
        r"\1\n\ndef _pack_first_macro_result(market, indicator):\n    uploaded = get_uploaded_macro_value(market, indicator)\n    if uploaded is not None:\n        return _uploaded_result(uploaded)\n    return None\n\ndef _is_real_macro_value(res):\n    try:\n        return isinstance(res, dict) and res.get('value') is not None\n    except Exception:\n        return False",
        'insert pack-first helper'
    )
else:
    print('OK: pack-first helper already present')

apply_sub(
    r"if indicator=='PMI':\s*return _source_result\([^\n]+\)",
    "if indicator=='PMI': return _source_result(None,'Awaiting pack',MACRO_SOURCE_REGISTRY.get(market,{}).get('PMI','Monthly macro pack PMI'),'Awaiting',diagnostic='PMI must be read from macro_pack_latest/macro_data.csv or explicit owner override. App defaults/session PMI are audit/admin only and cannot drive production scoring/display.')",
    'tighten resolve_macro_value PMI branch'
)

apply_sub(
    r"pmi_v=_macro_numeric\(pmi_res\)\s*if pmi_v is None and asset_name not in PMI_NA_MARKETS:\s*try:\s*pmi_v=float\(pmi_value\)\s*except Exception:\s*pmi_v=None",
    "pmi_v=_macro_numeric(pmi_res)  # Governance: no fallback to passed-in/session/default PMI; missing pack PMI is excluded and weights re-normalise.",
    'remove Macro Risk Score fallback to passed-in PMI'
)

apply_sub(
    r"pmi_s=0 if pmi_value>=52 else 8 if pmi_value>=50 else 16 if pmi_value>=47 else 20\s*dd_s=0; trend_s=0; total=min\(vix_s\+curve_s\+pmi_s,100\); components=\[\]",
    "pmi_s=0\n        dd_s=0; trend_s=0; total=min(vix_s+curve_s,100); components=[]",
    'remove old fallback PMI score'
)

apply_sub(
    r"pmi_proxy_default=PMI_PROXY_MAP\.get\(sel, \{'label':'N/A','region':'N/A','source':'N/A','default':0\}\)\s*if st\.session_state\.get\('pmi_selected_market'\) != sel:.*?st\.session_state\.latest_pmi_source=.*?\s*close,peak,dd,ref,struct_peak_date,struct_current_date,struct_boundary=current_structural_dd\(ud\)",
    "pmi_proxy_default=PMI_PROXY_MAP.get(sel, {'label':'N/A','region':'N/A','source':'N/A','default':0})\nif st.session_state.get('pmi_selected_market') != sel:\n    st.session_state.pmi_selected_market=sel\n    st.session_state.pmi_proxy_label=pmi_proxy_default['label']\n    _boot_pmi = _pack_first_macro_result(sel,'PMI')\n    if _is_real_macro_value(_boot_pmi):\n        st.session_state.latest_pmi_value=float(_boot_pmi.get('value'))\n        st.session_state.latest_pmi_month=str(_boot_pmi.get('date',''))\n        st.session_state.latest_pmi_source=str(_boot_pmi.get('sub','Macro pack PMI'))\n    else:\n        st.session_state.latest_pmi_value=float('nan')\n        st.session_state.latest_pmi_month='Awaiting pack'\n        st.session_state.latest_pmi_source='Awaiting macro_pack_latest/macro_data.csv PMI row'\nclose,peak,dd,ref,struct_peak_date,struct_current_date,struct_boundary=current_structural_dd(ud)",
    'pack-first PMI bootstrap'
)

apply_sub(
    r"pmi_state='N/A' if not pmi_applicable else .*?pmi_src=pmi_res\['source_type'\] if pmi_res and pmi_res\.get\('value'\) is not None else 'Seed'",
    "_pmi_pack_value = pmi_res.get('value') if isinstance(pmi_res,dict) else None\ntry:\n    _pmi_pack_float = float(_pmi_pack_value) if _pmi_pack_value is not None else None\nexcept Exception:\n    _pmi_pack_float = None\npmi_state='N/A' if not pmi_applicable else ('Expansion' if (_pmi_pack_float is not None and _pmi_pack_float>=50) else 'Contraction' if _pmi_pack_float is not None else 'Awaiting pack')\ncurve_state='N/A' if curve_spread is None else ('Normal' if curve_spread>=0 else 'Inverted')\npmi_display=pmi_res['display'] if isinstance(pmi_res,dict) and pmi_res.get('value') is not None else ('N/A' if not pmi_applicable else 'Awaiting pack')\npmi_sub=pmi_res['sub'] if isinstance(pmi_res,dict) and pmi_res.get('value') is not None else pmi_state\npmi_src=pmi_res['source_type'] if isinstance(pmi_res,dict) and pmi_res.get('value') is not None else ('N/A' if not pmi_applicable else 'Awaiting')",
    'PMI card no seed/default'
)

apply_sub(
    r"def get_pmi_df\(chosen,latest_in\):.*?def render_trend_channel\(",
    "def get_pmi_df(chosen,latest_in):\n    if sel in PMI_NA_MARKETS:\n        return pd.DataFrame()\n    pack_pmi = resolve_macro_value(sel,'PMI')\n    hist_df = macro_trend_df(sel,'PMI',pack_pmi).rename(columns={'Value':'PMI'})\n    if hist_df is not None and not hist_df.empty:\n        return hist_df.tail(12)\n    if sel in PMI_FRED_MARKETS:\n        fred=fetch_fred_pmi('NAPM')\n        if not fred.empty:\n            return fred.tail(12)\n    return pd.DataFrame()\n\ndef render_trend_channel(",
    'replace get_pmi_df with pack/history-first version'
)

apply_sub(
    r"\n\s*latest_display=0\.0 if not pmi_app else latest_in\s*local_score,local_alert,lvix,lcurve,lpmi,ldd,ltrend=calc_market_scores_by_asset\(sel,latest_display,dd,trend_below,vix,curve_spread\)",
    "\n        _local_pmi_res = resolve_macro_value(sel,'PMI')\n        latest_display = 0.0 if not pmi_app else (_local_pmi_res.get('value') if isinstance(_local_pmi_res,dict) and _local_pmi_res.get('value') is not None else float('nan'))\n        local_score,local_alert,lvix,lcurve,lpmi,ldd,ltrend=calc_market_scores_by_asset(sel,latest_display,dd,trend_below,vix,curve_spread)",
    'Live Market score uses pack PMI only'
)

# Integrated indentation repairs. These are deliberately narrow.
for pattern, repl, label in [
    (r'\n[ \t]+rate_label=rate_card_label\(index_label\)', '\nrate_label=rate_card_label(index_label)', 'repair rate_label indentation'),
    (r'\n[ \t]+cards=\[\(', '\ncards=[(', 'repair cards indentation'),
    (r'\n[ \t]+def _source_class\(src\):', '\ndef _source_class(src):', 'repair _source_class indentation'),
]:
    text2, n = re.subn(pattern, repl, text, count=1)
    if n:
        text = text2; changes.append(label); print('OK:', label)
    else:
        print('OK:', label, 'already clean or not found')

# Ensure _source_class body is correctly indented if the def was repaired.
text = re.sub(
    r"\ndef _source_class\(src\):\n\s*badge=clean_macro_badge\(src\)\n\s*return",
    "\ndef _source_class(src):\n    badge=clean_macro_badge(src)\n    return",
    text,
    count=1
)

if "'PMI Proxy':st.session_state.get('pmi_proxy_label',pmi_label),'PMI Value':st.session_state.get('latest_pmi_value',latest_pmi)," in text:
    text = text.replace("'PMI Proxy':st.session_state.get('pmi_proxy_label',pmi_label),'PMI Value':st.session_state.get('latest_pmi_value',latest_pmi),",
                        "'PMI Proxy':'macro_pack_latest/macro_data.csv','PMI Value':(resolve_macro_value(index_label,'PMI').get('value') if isinstance(resolve_macro_value(index_label,'PMI'),dict) else None),")
    changes.append('snapshot export uses pack PMI')
    print('OK: snapshot export uses pack PMI')
else:
    print('OK: snapshot export already clean or pattern not found')

TARGET.write_text(text, encoding='utf-8')

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
print('\nPost-check:')
for name, ok in checks:
    print(('PASS' if ok else 'CHECK') + ' - ' + name)
py_compile.compile(str(TARGET), doraise=True)
print('PASS - Compile check')
if all(ok for _, ok in checks):
    print('RESULT: PASS')
else:
    print('RESULT: REVIEW REQUIRED')
    raise SystemExit(1)
print(f'Backup created: {backup}')
print(f'Patched file: {TARGET}')
print('Changes applied:', ', '.join(changes) if changes else 'none')
