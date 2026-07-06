#!/usr/bin/env python3
# Patch LP-R1 Global Macro Risk Regime balance only.
# Fixes: SVG gauge still distorted / card too wide.
# Approach: replace SVG gauge with compact CSS risk meter; rebalance KPI card widths.
# Scope: landing visual balance only. Logo is not touched.

from pathlib import Path
import os
import re
import sys
import py_compile

CANDIDATES = [
    os.environ.get('TARGET_FILE'),
    *sys.argv[1:],
    'sg_tactical_wealth_allocator.py',
    'Global20Engine_v38ac_LandingPage_Keep_LP-R1_LANDING_GAUGE35_LOGO.py',
    'Global20Engine_v38ac_LandingPage_Keep_LP-R1_LANDING_ONLY_FINAL.py',
    'Global20Engine_v38ac_LandingPage_Keep.py',
]

target = None
for item in CANDIDATES:
    if item and Path(item).exists():
        target = Path(item)
        break
if target is None:
    raise FileNotFoundError('No target app file found. Pass path as argument or set TARGET_FILE.')

text = target.read_text(encoding='utf-8')
original = text

# 1) Rebalance top KPI cards: Global Macro Risk remains slightly wider, but not oversized.
text = re.sub(
    r"\.cde-kpi-grid\{grid-template-columns:[^}]+\}",
    ".cde-kpi-grid{grid-template-columns:1fr 1fr 1.18fr 1.12fr}",
    text,
    count=1,
)

# 2) Replace old SVG gauge CSS with compact CSS meter styling.
# Remove/override old gauge side definitions regardless of previous values.
text = re.sub(
    r"\.cde-risk-flex\{display:grid;grid-template-columns:1fr\s+\d+px;gap:\d+px;align-items:center\}",
    ".cde-risk-flex{display:grid;grid-template-columns:1fr 78px;gap:6px;align-items:center}",
    text,
    count=1,
)
text = re.sub(
    r"\.cde-risk-gauge-side\{height:\d+px;overflow:hidden;display:flex;align-items:center;justify-content:[^}]+\}",
    ".cde-risk-gauge-side{height:44px;display:flex;align-items:center;justify-content:flex-end;overflow:visible}",
    text,
    count=1,
)
text = re.sub(
    r"\.cde-risk-gauge-side svg\{[^}]+\}",
    ".cde-risk-gauge-side svg{display:none}",
    text,
    count=1,
)

# Add compact CSS meter if not already present.
if '.cde-risk-mini-meter' not in text:
    insert_after = '.cde-risk-gauge-side svg{display:none}'
    meter_css = (
        '.cde-risk-mini-meter{width:66px;height:30px;position:relative;display:flex;align-items:flex-end;justify-content:center}'
        '.cde-risk-mini-arc{width:58px;height:29px;border-radius:58px 58px 0 0;background:conic-gradient(from 270deg,#22c55e 0deg,#22c55e 54deg,#facc15 54deg,#facc15 108deg,#f97316 108deg,#ef4444 180deg,transparent 180deg);position:absolute;bottom:0}'
        '.cde-risk-mini-arc:after{content:"";position:absolute;left:8px;right:8px;bottom:0;height:21px;background:#fff;border-radius:42px 42px 0 0}'
        '.cde-risk-mini-needle{position:absolute;bottom:0;left:50%;width:2px;height:24px;background:#0f172a;transform:rotate(var(--needle));transform-origin:bottom center;border-radius:2px}'
    )
    text = text.replace(insert_after, insert_after + meter_css, 1)

# 3) Replace SVG gauge generation with CSS mini meter generation in render_executive.
# The needle maps score 0..100 to -90..90 degrees.
old = "risk_gauge_html=svg_risk_gauge(global_risk_score,'Scorecard')"
new = "risk_needle_deg=max(-90,min(90,(safe_float(global_risk_score,0)/100*180)-90)); risk_gauge_html=f'<div class=\"cde-risk-mini-meter\"><div class=\"cde-risk-mini-arc\"></div><div class=\"cde-risk-mini-needle\" style=\"--needle:{risk_needle_deg:.0f}deg\"></div></div>'"
if old in text:
    text = text.replace(old, new, 1)
else:
    # In case spacing differs
    text = re.sub(r"risk_gauge_html\s*=\s*svg_risk_gauge\(global_risk_score\s*,\s*['\"]Scorecard['\"]\)", new, text, count=1)

# 4) Current Environment remains compact; ensure it does not become too wide internally.
text = re.sub(
    r"\.cde-env-compact\{display:grid;grid-template-columns:1fr 1fr;gap:[^}]+\}",
    ".cde-env-compact{display:grid;grid-template-columns:1fr 1fr;gap:4px 8px;margin-top:9px;font-size:11.5px;color:#334155;font-weight:850;line-height:1.3}",
    text,
    count=1,
)

if text == original:
    raise RuntimeError('Patch made no changes. Check target file structure / CSS names.')

backup = target.with_suffix(target.suffix + '.bak_lp_r1_macro_card_balance')
backup.write_text(original, encoding='utf-8')
target.write_text(text, encoding='utf-8')
py_compile.compile(str(target), doraise=True)

nav_line = re.search(r"NAV_OPTIONS = .*", text)
checks = {
    'kpi_ratio_balanced': '.cde-kpi-grid{grid-template-columns:1fr 1fr 1.18fr 1.12fr}' in text,
    'svg_hidden': '.cde-risk-gauge-side svg{display:none}' in text,
    'css_meter_present': '.cde-risk-mini-meter' in text and 'cde-risk-mini-needle' in text,
    'svg_function_not_used_for_landing': "risk_gauge_html=svg_risk_gauge(global_risk_score,'Scorecard')" not in text,
    'logo_not_removed': 'assets/cde_logo.png' in text or 'cde-logo-card' in text,
    'market_performance_hidden_nav': "'📊 Market Performance'" not in nav_line.group(0) if nav_line else True,
    'render_performance_kept': 'def render_performance' in text and 'render_performance(expanded=False)' in text,
}
failed = [k for k, v in checks.items() if not v]
if failed:
    raise AssertionError('Patch sanity checks failed: ' + ', '.join(failed))

print(f'PATCH_OK target={target}')
print(f'BACKUP={backup}')
for k, v in checks.items():
    print(f'{k}={v}')
