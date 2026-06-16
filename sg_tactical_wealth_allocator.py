import streamlit as st
import numpy as np
import pandas as pd
import datetime
import plotly.graph_objects as ob

# ==========================================
# 1. PAGE SETUP & CORPORATE DESIGN SYSTEM
# ==========================================
st.set_page_config(
    page_title="Singapore Tactical Wealth Allocator",
    page_icon="🇸🇬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Institutional CSS Injector
st.markdown("""
<style>
    /* Main Background & Fonts */
    .stApp { background-color: #F8FAFC; color: #1E293B; }
    h1, h2, h3 { font-family: 'Inter', -apple-system, sans-serif; font-weight: 700; color: #0F172A; }
    
    /* Custom Executive KPI Cards */
    .kpi-card {
        background: #FFFFFF;
        padding: 24px;
        border-radius: 12px;
        border-top: 4px solid #2563EB;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        margin-bottom: 16px;
    }
    .kpi-title { font-size: 0.85rem; font-weight: 600; text-transform: uppercase; color: #64748B; letter-spacing: 0.05em; }
    .kpi-value { font-size: 1.85rem; font-weight: 700; color: #0F172A; margin: 4px 0; font-family: monospace; }
    .kpi-subtitle { font-size: 0.8rem; color: #94A3B8; }
    
    /* Specific Variant Colors */
    .border-crimson { border-top: 4px solid #EF4444 !important; }
    .border-amber { border-top: 4px solid #F59E0B !important; }
    .border-slate { border-top: 4px solid #475569 !important; }
    
    /* Typography Overrides */
    .mono-text { font-family: monospace; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. FIXED SIDEBAR GLOBAL RISK PARAMETERS
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/singapore.png", width=64)
    st.title("Capital Guardrails")
    st.caption("Configure dynamic balance allocations & liquid thresholds.")
    st.hr()
    
    # Wallet Allocation Inputs
    st.subheader("💼 Portfolio Balances")
    cash_bal = st.number_input("Liquid Cash (S$)", min_value=0, value=80000, step=5000)
    srs_bal = st.number_input("Supplementary Retirement Scheme (S$)", min_value=0, value=35000, step=5000)
    cpf_bal = st.number_input("CPF Ordinary Account (S$)", min_value=0, value=160000, step=5000)
    
    st.hr()
    st.subheader("🛡️ Safety Floor Parameters")
    preserve_cpf_floor = st.toggle("Preserve S$20,000 CPF-OA Floor", value=True)
    emergency_buffer = st.number_input("Emergency Cash Reserve (S$)", min_value=0, value=15000, step=1000)
    
    st.hr()
    st.subheader("📈 Reference Configurations")
    peak_horizon = st.selectbox("Drawdown Peak Reference Horizon", ["Rolling 252-Day Peak", "All-Time High (ATH)"])
    
    # Calculate Deployable Pools Instantly
    actual_cpf_pool = max(0, cpf_bal - 20000) if preserve_cpf_floor else cpf_bal
    actual_cash_pool = max(0, cash_bal - emergency_buffer)
    total_liquidity = actual_cash_pool + srs_bal + actual_cpf_pool

# ==========================================
# 3. DUMMY DATA ENGINE (PIPELINE MIRROR)
# ==========================================
# Mock historic price data for Tseng Channel visualization
dates = pd.date_range(end=datetime.datetime.today(), periods=300, freq='D')
np.random.seed(42)
price_trend = np.linspace(2500, 3320, 300)
noise = np.random.normal(0, 45, 300)
simulated_prices = price_trend + noise

# Generate standard regression bands
log_prices = np.log(simulated_prices)
x = np.arange(len(log_prices))
slope, intercept = np.polyfit(x, log_prices, 1)
reg_line = np.exp(slope * x + intercept)
sd_high = np.exp(slope * x + intercept + 0.08)
sd_low = np.exp(slope * x + intercept - 0.08)

# ==========================================
# 4. TOP WORKSPACE: EXECUTIVE COMMAND MATRIX
# ==========================================
st.title("🇸🇬 Tactical Wealth Allocation Command Center")
st.markdown("Multi-tier framework balancing Tseng Channel regressions with real-time systemic macro risk.")

kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

with kpi_col1:
    st.markdown("""
    <div class="kpi-card">
        <div class="kpi-title">Asset Class Target</div>
        <div class="kpi-value">SPDR STI ETF</div>
        <div class="kpi-subtitle">Ticker: <b>ES3.SI</b> | Equity Segment</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col2:
    st.markdown("""
    <div class="kpi-card border-crimson">
        <div class="kpi-title">Current Drawdown</div>
        <div class="kpi-value" style="color: #EF4444;">-12.4%</div>
        <div class="kpi-subtitle">Ref: Rolling 252-Day Peak Cycle</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col3:
    st.markdown("""
    <div class="kpi-card border-amber">
        <div class="kpi-title">Tactical Allocation Zone</div>
        <div class="kpi-value" style="color: #D97706;">INITIAL BUY</div>
        <div class="kpi-subtitle">Condition met: Deploy Cash First</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col4:
    st.markdown("""
    <div class="kpi-card border-slate">
        <div class="kpi-title">Systemic Macro Risk Score</div>
        <div class="kpi-value">42 / 100</div>
        <div class="kpi-subtitle">Regime Classification: <b>WATCH</b></div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 5. MIDDLE WORKSPACE: DEPLOYMENT ENGINE
# ==========================================
st.subheader("⚡ Active Capital Deployment Engine")
matrix_col, proxy_col = st.columns([3, 2])

with matrix_col:
    st.caption("Recommended allocation layout mapped down to specific local structural capital lines.")
    
    # Calculate recommended tranches dynamically (simulated numbers based on inputs)
    cash_tranche = actual_cash_pool * 0.12 if actual_cash_pool > 0 else 0.0
    srs_tranche = 0.0  # Kept locked during early buy tranches
    cpf_tranche = 0.0  # Preserved for deep corrections
    
    data_matrix = {
        "Capital Pool": ["Liquid Cash Pool", "Supplementary Retirement (SRS)", "CPF Ordinary Account (CPF-OA)"],
        "Total Structural Base": [f"S$ {cash_bal:,.2f}", f"S$ {srs_bal:,.2f}", f"S$ {cpf_bal:,.2f}"],
        "Net Available Liquid Asset": [f"S$ {actual_cash_pool:,.2f}", f"S$ {srs_bal:,.2f}", f"S$ {actual_cpf_pool:,.2f}"],
        "Suggested Action Tranche": [f"S$ {cash_tranche:,.2f}", "S$ 0.00", "S$ 0.00"],
        "Status Indicator": ["🟢 Active Direct Deployment", "💤 Preserved for Value (BUY)", "💤 Preserved for Deep Value (STRONG BUY)"]
    }
    st.dataframe(pd.DataFrame(data_matrix), use_container_width=True, hide_index=True)

with proxy_col:
    st.caption("Compliance Translation Layer")
    # Simulate a smart proxy routing message card
    st.info("💡 **Asset Class Rule Translation Engine**")
    st.markdown(
        """
        **Target Configuration Profile:** US Large-Cap / Technology Indices
        
        *   ⚠️ **CPFIS Constraint Alert:** Selected local accounts cannot trade standard US-listed exchange instruments (`VOO` / `QQQ`) directly on western exchanges.
        *   🔄 **Automatic Route Redirection:** If scaling inputs target deep value regions requiring a shift to **CPF-OA**, execution directives will switch automatically to tracking proxy instruments:
            *   **S&P 500 Alternative Base:** `Amundi Prime USA Fund` (via Endowus CPFIS platform)
            *   **NASDAQ Alternative Base:** `Lion Global Infinity U.S. 500 Stock Index Fund`
        *   ⚙️ *Pipeline Integrity Note: Regressions and historical channels are kept mapped to underlying core US indices to ensure statistical accuracy.*
        """
    )

# ==========================================
# 6. BOTTOM WORKSPACE: VALUATION LAYERS
# ==========================================
st.subheader("🔍 Dual-Engine Asset Valuation Engine")
tab_chart, tab_macro = st.tabs(["曾氏通道 (Secular Trend Channel)", "Cycle Macro Risk Monitors"])

with tab_chart:
    v_col1, v_col2 = st.columns([3, 1])
    
    with v_col1:
        # Generate Plotly Tseng Channel
        fig = ob.Figure()
        fig.add_trace(ob.Scatter(x=dates, y=simulated_prices, name="Asset Closing Price", line=dict(color='#0F172A', width=2)))
        fig.add_trace(ob.Scatter(x=dates, y=reg_line, name="Regression Mean Line", line=dict(color='#2563EB', dash='dash')))
        fig.add_trace(ob.Scatter(x=dates, y=sd_high, name="+1 Standard Deviation", line=dict(color='#94A3B8', width=1)))
        fig.add_trace(ob.Scatter(x=dates, y=sd_low, name="-1 Standard Deviation", line=dict(color='#EF4444', width=1, dash='dot')))
        
        fig.update_layout(
            title="Log-Linear Regression Channel Analysis",
            xaxis_title="Date Sequence Tracking",
            yaxis_title="Price Framework (S$)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=60, b=20),
            plot_bgcolor="white",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        
    with v_col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.metric(label="Current Z-Score Context", value="-1.14 σ", delta="Attractive Market Region")
        st.caption("The system measures deviation away from the long-term secular growth baseline to compute systemic undervaluation thresholds.")
        st.divider()
        st.markdown("**Historical Overlays Displayed:**")
        st.caption("✓ 2020 Black Swan COVID Structural Dip")
        st.caption("✓ 2022 Central Bank Tightening De-rating Cycle")

with tab_macro:
    m_col1, m_col2, m_col3 = st.columns(3)
    
    with m_col1:
        st.metric(label="Implied Volatility (VIX Index Proxy)", value="14.20", delta="Normal Liquidity State")
        st.progress(0.14)
        st.caption("Risk allocation triggers penalty parameters when VIX moves past 15.00.")
        
    with m_col2:
        st.metric(label="Treasury Curve Yield Spread (10Y - 3M)", value="+0.22%", delta="Expansion State")
        st.progress(0.40)
        st.caption("Inverted status signals late-stage industrial cycle contractions.")
        
    with m_col3:
        st.metric(label="Purchasing Managers Index (Regional PMI)", value="51.00", delta="Manufacturing Growth")
        st.progress(0.52)
        st.caption("Monitors expansionary or contractionary environments across regional manufacturing hubs.")

# ==========================================
# 7. LOWER-TIER: CRASH & PORTFOLIO SIMULATOR
# ==========================================
st.hr()
st.subheader("🎮 Interactive Crash & Portfolio Sandbox Simulator")
sim_col1, sim_col2 = st.columns([1, 2])

with sim_col1:
    st.markdown("**Backtest Optimization Parameters:**")
    trigger_dd = st.slider("Target Execution Drawdown Trigger (%)", min_value=-5, max_value=-50, value=-10, step=-1)
    sim_capital = st.number_input("Incremental Cash Injected per Trigger (S$)", min_value=1000, value=10000, step=1000)
    
    st.button("Run Counter-Cyclical Simulation Model", use_container_width=True, type="primary")

with sim_col2:
    st.caption("Evaluated performance results during corresponding cycle drawdowns across historic correction periods:")
    
    # Generate mock performance data matrix for historical validation
    sim_results = {
        "Historical Event Horizon": ["2008 Great Financial Crisis", "2015 China Growth Taper Shock", "2020 COVID Liquidity Squeeze", "2022 Rate Hikes Correction"],
        "Detected Tranche Trigger Hits": ["4 Times", "1 Time", "2 Times", "1 Time"],
        "Total Portfolio Outlay": ["S$ 40,000.00", "S$ 10,000.00", "S$ 20,000.00", "S$ 10,000.00"],
        "Subsequent Alpha Return (3Y)": ["+48.3%", "+18.4%", "+62.1%", "+24.5%"]
    }
    st.table(pd.DataFrame(sim_results))
