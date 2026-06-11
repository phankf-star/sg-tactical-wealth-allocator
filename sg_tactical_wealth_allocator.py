
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time
import math
from datetime import datetime

st.set_page_config(
    page_title='SG Tactical Wealth Allocator',
    layout='wide',
    initial_sidebar_state='expanded'
)

st.title('🇸🇬 Tactical Wealth Allocation & Future Drawdown Simulator')
st.caption('Singapore wealth allocation platform with regime classification, opportunity scoring, and crash-recovery analytics.')

# =========================
# Sidebar Inputs
# =========================
st.sidebar.markdown('## 💰 Capital Pools')
cash_balance = st.sidebar.number_input('Liquid Cash (S$)', min_value=0.0, value=100000.0, step=5000.0)
srs_balance = st.sidebar.number_input('SRS (S$)', min_value=0.0, value=35000.0, step=5000.0)
cpy_oa_balance_default = 180000.0
cpf_oa_balance = st.sidebar.number_input('CPF-OA (S$)', min_value=0.0, value=cpy_oa_balance_default, step=5000.0)

st.sidebar.markdown('---')
st.sidebar.markdown('## ⚙️ Safeguards')
emergency_buffer = st.sidebar.number_input('Emergency Buffer (S$)', min_value=0.0, value=20000.0, step=1000.0)
preserve_cpf = st.sidebar.checkbox('Preserve S$20k CPF-OA Floor', value=True)

st.sidebar.markdown('---')
st.sidebar.markdown('## 🔄 Data Sync')
if st.sidebar.button('🔄 Force Refresh'):
    st.cache_data.clear()
    st.toast('Market data cache cleared.', icon='🔄')

INDEX_TICKERS = {
    'S&P 500 (US Market Core)': '^GSPC',
    'Nasdaq 100 (Tech Growth)': '^IXIC',
    'Straits Times Index (SG Value/REITs)': '^STI',
    'Hang Seng Index (HK Cyclical/Beta)': '^HSI'
}

ETF_UNIVERSE = {
    'Straits Times Index (SG Value/REITs)': {'label':'🇸🇬 Singapore','etfs':[('SPDR STI ETF','ES3.SI'),('Nikko AM STI ETF','G3B.SI')]},
    'Hang Seng Index (HK Cyclical/Beta)': {'label':'🇭🇰 Hong Kong','etfs':[('Tracker Fund','2800.HK'),('iShares HSI','3115.HK'),('iShares HS TECH','3067.HK')]},
    'Nasdaq 100 (Tech Growth)': {'label':'🇺🇸 Nasdaq','etfs':[('Invesco QQQ','QQQ'),('Invesco QQQM','QQQM')]},
    'S&P 500 (US Market Core)': {'label':'🇺🇸 S&P 500','etfs':[('SPDR SPY','SPY'),('Vanguard VOO','VOO'),('iShares IVV','IVV')]},
    'AI & Technology': {'label':'🤖 AI & Technology','etfs':[('iShares AI Innovation','BAI'),('Global X AI & Tech','AIQ'),('Global X Robotics & AI','BOTZ')]},
    'Semiconductors': {'label':'💡 Semiconductors','etfs':[('iShares Semiconductor','SOXX'),('VanEck Semiconductor','SMH')]},
    'China Internet': {'label':'🇨🇳 China Internet','etfs':[('KraneShares China Internet','KWEB')]},
    'Emerging Markets': {'label':'🌏 Emerging Markets','etfs':[('iShares MSCI EM','EEM')]},
    'US REITs': {'label':'🏠 US REITs','etfs':[('Vanguard Real Estate','VNQ')]},
    'Dividend': {'label':'💸 Dividend','etfs':[('Schwab US Dividend','SCHD')]},
    'Global': {'label':'🌍 Global','etfs':[('Vanguard Total World','VT')]},
    'Bonds': {'label':'📉 Bonds','etfs':[('iShares 20+ Year Treasury','TLT')]},
}

BENCHMARK_TICKERS = {
    'Global Indices': [('STI','^STI'),('Nasdaq','^IXIC'),('S&P 500','^GSPC'),('DJIA','^DJI'),('Nikkei 225','^N225'),('SSE A Share','000002.SS'),('TWSE','^TWII')],
    'Commodities & Crypto': [('Crude Oil','CL=F'),('Gold','GC=F'),('Silver','SI=F'),('Bitcoin','BTC-USD')],
}

def safe_float(v, fb=0.0):
    try:
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return fb
        return x
    except Exception:
        return fb

@st.cache_data(ttl=14400)
def download_price_history(ticker, start='1997-01-01'):
    df = yf.Ticker(ticker).history(start=start)
    time.sleep(0.2)
    if df is None or df.empty:
        return pd.DataFrame()
    return df.dropna(subset=['Close']).copy()

@st.cache_data(ttl=14400)
def harvest_market():
    market = {}
    for name, ticker in INDEX_TICKERS.items():
        try:
            df = download_price_history(ticker)
            if df.empty:
                continue
            close = safe_float(df['Close'].iloc[-1])
            ma200 = safe_float(df['Close'].rolling(200).mean().dropna().iloc[-1], close) if len(df) >= 200 else close
            ath = safe_float(df['Close'].max(), close)
            dd = ((close - ath) / ath) * 100 if ath else 0
            market[name] = {
                'ticker': ticker,
                'live_close': close,
                'ma_200': ma200,
                'ath_peak': ath,
                'drawdown': dd,
                'underlying_df': df
            }
        except Exception:
            continue
    return market

@st.cache_data(ttl=14400)
def fetch_perf_records(items):
    records = []
    for name, ticker in items:
        try:
            df = download_price_history(ticker, start='2018-01-01')
            if df.empty:
                records.append({'name':name,'ticker':ticker,'price':None,'1y':None,'3y':None,'5y':None})
                continue
            last = safe_float(df['Close'].iloc[-1])
            def ret(days):
                if len(df) <= days:
                    return None
                start_px = safe_float(df['Close'].iloc[-days])
                return ((last / start_px) - 1) * 100 if start_px else None
            records.append({'name':name,'ticker':ticker,'price':last,'1y':ret(252),'3y':ret(756),'5y':ret(1260)})
        except Exception:
            records.append({'name':name,'ticker':ticker,'price':None,'1y':None,'3y':None,'5y':None})
    return records

@st.cache_data(ttl=14400)
def fetch_bench():
    return {group: fetch_perf_records(items) for group, items in BENCHMARK_TICKERS.items()}

@st.cache_data(ttl=14400)
def fetch_etf_perf():
    return {name: fetch_perf_records(info['etfs']) for name, info in ETF_UNIVERSE.items()}

def classify_zone(drawdown_pct):
    if drawdown_pct <= -35:
        return 'STRONG BUY', '#D32F2F'
    if drawdown_pct <= -20:
        return 'BUY', '#E65100'
    if drawdown_pct <= -10:
        return 'INITIAL BUY', '#F9A825'
    if drawdown_pct >= 0:
        return 'STRONG SELL', '#6A1B9A'
    return 'HOLD', '#1976D2'

def build_drawdown_events(bt, bt_threshold, bt_amount, current_level):
    events = []
    in_dd = False
    ep_s = None
    for i in range(len(bt)):
        dv = bt['dd_pct'].iloc[i]
        if dv <= -bt_threshold and not in_dd:
            in_dd = True
            ep_s = i
        elif dv > -5 and in_dd:
            in_dd = False
            episode = bt.iloc[ep_s:i]
            if episode.empty:
                continue
            ti = episode['dd_pct'].idxmin()
            tr = bt.loc[ti]
            if len(events) == 0 or (ti - events[-1]['date']).days >= 60:
                d_ = safe_float(tr['dd_pct'])
                p_ = safe_float(tr['Close'])
                pk_ = safe_float(tr['rm'])
                lookback = bt.loc[:ti]
                lookback252 = lookback.iloc[max(0, len(lookback)-252):]
                pk_dt = lookback252['Close'].idxmax()
                zone, colour = classify_zone(d_)
                events.append({
                    'date': ti,
                    'price': p_,
                    'dd': d_,
                    'zone': zone,
                    'colour': colour,
                    'cv': bt_amount * (current_level / p_) if p_ else 0,
                    'ret': ((current_level / p_) - 1) * 100 if p_ else 0,
                    'peak': pk_,
                    'peak_dt': pk_dt
                })
    if in_dd and ep_s is not None:
        episode = bt.iloc[ep_s:]
        if not episode.empty:
            ti = episode['dd_pct'].idxmin()
            tr = bt.loc[ti]
            if len(events) == 0 or (ti - events[-1]['date']).days >= 60:
                d_ = safe_float(tr['dd_pct'])
                p_ = safe_float(tr['Close'])
                pk_ = safe_float(tr['rm'])
                lookback = bt.loc[:ti]
                lookback252 = lookback.iloc[max(0, len(lookback)-252):]
                pk_dt = lookback252['Close'].idxmax()
                zone, colour = classify_zone(d_)
                events.append({
                    'date': ti,
                    'price': p_,
                    'dd': d_,
                    'zone': zone,
                    'colour': colour,
                    'cv': bt_amount * (current_level / p_) if p_ else 0,
                    'ret': ((current_level / p_) - 1) * 100 if p_ else 0,
                    'peak': pk_,
                    'peak_dt': pk_dt
                })
    return events

# =========================
# Market Harvest
# =========================
with st.spinner('Loading market data...'):
    market = harvest_market()

if not market:
    st.error('Market data unavailable. Try Force Refresh or check data connectivity.')
    st.stop()

sel_idx = st.selectbox('Select Market Index', list(market.keys()), index=list(market.keys()).index('Hang Seng Index (HK Cyclical/Beta)') if 'Hang Seng Index (HK Cyclical/Beta)' in market else 0)
selected = market[sel_idx]
ud = selected['underlying_df'].copy()

# =========================
# Executive Tactical Allocation Centre
# =========================
st.markdown('---')
st.markdown('## 🧠 Executive Tactical Allocation Centre')
st.caption('Always-visible decision engine for deployment sizing, capital pools and current market opportunity zone.')

live_close = selected['live_close']
current_dd = selected['drawdown']
ma200 = selected['ma_200']
zone, zone_colour = classify_zone(current_dd)
trend_status = 'Above 200D MA' if live_close >= ma200 else 'Below 200D MA'

if current_dd <= -35:
    deploy_pct = 0.50
elif current_dd <= -25:
    deploy_pct = 0.35
elif current_dd <= -15:
    deploy_pct = 0.20
elif current_dd <= -8:
    deploy_pct = 0.10
else:
    deploy_pct = 0.00

available_cash = max(cash_balance - emergency_buffer, 0)
available_srs = srs_balance
cpf_floor = 20000 if preserve_cpf else 0
available_cpf = max(cpf_oa_balance - cpf_floor, 0)
total_available = available_cash + available_srs + available_cpf
deploy_amount = total_available * deploy_pct

c1,c2,c3,c4,c5 = st.columns(5)
with c1:
    st.metric('Index Level', f'{live_close:,.0f}')
with c2:
    st.metric('Current Drawdown', f'{current_dd:.1f}%')
with c3:
    st.metric('Trend', trend_status)
with c4:
    st.metric('Action Zone', zone)
with c5:
    st.metric('Suggested Deploy', f'S${deploy_amount:,.0f}')

st.markdown(f"""
<div style='padding:14px;border-left:6px solid {zone_colour};background:#FAFAFA;border-radius:10px;margin-top:8px'>
<b>Current tactical interpretation:</b> {sel_idx} is in <b>{zone}</b> territory with a drawdown of <b>{current_dd:.1f}%</b> from its available historical peak. Suggested deployment is based on drawdown severity and capital safeguards.
</div>
""", unsafe_allow_html=True)

a1,a2,a3 = st.columns(3)
with a1:
    st.markdown('#### 💵 Cash')
    st.metric('Deploy', f'S${available_cash * deploy_pct:,.0f}')
    st.caption(f'Available after buffer: S${available_cash:,.0f}')
with a2:
    st.markdown('#### 📈 SRS')
    st.metric('Deploy', f'S${available_srs * deploy_pct:,.0f}')
    st.caption(f'Available: S${available_srs:,.0f}')
with a3:
    st.markdown('#### 🛡️ CPF-OA')
    st.metric('Deploy', f'S${available_cpf * deploy_pct:,.0f}')
    st.caption(f'Available after floor: S${available_cpf:,.0f}')

# =========================
# Market Conditions & Scenario Modeler
# =========================
with st.expander('🌦️ MARKET CONDITIONS & SCENARIO MODELER', expanded=False):
    st.markdown("""
    <h1 style='font-size:34px;margin-bottom:0'>🌦️ Market Conditions & Scenario Modeler</h1>
    <p style='font-size:16px;color:gray;margin-top:0'>Scenario-based risk adjustment for deployment planning.</p>
    """, unsafe_allow_html=True)

    s1,s2,s3,s4 = st.columns(4)
    with s1:
        vix_assumption = st.slider('VIX Assumption', 10, 60, 22)
    with s2:
        pmi_assumption = st.slider('PMI Assumption', 35, 60, 50)
    with s3:
        yield_assumption = st.slider('10Y Yield Assumption (%)', 1.0, 7.0, 4.0, 0.1)
    with s4:
        scenario_dd = st.slider('Scenario Drawdown (%)', 0, 60, int(abs(current_dd)))

    risk_score = 0
    risk_score += min(max((vix_assumption - 15) * 1.5, 0), 40)
    risk_score += min(max((50 - pmi_assumption) * 2, 0), 30)
    risk_score += min(max((yield_assumption - 3.5) * 8, 0), 20)
    risk_score += min(max(scenario_dd * 0.5, 0), 30)
    risk_score = min(risk_score, 100)

    suggested_scenario_deploy = max(0, min(50, 50 - risk_score * 0.35))
    m1,m2,m3 = st.columns(3)
    with m1:
        st.metric('Scenario Risk Score', f'{risk_score:.0f}/100')
    with m2:
        st.metric('Scenario Deploy Cap', f'{suggested_scenario_deploy:.0f}%')
    with m3:
        st.metric('Scenario Action', 'Preserve Cash' if risk_score >= 70 else ('Partial Deploy' if risk_score >= 40 else 'Accumulate'))

# =========================
# Market Performance & ETF Tracker
# =========================
with st.expander('📊 MARKET PERFORMANCE & ETF TRACKER', expanded=False):
    st.markdown("""
    <h1 style='font-size:34px;margin-bottom:0'>📊 Market Performance & ETF Tracker</h1>
    <p style='font-size:16px;color:gray;margin-top:0'>Global indices, ETFs, benchmarks and tactical opportunity tracking.</p>
    """, unsafe_allow_html=True)

    def bpt(recs):
        t='<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px"><thead><tr style="background:#F0F2F6;border-bottom:2px solid #DDD">'
        t+='<th style="text-align:left;padding:10px">Name</th><th style="text-align:center;padding:10px">Ticker</th><th style="text-align:center;padding:10px">Price</th>'
        t+='<th style="text-align:center;padding:10px">1Y</th><th style="text-align:center;padding:10px">3Y</th><th style="text-align:center;padding:10px">5Y</th></tr></thead><tbody>'
        for r in recs:
            ps=f"{r['price']:,.2f}" if r['price'] is not None else 'N/A'
            yf_url='https://finance.yahoo.com/quote/'+r['ticker']
            def fr(v):
                if v is None:
                    return '<span style="color:#999">N/A</span>'
                c='#2E7D32' if v>=0 else '#D32F2F'
                ar='▲' if v>=0 else '▼'
                return '<span style="color:'+c+';font-weight:600">'+ar+' '+f'{v:.1f}'+'%</span>'
            t+='<tr style="border-bottom:1px solid #EEE"><td style="padding:10px">'+r['name']+'</td><td style="text-align:center;padding:10px"><a href="'+yf_url+'" target="_blank" style="color:#1565C0;text-decoration:none;font-family:monospace">'+r['ticker']+'</a></td><td style="text-align:center;padding:10px;font-weight:600">'+ps+'</td><td style="text-align:center;padding:10px">'+fr(r['1y'])+'</td><td style="text-align:center;padding:10px">'+fr(r['3y'])+'</td><td style="text-align:center;padding:10px">'+fr(r['5y'])+'</td></tr>'
        return t+'</tbody></table>'

    try:
        with st.spinner('Fetching benchmarks...'):
            bd = fetch_bench()
        for group, recs in bd.items():
            st.markdown(f'### {group}')
            st.markdown(bpt(recs), unsafe_allow_html=True)
    except Exception as e:
        st.warning(f'Benchmarks unavailable: {e}')

    try:
        with st.spinner('Fetching ETFs...'):
            ed = fetch_etf_perf()
        display_order = []
        if sel_idx in ETF_UNIVERSE:
            display_order.append(sel_idx)
        for ix in ETF_UNIVERSE:
            if ix not in display_order:
                display_order.append(ix)
        for ix in display_order:
            if ix not in ed:
                continue
            badge = ' ✅ SELECTED' if ix == sel_idx else ''
            st.markdown(f"### {ETF_UNIVERSE[ix]['label']}{badge}")
            st.markdown(bpt(ed[ix]), unsafe_allow_html=True)
    except Exception as e:
        st.warning(f'ETFs unavailable: {e}')

# =========================
# Crash & Recovery Analytics
# =========================
with st.expander('🏆 CRASH & RECOVERY ANALYTICS', expanded=False):
    st.markdown("""
    <h1 style='font-size:34px;margin-bottom:0'>🏆 Crash & Recovery Analytics</h1>
    <p style='font-size:16px;color:gray;margin-top:0'>Historical drawdown analytics, event filtering, selected-event deployment outcome and market cycle education.</p>
    """, unsafe_allow_html=True)

    bt_c1,bt_c2,bt_c3 = st.columns(3)
    with bt_c1:
        bt_amount = st.number_input('Investment per selected crash (S$)', min_value=1000, value=10000, step=1000)
    with bt_c2:
        bt_min_date = ud.index.min().to_pydatetime().date()
        bt_max_date = ud.index.max().to_pydatetime().date()
        bt_start = st.date_input('Start backtest from', value=bt_min_date, min_value=bt_min_date, max_value=bt_max_date)
    with bt_c3:
        bt_threshold = st.slider('Min drawdown threshold (%)', min_value=5, max_value=50, value=10, step=5)

    try:
        bt = ud.loc[pd.Timestamp(bt_start):].copy()
        bt['rm'] = bt['Close'].rolling(252, min_periods=1).max()
        bt['dd_pct'] = ((bt['Close'] - bt['rm']) / bt['rm']) * 100
        lc_ = safe_float(bt['Close'].iloc[-1])

        troughs = build_drawdown_events(bt, bt_threshold, bt_amount, lc_)

        if not troughs:
            st.info('No drawdown events found with selected parameters.')
        else:
            years_span = max((bt.index.max() - bt.index.min()).days / 365.25, 1)
            dd10 = len([t for t in troughs if -20 < t['dd'] <= -10])
            dd20 = len([t for t in troughs if -30 < t['dd'] <= -20])
            dd30 = len([t for t in troughs if t['dd'] <= -30])

            st.markdown('### 📚 Full Market Cycle Statistics')
            c1,c2,c3 = st.columns(3)
            with c1:
                st.info(f"📉 10–20% corrections historically occur every ~{round(years_span/dd10,1) if dd10 else 'N/A'} years")
            with c2:
                st.warning(f"⚠️ 20–30% corrections historically occur every ~{round(years_span/dd20,1) if dd20 else 'N/A'} years")
            with c3:
                st.error(f"🔥 30%+ crashes historically occur every ~{round(years_span/dd30,1) if dd30 else 'N/A'} years")

            st.markdown('### 📊 Executive Crash Summary')
            k1,k2,k3,k4,k5 = st.columns(5)
            with k1:
                st.metric('Crash Events', len(troughs))
            with k2:
                st.metric('Success Rate', f"{sum(1 for t in troughs if t['ret'] > 0) / len(troughs) * 100:.0f}%")
            with k3:
                st.metric('Avg Recovery', f"{np.mean([t['ret'] for t in troughs]):.1f}%")
            with k4:
                st.metric('Best Recovery', f"{max([t['ret'] for t in troughs]):.1f}%")
            with k5:
                st.metric('Current Drawdown', f"{bt['dd_pct'].iloc[-1]:.1f}%")

            event_df = pd.DataFrame([
                {
                    'Peak Date': t['peak_dt'].strftime('%Y-%m-%d'),
                    'Peak Index': round(t['peak'], 0),
                    'Trough Date': t['date'].strftime('%Y-%m-%d'),
                    'Trough Index': round(t['price'], 0),
                    'Drawdown %': round(t['dd'], 1),
                    'Recovery Return %': round(t['ret'], 1),
                    'Zone': t['zone'],
                    'Value Today From Selected Deployment': round(t['cv'], 0)
                }
                for t in troughs
            ])

            def sev_bucket(v):
                if v <= -30:
                    return '30%+'
                if v <= -20:
                    return '20-30%'
                return '10-20%'

            event_df['Severity'] = event_df['Drawdown %'].apply(sev_bucket)

            st.markdown('### 🔍 Interactive Event Explorer')
            f1,f2 = st.columns(2)
            with f1:
                severity_filter = st.multiselect('Severity filters', ['10-20%','20-30%','30%+'], default=['10-20%','20-30%','30%+'])
            with f2:
                zone_filter = st.multiselect('Buy Zone filters', ['INITIAL BUY','BUY','STRONG BUY'], default=['INITIAL BUY','BUY','STRONG BUY'])

            filtered_df = event_df[event_df['Severity'].isin(severity_filter) & event_df['Zone'].isin(zone_filter)].copy()

            st.markdown('#### 🔎 Filtered Event Statistics')
            if filtered_df.empty:
                st.info('No events match the selected filters.')
            else:
                fs1,fs2,fs3,fs4 = st.columns(4)
                with fs1:
                    st.metric('Filtered Events', len(filtered_df))
                with fs2:
                    st.metric('Avg Drawdown', f"{filtered_df['Drawdown %'].mean():.1f}%")
                with fs3:
                    st.metric('Avg Recovery', f"{filtered_df['Recovery Return %'].mean():.1f}%")
                with fs4:
                    st.metric('Best Recovery', f"{filtered_df['Recovery Return %'].max():.1f}%")

                st.markdown('#### 📉 Filtered Event Table')
                st.dataframe(filtered_df, use_container_width=True, hide_index=True)

                event_options = [f"{r['Peak Date']} → {r['Trough Date']} ({r['Drawdown %']}%)" for _, r in filtered_df.iterrows()]
                selected_event = st.selectbox('Historical Crash Explorer', event_options)
                selected_row = filtered_df.iloc[event_options.index(selected_event)]

                st.markdown('#### 📊 Detailed Event Breakdown')
                d1,d2,d3,d4 = st.columns(4)
                with d1:
                    st.metric('Peak Index', f"{selected_row['Peak Index']:,.0f}")
                with d2:
                    st.metric('Trough Index', f"{selected_row['Trough Index']:,.0f}")
                with d3:
                    st.metric('Drawdown', f"{selected_row['Drawdown %']:.1f}%")
                with d4:
                    st.metric('Recovery Return', f"{selected_row['Recovery Return %']:.1f}%")

                peak_date = pd.Timestamp(selected_row['Peak Date'])
                trough_date = pd.Timestamp(selected_row['Trough Date'])
                days_to_trough = max((trough_date - peak_date).days, 0)
                if days_to_trough <= 90:
                    crash_speed = 'Fast crash'
                elif days_to_trough <= 365:
                    crash_speed = 'Medium-speed bear market'
                else:
                    crash_speed = 'Slow grinding bear market'

                st.markdown('#### 🧭 Pre-Crash Context')
                st.info(
                    f"Before this drawdown, {sel_idx} peaked at approximately {selected_row['Peak Index']:,.0f} on {selected_row['Peak Date']}. "
                    f"The index then declined to approximately {selected_row['Trough Index']:,.0f} by {selected_row['Trough Date']}, "
                    f"a drawdown of {selected_row['Drawdown %']:.1f}% over about {days_to_trough} days. "
                    f"This was classified as a {crash_speed} and entered the {selected_row['Zone']} zone based on drawdown severity."
                )

                st.markdown('#### 💰 Selected Event Deployment Outcome')
                selected_value_today = safe_float(selected_row['Value Today From Selected Deployment'])
                selected_return = safe_float(selected_row['Recovery Return %'])
                o1,o2,o3,o4 = st.columns(4)
                with o1:
                    st.metric('Deployment Amount', f'S${bt_amount:,.0f}')
                with o2:
                    st.metric('Entry Level', f"{selected_row['Trough Index']:,.0f}")
                with o3:
                    st.metric('Value Today', f'S${selected_value_today:,.0f}')
                with o4:
                    st.metric('Return Since Trough', f'{selected_return:.1f}%')

                chart_start = peak_date
                chart_end = trough_date
                chart_df = bt.loc[chart_start:chart_end].copy()
                if not chart_df.empty:
                    st.markdown('#### 📉 Mini Historical Crash Chart')
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=chart_df.index,
                        y=chart_df['Close'],
                        mode='lines',
                        line=dict(color='#D32F2F', width=3),
                        name='Peak → Trough Path'
                    ))
                    fig.add_trace(go.Scatter(
                        x=[chart_start], y=[selected_row['Peak Index']], mode='markers+text',
                        marker=dict(color='#555', size=10), text=['Peak'], textposition='top center', name='Peak'
                    ))
                    fig.add_trace(go.Scatter(
                        x=[chart_end], y=[selected_row['Trough Index']], mode='markers+text',
                        marker=dict(color='#D32F2F', size=10), text=['Trough'], textposition='bottom center', name='Trough'
                    ))
                    fig.update_layout(
                        height=340,
                        margin=dict(l=10,r=10,t=40,b=10),
                        title='Mini Historical Crash Chart: Peak → Trough',
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        xaxis_title='Date',
                        yaxis_title='Index Level',
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})

            st.info('📌 Historical insight: severe drawdowns have historically produced stronger forward return potential, but recovery timing varies materially across cycles. This section is educational and does not guarantee future outcomes.')
            st.download_button('⬇️ Export Crash Analytics CSV', event_df.to_csv(index=False), file_name='crash_recovery_analytics.csv', mime='text/csv')

    except Exception as e:
        st.warning(f'Crash analytics unavailable: {e}')

st.markdown('---')
st.caption(f'🕒 Last refreshed: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} SGT')
st.caption('⚠️ Disclaimer: Educational only. Not financial advice. Past performance does not guarantee future results. Consult a licensed advisor.')
