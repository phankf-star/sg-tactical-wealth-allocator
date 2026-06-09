import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as gr
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

# Available investment options mapping configuration
INDEX_TICKERS = {
    "S&P 500 (US Market Core)": "^GSPC",
    "Nasdaq 100 (Tech Growth)": "^IXIC",
    "Straits Times Index (SG Value/REITs)": "^STI",
    "Hang Seng Index (HK Cyclical/Beta)": "^HSI"
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
                computed_metrics[standard_name] = {
                    "live_close": current_spot,
                    "ma_200": moving_average_200,
                    "ath_peak": all_time_peak,
                    "drawdown": active_drawdown,
                    "underlying_df": dataframe
                }
            else:
                st.warning(f"\u26a0\ufe0f No data returned for {standard_name} ({target_ticker}).")
        except Exception as system_error:
            error_msg = str(system_error)
            if "Too Many Requests" in error_msg or "Rate" in error_msg or "429" in error_msg:
                st.error(f"Error fetching data for {standard_name}: Too Many Requests. Rate limited. Try after a while.")
            else:
                st.error(f"Error fetching data for {standard_name}: {error_msg}")
    return computed_metrics

with st.spinner("Harvesting live historical index structures via API pipelines..."):
    market_state_database = harvest_market_historical_metrics()

# Safety check
if not market_state_database:
    st.error("\U0001f6a8 **No market data could be loaded.** Yahoo Finance may be temporarily rate-limiting this server.")
    st.markdown("""
    1. Wait **1-2 minutes** and click **\U0001f504 Force Refresh Market Data** in the sidebar
    2. Reload the page (Ctrl+R / Cmd+R)
    3. If the issue persists, try again in 10-15 minutes
    """)
    st.stop()

# ==============================================================================
# 4. FUTURE DRAWDOWN STRESS TESTING CONTROL MATRIX (WITH HISTORICAL PICKER)
# ==============================================================================
st.markdown("### \U0001f52e Future Drawdown Scenario Modeler")
st.info("Simulate a future market crash or select a historical date to see past allocation zones.")

available_indices = list(market_state_database.keys())
selected_index_profile = st.selectbox("Select Target Index Spectrum", available_indices)

if selected_index_profile not in market_state_database:
    st.error(f"\u274c Data for **{selected_index_profile}** is not available. Please select another index or refresh.")
    st.stop()

selected_index_package = market_state_database[selected_index_profile]
live_anchor_close = selected_index_package["live_close"]
historical_ath_anchor = selected_index_package["ath_peak"]
underlying_data = selected_index_package["underlying_df"]

control_col_1, control_col_2, control_col_3, control_col_4 = st.columns(4)

with control_col_1:
    underlying_data.index = underlying_data.index.tz_localize(None)
    min_date = underlying_data.index.min().to_pydatetime().date()
    max_date = underlying_data.index.max().to_pydatetime().date()
    use_historical = st.checkbox("Use Historical Date Price", value=False)
    if use_historical:
        target_date = st.date_input("Pick Historical Date", value=max_date, min_value=min_date, max_value=max_date)
        closest_row_idx = underlying_data.index.get_indexer([pd.Timestamp(target_date)], method='nearest')[0]
        closest_row = underlying_data.iloc[closest_row_idx]
        picked_price = float(closest_row['Close'])
        st.caption(f"Price on {target_date.strftime('%Y-%m-%d')}: **{picked_price:,.2f}**")
    else:
        picked_price = None

with control_col_2:
    if use_historical:
        simulated_future_price = st.slider(
            "Simulated Future Target Price",
            int(live_anchor_close * 0.35), int(historical_ath_anchor * 1.25), int(picked_price),
            disabled=True, help="Disabled while historical date mode is active."
        )
    else:
        simulated_future_price = st.slider(
            "Simulated Future Target Price",
            int(live_anchor_close * 0.35), int(historical_ath_anchor * 1.25), int(live_anchor_close),
            help="Slide left to simulate future drawdowns, or right to simulate upward expansions."
        )

with control_col_3:
    simulated_future_pmi = st.slider(
        "Simulated Manufacturing PMI Baseline",
        40.0, 60.0, 51.5,
        help="Global industrial production boundary indicator. Readings dropping below 50 reflect contractionary risk profiles."
    )

with control_col_4:
    simulated_yield_spread = st.slider(
        "Simulated Yield Curve Spread (10Y - 2Y)",
        -1.50, 2.00, 0.45,
        help="Inversion trends falling below 0 signal institutional positioning ahead of global economic recessions."
    )

# ==============================================================================
# 5. DYNAMIC PROCESSING ENGINE & STATE CALCULATOR
# ==============================================================================
evaluation_price = picked_price if use_historical else simulated_future_price
active_rolling_peak = max(historical_ath_anchor, evaluation_price)
effective_scenario_drawdown = ((evaluation_price - active_rolling_peak) / active_rolling_peak) * 100
baseline_200_ma = selected_index_package["ma_200"]

systemic_risk_score = 0
if simulated_future_pmi < 50.0:
    systemic_risk_score += 1
if simulated_yield_spread < 0.0:
    systemic_risk_score += 1
if evaluation_price < baseline_200_ma:
    systemic_risk_score += 1

# Define zones
if effective_scenario_drawdown <= -35.0:
    active_allocation_zone = "STRONG BUY"
    zone_presentation_title = "STRONG BUY ZONE"
    zone_subtitle = "Generational Allocation Opportunity — Deploy Maximum Capital"
    zone_emoji = "\U0001f6a8"
    zone_color = "#D32F2F"
    zone_text_color = "#FFFFFF"
elif effective_scenario_drawdown <= -20.0:
    active_allocation_zone = "BUY"
    zone_presentation_title = "BUY ZONE"
    zone_subtitle = "Structural Bear Market Value Framework — Scale Into Positions"
    zone_emoji = "\U0001f7e2"
    zone_color = "#E65100"
    zone_text_color = "#FFFFFF"
elif effective_scenario_drawdown <= -10.0:
    active_allocation_zone = "INITIAL BUY"
    zone_presentation_title = "INITIAL BUY ZONE"
    zone_subtitle = "Healthy Market Correction — Nibble & Build Starter Positions"
    zone_emoji = "\U0001f7e1"
    zone_color = "#F9A825"
    zone_text_color = "#1A1A1A"
elif evaluation_price > (1.20 * baseline_200_ma) and systemic_risk_score >= 2:
    active_allocation_zone = "STRONG SELL"
    zone_presentation_title = "STRONG SELL ZONE"
    zone_subtitle = "Systemic Market Bubble Detected — Maximize Liquidity & Take Profits"
    zone_emoji = "\U0001f534"
    zone_color = "#B71C1C"
    zone_text_color = "#FFFFFF"
else:
    active_allocation_zone = "HOLD"
    zone_presentation_title = "HOLD / DCA ZONE"
    zone_subtitle = "Market Within Normal Boundaries — Maintain Dollar-Cost Averaging"
    zone_emoji = "\u26aa"
    zone_color = "#2E7D32"
    zone_text_color = "#FFFFFF"

# ------------------------------------------------------------------------------
# ENHANCED INDICATOR CARDS WITH COLOR-CODED ALERTS
# ------------------------------------------------------------------------------
st.markdown("---")

# Determine drawdown alert state
if effective_scenario_drawdown <= -35.0:
    dd_bg = "#FFCDD2"; dd_border = "#D32F2F"; dd_icon = "\U0001f6a8"; dd_text_color = "#B71C1C"
elif effective_scenario_drawdown <= -20.0:
    dd_bg = "#FFE0B2"; dd_border = "#E65100"; dd_icon = "\u26a0\ufe0f"; dd_text_color = "#E65100"
elif effective_scenario_drawdown <= -10.0:
    dd_bg = "#FFF9C4"; dd_border = "#F9A825"; dd_icon = "\u26a0\ufe0f"; dd_text_color = "#F57F17"
else:
    dd_bg = "#E8F5E9"; dd_border = "#2E7D32"; dd_icon = "\u2705"; dd_text_color = "#2E7D32"

# Determine risk score alert state
if systemic_risk_score >= 2:
    rs_bg = "#FFCDD2"; rs_border = "#D32F2F"; rs_icon = "\U0001f6a8"; rs_text_color = "#B71C1C"
elif systemic_risk_score == 1:
    rs_bg = "#FFE0B2"; rs_border = "#E65100"; rs_icon = "\u26a0\ufe0f"; rs_text_color = "#E65100"
else:
    rs_bg = "#E8F5E9"; rs_border = "#2E7D32"; rs_icon = "\u2705"; rs_text_color = "#2E7D32"

# Peak horizon is always informational
pk_bg = "#E3F2FD"; pk_border = "#1565C0"; pk_icon = "\U0001f4ca"; pk_text_color = "#1565C0"

metric_col_1, metric_col_2, metric_col_3 = st.columns(3)

with metric_col_1:
    st.markdown(f"""
    <div style="background:{dd_bg}; border-left:6px solid {dd_border}; border-radius:10px; padding:20px; text-align:center;">
        <div style="font-size:14px; color:#555; font-weight:600;">EFFECTIVE DRAWDOWN FROM PEAK</div>
        <div style="font-size:42px; font-weight:800; color:{dd_text_color}; margin:8px 0;">{dd_icon} {effective_scenario_drawdown:.2f}%</div>
        <div style="font-size:12px; color:#777;">{'ALERT: Deep drawdown detected!' if effective_scenario_drawdown <= -20 else 'Correction zone' if effective_scenario_drawdown <= -10 else 'Within normal range'}</div>
    </div>
    """, unsafe_allow_html=True)

with metric_col_2:
    st.markdown(f"""
    <div style="background:{rs_bg}; border-left:6px solid {rs_border}; border-radius:10px; padding:20px; text-align:center;">
        <div style="font-size:14px; color:#555; font-weight:600;">CALCULATED MACRO RISK SCORE</div>
        <div style="font-size:42px; font-weight:800; color:{rs_text_color}; margin:8px 0;">{rs_icon} {systemic_risk_score} / 3</div>
        <div style="font-size:12px; color:#777;">{'CRITICAL: Multiple risk triggers active!' if systemic_risk_score >= 2 else 'Elevated: 1 risk factor active' if systemic_risk_score == 1 else 'All clear — no risk triggers'}</div>
    </div>
    """, unsafe_allow_html=True)

with metric_col_3:
    st.markdown(f"""
    <div style="background:{pk_bg}; border-left:6px solid {pk_border}; border-radius:10px; padding:20px; text-align:center;">
        <div style="font-size:14px; color:#555; font-weight:600;">ACTIVE ROLLING TARGET PEAK</div>
        <div style="font-size:42px; font-weight:800; color:{pk_text_color}; margin:8px 0;">{pk_icon} {active_rolling_peak:,.2f}</div>
        <div style="font-size:12px; color:#777;">All-time high reference horizon</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# ENHANCED ZONE BANNER — TRADING TERMINAL STYLE
# ------------------------------------------------------------------------------
# Pulse animation for STRONG BUY and STRONG SELL
pulse_css = ""
if active_allocation_zone in ["STRONG BUY", "STRONG SELL"]:
    pulse_css = """
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(211, 47, 47, 0.6); }
        50% { box-shadow: 0 0 25px 10px rgba(211, 47, 47, 0.3); }
        100% { box-shadow: 0 0 0 0 rgba(211, 47, 47, 0.6); }
    }
    """

st.markdown(f"""
<style>
    {pulse_css}
</style>
<div style="
    background: linear-gradient(135deg, {zone_color}, {zone_color}DD);
    border-radius: 16px;
    padding: 30px 40px;
    text-align: center;
    {'animation: pulse 2s infinite;' if active_allocation_zone in ['STRONG BUY', 'STRONG SELL'] else ''}
    border: 2px solid {zone_color};
    margin-bottom: 10px;
">
    <div style="font-size:50px; margin-bottom:5px;">{zone_emoji}</div>
    <div style="font-size:13px; color:{zone_text_color}; opacity:0.8; letter-spacing:3px; text-transform:uppercase; font-weight:600;">Target Evaluation Matrix Output</div>
    <div style="font-size:32px; font-weight:900; color:{zone_text_color}; margin:10px 0; letter-spacing:2px;">{zone_presentation_title}</div>
    <div style="font-size:16px; color:{zone_text_color}; opacity:0.9; font-weight:400;">{zone_subtitle}</div>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# 6. CASCADING RESOURCE WATERFALL DECISION MATRIX
# ==============================================================================
st.markdown("### \U0001f4cb Tactical Allocation Recommendations")

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
    suggested_cash_outflow = 0.0
    suggested_srs_outflow = 0.0
    suggested_cpf_outflow = 0.0
    st.warning("\u26a0\ufe0f Systemic Bubble Risk Detected. Pausing new deployments. Consider taking profits or building up cash reserves.")

else:
    suggested_cash_outflow = 0.0
    suggested_srs_outflow = 0.0
    suggested_cpf_outflow = 0.0
    st.info("\u2139\ufe0f Market is trading inside normal boundaries. Maintain standard Dollar-Cost Averaging (DCA) schedules.")

remaining_cash = cash_balance - suggested_cash_outflow
remaining_srs = srs_balance - suggested_srs_outflow
remaining_cpf = cpf_oa_balance - suggested_cpf_outflow
total_tactical_deployed = suggested_cash_outflow + suggested_srs_outflow + suggested_cpf_outflow

display_col_1, display_col_2, display_col_3 = st.columns(3)

with display_col_1:
    st.markdown("#### \U0001f4b5 Liquid Cash Capital")
    st.metric("Suggested Cash Deploy", f"S${suggested_cash_outflow:,.2f}", help="Extracted purely from cash exceeding your emergency shield buffer.")
    st.caption(f"Remaining Cash Left: S${remaining_cash:,.2f}")

with display_col_2:
    st.markdown("#### \U0001f4c8 Supplementary Retirement (SRS)")
    st.metric("Suggested SRS Deploy", f"S${suggested_srs_outflow:,.2f}", help="Tax-deferred investments optimization.")
    st.caption(f"Remaining SRS Left: S${remaining_srs:,.2f}")

with display_col_3:
    st.markdown("#### \U0001f6e1\ufe0f CPF Ordinary Account")
    st.metric("Suggested CPF-OA Deploy", f"S${suggested_cpf_outflow:,.2f}", help="Protects the S$20k floor to secure the extra 1% yield if toggled.")
    st.caption(f"Remaining CPF-OA Left: S${remaining_cpf:,.2f}")

st.markdown("---")
st.subheader(f"Total Capital to Deploy in this Tranche: :green[S${total_tactical_deployed:,.2f}]")
