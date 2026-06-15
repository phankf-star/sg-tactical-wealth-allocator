
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math, time
from datetime import datetime

st.set_page_config(page_title="SG Tactical Wealth Allocator", layout="wide", initial_sidebar_state="expanded")

# =========================
# Palette / CSS
# =========================
BLUE="#2563EB"; RED="#EF4444"; ORANGE="#F97316"; AMBER="#F59E0B"; GREEN="#16A34A"; SLATE="#64748B"
AMBER_BG="#FEF3C7"; AMBER_TEXT="#92400E"; RED_BG="#FEE2E2"; GREY_BORDER="#E5E7EB"; GREY_TEXT="#6B7280"

st.markdown(f"""
<style>
.block-container {{padding-top:1.1rem;padding-bottom:2rem;}}
.small-note {{font-size:.88rem;color:{GREY_TEXT};line-height:1.35;margin-top:.25rem;}}
.preview-panel {{padding:18px;border:1px solid {GREY_BORDER};border-radius:18px;background:#FFFFFF;margin:12px 0 18px 0;}}
.preview-row {{padding:10px 12px;border:1px solid {GREY_BORDER};border-radius:10px;background:#F9FAFB;margin-bottom:8px;display:flex;justify-content:space-between;gap:10px;align-items:center;}}
.preview-label {{font-size:.95rem;color:#374151;line-height:1.25;}}
.preview-value {{font-size:.95rem;font-weight:700;white-space:nowrap;text-align:right;}}
.exec-card {{background:#fff;border:1px solid {GREY_BORDER};border-radius:14px;padding:14px 14px 13px 18px;min-height:112px;position:relative;overflow:hidden;box-shadow:0 1px 2px rgba(17,24,39,.03);}}
.exec-card:before {{content:"";position:absolute;left:0;top:0;bottom:0;width:7px;background:var(--accent);}}
.exec-card-title {{font-size:.78rem;color:#6B7280;line-height:1.15;margin:0 0 4px 0;}}
.exec-card-value {{font-size:1.55rem;font-weight:800;color:#111827;line-height:1.08;margin:0 0 6px 0;letter-spacing:-.01em;}}
.exec-card-sub {{font-size:.78rem;color:#6B7280;line-height:1.2;margin:0;}}
.alert-card {{padding:22px;border-radius:16px;margin:14px 0 18px 0;}}
.alert-normal {{background:#ECFDF5;border:1px solid #A7F3D0;color:#065F46;}}
.alert-watch {{background:{AMBER_BG};border:1px solid {AMBER};color:{AMBER_TEXT};}}
.alert-warning {{background:#FFEDD5;border:1px solid {ORANGE};color:#9A3412;}}
.alert-risk {{background:{RED_BG};border:1px solid {RED};color:#991B1B;}}
.note-amber {{background:{AMBER_BG};border:1px solid {AMBER};color:{AMBER_TEXT};border-radius:12px;padding:10px 14px;font-size:.86rem;line-height:1.35;margin:8px 0;}}
.note-blue {{background:#DBEAFE;border:1px solid #93C5FD;color:#1E3A8A;border-radius:12px;padding:10px 14px;font-size:.86rem;line-height:1.35;margin-top:12px;}}
.sidebar-note {{background:{AMBER_BG};border:1px solid {AMBER};color:{AMBER_TEXT};border-radius:12px;padding:10px 12px;font-size:.78rem;line-height:1.32;margin-top:8px;}}
.severity-card {{border-radius:12px;padding:16px 18px;min-height:74px;border:1px solid transparent;font-weight:600;line-height:1.45;}}
.severity-blue {{background:#DBEAFE;border-color:#BFDBFE;color:#075985;}}
.severity-yellow {{background:#FEF9C3;border-color:#FEF08A;color:#92400E;}}
.severity-red {{background:#FEE2E2;border-color:#FECACA;color:#B91C1C;}}
</style>
""", unsafe_allow_html=True)

# =========================
# Static mappings
# =========================
INDEX_TICKERS={
 "S&P 500":"^GSPC",
 "Nasdaq":"^IXIC",
 "DJIA":"^DJI",
 "HSI":"^HSI",
 "STI":"^STI",
 "KLSE":"^KLSE",
 "Gold":"GLD",
 "Bitcoin":"BTC-USD",
}
DISPLAY_NAME={
 "S&P 500":"S&P 500",
 "Nasdaq":"Nasdaq",
 "DJIA":"DJIA",
 "HSI":"HSI",
 "STI":"STI",
 "KLSE":"KLSE",
 "Gold":"Gold",
 "Bitcoin":"Bitcoin",
}
PMI_PROXY_MAP={
 "S&P 500":{"label":"US Composite PMI","region":"United States","source":"S&P Global US Composite PMI / economic calendar","default":51.5},
 "Nasdaq":{"label":"US Composite PMI","region":"United States","source":"S&P Global US Composite PMI / economic calendar","default":51.5},
 "DJIA":{"label":"US Composite PMI","region":"United States","source":"S&P Global US Composite PMI / economic calendar","default":51.5},
 "HSI":{"label":"China Caixin Manufacturing PMI","region":"China / Hong Kong","source":"S&P Global Caixin PMI / economic calendar","default":51.8},
 "STI":{"label":"Singapore S&P Global PMI","region":"Singapore","source":"S&P Global Singapore PMI / economic calendar","default":56.7},
 "KLSE":{"label":"Malaysia Manufacturing PMI","region":"Malaysia","source":"S&P Global Malaysia PMI / economic calendar","default":49.8},
 "Gold":{"label":"Global PMI","region":"Global","source":"S&P Global / JPMorgan Global Composite PMI","default":51.0},
 "Bitcoin":{"label":"Global PMI","region":"Global","source":"S&P Global / JPMorgan Global Composite PMI","default":51.0},
}
PMI_FALLBACK={"label":"Global PMI","region":"Global","source":"S&P Global / JPMorgan Global Composite PMI","default":51.5}
LATEST_PMI_ACTUALS={
    "US Composite PMI":{"value":51.5,"month":"May 2026","source":"S&P Global US Composite PMI / economic calendar"},
    "China RatingDog / Caixin Manufacturing PMI":{"value":51.8,"month":"May 2026","source":"RatingDog / S&P Global / economic calendar"},
    "Singapore S&P Global PMI":{"value":56.7,"month":"May 2026","source":"S&P Global Singapore PMI / economic calendar"},
    "Singapore Manufacturing PMI (SIPMM)":{"value":51.0,"month":"May 2026","source":"SIPMM / economic calendar"},
    "Singapore Electronics PMI (SIPMM)":{"value":51.9,"month":"May 2026","source":"SIPMM / economic calendar"},
    "Malaysia Manufacturing PMI":{"value":49.8,"month":"May 2026","source":"S&P Global Malaysia PMI / economic calendar"},
 "Global PMI":{"value":51.8,"month":"May 2026","source":"S&P Global / JPMorgan Global Composite PMI"},
}
PMI_PROXY_OPTIONS=list(LATEST_PMI_ACTUALS.keys())
NAV_OPTIONS=["🧠 Executive Centre","💰 Suggested Deploy","🌦️ Market Conditions","📊 Market Performance","🏆 Crash Analytics","📡 Audit Trail & Export"]
SECTION_ORDER=["💰 Suggested Deploy","🌦️ Market Conditions","📊 Market Performance","🏆 Crash Analytics","📡 Audit Trail & Export"]
BENCHMARK_TICKERS={"Global Indices":[("STI","^STI"),("Nasdaq","^IXIC"),("S&P 500","^GSPC"),("DJIA","^DJI"),("Nikkei 225","^N225"),("TWSE","^TWII")],"Commodities & Crypto":[("Crude Oil","CL=F"),("Gold","GC=F"),("Silver","SI=F"),("Bitcoin","BTC-USD")]}
ETF_UNIVERSE={
"STI":{"label":"🇸🇬 Singapore","etfs":[("Core exposure","SPDR STI ETF","ES3.SI","Broad STI exposure"),("Core alternative","Nikko AM STI ETF","G3B.SI","Alternative STI exposure")]},
"HSI":{"label":"🇭🇰 Hong Kong","etfs":[("Core exposure","Tracker Fund of Hong Kong","2800.HK","Broad HSI exposure"),("Broad HSI ETF","iShares HSI ETF","3115.HK","Alternative HSI exposure"),("Higher beta satellite","iShares Hang Seng TECH ETF","3067.HK","Growth / tech sensitivity")]},
"Nasdaq":{"label":"🇺🇸 Nasdaq","etfs":[("Core exposure","Invesco QQQ","QQQ","Nasdaq 100 exposure"),("Lower-cost alternative","Invesco QQQM","QQQM","Nasdaq 100 lower-fee alternative")]},
"S&P 500":{"label":"🇺🇸 S&P 500","etfs":[("Core exposure","SPDR S&P 500 ETF","SPY","Broad US large-cap exposure"),("Lower-cost core","Vanguard S&P 500 ETF","VOO","Low-cost S&P 500 exposure"),("Core alternative","iShares Core S&P 500 ETF","IVV","Broad S&P 500 exposure")]},
 "DJIA":{"label":"🇺🇸 DJIA","etfs":[("Core exposure","SPDR DJIA ETF","DIA","Blue-chip US exposure")]},
 "KLSE":{"label":"🇲🇾 Malaysia","etfs":[("Core exposure","FTSE Bursa Malaysia KLCI ETF","0820EA.KL","Broad Malaysia exposure")]},
 "Gold":{"label":"🪙 Gold","etfs":[("Core exposure","SPDR Gold Shares","GLD","Physical gold ETF"),("Alternative","iShares Gold Trust","IAU","Lower-cost gold ETF")]},
}

# =========================
# Helpers
# =========================
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
    df=yf.Ticker(ticker).history(start=start); time.sleep(.05)
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
            return None if df.empty else safe_float(df.Close.iloc[-1])
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

def severity_bucket(dd):
    a=abs(dd)
    if a<10: return "Below 10% move"
    if a<20: return "10–20% correction"
    if a<30: return "20–30% correction"
    return ">30% crash"

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

def crash_events(bt,thr,current):
    ev=[]; in_dd=False; start=None
    for i in range(len(bt)):
        dv=bt.dd_pct.iloc[i]
        if dv<=-thr and not in_dd:
            in_dd=True; start=i
        elif (dv>-5 and in_dd) or (i==len(bt)-1 and in_dd):
            in_dd=False; e=bt.iloc[start:i+1]
            if e.empty: continue
            ti=e.dd_pct.idxmin(); row=bt.loc[ti]
            if len(ev)==0 or (ti-ev[-1]["Trough Date"]).days>=60:
                look=bt.loc[:ti].iloc[max(0,len(bt.loc[:ti])-252):]
                ddv=safe_float(row.dd_pct); price=safe_float(row.Close); peak=safe_float(row.rm); pkdt=look.Close.idxmax(); z,_=classify(ddv)
                recovery=((current/price)-1)*100 if price else 0
                ev.append({"Peak Date":pkdt,"Peak Index":peak,"Trough Date":ti,"Trough Index":price,"Drawdown %":ddv,"Recovery Return %":recovery,"Zone":z,"Historical Label":label_event(ti),"Severity":severity_bucket(ddv)})
    return pd.DataFrame(ev)

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

def calc_market_scores(pmi_value, dd_value, trend_weak, vix_value, curve_value):
    vix_s=0 if vix_value is None else min(max((vix_value-15)*2,0),30)
    curve_s=10 if curve_value is None else (20 if curve_value<0 else 10 if curve_value<.5 else 0)
    pmi_s=0 if pmi_value>=52 else 8 if pmi_value>=50 else 16 if pmi_value>=47 else 20
    dd_s=min(abs(dd_value)*1.2,25)
    trend_s=15 if trend_weak else 0
    total=min(vix_s+curve_s+pmi_s+dd_s+trend_s,100)
    if total>=70: return total,"CRASH RISK","alert-risk",vix_s,curve_s,pmi_s,dd_s,trend_s
    if total>=50: return total,"WARNING","alert-warning",vix_s,curve_s,pmi_s,dd_s,trend_s
    if total>=30: return total,"WATCH","alert-watch",vix_s,curve_s,pmi_s,dd_s,trend_s
    return total,"NORMAL","alert-normal",vix_s,curve_s,pmi_s,dd_s,trend_s

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


# =========================
# Trend Channel Engine (Enhanced — Preview Version)
# =========================
CRISIS_EVENTS = [
    ("1987-10-19", "1987\nBlack Monday"),
    ("2000-03-24", "2000-2002\nDot-com Bust"),
    ("2008-09-15", "2008\nGlobal Financial\nCrisis"),
    ("2020-03-23", "2020\nCOVID-19 Crash"),
    ("2022-06-16", "2022\nInflation &\nRate Hike"),
]

def build_trend_channel(df, projection_year=2040):
    if df is None or df.empty or len(df) < 36:
        return None
    monthly = df[["Close"]].resample("ME").last().dropna().copy()
    monthly["Seq"] = np.arange(1, len(monthly) + 1)
    monthly["LogPrice"] = np.log(monthly["Close"])
    slope, intercept = np.polyfit(monthly["Seq"], monthly["LogPrice"], 1)
    monthly["Trend"] = intercept + slope * monthly["Seq"]
    monthly["Residual"] = monthly["LogPrice"] - monthly["Trend"]
    sd = monthly["Residual"].std()
    monthly["TrendPrice"] = np.exp(monthly["Trend"])
    monthly["Upper1"] = np.exp(monthly["Trend"] + sd)
    monthly["Upper2"] = np.exp(monthly["Trend"] + 2 * sd)
    monthly["Lower1"] = np.exp(monthly["Trend"] - sd)
    monthly["Lower2"] = np.exp(monthly["Trend"] - 2 * sd)
    z_score = (monthly["LogPrice"].iloc[-1] - monthly["Trend"].iloc[-1]) / sd if sd else 0
    pct_rank = (monthly["Residual"] < monthly["Residual"].iloc[-1]).mean() * 100
    reg_cagr = (np.exp(slope * 12) - 1) * 100
    first_p = monthly["Close"].iloc[0]; last_p = monthly["Close"].iloc[-1]
    years = len(monthly) / 12
    actual_cagr = ((last_p / first_p) ** (1 / years) - 1) * 100 if years > 0 and first_p > 0 else 0
    # Future projection
    last_date = monthly.index[-1]; last_seq = monthly["Seq"].iloc[-1]
    proj_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), end=f"{projection_year}-12-31", freq="ME")
    proj_seq = np.arange(last_seq + 1, last_seq + 1 + len(proj_dates))
    proj_trend = intercept + slope * proj_seq
    proj_df = pd.DataFrame({
        "Seq": proj_seq, "TrendPrice": np.exp(proj_trend),
        "Upper1": np.exp(proj_trend + sd), "Upper2": np.exp(proj_trend + 2 * sd),
        "Lower1": np.exp(proj_trend - sd), "Lower2": np.exp(proj_trend - 2 * sd),
    }, index=proj_dates)
    # Historical extremes — top 3 highest + top 2 lowest z-scores
    monthly["ZHist"] = monthly["Residual"] / sd
    top_high = monthly.nlargest(3, "ZHist")[["Close", "ZHist"]]
    top_low = monthly.nsmallest(2, "ZHist")[["Close", "ZHist"]]
    extremes = pd.concat([top_high, top_low]).sort_index()
    return {
        "data": monthly, "proj": proj_df, "slope": slope, "intercept": intercept,
        "sd": sd, "z_score": z_score, "pct_rank": pct_rank,
        "reg_cagr": reg_cagr, "actual_cagr": actual_cagr, "extremes": extremes,
    }

def _valuation_status(z):
    if z > 2: return "Extreme Overvaluation", "#EF4444"
    if z > 1: return "Expensive", "#F97316"
    if z > -1: return "Neutral / Fair", "#2563EB"
    if z > -2: return "Attractive", "#16A34A"
    return "Extreme Undervaluation", "#059669"

def _tactical_implication(z):
    if z > 2: return "Above long-term trend significantly", "Very High", "Very Defensive", "Reduce Aggression"
    if z > 1: return "Above trend by >1 SD", "Moderately High", "Slow DCA / Maintain Cash Buffer", "Reduce Aggression"
    if z > -1: return "Near long-term fair value", "Moderate", "Neutral Deployment", "Normal"
    if z > -2: return "Below trend — historically attractive", "Moderate-Low", "Accumulation Phase", "Increase Allocation"
    return "Deeply below trend — rare opportunity", "Low", "Aggressive Deployment", "Maximum Allocation"

def _label_extreme(date):
    y = date.year
    if 1987 <= y <= 1988: return "Black Monday"
    if 1997 <= y <= 1998: return "Asian Financial Crisis"
    if 2000 <= y <= 2002: return "Dot-com Peak/Bust"
    if 2003 <= y <= 2004: return "Post Dot-com Recovery"
    if 2007 <= y <= 2009: return "GFC Peak/Bottom"
    if y == 2020: return "COVID Crash Bottom"
    if 2021 <= y <= 2022: return "Post-COVID / Rate Hike"
    return f"Market Event ({y})"

def render_trend_channel(df, market_name):
    # ── Controls ──
    tc_c1, tc_c2, tc_c3 = st.columns(3)
    with tc_c1:
        tc_freq = st.selectbox("Data Frequency", ["Monthly", "Weekly", "Daily"], index=0, key="tc_freq")
    with tc_c2:
        tc_period = st.selectbox("Regression Period", ["Full History", "Rolling 15Y", "Post-GFC", "Post-COVID"], index=0, key="tc_period")
    with tc_c3:
        tc_proj = st.selectbox("Projection Horizon", [2030, 2035, 2040, 2050], index=2, key="tc_proj")

    # ── Resample ──
    if tc_freq == "Weekly":
        wdf = df[["Close"]].resample("W").last().dropna()
    elif tc_freq == "Daily":
        wdf = df[["Close"]].copy()
    else:
        wdf = df[["Close"]].resample("ME").last().dropna()

    # ── Period filter ──
    if tc_period == "Rolling 15Y":
        wdf = wdf.loc[wdf.index >= wdf.index.max() - pd.DateOffset(years=15)]
    elif tc_period == "Post-GFC":
        wdf = wdf.loc[wdf.index >= "2009-01-01"]
    elif tc_period == "Post-COVID":
        wdf = wdf.loc[wdf.index >= "2020-01-01"]

    tc = build_trend_channel(wdf, projection_year=tc_proj)
    if tc is None:
        st.warning("Insufficient data for trend channel analysis.")
        return

    tdf = tc["data"]; proj = tc["proj"]; z = tc["z_score"]
    status, status_col = _valuation_status(z)
    dist = ((tdf["Close"].iloc[-1] / tdf["TrendPrice"].iloc[-1]) - 1) * 100

    # ── Top Metrics ──
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Market Status", status)
    mc2.metric("Z-Score", f"{z:+.2f}")
    mc3.metric("Percentile Rank", f"{tc['pct_rank']:.0f}th")
    mc4.metric("Distance from Trend", f"{dist:+.1f}%")

    # ════════════════════════════════════════════
    # MAIN CHART
    # ════════════════════════════════════════════
    fig = go.Figure()
    # Price
    fig.add_trace(go.Scatter(x=tdf.index, y=tdf["Close"], name=f"{market_name} (Adj Close)", line=dict(color="#2563EB", width=2)))
    # Trend
    fig.add_trace(go.Scatter(x=tdf.index, y=tdf["TrendPrice"], name="Trend (Log Regression)", line=dict(color="#7C3AED", width=2)))
    # Bands — historical
    band_cfg = [("Upper2","+2 SD (95%)","#EF4444"),("Upper1","+1 SD (75%)","#F59E0B"),("Lower1","-1 SD (75%)","#10B981"),("Lower2","-2 SD (95%)","#059669")]
    for col, lbl, clr in band_cfg:
        fig.add_trace(go.Scatter(x=tdf.index, y=tdf[col], name=lbl, line=dict(color=clr, dash="dash", width=1.5)))
    # Bands — future projection
    if not proj.empty:
        fig.add_trace(go.Scatter(x=proj.index, y=proj["TrendPrice"], name="Projection (Trend)", line=dict(color="#7C3AED", dash="dot", width=1.5), showlegend=False))
        for col, _, clr in band_cfg:
            fig.add_trace(go.Scatter(x=proj.index, y=proj[col], line=dict(color=clr, dash="dot", width=1), showlegend=False))
        # Right-side price annotations
        last_proj = proj.iloc[-1]
        for col, lbl_short in [("Upper2","+2SD"),("Upper1","+1SD"),("TrendPrice","Trend"),("Lower1","-1SD"),("Lower2","-2SD")]:
            fig.add_annotation(x=proj.index[-1], y=last_proj[col], text=f"{last_proj[col]:,.0f}", showarrow=False, xanchor="left", font=dict(size=10))

    # Crisis annotations
    for evt_date, evt_label in CRISIS_EVENTS:
        evt_ts = pd.Timestamp(evt_date)
        if tdf.index.min() <= evt_ts <= tdf.index.max():
            fig.add_annotation(x=evt_ts, y=1.08, yref="paper", text=evt_label, showarrow=True, arrowhead=2, ax=0, ay=-30, font=dict(size=9, color="#374151"), align="center")

    # Today marker
    fig.add_annotation(x=tdf.index[-1], y=1.05, yref="paper", text=f"Today\n{tdf.index[-1].strftime('%b %d, %Y')}", showarrow=True, arrowhead=2, ax=0, ay=-25, font=dict(size=9, color="#2563EB", weight="bold"))

    subtitle = f"{tc_freq} Data • {tc_period}"
    fig.update_layout(
        height=550,
        title=dict(text=f"{market_name} 曾氏通道 (Trend Channel Line) — {subtitle}", font=dict(size=16)),
        yaxis_type="log", yaxis_title="Price (Log Scale)",
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=80, t=60, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5, font=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ════════════════════════════════════════════
    # ROW 2: Summary | Z-Score Chart | Guide | Gauge
    # ════════════════════════════════════════════
    r2c1, r2c2, r2c3, r2c4 = st.columns([1, 1.2, 1.1, 0.8])

    with r2c1:
        st.markdown("#### 📋 Current Valuation Summary")
        cur_price = tdf["Close"].iloc[-1]
        trend_val = tdf["TrendPrice"].iloc[-1]
        rows_html = ""
        for lbl, val, clr in [
            ("Current Price", f"{cur_price:,.2f}", "#111827"),
            ("Trend Value (Log)", f"{trend_val:,.2f}", "#7C3AED"),
            ("Distance from Trend", f"{dist:+.1f}%", "#F97316" if dist > 0 else "#16A34A"),
            ("Z-Score", f"{z:+.2f}", status_col),
            ("Valuation Zone", status, status_col),
            ("Historical Percentile", f"{tc['pct_rank']:.0f}th", "#111827"),
            ("Regression CAGR", f"{tc['reg_cagr']:.2f}%", "#111827"),
            ("Actual CAGR", f"{tc['actual_cagr']:.2f}%", "#111827"),
            ("Volatility (SD - Log)", f"{tc['sd']:.4f}", "#111827"),
            ("Total Months", f"{len(tdf)}", "#111827"),
        ]:
            rows_html += f'<div style="display:flex;justify-content:space-between;padding:3px 8px;border-bottom:1px solid #334155"><span style="color:#94A3B8;font-size:13px">{lbl}</span><span style="color:{clr};font-weight:600;font-size:13px">{val}</span></div>'
        st.markdown(f'<div style="background:#1E293B;border-radius:8px;padding:10px 4px;margin-top:4px">{rows_html}</div>', unsafe_allow_html=True)

    with r2c2:
        st.markdown("#### 📈 Historical Z-Score")
        zfig = go.Figure()
        zhist = tdf["Residual"] / tc["sd"]
        zfig.add_trace(go.Scatter(x=tdf.index, y=zhist, mode="lines", line=dict(color="#2563EB", width=1.5), fill="tozeroy", fillcolor="rgba(37,99,235,0.12)"))
        for lv, clr_lv in [(2,"#EF4444"),(1,"#F59E0B"),(0,"#94A3B8"),(-1,"#10B981"),(-2,"#059669")]:
            zfig.add_hline(y=lv, line_dash="dash", line_color=clr_lv, line_width=1)
        zfig.add_annotation(x=tdf.index[-1], y=z, text=f"{z:+.2f}", showarrow=True, arrowhead=2, ax=30, ay=-20, font=dict(size=11, color=status_col, weight="bold"), bgcolor="white", bordercolor=status_col)
        zfig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white", paper_bgcolor="white", showlegend=False, yaxis_title="Z-Score")
        st.plotly_chart(zfig, use_container_width=True, config={"displayModeBar": False})

    with r2c3:
        st.markdown("#### 🎯 Z-Score Guide (Valuation Zones)")
        guide_html = '<table style="width:100%;border-collapse:collapse;font-size:12px">'
        guide_html += '<tr style="border-bottom:2px solid #E5E7EB"><th style="text-align:left;padding:4px">Z-Score</th><th style="text-align:left;padding:4px">Market State</th><th style="text-align:left;padding:4px">Suggested Stance</th></tr>'
        for dot, zr, state, stance in [
            ("🔴", "> +2.0", "Extreme Overvaluation", "Very Defensive"),
            ("🟠", "+1.0 to +2.0", "Expensive", "Defensive"),
            ("🟡", "-1.0 to +1.0", "Neutral / Fair", "Neutral"),
            ("🟢", "-2.0 to -1.0", "Attractive", "Accumulation"),
            ("🟢", "< -2.0", "Extreme Undervaluation", "Aggressive"),
        ]:
            guide_html += f'<tr style="border-bottom:1px solid #F3F4F6"><td style="padding:5px">{dot} {zr}</td><td style="padding:5px">{state}</td><td style="padding:5px">{stance}</td></tr>'
        guide_html += '</table>'
        st.markdown(guide_html, unsafe_allow_html=True)

    with r2c4:
        st.markdown("#### 📊 Z-Score")
        gfig = go.Figure(go.Indicator(
            mode="gauge+number", value=z, number={"suffix": "", "font": {"size": 28}},
            gauge={
                "axis": {"range": [-3, 3], "tickwidth": 1},
                "bar": {"color": status_col},
                "steps": [
                    {"range": [-3, -2], "color": "#D1FAE5"},
                    {"range": [-2, -1], "color": "#A7F3D0"},
                    {"range": [-1, 1], "color": "#FEF9C3"},
                    {"range": [1, 2], "color": "#FED7AA"},
                    {"range": [2, 3], "color": "#FECACA"},
                ],
                "threshold": {"line": {"color": "#111827", "width": 3}, "thickness": 0.8, "value": z},
            }
        ))
        gfig.update_layout(height=220, margin=dict(l=20, r=20, t=30, b=10))
        st.plotly_chart(gfig, use_container_width=True, config={"displayModeBar": False})
        st.markdown(f'<div style="text-align:center;font-size:13px"><b style="color:{status_col}">{status}</b><br>Percentile Rank: <b>{tc["pct_rank"]:.0f}th</b></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════
    # ROW 3: Extremes | Projection | Tactical
    # ════════════════════════════════════════════
    r3c1, r3c2, r3c3 = st.columns([1, 1.2, 1])

    with r3c1:
        st.markdown("#### 📜 Historical Extremes (Z-Score)")
        ext = tc["extremes"]
        ext_rows = []
        for dt, row in ext.iterrows():
            zv = row["ZHist"]; prc = row["Close"]
            state_e, _ = _valuation_status(zv)
            ext_rows.append({"Date": dt.strftime("%b %Y"), "Event": _label_extreme(dt), "Z-Score": f"{zv:+.2f}", "Price": f"{prc:,.0f}", "Market State": state_e})
        st.dataframe(pd.DataFrame(ext_rows), use_container_width=True, hide_index=True)

    with r3c2:
        st.markdown("#### 🔮 Future Projection (Price Scale)")
        if not proj.empty:
            proj_rows = []
            for yr in sorted(set([tc_proj] + [y for y in [2025,2030,2035,2040] if y <= tc_proj])):
                yr_data = proj.loc[proj.index.year == yr]
                if yr_data.empty: continue
                last_yr = yr_data.iloc[-1]
                proj_rows.append({
                    "Year": yr,
                    "Trend (Mean)": f"{last_yr['TrendPrice']:,.0f}",
                    "+1 SD (75%)": f"{last_yr['Upper1']:,.0f}",
                    "+2 SD (95%)": f"{last_yr['Upper2']:,.0f}",
                    "-1 SD (75%)": f"{last_yr['Lower1']:,.0f}",
                    "-2 SD (95%)": f"{last_yr['Lower2']:,.0f}",
                })
            if proj_rows:
                st.dataframe(pd.DataFrame(proj_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No projection data available for selected horizon.")
        else:
            st.info("No projection data available.")

    with r3c3:
        st.markdown("#### 🎯 Tactical Implication")
        val_txt, risk_txt, stance_txt, bias_txt = _tactical_implication(z)
        for emoji, lbl, val in [
            ("📊", "Valuation", val_txt),
            ("⚠️", "Risk Level", risk_txt),
            ("🧭", "Suggested Stance", stance_txt),
            ("📈", "Deployment Bias", bias_txt),
        ]:
            clr = "#16A34A" if "Accumulation" in val or "Increase" in val or "Aggressive" in val or "Maximum" in val else "#F97316" if "Defensive" in val or "Reduce" in val or "High" in val else "#2563EB"
            st.markdown(f'<div style="padding:6px 10px;margin:4px 0;border-left:3px solid {clr};background:#F8FAFC;border-radius:4px"><span style="font-size:12px;color:#6B7280">{emoji} {lbl}</span><br><span style="font-size:14px;font-weight:600;color:{clr}">{val}</span></div>', unsafe_allow_html=True)

    st.caption("This engine uses logarithmic regression channel (曾氏通道) with standard deviation bands (75% and 95%) to evaluate long-term market valuation and regime. Disclaimer: For educational purposes only. Not financial advice.")


# =========================
# Load data + sidebar
# =========================
with st.spinner("Loading market data..."):
    m=market_data()
if not m:
    st.error("Market data unavailable. Try Refresh Market Data."); st.stop()

with st.sidebar:
    st.markdown("## 📍 Navigation")
    active_section=st.radio("Go to section", NAV_OPTIONS, index=0, label_visibility="collapsed")
    st.markdown("---")
    st.markdown("## ⚙️ Quick Settings")
    sel=st.selectbox("Selected Market",list(m.keys()),index=list(m.keys()).index("STI") if "STI" in m else 0)
    st.markdown("### 💰 Capital Pools & Safeguards")
    cash_balance=st.number_input("Liquid Cash (S$)",0.0,value=100000.0,step=5000.0)
    srs_balance=st.number_input("SRS (S$)",0.0,value=35000.0,step=5000.0)
    cpf_oa_balance=st.number_input("CPF-OA (S$)",0.0,value=180000.0,step=5000.0)
    emergency_buffer=st.number_input("Emergency Buffer (S$)",0.0,value=20000.0,step=1000.0)
    preserve_cpf=st.checkbox("Preserve S$20k CPF-OA Floor",value=True)
    drawdown_method=st.radio("Drawdown Reference",["Rolling 252D Peak","2Y Peak","3Y Peak","5Y Peak","All-Time High Peak"],index=0)
    if st.button("🔄 Refresh Market Data",use_container_width=True):
        st.cache_data.clear(); st.toast("Market data refreshed.",icon="🔄")
    st.caption(f"Last refreshed: {datetime.now().strftime('%d %b %Y %H:%M SGT')}")
    st.markdown("<div class='sidebar-note'><b>Sidebar rule:</b><br>Navigation + quick settings only. Capital inputs are settings; analysis stays in the main page.</div>",unsafe_allow_html=True)

ud=m[sel]["df"]; ticker=m[sel]["ticker"]; index_label=DISPLAY_NAME.get(sel,sel); pmi_proxy_default=PMI_PROXY_MAP.get(sel,PMI_FALLBACK)
st.title("🇸🇬 Tactical Wealth Allocation & Future Drawdown Simulator")
st.caption("Singapore wealth allocation dashboard with market-specific PMI, live risk monitoring, staged deployment and crash-recovery analytics.")

# =========================
# Core calculations
# =========================
close,peak,dd,ref=current_dd(ud,drawdown_method); zone,zc=classify(dd); deploy_pct=deploy_rule(dd)
available_cash=max(cash_balance-emergency_buffer,0); available_srs=srs_balance; available_cpf=max(cpf_oa_balance-(20000 if preserve_cpf else 0),0)
total_available=available_cash+available_srs+available_cpf; deploy=total_available*deploy_pct
cash_deploy,srs_deploy,cpf_deploy,capital_reason=capital_breakdown(zone,deploy,available_cash,available_srs,available_cpf)
funding_source="Cash First" if cash_deploy>0 else "No deployment"
macro=live_macro_data(); vix=macro.get("vix"); tnx=macro.get("tnx"); irx=macro.get("irx")
curve_spread=(tnx-irx) if (tnx is not None and irx is not None) else None
trend_below=close<m[sel]["ma200"]
pmi_proxy_label=pmi_proxy_default["label"]
selected_actual=LATEST_PMI_ACTUALS.get(pmi_proxy_label,{"value":pmi_proxy_default.get("default",51.5),"month":"May 2026","source":pmi_proxy_default.get("source","Economic calendar / manual source")})
if "latest_pmi_value" not in st.session_state or st.session_state.get("pmi_proxy_label")!=pmi_proxy_label:
    st.session_state.latest_pmi_value=float(selected_actual["value"]); st.session_state.latest_pmi_month=selected_actual["month"]; st.session_state.latest_pmi_source=selected_actual["source"]; st.session_state.pmi_proxy_label=pmi_proxy_label
latest_pmi=float(st.session_state.latest_pmi_value); pmi_month=st.session_state.latest_pmi_month; pmi_source=st.session_state.latest_pmi_source
live_score,alert,klass,vix_score,curve_score,pmi_score,dd_score,trend_score=calc_market_scores(latest_pmi,dd,trend_below,vix,curve_spread)
conf_score=confidence_score(dd,live_score,trend_below); conf_label=confidence_label(conf_score); flags=do_not_deploy_flags(live_score,vix,latest_pmi,available_cash)
decision_line="Deploy a small initial tranche only. Preserve SRS and CPF-OA for deeper drawdown zones." if deploy>0 else "No deployment now. Capital is preserved until a deployment trigger appears."
next_trigger=next_trigger_label(zone)
risk_colour=GREEN if alert=="NORMAL" else AMBER if alert=="WATCH" else ORANGE if alert=="WARNING" else RED

# =========================
# Render functions
# =========================
def render_executive():
    st.markdown("---")
    st.markdown("## 🧠 Executive Tactical Allocation Centre")
    st.caption("Summary only: six decision cards, drawdown reference, formula and decision note. Capital inputs and funding details are handled outside the Executive Centre.")
    st.markdown(f"#### 📐 Current Drawdown Reference: {drawdown_method}")
    row1=st.columns(3)
    with row1[0]: st.markdown(exec_card(index_label,f"{close:,.0f}",f"{ticker} · Index Level",BLUE),unsafe_allow_html=True)
    with row1[1]: st.markdown(exec_card("Current Drawdown",f"{dd:.1f}%",ref,RED),unsafe_allow_html=True)
    with row1[2]: st.markdown(exec_card("Current Market Action",zone,"Drawdown-based rule",ORANGE),unsafe_allow_html=True)
    row2=st.columns(3)
    with row2[0]: st.markdown(exec_card("Suggested Deploy",f"S${deploy:,.0f}","Calculation output",AMBER),unsafe_allow_html=True)
    with row2[1]: st.markdown(exec_card("Risk Regime",alert,f"Live Risk Score: {live_score:.0f} / 100",risk_colour),unsafe_allow_html=True)
    with row2[2]: st.markdown(exec_card("Signal Confidence",conf_label,f"Approx. {conf_score:.0f} / 100",BLUE),unsafe_allow_html=True)
    st.markdown(f"<div class='preview-panel'><b>Formula used:</b> Current drawdown = (current close − selected peak reference) ÷ selected peak reference.<br><b>Selected reference:</b> {ref} at approximately <b>{peak:,.0f}</b>.<br><br><b>Decision note:</b> {decision_line}</div>",unsafe_allow_html=True)

def render_suggested(expanded=False):
    with st.expander("💰 Suggested Deploy Basis & Capital Source",expanded=expanded):
        s1,s2,s3,s4=st.columns([1,1.15,1,1.1])
        with s1:
            st.markdown(f"<div class='preview-panel'><h3 style='margin-top:0'>📌 Suggested Deploy Basis</h3><p>Suggested Deploy = Available Deployable Capital × Deployment Rule</p><h2 style='margin-top:0;color:{AMBER_TEXT}'>S${deploy:,.0f} = S${total_available:,.0f} × {deploy_pct:.0%}</h2><p class='small-note'>Source: selected index price data, {ref} drawdown formula, and sidebar capital inputs.</p></div>",unsafe_allow_html=True)
        with s2:
            st.markdown("<div class='preview-panel'><h3 style='margin-top:0'>🏦 Capital Source Breakdown</h3><p class='small-note'>Funding details are shown here rather than in the Executive Centre.</p>"+preview_row("Funding Source",funding_source,GREEN if cash_deploy>0 else SLATE)+preview_row("Cash Deployment",f"S${cash_deploy:,.0f}",GREEN)+preview_row("SRS Deployment",f"S${srs_deploy:,.0f}",SLATE)+preview_row("CPF-OA Deployment",f"S${cpf_deploy:,.0f}",SLATE)+f"<div class='note-amber'>Reason: {capital_reason}</div></div>",unsafe_allow_html=True)
        with s3:
            if deploy>0:
                t1,t2,t3=deploy*.5,deploy*.25,deploy*.25
                st.markdown("<div class='preview-panel'><h3 style='margin-top:0'>🧱 Tranche Deployment Plan</h3>"+preview_row("Tranche 1 — Deploy now",f"S${t1:,.0f}",AMBER)+preview_row("Tranche 2 — If drawdown deepens",f"S${t2:,.0f}",ORANGE)+preview_row("Tranche 3 — If stabilisation appears",f"S${t3:,.0f}",BLUE)+"<p class='small-note'>Tranches are staged to avoid one-shot deployment.</p></div>",unsafe_allow_html=True)
            else: st.info("No tranche plan because Suggested Deploy is S$0 under current rule engine.")
        with s4:
            st.markdown("<div class='preview-panel'><h3 style='margin-top:0'>🧭 Deployment Ladder & 🛑 Safeguards</h3>"+preview_row("HOLD / small drawdown","0% deploy",SLATE)+preview_row("INITIAL BUY","10% deploy · Cash only",AMBER)+preview_row("BUY","20–35% deploy · Cash then SRS",ORANGE)+preview_row("STRONG BUY","50% deploy · Cash + SRS + CPF-OA",RED)+preview_row("Next Trigger",next_trigger,ORANGE)+preview_row("Hard-stop flags",f"{len(flags)} active",RED if flags else GREEN)+"</div>",unsafe_allow_html=True)
        options=ETF_UNIVERSE.get(sel,{}).get("etfs",[])
        if options:
            st.markdown("#### 🎯 Suggested Investment Options")
            st.caption("ETF-based educational options linked to the selected market. Not a personalised buy list.")
            st.dataframe(pd.DataFrame([{"Role":r,"Instrument":n,"Ticker":t,"Use case":u} for r,n,t,u in options]),use_container_width=True,hide_index=True)

def render_market(expanded=False):
    with st.expander("🌦️ MARKET CONDITIONS & LIVE RISK MONITOR",expanded=expanded):
        st.markdown("<h1 style='font-size:34px;margin-bottom:0'>🌦️ Market Conditions & Live Risk Monitor</h1><p class='small-note'>PMI controls, signal confidence, live triggers, risk-score engine, 12M trend snapshot and scenario override.</p>",unsafe_allow_html=True)

        current_proxy=st.session_state.get("pmi_proxy_label",pmi_proxy_label)
        chosen_pmi_default_index=PMI_PROXY_OPTIONS.index(current_proxy) if current_proxy in PMI_PROXY_OPTIONS else 0
        selected_actual=LATEST_PMI_ACTUALS.get(current_proxy,LATEST_PMI_ACTUALS["Global PMI"])
        display_pmi=float(st.session_state.get("latest_pmi_value",selected_actual["value"]))
        local_score,local_alert,local_klass,local_vix_s,local_curve_s,local_pmi_s,local_dd_s,local_trend_s=calc_market_scores(display_pmi,dd,trend_below,vix,curve_spread)
        local_conf=confidence_score(dd,local_score,trend_below); local_conf_label=confidence_label(local_conf)
        local_risk_colour=GREEN if local_alert=="NORMAL" else AMBER if local_alert=="WATCH" else ORANGE if local_alert=="WARNING" else RED

        st.markdown(f"<div class='alert-card {local_klass}'><h2 style='margin:0'>LIVE MARKET RISK ALERT: {local_alert}</h2><p class='small-note'>This is a rules-based stress indicator, not a crash prediction. PMI proxy used: <b>{current_proxy}</b>.</p></div>",unsafe_allow_html=True)
        st.markdown("#### 🟢 Market-Specific PMI Monthly Signal")
        p1,p2,p3,p4,p5,p6,p7=st.columns([1.15,1.05,1.45,.75,.75,.8,.55])
        with p1:
            chosen=st.selectbox("PMI Proxy Used",PMI_PROXY_OPTIONS,index=chosen_pmi_default_index,key="market_pmi_proxy_select")
        actual=LATEST_PMI_ACTUALS.get(chosen,LATEST_PMI_ACTUALS["Global PMI"])
        region=("United States" if chosen.startswith("US") else "China / Hong Kong proxy" if chosen.startswith("China") else "Singapore" if chosen.startswith("Singapore") else "Global")
        if chosen!=st.session_state.get("pmi_proxy_label"):
            st.session_state.latest_pmi_value=float(actual["value"]); st.session_state.latest_pmi_month=actual["month"]; st.session_state.latest_pmi_source=actual["source"]; st.session_state.pmi_proxy_label=chosen
        with p2:
            pmi_region=st.text_input("PMI Region",value=region)
        with p3:
            pmi_source_in=st.text_input("PMI Source",value=st.session_state.get("latest_pmi_source",actual["source"]))
        with p4:
            latest_in=st.number_input("Latest PMI",30.0,70.0,float(st.session_state.get("latest_pmi_value",actual["value"])),step=.1)
        with p5:
            month_in=st.text_input("PMI Month",value=st.session_state.get("latest_pmi_month",actual["month"]))
        with p6:
            st.markdown("<div style='height:27px'></div>",unsafe_allow_html=True)
            if st.button("🔄 Update PMI",use_container_width=True):
                st.session_state.latest_pmi_value=float(actual["value"]); st.session_state.latest_pmi_month=actual["month"]; st.session_state.latest_pmi_source=actual["source"]; st.session_state.pmi_proxy_label=chosen
                st.toast(f"{chosen} updated to {actual['value']} for {actual['month']}.",icon="🔄"); st.rerun()
        with p7:
            st.markdown("<div style='height:27px'></div>",unsafe_allow_html=True); st.toggle("Manual",value=True)
        st.session_state.latest_pmi_value=latest_in; st.session_state.latest_pmi_month=month_in; st.session_state.latest_pmi_source=pmi_source_in; st.session_state.pmi_proxy_label=chosen

        local_score,local_alert,local_klass,local_vix_s,local_curve_s,local_pmi_s,local_dd_s,local_trend_s=calc_market_scores(latest_in,dd,trend_below,vix,curve_spread)
        local_conf=confidence_score(dd,local_score,trend_below); local_conf_label=confidence_label(local_conf)
        local_risk_colour=GREEN if local_alert=="NORMAL" else AMBER if local_alert=="WATCH" else ORANGE if local_alert=="WARNING" else RED
        st.markdown(f"<div class='note-amber'>Current PMI proxy: <b>{chosen}</b> for <b>{pmi_region}</b>. Latest value: <b>{latest_in:.1f}</b> for <b>{month_in}</b>. PMI is monthly, not intraday live data.</div>",unsafe_allow_html=True)

        m1,m2,m3,m4,m5=st.columns(5)
        with m1: st.metric("VIX Live","N/A" if vix is None else f"{vix:.1f}")
        with m2: st.metric("Yield Curve","N/A" if curve_spread is None else f"10Y-13W {curve_spread:.2f}%")
        with m3: st.metric(chosen,f"{latest_in:.1f}")
        with m4: st.metric(f"{index_label} Drawdown",f"{dd:.1f}%")
        with m5: st.metric("Live Risk Score",f"{local_score:.0f}/100")

        sig,trigger,engine=st.columns([1,1,1.15])
        with sig:
            st.markdown("#### 📊 Signal Confidence Details")
            st.markdown(preview_row("Drawdown Signal","Active" if dd<=-8 else "Inactive",ORANGE if dd<=-8 else SLATE),unsafe_allow_html=True)
            st.markdown(preview_row("Macro Stress",local_alert,local_risk_colour),unsafe_allow_html=True)
            st.markdown(preview_row("Technical Trend","Weak" if trend_below else "Stable",BLUE),unsafe_allow_html=True)
            st.progress(local_conf/100,text=f"Signal Confidence: {local_conf_label} · {local_conf:.0f}/100")
        with trigger:
            st.markdown("#### 📡 Live Trigger Monitor")
            trig=pd.DataFrame([
                {"Trigger":"VIX > 25","Status":"Yes" if vix is not None and vix>25 else "No","Detail":"Global volatility proxy"},
                {"Trigger":"Yield curve inverted","Status":"Yes" if curve_spread is not None and curve_spread<0 else "No","Detail":"US macro/liquidity proxy"},
                {"Trigger":f"{chosen} < 50","Status":"Yes" if latest_in<50 else "No","Detail":"Monthly contraction threshold"},
                {"Trigger":"Drawdown < -10%","Status":"Yes" if dd<-10 else "No","Detail":f"{index_label} correction threshold"},
                {"Trigger":"Below 200D MA","Status":"Yes" if trend_below else "No","Detail":f"{index_label} trend deterioration"},
            ])
            st.dataframe(trig,use_container_width=True,hide_index=True)
        with engine:
            st.markdown("#### 🧮 Live Risk Score Engine")
            for lab,val,col in [("VIX Score",f"{local_vix_s:.0f} / 30",AMBER),("Yield Curve Score",f"{local_curve_s:.0f} / 20",BLUE),(f"{chosen} Score",f"{local_pmi_s:.0f} / 20",GREEN),("Drawdown Score",f"{local_dd_s:.0f} / 25",ORANGE),("Trend Score",f"{local_trend_s:.0f} / 15",RED)]:
                st.markdown(preview_row(lab,val,col),unsafe_allow_html=True)
            st.markdown(f"<div class='alert-card {local_klass}' style='padding:14px'><b>Total Live Risk Score: {local_score:.0f} / 100 → {local_alert}</b></div>",unsafe_allow_html=True)

        with st.expander("📈 12M Trend Snapshot",expanded=False):
            st.caption("PMI is market-specific and shown as monthly bars with small values above each bar.")
            vix_raw=hist("^VIX","2025-06-01"); vix_df=vix_raw[["Close"]].rename(columns={"Close":"VIX"}) if not vix_raw.empty else pd.DataFrame()
            tnx_raw=hist("^TNX","2025-06-01"); irx_raw=hist("^IRX","2025-06-01"); curve_df=pd.DataFrame()
            if not tnx_raw.empty and not irx_raw.empty:
                aligned=tnx_raw[["Close"]].rename(columns={"Close":"TNX"}).join(irx_raw[["Close"]].rename(columns={"Close":"IRX"}),how="inner")
                if not aligned.empty: curve_df=pd.DataFrame({"10Y-13W":aligned["TNX"]-aligned["IRX"]},index=aligned.index)
            pmi_dates=pd.date_range(end=pd.Timestamp.today().normalize(),periods=12,freq="ME"); pmi_vals=np.linspace(max(latest_in+1.0,30),latest_in,12); pmi_df=pd.DataFrame({"PMI":pmi_vals},index=pmi_dates)
            idx12=ud.loc[ud.index>=ud.index.max()-pd.DateOffset(months=12)][["Close"]].rename(columns={"Close":"Index"})
            ch1,ch2=st.columns(2)
            with ch1: mini_trend_chart(vix_df,"VIX 12M","Volatility regime",AMBER,"rgba(245,158,11,0.18)","VIX")
            with ch2: mini_trend_chart(curve_df,"Yield Curve 12M","10Y minus 13W spread",BLUE,"rgba(37,99,235,0.16)","Spread %")
            ch3,ch4=st.columns(2)
            with ch3: mini_pmi_bar_chart(pmi_df,f"{chosen} 12M Monthly Releases",f"{month_in} latest monthly signal")
            with ch4: mini_trend_chart(idx12,f"{index_label} 12M",f"{ticker} · 12M price path",RED,"rgba(239,68,68,0.16)","Index Level")
        with st.expander("📈 曾氏通道 (Trend Channel Line) — Secular Valuation Engine", expanded=False):
            st.markdown("### 曾氏通道 (TREND CHANNEL LINE) — SECULAR VALUATION ENGINE")
            st.caption("Long-term Logarithmic Regression Trend Channel Analysis. Chart changes dynamically according to selected market.")
            render_trend_channel(ud, index_label)

        with st.expander("🧪 What-if Scenario Override",expanded=False):
            w1,w2,w3,w4=st.columns(4)
            with w1: st.slider("Override VIX",10,60,int(vix if vix else 20))
            with w2: st.slider(f"Override {chosen}",35,60,int(float(st.session_state.get("latest_pmi_value",50))))
            with w3: st.slider("Override 10Y-13W Spread",-2.0,3.0,float(curve_spread if curve_spread is not None else .5),.1)
            with w4: st.slider("Override Drawdown (%)",0,60,int(abs(dd)))
            st.info("Simulation output only: use this to stress-test assumptions, not as the live market alert.")

def render_performance(expanded=False):
    with st.expander("📊 MARKET PERFORMANCE & ETF TRACKER",expanded=expanded):
        try:
            for g,recs in bench().items(): st.markdown(f"### {g}"); st.dataframe(pd.DataFrame(recs),use_container_width=True,hide_index=True)
        except Exception as e: st.warning(f"Benchmarks unavailable: {e}")
        try:
            ed=etfs(); order=[sel] if sel in ETF_UNIVERSE else []; order += [x for x in ETF_UNIVERSE if x not in order]
            for k in order:
                if k in ed: st.markdown(f"### {ETF_UNIVERSE[k]['label']}{' ✅ SELECTED' if k==sel else ''}"); st.dataframe(pd.DataFrame(ed[k]),use_container_width=True,hide_index=True)
        except Exception as e: st.warning(f"ETFs unavailable: {e}")

def render_crash(expanded=False):
    with st.expander("🏆 Crash & Recovery Analytics",expanded=expanded):
        st.markdown("## 📊 Executive Crash & Cycle Summary")
        st.caption("Historical drawdown severity bands used to classify correction, bear-market and crash-regime events.")
        sev1,sev2,sev3=st.columns(3)
        with sev1: st.markdown("<div class='severity-card severity-blue'>📉 <b>10–20% corrections</b> represent normal correction-zone events in this dashboard.</div>",unsafe_allow_html=True)
        with sev2: st.markdown("<div class='severity-card severity-yellow'>⚠️ <b>20–30% corrections</b> represent deeper bear-market drawdowns.</div>",unsafe_allow_html=True)
        with sev3: st.markdown("<div class='severity-card severity-red'>🚨 <b>&gt;30% crashes</b> represent severe crash-regime drawdowns.</div>",unsafe_allow_html=True)
        st.markdown("---")
        try:
            p,q=st.columns([1,1])
            with p: start=st.date_input("Historical analysis start date",value=ud.index.min().date(),min_value=ud.index.min().date(),max_value=ud.index.max().date(),key="crash_start")
            with q: thr=st.slider("Minimum drawdown threshold (%)",10,50,10,5,key="crash_threshold")
            st.caption("Changing these controls recalculates the crash-event universe and summary metrics.")
            bt=ud.loc[pd.Timestamp(start):].copy(); bt["rm"]=bt.Close.rolling(252,min_periods=1).max(); bt["dd_pct"]=((bt.Close-bt.rm)/bt.rm)*100
            cur=safe_float(bt.Close.iloc[-1]); event_df=crash_events(bt,thr,cur)
            if event_df.empty:
                st.info("No drawdown events found with the selected parameters."); return
            rets=event_df["Recovery Return %"].astype(float)
            k1,k2,k3,k4,k5=st.columns(5)
            with k1: st.metric("Crash Events",len(event_df))
            with k2: st.metric("Success Rate",f"{rets.gt(0).mean()*100:.0f}%")
            with k3: st.metric("Avg Recovery",f"{rets.mean():.1f}%")
            with k4: st.metric("Best Recovery",f"{rets.max():.1f}%")
            with k5: st.metric("Current Drawdown",f"{bt.dd_pct.iloc[-1]:.1f}%")
            st.markdown("---")
            st.markdown("## 🔍 Interactive Event Explorer")
            f1,f2,f3=st.columns(3)
            severity_order=["10–20% correction","20–30% correction",">30% crash"]
            available=event_df["Severity"].unique().tolist()
            sev_options=[s for s in severity_order if s in available] + [s for s in sorted(available) if s not in severity_order]
            zone_options=sorted(event_df["Zone"].unique().tolist()); label_options=sorted(event_df["Historical Label"].unique().tolist())
            with f1: selected_sev=st.multiselect("Severity filter",sev_options,default=sev_options)
            with f2: selected_zone=st.multiselect("Buy zone filter",zone_options,default=zone_options)
            with f3: selected_label=st.selectbox("Historical label group",["All"]+label_options)
            filtered=event_df[event_df["Severity"].isin(selected_sev) & event_df["Zone"].isin(selected_zone)].copy()
            if selected_label!="All": filtered=filtered[filtered["Historical Label"]==selected_label]
            st.markdown("### 📋 Filtered Event Table")
            display_df=filtered.copy()
            for c in ["Peak Date","Trough Date"]:
                if c in display_df: display_df[c]=pd.to_datetime(display_df[c]).dt.strftime("%Y-%m-%d")
            for c in ["Peak Index","Trough Index","Drawdown %","Recovery Return %"]:
                if c in display_df: display_df[c]=display_df[c].round(1)
            st.dataframe(display_df,use_container_width=True,hide_index=True)
            st.download_button("⬇️ Export Filtered Crash Events CSV",display_df.to_csv(index=False),file_name="filtered_crash_events.csv",mime="text/csv")
            with st.expander("🧪 Master Crash Deployment Simulator",expanded=False):
                st.caption("Simulates investing a fixed amount at every selected crash/correction event and holding until today or a user-selected end date.")
                s1,s2,s3=st.columns(3)
                with s1: investment_per_event=st.number_input("Investment per event (S$)",min_value=1000.0,value=10000.0,step=1000.0,key="master_invest")
                with s2: end_date=st.date_input("Simulation end date",value=ud.index.max().date(),min_value=ud.index.min().date(),max_value=ud.index.max().date(),key="master_end")
                with s3: use_filtered=st.checkbox("Use currently filtered events only",value=True,key="master_use_filtered")
                sim_source=filtered.copy() if use_filtered else event_df.copy()
                sim_source=sim_source[pd.to_datetime(sim_source["Trough Date"])<=pd.Timestamp(end_date)].copy() if not sim_source.empty else sim_source
                end_slice=ud.loc[:pd.Timestamp(end_date)]
                if sim_source.empty or end_slice.empty:
                    st.info("No events or end-date price available for the simulator.")
                else:
                    end_index=safe_float(end_slice.Close.iloc[-1]); sim_df=sim_source.copy()
                    sim_df["End Date"]=pd.Timestamp(end_date); sim_df["End Index"]=end_index; sim_df["Investment Amount"]=investment_per_event
                    sim_df["Ending Value"]=investment_per_event*(sim_df["End Index"]/sim_df["Trough Index"])
                    sim_df["Gain / Loss"]=sim_df["Ending Value"]-sim_df["Investment Amount"]
                    sim_df["Return %"]=(sim_df["Ending Value"]/sim_df["Investment Amount"]-1)*100
                    sim_df["Holding Days"]=(pd.Timestamp(end_date)-pd.to_datetime(sim_df["Trough Date"])).dt.days
                    total_deployed=sim_df["Investment Amount"].sum(); ending_value=sim_df["Ending Value"].sum(); gain=sim_df["Gain / Loss"].sum(); total_return=(ending_value/total_deployed-1)*100 if total_deployed else 0
                    mc1,mc2,mc3,mc4,mc5=st.columns(5)
                    with mc1: st.metric("Deployments",len(sim_df))
                    with mc2: st.metric("Capital Deployed",f"S${total_deployed:,.0f}")
                    with mc3: st.metric("Ending Value",f"S${ending_value:,.0f}")
                    with mc4: st.metric("Total Gain / Loss",f"S${gain:,.0f}")
                    with mc5: st.metric("Total Return",f"{total_return:.1f}%")
                    mc6,mc7,mc8=st.columns(3)
                    with mc6: st.metric("Avg Return / Event",f"{sim_df['Return %'].mean():.1f}%")
                    with mc7: st.metric("Best Event",f"{sim_df['Return %'].max():.1f}%")
                    with mc8: st.metric("Positive Hit Rate",f"{sim_df['Return %'].gt(0).mean()*100:.0f}%")
                    sim_display=sim_df[["Trough Date","Historical Label","Severity","Zone","Trough Index","End Index","Investment Amount","Ending Value","Gain / Loss","Return %","Holding Days"]].copy()
                    sim_display["Trough Date"]=pd.to_datetime(sim_display["Trough Date"]).dt.strftime("%Y-%m-%d")
                    for c in ["Trough Index","End Index","Investment Amount","Ending Value","Gain / Loss","Return %"]: sim_display[c]=sim_display[c].round(1)
                    st.dataframe(sim_display,use_container_width=True,hide_index=True)
                    chart_df=sim_df.sort_values("Trough Date"); colour_map={"10–20% correction":BLUE,"20–30% correction":AMBER,">30% crash":RED,"Below 10% move":SLATE}
                    fig=go.Figure(); fig.add_trace(go.Bar(x=pd.to_datetime(chart_df["Trough Date"]).dt.strftime("%Y-%m-%d"),y=chart_df["Return %"],marker_color=[colour_map.get(x,SLATE) for x in chart_df["Severity"]],name="Return %"))
                    fig.update_layout(height=330,margin=dict(l=10,r=10,t=45,b=10),title="Master Simulator Return by Event",plot_bgcolor="white",paper_bgcolor="white",yaxis_title="Return %")
                    st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
                    st.download_button("⬇️ Export Master Simulator CSV",sim_display.to_csv(index=False),file_name="master_crash_deployment_simulator.csv",mime="text/csv")
            st.markdown("### 📌 Selected Event Deep Dive")
            if filtered.empty:
                st.info("No filtered event available for deep dive."); return
            deep_labels=[f"{pd.to_datetime(r['Trough Date']).strftime('%Y-%m-%d')} | {r['Historical Label']} | {r['Drawdown %']:.1f}%" for _,r in filtered.iterrows()]
            selected_deep=st.selectbox("Select event",deep_labels)
            deep_row=filtered.iloc[deep_labels.index(selected_deep)]
            invest_amount=st.number_input("Hypothetical investment amount (S$)",min_value=1000.0,value=15000.0,step=1000.0,key="deep_invest")
            ret=deep_row["Recovery Return %"]/100; value_today=invest_amount*(1+ret); gain=value_today-invest_amount
            d1,d2,d3,d4=st.columns(4)
            with d1: st.metric("Deployment Amount",f"S${invest_amount:,.0f}")
            with d2: st.metric("Initial Index",f"{deep_row['Trough Index']:,.0f}")
            with d3: st.metric("Value Today",f"S${value_today:,.0f}")
            with d4: st.metric("Return Since Trough",f"{deep_row['Recovery Return %']:.1f}%")
            d5,d6,d7,d8=st.columns(4)
            with d5: st.metric("Peak Index",f"{deep_row['Peak Index']:,.0f}")
            with d6: st.metric("Trough Index",f"{deep_row['Trough Index']:,.0f}")
            with d7: st.metric("Drawdown",f"{deep_row['Drawdown %']:.1f}%")
            with d8: st.metric("Potential Gain",f"S${gain:,.0f}")
            st.markdown(f"<div class='note-blue'>Historical label: <b>{deep_row['Historical Label']}</b>. Classified as <b>{deep_row['Severity']}</b> and <b>{deep_row['Zone']}</b>. Historical analysis is broad reference only.</div>",unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"Crash analytics unavailable: {e}")

def render_audit(expanded=False):
    with st.expander("📡 AUDIT TRAIL & EXPORT",expanded=expanded):
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
            st.markdown("- Crash severity bands classify historical drawdowns by peak-to-trough loss.")
        snap=pd.DataFrame([{"Timestamp":datetime.now().strftime('%Y-%m-%d %H:%M:%S SGT'),"Selected Index":index_label,"Ticker":ticker,"Drawdown Reference":ref,"Current Drawdown %":round(dd,2),"Action Zone":zone,"Suggested Deploy S$":round(deploy,2),"Funding Source":funding_source,"PMI Proxy":st.session_state.get("pmi_proxy_label",pmi_proxy_label),"PMI Value":st.session_state.get("latest_pmi_value",latest_pmi),"Live Risk Score":round(live_score,1),"Risk Regime":alert,"Signal Confidence":conf_label,"Do Not Deploy Flags":"; ".join(flags) if flags else "None"}])
        st.markdown("#### 📤 Tactical Snapshot Export")
        st.dataframe(snap,use_container_width=True,hide_index=True)
        st.download_button("⬇️ Export Tactical Snapshot CSV",snap.to_csv(index=False),file_name="tactical_snapshot.csv",mime="text/csv")

RENDERERS={"💰 Suggested Deploy":render_suggested,"🌦️ Market Conditions":render_market,"📊 Market Performance":render_performance,"🏆 Crash Analytics":render_crash,"📡 Audit Trail & Export":render_audit}
render_executive()
if active_section != "🧠 Executive Centre": RENDERERS[active_section](expanded=True)
for section in SECTION_ORDER:
    if section != active_section: RENDERERS[section](expanded=False)
st.markdown("---")
st.caption(f"🕒 Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} SGT")
st.caption("⚠️ Disclaimer: Educational only. Not financial advice. Past performance does not guarantee future results. Consult a licensed adviser.")
