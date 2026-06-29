# Global20Engine Change Verification Checklist

Use this checklist before marking any milestone as `VERIFIED`.

## Approval
- [ ] User approval signal received
- [ ] Decision scope is clear
- [ ] Exceptions / KIV items noted

## Code / file change
- [ ] Files affected are listed
- [ ] Patch is consolidated where possible
- [ ] No unnecessary line-by-line patching

## Source governance
- [ ] Production macro values read from `macro_pack_latest/macro_data.csv`
- [ ] Monthly trends read from `macro_pack_latest/macro_history_12m.csv`
- [ ] Rates trends read from `macro_pack_latest/rates_history_252d.csv`
- [ ] Manual/default/seed logic is Audit/Admin only

## PMI-specific gates
- [ ] PMI card uses macro pack row
- [ ] Macro Risk Score PMI component uses macro pack row
- [ ] Audit source/freshness displays active macro pack source
- [ ] 12M PMI chart uses macro history or shows unavailable
- [ ] China / A-Share exception remains explicit
- [ ] No silent fallback to app PMI defaults

## Regime output gates
- [ ] Growth regime is derived from `macro_data.csv` PMI rows
- [ ] Growth does not show `FALLBACK` if valid PMI rows exist
- [ ] No `App PMI defaults composite` in production output when PMI rows exist

## Final verification
- [ ] App runs without error
- [ ] Output screenshot / CSV evidence checked
- [ ] Milestone updated from `PATCHED` to `VERIFIED` only after confirmation
