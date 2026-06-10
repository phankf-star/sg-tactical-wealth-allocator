import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time
from datetime import datetime

# ==============================================================================
# 1. PAGE LAYOUT CONFIGURATION & STYLING
# ==============================================================================
st.set_page_config(
    page_title="SG Tactical Capital Allocator & Future Drawdown Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("\U0001f1f8\U0001f1ec Tactical Wealth Allocation & Future Drawdown Simulator")
st.caption("A dynamic live-updating platform evaluating S&P 500, Nasdaq, STI, and HSI under cascading Singapore structural asset pool parameters.")

# ==============================================================================
# 2. SIDEBAR PARAMETER AND ASSET POOL ENGINE
# ==============================================================================
st.sidebar.markdown("## \U0001f4b0 Your Available Capital Pools")
cash_balance = st.sidebar.number_input("Liquid Cash Savings Pool ($)", min_value=0.0, value=100000.0, step=5000.0)
srs_balance = st.sidebar.number_input("Supplementary Retirement Scheme (SRS) ($)", min_value=0.0, value=35000.0, step=5000.0)
cpf_oa_balance = st.sidebar.number_input("CPF Ordinary Account (OA) ($)", min_value=0.0, value=180000.0, step=5000.0)

st.sidebar.markdown("---")
st.sidebar.markdown("## \u2699\ufe0f Core Risk Safeguards")
emergency_buffer = st.sidebar.number_input("Emergency Liquid Cash Buffer ($)", min_value=0.0, value=20000.0, step=1000.0)
preserve_cpf_bonus = st.sidebar.checkbox("Preserve S$20k CPF-OA Core Floor", value=True, help="Protects the initial structural floor space to secure the government's extra 1% bonus yield tier.")

INDEX_TICKERS = {
    "S&P 500 (US Market Core)": "^GSPC",
    "Nasdaq 100 (Tech Growth)": "^IXIC",
    "Straits Times Index (SG Value/REITs)": "^STI",
    "Hang Seng Index (HK Cyclical/Beta)": "^HSI"
}

ETF_UNIVERSE = {
    "Straits Times Index (SG Value/REITs)": {
        "market_label": "\U0001f1f8\U0001f1ec Singapore",
        "etfs": [("SPDR STI ETF", "ES3.SI"), ("Nikko AM STI ETF", "G3B.SI")]
    },
    "Hang Seng Index (HK Cyclical/Beta)": {
        "market_label": "\U0001f1ed\U0001f1f0 Hong Kong",
        "etfs": [("Tracker Fund (TraHK)", "2800.HK"), ("iShares HSI ETF", "3115.HK"), ("iShares HS TECH ETF", "3067.HK")]
    },
    "Nasdaq 100 (Tech Growth)": {
        "market_label": "\U0001f1fa\U0001f1f8 Nasdaq",
        "etfs": [("Invesco QQQ Trust", "QQQ"), ("Invesco NASDAQ 100 (QQQM)", "QQQM")]
    },
    "S&P 500 (US Market Core)": {
        "market_label": "\U0001f1fa\U0001f1f8 S&P 500",
        "etfs": [("SPDR S&P 500 (SPY)", "SPY"), ("Vanguard S&P 500 (VOO)", "VOO"), ("iShares Core S&P 500 (IVV)", "IVV")]
    },
}

# ==============================================================================
# 3. LIVE API DATA COLLECTION PIPELINE
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.markdown("## \U0001f504 Data Synchronization")
refresh_data_trigger = st.sidebar.button("\U0001f504 Force Refresh Market Data", help="Clears local cache and fetches the latest live price feeds.")

if refresh_data_trigger:
    st.cache_data.clear()
    st.toast("Cache cleared! Re-harvesting data pipelines...", icon="\U0001f504")

@st.cache_data(ttl=14400)
def harvest_market_historical_metrics():
    computed_metrics = {}
    for standard_name, target_ticker in INDEX_TICKERS.items():
        try:
            ticker_object = yf.Ticker(target_ticker)
            dataframe = ticker_object.history(start="1997-01-01")
            time.sleep(1.5)
            if not dataframe.empty:
                current_spot = float(dataframe['Close'].iloc[-1])
                moving_average_200 = float(dataframe['Close'].rolling(200).mean().iloc[-1])
                all_time_peak = float(dataframe['Close'].max())
                active_drawdown = ((current_spot - all_time_peak) / all_time_peak) * 100
                computed_metrics[standard_name] = {"live_close": current_spot, "ma_200": moving_average_200, "ath_peak": all_time_peak, "drawdown": active_drawdown, "underlying_df": dataframe}
            else:
                st.warning(f"\u26a0\ufe0f No data returned for {standard_name} ({target_ticker}).")
        except Exception as system_error:
            error_msg = str(system_error)
            if "Too Many Requests" in error_msg or "Rate" in error_msg or "429" in error_msg:
                st.error(f"Error fetching data for {standard_name}: Too Many Requests. Rate limited.")
            else:
                st.error(f"Error fetching data for {standard_name}: {error_msg}")
    return computed_metrics

@st.cache_data(ttl=14400)
def fetch_macro_indicators():
    macro = {"vix": None, "yield_10y": None, "yield_3m": None, "yield_spread": None, "vix_hist": None, "tnx_hist": None, "irx_hist": None}
    try:
        vix_hist = yf.Ticker("^VIX").history(period="1y")
        time.sleep(1.5)
        if not vix_hist.empty:
            macro["vix"] = float(vix_hist["Close"].iloc[-1])
            macro["vix_hist"] = vix_hist
    except Exception: pass
    try:
        tnx_hist = yf.Ticker("^TNX").history(period="1y")
        time.sleep(1.5)
        if not tnx_hist.empty:
            macro["yield_10y"] = float(tnx_hist["Close"].iloc[-1])
            macro["tnx_hist"] = tnx_hist
    except Exception: pass
    try:
        irx_hist = yf.Ticker("^IRX").history(period="1y")
        time.sleep(1.5)
        if not irx_hist.empty:
            macro["yield_3m"] = float(irx_hist["Close"].iloc[-1])
            macro["irx_hist"] = irx_hist
    except Exception: pass
    if macro["yield_10y"] is not None and macro["yield_3m"] is not None:
        macro["yield_spread"] = macro["yield_10y"] - macro["yield_3m"]
    return macro

@st.cache_data(ttl=14400)
def fetch_etf_performance():
    results = {}
    for index_name, group in ETF_UNIVERSE.items():
        group_results = []
        for etf_name, ticker in group["etfs"]:
            rec = {"name": etf_name, "ticker": ticker, "1y": None, "3y": None, "5y": None, "price": None}
            try:
                hist = yf.Ticker(ticker).history(period="6y")
                time.sleep(0.8)
                if not hist.empty:
                    cp = float(hist['Close'].iloc[-1])
                    rec["price"] = cp
                    td = len(hist)
                    if td >= 252: rec["1y"] = ((cp / float(hist["Close"].iloc[-252])) - 1) * 100
                    if td >= 756: rec["3y"] = ((cp / float(hist["Close"].iloc[-756])) - 1) * 100
                    if td >= 1260: rec["5y"] = ((cp / float(hist["Close"].iloc[-1260])) - 1) * 100
            except Exception: pass
            group_results.append(rec)
        results[index_name] = group_results
    return results

with st.spinner("Harvesting live historical index structures via API pipelines..."):
    market_state_database = harvest_market_historical_metrics()
with st.spinner("Fetching live macro indicators (VIX, Yield Curve)..."):
    live_macro = fetch_macro_indicators()

if not market_state_database:
    st.error("\U0001f6a8 **No market data could be loaded.** Yahoo Finance may be temporarily rate-limiting.")
    st.markdown("Wait 1-2 minutes and click Force Refresh, or reload the page.")
    st.stop()

# ==============================================================================
# 4. MARKET CONDITIONS & SCENARIO MODELER
# ==============================================================================
st.markdown("### \U0001f52e Market Conditions & Scenario Modeler")
st.info("Live market data is loaded by default. Adjust sliders to run scenario analysis or override with manual inputs.")

available_indices = list(market_state_database.keys())
selected_index_profile = st.selectbox("Select Target Index Spectrum", available_indices)
if selected_index_profile not in market_state_database:
    st.error(f"\u274c Data for **{selected_index_profile}** is not available.")
    st.stop()

selected_index_package = market_state_database[selected_index_profile]
live_anchor_close = selected_index_package["live_close"]
historical_ath_anchor = selected_index_package["ath_peak"]
underlying_data = selected_index_package["underlying_df"]
underlying_data.index = underlying_data.index.tz_localize(None)

ath_value = float(underlying_data['Close'].max())
ath_date = underlying_data['Close'].idxmax()
try:
    ath_date_str = ath_date.strftime('%Y-%m-%d')
except Exception:
    ath_date_str = "N/A"

row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    min_date = underlying_data.index.min().to_pydatetime().date()
    max_date = underlying_data.index.max().to_pydatetime().date()
    use_historical = st.checkbox("Use Historical Date Price", value=False)
    if use_historical:
        target_date = st.date_input("Pick Historical Date", value=max_date, min_value=min_date, max_value=max_date)
        closest_row_idx = underlying_data.index.get_indexer([pd.Timestamp(target_date)], method='nearest')[0]
        closest_row = underlying_data.iloc[closest_row_idx]
        picked_price = float(closest_row['Close'])
        st.caption(f"Price on {target_date.strftime('%Y-%m-%d')}: **{picked_price:,.2f}**")
        data_up_to_date = underlying_data.loc[:pd.Timestamp(target_date)]
        lookback_start = max(0, len(data_up_to_date) - 252)
        recent_window = data_up_to_date.iloc[lookback_start:]
        trailing_peak = float(recent_window['Close'].max())
        peak_date = recent_window['Close'].idxmax()
    else:
        picked_price = None

with row1_col2:
    if use_historical:
        index_price_input = st.slider(
            "Market Index Price Level",
            int(live_anchor_close * 0.35), int(historical_ath_anchor * 1.25), int(picked_price),
            disabled=True, help="Disabled while historical date mode is active.")
    else:
        index_price_input = st.slider(
            "Market Index Price Level",
            int(live_anchor_close * 0.35), int(historical_ath_anchor * 1.25), int(live_anchor_close),
            help="Default is live close price. Slide left to simulate drawdowns, right to simulate rallies.")
    st.caption(f"\U0001f4e1 Live close: **{live_anchor_close:,.2f}**")

if not use_historical:
    lookback_start = max(0, len(underlying_data) - 252)
    recent_window = underlying_data.iloc[lookback_start:]
    trailing_peak = float(recent_window['Close'].max())
    peak_date = recent_window['Close'].idxmax()

try:
    peak_date_str = peak_date.strftime('%Y-%m-%d')
except Exception:
    peak_date_str = "N/A"

# --- 52-Week Index Price Chart ---
try:
    chart_data_52w = underlying_data.iloc[max(0, len(underlying_data) - 252):]
    ma_200_series = underlying_data['Close'].rolling(200).mean().iloc[max(0, len(underlying_data) - 252):]
    fig_index = go.Figure()
    fig_index.add_trace(go.Scatter(x=chart_data_52w.index, y=chart_data_52w['Close'], mode='lines', name='Close', line=dict(color='#1565C0', width=1.5)))
    fig_index.add_trace(go.Scatter(x=ma_200_series.index, y=ma_200_series.values, mode='lines', name='200MA', line=dict(color='#4CAF50', width=1, dash='dot')))
    fig_index.add_hline(y=trailing_peak, line_dash="dash", line_color="#D32F2F", line_width=1, annotation_text="52W High: " + f"{trailing_peak:,.0f}", annotation_position="top left", annotation_font_size=10, annotation_font_color="#D32F2F")
    fig_index.update_layout(title=dict(text="52-Week Price Chart \u2014 " + selected_index_profile, font=dict(size=13)), height=220, margin=dict(l=10, r=10, t=35, b=10), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#F0F0F0"), plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig_index, use_container_width=True, config={'displayModeBar': False})
except Exception:
    st.caption("\u26a0\ufe0f Index chart unavailable")

st.markdown("")
row2_col1, row2_col2, row2_col3 = st.columns(3)
live_vix = live_macro.get("vix")
live_yield_spread = live_macro.get("yield_spread")
vix_default = round(live_vix, 1) if live_vix is not None else 20.0
yield_spread_default = round(live_yield_spread, 2) if live_yield_spread is not None else 0.45

with row2_col1:
    pmi_input = st.slider("US ISM Manufacturing PMI", 40.0, 60.0, 51.5, help="Manufacturing activity gauge. Below 50 = contraction.")
    st.caption("\U0001f4dd Manual input \u2014 [Check latest at ISM](https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/)")

with row2_col2:
    yield_spread_input = st.slider("US Treasury Yield Spread (10Y\u22123M)", -1.50, 2.50, yield_spread_default, help="Yield curve inversion (below 0) signals recession risk.")
    if live_yield_spread is not None:
        st.caption(f"\U0001f4e1 Live spread: **{live_yield_spread:.2f}%** (10Y: {live_macro.get('yield_10y', 0):.2f}% \u2212 3M: {live_macro.get('yield_3m', 0):.2f}%)")
    else:
        st.caption("\u26a0\ufe0f Live yield data unavailable \u2014 using default")

with row2_col3:
    vix_input = st.slider("CBOE VIX Volatility Index", 10.0, 80.0, vix_default, help="Market fear gauge. Above 30 = elevated fear/stress.")
    if live_vix is not None:
        st.caption(f"\U0001f4e1 Live VIX: **{live_vix:.2f}**")
    else:
        st.caption("\u26a0\ufe0f Live VIX unavailable \u2014 using default")

chart_col1, chart_col2, chart_col3 = st.columns(3)

with chart_col1:
    pmi_note = '<div style="background:#F5F5F5; border:1px solid #DDD; border-radius:8px; padding:16px; text-align:center; height:200px; display:flex; flex-direction:column; justify-content:center;">'
    pmi_note += '<div style="font-size:13px; font-weight:600; color:#555; margin-bottom:8px;">\U0001f4ca PMI Historical Chart</div>'
    pmi_note += '<div style="font-size:12px; color:#888;">No free live API for ISM PMI data.</div>'
    pmi_note += '<div style="font-size:12px; color:#888; margin-top:4px;">Update manually from <a href="https://www.ismworld.org" target="_blank" style="color:#1565C0;">ISM Reports</a></div>'
    pmi_note += '<div style="font-size:11px; color:#aaa; margin-top:8px;">Published monthly, first business day.</div>'
    pmi_note += '</div>'
    st.markdown(pmi_note, unsafe_allow_html=True)

with chart_col2:
    try:
        tnx_hist = live_macro.get("tnx_hist")
        irx_hist = live_macro.get("irx_hist")
        if tnx_hist is not None and irx_hist is not None:
            tnx_df = tnx_hist[['Close']].rename(columns={'Close': 'TNX'})
            irx_df = irx_hist[['Close']].rename(columns={'Close': 'IRX'})
            tnx_df.index = tnx_df.index.tz_localize(None)
            irx_df.index = irx_df.index.tz_localize(None)
            spread_df = tnx_df.join(irx_df, how='inner')
            spread_df['Spread'] = spread_df['TNX'] - spread_df['IRX']
            fig_yield = go.Figure()
            fig_yield.add_trace(go.Scatter(x=spread_df.index, y=spread_df['TNX'], mode='lines', name='10Y Yield', line=dict(color='#1565C0', width=1.5)))
            fig_yield.add_trace(go.Scatter(x=spread_df.index, y=spread_df['IRX'], mode='lines', name='3M Yield', line=dict(color='#E65100', width=1.5)))
            fig_yield.add_trace(go.Scatter(x=spread_df.index, y=spread_df['Spread'], mode='lines', name='Spread', line=dict(color='#7B1FA2', width=1.5, dash='dot')))
            fig_yield.add_hline(y=0, line_dash="dash", line_color="#D32F2F", line_width=1, annotation_text="Inversion", annotation_position="bottom left", annotation_font_size=9, annotation_font_color="#D32F2F")
            fig_yield.update_layout(title=dict(text="US Treasury Yields \u2014 10Y vs 3M (1 Year)", font=dict(size=12)), height=200, margin=dict(l=10, r=10, t=30, b=10), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9)), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#F0F0F0", ticksuffix="%"), plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_yield, use_container_width=True, config={'displayModeBar': False})
            st.caption("Using 3M yield as short-end proxy (standard Fed recession indicator). 2Y unavailable via free API.")
        else:
            st.caption("\u26a0\ufe0f Yield chart data unavailable")
    except Exception:
        st.caption("\u26a0\ufe0f Yield chart unavailable")

with chart_col3:
    try:
        vix_hist = live_macro.get("vix_hist")
        if vix_hist is not None:
            vix_chart = vix_hist.copy()
            vix_chart.index = vix_chart.index.tz_localize(None)
            fig_vix = go.Figure()
            fig_vix.add_trace(go.Scatter(x=vix_chart.index, y=vix_chart['Close'], mode='lines', name='VIX', line=dict(color='#7B1FA2', width=1.5)))
            fig_vix.add_hline(y=30, line_dash="dash", line_color="#D32F2F", line_width=1, annotation_text="Fear Zone (30)", annotation_position="top left", annotation_font_size=9, annotation_font_color="#D32F2F")
            fig_vix.update_layout(title=dict(text="CBOE VIX \u2014 1 Year", font=dict(size=12)), height=200, margin=dict(l=10, r=10, t=30, b=10), showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#F0F0F0"), plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_vix, use_container_width=True, config={'displayModeBar': False})
        else:
            st.caption("\u26a0\ufe0f VIX chart data unavailable")
    except Exception:
        st.caption("\u26a0\ufe0f VIX chart unavailable")

# ==============================================================================
# 5. DYNAMIC PROCESSING ENGINE & STATE CALCULATOR
# ==============================================================================
evaluation_price = picked_price if use_historical else index_price_input
effective_scenario_drawdown = ((evaluation_price - trailing_peak) / trailing_peak) * 100 if trailing_peak > 0 else 0.0
baseline_200_ma = selected_index_package["ma_200"]

pmi_triggered = pmi_input < 50.0
yield_triggered = yield_spread_input < 0.0
ma_triggered = evaluation_price < baseline_200_ma
vix_triggered = vix_input > 30.0

systemic_risk_score = sum([pmi_triggered, yield_triggered, ma_triggered, vix_triggered])

if effective_scenario_drawdown <= -35.0:
    active_allocation_zone = "STRONG BUY"
    zone_presentation_title = "STRONG BUY ZONE"
    zone_subtitle = "Generational Allocation Opportunity &mdash; Deploy Maximum Capital"
    zone_emoji = "\U0001f6a8"; zone_color = "#D32F2F"; zone_text_color = "#FFFFFF"; use_pulse = True
elif effective_scenario_drawdown <= -20.0:
    active_allocation_zone = "BUY"
    zone_presentation_title = "BUY ZONE"
    zone_subtitle = "Structural Bear Market Value Framework &mdash; Scale Into Positions"
    zone_emoji = "\U0001f7e2"; zone_color = "#E65100"; zone_text_color = "#FFFFFF"; use_pulse = False
elif effective_scenario_drawdown <= -10.0:
    active_allocation_zone = "INITIAL BUY"
    zone_presentation_title = "INITIAL BUY ZONE"
    zone_subtitle = "Healthy Market Correction &mdash; Nibble &amp; Build Starter Positions"
    zone_emoji = "\U0001f7e1"; zone_color = "#F9A825"; zone_text_color = "#1A1A1A"; use_pulse = False
elif evaluation_price > (1.20 * baseline_200_ma) and systemic_risk_score >= 3:
    active_allocation_zone = "STRONG SELL"
    zone_presentation_title = "STRONG SELL ZONE"
    zone_subtitle = "Systemic Market Bubble Detected &mdash; Maximize Liquidity &amp; Take Profits"
    zone_emoji = "\U0001f534"; zone_color = "#B71C1C"; zone_text_color = "#FFFFFF"; use_pulse = True
else:
    active_allocation_zone = "HOLD"
    zone_presentation_title = "HOLD / DCA ZONE"
    zone_subtitle = "Market Within Normal Boundaries &mdash; Maintain Dollar-Cost Averaging"
    zone_emoji = "\u26aa"; zone_color = "#2E7D32"; zone_text_color = "#FFFFFF"; use_pulse = False

st.markdown("---")

# Drawdown card colors
if effective_scenario_drawdown <= -35.0:
    dd_bg="#FFCDD2"; dd_border="#D32F2F"; dd_icon="\U0001f6a8"; dd_text_color="#B71C1C"; dd_label="ALERT: Generational drawdown!"
elif effective_scenario_drawdown <= -20.0:
    dd_bg="#FFE0B2"; dd_border="#E65100"; dd_icon="\u26a0\ufe0f"; dd_text_color="#E65100"; dd_label="ALERT: Deep drawdown detected!"
elif effective_scenario_drawdown <= -10.0:
    dd_bg="#FFF9C4"; dd_border="#F9A825"; dd_icon="\u26a0\ufe0f"; dd_text_color="#F57F17"; dd_label="Correction zone"
else:
    dd_bg="#E8F5E9"; dd_border="#2E7D32"; dd_icon="\u2705"; dd_text_color="#2E7D32"; dd_label="Within normal range"

# Risk score card colors
if systemic_risk_score >= 3:
    rs_bg="#FFCDD2"; rs_border="#D32F2F"; rs_icon="\U0001f6a8"; rs_text_color="#B71C1C"; rs_label="CRITICAL: Multiple risk triggers!"
elif systemic_risk_score >= 1:
    rs_bg="#FFE0B2"; rs_border="#E65100"; rs_icon="\u26a0\ufe0f"; rs_text_color="#E65100"; rs_label="Elevated: " + str(systemic_risk_score) + " risk factor(s)"
else:
    rs_bg="#E8F5E9"; rs_border="#2E7D32"; rs_icon="\u2705"; rs_text_color="#2E7D32"; rs_label="All clear &mdash; no risk triggers"

pk_bg="#E3F2FD"; pk_border="#1565C0"; pk_icon="\U0001f4ca"; pk_text_color="#1565C0"

# Risk indicator statuses
pmi_si = "\U0001f6a8" if pmi_triggered else "\u2705"
pmi_sc = "#D32F2F" if pmi_triggered else "#2E7D32"
pmi_st = "CONTRACTION" if pmi_triggered else "Expansionary"
yield_si = "\U0001f6a8" if yield_triggered else "\u2705"
yield_sc = "#D32F2F" if yield_triggered else "#2E7D32"
yield_st = "INVERTED" if yield_triggered else "Normal"
ma_si = "\U0001f6a8" if ma_triggered else "\u2705"
ma_sc = "#D32F2F" if ma_triggered else "#2E7D32"
ma_st = "BELOW 200MA" if ma_triggered else "Above 200MA"
vix_si = "\U0001f6a8" if vix_triggered else "\u2705"
vix_sc = "#D32F2F" if vix_triggered else "#2E7D32"
vix_st = "ELEVATED FEAR" if vix_triggered else "Normal"

metric_col_1, metric_col_2, metric_col_3 = st.columns(3)

with metric_col_1:
    dd_html = '<div style="background:' + dd_bg + '; border-left:6px solid ' + dd_border + '; border-radius:10px; padding:20px; text-align:center;">'
    dd_html += '<div style="font-size:14px; color:#555; font-weight:600;">EFFECTIVE DRAWDOWN FROM PEAK</div>'
    dd_html += '<div style="font-size:42px; font-weight:800; color:' + dd_text_color + '; margin:8px 0;">' + dd_icon + " " + f"{effective_scenario_drawdown:.2f}%" + '</div>'
    dd_html += '<div style="font-size:12px; color:#777;">' + dd_label + '</div>'
    dd_html += '<div style="font-size:11px; color:#999; margin-top:6px;">vs 52-week trailing high</div></div>'
    st.markdown(dd_html, unsafe_allow_html=True)

with metric_col_2:
    rs_html = '<div style="background:' + rs_bg + '; border-left:6px solid ' + rs_border + '; border-radius:10px; padding:20px; text-align:center;">'
    rs_html += '<div style="font-size:14px; color:#555; font-weight:600;">CALCULATED MACRO RISK SCORE</div>'
    rs_html += '<div style="font-size:42px; font-weight:800; color:' + rs_text_color + '; margin:8px 0;">' + rs_icon + " " + str(systemic_risk_score) + " / 4</div>"
    rs_html += '<div style="font-size:12px; color:#777; margin-bottom:12px;">' + rs_label + '</div>'
    rs_html += '<div style="text-align:left; padding:10px 14px; background:rgba(255,255,255,0.7); border-radius:8px;">'
    rs_html += '<div style="font-size:11px; font-weight:700; color:#333; margin-bottom:8px; text-transform:uppercase; letter-spacing:1px;">Risk Breakdown:</div>'
    rs_html += '<div style="font-size:12px; color:' + pmi_sc + '; margin:4px 0;">' + pmi_si + " <b>ISM PMI:</b> " + f"{pmi_input:.1f}" + " &mdash; " + pmi_st + ' <span style="color:#999;">(trigger &lt; 50)</span></div>'
    rs_html += '<div style="font-size:12px; color:' + yield_sc + '; margin:4px 0;">' + yield_si + " <b>Yield Spread:</b> " + f"{yield_spread_input:.2f}" + " &mdash; " + yield_st + ' <span style="color:#999;">(trigger &lt; 0)</span></div>'
    rs_html += '<div style="font-size:12px; color:' + ma_sc + '; margin:4px 0;">' + ma_si + " <b>Price vs 200MA:</b> " + f"{evaluation_price:,.0f}" + " vs " + f"{baseline_200_ma:,.0f}" + " &mdash; " + ma_st + '</div>'
    rs_html += '<div style="font-size:12px; color:' + vix_sc + '; margin:4px 0;">' + vix_si + " <b>VIX Index:</b> " + f"{vix_input:.1f}" + " &mdash; " + vix_st + ' <span style="color:#999;">(trigger &gt; 30)</span></div>'
    rs_html += '</div></div>'
    st.markdown(rs_html, unsafe_allow_html=True)

with metric_col_3:
    pk_html = '<div style="background:' + pk_bg + '; border-left:6px solid ' + pk_border + '; border-radius:10px; padding:20px; text-align:center;">'
    pk_html += '<div style="font-size:14px; color:#555; font-weight:600;">52-WEEK TRAILING HIGH</div>'
    pk_html += '<div style="font-size:42px; font-weight:800; color:' + pk_text_color + '; margin:8px 0;">' + pk_icon + " " + f"{trailing_peak:,.2f}" + '</div>'
    pk_html += '<div style="font-size:12px; color:#777;">Peak reached on ' + peak_date_str + '</div>'
    pk_html += '<div style="font-size:11px; color:#aaa; margin-top:8px; padding-top:8px; border-top:1px solid #D0D0D0;">All-Time High: ' + f"{ath_value:,.2f}" + " (" + ath_date_str + ")</div></div>"
    st.markdown(pk_html, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if use_pulse:
    pulse_style = """<style>@keyframes zone_pulse { 0% { box-shadow: 0 0 0 0 rgba(211,47,47,0.6); } 50% { box-shadow: 0 0 25px 10px rgba(211,47,47,0.3); } 100% { box-shadow: 0 0 0 0 rgba(211,47,47,0.6); } } .zone-banner { animation: zone_pulse 2s infinite; }</style>"""
else:
    pulse_style = "<style>.zone-banner { }</style>"

banner_html = pulse_style
banner_html += '<div class="zone-banner" style="background: linear-gradient(135deg, ' + zone_color + ', ' + zone_color + 'DD); border-radius:16px; padding:30px 40px; text-align:center; border:2px solid ' + zone_color + '; margin-bottom:10px;">'
banner_html += '<div style="font-size:50px; margin-bottom:5px;">' + zone_emoji + '</div>'
banner_html += '<div style="font-size:13px; color:' + zone_text_color + '; opacity:0.8; letter-spacing:3px; text-transform:uppercase; font-weight:600;">Target Evaluation Matrix Output</div>'
banner_html += '<div style="font-size:32px; font-weight:900; color:' + zone_text_color + '; margin:10px 0; letter-spacing:2px;">' + zone_presentation_title + '</div>'
banner_html += '<div style="font-size:16px; color:' + zone_text_color + '; opacity:0.9; font-weight:400;">' + zone_subtitle + '</div></div>'

st.markdown(banner_html, unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# 6. CASCADING RESOURCE WATERFALL DECISION MATRIX
# ==============================================================================
st.markdown("### \U0001f4cb Tactical Allocation Recommendations")

with st.expander("\U0001f4d0 Allocation Rules & Deployment Matrix \u2014 Click to view"):
    zones_data = [
        ("STRONG BUY", "\u2264 -35%", "100%", "100%", "100%", "Generational opportunity \u2014 max conviction"),
        ("BUY", "\u2264 -20%", "50%", "75%", "40%", "Structural bear \u2014 scale in aggressively"),
        ("INITIAL BUY", "\u2264 -10%", "20%", "30%", "15%", "Healthy correction \u2014 nibble positions"),
        ("HOLD / DCA", "Normal", "0%", "0%", "0%", "Maintain DCA schedules only"),
        ("STRONG SELL", "Bubble + Risk \u22653", "0%", "0%", "0%", "Pause all buying \u2014 take profits"),
    ]
    table_header = "| Zone | Drawdown Trigger | Cash | SRS | CPF-OA | Rationale |" + chr(10)
    table_header += "|:---|:---|:---:|:---:|:---:|:---|" + chr(10)
    table_rows = ""
    for zn, tr, cp, sp, cpfp, rat in zones_data:
        is_active = (zn == "STRONG BUY" and active_allocation_zone == "STRONG BUY") or (zn == "BUY" and active_allocation_zone == "BUY") or (zn == "INITIAL BUY" and active_allocation_zone == "INITIAL BUY") or (zn == "HOLD / DCA" and active_allocation_zone == "HOLD") or (zn == "STRONG SELL" and active_allocation_zone == "STRONG SELL")
        if is_active:
            table_rows += f"| \U0001f449 **{zn}** | **{tr}** | **{cp}** | **{sp}** | **{cpfp}** | **{rat}** |" + chr(10)
        else:
            table_rows += f"| {zn} | {tr} | {cp} | {sp} | {cpfp} | {rat} |" + chr(10)
    st.markdown(table_header + table_rows)
    st.markdown("""
    **How drawdown is calculated:**
    - Measured from the **52-week (252 trading day) trailing high**
    - Reflects the **current market cycle**, not stale historical peaks

    **How deployment amounts are calculated:**
    - \U0001f4b5 **Cash** deploys **after** deducting Emergency Buffer
    - \U0001f6e1\ufe0f **CPF-OA** deploys **after** preserving S$20k floor (if toggled)
    - \U0001f4c8 **SRS** deploys from full balance

    **Risk score triggers (4 indicators):**
    - ISM PMI < 50 | Yield Spread < 0 | Price below 200MA | VIX > 30
    """)

st.markdown("")
usable_cash_reserves = max(0.0, cash_balance - emergency_buffer)
usable_srs_reserves = srs_balance
usable_cpf_reserves = max(0.0, cpf_oa_balance - 20000.0) if preserve_cpf_bonus else cpf_oa_balance

suggested_cash_outflow = 0.0
suggested_srs_outflow = 0.0
suggested_cpf_outflow = 0.0

if active_allocation_zone == "STRONG BUY":
    suggested_cash_outflow = usable_cash_reserves
    suggested_srs_outflow = usable_srs_reserves
    suggested_cpf_outflow = usable_cpf_reserves
elif active_allocation_zone == "BUY":
    suggested_cash_outflow = usable_cash_reserves * 0.50
    suggested_srs_outflow = usable_srs_reserves * 0.75
    suggested_cpf_outflow = usable_cpf_reserves * 0.40
elif active_allocation_zone == "INITIAL BUY":
    suggested_cash_outflow = usable_cash_reserves * 0.20
    suggested_srs_outflow = usable_srs_reserves * 0.30
    suggested_cpf_outflow = usable_cpf_reserves * 0.15
elif active_allocation_zone == "STRONG SELL":
    st.warning("\u26a0\ufe0f Systemic Bubble Risk Detected. Pausing new deployments.")
else:
    st.info("\u2139\ufe0f Market within normal boundaries. Maintain standard DCA schedules.")

remaining_cash = cash_balance - suggested_cash_outflow
remaining_srs = srs_balance - suggested_srs_outflow
remaining_cpf = cpf_oa_balance - suggested_cpf_outflow
total_tactical_deployed = suggested_cash_outflow + suggested_srs_outflow + suggested_cpf_outflow

display_col_1, display_col_2, display_col_3 = st.columns(3)
with display_col_1:
    st.markdown("#### \U0001f4b5 Liquid Cash Capital")
    st.metric("Suggested Cash Deploy", f"S${suggested_cash_outflow:,.2f}")
    st.caption(f"Remaining Cash Left: S${remaining_cash:,.2f}")
with display_col_2:
    st.markdown("#### \U0001f4c8 Supplementary Retirement (SRS)")
    st.metric("Suggested SRS Deploy", f"S${suggested_srs_outflow:,.2f}")
    st.caption(f"Remaining SRS Left: S${remaining_srs:,.2f}")
with display_col_3:
    st.markdown("#### \U0001f6e1\ufe0f CPF Ordinary Account")
    st.metric("Suggested CPF-OA Deploy", f"S${suggested_cpf_outflow:,.2f}")
    st.caption(f"Remaining CPF-OA Left: S${remaining_cpf:,.2f}")

st.markdown("---")
st.subheader(f"Total Capital to Deploy in this Tranche: :green[S${total_tactical_deployed:,.2f}]")

# ==============================================================================
# 7. ETF PERFORMANCE TRACKER
# ==============================================================================
st.markdown("---")
st.markdown("### \U0001f4ca Investable ETF Performance Tracker")
st.caption("Trailing total returns for investable ETFs mapped to each index.")

try:
    with st.spinner("Fetching ETF performance data..."):
        etf_data = fetch_etf_performance()
    if etf_data:
        display_order = []
        if selected_index_profile in ETF_UNIVERSE: display_order.append(selected_index_profile)
        for idx_name in ETF_UNIVERSE:
            if idx_name not in display_order: display_order.append(idx_name)
        for idx_name in display_order:
            if idx_name not in etf_data: continue
            group_info = ETF_UNIVERSE[idx_name]
            market_label = group_info["market_label"]
            etf_records = etf_data[idx_name]
            is_selected = (idx_name == selected_index_profile)
            highlight_note = ' &nbsp; <span style="background:#E8F5E9; color:#2E7D32; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600;">\u2705 CURRENTLY SELECTED</span>' if is_selected else ''
            st.markdown('<div style="font-size:18px; font-weight:700; margin-top:16px; margin-bottom:8px;">' + market_label + highlight_note + '</div>', unsafe_allow_html=True)

            table_html = '<table style="width:100%; border-collapse:collapse; font-size:14px; margin-bottom:16px;"><thead><tr style="background:#F0F2F6; border-bottom:2px solid #DDD;">'
            table_html += '<th style="text-align:left; padding:10px 12px;">ETF Name</th>'
            table_html += '<th style="text-align:center; padding:10px 12px;">Ticker</th>'
            table_html += '<th style="text-align:center; padding:10px 12px;">Price</th>'
            table_html += '<th style="text-align:center; padding:10px 12px;">1Y Return</th>'
            table_html += '<th style="text-align:center; padding:10px 12px;">3Y Return</th>'
            table_html += '<th style="text-align:center; padding:10px 12px;">5Y Return</th>'
            table_html += '</tr></thead><tbody>'

            for rec in etf_records:
                price_str = f"{rec['price']:,.2f}" if rec['price'] is not None else 'N/A'
                def fmt_ret(val):
                    if val is None: return '<span style="color:#999;">N/A</span>'
                    color = '#2E7D32' if val >= 0 else '#D32F2F'
                    arrow = '\u25b2' if val >= 0 else '\u25bc'
                    return '<span style="color:' + color + '; font-weight:600;">' + arrow + ' ' + f'{val:.1f}' + '%</span>'
                table_html += '<tr style="background:#FFF; border-bottom:1px solid #EEE;">'
                table_html += '<td style="padding:10px 12px;">' + rec['name'] + '</td>'
                table_html += '<td style="text-align:center; padding:10px 12px; font-family:monospace; color:#555;">' + rec['ticker'] + '</td>'
                table_html += '<td style="text-align:center; padding:10px 12px; font-weight:600;">' + price_str + '</td>'
                table_html += '<td style="text-align:center; padding:10px 12px;">' + fmt_ret(rec['1y']) + '</td>'
                table_html += '<td style="text-align:center; padding:10px 12px;">' + fmt_ret(rec['3y']) + '</td>'
                table_html += '<td style="text-align:center; padding:10px 12px;">' + fmt_ret(rec['5y']) + '</td></tr>'
            table_html += '</tbody></table>'
            st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.warning("ETF data could not be loaded.")
except Exception as etf_error:
    st.warning(f"\u26a0\ufe0f ETF data temporarily unavailable: {str(etf_error)}")

st.markdown("---")
st.caption("\u26a0\ufe0f Disclaimer: This tool is for educational and informational purposes only. It does not constitute financial advice. Always consult a licensed financial advisor.")
