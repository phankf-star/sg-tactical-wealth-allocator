
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
div[data-testid="stMetric"] {background:white; border:1px solid #E5E7EB; border-radius:16px; padding:14px 16px; box-shadow:0 1px 2px rgba(15,23,42,.05);}
.light-card {background:#fff; border:1px solid #E5E7EB; border-radius:16px; padding:14px 16px; box-shadow:0 1px 2px rgba(15,23,42,.05); margin-bottom:10px;}
.kv {display:flex; justify-content:space-between; border-bottom:1px solid #F3F4F6; padding:6px 0; gap:12px;}
.kv:last-child {border-bottom:0;}
.kv-label {color:#6B7280; font-size:.88rem;}
.kv-value {font-weight:650; color:#111827; text-align:right;}
.warn-box {background:#FFFBEB; border:1px solid #FDE68A; border-radius:14px; padding:12px 14px; color:#92400E;}
.info-box {background:#EFF6FF; border:1px solid #BFDBFE; border-radius:14px; padding:12px 14px; color:#1E3A8A;}

/* v36o light sidebar + mock-up styling */
section[data-testid="stSidebar"] {background:#F8FAFC; border-right:1px solid #E5E7EB;}
section[data-testid="stSidebar"] * {color:#111827;}
section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small {color:#64748B !important;}
section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] textarea, section[data-testid="stSidebar"] select {color:#111827 !important; background:#FFFFFF !important;}
section[data-testid="stSidebar"] [data-baseweb="select"] * {color:#111827 !important;}
.currency-pill {display:inline-flex; align-items:center; gap:8px; background:#ECFDF5; color:#047857; border:1px solid #A7F3D0; border-radius:8px; padding:5px 9px; font-weight:750; font-size:.84rem; margin:4px 0 8px 0;}
.mock-control-card {background:#fff; border:1px solid #E5E7EB; border-radius:10px; padding:10px 12px; min-height:74px; box-shadow:0 1px 2px rgba(15,23,42,.04);}
.mock-label {color:#6B7280; font-size:.78rem; font-weight:700; margin-bottom:5px;}
.mock-value {color:#111827; font-size:1.05rem; font-weight:850;}
.mock-sub {color:#6B7280; font-size:.75rem; margin-top:3px;}
.risk-alert {border-radius:10px; padding:12px 14px; font-weight:750; margin:10px 0 14px 0;}
.risk-alert-normal {background:#ECFDF5; border:1px solid #BBF7D0; color:#166534;}
.risk-alert-watch {background:#FFFBEB; border:1px solid #FDE68A; color:#92400E;}
.risk-alert-warning {background:#FFF7ED; border:1px solid #FED7AA; color:#9A3412;}
.risk-alert-crash {background:#FEF2F2; border:1px solid #FECACA; color:#991B1B;}
.kpi-card {background:#fff; border:1px solid #E5E7EB; border-radius:14px; padding:13px 14px; box-shadow:0 1px 2px rgba(15,23,42,.04); min-height:96px;}
.kpi-title {color:#6B7280; font-size:.78rem; font-weight:700;}
.kpi-value {font-size:1.35rem; font-weight:850; color:#111827; margin-top:4px;}
.kpi-sub-green {font-size:.78rem; color:#16A34A; font-weight:750; margin-top:3px;}
.kpi-sub-orange {font-size:.78rem; color:#F97316; font-weight:750; margin-top:3px;}
.kpi-sub-muted {font-size:.78rem; color:#64748B; font-weight:650; margin-top:3px;}


/* Executive Centre tooltip / help text */
.light-card {overflow:visible;}
.exec-title-row {display:flex; align-items:center; gap:7px; color:#6B7280; font-size:.86rem; font-weight:700;}
.exec-info-dot {position:relative; display:inline-flex; align-items:center; justify-content:center; width:17px; height:17px; border-radius:50%; background:#EEF2FF; color:#2563EB; border:1px solid #BFDBFE; font-size:11px; font-weight:900; cursor:help; line-height:1;}
.exec-tooltip {visibility:hidden; opacity:0; position:absolute; z-index:9999; top:24px; left:-10px; width:340px; background:#0F172A; color:#FFFFFF; border-radius:12px; padding:12px 13px; box-shadow:0 16px 40px rgba(15,23,42,.25); transform:translateY(4px); transition:opacity .16s ease, transform .16s ease; text-align:left;}
.exec-tooltip::before {content:""; position:absolute; top:-7px; left:17px; width:14px; height:14px; background:#0F172A; transform:rotate(45deg);}
.exec-info-dot:hover .exec-tooltip, .exec-info-dot:focus .exec-tooltip {visibility:visible; opacity:1; transform:translateY(0);}
.exec-tooltip-title {font-size:13px; font-weight:850; margin-bottom:7px; color:#FFFFFF;}
.exec-tooltip-row {display:grid; grid-template-columns:96px 1fr; gap:8px; font-size:12px; line-height:1.45; margin:4px 0;}
.exec-tooltip-label {color:#CBD5E1; font-weight:700;}
.exec-tooltip-value {color:#FFFFFF; font-weight:650;}
.exec-tooltip-footer {margin-top:8px; padding-top:8px; border-top:1px solid rgba(255,255,255,.16); font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:11.5px; line-height:1.45; color:#E2E8F0;}
.exec-pill {display:inline-flex; align-items:center; gap:6px; margin-top:8px; border-radius:999px; padding:5px 9px; font-size:.78rem; font-weight:750;}
.exec-pill-hold {background:#F0FDF4; border:1px solid #BBF7D0; color:#166534;}
.exec-pill-action {background:#FFFBEB; border:1px solid #FDE68A; color:#92400E;}

</style>
''', unsafe_allow_html=True)

INDEX_TICKERS = {
    'S&P 500':'^GSPC','Nasdaq':'^IXIC','DJIA':'^DJI','HSI':'^HSI','STI':'^STI','KLSE':'^KLSE',
    'A-Share':'000001.SS','Nikkei 225':'^N225','Gold':'GC=F','Bitcoin':'BTC-USD'
}

MARKET_CURRENCY_MAP = {
    'S&P 500':'USD','Nasdaq':'USD','DJIA':'USD','HSI':'HKD','STI':'SGD','KLSE':'MYR',
    'A-Share':'CNY','Nikkei 225':'JPY','Gold':'USD','Bitcoin':'USD'
}
CURRENCY_SYMBOL_MAP = {'USD':'US$','SGD':'S$','HKD':'HK$','MYR':'RM','CNY':'RMB','JPY':'¥'}
CURRENCY_HTML_MAP = {'USD':'US&#36;','SGD':'S&#36;','HKD':'HK&#36;','MYR':'RM','CNY':'RMB','JPY':'¥'}
CURRENCY_NAME_MAP = {'USD':'United States Dollar','SGD':'Singapore Dollar','HKD':'Hong Kong Dollar','MYR':'Malaysian Ringgit','CNY':'Chinese Yuan / RMB','JPY':'Japanese Yen'}

def market_currency_info(market_name):
    code = MARKET_CURRENCY_MAP.get(market_name, 'SGD')
    return code, CURRENCY_SYMBOL_MAP.get(code, '$'), CURRENCY_HTML_MAP.get(code, '$'), CURRENCY_NAME_MAP.get(code, code)
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
NAV_OPTIONS = ['🧠 Executive Centre','💰 Suggested Deploy','🌦️ Market Conditions','🏆 Crash Analytics','📊 Market Performance','📡 Audit Trail & Export']
SECTION_ORDER = ['💰 Suggested Deploy','🌦️ Market Conditions','🏆 Crash Analytics','📊 Market Performance','📡 Audit Trail & Export']
CRISIS_EVENTS = [('1987-08-01','1987-12-31','1987 Black Monday'),('2000-03-01','2002-10-31','2000-2002 Dot-com Bust'),('2007-10-01','2009-03-31','2008 Global Financial Crisis'),('2020-02-01','2020-04-30','2020 COVID-19'),('2022-01-01','2022-10-31','2022 Inflation & Rate Hike')]

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

def hesc(v):
    return str(v).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&#39;')

def kv(label, value, colour=TEXT):
    return f'<div class="kv"><div class="kv-label">{label}</div><div class="kv-value" style="color:{colour};">{value}</div></div>'

def tooltip_html(title, rows=None, footer=None):
    rows = rows or []
    row_html = ''.join([f'<div class="exec-tooltip-row"><span class="exec-tooltip-label">{hesc(k)}</span><span class="exec-tooltip-value">{hesc(v)}</span></div>' for k,v in rows])
    footer_html = f'<div class="exec-tooltip-footer">{footer}</div>' if footer else ''
    return f'<span class="exec-info-dot" tabindex="0">i<span class="exec-tooltip"><div class="exec-tooltip-title">{hesc(title)}</div>{row_html}{footer_html}</span></span>'

def card(title,value,sub,accent,tooltip=None,pill=None):
    info = tooltip or ''
    pill_html = pill or ''
    return f'<div class="light-card" style="border-top:4px solid {accent};"><div class="exec-title-row">{title}{info}</div><div style="font-size:1.55rem;font-weight:800;color:{TEXT};margin-top:4px;">{value}</div><div style="font-size:.82rem;color:{MUTED};margin-top:3px;">{sub}</div>{pill_html}</div>'

def classify(dd):
    # Drawdown Allocation Engine stance only. Do not generate SELL / STRONG SELL
    # from the drawdown module; overvaluation is handled separately by Z-score.
    if dd <= -50: return 'MAX CRISIS BUY', RED
    if dd <= -35: return 'CRISIS BUY', '#DC2626'
    if dd <= -25: return 'STRONG BUY', ORANGE
    if dd <= -15: return 'BUY', AMBER
    if dd <= -8: return 'INITIAL BUY', BLUE
    return 'HOLD / NO DEPLOYMENT', SLATE

def severity_bucket(dd):
    a=abs(dd)
    if a<10: return 'Below 10% move'
    if a<20: return '10-20% correction'
    if a<30: return '20-30% bear drawdown'
    if a<40: return '30-40% crash'
    if a<50: return '40-50% severe crash'
    return '>50% crisis crash'

def years_between(start_date, end_date):
    try:
        return max((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days / 365.25, 0.0)
    except Exception:
        return 0.0

def frequency_label(event_count, observation_years):
    if event_count <= 0:
        return 'Frequency: not observed'
    if observation_years <= 0:
        return 'Frequency: insufficient history'
    yrs = observation_years / event_count
    if yrs < 1:
        months = max(1, round(yrs * 12))
        return f'Frequency: ~{months} mths/event'
    return f'Frequency: ~{yrs:.1f} yrs/event'

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


def current_dd_detail(df, method):
    """Secondary diagnostic drawdown with peak/current date details. Diagnostic only."""
    c=safe_float(df.Close.iloc[-1]); current_date=df.index[-1]
    if method.startswith('Rolling'): days,label=252,'Rolling 252D Peak'
    elif method.startswith('2Y'): days,label=504,'2Y Peak'
    elif method.startswith('3Y'): days,label=756,'3Y Peak'
    elif method.startswith('5Y'): days,label=1260,'5Y Peak'
    else:
        peak_date=df.Close.idxmax(); peak=safe_float(df.loc[peak_date,'Close'],c)
        return c,peak,((c-peak)/peak)*100 if peak else 0,'All-Time High Peak',pd.Timestamp(peak_date),pd.Timestamp(current_date)
    window=df.tail(days)
    peak_date=window.Close.idxmax(); peak=safe_float(window.loc[peak_date,'Close'],c)
    return c,peak,((c-peak)/peak)*100 if peak else 0,label,pd.Timestamp(peak_date),pd.Timestamp(current_date)

def deploy_rule(dd):
    # Cumulative deployment of available investible capital / dry powder.
    if dd <= -50: return 1.00
    if dd <= -35: return .75
    if dd <= -25: return .50
    if dd <= -15: return .25
    if dd <= -8: return .10
    return 0.0

def capital_breakdown(zone, deploy_amount, available_cash, available_srs, available_cpf):
    cash=srs=cpf=0.0
    if deploy_amount <= 0: return cash,srs,cpf,'Current allocation stance does not trigger deployment; investible capital is preserved.'
    cash=min(deploy_amount, available_cash); rem=max(deploy_amount-cash,0)
    if zone in ['BUY','STRONG BUY','CRISIS BUY','MAX CRISIS BUY']:
        srs=min(rem,available_srs); rem=max(rem-srs,0)
    if zone in ['STRONG BUY','CRISIS BUY','MAX CRISIS BUY']:
        cpf=min(rem,available_cpf)
    reason = (
        'INITIAL BUY zone uses investible cash first; SRS/CPF-OA are preserved for deeper drawdowns.' if zone=='INITIAL BUY' else
        'BUY zone uses investible cash first, then SRS if cash is insufficient. CPF-OA remains reserved.' if zone=='BUY' else
        'STRONG BUY zone can use investible cash, SRS and CPF-OA above preserved floor.' if zone=='STRONG BUY' else
        'CRISIS BUY zone deploys 75% of investible capital using cash, SRS and CPF-OA above preserved floor.' if zone=='CRISIS BUY' else
        'MAX CRISIS BUY zone deploys 100% of investible dry powder after excluding safeguards.'
    )
    return cash,srs,cpf,reason

def next_trigger_label(zone):
    if zone == 'HOLD / NO DEPLOYMENT': return 'Initial buy zone near -8% to -10% drawdown'
    if zone=='INITIAL BUY': return 'BUY zone if drawdown deepens toward -15%'
    if zone=='BUY': return 'STRONG BUY zone if drawdown deepens beyond -25%'
    if zone=='STRONG BUY': return 'CRISIS BUY zone if drawdown deepens beyond -35%'
    if zone=='CRISIS BUY': return 'MAX CRISIS BUY if drawdown deepens beyond -50%'
    return 'Already in maximum deployment zone'

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
        label='曾氏通道 — Full-History Secular Channel (Research Only)'; bias='Uses full sample; contains look-ahead bias for historical signals'
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
            latest=monthly.iloc[max(0,len(monthly)-roll_m):]; label=f'Rolling OOS Valuation Channel — {rolling_years}Y Adaptive Window'; bias='No look-ahead bias; each point uses only its rolling historical window'
        else:
            latest=monthly; label='OOS Expanding Valuation Channel (Live Quant Model)'; bias='No look-ahead bias; each point uses only data available up to that date'
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


def label_extreme(date):
    y = pd.Timestamp(date).year
    if 1987 <= y <= 1988: return 'Black Monday'
    if 1997 <= y <= 1998: return 'Asian Financial Crisis'
    if 2000 <= y <= 2002: return 'Dot-com Bust'
    if 2007 <= y <= 2009: return 'GFC Peak/Bottom'
    if y == 2020: return 'COVID-19 Shock'
    if 2021 <= y <= 2022: return 'Inflation & Rate Hike'
    return f'Market Event ({y})'

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


def overlaps_event_window(peak_date, trough_date, start, end):
    peak_date = pd.Timestamp(peak_date); trough_date = pd.Timestamp(trough_date)
    start = pd.Timestamp(start); end = pd.Timestamp(end)
    return peak_date <= end and trough_date >= start

def label_event_window(peak_date, trough_date, drawdown_pct, recovery_return_pct=None):
    if overlaps_event_window(peak_date, trough_date, '1987-08-01', '1987-12-31'): return '1987 Black Monday'
    if overlaps_event_window(peak_date, trough_date, '1990-07-01', '1991-03-31'): return 'Gulf War / 1990 Oil Shock'
    if overlaps_event_window(peak_date, trough_date, '1997-07-01', '1998-12-31'): return 'Asian Financial Crisis'
    if overlaps_event_window(peak_date, trough_date, '2000-03-01', '2003-03-31'): return 'Dot-com Bust / Corporate Scandals'
    if overlaps_event_window(peak_date, trough_date, '2007-10-01', '2009-03-31'): return 'Global Financial Crisis'
    if overlaps_event_window(peak_date, trough_date, '2011-07-01', '2011-12-31'): return 'Eurozone / US Debt Scare'
    if overlaps_event_window(peak_date, trough_date, '2015-06-01', '2016-03-31'): return 'China Devaluation / Oil Shock'
    if overlaps_event_window(peak_date, trough_date, '2018-01-01', '2018-12-31'): return 'US-China Trade War'
    if overlaps_event_window(peak_date, trough_date, '2020-02-01', '2020-04-30'): return 'COVID Shock'
    if overlaps_event_window(peak_date, trough_date, '2021-11-01', '2022-12-31'): return 'Inflation & Rate-Hike Cycle'
    if recovery_return_pct is not None and recovery_return_pct >= 200: return 'High-Recovery Technical Correction'
    if abs(float(drawdown_pct)) >= 20: return 'System-Detected Cyclical Drawdown'
    return 'Technical Correction'

STRUCTURAL_EVENT_WINDOWS = [
    ('1987 Black Monday','1987-08-01','1987-12-31'),
    ('Gulf War / 1990 Oil Shock','1990-07-01','1991-03-31'),
    ('Asian Financial Crisis','1997-02-01','1998-12-31'),
    ('Dot-com Bust / Corporate Scandals','2000-03-01','2003-03-31'),
    ('Global Financial Crisis','2007-10-01','2009-03-31'),
    ('Eurozone / US Debt Scare','2011-07-01','2011-12-31'),
    ('China Devaluation / Oil Shock','2015-06-01','2016-03-31'),
    ('US-China Trade War','2018-01-01','2018-12-31'),
    ('COVID Shock','2020-02-01','2020-04-30'),
    ('Inflation & Rate-Hike Cycle','2021-11-01','2022-12-31'),
]


def structural_event_window_for_date(target_date):
    t=pd.Timestamp(target_date)
    for label,start,end in STRUCTURAL_EVENT_WINDOWS:
        if pd.Timestamp(start) <= t <= pd.Timestamp(end):
            return label,pd.Timestamp(start),pd.Timestamp(end)
    return None,None,None


def find_structural_peak(bt, trough_date, max_lookback_days=756):
    if bt is None or bt.empty or trough_date not in bt.index:
        return pd.Timestamp(trough_date),np.nan,'invalid_input'
    loc=bt.index.get_loc(trough_date); start_loc=max(0,loc-int(max_lookback_days))
    prior=bt.iloc[start_loc:loc+1]
    if prior.empty:
        return pd.Timestamp(trough_date),safe_float(bt.loc[trough_date,'Close']),'fallback_same_day_trough'
    pkdt=prior.Close.idxmax(); peak=safe_float(prior.loc[pkdt,'Close'])
    if pd.Timestamp(pkdt)>=pd.Timestamp(trough_date):
        prior_only=bt.iloc[start_loc:loc]
        if prior_only.empty: return pd.Timestamp(trough_date),safe_float(bt.loc[trough_date,'Close']),'fallback_same_day_trough'
        pkdt=prior_only.Close.idxmax(); peak=safe_float(prior_only.loc[pkdt,'Close'])
        return pd.Timestamp(pkdt),peak,'causal_fallback_prior_peak'
    return pd.Timestamp(pkdt),peak,'bounded_lookback_limit'


def find_mapped_structural_peak(bt, trough_date, mapped_start):
    t=pd.Timestamp(trough_date); start=pd.Timestamp(mapped_start)
    window=bt.loc[start:t].copy()
    if window.empty: return find_structural_peak(bt,t)
    pkdt=window.Close.idxmax(); peak=safe_float(window.loc[pkdt,'Close'])
    if pd.Timestamp(pkdt)>=t:
        prior=window.loc[:t].iloc[:-1]
        if prior.empty: return find_structural_peak(bt,t)
        pkdt=prior.Close.idxmax(); peak=safe_float(prior.loc[pkdt,'Close'])
    return pd.Timestamp(pkdt),peak,'mapped_structural_event_window'


def current_structural_dd(df, max_lookback_days=756):
    """Primary current drawdown for Executive Centre and Market Conditions."""
    if df is None or df.empty:
        return np.nan,np.nan,0.0,'Structural Drawdown',pd.NaT,pd.NaT,'no_data'
    bt=df[['Close']].copy().dropna(); bt.index=pd.to_datetime(bt.index)
    cur_date=bt.index[-1]; cur=safe_float(bt.Close.iloc[-1])
    mapped_label,mapped_start,mapped_end=structural_event_window_for_date(cur_date)
    if mapped_label:
        pkdt,peak,boundary=find_mapped_structural_peak(bt,cur_date,mapped_start); basis=f'Structural Drawdown · {mapped_label}'
    else:
        pkdt,peak,boundary=find_structural_peak(bt,cur_date,max_lookback_days=max_lookback_days); basis='Structural Drawdown · bounded causal peak'
    ddv=((cur-peak)/peak)*100 if peak else 0.0
    return cur,peak,ddv,basis,pkdt,cur_date,boundary


def crash_events(bt, thr, current, valuation_tc=None, max_lookback_days=756, recovery_exit_pct=5, min_event_gap_days=60):
    ev=[]; in_dd=False; start=None
    if bt is None or bt.empty: return pd.DataFrame(ev)
    for i in range(len(bt)):
        dv=safe_float(bt.dd_pct.iloc[i])
        if dv <= -thr and not in_dd:
            in_dd=True; start=i
        elif (dv > -abs(recovery_exit_pct) and in_dd) or (i==len(bt)-1 and in_dd):
            in_dd=False; e=bt.iloc[start:i+1]
            if e.empty: continue
            ti=e.dd_pct.idxmin(); row=bt.loc[ti]
            mapped_label,mapped_start,mapped_end=structural_event_window_for_date(ti)
            if mapped_label: pkdt,structural_peak,boundary_reason=find_mapped_structural_peak(bt,ti,mapped_start)
            else: pkdt,structural_peak,boundary_reason=find_structural_peak(bt,ti,max_lookback_days=max_lookback_days)
            if len(ev)>0:
                if mapped_label and any(x.get('Historical Label')==mapped_label for x in ev):
                    existing_idx=[j for j,x in enumerate(ev) if x.get('Historical Label')==mapped_label][0]
                    existing_dd=safe_float(ev[existing_idx].get('Drawdown %',0)); tmp_price=safe_float(row.Close); tmp_dd=((tmp_price/structural_peak)-1)*100 if structural_peak else safe_float(row.dd_pct)
                    if tmp_dd < existing_dd: ev.pop(existing_idx)
                    else: continue
                elif (pd.Timestamp(ti)-pd.Timestamp(ev[-1]['Trough Date'])).days<min_event_gap_days:
                    continue
            price=safe_float(row.Close); ddv=((price/structural_peak)-1)*100 if structural_peak else safe_float(row.dd_pct)
            zone,_=classify(ddv); recovery=((current/price)-1)*100 if price else 0
            zp=get_z_at(valuation_tc, pkdt) if valuation_tc is not None else np.nan; zt=get_z_at(valuation_tc, ti) if valuation_tc is not None else np.nan
            detected_start=e.index.min(); detected_end=e.index.max(); duration=max((pd.Timestamp(ti)-pd.Timestamp(pkdt)).days,0)
            label=mapped_label if mapped_label else label_event_window(pkdt,ti,ddv,recovery)
            ev.append({'Peak Date':pkdt,'Peak Index':structural_peak,'Trough Date':ti,'Trough Index':price,'Drawdown %':ddv,'Recovery Return %':recovery,'Zone':zone,'Historical Label':label,'Severity':severity_bucket(ddv),'Duration Days':duration,'Detected Window Start':detected_start,'Detected Window End':detected_end,'Peak Selection Rule':'mapped structural window' if mapped_label else 'bounded backward causal search','Boundary Reason':boundary_reason,'Lookback Cap Days':int(max_lookback_days),'Z @ Peak':zp,'Z @ Trough':zt,'Valuation Classification':crash_valuation_classification(zp,zt)})
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
    currency_code,currency_symbol,currency_html,currency_name=market_currency_info(sel)
    st.session_state.currency_text=currency_symbol
    st.session_state.currency_html=currency_html
    st.markdown('### 💰 Investible Capital & Safeguards')
    st.caption('Investible capital excludes emergency funds. This platform is for decision support only and should not be relied on as a sole trading or investment instruction.')
    st.markdown(f'<div class="currency-pill">{currency_symbol} &nbsp; {currency_name}</div>', unsafe_allow_html=True)
    if sel == 'STI':
        include_srs=st.toggle('Include SRS in investible capital',value=False,key='include_srs_sti')
        include_cpf_oa=st.toggle('Include CPF-OA in investible capital',value=False,key='include_cpf_oa_sti')
        funding_parts=['S$ Cash']
        if include_srs: funding_parts.append('SRS')
        if include_cpf_oa: funding_parts.append('CPF-OA')
        funding_profile=' + '.join(funding_parts)
        st.caption(f'Funding Profile: {funding_profile}')
        cash_balance=st.number_input(f'Investible Cash ({currency_symbol})',0.0,value=100000.0,step=5000.0)
        srs_balance=0.0; cpf_oa_balance=0.0; preserve_cpf=False
        if include_srs:
            srs_balance=st.number_input('Investible SRS (S$)',0.0,value=35000.0,step=5000.0)
        if include_cpf_oa:
            cpf_oa_balance=st.number_input('CPF-OA Balance (S$)',0.0,value=180000.0,step=5000.0)
            preserve_cpf=st.checkbox('Exclude S$20k CPF-OA Minimum Floor',value=True)
    else:
        funding_profile=f'{currency_symbol} Investible Cash'
        st.caption(f'Funding Profile: {funding_profile}')
        cash_balance=st.number_input(f'Investible Cash ({currency_symbol})',0.0,value=100000.0,step=5000.0)
        srs_balance=0.0; cpf_oa_balance=0.0; preserve_cpf=False
    emergency_buffer=0.0
    st.session_state.funding_profile=funding_profile
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

close,peak,dd,ref,struct_peak_date,struct_current_date,struct_boundary=current_structural_dd(ud)
zone,zc=classify(dd); deploy_pct=deploy_rule(dd)
available_cash=max(cash_balance,0); available_srs=srs_balance; available_cpf=max(cpf_oa_balance-(20000 if preserve_cpf else 0),0); total_available=available_cash+available_srs+available_cpf; deploy=total_available*deploy_pct
cash_deploy,srs_deploy,cpf_deploy,capital_reason=capital_breakdown(zone,deploy,available_cash,available_srs,available_cpf); funding_source='Cash First' if cash_deploy>0 else 'No deployment'
macro=live_macro_data(); vix=macro.get('vix'); tnx=macro.get('tnx'); irx=macro.get('irx'); curve_spread=(tnx-irx) if (tnx is not None and irx is not None) else None
trend_below=close<m[sel]['ma200']; pmi_label=pmi_proxy_default['label']; latest_pmi=float(st.session_state.get('latest_pmi_value', pmi_proxy_default['default'])); pmi_applicable=sel not in PMI_NA_MARKETS
live_score,alert,vix_s,curve_s,pmi_s,dd_s,trend_s=calc_market_scores_by_asset(sel,latest_pmi,dd,trend_below,vix,curve_spread)
conf_score=confidence_score(dd,live_score,trend_below); conf_label=confidence_label(conf_score); decision_line=f'Deploy approximately {fmt_sgd(deploy)} using staged tranches.' if deploy>0 else 'No deployment now. Capital is preserved until a deployment trigger appears.'; next_trigger=next_trigger_label(zone)
_exec_tc=build_trend_channel(ud,2040,model='Expanding Window',rolling_years=15); exec_z_score=float(_exec_tc['z_score']) if _exec_tc is not None else None; exec_valuation_zone,exec_valuation_colour=valuation_status(exec_z_score)

st.title('📉 Global Drawdown Allocation Engine')
st.caption('v36 Phase 2 · Multi-asset drawdown allocation platform with OOS valuation model, crash-context analytics and audit-ready transparency.')

# ------------------------- renderers -------------------------
def render_executive():
    st.markdown('---'); st.markdown('## 🧠 Executive Tactical Allocation Centre')
    structural_tip=tooltip_html(
        'Structural Drawdown Method',
        [('Basis',ref.replace('Structural Drawdown · ','')),('Peak',f'{struct_peak_date.strftime("%Y-%m-%d")} · {peak:,.0f}'),('Current',f'{struct_current_date.strftime("%Y-%m-%d")} · {close:,.0f}')],
        'Formula:<br>(current close − structural peak) ÷ structural peak'
    )
    stance_tip=tooltip_html(
        'Decision Rule Explanation',
        [('Current Zone',zone),('Deploy Rule',f'{deploy_pct:.0%} cumulative deploy'),('Next Trigger',next_trigger)],
        f'Decision note:<br>{hesc(decision_line)}'
    )
    structural_colour = zc if zone != 'HOLD / NO DEPLOYMENT' else SLATE
    action_colour = zc if zone != 'HOLD / NO DEPLOYMENT' else SLATE
    if deploy>0:
        stance_pill=f'<div class="exec-pill exec-pill-action">✓ Deployment active · {deploy_pct:.0%} cumulative</div>'
        deploy_sub=f'{deploy_pct:.0%} cumulative · {funding_source}'
    else:
        stance_pill='<div class="exec-pill exec-pill-hold">✓ Capital preserved · Next trigger near -8%</div>'
        deploy_sub='No deployment triggered'
    r1=st.columns(3)
    r1[0].markdown(card(index_label,f'{close:,.0f}',f'{ticker} · Index Level',BLUE),unsafe_allow_html=True)
    r1[1].markdown(card('Current Structural Drawdown',f'{dd:.1f}%',f'Peak {struct_peak_date.strftime("%Y-%m-%d")} · {peak:,.0f}<br>Current {struct_current_date.strftime("%Y-%m-%d")} · {close:,.0f}<br>Basis: {ref.replace("Structural Drawdown · ","")}',structural_colour,tooltip=structural_tip),unsafe_allow_html=True)
    r1[2].markdown(card('Current Allocation Stance',zone,'Drawdown-based deployment rule',action_colour,tooltip=stance_tip,pill=stance_pill),unsafe_allow_html=True)
    r2=st.columns(3)
    r2[0].markdown(card('Suggested Deploy',fmt_sgd(deploy),deploy_sub,AMBER),unsafe_allow_html=True)
    risk_colour=RED if alert=='CRASH RISK' else ORANGE if alert=='WARNING' else AMBER if alert=='WATCH' else GREEN
    model_note='Alternative price model' if sel in PMI_NA_MARKETS else 'Equity macro model'
    r2[1].markdown(card('Risk Regime',alert,f'{model_note} · Score {live_score:.0f}/100',risk_colour),unsafe_allow_html=True)
    z_display='N/A' if exec_z_score is None else f'{exec_z_score:+.2f}'
    r2[2].markdown(card('Valuation Z-Score (OOS)',z_display,f'{exec_valuation_zone} · Expanding Window',exec_valuation_colour),unsafe_allow_html=True)

def render_suggested(expanded=False):
    suggested_title = f'💰 Suggested Deploy Basis & Capital Source — {fmt_sgd(deploy)} Suggested' if deploy>0 else f'💰 Suggested Deploy Basis & Capital Source — {fmt_sgd(0)} / Capital Preserved'
    with st.expander(suggested_title,expanded=expanded):
        s1,s2,s3,s4=st.columns([1,1.15,1,1.1])
        s1.markdown(f'<div class="light-card"><div style="font-weight:700; font-size:1.05rem; margin-bottom:8px;">📌 Suggested Deploy Basis</div><div style="color:#374151; margin-bottom:8px;">Suggested Deploy = Available Deployable Capital × Deployment Rule</div><div style="font-size:1.45rem; font-weight:800; color:#111827; margin:8px 0;">{current_currency_html()}{deploy:,.0f} = {current_currency_html()}{total_available:,.0f} × {deploy_pct:.0%}</div><div style="color:#6B7280; font-size:0.88rem;">Source: selected price data, structural drawdown formula, and sidebar capital inputs.</div></div>', unsafe_allow_html=True)
        s2.markdown('#### 🏦 Capital Source Breakdown')
        show_srs_row = (sel == 'STI' and available_srs > 0)
        show_cpf_row = (sel == 'STI' and available_cpf > 0)
        if show_srs_row and show_cpf_row:
            buy_label='25% cumulative · cash then SRS'
            strong_label='50% cumulative · cash + SRS + CPF-OA'
            initial_reason='INITIAL BUY zone uses investible cash first; SRS/CPF-OA are preserved for deeper drawdowns.'
        elif show_srs_row:
            buy_label='25% cumulative · cash then SRS'
            strong_label='50% cumulative · cash + SRS'
            initial_reason='INITIAL BUY zone uses investible cash first; SRS is preserved for deeper drawdowns.'
        else:
            buy_label='25% cumulative · cash first'
            strong_label='50% cumulative · cash first'
            initial_reason='INITIAL BUY zone uses investible cash first; other funding sources are not included in the selected profile.'
        display_reason = initial_reason if zone == 'INITIAL BUY' else capital_reason
        if sel != 'STI' or (not show_srs_row and not show_cpf_row):
            display_reason = display_reason.replace('SRS/CPF-OA are preserved for deeper drawdowns.','other funding sources are not included in the selected profile.')
            display_reason = display_reason.replace(' then SRS if cash is insufficient. CPF-OA remains reserved.',' first under the selected cash-only profile.')
            display_reason = display_reason.replace('cash, SRS and CPF-OA','cash')
            display_reason = display_reason.replace('using cash, SRS and CPF-OA above preserved floor','using selected investible cash')
        capital_rows=kv('Funding Source',funding_source,GREEN if cash_deploy>0 else SLATE)+kv('Cash Deployment',fmt_sgd(cash_deploy),GREEN)
        if show_srs_row:
            capital_rows += kv('SRS Deployment',fmt_sgd(srs_deploy),SLATE)
        if show_cpf_row:
            capital_rows += kv('CPF-OA Deployment',fmt_sgd(cpf_deploy),SLATE)
        capital_rows += kv('Reason',display_reason,SLATE)
        s2.markdown('<div class="light-card">'+capital_rows+'</div>',unsafe_allow_html=True)
        s3.markdown('#### 🧱 Tranche Deployment Plan')
        if deploy<=0: s3.info('No tranche plan because Suggested Deploy is S$0 under current rule engine.')
        else: s3.markdown('<div class="light-card">'+kv('Tranche 1 — Deploy now',fmt_sgd(deploy*.5),AMBER)+kv('Tranche 2 — If drawdown deepens',fmt_sgd(deploy*.25),ORANGE)+kv('Tranche 3 — If stabilisation appears',fmt_sgd(deploy*.25),BLUE)+'</div>',unsafe_allow_html=True)
        s4.markdown('#### 🧭 Deployment Ladder — Cumulative Investible Capital'); s4.markdown('<div class="light-card">'+kv('HOLD / NO DEPLOYMENT','0% cumulative deploy',SLATE)+kv('INITIAL BUY · -8%','10% cumulative · cash first',BLUE)+kv('BUY · -15%',buy_label,AMBER)+kv('STRONG BUY · -25%',strong_label,ORANGE)+kv('CRISIS BUY · -35%','75% cumulative deploy',RED)+kv('MAX CRISIS BUY · -50%','100% cumulative investible capital',PURPLE)+kv('Next Trigger',next_trigger,ORANGE)+'</div>',unsafe_allow_html=True)
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
    rolling_years=c3.selectbox('Rolling Window Length',[10,15,20],index=1,key='tc_roll_years')
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
    for name,obj in [('OOS Expanding Valuation Channel (Live Quant Model)',exp_tc),('曾氏通道 — Full-History Secular Channel (Research Only)',full_tc)]:
        if obj is not None:
            stt,_=valuation_status(obj['z_score']); comp.append({'Model':name,'Current Z-Score':f'{obj["z_score"]:+.2f}','Interpretation':stt,'Bias Status':'No look-ahead bias' if name.startswith('OOS') else 'Research only / biased historically'})
    if comp: st.markdown('#### 🧭 Valuation Model Comparison'); st.dataframe(pd.DataFrame(comp),use_container_width=True,hide_index=True)
    fig=go.Figure(); fig.add_trace(go.Scatter(x=tdf.index,y=tdf.Close,name=f'{market_name} Price',line=dict(color=BLUE,width=2))); fig.add_trace(go.Scatter(x=tdf.index,y=tdf.TrendPrice,name='Trend',line=dict(color=PURPLE,width=2)))
    for col,label,colour in [('Upper2','+2 SD',RED),('Upper1','+1 SD',AMBER),('Lower1','-1 SD',GREEN),('Lower2','-2 SD','#059669')]: fig.add_trace(go.Scatter(x=tdf.index,y=tdf[col],name=label,line=dict(color=colour,dash='dash',width=1.5)))
    if not proj.empty:
        fig.add_trace(go.Scatter(x=proj.index,y=proj.TrendPrice,name='Projection',line=dict(color=PURPLE,dash='dot',width=1.5),showlegend=False))
    for start,end,label in CRISIS_EVENTS:
        s=pd.Timestamp(start); e=pd.Timestamp(end)
        if tdf.index.min()<=e and s<=tdf.index.max():
            x0=max(s,tdf.index.min()); x1=min(e,tdf.index.max())
            fig.add_vrect(x0=x0,x1=x1,fillcolor='rgba(34,197,94,.055)',line_width=0,layer='below')
            mid=x0+(x1-x0)/2
            parts=label.split(' ',1); event_year=parts[0]; event_name=parts[1] if len(parts)>1 else ''
            fig.add_annotation(x=mid,y=.96,yref='paper',text=f'<b>{event_year}</b><br>{event_name}',showarrow=False,font=dict(size=10,color='#111827'),align='center',bgcolor='rgba(255,255,255,.78)',borderwidth=0,borderpad=2)
    fig.add_vline(x=tdf.index[-1],line_dash='dash',line_color=RED,line_width=1.5); fig.add_annotation(x=tdf.index[-1],y=.95,yref='paper',text=f'<b>Today</b><br>{tdf.index[-1].strftime("%b %d, %Y")}',showarrow=False,font=dict(size=11,color=RED),bgcolor='rgba(255,255,255,.92)',bordercolor=RED,borderwidth=1,borderpad=3)
    chart_title = f'{market_name} 曾氏通道 — Full-History Secular Channel' if model == 'Full History' else (f'{market_name} Rolling OOS Valuation Channel — {rolling_years}Y Window' if model.startswith('Rolling') else f'{market_name} OOS Expanding Valuation Channel')
    fig.update_layout(height=620,title=dict(text=f'<b>{chart_title}</b> — {freq}, {tc["model_label"]}',font=dict(size=15)),yaxis_type='log',yaxis_title='Price (Log Scale)',plot_bgcolor='white',paper_bgcolor='white',margin=dict(l=10,r=90,t=60,b=10),legend=dict(orientation='h',yanchor='bottom',y=-.13,xanchor='center',x=.5,font=dict(size=10)))
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
    r2c1,r2c2,r2c3=st.columns([1,1.2,1])
    section_header = '<div style="height:34px;display:flex;align-items:center;margin:0 0 8px 0;font-size:1.05rem;font-weight:800;color:#111827;">{title}</div>'
    rows=[('Current Price',f'{tdf.Close.iloc[-1]:,.2f}',TEXT),('Trend Value',f'{tdf.TrendPrice.iloc[-1]:,.2f}',PURPLE),('Distance from Trend',f'{dist:+.1f}%',ORANGE if dist>0 else GREEN),('Z-Score',f'{z:+.2f}',status_colour),('Valuation Zone',status,status_colour),('Historical Percentile',f'{tc["pct_rank"]:.0f}th',TEXT),('Regression CAGR',f'{tc["reg_cagr"]:.2f}%',TEXT),('Actual CAGR',f'{tc["actual_cagr"]:.2f}%',TEXT),('Model',tc['model_label'],BLUE)]
    with r2c1:
        st.markdown(section_header.format(title='📋 Current Valuation Summary'),unsafe_allow_html=True)
        st.markdown('<div class="light-card" style="margin-top:0;">'+''.join([kv(a,b,c) for a,b,c in rows])+'</div>',unsafe_allow_html=True)
    with r2c2:
        st.markdown(section_header.format(title='📈 Historical Z-Score'),unsafe_allow_html=True)
        zfig=go.Figure(); zfig.add_trace(go.Scatter(x=tdf.index,y=tdf.ZHist,mode='lines',line=dict(color=BLUE,width=1.5),fill='tozeroy',fillcolor='rgba(37,99,235,.12)'))
        for lv,colour in [(2,RED),(1,AMBER),(0,SLATE),(-1,GREEN),(-2,'#059669')]: zfig.add_hline(y=lv,line_dash='dash',line_color=colour,line_width=1)
        zfig.update_layout(height=300,margin=dict(l=10,r=10,t=0,b=10),plot_bgcolor='white',paper_bgcolor='white',showlegend=False,yaxis_title='Z-Score')
        st.plotly_chart(zfig,use_container_width=True,config={'displayModeBar':False})
    with r2c3:
        st.markdown(section_header.format(title='🎯 Tactical Implication'),unsafe_allow_html=True)
        vals=tactical_implication(z)
        for emoji,label,value in [('📊','Valuation',vals[0]),('⚠️','Risk Level',vals[1]),('🧭','Suggested Stance',vals[2]),('📈','Deployment Bias',vals[3])]: st.markdown(card(f'{emoji} {label}',value,'Model-derived',GREEN if any(x in value for x in ['Accumulation','Increase','Aggressive','Maximum','Low']) else ORANGE if any(x in value for x in ['Defensive','Reduce','High']) else BLUE),unsafe_allow_html=True)

    # Useful reference tables restored: Historical Extremes and Future Projection
    st.markdown('---')
    ext_col, proj_col = st.columns([1.05, 1.25])
    with ext_col:
        st.markdown('#### 📜 Historical Extremes (Z-Score)')
        ext_rows = []
        for dt, row in tc['extremes'].iterrows():
            stt, _ = valuation_status(row['ZHist'])
            ext_rows.append({
                'Date': dt.strftime('%b %Y'),
                'Event': label_extreme(dt),
                'Z-Score': f"{row['ZHist']:+.2f}",
                'Price': f"{row['Close']:,.0f}",
                'Market State': stt,
            })
        if ext_rows:
            st.dataframe(pd.DataFrame(ext_rows), use_container_width=True, hide_index=True)
        else:
            st.info('No historical extremes available for the selected model/window.')
    with proj_col:
        st.markdown('#### 🔮 Future Projection (Price Scale)')
        proj_rows = []
        if proj is not None and not proj.empty:
            years_to_show = sorted(set([y for y in [2030, 2035, 2040, proj_year] if y <= proj_year]))
            for yr in years_to_show:
                yd = proj.loc[proj.index.year == yr]
                if yd.empty:
                    continue
                yv = yd.iloc[-1]
                proj_rows.append({
                    'Year': yr,
                    'Trend (Mean)': f"{yv['TrendPrice']:,.0f}",
                    '+1 SD (75%)': f"{yv['Upper1']:,.0f}",
                    '+2 SD (95%)': f"{yv['Upper2']:,.0f}",
                    '-1 SD (25%)': f"{yv['Lower1']:,.0f}",
                    '-2 SD (5%)': f"{yv['Lower2']:,.0f}",
                })
        if proj_rows:
            st.dataframe(pd.DataFrame(proj_rows), use_container_width=True, hide_index=True)
        else:
            st.info('No projection rows available for the selected horizon.')

    with st.expander('📚 曾氏通道 — Full-History Secular Channel (Research Only)',expanded=False):
        st.markdown('<div class="warn-box"><b>Research view only:</b> this model uses the full sample and therefore contains look-ahead bias when interpreting historical dates. Useful as secular reference, not live decision-grade model.</div>',unsafe_allow_html=True)
        if full_tc is not None:
            fstat,_=valuation_status(full_tc['z_score']); a,b,c=st.columns(3); a.metric('Full-History Z',f'{full_tc["z_score"]:+.2f}'); b.metric('Full-History Status',fstat); c.metric('Bias Status','Research only')
    return tc

def render_market(expanded=False):
    with st.expander('🌦️ MARKET CONDITIONS & LIVE RISK MONITOR',expanded=expanded):
        st.markdown('## 🌦️ Market Conditions & Live Risk Monitor')
        current_proxy=st.session_state.get('pmi_proxy_label',pmi_proxy_default['label'])
        actual=LATEST_PMI_ACTUALS.get(current_proxy,LATEST_PMI_ACTUALS['N/A'])
        top1,top2,top3=st.columns([1.15,.85,1.05])
        top1.markdown(f'<div class="mock-control-card"><div class="mock-label">Selected Market / Asset</div><div class="mock-value">{index_label}</div><div class="mock-sub">{ticker}</div></div>',unsafe_allow_html=True)
        top2.markdown(f'<div class="mock-control-card"><div class="mock-label">Funding Profile</div><div class="mock-value">{st.session_state.get("funding_profile","")}</div><div class="mock-sub">Investible capital basis</div></div>',unsafe_allow_html=True)
        top3.markdown(f'<div class="mock-control-card"><div class="mock-label">Primary: Structural Drawdown</div><div class="mock-value">{dd:.1f}%</div><div class="mock-sub" style="color:#EA580C;font-weight:800;">Peak {struct_peak_date.strftime("%Y-%m-%d")} · {peak:,.0f}<br>Current {struct_current_date.strftime("%Y-%m-%d")} · {close:,.0f}</div></div>',unsafe_allow_html=True)

        chosen=st.session_state.get('pmi_proxy_label',current_proxy)
        actual=LATEST_PMI_ACTUALS.get(chosen,LATEST_PMI_ACTUALS['N/A'])
        latest_in=float(st.session_state.get('latest_pmi_value',actual['value']))
        month_in=st.session_state.get('latest_pmi_month',actual['month'])
        pmi_app=sel not in PMI_NA_MARKETS
        latest_display=0.0 if not pmi_app else latest_in
        local_score,local_alert,lvix,lcurve,lpmi,ldd,ltrend=calc_market_scores_by_asset(sel,latest_display,dd,trend_below,vix,curve_spread)
        risk_colour=GREEN if local_score<30 else AMBER if local_score<50 else ORANGE if local_score<70 else RED
        live_model_note='Alternative price model' if sel in PMI_NA_MARKETS else 'Equity macro model (VIX + PMI + Yield Curve)'
        k1,k2,k3,k4=st.columns([1,1,1,1])
        k1.markdown(f'<div class="kpi-card"><div class="kpi-title">VIX Live</div><div class="kpi-value">{"N/A" if (vix is None or sel in PMI_NA_MARKETS) else f"{vix:.1f}"}</div><div class="kpi-sub-muted">Volatility regime</div></div>',unsafe_allow_html=True)
        k2.markdown(f'<div class="kpi-card"><div class="kpi-title">Yield Curve</div><div class="kpi-value">{"N/A" if (curve_spread is None or sel in PMI_NA_MARKETS) else f"{curve_spread:.2f}%"}</div><div class="kpi-sub-muted">10Y minus 13W</div></div>',unsafe_allow_html=True)
        k3.markdown(f'<div class="kpi-card"><div class="kpi-title">{chosen}</div><div class="kpi-value">{"N/A" if not pmi_app else f"{latest_in:.1f}"}</div><div class="kpi-sub-green">{month_in}</div></div>',unsafe_allow_html=True)
        k4.markdown(f'<div class="kpi-card"><div class="kpi-title" style="color:{risk_colour};font-weight:900;">LIVE MARKET RISK ALERT:</div><div class="kpi-value">{local_score:.0f} / 100</div><div class="kpi-sub-green" style="font-weight:900;">{local_alert}</div><div class="kpi-sub-muted">{live_model_note}</div></div>',unsafe_allow_html=True)

        st.markdown('---')
        st.markdown('## Drawdown Basis Comparison')
        set_label,set_radio=st.columns([0.14,0.86])
        set_label.markdown('<div style="font-weight:800;color:#475569;font-size:.86rem;padding-top:.35rem;">Secondary Setting</div>',unsafe_allow_html=True)
        with set_radio:
            diag_method=st.radio('Choose comparison lens',['Rolling 252D Peak','2Y Peak','3Y Peak','5Y Peak','All-Time High Peak'],index=0,key='secondary_drawdown_diagnostic_market',horizontal=True,label_visibility='collapsed')
        diag_close,diag_peak,diag_dd,diag_ref,diag_peak_date,diag_current_date=current_dd_detail(ud,diag_method)
        comp1,comp2=st.columns([1,1])
        comp1.markdown(f'<div class="kpi-card"><div class="kpi-title">Primary: Structural Drawdown — Used for Suggested Deploy</div><div class="kpi-value">{dd:.1f}%</div><div class="kpi-sub-orange" style="font-weight:800;">Peak {struct_peak_date.strftime("%Y-%m-%d")} · {peak:,.0f}<br>Current {struct_current_date.strftime("%Y-%m-%d")} · {close:,.0f}</div></div>',unsafe_allow_html=True)
        comp2.markdown(f'<div class="kpi-card"><div class="kpi-title">Secondary: {diag_ref} — Diagnostic only</div><div class="kpi-value">{diag_dd:.1f}%</div><div class="kpi-sub-green" style="font-weight:800;">Peak {diag_peak_date.strftime("%Y-%m-%d")} · {diag_peak:,.0f}<br>Current {diag_current_date.strftime("%Y-%m-%d")} · {diag_close:,.0f}</div></div>',unsafe_allow_html=True)
        st.caption('Structural Drawdown drives deployment and risk scoring. The secondary drawdown basis is a comparison indicator only.')

        with st.expander('📈 Quantitative Valuation Channels',expanded=True):
            st.markdown('### Quantitative Valuation Channels')
            render_trend_channel(ud,index_label)

        with st.expander('⚙️ Cycle Signal Settings & PMI Override', expanded=False):
            p1,p2,p3,p4,p5,p6,p7=st.columns([1.15,1.05,1.45,.75,.75,.8,.55])
            chosen=p1.selectbox('PMI Proxy Used (Cycle Signal)',PMI_PROXY_OPTIONS,index=PMI_PROXY_OPTIONS.index(current_proxy) if current_proxy in PMI_PROXY_OPTIONS else 0,help='Market-specific PMI used as economic-cycle input.')
            actual=LATEST_PMI_ACTUALS.get(chosen,LATEST_PMI_ACTUALS['N/A'])
            p2.text_input('PMI Region',value=PMI_PROXY_MAP.get(sel,{}).get('region','N/A'))
            pmi_source_in=p3.text_input('PMI Source',value=st.session_state.get('latest_pmi_source',actual['source']))
            latest_in=p4.number_input('Latest PMI',0.0,70.0,float(st.session_state.get('latest_pmi_value',actual['value'])),step=.1)
            month_in=p5.text_input('PMI Month',value=st.session_state.get('latest_pmi_month',actual['month']))
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


        with st.expander('🧮 Signal Diagnostics, Trigger Monitor & Score Engine', expanded=False):
            sig,trigger,engine=st.columns([1,1,1.15])
            sig.markdown('#### 📊 Signal Confidence Details')
            sig.markdown('<div class="light-card">'+kv('Drawdown Signal','Active' if dd<=-8 else 'Inactive',ORANGE if dd<=-8 else SLATE)+kv('Risk Regime',local_alert,RED if local_alert=='CRASH RISK' else ORANGE if local_alert=='WARNING' else AMBER if local_alert=='WATCH' else GREEN)+kv('Technical Trend','Weak' if trend_below else 'Stable',BLUE)+'</div>',unsafe_allow_html=True)
            is_alt=sel in PMI_NA_MARKETS
            trig=pd.DataFrame([{'Trigger':'VIX > 25','Status':'N/A' if is_alt else ('Yes' if vix is not None and vix>25 else 'No')},{'Trigger':'Yield curve inverted','Status':'N/A' if is_alt else ('Yes' if curve_spread is not None and curve_spread<0 else 'No')},{'Trigger':f'{chosen} < 50','Status':'N/A' if (is_alt or not pmi_app) else ('Yes' if latest_in<50 else 'No')},{'Trigger':'Structural drawdown < -10%','Status':'Yes' if dd<-10 else 'No'},{'Trigger':'Below 200D MA','Status':'Yes' if trend_below else 'No'}])
            trigger.markdown('#### 📡 Live Trigger Monitor'); trigger.dataframe(trig,use_container_width=True,hide_index=True)
            engine.markdown('#### 🧮 Live Risk Score Engine')
            if is_alt:
                engine.markdown('<div class="light-card">'+kv('VIX Score','Disabled for alternative assets',SLATE)+kv('Yield Curve Score','Disabled for alternative assets',SLATE)+kv('PMI Score','Not applicable',SLATE)+kv('Drawdown Score',f'{ldd:.0f} / 40',ORANGE)+kv('Trend Score',f'{ltrend:.0f} / 20',RED)+kv('Total',f'{local_score:.0f} / 100 → {local_alert}',RED if local_alert=='CRASH RISK' else ORANGE if local_alert=='WARNING' else GREEN)+'</div>',unsafe_allow_html=True)
            else:
                engine.markdown('<div class="light-card">'+kv('VIX Score',f'{lvix:.0f} / 30',AMBER)+kv('Yield Curve Score',f'{lcurve:.0f} / 20',BLUE)+kv(f'{chosen} Score',f'{lpmi:.0f} / 20',GREEN)+kv('Drawdown Score',f'{ldd:.0f} / 25',ORANGE)+kv('Trend Score',f'{ltrend:.0f} / 15',RED)+kv('Total',f'{local_score:.0f} / 100 → {local_alert}',RED if local_alert=='CRASH RISK' else ORANGE if local_alert=='WARNING' else GREEN)+'</div>',unsafe_allow_html=True)

        with st.expander('📈 12M Trend Snapshot',expanded=False):
            vix_raw=hist('^VIX','2025-06-01'); vix_df=vix_raw[['Close']].rename(columns={'Close':'VIX'}) if not vix_raw.empty else pd.DataFrame()
            tnx_raw=hist('^TNX','2025-06-01'); irx_raw=hist('^IRX','2025-06-01'); curve_df=pd.DataFrame()
            if not tnx_raw.empty and not irx_raw.empty:
                aligned=tnx_raw[['Close']].rename(columns={'Close':'TNX'}).join(irx_raw[['Close']].rename(columns={'Close':'IRX'}),how='inner')
                if not aligned.empty: curve_df=pd.DataFrame({'10Y-13W':aligned.TNX-aligned.IRX},index=aligned.index)
            pmi_df=get_pmi_df(chosen,latest_in); idx12=ud.loc[ud.index>=ud.index.max()-pd.DateOffset(months=12)][['Close']].rename(columns={'Close':'Index'})
            top_left,top_right=st.columns(2)
            with top_left: mini_trend_chart(vix_df,'VIX 12M','Volatility regime',AMBER,'rgba(245,158,11,.18)','VIX')
            with top_right: mini_trend_chart(curve_df,'Yield Curve 12M','10Y minus 13W spread',BLUE,'rgba(37,99,235,.16)','Spread %')
            bottom_left,bottom_right=st.columns(2)
            with bottom_left:
                st.info('ℹ️ PMI is not applicable for this asset class (Gold / Bitcoin).') if sel in PMI_NA_MARKETS else mini_pmi_bar_chart(pmi_df,f'{chosen} 12M Monthly Releases',f'{month_in} latest monthly signal')
            with bottom_right: mini_trend_chart(idx12,f'{index_label} 12M',f'{ticker} · 12M price path',RED,'rgba(239,68,68,.16)','Index Level')

def render_performance(expanded=False):
    with st.expander('📊 MARKET PERFORMANCE & ETF TRACKER',expanded=expanded):
        for g,recs in bench().items(): st.markdown(f'### {g}'); st.dataframe(pd.DataFrame(recs),use_container_width=True,hide_index=True)
        ed=etfs(); order=[sel] if sel in ETF_UNIVERSE else []; order += [x for x in ETF_UNIVERSE if x not in order]
        for k in order:
            if k in ed: st.markdown(f'### {k}{" ✅ SELECTED" if k==sel else ""}'); st.dataframe(pd.DataFrame(ed[k]),use_container_width=True,hide_index=True)


EVENT_CONTEXT_MAP = {
    '1987 Black Monday': {'primary_driver':'Market-structure shock / liquidity stress','driver_tags':['Market structure','Liquidity stress','Programme trading','Portfolio insurance'],'key_causes':['Asset-bubble concern after rapid market gains','Trade-deficit and US dollar pressure','Programme trading / portfolio-insurance selling','Margin calls and trading-system strain'],'interpretation':'A fast market-structure crash rather than a normal earnings-cycle recession.'},
    'Gulf War / 1990 Oil Shock': {'primary_driver':'Geopolitical / oil shock','driver_tags':['War','Oil shock','Inflation risk','Recession fear'],'key_causes':['Iraq-Kuwait conflict and regional geopolitical uncertainty','Sharp oil-price increase','Risk-off market repricing','Early-1990s recession pressure'],'interpretation':'A geopolitical and energy-price shock rather than a pure valuation bubble unwind.'},
    'Asian Financial Crisis': {'primary_driver':'Currency / capital-flow crisis','driver_tags':['Currency stress','Capital outflow','Banking stress','Regional contagion'],'key_causes':['Currency devaluation pressure','Regional capital outflows','Banking and balance-sheet stress','Contagion across Asian equity and FX markets'],'interpretation':'A regional currency and capital-flow crisis rather than a pure valuation-cycle correction.'},
    'Dot-com Bust / Corporate Scandals': {'primary_driver':'Technology bubble unwind / corporate confidence shock','driver_tags':['Valuation bubble','Technology','Corporate scandals','Post-9/11 uncertainty'],'key_causes':['Unwinding of internet and technology-stock valuations','Accounting scandals including Enron and WorldCom','Investor confidence deterioration','Post-9/11 uncertainty'],'interpretation':'A late-stage bear-market drawdown linked to the dot-com unwind and confidence shocks.'},
    'Dot-com Bust': {'primary_driver':'Technology valuation bubble unwind','driver_tags':['Valuation bubble','Technology','Speculation','Capital tightening'],'key_causes':['Extreme internet and technology-stock valuations','Weak profitability discipline in many dot-com companies','Venture capital and IPO speculation','Rising-rate / capital-tightening pressure'],'interpretation':'A valuation-led bubble unwind.'},
    'Global Financial Crisis': {'primary_driver':'Credit / banking crisis','driver_tags':['Credit crisis','Housing bubble','Banking stress','Mortgage risk'],'key_causes':['Subprime mortgage expansion','Housing bubble and falling home prices','Mortgage-backed securities losses','Bank funding stress and credit contraction'],'interpretation':'A systemic credit crisis with broad financial-sector stress.'},
    'Eurozone / US Debt Scare': {'primary_driver':'Sovereign-debt / policy confidence shock','driver_tags':['Sovereign debt','US downgrade','Policy risk','Risk-off'],'key_causes':['Eurozone sovereign-debt stress','US debt-ceiling and downgrade concerns','Global growth uncertainty','Risk-off equity repricing'],'interpretation':'A policy-confidence and sovereign-risk shock.'},
    'China Devaluation / Oil Shock': {'primary_driver':'Currency / commodity shock','driver_tags':['Currency stress','Oil shock','China growth concern','Risk-off'],'key_causes':['China currency devaluation / growth concern','Oil-price weakness or commodity stress','Emerging-market risk-off sentiment','Global growth slowdown concern'],'interpretation':'A macro risk-off drawdown linked to currency and commodity stress.'},
    'US-China Trade War': {'primary_driver':'Trade-war / geopolitical risk-off','driver_tags':['Trade war','Tariffs','Geopolitics','Growth slowdown'],'key_causes':['Tariff escalation and trade-policy uncertainty','Pressure on global manufacturing and supply chains','Risk-off rotation from cyclical and export-sensitive assets'],'interpretation':'A geopolitical and trade-policy shock with growth-slowdown risk.'},
    'COVID Shock': {'primary_driver':'Pandemic / liquidity shock','driver_tags':['Pandemic','Lockdowns','Liquidity stress','Recession fear'],'key_causes':['COVID-19 pandemic uncertainty','Lockdowns and economic-shutdown risk','Liquidity stress and forced de-risking','Sharp recession fears'],'interpretation':'A fast exogenous macro shock rather than a valuation bubble unwind.'},
    'Inflation & Rate-Hike Cycle': {'primary_driver':'Inflation, rate hikes and geopolitical / energy shock','driver_tags':['Inflation','Interest rates','War','Energy shock','Supply chain'],'key_causes':['High inflation','Rapid central-bank tightening','Russia-Ukraine-war-related supply disruption','Energy and commodity-price pressure','Recession fears and valuation compression'],'interpretation':'A macro tightening cycle amplified by war-related supply and energy shocks.'},
    'Rate-Hike Cycle': {'primary_driver':'Inflation and monetary tightening','driver_tags':['Inflation','Interest rates','QT','Bond yields'],'key_causes':['High inflation','Rapid central-bank rate hikes','Higher bond yields','Valuation compression in long-duration / growth assets'],'interpretation':'A policy-tightening and valuation-compression cycle.'},
    'High-Recovery Technical Correction': {'primary_driver':'High-recovery technical correction','driver_tags':['Technical correction','High recovery','Mechanical drawdown signal'],'key_causes':['No mapped macro-crisis window was matched.','Recovery return exceeded 200%.','Use as a mechanical drawdown-rule case study rather than a labelled crisis event.'],'interpretation':'This was an economically significant technical correction. It is useful for rule testing, but should be separated from labelled macro-crisis validation.'},
    'Technical Correction': {'primary_driver':'Price-based technical correction','driver_tags':['Technical correction','No mapped macro crisis','Data-defined drawdown'],'key_causes':['No mapped macro-crisis window was matched.','The event appears to be a price-defined correction rather than a labelled historical crisis.','Interpret using drawdown severity, Z-score path and recovery profile.'],'interpretation':'This is a model-detected correction cycle. Useful for drawdown-rule testing, but should not be treated as a known historical crisis.'},
    'System-Detected Cyclical Drawdown': {'primary_driver':'System-detected cyclical drawdown','driver_tags':['Unlabelled drawdown','Bear-market cycle','Data-defined event'],'key_causes':['No mapped macro-crisis window was matched.','The peak-to-trough decline exceeded the event threshold and is retained for statistical recovery and deployment analysis.','Review valuation Z-score path and recovery profile before treating it as a crisis analogue.'],'interpretation':'This is an intentional unlabelled >20% drawdown category, not missing data. Include it in the event universe but separate it from named macro crises.'},
}

def get_event_context(label):
    label=str(label)
    for key,context in EVENT_CONTEXT_MAP.items():
        if key in label: return context
    return {'primary_driver':'Unclassified / not mapped','driver_tags':['Data-defined drawdown'],'key_causes':['No mapped major macro-crisis label is attached to this event.','Interpret using observed drawdown, Z-score movement and recovery outcome.'],'interpretation':'This should be treated as a data-defined drawdown cycle unless manually tagged.'}

def render_event_context_card(row):
    ctx=get_event_context(row.get('Historical Label',''))
    causes_html=''.join([f'<li>{c}</li>' for c in ctx['key_causes']])
    tags=' · '.join(ctx['driver_tags'])
    z_peak=row.get('Z @ Peak',np.nan); z_trough=row.get('Z @ Trough',np.nan)
    z_line='N/A' if pd.isna(z_peak) or pd.isna(z_trough) else f'{z_peak:+.2f} → {z_trough:+.2f}'
    st.markdown(f"""<div class="light-card" style="padding:14px 16px 12px 16px;"><div style="font-weight:800; font-size:1.05rem; margin-bottom:10px;">📌 Event Context & Market Drivers</div><div style="display:grid; grid-template-columns:105px minmax(0, 1fr); column-gap:10px; row-gap:8px; max-width:700px; align-items:start;"><div style="color:{MUTED}; font-size:.86rem;">Primary Driver</div><div style="color:{PURPLE}; font-weight:800; font-size:.92rem; text-align:left;">{ctx["primary_driver"]}</div><div style="color:{MUTED}; font-size:.86rem;">Driver Tags</div><div style="font-weight:700; font-size:.90rem; text-align:left;">{tags}</div><div style="color:{MUTED}; font-size:.86rem;">Z-Score Path</div><div style="font-weight:800; font-size:.90rem; text-align:left;">{z_line}</div></div><div style="margin-top:14px; color:#374151; max-width:860px;"><b>Key causes / context:</b><ul style="margin-top:6px; margin-bottom:8px; padding-left:20px; line-height:1.55;">{causes_html}</ul></div><div style="margin-top:8px; color:#374151; max-width:860px;"><b>Interpretation:</b> {ctx["interpretation"]}</div></div>""", unsafe_allow_html=True)

def find_first_trigger(bt, peak_date, trough_date, threshold_pct):
    threshold_pct=abs(float(threshold_pct)); window=bt.loc[pd.Timestamp(peak_date):pd.Timestamp(trough_date)].copy()
    if window.empty: return None
    hit=window[window['dd_pct'] <= -threshold_pct]
    if hit.empty: return None
    r=hit.iloc[0]; return hit.index[0], safe_float(r.Close), safe_float(r.dd_pct)

def price_on_or_before(price_df, target_date):
    try:
        s=price_df.loc[:pd.Timestamp(target_date)]
        if s.empty: return pd.NaT, np.nan
        return s.index[-1], safe_float(s.Close.iloc[-1])
    except Exception: return pd.NaT, np.nan

def build_event_deployment_plan(bt, price_df, peak_date, trough_date, event_budget, ending_basis, custom_end_date=None):
    ladder=[('Deployment 1','INITIAL BUY',8,.10),('Deployment 2','BUY',15,.25),('Deployment 3','STRONG BUY',25,.50),('Deployment 4','CRISIS BUY',35,.75),('Deployment 5','MAX CRISIS BUY',50,1.00)]
    rows=[]; prev_cum=0.0; latest_date=price_df.index.max()
    for dep_name,zone_name,threshold,cum_pct in ladder:
        inc_pct=max(cum_pct-prev_cum,0); trig=find_first_trigger(bt,peak_date,trough_date,threshold)
        if trig is None:
            rows.append({'Deployment':dep_name,'Trigger':zone_name,'Trigger Threshold':f'-{threshold:.0f}%', 'Status':'Not triggered','Trigger Date':'—','Index Level':'—','Drawdown':'—','Cumulative Deploy %':f'{cum_pct:.0%}','Incremental Deploy %':f'{inc_pct:.0%}','Deploy Amount':0.0,'Ending Date':'—','Ending Level':'—','Ending Value':0.0,'Return %':np.nan}); continue
        entry_date,entry_level,entry_dd=trig; deploy_amount=event_budget*inc_pct; prev_cum=cum_pct
        end_target=latest_date if ending_basis.startswith('Never') else entry_date+pd.DateOffset(years=1) if ending_basis.startswith('1Y') else entry_date+pd.DateOffset(years=2) if ending_basis.startswith('2Y') else entry_date+pd.DateOffset(years=5) if ending_basis.startswith('5Y') else pd.Timestamp(custom_end_date) if custom_end_date is not None else latest_date
        if end_target>latest_date: end_target=latest_date
        end_date,end_level=price_on_or_before(price_df,end_target); ending_value=deploy_amount*(end_level/entry_level) if deploy_amount and entry_level and end_level else 0.0; ret_pct=((end_level/entry_level)-1)*100 if entry_level and end_level else np.nan
        rows.append({'Deployment':dep_name,'Trigger':zone_name,'Trigger Threshold':f'-{threshold:.0f}%', 'Status':'Triggered','Trigger Date':entry_date.strftime('%Y-%m-%d'),'Index Level':f'{entry_level:,.0f}','Drawdown':f'{entry_dd:.1f}%','Cumulative Deploy %':f'{cum_pct:.0%}','Incremental Deploy %':f'{inc_pct:.0%}','Deploy Amount':deploy_amount,'Ending Date':'—' if pd.isna(end_date) else pd.Timestamp(end_date).strftime('%Y-%m-%d'),'Ending Level':'—' if pd.isna(end_level) else f'{end_level:,.0f}','Ending Value':ending_value,'Return %':ret_pct})
    return pd.DataFrame(rows)

def render_compact_timeline(row, peak_date, trough_date):
    period_days=max((trough_date-peak_date).days,0)
    peak_level=safe_float(row['Peak Index'])
    trough_level=safe_float(row['Trough Index'])
    trough_dd=safe_float(row['Drawdown %'])
    event_label=str(row.get('Historical Label',''))
    period_label=f'{peak_date.strftime("%Y-%m-%d")} → {trough_date.strftime("%Y-%m-%d")}'
    mini_cards=[
        ('Peak',peak_date.strftime('%Y-%m-%d'),f'{peak_level:,.0f}',BLUE),
        ('Trough',trough_date.strftime('%Y-%m-%d'),f'{trough_level:,.0f}',RED),
        ('Drawdown','Peak to trough',f'{trough_dd:.1f}%',ORANGE if abs(trough_dd)<40 else RED),
        ('Duration','Trading cycle',f'{period_days} days',SLATE),
    ]
    card_html=''.join([
        f'<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;padding:10px 12px;min-height:82px;">'
        f'<div style="font-size:.78rem;color:{MUTED};font-weight:700;text-transform:uppercase;letter-spacing:.03em;">{label}</div>'
        f'<div style="font-size:.82rem;color:{MUTED};margin-top:4px;">{sub}</div>'
        f'<div style="font-size:1.15rem;font-weight:850;color:{colour};margin-top:6px;">{value}</div>'
        f'</div>'
        for label,sub,value,colour in mini_cards
    ])
    st.markdown(f"""
<div class="light-card" style="padding:14px 16px;margin:10px 0 12px 0;max-width:100%;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:10px;">
    <div>
      <div style="font-weight:850;font-size:1.02rem;color:{TEXT};">🧭 Crisis Timeline</div>
      <div style="font-size:.88rem;color:{MUTED};margin-top:2px;">{event_label}</div>
    </div>
    <div style="font-size:.82rem;font-weight:750;color:{TEXT};background:#F8FAFC;border:1px solid #E5E7EB;border-radius:999px;padding:5px 10px;">{period_label}</div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;">{card_html}</div>
</div>
""", unsafe_allow_html=True)

def render_crash(expanded=False):
    with st.expander('🏆 Crash & Recovery Analytics', expanded=expanded):
        st.markdown('## 📊 Crash & Recovery Analytics')
        st.caption('Four-part structure: summary, event explorer with valuation context, deployment simulator, and full audit table. Event definition uses mapped structural windows where available and bounded causal peak search otherwise.')
        st.markdown('### 1. Executive Crash & Cycle Summary')
        st.markdown('---')
        p,q,r=st.columns([1,1,1])
        start=p.date_input('Historical analysis start date',value=ud.index.min().date(),min_value=ud.index.min().date(),max_value=ud.index.max().date(),key='crash_start')
        thr=q.slider('Minimum drawdown threshold (%)',10,50,10,5,key='crash_threshold')
        crash_val_model=r.selectbox('Crash valuation model',['Expanding Window','Rolling Window','Full History'],index=0,key='crash_val_model')
        bt=ud.loc[pd.Timestamp(start):].copy(); bt['rm']=bt.Close.rolling(252,min_periods=1).max(); bt['dd_pct']=((bt.Close-bt.rm)/bt.rm)*100; cur=safe_float(bt.Close.iloc[-1]); valuation_tc=build_trend_channel(ud,2040,model=crash_val_model,rolling_years=15); event_df=crash_events(bt,thr,cur,valuation_tc)
        if event_df.empty: st.info('No drawdown events found with the selected parameters.'); return
        severity_order=['10-20% correction','20-30% bear drawdown','30-40% crash','40-50% severe crash','>50% crisis crash']
        severity_meta={'10-20% correction':{'icon':'📉','title':'10-20%','desc':'Normal correction-zone events.','colour':BLUE},'20-30% bear drawdown':{'icon':'⚠️','title':'20-30%','desc':'Deeper bear-market drawdowns.','colour':AMBER},'30-40% crash':{'icon':'🚨','title':'30-40%','desc':'Crash-regime events.','colour':ORANGE},'40-50% severe crash':{'icon':'🔥','title':'40-50%','desc':'Severe crisis drawdowns.','colour':RED},'>50% crisis crash':{'icon':'🧨','title':'>50%','desc':'Rare crisis-level drawdowns.','colour':PURPLE}}
        observation_years=years_between(bt.index.min(),bt.index.max())
        sev_counts=event_df['Severity'].value_counts().to_dict(); sev_cols=st.columns(5)
        for i,bucket in enumerate(severity_order):
            meta=severity_meta[bucket]; count=int(sev_counts.get(bucket,0)); word='Event' if count==1 else 'Events'; freq=frequency_label(count,observation_years)
            sev_cols[i].markdown(f'<div class="light-card" style="border-top:4px solid {meta["colour"]};"><div style="font-weight:800;color:{meta["colour"]};">{meta["icon"]} {meta["title"]}</div><div style="font-size:1.35rem;font-weight:900;margin-top:8px;">{count} {word}</div><div style="font-size:.82rem;color:{TEXT};font-weight:700;margin-top:4px;">{freq}</div><div style="font-size:.82rem;color:{MUTED};margin-top:6px;">{meta["desc"]}</div></div>',unsafe_allow_html=True)
        st.caption('Historical frequency is calculated from the selected analysis window and is not a forecast of future crash timing.')
        rets=event_df['Recovery Return %'].astype(float)
        crash_freq_inline=frequency_label(len(event_df),observation_years).replace('Frequency: ','')
        k1,k2,k3,k4,k5=st.columns(5)
        k1.markdown(f'<div class="kpi"><div class="label">Crash Events</div><div class="value">{len(event_df)} <span style="font-size:15px;color:{GREEN};font-weight:700;">({crash_freq_inline})</span></div></div>',unsafe_allow_html=True)
        k2.metric('Success Rate',f'{rets.gt(0).mean()*100:.0f}%')
        k3.metric('Avg Recovery',f'{rets.mean():.1f}%')
        k4.metric('Best Recovery',f'{rets.max():.1f}%')
        k5.metric('Active Structural Drawdown',f'{dd:.1f}%')
        st.markdown('---'); st.markdown('### 2. 🔍 Crash Event Explorer & Valuation Context'); st.caption('Filter historical crash events and review drawdown severity, valuation Z-score at peak/trough, and event classification.')
        if 'crash_detail_open' not in st.session_state: st.session_state.crash_detail_open=False
        if 'selected_crash_event_id' not in st.session_state: st.session_state.selected_crash_event_id=None
        f1,f2,f3,f4=st.columns([1,1,1,1])
        detected_sev_opts=sorted(event_df.Severity.dropna().unique().tolist())
        sev_opts=severity_order + [x for x in detected_sev_opts if x not in severity_order]
        preferred_zone_order=['INITIAL BUY','BUY','STRONG BUY','CRISIS BUY','MAX CRISIS BUY']
        detected_zone_opts=event_df.Zone.dropna().unique().tolist()
        zone_opts=[z for z in preferred_zone_order if z in detected_zone_opts] + sorted([z for z in detected_zone_opts if z not in preferred_zone_order])
        label_opts=['All']+sorted(event_df['Historical Label'].dropna().unique().tolist())
        val_class_opts=['All']+sorted(event_df['Valuation Classification'].dropna().unique().tolist())
        sev_sel=f1.selectbox('Severity',['All']+sev_opts,index=0,key='crash_severity_dropdown')
        zone_sel=f2.selectbox('Buy Zone',['All']+zone_opts,index=0,key='crash_zone_dropdown')
        label_sel=f3.selectbox('Event Label',label_opts,index=0,key='crash_label_dropdown')
        val_class_sel=f4.selectbox('Valuation Class',val_class_opts,index=0,key='crash_valuation_class_dropdown')
        filtered_df=event_df.copy()
        if sev_sel!='All':
            filtered_df=filtered_df[filtered_df.Severity==sev_sel]
        if zone_sel!='All':
            filtered_df=filtered_df[filtered_df.Zone==zone_sel]
        if label_sel!='All':
            filtered_df=filtered_df[filtered_df['Historical Label']==label_sel]
        if val_class_sel!='All':
            filtered_df=filtered_df[filtered_df['Valuation Classification']==val_class_sel]
        explorer_cols=['Peak Date','Peak Index','Trough Date','Trough Index','Historical Label','Severity','Zone','Drawdown %','Duration Days','Recovery Return %','Z @ Peak','Z @ Trough','Valuation Classification']
        if filtered_df.empty: st.info('No events match the selected filters.')
        else:
            working_df=filtered_df.copy(); working_df['_EventID']=working_df.index.astype(int); display_df=working_df[['_EventID']+explorer_cols].copy()
            for c in ['Peak Date','Trough Date']: display_df[c]=pd.to_datetime(display_df[c]).dt.strftime('%Y-%m-%d')
            for c in ['Drawdown %','Recovery Return %','Z @ Peak','Z @ Trough']: display_df[c]=display_df[c].astype(float).round(2)
            display_df['Inspect Event Detail']=display_df['_EventID'].eq(st.session_state.selected_crash_event_id)
            edited_df=st.data_editor(display_df,use_container_width=True,hide_index=True,disabled=[c for c in display_df.columns if c!='Inspect Event Detail'],column_config={'_EventID':None,'Inspect Event Detail':st.column_config.CheckboxColumn('Inspect Event Detail',help='Tick one event row to expand its detail panel.')},key='crash_event_inspector_table')
            selected_ids=edited_df.loc[edited_df['Inspect Event Detail'],'_EventID'].tolist() if 'Inspect Event Detail' in edited_df.columns else []
            if selected_ids: st.session_state.selected_crash_event_id=int(selected_ids[-1]); st.session_state.crash_detail_open=True
            else: st.session_state.selected_crash_event_id=None; st.session_state.crash_detail_open=False
            st.download_button('⬇️ Export Filtered Crash Events CSV',display_df.drop(columns=['_EventID','Inspect Event Detail'],errors='ignore').to_csv(index=False),file_name='filtered_crash_events_phase2.csv',mime='text/csv')
        with st.expander('📌 Selected Event Detail / Historical Crash Deployment Explorer',expanded=st.session_state.crash_detail_open):
            selected_id=st.session_state.selected_crash_event_id
            if selected_id is None or selected_id not in event_df.index: st.info('Select an event by ticking **Inspect Event Detail** beside the event row above.')
            else:
                row=event_df.loc[selected_id]; peak_date=pd.to_datetime(row['Peak Date']); trough_date=pd.to_datetime(row['Trough Date']); z_peak=row.get('Z @ Peak',np.nan); z_trough=row.get('Z @ Trough',np.nan)
                render_compact_timeline(row,peak_date,trough_date)
                render_event_context_card(row)
                st.markdown('#### 🧪 Event-Level Staged Deployment Simulation')
                c_amt,c_end,c_custom=st.columns([1,1,1]); event_budget=c_amt.number_input(f'Event Investible Budget ({current_currency_text()})',min_value=1000.0,value=15000.0,step=1000.0,key='selected_event_investment_amount')
                ending_basis=c_end.selectbox('Ending Date Basis',['Never sell / Latest available','1Y after each deployment','2Y after each deployment','5Y after each deployment','Custom end date'],index=0,key='selected_event_ending_basis')
                custom_end=None
                if ending_basis=='Custom end date': custom_end=c_custom.date_input('Custom ending date',value=ud.index.max().date(),min_value=ud.index.min().date(),max_value=ud.index.max().date(),key='selected_event_custom_end')
                else: c_custom.caption('Default: never sell uses latest available price.')
                plan_df=build_event_deployment_plan(bt,ud,peak_date,trough_date,event_budget,ending_basis,custom_end); triggered=plan_df[plan_df['Status']=='Triggered'].copy(); total_deployed=float(triggered['Deploy Amount'].sum()) if not triggered.empty else 0.0; ending_value=float(triggered['Ending Value'].sum()) if not triggered.empty else 0.0
                gain_loss=ending_value-total_deployed; total_return=(ending_value/total_deployed-1)*100 if total_deployed else 0.0; first_entry=triggered['Trigger Date'].iloc[0] if not triggered.empty else '—'
                m1,m2,m3,m4,m5,m6=st.columns(6); m1.metric('Number of Deployments',len(triggered)); m2.metric('Total Deployed',fmt_sgd(total_deployed)); m3.metric('Ending Value',fmt_sgd(ending_value)); m4.metric('Gain / Loss',fmt_sgd(gain_loss)); m5.metric('Total Return',f'{total_return:.1f}%'); m6.metric('First Entry Date',first_entry)
                display_plan=plan_df.copy()
                for c in ['Deploy Amount','Ending Value']: display_plan[c]=display_plan[c].apply(lambda x: fmt_sgd(x) if float(x)>0 else fmt_sgd(0))
                display_plan['Return %']=display_plan['Return %'].apply(lambda x: '—' if pd.isna(x) else f'{x:.1f}%')
                st.dataframe(display_plan,use_container_width=True,hide_index=True)
                st.info(f"This event was classified as: {row['Valuation Classification']}. Historical label: {row['Historical Label']}. Deployments are staged by cumulative investible-capital ladder triggers, not by the final trough.")
        st.markdown('---'); st.markdown('### 3. 🧪 Master Crash Deployment Simulator')
        with st.expander('Master Crash Deployment Simulator',expanded=True):
            s1,s2,s3,s4=st.columns([1,1,1,1.25]); inv=s1.number_input('Investment per event (S$)',min_value=1000.0,value=10000.0,step=1000.0); end_date=s2.date_input('Simulation end date',value=ud.index.max().date(),min_value=ud.index.min().date(),max_value=ud.index.max().date()); use_filtered=s3.checkbox('Use currently filtered events only',value=True); simulation_universe=s4.selectbox('Simulation Universe',['Known Crisis Events Only','All Events Including Technical Corrections','Technical Corrections Only'],index=0)
            end_slice=ud.loc[:pd.Timestamp(end_date)]
            if end_slice.empty: st.info('No end-date price available.'); return
            end_index=safe_float(end_slice.Close.iloc[-1]); base=filtered_df.copy() if use_filtered and not filtered_df.empty else event_df.copy(); technical_labels=['Technical Correction','High-Recovery Technical Correction','System-Detected Cyclical Drawdown']
            if simulation_universe=='Known Crisis Events Only': sim_base=base[~base['Historical Label'].isin(technical_labels)].copy()
            elif simulation_universe=='Technical Corrections Only': sim_base=base[base['Historical Label'].isin(technical_labels)].copy(); st.warning('This simulation uses technical corrections only. Treat this as mechanical drawdown-rule testing, not labelled macro-crisis validation.')
            else: sim_base=base.copy(); st.warning('This simulation includes technical corrections. Interpret separately from crisis-regime validation.') if base['Historical Label'].isin(technical_labels).any() else None
            sim=sim_base[pd.to_datetime(sim_base['Trough Date'])<=pd.Timestamp(end_date)].copy()
            if sim.empty: st.info('No events before selected end date for the selected simulation universe.'); return
            sim['Investment Amount']=inv; sim['End Index']=end_index; sim['Ending Value']=inv*(sim['End Index']/sim['Trough Index']); sim['Gain / Loss']=sim['Ending Value']-sim['Investment Amount']; sim['Return %']=(sim['Ending Value']/sim['Investment Amount']-1)*100; sim['Holding Days']=(pd.Timestamp(end_date)-pd.to_datetime(sim['Trough Date'])).dt.days.clip(lower=0)
            total=sim['Investment Amount'].sum(); ending=sim['Ending Value'].sum(); gain=ending-total; tr=(ending/total-1)*100 if total else 0; known_used=int((~sim['Historical Label'].isin(technical_labels)).sum()); technical_used=int(sim['Historical Label'].isin(technical_labels).sum())
            m1,m2,m3,m4,m5,m6,m7=st.columns(7); m1.metric('Deployments',len(sim)); m2.metric('Known Events Used',known_used); m3.metric('Technical Corrections',technical_used); m4.metric('Capital Deployed',fmt_sgd(total)); m5.metric('Ending Value',fmt_sgd(ending)); m6.metric('Total Gain / Loss',fmt_sgd(gain)); m7.metric('Total Return',f'{tr:.1f}%')
            sim_display=sim[['Trough Date','Historical Label','Severity','Zone','Valuation Classification','Z @ Trough','Trough Index','End Index','Investment Amount','Ending Value','Gain / Loss','Return %','Holding Days']].copy(); sim_display['Trough Date']=pd.to_datetime(sim_display['Trough Date']).dt.strftime('%Y-%m-%d')
            for c in ['Z @ Trough','Trough Index','End Index','Investment Amount','Ending Value','Gain / Loss','Return %']: sim_display[c]=sim_display[c].astype(float).round(2)
            st.dataframe(sim_display,use_container_width=True,hide_index=True); st.download_button('⬇️ Export Master Simulator CSV',sim_display.to_csv(index=False),file_name='master_crash_simulator_phase2.csv',mime='text/csv')
        st.markdown('---'); st.markdown('### 4. Full Crash Event Universe / Audit Table'); audit_cols=['Peak Date','Peak Index','Trough Date','Trough Index','Drawdown %','Duration Days','Recovery Return %','Zone','Historical Label','Severity','Detected Window Start','Detected Window End','Peak Selection Rule','Boundary Reason','Lookback Cap Days','Z @ Peak','Z @ Trough','Valuation Classification']; full_display=event_df[audit_cols].copy()
        for c in ['Peak Date','Trough Date']: full_display[c]=pd.to_datetime(full_display[c]).dt.strftime('%Y-%m-%d')
        for c in ['Peak Index','Trough Index','Drawdown %','Recovery Return %','Z @ Peak','Z @ Trough']: full_display[c]=full_display[c].astype(float).round(2)
        with st.expander('📚 Full Crash Event Universe / Audit Table',expanded=False): st.caption('Complete unfiltered event universe used by the explorer, valuation context layer and simulator. Kept collapsed as the audit trail.'); st.dataframe(full_display,use_container_width=True,hide_index=True); st.download_button('⬇️ Export Full Crash Events CSV',full_display.to_csv(index=False),file_name='crash_events_full_phase2.csv',mime='text/csv')

def render_audit(expanded=False):
    with st.expander('📡 AUDIT TRAIL & EXPORT',expanded=expanded):
        left,right=st.columns([1,1])
        left.markdown('#### 📡 Data Source & Freshness'); left.markdown('<div class="light-card">'+kv('Market Data','Yahoo Finance',BLUE)+kv('Currency Display',f'{currency_symbol} / {currency_name}',GREEN)+kv('PMI Proxy',st.session_state.get('pmi_proxy_label',pmi_label),GREEN)+kv('PMI Value',f'{st.session_state.get("latest_pmi_value",latest_pmi):.1f} · {st.session_state.get("latest_pmi_month","")}',GREEN)+kv('PMI Source',st.session_state.get('latest_pmi_source',pmi_proxy_default['source']),GREEN)+kv('Risk Model','Alternative asset' if sel in PMI_NA_MARKETS else 'Equity macro',PURPLE)+kv('Valuation Model','OOS Expanding Valuation Channel (Live Quant Model)',PURPLE)+kv('Bias Status','No look-ahead bias for OOS valuation model',GREEN)+kv('Last Refreshed',datetime.now().strftime('%d %b %Y %H:%M SGT'),SLATE)+'</div>',unsafe_allow_html=True)
        right.markdown('#### 🧾 Methodology Notes'); right.markdown('- Live Risk Score is rules-based and not a crash prediction.\n- PMI is monthly, not intraday live data.\n- US PMI is fetched from FRED only when Update PMI is clicked.\n- Non-US PMI uses manual input with pre-filled 12M defaults.\n- Gold / Bitcoin use the alternative-asset risk model; PMI is not applicable.\n- Phase 2 default valuation model is Expanding Window (OOS) to reduce look-ahead bias.\n- Full-history regression remains available as collapsible research-only reference.')
        snap=pd.DataFrame([{'Timestamp':datetime.now().strftime('%Y-%m-%d %H:%M:%S SGT'),'Selected Index':index_label,'Ticker':ticker,'Drawdown Reference':ref,'Current Structural Drawdown %':round(dd,2),'Allocation Stance':zone,'Action Zone':zone,'Suggested Deploy S$':round(deploy,2),'Funding Source':funding_source,'PMI Proxy':st.session_state.get('pmi_proxy_label',pmi_label),'PMI Value':st.session_state.get('latest_pmi_value',latest_pmi),'Live Risk Score':round(live_score,1),'Risk Regime':alert,'Risk Model':'Alternative asset' if sel in PMI_NA_MARKETS else 'Equity macro','Valuation Model':'OOS Expanding Valuation Channel (Live Quant Model)','Valuation Z-Score':exec_z_score,'Bias Status':'No look-ahead bias for OOS valuation model','Signal Confidence':conf_label}])
        st.markdown('#### 📤 Tactical Snapshot Export'); st.dataframe(snap,use_container_width=True,hide_index=True); st.download_button('⬇️ Export Tactical Snapshot CSV',snap.to_csv(index=False),file_name='tactical_snapshot_phase2.csv',mime='text/csv')

RENDERERS={'💰 Suggested Deploy':render_suggested,'🌦️ Market Conditions':render_market,'📊 Market Performance':render_performance,'🏆 Crash Analytics':render_crash,'📡 Audit Trail & Export':render_audit}
render_executive()
if active_section != '🧠 Executive Centre':
    RENDERERS[active_section](expanded=True)
for section in SECTION_ORDER:
    if section != active_section:
        if active_section == '🧠 Executive Centre' and section == '💰 Suggested Deploy':
            RENDERERS[section](expanded=deploy>0)
        else:
            RENDERERS[section](expanded=False)
st.markdown('---'); st.caption(f'🕒 Last refreshed: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} SGT'); st.caption('⚠️ Disclaimer: Educational only. Not financial advice. Past performance does not guarantee future results. Consult a licensed adviser.')
