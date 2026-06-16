
import math
import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title='Global Drawdown Allocation Engine v36 Phase 2', layout='wide', initial_sidebar_state='expanded')

BLUE = '#2563EB'; RED = '#EF4444'; ORANGE = '#F97316'; AMBER = '#F59E0B'; GREEN = '#16A34A'; SLATE = '#64748B'; PURPLE = '#7C3AED'; TEXT = '#111827'; MUTED = '#6B7280'

st.markdown('''
<style>
.block-container {padding-top:1.2rem; padding-bottom:2rem;}
div[data-testid="stMetric"] {background:white; border:1px solid #E5E7EB; border-radius:16px; padding:14px 16px; box-shadow:0 1px 2px rgba(15,23,42,.05);}
.light-card {background:#fff; border:1px solid #E5E7EB; border-radius:16px; padding:14px 16px; box-shadow:0 1px 2px rgba(15,23,42,.05); margin-bottom:10px;}
.kv {display:flex; justify-content:space-between; border-bottom:1px solid #F3F4F6; padding:6px 0; gap:12px;}
.kv:last-child {border-bottom:0;}
.kv-label {color:#6B7280; font-size:.88rem;}
.kv-value {font-weight:650; color:#111827; text-align:right;}
.warn-box {background:#FFFBEB; border:1px solid #FDE68A; border-radius:14px; padding:12px 14px; color:#92400E;}
.info-box {background:#EFF6FF; border:1px solid #BFDBFE; border-radius:14px; padding:12px 14px; color:#1E3A8A;}
</style>
''', unsafe_allow_html=True)

INDEX_TICKERS = {
    'S&P 500':'^GSPC','Nasdaq':'^IXIC','DJIA':'^DJI','HSI':'^HSI','STI':'^STI','KLSE':'^KLSE',
    'A-Share':'000001.SS','Nikkei 225':'^N225','Gold':'GC=F','Bitcoin':'BTC-USD'
}
ASSET_GROUPS = {
    'Market / Equity Index':['S&P 500','Nasdaq','DJIA','HSI','STI','KLSE','A-Share','Nikkei 225'],
    'Alternative Assets':['Gold','Bitcoin']
}
PMI_FRED_MARKETS = {'S&P 500','Nasdaq','DJIA'}
PMI_NA_MARKETS = {'Gold','Bitcoin'}
PMI_PROXY_MAP = {
    'S&P 500':{'label':'US ISM Manufacturing PMI','region':'United States','source':'FRED (ISM Manufacturing PMI)','default':54.0},
    'Nasdaq':{'label':'US ISM Manufacturing PMI','region':'United States','source':'FRED (ISM Manufacturing PMI)','default':54.0},
    'DJIA':{'label':'US ISM Manufacturing PMI','region':'United States','source':'FRED (ISM Manufacturing PMI)','default':54.0},
    'HSI':{'label':'China Caixin Manufacturing PMI','region':'China / Hong Kong','source':'NBS / Caixin / manual input','default':50.0},
    'STI':{'label':'Singapore S&P Global PMI','region':'Singapore','source':'SIPMM / S&P Global Singapore PMI / manual input','default':51.0},
    'KLSE':{'label':'Malaysia Manufacturing PMI','region':'Malaysia','source':'S&P Global Malaysia PMI / manual input','default':49.9},
    'A-Share':{'label':'China Caixin Manufacturing PMI','region':'China','source':'NBS / Caixin / manual input','default':50.0},
    'Nikkei 225':{'label':'Japan Jibun Bank Manufacturing PMI','region':'Japan','source':'Jibun Bank / S&P Global Japan PMI / manual input','default':50.4},
    'Gold':{'label':'N/A','region':'N/A','source':'PMI not applicable for Gold','default':0.0},
    'Bitcoin':{'label':'N/A','region':'N/A','source':'PMI not applicable for Bitcoin','default':0.0},
}
LATEST_PMI_ACTUALS = {
    'US ISM Manufacturing PMI':{'value':54.0,'month':'May 2026','source':'FRED (ISM Manufacturing PMI)'},
    'China Caixin Manufacturing PMI':{'value':50.0,'month':'Jun 2026','source':'NBS / Caixin / manual input'},
    'Singapore S&P Global PMI':{'value':51.0,'month':'Jun 2026','source':'SIPMM / S&P Global Singapore PMI / manual input'},
    'Malaysia Manufacturing PMI':{'value':49.9,'month':'Jun 2026','source':'S&P Global Malaysia PMI / manual input'},
    'Japan Jibun Bank Manufacturing PMI':{'value':50.4,'month':'Jun 2026','source':'Jibun Bank / S&P Global Japan PMI / manual input'},
    'N/A':{'value':0.0,'month':'N/A','source':'PMI not applicable for this asset class'},
}
PMI_PROXY_OPTIONS = list(LATEST_PMI_ACTUALS.keys())
DEFAULT_PMI_HISTORY = {
    'Singapore S&P Global PMI': {'2025-07':50.1,'2025-08':50.3,'2025-09':49.8,'2025-10':50.0,'2025-11':50.2,'2025-12':50.4,'2026-01':50.5,'2026-02':50.6,'2026-03':50.5,'2026-04':50.7,'2026-05':51.0,'2026-06':51.0},
    'China Caixin Manufacturing PMI': {'2025-07':49.4,'2025-08':49.1,'2025-09':49.8,'2025-10':50.1,'2025-11':50.3,'2025-12':50.1,'2026-01':49.1,'2026-02':50.2,'2026-03':50.5,'2026-04':49.0,'2026-05':49.6,'2026-06':50.0},
    'Malaysia Manufacturing PMI': {'2025-07':49.5,'2025-08':49.7,'2025-09':49.5,'2025-10':49.5,'2025-11':49.2,'2025-12':49.0,'2026-01':48.8,'2026-02':48.6,'2026-03':48.8,'2026-04':49.0,'2026-05':49.9,'2026-06':49.9},
    'Japan Jibun Bank Manufacturing PMI': {'2025-07':49.7,'2025-08':49.9,'2025-09':50.1,'2025-10':50.0,'2025-11':49.8,'2025-12':49.9,'2026-01':50.0,'2026-02':50.2,'2026-03':50.3,'2026-04':50.2,'2026-05':50.4,'2026-06':50.4},
}
ETF_UNIVERSE = {
    'S&P 500': [('Core exposure','SPDR S&P 500 ETF','SPY','Broad US large-cap exposure'),('Lower-cost core','Vanguard S&P 500 ETF','VOO','Low-cost S&P 500 exposure'),('Core alternative','iShares Core S&P 500 ETF','IVV','Broad S&P 500 exposure')],
    'Nasdaq': [('Core exposure','Invesco QQQ','QQQ','Nasdaq 100 exposure'),('Lower-cost alternative','Invesco QQQM','QQQM','Nasdaq 100 lower-fee alternative')],
    'DJIA': [('Core exposure','SPDR DJIA ETF','DIA','Blue-chip US exposure')],
    'HSI': [('Core exposure','Tracker Fund of Hong Kong','2800.HK','Broad HSI exposure'),('Broad HSI ETF','iShares HSI ETF','3115.HK','Alternative HSI exposure'),('Higher beta satellite','iShares Hang Seng TECH ETF','3067.HK','Growth / tech sensitivity')],
    'STI': [('Core exposure','SPDR STI ETF','ES3.SI','Broad STI exposure'),('Core alternative','Nikko AM STI ETF','G3B.SI','Alternative STI exposure')],
    'KLSE': [('Core exposure','FTSE Bursa Malaysia KLCI ETF','0820EA.KL','Broad Malaysia exposure')],
    'A-Share': [('Core exposure','Xtrackers Harvest CSI 300 China A-Shares ETF','ASHR','China A-share exposure'),('Satellite','KraneShares Bosera MSCI China A 50 Connect ETF','KBA','China A-share alternative')],
    'Nikkei 225': [('Core exposure','NEXT FUNDS Nikkei 225 ETF','1321.T','Nikkei 225 exposure'),('International proxy','iShares MSCI Japan ETF','EWJ','Broad Japan equity exposure')],
    'Gold': [('Core exposure','SPDR Gold Shares','GLD','Physical gold ETF'),('Alternative','iShares Gold Trust','IAU','Lower-cost gold ETF')],
    'Bitcoin': [('Core exposure','iShares Bitcoin Trust','IBIT','Spot Bitcoin ETF'),('Alternative','Grayscale Bitcoin Trust','GBTC','Bitcoin trust')],
}
BENCHMARK_TICKERS = {
    'Global Indices':[('STI','^STI'),('Nasdaq','^IXIC'),('S&P 500','^GSPC'),('DJIA','^DJI'),('HSI','^HSI'),('KLSE','^KLSE'),('A-Share','000001.SS'),('Nikkei 225','^N225')],
    'Commodities & Crypto':[('Crude Oil','CL=F'),('Gold','GC=F'),('Silver','SI=F'),('Bitcoin','BTC-USD')]
}
NAV_OPTIONS = ['🧠 Executive Centre','💰 Suggested Deploy','🌦️ Market Conditions','📊 Market Performance','🏆 Crash Analytics','📡 Audit Trail & Export']
SECTION_ORDER = ['💰 Suggested Deploy','🌦️ Market Conditions','📊 Market Performance','🏆 Crash Analytics','📡 Audit Trail & Export']
CRISIS_EVENTS = [('1987-08-01','1987-12-31','1987 Black Monday'),('2000-03-01','2002-10-31','2000-2002 Dot-com Bust'),('2007-10-01','2009-03-31','2008 Global Financial Crisis'),('2020-02-01','2020-04-30','2020 COVID-19 Crash'),('2022-01-01','2022-10-31','2022 Inflation & Rate Hike')]

# ------------------------- helpers -------------------------
def safe_float(v, fb=0.0):
    try:
        x = float(v)
        return fb if math.isnan(x) or math.isinf(x) else x
    except Exception:
        return fb

def tz_naive(df):
    df = df.copy(); df.index = pd.to_datetime(df.index)
    if getattr(df.index, 'tz', None) is not None: df.index = df.index.tz_convert(None)
    return df

@st.cache_data(ttl=14400)
def hist(ticker, start='1950-01-01'):
    try:
        df = yf.Ticker(ticker).history(start=start); time.sleep(0.03)
        if df is None or df.empty: return pd.DataFrame()
        return tz_naive(df.dropna(subset=['Close']).copy())
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=14400)
def market_data():
    out = {}
    for name,ticker in INDEX_TICKERS.items():
        df = hist(ticker)
        if df.empty: continue
        close = safe_float(df.Close.iloc[-1])
        ma = safe_float(df.Close.rolling(200).mean().dropna().iloc[-1], close) if len(df) >= 200 else close
        out[name] = {'ticker':ticker, 'df':df, 'close':close, 'ma200':ma}
    return out

@st.cache_data(ttl=3600)
def live_macro_data():
    def last_close(ticker):
        df = hist(ticker, '2025-01-01')
        return None if df.empty else safe_float(df.Close.iloc[-1])
    return {'vix':last_close('^VIX'), 'tnx':last_close('^TNX'), 'irx':last_close('^IRX')}

@st.cache_data(ttl=14400)
def perf(items):
    rec=[]
    for item in items:
        name, ticker = (item[1], item[2]) if len(item)==4 else item[:2]
        df = hist(ticker, '2018-01-01')
        if df.empty:
            rec.append({'Name':name,'Ticker':ticker,'Price':None,'1Y %':None,'3Y %':None,'5Y %':None}); continue
        last = safe_float(df.Close.iloc[-1])
        def r(days):
            if len(df) <= days: return None
            s = safe_float(df.Close.iloc[-days]); return round(((last/s)-1)*100,1) if s else None
        rec.append({'Name':name,'Ticker':ticker,'Price':round(last,2),'1Y %':r(252),'3Y %':r(756),'5Y %':r(1260)})
    return rec

@st.cache_data(ttl=14400)
def bench(): return {g:perf(v) for g,v in BENCHMARK_TICKERS.items()}

@st.cache_data(ttl=14400)
def etfs(): return {k:perf(v) for k,v in ETF_UNIVERSE.items()}

@st.cache_data(ttl=86400)
def fetch_fred_pmi(series_id='NAPM'):
    try:
        url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
        df = pd.read_csv(url, parse_dates=['DATE']); df.columns = ['Date','PMI']
        df = df.set_index('Date').dropna(); df['PMI'] = pd.to_numeric(df['PMI'], errors='coerce')
        return df.dropna()
    except Exception:
        return pd.DataFrame()

if 'pmi_history' not in st.session_state: st.session_state.pmi_history = {}

def kv(label, value, colour=TEXT): return f'<div class="kv"><div class="kv-label">{label}</div><div class="kv-value" style="color:{colour};">{value}</div></div>'

def card(title,value,sub,accent):
    return f'<div class="light-card" style="border-top:4px solid {accent};"><div style="color:{MUTED};font-size:.86rem;font-weight:600;">{title}</div><div style="font-size:1.55rem;font-weight:800;color:{TEXT};margin-top:4px;">{value}</div><div style="font-size:.82rem;color:{MUTED};margin-top:3px;">{sub}</div></div>'

def classify(dd):
    if dd <= -35: return 'STRONG BUY', RED
    if dd <= -20: return 'BUY', ORANGE
    if dd <= -10: return 'INITIAL BUY', AMBER
    if dd >= 0: return 'STRONG SELL', '#6A1B9A'
    return 'HOLD', BLUE

def severity_bucket(dd):
    a=abs(dd)
    if a<10: return 'Below 10% move'
    if a<20: return '10-20% correction'
    if a<30: return '20-30% correction'
    return '>30% crash'

def current_dd(df, method):
    c=safe_float(df.Close.iloc[-1])
    if method.startswith('Rolling'): days,label=252,'Rolling 252D Peak'
    elif method.startswith('2Y'): days,label=504,'2Y Peak'
    elif method.startswith('3Y'): days,label=756,'3Y Peak'
    elif method.startswith('5Y'): days,label=1260,'5Y Peak'
    else:
        peak=safe_float(df.Close.max(), c); return c, peak, ((c-peak)/peak)*100 if peak else 0, 'All-Time High Peak'
    peak=safe_float(df.Close.rolling(days,min_periods=1).max().iloc[-1], c)
    return c, peak, ((c-peak)/peak)*100 if peak else 0, label

def deploy_rule(dd):
    if dd <= -35: return .50
    if dd <= -25: return .35
    if dd <= -15: return .20
    if dd <= -8: return .10
    return 0.0

def capital_breakdown(zone, deploy_amount, available_cash, available_srs, available_cpf):
    cash=srs=cpf=0.0
    if deploy_amount <= 0: return cash,srs,cpf,'Current market action does not trigger deployment; capital preserved.'
    cash=min(deploy_amount, available_cash); rem=max(deploy_amount-cash,0)
    if zone in ['BUY','STRONG BUY']:
        srs=min(rem,available_srs); rem=max(rem-srs,0)
    if zone=='STRONG BUY': cpf=min(rem,available_cpf)
    reason = 'INITIAL BUY zone uses cash first; SRS/CPF-OA are preserved for deeper drawdowns.' if zone=='INITIAL BUY' else ('BUY zone uses cash first, then SRS if cash is insufficient. CPF-OA remains reserved.' if zone=='BUY' else 'STRONG BUY zone can use cash, SRS and CPF-OA above preserved floor.')
    return cash,srs,cpf,reason

def next_trigger_label(zone):
    if zone in ['HOLD','STRONG SELL']: return 'Initial buy zone near -8% to -10% drawdown'
    if zone=='INITIAL BUY': return 'BUY zone if drawdown deepens toward -20%'
    if zone=='BUY': return 'STRONG BUY zone if drawdown deepens beyond -35%'
    return 'Already in deepest deployment zone'

def confidence_score(dd, live_score, trend_below):
    score = 35 + (15 if dd <= -8 else 0) + (10 if trend_below else 0) + (10 if live_score < 50 else 0) - (25 if live_score >= 70 else 0)
    return max(0,min(100,score))

def confidence_label(score): return 'High' if score >=70 else 'Medium' if score >=45 else 'Low'

def calc_market_scores_by_asset(asset_name, pmi_value, dd_value, trend_weak, vix_value, curve_value):
    if asset_name in PMI_NA_MARKETS:
        vix_s=curve_s=pmi_s=0; dd_s=min(abs(dd_value)*1.5,40); trend_s=20 if trend_weak else 0; total=min(dd_s+trend_s,100)
    else:
        vix_s=0 if vix_value is None else min(max((vix_value-15)*2,0),30)
        curve_s=10 if curve_value is None else (20 if curve_value<0 else 10 if curve_value<.5 else 0)
        pmi_s=0 if pmi_value>=52 else 8 if pmi_value>=50 else 16 if pmi_value>=47 else 20
        dd_s=min(abs(dd_value)*1.2,25); trend_s=15 if trend_weak else 0; total=min(vix_s+curve_s+pmi_s+dd_s+trend_s,100)
    regime='CRASH RISK' if total>=70 else 'WARNING' if total>=50 else 'WATCH' if total>=30 else 'NORMAL'
    return total,regime,vix_s,curve_s,pmi_s,dd_s,trend_s

def valuation_status(z):
    if z is None or pd.isna(z): return 'N/A', SLATE
    if z>2: return 'Extreme Overvaluation', RED
    if z>1: return 'Expensive', ORANGE
    if z>-1: return 'Neutral / Fair', BLUE
    if z>-2: return 'Attractive', GREEN
    return 'Extreme Undervaluation', '#059669'

def tactical_implication(z):
    if z is None or pd.isna(z): return 'Insufficient data','N/A','Wait for more history','Neutral'
    if z>2: return 'Above long-term trend significantly','Very High','Very Defensive','Reduce Aggression'
    if z>1: return 'Above trend by >1 SD','Moderately High','Slow DCA / Maintain Cash Buffer','Reduce Aggression'
    if z>-1: return 'Near long-term fair value','Moderate','Neutral Deployment','Normal'
    if z>-2: return 'Below trend — historically attractive','Moderate-Low','Accumulation Phase','Increase Allocation'
    return 'Deeply below trend — rare opportunity','Low','Aggressive Deployment','Maximum Allocation'

# ------------------------- Phase 2 valuation engine -------------------------
def _prepare_monthly(df):
    if df is None or df.empty: return pd.DataFrame()
    m=df[['Close']].resample('ME').last().dropna().copy(); m=m[m.Close>0]
    m['Seq']=np.arange(1,len(m)+1); m['LogPrice']=np.log(m.Close)
    return m

def _fit_window(w):
    x=w.Seq.values.astype(float); y=w.LogPrice.values.astype(float)
    slope,intercept=np.polyfit(x,y,1); fitted=intercept+slope*x; resid=y-fitted
    sd=float(np.std(resid,ddof=1)) if len(resid)>2 else 0.0
    if not sd or np.isnan(sd): sd=1e-9
    return slope,intercept,sd

def build_trend_channel(df, projection_year=2040, model='Expanding Window', rolling_years=15, min_months=60):
    monthly=_prepare_monthly(df)
    if monthly.empty or len(monthly)<36: return None
    model = model or 'Expanding Window'
    if model == 'Full History':
        slope,intercept,sd=_fit_window(monthly)
        monthly['Trend']=intercept+slope*monthly.Seq
        monthly['Residual']=monthly.LogPrice-monthly.Trend
        monthly['ZHist']=monthly.Residual/sd
        label='Full History (Research View)'; bias='Uses full sample; contains look-ahead bias for historical signals'
    else:
        min_m=min(max(int(min_months),36),len(monthly)); roll_m=max(int(rolling_years*12),min_m)
        monthly['Trend']=np.nan; monthly['Residual']=np.nan; monthly['ZHist']=np.nan
        for i in range(len(monthly)):
            if i+1<min_m: continue
            start_i=max(0,i+1-roll_m) if model.startswith('Rolling') else 0
            w=monthly.iloc[start_i:i+1]; slope_i,intercept_i,sd_i=_fit_window(w)
            tr=intercept_i+slope_i*monthly.Seq.iloc[i]
            monthly.iloc[i, monthly.columns.get_loc('Trend')]=tr
            monthly.iloc[i, monthly.columns.get_loc('Residual')]=monthly.LogPrice.iloc[i]-tr
            monthly.iloc[i, monthly.columns.get_loc('ZHist')]=(monthly.LogPrice.iloc[i]-tr)/sd_i
        if model.startswith('Rolling'):
            latest=monthly.iloc[max(0,len(monthly)-roll_m):]; label=f'Rolling {rolling_years}Y Window (OOS)'; bias='No look-ahead bias; each point uses only its rolling historical window'
        else:
            latest=monthly; label='Expanding Window (OOS – Live Model)'; bias='No look-ahead bias; each point uses only data available up to that date'
        slope,intercept,sd=_fit_window(latest)
    monthly['TrendPrice']=np.exp(monthly.Trend); monthly['Upper1']=np.exp(monthly.Trend+sd); monthly['Upper2']=np.exp(monthly.Trend+2*sd); monthly['Lower1']=np.exp(monthly.Trend-sd); monthly['Lower2']=np.exp(monthly.Trend-2*sd)
    plot=monthly.dropna(subset=['TrendPrice','ZHist']).copy()
    if plot.empty: return None
    z=safe_float(plot.ZHist.iloc[-1]); pct=(plot.ZHist<z).mean()*100; reg_cagr=(np.exp(slope*12)-1)*100
    years=len(monthly)/12; actual_cagr=((monthly.Close.iloc[-1]/monthly.Close.iloc[0])**(1/years)-1)*100 if years>0 and monthly.Close.iloc[0]>0 else 0
    last_date=monthly.index[-1]; last_seq=int(monthly.Seq.iloc[-1])
    proj_dates=pd.date_range(last_date+pd.DateOffset(months=1), f'{projection_year}-12-31', freq='ME')
    proj_seq=np.arange(last_seq+1,last_seq+1+len(proj_dates)); proj_trend=intercept+slope*proj_seq
    proj=pd.DataFrame({'TrendPrice':np.exp(proj_trend),'Upper1':np.exp(proj_trend+sd),'Upper2':np.exp(proj_trend+2*sd),'Lower1':np.exp(proj_trend-sd),'Lower2':np.exp(proj_trend-2*sd)}, index=proj_dates)
    extremes=pd.concat([plot.nlargest(min(3,len(plot)),'ZHist')[['Close','ZHist']], plot.nsmallest(min(2,len(plot)),'ZHist')[['Close','ZHist']]]).sort_index()
    return {'data':plot,'raw_monthly':monthly,'proj':proj,'sd':sd,'z_score':z,'pct_rank':pct,'reg_cagr':reg_cagr,'actual_cagr':actual_cagr,'extremes':extremes,'model':model,'model_label':label,'bias_status':bias}

def get_z_at(tc, date):
    if tc is None or tc.get('data') is None or tc['data'].empty: return np.nan
    zser=tc['data']['ZHist'].dropna(); target=pd.Timestamp(date); idx=zser.index[zser.index<=target]
    return np.nan if len(idx)==0 else safe_float(zser.loc[idx[-1]], np.nan)

def crash_valuation_classification(zp,zt):
    if pd.isna(zp) or pd.isna(zt): return 'Insufficient valuation history'
    if zp>=1.5 and zt<=-1.0: return 'Classic bubble unwind'
    if zt<=-2.0: return 'Deep undervaluation'
    if zp>=1.5: return 'Overvaluation reset'
    if abs(zp)<1.0 and zt<=-1.0: return 'Macro shock / panic reset'
    return 'Mid-cycle correction'

def label_event(date):
    y=pd.Timestamp(date).year
    if 1997<=y<=1998: return 'Asian Financial Crisis'
    if 2000<=y<=2002: return 'Dot-com Bust'
    if 2007<=y<=2009: return 'Global Financial Crisis'
    if y==2011: return 'Eurozone / US Debt Scare'
    if 2015<=y<=2016: return 'China Devaluation / Oil Shock'
    if y==2018: return 'US-China Trade War'
    if y==2020: return 'COVID Shock'
    if 2021<=y<=2022: return 'Rate-Hike Cycle'
    return 'Unlabelled Cycle'

def crash_events(bt, thr, current, valuation_tc=None):
    ev=[]; in_dd=False; start=None
    for i in range(len(bt)):
        dv=bt.dd_pct.iloc[i]
        if dv <= -thr and not in_dd: in_dd=True; start=i
        elif (dv > -5 and in_dd) or (i==len(bt)-1 and in_dd):
            in_dd=False; e=bt.iloc[start:i+1]
            if e.empty: continue
            ti=e.dd_pct.idxmin(); row=bt.loc[ti]
            if len(ev)==0 or (ti-ev[-1]['Trough Date']).days>=60:
                look=bt.loc[:ti].iloc[max(0,len(bt.loc[:ti])-252):]; pkdt=look.Close.idxmax()
                ddv=safe_float(row.dd_pct); price=safe_float(row.Close); peak=safe_float(row.rm); zone,_=classify(ddv); recovery=((current/price)-1)*100 if price else 0
                zp=get_z_at(valuation_tc, pkdt) if valuation_tc is not None else np.nan; zt=get_z_at(valuation_tc, ti) if valuation_tc is not None else np.nan
                ev.append({'Peak Date':pkdt,'Peak Index':peak,'Trough Date':ti,'Trough Index':price,'Drawdown %':ddv,'Recovery Return %':recovery,'Zone':zone,'Historical Label':label_event(ti),'Severity':severity_bucket(ddv),'Z @ Peak':zp,'Z @ Trough':zt,'Valuation Classification':crash_valuation_classification(zp,zt)})
    return pd.DataFrame(ev)

# ------------------------- charts -------------------------
def mini_trend_chart(df,title,subtitle,colour,fill_colour,y_title=''):
    if df is None or df.empty: st.info(f'{title}: data unavailable'); return
    fig=go.Figure(); fig.add_trace(go.Scatter(x=df.index,y=df.iloc[:,0],mode='lines',line=dict(color=colour,width=3),fill='tozeroy',fillcolor=fill_colour))
    fig.update_layout(height=240, margin=dict(l=10,r=10,t=48,b=10), title=f'{title}<br><sup>{subtitle}</sup>', plot_bgcolor='white', paper_bgcolor='white', showlegend=False, yaxis_title=y_title)
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})

def mini_pmi_bar_chart(df,title,subtitle):
    if df is None or df.empty or 'PMI' not in df.columns: st.info(f'{title}: data unavailable'); return
    colours=[GREEN if v>=50 else RED for v in df.PMI]
    fig=go.Figure(); fig.add_trace(go.Bar(x=df.index,y=df.PMI,marker_color=colours,text=[f'{v:.1f}' for v in df.PMI],textposition='outside',cliponaxis=False))
    fig.add_hline(y=50,line_dash='dash',line_color=SLATE,annotation_text='50 Expansion / Contraction',annotation_position='top left')
    fig.update_layout(height=250,margin=dict(l=10,r=10,t=58,b=10),title=f'{title}<br><sup>{subtitle}</sup>',plot_bgcolor='white',paper_bgcolor='white',showlegend=False,yaxis_title='PMI')
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})

# ------------------------- app state/load -------------------------
with st.spinner('Loading market data...'):
    m=market_data()
    if not m: st.error('Market data unavailable. Try Refresh Market Data.'); st.stop()

with st.sidebar:
    st.markdown('## 📍 Navigation')
    active_section=st.radio('Go to section', NAV_OPTIONS, index=0, label_visibility='collapsed')
    st.markdown('---'); st.markdown('## ⚙️ Quick Settings')
    asset_group=st.selectbox('Asset Group', list(ASSET_GROUPS.keys()), index=0)
    group_items=ASSET_GROUPS[asset_group]; default_item='STI' if asset_group=='Market / Equity Index' and 'STI' in group_items else group_items[0]
    sel=st.selectbox('Selected Market' if asset_group=='Market / Equity Index' else 'Selected Alternative Asset', group_items, index=group_items.index(default_item))
    st.session_state.selected_market_name=sel
    st.markdown('### 💰 Capital Pools & Safeguards')
    cash_balance=st.number_input('Liquid Cash (S$)',0.0,value=100000.0,step=5000.0)
    srs_balance=st.number_input('SRS (S$)',0.0,value=35000.0,step=5000.0)
    cpf_oa_balance=st.number_input('CPF-OA (S$)',0.0,value=180000.0,step=5000.0)
    emergency_buffer=st.number_input('Emergency Buffer (S$)',0.0,value=20000.0,step=1000.0)
    preserve_cpf=st.checkbox('Preserve S$20k CPF-OA Floor',value=True)
    drawdown_method=st.radio('Drawdown Reference',['Rolling 252D Peak','2Y Peak','3Y Peak','5Y Peak','All-Time High Peak'],index=0)
    if st.button('🔄 Refresh Market Data',use_container_width=True): st.cache_data.clear(); st.toast('Market data refreshed.', icon='🔄')

if sel not in m:
    df=hist(INDEX_TICKERS[sel])
    if df.empty: st.error(f'Market data unavailable for {sel} ({INDEX_TICKERS[sel]}). Try Refresh Market Data.'); st.stop()
    close_=safe_float(df.Close.iloc[-1]); ma=safe_float(df.Close.rolling(200).mean().dropna().iloc[-1],close_) if len(df)>=200 else close_
    m[sel]={'ticker':INDEX_TICKERS[sel],'df':df,'close':close_,'ma200':ma}

ud=m[sel]['df']; ticker=m[sel]['ticker']; index_label=sel; pmi_proxy_default=PMI_PROXY_MAP.get(sel, {'label':'N/A','region':'N/A','source':'N/A','default':0})
if st.session_state.get('pmi_selected_market') != sel:
    st.session_state.pmi_selected_market=sel; st.session_state.pmi_proxy_label=pmi_proxy_default['label']; st.session_state.latest_pmi_value=float(pmi_proxy_default['default'])
    act=LATEST_PMI_ACTUALS.get(pmi_proxy_default['label'], LATEST_PMI_ACTUALS['N/A']); st.session_state.latest_pmi_month=act['month']; st.session_state.latest_pmi_source=pmi_proxy_default['source']

close,peak,dd,ref=current_dd(ud,drawdown_method); zone,zc=classify(dd); deploy_pct=deploy_rule(dd)
available_cash=max(cash_balance-emergency_buffer,0); available_srs=srs_balance; available_cpf=max(cpf_oa_balance-(20000 if preserve_cpf else 0),0); total_available=available_cash+available_srs+available_cpf; deploy=total_available*deploy_pct
cash_deploy,srs_deploy,cpf_deploy,capital_reason=capital_breakdown(zone,deploy,available_cash,available_srs,available_cpf); funding_source='Cash First' if cash_deploy>0 else 'No deployment'
macro=live_macro_data(); vix=macro.get('vix'); tnx=macro.get('tnx'); irx=macro.get('irx'); curve_spread=(tnx-irx) if (tnx is not None and irx is not None) else None
trend_below=close<m[sel]['ma200']; pmi_label=pmi_proxy_default['label']; latest_pmi=float(st.session_state.get('latest_pmi_value', pmi_proxy_default['default'])); pmi_applicable=sel not in PMI_NA_MARKETS
live_score,alert,vix_s,curve_s,pmi_s,dd_s,trend_s=calc_market_scores_by_asset(sel,latest_pmi,dd,trend_below,vix,curve_spread)
conf_score=confidence_score(dd,live_score,trend_below); conf_label=confidence_label(conf_score); decision_line=f'Deploy approximately S${deploy:,.0f} using staged tranches.' if deploy>0 else 'No deployment now. Capital is preserved until a deployment trigger appears.'; next_trigger=next_trigger_label(zone)
_exec_tc=build_trend_channel(ud,2040,model='Expanding Window',rolling_years=15); exec_z_score=float(_exec_tc['z_score']) if _exec_tc is not None else None; exec_valuation_zone,exec_valuation_colour=valuation_status(exec_z_score)

st.title('📉 Global Drawdown Allocation Engine')
st.caption('v36 Phase 2 · Multi-asset drawdown allocation platform with OOS valuation model, crash-context analytics and audit-ready transparency.')

# ------------------------- renderers -------------------------
def render_executive():
    st.markdown('---'); st.markdown('## 🧠 Executive Tactical Allocation Centre')
    r1=st.columns(3)
    r1[0].markdown(card(index_label,f'{close:,.0f}',f'{ticker} · Index Level',BLUE),unsafe_allow_html=True)
    r1[1].markdown(card('Current Drawdown',f'{dd:.1f}%',ref,RED),unsafe_allow_html=True)
    r1[2].markdown(card('Current Market Action',zone,'Drawdown-based rule',ORANGE),unsafe_allow_html=True)
    r2=st.columns(3)
    r2[0].markdown(card('Suggested Deploy',f'S${deploy:,.0f}','Calculation output',AMBER),unsafe_allow_html=True)
    risk_colour=RED if alert=='CRASH RISK' else ORANGE if alert=='WARNING' else AMBER if alert=='WATCH' else GREEN
    model_note='Alternative price model' if sel in PMI_NA_MARKETS else 'Equity macro model'
    r2[1].markdown(card('Risk Regime',alert,f'{model_note} · Score {live_score:.0f}/100',risk_colour),unsafe_allow_html=True)
    z_display='N/A' if exec_z_score is None else f'{exec_z_score:+.2f}'
    r2[2].markdown(card('Valuation Z-Score (OOS)',z_display,f'{exec_valuation_zone} · Expanding Window',exec_valuation_colour),unsafe_allow_html=True)
    st.markdown(f'**Formula used:** Current drawdown = (current close − selected peak reference) ÷ selected peak reference. **Selected reference:** {ref} at approximately **{peak:,.0f}**.  \n**Decision note:** {decision_line}')

def render_suggested(expanded=False):
    with st.expander('💰 Suggested Deploy Basis & Capital Source',expanded=expanded):
        s1,s2,s3,s4=st.columns([1,1.15,1,1.1])
        s1.markdown(f'#### 📌 Suggested Deploy Basis\nSuggested Deploy = Available Deployable Capital × Deployment Rule\n\n#### S\${deploy:,.0f} = S\${total_available:,.0f} × {deploy_pct:.0%}${total_available:,.0f} × {deploy_pct:.0%}\nSource: selected price data, {ref} drawdown formula, and sidebar capital inputs.')
        s2.markdown('#### 🏦 Capital Source Breakdown'); s2.markdown('<div class="light-card">'+kv('Funding Source',funding_source,GREEN if cash_deploy>0 else SLATE)+kv('Cash Deployment',f'S${cash_deploy:,.0f}',GREEN)+kv('SRS Deployment',f'S${srs_deploy:,.0f}',SLATE)+kv('CPF-OA Deployment',f'S${cpf_deploy:,.0f}',SLATE)+kv('Reason',capital_reason,SLATE)+'</div>',unsafe_allow_html=True)
        s3.markdown('#### 🧱 Tranche Deployment Plan')
        if deploy<=0: s3.info('No tranche plan because Suggested Deploy is S$0 under current rule engine.')
        else: s3.markdown('<div class="light-card">'+kv('Tranche 1 — Deploy now',f'S${deploy*.5:,.0f}',AMBER)+kv('Tranche 2 — If drawdown deepens',f'S${deploy*.25:,.0f}',ORANGE)+kv('Tranche 3 — If stabilisation appears',f'S${deploy*.25:,.0f}',BLUE)+'</div>',unsafe_allow_html=True)
        s4.markdown('#### 🧭 Deployment Ladder'); s4.markdown('<div class="light-card">'+kv('HOLD / small drawdown','0% deploy',SLATE)+kv('INITIAL BUY','10% deploy · Cash only',AMBER)+kv('BUY','20–35% deploy · Cash then SRS',ORANGE)+kv('STRONG BUY','50% deploy · Cash + SRS + CPF-OA',RED)+kv('Next Trigger',next_trigger,ORANGE)+'</div>',unsafe_allow_html=True)
        if sel in ETF_UNIVERSE:
            st.markdown('#### 🎯 Suggested Investment Options')
            st.dataframe(pd.DataFrame([{'Role':r,'Instrument':n,'Ticker':t,'Use case':u} for r,n,t,u in ETF_UNIVERSE[sel]]),use_container_width=True,hide_index=True)

def get_pmi_df(chosen,latest_in):
    if sel in PMI_NA_MARKETS: return pd.DataFrame()
    if sel in PMI_FRED_MARKETS:
        fred=fetch_fred_pmi('NAPM')
        if not fred.empty: return fred.tail(12)
    hist_map=st.session_state.pmi_history.get(chosen) or DEFAULT_PMI_HISTORY.get(chosen)
    if hist_map:
        idx=pd.to_datetime([k+'-01' for k in sorted(hist_map.keys())]); vals=[hist_map[k] for k in sorted(hist_map.keys())]
        return pd.DataFrame({'PMI':vals},index=idx).tail(12)
    dates=pd.date_range(end=pd.Timestamp.today().normalize(),periods=12,freq='ME'); vals=np.linspace(max(latest_in+1.0,30),latest_in,12); st.caption('⚠️ Simulated PMI trend — click 🔄 Update PMI to fetch/save actual data.'); return pd.DataFrame({'PMI':vals},index=dates)

def render_trend_channel(df, market_name):
    c1,c2,c3,c4=st.columns([1,1,1,1])
    freq=c1.selectbox('Data Frequency',['Monthly','Weekly','Daily'],index=0,key='tc_freq')
    model=c2.radio('Valuation Model',['Expanding Window','Rolling Window','Full History'],index=0,horizontal=True,key='tc_model')
    rolling_years=c3.selectbox('Rolling Window',[10,15,20],index=1,key='tc_roll_years')
    proj_year=c4.selectbox('Projection Horizon',[2030,2035,2040,2050],index=2,key='tc_proj')
    src=hist(INDEX_TICKERS.get(market_name,ticker))
    if src.empty: src=df
    wdf=src[['Close']].resample('W').last().dropna() if freq=='Weekly' else src[['Close']].copy() if freq=='Daily' else src[['Close']].resample('ME').last().dropna()
    tc=build_trend_channel(wdf,proj_year,model=model,rolling_years=rolling_years); full_tc=build_trend_channel(wdf,proj_year,model='Full History',rolling_years=rolling_years); exp_tc=build_trend_channel(wdf,proj_year,model='Expanding Window',rolling_years=rolling_years)
    if tc is None: st.warning('Insufficient data for trend channel analysis.'); return None
    tdf=tc['data']; proj=tc['proj']; z=tc['z_score']; status,status_colour=valuation_status(z); dist=((tdf.Close.iloc[-1]/tdf.TrendPrice.iloc[-1])-1)*100
    st.markdown(f'<div class="info-box"><b>Model:</b> {tc["model_label"]}<br><b>Bias status:</b> {tc["bias_status"]}</div>',unsafe_allow_html=True)
    m1,m2,m3,m4=st.columns(4); m1.metric('Market Status',status); m2.metric('Z-Score',f'{z:+.2f}'); m3.metric('Percentile Rank',f'{tc["pct_rank"]:.0f}th'); m4.metric('Distance from Trend',f'{dist:+.1f}%')
    comp=[]
    for name,obj in [('Expanding Window (OOS)',exp_tc),('Full History',full_tc)]:
        if obj is not None:
            stt,_=valuation_status(obj['z_score']); comp.append({'Model':name,'Current Z-Score':f'{obj["z_score"]:+.2f}','Interpretation':stt,'Bias Status':'No look-ahead bias' if name.startswith('Expanding') else 'Research only / biased historically'})
    if comp: st.markdown('#### 🧭 Valuation Model Comparison'); st.dataframe(pd.DataFrame(comp),use_container_width=True,hide_index=True)
    fig=go.Figure(); fig.add_trace(go.Scatter(x=tdf.index,y=tdf.Close,name=f'{market_name} Price',line=dict(color=BLUE,width=2))); fig.add_trace(go.Scatter(x=tdf.index,y=tdf.TrendPrice,name='Trend',line=dict(color=PURPLE,width=2)))
    for col,label,colour in [('Upper2','+2 SD',RED),('Upper1','+1 SD',AMBER),('Lower1','-1 SD',GREEN),('Lower2','-2 SD','#059669')]: fig.add_trace(go.Scatter(x=tdf.index,y=tdf[col],name=label,line=dict(color=colour,dash='dash',width=1.5)))
    if not proj.empty:
        fig.add_trace(go.Scatter(x=proj.index,y=proj.TrendPrice,name='Projection',line=dict(color=PURPLE,dash='dot',width=1.5),showlegend=False))
    for start,end,label in CRISIS_EVENTS:
        s=pd.Timestamp(start); e=pd.Timestamp(end)
        if tdf.index.min()<=e and s<=tdf.index.max(): fig.add_vrect(x0=max(s,tdf.index.min()),x1=min(e,tdf.index.max()),fillcolor='rgba(34,197,94,.055)',line_width=0,layer='below')
    fig.add_vline(x=tdf.index[-1],line_dash='dash',line_color=RED,line_width=1.5); fig.add_annotation(x=tdf.index[-1],y=.95,yref='paper',text=f'<b>Today</b><br>{tdf.index[-1].strftime("%b %d, %Y")}',showarrow=False,font=dict(size=11,color=RED),bgcolor='rgba(255,255,255,.92)',bordercolor=RED,borderwidth=1,borderpad=3)
    fig.update_layout(height=620,title=dict(text=f'<b>{market_name} 曾氏通道 (Trend Channel Line)</b> — {freq}, {tc["model_label"]}',font=dict(size=15)),yaxis_type='log',yaxis_title='Price (Log Scale)',plot_bgcolor='white',paper_bgcolor='white',margin=dict(l=10,r=90,t=60,b=10),legend=dict(orientation='h',yanchor='bottom',y=-.13,xanchor='center',x=.5,font=dict(size=10)))
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
    r2c1,r2c2,r2c3=st.columns([1,1.2,1])
    rows=[('Current Price',f'{tdf.Close.iloc[-1]:,.2f}',TEXT),('Trend Value',f'{tdf.TrendPrice.iloc[-1]:,.2f}',PURPLE),('Distance from Trend',f'{dist:+.1f}%',ORANGE if dist>0 else GREEN),('Z-Score',f'{z:+.2f}',status_colour),('Valuation Zone',status,status_colour),('Historical Percentile',f'{tc["pct_rank"]:.0f}th',TEXT),('Regression CAGR',f'{tc["reg_cagr"]:.2f}%',TEXT),('Actual CAGR',f'{tc["actual_cagr"]:.2f}%',TEXT),('Model',tc['model_label'],BLUE)]
    r2c1.markdown('#### 📋 Current Valuation Summary'); r2c1.markdown('<div class="light-card">'+''.join([kv(a,b,c) for a,b,c in rows])+'</div>',unsafe_allow_html=True)
    r2c2.markdown('#### 📈 Historical Z-Score'); zfig=go.Figure(); zfig.add_trace(go.Scatter(x=tdf.index,y=tdf.ZHist,mode='lines',line=dict(color=BLUE,width=1.5),fill='tozeroy',fillcolor='rgba(37,99,235,.12)'))
    for lv,colour in [(2,RED),(1,AMBER),(0,SLATE),(-1,GREEN),(-2,'#059669')]: zfig.add_hline(y=lv,line_dash='dash',line_color=colour,line_width=1)
    zfig.update_layout(height=300,margin=dict(l=10,r=10,t=10,b=10),plot_bgcolor='white',paper_bgcolor='white',showlegend=False,yaxis_title='Z-Score'); r2c2.plotly_chart(zfig,use_container_width=True,config={'displayModeBar':False})
    r2c3.markdown('#### 🎯 Tactical Implication'); vals=tactical_implication(z)
    for emoji,label,value in [('📊','Valuation',vals[0]),('⚠️','Risk Level',vals[1]),('🧭','Suggested Stance',vals[2]),('📈','Deployment Bias',vals[3])]: r2c3.markdown(card(f'{emoji} {label}',value,'Model-derived',GREEN if any(x in value for x in ['Accumulation','Increase','Aggressive','Maximum','Low']) else ORANGE if any(x in value for x in ['Defensive','Reduce','High']) else BLUE),unsafe_allow_html=True)
    with st.expander('📚 Full History Model (Research Only)',expanded=False):
        st.markdown('<div class="warn-box"><b>Research view only:</b> this model uses the full sample and therefore contains look-ahead bias when interpreting historical dates. Useful as secular reference, not live decision-grade model.</div>',unsafe_allow_html=True)
        if full_tc is not None:
            fstat,_=valuation_status(full_tc['z_score']); a,b,c=st.columns(3); a.metric('Full-History Z',f'{full_tc["z_score"]:+.2f}'); b.metric('Full-History Status',fstat); c.metric('Bias Status','Research only')
    return tc

def render_market(expanded=False):
    with st.expander('🌦️ MARKET CONDITIONS & LIVE RISK MONITOR',expanded=expanded):
        st.markdown('## 🌦️ Market Conditions & Live Risk Monitor')
        current_proxy=st.session_state.get('pmi_proxy_label',pmi_proxy_default['label']); actual=LATEST_PMI_ACTUALS.get(current_proxy,LATEST_PMI_ACTUALS['N/A'])
        st.markdown(f'### LIVE MARKET RISK ALERT: {alert}'); st.caption(f'Rules-based stress indicator, not a crash prediction. PMI proxy used as cycle signal: {current_proxy}.'); st.caption(f'Risk model used: {"Equity macro model (VIX + PMI + Yield Curve)" if sel not in PMI_NA_MARKETS else "Alternative asset model (Price-driven, no macro inputs)"}')
        p1,p2,p3,p4,p5,p6,p7=st.columns([1.15,1.05,1.45,.75,.75,.8,.55])
        chosen=p1.selectbox('PMI Proxy Used (Cycle Signal)',PMI_PROXY_OPTIONS,index=PMI_PROXY_OPTIONS.index(current_proxy) if current_proxy in PMI_PROXY_OPTIONS else 0,help='Market-specific PMI used as economic-cycle input.'); actual=LATEST_PMI_ACTUALS.get(chosen,LATEST_PMI_ACTUALS['N/A'])
        p2.text_input('PMI Region',value=PMI_PROXY_MAP.get(sel,{}).get('region','N/A')); pmi_source_in=p3.text_input('PMI Source',value=st.session_state.get('latest_pmi_source',actual['source'])); latest_in=p4.number_input('Latest PMI',0.0,70.0,float(st.session_state.get('latest_pmi_value',actual['value'])),step=.1); month_in=p5.text_input('PMI Month',value=st.session_state.get('latest_pmi_month',actual['month']))
        with p6:
            st.markdown('<br>',unsafe_allow_html=True)
            if st.button('🔄 Update PMI',use_container_width=True):
                if sel in PMI_FRED_MARKETS:
                    fred=fetch_fred_pmi('NAPM')
                    if not fred.empty:
                        st.session_state.latest_pmi_value=float(fred.PMI.iloc[-1]); st.session_state.latest_pmi_month=fred.index[-1].strftime('%b %Y'); st.session_state.latest_pmi_source='FRED (ISM Manufacturing PMI)'; st.session_state.pmi_proxy_label='US ISM Manufacturing PMI'; st.session_state.pmi_history['US ISM Manufacturing PMI']={d.strftime('%Y-%m'):float(v) for d,v in fred.tail(12).PMI.items()}; st.toast('✅ ISM PMI fetched from FRED.',icon='🔄')
                    else: st.toast('❌ Failed to fetch from FRED. Please try again.',icon='⚠️')
                elif sel in PMI_NA_MARKETS:
                    st.session_state.latest_pmi_value=0.0; st.session_state.latest_pmi_month='N/A'; st.session_state.latest_pmi_source='PMI not applicable'; st.session_state.pmi_proxy_label='N/A'; st.toast('ℹ️ PMI is not applicable for this asset class.',icon='ℹ️')
                else:
                    st.session_state.latest_pmi_value=float(latest_in); st.session_state.latest_pmi_month=month_in; st.session_state.latest_pmi_source=pmi_source_in; st.session_state.pmi_proxy_label=chosen; hist_map=DEFAULT_PMI_HISTORY.get(chosen,{}).copy(); hist_map[pd.Timestamp.today().strftime('%Y-%m')]=float(latest_in); st.session_state.pmi_history[chosen]=hist_map; st.toast(f'✅ {chosen} saved: {latest_in:.1f} for {month_in} (manual input)',icon='🔄')
                st.rerun()
        p7.markdown('<br>',unsafe_allow_html=True); p7.toggle('Manual',value=sel not in PMI_FRED_MARKETS and sel not in PMI_NA_MARKETS)
        pmi_app=sel not in PMI_NA_MARKETS; latest_display=0.0 if not pmi_app else latest_in; local_score,local_alert,lvix,lcurve,lpmi,ldd,ltrend=calc_market_scores_by_asset(sel,latest_display,dd,trend_below,vix,curve_spread)
        cols=st.columns(5); cols[0].metric('VIX Live','N/A' if (vix is None or sel in PMI_NA_MARKETS) else f'{vix:.1f}'); cols[1].metric('Yield Curve','N/A' if (curve_spread is None or sel in PMI_NA_MARKETS) else f'10Y-13W {curve_spread:.2f}%'); cols[2].metric(chosen,'N/A' if not pmi_app else f'{latest_in:.1f}'); cols[3].metric(f'{index_label} Drawdown',f'{dd:.1f}%'); cols[4].metric('Live Risk Score',f'{local_score:.0f}/100')
        sig,trigger,engine=st.columns([1,1,1.15]); sig.markdown('#### 📊 Signal Confidence Details'); sig.markdown('<div class="light-card">'+kv('Drawdown Signal','Active' if dd<=-8 else 'Inactive',ORANGE if dd<=-8 else SLATE)+kv('Risk Regime',local_alert,RED if local_alert=='CRASH RISK' else ORANGE if local_alert=='WARNING' else AMBER if local_alert=='WATCH' else GREEN)+kv('Technical Trend','Weak' if trend_below else 'Stable',BLUE)+'</div>',unsafe_allow_html=True)
        is_alt=sel in PMI_NA_MARKETS; trig=pd.DataFrame([{'Trigger':'VIX > 25','Status':'N/A' if is_alt else ('Yes' if vix is not None and vix>25 else 'No')},{'Trigger':'Yield curve inverted','Status':'N/A' if is_alt else ('Yes' if curve_spread is not None and curve_spread<0 else 'No')},{'Trigger':f'{chosen} < 50','Status':'N/A' if (is_alt or not pmi_app) else ('Yes' if latest_in<50 else 'No')},{'Trigger':'Drawdown < -10%','Status':'Yes' if dd<-10 else 'No'},{'Trigger':'Below 200D MA','Status':'Yes' if trend_below else 'No'}]); trigger.markdown('#### 📡 Live Trigger Monitor'); trigger.dataframe(trig,use_container_width=True,hide_index=True)
        engine.markdown('#### 🧮 Live Risk Score Engine')
        if is_alt: engine.markdown('<div class="light-card">'+kv('VIX Score','Disabled for alternative assets',SLATE)+kv('Yield Curve Score','Disabled for alternative assets',SLATE)+kv('PMI Score','Not applicable',SLATE)+kv('Drawdown Score',f'{ldd:.0f} / 40',ORANGE)+kv('Trend Score',f'{ltrend:.0f} / 20',RED)+kv('Total',f'{local_score:.0f} / 100 → {local_alert}',RED if local_alert=='CRASH RISK' else ORANGE if local_alert=='WARNING' else GREEN)+'</div>',unsafe_allow_html=True)
        else: engine.markdown('<div class="light-card">'+kv('VIX Score',f'{lvix:.0f} / 30',AMBER)+kv('Yield Curve Score',f'{lcurve:.0f} / 20',BLUE)+kv(f'{chosen} Score',f'{lpmi:.0f} / 20',GREEN)+kv('Drawdown Score',f'{ldd:.0f} / 25',ORANGE)+kv('Trend Score',f'{ltrend:.0f} / 15',RED)+kv('Total',f'{local_score:.0f} / 100 → {local_alert}',RED if local_alert=='CRASH RISK' else ORANGE if local_alert=='WARNING' else GREEN)+'</div>',unsafe_allow_html=True)
        with st.expander('📈 12M Trend Snapshot',expanded=False):
            vix_raw=hist('^VIX','2025-06-01'); vix_df=vix_raw[['Close']].rename(columns={'Close':'VIX'}) if not vix_raw.empty else pd.DataFrame(); tnx_raw=hist('^TNX','2025-06-01'); irx_raw=hist('^IRX','2025-06-01'); curve_df=pd.DataFrame()
            if not tnx_raw.empty and not irx_raw.empty:
                aligned=tnx_raw[['Close']].rename(columns={'Close':'TNX'}).join(irx_raw[['Close']].rename(columns={'Close':'IRX'}),how='inner')
                if not aligned.empty: curve_df=pd.DataFrame({'10Y-13W':aligned.TNX-aligned.IRX},index=aligned.index)
            pmi_df=get_pmi_df(chosen,latest_in); idx12=ud.loc[ud.index>=ud.index.max()-pd.DateOffset(months=12)][['Close']].rename(columns={'Close':'Index'})
            ch1,ch2=st.columns(2); mini_trend_chart(vix_df,'VIX 12M','Volatility regime',AMBER,'rgba(245,158,11,.18)','VIX'); mini_trend_chart(curve_df,'Yield Curve 12M','10Y minus 13W spread',BLUE,'rgba(37,99,235,.16)','Spread %')
            ch3,ch4=st.columns(2)
            with ch3: st.info('ℹ️ PMI is not applicable for this asset class (Gold / Bitcoin).') if sel in PMI_NA_MARKETS else mini_pmi_bar_chart(pmi_df,f'{chosen} 12M Monthly Releases',f'{month_in} latest monthly signal')
            with ch4: mini_trend_chart(idx12,f'{index_label} 12M',f'{ticker} · 12M price path',RED,'rgba(239,68,68,.16)','Index Level')
        with st.expander('📈 曾氏通道 (Trend Channel Line) — Secular Valuation Engine',expanded=False): st.markdown('### 曾氏通道 (TREND CHANNEL LINE) — SECULAR VALUATION ENGINE'); render_trend_channel(ud,index_label)

def render_performance(expanded=False):
    with st.expander('📊 MARKET PERFORMANCE & ETF TRACKER',expanded=expanded):
        for g,recs in bench().items(): st.markdown(f'### {g}'); st.dataframe(pd.DataFrame(recs),use_container_width=True,hide_index=True)
        ed=etfs(); order=[sel] if sel in ETF_UNIVERSE else []; order += [x for x in ETF_UNIVERSE if x not in order]
        for k in order:
            if k in ed: st.markdown(f'### {k}{" ✅ SELECTED" if k==sel else ""}'); st.dataframe(pd.DataFrame(ed[k]),use_container_width=True,hide_index=True)

def render_crash(expanded=False):
    with st.expander('🏆 Crash & Recovery Analytics',expanded=expanded):
        st.markdown('## 📊 Crash & Recovery Analytics + Valuation Context'); st.caption('Historical drawdown events are linked to OOS valuation context at peak and trough. Default valuation model: Expanding Window (OOS).')
        b1,b2,b3=st.columns(3); b1.markdown('<div class="light-card">📉 <b>10-20%</b><br>Normal correction-zone events.</div>',unsafe_allow_html=True); b2.markdown('<div class="light-card">⚠️ <b>20-30%</b><br>Deeper bear-market drawdowns.</div>',unsafe_allow_html=True); b3.markdown('<div class="light-card">🚨 <b>>30%</b><br>Severe crash-regime drawdowns.</div>',unsafe_allow_html=True)
        st.markdown('---'); p,q,r=st.columns([1,1,1]); start=p.date_input('Historical analysis start date',value=ud.index.min().date(),min_value=ud.index.min().date(),max_value=ud.index.max().date(),key='crash_start'); thr=q.slider('Minimum drawdown threshold (%)',10,50,10,5,key='crash_threshold'); crash_val_model=r.selectbox('Crash valuation model',['Expanding Window','Rolling Window','Full History'],index=0,key='crash_val_model')
        bt=ud.loc[pd.Timestamp(start):].copy(); bt['rm']=bt.Close.rolling(252,min_periods=1).max(); bt['dd_pct']=((bt.Close-bt.rm)/bt.rm)*100; cur=safe_float(bt.Close.iloc[-1]); valuation_tc=build_trend_channel(ud,2040,model=crash_val_model,rolling_years=15); event_df=crash_events(bt,thr,cur,valuation_tc)
        if event_df.empty: st.info('No drawdown events found with the selected parameters.'); return
        rets=event_df['Recovery Return %'].astype(float); k1,k2,k3,k4,k5=st.columns(5); k1.metric('Crash Events',len(event_df)); k2.metric('Success Rate',f'{rets.gt(0).mean()*100:.0f}%'); k3.metric('Avg Recovery',f'{rets.mean():.1f}%'); k4.metric('Best Recovery',f'{rets.max():.1f}%'); k5.metric('Current Drawdown',f'{bt.dd_pct.iloc[-1]:.1f}%')
        st.markdown('---'); st.markdown('## 🏛️ Valuation at Crash Engine'); val_table=event_df[['Historical Label','Drawdown %','Z @ Peak','Z @ Trough','Valuation Classification']].copy(); val_table['Drawdown %']=val_table['Drawdown %'].round(1)
        for c in ['Z @ Peak','Z @ Trough']: val_table[c]=val_table[c].apply(lambda x:'N/A' if pd.isna(x) else f'{x:+.2f}')
        st.dataframe(val_table,use_container_width=True,hide_index=True)
        st.markdown('---'); st.markdown('## 🔍 Interactive Event Explorer'); f1,f2,f3=st.columns([1,1,1]); sev_opts=sorted(event_df.Severity.dropna().unique().tolist()); zone_opts=sorted(event_df.Zone.dropna().unique().tolist()); label_opts=['All']+sorted(event_df['Historical Label'].dropna().unique().tolist()); sev_sel=f1.multiselect('Severity filter',sev_opts,default=sev_opts); zone_sel=f2.multiselect('Buy zone filter',zone_opts,default=zone_opts); label_sel=f3.selectbox('Historical label group',label_opts,index=0)
        filtered_df=event_df.copy(); filtered_df=filtered_df[filtered_df.Severity.isin(sev_sel)] if sev_sel else filtered_df; filtered_df=filtered_df[filtered_df.Zone.isin(zone_sel)] if zone_sel else filtered_df; filtered_df=filtered_df[filtered_df['Historical Label']==label_sel] if label_sel!='All' else filtered_df
        filtered_display=filtered_df.copy()
        if filtered_display.empty: st.info('No events match the selected filters.')
        else:
            for c in ['Peak Date','Trough Date']: filtered_display[c]=pd.to_datetime(filtered_display[c]).dt.strftime('%Y-%m-%d')
            for c in ['Peak Index','Trough Index','Drawdown %','Recovery Return %','Z @ Peak','Z @ Trough']: filtered_display[c]=filtered_display[c].astype(float).round(2)
            st.dataframe(filtered_display,use_container_width=True,hide_index=True); st.download_button('⬇️ Export Filtered Crash Events CSV',filtered_display.to_csv(index=False),file_name='filtered_crash_events_phase2.csv',mime='text/csv')
        src=filtered_df if not filtered_df.empty else event_df
        def event_label(row): return f'{row["Historical Label"]} | {pd.to_datetime(row["Peak Date"]).strftime("%Y-%m-%d")} > {pd.to_datetime(row["Trough Date"]).strftime("%Y-%m-%d")} ({row["Drawdown %"]:.1f}%)'
        labels=[event_label(rw) for _,rw in src.iterrows()]
        st.markdown('## 📌 Selected Event Deep Dive'); chosen_event=st.selectbox('Historical Crash Explorer',labels,index=0); show_deep=st.toggle('Show Selected Event Deep Dive',value=True)
        if show_deep and labels:
            row=src.iloc[labels.index(chosen_event)]; peak_date=pd.to_datetime(row['Peak Date']); trough_date=pd.to_datetime(row['Trough Date']); entry=safe_float(row['Trough Index']); z_peak=row.get('Z @ Peak',np.nan); z_trough=row.get('Z @ Trough',np.nan); inv_one=st.number_input('Investment for selected event (S$)',min_value=1000.0,value=15000.0,step=1000.0); val_today=inv_one*(cur/entry) if entry else 0; ret_today=(val_today/inv_one-1)*100 if inv_one else 0
            d1,d2,d3,d4,d5,d6=st.columns(6); d1.metric('Deployment Amount',f'S${inv_one:,.0f}'); d2.metric('Entry Level',f'{entry:,.0f}'); d3.metric('Value Today',f'S${val_today:,.0f}'); d4.metric('Return Since Trough',f'{ret_today:.1f}%'); d5.metric('Z @ Peak','N/A' if pd.isna(z_peak) else f'{z_peak:+.2f}'); d6.metric('Z @ Trough','N/A' if pd.isna(z_trough) else f'{z_trough:+.2f}')
            st.info(f'This event was classified as: {row["Valuation Classification"]}. Historical label: {row["Historical Label"]}.')
            cs=ud.loc[peak_date:trough_date].copy(); zpath=pd.Series(dtype=float)
            if valuation_tc is not None and valuation_tc.get('data') is not None: zpath=valuation_tc['data']['ZHist'].dropna().loc[peak_date:trough_date]
            if not cs.empty:
                fig=go.Figure(); fig.add_trace(go.Scatter(x=cs.index,y=cs.Close,mode='lines',line=dict(color=RED,width=2),name='Price path',yaxis='y1')); fig.add_trace(go.Scatter(x=[peak_date],y=[safe_float(row['Peak Index'])],mode='markers+text',text=['Peak'],textposition='top center',marker=dict(size=8,color=BLUE),name='Peak',yaxis='y1')); fig.add_trace(go.Scatter(x=[trough_date],y=[entry],mode='markers+text',text=['Trough'],textposition='bottom center',marker=dict(size=8,color=RED),name='Trough',yaxis='y1'))
                if not zpath.empty: fig.add_trace(go.Scatter(x=zpath.index,y=zpath.values,mode='lines',line=dict(color=PURPLE,width=2,dash='dot'),name='OOS Z-Score',yaxis='y2'))
                fig.update_layout(height=320,margin=dict(l=10,r=10,t=10,b=10),plot_bgcolor='white',paper_bgcolor='white',legend=dict(orientation='h'),yaxis=dict(title='Index Level'),yaxis2=dict(title='Z-Score',overlaying='y',side='right',showgrid=False)); st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
        with st.expander('🧪 Master Crash Deployment Simulator',expanded=True):
            s1,s2,s3=st.columns([1,1,1]); inv=s1.number_input('Investment per event (S$)',min_value=1000.0,value=10000.0,step=1000.0); end_date=s2.date_input('Simulation end date',value=ud.index.max().date(),min_value=ud.index.min().date(),max_value=ud.index.max().date()); use_filtered=s3.checkbox('Use currently filtered events only',value=True)
            end_slice=ud.loc[:pd.Timestamp(end_date)]
            if end_slice.empty: st.info('No end-date price available.'); return
            end_index=safe_float(end_slice.Close.iloc[-1]); sim_base=filtered_df.copy() if use_filtered and not filtered_df.empty else event_df.copy(); sim=sim_base[pd.to_datetime(sim_base['Trough Date'])<=pd.Timestamp(end_date)].copy()
            if sim.empty: st.info('No events before selected end date.'); return
            sim['Investment Amount']=inv; sim['End Index']=end_index; sim['Ending Value']=inv*(sim['End Index']/sim['Trough Index']); sim['Gain / Loss']=sim['Ending Value']-sim['Investment Amount']; sim['Return %']=(sim['Ending Value']/sim['Investment Amount']-1)*100; sim['Holding Days']=(pd.Timestamp(end_date)-pd.to_datetime(sim['Trough Date'])).dt.days.clip(lower=0)
            total=sim['Investment Amount'].sum(); ending=sim['Ending Value'].sum(); gain=ending-total; tr=(ending/total-1)*100 if total else 0; m1,m2,m3,m4,m5=st.columns(5); m1.metric('Deployments',len(sim)); m2.metric('Capital Deployed',f'S${total:,.0f}'); m3.metric('Ending Value',f'S${ending:,.0f}'); m4.metric('Total Gain / Loss',f'S${gain:,.0f}'); m5.metric('Total Return',f'{tr:.1f}%')
            sim_display=sim[['Trough Date','Historical Label','Severity','Zone','Valuation Classification','Z @ Trough','Trough Index','End Index','Investment Amount','Ending Value','Gain / Loss','Return %','Holding Days']].copy(); sim_display['Trough Date']=pd.to_datetime(sim_display['Trough Date']).dt.strftime('%Y-%m-%d')
            for c in ['Z @ Trough','Trough Index','End Index','Investment Amount','Ending Value','Gain / Loss','Return %']: sim_display[c]=sim_display[c].astype(float).round(2)
            st.dataframe(sim_display,use_container_width=True,hide_index=True); st.download_button('⬇️ Export Master Simulator CSV',sim_display.to_csv(index=False),file_name='master_crash_simulator_phase2.csv',mime='text/csv')

def render_audit(expanded=False):
    with st.expander('📡 AUDIT TRAIL & EXPORT',expanded=expanded):
        left,right=st.columns([1,1])
        left.markdown('#### 📡 Data Source & Freshness'); left.markdown('<div class="light-card">'+kv('Market Data','Yahoo Finance',BLUE)+kv('PMI Proxy',st.session_state.get('pmi_proxy_label',pmi_label),GREEN)+kv('PMI Value',f'{st.session_state.get("latest_pmi_value",latest_pmi):.1f} · {st.session_state.get("latest_pmi_month","")}',GREEN)+kv('PMI Source',st.session_state.get('latest_pmi_source',pmi_proxy_default['source']),GREEN)+kv('Risk Model','Alternative asset' if sel in PMI_NA_MARKETS else 'Equity macro',PURPLE)+kv('Valuation Model','Expanding Window (OOS – default)',PURPLE)+kv('Bias Status','No look-ahead bias for OOS valuation model',GREEN)+kv('Last Refreshed',datetime.now().strftime('%d %b %Y %H:%M SGT'),SLATE)+'</div>',unsafe_allow_html=True)
        right.markdown('#### 🧾 Methodology Notes'); right.markdown('- Live Risk Score is rules-based and not a crash prediction.\n- PMI is monthly, not intraday live data.\n- US PMI is fetched from FRED only when Update PMI is clicked.\n- Non-US PMI uses manual input with pre-filled 12M defaults.\n- Gold / Bitcoin use the alternative-asset risk model; PMI is not applicable.\n- Phase 2 default valuation model is Expanding Window (OOS) to reduce look-ahead bias.\n- Full-history regression remains available as collapsible research-only reference.')
        snap=pd.DataFrame([{'Timestamp':datetime.now().strftime('%Y-%m-%d %H:%M:%S SGT'),'Selected Index':index_label,'Ticker':ticker,'Drawdown Reference':ref,'Current Drawdown %':round(dd,2),'Action Zone':zone,'Suggested Deploy S$':round(deploy,2),'Funding Source':funding_source,'PMI Proxy':st.session_state.get('pmi_proxy_label',pmi_label),'PMI Value':st.session_state.get('latest_pmi_value',latest_pmi),'Live Risk Score':round(live_score,1),'Risk Regime':alert,'Risk Model':'Alternative asset' if sel in PMI_NA_MARKETS else 'Equity macro','Valuation Model':'Expanding Window (OOS)','Valuation Z-Score':exec_z_score,'Bias Status':'No look-ahead bias for OOS valuation model','Signal Confidence':conf_label}])
        st.markdown('#### 📤 Tactical Snapshot Export'); st.dataframe(snap,use_container_width=True,hide_index=True); st.download_button('⬇️ Export Tactical Snapshot CSV',snap.to_csv(index=False),file_name='tactical_snapshot_phase2.csv',mime='text/csv')

RENDERERS={'💰 Suggested Deploy':render_suggested,'🌦️ Market Conditions':render_market,'📊 Market Performance':render_performance,'🏆 Crash Analytics':render_crash,'📡 Audit Trail & Export':render_audit}
render_executive()
if active_section != '🧠 Executive Centre': RENDERERS[active_section](expanded=True)
for section in SECTION_ORDER:
    if section != active_section: RENDERERS[section](expanded=False)
st.markdown('---'); st.caption(f'🕒 Last refreshed: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} SGT'); st.caption('⚠️ Disclaimer: Educational only. Not financial advice. Past performance does not guarantee future results. Consult a licensed adviser.')
