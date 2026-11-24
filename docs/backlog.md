# Agile Backlog (user stories)

Epics map to the data workstream. Story points are relative; each increment is demonstrable.

| # | Epic | User story | Acceptance criteria | Pts | Status |
|---|---|---|---|---|---|
| 1 | Extract & profile | As the data lead I want a profiling scorecard so I can size the cleansing effort by domain | Completeness, validity, orphan, duplicate metrics by domain and BU; RAG status | 5 | Done |
| 2 | Mapping | As the implementation partner I want a source-to-target mapping so I can configure IFS templates | STTM generated from code; mandatory fields flagged | 3 | Done |
| 3 | MDM | As an item steward I want duplicates found on attributes so grade/size variants are never merged | Precision 100% on ground truth; cross-BU lineage kept in XREF | 8 | Done |
| 4 | MDM | As a customer steward I want fuzzy + tax-ID matching with a review queue | No auto-merge on conflicting tax IDs; grey zone queued | 8 | Done |
| 5 | BOM | As Engineering I want circular and orphan BOMs quarantined with an actionable reason | Recursive CTE; loop path shown | 5 | Done |
| 6 | Cutover | As Finance I want dollar parity to $0.00 with a signed report | Reconciliation on counts and dollars; adjusting journals visible | 8 | Done |
| 7 | Cutover | As the program I want gates that halt a corrupt load | Null PK / UOM / negative stock / RI / cycle / TB gates tested | 5 | Done |
| 8 | Rehearsal | As the program I want Mock 1/2/3 with burn-down | Fix files applied cumulatively; history table | 5 | Done |
| 9 | Governance | As a data owner I want RACI, standards and a change workflow | Docs in `docs/governance` | 3 | Done |
| 10 | Reporting | As an executive I want Power BI continuity | Star schema + semantic model spec | 5 | Done (spec) |
| 11 | Next | Routings and work centres migration | Validate against item master | 5 | Backlog |
| 12 | Next | Chart-of-accounts hierarchy, fixed assets, employees | STTM + gates per object | 8 | Backlog |
| 13 | Next | Incremental loads and orchestration (Fabric) | Watermark MERGE; scheduled pipeline | 8 | Backlog |
| 14 | Next | Multi-currency and multi-company GL | Currency rates, company mapping | 5 | Backlog |
