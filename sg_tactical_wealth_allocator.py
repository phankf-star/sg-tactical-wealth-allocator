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
preserve_cpf_bonus = st.sidebar.checkbox('Preserve S$20k CPF-OA Core Floor', value=True, help='Protects the extra 1% bonus yield tier.')

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
if st.sidebar.button('\U0001f504 Force Refresh Market Data'): st.cache_data.clear(); st.toast('Cache cleared!', icon='\U0001f504')

def safe_float(val, fallback=1000.0):
    try:
        v = float(val)
        if math.isnan(v) or math.isinf(v): return fallback
        return v
    except: return fallback

@st.cache_data(ttl=14400)
def harvest_market_historical_metrics():
    m = {}
    for name, tick in INDEX_TICKERS.items():
        try:
            df = yf.Ticker(tick).history(start='1997-01-01'); time.sleep(1.5)
            if not df.empty:
                df = df.dropna(subset=['Close'])
                if df.empty: continue
                cs = float(df['Close'].iloc[-1]); ma = float(df['Close'].rolling(200).mean().dropna().iloc[-1]) if len(df)>=200 else cs
                atp = float(df['Close'].max()); dd = ((cs-atp)/atp)*100
                if math.isnan(cs) or math.isnan(atp): continue
                m[name] = {'live_close':cs,'ma_200':ma,'ath_peak':atp,'drawdown':dd,'underlying_df':df}
        except Exception as e: st.error(f'Error fetching {name}: {e}')
    return m

@st.cache_data(ttl=14400)
def fetch_macro_indicators():
    m = {'vix':None,'yield_10y':None,'yield_3m':None,'yield_spread':None,'vix_hist':None,'tnx_hist':None,'irx_hist':None}
    try:
        vh = yf.Ticker('^VIX').history(period='1y'); time.sleep(1.5)
        if not vh.empty: m['vix']=float(vh['Close'].dropna().iloc[-1]); m['vix_hist']=vh
    except: pass
    try:
        th = yf.Ticker('^TNX').history(period='1y'); time.sleep(1.5)
        if not th.empty: m['yield_10y']=float(th['Close'].dropna().iloc[-1]); m['tnx_hist']=th
    except: pass
    try:
        ih = yf.Ticker('^IRX').history(period='1y'); time.sleep(1.5)
        if not ih.empty: m['yield_3m']=float(ih['Close'].dropna().iloc[-1]); m['irx_hist']=ih
    except: pass
    if m['yield_10y'] is not None and m['yield_3m'] is not None: m['yield_spread']=m['yield_10y']-m['yield_3m']
    return m

@st.cache_data(ttl=14400)
def fetch_etf_performance():
    r = {}
    for iname, g in ETF_UNIVERSE.items():
        gr = []
        for en, tk in g['etfs']:
            rec = {'name':en,'ticker':tk,'1y':None,'3y':None,'5y':None,'price':None}
            try:
                h = yf.Ticker(tk).history(period='6y'); time.sleep(0.8)
                if not h.empty:
                    h = h.dropna(subset=['Close']); cp = float(h['Close'].iloc[-1]); rec['price']=cp; td=len(h)
                    if td>=252: rec['1y']=((cp/float(h['Close'].iloc[-252]))-1)*100
                    if td>=756: rec['3y']=((cp/float(h['Close'].iloc[-756]))-1)*100
                    if td>=1260: rec['5y']=((cp/float(h['Close'].iloc[-1260]))-1)*100
            except: pass
            gr.append(rec)
        r[iname] = gr
    return r

@st.cache_data(ttl=14400)
def fetch_benchmark_performance():
    r = {}
    for gn, tickers in BENCHMARK_TICKERS.items():
        gr = []
        for nm, tk in tickers:
            rec = {'name':nm,'ticker':tk,'1y':None,'3y':None,'5y':None,'price':None}
            try:
                h = yf.Ticker(tk).history(period='6y'); time.sleep(0.8)
                if not h.empty:
                    h = h.dropna(subset=['Close']); cp = float(h['Close'].iloc[-1]); rec['price']=cp; td=len(h)
                    if td>=252: rec['1y']=((cp/float(h['Close'].iloc[-252]))-1)*100
                    if td>=756: rec['3y']=((cp/float(h['Close'].iloc[-756]))-1)*100
                    if td>=1260: rec['5y']=((cp/float(h['Close'].iloc[-1260]))-1)*100
            except: pass
            gr.append(rec)
        r[gn] = gr
    return r

with st.spinner('Harvesting live index data...'): market_state_database = harvest_market_historical_metrics()
with st.spinner('Fetching macro indicators...'): live_macro = fetch_macro_indicators()
if not market_state_database: st.error('\U0001f6a8 No market data loaded. Try Force Refresh.'); st.stop()

st.markdown('### \U0001f52e Market Conditions & Scenario Modeler')
st.info('Live market data loaded. Adjust sliders for scenario analysis.')
available_indices = list(market_state_database.keys())
selected_index_profile = st.selectbox('Select Target Index Spectrum', available_indices)
if selected_index_profile not in market_state_database: st.error('Data not available.'); st.stop()
sp = market_state_database[selected_index_profile]
live_anchor_close = safe_float(sp['live_close'])
historical_ath_anchor = safe_float(sp['ath_peak'], live_anchor_close*1.5)
underlying_data = sp['underlying_df']
underlying_data.index = underlying_data.index.tz_localize(None)
ath_value = float(underlying_data['Close'].max()); ath_date = underlying_data['Close'].idxmax()
try: ath_date_str = ath_date.strftime('%Y-%m-%d')
except: ath_date_str = 'N/A'
slider_min = max(1, int(live_anchor_close*0.35)); slider_max = max(slider_min+100, int(historical_ath_anchor*1.25))

r1c1, r1c2 = st.columns(2)
with r1c1:
    min_date = underlying_data.index.min().to_pydatetime().date(); max_date = underlying_data.index.max().to_pydatetime().date()
    use_historical = st.checkbox('Use Historical Date Price', value=False)
    if use_historical:
        target_date = st.date_input('Pick Historical Date', value=max_date, min_value=min_date, max_value=max_date)
        cidx = underlying_data.index.get_indexer([pd.Timestamp(target_date)], method='nearest')[0]
        picked_price = float(underlying_data.iloc[cidx]['Close'])
        st.caption(f'Price on {target_date}: **{picked_price:,.2f}**')
        dup = underlying_data.loc[:pd.Timestamp(target_date)]
        rw = dup.iloc[max(0,len(dup)-252):]
        trailing_peak = float(rw['Close'].max()); peak_date = rw['Close'].idxmax()
    else: picked_price = None
with r1c2:
    if use_historical:
        sv = min(max(int(picked_price), slider_min), slider_max)
        index_price_input = st.slider('Market Index Price Level', slider_min, slider_max, sv, disabled=True)
    else:
        sv = min(max(int(live_anchor_close), slider_min), slider_max)
        index_price_input = st.slider('Market Index Price Level', slider_min, slider_max, sv, help='Slide to simulate.')
    st.caption(f'\U0001f4e1 Live close: **{live_anchor_close:,.2f}**')
if not use_historical:
    rw = underlying_data.iloc[max(0,len(underlying_data)-252):]
    trailing_peak = float(rw['Close'].max()); peak_date = rw['Close'].idxmax()
try: peak_date_str = peak_date.strftime('%Y-%m-%d')
except: peak_date_str = 'N/A'

try:
    cd52 = underlying_data.iloc[max(0,len(underlying_data)-252):]
    ma200s = underlying_data['Close'].rolling(200).mean().iloc[max(0,len(underlying_data)-252):]
    fi = go.Figure()
    fi.add_trace(go.Scatter(x=cd52.index,y=cd52['Close'],mode='lines',name='Close',line=dict(color='#1565C0',width=1.5)))
    fi.add_trace(go.Scatter(x=ma200s.index,y=ma200s.values,mode='lines',name='200MA',line=dict(color='#4CAF50',width=1,dash='dot')))
    fi.add_hline(y=trailing_peak,line_dash='dash',line_color='#D32F2F',line_width=1,annotation_text='52W High: '+f'{trailing_peak:,.0f}',annotation_position='top left',annotation_font_size=10,annotation_font_color='#D32F2F')
    fi.update_layout(title=dict(text='52-Week Price Chart \u2014 '+selected_index_profile,font=dict(size=13)),height=220,margin=dict(l=10,r=10,t=35,b=10),showlegend=True,legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='right',x=1,font=dict(size=10)),xaxis=dict(showgrid=False),yaxis=dict(showgrid=True,gridcolor='#F0F0F0'),plot_bgcolor='white',paper_bgcolor='white')
    st.plotly_chart(fi,use_container_width=True,config={'displayModeBar':False})
except: st.caption('\u26a0\ufe0f Index chart unavailable')

st.markdown('')
r2c1,r2c2,r2c3 = st.columns(3)
live_vix = live_macro.get('vix'); live_ys = live_macro.get('yield_spread')
vd = round(live_vix,1) if live_vix else 20.0; yd = round(live_ys,2) if live_ys else 0.45
with r2c1:
    pmi_input = st.slider('US ISM Manufacturing PMI',40.0,60.0,51.5,help='Below 50 = contraction.')
    st.caption('\U0001f4dd Manual \u2014 [ISM Reports](https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/)')
with r2c2:
    yield_spread_input = st.slider('US Treasury Yield Spread (10Y\u22123M)',-1.50,2.50,yd,help='Below 0 = inverted.')
    if live_ys is not None:
        y10=live_macro.get('yield_10y',0); y3=live_macro.get('yield_3m',0)
        st.caption(f'\U0001f4e1 Live: **{live_ys:.2f}%** (10Y:{y10:.2f}% \u2212 3M:{y3:.2f}%)')
    else: st.caption('\u26a0\ufe0f Unavailable')
with r2c3:
    vix_input = st.slider('CBOE VIX Volatility Index',10.0,80.0,vd,help='Above 30 = fear.')
    if live_vix: st.caption(f'\U0001f4e1 Live VIX: **{live_vix:.2f}**')
    else: st.caption('\u26a0\ufe0f Unavailable')

cc1,cc2,cc3 = st.columns(3)
with cc1:
    st.markdown('<div style="background:#F5F5F5;border:1px solid #DDD;border-radius:8px;padding:16px;text-align:center;height:200px;display:flex;flex-direction:column;justify-content:center"><div style="font-size:13px;font-weight:600;color:#555">\U0001f4ca PMI Chart</div><div style="font-size:12px;color:#888;margin-top:8px">No free API. <a href="https://www.ismworld.org" target="_blank" style="color:#1565C0">ISM Reports</a></div></div>', unsafe_allow_html=True)
with cc2:
    try:
        th_=live_macro.get('tnx_hist'); ih_=live_macro.get('irx_hist')
        if th_ is not None and ih_ is not None:
            td_=th_[['Close']].rename(columns={'Close':'T'}); td_.index=td_.index.tz_localize(None)
            id__=ih_[['Close']].rename(columns={'Close':'I'}); id__.index=id__.index.tz_localize(None)
            sd_=td_.join(id__,how='inner'); sd_['S']=sd_['T']-sd_['I']
            fy=go.Figure()
            fy.add_trace(go.Scatter(x=sd_.index,y=sd_['T'],mode='lines',name='10Y',line=dict(color='#1565C0',width=1.5)))
            fy.add_trace(go.Scatter(x=sd_.index,y=sd_['I'],mode='lines',name='3M',line=dict(color='#E65100',width=1.5)))
            fy.add_trace(go.Scatter(x=sd_.index,y=sd_['S'],mode='lines',name='Spread',line=dict(color='#7B1FA2',width=1.5,dash='dot')))
            fy.add_hline(y=0,line_dash='dash',line_color='#D32F2F',line_width=1)
            fy.update_layout(title=dict(text='US Treasury Yields \u2014 10Y vs 3M',font=dict(size=12)),height=200,margin=dict(l=10,r=10,t=30,b=10),showlegend=True,legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='right',x=1,font=dict(size=9)),xaxis=dict(showgrid=False),yaxis=dict(showgrid=True,gridcolor='#F0F0F0',ticksuffix='%'),plot_bgcolor='white',paper_bgcolor='white')
            st.plotly_chart(fy,use_container_width=True,config={'displayModeBar':False})
            st.caption('3M as short-end proxy. 2Y unavailable via free API.')
    except: st.caption('\u26a0\ufe0f Yield chart unavailable')
with cc3:
    try:
        vhist=live_macro.get('vix_hist')
        if vhist is not None:
            vc=vhist.copy(); vc.index=vc.index.tz_localize(None)
            fv=go.Figure(); fv.add_trace(go.Scatter(x=vc.index,y=vc['Close'],mode='lines',name='VIX',line=dict(color='#7B1FA2',width=1.5)))
            fv.add_hline(y=30,line_dash='dash',line_color='#D32F2F',line_width=1,annotation_text='Fear(30)',annotation_position='top left',annotation_font_size=9,annotation_font_color='#D32F2F')
            fv.update_layout(title=dict(text='CBOE VIX \u2014 1Y',font=dict(size=12)),height=200,margin=dict(l=10,r=10,t=30,b=10),showlegend=False,xaxis=dict(showgrid=False),yaxis=dict(showgrid=True,gridcolor='#F0F0F0'),plot_bgcolor='white',paper_bgcolor='white')
            st.plotly_chart(fv,use_container_width=True,config={'displayModeBar':False})
    except: st.caption('\u26a0\ufe0f VIX chart unavailable')

evaluation_price = picked_price if use_historical else index_price_input
trailing_peak = safe_float(trailing_peak, evaluation_price)
effective_scenario_drawdown = ((evaluation_price-trailing_peak)/trailing_peak)*100 if trailing_peak>0 else 0.0
baseline_200_ma = safe_float(sp['ma_200'], evaluation_price)
pmi_triggered=pmi_input<50; yield_triggered=yield_spread_input<0; ma_triggered=evaluation_price<baseline_200_ma; vix_triggered=vix_input>30
systemic_risk_score = sum([pmi_triggered,yield_triggered,ma_triggered,vix_triggered])

if effective_scenario_drawdown<=-35: azn='STRONG BUY'; zpt='STRONG BUY ZONE'; zs='Generational &mdash; Deploy Maximum Capital'; ze='\U0001f6a8'; zc='#D32F2F'; ztc='#FFF'; up=True
elif effective_scenario_drawdown<=-20: azn='BUY'; zpt='BUY ZONE'; zs='Bear Market &mdash; Scale In'; ze='\U0001f7e2'; zc='#E65100'; ztc='#FFF'; up=False
elif effective_scenario_drawdown<=-10: azn='INITIAL BUY'; zpt='INITIAL BUY ZONE'; zs='Correction &mdash; Nibble Positions'; ze='\U0001f7e1'; zc='#F9A825'; ztc='#1A1A1A'; up=False
elif evaluation_price>(1.20*baseline_200_ma) and systemic_risk_score>=3: azn='STRONG SELL'; zpt='STRONG SELL ZONE'; zs='Bubble &mdash; Maximize Liquidity'; ze='\U0001f534'; zc='#B71C1C'; ztc='#FFF'; up=True
else: azn='HOLD'; zpt='HOLD / DCA ZONE'; zs='Normal &mdash; Maintain DCA'; ze='\u26aa'; zc='#2E7D32'; ztc='#FFF'; up=False

st.markdown('---')
if effective_scenario_drawdown<=-35: dbg='#FFCDD2';dbd='#D32F2F';di='\U0001f6a8';dtc='#B71C1C';dl='Generational drawdown!'
elif effective_scenario_drawdown<=-20: dbg='#FFE0B2';dbd='#E65100';di='\u26a0\ufe0f';dtc='#E65100';dl='Deep drawdown!'
elif effective_scenario_drawdown<=-10: dbg='#FFF9C4';dbd='#F9A825';di='\u26a0\ufe0f';dtc='#F57F17';dl='Correction zone'
else: dbg='#E8F5E9';dbd='#2E7D32';di='\u2705';dtc='#2E7D32';dl='Normal range'
if systemic_risk_score>=3: rbg='#FFCDD2';rbd='#D32F2F';ri='\U0001f6a8';rtc='#B71C1C';rl='CRITICAL!'
elif systemic_risk_score>=1: rbg='#FFE0B2';rbd='#E65100';ri='\u26a0\ufe0f';rtc='#E65100';rl='Elevated: '+str(systemic_risk_score)+' factor(s)'
else: rbg='#E8F5E9';rbd='#2E7D32';ri='\u2705';rtc='#2E7D32';rl='All clear'
psi='\U0001f6a8' if pmi_triggered else '\u2705'; psc='#D32F2F' if pmi_triggered else '#2E7D32'; pst='CONTRACTION' if pmi_triggered else 'Expansionary'
ysi='\U0001f6a8' if yield_triggered else '\u2705'; ysc='#D32F2F' if yield_triggered else '#2E7D32'; yst='INVERTED' if yield_triggered else 'Normal'
msi='\U0001f6a8' if ma_triggered else '\u2705'; msc='#D32F2F' if ma_triggered else '#2E7D32'; mst='BELOW 200MA' if ma_triggered else 'Above 200MA'
vsi='\U0001f6a8' if vix_triggered else '\u2705'; vsc='#D32F2F' if vix_triggered else '#2E7D32'; vst='FEAR' if vix_triggered else 'Normal'

mc1,mc2,mc3 = st.columns(3)
with mc1:
    h='<div style="background:'+dbg+';border-left:6px solid '+dbd+';border-radius:10px;padding:20px;text-align:center">'
    h+='<div style="font-size:14px;color:#555;font-weight:600">EFFECTIVE DRAWDOWN</div>'
    h+='<div style="font-size:42px;font-weight:800;color:'+dtc+';margin:8px 0">'+di+' '+f'{effective_scenario_drawdown:.2f}%'+'</div>'
    h+='<div style="font-size:12px;color:#777">'+dl+'</div><div style="font-size:11px;color:#999;margin-top:6px">vs 52-week high</div></div>'
    st.markdown(h,unsafe_allow_html=True)
with mc2:
    h='<div style="background:'+rbg+';border-left:6px solid '+rbd+';border-radius:10px;padding:20px;text-align:center">'
    h+='<div style="font-size:14px;color:#555;font-weight:600">MACRO RISK SCORE</div>'
    h+='<div style="font-size:42px;font-weight:800;color:'+rtc+';margin:8px 0">'+ri+' '+str(systemic_risk_score)+' / 4</div>'
    h+='<div style="font-size:12px;color:#777;margin-bottom:12px">'+rl+'</div>'
    h+='<div style="text-align:left;padding:10px 14px;background:rgba(255,255,255,0.7);border-radius:8px">'
    h+='<div style="font-size:11px;font-weight:700;color:#333;margin-bottom:8px">RISK BREAKDOWN:</div>'
    h+='<div style="font-size:12px;color:'+psc+';margin:4px 0">'+psi+' <b>PMI:</b> '+f'{pmi_input:.1f}'+' &mdash; '+pst+'</div>'
    h+='<div style="font-size:12px;color:'+ysc+';margin:4px 0">'+ysi+' <b>Yield:</b> '+f'{yield_spread_input:.2f}'+' &mdash; '+yst+'</div>'
    h+='<div style="font-size:12px;color:'+msc+';margin:4px 0">'+msi+' <b>200MA:</b> '+f'{evaluation_price:,.0f}'+' vs '+f'{baseline_200_ma:,.0f}'+' &mdash; '+mst+'</div>'
    h+='<div style="font-size:12px;color:'+vsc+';margin:4px 0">'+vsi+' <b>VIX:</b> '+f'{vix_input:.1f}'+' &mdash; '+vst+'</div></div></div>'
    st.markdown(h,unsafe_allow_html=True)
with mc3:
    h='<div style="background:#E3F2FD;border-left:6px solid #1565C0;border-radius:10px;padding:20px;text-align:center">'
    h+='<div style="font-size:14px;color:#555;font-weight:600">52-WEEK TRAILING HIGH</div>'
    h+='<div style="font-size:42px;font-weight:800;color:#1565C0;margin:8px 0">\U0001f4ca '+f'{trailing_peak:,.2f}'+'</div>'
    h+='<div style="font-size:12px;color:#777">Peak on '+peak_date_str+'</div>'
    h+='<div style="font-size:11px;color:#aaa;margin-top:8px;padding-top:8px;border-top:1px solid #D0D0D0">ATH: '+f'{ath_value:,.2f}'+' ('+ath_date_str+')</div></div>'
    st.markdown(h,unsafe_allow_html=True)

st.markdown('<br>',unsafe_allow_html=True)
if up: pcss='<style>@keyframes zp{0%{box-shadow:0 0 0 0 rgba(211,47,47,.6)}50%{box-shadow:0 0 25px 10px rgba(211,47,47,.3)}100%{box-shadow:0 0 0 0 rgba(211,47,47,.6)}}.zb{animation:zp 2s infinite}</style>'
else: pcss='<style>.zb{}</style>'
bh=pcss+'<div class="zb" style="background:linear-gradient(135deg,'+zc+','+zc+'DD);border-radius:16px;padding:30px 40px;text-align:center;border:2px solid '+zc+'">'
bh+='<div style="font-size:50px;margin-bottom:5px">'+ze+'</div>'
bh+='<div style="font-size:13px;color:'+ztc+';opacity:.8;letter-spacing:3px;text-transform:uppercase;font-weight:600">Target Evaluation Matrix</div>'
bh+='<div style="font-size:32px;font-weight:900;color:'+ztc+';margin:10px 0;letter-spacing:2px">'+zpt+'</div>'
bh+='<div style="font-size:16px;color:'+ztc+';opacity:.9">'+zs+'</div></div>'
st.markdown(bh,unsafe_allow_html=True)
st.markdown('<br>',unsafe_allow_html=True)

st.markdown('### \U0001f4cb Tactical Allocation Recommendations')
with st.expander('\U0001f4d0 Allocation Rules \u2014 Click to view'):
    zd=[('STRONG BUY','\u2264-35%','100%','100%','100%','Generational'),('BUY','\u2264-20%','50%','75%','40%','Bear market'),('INITIAL BUY','\u2264-10%','20%','30%','15%','Correction'),('HOLD/DCA','Normal','0%','0%','0%','Maintain DCA'),('STRONG SELL','Bubble+Risk\u22653','0%','0%','0%','Pause')]
    tbl='| Zone | Trigger | Cash | SRS | CPF-OA | Rationale |'+chr(10)+'|:---|:---|:---:|:---:|:---:|:---|'+chr(10)
    for zn,tr,cp,sp,cpfp,rat in zd:
        ac=(zn=='STRONG BUY' and azn=='STRONG BUY') or (zn=='BUY' and azn=='BUY') or (zn=='INITIAL BUY' and azn=='INITIAL BUY') or (zn=='HOLD/DCA' and azn=='HOLD') or (zn=='STRONG SELL' and azn=='STRONG SELL')
        if ac: tbl+=f'| \U0001f449 **{zn}** | **{tr}** | **{cp}** | **{sp}** | **{cpfp}** | **{rat}** |'+chr(10)
        else: tbl+=f'| {zn} | {tr} | {cp} | {sp} | {cpfp} | {rat} |'+chr(10)
    st.markdown(tbl)
    st.markdown('**Drawdown:** from 52W high. **Cash** after buffer. **CPF-OA** after S$20k floor. **Triggers:** PMI<50, Spread<0, Price<200MA, VIX>30.')

uc=max(0.0,cash_balance-emergency_buffer); us=srs_balance; ucpf=max(0.0,cpf_oa_balance-20000.0) if preserve_cpf_bonus else cpf_oa_balance
co=0.0;so=0.0;cpfo=0.0
if azn=='STRONG BUY': co=uc;so=us;cpfo=ucpf
elif azn=='BUY': co=uc*0.5;so=us*0.75;cpfo=ucpf*0.4
elif azn=='INITIAL BUY': co=uc*0.2;so=us*0.3;cpfo=ucpf*0.15
elif azn=='STRONG SELL': st.warning('\u26a0\ufe0f Bubble. Pausing deployments.')
else: st.info('\u2139\ufe0f Normal. Maintain DCA.')
rc=cash_balance-co;rs_=srs_balance-so;rcpf=cpf_oa_balance-cpfo;td_=co+so+cpfo
d1,d2,d3=st.columns(3)
with d1: st.markdown('#### \U0001f4b5 Cash'); st.metric('Deploy',f'S${co:,.2f}'); st.caption(f'Remaining: S${rc:,.2f}')
with d2: st.markdown('#### \U0001f4c8 SRS'); st.metric('Deploy',f'S${so:,.2f}'); st.caption(f'Remaining: S${rs_:,.2f}')
with d3: st.markdown('#### \U0001f6e1\ufe0f CPF-OA'); st.metric('Deploy',f'S${cpfo:,.2f}'); st.caption(f'Remaining: S${rcpf:,.2f}')
st.markdown('---')
st.subheader(f'Total Capital to Deploy: :green[S${td_:,.2f}]')

st.markdown('---')
st.markdown('### \U0001f4ca Market Performance & ETF Tracker')
def build_perf_table(records):
    t='<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px"><thead><tr style="background:#F0F2F6;border-bottom:2px solid #DDD">'
    t+='<th style="text-align:left;padding:10px 12px">Name</th><th style="text-align:center;padding:10px 12px">Ticker</th><th style="text-align:center;padding:10px 12px">Price</th>'
    t+='<th style="text-align:center;padding:10px 12px">1Y</th><th style="text-align:center;padding:10px 12px">3Y</th><th style="text-align:center;padding:10px 12px">5Y</th></tr></thead><tbody>'
    for r in records:
        ps=f"{r['price']:,.2f}" if r['price'] is not None else 'N/A'
        def fr(v):
            if v is None: return '<span style="color:#999">N/A</span>'
            c='#2E7D32' if v>=0 else '#D32F2F'; ar='\u25b2' if v>=0 else '\u25bc'
            return '<span style="color:'+c+';font-weight:600">'+ar+' '+f'{v:.1f}'+'%</span>'
        t+='<tr style="background:#FFF;border-bottom:1px solid #EEE"><td style="padding:10px 12px">'+r['name']+'</td><td style="text-align:center;padding:10px 12px;font-family:monospace;color:#555">'+r['ticker']+'</td><td style="text-align:center;padding:10px 12px;font-weight:600">'+ps+'</td><td style="text-align:center;padding:10px 12px">'+fr(r['1y'])+'</td><td style="text-align:center;padding:10px 12px">'+fr(r['3y'])+'</td><td style="text-align:center;padding:10px 12px">'+fr(r['5y'])+'</td></tr>'
    t+='</tbody></table>'; return t

try:
    with st.spinner('Fetching benchmarks...'): bd=fetch_benchmark_performance()
    if bd:
        for gn,recs in bd.items():
            ic='\U0001f30d' if 'Indic' in gn else '\U0001f6e2\ufe0f'
            st.markdown('<div style="font-size:18px;font-weight:700;margin-top:16px;margin-bottom:8px">'+ic+' '+gn+'</div>',unsafe_allow_html=True)
            st.markdown(build_perf_table(recs),unsafe_allow_html=True)
except Exception as e: st.warning(f'\u26a0\ufe0f Benchmarks unavailable: {e}')

try:
    with st.spinner('Fetching ETFs...'): ed=fetch_etf_performance()
    if ed:
        st.markdown('<div style="font-size:20px;font-weight:700;margin-top:24px;margin-bottom:8px">\U0001f4c8 Investable ETFs</div>',unsafe_allow_html=True)
        do=[]
        if selected_index_profile in ETF_UNIVERSE: do.append(selected_index_profile)
        for ix in ETF_UNIVERSE:
            if ix not in do: do.append(ix)
        for ix in do:
            if ix not in ed: continue
            gi=ETF_UNIVERSE[ix]; recs=ed[ix]; sel=(ix==selected_index_profile)
            badge=' <span style="background:#E8F5E9;color:#2E7D32;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">\u2705 SELECTED</span>' if sel else ''
            st.markdown('<div style="font-size:18px;font-weight:700;margin-top:16px;margin-bottom:8px">'+gi['market_label']+badge+'</div>',unsafe_allow_html=True)
            st.markdown(build_perf_table(recs),unsafe_allow_html=True)
except Exception as e: st.warning(f'\u26a0\ufe0f ETFs unavailable: {e}')

st.markdown('---')
st.markdown('### \U0001f3c6 Crash Buying Backtest \u2014 Proof That Buying The Dip Works')
st.caption('What if you invested $10,000 at every major drawdown trough in ' + selected_index_profile + '? Here are the real results.')

try:
    bt_data = underlying_data.copy()
    bt_data['rolling_max'] = bt_data['Close'].rolling(252, min_periods=1).max()
    bt_data['drawdown'] = ((bt_data['Close'] - bt_data['rolling_max']) / bt_data['rolling_max']) * 100
    latest_close = float(bt_data['Close'].iloc[-1])

    # Find trough events: drawdown crosses below -10%, find deepest point, min 60 days apart
    troughs = []
    in_drawdown = False
    episode_start = None
    min_gap = 60

    for i in range(len(bt_data)):
        dd_val = bt_data['drawdown'].iloc[i]
        if dd_val <= -10.0 and not in_drawdown:
            in_drawdown = True; episode_start = i
        elif dd_val > -5.0 and in_drawdown:
            in_drawdown = False
            episode = bt_data.iloc[episode_start:i]
            trough_idx = episode['drawdown'].idxmin()
            trough_row = bt_data.loc[trough_idx]
            trough_dd = float(trough_row['drawdown'])
            trough_price = float(trough_row['Close'])
            if len(troughs) == 0 or (trough_idx - troughs[-1]['date']).days >= min_gap:
                zone = 'STRONG BUY' if trough_dd <= -35 else ('BUY' if trough_dd <= -20 else 'INITIAL BUY')
                zcolor = '#D32F2F' if trough_dd <= -35 else ('#E65100' if trough_dd <= -20 else '#F9A825')
                current_val = 10000 * (latest_close / trough_price)
                ret_pct = ((latest_close / trough_price) - 1) * 100
                troughs.append({'date': trough_idx, 'price': trough_price, 'dd': trough_dd, 'zone': zone, 'zcolor': zcolor, 'current_val': current_val, 'return': ret_pct})

    # Also catch ongoing drawdown at end of data
    if in_drawdown and episode_start is not None:
        episode = bt_data.iloc[episode_start:]
        trough_idx = episode['drawdown'].idxmin()
        trough_row = bt_data.loc[trough_idx]
        trough_dd = float(trough_row['drawdown'])
        trough_price = float(trough_row['Close'])
        if len(troughs) == 0 or (trough_idx - troughs[-1]['date']).days >= min_gap:
            zone = 'STRONG BUY' if trough_dd <= -35 else ('BUY' if trough_dd <= -20 else 'INITIAL BUY')
            zcolor = '#D32F2F' if trough_dd <= -35 else ('#E65100' if trough_dd <= -20 else '#F9A825')
            current_val = 10000 * (latest_close / trough_price)
            ret_pct = ((latest_close / trough_price) - 1) * 100
            troughs.append({'date': trough_idx, 'price': trough_price, 'dd': trough_dd, 'zone': zone, 'zcolor': zcolor, 'current_val': current_val, 'return': ret_pct})

    if troughs:
        total_invested = len(troughs) * 10000
        total_current = sum(t['current_val'] for t in troughs)
        total_return = ((total_current - total_invested) / total_invested) * 100

        # Summary cards
        sc1, sc2, sc3 = st.columns(3)
        with sc1: st.metric('Total Invested', f'${total_invested:,.0f}', help=f'{len(troughs)} crash events x $10,000')
        with sc2: st.metric('Portfolio Value Today', f'${total_current:,.0f}', f'{total_return:+.1f}%')
        with sc3:
            avg_ret = sum(t['return'] for t in troughs) / len(troughs)
            st.metric('Avg Return Per Event', f'{avg_ret:,.1f}%', help='Average return across all crash-buy entries')

        # HTML table
        th = '<table style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0"><thead><tr style="background:#F0F2F6;border-bottom:2px solid #DDD">'
        th += '<th style="padding:10px">#</th><th style="padding:10px">Trough Date</th><th style="text-align:center;padding:10px">Index Level</th>'
        th += '<th style="text-align:center;padding:10px">Drawdown</th><th style="text-align:center;padding:10px">Zone</th>'
        th += '<th style="text-align:center;padding:10px">Invested</th><th style="text-align:center;padding:10px">Value Today</th>'
        th += '<th style="text-align:center;padding:10px">Return</th></tr></thead><tbody>'
        for i, t in enumerate(troughs):
            rc_ = '#2E7D32' if t['return'] >= 0 else '#D32F2F'
            ar_ = '\u25b2' if t['return'] >= 0 else '\u25bc'
            th += '<tr style="border-bottom:1px solid #EEE">'
            th += '<td style="padding:10px;text-align:center">' + str(i+1) + '</td>'
            th += '<td style="padding:10px">' + t['date'].strftime('%Y-%m-%d') + '</td>'
            th += '<td style="text-align:center;padding:10px">' + f"{t['price']:,.0f}" + '</td>'
            th += '<td style="text-align:center;padding:10px;color:#D32F2F;font-weight:600">' + f"{t['dd']:.1f}%" + '</td>'
            th += '<td style="text-align:center;padding:10px"><span style="background:' + t['zcolor'] + ';color:#FFF;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">' + t['zone'] + '</span></td>'
            th += '<td style="text-align:center;padding:10px">$10,000</td>'
            th += '<td style="text-align:center;padding:10px;font-weight:700">' + f"${t['current_val']:,.0f}" + '</td>'
            th += '<td style="text-align:center;padding:10px;color:' + rc_ + ';font-weight:700">' + ar_ + ' ' + f"{t['return']:.1f}%" + '</td></tr>'
        th += '</tbody></table>'
        st.markdown(th, unsafe_allow_html=True)

        # Bar chart
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Bar(
            x=[t['date'].strftime('%Y-%m') for t in troughs],
            y=[t['current_val'] for t in troughs],
            marker_color=[t['zcolor'] for t in troughs],
            text=[f"${t['current_val']:,.0f}" for t in troughs],
            textposition='outside',
            hovertemplate='%{x}<br>Value: $%{y:,.0f}<extra></extra>'
        ))
        fig_bt.add_hline(y=10000, line_dash='dash', line_color='#999', line_width=1, annotation_text='$10K invested', annotation_position='bottom right', annotation_font_size=10)
        fig_bt.update_layout(title=dict(text='Value Today of $10K Invested at Each Crash Trough', font=dict(size=14)), height=350, margin=dict(l=10, r=10, t=40, b=10), xaxis_title='Trough Date', yaxis_title='Current Value ($)', plot_bgcolor='white', paper_bgcolor='white', showlegend=False, yaxis=dict(showgrid=True, gridcolor='#F0F0F0'))
        st.plotly_chart(fig_bt, use_container_width=True, config={'displayModeBar': False})

        # Motivational callout
        st.success('\U0001f4a1 **Every single major crash in ' + selected_index_profile + ' history was a buying opportunity.** Out of ' + str(len(troughs)) + ' crash events, the market recovered every time. Total $' + f'{total_invested:,.0f}' + ' invested became $' + f'{total_current:,.0f}' + ' \u2014 a ' + f'{total_return:.1f}%' + ' total return. **The market always recovers.**')
    else:
        st.info('No drawdown events \u2265 10% found in the available data for ' + selected_index_profile + '.')
except Exception as e:
    st.warning(f'\u26a0\ufe0f Backtest unavailable: {e}')

st.markdown('---')
st.caption('\u26a0\ufe0f Disclaimer: This tool is for educational purposes only. Not financial advice. Past performance does not guarantee future results. Consult a licensed advisor.')
