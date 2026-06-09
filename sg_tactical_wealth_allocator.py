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

st.title("🇸🇬 Tactical Wealth Allocation & Future Drawdown Simulator")
st.caption("A dynamic live-updating platform evaluating S&P 500, Nasdaq, STI, and HSI under cascading Singapore structural asset pool parameters.")

# ==============================================================================
# 2. SIDEBAR PARAMETER AND ASSET POOL ENGINE
# ==============================================================================
st.sidebar.markdown("## 💰 Your Available Capital Pools")
cash_balance = st.sidebar.number_input("Liquid Cash Savings Pool ($)", min_value=0.0, value=100000.0, step=5000.0)
srs_balance = st.sidebar.number_input("Supplementary Retirement Scheme (SRS) ($)", min_value=0.0, value=35000.0, step=5000.0)
cpf_oa_balance = st.sidebar.number_input("CPF Ordinary Account (OA) ($)", min_value=0.0, value=180000.0, step=5000.0)

st.sidebar.markdown("---")
st.sidebar.markdown("## ⚙️ Core Risk Safeguards")
emergency_buffer = st.sidebar.number_input("Emergency Liquid Cash Buffer ($)", min_value=0.0, value=20000.0, step=1000.0)
preserve_cpf_bonus = st.sidebar.checkbox("Preserve S$20k CPF-OA Core Floor", value=True, help="Protects the initial structural floor space to secure the government's extra 1% bonus yield tier.")

# Available investment options mapping configuration
# Using reliable yfinance ticker symbols
INDEX_TICKERS = {
    "S&P 500 (US Market Core)": "^GSPC",
    "Nasdaq 100 (Tech Growth)": "^IXIC",
    "Straits Times Index (SG Value/REITs)": "^STI",
    "Hang Seng Index (HK Cyclical/Beta)": "^HSI"
}

# ==============================================================================
# 3. LIVE API DATA COLLECTION PIPELINE
# ==============================================================================
# Add a manual refresh trigger at the top of the sidebar controls
st.sidebar.markdown("---")
st.sidebar.markdown("## 🔄 Data Synchronization")
refresh_data_trigger = st.sidebar.button("🔄 Force Refresh Market Data", help="Clears local cache and fetches the latest live price feeds.")

# Clear the Streamlit cache BEFORE harvesting if the user clicks the force refresh button
if refresh_data_trigger:
    st.cache_data.clear()
    st.toast("Cache cleared! Re-harvesting data pipelines...", icon="🔄")

@st.cache_data(ttl=14400)  # Data cached for 4 hours to maximize performance
def harvest_market_historical_metrics():
    """
    Queries live closing metrics, calculates trailing historical milestones,
    moving horizons, and captures structural drawdown realities since 1997.
    """
    computed_metrics = {}
    for standard_name, target_ticker in INDEX_TICKERS.items():
        try:
            # Query maximum historical duration sequence starting before 1997
            ticker_object = yf.Ticker(target_ticker)
            dataframe = ticker_object.history(start="1997-01-01")

            # Small delay between API calls to avoid Yahoo Finance rate limiting
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
                st.warning(f"⚠️ No data returned for {standard_name} ({target_ticker}). The market may be closed or the ticker is unavailable.")
        except Exception as system_error:
            error_msg = str(system_error)
            if "Too Many Requests" in error_msg or "Rate" in error_msg or "429" in error_msg:
                st.error(f"Error fetching data for {standard_name}: Too Many Requests. Rate limited. Try after a while.")
            else:
                st.error(f"Error fetching data for {standard_name}: {error_msg}")
    return computed_metrics

with st.spinner("Harvesting live historical index structures via API pipelines..."):
    market_state_database = harvest_market_historical_metrics()

# ==============================================================================
# SAFETY CHECK: Ensure data was loaded before proceeding
# ==============================================================================
if not market_state_database:
    st.error("🚨 **No market data could be loaded.** Yahoo Finance may be temporarily rate-limiting this server. Please try:")
    st.markdown("""
    1. Wait **1-2 minutes** and click **🔄 Force Refresh Market Data** in the sidebar
    2. Reload the page (Ctrl+R / Cmd+R)
    3. If the issue persists, try again in 10-15 minutes
    """)
    st.stop()

# ==============================================================================
# 4. FUTURE DRAWDOWN STRESS TESTING CONTROL MATRIX (WITH HISTORICAL PICKER)
# ==============================================================================
st.markdown("### 🔮 Future Drawdown Scenario Modeler")
st.info("Simulate a future market crash or select a historical date to see past allocation zones.")

# Only show indices that were successfully loaded
available_indices = list(market_state_database.keys())
selected_index_profile = st.selectbox("Select Target Index Spectrum", available_indices)

# Safely access the selected index data
if selected_index_profile not in market_state_database:
    st.error(f"❌ Data for **{selected_index_profile}** is not available. Please select another index or refresh.")
    st.stop()

selected_index_package = market_state_database[selected_index_profile]
live_anchor_close = selected_index_package["live_close"]
historical_ath_anchor = selected_index_package["ath_peak"]
underlying_data = selected_index_package["underlying_df"]

# Split controls into 4 clean columns to fit the new date picker
control_col_1, control_col_2, control_col_3, control_col_4 = st.columns(4)

with control_col_1:
    # Convert index to timezone-naive to avoid comparisons error with date_input
    underlying_data.index = underlying_data.index.tz_localize(None)
    min_date = underlying_data.index.min().to_pydatetime().date()
    max_date = underlying_data.index.max().to_pydatetime().date()
    use_historical = st.checkbox("Use Historical Date Price", value=False)
    if use_historical:
        target_date = st.date_input("Pick Historical Date", value=max_date, min_value=min_date, max_value=max_date)
        # Find closest available market day row
        closest_row_idx = underlying_data.index.get_indexer([pd.Timestamp(target_date)], method='nearest')[0]
        closest_row = underlying_data.iloc[closest_row_idx]
        picked_price = float(closest_row['Close'])
        st.caption(f"Price on {target_date.strftime('%Y-%m-%d')}: **{picked_price:,.2f}**")
    else:
        picked_price = None

with control_col_2:
    # Use historical price if checked, otherwise unlock the manual slider
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
# Override the price target variable if historical mode is active
evaluation_price = picked_price if use_historical else simulated_future_price

# Dynamically evaluate the trailing peak context
active_rolling_peak = max(historical_ath_anchor, evaluation_price)
effective_scenario_drawdown = ((evaluation_price - active_rolling_peak) / active_rolling_peak) * 100
baseline_200_ma = selected_index_package["ma_200"]

# Calculate Systemic Macro Risk Scores based on simulated indicators
systemic_risk_score = 0
if simulated_future_pmi < 50.0:
    systemic_risk_score += 1
if simulated_yield_spread < 0.0:
    systemic_risk_score += 1
if evaluation_price < baseline_200_ma:
    systemic_risk_score += 1

# Define asset pricing target execution zones
if effective_scenario_drawdown <= -35.0:
    active_allocation_zone = "STRONG BUY"
    zone_presentation_title = "🚨 STRONG BUY ZONE (Generational Allocation Opportunity)"
    alert_delivery_ui = st.error
elif effective_scenario_drawdown <= -20.0:
    active_allocation_zone = "BUY"
    zone_presentation_title = "🟢 BUY ZONE (Structural Bear Market Value Framework)"
    alert_delivery_ui = st.warning
elif effective_scenario_drawdown <= -10.0:
    active_allocation_zone = "INITIAL BUY"
    zone_presentation_title = "🟡 INITIAL BUY ZONE (Healthy Market Correction/Nibble Target)"
    alert_delivery_ui = st.info
elif evaluation_price > (1.20 * baseline_200_ma) and systemic_risk_score >= 2:
    active_allocation_zone = "STRONG SELL"
    zone_presentation_title = "🔴 STRONG SELL ZONE (Systemic Market Bubble / Maximize Liquidity)"
    alert_delivery_ui = st.error
else:
    active_allocation_zone = "HOLD"
    zone_presentation_title = "⚪ HOLD / OVERALL STANDARD DOLLAR-COST AVERAGE ZONE"
    alert_delivery_ui = st.success

# Display summary metric readouts
metric_display_col_1, metric_display_col_2, metric_display_col_3 = st.columns(3)
with metric_display_col_1:
    st.metric("Effective Drawdown From Peak", f"{effective_scenario_drawdown:.2f}%")
with metric_display_col_2:
    st.metric("Calculated Macro Risk Core Score", f"{systemic_risk_score} / 3")
with metric_display_col_3:
    st.metric("Active Rolling Target Peak Horizon", f"{active_rolling_peak:,.2f}")

alert_delivery_ui(f"**Target Evaluation Matrix Output:** {zone_presentation_title}")

# ==============================================================================
# 6. CASCADING RESOURCE WATERFALL DECISION MATRIX
# ==============================================================================
st.markdown("### 📋 Tactical Allocation Recommendations")

# Compute individual net usable resources based on sidebar risk parameters
usable_cash_reserves = max(0.0, cash_balance - emergency_buffer)
usable_srs_reserves = srs_balance
usable_cpf_reserves = max(0.0, cpf_oa_balance - 20000.0) if preserve_cpf_bonus else cpf_oa_balance

# Initialize suggested deployment outflow amounts
suggested_cash_outflow = 0.0
suggested_srs_outflow = 0.0
suggested_cpf_outflow = 0.0

# Strategic ruleset engine execution based on calculated market zones
if active_allocation_zone == "STRONG BUY":
    # Maximum conviction deployment: Deploy 100% of all available tactical capital
    suggested_cash_outflow = usable_cash_reserves
    suggested_srs_outflow = usable_srs_reserves
    suggested_cpf_outflow = usable_cpf_reserves

elif active_allocation_zone == "BUY":
    # High conviction structural bear market deployment
    suggested_cash_outflow = usable_cash_reserves * 0.50   # Deploy 50% of free cash
    suggested_srs_outflow = usable_srs_reserves * 0.75     # Deploy 75% of SRS funds
    suggested_cpf_outflow = usable_cpf_reserves * 0.40     # Deploy 40% of usable CPF-OA

elif active_allocation_zone == "INITIAL BUY":
    # Healthy correction nibble: Light deployment to build initial positions
    suggested_cash_outflow = usable_cash_reserves * 0.20   # Deploy 20% of free cash
    suggested_srs_outflow = usable_srs_reserves * 0.30     # Deploy 30% of SRS funds
    suggested_cpf_outflow = usable_cpf_reserves * 0.15     # Deploy 15% of usable CPF-OA

elif active_allocation_zone == "STRONG SELL":
    # Systemic bubble market warning: Stop buying and maximize liquidity safety
    suggested_cash_outflow = 0.0
    suggested_srs_outflow = 0.0
    suggested_cpf_outflow = 0.0
    st.warning("⚠️ Systemic Bubble Risk Detected. Pausing new deployments. Consider taking profits or building up cash reserves.")

else:
    # Default HOLD / DCA Zone: No bulk opportunistic deployment required
    suggested_cash_outflow = 0.0
    suggested_srs_outflow = 0.0
    suggested_cpf_outflow = 0.0
    st.info("ℹ️ Market is trading inside normal boundaries. Maintain standard Dollar-Cost Averaging (DCA) schedules.")

# Calculate final remaining untouched balances after proposed deployments
remaining_cash = cash_balance - suggested_cash_outflow
remaining_srs = srs_balance - suggested_srs_outflow
remaining_cpf = cpf_oa_balance - suggested_cpf_outflow
total_tactical_deployed = suggested_cash_outflow + suggested_srs_outflow + suggested_cpf_outflow

# Render UI layout display cards for allocations
display_col_1, display_col_2, display_col_3 = st.columns(3)

with display_col_1:
    st.markdown("#### 💵 Liquid Cash Capital")
    st.metric("Suggested Cash Deploy", f"S${suggested_cash_outflow:,.2f}", help="Extracted purely from cash exceeding your emergency shield buffer.")
    st.caption(f"Remaining Cash Left: S${remaining_cash:,.2f}")

with display_col_2:
    st.markdown("#### 📈 Supplementary Retirement (SRS)")
    st.metric("Suggested SRS Deploy", f"S${suggested_srs_outflow:,.2f}", help="Tax-deferred investments optimization.")
    st.caption(f"Remaining SRS Left: S${remaining_srs:,.2f}")

with display_col_3:
    st.markdown("#### 🛡️ CPF Ordinary Account")
    st.metric("Suggested CPF-OA Deploy", f"S${suggested_cpf_outflow:,.2f}", help="Protects the S$20k floor to secure the extra 1% yield if toggled.")
    st.caption(f"Remaining CPF-OA Left: S${remaining_cpf:,.2f}")

st.markdown("---")
st.subheader(f"Total Capital to Deploy in this Tranche: :green[S${total_tactical_deployed:,.2f}]")
