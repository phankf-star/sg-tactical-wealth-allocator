
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math, time
from datetime import datetime

st.set_page_config(page_title="SG Tactical Wealth Allocator", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background:#FFFFFF; border:1px solid #E5E7EB; border-radius:14px; padding:14px 16px; min-height:112px; overflow-wrap:anywhere;}
[data-testid="stMetricLabel"] {white-space:normal !important; overflow-wrap:anywhere !important; line-height:1.2 !important; color:#6B7280 !important;}
[data-testid="stMetricValue"] {white-space:normal !important; overflow-wrap:anywhere !important; line-height:1.1 !important; font-size:1.75rem !important;}
.small-note {font-size:0.88rem;color:#6B7280;line-height:1.35;margin-top:0.25rem;}
.section-card {padding:16px;border:1px solid #E5E7EB;border-radius:14px;background:#FAFAFA;margin:10px 0 16px 0;}
.alert-card {padding:18px;border-radius:16px;margin:10px 0 18px 0;}
.alert-normal {background:#ECFDF5;border:1px solid #A7F3D0;color:#065F46;}
.alert-watch {background:#FEF3C7;border:1px solid #F59E0B;color:#92400E;}
.alert-warning {background:#FFEDD5;border:1px solid #F97316;color:#9A3412;}
.alert-risk {background:#FEE2E2;border:1px solid #EF4444;color:#991B1B;}
.table-wrap {overflow-x:auto;}
</style>
""", unsafe_allow_html=True)

st.title("🇸🇬 Tactical Wealth Allocation & Future Drawdown Simulator")
st.caption("Singapore wealth allocation dashboard with tactical allocation, live risk monitoring, ETF tracking and crash-recovery analytics.")

INDEX_TICKERS={"S&P 500 (US Market Core)":"^GSPC","Nasdaq 100 (Tech Growth)":"^IXIC","Straits Times Index (SG Value/REITs)":"^STI","Hang Seng Index (HK Cyclical/Beta)":"^HSI"}
BENCHMARK_TICKERS={"Global Indices":[("STI","^STI"),("Nasdaq","^IXIC"),("S&P 500","^GSPC"),("DJIA","^DJI"),("Nikkei 225","^N225"),("SSE A Share","000002.SS"),("TWSE","^TWII")],"Commodities & Crypto":[("Crude Oil","CL=F"),("Gold","GC=F"),("Silver","SI=F"),("Bitcoin","BTC-USD")]}
ETF_UNIVERSE={"Straits Times Index (SG Value/REITs)":{"label":"🇸🇬 Singapore","etfs":[("SPDR STI ETF","ES3.SI"),("Nikko AM STI ETF","G3B.SI")]},"Hang Seng Index (HK Cyclical/Beta)":{"label":"🇭🇰 Hong Kong","etfs":[("Tracker Fund","2800.HK"),("iShares HSI","3115.HK"),("iShares HS TECH","3067.HK")]},"Nasdaq 100 (Tech Growth)":{"label":"🇺🇸 Nasdaq","etfs":[("Invesco QQQ","QQQ"),("Invesco QQQM","QQQM")]},"S&P 500 (US Market Core)":{"label":"🇺🇸 S&P 500","etfs":[("SPDR SPY","SPY"),("Vanguard VOO","VOO"),("iShares IVV","IVV")]},"AI & Technology":{"label":"🤖 AI & Technology","etfs":[("iShares AI Innovation","BAI"),("Global X AI & Tech","AIQ"),("Global X Robotics & AI","BOTZ")]},"Semiconductors":{"label":"💡 Semiconductors","etfs":[("iShares Semiconductor","SOXX"),("VanEck Semiconductor","SMH")]},"China Internet":{"label":"🇨🇳 China Internet","etfs":[("KraneShares China Internet","KWEB")]},"Emerging Markets":{"label":"🌏 Emerging Markets","etfs":[("iShares MSCI EM","EEM")]},"US REITs":{"label":"🏠 US REITs","etfs":[("Vanguard Real Estate","VNQ")]},"Dividend":{"label":"💸 Dividend","etfs":[("Schwab US Dividend","SCHD")]},"Global":{"label":"🌍 Global","etfs":[("Vanguard Total World","VT")]},"Bonds":{"label":"📉 Bonds","etfs":[("iShares 20+ Year Treasury","TLT")]}}

st.sidebar.markdown("## 💰 Capital Pools")
cash_balance=st.sidebar.number_input("Liquid Cash (S$)",0.0,value=100000.0,step=5000.0)
srs_balance=st.sidebar.number_input("SRS (S$)",0.0,value=35000.0,step=5000.0)
cpf_oa_balance=st.sidebar.number_input("CPF-OA (S$)",0.0,value=180000.0,step=5000.0)
st.sidebar.markdown("---")
st.sidebar.markdown("## ⚙️ Safeguards")
emergency_buffer=st.sidebar.number_input("Emergency Buffer (S$)",0.0,value=20000.0,step=1000.0)
preserve_cpf=st.sidebar.checkbox("Preserve S$20k CPF-OA Floor",value=True)
st.sidebar.markdown("---")
st.sidebar.markdown("## 📐 Drawdown Formula")
drawdown_method=st.sidebar.radio("Current drawdown reference",["Rolling 252D Peak (previous backtest formula)","All-Time High Peak"],index=0)
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Force Refresh"):
    st.cache_data.clear(); st.toast("Market data cache cleared.",icon="🔄")

def safe_float(v,fb=0.0):
    try:
        x=float(v); return fb if math.isnan(x) or math.isinf(x) else x
    except Exception: return fb

def tz_naive(df):
    df=df.copy(); df.index=pd.to_datetime(df.index)
    if getattr(df.index,"tz",None) is not None: df.index=df.index.tz_convert(None)
    return df

@st.cache_data(ttl=14400)
def hist(ticker,start="1997-01-01"):
    df=yf.Ticker(ticker).history(start=start); time.sleep(0.12)
    if df is None or df.empty: return pd.DataFrame()
    return tz_naive(df.dropna(subset=["Close"]).copy())

@st.cache_data(ttl=14400)
def market_data():
    out={}
    for n,t in INDEX_TICKERS.items():
        try:
            df=hist(t)
            if df.empty: continue
            c=safe_float(df.Close.iloc[-1]); ma=safe_float(df.Close.rolling(200).mean().dropna().iloc[-1],c) if len(df)>=200 else c
            out[n]={"ticker":t,"df":df,"close":c,"ma200":ma}
        except Exception: pass
    return out

@st.cache_data(ttl=3600)
def live_macro_data():
    def last_close(ticker):
        try:
            df=hist(ticker,"2025-01-01")
            if df.empty: return None
            return safe_float(df.Close.iloc[-1])
        except Exception: return None
    return {"vix":last_close("^VIX"),"tnx":last_close("^TNX"),"irx":last_close("^IRX")}

@st.cache_data(ttl=14400)
def perf(items):
    rec=[]
    for name,ticker in items:
        try:
            df=hist(ticker,"2018-01-01")
            if df.empty: rec.append({"Name":name,"Ticker":ticker,"Price":None,"1Y %":None,"3Y %":None,"5Y %":None}); continue
            last=safe_float(df.Close.iloc[-1])
            def r(days):
                if len(df)<=days: return None
                s=safe_float(df.Close.iloc[-days]); return round(((last/s)-1)*100,1) if s else None
            rec.append({"Name":name,"Ticker":ticker,"Price":round(last,2),"1Y %":r(252),"3Y %":r(756),"5Y %":r(1260)})
        except Exception: rec.append({"Name":name,"Ticker":ticker,"Price":None,"1Y %":None,"3Y %":None,"5Y %":None})
    return rec

@st.cache_data(ttl=14400)
def bench(): return {g:perf(v) for g,v in BENCHMARK_TICKERS.items()}
@st.cache_data(ttl=14400)
def etfs(): return {k:perf(v["etfs"]) for k,v in ETF_UNIVERSE.items()}

def classify(dd):
    if dd<=-35: return "STRONG BUY","#D32F2F"
    if dd<=-20: return "BUY","#E65100"
    if dd<=-10: return "INITIAL BUY","#F9A825"
    if dd>=0: return "STRONG SELL","#6A1B9A"
    return "HOLD","#1976D2"

def current_dd(df,method):
    c=safe_float(df.Close.iloc[-1])
    if method.startswith("Rolling"):
        peak=safe_float(df.Close.rolling(252,min_periods=1).max().iloc[-1],c); label="Rolling 252D Peak"
    else:
        peak=safe_float(df.Close.max(),c); label="All-Time High Peak"
    return c,peak,((c-peak)/peak)*100 if peak else 0,label

def label_event(date):
    y=pd.Timestamp(date).year
    if 1997<=y<=1998: return "Asian Financial Crisis"
    if 2000<=y<=2002: return "Dot-com Bust"
    if 2007<=y<=2009: return "Global Financial Crisis"
    if y==2011: return "Eurozone / US Debt Scare"
    if 2015<=y<=2016: return "China Devaluation / Oil Shock"
    if y==2018: return "US-China Trade War"
    if y==2020: return "COVID Shock"
    if 2021<=y<=2022: return "China / HK Bear Market + Rate-Hike Cycle"
    if 2023<=y<=2024: return "China / HK Property & Growth Slowdown"
    return "Unlabelled Cycle"

def events(bt,thr,current):
    ev=[]; in_dd=False; start=None
    for i in range(len(bt)):
        dv=bt.dd_pct.iloc[i]
        if dv<=-thr and not in_dd: in_dd=True; start=i
        elif dv>-5 and in_dd:
            in_dd=False; e=bt.iloc[start:i]
            if e.empty: continue
            ti=e.dd_pct.idxmin(); row=bt.loc[ti]
            if len(ev)==0 or (ti-ev[-1]["date"]).days>=60:
                look=bt.loc[:ti].iloc[max(0,len(bt.loc[:ti])-252):]
                dd=safe_float(row.dd_pct); price=safe_float(row.Close); peak=safe_float(row.rm); pkdt=look.Close.idxmax(); z,c=classify(dd)
                ev.append({"date":ti,"price":price,"dd":dd,"zone":z,"peak":peak,"peak_dt":pkdt,"ret":((current/price)-1)*100 if price else 0})
    if in_dd and start is not None:
        e=bt.iloc[start:]
        if not e.empty:
            ti=e.dd_pct.idxmin(); row=bt.loc[ti]
            if len(ev)==0 or (ti-ev[-1]["date"]).days>=60:
                look=bt.loc[:ti].iloc[max(0,len(bt.loc[:ti])-252):]
                dd=safe_float(row.dd_pct); price=safe_float(row.Close); peak=safe_float(row.rm); pkdt=look.Close.idxmax(); z,c=classify(dd)
                ev.append({"date":ti,"price":price,"dd":dd,"zone":z,"peak":peak,"peak_dt":pkdt,"ret":((current/price)-1)*100 if price else 0})
    return ev

with st.spinner("Loading market data..."):
    m=market_data()
if not m:
    st.error("Market data unavailable. Try Force Refresh."); st.stop()
sel=st.selectbox("Select Market Index",list(m.keys()),index=list(m.keys()).index("Hang Seng Index (HK Cyclical/Beta)") if "Hang Seng Index (HK Cyclical/Beta)" in m else 0)
ud=m[sel]["df"]

st.markdown("---")
st.markdown("## 🧠 Executive Tactical Allocation Centre")
st.caption("Always-visible decision engine for deployment sizing, capital pools and current market opportunity zone.")
close,peak,dd,ref=current_dd(ud,drawdown_method); zone,zc=classify(dd)
deploy_pct=0.50 if dd<=-35 else 0.35 if dd<=-25 else 0.20 if dd<=-15 else 0.10 if dd<=-8 else 0.00
cash=max(cash_balance-emergency_buffer,0); srs=srs_balance; cpf=max(cpf_oa_balance-(20000 if preserve_cpf else 0),0); deploy=(cash+srs+cpf)*deploy_pct
c1,c2,c3,c4,c5=st.columns(5)
with c1: st.metric("Index Level",f"{close:,.0f}")
with c2: st.metric("Current Drawdown",f"{dd:.1f}%")
with c3: st.metric("Drawdown Ref.",ref)
with c4: st.metric("Current Market Action",zone)
with c5: st.metric("Suggested Deploy",f"S${deploy:,.0f}")
st.markdown(f"<div class='section-card'><b>Formula used:</b> Current drawdown = (current close − selected peak reference) ÷ selected peak reference. Current reference is <b>{ref}</b> at approximately <b>{peak:,.0f}</b>.</div>",unsafe_allow_html=True)

with st.expander("🌦️ MARKET CONDITIONS & LIVE RISK MONITOR",expanded=False):
    st.markdown("<h1 style='font-size:34px;margin-bottom:0'>🌦️ Market Conditions & Live Risk Monitor</h1><p class='small-note'>Auto-updated where market data is available. PMI is monthly/latest-release input rather than intraday live data.</p>",unsafe_allow_html=True)
    macro=live_macro_data(); vix=macro.get("vix"); tnx=macro.get("tnx"); irx=macro.get("irx")
    latest_pmi=st.number_input("Latest PMI (monthly release)",min_value=30.0,max_value=70.0,value=51.5,step=0.1,help="PMI is not true intraday data. Use latest released PMI value.")
    curve_spread=(tnx-irx) if (tnx is not None and irx is not None) else None
    trend_below=close < m[sel]["ma200"]
    vix_score=0 if vix is None else min(max((vix-15)*2,0),30)
    curve_score=10 if curve_spread is None else (20 if curve_spread<0 else 10 if curve_spread<0.5 else 0)
    pmi_score=0 if latest_pmi>=52 else 8 if latest_pmi>=50 else 16 if latest_pmi>=47 else 20
    dd_score=min(abs(dd)*1.2,25)
    trend_score=15 if trend_below else 0
    live_score=min(vix_score+curve_score+pmi_score+dd_score+trend_score,100)
    if live_score>=70: alert,klass="CRASH RISK","alert-risk"
    elif live_score>=50: alert,klass="WARNING","alert-warning"
    elif live_score>=30: alert,klass="WATCH","alert-watch"
    else: alert,klass="NORMAL","alert-normal"
    st.markdown(f"<div class='alert-card {klass}'><h2 style='margin:0'>LIVE MARKET RISK ALERT: {alert}</h2><div class='small-note'>Risk score is calculated from VIX, yield curve, PMI, current drawdown and 200D trend.</div></div>",unsafe_allow_html=True)
    a,b,c,d,e=st.columns(5)
    with a: st.metric("VIX Live", "N/A" if vix is None else f"{vix:.1f}")
    with b: st.metric("Yield Curve", "N/A" if curve_spread is None else f"10Y-13W {curve_spread:.2f}%")
    with c: st.metric("Latest PMI", f"{latest_pmi:.1f}")
    with d: st.metric("Current Drawdown", f"{dd:.1f}%")
    with e: st.metric("Live Risk Score", f"{live_score:.0f}/100")
    st.markdown("#### 📡 Live Trigger Monitor")
    trig=pd.DataFrame([
        {"Trigger":"VIX > 25","Status":"Yes" if vix is not None and vix>25 else "No"},
        {"Trigger":"Yield curve inverted","Status":"Yes" if curve_spread is not None and curve_spread<0 else "No"},
        {"Trigger":"PMI < 50","Status":"Yes" if latest_pmi<50 else "No"},
        {"Trigger":"Drawdown < -10%","Status":"Yes" if dd<-10 else "No"},
        {"Trigger":"Below 200D MA","Status":"Yes" if trend_below else "No"},
    ])
    st.dataframe(trig,use_container_width=True,hide_index=True)

with st.expander("📊 MARKET PERFORMANCE & ETF TRACKER",expanded=False):
    st.markdown("<h1 style='font-size:34px;margin-bottom:0'>📊 Market Performance & ETF Tracker</h1>",unsafe_allow_html=True)
    try:
        for g,recs in bench().items(): st.markdown(f"### {g}"); st.dataframe(pd.DataFrame(recs),use_container_width=True,hide_index=True)
    except Exception as e: st.warning(f"Benchmarks unavailable: {e}")
    try:
        ed=etfs(); order=[sel] if sel in ETF_UNIVERSE else []
        order += [x for x in ETF_UNIVERSE if x not in order]
        for k in order:
            if k in ed: st.markdown(f"### {ETF_UNIVERSE[k]['label']}{' ✅ SELECTED' if k==sel else ''}"); st.dataframe(pd.DataFrame(ed[k]),use_container_width=True,hide_index=True)
    except Exception as e: st.warning(f"ETFs unavailable: {e}")

with st.expander("🏆 CRASH & RECOVERY ANALYTICS",expanded=False):
    st.markdown("<h1 style='font-size:34px;margin-bottom:0'>🏆 Crash & Recovery Analytics</h1>",unsafe_allow_html=True)
    try:
        st.markdown("### 📊 Executive Crash Summary")
        st.caption("The controls below define the detected crash-event universe used by the summary, cycle statistics and event explorer.")
        p,q=st.columns(2)
        with p: start=st.date_input("Historical analysis start date",value=ud.index.min().date(),min_value=ud.index.min().date(),max_value=ud.index.max().date())
        with q: thr=st.slider("Min drawdown threshold (%)",5,50,10,5)
        st.caption("Crash event drawdown formula follows the previous version: rolling 252-day peak → trough close.")
        bt=ud.loc[pd.Timestamp(start):].copy(); bt["rm"]=bt.Close.rolling(252,min_periods=1).max(); bt["dd_pct"]=((bt.Close-bt.rm)/bt.rm)*100; cur=safe_float(bt.Close.iloc[-1])
        ev=events(bt,thr,cur)
        if not ev: st.info("No drawdown events found with selected parameters.")
        else:
            k1,k2,k3,k4,k5=st.columns(5)
            with k1: st.metric("Crash Events",len(ev))
            with k2: st.metric("Success Rate",f"{sum(1 for t in ev if t['ret']>0)/len(ev)*100:.0f}%")
            with k3: st.metric("Avg Recovery",f"{np.mean([t['ret'] for t in ev]):.1f}%")
            with k4: st.metric("Best Recovery",f"{max([t['ret'] for t in ev]):.1f}%")
            with k5: st.metric("Current Drawdown",f"{bt.dd_pct.iloc[-1]:.1f}%")
            st.markdown("---")
            st.markdown("### 📚 Full Market Cycle Statistics")
            st.caption("Cycle statistics below are calculated from the same detected crash-event universe above.")
            yrs=max((bt.index.max()-bt.index.min()).days/365.25,1); d10=len([t for t in ev if -20<t['dd']<=-10]); d20=len([t for t in ev if -30<t['dd']<=-20]); d30=len([t for t in ev if t['dd']<=-30])
            a,b,c=st.columns(3)
            with a: st.info(f"📉 10–20% corrections historically occur every ~{round(yrs/d10,1) if d10 else 'N/A'} years")
            with b: st.warning(f"⚠️ 20–30% corrections historically occur every ~{round(yrs/d20,1) if d20 else 'N/A'} years")
            with c: st.error(f"🔥 30%+ crashes historically occur every ~{round(yrs/d30,1) if d30 else 'N/A'} years")
            event_df=pd.DataFrame([{"Peak Date":t['peak_dt'].strftime('%Y-%m-%d'),"Peak Index":round(t['peak'],0),"Trough Date":t['date'].strftime('%Y-%m-%d'),"Trough Index":round(t['price'],0),"Drawdown %":round(t['dd'],1),"Recovery Return %":round(t['ret'],1),"Zone":t['zone'],"Historical Label":label_event(t['date'])} for t in ev])
            event_df["Severity"]=event_df["Drawdown %"].apply(lambda v:"30%+" if v<=-30 else "20-30%" if v<=-20 else "10-20%")
            event_df["Trough Date_dt"]=pd.to_datetime(event_df["Trough Date"]).dt.date
            st.markdown("### 🔍 Interactive Event Explorer")
            f1,f2,f3=st.columns([1,1,1.2])
            with f1: sev=st.multiselect("Severity filters",["10-20%","20-30%","30%+"],default=["10-20%","20-30%","30%+"])
            with f2: zones=st.multiselect("Buy Zone filters",["INITIAL BUY","BUY","STRONG BUY"],default=["INITIAL BUY","BUY","STRONG BUY"])
            with f3: rng=st.date_input("Historical event date range",value=(event_df["Trough Date_dt"].min(),event_df["Trough Date_dt"].max()),min_value=event_df["Trough Date_dt"].min(),max_value=event_df["Trough Date_dt"].max())
            rs,re=rng if isinstance(rng,tuple) and len(rng)==2 else (event_df["Trough Date_dt"].min(),event_df["Trough Date_dt"].max())
            filt=event_df[event_df.Severity.isin(sev)&event_df.Zone.isin(zones)&(event_df["Trough Date_dt"]>=rs)&(event_df["Trough Date_dt"]<=re)].copy()
            if filt.empty: st.info("No events match the selected filters.")
            else:
                st.markdown("#### 📉 Filtered Event Table")
                st.dataframe(filt.drop(columns=["Trough Date_dt"]),use_container_width=True,hide_index=True)
                opts=[f"{r['Historical Label']} | {r['Peak Date']} → {r['Trough Date']} ({r['Drawdown %']}%)" for _,r in filt.iterrows()]
                picked=st.selectbox("Historical Crash Explorer",opts); row=filt.iloc[opts.index(picked)]
                if st.toggle("📌 Show Selected Event Deep Dive",value=True):
                    st.markdown("<div class='section-card'><h3 style='margin-top:0'>📌 Selected Event Deep Dive</h3><p class='small-note'>Deployment controls, event-level breakdown, historical label, pre-crash context and crash path visualisation.</p></div>",unsafe_allow_html=True)
                    st.markdown(f"**Historical Label:** {row['Historical Label']}")
                    amount=st.number_input("Investment for selected event (S$)",1000,value=15000,step=1000)
                    trough=safe_float(row["Trough Index"]); val=amount*(cur/trough) if trough else 0; ret=((cur/trough)-1)*100 if trough else 0
                    o1,o2,o3,o4=st.columns(4)
                    with o1: st.metric("Deployment Amount",f"S${amount:,.0f}")
                    with o2: st.metric("Entry Level",f"{row['Trough Index']:,.0f}")
                    with o3: st.metric("Value Today",f"S${val:,.0f}")
                    with o4: st.metric("Return Since Trough",f"{ret:.1f}%")
                    d1,d2,d3,d4=st.columns(4)
                    with d1: st.metric("Peak Index",f"{row['Peak Index']:,.0f}")
                    with d2: st.metric("Trough Index",f"{row['Trough Index']:,.0f}")
                    with d3: st.metric("Drawdown",f"{row['Drawdown %']:.1f}%")
                    with d4: st.metric("Recovery Return",f"{row['Recovery Return %']:.1f}%")
                    pk=pd.Timestamp(row["Peak Date"]); tr=pd.Timestamp(row["Trough Date"]); days=max((tr-pk).days,0); speed="Fast crash" if days<=90 else "Medium-speed bear market" if days<=365 else "Slow grinding bear market"
                    st.info(f"Before this drawdown, {sel} peaked at approximately {row['Peak Index']:,.0f} on {row['Peak Date']}. The index then declined to approximately {row['Trough Index']:,.0f} by {row['Trough Date']}, a drawdown of {row['Drawdown %']:.1f}% over about {days} days. Historical label: {row['Historical Label']}. This was classified as a {speed} and entered the {row['Zone']} zone based on drawdown severity.")
                    ch=bt.loc[pk:tr].copy()
                    if not ch.empty:
                        fig=go.Figure(); fig.add_trace(go.Scatter(x=ch.index,y=ch.Close,mode="lines",line=dict(color="#D32F2F",width=3))); fig.add_trace(go.Scatter(x=[pk],y=[row["Peak Index"]],mode="markers+text",text=["Peak"],textposition="top center")); fig.add_trace(go.Scatter(x=[tr],y=[row["Trough Index"]],mode="markers+text",text=["Trough"],textposition="bottom center")); fig.update_layout(height=340,title="Mini Historical Crash Chart: Peak → Trough",plot_bgcolor="white",paper_bgcolor="white",showlegend=False); st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
            st.info("📌 Historical labels are broad reference tags, not causal claims. Past performance does not guarantee future outcomes.")
            st.download_button("⬇️ Export Crash Analytics CSV",event_df.drop(columns=["Trough Date_dt"]).to_csv(index=False),file_name="crash_recovery_analytics.csv",mime="text/csv")
    except Exception as e: st.warning(f"Crash analytics unavailable: {e}")

st.markdown("---")
st.caption(f"🕒 Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} SGT")
st.caption("⚠️ Disclaimer: Educational only. Not financial advice. Past performance does not guarantee future results. Consult a licensed advisor.")
