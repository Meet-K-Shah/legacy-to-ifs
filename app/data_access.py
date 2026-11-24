"""Data access for the Streamlit app (pure Python, no Streamlit imports -> unit-testable).

Reads the Gold/Silver tables from the warehouse (DuckDB, or the SQLite fallback) and the per-mock files in reconciliation_logs/.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ifs_migration.config import Paths  # noqa: E402
from ifs_migration.db import connect  # noqa: E402
from ifs_migration.mapping import FIELD_MAP, bronze_table  # noqa: E402

DOMAIN_TABLES = {"Item": ("silver_item_golden", "silver_item_xref", "part_no", "enterprise_part_no", "item"),
                 "Customer": ("silver_customer_golden", "silver_customer_xref", "enterprise_id", "enterprise_id", "customer"),
                 "Vendor": ("silver_vendor_golden", "silver_vendor_xref", "enterprise_id", "enterprise_id", "vendor")}


def open_db(paths: Paths | None = None):
    return connect(paths or Paths(), read_only=True)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def available_mocks(paths: Paths) -> list[int]:
    return sorted(int(r["mock"]) for r in read_csv(paths.logs / "mock_history.csv"))


def mock_files(paths: Paths, mock: int) -> dict:
    folder = paths.mock_logs(mock)
    return {"recon": read_csv(folder / "reconciliation_results.csv"), "dollars": read_csv(folder / "reconciliation_dollars.csv"),
            "gates": read_csv(folder / "readiness_gate_results.csv"), "issues": read_csv(folder / "data_issue_log.csv"),
            "scorecard": read_csv(folder / "domain_readiness_scorecard.csv"),
            "report": next(iter(sorted(folder.glob("cutover_signoff_report_*.md"))), None)}


def search_golden(db, domain: str, text: str, limit: int = 50) -> list[dict]:
    golden, _x, idcol, _ent, _k = DOMAIN_TABLES[domain]
    like = f"%{text.strip().upper()}%"
    name_col = "description" if domain == "Item" else "name"
    return db.query(f"SELECT * FROM {golden} WHERE UPPER({idcol}) LIKE ? OR UPPER({name_col}) LIKE ? OR UPPER(legacy_sources) LIKE ? "
                    f"ORDER BY {idcol} LIMIT {int(limit)}", (like, like, like))


def lineage(db, domain: str, ent_id: str) -> list[dict]:
    """Legacy SYSPRO / Syteline records behind a golden record, with the raw source values for comparison."""
    _g, xref, _id, entcol, tkey = DOMAIN_TABLES[domain]
    rows = db.query(f"SELECT * FROM {xref} WHERE {entcol} = ? ORDER BY bu, source_row", (ent_id,))
    out = []
    for x in rows:
        fm = FIELD_MAP[(x["bu"], tkey)]
        raw = db.query(f"SELECT * FROM {bronze_table(x['bu'], tkey)} WHERE _row_num = ?", (x["source_row"],))
        r = raw[0] if raw else {}
        label = r.get(fm.get("desc") if domain == "Item" else fm.get("name"), "")
        out.append({"bu": x["bu"], "legacy_code": x["legacy_code"], "source_row": x["source_row"], "legacy_value": label,
                    "status": x["status"], "role": "SURVIVOR" if x["is_survivor"] else "CONSOLIDATED", "match_rule": x.get("match_rule", "")})
    return out


def kpis(db) -> dict:
    return {"kpi": db.query("SELECT * FROM gold_dq_kpi ORDER BY domain, dimension, bu") if db.table_exists("gold_dq_kpi") else [],
            "readiness": db.query("SELECT * FROM profile_domain_readiness ORDER BY domain, bu") if db.table_exists("profile_domain_readiness") else []}
