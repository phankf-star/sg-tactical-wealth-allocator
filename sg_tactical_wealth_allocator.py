
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time, math
from datetime import datetime

st.set_page_config(page_title="SG Tactical Wealth Allocator", layout="wide", initial_sidebar_state="expanded")
st.title("🇸🇬 Tactical Wealth Allocation & Future Drawdown Simulator")
st.caption("Singapore wealth allocation platform with regime classification, opportunity scoring, and crash-recovery analytics.")

st.sidebar.markdown("## 💰 Capital Pools")
cash_balance=st.sidebar.number_input("Liquid Cash (S$)",min_value=0.0,value=100000.0,step=5000.0)
srs_balance=st.sidebar.number_input("SRS (S$)",min_value=0.0,value=35000.0,step=5000.0)
cpf_oa_balance=st.sidebar.number_input("CPF-OA (S$)",min_value=0.0,value=180000.0,step=5000.0)
st.sidebar.markdown("---")
st.sidebar.markdown("## ⚙️ Safeguards")
emergency_buffer=st.sidebar.number_input("Emergency Buffer (S$)",min_value=0.0,value=20000.0,step=1000.0)
preserve_cpf=st.sidebar.checkbox("Preserve S$20k CPF-OA Floor",value=True)
st.sidebar.markdown("---")
st.sidebar.markdown("## 📐 Drawdown Formula")
drawdown_method=st.sidebar.radio("Current drawdown reference",["Rolling 252D Peak (previous backtest formula)","All-Time High Peak"],index=0)
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Force Refresh"):
    st.cache_data.clear(); st.toast("Market data cache cleared.",icon="🔄")

INDEX_TICKERS={"S&P 500 (US Market Core)":"^GSPC","Nasdaq 100 (Tech Growth)":"^IXIC","Straits Times Index (SG Value/REITs)":"^STI","Hang Seng Index (HK Cyclical/Beta)":"^HSI"}
ETF_UNIVERSE={
"Straits Times Index (SG Value/REITs)":{"label":"🇸🇬 Singapore","etfs":[("SPDR STI ETF","ES3.SI"),("Nikko AM STI ETF","G3B.SI")]},
"Hang Seng Index (HK Cyclical/Beta)":{"label":"🇭🇰 Hong Kong","etfs":[("Tracker Fund","2800.HK"),("iShares HSI","3115.HK"),("iShares HS TECH","3067.HK")]},
"Nasdaq 100 (Tech Growth)":{"label":"🇺🇸 Nasdaq","etfs":[("Invesco QQQ","QQQ"),("Invesco QQQM","QQQM")]},
"S&P 500 (US Market Core)":{"label":"🇺🇸 S&P 500","etfs":[("SPDR SPY","SPY"),("Vanguard VOO","VOO"),("iShares IVV","IVV")]},
"AI & Technology":{"label":"🤖 AI & Technology","etfs":[("iShares AI Innovation","BAI"),("Global X AI & Tech","AIQ"),("Global X Robotics & AI","BOTZ")]},
"Semiconductors":{"label":"💡 Semiconductors","etfs":[("iShares Semiconductor","SOXX"),("VanEck Semiconductor","SMH")]},
"China Internet":{"label":"🇨🇳 China Internet","etfs":[("KraneShares China Internet","KWEB")]},
"Emerging Markets":{"label":"🌏 Emerging Markets","etfs":[("iShares MSCI EM","EEM")]},
"US REITs":{"label":"🏠 US REITs","etfs":[("Vanguard Real Estate","VNQ")]},
"Dividend":{"label":"💸 Dividend","etfs":[("Schwab US Dividend","SCHD")]},
"Global":{"label":"🌍 Global","etfs":[("Vanguard Total World","VT")]},
"Bonds":{"label":"📉 Bonds","etfs":[("iShares 20+ Year Treasury","TLT")]}}
BENCHMARK_TICKERS={"Global Indices":[("STI","^STI"),("Nasdaq","^IXIC"),("S&P 500","^GSPC"),("DJIA","^DJI"),("Nikkei 225","^N225"),("SSE A Share","000002.SS"),("TWSE","^TWII")],"Commodities & Crypto":[("Crude Oil","CL=F"),("Gold","GC=F"),("Silver","SI=F"),("Bitcoin","BTC-USD")]}

def safe_float(v,fb=0.0):
    try:
        x=float(v); return fb if math.isnan(x) or math.isinf(x) else x
    except Exception: return fb

def make_index_tz_naive(df):
    df=df.copy(); df.index=pd.to_datetime(df.index)
    if getattr(df.index,"tz",None) is not None: df.index=df.index.tz_convert(None)
    return df

@st.cache_data(ttl=14400)
def download_price_history(ticker,start="1997-01-01"):
    df=yf.Ticker(ticker).history(start=start); time.sleep(0.2)
    if df is None or df.empty: return pd.DataFrame()
    return make_index_tz_naive(df.dropna(subset=["Close"]).copy())

@st.cache_data(ttl=14400)
def harvest_market():
    out={}
    for name,ticker in INDEX_TICKERS.items():
        try:
            df=download_price_history(ticker)
            if df.empty: continue
            close=safe_float(df["Close"].iloc[-1]); ma200=safe_float(df["Close"].rolling(200).mean().dropna().iloc[-1],close) if len(df)>=200 else close
            ath=safe_float(df["Close"].max(),close); r252=safe_float(df["Close"].rolling(252,min_periods=1).max().iloc[-1],close)
            out[name]={"ticker":ticker,"live_close":close,"ma_200":ma200,"ath_peak":ath,"rolling_252_peak":r252,"underlying_df":df}
        except Exception: continue
    return out

@st.cache_data(ttl=14400)
def fetch_perf_records(items):
    recs=[]
    for name,ticker in items:
        try:
            df=download_price_history(ticker,start="2018-01-01")
            if df.empty: recs.append({"name":name,"ticker":ticker,"price":None,"1y":None,"3y":None,"5y":None}); continue
            last=safe_float(df["Close"].iloc[-1])
            def ret(days):
                if len(df)<=days: return None
                s=safe_float(df["Close"].iloc[-days]); return ((last/s)-1)*100 if s else None
            recs.append({"name":name,"ticker":ticker,"price":last,"1y":ret(252),"3y":ret(756),"5y":ret(1260)})
        except Exception: recs.append({"name":name,"ticker":ticker,"price":None,"1y":None,"3y":None,"5y":None})
    return recs
@st.cache_data(ttl=14400)
def fetch_bench(): return {g:fetch_perf_records(v) for g,v in BENCHMARK_TICKERS.items()}
@st.cache_data(ttl=14400)
def fetch_etf_perf(): return {k:fetch_perf_records(v["etfs"]) for k,v in ETF_UNIVERSE.items()}

def classify_zone(dd):
    if dd<=-35: return "STRONG BUY","#D32F2F"
    if dd<=-20: return "BUY","#E65100"
    if dd<=-10: return "INITIAL BUY","#F9A825"
    if dd>=0: return "STRONG SELL","#6A1B9A"
    return "HOLD","#1976D2"

def latest_drawdown(df,method):
    close=safe_float(df["Close"].iloc[-1])
    if method.startswith("Rolling"):
        peak=safe_float(df["Close"].rolling(252,min_periods=1).max().iloc[-1],close); label="Rolling 252D Peak"
    else:
        peak=safe_float(df["Close"].max(),close); label="All-Time High Peak"
    return close,peak,((close-peak)/peak)*100 if peak else 0,label

def build_drawdown_events(bt,threshold,current_level):
    events=[]; in_dd=False; ep_s=None
    for i in range(len(bt)):
        dv=bt["dd_pct"].iloc[i]
        if dv<=-threshold and not in_dd: in_dd=True; ep_s=i
        elif dv>-5 and in_dd:
            in_dd=False; episode=bt.iloc[ep_s:i]
            if episode.empty: continue
            ti=episode["dd_pct"].idxmin(); tr=bt.loc[ti]
            if len(events)==0 or (ti-events[-1]["date"]).days>=60:
                d=safe_float(tr["dd_pct"]); p=safe_float(tr["Close"]); pk=safe_float(tr["rm"])
                lkb=bt.loc[:ti]; pk_dt=lkb.iloc[max(0,len(lkb)-252):]["Close"].idxmax(); zone,colour=classify_zone(d)
                events.append({"date":ti,"price":p,"dd":d,"zone":zone,"colour":colour,"ret":((current_level/p)-1)*100 if p else 0,"peak":pk,"peak_dt":pk_dt})
    if in_dd and ep_s is not None:
        episode=bt.iloc[ep_s:]
        if not episode.empty:
            ti=episode["dd_pct"].idxmin(); tr=bt.loc[ti]
            if len(events)==0 or (ti-events[-1]["date"]).days>=60:
                d=safe_float(tr["dd_pct"]); p=safe_float(tr["Close"]); pk=safe_float(tr["rm"])
                lkb=bt.loc[:ti]; pk_dt=lkb.iloc[max(0,len(lkb)-252):]["Close"].idxmax(); zone,colour=classify_zone(d)
                events.append({"date":ti,"price":p,"dd":d,"zone":zone,"colour":colour,"ret":((current_level/p)-1)*100 if p else 0,"peak":pk,"peak_dt":pk_dt})
    return events

with st.spinner("Loading market data..."):
    market=harvest_market()
if not market: st.error("Market data unavailable. Try Force Refresh or check data connectivity."); st.stop()
sel_idx=st.selectbox("Select Market Index",list(market.keys()),index=list(market.keys()).index("Hang Seng Index (HK Cyclical/Beta)") if "Hang Seng Index (HK Cyclical/Beta)" in market else 0)
selected=market[sel_idx]; ud=make_index_tz_naive(selected["underlying_df"])

st.markdown("---"); st.markdown("## 🧠 Executive Tactical Allocation Centre"); st.caption("Always-visible decision engine for deployment sizing, capital pools and current market opportunity zone.")
live_close,drawdown_peak,current_dd,drawdown_label=latest_drawdown(ud,drawdown_method); zone,zone_colour=classify_zone(current_dd)
deploy_pct=0.50 if current_dd<=-35 else 0.35 if current_dd<=-25 else 0.20 if current_dd<=-15 else 0.10 if current_dd<=-8 else 0.00
available_cash=max(cash_balance-emergency_buffer,0); available_srs=srs_balance; available_cpf=max(cpf_oa_balance-(20000 if preserve_cpf else 0),0); deploy_amount=(available_cash+available_srs+available_cpf)*deploy_pct
c1,c2,c3,c4,c5=st.columns(5)
with c1: st.metric("Index Level",f"{live_close:,.0f}")
with c2: st.metric("Current Drawdown",f"{current_dd:.1f}%")
with c3: st.metric("Drawdown Ref.",drawdown_label)
with c4: st.metric("Action Zone",zone)
with c5: st.metric("Suggested Deploy",f"S${deploy_amount:,.0f}")
st.markdown(f"""<div style='padding:14px;border-left:6px solid {zone_colour};background:#FAFAFA;border-radius:10px;margin-top:8px'><b>Formula used:</b> Current drawdown = (current close − selected peak reference) ÷ selected peak reference. Current reference is <b>{drawdown_label}</b> at approximately <b>{drawdown_peak:,.0f}</b>.<br><b>Current tactical interpretation:</b> {sel_idx} is in <b>{zone}</b> territory with a drawdown of <b>{current_dd:.1f}%</b>.</div>""",unsafe_allow_html=True)
a1,a2,a3=st.columns(3)
with a1: st.markdown("#### 💵 Cash"); st.metric("Deploy",f"S${available_cash*deploy_pct:,.0f}"); st.caption(f"Available after buffer: S${available_cash:,.0f}")
with a2: st.markdown("#### 📈 SRS"); st.metric("Deploy",f"S${available_srs*deploy_pct:,.0f}"); st.caption(f"Available: S${available_srs:,.0f}")
with a3: st.markdown("#### 🛡️ CPF-OA"); st.metric("Deploy",f"S${available_cpf*deploy_pct:,.0f}"); st.caption(f"Available after floor: S${available_cpf:,.0f}")

with st.expander("🌦️ MARKET CONDITIONS & SCENARIO MODELER",expanded=False):
    st.markdown("""<h1 style='font-size:34px;margin-bottom:0'>🌦️ Market Conditions & Scenario Modeler</h1><p style='font-size:16px;color:gray;margin-top:0'>Scenario-based risk adjustment for deployment planning.</p>""",unsafe_allow_html=True)
    s1,s2,s3,s4=st.columns(4)
    with s1: vix=st.slider("VIX Assumption",10,60,22)
    with s2: pmi=st.slider("PMI Assumption",35,60,50)
    with s3: yld=st.slider("10Y Yield Assumption (%)",1.0,7.0,4.0,0.1)
    with s4: scen_dd=st.slider("Scenario Drawdown (%)",0,60,int(abs(current_dd)))
    risk=min(min(max((vix-15)*1.5,0),40)+min(max((50-pmi)*2,0),30)+min(max((yld-3.5)*8,0),20)+min(max(scen_dd*0.5,0),30),100)
    cap=max(0,min(50,50-risk*0.35)); m1,m2,m3=st.columns(3)
    with m1: st.metric("Scenario Risk Score",f"{risk:.0f}/100")
    with m2: st.metric("Scenario Deploy Cap",f"{cap:.0f}%")
    with m3: st.metric("Scenario Action","Preserve Cash" if risk>=70 else ("Partial Deploy" if risk>=40 else "Accumulate"))

with st.expander("📊 MARKET PERFORMANCE & ETF TRACKER",expanded=False):
    st.markdown("""<h1 style='font-size:34px;margin-bottom:0'>📊 Market Performance & ETF Tracker</h1><p style='font-size:16px;color:gray;margin-top:0'>Global indices, ETFs, benchmarks and tactical opportunity tracking.</p>""",unsafe_allow_html=True)
    def bpt(recs):
        t='<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px"><thead><tr style="background:#F0F2F6;border-bottom:2px solid #DDD"><th style="text-align:left;padding:10px">Name</th><th style="text-align:center;padding:10px">Ticker</th><th style="text-align:center;padding:10px">Price</th><th style="text-align:center;padding:10px">1Y</th><th style="text-align:center;padding:10px">3Y</th><th style="text-align:center;padding:10px">5Y</th></tr></thead><tbody>'
        for r in recs:
            ps=f"{r['price']:,.2f}" if r['price'] is not None else 'N/A'; yf_url='https://finance.yahoo.com/quote/'+r['ticker']
            def fr(v):
                if v is None: return '<span style="color:#999">N/A</span>'
                c='#2E7D32' if v>=0 else '#D32F2F'; ar='▲' if v>=0 else '▼'; return '<span style="color:'+c+';font-weight:600">'+ar+' '+f'{v:.1f}'+'%</span>'
            t+='<tr style="border-bottom:1px solid #EEE"><td style="padding:10px">'+r['name']+'</td><td style="text-align:center;padding:10px"><a href="'+yf_url+'" target="_blank" style="color:#1565C0;text-decoration:none;font-family:monospace">'+r['ticker']+'</a></td><td style="text-align:center;padding:10px;font-weight:600">'+ps+'</td><td style="text-align:center;padding:10px">'+fr(r['1y'])+'</td><td style="text-align:center;padding:10px">'+fr(r['3y'])+'</td><td style="text-align:center;padding:10px">'+fr(r['5y'])+'</td></tr>'
        return t+'</tbody></table>'
    try:
        for group,recs in fetch_bench().items(): st.markdown(f"### {group}"); st.markdown(bpt(recs),unsafe_allow_html=True)
    except Exception as e: st.warning(f"Benchmarks unavailable: {e}")
    try:
        ed=fetch_etf_perf(); order=[]
        if sel_idx in ETF_UNIVERSE: order.append(sel_idx)
        for ix in ETF_UNIVERSE:
            if ix not in order: order.append(ix)
        for ix in order:
            if ix in ed: st.markdown(f"### {ETF_UNIVERSE[ix]['label']}{' ✅ SELECTED' if ix==sel_idx else ''}"); st.markdown(bpt(ed[ix]),unsafe_allow_html=True)
    except Exception as e: st.warning(f"ETFs unavailable: {e}")

with st.expander("🏆 CRASH & RECOVERY ANALYTICS",expanded=False):
    st.markdown("""<h1 style='font-size:34px;margin-bottom:0'>🏆 Crash & Recovery Analytics</h1><p style='font-size:16px;color:gray;margin-top:0'>Historical drawdown analytics, event filtering and selected-event deployment outcome.</p>""",unsafe_allow_html=True)
    ctl1,ctl2=st.columns(2)
    with ctl1: bt_start=st.date_input("Historical analysis start date",value=ud.index.min().date(),min_value=ud.index.min().date(),max_value=ud.index.max().date())
    with ctl2: bt_threshold=st.slider("Min drawdown threshold (%)",min_value=5,max_value=50,value=10,step=5)
    st.caption("Crash event drawdown formula follows the previous version: rolling 252-day peak → trough close.")
    try:
        bt=make_index_tz_naive(ud.loc[pd.Timestamp(bt_start):].copy()); bt['rm']=bt['Close'].rolling(252,min_periods=1).max(); bt['dd_pct']=((bt['Close']-bt['rm'])/bt['rm'])*100; lc_=safe_float(bt['Close'].iloc[-1])
        troughs=build_drawdown_events(bt,bt_threshold,lc_)
        if not troughs: st.info("No drawdown events found with selected parameters.")
        else:
            years_span=max((bt.index.max()-bt.index.min()).days/365.25,1); dd10=len([t for t in troughs if -20<t['dd']<=-10]); dd20=len([t for t in troughs if -30<t['dd']<=-20]); dd30=len([t for t in troughs if t['dd']<=-30])
            st.markdown("### 📚 Full Market Cycle Statistics"); cc1,cc2,cc3=st.columns(3)
            with cc1: st.info(f"📉 10–20% corrections historically occur every ~{round(years_span/dd10,1) if dd10 else 'N/A'} years")
            with cc2: st.warning(f"⚠️ 20–30% corrections historically occur every ~{round(years_span/dd20,1) if dd20 else 'N/A'} years")
            with cc3: st.error(f"🔥 30%+ crashes historically occur every ~{round(years_span/dd30,1) if dd30 else 'N/A'} years")
            st.markdown("### 📊 Executive Crash Summary"); k1,k2,k3,k4,k5=st.columns(5)
            with k1: st.metric("Crash Events",len(troughs))
            with k2: st.metric("Success Rate",f"{sum(1 for t in troughs if t['ret']>0)/len(troughs)*100:.0f}%")
            with k3: st.metric("Avg Recovery",f"{np.mean([t['ret'] for t in troughs]):.1f}%")
            with k4: st.metric("Best Recovery",f"{max([t['ret'] for t in troughs]):.1f}%")
            with k5: st.metric("Current Drawdown",f"{bt['dd_pct'].iloc[-1]:.1f}%")
            event_df=pd.DataFrame([{"Peak Date":t['peak_dt'].strftime('%Y-%m-%d'),"Peak Index":round(t['peak'],0),"Trough Date":t['date'].strftime('%Y-%m-%d'),"Trough Index":round(t['price'],0),"Drawdown %":round(t['dd'],1),"Recovery Return %":round(t['ret'],1),"Zone":t['zone']} for t in troughs])
            event_df['Severity']=event_df['Drawdown %'].apply(lambda v:'30%+' if v<=-30 else '20-30%' if v<=-20 else '10-20%'); event_df['Trough Date_dt']=pd.to_datetime(event_df['Trough Date']).dt.date
            st.markdown("### 🔍 Interactive Event Explorer"); f1,f2,f3=st.columns([1,1,1.2])
            with f1: severity_filter=st.multiselect("Severity filters",['10-20%','20-30%','30%+'],default=['10-20%','20-30%','30%+'])
            with f2: zone_filter=st.multiselect("Buy Zone filters",['INITIAL BUY','BUY','STRONG BUY'],default=['INITIAL BUY','BUY','STRONG BUY'])
            with f3: historical_date_range=st.date_input("Historical event date range",value=(event_df['Trough Date_dt'].min(),event_df['Trough Date_dt'].max()),min_value=event_df['Trough Date_dt'].min(),max_value=event_df['Trough Date_dt'].max())
            hist_start,hist_end=historical_date_range if isinstance(historical_date_range,tuple) and len(historical_date_range)==2 else (event_df['Trough Date_dt'].min(),event_df['Trough Date_dt'].max())
            filtered_df=event_df[event_df['Severity'].isin(severity_filter)&event_df['Zone'].isin(zone_filter)&(event_df['Trough Date_dt']>=hist_start)&(event_df['Trough Date_dt']<=hist_end)].copy()
            st.markdown("#### 🔎 Filtered Event Statistics")
            if filtered_df.empty: st.info("No events match the selected filters.")
            else:
                fs1,fs2,fs3,fs4=st.columns(4)
                with fs1: st.metric("Filtered Events",len(filtered_df))
                with fs2: st.metric("Avg Drawdown",f"{filtered_df['Drawdown %'].mean():.1f}%")
                with fs3: st.metric("Avg Recovery",f"{filtered_df['Recovery Return %'].mean():.1f}%")
                with fs4: st.metric("Best Recovery",f"{filtered_df['Recovery Return %'].max():.1f}%")
                st.markdown("#### 📉 Filtered Event Table"); st.dataframe(filtered_df.drop(columns=['Trough Date_dt']),use_container_width=True,hide_index=True)
                event_options=[f"{r['Peak Date']} → {r['Trough Date']} ({r['Drawdown %']}%)" for _,r in filtered_df.iterrows()]; selected_event=st.selectbox("Historical Crash Explorer",event_options); selected_row=filtered_df.iloc[event_options.index(selected_event)]
                show_deep_dive=st.toggle("📌 Show Selected Event Deep Dive",value=True)
                if show_deep_dive:
                    st.markdown("""<div style='padding:16px;border:1px solid #E0E0E0;border-radius:12px;background:#FAFAFA;margin-top:12px;margin-bottom:16px'><h3 style='margin-bottom:4px;'>📌 Selected Event Deep Dive</h3><p style='color:#666;margin-top:0;'>Deployment controls, event-level breakdown, pre-crash context and crash path visualisation.</p></div>""",unsafe_allow_html=True)
                    st.markdown("#### 💰 Selected Event Deployment Outcome"); oc1,oc2=st.columns([1,2])
                    with oc1: selected_deploy_amount=st.number_input("Investment for selected event (S$)",min_value=1000,value=15000,step=1000)
                    trough_index=safe_float(selected_row['Trough Index']); selected_value_today=selected_deploy_amount*(lc_/trough_index) if trough_index else 0; selected_return=((lc_/trough_index)-1)*100 if trough_index else 0
                    o1,o2,o3,o4=st.columns(4)
                    with o1: st.metric("Deployment Amount",f"S${selected_deploy_amount:,.0f}")
                    with o2: st.metric("Entry Level",f"{selected_row['Trough Index']:,.0f}")
                    with o3: st.metric("Value Today",f"S${selected_value_today:,.0f}")
                    with o4: st.metric("Return Since Trough",f"{selected_return:.1f}%")
                    st.markdown("#### 📊 Detailed Event Breakdown"); d1,d2,d3,d4=st.columns(4)
                    with d1: st.metric("Peak Index",f"{selected_row['Peak Index']:,.0f}")
                    with d2: st.metric("Trough Index",f"{selected_row['Trough Index']:,.0f}")
                    with d3: st.metric("Drawdown",f"{selected_row['Drawdown %']:.1f}%")
                    with d4: st.metric("Recovery Return",f"{selected_row['Recovery Return %']:.1f}%")
                    peak_date=pd.Timestamp(selected_row['Peak Date']); trough_date=pd.Timestamp(selected_row['Trough Date']); days_to_trough=max((trough_date-peak_date).days,0); speed="Fast crash" if days_to_trough<=90 else "Medium-speed bear market" if days_to_trough<=365 else "Slow grinding bear market"
                    st.markdown("#### 🧭 Pre-Crash Context"); st.info(f"Before this drawdown, {sel_idx} peaked at approximately {selected_row['Peak Index']:,.0f} on {selected_row['Peak Date']}. The index then declined to approximately {selected_row['Trough Index']:,.0f} by {selected_row['Trough Date']}, a drawdown of {selected_row['Drawdown %']:.1f}% over about {days_to_trough} days. This was classified as a {speed} and entered the {selected_row['Zone']} zone based on drawdown severity.")
                    chart_df=bt.loc[peak_date:trough_date].copy()
                    if not chart_df.empty:
                        st.markdown("#### 📉 Mini Historical Crash Chart"); fig=go.Figure(); fig.add_trace(go.Scatter(x=chart_df.index,y=chart_df['Close'],mode='lines',line=dict(color='#D32F2F',width=3),name='Peak → Trough Path')); fig.add_trace(go.Scatter(x=[peak_date],y=[selected_row['Peak Index']],mode='markers+text',marker=dict(color='#555',size=10),text=['Peak'],textposition='top center')); fig.add_trace(go.Scatter(x=[trough_date],y=[selected_row['Trough Index']],mode='markers+text',marker=dict(color='#D32F2F',size=10),text=['Trough'],textposition='bottom center')); fig.update_layout(height=340,margin=dict(l=10,r=10,t=40,b=10),title="Mini Historical Crash Chart: Peak → Trough",plot_bgcolor='white',paper_bgcolor='white',xaxis_title='Date',yaxis_title='Index Level',showlegend=False); st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
            st.info("📌 Historical insight: severe drawdowns have historically produced stronger forward return potential, but recovery timing varies materially across cycles. This section is educational and does not guarantee future outcomes.")
            st.download_button("⬇️ Export Crash Analytics CSV",event_df.drop(columns=['Trough Date_dt']).to_csv(index=False),file_name="crash_recovery_analytics.csv",mime="text/csv")
    except Exception as e: st.warning(f"Crash analytics unavailable: {e}")

st.markdown("---"); st.caption(f"🕒 Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} SGT"); st.caption("⚠️ Disclaimer: Educational only. Not financial advice. Past performance does not guarantee future results. Consult a licensed advisor.")
