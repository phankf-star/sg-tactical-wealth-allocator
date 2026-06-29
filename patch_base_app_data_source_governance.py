#!/usr/bin/env python3
"""
Global20Engine Base App Data-Source Governance Patch
Target: sg_tactical_wealth_allocator.py or Global20Engine v38ac.py

Purpose:
- Keep existing working macro fetcher untouched.
- Keep existing base-app live price / macro adapter logic intact.
- Stop legacy PMI defaults from silently driving production score/cards/charts
  when macro_pack_latest/macro_data.csv / macro_history_12m.csv should be source of truth.

Usage:
  python patch_base_app_data_source_governance.py sg_tactical_wealth_allocator.py

This script creates a .bak backup before editing.
"""
from pathlib import Path
import re
import sys
import py_compile

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('sg_tactical_wealth_allocator.py')
if not TARGET.exists():
    raise SystemExit(f"Target file not found: {TARGET}")

text = TARGET.read_text(encoding='utf-8', errors='replace')
original = text
backup = TARGET.with_suffix(TARGET.suffix + '.bak_data_source_governance')
backup.write_text(original, encoding='utf-8')

changes = []

def replace_once(old, new, label):
    global text
    if old not in text:
        print(f"SKIP: {label} — exact block not found")
        return False
    text = text.replace(old, new, 1)
    changes.append(label)
    print(f"OK: {label}")
    return True

def regex_replace(pattern, repl, label, flags=0):
    global text
    text2, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n == 0:
        print(f"SKIP: {label} — pattern not found")
        return False
    text = text2
    changes.append(label)
    print(f"OK: {label}")
    return True

# 0) Version marker only; no functional impact.
text = text.replace("Global Drawdown Allocation Engine v38ac", "Global Drawdown Allocation Engine v38ad Data-Source Governance", 1)
text = text.replace("# Global20Engine v38ac — render_market macro fallback fix; Live Market Trend Monitor", "# Global20Engine v38ad — base-app data-source governance; no silent macro/PMI defaults in production", 1)

# 1) Add pack-first helper after _uploaded_result.
anchor = "def _uploaded_result(uploaded): unit=uploaded.get('unit',''); display=f\"{uploaded['value']:.1f}{unit}\" if unit and '%' in unit else (f\"{uploaded['value']:.1f}\" if abs(uploaded['value'])<1000 else f\"{uploaded['value']:,.0f}\") return _source_result(uploaded['value'],display,f\"{uploaded.get('source_type','Owner-uploaded')} · {uploaded.get('source','')} · {uploaded.get('date','')}\",uploaded.get('source_type','Owner-uploaded'),uploaded.get('date',''))"
insert = anchor + "\n\ndef _pack_first_macro_result(market, indicator):\n    \"\"\"Return production macro value from macro pack / overrides only.\n\n    This helper deliberately does not use app default/session PMI values.\n    It keeps the base app pack-governed without touching the macro fetcher.\n    \"\"\"\n    uploaded = get_uploaded_macro_value(market, indicator)\n    if uploaded is not None:\n        return _uploaded_result(uploaded)\n    return None\n\ndef _is_real_macro_value(res):\n    try:\n        return isinstance(res, dict) and res.get('value') is not None\n    except Exception:\n        return False\n"
replace_once(anchor, insert, "add pack-first macro helper")

# 2) Strengthen resolve_macro_value PMI branch: pack first, otherwise Awaiting only.
old = "if indicator=='PMI': return _source_result(None,'Awaiting pack',MACRO_SOURCE_REGISTRY.get(market,{}).get('PMI','Monthly macro pack PMI'),'Awaiting',diagnostic='PMI is resolved from generated/uploaded monthly macro pack first; default/session PMI remains fallback display only.')"
new = "if indicator=='PMI': return _source_result(None,'Awaiting pack',MACRO_SOURCE_REGISTRY.get(market,{}).get('PMI','Monthly macro pack PMI'),'Awaiting',diagnostic='PMI must be read from macro_pack_latest/macro_data.csv or explicit owner override. App defaults/session PMI are audit/admin only and cannot drive production scoring/display.')"
replace_once(old, new, "PMI awaiting message tightened")

# 3) Remove Macro Risk Score v2 legacy PMI fallback.
old = "infl_v=_macro_numeric(inflation); unemp_v=_macro_numeric(unemployment); claims_v=_macro_numeric(claims); rates_v=_macro_numeric(rates); pmi_v=_macro_numeric(pmi_res) if pmi_v is None and asset_name not in PMI_NA_MARKETS: try: pmi_v=float(pmi_value) except Exception: pmi_v=None"
new = "infl_v=_macro_numeric(inflation); unemp_v=_macro_numeric(unemployment); claims_v=_macro_numeric(claims); rates_v=_macro_numeric(rates); pmi_v=_macro_numeric(pmi_res) # Governance: do not fall back to passed-in/session/default PMI. If macro pack PMI is missing, exclude PMI and re-normalise weights."
replace_once(old, new, "remove Macro Risk Score legacy PMI fallback")

# 4) Prevent old calc fallback from using passed-in PMI when components are empty.
old = "pmi_s=0 if pmi_value>=52 else 8 if pmi_value>=50 else 16 if pmi_value>=47 else 20 dd_s=0; trend_s=0; total=min(vix_s+curve_s+pmi_s,100); components=[]"
new = "pmi_s=0  # Governance: no fallback PMI score from session/default value when pack data is unavailable.\n        dd_s=0; trend_s=0; total=min(vix_s+curve_s,100); components=[]"
replace_once(old, new, "remove legacy PMI scoring in empty-component fallback")

# 5) Pack-first session bootstrap. This is defensive only; it does not touch fetchers.
old = "if st.session_state.get('pmi_selected_market') != sel: st.session_state.pmi_selected_market=sel; st.session_state.pmi_proxy_label=pmi_proxy_default['label']; st.session_state.latest_pmi_value=float(pmi_proxy_default['default']) act=LATEST_PMI_ACTUALS.get(pmi_proxy_default['label'], LATEST_PMI_ACTUALS['N/A']); st.session_state.latest_pmi_month=act['month']; st.session_state.latest_pmi_source=pmi_proxy_default['source']"
new = "if st.session_state.get('pmi_selected_market') != sel:\n    st.session_state.pmi_selected_market=sel\n    st.session_state.pmi_proxy_label=pmi_proxy_default['label']\n    _boot_pmi = _pack_first_macro_result(sel,'PMI')\n    if _is_real_macro_value(_boot_pmi):\n        st.session_state.latest_pmi_value=float(_boot_pmi.get('value'))\n        st.session_state.latest_pmi_month=str(_boot_pmi.get('date',''))\n        st.session_state.latest_pmi_source=str(_boot_pmi.get('sub','Macro pack PMI'))\n    else:\n        st.session_state.latest_pmi_value=float('nan')\n        st.session_state.latest_pmi_month='Awaiting pack'\n        st.session_state.latest_pmi_source='Awaiting macro_pack_latest/macro_data.csv PMI row'"
replace_once(old, new, "pack-first PMI session bootstrap")

# 6) Production PMI card must show Awaiting, not Seed/default, if pack PMI missing.
old = "pmi_state='N/A' if not pmi_applicable else ('Expansion' if latest_pmi>=50 else 'Contraction'); curve_state='N/A' if curve_spread is None else ('Normal' if curve_spread>=0 else 'Inverted') pmi_display=pmi_res['display'] if pmi_res and pmi_res.get('value') is not None else (f'{latest_pmi:.1f}' if pmi_applicable else 'N/A') pmi_sub=pmi_res['sub'] if pmi_res and pmi_res.get('source_type')=='Owner-uploaded' else pmi_state pmi_src=pmi_res['source_type'] if pmi_res and pmi_res.get('value') is not None else 'Seed'"
new = "_pmi_pack_value = pmi_res.get('value') if isinstance(pmi_res,dict) else None\ntry:\n    _pmi_pack_float = float(_pmi_pack_value) if _pmi_pack_value is not None else None\nexcept Exception:\n    _pmi_pack_float = None\npmi_state='N/A' if not pmi_applicable else ('Expansion' if (_pmi_pack_float is not None and _pmi_pack_float>=50) else 'Contraction' if _pmi_pack_float is not None else 'Awaiting pack')\ncurve_state='N/A' if curve_spread is None else ('Normal' if curve_spread>=0 else 'Inverted')\npmi_display=pmi_res['display'] if isinstance(pmi_res,dict) and pmi_res.get('value') is not None else ('N/A' if not pmi_applicable else 'Awaiting pack')\npmi_sub=pmi_res['sub'] if isinstance(pmi_res,dict) and pmi_res.get('value') is not None else pmi_state\npmi_src=pmi_res['source_type'] if isinstance(pmi_res,dict) and pmi_res.get('value') is not None else ('N/A' if not pmi_applicable else 'Awaiting')"
replace_once(old, new, "production PMI card no longer shows Seed/default")

# 7) get_pmi_df: macro_history_12m first; no DEFAULT_PMI_HISTORY or simulated trend.
pattern = r"def get_pmi_df\(chosen,latest_in\): if sel in PMI_NA_MARKETS: return pd\.DataFrame\(\) if sel in PMI_FRED_MARKETS: fred=fetch_fred_pmi\('NAPM'\) if not fred\.empty: return fred\.tail\(12\) hist_map=st\.session_state\.pmi_history\.get\(chosen\) or DEFAULT_PMI_HISTORY\.get\(chosen\) if hist_map: idx=pd\.to_datetime\(\[k\+'-01' for k in sorted\(hist_map\.keys\(\)\)\]\); vals=\[hist_map\[k\] for k in sorted\(hist_map\.keys\(\)\)\] return pd\.DataFrame\(\{'PMI':vals\},index=idx\)\.tail\(12\) dates=pd\.date_range\(end=pd\.Timestamp\.today\(\)\.normalize\(\),periods=12,freq='ME'\); vals=np\.linspace\(max\(latest_in\+1\.0,30\),latest_in,12\); st\.caption\('⚠️ Simulated PMI trend — click 🔄 Update PMI to fetch/save actual data\.'\); return pd\.DataFrame\(\{'PMI':vals\},index=dates\)"
repl = "def get_pmi_df(chosen,latest_in):\n    if sel in PMI_NA_MARKETS:\n        return pd.DataFrame()\n    # Production source: macro_pack_latest/macro_history_12m.csv first, then latest macro pack point only.\n    pack_pmi = resolve_macro_value(sel,'PMI')\n    hist_df = macro_trend_df(sel,'PMI',pack_pmi).rename(columns={'Value':'PMI'})\n    if hist_df is not None and not hist_df.empty:\n        return hist_df.tail(12)\n    # US FRED retained only as live official fallback when macro history is unavailable.\n    if sel in PMI_FRED_MARKETS:\n        fred=fetch_fred_pmi('NAPM')\n        if not fred.empty:\n            return fred.tail(12)\n    # Governance: do not fabricate/simulate PMI history and do not use DEFAULT_PMI_HISTORY for production charts.\n    return pd.DataFrame()"
regex_replace(pattern, repl, "PMI chart uses macro history / no simulated default", flags=re.S)

# 8) Live Market monitor local score should use pack PMI only; if missing, pass NaN so v2 excludes PMI.
old = "latest_display=0.0 if not pmi_app else latest_in local_score,local_alert,lvix,lcurve,lpmi,ldd,ltrend=calc_market_scores_by_asset(sel,latest_display,dd,trend_below,vix,curve_spread)"
new = "_local_pmi_res = resolve_macro_value(sel,'PMI')\nlatest_display = 0.0 if not pmi_app else (_local_pmi_res.get('value') if isinstance(_local_pmi_res,dict) and _local_pmi_res.get('value') is not None else float('nan'))\nlocal_score,local_alert,lvix,lcurve,lpmi,ldd,ltrend=calc_market_scores_by_asset(sel,latest_display,dd,trend_below,vix,curve_spread)"
replace_once(old, new, "Live Market score uses pack PMI only")

# 9) Audit freshness: show active pack PMI source, not session/default.
old = "left.markdown('#### 📡 Data Source & Freshness'); left.markdown('<div class=\"light-card\">'+kv('Market Data','Yahoo Finance',BLUE)+kv('Currency Display',f'{currency_symbol} / {currency_name}',GREEN)+kv('PMI Proxy',st.session_state.get('pmi_proxy_label',pmi_label),GREEN)+kv('PMI Value',f'{st.session_state.get(\"latest_pmi_value\",latest_pmi):.1f} · {st.session_state.get(\"latest_pmi_month\",\"\")}',GREEN)+kv('PMI Source',st.session_state.get('latest_pmi_source',pmi_proxy_default['source']),GREEN)+kv('Risk Model','Alternative asset' if sel in PMI_NA_MARKETS else 'Equity macro',PURPLE)+kv('Valuation Model','OOS Expanding Valuation Channel (Live Quant Model)',PURPLE)+kv('Bias Status','No look-ahead bias for OOS valuation model',GREEN)+kv('Last Refreshed',datetime.now().strftime('%d %b %Y %H:%M SGT'),SLATE)+'</div>',unsafe_allow_html=True)"
new = "left.markdown('#### 📡 Data Source & Freshness'); _audit_pmi_freshness=resolve_macro_value(index_label,'PMI'); _audit_pmi_value=(_audit_pmi_freshness.get('display','Awaiting pack') if isinstance(_audit_pmi_freshness,dict) else 'Awaiting pack'); _audit_pmi_source=(_audit_pmi_freshness.get('sub','Macro pack PMI') if isinstance(_audit_pmi_freshness,dict) else 'Macro pack PMI'); left.markdown('<div class=\"light-card\">'+kv('Market Data','Yahoo Finance',BLUE)+kv('Currency Display',f'{currency_symbol} / {currency_name}',GREEN)+kv('PMI Source of Truth','macro_pack_latest/macro_data.csv',GREEN)+kv('PMI Value',_audit_pmi_value,GREEN)+kv('PMI Source',_audit_pmi_source,GREEN)+kv('Risk Model','Alternative asset' if sel in PMI_NA_MARKETS else 'Equity macro',PURPLE)+kv('Valuation Model','OOS Expanding Valuation Channel (Live Quant Model)',PURPLE)+kv('Bias Status','No look-ahead bias for OOS valuation model',GREEN)+kv('Last Refreshed',datetime.now().strftime('%d %b %Y %H:%M SGT'),SLATE)+'</div>',unsafe_allow_html=True)"
replace_once(old, new, "Audit freshness uses macro pack PMI source")

# 10) Tactical snapshot export should not write default PMI value.
old = "'PMI Proxy':st.session_state.get('pmi_proxy_label',pmi_label),'PMI Value':st.session_state.get('latest_pmi_value',latest_pmi),"
new = "'PMI Proxy':'macro_pack_latest/macro_data.csv','PMI Value':(resolve_macro_value(index_label,'PMI').get('value') if isinstance(resolve_macro_value(index_label,'PMI'),dict) else None),"
replace_once(old, new, "snapshot export uses pack PMI")

# Write patched file.
TARGET.write_text(text, encoding='utf-8')

# Basic post-check scan.
scan_terms = {
    'Macro risk fallback removed': "try: pmi_v=float(pmi_value)" not in text,
    'PMI card no Seed fallback': "else 'Seed'" not in text,
    'No simulated PMI trend': "Simulated PMI trend" not in text,
    'No DEFAULT_PMI_HISTORY in get_pmi_df': not re.search(r"def get_pmi_df[\s\S]*?DEFAULT_PMI_HISTORY", text),
}
print("\nPost-check:")
for k,v in scan_terms.items():
    print(f"  {'PASS' if v else 'CHECK'}: {k}")

# Compile check. Existing file may have unrelated pre-existing syntax issues; report but do not erase patched file.
try:
    py_compile.compile(str(TARGET), doraise=True)
    print("\nCompile check: PASS")
except Exception as e:
    print(f"\nCompile check: CHECK MANUALLY — {e}")

print(f"\nBackup created: {backup}")
print(f"Patched file: {TARGET}")
print("Changes applied:", ', '.join(changes) if changes else 'none')
