

from pathlib import Path

APP_FILE = Path("sg_tactical_wealth_allocator.py")

if not APP_FILE.exists():
    print("Repo root Python files found:")
    for f in sorted(Path(".").glob("*.py")):
        print(" -", f)
    raise FileNotFoundError(f"App file not found: {APP_FILE}")

print(f"Using app file: {APP_FILE}")

text = APP_FILE.read_text(encoding="utf-8")


# ------------------------------------------------------------
# PATCH 1: Remove Yahoo-style wording
# ------------------------------------------------------------
text = text.replace(
    "# 1. Yahoo-style price chart. Visible once the monitor is opened.",
    "# 1. Index price chart. Visible once the monitor is opened."
)

text = text.replace(
    "st.markdown('### 📉 Yahoo-style Index Price Chart')",
    "st.markdown('### 📉 Index Price Chart')"
)


# ------------------------------------------------------------
# PATCH 2: Clean macro trend chart date axis
# This fixes ugly timestamp labels when macro series has monthly data.
# ------------------------------------------------------------
old = """def render_macro_line_chart(df, title, subtitle='', colour=BLUE, y_title='Value'):
    if df is None or df.empty:
        st.info(f'{title}: actual trend data unavailable.'); return
    col=df.columns[0]
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=df.index,y=df[col],mode='lines+markers',line=dict(color=colour,width=2),marker=dict(size=6),hovertemplate='%{x|%d %b %Y}<br>%{y:.2f}'))
    fig.update_layout(height=250,margin=dict(l=10,r=10,t=52,b=18),title=f'{title}<br><sup>{subtitle}</sup>',plot_bgcolor='white',paper_bgcolor='white',showlegend=False,yaxis_title=y_title)
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})"""

new = """def render_macro_line_chart(df, title, subtitle='', colour=BLUE, y_title='Value'):
    if df is None or df.empty:
        st.info(f'{title}: actual trend data unavailable.'); return

    df = df.copy()
    df.index = pd.to_datetime(df.index, errors='coerce')
    df = df[df.index.notna()].sort_index()

    col = df.columns[0]
    df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=[col])

    if df.empty:
        st.info(f'{title}: actual trend data unavailable.'); return

    # Normalise monthly macro dates to month-start to avoid ugly timestamp axis labels.
    if len(df) <= 18:
        df.index = df.index.to_period('M').to_timestamp()

    fig = go.Figure()

    mode = 'lines+markers' if len(df) >= 2 else 'markers'
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df[col],
        mode=mode,
        line=dict(color=colour,width=2),
        marker=dict(size=6),
        hovertemplate='%{x|%b %Y}<br>%{y:.2f}<extra></extra>'
    ))

    fig.update_layout(
        height=250,
        margin=dict(l=10,r=10,t=52,b=18),
        title=f'{title}<br><sup>{subtitle}</sup>',
        plot_bgcolor='white',
        paper_bgcolor='white',
        showlegend=False,
        yaxis_title=y_title,
        xaxis=dict(
            tickformat='%b %Y',
            type='date',
            showgrid=False
        )
    )

    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})"""

if old in text:
    text = text.replace(old, new)
else:
    print("WARNING: render_macro_line_chart block not found. No replacement made.")


# ------------------------------------------------------------
# PATCH 3: Improve macro trend dataframe fallback
# If only one live point exists, keep it clean but do not fake 12M history.
# The proper 12M fix should come from macro_pack_latest history files.
# ------------------------------------------------------------
old2 = """def macro_trend_df(market, indicator, fallback_result=None):
    df=_macro_pack_history(market,indicator)
    if not df.empty:
        return df.tail(12)
    if isinstance(fallback_result,dict) and fallback_result.get('value') is not None:
        dt=pd.to_datetime(fallback_result.get('date',''),errors='coerce')
        if pd.isna(dt):
            dt=pd.Timestamp.today().normalize()
        return pd.DataFrame({'Value':[float(fallback_result.get('value'))]},index=[dt])
    return pd.DataFrame()"""

new2 = """def macro_trend_df(market, indicator, fallback_result=None):
    df=_macro_pack_history(market,indicator)

    if not df.empty:
        df = df.copy()
        df.index = pd.to_datetime(df.index, errors='coerce')
        df = df[df.index.notna()].sort_index()
        df = df[~df.index.to_period('M').duplicated(keep='last')]
        return df.tail(12)

    # Fallback: show latest official value only when no historical pack exists.
    # Do not simulate 12M macro history here; historical series should come from macro_pack_latest.
    if isinstance(fallback_result,dict) and fallback_result.get('value') is not None:
        dt=pd.to_datetime(fallback_result.get('date',''),errors='coerce')
        if pd.isna(dt):
            dt=pd.Timestamp.today().normalize()
        dt = dt.to_period('M').to_timestamp()
        return pd.DataFrame({'Value':[float(fallback_result.get('value'))]},index=[dt])

    return pd.DataFrame()"""

if old2 in text:
    text = text.replace(old2, new2)
else:
    print("WARNING: macro_trend_df block not found. No replacement made.")


APP_FILE.write_text(text, encoding="utf-8")

print("Patch completed successfully.")
print(f"Updated file: {APP_FILE}")
