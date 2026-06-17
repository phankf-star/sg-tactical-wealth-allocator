#!/usr/bin/env python3
# v36.1 Institutional Cleanup Patch for Global Drawdown Allocation Engine
# Applies R1 currency fix, R2 event labels, R3 naming, R4 crash structure, R5 event drivers.
from pathlib import Path
import re
import py_compile

py_files = sorted(Path('.').glob('Global Drawdown Allocation Engine*.py'))
if not py_files:
    raise FileNotFoundError('No Global Drawdown Allocation Engine .py file found in this folder.')
preferred = [p for p in py_files if ('phase2' in p.name.lower() or 'v36' in p.name.lower())]
src = preferred[-1] if preferred else py_files[-1]
text = src.read_text(encoding='utf-8')

# R1 currency helpers
colour_line = "BLUE = '#2563EB'; RED = '#EF4444'; ORANGE = '#F97316'; AMBER = '#F59E0B'; GREEN = '#16A34A'; SLATE = '#64748B'; PURPLE = '#7C3AED'; TEXT = '#111827'; MUTED = '#6B7280'"
helper = """

# Currency display helpers.
# Use HTML entity for dollar sign inside Markdown/HTML-rendered blocks to avoid Streamlit LaTeX parsing.
SGD_TEXT = 'S$'          # for metric widgets / dataframe values
SGD_HTML = 'S&#36;'       # for st.markdown(..., unsafe_allow_html=True)
def fmt_sgd(value):
    return f'{SGD_TEXT}{value:,.0f}'
def fmt_sgd_html(value):
    return f'{SGD_HTML}{value:,.0f}'
"""
if 'SGD_HTML' not in text and colour_line in text:
    text = text.replace(colour_line, colour_line + helper, 1)

pattern = re.compile(r"s1\.markdown\(f['"]#### .*?Suggested Deploy Basis.*?Source: selected price data, \{ref\} drawdown formula, and sidebar capital inputs\.['"]\)", re.S)
replacement = (
    "s1.markdown("
    "f'<div class=\"light-card\">'"
    "f'<div style=\"font-weight:700; font-size:1.05rem; margin-bottom:8px;\">📌 Suggested Deploy Basis</div>'"
    "f'<div style=\"color:#374151; margin-bottom:8px;\">Suggested Deploy = Available Deployable Capital × Deployment Rule</div>'"
    "f'<div style=\"font-size:1.45rem; font-weight:800; color:#111827; margin:8px 0;\">{SGD_HTML}{deploy:,.0f} = {SGD_HTML}{total_available:,.0f} × {deploy_pct:.0%}</div>'"
    "f'<div style=\"color:#6B7280; font-size:0.88rem;\">Source: selected price data, {ref} drawdown formula, and sidebar capital inputs.</div>'"
    "f'</div>', unsafe_allow_html=True)"
)
text, _ = pattern.subn(replacement, text, count=1)

for old, new in {
    "f'S${deploy:,.0f}'": "fmt_sgd(deploy)",
    'f"S${deploy:,.0f}"': "fmt_sgd(deploy)",
    "f'S${cash_deploy:,.0f}'": "fmt_sgd(cash_deploy)",
    "f'S${srs_deploy:,.0f}'": "fmt_sgd(srs_deploy)",
    "f'S${cpf_deploy:,.0f}'": "fmt_sgd(cpf_deploy)",
    "f'S${deploy*.5:,.0f}'": "fmt_sgd(deploy*.5)",
    "f'S${deploy*.25:,.0f}'": "fmt_sgd(deploy*.25)",
    "f'S${inv_one:,.0f}'": "fmt_sgd(inv_one)",
    "f'S${val_today:,.0f}'": "fmt_sgd(val_today)",
    "f'S${total:,.0f}'": "fmt_sgd(total)",
    "f'S${ending:,.0f}'": "fmt_sgd(ending)",
    "f'S${gain:,.0f}'": "fmt_sgd(gain)",
}.items():
    text = text.replace(old, new)
text = text.replace("decision_line=f'Deploy approximately S${deploy:,.0f} using staged tranches.'", "decision_line=f'Deploy approximately {fmt_sgd(deploy)} using staged tranches.'")
text = re.sub(r"SGD_MD\s*=\s*['"].*?['"].*?\n", "", text)

# R3 naming cleanup
text = text.replace('曾氏通道 (Trend Channel Line) — Secular Valuation Engine', 'Quantitative Valuation Channels')
text = text.replace('### 曾氏通道 (TREND CHANNEL LINE) — SECULAR VALUATION ENGINE', '### Quantitative Valuation Channels')
text = text.replace('Expanding Window (OOS – Live Model)', 'OOS Expanding Valuation Channel (Live Quant Model)')
text = text.replace('Rolling 15Y Window (OOS)', 'Rolling OOS Valuation Channel — 15Y Adaptive Window')
text = text.replace('Full History (Research View)', '曾氏通道 — Full-History Secular Channel (Research Only)')
text = text.replace('Full History Model (Research Only)', '曾氏通道 — Full-History Secular Channel (Research Only)')
text = text.replace('("2020-02-01", "2020-04-30", "2020 COVID-19 Crash")', '("2020-02-01", "2020-04-30", "2020 COVID-19")')

# R2 event labels on channel chart
if 'event_year = parts[0]' not in text and 'for start, end, label in CRISIS_EVENTS:' in text:
    vrect_pattern = re.compile(r"for start, end, label in CRISIS_EVENTS:\n(?P<body>(?:\s+.*\n){1,12}?\s+fig\.add_vrect\(.*?\)\n)", re.S)
    def add_event_annotation(m):
        body = m.group('body')
        annotation = (
            "            mid = x0 + (x1 - x0) / 2\n"
            "            parts = label.split(' ', 1)\n"
            "            event_year = parts[0]\n"
            "            event_name = parts[1] if len(parts) > 1 else ''\n"
            "            fig.add_annotation(x=mid, y=0.96, yref='paper', text=f'<b>{event_year}</b><br>{event_name}', showarrow=False, font=dict(size=10, color='#111827'), align='center', bgcolor='rgba(255,255,255,0.78)', borderwidth=0, borderpad=2)\n"
        )
        return "for start, end, label in CRISIS_EVENTS:\n" + body + annotation
    text, _ = vrect_pattern.subn(add_event_annotation, text, count=1)

# R5 richer event context
context_code = """

EVENT_CONTEXT_MAP = {
    '1987 Black Monday': {'primary_driver':'Market-structure shock / liquidity stress','driver_tags':['Market structure','Liquidity stress','Programme trading','Portfolio insurance'],'key_causes':['Asset-bubble concern after rapid market gains','Trade-deficit and US dollar pressure','Programme trading / portfolio-insurance selling','Margin calls and trading-system strain'],'interpretation':'A fast market-structure crash rather than a normal earnings-cycle recession.'},
    'Dot-com Bust': {'primary_driver':'Technology valuation bubble unwind','driver_tags':['Valuation bubble','Technology','Speculation','Capital tightening'],'key_causes':['Extreme internet and technology-stock valuations','Weak profitability discipline in many dot-com companies','Venture capital and IPO speculation','Rising-rate / capital-tightening pressure'],'interpretation':'A valuation-led bubble unwind.'},
    'Global Financial Crisis': {'primary_driver':'Credit / banking crisis','driver_tags':['Credit crisis','Housing bubble','Banking stress','Mortgage risk'],'key_causes':['Subprime mortgage expansion','Housing bubble and falling home prices','Mortgage-backed securities losses','Bank funding stress and credit contraction'],'interpretation':'A systemic credit crisis with broad financial-sector stress.'},
    'COVID Shock': {'primary_driver':'Pandemic / liquidity shock','driver_tags':['Pandemic','Lockdowns','Liquidity stress','Recession fear'],'key_causes':['COVID-19 pandemic uncertainty','Lockdowns and economic-shutdown risk','Liquidity stress and forced de-risking','Sharp recession fears'],'interpretation':'A fast exogenous macro shock rather than a valuation bubble unwind.'},
    'COVID-19': {'primary_driver':'Pandemic / liquidity shock','driver_tags':['Pandemic','Lockdowns','Liquidity stress','Recession fear'],'key_causes':['COVID-19 pandemic uncertainty','Lockdowns and economic-shutdown risk','Liquidity stress and forced de-risking','Sharp recession fears'],'interpretation':'A fast exogenous macro shock rather than a valuation bubble unwind.'},
    'Rate-Hike Cycle': {'primary_driver':'Inflation and monetary tightening','driver_tags':['Inflation','Interest rates','QT','Bond yields'],'key_causes':['High inflation','Rapid central-bank rate hikes','Higher bond yields','Valuation compression in long-duration / growth assets'],'interpretation':'A policy-tightening and valuation-compression cycle.'},
    'Inflation & Rate Hike': {'primary_driver':'Inflation, rate hikes and geopolitical / energy shock','driver_tags':['Inflation','Interest rates','War','Energy shock','Supply chain'],'key_causes':['High inflation','Rapid central-bank tightening','Russia-Ukraine-war-related supply disruption','Energy and commodity-price pressure','Recession fears and valuation compression'],'interpretation':'A macro tightening cycle amplified by war-related supply and energy shocks.'},
    'China Devaluation / Oil Shock': {'primary_driver':'Currency / commodity shock','driver_tags':['Currency stress','Oil shock','China growth concern','Risk-off'],'key_causes':['China currency devaluation / growth concern','Oil-price weakness or commodity stress','Emerging-market risk-off sentiment','Global growth slowdown concern'],'interpretation':'A macro risk-off drawdown linked to currency and commodity stress.'},
    'Asian Financial Crisis': {'primary_driver':'Currency / capital-flow crisis','driver_tags':['Currency stress','Capital outflow','Banking stress','Regional contagion'],'key_causes':['Currency devaluation pressure','Regional capital outflows','Banking and balance-sheet stress','Contagion across Asian equity and FX markets'],'interpretation':'A regional currency and capital-flow crisis rather than a pure valuation-cycle correction.'},
    'US-China Trade War': {'primary_driver':'Trade-war / geopolitical risk-off','driver_tags':['Trade war','Tariffs','Geopolitics','Growth slowdown'],'key_causes':['Tariff escalation and trade-policy uncertainty','Pressure on global manufacturing and supply chains','Risk-off rotation from cyclical and export-sensitive assets'],'interpretation':'A geopolitical and trade-policy shock with growth-slowdown risk.'},
}

def get_event_context(label):
    label = str(label)
    for key, context in EVENT_CONTEXT_MAP.items():
        if key in label:
            return context
    return {'primary_driver':'Unclassified / not mapped','driver_tags':['Data-defined drawdown'],'key_causes':['No mapped major macro-crisis label is attached to this event.','Interpret using observed drawdown, Z-score movement and recovery outcome.'],'interpretation':'This should be treated as a data-defined drawdown cycle unless manually tagged.'}

def render_event_context_card(row):
    ctx = get_event_context(row.get('Historical Label', ''))
    causes_html = ''.join([f'<li>{c}</li>' for c in ctx['key_causes']])
    tags = ' · '.join(ctx['driver_tags'])
    z_peak = row.get('Z @ Peak', np.nan)
    z_trough = row.get('Z @ Trough', np.nan)
    z_line = 'N/A' if pd.isna(z_peak) or pd.isna(z_trough) else f'{z_peak:+.2f} → {z_trough:+.2f}'
    st.markdown(f'<div class="light-card"><div style="font-weight:800; font-size:1.05rem; margin-bottom:8px;">📌 Event Context & Market Drivers</div><div class="kv"><div class="kv-label">Primary Driver</div><div class="kv-value" style="color:{PURPLE};">{ctx["primary_driver"]}</div></div><div class="kv"><div class="kv-label">Driver Tags</div><div class="kv-value">{tags}</div></div><div class="kv"><div class="kv-label">Z-Score Path</div><div class="kv-value">{z_line}</div></div><div style="margin-top:8px; color:#374151;"><b>Key causes / context:</b><ul style="margin-top:6px;">{causes_html}</ul></div><div style="margin-top:8px; color:#374151;"><b>Interpretation:</b> {ctx["interpretation"]}</div></div>', unsafe_allow_html=True)
"""
if 'EVENT_CONTEXT_MAP' not in text:
    idx = text.find('def render_crash(')
    text = text[:idx] + context_code + '
' + text[idx:] if idx != -1 else text + context_code

if 'render_event_context_card(row)' not in text:
    text = re.sub(r"(row\s*=\s*src\.iloc\[labels\.index\(chosen_event\)\].*?\n)", r"            render_event_context_card(row)
", text, count=1)

# R4 crash section restructure
text = text.replace('## 🏛️ Valuation at Crash Engine', '## 🔍 Crash Event Explorer & Valuation Context')
text = text.replace('## 🔍 Interactive Event Explorer', '## 🔍 Crash Event Explorer & Valuation Context')
text = text.replace('Interactive Event Explorer', 'Crash Event Explorer & Valuation Context')
text = text.replace('Historical Crash Explorer', 'Inspect Event Detail')

if 'Valuation classification filter' not in text and "label_opts = ['All']" in text:
    text = text.replace("f1,f2,f3=st.columns([1,1,1])", "f1,f2,f3,f4=st.columns([1,1,1,1])", 1)
    text = text.replace("label_sel=f3.selectbox('Historical label group',label_opts,index=0)", "label_sel=f3.selectbox('Historical label group',label_opts,index=0)
        val_class_opts=['All']+sorted(event_df['Valuation Classification'].dropna().unique().tolist())
        val_class_sel=f4.selectbox('Valuation classification filter',val_class_opts,index=0)", 1)
    text = text.replace("filtered_df=filtered_df[filtered_df['Historical Label']==label_sel] if label_sel!='All' else filtered_df", "filtered_df=filtered_df[filtered_df['Historical Label']==label_sel] if label_sel!='All' else filtered_df
        filtered_df=filtered_df[filtered_df['Valuation Classification']==val_class_sel] if val_class_sel!='All' else filtered_df", 1)

if 'Full Crash Event Universe / Audit Table' not in text:
    audit_snippet = """
        # Full audit layer — complete, unfiltered event universe.
        audit_cols = ['Peak Date', 'Peak Index', 'Trough Date', 'Trough Index', 'Drawdown %', 'Recovery Return %', 'Zone', 'Historical Label', 'Severity', 'Z @ Peak', 'Z @ Trough', 'Valuation Classification']
        full_display = event_df[audit_cols].copy()
        for c in ['Peak Date', 'Trough Date']:
            full_display[c] = pd.to_datetime(full_display[c]).dt.strftime('%Y-%m-%d')
        for c in ['Peak Index', 'Trough Index', 'Drawdown %', 'Recovery Return %', 'Z @ Peak', 'Z @ Trough']:
            full_display[c] = full_display[c].astype(float).round(2)
        with st.expander('📚 Full Crash Event Universe / Audit Table', expanded=False):
            st.caption('Complete unfiltered event universe used by the explorer, valuation context layer and simulator. Kept collapsed as the audit trail.')
            st.dataframe(full_display, use_container_width=True, hide_index=True)
            st.download_button('⬇️ Export Full Crash Events CSV', full_display.to_csv(index=False), file_name='crash_events_full_phase2.csv', mime='text/csv')
"""
    idx = text.find('def render_audit(')
    if idx != -1:
        text = text[:idx] + audit_snippet + '
' + text[idx:]

text = text.replace("kv('Market Data','Yahoo Finance',BLUE)+", "kv('Market Data','Yahoo Finance',BLUE)+kv('Currency Display','S$ / Singapore dollar',GREEN)+", 1)

out = src.with_name(src.stem + '_v36_1_institutional_cleanup.py')
out.write_text(text, encoding='utf-8')
py_compile.compile(str(out), doraise=True)
print(f'Created: {out}')
print('Syntax check: passed')
print('Applied R1 currency fix, R2 event labels, R3 naming cleanup, R4 crash restructure, R5 event driver context.')
