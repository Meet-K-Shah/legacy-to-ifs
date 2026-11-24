# Mapping to Microsoft Fabric

| This project (local) | Fabric equivalent |
|---|---|
| Legacy CSV extracts in `data/raw/` | OneLake **Files** landing zone (or database mirroring from the legacy SQL Server) |
| Bronze tables in DuckDB | Lakehouse **Delta tables** `bronze_*` loaded by a Data Factory Copy activity / notebook |
| `silver_*.py` transformations | **PySpark / SQL notebooks** writing Silver Delta tables, orchestrated by a Data Factory pipeline |
| `silver_row_ledger`, `recon_*` | Delta tables in a `governance` schema; reconciliation notebook runs after every load |
| Readiness gates (`gates.py`) | Notebook assertions / data-quality checks that fail the pipeline run (halt downstream activities) |
| `sql/gold_star_schema.sql` | Gold Lakehouse or Warehouse; star schema consumed by a **Direct Lake** semantic model |
| Streamlit app | Power BI report on the semantic model (+ Data Activator alerts on failed gates) |
| `pipeline.py --mock N` | Pipeline parameter `mock_number`; fixes files in a Lakehouse folder |
| `data/id_registry` JSON | A small Delta table (`ref_enterprise_id`) with MERGE |
| Git + CI | Fabric Git integration with Azure DevOps; dev / test / prod workspaces promoted by deployment pipelines |

## Porting notes
- Replace `db.py` with Spark SQL; the transformation SQL is already portable (recursive CTE needs Spark 4 or an iterative DataFrame loop for BOM cycles).
- Incremental loads: add a watermark (`last_modified`) per source table and MERGE into Silver; the ledger design (one disposition per source row) carries over unchanged.
- Fuzzy matching at scale: block first (as `candidate_pairs` does), then broadcast small blocks to a UDF using rapidfuzz.
