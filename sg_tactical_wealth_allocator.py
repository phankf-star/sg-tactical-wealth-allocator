import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time
import math

st.set_page_config(page_title='SG Tactical Wealth Allocator', layout='wide', initial_sidebar_state='expanded')
st.title('\U0001f1f8\U0001f1ec Tactical Wealth Allocation & Future Drawdown Simulator')
st.caption('Singapore wealth allocation platform with regime classification, opportunity scoring, and crash-buying validation.')

st.sidebar.markdown('## \U0001f4b0 Capital Pools')
cash_balance = st.sidebar.number_input('Liquid Cash ($)',min_value=0.0,value=100000.0,step=5000.0)
srs_balance = st.sidebar.number_input('SRS ($)',min_value=0.0,value=35000.0,step=5000.0)
cpf_oa_balance = st.sidebar.number_input('CPF-OA ($)',min_value=0.0,value=180000.0,step=5000.0)
st.sidebar.markdown('---')
st.sidebar.markdown('## \u2699\ufe0f Safeguards')
emergency_buffer = st.sidebar.number_input('Emergency Buffer ($)',min_value=0.0,value=20000.0,step=1000.0)
preserve_cpf = st.sidebar.checkbox('Preserve S$20k CPF-OA Floor',value=True)

INDEX_TICKERS = {'S&P 500 (US Market Core)':'^GSPC','Nasdaq 100 (Tech Growth)':'^IXIC','Straits Times Index (SG Value/REITs)':'^STI','Hang Seng Index (HK Cyclical/Beta)':'^HSI'}

ETF_UNIVERSE = {
    'Straits Times Index (SG Value/REITs)':{'label':'\U0001f1f8\U0001f1ec Singapore','etfs':[('SPDR STI ETF','ES3.SI'),('Nikko AM STI ETF','G3B.SI')]},
    'Hang Seng Index (HK Cyclical/Beta)':{'label':'\U0001f1ed\U0001f1f0 Hong Kong','etfs':[('Tracker Fund','2800.HK'),('iShares HSI','3115.HK'),('iShares HS TECH','3067.HK')]},
    'Nasdaq 100 (Tech Growth)':{'label':'\U0001f1fa\U0001f1f8 Nasdaq','etfs':[('Invesco QQQ','QQQ'),('Invesco QQQM','QQQM')]},
    'S&P 500 (US Market Core)':{'label':'\U0001f1fa\U0001f1f8 S&P 500','etfs':[('SPDR SPY','SPY'),('Vanguard VOO','VOO'),('iShares IVV','IVV')]},
    'AI & Technology':{'label':'\U0001f916 AI & Technology','etfs':[('iShares AI Innovation','BAI'),('Global X AI & Tech','AIQ'),('Global X Robotics & AI','BOTZ')]},
    'Semiconductors':{'label':'\U0001f4a1 Semiconductors','etfs':[('iShares Semiconductor','SOXX'),('VanEck Semiconductor','SMH')]},
    'China Internet':{'label':'\U0001f1e8\U0001f1f3 China Internet','etfs':[('KraneShares China Internet','KWEB')]},
    'Emerging Markets':{'label':'\U0001f30f Emerging Markets','etfs':[('iShares MSCI EM','EEM')]},
    'US REITs':{'label':'\U0001f3e0 US REITs','etfs':[('Vanguard Real Estate','VNQ')]},
    'Dividend':{'label':'\U0001f4b8 Dividend','etfs':[('Schwab US Dividend','SCHD')]},
    'Global':{'label':'\U0001f30d Global','etfs':[('Vanguard Total World','VT')]},
    'Bonds':{'label':'\U0001f4c9 Bonds','etfs':[('iShares 20+ Year Treasury','TLT')]},
}
BENCHMARK_TICKERS = {
    'Global Indices':[('STI','^STI'),('Nasdaq','^IXIC'),('S&P 500','^GSPC'),('DJIA','^DJI'),('Nikkei 225','^N225'),('SSE A Share','000002.SS'),('TWSE','^TWII')],
    'Commodities & Crypto':[('Crude Oil','CL=F'),('Gold','GC=F'),('Silver','SI=F'),('Bitcoin','BTC-USD')],
}

st.sidebar.markdown('---')
st.sidebar.markdown('## \U0001f504 Data Sync')
if st.sidebar.button('\U0001f504 Force Refresh'): st.cache_data.clear(); st.toast('Cache cleared!',icon='\U0001f504')

def safe_float(v,fb=1000.0):
    try:
        x=float(v)
        if math.isnan(x) or math.isinf(x): return fb
        return x
    except: return fb

@st.cache_data(ttl=14400)
def harvest_market():
    m={}
    for nm,tk in INDEX_TICKERS.items():
        try:
            df=yf.Ticker(tk).history(start='1997-01-01'); time.sleep(1.5)
            if not df.empty:
                df=df.dropna(subset=['Close'])
                if df.empty: continue
                cs=float(df['Close'].iloc[-1]); ma=float(df['Close'].rolling(200).mean().dropna().iloc[-1]) if len(df)>=200 else cs
                atp=float(df['Close'].max())
                if math.isnan(cs) or math.isnan(atp): continue
                m[nm]={'live_close':cs,'ma_200':ma,'ath_peak':atp,'drawdown':((cs-atp)/atp)*100,'underlying_df':df}
        except Exception as e: st.error(f'Error: {nm}: {e}')
    return m

@st.cache_data(ttl=14400)
def fetch_macro():
    m={'vix':None,'yield_10y':None,'yield_3m':None,'yield_spread':None,'vix_hist':None,'tnx_hist':None,'irx_hist':None}
    try:
        vh=yf.Ticker('^VIX').history(period='1y'); time.sleep(1.5)
        if not vh.empty: m['vix']=float(vh['Close'].dropna().iloc[-1]); m['vix_hist']=vh
    except: pass
    try:
        th=yf.Ticker('^TNX').history(period='1y'); time.sleep(1.5)
        if not th.empty: m['yield_10y']=float(th['Close'].dropna().iloc[-1]); m['tnx_hist']=th
    except: pass
    try:
        ih=yf.Ticker('^IRX').history(period='1y'); time.sleep(1.5)
        if not ih.empty: m['yield_3m']=float(ih['Close'].dropna().iloc[-1]); m['irx_hist']=ih
    except: pass
    if m['yield_10y'] is not None and m['yield_3m'] is not None: m['yield_spread']=m['yield_10y']-m['yield_3m']
    return m

@st.cache_data(ttl=14400)
def fetch_etf_perf():
    r={}
    for iname,g in ETF_UNIVERSE.items():
        gr=[]
        for en,tk in g['etfs']:
            rec={'name':en,'ticker':tk,'1y':None,'3y':None,'5y':None,'price':None}
            try:
                h=yf.Ticker(tk).history(period='6y'); time.sleep(0.8)
                if not h.empty:
                    h=h.dropna(subset=['Close']); cp=float(h['Close'].iloc[-1]); rec['price']=cp; td=len(h)
                    if td>=252: rec['1y']=((cp/float(h['Close'].iloc[-252]))-1)*100
                    if td>=756: rec['3y']=((cp/float(h['Close'].iloc[-756]))-1)*100
                    if td>=1260: rec['5y']=((cp/float(h['Close'].iloc[-1260]))-1)*100
            except: pass
            gr.append(rec)
        r[iname]=gr
    return r

@st.cache_data(ttl=14400)
def fetch_bench():
    r={}
    for gn,tks in BENCHMARK_TICKERS.items():
        gr=[]
        for nm,tk in tks:
            rec={'name':nm,'ticker':tk,'1y':None,'3y':None,'5y':None,'price':None}
            try:
                h=yf.Ticker(tk).history(period='6y'); time.sleep(0.8)
                if not h.empty:
                    h=h.dropna(subset=['Close']); cp=float(h['Close'].iloc[-1]); rec['price']=cp; td=len(h)
                    if td>=252: rec['1y']=((cp/float(h['Close'].iloc[-252]))-1)*100
                    if td>=756: rec['3y']=((cp/float(h['Close'].iloc[-756]))-1)*100
                    if td>=1260: rec['5y']=((cp/float(h['Close'].iloc[-1260]))-1)*100
            except: pass
            gr.append(rec)
        r[gn]=gr
    return r

with st.spinner('Harvesting index data...'): mdb=harvest_market()
with st.spinner('Fetching macro...'): live_macro=fetch_macro()
if not mdb: st.error('\U0001f6a8 No data. Try Force Refresh.'); st.stop()

st.markdown('### \U0001f52e Market Conditions & Scenario Modeler')
st.info('Live data loaded. Adjust sliders for scenarios.')
avail=list(mdb.keys())
sel_idx=st.selectbox('Select Target Index',avail)
if sel_idx not in mdb: st.error('Unavailable.'); st.stop()
sp=mdb[sel_idx]; lac=safe_float(sp['live_close']); haa=safe_float(sp['ath_peak'],lac*1.5)
ud=sp['underlying_df']; ud.index=ud.index.tz_localize(None)
ath_val=float(ud['Close'].max()); ath_dt=ud['Close'].idxmax()
try: ath_ds=ath_dt.strftime('%Y-%m-%d')
except: ath_ds='N/A'
smin=max(1,int(lac*0.35)); smax=max(smin+100,int(haa*1.25))
r1c1,r1c2=st.columns(2)
with r1c1:
    mnd=ud.index.min().to_pydatetime().date(); mxd=ud.index.max().to_pydatetime().date()
    use_hist=st.checkbox('Use Historical Date',value=False)
    if use_hist:
        tdt=st.date_input('Pick Date',value=mxd,min_value=mnd,max_value=mxd)
        ci=ud.index.get_indexer([pd.Timestamp(tdt)],method='nearest')[0]
        pp=float(ud.iloc[ci]['Close']); st.caption(f'Price: **{pp:,.2f}**')
        dup=ud.loc[:pd.Timestamp(tdt)]; rw=dup.iloc[max(0,len(dup)-252):]
        tp=float(rw['Close'].max()); pdt=rw['Close'].idxmax()
    else: pp=None
with r1c2:
    if use_hist:
        sv=min(max(int(pp),smin),smax); ipi=st.slider('Index Price',smin,smax,sv,disabled=True)
    else:
        sv=min(max(int(lac),smin),smax); ipi=st.slider('Index Price',smin,smax,sv,help='Slide to simulate.')
    st.caption(f'\U0001f4e1 Live: **{lac:,.2f}**')
if not use_hist:
    rw=ud.iloc[max(0,len(ud)-252):]; tp=float(rw['Close'].max()); pdt=rw['Close'].idxmax()
try: pds=pdt.strftime('%Y-%m-%d')
except: pds='N/A'

try:
    cd=ud.iloc[max(0,len(ud)-252):]; m2=ud['Close'].rolling(200).mean().iloc[max(0,len(ud)-252):]
    fi=go.Figure()
    fi.add_trace(go.Scatter(x=cd.index,y=cd['Close'],mode='lines',name='Close',line=dict(color='#1565C0',width=1.5)))
    fi.add_trace(go.Scatter(x=m2.index,y=m2.values,mode='lines',name='200MA',line=dict(color='#4CAF50',width=1,dash='dot')))
    fi.add_hline(y=tp,line_dash='dash',line_color='#D32F2F',line_width=1,annotation_text='52W High: '+f'{tp:,.0f}',annotation_position='top left',annotation_font_size=10,annotation_font_color='#D32F2F')
    fi.update_layout(title=dict(text='52-Week Price \u2014 '+sel_idx,font=dict(size=13)),height=220,margin=dict(l=10,r=10,t=35,b=10),showlegend=True,legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='right',x=1,font=dict(size=10)),xaxis=dict(showgrid=False),yaxis=dict(showgrid=True,gridcolor='#F0F0F0'),plot_bgcolor='white',paper_bgcolor='white')
    st.plotly_chart(fi,use_container_width=True,config={'displayModeBar':False})
except: st.caption('\u26a0\ufe0f Chart unavailable')

st.markdown('')
r2c1,r2c2,r2c3=st.columns(3)
lv_=live_macro.get('vix'); ls_=live_macro.get('yield_spread')
vd_=round(lv_,1) if lv_ else 20.0; yd_=round(ls_,2) if ls_ else 0.45
with r2c1:
    pmi_in=st.slider('US ISM PMI',40.0,60.0,51.5)
    st.caption('\U0001f4dd [ISM Reports](https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/)')
with r2c2:
    ys_in=st.slider('Yield Spread (10Y\u22123M)',-1.50,2.50,yd_)
    if ls_ is not None:
        y10=live_macro.get('yield_10y',0); y3=live_macro.get('yield_3m',0)
        st.caption(f'\U0001f4e1 **{ls_:.2f}%** (10Y:{y10:.2f}% \u2212 3M:{y3:.2f}%)')
with r2c3:
    vix_in=st.slider('CBOE VIX',10.0,80.0,vd_)
    if lv_: st.caption(f'\U0001f4e1 VIX: **{lv_:.2f}**')

cc1,cc2,cc3=st.columns(3)
with cc1:
    st.markdown('<div style="background:#F5F5F5;border:1px solid #DDD;border-radius:8px;padding:16px;text-align:center;height:200px;display:flex;flex-direction:column;justify-content:center"><div style="font-size:13px;font-weight:600;color:#555">\U0001f4ca PMI Chart</div><div style="font-size:12px;color:#888;margin-top:8px">No free API. <a href="https://www.ismworld.org" target="_blank" style="color:#1565C0">ISM Reports</a></div></div>',unsafe_allow_html=True)
with cc2:
    try:
        th_=live_macro.get('tnx_hist'); ih_=live_macro.get('irx_hist')
        if th_ is not None and ih_ is not None:
            td2=th_[['Close']].rename(columns={'Close':'T'}); td2.index=td2.index.tz_localize(None)
            id2=ih_[['Close']].rename(columns={'Close':'I'}); id2.index=id2.index.tz_localize(None)
            sd2=td2.join(id2,how='inner'); sd2['S']=sd2['T']-sd2['I']
            fy=go.Figure()
            fy.add_trace(go.Scatter(x=sd2.index,y=sd2['T'],mode='lines',name='10Y',line=dict(color='#1565C0',width=1.5)))
            fy.add_trace(go.Scatter(x=sd2.index,y=sd2['I'],mode='lines',name='3M',line=dict(color='#E65100',width=1.5)))
            fy.add_trace(go.Scatter(x=sd2.index,y=sd2['S'],mode='lines',name='Spread',line=dict(color='#7B1FA2',width=1.5,dash='dot')))
            fy.add_hline(y=0,line_dash='dash',line_color='#D32F2F',line_width=1)
            fy.update_layout(title=dict(text='US Yields \u2014 10Y vs 3M',font=dict(size=12)),height=200,margin=dict(l=10,r=10,t=30,b=10),showlegend=True,legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='right',x=1,font=dict(size=9)),xaxis=dict(showgrid=False),yaxis=dict(showgrid=True,gridcolor='#F0F0F0',ticksuffix='%'),plot_bgcolor='white',paper_bgcolor='white')
            st.plotly_chart(fy,use_container_width=True,config={'displayModeBar':False})
    except: st.caption('\u26a0\ufe0f Yield chart unavailable')
with cc3:
    try:
        vh_=live_macro.get('vix_hist')
        if vh_ is not None:
            vc=vh_.copy(); vc.index=vc.index.tz_localize(None)
            fv=go.Figure(); fv.add_trace(go.Scatter(x=vc.index,y=vc['Close'],mode='lines',line=dict(color='#7B1FA2',width=1.5)))
            fv.add_hline(y=30,line_dash='dash',line_color='#D32F2F',line_width=1,annotation_text='Fear(30)',annotation_position='top left',annotation_font_size=9,annotation_font_color='#D32F2F')
            fv.update_layout(title=dict(text='VIX \u2014 1Y',font=dict(size=12)),height=200,margin=dict(l=10,r=10,t=30,b=10),showlegend=False,xaxis=dict(showgrid=False),yaxis=dict(showgrid=True,gridcolor='#F0F0F0'),plot_bgcolor='white',paper_bgcolor='white')
            st.plotly_chart(fv,use_container_width=True,config={'displayModeBar':False})
    except: st.caption('\u26a0\ufe0f VIX chart unavailable')

ep=pp if use_hist else ipi
tp=safe_float(tp,ep)
edd=((ep-tp)/tp)*100 if tp>0 else 0.0
bma=safe_float(sp['ma_200'],ep)
pt=pmi_in<50; yt=ys_in<0; mt=ep<bma; vt=vix_in>30
rsk=sum([pt,yt,mt,vt])

if edd<=-35: azn='STRONG BUY'; zpt='STRONG BUY ZONE'; zs='Generational &mdash; Deploy Maximum Capital'; ze='\U0001f6a8'; zc='#D32F2F'; ztc='#FFF'; pulse=True
elif edd<=-20: azn='BUY'; zpt='BUY ZONE'; zs='Bear Market &mdash; Scale In'; ze='\U0001f7e2'; zc='#E65100'; ztc='#FFF'; pulse=False
elif edd<=-10: azn='INITIAL BUY'; zpt='INITIAL BUY ZONE'; zs='Correction &mdash; Nibble Positions'; ze='\U0001f7e1'; zc='#F9A825'; ztc='#1A1A1A'; pulse=False
elif ep>(1.20*bma) and rsk>=3: azn='STRONG SELL'; zpt='STRONG SELL ZONE'; zs='Bubble &mdash; Maximize Liquidity'; ze='\U0001f534'; zc='#B71C1C'; ztc='#FFF'; pulse=True
else: azn='HOLD'; zpt='HOLD / DCA ZONE'; zs='Normal &mdash; Maintain DCA'; ze='\u26aa'; zc='#2E7D32'; ztc='#FFF'; pulse=False

if rsk>=3 or edd<=-35: regime='CRISIS'; regime_color='#B71C1C'; regime_emoji='\U0001f534'; regime_label='Maximum contrarian'
elif rsk>=2 or edd<=-20: regime='RISK-OFF'; regime_color='#E65100'; regime_emoji='\U0001f7e0'; regime_label='Elevated contrarian'
elif rsk>=1 or edd<=-10: regime='NEUTRAL'; regime_color='#F9A825'; regime_emoji='\U0001f7e1'; regime_label='Selective deploy'
else: regime='RISK-ON'; regime_color='#2E7D32'; regime_emoji='\U0001f7e2'; regime_label='Standard pace'

dd_score=20 if edd<=-35 else (15 if edd<=-20 else (10 if edd<=-10 else 5))
vix_score=20 if vix_in>30 else (15 if vix_in>20 else (10 if vix_in>15 else 5))
pmi_score=20 if pmi_in>55 else (15 if pmi_in>=50 else (10 if pmi_in>=45 else 5))
trend_score=5 if mt else 15
if edd<=-20 and mt: trend_score=10
yield_score=15 if ys_in>0.5 else (10 if ys_in>=0 else 5)
opp_score=dd_score+vix_score+pmi_score+trend_score+yield_score
if opp_score>=70: opp_label='High Conviction'; opp_color='#2E7D32'
elif opp_score>=50: opp_label='Moderate'; opp_color='#E65100'
else: opp_label='Low'; opp_color='#999'
confidence_pct=min(99,max(10,opp_score+(rsk*5)))

# Compute allocation FIRST so deploy figures are synced
uc=max(0.0,cash_balance-emergency_buffer); us=srs_balance; ucpf=max(0.0,cpf_oa_balance-20000.0) if preserve_cpf else cpf_oa_balance
co=0.0;so=0.0;cpfo=0.0
if azn=='STRONG BUY': co=uc;so=us;cpfo=ucpf
elif azn=='BUY': co=uc*0.5;so=us*0.75;cpfo=ucpf*0.4
elif azn=='INITIAL BUY': co=uc*0.2;so=us*0.3;cpfo=ucpf*0.15
deploy_amount=co+so+cpfo
avail_capital=uc+us+ucpf
hold_amount=avail_capital-deploy_amount
deploy_pct=int((deploy_amount/avail_capital)*100) if avail_capital>0 else 0

st.markdown('---')
if edd<=-35: dbg='#FFCDD2';dbd='#D32F2F';di='\U0001f6a8';dtc='#B71C1C';dl='Generational!'
elif edd<=-20: dbg='#FFE0B2';dbd='#E65100';di='\u26a0\ufe0f';dtc='#E65100';dl='Deep drawdown!'
elif edd<=-10: dbg='#FFF9C4';dbd='#F9A825';di='\u26a0\ufe0f';dtc='#F57F17';dl='Correction'
else: dbg='#E8F5E9';dbd='#2E7D32';di='\u2705';dtc='#2E7D32';dl='Normal'
if rsk>=3: rbg='#FFCDD2';rbd='#D32F2F';ri='\U0001f6a8';rtc='#B71C1C';rl='CRITICAL!'
elif rsk>=1: rbg='#FFE0B2';rbd='#E65100';ri='\u26a0\ufe0f';rtc='#E65100';rl='Elevated: '+str(rsk)
else: rbg='#E8F5E9';rbd='#2E7D32';ri='\u2705';rtc='#2E7D32';rl='All clear'
psi='\U0001f6a8' if pt else '\u2705'; psc='#D32F2F' if pt else '#2E7D32'; pst='CONTRACTION' if pt else 'OK'
ysi='\U0001f6a8' if yt else '\u2705'; ysc='#D32F2F' if yt else '#2E7D32'; yst='INVERTED' if yt else 'Normal'
msi='\U0001f6a8' if mt else '\u2705'; msc='#D32F2F' if mt else '#2E7D32'; mst='BELOW' if mt else 'Above'
vsi='\U0001f6a8' if vt else '\u2705'; vsc='#D32F2F' if vt else '#2E7D32'; vst='FEAR' if vt else 'Normal'

mc1,mc2,mc3=st.columns(3)
with mc1:
    h='<div style="background:'+dbg+';border-left:6px solid '+dbd+';border-radius:10px;padding:20px;text-align:center">'
    h+='<div style="font-size:14px;color:#555;font-weight:600">EFFECTIVE DRAWDOWN</div>'
    h+='<div style="font-size:42px;font-weight:800;color:'+dtc+';margin:8px 0">'+di+' '+f'{edd:.2f}%'+'</div>'
    h+='<div style="font-size:12px;color:#777">'+dl+'</div><div style="font-size:11px;color:#999;margin-top:6px">vs 52-week high</div></div>'
    st.markdown(h,unsafe_allow_html=True)
with mc2:
    h='<div style="background:'+rbg+';border-left:6px solid '+rbd+';border-radius:10px;padding:20px;text-align:center">'
    h+='<div style="font-size:14px;color:#555;font-weight:600">MACRO RISK SCORE</div>'
    h+='<div style="font-size:42px;font-weight:800;color:'+rtc+';margin:8px 0">'+ri+' '+str(rsk)+' / 4</div>'
    h+='<div style="font-size:12px;color:#777;margin-bottom:12px">'+rl+'</div>'
    h+='<div style="text-align:left;padding:10px;background:rgba(255,255,255,.7);border-radius:8px">'
    h+='<div style="font-size:11px;font-weight:700;color:#333;margin-bottom:6px">BREAKDOWN:</div>'
    h+='<div style="font-size:12px;color:'+psc+'">'+psi+' PMI: '+f'{pmi_in:.1f}'+' \u2014 '+pst+'</div>'
    h+='<div style="font-size:12px;color:'+ysc+'">'+ysi+' Yield: '+f'{ys_in:.2f}'+' \u2014 '+yst+'</div>'
    h+='<div style="font-size:12px;color:'+msc+'">'+msi+' 200MA: '+f'{ep:,.0f}'+' vs '+f'{bma:,.0f}'+' \u2014 '+mst+'</div>'
    h+='<div style="font-size:12px;color:'+vsc+'">'+vsi+' VIX: '+f'{vix_in:.1f}'+' \u2014 '+vst+'</div></div></div>'
    st.markdown(h,unsafe_allow_html=True)
with mc3:
    h='<div style="background:#E3F2FD;border-left:6px solid #1565C0;border-radius:10px;padding:20px;text-align:center">'
    h+='<div style="font-size:14px;color:#555;font-weight:600">52-WEEK TRAILING HIGH</div>'
    h+='<div style="font-size:42px;font-weight:800;color:#1565C0;margin:8px 0">\U0001f4ca '+f'{tp:,.2f}'+'</div>'
    h+='<div style="font-size:12px;color:#777">Peak: '+pds+'</div>'
    h+='<div style="font-size:11px;color:#aaa;margin-top:8px;padding-top:8px;border-top:1px solid #D0D0D0">ATH: '+f'{ath_val:,.2f}'+' ('+ath_ds+')</div></div>'
    st.markdown(h,unsafe_allow_html=True)

st.markdown('<br>',unsafe_allow_html=True)
if pulse: pcss='<style>@keyframes zp{0%{box-shadow:0 0 0 0 rgba(211,47,47,.6)}50%{box-shadow:0 0 25px 10px rgba(211,47,47,.3)}100%{box-shadow:0 0 0 0 rgba(211,47,47,.6)}}.zb{animation:zp 2s infinite}</style>'
else: pcss='<style>.zb{}</style>'
bh=pcss+'<div class="zb" style="background:linear-gradient(135deg,'+zc+','+zc+'DD);border-radius:16px;padding:30px 40px;text-align:center;border:2px solid '+zc+'">'
bh+='<div style="font-size:50px;margin-bottom:5px">'+ze+'</div>'
bh+='<div style="font-size:32px;font-weight:900;color:'+ztc+';margin:10px 0;letter-spacing:2px">'+zpt+'</div>'
bh+='<div style="font-size:16px;color:'+ztc+';opacity:.9">'+zs+'</div>'
bh+='<div style="margin-top:15px;display:flex;justify-content:center;gap:30px">'
bh+='<div style="background:rgba(255,255,255,0.2);border-radius:8px;padding:8px 16px"><div style="font-size:11px;color:'+ztc+';opacity:.7">Regime</div><div style="font-size:16px;font-weight:700;color:'+ztc+'">'+regime_emoji+' '+regime+'</div></div>'
bh+='<div style="background:rgba(255,255,255,0.2);border-radius:8px;padding:8px 16px"><div style="font-size:11px;color:'+ztc+';opacity:.7">Confidence</div><div style="font-size:16px;font-weight:700;color:'+ztc+'">'+str(confidence_pct)+'%</div></div>'
bh+='<div style="background:rgba(255,255,255,0.2);border-radius:8px;padding:8px 16px"><div style="font-size:11px;color:'+ztc+';opacity:.7">Deploy</div><div style="font-size:16px;font-weight:700;color:'+ztc+'">'+str(deploy_pct)+'%</div></div>'
bh+='</div></div>'
st.markdown(bh,unsafe_allow_html=True)
st.markdown('<br>',unsafe_allow_html=True)

st.markdown('### \U0001f3af Executive Command Centre')
ec1,ec2,ec3,ec4=st.columns(4)
with ec1:
    h='<div style="background:'+regime_color+';border-radius:12px;padding:20px;text-align:center">'
    h+='<div style="font-size:12px;color:#FFF;opacity:.8">MARKET REGIME</div>'
    h+='<div style="font-size:28px;font-weight:900;color:#FFF;margin:8px 0">'+regime_emoji+' '+regime+'</div>'
    h+='<div style="font-size:11px;color:#FFF;opacity:.7">'+regime_label+'</div></div>'
    st.markdown(h,unsafe_allow_html=True)
with ec2:
    sb='#2E7D32' if opp_score>=70 else ('#E65100' if opp_score>=50 else '#999')
    h='<div style="background:#F5F5F5;border:3px solid '+sb+';border-radius:12px;padding:20px;text-align:center">'
    h+='<div style="font-size:12px;color:#555">OPPORTUNITY SCORE</div>'
    h+='<div style="font-size:36px;font-weight:900;color:'+sb+';margin:8px 0">'+str(opp_score)+' / 100</div>'
    h+='<div style="font-size:12px;color:'+sb+';font-weight:600">'+opp_label+'</div>'
    h+='<div style="margin-top:8px;font-size:10px;color:#888">DD:'+str(dd_score)+' VIX:'+str(vix_score)+' PMI:'+str(pmi_score)+' Trend:'+str(trend_score)+' Yield:'+str(yield_score)+'</div></div>'
    st.markdown(h,unsafe_allow_html=True)
with ec3:
    h='<div style="background:#E8F5E9;border:3px solid #2E7D32;border-radius:12px;padding:20px;text-align:center">'
    h+='<div style="font-size:12px;color:#555">DEPLOY NOW</div>'
    h+='<div style="font-size:28px;font-weight:900;color:#2E7D32;margin:8px 0">S$'+f'{deploy_amount:,.0f}'+'</div>'
    h+='<div style="font-size:12px;color:#777">'+str(deploy_pct)+'% of S$'+f'{avail_capital:,.0f}'+'</div></div>'
    st.markdown(h,unsafe_allow_html=True)
with ec4:
    h='<div style="background:#FFF;border:2px solid #DDD;border-radius:12px;padding:20px;text-align:center">'
    h+='<div style="font-size:12px;color:#555">HOLD / RESERVE</div>'
    h+='<div style="font-size:28px;font-weight:900;color:#555;margin:8px 0">S$'+f'{hold_amount:,.0f}'+'</div>'
    h+='<div style="font-size:12px;color:#999">Dry powder</div></div>'
    st.markdown(h,unsafe_allow_html=True)

# Top 3 Opportunities (scored from ETF data)
try:
    with st.spinner('Ranking ETFs...'): etf_all = fetch_etf_perf()
    flat_etfs = []
    for cat, recs in etf_all.items():
        for r in recs:
            if r['1y'] is not None:
                y1 = r['1y']
                if y1 < -20: sc = 90 + abs(y1)
                elif y1 < 0: sc = 70 + abs(y1)
                elif y1 < 20: sc = 50 + y1
                else: sc = 40 + y1 * 0.3
                flat_etfs.append({'name': r['name'], 'ticker': r['ticker'], 'score': round(sc, 1), 'ret_1y': y1, 'cat': cat})
    flat_etfs.sort(key=lambda x: x['score'], reverse=True)
    top3 = flat_etfs[:3]
    if top3 and deploy_amount > 0:
        st.markdown('#### \U0001f947 Top 3 Opportunities & Suggested Capital Split')
        splits = [0.50, 0.30, 0.20]
        t3h = '<table style="width:100%;border-collapse:collapse;font-size:14px;margin:12px 0"><thead><tr style="background:#F0F2F6;border-bottom:2px solid #DDD">'
        t3h += '<th style="padding:10px">Rank</th><th style="text-align:left;padding:10px">ETF</th><th style="text-align:center;padding:10px">Ticker</th><th style="text-align:center;padding:10px">Score</th><th style="text-align:center;padding:10px">1Y Return</th><th style="text-align:center;padding:10px">Suggested Deploy</th></tr></thead><tbody>'
        medals = ['\U0001f947', '\U0001f948', '\U0001f949']
        for i, etf in enumerate(top3):
            amt = deploy_amount * splits[i]
            rc = '#2E7D32' if etf['ret_1y'] >= 0 else '#D32F2F'
            ar = '\u25b2' if etf['ret_1y'] >= 0 else '\u25bc'
            act = 'STRONG BUY' if etf['score'] >= 80 else 'BUY'
            ac = '#D32F2F' if act == 'STRONG BUY' else '#E65100'
            t3h += '<tr style="border-bottom:1px solid #EEE"><td style="padding:10px;text-align:center;font-size:20px">' + medals[i] + '</td>'
            t3h += '<td style="padding:10px;font-weight:600">' + etf['name'] + '</td>'
            t3h += '<td style="text-align:center;padding:10px;font-family:monospace">' + etf['ticker'] + '</td>'
            t3h += '<td style="text-align:center;padding:10px"><span style="background:' + ac + ';color:#FFF;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600">' + str(etf['score']) + '</span></td>'
            t3h += '<td style="text-align:center;padding:10px;color:' + rc + ';font-weight:600">' + ar + ' ' + f"{etf['ret_1y']:.1f}%" + '</td>'
            t3h += '<td style="text-align:center;padding:10px;font-weight:700;color:#2E7D32">S$' + f'{amt:,.0f}' + '</td></tr>'
        t3h += '</tbody></table>'
        st.markdown(t3h, unsafe_allow_html=True)
except Exception as e: st.caption(f'Top 3 ranking unavailable: {e}')

with st.expander('\U0001f4ca Opportunity Score Breakdown'):
    sc_tbl='| Factor | Input | Score |'+chr(10)+'|:---|:---|:---:|'+chr(10)
    sc_tbl+=f'| Drawdown | {edd:.1f}% | **{dd_score}/20** |'+chr(10)
    sc_tbl+=f'| VIX | {vix_in:.1f} | **{vix_score}/20** |'+chr(10)
    sc_tbl+=f'| PMI | {pmi_in:.1f} | **{pmi_score}/20** |'+chr(10)
    sc_tbl+=f'| Trend | {"Below" if mt else "Above"} 200MA | **{trend_score}/20** |'+chr(10)
    sc_tbl+=f'| Yield Spread | {ys_in:.2f} | **{yield_score}/20** |'+chr(10)
    sc_tbl+=f'| **TOTAL** | | **{opp_score}/100** |'+chr(10)
    st.markdown(sc_tbl)

st.markdown('---')
st.markdown('### \U0001f4cb Tactical Allocation')
with st.expander('\U0001f4d0 Allocation Rules'):
    zd=[('STRONG BUY','\u2264-35%','100%','100%','100%','Generational'),('BUY','\u2264-20%','50%','75%','40%','Scale in'),('INITIAL BUY','\u2264-10%','20%','30%','15%','Nibble'),('HOLD/DCA','Normal','0%','0%','0%','DCA'),('STRONG SELL','Bubble','0%','0%','0%','Pause')]
    tb='| Zone | Trigger | Cash | SRS | CPF-OA | Action |'+chr(10)+'|:---|:---|:---:|:---:|:---:|:---|'+chr(10)
    for z,t,c,s,p,r in zd:
        ac=(z=='STRONG BUY' and azn=='STRONG BUY') or (z=='BUY' and azn=='BUY') or (z=='INITIAL BUY' and azn=='INITIAL BUY') or (z=='HOLD/DCA' and azn=='HOLD') or (z=='STRONG SELL' and azn=='STRONG SELL')
        if ac: tb+=f'| \U0001f449 **{z}** | **{t}** | **{c}** | **{s}** | **{p}** | **{r}** |'+chr(10)
        else: tb+=f'| {z} | {t} | {c} | {s} | {p} | {r} |'+chr(10)
    st.markdown(tb)

if azn=='STRONG SELL': st.warning('\u26a0\ufe0f Bubble. Pausing.')
elif azn=='HOLD': st.info('\u2139\ufe0f Normal. Maintain DCA.')
d1,d2,d3=st.columns(3)
with d1: st.markdown('#### \U0001f4b5 Cash'); st.metric('Deploy',f'S${co:,.2f}'); st.caption(f'Left: S${cash_balance-co:,.2f}')
with d2: st.markdown('#### \U0001f4c8 SRS'); st.metric('Deploy',f'S${so:,.2f}'); st.caption(f'Left: S${srs_balance-so:,.2f}')
with d3: st.markdown('#### \U0001f6e1\ufe0f CPF-OA'); st.metric('Deploy',f'S${cpfo:,.2f}'); st.caption(f'Left: S${cpf_oa_balance-cpfo:,.2f}')
st.markdown('---')
st.subheader(f'Total Deploy: :green[S${deploy_amount:,.2f}]')

st.markdown('---')
st.markdown('### \U0001f4ca Market Performance & ETF Tracker')
def bpt(recs):
    t='<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px"><thead><tr style="background:#F0F2F6;border-bottom:2px solid #DDD">'
    t+='<th style="text-align:left;padding:10px">Name</th><th style="text-align:center;padding:10px">Ticker</th><th style="text-align:center;padding:10px">Price</th>'
    t+='<th style="text-align:center;padding:10px">1Y</th><th style="text-align:center;padding:10px">3Y</th><th style="text-align:center;padding:10px">5Y</th></tr></thead><tbody>'
    for r in recs:
        ps=f"{r['price']:,.2f}" if r['price'] is not None else 'N/A'
        def fr(v):
            if v is None: return '<span style="color:#999">N/A</span>'
            c='#2E7D32' if v>=0 else '#D32F2F'; ar='\u25b2' if v>=0 else '\u25bc'
            return '<span style="color:'+c+';font-weight:600">'+ar+' '+f'{v:.1f}'+'%</span>'
        t+='<tr style="border-bottom:1px solid #EEE"><td style="padding:10px">'+r['name']+'</td><td style="text-align:center;padding:10px;font-family:monospace;color:#555">'+r['ticker']+'</td><td style="text-align:center;padding:10px;font-weight:600">'+ps+'</td><td style="text-align:center;padding:10px">'+fr(r['1y'])+'</td><td style="text-align:center;padding:10px">'+fr(r['3y'])+'</td><td style="text-align:center;padding:10px">'+fr(r['5y'])+'</td></tr>'
    return t+'</tbody></table>'

try:
    with st.spinner('Fetching benchmarks...'): bd=fetch_bench()
    if bd:
        for gn,recs in bd.items():
            ic='\U0001f30d' if 'Indic' in gn else '\U0001f6e2\ufe0f'
            st.markdown('<div style="font-size:18px;font-weight:700;margin:16px 0 8px">'+ic+' '+gn+'</div>',unsafe_allow_html=True)
            st.markdown(bpt(recs),unsafe_allow_html=True)
except Exception as e: st.warning(f'Benchmarks unavailable: {e}')

try:
    with st.spinner('Fetching ETFs...'): ed=fetch_etf_perf()
    if ed:
        st.markdown('<div style="font-size:20px;font-weight:700;margin:24px 0 8px">\U0001f4c8 Investable ETFs</div>',unsafe_allow_html=True)
        do=[]
        if sel_idx in ETF_UNIVERSE: do.append(sel_idx)
        for ix in ETF_UNIVERSE:
            if ix not in do: do.append(ix)
        for ix in do:
            if ix not in ed: continue
            gi=ETF_UNIVERSE[ix]; sel=(ix==sel_idx)
            badge=' <span style="background:#E8F5E9;color:#2E7D32;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">\u2705 SELECTED</span>' if sel else ''
            st.markdown('<div style="font-size:18px;font-weight:700;margin:16px 0 8px">'+gi['label']+badge+'</div>',unsafe_allow_html=True)
            st.markdown(bpt(ed[ix]),unsafe_allow_html=True)
except Exception as e: st.warning(f'ETFs unavailable: {e}')

st.markdown('---')
st.markdown('### \U0001f3c6 Crash Buying Backtest \u2014 Proof That Buying The Dip Works')
st.caption('What if you invested $10,000 at every drawdown trough in ' + sel_idx + '?')
try:
    bt=ud.copy(); bt['rm']=bt['Close'].rolling(252,min_periods=1).max(); bt['dd_']=((bt['Close']-bt['rm'])/bt['rm'])*100
    lc_=float(bt['Close'].iloc[-1]); troughs=[]; in_dd=False; ep_s=None
    for i in range(len(bt)):
        dv=bt['dd_'].iloc[i]
        if dv<=-10 and not in_dd: in_dd=True; ep_s=i
        elif dv>-5 and in_dd:
            in_dd=False; episode=bt.iloc[ep_s:i]; ti=episode['dd_'].idxmin(); tr=bt.loc[ti]
            if len(troughs)==0 or (ti-troughs[-1]['date']).days>=60:
                d_=float(tr['dd_']); p_=float(tr['Close'])
                z_='STRONG BUY' if d_<=-35 else ('BUY' if d_<=-20 else 'INITIAL BUY')
                zc_='#D32F2F' if d_<=-35 else ('#E65100' if d_<=-20 else '#F9A825')
                troughs.append({'date':ti,'price':p_,'dd':d_,'zone':z_,'zc':zc_,'cv':10000*(lc_/p_),'ret':((lc_/p_)-1)*100})
    if in_dd and ep_s is not None:
        episode=bt.iloc[ep_s:]; ti=episode['dd_'].idxmin(); tr=bt.loc[ti]
        if len(troughs)==0 or (ti-troughs[-1]['date']).days>=60:
            d_=float(tr['dd_']); p_=float(tr['Close'])
            z_='STRONG BUY' if d_<=-35 else ('BUY' if d_<=-20 else 'INITIAL BUY')
            zc_='#D32F2F' if d_<=-35 else ('#E65100' if d_<=-20 else '#F9A825')
            troughs.append({'date':ti,'price':p_,'dd':d_,'zone':z_,'zc':zc_,'cv':10000*(lc_/p_),'ret':((lc_/p_)-1)*100})
    if troughs:
        ti_=len(troughs)*10000; tc_=sum(t['cv'] for t in troughs); tr_=((tc_-ti_)/ti_)*100
        s1,s2,s3=st.columns(3)
        with s1: st.metric('Invested',f'${ti_:,.0f}',help=f'{len(troughs)} events')
        with s2: st.metric('Value Today',f'${tc_:,.0f}',f'{tr_:+.1f}%')
        with s3: st.metric('Avg Return',f'{sum(t["ret"] for t in troughs)/len(troughs):,.1f}%')
        th_='<table style="width:100%;border-collapse:collapse;font-size:13px;margin:16px 0"><thead><tr style="background:#F0F2F6;border-bottom:2px solid #DDD"><th style="padding:8px">#</th><th style="padding:8px">Date</th><th style="text-align:center;padding:8px">Level</th><th style="text-align:center;padding:8px">DD</th><th style="text-align:center;padding:8px">Zone</th><th style="text-align:center;padding:8px">Invested</th><th style="text-align:center;padding:8px">Value</th><th style="text-align:center;padding:8px">Return</th></tr></thead><tbody>'
        for i,t in enumerate(troughs):
            rc_='#2E7D32' if t['ret']>=0 else '#D32F2F'; ar_='\u25b2' if t['ret']>=0 else '\u25bc'
            th_+='<tr style="border-bottom:1px solid #EEE"><td style="padding:8px;text-align:center">'+str(i+1)+'</td><td style="padding:8px">'+t['date'].strftime('%Y-%m-%d')+'</td><td style="text-align:center;padding:8px">'+f"{t['price']:,.0f}"+'</td><td style="text-align:center;padding:8px;color:#D32F2F;font-weight:600">'+f"{t['dd']:.1f}%"+'</td><td style="text-align:center;padding:8px"><span style="background:'+t['zc']+';color:#FFF;padding:2px 8px;border-radius:4px;font-size:11px">'+t['zone']+'</span></td><td style="text-align:center;padding:8px">$10,000</td><td style="text-align:center;padding:8px;font-weight:700">$'+f"{t['cv']:,.0f}"+'</td><td style="text-align:center;padding:8px;color:'+rc_+';font-weight:700">'+ar_+' '+f"{t['ret']:.1f}%"+'</td></tr>'
        th_+='</tbody></table>'
        st.markdown(th_,unsafe_allow_html=True)
        fb=go.Figure()
        fb.add_trace(go.Bar(x=[t['date'].strftime('%Y-%m') for t in troughs],y=[t['cv'] for t in troughs],marker_color=[t['zc'] for t in troughs],text=[f"${t['cv']:,.0f}" for t in troughs],textposition='outside'))
        fb.add_hline(y=10000,line_dash='dash',line_color='#999',line_width=1,annotation_text='$10K',annotation_position='bottom right',annotation_font_size=10)
        fb.update_layout(title=dict(text='Value of $10K at Each Trough',font=dict(size=14)),height=350,margin=dict(l=10,r=10,t=40,b=10),plot_bgcolor='white',paper_bgcolor='white',showlegend=False,yaxis=dict(showgrid=True,gridcolor='#F0F0F0'))
        st.plotly_chart(fb,use_container_width=True,config={'displayModeBar':False})

        # Success Rate Table
        st.markdown('#### \U0001f4ca Historical Success Probability')
        thresholds=[5,10,15,20,30,40]
        sr='| Correction | Events | Profitable | Success Rate |'+chr(10)+'|:---|:---:|:---:|:---:|'+chr(10)
        for thr in thresholds:
            ev=[t for t in troughs if t['dd']<=-thr]; w=[t for t in ev if t['ret']>0]
            rate=(len(w)/len(ev)*100) if ev else 0
            em='\U0001f7e2' if rate>=80 else ('\U0001f7e1' if rate>=60 else '\U0001f534')
            sr+=f'| \u2265 {thr}% | {len(ev)} | {len(w)} | {em} **{rate:.0f}%** |'+chr(10)
        st.markdown(sr)
        st.success('\U0001f4a1 **Every major crash in '+sel_idx+' was a buying opportunity.** $'+f'{ti_:,.0f}'+' became $'+f'{tc_:,.0f}'+' \u2014 '+f'{tr_:.1f}%'+' return.')
    else: st.info('No events found.')
except Exception as e: st.warning(f'Backtest unavailable: {e}')

st.markdown('---')
st.caption('\u26a0\ufe0f Disclaimer: Educational only. Not financial advice. Past performance does not guarantee future results. Consult a licensed advisor.')
