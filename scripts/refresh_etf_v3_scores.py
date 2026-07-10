
python - <<'PY'
from pathlib import Path

path = Path("scripts/refresh_etf_v3_scores.py")
s = path.read_text(encoding="utf-8")

helper = '''
ROLE_ORDER_DEFAULT = {
    "CORE": 0,
    "DEFENSIVE": 1,
    "SATELLITE": 2,
    "THEMATIC": 3,
}

ROLE_ORDER_BY_MARKET = {
    # Broad market implementation first, then defensive, then satellites.
    "STI": {"CORE": 0, "DEFENSIVE": 1, "SATELLITE": 2, "THEMATIC": 3},
    "S&P 500": {"CORE": 0, "DEFENSIVE": 1, "SATELLITE": 2, "THEMATIC": 3},
    "NASDAQ": {"CORE": 0, "DEFENSIVE": 1, "SATELLITE": 2, "THEMATIC": 3},
    "DJIA": {"CORE": 0, "DEFENSIVE": 1, "SATELLITE": 2, "THEMATIC": 3},
    "HSI": {"CORE": 0, "DEFENSIVE": 1, "SATELLITE": 2, "THEMATIC": 3},
    "KLSE": {"CORE": 0, "DEFENSIVE": 1, "SATELLITE": 2, "THEMATIC": 3},
    "A-SHARE": {"CORE": 0, "DEFENSIVE": 1, "SATELLITE": 2, "THEMATIC": 3},
    "NIKKEI 225": {"CORE": 0, "DEFENSIVE": 1, "SATELLITE": 2, "THEMATIC": 3},

    # Gold implementation should prioritise defensive physical-gold vehicles.
    "GOLD": {"DEFENSIVE": 0, "CORE": 1, "SATELLITE": 2, "THEMATIC": 3},

    # Bitcoin products are usually satellite by design.
    "BITCOIN": {"SATELLITE": 0, "CORE": 1, "DEFENSIVE": 2, "THEMATIC": 3},
}


def role_priority_for_market(market, role):
    market_key = clean_text(market).upper()
    role_key = clean_text(role).upper()
    market_map = ROLE_ORDER_BY_MARKET.get(market_key, ROLE_ORDER_DEFAULT)
    return market_map.get(role_key, 9)
'''

if "def role_priority_for_market(" not in s:
    marker = "def clean_text(value):"
    if marker not in s:
        raise SystemExit("Could not find insertion point for role priority helper.")
    s = s.replace(marker, helper + "\n\n" + marker, 1)

old = '''        active_group.sort(
            key=lambda r: (
                -parse_float(r.get("implementation_fit_score"), 0.0),
                parse_float(r.get("rank"), 999),
                clean_text(r.get("instrument")),
            )
        )
'''

new = '''        active_group.sort(
            key=lambda r: (
                role_priority_for_market(market, r.get("role")),
                -parse_float(r.get("implementation_fit_score"), 0.0),
                parse_float(r.get("rank"), 999),
                clean_text(r.get("instrument")),
            )
        )
'''

if old not in s:
    raise SystemExit("Could not find old active_group.sort block. Please send script if patch fails.")

s = s.replace(old, new, 1)

s = s.replace(
    '[OK] Ranking method: implementation_fit_score then rank within market',
    '[OK] Ranking method: role_priority then implementation_fit_score within market'
)

path.write_text(s, encoding="utf-8")
print("[OK] Patched ETF v3.2 role-aware ranking logic.")
PY
