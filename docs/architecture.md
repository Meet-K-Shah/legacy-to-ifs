# Architecture

```mermaid
flowchart LR
  subgraph Legacy["Legacy ERPs (synthetic, deliberately dirty)"]
    S1[BU-1 SYSPRO extracts]:::src
    S2[BU-2 Infor Syteline extracts]:::src
  end
  S1 & S2 --> B[(Bronze<br/>raw landing, all text,<br/>lineage columns)]
  B --> P[Profiling engine<br/>Domain Readiness Scorecard]
  B --> SV[(Silver<br/>standardise, entity-resolve,<br/>golden IDs + XREF,<br/>quarantine)]
  FX[Approved business fixes<br/>mock2 / mock3] --> SV
  SV --> L[IFS load files<br/>IFS_*.csv]
  L --> G{Readiness gates<br/>BLOCKER = halt}
  G --> R[Reconciliation engine<br/>counts + $ + GL tie-out]
  R --> REP[Cutover sign-off report<br/>data_issue_log.csv]
  SV --> GD[(Gold<br/>Kimball star schema)]
  GD --> APP[Streamlit governance app<br/>Power BI semantic layer]
  classDef src fill:#f6e7c1,stroke:#8a6d1d;
```

## Layer contracts

| Layer | What it guarantees | Where |
|---|---|---|
| Bronze | Byte-faithful landing of every legacy row (all columns as text) + `_row_num`, `_src_file`, `_ingested_at` | `bronze.py`, tables `bronze_<bu>_<entity>` |
| Silver | Standardised, validated, de-duplicated; **every source row ends in exactly one disposition** (LOADED / CONSOLIDATED / QUARANTINED / EXCLUDED) in `silver_row_ledger` | `silver_*.py` |
| IFS load | Schema-validated files; blockers halt the run | `ifs_load.py`, `gates.py` |
| Reconciliation | Independent recomputation from raw bronze + the load files themselves | `reconcile.py` |
| Gold | Star schema with surrogate keys, no legacy schema leakage | `sql/gold_star_schema.sql`, `gold.py` |

## Design principles

1. **Nothing disappears.** A row-level ledger plus reconciliation makes "where did record X go?" answerable for every source row.
2. **Money is integer cents** with one half-up rounding rule (`money.py`); floats never touch values.
3. **Identity is decided on attributes, not text.** SA-516 Gr 70 and Gr 60 plate never merge (`itemspec.py`).
4. **Steward in the loop.** Fuzzy matches are auto-merged only with tax-ID or name+address evidence; the grey zone goes to a review queue.
5. **Frozen enterprise IDs.** `data/id_registry/enterprise_ids.json` keeps IDs stable between mock loads; merged IDs are retired as aliases.
6. **Docs as code.** The STTM, data dictionary and defect catalogue are generated from the code (`make docs`).
7. **Portable SQL.** All SQL runs on DuckDB and SQLite (recursive CTE for BOM cycles, window functions for surrogate keys).
