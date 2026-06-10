import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time
import math

st.set_page_config(page_title='SG Tactical Capital Allocator', layout='wide', initial_sidebar_state='expanded')
st.title('\U0001f1f8\U0001f1ec Tactical Wealth Allocation & Future Drawdown Simulator')
st.caption('A dynamic live-updating platform evaluating S&P 500, Nasdaq, STI, and HSI under cascading Singapore structural asset pool parameters.')

st.sidebar.markdown('## \U0001f4b0 Your Available Capital Pools')
cash_balance = st.sidebar.number_input('Liquid Cash Savings Pool ($)', min_value=0.0, value=100000.0, step=5000.0)
srs_balance = st.sidebar.number_input('Supplementary Retirement Scheme (SRS) ($)', min_value=0.0, value=35000.0, step=5000.0)
cpf_oa_balance = st.sidebar.number_input('CPF Ordinary Account (OA) ($)', min_value=0.0, value=180000.0, step=5000.0)
st.sidebar.markdown('---')
st.sidebar.markdown('## \u2699\ufe0f Core Risk Safeguards')
emergency_buffer = st.sidebar.number_input('Emergency Liquid Cash Buffer ($)', min_value=0.0, value=20000.0, step=1000.0)
preserve_cpf_bonus = st.sidebar.checkbox('Preserve S$20k CPF-OA Core Floor', value=True, help='Protects the initial structural floor space to secure the extra 1% bonus yield tier.')

INDEX_TICKERS = {'S&P 500 (US Market Core)': '^GSPC', 'Nasdaq 100 (Tech Growth)': '^IXIC', 'Straits Times Index (SG Value/REITs)': '^STI', 'Hang Seng Index (HK Cyclical/Beta)': '^HSI'}

ETF_UNIVERSE = {
    'Straits Times Index (SG Value/REITs)': {'market_label': '\U0001f1f8\U0001f1ec Singapore', 'etfs': [('SPDR STI ETF', 'ES3.SI'), ('Nikko AM STI ETF', 'G3B.SI')]},
    'Hang Seng Index (HK Cyclical/Beta)': {'market_label': '\U0001f1ed\U0001f1f0 Hong Kong', 'etfs': [('Tracker Fund (TraHK)', '2800.HK'), ('iShares HSI ETF', '3115.HK'), ('iShares HS TECH ETF', '3067.HK')]},
    'Nasdaq 100 (Tech Growth)': {'market_label': '\U0001f1fa\U0001f1f8 Nasdaq', 'etfs': [('Invesco QQQ Trust', 'QQQ'), ('Invesco NASDAQ 100 (QQQM)', 'QQQM')]},
    'S&P 500 (US Market Core)': {'market_label': '\U0001f1fa\U0001f1f8 S&P 500', 'etfs': [('SPDR S&P 500 (SPY)', 'SPY'), ('Vanguard S&P 500 (VOO)', 'VOO'), ('iShares Core S&P 500 (IVV)', 'IVV')]},
}

BENCHMARK_TICKERS = {
    'Global Indices': [('Straits Times Index', '^STI'), ('Nasdaq Composite', '^IXIC'), ('S&P 500', '^GSPC'), ('Dow Jones Industrial', '^DJI'), ('Nikkei 225', '^N225'), ('SSE A Share Index', '000002.SS'), ('TWSE Weighted Index', '^TWII')],
    'Commodities & Crypto': [('Crude Oil (WTI)', 'CL=F'), ('Gold', 'GC=F'), ('Silver', 'SI=F'), ('Bitcoin', 'BTC-USD')],
}

st.sidebar.markdown('---')
st.sidebar.markdown('## \U0001f504 Data Synchronization')
refresh_data_trigger = st.sidebar.button('\U0001f504 Force Refresh Market Data')
if refresh_data_trigger:
    st.cache_data.clear()
    st.toast('Cache cleared!', icon='\U0001f504')

@st.cache_data(ttl=14400)
def harvest_market_historical_metrics():
    computed_metrics = {}
    for standard_name, target_ticker in INDEX_TICKERS.items():
        try:
            df = yf.Ticker(target_ticker).history(start='1997-01-01')
            time.sleep(1.5)
            if not df.empty:
                df = df.dropna(subset=['Close'])
                if df.empty: continue
                cs = float(df['Close'].iloc[-1])
                ma = float(df['Close'].rolling(200).mean().dropna().iloc[-1]) if len(df) >= 200 else cs
                atp = float(df['Close'].max())
                dd = ((cs - atp) / atp) * 100
                if math.isnan(cs) or math.isnan(atp): continue
                computed_metrics[standard_name] = {'live_close': cs, 'ma_200': ma, 'ath_peak': atp, 'drawdown': dd, 'underlying_df': df}
        except Exception as e:
            st.error(f'Error fetching {standard_name}: {e}')
    return computed_metrics

@st.cache_data(ttl=14400)
def fetch_macro_indicators():
    macro = {'vix': None, 'yield_10y': None, 'yield_3m': None, 'yield_spread': None, 'vix_hist': None, 'tnx_hist': None, 'irx_hist': None}
    try:
        vh = yf.Ticker('^VIX').history(period='1y')
        time.sleep(1.5)
        if not vh.empty: macro['vix'] = float(vh['Close'].dropna().iloc[-1]); macro['vix_hist'] = vh
    except: pass
    try:
        th = yf.Ticker('^TNX').history(period='1y')
        time.sleep(1.5)
        if not th.empty: macro['yield_10y'] = float(th['Close'].dropna().iloc[-1]); macro['tnx_hist'] = th
    except: pass
    try:
        ih = yf.Ticker('^IRX').history(period='1y')
        time.sleep(1.5)
        if not ih.empty: macro['yield_3m'] = float(ih['Close'].dropna().iloc[-1]); macro['irx_hist'] = ih
    except: pass
    if macro['yield_10y'] is not None and macro['yield_3m'] is not None:
        macro['yield_spread'] = macro['yield_10y'] - macro['yield_3m']
    return macro

@st.cache_data(ttl=14400)
def fetch_etf_performance():
    results = {}
    for index_name, group in ETF_UNIVERSE.items():
        group_results = []
        for etf_name, ticker in group['etfs']:
            rec = {'name': etf_name, 'ticker': ticker, '1y': None, '3y': None, '5y': None, 'price': None}
            try:
                hist = yf.Ticker(ticker).history(period='6y')
                time.sleep(0.8)
                if not hist.empty:
                    hist = hist.dropna(subset=['Close'])
                    cp = float(hist['Close'].iloc[-1]); rec['price'] = cp; td = len(hist)
                    if td >= 252: rec['1y'] = ((cp / float(hist['Close'].iloc[-252])) - 1) * 100
                    if td >= 756: rec['3y'] = ((cp / float(hist['Close'].iloc[-756])) - 1) * 100
                    if td >= 1260: rec['5y'] = ((cp / float(hist['Close'].iloc[-1260])) - 1) * 100
            except: pass
            group_results.append(rec)
        results[index_name] = group_results
    return results

@st.cache_data(ttl=14400)
def fetch_benchmark_performance():
    results = {}
    for group_name, tickers in BENCHMARK_TICKERS.items():
        group_results = []
        for name, ticker in tickers:
            rec = {'name': name, 'ticker': ticker, '1y': None, '3y': None, '5y': None, 'price': None}
            try:
                hist = yf.Ticker(ticker).history(period='6y')
                time.sleep(0.8)
                if not hist.empty:
                    hist = hist.dropna(subset=['Close'])
                    cp = float(hist['Close'].iloc[-1]); rec['price'] = cp; td = len(hist)
                    if td >= 252: rec['1y'] = ((cp / float(hist['Close'].iloc[-252])) - 1) * 100
                    if td >= 756: rec['3y'] = ((cp / float(hist['Close'].iloc[-756])) - 1) * 100
                    if td >= 1260: rec['5y'] = ((cp / float(hist['Close'].iloc[-1260])) - 1) * 100
            except: pass
            group_results.append(rec)
        results[group_name] = group_results
    return results

with st.spinner('Harvesting live historical index data...'):
    market_state_database = harvest_market_historical_metrics()
with st.spinner('Fetching macro indicators (VIX, Yield Curve)...'):
    live_macro = fetch_macro_indicators()

if not market_state_database:
    st.error('\U0001f6a8 **No market data loaded.** Yahoo Finance may be rate-limiting. Wait 1-2 minutes and click Force Refresh.')
    st.stop()

st.markdown('### \U0001f52e Market Conditions & Scenario Modeler')
st.info('Live market data loaded by default. Adjust sliders to run scenario analysis.')

available_indices = list(market_state_database.keys())
selected_index_profile = st.selectbox('Select Target Index Spectrum', available_indices)
if selected_index_profile not in market_state_database:
    st.error('Data not available for selected index.'); st.stop()

selected_index_package = market_state_database[selected_index_profile]
live_anchor_close = selected_index_package['live_close']
historical_ath_anchor = selected_index_package['ath_peak']
underlying_data = selected_index_package['underlying_df']
underlying_data.index = underlying_data.index.tz_localize(None)

# Safety guard: ensure numeric values are valid
def safe_float(val, fallback=1000.0):
    try:
        v = float(val)
        if math.isnan(v) or math.isinf(v): return fallback
        return v
    except: return fallback

live_anchor_close = safe_float(live_anchor_close, 1000.0)
historical_ath_anchor = safe_float(historical_ath_anchor, live_anchor_close * 1.5)

ath_value = float(underlying_data['Close'].max())
ath_date = underlying_data['Close'].idxmax()
try: ath_date_str = ath_date.strftime('%Y-%m-%d')
except: ath_date_str = 'N/A'

slider_min = max(1, int(live_anchor_close * 0.35))
slider_max = max(slider_min + 100, int(historical_ath_anchor * 1.25))

row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    min_date = underlying_data.index.min().to_pydatetime().date()
    max_date = underlying_data.index.max().to_pydatetime().date()
    use_historical = st.checkbox('Use Historical Date Price', value=False)
    if use_historical:
        target_date = st.date_input('Pick Historical Date', value=max_date, min_value=min_date, max_value=max_date)
        cidx = underlying_data.index.get_indexer([pd.Timestamp(target_date)], method='nearest')[0]
        picked_price = float(underlying_data.iloc[cidx]['Close'])
        st.caption(f'Price on {target_date}: **{picked_price:,.2f}**')
        dup = underlying_data.loc[:pd.Timestamp(target_date)]
        ls = max(0, len(dup) - 252)
        rw = dup.iloc[ls:]
        trailing_peak = float(rw['Close'].max()); peak_date = rw['Close'].idxmax()
    else: picked_price = None

with row1_col2:
    if use_historical:
        sv = min(max(int(picked_price), slider_min), slider_max)
        index_price_input = st.slider('Market Index Price Level', slider_min, slider_max, sv, disabled=True)
    else:
        sv = min(max(int(live_anchor_close), slider_min), slider_max)
        index_price_input = st.slider('Market Index Price Level', slider_min, slider_max, sv, help='Slide left to simulate drawdowns.')
    st.caption(f'\U0001f4e1 Live close: **{live_anchor_close:,.2f}**')

if not use_historical:
    ls = max(0, len(underlying_data) - 252)
    rw = underlying_data.iloc[ls:]
    trailing_peak = float(rw['Close'].max()); peak_date = rw['Close'].idxmax()

try: peak_date_str = peak_date.strftime('%Y-%m-%d')
except: peak_date_str = 'N/A'

try:
    cd52 = underlying_data.iloc[max(0, len(underlying_data) - 252):]
    ma200s = underlying_data['Close'].rolling(200).mean().iloc[max(0, len(underlying_data) - 252):]
    fig_idx = go.Figure()
    fig_idx.add_trace(go.Scatter(x=cd52.index, y=cd52['Close'], mode='lines', name='Close', line=dict(color='#1565C0', width=1.5)))
    fig_idx.add_trace(go.Scatter(x=ma200s.index, y=ma200s.values, mode='lines', name='200MA', line=dict(color='#4CAF50', width=1, dash='dot')))
    fig_idx.add_hline(y=trailing_peak, line_dash='dash', line_color='#D32F2F', line_width=1, annotation_text='52W High: ' + f'{trailing_peak:,.0f}', annotation_position='top left', annotation_font_size=10, annotation_font_color='#D32F2F')
    fig_idx.update_layout(title=dict(text='52-Week Price Chart \u2014 ' + selected_index_profile, font=dict(size=13)), height=220, margin=dict(l=10, r=10, t=35, b=10), showlegend=True, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=10)), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#F0F0F0'), plot_bgcolor='white', paper_bgcolor='white')
    st.plotly_chart(fig_idx, use_container_width=True, config={'displayModeBar': False})
except: st.caption('\u26a0\ufe0f Index chart unavailable')

st.markdown('')
row2_col1, row2_col2, row2_col3 = st.columns(3)
live_vix = live_macro.get('vix')
live_yield_spread = live_macro.get('yield_spread')
vix_default = round(live_vix, 1) if live_vix is not None else 20.0
yield_spread_default = round(live_yield_spread, 2) if live_yield_spread is not None else 0.45

with row2_col1:
    pmi_input = st.slider('US ISM Manufacturing PMI', 40.0, 60.0, 51.5, help='Below 50 = contraction.')
    st.caption('\U0001f4dd Manual input \u2014 [Check latest at ISM](https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/)')
with row2_col2:
    yield_spread_input = st.slider('US Treasury Yield Spread (10Y\u22123M)', -1.50, 2.50, yield_spread_default, help='Below 0 = inverted curve.')
    if live_yield_spread is not None:
        y10 = live_macro.get('yield_10y', 0)
        y3m = live_macro.get('yield_3m', 0)
        st.caption(f'\U0001f4e1 Live spread: **{live_yield_spread:.2f}%** (10Y: {y10:.2f}% \u2212 3M: {y3m:.2f}%)')
    else: st.caption('\u26a0\ufe0f Live yield data unavailable')
with row2_col3:
    vix_input = st.slider('CBOE VIX Volatility Index', 10.0, 80.0, vix_default, help='Above 30 = elevated fear.')
    if live_vix is not None: st.caption(f'\U0001f4e1 Live VIX: **{live_vix:.2f}**')
    else: st.caption('\u26a0\ufe0f Live VIX unavailable')

chart_col1, chart_col2, chart_col3 = st.columns(3)
with chart_col1:
    pmi_note = '<div style="background:#F5F5F5; border:1px solid #DDD; border-radius:8px; padding:16px; text-align:center; height:200px; display:flex; flex-direction:column; justify-content:center;">'
    pmi_note += '<div style="font-size:13px; font-weight:600; color:#555;">\U0001f4ca PMI Historical Chart</div>'
    pmi_note += '<div style="font-size:12px; color:#888; margin-top:8px;">No free API. Update manually from <a href="https://www.ismworld.org" target="_blank" style="color:#1565C0;">ISM Reports</a></div></div>'
    st.markdown(pmi_note, unsafe_allow_html=True)

with chart_col2:
    try:
        tnx_h = live_macro.get('tnx_hist')
        irx_h = live_macro.get('irx_hist')
        if tnx_h is not None and irx_h is not None:
            td_ = tnx_h[['Close']].rename(columns={'Close':'TNX'}); td_.index = td_.index.tz_localize(None)
            id_ = irx_h[['Close']].rename(columns={'Close':'IRX'}); id_.index = id_.index.tz_localize(None)
            sd = td_.join(id_, how='inner'); sd['Spread'] = sd['TNX'] - sd['IRX']
            fy = go.Figure()
            fy.add_trace(go.Scatter(x=sd.index, y=sd['TNX'], mode='lines', name='10Y Yield', line=dict(color='#1565C0', width=1.5)))
            fy.add_trace(go.Scatter(x=sd.index, y=sd['IRX'], mode='lines', name='3M Yield', line=dict(color='#E65100', width=1.5)))
            fy.add_trace(go.Scatter(x=sd.index, y=sd['Spread'], mode='lines', name='Spread', line=dict(color='#7B1FA2', width=1.5, dash='dot')))
            fy.add_hline(y=0, line_dash='dash', line_color='#D32F2F', line_width=1, annotation_text='Inversion', annotation_position='bottom left', annotation_font_size=9, annotation_font_color='#D32F2F')
            fy.update_layout(title=dict(text='US Treasury Yields \u2014 10Y vs 3M (1Y)', font=dict(size=12)), height=200, margin=dict(l=10, r=10, t=30, b=10), showlegend=True, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=9)), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#F0F0F0', ticksuffix='%'), plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(fy, use_container_width=True, config={'displayModeBar': False})
            st.caption('Using 3M as short-end proxy (standard Fed indicator). 2Y unavailable via free API.')
        else: st.caption('\u26a0\ufe0f Yield chart unavailable')
    except: st.caption('\u26a0\ufe0f Yield chart unavailable')

with chart_col3:
    try:
        vhist = live_macro.get('vix_hist')
        if vhist is not None:
            vc = vhist.copy(); vc.index = vc.index.tz_localize(None)
            fv = go.Figure()
            fv.add_trace(go.Scatter(x=vc.index, y=vc['Close'], mode='lines', name='VIX', line=dict(color='#7B1FA2', width=1.5)))
            fv.add_hline(y=30, line_dash='dash', line_color='#D32F2F', line_width=1, annotation_text='Fear Zone (30)', annotation_position='top left', annotation_font_size=9, annotation_font_color='#D32F2F')
            fv.update_layout(title=dict(text='CBOE VIX \u2014 1 Year', font=dict(size=12)), height=200, margin=dict(l=10, r=10, t=30, b=10), showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#F0F0F0'), plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(fv, use_container_width=True, config={'displayModeBar': False})
        else: st.caption('\u26a0\ufe0f VIX chart unavailable')
    except: st.caption('\u26a0\ufe0f VIX chart unavailable')

evaluation_price = picked_price if use_historical else index_price_input
trailing_peak = safe_float(trailing_peak, evaluation_price)
effective_scenario_drawdown = ((evaluation_price - trailing_peak) / trailing_peak) * 100 if trailing_peak > 0 else 0.0
baseline_200_ma = safe_float(selected_index_package['ma_200'], evaluation_price)

pmi_triggered = pmi_input < 50.0
yield_triggered = yield_spread_input < 0.0
ma_triggered = evaluation_price < baseline_200_ma
vix_triggered = vix_input > 30.0
systemic_risk_score = sum([pmi_triggered, yield_triggered, ma_triggered, vix_triggered])

if effective_scenario_drawdown <= -35.0:
    active_allocation_zone = 'STRONG BUY'; zone_presentation_title = 'STRONG BUY ZONE'; zone_subtitle = 'Generational Allocation Opportunity &mdash; Deploy Maximum Capital'; zone_emoji = '\U0001f6a8'; zone_color = '#D32F2F'; zone_text_color = '#FFFFFF'; use_pulse = True
elif effective_scenario_drawdown <= -20.0:
    active_allocation_zone = 'BUY'; zone_presentation_title = 'BUY ZONE'; zone_subtitle = 'Structural Bear Market &mdash; Scale Into Positions'; zone_emoji = '\U0001f7e2'; zone_color = '#E65100'; zone_text_color = '#FFFFFF'; use_pulse = False
elif effective_scenario_drawdown <= -10.0:
    active_allocation_zone = 'INITIAL BUY'; zone_presentation_title = 'INITIAL BUY ZONE'; zone_subtitle = 'Healthy Correction &mdash; Nibble &amp; Build Positions'; zone_emoji = '\U0001f7e1'; zone_color = '#F9A825'; zone_text_color = '#1A1A1A'; use_pulse = False
elif evaluation_price > (1.20 * baseline_200_ma) and systemic_risk_score >= 3:
    active_allocation_zone = 'STRONG SELL'; zone_presentation_title = 'STRONG SELL ZONE'; zone_subtitle = 'Systemic Bubble &mdash; Maximize Liquidity'; zone_emoji = '\U0001f534'; zone_color = '#B71C1C'; zone_text_color = '#FFFFFF'; use_pulse = True
else:
    active_allocation_zone = 'HOLD'; zone_presentation_title = 'HOLD / DCA ZONE'; zone_subtitle = 'Normal Boundaries &mdash; Maintain Dollar-Cost Averaging'; zone_emoji = '\u26aa'; zone_color = '#2E7D32'; zone_text_color = '#FFFFFF'; use_pulse = False

st.markdown('---')
if effective_scenario_drawdown <= -35.0: dd_bg='#FFCDD2'; dd_border='#D32F2F'; dd_icon='\U0001f6a8'; dd_tc='#B71C1C'; dd_label='ALERT: Generational drawdown!'
elif effective_scenario_drawdown <= -20.0: dd_bg='#FFE0B2'; dd_border='#E65100'; dd_icon='\u26a0\ufe0f'; dd_tc='#E65100'; dd_label='ALERT: Deep drawdown!'
elif effective_scenario_drawdown <= -10.0: dd_bg='#FFF9C4'; dd_border='#F9A825'; dd_icon='\u26a0\ufe0f'; dd_tc='#F57F17'; dd_label='Correction zone'
else: dd_bg='#E8F5E9'; dd_border='#2E7D32'; dd_icon='\u2705'; dd_tc='#2E7D32'; dd_label='Within normal range'

if systemic_risk_score >= 3: rs_bg='#FFCDD2'; rs_border='#D32F2F'; rs_icon='\U0001f6a8'; rs_tc='#B71C1C'; rs_label='CRITICAL: Multiple triggers!'
elif systemic_risk_score >= 1: rs_bg='#FFE0B2'; rs_border='#E65100'; rs_icon='\u26a0\ufe0f'; rs_tc='#E65100'; rs_label='Elevated: ' + str(systemic_risk_score) + ' factor(s)'
else: rs_bg='#E8F5E9'; rs_border='#2E7D32'; rs_icon='\u2705'; rs_tc='#2E7D32'; rs_label='All clear &mdash; no triggers'

pmi_si = '\U0001f6a8' if pmi_triggered else '\u2705'; pmi_sc = '#D32F2F' if pmi_triggered else '#2E7D32'; pmi_st = 'CONTRACTION' if pmi_triggered else 'Expansionary'
yield_si = '\U0001f6a8' if yield_triggered else '\u2705'; yield_sc = '#D32F2F' if yield_triggered else '#2E7D32'; yield_st = 'INVERTED' if yield_triggered else 'Normal'
ma_si = '\U0001f6a8' if ma_triggered else '\u2705'; ma_sc = '#D32F2F' if ma_triggered else '#2E7D32'; ma_st = 'BELOW 200MA' if ma_triggered else 'Above 200MA'
vix_si = '\U0001f6a8' if vix_triggered else '\u2705'; vix_sc = '#D32F2F' if vix_triggered else '#2E7D32'; vix_st = 'ELEVATED FEAR' if vix_triggered else 'Normal'

mc1, mc2, mc3 = st.columns(3)
with mc1:
    h = '<div style="background:' + dd_bg + '; border-left:6px solid ' + dd_border + '; border-radius:10px; padding:20px; text-align:center;">'
    h += '<div style="font-size:14px; color:#555; font-weight:600;">EFFECTIVE DRAWDOWN FROM PEAK</div>'
    h += '<div style="font-size:42px; font-weight:800; color:' + dd_tc + '; margin:8px 0;">' + dd_icon + ' ' + f'{effective_scenario_drawdown:.2f}%' + '</div>'
    h += '<div style="font-size:12px; color:#777;">' + dd_label + '</div>'
    h += '<div style="font-size:11px; color:#999; margin-top:6px;">vs 52-week trailing high</div></div>'
    st.markdown(h, unsafe_allow_html=True)

with mc2:
    h = '<div style="background:' + rs_bg + '; border-left:6px solid ' + rs_border + '; border-radius:10px; padding:20px; text-align:center;">'
    h += '<div style="font-size:14px; color:#555; font-weight:600;">CALCULATED MACRO RISK SCORE</div>'
    h += '<div style="font-size:42px; font-weight:800; color:' + rs_tc + '; margin:8px 0;">' + rs_icon + ' ' + str(systemic_risk_score) + ' / 4</div>'
    h += '<div style="font-size:12px; color:#777; margin-bottom:12px;">' + rs_label + '</div>'
    h += '<div style="text-align:left; padding:10px 14px; background:rgba(255,255,255,0.7); border-radius:8px;">'
    h += '<div style="font-size:11px; font-weight:700; color:#333; margin-bottom:8px; text-transform:uppercase;">Risk Breakdown:</div>'
    h += '<div style="font-size:12px; color:' + pmi_sc + '; margin:4px 0;">' + pmi_si + ' <b>ISM PMI:</b> ' + f'{pmi_input:.1f}' + ' &mdash; ' + pmi_st + ' <span style="color:#999">(trigger &lt; 50)</span></div>'
    h += '<div style="font-size:12px; color:' + yield_sc + '; margin:4px 0;">' + yield_si + ' <b>Yield Spread:</b> ' + f'{yield_spread_input:.2f}' + ' &mdash; ' + yield_st + ' <span style="color:#999">(trigger &lt; 0)</span></div>'
    h += '<div style="font-size:12px; color:' + ma_sc + '; margin:4px 0;">' + ma_si + ' <b>Price vs 200MA:</b> ' + f'{evaluation_price:,.0f}' + ' vs ' + f'{baseline_200_ma:,.0f}' + ' &mdash; ' + ma_st + '</div>'
    h += '<div style="font-size:12px; color:' + vix_sc + '; margin:4px 0;">' + vix_si + ' <b>VIX:</b> ' + f'{vix_input:.1f}' + ' &mdash; ' + vix_st + ' <span style="color:#999">(trigger &gt; 30)</span></div>'
    h += '</div></div>'
    st.markdown(h, unsafe_allow_html=True)

with mc3:
    h = '<div style="background:#E3F2FD; border-left:6px solid #1565C0; border-radius:10px; padding:20px; text-align:center;">'
    h += '<div style="font-size:14px; color:#555; font-weight:600;">52-WEEK TRAILING HIGH</div>'
    h += '<div style="font-size:42px; font-weight:800; color:#1565C0; margin:8px 0;">\U0001f4ca ' + f'{trailing_peak:,.2f}' + '</div>'
    h += '<div style="font-size:12px; color:#777;">Peak on ' + peak_date_str + '</div>'
    h += '<div style="font-size:11px; color:#aaa; margin-top:8px; padding-top:8px; border-top:1px solid #D0D0D0;">ATH: ' + f'{ath_value:,.2f}' + ' (' + ath_date_str + ')</div></div>'
    st.markdown(h, unsafe_allow_html=True)

st.markdown('<br>', unsafe_allow_html=True)

if use_pulse:
    pulse_css = '<style>@keyframes zp{0%{box-shadow:0 0 0 0 rgba(211,47,47,.6)}50%{box-shadow:0 0 25px 10px rgba(211,47,47,.3)}100%{box-shadow:0 0 0 0 rgba(211,47,47,.6)}}.zb{animation:zp 2s infinite}</style>'
else: pulse_css = '<style>.zb{}</style>'
bh = pulse_css + '<div class="zb" style="background:linear-gradient(135deg,' + zone_color + ',' + zone_color + 'DD);border-radius:16px;padding:30px 40px;text-align:center;border:2px solid ' + zone_color + '">'
bh += '<div style="font-size:50px;margin-bottom:5px">' + zone_emoji + '</div>'
bh += '<div style="font-size:13px;color:' + zone_text_color + ';opacity:.8;letter-spacing:3px;text-transform:uppercase;font-weight:600">Target Evaluation Matrix Output</div>'
bh += '<div style="font-size:32px;font-weight:900;color:' + zone_text_color + ';margin:10px 0;letter-spacing:2px">' + zone_presentation_title + '</div>'
bh += '<div style="font-size:16px;color:' + zone_text_color + ';opacity:.9">' + zone_subtitle + '</div></div>'
st.markdown(bh, unsafe_allow_html=True)
st.markdown('<br>', unsafe_allow_html=True)

st.markdown('### \U0001f4cb Tactical Allocation Recommendations')

with st.expander('\U0001f4d0 Allocation Rules & Deployment Matrix \u2014 Click to view'):
    zones_data = [('STRONG BUY','\u2264 -35%','100%','100%','100%','Generational \u2014 max conviction'), ('BUY','\u2264 -20%','50%','75%','40%','Bear \u2014 scale in'), ('INITIAL BUY','\u2264 -10%','20%','30%','15%','Correction \u2014 nibble'), ('HOLD / DCA','Normal','0%','0%','0%','Maintain DCA'), ('STRONG SELL','Bubble+Risk\u22653','0%','0%','0%','Pause \u2014 take profits')]
    tbl = '| Zone | Trigger | Cash | SRS | CPF-OA | Rationale |' + chr(10) + '|:---|:---|:---:|:---:|:---:|:---|' + chr(10)
    for zn, tr, cp, sp, cpfp, rat in zones_data:
        active = (zn == 'STRONG BUY' and active_allocation_zone == 'STRONG BUY') or (zn == 'BUY' and active_allocation_zone == 'BUY') or (zn == 'INITIAL BUY' and active_allocation_zone == 'INITIAL BUY') or (zn == 'HOLD / DCA' and active_allocation_zone == 'HOLD') or (zn == 'STRONG SELL' and active_allocation_zone == 'STRONG SELL')
        if active: tbl += f'| \U0001f449 **{zn}** | **{tr}** | **{cp}** | **{sp}** | **{cpfp}** | **{rat}** |' + chr(10)
        else: tbl += f'| {zn} | {tr} | {cp} | {sp} | {cpfp} | {rat} |' + chr(10)
    st.markdown(tbl)
    st.markdown('**Drawdown:** Measured from 52-week trailing high. **Cash** deploys after emergency buffer. **CPF-OA** after S$20k floor. **Risk triggers:** PMI<50, Spread<0, Price<200MA, VIX>30.')

usable_cash = max(0.0, cash_balance - emergency_buffer)
usable_srs = srs_balance
usable_cpf = max(0.0, cpf_oa_balance - 20000.0) if preserve_cpf_bonus else cpf_oa_balance
cash_out = 0.0; srs_out = 0.0; cpf_out = 0.0
if active_allocation_zone == 'STRONG BUY': cash_out = usable_cash; srs_out = usable_srs; cpf_out = usable_cpf
elif active_allocation_zone == 'BUY': cash_out = usable_cash * 0.50; srs_out = usable_srs * 0.75; cpf_out = usable_cpf * 0.40
elif active_allocation_zone == 'INITIAL BUY': cash_out = usable_cash * 0.20; srs_out = usable_srs * 0.30; cpf_out = usable_cpf * 0.15
elif active_allocation_zone == 'STRONG SELL': st.warning('\u26a0\ufe0f Systemic Bubble. Pausing deployments.')
else: st.info('\u2139\ufe0f Normal boundaries. Maintain DCA schedules.')

r_cash = cash_balance - cash_out; r_srs = srs_balance - srs_out; r_cpf = cpf_oa_balance - cpf_out
total_deploy = cash_out + srs_out + cpf_out

dc1, dc2, dc3 = st.columns(3)
with dc1: st.markdown('#### \U0001f4b5 Liquid Cash'); st.metric('Deploy', f'S${cash_out:,.2f}'); st.caption(f'Remaining: S${r_cash:,.2f}')
with dc2: st.markdown('#### \U0001f4c8 SRS'); st.metric('Deploy', f'S${srs_out:,.2f}'); st.caption(f'Remaining: S${r_srs:,.2f}')
with dc3: st.markdown('#### \U0001f6e1\ufe0f CPF-OA'); st.metric('Deploy', f'S${cpf_out:,.2f}'); st.caption(f'Remaining: S${r_cpf:,.2f}')
st.markdown('---')
st.subheader(f'Total Capital to Deploy: :green[S${total_deploy:,.2f}]')

st.markdown('---')
st.markdown('### \U0001f4ca Market Performance & ETF Tracker')
st.caption('Live performance data for global benchmarks, commodities, and investable ETFs.')

def build_perf_table(records):
    t = '<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px"><thead><tr style="background:#F0F2F6;border-bottom:2px solid #DDD">'
    t += '<th style="text-align:left;padding:10px 12px">Name</th><th style="text-align:center;padding:10px 12px">Ticker</th><th style="text-align:center;padding:10px 12px">Price</th>'
    t += '<th style="text-align:center;padding:10px 12px">1Y Return</th><th style="text-align:center;padding:10px 12px">3Y Return</th><th style="text-align:center;padding:10px 12px">5Y Return</th>'
    t += '</tr></thead><tbody>'
    for r in records:
        ps = f"{r['price']:,.2f}" if r['price'] is not None else 'N/A'
        def fr(v):
            if v is None: return '<span style="color:#999">N/A</span>'
            c = '#2E7D32' if v >= 0 else '#D32F2F'; ar = '\u25b2' if v >= 0 else '\u25bc'
            return '<span style="color:' + c + ';font-weight:600">' + ar + ' ' + f'{v:.1f}' + '%</span>'
        t += '<tr style="background:#FFF;border-bottom:1px solid #EEE">'
        t += '<td style="padding:10px 12px">' + r['name'] + '</td>'
        t += '<td style="text-align:center;padding:10px 12px;font-family:monospace;color:#555">' + r['ticker'] + '</td>'
        t += '<td style="text-align:center;padding:10px 12px;font-weight:600">' + ps + '</td>'
        t += '<td style="text-align:center;padding:10px 12px">' + fr(r['1y']) + '</td>'
        t += '<td style="text-align:center;padding:10px 12px">' + fr(r['3y']) + '</td>'
        t += '<td style="text-align:center;padding:10px 12px">' + fr(r['5y']) + '</td></tr>'
    t += '</tbody></table>'
    return t

try:
    with st.spinner('Fetching global benchmarks & commodities...'):
        bench_data = fetch_benchmark_performance()
    if bench_data:
        for group_name, records in bench_data.items():
            icon = '\U0001f30d' if 'Indic' in group_name else '\U0001f6e2\ufe0f'
            st.markdown('<div style="font-size:18px;font-weight:700;margin-top:16px;margin-bottom:8px">' + icon + ' ' + group_name + '</div>', unsafe_allow_html=True)
            st.markdown(build_perf_table(records), unsafe_allow_html=True)
except Exception as e: st.warning(f'\u26a0\ufe0f Benchmark data unavailable: {e}')

try:
    with st.spinner('Fetching ETF performance...'):
        etf_data = fetch_etf_performance()
    if etf_data:
        st.markdown('<div style="font-size:20px;font-weight:700;margin-top:24px;margin-bottom:8px">\U0001f4c8 Investable ETFs</div>', unsafe_allow_html=True)
        display_order = []
        if selected_index_profile in ETF_UNIVERSE: display_order.append(selected_index_profile)
        for idx in ETF_UNIVERSE:
            if idx not in display_order: display_order.append(idx)
        for idx in display_order:
            if idx not in etf_data: continue
            gi = ETF_UNIVERSE[idx]; ml = gi['market_label']; recs = etf_data[idx]
            sel = (idx == selected_index_profile)
            badge = ' <span style="background:#E8F5E9;color:#2E7D32;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">\u2705 SELECTED</span>' if sel else ''
            st.markdown('<div style="font-size:18px;font-weight:700;margin-top:16px;margin-bottom:8px">' + ml + badge + '</div>', unsafe_allow_html=True)
            st.markdown(build_perf_table(recs), unsafe_allow_html=True)
except Exception as e: st.warning(f'\u26a0\ufe0f ETF data unavailable: {e}')

st.markdown('---')
st.caption('\u26a0\ufe0f Disclaimer: This tool is for educational purposes only. Not financial advice. Consult a licensed advisor.')
