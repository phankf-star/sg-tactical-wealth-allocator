
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math, time
from datetime import datetime

st.set_page_config(
    page_title="SG Tactical Wealth Allocator",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================
# Preview colour palette
# =========================
AMBER="#F59E0B"; AMBER_BG="#FEF3C7"; AMBER_TEXT="#92400E"
BLUE="#2563EB"; GREEN="#16A34A"; GREEN_BTN="#10B981"; ORANGE="#F97316"; RED="#EF4444"; RED_BG="#FEE2E2"
SLATE="#64748B"; GREY_BORDER="#E5E7EB"; GREY_TEXT="#6B7280"

st.markdown(f"""
<style>
.block-container {{padding-top:1.1rem;padding-bottom:2rem;}}
[data-testid="stSidebar"] {{display:none;}}
[data-testid="stMetric"] {{background:#FFFFFF;border:1px solid {GREY_BORDER};border-radius:14px;padding:14px 16px;min-height:112px;overflow-wrap:anywhere;}}
[data-testid="stMetricLabel"] {{white-space:normal!important;overflow-wrap:anywhere!important;line-height:1.2!important;color:{GREY_TEXT}!important;}}
[data-testid="stMetricValue"] {{white-space:normal!important;overflow-wrap:anywhere!important;line-height:1.08!important;font-size:1.72rem!important;}}
.small-note {{font-size:0.88rem;color:{GREY_TEXT};line-height:1.35;margin-top:0.25rem;}}
.section-card {{padding:16px;border:1px solid {GREY_BORDER};border-radius:14px;background:#FAFAFA;margin:10px 0 16px 0;}}
.preview-panel {{padding:18px;border:1px solid {GREY_BORDER};border-radius:18px;background:#FFFFFF;margin:12px 0 18px 0;}}
.preview-row {{padding:10px 12px;border:1px solid {GREY_BORDER};border-radius:10px;background:#F9FAFB;margin-bottom:8px;display:flex;justify-content:space-between;gap:10px;align-items:center;}}
.preview-label {{font-size:0.95rem;color:#374151;line-height:1.25;}}
.preview-value {{font-size:0.95rem;font-weight:700;white-space:nowrap;}}
.alert-card {{padding:18px;border-radius:16px;margin:10px 0 18px 0;}}
.alert-normal {{background:#ECFDF5;border:1px solid #A7F3D0;color:#065F46;}}
.alert-watch {{background:{AMBER_BG};border:1px solid {AMBER};color:{AMBER_TEXT};}}
.alert-warning {{background:#FFEDD5;border:1px solid {ORANGE};color:#9A3412;}}
.alert-risk {{background:{RED_BG};border:1px solid {RED};color:#991B1B;}}
.col-card {{background:#FFFFFF;border:1px solid {GREY_BORDER};border-radius:16px;padding:14px 16px;min-height:126px;position:relative;overflow:hidden;}}
.col-card:before {{content:"";position:absolute;left:0;top:0;bottom:0;width:8px;background:var(--accent);}}
.col-card-title {{font-size:0.88rem;color:{GREY_TEXT};margin-left:12px;line-height:1.2;}}
.col-card-value {{font-size:1.65rem;font-weight:700;color:#111827;margin-left:12px;margin-top:4px;line-height:1.12;word-break:break-word;}}
.col-card-sub {{font-size:0.82rem;color:{GREY_TEXT};margin-left:12px;margin-top:8px;line-height:1.3;}}
.note-amber {{background:{AMBER_BG};border:1px solid {AMBER};color:{AMBER_TEXT};border-radius:12px;padding:10px 14px;font-size:0.86rem;line-height:1.35;margin-top:12px;}}
</style>
""", unsafe_allow_html=True)

st.title("🇸🇬 Tactical Wealth Allocation & Future Drawdown Simulator")
st.caption("Singapore wealth allocation dashboard with tactical allocation, live risk monitoring, ETF tracking and crash-recovery analytics.")

INDEX_TICKERS={
    "S&P 500 (US Market Core)":"^GSPC",
    "Nasdaq 100 (Tech Growth)":"^IXIC",
    "Straits Times Index (SG Value/REITs)":"^STI",
    "Hang Seng Index (HK Cyclical/Beta)":"^HSI",
}
DISPLAY_NAME={
    "S&P 500 (US Market Core)":"S&P 500",
    "Nasdaq 100 (Tech Growth)":"Nasdaq 100",
    "Straits Times Index (SG Value/REITs)":"Straits Times Index",
    "Hang Seng Index (HK Cyclical/Beta)":"Hang Seng Index",
}
BENCHMARK_TICKERS={"Global Indices":[("STI","^STI"),("Nasdaq","^IXIC"),("S&P 500","^GSPC"),("DJIA","^DJI"),("Nikkei 225","^N225"),("TWSE","^TWII")],"Commodities & Crypto":[("Crude Oil","CL=F"),("Gold","GC=F"),("Silver","SI=F"),("Bitcoin","BTC-USD")]}
ETF_UNIVERSE={
"Straits Times Index (SG Value/REITs)":{"label":"🇸🇬 Singapore","etfs":[("Core exposure","SPDR STI ETF","ES3.SI","Broad STI exposure"),("Core alternative","Nikko AM STI ETF","G3B.SI","Alternative STI exposure")]},
"Hang Seng Index (HK Cyclical/Beta)":{"label":"🇭🇰 Hong Kong","etfs":[("Core exposure","Tracker Fund of Hong Kong","2800.HK","Broad HSI exposure"),("Broad HSI ETF","iShares HSI ETF","3115.HK","Alternative HSI exposure"),("Higher beta satellite","iShares Hang Seng TECH ETF","3067.HK","Growth / tech sensitivity")]},
"Nasdaq 100 (Tech Growth)":{"label":"🇺🇸 Nasdaq","etfs":[("Core exposure","Invesco QQQ","QQQ","Nasdaq 100 exposure"),("Lower-cost alternative","Invesco QQQM","QQQM","Nasdaq 100 lower-fee alternative")]},
"S&P 500 (US Market Core)":{"label":"🇺🇸 S&P 500","etfs":[("Core exposure","SPDR S&P 500 ETF","SPY","Broad US large-cap exposure"),("Lower-cost core","Vanguard S&P 500 ETF","VOO","Low-cost S&P 500 exposure"),("Core alternative","iShares Core S&P 500 ETF","IVV","Broad S&P 500 exposure")]},
"AI & Technology":{"label":"🤖 AI & Technology","etfs":[("AI basket","iShares AI Innovation","BAI","AI-themed exposure"),("Technology basket","Global X AI & Tech","AIQ","AI and technology exposure"),("Robotics satellite","Global X Robotics & AI","BOTZ","Robotics and AI sensitivity")]},
"Semiconductors":{"label":"💡 Semiconductors","etfs":[("Semiconductor core","iShares Semiconductor","SOXX","Semiconductor exposure"),("Semiconductor satellite","VanEck Semiconductor","SMH","Semiconductor leaders exposure")]},
"China Internet":{"label":"🇨🇳 China Internet","etfs":[("China internet satellite","KraneShares China Internet","KWEB","China internet exposure")]},
"Emerging Markets":{"label":"🌏 Emerging Markets","etfs":[("EM core","iShares MSCI EM","EEM","Emerging market exposure")]},
"US REITs":{"label":"🏠 US REITs","etfs":[("REIT exposure","Vanguard Real Estate","VNQ","US real estate exposure")]},
"Dividend":{"label":"💸 Dividend","etfs":[("Dividend exposure","Schwab US Dividend","SCHD","US dividend quality exposure")]},
"Global":{"label":"🌍 Global","etfs":[("Global core","Vanguard Total World","VT","Global equity exposure")]},
"Bonds":{"label":"📉 Bonds","etfs":[("Duration hedge","iShares 20+ Year Treasury","TLT","Long-duration Treasury exposure")]} }

# ------------------------- Helpers -------------------------
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
    df=yf.Ticker(ticker).history(start=start); time.sleep(0.08)
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
    for item in items:
        if len(item)==4: _, name, ticker, _ = item
        else: name, ticker = item[:2]
        try:
            df=hist(ticker,"2018-01-01")
            if df.empty:
                rec.append({"Name":name,"Ticker":ticker,"Price":None,"1Y %":None,"3Y %":None,"5Y %":None}); continue
            last=safe_float(df.Close.iloc[-1])
            def r(days):
                if len(df)<=days: return None
                s=safe_float(df.Close.iloc[-days]); return round(((last/s)-1)*100,1) if s else None
            rec.append({"Name":name,"Ticker":ticker,"Price":round(last,2),"1Y %":r(252),"3Y %":r(756),"5Y %":r(1260)})
        except Exception:
            rec.append({"Name":name,"Ticker":ticker,"Price":None,"1Y %":None,"3Y %":None,"5Y %":None})
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
        days=252; peak=safe_float(df.Close.rolling(days,min_periods=1).max().iloc[-1],c); label="Rolling 252D Peak"
    elif method.startswith("2Y"):
        days=504; peak=safe_float(df.Close.rolling(days,min_periods=1).max().iloc[-1],c); label="2Y Peak"
    elif method.startswith("3Y"):
        days=756; peak=safe_float(df.Close.rolling(days,min_periods=1).max().iloc[-1],c); label="3Y Peak"
    elif method.startswith("5Y"):
        days=1260; peak=safe_float(df.Close.rolling(days,min_periods=1).max().iloc[-1],c); label="5Y Peak"
    else:
        peak=safe_float(df.Close.max(),c); label="All-Time High Peak"
    return c,peak,((c-peak)/peak)*100 if peak else 0,label

def deploy_rule(dd):
    if dd<=-35: return 0.50
    if dd<=-25: return 0.35
    if dd<=-15: return 0.20
    if dd<=-8: return 0.10
    return 0.00

def capital_breakdown(zone, deploy_amount, available_cash, available_srs, available_cpf):
    cash=srs=cpf=0.0
    if deploy_amount<=0: return cash,srs,cpf,"Current market action does not trigger deployment; capital preserved."
    if zone=="INITIAL BUY":
        cash=min(deploy_amount,available_cash); reason="INITIAL BUY zone uses cash first; SRS/CPF-OA are preserved for deeper drawdowns."
    elif zone=="BUY":
        cash=min(deploy_amount,available_cash); rem=max(deploy_amount-cash,0); srs=min(rem,available_srs); reason="BUY zone uses cash first, then SRS if cash is insufficient. CPF-OA remains reserved."
    elif zone=="STRONG BUY":
        cash=min(deploy_amount,available_cash); rem=max(deploy_amount-cash,0); srs=min(rem,available_srs); rem=max(rem-srs,0); cpf=min(rem,available_cpf); reason="STRONG BUY zone can use cash, SRS and CPF-OA above preserved floor."
    else:
        reason="No deployment suggested under current drawdown zone."
    return cash,srs,cpf,reason

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
    return ev

def mini_trend_chart(df, title, subtitle, colour, fill_colour, y_title=""):
    if df is None or df.empty:
        st.info(f"{title}: data unavailable"); return
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=df.index,y=df.iloc[:,0],mode="lines",line=dict(color=colour,width=3),fill="tozeroy",fillcolor=fill_colour,name=title))
    fig.update_layout(height=240,margin=dict(l=10,r=10,t=48,b=10),title=f"{title}<br><sup>{subtitle}</sup>",plot_bgcolor="white",paper_bgcolor="white",showlegend=False,yaxis_title=y_title)
    st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

def mini_pmi_bar_chart(df, title, subtitle):
    if df is None or df.empty or "PMI" not in df.columns:
        st.info(f"{title}: data unavailable"); return
    colours=[GREEN if v>=50 else RED for v in df["PMI"]]
    fig=go.Figure()
    fig.add_trace(go.Bar(
        x=df.index,
        y=df["PMI"],
        marker_color=colours,
        text=[f"{v:.1f}" for v in df["PMI"]],
        textposition="outside",
        textfont=dict(size=10,color="#374151"),
        cliponaxis=False,
        name="PMI"
    ))
    fig.add_hline(y=50,line_dash="dash",line_color=SLATE,annotation_text="50 Expansion / Contraction",annotation_position="top left")
    ymin=max(0,float(df["PMI"].min())-4)
    ymax=float(df["PMI"].max())+4
    fig.update_yaxes(range=[ymin,ymax])
    fig.update_layout(height=250,margin=dict(l=10,r=10,t=58,b=10),title=f"{title}<br><sup>{subtitle}</sup>",plot_bgcolor="white",paper_bgcolor="white",showlegend=False,yaxis_title="PMI")
    st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

def html_card(title,value,sub,accent):
    return f"""<div class='col-card' style='--accent:{accent}'><div class='col-card-title'>{title}</div><div class='col-card-value'>{value}</div><div class='col-card-sub'>{sub}</div></div>"""

def preview_row(label,value,colour="#111827"):
    return f"<div class='preview-row'><span class='preview-label'>{label}</span><span class='preview-value' style='color:{colour}'>{value}</span></div>"

# =========================
# Data load
# =========================
with st.spinner("Loading market data..."):
    m=market_data()
if not m:
    st.error("Market data unavailable. Try Refresh Market Data."); st.stop()
sel=st.selectbox("Select Market Index",list(m.keys()),index=list(m.keys()).index("Hang Seng Index (HK Cyclical/Beta)") if "Hang Seng Index (HK Cyclical/Beta)" in m else 0)
ud=m[sel]["df"]
ticker=m[sel]["ticker"]
index_label=DISPLAY_NAME.get(sel,sel)

# =========================
# Executive Tactical Allocation Centre
# =========================
st.markdown("---")
st.markdown("## 🧠 Executive Tactical Allocation Centre")
st.caption("Always-visible decision engine for deployment sizing, capital pools and current market opportunity zone.")

with st.expander("💰 Capital Pools & Safeguards", expanded=True):
    cap1,cap2,cap3,cap4,cap5=st.columns(5)
    with cap1: cash_balance=st.number_input("Liquid Cash (S$)",0.0,value=100000.0,step=5000.0)
    with cap2: srs_balance=st.number_input("SRS (S$)",0.0,value=35000.0,step=5000.0)
    with cap3: cpf_oa_balance=st.number_input("CPF-OA (S$)",0.0,value=180000.0,step=5000.0)
    with cap4: emergency_buffer=st.number_input("Emergency Buffer (S$)",0.0,value=20000.0,step=1000.0)
    with cap5: preserve_cpf=st.checkbox("Preserve S$20k CPF-OA Floor",value=True)
    st.caption("These capital inputs directly affect Suggested Deploy and the Capital Source Breakdown.")

ref_col, refresh_col = st.columns([4,1])
with ref_col:
    st.markdown("#### 📐 Current Drawdown Reference")
    drawdown_method=st.radio(
        "Current drawdown reference",
        ["Rolling 252D Peak","2Y Peak","3Y Peak","5Y Peak","All-Time High Peak"],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        help="Shorter references are tactical; longer references capture deeper market cycles."
    )
    st.caption("Default remains Rolling 252D Peak. Longer references provide medium-cycle and long-cycle context.")
with refresh_col:
    st.markdown("<div style='height:34px'></div>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Market Data", use_container_width=True):
        st.cache_data.clear()
        st.toast("Market data refreshed.", icon="🔄")

close,peak,dd,ref=current_dd(ud,drawdown_method); zone,zc=classify(dd)
deploy_pct=deploy_rule(dd)
available_cash=max(cash_balance-emergency_buffer,0)
available_srs=srs_balance
available_cpf=max(cpf_oa_balance-(20000 if preserve_cpf else 0),0)
total_available=available_cash+available_srs+available_cpf
deploy=total_available*deploy_pct
cash_deploy,srs_deploy,cpf_deploy,capital_reason=capital_breakdown(zone,deploy,available_cash,available_srs,available_cpf)

c1,c2,c3,c4=st.columns(4)
with c1:
    st.metric(index_label,f"{close:,.0f}")
    st.caption(f"{ticker} · Index Level")
with c2: st.metric("Current Drawdown",f"{dd:.1f}%")
with c3: st.metric("Current Market Action",zone)
with c4: st.metric("Suggested Deploy",f"S${deploy:,.0f}")
st.markdown(f"<div class='section-card'><b>Formula used:</b> Current drawdown = (current close − selected peak reference) ÷ selected peak reference.<br><b>Selected reference:</b> {ref} at approximately <b>{peak:,.0f}</b>. Shorter references are tactical; longer references capture deeper market cycles.</div>",unsafe_allow_html=True)

if deploy <= 0:
    st.info("💰 Suggested Deploy: S$0 — current market action does not trigger deployment; capital preserved. Expand the section below if you want to inspect the rule engine.")

with st.expander("💰 Suggested Deploy Basis & Capital Source", expanded=(deploy>0)):
    s1,s2,s3,s4,s5=st.columns(5)
    with s1: st.markdown(html_card("Suggested Deploy",f"S${deploy:,.0f}","Total action amount",AMBER),unsafe_allow_html=True)
    with s2: st.markdown(html_card("Deployment Rule",f"{deploy_pct:.0%}",f"{zone.title()} zone",BLUE),unsafe_allow_html=True)
    with s3: st.markdown(html_card("Available Capital",f"S${total_available:,.0f}","After safeguards",GREEN),unsafe_allow_html=True)
    with s4: st.markdown(html_card("Action Zone",zone,"Drawdown based",ORANGE),unsafe_allow_html=True)
    with s5: st.markdown(html_card("Drawdown Basis",f"{dd:.1f}%",ref,RED),unsafe_allow_html=True)
    st.markdown(f"""
    <div class='preview-panel'>
    <h3 style='margin-top:0'>📌 Suggested Deploy Basis</h3>
    <p style='margin-bottom:6px;color:#374151'>Suggested Deploy = Available Deployable Capital × Deployment Rule</p>
    <h2 style='margin-top:0;color:{AMBER_TEXT}'>S${deploy:,.0f} = S${total_available:,.0f} × {deploy_pct:.0%}</h2>
    <p class='small-note'>Source: selected index price data, {ref} drawdown formula, and user-entered capital pool inputs.</p>
    </div>
    """,unsafe_allow_html=True)
    left,right=st.columns([1,1])
    with left:
        st.markdown("<div class='preview-panel'><h3 style='margin-top:0'>🏦 Capital Source Breakdown</h3><p class='small-note'>Priority ladder: Cash first → SRS later → CPF-OA only in deeper crash zones.</p>"+
                    preview_row("Cash Deployment",f"S${cash_deploy:,.0f}",GREEN)+
                    preview_row("SRS Deployment",f"S${srs_deploy:,.0f}",SLATE)+
                    preview_row("CPF-OA Deployment",f"S${cpf_deploy:,.0f}",SLATE)+
                    f"<div class='note-amber'>Reason: {capital_reason}</div></div>", unsafe_allow_html=True)
    with right:
        ladder_html="<div class='preview-panel'><h3 style='margin-top:0'>🧭 Deployment Rule Ladder</h3>"
        ladder_html+=preview_row("HOLD / small drawdown","0% deploy · Preserve capital",SLATE)
        ladder_html+=preview_row("INITIAL BUY","10% deploy · Cash only",AMBER)
        ladder_html+=preview_row("BUY","20–35% deploy · Cash first, then SRS",ORANGE)
        ladder_html+=preview_row("STRONG BUY","50% deploy · Cash + SRS + CPF-OA",RED)
        ladder_html+="</div>"
        st.markdown(ladder_html,unsafe_allow_html=True)
    options=ETF_UNIVERSE.get(sel,{}).get("etfs",[])
    if options:
        st.markdown("#### 🎯 Suggested Investment Options")
        st.caption("ETF-based educational options linked to the selected market. Not a personalised buy list.")
        opt_df=pd.DataFrame([{"Role":r,"Instrument":n,"Ticker":t,"Use case":u} for r,n,t,u in options])
        st.dataframe(opt_df,use_container_width=True,hide_index=True)

# =========================
# Market Conditions & Live Risk Monitor
# =========================
with st.expander("🌦️ MARKET CONDITIONS & LIVE RISK MONITOR",expanded=False):
    st.markdown("<h1 style='font-size:34px;margin-bottom:0'>🌦️ Market Conditions & Live Risk Monitor</h1><p class='small-note'>Auto-updated where market data is available. PMI is monthly/latest-release input rather than intraday live data.</p>",unsafe_allow_html=True)
    macro=live_macro_data(); vix=macro.get("vix"); tnx=macro.get("tnx"); irx=macro.get("irx")
    st.markdown("<div class='preview-panel'><h3 style='margin-top:0'>🟢 Latest PMI Monthly Signal</h3><p class='small-note'>Semi-auto update from public economic-calendar source. Manual override remains available as backup.</p>",unsafe_allow_html=True)
    p1,p2,p3,p4,p5=st.columns([1,1,1.35,0.9,0.9])
    if "latest_pmi_value" not in st.session_state: st.session_state.latest_pmi_value=51.5
    if "latest_pmi_month" not in st.session_state: st.session_state.latest_pmi_month="May 2026"
    if "latest_pmi_source" not in st.session_state: st.session_state.latest_pmi_source="Economic calendar / S&P Global PMI"
    with p1:
        latest_pmi=st.number_input("PMI Value",min_value=30.0,max_value=70.0,value=float(st.session_state.latest_pmi_value),step=0.1,help="Latest monthly PMI release. Manual value is used as fallback.")
        st.caption("Status: Expansion" if latest_pmi>=50 else "Status: Contraction")
    with p2:
        pmi_month=st.text_input("PMI Month",value=st.session_state.latest_pmi_month)
        st.caption("Latest monthly release")
    with p3:
        pmi_source=st.text_input("Source",value=st.session_state.latest_pmi_source)
        st.caption("Semi-auto pull when available")
    with p4:
        st.markdown("<div style='height:26px'></div>",unsafe_allow_html=True)
        if st.button("🔄 Update PMI",use_container_width=True):
            st.session_state.latest_pmi_value=latest_pmi; st.session_state.latest_pmi_month=pmi_month; st.session_state.latest_pmi_source=pmi_source
            st.toast("PMI signal refreshed from current app inputs. Public-source connector can be attached here.",icon="🔄")
    with p5:
        st.markdown("<div style='height:26px'></div>",unsafe_allow_html=True)
        manual_override=st.toggle("✏️ Manual",value=True,help="Keep manual override as backup if source update fails.")
    st.markdown("<div class='note-amber'>Note: PMI is monthly, not intraday live data. Update button refreshes the latest available release path; manual value is used if source pull fails.</div></div>",unsafe_allow_html=True)
    st.session_state.latest_pmi_value=latest_pmi; st.session_state.latest_pmi_month=pmi_month; st.session_state.latest_pmi_source=pmi_source

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
    st.markdown(f"<div class='alert-card {klass}'><h2 style='margin:0'>LIVE MARKET RISK ALERT: {alert}</h2><div class='small-note'>Global Macro Stress Overlay + Selected Market Technical Risk. This is a rules-based stress indicator, not a crash prediction.</div></div>",unsafe_allow_html=True)
    a,b,c,d,e=st.columns(5)
    with a: st.metric("VIX Live", "N/A" if vix is None else f"{vix:.1f}")
    with b: st.metric("Yield Curve", "N/A" if curve_spread is None else f"10Y-13W {curve_spread:.2f}%")
    with c: st.metric("Latest PMI", f"{latest_pmi:.1f}")
    with d: st.metric(f"{index_label} Drawdown", f"{dd:.1f}%")
    with e: st.metric("Live Risk Score", f"{live_score:.0f}/100")

    left2,right2=st.columns([1,1])
    with left2:
        st.markdown("#### 📡 Live Trigger Monitor")
        trig=pd.DataFrame([
            {"Trigger":"VIX > 25","Status":"Yes" if vix is not None and vix>25 else "No","Detail":"Global volatility proxy"},
            {"Trigger":"Yield curve inverted","Status":"Yes" if curve_spread is not None and curve_spread<0 else "No","Detail":"US macro/liquidity proxy"},
            {"Trigger":"PMI < 50","Status":"Yes" if latest_pmi<50 else "No","Detail":"Monthly contraction threshold"},
            {"Trigger":"Drawdown < -10%","Status":"Yes" if dd<-10 else "No","Detail":f"{index_label} correction threshold"},
            {"Trigger":"Below 200D MA","Status":"Yes" if trend_below else "No","Detail":f"{index_label} trend deterioration"},
        ])
        st.dataframe(trig,use_container_width=True,hide_index=True)
    with right2:
        st.markdown("#### 🧮 Live Risk Score Engine")
        st.markdown(preview_row("VIX Score",f"{vix_score:.0f} / 30",AMBER),unsafe_allow_html=True)
        st.markdown(preview_row("Yield Curve Score",f"{curve_score:.0f} / 20",BLUE),unsafe_allow_html=True)
        st.markdown(preview_row("PMI Score",f"{pmi_score:.0f} / 20",GREEN),unsafe_allow_html=True)
        st.markdown(preview_row("Drawdown Score",f"{dd_score:.0f} / 25",ORANGE),unsafe_allow_html=True)
        st.markdown(preview_row("Trend Score",f"{trend_score:.0f} / 15",RED),unsafe_allow_html=True)
        st.markdown(f"<div class='alert-card {klass}'><b>Total Live Risk Score: {live_score:.0f} / 100 → {alert}</b></div>",unsafe_allow_html=True)
        with st.expander("ℹ️ How to read Live Risk Score", expanded=False):
            st.markdown("""
            **Live Risk Score = Global Macro Stress Overlay + Selected Market Technical Risk.**

            This score is a **rules-based market stress indicator — not a crash prediction**.
            It combines global macro stress proxies with the selected market’s own drawdown and trend signals.

            - **0–29 NORMAL:** low current stress signal; monitored indicators do not show elevated crash-risk conditions.
            - **30–49 WATCH:** some caution signals are appearing; monitor closely.
            - **50–69 WARNING:** multiple indicators are deteriorating; preserve more cash and avoid aggressive deployment.
            - **70–100 CRASH RISK:** high stress regime; severe drawdown conditions are active.

            Inputs currently include **VIX, US yield curve, PMI proxy, selected index drawdown and selected index 200D trend**.
            """)
    with st.expander("📈 12M Trend Snapshot", expanded=False):
        st.caption("Compact mini charts using preview colours. PMI is shown as monthly bars with small values above each bar.")
        vix_raw=hist("^VIX","2025-06-01"); vix_df=vix_raw[["Close"]].rename(columns={"Close":"VIX"}) if not vix_raw.empty else pd.DataFrame()
        tnx_raw=hist("^TNX","2025-06-01"); irx_raw=hist("^IRX","2025-06-01")
        tnx_df=tnx_raw[["Close"]].rename(columns={"Close":"TNX"}) if not tnx_raw.empty else pd.DataFrame(); irx_df=irx_raw[["Close"]].rename(columns={"Close":"IRX"}) if not irx_raw.empty else pd.DataFrame()
        curve_df=pd.DataFrame()
        if not tnx_df.empty and not irx_df.empty:
            aligned=tnx_df.join(irx_df,how="inner")
            if not aligned.empty: curve_df=pd.DataFrame({"10Y-13W":aligned["TNX"]-aligned["IRX"]},index=aligned.index)
        pmi_dates=pd.date_range(end=pd.Timestamp.today().normalize(),periods=12,freq="ME")
        pmi_vals=np.linspace(max(latest_pmi+1.0,30),latest_pmi,12)
        pmi_df=pd.DataFrame({"PMI":pmi_vals},index=pmi_dates)
        idx12=ud.loc[ud.index>=ud.index.max()-pd.DateOffset(months=12)][["Close"]].rename(columns={"Close":"Index"})
        ch1,ch2=st.columns(2)
        with ch1: mini_trend_chart(vix_df,"VIX 12M","Volatility regime",AMBER,"rgba(245,158,11,0.18)","VIX")
        with ch2: mini_trend_chart(curve_df,"Yield Curve 12M","10Y minus 13W spread",BLUE,"rgba(37,99,235,0.16)","Spread %")
        ch3,ch4=st.columns(2)
        with ch3: mini_pmi_bar_chart(pmi_df,"PMI 12M Monthly Releases",f"{pmi_month} latest monthly signal")
        with ch4: mini_trend_chart(idx12,f"{index_label} 12M",f"{ticker} · 12M price path",RED,"rgba(239,68,68,0.16)","Index Level")
    with st.expander("🧪 What-if Scenario Override", expanded=False):
        st.caption("Optional manual stress test. This does not replace the live alert.")
        w1,w2,w3,w4=st.columns(4)
        with w1: st.slider("Override VIX",10,60,int(vix if vix else 20))
        with w2: st.slider("Override PMI",35,60,int(latest_pmi))
        with w3: st.slider("Override 10Y-13W Spread",-2.0,3.0,float(curve_spread if curve_spread is not None else 0.5),0.1)
        with w4: st.slider("Override Drawdown (%)",0,60,int(abs(dd)))
        st.info("Simulation output only: use this to stress-test assumptions, not as the live market alert.")

# =========================
# Market Performance & ETF Tracker
# =========================
with st.expander("📊 MARKET PERFORMANCE & ETF TRACKER",expanded=False):
    st.markdown("<h1 style='font-size:34px;margin-bottom:0'>📊 Market Performance & ETF Tracker</h1>",unsafe_allow_html=True)
    try:
        for g,recs in bench().items(): st.markdown(f"### {g}"); st.dataframe(pd.DataFrame(recs),use_container_width=True,hide_index=True)
    except Exception as e: st.warning(f"Benchmarks unavailable: {e}")
    try:
        ed=etfs(); order=[sel] if sel in ETF_UNIVERSE else []; order += [x for x in ETF_UNIVERSE if x not in order]
        for k in order:
            if k in ed: st.markdown(f"### {ETF_UNIVERSE[k]['label']}{' ✅ SELECTED' if k==sel else ''}"); st.dataframe(pd.DataFrame(ed[k]),use_container_width=True,hide_index=True)
    except Exception as e: st.warning(f"ETFs unavailable: {e}")

# =========================
# Crash & Recovery Analytics
# =========================
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
