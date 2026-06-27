
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


APP_FILE.write_text(text, encoding="utf-8")

print("Patch completed successfully.")
print(f"Updated file: {APP_FILE}")
print(f"render_macro_line_chart replaced: {ok1}")
print(f"macro_trend_df replaced: {ok2}")
