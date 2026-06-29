# Global20Engine Milestone Log

Purpose: source-of-truth record for locked decisions, implementation status, verification evidence, and KIV items.

Status legend: `DISCUSSED` → `LOCKED` → `PATCHED` → `VERIFIED`; also `KIV` / `REVERTED` where applicable.

---

## 2026-06-29 — Milestone Log Governance Implemented

**Status:** LOCKED  
**Approval signal:** let proceed  
**Area:** Governance / audit trail / change control

### Decision
Create and maintain a concise milestone log for Global20Engine so future changes are traceable by:
- what changed,
- when it changed,
- why it changed,
- which file/output proves it,
- whether it is locked, patched, verified, or KIV.

### Operating rule
For future Global20Engine changes, Copilot should provide a short approval checklist. Milestone log updates are made only after explicit approval signals.

Accepted approval signals:
- please proceed
- proceed
- APPROVE
- approve
- lock this
- good to go
- yes, proceed
- let proceed

### Concise-response rule
Default Global20Engine responses should be short and easy to review. Detailed explanations only when requested.

### Files created
- `docs/GLOBAL20ENGINE_MILESTONE_LOG.md`
- `docs/DATA_SOURCE_POLICY.md`
- `docs/CHANGE_VERIFICATION_CHECKLIST.md`

### Verification required
- Files committed into GitHub repo under `docs/`
- Future changes append entries here after approval

---

## 2026-06-29 — PMI / Macro Source Governance

**Status:** LOCKED — patch pending  
**Area:** Base app / macro pack / regime builder / PMI source routing

### Decision
`macro_pack_latest/macro_data.csv` is the production source of truth for latest monthly macro values, including PMI.

### Scope
- Base app must read PMI from macro pack first.
- `global_macro_regime_latest.csv` Growth must be derived from `macro_data.csv`, not app PMI defaults.
- Hardcoded/default/seed PMI must not drive production cards, Macro Risk Score, or Growth regime.
- Manual PMI override remains Audit/Admin only, mainly for China / A-Share exception.
- If macro pack PMI is missing, app should show Awaiting/PARTIAL, not silently fall back to defaults.

### Reason
`macro_data.csv` already stores automated PMI rows. Therefore fallback to App PMI defaults is no longer acceptable for production output.

### Files / areas affected
- Base app: `Global20Engine v38ac.py` / `sg_tactical_wealth_allocator.py`
- `macro_pack_latest/macro_data.csv`
- `macro_pack_latest/macro_history_12m.csv`
- `macro_pack_latest/global_macro_regime_latest.csv` or regime builder output

### Verification checklist
- [ ] PMI card reads macro pack row
- [ ] Macro Risk Score PMI component reads macro pack row
- [ ] Audit displays active macro pack source
- [ ] 12M PMI chart uses macro history or clearly says unavailable
- [ ] Growth regime does not say FALLBACK if valid PMI rows exist
- [ ] Hardcoded fallback scan passes

---

## 2026-06-29 — Base App Data-Source Governance Audit

**Status:** LOCKED — patch pending  
**Area:** Base app source routing

### Decision
The base app is pack-aware but not yet fully pack-governed. Legacy macro/PMI fallback paths must be quarantined so they cannot re-enter production scoring/display.

### Known legacy paths to quarantine
- `PMI_PROXY_MAP`
- `LATEST_PMI_ACTUALS`
- `DEFAULT_PMI_HISTORY`
- `PMI_DEFAULTS`
- `PMI_SOURCE_CHAINS`

### Production rule
No production dashboard value should come from hardcoded macro defaults if `macro_pack_latest/macro_data.csv` has a valid row.

### Status
Locked for implementation after source-routing patch.
