#!/usr/bin/env python3
# Patch LP-R1 Global Macro Risk Regime gauge shape only.
# Scope: Fix distorted gauge by preserving SVG aspect ratio with scale transform.
# Do not touch logo, layout order, Market Opportunity Overview, Command Centre, or data logic.

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

# Keep the Global Macro Risk card wider enough to prevent tooltip wrapping and preserve layout balance.
text = re.sub(
    r"\.cde-kpi-grid\{grid-template-columns:[^}]+\}",
    ".cde-kpi-grid{grid-template-columns:1fr 1fr 1.35fr 1.15fr}",
    text,
    count=1,
)

# Gauge-only shape fix: keep container compact, but do not distort SVG width/height.
# The SVG keeps its own aspect ratio; visual size is controlled by transform scale.
text = re.sub(
    r"\.cde-risk-flex\{display:grid;grid-template-columns:1fr\s+\d+px;gap:\d+px;align-items:center\}",
    ".cde-risk-flex{display:grid;grid-template-columns:1fr 95px;gap:8px;align-items:center}",
    text,
    count=1,
)
text = re.sub(
    r"\.cde-risk-gauge-side\{height:\d+px;overflow:hidden;display:flex;align-items:center;justify-content:[^}]+\}",
    ".cde-risk-gauge-side{height:52px;overflow:hidden;display:flex;align-items:center;justify-content:flex-end}",
    text,
    count=1,
)
text = re.sub(
    r"\.cde-risk-gauge-side svg\{width:\d+px;height:\d+px\}",
    ".cde-risk-gauge-side svg{width:95px;height:auto;transform:scale(0.75);transform-origin:center center}",
    text,
    count=1,
)

# If a previous patch added width/height but no transform, handle that case too.
if '.cde-risk-gauge-side svg{width:95px;height:auto;transform:scale(0.75);transform-origin:center center}' not in text:
    text = text.replace(
        '.cde-risk-gauge-side svg{width:95px;height:auto}',
        '.cde-risk-gauge-side svg{width:95px;height:auto;transform:scale(0.75);transform-origin:center center}'
    )

if text == original:
    raise RuntimeError('Patch made no changes. Check target file structure / CSS names.')

backup = target.with_suffix(target.suffix + '.bak_lp_r1_gauge_shape')
backup.write_text(original, encoding='utf-8')
target.write_text(text, encoding='utf-8')
py_compile.compile(str(target), doraise=True)

nav_line = re.search(r"NAV_OPTIONS = .*", text)
checks = {
    'kpi_ratio_kept': '.cde-kpi-grid{grid-template-columns:1fr 1fr 1.35fr 1.15fr}' in text,
    'gauge_aspect_ratio_fixed': '.cde-risk-gauge-side svg{width:95px;height:auto;transform:scale(0.75);transform-origin:center center}' in text,
    'gauge_container_compact': '.cde-risk-gauge-side{height:52px;overflow:hidden;display:flex;align-items:center;justify-content:flex-end}' in text,
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
