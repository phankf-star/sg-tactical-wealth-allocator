
import math
import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="SG Tactical Wealth Allocator v35k", layout="wide", initial_sidebar_state="expanded")

# =========================
# Colours / CSS
# =========================
BLUE = "#2563EB"
RED = "#EF4444"
ORANGE = "#F97316"
AMBER = "#F59E0B"
GREEN = "#16A34A"
SLATE = "#64748B"
PURPLE = "#7C3AED"
BORDER = "#E5E7EB"
TEXT = "#111827"
MUTED = "#6B7280"

st.markdown(
    """
<style>
.block-container {padding-top: 1.25rem; padding-bottom: 2rem;}
.kpi-card {border:1px solid #E5E7EB; border-radius:14px; padding:14px 16px; background:white; box-shadow:0 1px 2px rgba(0,0,0,.04)}
.kpi-title {font-size:12px; color:#64748B; font-weight:650; margin-bottom:4px;}
.kpi-value {font-size:27px; font-weight:760; color:#111827; line-height:1.12;}
.kpi-sub {font-size:12px; color:#6B7280; margin-top:6px;}
.light-card {background:#F8FAFC; border:1px solid #E5E7EB; border-radius:10px; padding:8px; margin-top:4px;}
.kv-row {display:flex; justify-content:space-between; gap:12px; padding:5px 8px; border-bottom:1px solid #E5E7EB;}
.kv-lab {font-size:13px; color:#6B7280;}
.kv-val {font-size:13px; font-weight:650; text-align:right; color:#111827;}
.small-note {font-size:12px; color:#64748B;}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Static mappings
# =========================
INDEX_TICKERS = {
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "DJIA": "^DJI",
    "HSI": "^HSI",
    "STI": "^STI",
    "KLSE": "^KLSE",
    "A-Share": "000001.SS",
    "Nikkei 225": "^N225",
    "Gold": "GC=F",
    "Bitcoin": "BTC-USD",
}

ASSET_GROUPS = {
    "Market / Equity Index": ["S&P 500", "Nasdaq", "DJIA", "HSI", "STI", "KLSE", "A-Share", "Nikkei 225"],
    "Alternative Assets": ["Gold", "Bitcoin"],
}
DISPLAY_NAME = {k: k for k in INDEX_TICKERS}

PMI_FRED_MARKETS = {"S&P 500", "Nasdaq", "DJIA"}
PMI_NA_MARKETS = {"Gold", "Bitcoin"}

PMI_PROXY_MAP = {
    "S&P 500": {"label": "US ISM Manufacturing PMI", "region": "United States", "source": "FRED (ISM Manufacturing PMI)", "default": 54.0},
    "Nasdaq": {"label": "US ISM Manufacturing PMI", "region": "United States", "source": "FRED (ISM Manufacturing PMI)", "default": 54.0},
    "DJIA": {"label": "US ISM Manufacturing PMI", "region": "United States", "source": "FRED (ISM Manufacturing PMI)", "default": 54.0},
    "HSI": {"label": "China Caixin Manufacturing PMI", "region": "China / Hong Kong", "source": "NBS / Caixin / manual input", "default": 50.0},
    "STI": {"label": "Singapore S&P Global PMI", "region": "Singapore", "source": "SIPMM / S&P Global Singapore PMI / manual input", "default": 51.0},
    "KLSE": {"label": "Malaysia Manufacturing PMI", "region": "Malaysia", "source": "S&P Global Malaysia PMI / manual input", "default": 49.9},
    "A-Share": {"label": "China Caixin Manufacturing PMI", "region": "China", "source": "NBS / Caixin / manual input", "default": 50.0},
    "Nikkei 225": {"label": "Japan Jibun Bank Manufacturing PMI", "region": "Japan", "source": "Jibun Bank / S&P Global Japan PMI / manual input", "default": 50.4},
    "Gold": {"label": "N/A", "region": "N/A", "source": "PMI not applicable for Gold", "default": 0.0},
    "Bitcoin": {"label": "N/A", "region": "N/A", "source": "PMI not applicable for Bitcoin", "default": 0.0},
}

LATEST_PMI_ACTUALS = {
    "US ISM Manufacturing PMI": {"value": 54.0, "month": "May 2026", "source": "FRED (ISM Manufacturing PMI)"},
    "China Caixin Manufacturing PMI": {"value": 50.0, "month": "Jun 2026", "source": "NBS / Caixin / manual input"},
    "Singapore S&P Global PMI": {"value": 51.0, "month": "Jun 2026", "source": "SIPMM / S&P Global Singapore PMI / manual input"},
    "Malaysia Manufacturing PMI": {"value": 49.9, "month": "Jun 2026", "source": "S&P Global Malaysia PMI / manual input"},
    "Japan Jibun Bank Manufacturing PMI": {"value": 50.4, "month": "Jun 2026", "source": "Jibun Bank / S&P Global Japan PMI / manual input"},
    "N/A": {"value": 0.0, "month": "N/A", "source": "PMI not applicable for this asset class"},
}
PMI_PROXY_OPTIONS = list(LATEST_PMI_ACTUALS.keys())

DEFAULT_PMI_HISTORY = {
    "Singapore S&P Global PMI": {
        "2025-07": 50.1, "2025-08": 50.3, "2025-09": 49.8, "2025-10": 50.0,
        "2025-11": 50.2, "2025-12": 50.4, "2026-01": 50.5, "2026-02": 50.6,
        "2026-03": 50.5, "2026-04": 50.7, "2026-05": 51.0, "2026-06": 51.0,
    },
    "China Caixin Manufacturing PMI": {
        "2025-07": 49.4, "2025-08": 49.1, "2025-09": 49.8, "2025-10": 50.1,
        "2025-11": 50.3, "2025-12": 50.1, "2026-01": 49.1, "2026-02": 50.2,
        "2026-03": 50.5, "2026-04": 49.0, "2026-05": 49.6, "2026-06": 50.0,
    },
    "Malaysia Manufacturing PMI": {
        "2025-07": 49.5, "2025-08": 49.7, "2025-09": 49.5, "2025-10": 49.5,
        "2025-11": 49.2, "2025-12": 49.0, "2026-01": 48.8, "2026-02": 48.6,
        "2026-03": 48.8, "2026-04": 49.0, "2026-05": 49.9, "2026-06": 49.9,
    },
    "Japan Jibun Bank Manufacturing PMI": {
        "2025-07": 49.7, "2025-08": 49.9, "2025-09": 50.1, "2025-10": 50.0,
        "2025-11": 49.8, "2025-12": 49.9, "2026-01": 50.0, "2026-02": 50.2,
        "2026-03": 50.3, "2026-04": 50.2, "2026-05": 50.4, "2026-06": 50.4,
    },
}

ETF_UNIVERSE = {
    "S&P 500": {"label": "🇺🇸 S&P 500", "etfs": [("Core exposure", "SPDR S&P 500 ETF", "SPY", "Broad US large-cap exposure"), ("Lower-cost core", "Vanguard S&P 500 ETF", "VOO", "Low-cost S&P 500 exposure"), ("Core alternative", "iShares Core S&P 500 ETF", "IVV", "Broad S&P 500 exposure")]},
    "Nasdaq": {"label": "🇺🇸 Nasdaq", "etfs": [("Core exposure", "Invesco QQQ", "QQQ", "Nasdaq 100 exposure"), ("Lower-cost alternative", "Invesco QQQM", "QQQM", "Nasdaq 100 lower-fee alternative")]},
    "DJIA": {"label": "🇺🇸 DJIA", "etfs": [("Core exposure", "SPDR DJIA ETF", "DIA", "Blue-chip US exposure")]},
    "HSI": {"label": "🇭🇰 Hong Kong", "etfs": [("Core exposure", "Tracker Fund of Hong Kong", "2800.HK", "Broad HSI exposure"), ("Broad HSI ETF", "iShares HSI ETF", "3115.HK", "Alternative HSI exposure"), ("Higher beta satellite", "iShares Hang Seng TECH ETF", "3067.HK", "Growth / tech sensitivity")]},
    "STI": {"label": "🇸🇬 Singapore", "etfs": [("Core exposure", "SPDR STI ETF", "ES3.SI", "Broad STI exposure"), ("Core alternative", "Nikko AM STI ETF", "G3B.SI", "Alternative STI exposure")]},
    "KLSE": {"label": "🇲🇾 Malaysia", "etfs": [("Core exposure", "FTSE Bursa Malaysia KLCI ETF", "0820EA.KL", "Broad Malaysia exposure")]},
    "A-Share": {"label": "🇨🇳 China A-Share", "etfs": [("Core exposure", "Xtrackers Harvest CSI 300 China A-Shares ETF", "ASHR", "China A-share exposure"), ("Satellite", "KraneShares Bosera MSCI China A 50 Connect ETF", "KBA", "China A-share alternative")]},
    "Nikkei 225": {"label": "🇯🇵 Nikkei 225", "etfs": [("Core exposure", "NEXT FUNDS Nikkei 225 ETF", "1321.T", "Nikkei 225 exposure"), ("International proxy", "iShares MSCI Japan ETF", "EWJ", "Broad Japan equity exposure")]},
    "Gold": {"label": "🪙 Gold", "etfs": [("Core exposure", "SPDR Gold Shares", "GLD", "Physical gold ETF"), ("Alternative", "iShares Gold Trust", "IAU", "Lower-cost gold ETF")]},
    "Bitcoin": {"label": "₿ Bitcoin", "etfs": [("Core exposure", "iShares Bitcoin Trust", "IBIT", "Spot Bitcoin ETF"), ("Alternative", "Grayscale Bitcoin Trust", "GBTC", "Bitcoin trust")]},
}

BENCHMARK_TICKERS = {
    "Global Indices": [("STI", "^STI"), ("Nasdaq", "^IXIC"), ("S&P 500", "^GSPC"), ("DJIA", "^DJI"), ("HSI", "^HSI"), ("KLSE", "^KLSE"), ("A-Share", "000001.SS"), ("Nikkei 225", "^N225")],
    "Commodities & Crypto": [("Crude Oil", "CL=F"), ("Gold", "GC=F"), ("Silver", "SI=F"), ("Bitcoin", "BTC-USD")],
}

NAV_OPTIONS = ["🧠 Executive Centre", "💰 Suggested Deploy", "🌦️ Market Conditions", "📊 Market Performance", "🏆 Crash Analytics", "📡 Audit Trail & Export"]
SECTION_ORDER = ["💰 Suggested Deploy", "🌦️ Market Conditions", "📊 Market Performance", "🏆 Crash Analytics", "📡 Audit Trail & Export"]

# =========================
# Data helpers
# =========================
def safe_float(v, fb=0.0):
    try:
        x = float(v)
        return fb if math.isnan(x) or math.isinf(x) else x
    except Exception:
        return fb


def tz_naive(df):
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_convert(None)
    return df


@st.cache_data(ttl=14400)
def hist(ticker, start="1950-01-01"):
    try:
        df = yf.Ticker(ticker).history(start=start)
        time.sleep(0.03)
        if df is None or df.empty:
            return pd.DataFrame()
        return tz_naive(df.dropna(subset=["Close"]).copy())
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=14400)
def market_data():
    out = {}
    for name, ticker in INDEX_TICKERS.items():
        df = hist(ticker)
        if df.empty:
            continue
        close = safe_float(df.Close.iloc[-1])
        ma = safe_float(df.Close.rolling(200).mean().dropna().iloc[-1], close) if len(df) >= 200 else close
        out[name] = {"ticker": ticker, "df": df, "close": close, "ma200": ma}
    return out


@st.cache_data(ttl=3600)
def live_macro_data():
    def last_close(ticker):
        df = hist(ticker, "2025-01-01")
        return None if df.empty else safe_float(df.Close.iloc[-1])

    return {"vix": last_close("^VIX"), "tnx": last_close("^TNX"), "irx": last_close("^IRX")}


@st.cache_data(ttl=14400)
def perf(items):
    rec = []
    for item in items:
        name, ticker = (item[1], item[2]) if len(item) == 4 else item[:2]
        df = hist(ticker, "2018-01-01")
        if df.empty:
            rec.append({"Name": name, "Ticker": ticker, "Price": None, "1Y %": None, "3Y %": None, "5Y %": None})
            continue
        last = safe_float(df.Close.iloc[-1])

        def r(days):
            if len(df) <= days:
                return None
            s = safe_float(df.Close.iloc[-days])
            return round(((last / s) - 1) * 100, 1) if s else None

        rec.append({"Name": name, "Ticker": ticker, "Price": round(last, 2), "1Y %": r(252), "3Y %": r(756), "5Y %": r(1260)})
    return rec


@st.cache_data(ttl=14400)
def bench():
    return {g: perf(v) for g, v in BENCHMARK_TICKERS.items()}


@st.cache_data(ttl=14400)
def etfs():
    return {k: perf(v["etfs"]) for k, v in ETF_UNIVERSE.items()}


@st.cache_data(ttl=86400)
def fetch_fred_pmi(series_id="NAPM"):
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        df = pd.read_csv(url, parse_dates=["DATE"])
        df.columns = ["Date", "PMI"]
        df = df.set_index("Date").dropna()
        df["PMI"] = pd.to_numeric(df["PMI"], errors="coerce")
        return df.dropna()
    except Exception:
        return pd.DataFrame()


if "pmi_history" not in st.session_state:
    st.session_state.pmi_history = {}

# =========================
# Rules / UI helpers
# =========================
def card(title, value, sub, accent):
    return f'<div class="kpi-card" style="border-top:4px solid {accent}"><div class="kpi-title">{title}</div><div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>'


def kv(label, value, colour=TEXT):
    return f'<div class="kv-row"><span class="kv-lab">{label}</span><span class="kv-val" style="color:{colour}">{value}</span></div>'


def classify(dd):
    if dd <= -35:
        return "STRONG BUY", RED
    if dd <= -20:
        return "BUY", ORANGE
    if dd <= -10:
        return "INITIAL BUY", AMBER
    if dd >= 0:
        return "STRONG SELL", "#6A1B9A"
    return "HOLD", BLUE


def severity_bucket(dd):
    a = abs(dd)
    if a < 10:
        return "Below 10% move"
    if a < 20:
        return "10-20% correction"
    if a < 30:
        return "20-30% correction"
    return ">30% crash"


def current_dd(df, method):
    c = safe_float(df.Close.iloc[-1])
    if method.startswith("Rolling"):
        days, label = 252, "Rolling 252D Peak"
    elif method.startswith("2Y"):
        days, label = 504, "2Y Peak"
    elif method.startswith("3Y"):
        days, label = 756, "3Y Peak"
    elif method.startswith("5Y"):
        days, label = 1260, "5Y Peak"
    else:
        peak = safe_float(df.Close.max(), c)
        return c, peak, ((c - peak) / peak) * 100 if peak else 0, "All-Time High Peak"
    peak = safe_float(df.Close.rolling(days, min_periods=1).max().iloc[-1], c)
    return c, peak, ((c - peak) / peak) * 100 if peak else 0, label


def deploy_rule(dd):
    if dd <= -35:
        return 0.50
    if dd <= -25:
        return 0.35
    if dd <= -15:
        return 0.20
    if dd <= -8:
        return 0.10
    return 0.00


def capital_breakdown(zone, deploy_amount, available_cash, available_srs, available_cpf):
    cash = srs = cpf = 0.0
    if deploy_amount <= 0:
        return cash, srs, cpf, "Current market action does not trigger deployment; capital preserved."
    cash = min(deploy_amount, available_cash)
    rem = max(deploy_amount - cash, 0)
    if zone in ["BUY", "STRONG BUY"]:
        srs = min(rem, available_srs)
        rem = max(rem - srs, 0)
    if zone == "STRONG BUY":
        cpf = min(rem, available_cpf)
    if zone == "INITIAL BUY":
        reason = "INITIAL BUY zone uses cash first; SRS/CPF-OA are preserved for deeper drawdowns."
    elif zone == "BUY":
        reason = "BUY zone uses cash first, then SRS if cash is insufficient. CPF-OA remains reserved."
    else:
        reason = "STRONG BUY zone can use cash, SRS and CPF-OA above preserved floor."
    return cash, srs, cpf, reason


def next_trigger_label(zone):
    if zone in ["HOLD", "STRONG SELL"]:
        return "Initial buy zone near -8% to -10% drawdown"
    if zone == "INITIAL BUY":
        return "BUY zone if drawdown deepens toward -20%"
    if zone == "BUY":
        return "STRONG BUY zone if drawdown deepens beyond -35%"
    return "Already in deepest deployment zone"


def confidence_score(dd, live_score, trend_below):
    score = 35 + (15 if dd <= -8 else 0) + (10 if trend_below else 0) + (10 if live_score < 50 else 0) - (25 if live_score >= 70 else 0)
    return max(0, min(100, score))


def confidence_label(score):
    return "High" if score >= 70 else "Medium" if score >= 45 else "Low"


def calc_market_scores(pmi_value, dd_value, trend_weak, vix_value, curve_value, pmi_applicable=True):
    vix_s = 0 if vix_value is None else min(max((vix_value - 15) * 2, 0), 30)
    curve_s = 10 if curve_value is None else (20 if curve_value < 0 else 10 if curve_value < 0.5 else 0)
    pmi_s = 0 if not pmi_applicable else (0 if pmi_value >= 52 else 8 if pmi_value >= 50 else 16 if pmi_value >= 47 else 20)
    dd_s = min(abs(dd_value) * 1.2, 25)
    trend_s = 15 if trend_weak else 0
    total = min(vix_s + curve_s + pmi_s + dd_s + trend_s, 100)
    regime = "CRASH RISK" if total >= 70 else "WARNING" if total >= 50 else "WATCH" if total >= 30 else "NORMAL"
    return total, regime, vix_s, curve_s, pmi_s, dd_s, trend_s

# =========================
# Mini charts
# =========================
def mini_trend_chart(df, title, subtitle, colour, fill_colour, y_title=""):
    if df is None or df.empty:
        st.info(f"{title}: data unavailable")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df.iloc[:, 0], mode="lines", line=dict(color=colour, width=3), fill="tozeroy", fillcolor=fill_colour))
    fig.update_layout(height=240, margin=dict(l=10, r=10, t=48, b=10), title=f"{title}<br><sup>{subtitle}</sup>", plot_bgcolor="white", paper_bgcolor="white", showlegend=False, yaxis_title=y_title)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def mini_pmi_bar_chart(df, title, subtitle):
    if df is None or df.empty or "PMI" not in df.columns:
        st.info(f"{title}: data unavailable")
        return
    colours = [GREEN if v >= 50 else RED for v in df["PMI"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df.index, y=df["PMI"], marker_color=colours, text=[f"{v:.1f}" for v in df["PMI"]], textposition="outside", textfont=dict(size=10, color="#374151"), cliponaxis=False))
    fig.add_hline(y=50, line_dash="dash", line_color=SLATE, annotation_text="50 Expansion / Contraction", annotation_position="top left")
    fig.update_yaxes(range=[max(0, float(df["PMI"].min()) - 4), float(df["PMI"].max()) + 4])
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=58, b=10), title=f"{title}<br><sup>{subtitle}</sup>", plot_bgcolor="white", paper_bgcolor="white", showlegend=False, yaxis_title="PMI")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# =========================
# Trend Channel Engine
# =========================
CRISIS_EVENTS = [
    ("1987-08-01", "1987-12-31", "1987 Black Monday"),
    ("2000-03-01", "2002-10-31", "2000-2002 Dot-com Bust"),
    ("2007-10-01", "2009-03-31", "2008 Global Financial Crisis"),
    ("2020-02-01", "2020-04-30", "2020 COVID-19 Crash"),
    ("2022-01-01", "2022-10-31", "2022 Inflation & Rate Hike"),
]
TREND_CHANNEL_OVERRIDE = {"Gold": "GC=F", "Bitcoin": "BTC-USD"}


@st.cache_data(ttl=14400)
def fetch_trend_data(ticker, start="1950-01-01"):
    return hist(ticker, start)


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
    monthly["ZHist"] = monthly["Residual"] / sd if sd else 0
    z = (monthly["LogPrice"].iloc[-1] - monthly["Trend"].iloc[-1]) / sd if sd else 0
    pct = (monthly["Residual"] < monthly["Residual"].iloc[-1]).mean() * 100
    reg_cagr = (np.exp(slope * 12) - 1) * 100
    years = len(monthly) / 12
    actual_cagr = ((monthly["Close"].iloc[-1] / monthly["Close"].iloc[0]) ** (1 / years) - 1) * 100 if years > 0 and monthly["Close"].iloc[0] > 0 else 0
    last_date = monthly.index[-1]
    last_seq = monthly["Seq"].iloc[-1]
    proj_dates = pd.date_range(last_date + pd.DateOffset(months=1), f"{projection_year}-12-31", freq="ME")
    proj_seq = np.arange(last_seq + 1, last_seq + 1 + len(proj_dates))
    proj_trend = intercept + slope * proj_seq
    proj = pd.DataFrame({
        "TrendPrice": np.exp(proj_trend),
        "Upper1": np.exp(proj_trend + sd),
        "Upper2": np.exp(proj_trend + 2 * sd),
        "Lower1": np.exp(proj_trend - sd),
        "Lower2": np.exp(proj_trend - 2 * sd),
    }, index=proj_dates)
    extremes = pd.concat([monthly.nlargest(3, "ZHist")[["Close", "ZHist"]], monthly.nsmallest(2, "ZHist")[["Close", "ZHist"]]]).sort_index()
    return {"data": monthly, "proj": proj, "sd": sd, "z_score": z, "pct_rank": pct, "reg_cagr": reg_cagr, "actual_cagr": actual_cagr, "extremes": extremes}


def valuation_status(z):
    if z > 2:
        return "Extreme Overvaluation", RED
    if z > 1:
        return "Expensive", ORANGE
    if z > -1:
        return "Neutral / Fair", BLUE
    if z > -2:
        return "Attractive", GREEN
    return "Extreme Undervaluation", "#059669"


def tactical_implication(z):
    if z > 2:
        return "Above long-term trend significantly", "Very High", "Very Defensive", "Reduce Aggression"
    if z > 1:
        return "Above trend by >1 SD", "Moderately High", "Slow DCA / Maintain Cash Buffer", "Reduce Aggression"
    if z > -1:
        return "Near long-term fair value", "Moderate", "Neutral Deployment", "Normal"
    if z > -2:
        return "Below trend — historically attractive", "Moderate-Low", "Accumulation Phase", "Increase Allocation"
    return "Deeply below trend — rare opportunity", "Low", "Aggressive Deployment", "Maximum Allocation"


def label_extreme(date):
    y = pd.Timestamp(date).year
    if 1987 <= y <= 1988:
        return "Black Monday"
    if 1997 <= y <= 1998:
        return "Asian Financial Crisis"
    if 2000 <= y <= 2002:
        return "Dot-com Peak/Bust"
    if 2007 <= y <= 2009:
        return "GFC Peak/Bottom"
    if y == 2020:
        return "COVID Crash Bottom"
    if 2021 <= y <= 2022:
        return "Post-COVID / Rate Hike"
    return f"Market Event ({y})"


def render_trend_channel(df, market_name):
    c1, c2, c3 = st.columns(3)
    with c1:
        freq = st.selectbox("Data Frequency", ["Monthly", "Weekly", "Daily"], index=0, key="tc_freq")
    with c2:
        period = st.selectbox("Regression Period", ["Full History", "Rolling 15Y", "Post-GFC", "Post-COVID"], index=0, key="tc_period")
    with c3:
        proj_year = st.selectbox("Projection Horizon", [2030, 2035, 2040, 2050], index=2, key="tc_proj")

    ticker = TREND_CHANNEL_OVERRIDE.get(market_name, INDEX_TICKERS.get(market_name))
    src = fetch_trend_data(ticker) if ticker else df
    if src is None or src.empty:
        src = df

    if freq == "Weekly":
        wdf = src[["Close"]].resample("W").last().dropna()
    elif freq == "Daily":
        wdf = src[["Close"]].copy()
    else:
        wdf = src[["Close"]].resample("ME").last().dropna()

    if period == "Rolling 15Y":
        wdf = wdf.loc[wdf.index >= wdf.index.max() - pd.DateOffset(years=15)]
    elif period == "Post-GFC":
        wdf = wdf.loc[wdf.index >= "2009-01-01"]
    elif period == "Post-COVID":
        wdf = wdf.loc[wdf.index >= "2020-01-01"]

    tc = build_trend_channel(wdf, proj_year)
    if tc is None:
        st.warning("Insufficient data for trend channel analysis.")
        return

    tdf = tc["data"]
    proj = tc["proj"]
    z = tc["z_score"]
    status, status_colour = valuation_status(z)
    dist = ((tdf["Close"].iloc[-1] / tdf["TrendPrice"].iloc[-1]) - 1) * 100

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Market Status", status)
    m2.metric("Z-Score", f"{z:+.2f}")
    m3.metric("Percentile Rank", f"{tc['pct_rank']:.0f}th")
    m4.metric("Distance from Trend", f"{dist:+.1f}%")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tdf.index, y=tdf["Close"], name=f"{market_name} Price", line=dict(color=BLUE, width=2)))
    fig.add_trace(go.Scatter(x=tdf.index, y=tdf["TrendPrice"], name="Trend", line=dict(color=PURPLE, width=2)))
    bands = [("Upper2", "+2 SD", RED), ("Upper1", "+1 SD", AMBER), ("Lower1", "-1 SD", GREEN), ("Lower2", "-2 SD", "#059669")]
    for col, label, colour in bands:
        fig.add_trace(go.Scatter(x=tdf.index, y=tdf[col], name=label, line=dict(color=colour, dash="dash", width=1.5)))

    if not proj.empty:
        fig.add_trace(go.Scatter(x=proj.index, y=proj["TrendPrice"], name="Projection", line=dict(color=PURPLE, dash="dot", width=1.5), showlegend=False))
        for col, _, colour in bands:
            fig.add_trace(go.Scatter(x=proj.index, y=proj[col], line=dict(color=colour, dash="dot", width=1), showlegend=False))
        last = proj.iloc[-1]
        for col, colour in [("Upper2", RED), ("Upper1", AMBER), ("TrendPrice", PURPLE), ("Lower1", GREEN), ("Lower2", "#059669")]:
            fig.add_annotation(x=proj.index[-1], y=last[col], text=f"<b>{last[col]:,.0f}</b>", showarrow=False, xanchor="left", xshift=5, font=dict(size=11, color=colour))

    for start, end, label in CRISIS_EVENTS:
        s = pd.Timestamp(start)
        e = pd.Timestamp(end)
        if tdf.index.min() <= e and s <= tdf.index.max():
            x0 = max(s, tdf.index.min())
            x1 = min(e, tdf.index.max())
            fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(34,197,94,0.055)", line_width=0, layer="below")
            mid = x0 + (x1 - x0) / 2
            parts = label.split(" ", 1)
            event_year = parts[0]
            event_name = parts[1] if len(parts) > 1 else label
            fig.add_annotation(x=mid, y=0.96, yref="paper", text=f"<b>{event_year}</b><br>{event_name}", showarrow=False, font=dict(size=10, color="#1F2937"), bgcolor="rgba(255,255,255,0.82)", borderwidth=0, borderpad=3)

    fig.add_vline(x=tdf.index[-1].timestamp() * 1000, line_dash="dash", line_color=RED, line_width=1.5)
    fig.add_annotation(x=tdf.index[-1], y=0.95, yref="paper", text=f"<b>Today</b><br>{tdf.index[-1].strftime('%b %d, %Y')}", showarrow=False, font=dict(size=11, color=RED), bgcolor="rgba(255,255,255,0.92)", bordercolor=RED, borderwidth=1, borderpad=3)
    if not proj.empty:
        fig.add_annotation(x=proj.index[len(proj) // 2], y=0.90, yref="paper", text=f"<b>Projection to {proj_year}</b>", showarrow=False, font=dict(size=11, color=PURPLE), bgcolor="rgba(255,255,255,0.8)")

    subtitle = f"{freq}, {period} ({tdf.index[0].strftime('%b %Y')} – {tdf.index[-1].strftime('%b %Y')})"
    fig.update_layout(height=600, title=dict(text=f"<b>{market_name} 曾氏通道 (Trend Channel Line)</b> — {subtitle}", font=dict(size=15)), yaxis_type="log", yaxis_title="Price (Log Scale)", plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=10, r=90, t=50, b=10), legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="center", x=0.5, font=dict(size=10)))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    r2c1, r2c2, r2c3, r2c4 = st.columns([1, 1.2, 1.1, 0.8])
    with r2c1:
        st.markdown("#### 📋 Current Valuation Summary")
        cur = tdf["Close"].iloc[-1]
        trend = tdf["TrendPrice"].iloc[-1]
        rows = [
            ("Current Price", f"{cur:,.2f}", TEXT),
            ("Trend Value (Log)", f"{trend:,.2f}", PURPLE),
            ("Distance from Trend", f"{dist:+.1f}%", ORANGE if dist > 0 else GREEN),
            ("Z-Score", f"{z:+.2f}", status_colour),
            ("Valuation Zone", status, status_colour),
            ("Historical Percentile", f"{tc['pct_rank']:.0f}th", TEXT),
            ("Regression CAGR", f"{tc['reg_cagr']:.2f}%", TEXT),
            ("Actual CAGR", f"{tc['actual_cagr']:.2f}%", TEXT),
            ("Volatility (SD)", f"{tc['sd']:.4f}", TEXT),
            ("Total Months", f"{len(tdf)}", TEXT),
        ]
        st.markdown('<div class="light-card">' + ''.join([kv(a, b, c) for a, b, c in rows]) + '</div>', unsafe_allow_html=True)

    with r2c2:
        st.markdown("#### 📈 Historical Z-Score")
        zfig = go.Figure()
        zfig.add_trace(go.Scatter(x=tdf.index, y=tdf["ZHist"], mode="lines", line=dict(color=BLUE, width=1.5), fill="tozeroy", fillcolor="rgba(37,99,235,0.12)"))
        for lv, colour in [(2, RED), (1, AMBER), (0, SLATE), (-1, GREEN), (-2, "#059669")]:
            zfig.add_hline(y=lv, line_dash="dash", line_color=colour, line_width=1)
        zfig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white", paper_bgcolor="white", showlegend=False, yaxis_title="Z-Score")
        st.plotly_chart(zfig, use_container_width=True, config={"displayModeBar": False})

    with r2c3:
        st.markdown("#### 🎯 Z-Score Guide")
        guide = pd.DataFrame([
            {"Zone": "🔴 > +2.0", "State": "Extreme Overvaluation", "Stance": "Very Defensive"},
            {"Zone": "🟠 +1.0 to +2.0", "State": "Expensive", "Stance": "Defensive"},
            {"Zone": "🟡 -1.0 to +1.0", "State": "Neutral / Fair", "Stance": "Neutral"},
            {"Zone": "🟢 -2.0 to -1.0", "State": "Attractive", "Stance": "Accumulation"},
            {"Zone": "🟢 < -2.0", "State": "Extreme Undervaluation", "Stance": "Aggressive"},
        ])
        st.dataframe(guide, use_container_width=True, hide_index=True)

    with r2c4:
        st.markdown("#### 📊 Z-Score")
        gfig = go.Figure(go.Indicator(mode="gauge+number", value=z, number={"font": {"size": 28}}, gauge={"axis": {"range": [-3, 3]}, "bar": {"color": status_colour}, "steps": [{"range": [-3, -2], "color": "#D1FAE5"}, {"range": [-2, -1], "color": "#A7F3D0"}, {"range": [-1, 1], "color": "#FEF9C3"}, {"range": [1, 2], "color": "#FED7AA"}, {"range": [2, 3], "color": "#FECACA"}], "threshold": {"line": {"color": TEXT, "width": 3}, "value": z}}))
        gfig.update_layout(height=220, margin=dict(l=20, r=20, t=30, b=10))
        st.plotly_chart(gfig, use_container_width=True, config={"displayModeBar": False})

    r3c1, r3c2, r3c3 = st.columns([1, 1.2, 1])
    with r3c1:
        st.markdown("#### 📜 Historical Extremes")
        ext = []
        for dt, row in tc["extremes"].iterrows():
            state, _ = valuation_status(row["ZHist"])
            ext.append({"Date": dt.strftime("%b %Y"), "Event": label_extreme(dt), "Z-Score": f"{row['ZHist']:+.2f}", "Price": f"{row['Close']:,.0f}", "State": state})
        st.dataframe(pd.DataFrame(ext), use_container_width=True, hide_index=True)

    with r3c2:
        st.markdown("#### 🔮 Future Projection")
        rows = []
        for yr in sorted(set([proj_year] + [y for y in [2025, 2030, 2035, 2040] if y <= proj_year])):
            yd = proj.loc[proj.index.year == yr]
            if yd.empty:
                continue
            yv = yd.iloc[-1]
            rows.append({"Year": yr, "Trend": f"{yv['TrendPrice']:,.0f}", "+1SD": f"{yv['Upper1']:,.0f}", "+2SD": f"{yv['Upper2']:,.0f}", "-1SD": f"{yv['Lower1']:,.0f}", "-2SD": f"{yv['Lower2']:,.0f}"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with r3c3:
        st.markdown("#### 🎯 Tactical Implication")
        vals = tactical_implication(z)
        for emoji, label, value in [("📊", "Valuation", vals[0]), ("⚠️", "Risk Level", vals[1]), ("🧭", "Suggested Stance", vals[2]), ("📈", "Deployment Bias", vals[3])]:
            colour = GREEN if any(x in value for x in ["Accumulation", "Increase", "Aggressive", "Maximum", "Low"]) else ORANGE if any(x in value for x in ["Defensive", "Reduce", "High"]) else BLUE
            st.markdown(f'<div style="padding:6px 10px;margin:4px 0;border-left:3px solid {colour};background:#F8FAFC;border-radius:4px"><span style="font-size:12px;color:#6B7280">{emoji} {label}</span><br><span style="font-size:14px;font-weight:650;color:{colour}">{value}</span></div>', unsafe_allow_html=True)

# =========================
# Crash helpers
# =========================
def label_event(date):
    y = pd.Timestamp(date).year
    if 1997 <= y <= 1998:
        return "Asian Financial Crisis"
    if 2000 <= y <= 2002:
        return "Dot-com Bust"
    if 2007 <= y <= 2009:
        return "Global Financial Crisis"
    if y == 2011:
        return "Eurozone / US Debt Scare"
    if 2015 <= y <= 2016:
        return "China Devaluation / Oil Shock"
    if y == 2018:
        return "US-China Trade War"
    if y == 2020:
        return "COVID Shock"
    if 2021 <= y <= 2022:
        return "Rate-Hike Cycle"
    return "Unlabelled Cycle"


def crash_events(bt, thr, current):
    ev = []
    in_dd = False
    start = None
    for i in range(len(bt)):
        dv = bt.dd_pct.iloc[i]
        if dv <= -thr and not in_dd:
            in_dd = True
            start = i
        elif (dv > -5 and in_dd) or (i == len(bt) - 1 and in_dd):
            in_dd = False
            e = bt.iloc[start:i + 1]
            if e.empty:
                continue
            ti = e.dd_pct.idxmin()
            row = bt.loc[ti]
            if len(ev) == 0 or (ti - ev[-1]["Trough Date"]).days >= 60:
                look = bt.loc[:ti].iloc[max(0, len(bt.loc[:ti]) - 252):]
                ddv = safe_float(row.dd_pct)
                price = safe_float(row.Close)
                peak = safe_float(row.rm)
                pkdt = look.Close.idxmax()
                z, _ = classify(ddv)
                recovery = ((current / price) - 1) * 100 if price else 0
                ev.append({"Peak Date": pkdt, "Peak Index": peak, "Trough Date": ti, "Trough Index": price, "Drawdown %": ddv, "Recovery Return %": recovery, "Zone": z, "Historical Label": label_event(ti), "Severity": severity_bucket(ddv)})
    return pd.DataFrame(ev)

# =========================
# Load data + sidebar
# =========================
with st.spinner("Loading market data..."):
    m = market_data()
if not m:
    st.error("Market data unavailable. Try Refresh Market Data.")
    st.stop()

with st.sidebar:
    st.markdown("## 📍 Navigation")
    active_section = st.radio("Go to section", NAV_OPTIONS, index=0, label_visibility="collapsed")
    st.markdown("---")
    st.markdown("## ⚙️ Quick Settings")
    asset_group = st.selectbox("Asset Group", list(ASSET_GROUPS.keys()), index=0, key="asset_group_select")
    group_items = ASSET_GROUPS[asset_group]
    default_item = "STI" if asset_group == "Market / Equity Index" and "STI" in group_items else group_items[0]
    sel = st.selectbox("Selected Market" if asset_group == "Market / Equity Index" else "Selected Alternative Asset", group_items, index=group_items.index(default_item), key="selected_asset_select")
    st.session_state.selected_asset_group = asset_group
    st.session_state.selected_market_name = DISPLAY_NAME.get(sel, sel)
    st.markdown("### 💰 Capital Pools & Safeguards")
    cash_balance = st.number_input("Liquid Cash (S$)", 0.0, value=100000.0, step=5000.0)
    srs_balance = st.number_input("SRS (S$)", 0.0, value=35000.0, step=5000.0)
    cpf_oa_balance = st.number_input("CPF-OA (S$)", 0.0, value=180000.0, step=5000.0)
    emergency_buffer = st.number_input("Emergency Buffer (S$)", 0.0, value=20000.0, step=1000.0)
    preserve_cpf = st.checkbox("Preserve S$20k CPF-OA Floor", value=True)
    drawdown_method = st.radio("Drawdown Reference", ["Rolling 252D Peak", "2Y Peak", "3Y Peak", "5Y Peak", "All-Time High Peak"], index=0)
    if st.button("🔄 Refresh Market Data", use_container_width=True):
        st.cache_data.clear()
        st.toast("Market data refreshed.", icon="🔄")

# Ensure selected item exists even if the initial batch loader skipped it.
if sel not in m:
    _df = hist(INDEX_TICKERS[sel])
    if _df.empty:
        st.error(f"Market data unavailable for {sel} ({INDEX_TICKERS[sel]}). Try Refresh Market Data.")
        st.stop()
    _close = safe_float(_df.Close.iloc[-1])
    _ma = safe_float(_df.Close.rolling(200).mean().dropna().iloc[-1], _close) if len(_df) >= 200 else _close
    m[sel] = {"ticker": INDEX_TICKERS[sel], "df": _df, "close": _close, "ma200": _ma}

ud = m[sel]["df"]
ticker = m[sel]["ticker"]
index_label = DISPLAY_NAME.get(sel, sel)
pmi_proxy_default = PMI_PROXY_MAP.get(sel, {"label": "N/A", "region": "N/A", "source": "N/A", "default": 0})

# FIX: selected market change resets PMI proxy/value/source/month.
if st.session_state.get("pmi_selected_market") != sel:
    st.session_state.pmi_selected_market = sel
    st.session_state.pmi_proxy_label = pmi_proxy_default["label"]
    st.session_state.latest_pmi_value = float(pmi_proxy_default["default"])
    _pmi_actual = LATEST_PMI_ACTUALS.get(pmi_proxy_default["label"], LATEST_PMI_ACTUALS["N/A"])
    st.session_state.latest_pmi_month = _pmi_actual["month"]
    st.session_state.latest_pmi_source = pmi_proxy_default["source"]

st.title("🇸🇬 Tactical Wealth Allocation & Future Drawdown Simulator v35k")
st.caption("Singapore wealth allocation dashboard with market-specific PMI, live risk monitoring, staged deployment, crash analytics and secular valuation channel.")

close, peak, dd, ref = current_dd(ud, drawdown_method)
zone, zc = classify(dd)
deploy_pct = deploy_rule(dd)
available_cash = max(cash_balance - emergency_buffer, 0)
available_srs = srs_balance
available_cpf = max(cpf_oa_balance - (20000 if preserve_cpf else 0), 0)
total_available = available_cash + available_srs + available_cpf
deploy = total_available * deploy_pct
cash_deploy, srs_deploy, cpf_deploy, capital_reason = capital_breakdown(zone, deploy, available_cash, available_srs, available_cpf)
funding_source = "Cash First" if cash_deploy > 0 else "No deployment"
macro = live_macro_data()
vix = macro.get("vix")
tnx = macro.get("tnx")
irx = macro.get("irx")
curve_spread = (tnx - irx) if (tnx is not None and irx is not None) else None
trend_below = close < m[sel]["ma200"]
pmi_label = pmi_proxy_default["label"]
latest_pmi = float(st.session_state.get("latest_pmi_value", pmi_proxy_default["default"]))
pmi_applicable = sel not in PMI_NA_MARKETS
live_score, alert, vix_s, curve_s, pmi_s, dd_s, trend_s = calc_market_scores(latest_pmi, dd, trend_below, vix, curve_spread, pmi_applicable)
conf_score = confidence_score(dd, live_score, trend_below)
conf_label = confidence_label(conf_score)
decision_line = f"Deploy approximately S&#36;{deploy:,.0f} using staged tranches." if deploy > 0 else "No deployment now. Capital is preserved until a deployment trigger appears."
next_trigger = next_trigger_label(zone)

# =========================
# Render sections
# =========================
def render_executive():
    st.markdown("---")
    st.markdown("## 🧠 Executive Tactical Allocation Centre")
    r1 = st.columns(3)
    with r1[0]:
        st.markdown(card(index_label, f"{close:,.0f}", f"{ticker} · Index Level", BLUE), unsafe_allow_html=True)
    with r1[1]:
        st.markdown(card("Current Drawdown", f"{dd:.1f}%", ref, RED), unsafe_allow_html=True)
    with r1[2]:
        st.markdown(card("Current Market Action", zone, "Drawdown-based rule", ORANGE), unsafe_allow_html=True)
    r2 = st.columns(3)
    with r2[0]:
        st.markdown(card("Suggested Deploy", f"S${deploy:,.0f}", "Calculation output", AMBER), unsafe_allow_html=True)
    with r2[1]:
        risk_colour = RED if alert == "CRASH RISK" else ORANGE if alert == "WARNING" else AMBER if alert == "WATCH" else GREEN
        st.markdown(card("Risk Regime", alert, f"Live Risk Score: {live_score:.0f} / 100", risk_colour), unsafe_allow_html=True)
    with r2[2]:
        st.markdown(card("Signal Confidence", conf_label, f"Approx. {conf_score:.0f} / 100", BLUE), unsafe_allow_html=True)
    st.markdown(f"**Formula used:** Current drawdown = (current close − selected peak reference) ÷ selected peak reference. **Selected reference:** {ref} at approximately **{peak:,.0f}**.  \n**Decision note:** {decision_line}")


def render_suggested(expanded=False):
    with st.expander("💰 Suggested Deploy Basis & Capital Source", expanded=expanded):
        s1, s2, s3, s4 = st.columns([1, 1.15, 1, 1.1])
        with s1:
            st.markdown(f"#### 📌 Suggested Deploy Basis\nSuggested Deploy = Available Deployable Capital × Deployment Rule\n\n### S&#36;{deploy:,.0f} = S&#36;{total_available:,.0f} × {deploy_pct:.0%}\nSource: selected index price data, {ref} drawdown formula, and sidebar capital inputs.")
        with s2:
            st.markdown("#### 🏦 Capital Source Breakdown")
            st.markdown('<div class="light-card">' + kv("Funding Source", funding_source, GREEN if cash_deploy > 0 else SLATE) + kv("Cash Deployment", f"S${cash_deploy:,.0f}", GREEN) + kv("SRS Deployment", f"S${srs_deploy:,.0f}", SLATE) + kv("CPF-OA Deployment", f"S${cpf_deploy:,.0f}", SLATE) + kv("Reason", capital_reason, SLATE) + '</div>', unsafe_allow_html=True)
        with s3:
            st.markdown("#### 🧱 Tranche Deployment Plan")
            if deploy <= 0:
                st.info("No tranche plan because Suggested Deploy is S$0 under current rule engine.")
            else:
                st.markdown('<div class="light-card">' + kv("Tranche 1 — Deploy now", f"S${deploy*.5:,.0f}", AMBER) + kv("Tranche 2 — If drawdown deepens", f"S${deploy*.25:,.0f}", ORANGE) + kv("Tranche 3 — If stabilisation appears", f"S${deploy*.25:,.0f}", BLUE) + '</div>', unsafe_allow_html=True)
        with s4:
            st.markdown("#### 🧭 Deployment Ladder")
            st.markdown('<div class="light-card">' + kv("HOLD / small drawdown", "0% deploy", SLATE) + kv("INITIAL BUY", "10% deploy · Cash only", AMBER) + kv("BUY", "20–35% deploy · Cash then SRS", ORANGE) + kv("STRONG BUY", "50% deploy · Cash + SRS + CPF-OA", RED) + kv("Next Trigger", next_trigger, ORANGE) + kv("Hard-stop flags", "0 active", GREEN) + '</div>', unsafe_allow_html=True)
        options = ETF_UNIVERSE.get(sel, {}).get("etfs", [])
        if options:
            st.markdown("#### 🎯 Suggested Investment Options")
            st.dataframe(pd.DataFrame([{"Role": r, "Instrument": n, "Ticker": t, "Use case": u} for r, n, t, u in options]), use_container_width=True, hide_index=True)


def get_pmi_df(chosen, latest_in):
    market = st.session_state.get("selected_market_name", sel)
    if market in PMI_NA_MARKETS:
        return pd.DataFrame()
    if market in PMI_FRED_MARKETS:
        fred = fetch_fred_pmi("NAPM")
        if not fred.empty:
            return fred.tail(12)
    hist_map = st.session_state.pmi_history.get(chosen) or DEFAULT_PMI_HISTORY.get(chosen)
    if hist_map:
        idx = pd.to_datetime([k + "-01" for k in sorted(hist_map.keys())])
        vals = [hist_map[k] for k in sorted(hist_map.keys())]
        return pd.DataFrame({"PMI": vals}, index=idx).tail(12)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=12, freq="ME")
    vals = np.linspace(max(latest_in + 1.0, 30), latest_in, 12)
    st.caption("⚠️ Simulated PMI trend — click 🔄 Update PMI to fetch/save actual data.")
    return pd.DataFrame({"PMI": vals}, index=dates)


def render_market(expanded=False):
    with st.expander("🌦️ MARKET CONDITIONS & LIVE RISK MONITOR", expanded=expanded):
        st.markdown("## 🌦️ Market Conditions & Live Risk Monitor")
        current_proxy = st.session_state.get("pmi_proxy_label", pmi_proxy_default["label"])
        if st.session_state.get("pmi_selected_market") != sel:
            current_proxy = pmi_proxy_default["label"]
        if current_proxy not in PMI_PROXY_OPTIONS:
            current_proxy = pmi_proxy_default["label"] if pmi_proxy_default["label"] in PMI_PROXY_OPTIONS else "N/A"
        actual = LATEST_PMI_ACTUALS.get(current_proxy, LATEST_PMI_ACTUALS["N/A"])
        st.markdown(f"### LIVE MARKET RISK ALERT: {alert}")
        st.caption(f"Rules-based stress indicator, not a crash prediction. PMI proxy used as cycle signal: {current_proxy}.")

        p1, p2, p3, p4, p5, p6, p7 = st.columns([1.15, 1.05, 1.45, .75, .75, .8, .55])
        with p1:
            default_idx = PMI_PROXY_OPTIONS.index(current_proxy) if current_proxy in PMI_PROXY_OPTIONS else 0
            chosen = st.selectbox("PMI Proxy Used (Cycle Signal)", PMI_PROXY_OPTIONS, index=default_idx, key="market_pmi_proxy_select", help="Market-specific manufacturing PMI used as an economic-cycle input in the Live Risk Score.")
        actual = LATEST_PMI_ACTUALS.get(chosen, LATEST_PMI_ACTUALS["N/A"])
        with p2:
            pmi_region = st.text_input("PMI Region", value=PMI_PROXY_MAP.get(sel, {}).get("region", "N/A"))
        with p3:
            pmi_source_in = st.text_input("PMI Source", value=st.session_state.get("latest_pmi_source", actual["source"]))
        with p4:
            latest_in = st.number_input("Latest PMI", 0.0, 70.0, float(st.session_state.get("latest_pmi_value", actual["value"])), step=.1)
        with p5:
            month_in = st.text_input("PMI Month", value=st.session_state.get("latest_pmi_month", actual["month"]))
        with p6:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Update PMI", use_container_width=True):
                market = st.session_state.get("selected_market_name", sel)
                if market in PMI_FRED_MARKETS:
                    fred = fetch_fred_pmi("NAPM")
                    if not fred.empty:
                        latest_val = float(fred["PMI"].iloc[-1])
                        latest_month = fred.index[-1].strftime("%b %Y")
                        st.session_state.latest_pmi_value = latest_val
                        st.session_state.latest_pmi_month = latest_month
                        st.session_state.latest_pmi_source = "FRED (ISM Manufacturing PMI)"
                        st.session_state.pmi_proxy_label = "US ISM Manufacturing PMI"
                        st.session_state.pmi_history["US ISM Manufacturing PMI"] = {d.strftime("%Y-%m"): float(v) for d, v in fred.tail(12)["PMI"].items()}
                        st.toast(f"✅ ISM PMI fetched from FRED: {latest_val:.1f} for {latest_month}", icon="🔄")
                    else:
                        st.toast("❌ Failed to fetch from FRED. Please try again.", icon="⚠️")
                elif market in PMI_NA_MARKETS:
                    st.session_state.latest_pmi_value = 0.0
                    st.session_state.latest_pmi_month = "N/A"
                    st.session_state.latest_pmi_source = "PMI not applicable"
                    st.session_state.pmi_proxy_label = "N/A"
                    st.toast("ℹ️ PMI is not applicable for this asset class.", icon="ℹ️")
                else:
                    st.session_state.latest_pmi_value = float(latest_in)
                    st.session_state.latest_pmi_month = month_in
                    st.session_state.latest_pmi_source = pmi_source_in
                    st.session_state.pmi_proxy_label = chosen
                    hist_map = DEFAULT_PMI_HISTORY.get(chosen, {}).copy()
                    hist_map[pd.Timestamp.today().strftime("%Y-%m")] = float(latest_in)
                    st.session_state.pmi_history[chosen] = hist_map
                    st.toast(f"✅ {chosen} saved: {latest_in:.1f} for {month_in} (manual input)", icon="🔄")
                st.rerun()
        with p7:
            st.markdown("<br>", unsafe_allow_html=True)
            st.toggle("Manual", value=sel not in PMI_FRED_MARKETS and sel not in PMI_NA_MARKETS)

        pmi_app = sel not in PMI_NA_MARKETS
        latest_display = 0.0 if not pmi_app else latest_in
        local_score, local_alert, lvix, lcurve, lpmi, ldd, ltrend = calc_market_scores(latest_display, dd, trend_below, vix, curve_spread, pmi_app)
        st.caption("PMI is monthly, not intraday. US markets fetch actual FRED data on button click; non-US markets save manual inputs; Gold/Bitcoin are N/A.")
        cols = st.columns(5)
        cols[0].metric("VIX Live", "N/A" if vix is None else f"{vix:.1f}")
        cols[1].metric("Yield Curve", "N/A" if curve_spread is None else f"10Y-13W {curve_spread:.2f}%")
        cols[2].metric(chosen, "N/A" if not pmi_app else f"{latest_in:.1f}")
        cols[3].metric(f"{index_label} Drawdown", f"{dd:.1f}%")
        cols[4].metric("Live Risk Score", f"{local_score:.0f}/100")

        sig, trigger, engine = st.columns([1, 1, 1.15])
        with sig:
            st.markdown("#### 📊 Signal Confidence Details")
            st.markdown('<div class="light-card">' + kv("Drawdown Signal", "Active" if dd <= -8 else "Inactive", ORANGE if dd <= -8 else SLATE) + kv("Macro Stress", local_alert, RED if local_alert == "CRASH RISK" else ORANGE if local_alert == "WARNING" else AMBER if local_alert == "WATCH" else GREEN) + kv("Technical Trend", "Weak" if trend_below else "Stable", BLUE) + '</div>', unsafe_allow_html=True)
        with trigger:
            st.markdown("#### 📡 Live Trigger Monitor")
            trig = pd.DataFrame([
                {"Trigger": "VIX > 25", "Status": "Yes" if vix is not None and vix > 25 else "No"},
                {"Trigger": "Yield curve inverted", "Status": "Yes" if curve_spread is not None and curve_spread < 0 else "No"},
                {"Trigger": f"{chosen} < 50", "Status": "N/A" if not pmi_app else "Yes" if latest_in < 50 else "No"},
                {"Trigger": "Drawdown < -10%", "Status": "Yes" if dd < -10 else "No"},
                {"Trigger": "Below 200D MA", "Status": "Yes" if trend_below else "No"},
            ])
            st.dataframe(trig, use_container_width=True, hide_index=True)
        with engine:
            st.markdown("#### 🧮 Live Risk Score Engine")
            st.markdown('<div class="light-card">' + kv("VIX Score", f"{lvix:.0f} / 30", AMBER) + kv("Yield Curve Score", f"{lcurve:.0f} / 20", BLUE) + kv(f"{chosen} Score", f"{lpmi:.0f} / 20", GREEN) + kv("Drawdown Score", f"{ldd:.0f} / 25", ORANGE) + kv("Trend Score", f"{ltrend:.0f} / 15", RED) + kv("Total", f"{local_score:.0f} / 100 → {local_alert}", RED if local_alert == "CRASH RISK" else ORANGE if local_alert == "WARNING" else GREEN) + '</div>', unsafe_allow_html=True)

        with st.expander("📈 12M Trend Snapshot", expanded=False):
            vix_raw = hist("^VIX", "2025-06-01")
            vix_df = vix_raw[["Close"]].rename(columns={"Close": "VIX"}) if not vix_raw.empty else pd.DataFrame()
            tnx_raw = hist("^TNX", "2025-06-01")
            irx_raw = hist("^IRX", "2025-06-01")
            curve_df = pd.DataFrame()
            if not tnx_raw.empty and not irx_raw.empty:
                aligned = tnx_raw[["Close"]].rename(columns={"Close": "TNX"}).join(irx_raw[["Close"]].rename(columns={"Close": "IRX"}), how="inner")
                if not aligned.empty:
                    curve_df = pd.DataFrame({"10Y-13W": aligned["TNX"] - aligned["IRX"]}, index=aligned.index)
            pmi_df = get_pmi_df(chosen, latest_in)
            idx12 = ud.loc[ud.index >= ud.index.max() - pd.DateOffset(months=12)][["Close"]].rename(columns={"Close": "Index"})
            ch1, ch2 = st.columns(2)
            with ch1:
                mini_trend_chart(vix_df, "VIX 12M", "Volatility regime", AMBER, "rgba(245,158,11,0.18)", "VIX")
            with ch2:
                mini_trend_chart(curve_df, "Yield Curve 12M", "10Y minus 13W spread", BLUE, "rgba(37,99,235,0.16)", "Spread %")
            ch3, ch4 = st.columns(2)
            with ch3:
                if sel in PMI_NA_MARKETS:
                    st.info("ℹ️ PMI is not applicable for this asset class (Gold / Bitcoin).")
                else:
                    mini_pmi_bar_chart(pmi_df, f"{chosen} 12M Monthly Releases", f"{month_in} latest monthly signal")
            with ch4:
                mini_trend_chart(idx12, f"{index_label} 12M", f"{ticker} · 12M price path", RED, "rgba(239,68,68,0.16)", "Index Level")

        with st.expander("📈 曾氏通道 (Trend Channel Line) — Secular Valuation Engine", expanded=False):
            st.markdown("### 曾氏通道 (TREND CHANNEL LINE) — SECULAR VALUATION ENGINE")
            render_trend_channel(ud, index_label)

        with st.expander("🧪 What-if Scenario Override", expanded=False):
            w1, w2, w3, w4 = st.columns(4)
            with w1:
                st.slider("Override VIX", 10, 60, int(vix if vix else 20))
            with w2:
                st.slider(f"Override {chosen}", 35, 60, int(float(st.session_state.get("latest_pmi_value", 50))))
            with w3:
                st.slider("Override 10Y-13W Spread", -2.0, 3.0, float(curve_spread if curve_spread is not None else .5), .1)
            with w4:
                st.slider("Override Drawdown (%)", 0, 60, int(abs(dd)))
            st.info("Simulation output only: use this to stress-test assumptions, not as the live market alert.")


def render_performance(expanded=False):
    with st.expander("📊 MARKET PERFORMANCE & ETF TRACKER", expanded=expanded):
        for g, recs in bench().items():
            st.markdown(f"### {g}")
            st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)
        ed = etfs()
        order = [sel] if sel in ETF_UNIVERSE else []
        order += [x for x in ETF_UNIVERSE if x not in order]
        for k in order:
            if k in ed:
                st.markdown(f"### {ETF_UNIVERSE[k]['label']}{' ✅ SELECTED' if k == sel else ''}")
                st.dataframe(pd.DataFrame(ed[k]), use_container_width=True, hide_index=True)


def render_crash(expanded=False):
    with st.expander("🏆 Crash & Recovery Analytics", expanded=expanded):
        st.markdown("## 📊 Executive Crash & Cycle Summary")
        st.caption("Historical drawdown severity bands: 10–20%, 20–30%, and >30%.")
        p, q = st.columns([1, 1])
        with p:
            start = st.date_input("Historical analysis start date", value=ud.index.min().date(), min_value=ud.index.min().date(), max_value=ud.index.max().date(), key="crash_start")
        with q:
            thr = st.slider("Minimum drawdown threshold (%)", 10, 50, 10, 5, key="crash_threshold")
        bt = ud.loc[pd.Timestamp(start):].copy()
        bt["rm"] = bt.Close.rolling(252, min_periods=1).max()
        bt["dd_pct"] = ((bt.Close - bt.rm) / bt.rm) * 100
        cur = safe_float(bt.Close.iloc[-1])
        event_df = crash_events(bt, thr, cur)
        if event_df.empty:
            st.info("No drawdown events found with the selected parameters.")
            return
        rets = event_df["Recovery Return %"].astype(float)
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Crash Events", len(event_df))
        k2.metric("Success Rate", f"{rets.gt(0).mean()*100:.0f}%")
        k3.metric("Avg Recovery", f"{rets.mean():.1f}%")
        k4.metric("Best Recovery", f"{rets.max():.1f}%")
        k5.metric("Current Drawdown", f"{bt.dd_pct.iloc[-1]:.1f}%")
        display = event_df.copy()
        for c in ["Peak Date", "Trough Date"]:
            display[c] = pd.to_datetime(display[c]).dt.strftime("%Y-%m-%d")
        for c in ["Peak Index", "Trough Index", "Drawdown %", "Recovery Return %"]:
            display[c] = display[c].round(1)
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Export Crash Events CSV", display.to_csv(index=False), file_name="crash_events.csv", mime="text/csv")
        with st.expander("🧪 Master Crash Deployment Simulator", expanded=False):
            s1, s2 = st.columns(2)
            with s1:
                inv = st.number_input("Investment per event (S$)", min_value=1000.0, value=10000.0, step=1000.0, key="master_invest")
            with s2:
                end_date = st.date_input("Simulation end date", value=ud.index.max().date(), min_value=ud.index.min().date(), max_value=ud.index.max().date(), key="master_end")
            end_slice = ud.loc[:pd.Timestamp(end_date)]
            if end_slice.empty:
                st.info("No end-date price available.")
                return
            end_index = safe_float(end_slice.Close.iloc[-1])
            sim = event_df[pd.to_datetime(event_df["Trough Date"]) <= pd.Timestamp(end_date)].copy()
            if sim.empty:
                st.info("No events before selected end date.")
                return
            sim["Investment Amount"] = inv
            sim["End Index"] = end_index
            sim["Ending Value"] = inv * (sim["End Index"] / sim["Trough Index"])
            sim["Gain / Loss"] = sim["Ending Value"] - sim["Investment Amount"]
            sim["Return %"] = (sim["Ending Value"] / sim["Investment Amount"] - 1) * 100
            total = sim["Investment Amount"].sum()
            ending = sim["Ending Value"].sum()
            tr = (ending / total - 1) * 100 if total else 0
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Deployments", len(sim))
            c2.metric("Capital Deployed", f"S${total:,.0f}")
            c3.metric("Ending Value", f"S${ending:,.0f}")
            c4.metric("Total Return", f"{tr:.1f}%")
            st.dataframe(sim[["Trough Date", "Historical Label", "Severity", "Zone", "Trough Index", "End Index", "Investment Amount", "Ending Value", "Gain / Loss", "Return %"]], use_container_width=True, hide_index=True)


def render_audit(expanded=False):
    with st.expander("📡 AUDIT TRAIL & EXPORT", expanded=expanded):
        left, right = st.columns([1, 1])
        with left:
            st.markdown("#### 📡 Data Source & Freshness")
            st.markdown('<div class="light-card">' + kv("Market Data", "Yahoo Finance", BLUE) + kv("PMI Proxy", st.session_state.get("pmi_proxy_label", pmi_label), GREEN) + kv("PMI Value", f"{st.session_state.get('latest_pmi_value', latest_pmi):.1f} · {st.session_state.get('latest_pmi_month','')}", GREEN) + kv("PMI Source", st.session_state.get("latest_pmi_source", pmi_proxy_default["source"]), GREEN) + kv("Last Refreshed", datetime.now().strftime('%d %b %Y %H:%M SGT'), SLATE) + '</div>', unsafe_allow_html=True)
        with right:
            st.markdown("#### 🧾 Methodology Notes")
            st.markdown("- Live Risk Score is rules-based and not a crash prediction.\n- PMI is monthly, not intraday live data.\n- US PMI is fetched from FRED only when Update PMI is clicked.\n- Non-US PMI uses manual input with pre-filled 12M defaults.\n- Gold / Bitcoin PMI is not applicable.")
        snap = pd.DataFrame([{"Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S SGT'), "Selected Index": index_label, "Ticker": ticker, "Drawdown Reference": ref, "Current Drawdown %": round(dd, 2), "Action Zone": zone, "Suggested Deploy S$": round(deploy, 2), "Funding Source": funding_source, "PMI Proxy": st.session_state.get("pmi_proxy_label", pmi_label), "PMI Value": st.session_state.get("latest_pmi_value", latest_pmi), "Live Risk Score": round(live_score, 1), "Risk Regime": alert, "Signal Confidence": conf_label}])
        st.markdown("#### 📤 Tactical Snapshot Export")
        st.dataframe(snap, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Export Tactical Snapshot CSV", snap.to_csv(index=False), file_name="tactical_snapshot.csv", mime="text/csv")


RENDERERS = {"💰 Suggested Deploy": render_suggested, "🌦️ Market Conditions": render_market, "📊 Market Performance": render_performance, "🏆 Crash Analytics": render_crash, "📡 Audit Trail & Export": render_audit}

render_executive()
if active_section != "🧠 Executive Centre":
    RENDERERS[active_section](expanded=True)
for section in SECTION_ORDER:
    if section != active_section:
        RENDERERS[section](expanded=False)

st.markdown("---")
st.caption(f"🕒 Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} SGT")
st.caption("⚠️ Disclaimer: Educational only. Not financial advice. Past performance does not guarantee future results. Consult a licensed adviser.")
