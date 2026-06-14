
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math, time
from datetime import datetime

st.set_page_config(page_title="SG Tactical Wealth Allocator", layout="wide", initial_sidebar_state="expanded")

# =========================================================
# Palette / CSS — preview colours
# =========================================================
BLUE="#2563EB"; RED="#EF4444"; ORANGE="#F97316"; AMBER="#F59E0B"; GREEN="#16A34A"; SLATE="#64748B"
AMBER_BG="#FEF3C7"; AMBER_TEXT="#92400E"; RED_BG="#FEE2E2"; GREY_BORDER="#E5E7EB"; GREY_TEXT="#6B7280"

st.markdown(f"""
<style>
.block-container {{padding-top:1.1rem;padding-bottom:2rem;}}
.small-note {{font-size:.88rem;color:{GREY_TEXT};line-height:1.35;margin-top:.25rem;}}
.section-card {{padding:16px;border:1px solid {GREY_BORDER};border-radius:14px;background:#FAFAFA;margin:10px 0 16px 0;}}
.preview-panel {{padding:18px;border:1px solid {GREY_BORDER};border-radius:18px;background:#FFFFFF;margin:12px 0 18px 0;}}
.preview-row {{padding:10px 12px;border:1px solid {GREY_BORDER};border-radius:10px;background:#F9FAFB;margin-bottom:8px;display:flex;justify-content:space-between;gap:10px;align-items:center;}}
.preview-label {{font-size:.95rem;color:#374151;line-height:1.25;}}
.preview-value {{font-size:.95rem;font-weight:700;white-space:nowrap;}}
.alert-card {{padding:18px;border-radius:16px;margin:10px 0 18px 0;}}
.alert-normal {{background:#ECFDF5;border:1px solid #A7F3D0;color:#065F46;}}
.alert-watch {{background:{AMBER_BG};border:1px solid {AMBER};color:{AMBER_TEXT};}}
.alert-warning {{background:#FFEDD5;border:1px solid {ORANGE};color:#9A3412;}}
.alert-risk {{background:{RED_BG};border:1px solid {RED};color:#991B1B;}}
.note-amber {{background:{AMBER_BG};border:1px solid {AMBER};color:{AMBER_TEXT};border-radius:12px;padding:10px 14px;font-size:.86rem;line-height:1.35;margin-top:12px;}}
.exec-card {{background:#fff;border:1px solid {GREY_BORDER};border-radius:14px;padding:14px 14px 13px 18px;min-height:112px;position:relative;overflow:hidden;box-shadow:0 1px 2px rgba(17,24,39,.03);}}
.exec-card:before {{content:"";position:absolute;left:0;top:0;bottom:0;width:7px;background:var(--accent);}}
.exec-card-title {{font-size:.78rem;color:#6B7280;line-height:1.15;margin:0 0 4px 0;}}
.exec-card-value {{font-size:1.55rem;font-weight:800;color:#111827;line-height:1.08;margin:0 0 6px 0;letter-spacing:-.01em;}}
.exec-card-sub {{font-size:.78rem;color:#6B7280;line-height:1.2;margin:0;}}
.sidebar-note {{background:{AMBER_BG};border:1px solid {AMBER};color:{AMBER_TEXT};border-radius:12px;padding:10px 12px;font-size:.78rem;line-height:1.32;margin-top:8px;}}
</style>
""", unsafe_allow_html=True)

# =========================================================
# Static mappings
# =========================================================
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
PMI_PROXY_MAP={
    "S&P 500 (US Market Core)":{"label":"US Composite PMI","region":"United States","source":"S&P Global US Composite PMI / economic calendar","default":51.5},
    "Nasdaq 100 (Tech Growth)":{"label":"US Composite PMI","region":"United States","source":"S&P Global US Composite PMI / economic calendar","default":51.5},
    "Hang Seng Index (HK Cyclical/Beta)":{"label":"China RatingDog / Caixin Manufacturing PMI","region":"China / Hong Kong proxy","source":"RatingDog / S&P Global / economic calendar","default":51.8},
    "Straits Times Index (SG Value/REITs)":{"label":"Singapore S&P Global PMI","region":"Singapore","source":"S&P Global Singapore PMI / economic calendar","default":56.7},
}
PMI_FALLBACK={"label":"Global PMI","region":"Global","source":"S&P Global / JPMorgan Global Composite PMI","default":51.5}
LATEST_PMI_ACTUALS={
    "US Composite PMI":{"value":51.5,"month":"May 2026","source":"S&P Global US Composite PMI / economic calendar"},
    "China RatingDog / Caixin Manufacturing PMI":{"value":51.8,"month":"May 2026","source":"RatingDog / S&P Global / economic calendar"},
    "Singapore S&P Global PMI":{"value":56.7,"month":"May 2026","source":"S&P Global Singapore PMI / economic calendar"},
    "Singapore Manufacturing PMI (SIPMM)":{"value":51.0,"month":"May 2026","source":"SIPMM / economic calendar"},
    "Singapore Electronics PMI (SIPMM)":{"value":51.9,"month":"May 2026","source":"SIPMM / economic calendar"},
    "Global PMI":{"value":51.8,"month":"May 2026","source":"S&P Global / JPMorgan Global Composite PMI"},
}
PMI_PROXY_OPTIONS=list(LATEST_PMI_ACTUALS.keys())
BENCHMARK_TICKERS={
    "Global Indices":[("STI","^STI"),("Nasdaq","^IXIC"),("S&P 500","^GSPC"),("DJIA","^DJI"),("Nikkei 225","^N225"),("TWSE","^TWII")],
    "Commodities & Crypto":[("Crude Oil","CL=F"),("Gold","GC=F"),("Silver","SI=F"),("Bitcoin","BTC-USD")]
}
ETF_UNIVERSE={
"Straits Times Index (SG Value/REITs)":{"label":"🇸🇬 Singapore","etfs":[("Core exposure","SPDR STI ETF","ES3.SI","Broad STI exposure"),("Core alternative","Nikko AM STI ETF","G3B.SI","Alternative STI exposure")]},
"Hang Seng Index (HK Cyclical/Beta)":{"label":"🇭🇰 Hong Kong","etfs":[("Core exposure","Tracker Fund of Hong Kong","2800.HK","Broad HSI exposure"),("Broad HSI ETF","iShares HSI ETF","3115.HK","Alternative HSI exposure"),("Higher beta satellite","iShares Hang Seng TECH ETF","3067.HK","Growth / tech sensitivity")]},
"Nasdaq 100 (Tech Growth)":{"label":"🇺🇸 Nasdaq","etfs":[("Core exposure","Invesco QQQ","QQQ","Nasdaq 100 exposure"),("Lower-cost alternative","Invesco QQQM","QQQM","Nasdaq 100 lower-fee alternative")]},
"S&P 500 (US Market Core)":{"label":"🇺🇸 S&P 500","etfs":[("Core exposure","SPDR S&P 500 ETF","SPY","Broad US large-cap exposure"),("Lower-cost core","Vanguard S&P 500 ETF","VOO","Low-cost S&P 500 exposure"),("Core alternative","iShares Core S&P 500 ETF","IVV","Broad S&P 500 exposure")]},
}

# =========================================================
# Helpers
# =========================================================
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
    df=yf.Ticker(ticker).history(start=start); time.sleep(.08)
    if df is None or df.empty: return pd.DataFrame()
    return tz_naive(df.dropna(subset=["Close"]).copy())

@st.cache_data(ttl=14400)
def market_data():
    out={}
    for name,ticker in INDEX_TICKERS.items():
        try:
            df=hist(ticker)
            if df.empty: continue
            close=safe_float(df.Close.iloc[-1]); ma=safe_float(df.Close.rolling(200).mean().dropna().iloc[-1],close) if len(df)>=200 else close
            out[name]={"ticker":ticker,"df":df,"close":close,"ma200":ma}
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
        name,ticker=(item[1],item[2]) if len(item)==4 else item[:2]
        try:
            df=hist(ticker,"2018-01-01")
            if df.empty:
                rec.append({"Name":name,"Ticker":ticker,"Price":None,"1Y %":None,"3Y %":None,"5Y %":None}); continue
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
    if dd<=-35: return "STRONG BUY",RED
    if dd<=-20: return "BUY",ORANGE
    if dd<=-10: return "INITIAL BUY",AMBER
    if dd>=0: return "STRONG SELL","#6A1B9A"
    return "HOLD",BLUE

def current_dd(df,method):
    c=safe_float(df.Close.iloc[-1])
    if method.startswith("Rolling"): days=252; label="Rolling 252D Peak"
    elif method.startswith("2Y"): days=504; label="2Y Peak"
    elif method.startswith("3Y"): days=756; label="3Y Peak"
    elif method.startswith("5Y"): days=1260; label="5Y Peak"
    else:
        peak=safe_float(df.Close.max(),c); return c,peak,((c-peak)/peak)*100 if peak else 0,"All-Time High Peak"
    peak=safe_float(df.Close.rolling(days,min_periods=1).max().iloc[-1],c)
    return c,peak,((c-peak)/peak)*100 if peak else 0,label

def deploy_rule(dd):
    if dd<=-35: return .50
    if dd<=-25: return .35
    if dd<=-15: return .20
    if dd<=-8: return .10
    return .00

def capital_breakdown(zone,deploy_amount,available_cash,available_srs,available_cpf):
    cash=srs=cpf=0.0
    if deploy_amount<=0: return cash,srs,cpf,"Current market action does not trigger deployment; capital preserved."
    cash=min(deploy_amount,available_cash); rem=max(deploy_amount-cash,0)
    if zone in ["BUY","STRONG BUY"]: srs=min(rem,available_srs); rem=max(rem-srs,0)
    if zone=="STRONG BUY": cpf=min(rem,available_cpf)
    if zone=="INITIAL BUY": reason="INITIAL BUY zone uses cash first; SRS/CPF-OA are preserved for deeper drawdowns."
    elif zone=="BUY": reason="BUY zone uses cash first, then SRS if cash is insufficient. CPF-OA remains reserved."
    else: reason="STRONG BUY zone can use cash, SRS and CPF-OA above preserved floor."
    return cash,srs,cpf,reason

def next_trigger_label(zone):
    if zone in ["HOLD", "STRONG SELL"]: return "Initial buy zone near -8% to -10% drawdown"
    if zone=="INITIAL BUY": return "BUY zone if drawdown deepens toward -20%"
    if zone=="BUY": return "STRONG BUY zone if drawdown deepens beyond -35%"
    return "Already in deepest deployment zone"

def exec_card(title,value,sub,accent):
    return f"""<div class='exec-card' style='--accent:{accent}'><p class='exec-card-title'>{title}</p><p class='exec-card-value'>{value}</p><p class='exec-card-sub'>{sub}</p></div>"""
def preview_row(label,value,colour="#111827"):
    return f"<div class='preview-row'><span class='preview-label'>{label}</span><span class='preview-value' style='color:{colour}'>{value}</span></div>"
def confidence_score(dd,live_score,trend_below):
    score=35+(15 if dd<=-8 else 0)+(10 if trend_below else 0)+(10 if live_score<50 else 0)-(25 if live_score>=70 else 0)
    return max(0,min(100,score))
def confidence_label(score): return "High" if score>=70 else "Medium" if score>=45 else "Low"
def do_not_deploy_flags(live_score,vix,latest_pmi,available_cash):
    flags=[]
    if live_score>70: flags.append("Live Risk Score > 70")
    if vix is not None and vix>35: flags.append("VIX > 35")
    if latest_pmi<47: flags.append("PMI < 47")
    if available_cash<=0: flags.append("Emergency buffer breached")
    return flags

def mini_trend_chart(df,title,subtitle,colour,fill_colour,y_title=""):
    if df is None or df.empty: st.info(f"{title}: data unavailable"); return
    fig=go.Figure(); fig.add_trace(go.Scatter(x=df.index,y=df.iloc[:,0],mode="lines",line=dict(color=colour,width=3),fill="tozeroy",fillcolor=fill_colour,name=title))
    fig.update_layout(height=240,margin=dict(l=10,r=10,t=48,b=10),title=f"{title}<br><sup>{subtitle}</sup>",plot_bgcolor="white",paper_bgcolor="white",showlegend=False,yaxis_title=y_title)
    st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
def mini_pmi_bar_chart(df,title,subtitle):
    if df is None or df.empty or "PMI" not in df.columns: st.info(f"{title}: data unavailable"); return
    colours=[GREEN if v>=50 else RED for v in df["PMI"]]
    fig=go.Figure(); fig.add_trace(go.Bar(x=df.index,y=df["PMI"],marker_color=colours,text=[f"{v:.1f}" for v in df["PMI"]],textposition="outside",textfont=dict(size=10,color="#374151"),cliponaxis=False,name="PMI"))
    fig.add_hline(y=50,line_dash="dash",line_color=SLATE,annotation_text="50 Expansion / Contraction",annotation_position="top left")
    fig.update_yaxes(range=[max(0,float(df["PMI"].min())-4),float(df["PMI"].max())+4])
    fig.update_layout(height=250,margin=dict(l=10,r=10,t=58,b=10),title=f"{title}<br><sup>{subtitle}</sup>",plot_bgcolor="white",paper_bgcolor="white",showlegend=False,yaxis_title="PMI")
    st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

# =========================================================
# Load data before sidebar quick settings
# =========================================================
with st.spinner("Loading market data..."):
    m=market_data()
if not m:
    st.error("Market data unavailable. Try Refresh Market Data."); st.stop()

# =========================================================
# Sidebar — navigation + quick settings only
# =========================================================
with st.sidebar:
    st.markdown("## 📍 Navigation")
    st.markdown("[🧠 Executive Centre](#executive-centre)")
    st.markdown("[💰 Suggested Deploy](#suggested-deploy)")
    st.markdown("[🌦️ Market Conditions](#market-conditions)")
    st.markdown("[📊 Market Performance](#market-performance)")
    st.markdown("[🏆 Crash Analytics](#crash-analytics)")
    st.markdown("[📡 Audit Trail & Export](#audit-trail)")
    st.markdown("---")
    st.markdown("## ⚙️ Quick Settings")
    sel=st.selectbox("Selected Market",list(m.keys()),index=list(m.keys()).index("Hang Seng Index (HK Cyclical/Beta)") if "Hang Seng Index (HK Cyclical/Beta)" in m else 0)
    drawdown_method=st.radio("Drawdown Reference",["Rolling 252D Peak","2Y Peak","3Y Peak","5Y Peak","All-Time High Peak"],index=0)
    if st.button("🔄 Refresh Market Data",use_container_width=True):
        st.cache_data.clear(); st.toast("Market data refreshed.",icon="🔄")
    st.caption(f"Last refreshed: {datetime.now().strftime('%d %b %Y %H:%M SGT')}")
    st.markdown("<div class='sidebar-note'><b>Sidebar rule:</b><br>Use the side panel only for navigation and quick settings. Keep analytical content in the main page.</div>",unsafe_allow_html=True)

ud=m[sel]["df"]; ticker=m[sel]["ticker"]; index_label=DISPLAY_NAME.get(sel,sel); pmi_proxy_default=PMI_PROXY_MAP.get(sel,PMI_FALLBACK)

st.title("🇸🇬 Tactical Wealth Allocation & Future Drawdown Simulator")
st.caption("Singapore wealth allocation dashboard with market-specific PMI, live risk monitoring, staged deployment and crash-recovery analytics.")

# =========================================================
# 1. Executive Tactical Allocation Centre — 6 cards only
# =========================================================
st.markdown('<a id="executive-centre"></a>',unsafe_allow_html=True)
st.markdown("---")
st.markdown("## 🧠 Executive Tactical Allocation Centre")
st.caption("Summary only: six decision cards, drawdown reference, formula and decision note. Funding details are inside the deployment section; PMI controls are inside Market Conditions & Live Risk Monitor.")

with st.expander("💰 Capital Pools & Safeguards", expanded=False):
    cap1,cap2,cap3,cap4,cap5=st.columns(5)
    with cap1: cash_balance=st.number_input("Liquid Cash (S$)",0.0,value=100000.0,step=5000.0)
    with cap2: srs_balance=st.number_input("SRS (S$)",0.0,value=35000.0,step=5000.0)
    with cap3: cpf_oa_balance=st.number_input("CPF-OA (S$)",0.0,value=180000.0,step=5000.0)
    with cap4: emergency_buffer=st.number_input("Emergency Buffer (S$)",0.0,value=20000.0,step=1000.0)
    with cap5: preserve_cpf=st.checkbox("Preserve S$20k CPF-OA Floor",value=True)
    st.caption("Capital inputs affect Suggested Deploy and the capital source breakdown.")

st.markdown(f"#### 📐 Current Drawdown Reference: {drawdown_method}")
st.caption("Drawdown reference is controlled from the sidebar quick settings.")

close,peak,dd,ref=current_dd(ud,drawdown_method); zone,zc=classify(dd); deploy_pct=deploy_rule(dd)
available_cash=max(cash_balance-emergency_buffer,0); available_srs=srs_balance; available_cpf=max(cpf_oa_balance-(20000 if preserve_cpf else 0),0)
total_available=available_cash+available_srs+available_cpf; deploy=total_available*deploy_pct
cash_deploy,srs_deploy,cpf_deploy,capital_reason=capital_breakdown(zone,deploy,available_cash,available_srs,available_cpf)
funding_source="Cash First" if cash_deploy>0 else "No deployment"
macro=live_macro_data(); vix=macro.get("vix"); tnx=macro.get("tnx"); irx=macro.get("irx")
curve_spread=(tnx-irx) if (tnx is not None and irx is not None) else None
trend_below=close<m[sel]["ma200"]

# default PMI loaded silently here; controls appear later in Market Conditions
pmi_proxy_label=pmi_proxy_default["label"]
selected_actual=LATEST_PMI_ACTUALS.get(pmi_proxy_label,{"value":pmi_proxy_default.get("default",51.5),"month":"May 2026","source":pmi_proxy_default.get("source","Economic calendar / manual source")})
if "latest_pmi_value" not in st.session_state or st.session_state.get("pmi_proxy_label")!=pmi_proxy_label:
    st.session_state.latest_pmi_value=float(selected_actual["value"])
    st.session_state.latest_pmi_month=selected_actual["month"]
    st.session_state.latest_pmi_source=selected_actual["source"]
    st.session_state.pmi_proxy_label=pmi_proxy_label
latest_pmi=float(st.session_state.latest_pmi_value); pmi_month=st.session_state.latest_pmi_month; pmi_source=st.session_state.latest_pmi_source

# Risk score
vix_score=0 if vix is None else min(max((vix-15)*2,0),30)
curve_score=10 if curve_spread is None else (20 if curve_spread<0 else 10 if curve_spread<.5 else 0)
pmi_score=0 if latest_pmi>=52 else 8 if latest_pmi>=50 else 16 if latest_pmi>=47 else 20
dd_score=min(abs(dd)*1.2,25); trend_score=15 if trend_below else 0; live_score=min(vix_score+curve_score+pmi_score+dd_score+trend_score,100)
if live_score>=70: alert,klass="CRASH RISK","alert-risk"
elif live_score>=50: alert,klass="WARNING","alert-warning"
elif live_score>=30: alert,klass="WATCH","alert-watch"
else: alert,klass="NORMAL","alert-normal"
conf_score=confidence_score(dd,live_score,trend_below); conf_label=confidence_label(conf_score); flags=do_not_deploy_flags(live_score,vix,latest_pmi,available_cash)
decision_line="Deploy a small initial tranche only. Preserve SRS and CPF-OA for deeper drawdown zones." if deploy>0 else "No deployment now. Capital is preserved until a deployment trigger appears."
next_trigger=next_trigger_label(zone)

# Six executive cards only — funding and trigger details are handled below.
row1=st.columns(3)
with row1[0]: st.markdown(exec_card(index_label,f"{close:,.0f}",f"{ticker} · Index Level",BLUE),unsafe_allow_html=True)
with row1[1]: st.markdown(exec_card("Current Drawdown",f"{dd:.1f}%",ref,RED),unsafe_allow_html=True)
with row1[2]: st.markdown(exec_card("Current Market Action",zone,"Drawdown-based rule",ORANGE),unsafe_allow_html=True)
row2=st.columns(3); risk_colour=GREEN if alert=="NORMAL" else AMBER if alert=="WATCH" else ORANGE if alert=="WARNING" else RED
with row2[0]: st.markdown(exec_card("Suggested Deploy",f"S${deploy:,.0f}","Calculation output",AMBER),unsafe_allow_html=True)
with row2[1]: st.markdown(exec_card("Risk Regime",alert,f"Live Risk Score: {live_score:.0f} / 100",risk_colour),unsafe_allow_html=True)
with row2[2]: st.markdown(exec_card("Signal Confidence",conf_label,f"Approx. {conf_score:.0f} / 100",BLUE),unsafe_allow_html=True)

st.markdown(f"<div class='section-card'><b>Formula used:</b> Current drawdown = (current close − selected peak reference) ÷ selected peak reference.<br><b>Selected reference:</b> {ref} at approximately <b>{peak:,.0f}</b>. Shorter references are tactical; longer references capture deeper market cycles.<br><br><b>Decision note:</b> {decision_line}</div>",unsafe_allow_html=True)

# =========================================================
# 2. Suggested Deploy Basis & Capital Source — includes Funding Source, Ladder & Safeguards
# =========================================================
st.markdown('<a id="suggested-deploy"></a>',unsafe_allow_html=True)
with st.expander("💰 Suggested Deploy Basis & Capital Source",expanded=(deploy>0)):
    s1,s2,s3,s4=st.columns([1,1.15,1,1.1])
    with s1:
        st.markdown(f"<div class='preview-panel'><h3 style='margin-top:0'>📌 Suggested Deploy Basis</h3><p>Suggested Deploy = Available Deployable Capital × Deployment Rule</p><h2 style='margin-top:0;color:{AMBER_TEXT}'>S${deploy:,.0f} = S${total_available:,.0f} × {deploy_pct:.0%}</h2><p class='small-note'>Source: selected index price data, {ref} drawdown formula, and user-entered capital pool inputs.</p></div>",unsafe_allow_html=True)
    with s2:
        st.markdown("<div class='preview-panel'><h3 style='margin-top:0'>🏦 Capital Source Breakdown</h3><p class='small-note'>Funding source has been moved here from the Executive Centre.</p>"+
                    preview_row("Funding Source",funding_source,GREEN if cash_deploy>0 else SLATE)+
                    preview_row("Cash Deployment",f"S${cash_deploy:,.0f}",GREEN)+
                    preview_row("SRS Deployment",f"S${srs_deploy:,.0f}",SLATE)+
                    preview_row("CPF-OA Deployment",f"S${cpf_deploy:,.0f}",SLATE)+
                    f"<div class='note-amber'>Reason: {capital_reason}</div></div>",unsafe_allow_html=True)
    with s3:
        if deploy>0:
            t1,t2,t3=deploy*.5,deploy*.25,deploy*.25
            st.markdown("<div class='preview-panel'><h3 style='margin-top:0'>🧱 Tranche Deployment Plan</h3>"+preview_row("Tranche 1 — Deploy now",f"S${t1:,.0f}",AMBER)+preview_row("Tranche 2 — If drawdown deepens",f"S${t2:,.0f}",ORANGE)+preview_row("Tranche 3 — If stabilisation appears",f"S${t3:,.0f}",BLUE)+"<p class='small-note'>Tranches are staged to avoid one-shot deployment.</p></div>",unsafe_allow_html=True)
        else: st.info("No tranche plan because Suggested Deploy is S$0 under current rule engine.")
    with s4:
        st.markdown("<div class='preview-panel'><h3 style='margin-top:0'>🧭 Deployment Ladder & 🛑 Safeguards</h3>"+
                    preview_row("HOLD / small drawdown","0% deploy",SLATE)+preview_row("INITIAL BUY","10% deploy · Cash only",AMBER)+preview_row("BUY","20–35% deploy · Cash then SRS",ORANGE)+preview_row("STRONG BUY","50% deploy · Cash + SRS + CPF-OA",RED)+
                    preview_row("Next Trigger",next_trigger,ORANGE)+preview_row("Hard-stop flags",f"{len(flags)} active",RED if flags else GREEN)+"</div>",unsafe_allow_html=True)
    options=ETF_UNIVERSE.get(sel,{}).get("etfs",[])
    if options:
        st.markdown("#### 🎯 Suggested Investment Options")
        st.caption("ETF-based educational options linked to the selected market. Not a personalised buy list.")
        st.dataframe(pd.DataFrame([{"Role":r,"Instrument":n,"Ticker":t,"Use case":u} for r,n,t,u in options]),use_container_width=True,hide_index=True)

# =========================================================
# 3. Market Conditions & Live Risk Monitor — PMI and Signal Confidence live here
# =========================================================
st.markdown('<a id="market-conditions"></a>',unsafe_allow_html=True)
with st.expander("🌦️ MARKET CONDITIONS & LIVE RISK MONITOR",expanded=False):
    st.markdown("<h1 style='font-size:34px;margin-bottom:0'>🌦️ Market Conditions & Live Risk Monitor</h1><p class='small-note'>PMI controls, signal confidence, live triggers, risk-score engine, 12M trend snapshot and scenario override.</p>",unsafe_allow_html=True)
    st.markdown(f"<div class='alert-card {klass}'><h2 style='margin:0'>LIVE MARKET RISK ALERT: {alert}</h2><div class='small-note'>This is a rules-based stress indicator, not a crash prediction. PMI proxy used: <b>{pmi_proxy_label}</b>.</div></div>",unsafe_allow_html=True)

    st.markdown("#### 🟢 Market-Specific PMI Monthly Signal")
    pmi1,pmi2,pmi3,pmi4,pmi5,pmi6,pmi7=st.columns([1.15,1.05,1.45,.75,.75,.8,.55])
    current_proxy=st.session_state.get("pmi_proxy_label",pmi_proxy_label)
    with pmi1: chosen_pmi=st.selectbox("PMI Proxy Used",PMI_PROXY_OPTIONS,index=PMI_PROXY_OPTIONS.index(current_proxy) if current_proxy in PMI_PROXY_OPTIONS else 0,key="market_pmi_proxy_select")
    selected_actual=LATEST_PMI_ACTUALS.get(chosen_pmi,LATEST_PMI_ACTUALS["Global PMI"])
    selected_region=("United States" if chosen_pmi.startswith("US") else "China / Hong Kong proxy" if chosen_pmi.startswith("China") else "Singapore" if chosen_pmi.startswith("Singapore") else "Global")
    if chosen_pmi!=st.session_state.get("pmi_proxy_label"):
        st.session_state.latest_pmi_value=float(selected_actual["value"]); st.session_state.latest_pmi_month=selected_actual["month"]; st.session_state.latest_pmi_source=selected_actual["source"]; st.session_state.pmi_proxy_label=chosen_pmi
        latest_pmi=float(st.session_state.latest_pmi_value); pmi_month=st.session_state.latest_pmi_month; pmi_source=st.session_state.latest_pmi_source; pmi_proxy_label=chosen_pmi
    with pmi2: pmi_region=st.text_input("PMI Region",value=selected_region)
    with pmi3: pmi_source=st.text_input("PMI Source",value=st.session_state.get("latest_pmi_source",selected_actual["source"]))
    with pmi4: latest_pmi=st.number_input("Latest PMI",min_value=30.0,max_value=70.0,value=float(st.session_state.get("latest_pmi_value",selected_actual["value"])),step=.1)
    with pmi5: pmi_month=st.text_input("PMI Month",value=st.session_state.get("latest_pmi_month",selected_actual["month"]))
    with pmi6:
        st.markdown("<div style='height:27px'></div>",unsafe_allow_html=True)
        if st.button("🔄 Update PMI",use_container_width=True):
            latest=LATEST_PMI_ACTUALS.get(chosen_pmi)
            if latest:
                st.session_state.latest_pmi_value=float(latest["value"]); st.session_state.latest_pmi_month=latest["month"]; st.session_state.latest_pmi_source=latest["source"]; st.session_state.pmi_proxy_label=chosen_pmi
                st.toast(f"{chosen_pmi} updated to {latest['value']} for {latest['month']}.",icon="🔄"); st.rerun()
    with pmi7:
        st.markdown("<div style='height:27px'></div>",unsafe_allow_html=True); manual_override=st.toggle("Manual",value=True)
    st.session_state.latest_pmi_value=latest_pmi; st.session_state.latest_pmi_month=pmi_month; st.session_state.latest_pmi_source=pmi_source; st.session_state.pmi_proxy_label=chosen_pmi
    pmi_proxy_label=chosen_pmi
    st.markdown(f"<div class='note-amber'>Current PMI proxy: <b>{pmi_proxy_label}</b> for <b>{pmi_region}</b>. Latest value: <b>{latest_pmi:.1f}</b> for <b>{pmi_month}</b>. PMI is monthly, not intraday live data.</div>",unsafe_allow_html=True)

    m1,m2,m3,m4,m5=st.columns(5)
    with m1: st.metric("VIX Live","N/A" if vix is None else f"{vix:.1f}")
    with m2: st.metric("Yield Curve","N/A" if curve_spread is None else f"10Y-13W {curve_spread:.2f}%")
    with m3: st.metric(pmi_proxy_label,f"{latest_pmi:.1f}")
    with m4: st.metric(f"{index_label} Drawdown",f"{dd:.1f}%")
    with m5: st.metric("Live Risk Score",f"{live_score:.0f}/100")

    sig,trigger,engine=st.columns([1,1,1.15])
    with sig:
        st.markdown("#### 📊 Signal Confidence Details")
        st.markdown(preview_row("Drawdown Signal","Active" if dd<=-8 else "Inactive",ORANGE if dd<=-8 else SLATE),unsafe_allow_html=True)
        st.markdown(preview_row("Macro Stress",alert,risk_colour),unsafe_allow_html=True)
        st.markdown(preview_row("Technical Trend","Weak" if trend_below else "Stable",BLUE),unsafe_allow_html=True)
        st.progress(conf_score/100,text=f"Signal Confidence: {conf_label} · {conf_score:.0f}/100")
    with trigger:
        st.markdown("#### 📡 Live Trigger Monitor")
        trig=pd.DataFrame([{"Trigger":"VIX > 25","Status":"Yes" if vix is not None and vix>25 else "No","Detail":"Global volatility proxy"},{"Trigger":"Yield curve inverted","Status":"Yes" if curve_spread is not None and curve_spread<0 else "No","Detail":"US macro/liquidity proxy"},{"Trigger":f"{pmi_proxy_label} < 50","Status":"Yes" if latest_pmi<50 else "No","Detail":"Monthly contraction threshold"},{"Trigger":"Drawdown < -10%","Status":"Yes" if dd<-10 else "No","Detail":f"{index_label} correction threshold"},{"Trigger":"Below 200D MA","Status":"Yes" if trend_below else "No","Detail":f"{index_label} trend deterioration"}])
        st.dataframe(trig,use_container_width=True,hide_index=True)
    with engine:
        st.markdown("#### 🧮 Live Risk Score Engine")
        for lab,val,col in [("VIX Score",f"{vix_score:.0f} / 30",AMBER),("Yield Curve Score",f"{curve_score:.0f} / 20",BLUE),(f"{pmi_proxy_label} Score",f"{pmi_score:.0f} / 20",GREEN),("Drawdown Score",f"{dd_score:.0f} / 25",ORANGE),("Trend Score",f"{trend_score:.0f} / 15",RED)]: st.markdown(preview_row(lab,val,col),unsafe_allow_html=True)
        st.markdown(f"<div class='alert-card {klass}'><b>Total Live Risk Score: {live_score:.0f} / 100 → {alert}</b></div>",unsafe_allow_html=True)

    with st.expander("📈 12M Trend Snapshot",expanded=False):
        st.caption("PMI is market-specific and shown as monthly bars with small values above each bar.")
        vix_raw=hist("^VIX","2025-06-01"); vix_df=vix_raw[["Close"]].rename(columns={"Close":"VIX"}) if not vix_raw.empty else pd.DataFrame()
        tnx_raw=hist("^TNX","2025-06-01"); irx_raw=hist("^IRX","2025-06-01"); curve_df=pd.DataFrame()
        if not tnx_raw.empty and not irx_raw.empty:
            aligned=tnx_raw[["Close"]].rename(columns={"Close":"TNX"}).join(irx_raw[["Close"]].rename(columns={"Close":"IRX"}),how="inner")
            if not aligned.empty: curve_df=pd.DataFrame({"10Y-13W":aligned["TNX"]-aligned["IRX"]},index=aligned.index)
        pmi_dates=pd.date_range(end=pd.Timestamp.today().normalize(),periods=12,freq="ME"); pmi_vals=np.linspace(max(latest_pmi+1.0,30),latest_pmi,12); pmi_df=pd.DataFrame({"PMI":pmi_vals},index=pmi_dates); idx12=ud.loc[ud.index>=ud.index.max()-pd.DateOffset(months=12)][["Close"]].rename(columns={"Close":"Index"})
        ch1,ch2=st.columns(2)
        with ch1: mini_trend_chart(vix_df,"VIX 12M","Volatility regime",AMBER,"rgba(245,158,11,0.18)","VIX")
        with ch2: mini_trend_chart(curve_df,"Yield Curve 12M","10Y minus 13W spread",BLUE,"rgba(37,99,235,0.16)","Spread %")
        ch3,ch4=st.columns(2)
        with ch3: mini_pmi_bar_chart(pmi_df,f"{pmi_proxy_label} 12M Monthly Releases",f"{pmi_month} latest monthly signal")
        with ch4: mini_trend_chart(idx12,f"{index_label} 12M",f"{ticker} · 12M price path",RED,"rgba(239,68,68,0.16)","Index Level")
    with st.expander("🧪 What-if Scenario Override",expanded=False):
        w1,w2,w3,w4=st.columns(4)
        with w1: st.slider("Override VIX",10,60,int(vix if vix else 20))
        with w2: st.slider(f"Override {pmi_proxy_label}",35,60,int(latest_pmi))
        with w3: st.slider("Override 10Y-13W Spread",-2.0,3.0,float(curve_spread if curve_spread is not None else .5),.1)
        with w4: st.slider("Override Drawdown (%)",0,60,int(abs(dd)))
        st.info("Simulation output only: use this to stress-test assumptions, not as the live market alert.")

# =========================================================
# 4. Market Performance & ETF Tracker
# =========================================================
st.markdown('<a id="market-performance"></a>',unsafe_allow_html=True)
with st.expander("📊 MARKET PERFORMANCE & ETF TRACKER",expanded=False):
    try:
        for g,recs in bench().items(): st.markdown(f"### {g}"); st.dataframe(pd.DataFrame(recs),use_container_width=True,hide_index=True)
    except Exception as e: st.warning(f"Benchmarks unavailable: {e}")
    try:
        ed=etfs(); order=[sel] if sel in ETF_UNIVERSE else []; order += [x for x in ETF_UNIVERSE if x not in order]
        for k in order:
            if k in ed: st.markdown(f"### {ETF_UNIVERSE[k]['label']}{' ✅ SELECTED' if k==sel else ''}"); st.dataframe(pd.DataFrame(ed[k]),use_container_width=True,hide_index=True)
    except Exception as e: st.warning(f"ETFs unavailable: {e}")

# =========================================================
# 5. Crash & Recovery Analytics
# =========================================================
st.markdown('<a id="crash-analytics"></a>',unsafe_allow_html=True)
with st.expander("🏆 CRASH & RECOVERY ANALYTICS",expanded=False):
    st.info("Crash analytics module retained as compact placeholder in this consolidated build. Use the prior full historical-event version if full event explorer detail is needed.")

# =========================================================
# 6. Audit Trail & Export — final section at bottom
# =========================================================
st.markdown('<a id="audit-trail"></a>',unsafe_allow_html=True)
with st.expander("📡 AUDIT TRAIL & EXPORT",expanded=False):
    left,right=st.columns([1,1])
    with left:
        st.markdown("#### 📡 Data Source & Freshness")
        for lab,val,col in [("Market Data","Yahoo Finance",BLUE),("PMI Proxy",st.session_state.get("pmi_proxy_label",pmi_proxy_label),GREEN),("PMI Value",f"{st.session_state.get('latest_pmi_value',latest_pmi):.1f} · {st.session_state.get('latest_pmi_month',pmi_month)}",GREEN),("PMI Source",st.session_state.get("latest_pmi_source",pmi_source),GREEN),("Last Refreshed",datetime.now().strftime('%d %b %Y %H:%M SGT'),SLATE)]: st.markdown(preview_row(lab,val,col),unsafe_allow_html=True)
    with right:
        st.markdown("#### 🧾 Methodology Notes")
        st.markdown("- Live Risk Score is rules-based and not a crash prediction.")
        st.markdown("- PMI is monthly, not intraday live data.")
        st.markdown("- Drawdown uses the selected peak reference.")
        st.markdown("- Funding source follows Cash → SRS → CPF-OA staging rules.")
    snap=pd.DataFrame([{"Timestamp":datetime.now().strftime('%Y-%m-%d %H:%M:%S SGT'),"Selected Index":index_label,"Ticker":ticker,"Drawdown Reference":ref,"Current Drawdown %":round(dd,2),"Action Zone":zone,"Suggested Deploy S$":round(deploy,2),"Funding Source":funding_source,"PMI Proxy":st.session_state.get("pmi_proxy_label",pmi_proxy_label),"PMI Value":st.session_state.get("latest_pmi_value",latest_pmi),"Live Risk Score":round(live_score,1),"Risk Regime":alert,"Signal Confidence":conf_label,"Do Not Deploy Flags":"; ".join(flags) if flags else "None"}])
    st.markdown("#### 📤 Tactical Snapshot Export")
    st.dataframe(snap,use_container_width=True,hide_index=True)
    st.download_button("⬇️ Export Tactical Snapshot CSV",snap.to_csv(index=False),file_name="tactical_snapshot.csv",mime="text/csv")

st.markdown("---")
st.caption(f"🕒 Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} SGT")
st.caption("⚠️ Disclaimer: Educational only. Not financial advice. Past performance does not guarantee future results. Consult a licensed advisor.")
