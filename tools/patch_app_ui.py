
from pathlib import Path

APP_FILE = Path("sg_tactical_wealth_allocator.py")

if not APP_FILE.exists():
    print("Repo root Python files found:")
    for f in sorted(Path(".").glob("*.py")):
        print(" -", f)
    raise FileNotFoundError(f"App file not found: {APP_FILE}")

print(f"Using app file: {APP_FILE}")

text = APP_FILE.read_text(encoding="utf-8")


def replace_function(text, func_name, new_func):
    start = text.find(f"def {func_name}(")
    if start == -1:
        print(f"WARNING: function {func_name} not found. No replacement made.")
        return text, False

    next_def = text.find("\ndef ", start + 1)
    if next_def == -1:
        next_def = len(text)

    old_func = text[start:next_def]
    text = text[:start] + new_func.rstrip() + "\n" + text[next_def:]
    print(f"Replaced function: {func_name}")
    return text, True


# ------------------------------------------------------------
# PATCH 1: Remove Yahoo-style wording
# ------------------------------------------------------------
before = text

text = text.replace(
    "# 1. Yahoo-style price chart. Visible once the monitor is opened.",
    "# 1. Index price chart. Visible once the monitor is opened."
)

text = text.replace(
    "st.markdown('### 📉 Yahoo-style Index Price Chart')",
    "st.markdown('### 📉 Index Price Chart')"
)

text = text.replace(
    "Yahoo-style Index Price Chart",
    "Index Price Chart"
)

if text != before:
    print("Patched Yahoo-style wording.")
else:
    print("Yahoo-style wording already clean or not found.")


# ------------------------------------------------------------
# PATCH 2: Replace render_macro_line_chart flexibly
# ------------------------------------------------------------
new_render_macro_line_chart = '''
def render_macro_line_chart(df, title, subtitle='', colour=BLUE, y_title='Value'):
    if df is None or df.empty:
        st.info(f'{title}: actual trend data unavailable.')
        return

    df = df.copy()
    df.index = pd.to_datetime(df.index, errors='coerce')
    df = df[df.index.notna()].sort_index()

    col = df.columns[0]
    df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=[col])

    if df.empty:
        st.info(f'{title}: actual trend data unavailable.')
        return

    # Normalise monthly macro dates to month-start to avoid timestamp-like x-axis labels.
    if len(df) <= 18:
        df.index = df.index.to_period('M').to_timestamp()

    mode = 'lines+markers' if len(df) >= 2 else 'markers'

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df[col],
        mode=mode,
        line=dict(color=colour, width=2),
        marker=dict(size=6),
        hovertemplate='%{x|%b %Y}<br>%{y:.2f}<extra></extra>'
    ))

    fig.update_layout(
        height=250,
        margin=dict(l=10, r=10, t=52, b=18),
        title=f'{title}<br><sup>{subtitle}</sup>',
        plot_bgcolor='white',
        paper_bgcolor='white',
        showlegend=False,
        yaxis_title=y_title,
        xaxis=dict(
            type='date',
            tickformat='%b %Y',
            showgrid=False
        )
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
'''

text, ok1 = replace_function(text, "render_macro_line_chart", new_render_macro_line_chart)


# ------------------------------------------------------------
# PATCH 3: Replace macro_trend_df flexibly
# ------------------------------------------------------------

new_macro_trend_df = '''
def macro_trend_df(market, indicator, fallback_result=None):
    history_file = Path("macro_pack_latest/macro_history_12m.csv")

    frames = []

    if history_file.exists():
        try:
            hist_df = pd.read_csv(history_file)
            hist_df.columns = [str(c).strip().lower() for c in hist_df.columns]

            if {"market", "indicator", "date", "value"}.issubset(set(hist_df.columns)):
                frames.append(hist_df)
        except Exception:
            pass

    # Backward compatibility: old macro pack / overrides still work.
    df = _macro_pack_history(market, indicator)
    if not df.empty:
        tmp = df.reset_index().rename(columns={"Date": "date", "Value": "value"})
        tmp["market"] = market
        tmp["indicator"] = indicator
        tmp["unit"] = "%"
        tmp["source"] = "legacy macro pack history"
        tmp["source_type"] = "Legacy"
        tmp["notes"] = ""
        frames.append(tmp)

    if frames:
        raw = pd.concat(frames, ignore_index=True)
        raw.columns = [str(c).strip().lower() for c in raw.columns]

        aliases = {
            market,
            MARKET_UPLOAD_ALIASES.get(market, market),
            PLATFORM_TO_UPLOAD_ALIAS.get(market, market),
        }

        inds = {
            indicator,
            "Jobs" if indicator == "Unemployment" else indicator,
            "Unemployment" if indicator == "Jobs" else indicator,
        }

        sub = raw[
            raw["market"].astype(str).str.upper().isin({str(x).upper() for x in aliases})
            & raw["indicator"].astype(str).str.lower().isin({str(x).lower() for x in inds})
        ].copy()

        if not sub.empty:
            sub["Date"] = pd.to_datetime(sub["date"], errors="coerce")
            sub["Value"] = pd.to_numeric(sub["value"], errors="coerce")
            sub = sub.dropna(subset=["Date", "Value"]).sort_values("Date")

            if not sub.empty:
                sub["Month"] = sub["Date"].dt.to_period("M")
                sub = sub.drop_duplicates(["Month"], keep="last")
                sub["Date"] = sub["Month"].dt.to_timestamp()
                return sub[["Date", "Value"]].set_index("Date").tail(12)

    # Fallback: latest point only. Do not fake history.
    if isinstance(fallback_result, dict) and fallback_result.get("value") is not None:
        dt = pd.to_datetime(fallback_result.get("date", ""), errors="coerce")
        if pd.isna(dt):
            dt = pd.Timestamp.today().normalize()
        dt = dt.to_period("M").to_timestamp()
        return pd.DataFrame({"Value": [float(fallback_result.get("value"))]}, index=[dt])

    return pd.DataFrame()
'''

text, ok2 = replace_function(text, "macro_trend_df", new_macro_trend_df)


# ------------------------------------------------------------
# PATCH 4: Clean PMI bar chart title and remove overlapping labels
# ------------------------------------------------------------
new_mini_pmi_bar_chart = '''
def mini_pmi_bar_chart(df,title,subtitle):
    if df is None or df.empty or 'PMI' not in df.columns:
        st.info(f'{title}: data unavailable')
        return

    df = df.copy()
    df.index = pd.to_datetime(df.index, errors='coerce')
    df = df[df.index.notna()].sort_index()
    df['PMI'] = pd.to_numeric(df['PMI'], errors='coerce')
    df = df.dropna(subset=['PMI']).tail(12)

    if df.empty:
        st.info(f'{title}: data unavailable')
        return

    colours = [GREEN if v >= 50 else RED for v in df.PMI]

    # Keep title compact to avoid overlap inside two-column layout.
    clean_title = 'PMI 12M Monthly Releases'

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df.index,
        y=df.PMI,
        marker_color=colours,
        text=None,
        hovertemplate='%{x|%b %Y}<br>PMI: %{y:.1f}<extra></extra>'
    ))

    fig.add_hline(
        y=50,
        line_dash='dash',
        line_color=SLATE,
        annotation_text='50 Expansion / Contraction',
        annotation_position='top left'
    )

    fig.update_layout(
        height=250,
        margin=dict(l=10, r=10, t=58, b=10),
        title=f'{clean_title}<br><sup>{subtitle}</sup>',
        plot_bgcolor='white',
        paper_bgcolor='white',
        showlegend=False,
        yaxis_title='PMI',
        xaxis=dict(
            type='date',
            tickformat='%b %Y',
            showgrid=False
        )
    )

    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
'''
text, ok3 = replace_function(text, "mini_pmi_bar_chart", new_mini_pmi_bar_chart)



# ------------------------------------------------------------
# PATCH 5: Add rates history reader for 252D rates mini chart
# ------------------------------------------------------------
rates_history_helper = '''
def rates_history_trend_df(market, fallback_result=None, limit=252):
    rates_file = Path("macro_pack_latest/rates_history_252d.csv")

    if rates_file.exists():
        try:
            df = pd.read_csv(rates_file)
            df.columns = [str(c).strip().lower() for c in df.columns]

            market_cols = [c for c in ["market", "country", "region"] if c in df.columns]
            date_col = "date" if "date" in df.columns else None

            value_col = None
            for c in ["value", "rate", "rates", "yield", "close"]:
                if c in df.columns:
                    value_col = c
                    break

            if date_col and value_col:
                if market_cols:
                    mcol = market_cols[0]
                    aliases = {
                        market,
                        MARKET_UPLOAD_ALIASES.get(market, market),
                        PLATFORM_TO_UPLOAD_ALIAS.get(market, market),
                    }

                    sub = df[
                        df[mcol].astype(str).str.upper().isin({str(x).upper() for x in aliases})
                    ].copy()
                else:
                    sub = df.copy()

                if "indicator" in sub.columns:
                    rate_mask = sub["indicator"].astype(str).str.lower().str.contains(
                        "rate|yield|sora|opr|hibor|boj|dgs10",
                        regex=True,
                        na=False
                    )
                    if rate_mask.any():
                        sub = sub[rate_mask].copy()

                sub["Date"] = pd.to_datetime(sub[date_col], errors="coerce")
                sub["Value"] = pd.to_numeric(sub[value_col], errors="coerce")
                sub = sub.dropna(subset=["Date", "Value"]).sort_values("Date")

                if not sub.empty:
                    sub = sub.drop_duplicates(["Date"], keep="last")
                    return sub[["Date", "Value"]].set_index("Date").tail(limit)

        except Exception:
            pass

    return macro_trend_df(market, "Rates", fallback_result)
'''

if "def rates_history_trend_df(" not in text:
    marker = "def classify(dd):"
    idx = text.find(marker)

    if idx != -1:
        text = text[:idx] + rates_history_helper.rstrip() + "\n\n" + text[idx:]
        print("Inserted rates_history_trend_df before classify.")
        ok5 = True
    else:
        print("WARNING: Could not find insertion marker for rates_history_trend_df.")
        ok5 = False
else:
    print("rates_history_trend_df already present.")
    ok5 = True


# ------------------------------------------------------------
# PATCH 6: Make Rates Trend use rates_history_252d.csv
# ------------------------------------------------------------
old_rates_candidates = [
    "rates_df=macro_trend_df(index_label,'Rates',rates_res).rename(columns={'Value':'Rates'})",
    "rates_df = macro_trend_df(index_label,'Rates',rates_res).rename(columns={'Value':'Rates'})",
    "rates_df=macro_trend_df(index_label, 'Rates', rates_res).rename(columns={'Value':'Rates'})",
    "rates_df = macro_trend_df(index_label, 'Rates', rates_res).rename(columns={'Value':'Rates'})",
]

new_rates_line = "rates_df=rates_history_trend_df(index_label,rates_res).rename(columns={'Value':'Rates'})"

ok6 = False

if new_rates_line in text:
    print("Rates Trend already uses rates_history_trend_df.")
    ok6 = True
else:
    for old_rates_line in old_rates_candidates:
        if old_rates_line in text:
            text = text.replace(old_rates_line, new_rates_line)
            print("Patched Rates Trend to use rates_history_trend_df.")
            ok6 = True
            break

    if not ok6:
        print("WARNING: Rates Trend assignment line not found.")


# ------------------------------------------------------------
# PATCH 7: Restore ETF preference constants if function patch removed them
# ------------------------------------------------------------
ok4 = False

etf_constants_block = '''
# ------------------------- Owner mode, ETF preferences & platform ETF overrides -------------------------
ETF_PREFS_FILE = Path('user_etf_preferences.json')
PLATFORM_ETF_OVERRIDES_FILE = Path('platform_etf_overrides.json')
ETF_MARKET_SUFFIX_HINTS = {'STI': '.SI', 'KLSE': '.KL', 'HSI': '.HK', 'Nikkei 225': '.T'}
DEFAULT_OWNER_PASSCODE = 'Kf272287' # Testing default only. Override with st.secrets/env in production.
'''

if "ETF_PREFS_FILE =" not in text:
    marker = "def _load_user_etf_preferences():"
    idx = text.find(marker)

    if idx != -1:
        text = text[:idx] + etf_constants_block + "\n" + text[idx:]
        print("Restored ETF preference constants before _load_user_etf_preferences.")
        ok4 = True
    else:
        marker = "def _normalise_ticker("
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx] + etf_constants_block + "\n" + text[idx:]
            print("Restored ETF preference constants before _normalise_ticker.")
            ok4 = True
        else:
            print("WARNING: Could not find ETF insertion marker.")
            ok4 = False
else:
    print("ETF preference constants already present.")
    ok4 = True

APP_FILE.write_text(text, encoding="utf-8")

print("Patch completed successfully.")
print(f"Updated file: {APP_FILE}")
print(f"render_macro_line_chart replaced: {ok1}")
print(f"macro_trend_df replaced: {ok2}")
print(f"mini_pmi_bar_chart replaced: {ok3}")
print(f"ETF constants restored/present: {ok4}")
