# Interview Guide

## 60-second pitch
"ERP cutovers fail on unverified balances and duplicate master data, so I built a rehearsal engine for a two-BU consolidation: SYSPRO and
Syteline into IFS Cloud. It profiles the legacy data, resolves duplicate items, customers and vendors into golden records with cross-references,
quarantines defects with owners, generates IFS load files behind blocker gates, and reconciles counts and dollars to $0.00 before business sign-off.
Three mock loads show defects burning down from 1,042 to 164, and reconciliation only passes after Finance posts the journal for a planted AP break.
The Gold star schema is shaped for Fabric and Power BI continuity."

## Three artifacts to open
1. `reconciliation_logs/cutover_signoff_report_latest.md` + `docs/source_to_target_mapping.md`
2. `silver_item_xref` / Streamlit explorer: one golden part with its SYSPRO and Syteline lineage
3. `sql/gold_star_schema.sql` + `docs/semantic_model.md` + `docs/fabric_mapping.md`

## Be ready for
| Question | Answer |
|---|---|
| Have you run a full ERP implementation? | Say what is true. Then: "This project is how I learned the failure modes; here is how I would run the real workstream." Bridge with your own migration / reconciliation / data-quality work. |
| Why not merge on fuzzy name alone? | Distinct legal entities have near-identical names; I require tax-ID or name+address evidence and queue the grey zone. Precision was 100% on ground truth. |
| What happens if a load file is bad? | Gates halt the run; a gate caught a real stock-key collision during development. |
| How do you handle a legacy break? | The GL tie-out fails until Finance posts an adjusting journal; it is a business decision, not a data fix. |
| What would you do differently in Fabric? | Delta tables, notebooks, Data Factory orchestration, Direct Lake model, watermark MERGE for incrementals (see `fabric_mapping.md`). |
| What is missing? | Routings, COA hierarchy, fixed assets, multi-currency, incremental loads. |

## 30 / 60 / 90 days (proposal)
- **30:** inventory all legacy objects and owners, profile every domain, agree the STTM and readiness thresholds, stand up the issue and decision logs.
- **60:** Mock 1 and 2 with reconciliation, steward queue working, governance RACI and standards ratified, Fabric Bronze/Silver landing.
- **90:** Mock 3 with signed reconciliation, cutover runbook rehearsed, Gold layer and Power BI continuity validated, governance workflow ready for go-live.
