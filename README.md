# Legacy-to-IFS Cloud: Multi-BU ERP Migration & Master-Data Governance Engine

A portfolio project that simulates consolidating two acquired fabrication business units, **BU-1 on SYSPRO** and
**BU-2 on Infor Syteline**, into a single **IFS Cloud** data model, with cutover reconciliation gates and a
Medallion (Bronze / Silver / Gold) design that maps directly onto **Microsoft Fabric + Power BI**.

> **All data is synthetic.** SYSPRO/Syteline schemas are simplified and IFS field names are illustrative placeholders
> (PART_NO, UNIT_MEAS, CUSTOMER_ID, SUPPLIER_ID ...). This demonstrates method and controls, not hands-on experience
> with those products. Confirm real field names with the implementation partner.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # optional: the code also runs on the standard library alone
make mocks                             # Mock 1 -> 2 -> 3 on the shipped data (~15 s each)
make test                              # 15 tests
make app                               # Streamlit governance app
```
The shipped `data/` folder is ready to use; `make data` regenerates it deterministically (seed 42).
Engine auto-selects **DuckDB (+ Polars bulk load, rapidfuzz)** when installed, else a SQLite/difflib fallback
(`IFS_MIG_BACKEND=duckdb|sqlite` to force). All SQL is in the portable subset.

## What it does

| Stage | Output |
|---|---|
| **Source simulation** (`datagen/`) | 31,500 rows across 21 legacy extracts: 5,000 items/BU (15% cross-BU overlap), ~2,850 BOM lines, 1,500 customers + 1,500 vendors/BU with fuzzy name variants, ship-to hierarchies, inventory (lot/heat/serial), open PO/SO, open AR/AP, trial balance. **3,805 defects planted with known counts** (ground truth) |
| **Bronze + profiling** | Raw landing with lineage columns; Domain Readiness Scorecard: completeness, UOM validity, orphans, duplicates, hygiene |
| **Silver MDM** | Attribute-based item identity (SA-516 Gr 70 != Gr 60), golden IDs `TT-FAB-nnnnnn` / `ENT-CUST-nnnn` / `ENT-VEND-nnnn`, XREF tables, rapidfuzz + tax-ID matching with a steward review queue, recursive-CTE BOM cycle detection into `quarantine_bom_defects` |
| **IFS mock load + gates** | 11 `IFS_*.csv` load files; 53 blocker gates (null PK, unmapped UOM, negative on-hand, orphans, BOM cycles, extended-value rounding, trial balance) |
| **Reconciliation** | 98 independent checks: row-count equation, **$0.00 dollar variance**, GL control tie-out, XREF integrity; timestamped sign-off report + `data_issue_log.csv` |
| **Rehearsals** | Mock 1 -> 2 -> 3 apply simulated business-owner answers; burn-down in `reconciliation_logs/mock_burndown.md` |
| **Gold + app** | Kimball star schema (`gold_dim_item/customer/vendor`, `gold_fact_inventory`, `gold_fact_open_orders`) + 3-tab Streamlit app |

### Results on the shipped data

| Mock | Open issues | CRITICAL | Quarantined rows | Steward queue | Reconciliation | Readiness |
|---|---|---|---|---|---|---|
| 1 | 1,042 | 1 | 1,000 | 41 | FAIL | NOT READY |
| 2 | 516 | 1 | 496 | 19 | FAIL | NOT READY |
| 3 | 164 | 0 | 164 | 0 | PASS | READY |

Reconciliation **fails in Mock 1-2 on purpose**: the legacy source contains a planted $1,284.55 AP control-account break (BU-2).
It only passes once Finance's adjusting journal is approved (Mock 3). *Reconciliation* (nothing lost or invented) and
*readiness* (is the remaining data acceptable) are separate decisions.

Master-data outcome: 10,000 legacy items -> 9,083 golden parts (849 duplicates consolidated); 3,000 customers -> 2,598;
3,000 vendors -> 2,598. Entity resolution produced **zero false merges** against ground truth.

## Repository layout

```
src/ifs_migration/   config, db (DuckDB/SQLite), money, textnorm, itemspec, fuzzy, mapping (STTM as code), issues,
                     bronze, profiling, silver_items / silver_parties / silver_bom / silver_txn, ifs_load, gates,
                     reconcile, issue_log, gold, report, pipeline, docgen, datagen/
sql/                 bom_cycles.sql (recursive CTE), gold_star_schema.sql
app/                 streamlit_app.py + data_access.py (tested data layer)
data/                raw/ (SYSPRO + Syteline extracts), reference/ (UOM, category, GL maps), ground_truth/,
                     remediation/ (mock fixes), ifs_load/mock_N/, id_registry/
docs/                source_to_target_mapping.md (generated), data_dictionary, defect_catalog, decision_log, cutover_checklist,
                     runbook, architecture, governance/ (RACI, standards, workflow), semantic_model (Power BI), fabric_mapping,
                     backlog, ai_usage, interview_guide
reconciliation_logs/ sign-off reports, issue logs, burn-down per mock
tests/               seeded-defect, reconciliation, gate, matching and parser tests
```

## Design decisions worth discussing
1. **Every source row ends in exactly one disposition** (loaded / consolidated / quarantined / excluded), so "where did record X go?" is answerable.
2. **Money is integer cents**, one half-up rounding rule; exact parity is testable.
3. **Reconciliation is independent**: it recomputes from raw bronze and re-reads the load files rather than trusting the pipeline.
4. **Never auto-merge different tax IDs**; grey-zone matches go to a steward queue (decision log DL-005).
5. **Frozen enterprise IDs** across mocks; merges retire the higher ID as an alias.
6. **The gates found a real bug** during development (stock-key collision after consolidation) -> DL-009.

## Honest limitations
- Synthetic data; simplified legacy schemas; IFS names are placeholders.
- DuckDB, Polars, rapidfuzz and Streamlit were **not installable in the build sandbox**: the full pipeline and all tests were run on the SQLite/difflib fallback. The DuckDB/Polars/rapidfuzz paths and the Streamlit UI are written to the same interfaces but untested; the CI job runs the DuckDB path. Run `make test && make mocks` first.
- Not covered: routings, chart-of-accounts hierarchy, fixed assets, employees, multi-currency, incremental loads (see `docs/backlog.md`).
- No Power BI file (Windows-only); the model is specified in `docs/semantic_model.md`.
