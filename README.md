# 🇸🇬 Tactical Wealth Allocation & Future Drawdown Simulator

A dynamic, live-updating Streamlit dashboard built for Singapore-based investors to evaluate market conditions across major global indices and simulate tactical capital deployment strategies.

---

## 🚀 Live Demo

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

> Replace the link above with your deployed Streamlit Cloud URL.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Multi-Index Tracking** | S&P 500, Nasdaq 100, Straits Times Index (STI), Hang Seng Index (HSI) |
| **Live Market Data** | Real-time price feeds via Yahoo Finance API (cached for 4 hours) |
| **Historical Date Picker** | Jump to any historical date since 1997 to view past market conditions |
| **Drawdown Simulator** | Manually simulate future crashes or rallies with an interactive price slider |
| **Macro Risk Scoring** | Composite scoring using PMI, yield curve spread, and 200-day MA positioning |
| **Zone Classification** | STRONG BUY → BUY → INITIAL BUY → HOLD → STRONG SELL |
| **SG Capital Pools** | Cascading deployment across Liquid Cash, SRS, and CPF-OA |
| **CPF-OA Floor Protection** | Toggle to preserve S$20k CPF-OA floor for the extra 1% government bonus yield |
| **Emergency Buffer** | Automatic exclusion of your emergency cash reserves from deployment |

---

## 📁 Project Structure

```
├── sg_tactical_wealth_allocator.py   # Main Streamlit application
├── requirements.txt                   # Python dependencies
├── .streamlit/
│   └── config.toml                    # Theme and server configuration
└── README.md                          # This file
```

---

## 🖥️ Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-username/sg-tactical-wealth-allocator.git
cd sg-tactical-wealth-allocator

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run sg_tactical_wealth_allocator.py
```

The app will open automatically at `http://localhost:8501`

---

## ☁️ Deploy to Streamlit Community Cloud

1. Push this repository to **GitHub**
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **"New app"**
4. Select your repository, branch (`main`), and main file (`sg_tactical_wealth_allocator.py`)
5. Click **"Deploy"** — your app will be live in ~2 minutes!

---

## 🛠️ Tech Stack

- **Frontend**: [Streamlit](https://streamlit.io/)
- **Market Data**: [yfinance](https://github.com/ranaroussi/yfinance)
- **Data Processing**: [Pandas](https://pandas.pydata.org/), [NumPy](https://numpy.org/)
- **Visualisation**: [Plotly](https://plotly.com/python/)
- **Deployment**: [Streamlit Community Cloud](https://streamlit.io/cloud)

---

## ⚠️ Disclaimer

This tool is for **educational and informational purposes only**. It does not constitute financial advice. Always consult a licensed financial advisor before making investment decisions.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
