# Cutover Checklist (data workstream)

## T-4 weeks: Mock load readiness
- [ ] Source extract scripts frozen and version-controlled; extract row counts recorded
- [ ] STTM reviewed with implementation partner (`make docs` regenerates)
- [ ] Defect catalogue and owners confirmed; issue log distributed
- [ ] Decision log items DL-001..DL-013 ratified or consciously deferred

## Each mock load (1 -> 2 -> 3)
- [ ] Re-extract or re-land bronze; `python -m ifs_migration.pipeline --mock N`
- [ ] All readiness gates PASS (a BLOCKER halts the run)
- [ ] Reconciliation PASS (counts and $0.00 dollar variance); any FAIL has a named owner
- [ ] Defect burn-down reviewed (`reconciliation_logs/mock_burndown.md`); fixes returned by owners are loaded as `mockN_fixes`
- [ ] Steward review queue worked to empty
- [ ] Finance confirms GL tie-out and posts adjusting journals
- [ ] Business validation: sample records traced via XREF (Streamlit explorer)

## Go-live freeze
- [ ] Transaction freeze window agreed (legacy ERPs read-only)
- [ ] Final extract; checksums and row counts captured
- [ ] Production load order: reference -> items -> BOM -> customers/vendors -> inventory -> open orders -> open AR/AP -> GL opening balances
- [ ] Post-load reconciliation repeated against production IFS; variances = $0.00
- [ ] Signed `cutover_signoff_report` from Finance, Operations, Sales Ops, Procurement, Data & Analytics
- [ ] Quarantined backlog accepted as post-go-live work with owners and dates

## Post go-live (hypercare)
- [ ] Enterprise ID cross-reference published to reporting (Power BI continuity)
- [ ] Gold layer refresh switched from legacy sources to IFS; KPIs reconcile before vs after
- [ ] Governance workflow live; monthly steward review scheduled
