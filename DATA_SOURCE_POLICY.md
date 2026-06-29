# Global20Engine Data Source Policy

## Production source hierarchy

### Market / ETF prices
- Source: live Yahoo/yfinance inside the base app.
- Reason: price data is live dashboard context, not monthly macro pack data.

### Latest monthly macro values
- Primary source: `macro_pack_latest/macro_data.csv`.
- Applies to: Inflation, Unemployment/Jobs, Claims where applicable, Rates latest value where supplied, PMI.

### Monthly macro trend charts
- Primary source: `macro_pack_latest/macro_history_12m.csv`.
- If unavailable: show unavailable/partial; do not fabricate trend history.

### Daily / weekly rates trend charts
- Primary source: `macro_pack_latest/rates_history_252d.csv`.
- If unavailable: use latest point only or show unavailable; do not fabricate history.

### Macro regime summary
- Must be derived from macro pack data.
- Growth/PMI must use `macro_data.csv` PMI rows first.
- `App PMI defaults composite` is not acceptable when valid PMI rows exist.

### Manual / seed / default inputs
- Not allowed for production scoring/display unless explicitly marked as Audit/Admin exception.
- China / A-Share PMI may remain an explicit Audit/Admin exception while official source routing remains validation-oriented.

## Hard rule
If `macro_data.csv` contains a valid value, production output must not silently use hardcoded defaults.
