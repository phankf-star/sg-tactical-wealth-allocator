import math
import time
import json
import os
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title='Global Drawdown Allocation Engine v36 Phase 2', layout='wide', initial_sidebar_state='expanded')

BLUE = '#2563EB'; RED = '#EF4444'; ORANGE = '#F97316'; AMBER = '#F59E0B'; GREEN = '#16A34A'; SLATE = '#64748B'; PURPLE = '#7C3AED'; TEXT = '#111827'; MUTED = '#6B7280'

# Currency display helpers.
# Use HTML entity for dollar sign inside Markdown/HTML-rendered blocks to avoid Streamlit LaTeX parsing.
SGD_TEXT = 'S$'
SGD_HTML = 'S&#36;'
def current_currency_text():
    return st.session_state.get('currency_text', SGD_TEXT)
def current_currency_html():
    return st.session_state.get('currency_html', SGD_HTML)
def fmt_sgd(value):
    return f'{current_currency_text()}{value:,.0f}'
def fmt_sgd_html(value):
    return f'{current_currency_html()}{value:,.0f}'


st.markdown('''
<style>
.block-container {padding-top:1.2rem; padding-bottom:2rem;}
div[data-testid="stMetric"] {background:white; border:1px solid #E2E8F0; padding:0.8rem; border-radius:8px; box-shadow:0 1px 2px rgba(0,0,0,0.02);}
.metric-card-like {background:white; border:1px solid #E2E8F0; padding:12px 16px; border-radius:8px; box-shadow:0 1px 2px rgba(0,0,0,0.02); margin-bottom:12px;}
div[data-testid="stExpander"] {border:1px solid #E2E8F0; border-radius:8px; box-shadow:0 1px 2px rgba(0,0,0,0.02); background:white; margin-bottom:1rem;}
.stRadio > label {font-weight:600; color:#111827; margin-bottom:8px;}
div[data-testid="stSidebarNav"] {display:none;}
iframe {border-radius:8px;}
</style>
''', unsafe_allow_html=True)

def card(title, value, subtext, color):
    return f'''
    <div style="background:white; border:1px solid #E2E8F0; border-left:4px solid {color}; padding:14px 16px; border-radius:8px; box-shadow:0 1px 2px rgba(0,0,0,0.02); height:100%;">
        <div style="font-size:0.75rem; font-weight:700; color:{MUTED}; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:4px;">{title}</div>
        <div style="font-size:1.35rem; font-weight:800; color:{TEXT}; line-height:1.2; margin-bottom:4px;">{value}</div>
        <div style="font-size:0.72rem; font-weight:500; color:{MUTED};">{subtext}</div>
    </div>
    '''

PMI_NA_MARKETS = ['CSOP iEdge SREIT ETF', 'Lion-Phillip S-REIT ETF']

@st.cache_data(ttl=3600)
def fetch_mkt_data(ticker, start='2010-01-01'):
    try:
        df = yf.download(ticker, start=start)
        if df.empty: return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df.columns = [c.get_level_values(0) if isinstance(c, tuple) else c for c in df.columns]
        df.rename(columns={'Date':'Date','Close':'Close','High':'High','Low':'Low','Open':'Open','Volume':'Volume'}, inplace=True)
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        return df[['Date','Close']].dropna().sort_values('Date').reset_index(drop=True)
    except:
        return pd.DataFrame()

def build_trend_channel(df, len_window=2040, model='Expanding Window'):
    if len(df) < 100:
        return pd.Series(0.0, index=df.index), pd.Series(0.0, index=df.index), pd.Series(0.0, index=df.index)
    close = df['Close'].values
    n = len(df)
    mu = np.zeros(n)
    sig = np.zeros(n)
    t = np.arange(n)
    
    if model == 'Rolling Window':
        w = min(len_window, n)
        for i in range(n):
            start = max(0, i - w + 1)
            sub_t = t[start:i+1]
            sub_c = np.log(close[start:i+1])
            if len(sub_t) > 1:
                A = np.vstack([sub_t, np.ones(len(sub_t))]).T
                m, c = np.linalg.lstsq(A, sub_c, rcond=None)[0]
                pred = m * i + c
                mu[i] = np.exp(pred)
                sig[i] = np.std(sub_c - (m * sub_t + c))
            else:
                mu[i] = close[i]
                sig[i] = 0.05
    else: # Expanding Window
        sum_t = 0.0; sum_t2 = 0.0; sum_y = 0.0; sum_ty = 0.0
        for i in range(n):
            y = np.log(close[i])
            sum_t += i; sum_t2 += i*i; sum_y += y; sum_ty += i*y
            k = i + 1
            if k > 1:
                denom = (k * sum_t2 - sum_t * sum_t)
                if abs(denom) > 1e-9:
                    m = (k * sum_ty - sum_t * sum_y) / denom
                    c = (sum_y - m * sum_t) / k
                    pred = m * i + c
                    mu[i] = np.exp(pred)
                    
                    # Calculated expanding residual standard deviation
                    idx = np.arange(k)
                    fit = m * idx + c
                    sig[i] = np.std(np.log(close[:k]) - fit)
                else:
                    mu[i] = close[i]; sig[i] = 0.05
            else:
                mu[i] = close[i]; sig[i] = 0.05
                
    z = (np.log(close) - np.log(mu)) / np.where(sig == 0, 0.05, sig)
    return pd.Series(z, index=df.index), pd.Series(mu, index=df.index), pd.Series(sig, index=df.index)

def crash_events(df, thr=8.0, current=None, valuation_tc=None):
    if len(df) < 2: return pd.DataFrame()
    c = df['Close'].values
    d = df['Date'].values
    p_val = c[0]; p_idx = 0; inside = False
    p_date = d[0]; t_date = d[0]; max_dd = 0.0
    records = []
    
    for i in range(1, len(df)):
        if c[i] > p_val:
            if not inside:
                p_val = c[i]; p_idx = i; p_date = d[i]
            else:
                curr_dd = (c[i] - p_val) / p_val * 100.0
                if curr_dd < max_dd:
                    max_dd = curr_dd; t_date = d[i]
        else:
            curr_dd = (c[i] - p_val) / p_val * 100.0
            if curr_dd <= -thr:
                inside = True
            if curr_dd < max_dd:
                max_dd = curr_dd; t_date = d[i]
                
        if inside and (c[i] >= p_val or i == len(df)-1):
            dur = (pd.to_datetime(t_date) - pd.to_datetime(p_date)).days
            v_class = 'Neutral'
            if valuation_tc is not None and p_idx < len(valuation_tc):
                z = valuation_tc.iloc[p_idx]
                v_class = 'Overvalued' if z > 1.0 else ('Undervalued' if z < -1.0 else 'Fair Value')
            records.append({
                'Historical Label': f'Market Event {len(records)+1}',
                'Peak Date': pd.to_datetime(p_date).strftime('%Y-%m-%d'),
                'Drawdown %': round(max_dd, 2),
                'Trough Date': pd.to_datetime(t_date).strftime('%Y-%m-%d'),
                'Severity': 'Deep Crash' if max_dd <= -20 else ('Correction' if max_dd <= -10 else 'Pullback'),
                'Duration Days': max(1, dur),
                'Valuation Classification': v_class
            })
            p_val = c[i]; p_idx = i; p_date = d[i]; max_dd = 0.0; inside = False
            
    if current is not None and len(c) > 0:
        last_p = p_val
        c_dd = (current - last_p) / last_p * 100.0
        if c_dd <= -thr:
            dur = (datetime.now() - pd.to_datetime(p_date)).days
            records.append({
                'Historical Label': '⚠️ Current Cycle Action Window',
                'Peak Date': pd.to_datetime(p_date).strftime('%Y-%m-%d'),
                'Drawdown %': round(c_dd, 2),
                'Trough Date': 'Live Tracking',
                'Severity': 'Deep Crash' if c_dd <= -20 else ('Correction' if c_dd <= -10 else 'Pullback'),
                'Duration Days': max(1, dur),
                'Valuation Classification': 'OOS Quant Processed'
            })
    return pd.DataFrame(records)

def build_etf_reference_rows(sel):
    rows = [
        {'Source':'System Primary Spec','Role':'Target Asset Tracking','Instrument':'Hang Seng Index','Ticker':'^HSI','Coverage':'Primary Ticker Framework','Base CCY':'HKD','FX to SGD':0.1730},
        {'Source':'System Primary Spec','Role':'Target Asset Tracking','Instrument':'CSOP iEdge SREIT ETF','Ticker':'SRU.SI','Coverage':'Primary Ticker Framework','Base CCY':'SGD','FX to SGD':1.0000},
        {'Source':'System Primary Spec','Role':'Target Asset Tracking','Instrument':'Lion-Phillip S-REIT ETF','Ticker':'CLR.SI','Coverage':'Primary Ticker Framework','Base CCY':'SGD','FX to SGD':1.0000},
        {'Source':'System Primary Spec','Role':'Target Asset Tracking','Instrument':'SPDR S&P 500 ETF Trust','Ticker':'SPY','Coverage':'Primary Ticker Framework','Base CCY':'USD','FX to SGD':1.3520},
        {'Source':'System Primary Spec','Role':'Target Asset Tracking','Instrument':'iShares Core MSCI World ETF','Ticker':'EWRD.L','Coverage':'Primary Ticker Framework','Base CCY':'USD','FX to SGD':1.3520},
        {'Source':'System Primary Spec','Role':'System Alternative Reference','Instrument':'Tracker Fund of Hong Kong','Ticker':'2800.HK','Coverage':'Alternative System Tracker','Base CCY':'HKD','FX to SGD':0.1730},
        {'Source':'System Primary Spec','Role':'System Alternative Reference','Instrument':'iShares Core Hang Seng Index ETF','Ticker':'3115.HK','Coverage':'Alternative System Tracker','Base CCY':'HKD','FX to SGD':0.1730},
        {'Source':'System Primary Spec','Role':'System Alternative Reference','Instrument':'Hang Seng Index ETF','膨胀':'2833.HK','Coverage':'Alternative System Tracker','Base CCY':'HKD','FX to SGD':0.1730}
    ]
    return [r for r in rows if r['Instrument'] == sel or r['Role'] == 'System Alternative Reference']

def add_performance_and_gap(rows, sel):
    out = []
    for r in rows:
        df = fetch_mkt_data(r['Ticker'], start='2023-01-01')
        if not df.empty and len(df) >= 2:
            c_now = df['Close'].iloc[-1]
            t_prev = df['Date'].iloc[-1]
            df_1y = df[df['Date'] <= (t_prev - pd.Timedelta(days=365))]
            c_1y = df_1y['Close'].iloc[-1] if not df_1y.empty else df['Close'].iloc[0]
            perf_1y = ((c_now - c_1y) / c_1y) * 100.0
            gap = 0.0
            if r['Instrument'] != sel:
                df_sel = fetch_mkt_data(next((x['Ticker'] for x in rows if x['Instrument'] == sel), '^HSI'), start='2023-01-01')
                if not df_sel.empty:
                    s_now = df_sel['Close'].iloc[-1]
                    df_s_1y = df_sel[df_sel['Date'] <= (pd.to_datetime(datetime.now()) - pd.Timedelta(days=365))]
                    s_1y = df_s_1y['Close'].iloc[-1] if not df_s_1y.empty else df_sel['Close'].iloc[0]
                    s_perf = ((s_now - s_1y) / s_1y) * 100.0
                    gap = perf_1y - s_perf
            out.append({**r, 'Price': f'{c_now:,.2f}', '1Y %': f'{perf_1y:+.2f}%', '1Y Gap': f'{gap:+.2f}%'})
        else:
            out.append({**r, 'Price': 'N/A', '1Y %': '0.00%', '1Y Gap': '0.00%'})
    return pd.DataFrame(out)

# ----------------------------------------------------------------
# 🧭 PLATFORM ASSET SPECIFICATION & SIDEBAR ARCHITECTURE
# ----------------------------------------------------------------
ASSET_METRIC_MAP = {
    'Hang Seng Index': {'ticker':'^HSI', 'base_ccy':'HKD', 'fx_rate':0.1732, 'thr':8.0, 'step':2.0, 'max_tranches':5, 'pmi_label':'China Manufacturing PMI'},
    'CSOP iEdge SREIT ETF': {'ticker':'SRU.SI', 'base_ccy':'SGD', 'fx_rate':1.0000, 'thr':5.0, 'step':1.5, 'max_tranches':4, 'pmi_label':'Singapore PMI'},
    'Lion-Phillip S-REIT ETF': {'ticker':'CLR.SI', 'base_ccy':'SGD', 'fx_rate':1.0000, 'thr':5.0, 'step':1.5, 'max_tranches':4, 'pmi_label':'Singapore PMI'},
    'SPDR S&P 500 ETF Trust': {'ticker':'SPY', 'base_ccy':'USD', 'fx_rate':1.3485, 'thr':6.0, 'step':2.0, 'max_tranches':5, 'pmi_label':'US ISM Manufacturing PMI'},
    'iShares Core MSCI World ETF': {'ticker':'EWRD.L', 'base_ccy':'USD', 'fx_rate':1.3485, 'thr':6.0, 'step':2.0, 'max_tranches':5, 'pmi_label':'Global Manufacturing PMI'}
}

with st.sidebar:
    st.markdown('<div style="font-size:1.15rem; font-weight:800; color:#1E293B; margin-bottom:2px;">🎯 Allocation Hub</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.7rem; font-weight:600; color:#64748B; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:16px;">Drawdown Allocation Engine v36</div>', unsafe_allow_html=True)
    
    # 💼 Owner / Business Mode Status System
    is_owner_mode = st.session_state.get('owner_mode', False)
    access_label = "💼 Owner Account" if is_owner_mode else "🔬 Analyst View"
    status_indicator = "● Verified (Family Trust Setup)" if is_owner_mode else "○ Standard Sandbox Mode"
    status_color = "#3B82F6" if is_owner_mode else "#64748B"
    
    st.markdown(f'''
    <div class="metric-card-like" style="background:#F8FAFC; margin-bottom:20px; border: 1px solid #E2E8F0;">
        <div style="font-size:0.7rem; font-weight:700; color:{MUTED}; text-transform:uppercase;">Identity Vector</div>
        <div style="font-size:0.95rem; font-weight:800; color:{TEXT}; margin:2px 0;">{access_label}</div>
        <div style="font-size:0.7rem; font-weight:600; color:{status_color};">{status_indicator}</div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Structural Profile Toggle Switch Matrix
    st.markdown("**System Profile Matrix**")
    t1, t2 = st.columns(2)
    with t1:
        if st.button("💼 Owner", use_container_width=True):
            st.session_state.owner_mode = True
            st.rerun()
    with t2:
        if st.button("🔬 Analyst", use_container_width=True):
            st.session_state.owner_mode = False
            st.rerun()
            
    st.markdown("---")
    asset_group = st.selectbox('Asset Class Portfolio Quadrant', ['Global Broad Equities', 'Regional Systemic Indexes', 'Real Estate Investment Trusts (REITs)'])
    
    if asset_group == 'Regional Systemic Indexes':
        avail_assets = ['Hang Seng Index']
    elif asset_group == 'Real Estate Investment Trusts (REITs)':
        avail_assets = ['CSOP iEdge SREIT ETF', 'Lion-Phillip S-REIT ETF']
    else:
        avail_assets = ['SPDR S&P 500 ETF Trust', 'iShares Core MSCI World ETF']
        
    sel = st.selectbox('Target System Instrument', avail_assets)
    cfg = ASSET_METRIC_MAP[sel]
    ticker = cfg['ticker']; base_ccy = cfg['base_ccy']; fx_rate = cfg['fx_rate']
    
    st.markdown("---")
    st.markdown("**Portfolio Capital Parameters**")
    total_dry_powder = st.number_input(f'Total Available Capital Dry Powder ({SGD_TEXT})', min_value=10000, max_value=100000000, value=1000000, step=50000)
    rule_mode = st.radio('Deployment Rule Infrastructure', ['Fixed Percentage Allocation', 'Dynamic Valuation Scaling'])
    model_type = st.radio('OOS Regressive Base Calibration', ['Expanding Window', 'Rolling Window'])
    
    st.markdown("---")
    active_section = st.radio("Navigation Portals", ['🧠 Executive Centre', '💰 Suggested Deploy', '🌦️ Market Conditions', '📊 Market Performance', '🏆 Crash Analytics', '📡 Audit Trail & Export'])

# ----------------------------------------------------------------
# 🧮 CORE DATA PROCESSING & ENGINE CALCULATIONS
# ----------------------------------------------------------------
ud = fetch_mkt_data(ticker)
if ud.empty:
    st.error(f"Platform Alert: High latency or failure pipeline scraping historical structures for {ticker}.")
    st.stop()

# Execution calculations
close = ud['Close'].iloc[-1]
ud['Peak'] = ud['Close'].cummax()
peak = ud['Peak'].iloc[-1]
dd = ((close - peak) / peak) * 100.0

ud['MA200'] = ud['Close'].rolling(window=200).mean()
ma200 = ud['MA200'].iloc[-1] if not pd.isna(ud['MA200'].iloc[-1]) else close

# Call analytical out-of-sample trend channel module
z_scores, mu_series, sig_series = build_trend_channel(ud, len_window=2040, model=model_type)
exec_z_score = z_scores.iloc[-1]
val_mu = mu_series.iloc[-1]
val_sig = sig_series.iloc[-1]

val_label = "Deep Undervaluation (Extreme Buy)" if exec_z_score < -2.0 else \
            ("Undervalued (Accumulate)" if exec_z_score < -1.0 else \
             ("Overvalued (Trim/Hold)" if exec_z_score > 1.0 else "Fair Value Alignment"))

# PMI Risk Regime mapping modules
chosen = cfg['pmi_label']
latest_in = 49.2 if sel in PMI_NA_MARKETS else 50.8
month_in = 'May 2026'

if 'latest_pmi_value' not in st.session_state:
    st.session_state.latest_pmi_value = latest_in
if 'latest_pmi_month' not in st.session_state:
    st.session_state.latest_pmi_month = month_in

pmi_val = st.session_state.latest_pmi_value
pmi_m = st.session_state.latest_pmi_month

base_score = 50.0
pmi_gap = 50.0 - pmi_val
live_score = clip_val(base_score + (pmi_gap * 4.0) if pmi_val < 50.0 else base_score - ((pmi_val - 50.0) * 2.5), 0, 100)

alert_level = "CRITICAL (High Macro Risk)" if live_score >= 70 else \
              ("WATCH (Elevated Stance)" if live_score >= 40 else "NORMAL (Stable Economic Expansion)")

# Core Deployment Matrix Rules
thr_trigger = cfg['thr']
step_trigger = cfg['step']
max_t = cfg['max_tranches']

zone = "STABLE HOLD (NO SYSTEM OVERLAYS)"
deploy_pct = 0.0

if dd <= -thr_trigger:
    passed = abs(dd) - thr_trigger
    t_idx = int(passed // step_trigger) + 1
    t_idx = min(t_idx, max_t)
    
    if rule_mode == 'Dynamic Valuation Scaling' and exec_z_score < 0:
        multiplier = 1.0 + min(abs(exec_z_score), 1.5)
    else:
        multiplier = 1.0
        
    base_fraction = 1.0 / max_t
    deploy_pct = min(t_idx * base_fraction * multiplier, 1.0)
    zone = f"CRASH ACTION CYCLE: DEPLOY TRANCHE {t_idx} ({'CRIMSON SIGNAL' if t_idx >=3 else 'AMBER SIGNAL'})"
elif dd <= -3.0:
    zone = "EARLY CORRECTION CORRIDOR (MONITOR PIPELINES)"
    deploy_pct = 0.0

deploy = total_dry_powder * deploy_pct
conf_label = "HIGH CONFIDENCE" if len(ud) > 1000 and abs(exec_z_score) > 0.5 else "STANDBY RE-CALIBRATION"

# ----------------------------------------------------------------
# 📋 RESTRUCTURED EXECUTIVE CENTRE LANDING PAGE
# ----------------------------------------------------------------
def render_executive():
    st.markdown(f"### 🧠 Executive Centre: {sel} ({ticker})")
    st.caption("Live asset class tactical deployment summary and underlying structural core metrics.")
    st.markdown("---")
    
    # 1. NEW FULL-WIDTH HERO ACTION BANNER (ALLOCATION STANCE & AMOUNT DOMINANT)
    is_buy_zone = "DEPLOY" in zone or "ACTION" in zone or "CORRIDOR" in zone
    accent_color = RED if is_buy_zone else SLATE
    bg_light = "#FEF2F2" if is_buy_zone else "#F8FAFC"
    
    st.markdown(f"""
        <div style="background-color: {bg_light}; border-left: 6px solid {accent_color}; padding: 26px; border-radius: 12px; margin-bottom: 26px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <span style="font-size: 0.82rem; font-weight: 700; color: {MUTED}; text-transform: uppercase; letter-spacing: 0.05em;">Tactical Allocation Stance</span>
            <h1 style="margin: 6px 0 18px 0; color: {accent_color}; font-size: 2.35rem; font-weight: 850; line-height: 1.1;">{zone}</h1>
            
            <div style="display: flex; flex-wrap: wrap; gap: 56px; margin-top: 18px; border-top: 1px solid #E2E8F0; padding-top: 20px;">
                <div>
                    <span style="font-size: 0.85rem; color: {MUTED}; font-weight: 600; display: block; margin-bottom: 4px;">Deployment Target</span>
                    <span style="font-size: 1.85rem; font-weight: 850; color: {TEXT};">{deploy_pct:.0%} <span style="font-size: 0.95rem; font-weight: 500; color: {MUTED};">of Total Dry Powder</span></span>
                </div>
                <div>
                    <span style="font-size: 0.85rem; color: {MUTED}; font-weight: 600; display: block; margin-bottom: 4px;">Suggested Capital Deploy ({rule_mode})</span>
                    <span style="font-size: 1.85rem; font-weight: 850; color: {TEXT};">{fmt_sgd_html(deploy)} <span style="font-size: 0.95rem; font-weight: 500; color: {MUTED};">Local Currency Equiv.</span></span>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # 2. SUBORDINATE DISCIPLINED DIAGNOSTICS ROW FLOWING UNDERNEATH
    st.markdown("#### 🔍 Underlying Market Drivers & Diagnostics")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(f"""
            <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; padding: 16px; border-radius: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); height: 100%;">
                <span style="font-size: 0.78rem; color: {MUTED}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.02em;">Live Index Level</span>
                <div style="font-size: 1.45rem; font-weight: 850; color: {TEXT}; margin: 4px 0;">{close:,.2f}</div>
                <span style="font-size: 0.75rem; color: {AMBER if close < ma200 else GREEN}; font-weight: 600;">200 MA: {ma200:,.2f}</span>
            </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""
            <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; padding: 16px; border-radius: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); height: 100%;">
                <span style="font-size: 0.78rem; color: {MUTED}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.02em;">Structural Drawdown</span>
                <div style="font-size: 1.45rem; font-weight: 850; color: {RED if dd <= -thr_trigger else TEXT}; margin: 4px 0;">{dd:.2f}%</div>
                <span style="font-size: 0.75rem; color: {MUTED}; font-weight: 600;">Cycle Peak: {peak:,.2f}</span>
            </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown(f"""
            <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; padding: 16px; border-radius: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); height: 100%;">
                <span style="font-size: 0.78rem; color: {MUTED}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.02em;">Valuation Z-Score (OOS)</span>
                <div style="font-size: 1.45rem; font-weight: 850; color: {GREEN if exec_z_score < -1.0 else TEXT}; margin: 4px 0;">{exec_z_score:.2f}</div>
                <span style="font-size: 0.72rem; color: {MUTED}; font-weight: 600; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{val_label}</span>
            </div>
        """, unsafe_allow_html=True)
        
    with c4:
        st.markdown(f"""
            <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; padding: 16px; border-radius: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); height: 100%;">
                <span style="font-size: 0.78rem; color: {MUTED}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.02em;">Market Risk Alert</span>
                <div style="font-size: 1.45rem; font-weight: 850; color: {GREEN if live_score < 40 else (AMBER if live_score < 70 else RED)}; margin: 4px 0;">{live_score:.0f}/100</div>
                <span style="font-size: 0.72rem; color: {MUTED}; font-weight: 600; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">Regime: {alert_level}</span>
            </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)
    
    # Bottom alignment sub-grid panel for pipeline audit traces
    ca, cb = st.columns(2)
    with ca:
        st.markdown(f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 12px 16px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.82rem; color: {MUTED}; font-weight: 600;">📡 Signal Confidence Matrix:</span>
                <span style="font-size: 0.85rem; color: {PURPLE}; font-weight: 700;">{conf_label}</span>
            </div>
        """, unsafe_allow_html=True)
    with cb:
        st.markdown(f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 12px 16px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.82rem; color: {MUTED}; font-weight: 600;">💱 System Base Asset Currency:</span>
                <span style="font-size: 0.85rem; color: {TEXT}; font-weight: 700;">{base_ccy} <span style="font-size: 0.75rem; font-weight: 500; color: {MUTED};">(FX to SGD: {fx_rate:.4f})</span></span>
            </div>
        """, unsafe_allow_html=True)

# ----------------------------------------------------------------
# 📂 COMPONENT RENDERERS FOR SUB-QUADRANTS (REMAIN INTACT)
# ----------------------------------------------------------------
def clip_val(v, mi, ma):
    return max(mi, min(v, ma))

def render_suggested(expanded=False):
    with st.expander('💰 Capital Deployment Tranche Allocation Details', expanded=expanded):
        st.markdown("#### Capital Allocation Multi-Tier Distribution Matrix")
        st.caption("Calculation architecture partitioning dry powder across progressive structural drawdown bands.")
        
        step_table = []
        cum_allocated_pct = 0.0
        
        for idx in range(1, max_t + 1):
            trigger_dd = -(thr_trigger + (idx - 1) * step_trigger)
            
            if rule_mode == 'Dynamic Valuation Scaling' and exec_z_score < 0:
                mult = 1.0 + min(abs(exec_z_score), 1.5)
            else:
                mult = 1.0
                
            b_frac = 1.0 / max_t
            t_pct = min(b_frac * mult, 1.0 - cum_allocated_pct) if idx == max_t else min(b_frac * mult, 1.0)
            
            # Bound cumulative calculations
            if cum_allocated_pct + t_pct > 1.0:
                t_pct = 1.0 - cum_allocated_pct
            
            t_amt_sgd = total_dry_powder * t_pct
            t_amt_base = t_amt_sgd / fx_rate
            
            status = "🔴 ACTIVE TRIGGERED" if dd <= trigger_dd else "⚪ AWAITING CYCLE"
            cum_allocated_pct += t_pct
            
            step_table.append({
                "Tranche Element": f"Tranche Level {idx}",
                "Drawdown Trigger Point": f"{trigger_dd:.1f}%",
                "Allocation Factor": f"{t_pct:.1%}",
                "Tranche Deployment Amount": fmt_sgd(t_amt_sgd),
                "Asset Base Amount": f"{base_ccy} {t_amt_base:,.0f}",
                "Live Pipeline Status": status
            })
            
        st.dataframe(pd.DataFrame(step_table), use_container_width=True, hide_index=True)
        
        st.markdown("##### ⚙️ Live Macro Economic Risk Interface")
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.session_state.latest_pmi_value = st.number_input(f"Modify Active Input: {chosen}", min_value=30.0, max_value=70.0, value=pmi_val, step=0.1)
        with m_col2:
            st.session_state.latest_pmi_month = st.text_input("Modify Context Reporting Period", value=pmi_m)
        st.caption(f"Adjustments recalculate real-time platform metrics. System Core Level Indicator: {live_score:.1f}/100 → Stance: {alert_level}")

def render_assumptions():
    with st.expander('📋 Platform Strategy Core Assumptions', expanded=False):
        st.markdown(f"""
        * **Target Core Instrument Tracking Ticker**: {ticker} | **Denomination**: {base_ccy}
        * **Drawdown Trigger Minimum Limit**: -{thr_trigger:.1f}% | **Progression Sizing Steps**: -{step_trigger:.1f}% per level
        * **Maximum Tranche Slices Allowed**: {max_t} Deep Structural Segments
        * **Live Composite FX Calibration Matrix Value**: {fx_rate:.4f} Base Asset Currency to {SGD_TEXT} Conversion
        """)

def render_market(expanded=False):
    with st.expander('🌦️ Live Market Channel Validation Profiles', expanded=expanded):
        st.markdown("#### Out-of-Sample Expanded Window Valuation Channels")
        st.caption("Statistical parameters calculated on dynamic mathematical window boundaries against structural history.")
        
        # Plotly chart processing pipelines
        fig = go.Figure()
        sub_df = ud.suffix('').tail(750) # View window limitation
        t_idx = sub_df.index
        
        fig.add_trace(go.Scatter(x=sub_df['Date'], y=sub_df['Close'], name='Live Index Level', line=dict(color=TEXT, width=2.5)))
        
        # Reconstruct structural band bounds
        m_vals = mu_series.loc[t_idx].values
        s_vals = sig_series.loc[t_idx].values
        
        fig.add_trace(go.Scatter(x=sub_df['Date'], y=m_vals, name='Model Regression Mean', line=dict(color=BLUE, dash='dash')))
        fig.add_trace(go.Scatter(x=sub_df['Date'], y=m_vals * np.exp(s_vals), name='+1 Standard Dev (Overvalued)', line=dict(color=RED, width=1)))
        fig.add_trace(go.Scatter(x=sub_df['Date'], y=m_vals * np.exp(-s_vals), name='-1 Standard Dev (Undervalued)', line=dict(color=GREEN, width=1)))
        fig.add_trace(go.Scatter(x=sub_df['Date'], y=m_vals * np.exp(-2*s_vals), name='-2 Standard Dev (Extreme Entry)', line=dict(color=PURPLE, width=1.5)))
        
        fig.update_layout(template='plotly_white', height=450, margin=dict(l=20, r=20, t=20, b=20), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
        st.plotly_chart(fig, use_container_width=True)

def render_performance(expanded=False):
    with st.expander('📊 System Performance Alternative Universes', expanded=expanded):
        st.markdown("### 📡 Alternate Trackers & Deployment Discrepancies")
        ref_rows = build_etf_reference_rows(sel)
        df_ref = add_performance_and_gap(ref_rows, sel)
        if not df_ref.empty:
            st.dataframe(df_ref[['Source', 'Role', 'Instrument', 'Ticker', 'Price', '1Y %', '1Y Gap', 'Coverage']], use_container_width=True, hide_index=True)
        else:
            st.info("No baseline tracker validation matrix rows compiled for this segment.")

def render_crash(expanded=False):
    with st.expander('🏆 Historical Secular Crash Event Diagnostics', expanded=expanded):
        st.markdown("#### Historical Crisis Performance Matrix")
        st.caption("Deep analytics identifying structural drawdown cycles exceeding the selected threshold.")
        valuation_tc, _, _ = build_trend_channel(ud, 2040, model=model_type)
        df_crash = crash_events(ud, thr=thr_trigger, current=close, valuation_tc=valuation_tc)
        if not df_crash.empty:
            st.dataframe(df_crash[['Historical Label', 'Peak Date', 'Drawdown %', 'Trough Date', 'Severity', 'Duration Days', 'Valuation Classification']], use_container_width=True, hide_index=True)
        else:
            st.info("No historical cycles matched the specified minimum drawdown trigger limit.")

def render_audit(expanded=False):
    with st.expander('📡 Platform Verification Audit Trail Logs', expanded=expanded):
        snap = pd.DataFrame([{
            'Timestamp SGT': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Portfolio Segment': asset_group,
            'Asset Key': sel,
            'Ticker Symbol': ticker,
            'Spot Close': close,
            'Structural Peak': peak,
            'Current Drawdown': f"{dd:.2f}%",
            'Target Action Zone': zone,
            'Capital Factor Allocation': f"{deploy_pct:.0%}",
            'Calculated Amount': f"${deploy:,.2f}",
            'Macro Variable Input': pmi_val,
            'Risk Indicator Alert': f"{live_score:.1f}/100",
            'Economic Categorization': alert_level,
            'Analysis Infrastructure': 'Macro Multi-Factor Overlay Model' if sel in PMI_NA_MARKETS else 'Equity macro',
            'Valuation Model': 'OOS Expanding Valuation Channel (Live Quant Model)',
            'Valuation Z-Score': exec_z_score,
            'Bias Status': 'No look-ahead bias for OOS valuation model',
            'Signal Confidence': conf_label
        }])
        st.markdown('#### 📤 Tactical Snapshot Export')
        st.dataframe(snap, use_container_width=True, hide_index=True)
        st.download_button('⬇️ Export Tactical Snapshot CSV', snap.to_csv(index=False), file_name='tactical_snapshot_phase2.csv', mime='text/csv')

RENDERERS = {
    '💰 Suggested Deploy': render_suggested,
    '🌦️ Market Conditions': render_market,
    '📊 Market Performance': render_performance,
    '🏆 Crash Analytics': render_crash,
    '📡 Audit Trail & Export': render_audit
}

SECTION_ORDER = ['💰 Suggested Deploy', '🌦️ Market Conditions', '📊 Market Performance', '🏆 Crash Analytics', '📡 Audit Trail & Export']

def run_render_loop():
    render_executive()
    for section in SECTION_ORDER:
        if section == '💰 Suggested Deploy':
            if active_section == section:
                RENDERERS[section](expanded=True)
            else:
                RENDERERS[section](expanded=deploy > 0 if active_section == '🧠 Executive Centre' else False)
            render_assumptions()
        elif active_section == section:
            RENDERERS[section](expanded=True)
        else:
            RENDERERS[section](expanded=False)
    st.markdown('---')
    st.caption(f'🕒 Last refreshed: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} SGT')
    st.caption('⚠️ Disclaimer: Educational only. Not financial advice. Past performance does not guarantee future results. Consult a licensed adviser.')

# ----------------------------------------------------------------
# 🏁 APPLICATION PIPELINE START POINT
# ----------------------------------------------------------------
run_render_loop()
