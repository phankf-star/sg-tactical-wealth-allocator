#!/usr/bin/env python3
# Patch LP-R1 landing visual balance only.
# Scope:
# - Increase Global Macro Risk Regime card width.
# - Reduce Current Market Environment card width.
# - Rebalance Global Macro Risk Regime gauge so it is smaller than original but not too tiny.
# - Keep Global Macro Risk Regime Option 1: status left, gauge right.
# - Prefer image-based sidebar logo if assets/cde_logo.png exists; otherwise keep CSS fallback.

from pathlib import Path
import os
import re
import sys
import py_compile

CANDIDATES = [
    os.environ.get('TARGET_FILE'),
    *sys.argv[1:],
    'Global20Engine_v38ac_LandingPage_Keep_LP-R1_LANDING_GAUGE35_LOGO.py',
    'Global20Engine_v38ac_LandingPage_Keep_LP-R1_LANDING_ONLY_FINAL.py',
    'Global20Engine_v38ac_LandingPage_Keep.py',
    'sg_tactical_wealth_allocator.py',
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

text = re.sub(
    r"\.cde-kpi-grid\{grid-template-columns:[^}]+\}",
    ".cde-kpi-grid{grid-template-columns:1fr 1fr 1.35fr 1.15fr}",
    text,
    count=1,
)
text = re.sub(
    r"\.cde-risk-flex\{display:grid;grid-template-columns:1fr\s+\d+px;gap:\d+px;align-items:center\}",
    ".cde-risk-flex{display:grid;grid-template-columns:1fr 88px;gap:8px;align-items:center}",
    text,
    count=1,
)
text = re.sub(
    r"\.cde-risk-gauge-side\{height:\d+px;overflow:hidden;display:flex;align-items:center;justify-content:[^}]+\}",
    ".cde-risk-gauge-side{height:48px;overflow:hidden;display:flex;align-items:center;justify-content:flex-end}",
    text,
    count=1,
)
text = re.sub(
    r"\.cde-risk-gauge-side svg\{width:\d+px;height:\d+px\}",
    ".cde-risk-gauge-side svg{width:88px;height:58px}",
    text,
    count=1,
)
text = re.sub(
    r"\.cde-env-compact\{display:grid;grid-template-columns:1fr 1fr;gap:[^}]+\}",
    ".cde-env-compact{display:grid;grid-template-columns:1fr 1fr;gap:4px 8px;margin-top:9px;font-size:11.5px;color:#334155;font-weight:850;line-height:1.3}",
    text,
    count=1,
)

# Optional logo image support. If assets/cde_logo.png exists, use it; else keep CSS fallback.
sidebar_logo_pattern = r"(with st\.sidebar:\n\s*)st\.markdown\('''<div class=\"cde-logo-card\"[\s\S]*?</div></div>'''\s*,\s*unsafe_allow_html=True\)"
replacement = r"\1logo_asset = Path('assets/cde_logo.png')\n    if logo_asset.exists():\n        st.image(str(logo_asset), use_container_width=True)\n    else:\n        st.markdown('''<div class=\"cde-logo-card\"><div class=\"cde-logo-mark\"></div><div><div class=\"cde-logo-main\">CRASH</div><div class=\"cde-logo-sub\">DEPLOYMENT ENGINE</div><div class=\"cde-logo-tag\">Turning Market Crash into Opportunities</div></div></div>''', unsafe_allow_html=True)"
text = re.sub(sidebar_logo_pattern, replacement, text, count=1)

if text == original:
    raise RuntimeError('Patch made no changes. Check target file structure.')

backup = target.with_suffix(target.suffix + '.bak_lp_r1_visual_balance')
backup.write_text(original, encoding='utf-8')
target.write_text(text, encoding='utf-8')
py_compile.compile(str(target), doraise=True)

nav_line = re.search(r"NAV_OPTIONS = .*", text)
checks = {
    'kpi_ratio_updated': '.cde-kpi-grid{grid-template-columns:1fr 1fr 1.35fr 1.15fr}' in text,
    'gauge_right_size_updated': '.cde-risk-gauge-side svg{width:88px;height:58px}' in text,
    'env_compact_updated': 'gap:4px 8px;margin-top:9px;font-size:11.5px' in text,
    'optional_image_logo': "logo_asset = Path('assets/cde_logo.png')" in text,
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
