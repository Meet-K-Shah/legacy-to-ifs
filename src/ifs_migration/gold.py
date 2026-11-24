"""Gold layer: Kimball star schema + data-quality KPI table + persisted cutover results for the dashboard / Power BI."""
from __future__ import annotations

import re

from .config import BUS
from .context import RunContext


def _run_sql_file(ctx: RunContext, path) -> None:
    for stmt in (s.strip() for s in re.sub(r"--[^\n]*", "", path.read_text()).split(";")):
        if stmt:
            ctx.db.execute(stmt)


def build(ctx: RunContext, recon: dict, gates: list[dict], issues: list[dict], readiness: list[dict]) -> None:
    db = ctx.db
    _run_sql_file(ctx, ctx.paths.root / "sql" / "gold_star_schema.sql")

    kpis: list[dict] = []
    groups: dict[tuple, list[dict]] = {}
    for m in db.query("SELECT * FROM profile_metrics"):
        name = m["metric"]
        if m["dimension"] == "COMPLETENESS":
            dim = "COMPLETENESS" if name == "Mandatory fields populated" else None
        elif "duplicate candidates" in name:
            dim = "DUPLICATE_CANDIDATES"
        elif m["dimension"] == "UNIQUENESS":
            dim = "UNIQUENESS"
        elif "auto-fixable" in name or "cross-BU" in name:
            dim = None
        else:
            dim = m["dimension"]
        if dim:
            groups.setdefault((m["domain"], m["bu"], dim), []).append(m)
    for (dom, bu, dim), ms in sorted(groups.items()):
        bad, tot = sum(m["defects"] for m in ms), sum(m["total"] for m in ms)
        kpis.append({"stage": "SOURCE", "domain": dom, "bu": bu, "dimension": dim,
                     "score_pct": 100.0 if tot == 0 else round(100.0 * (1 - bad / tot), 2), "defects": bad, "total": tot})
    for c in recon["counts"]:
        tot = c["source_rows"]
        good = c["loaded"] + c["consolidated"]
        kpis.append({"stage": "IFS_LOAD", "domain": c["domain"], "bu": "ALL", "dimension": "MIGRATION_YIELD",
                     "score_pct": 100.0 if tot == 0 else round(100.0 * good / tot, 2), "defects": c["quarantined"] + c["excluded"], "total": tot})
    db.write_table("gold_dq_kpi", {"stage": "TEXT", "domain": "TEXT", "bu": "TEXT", "dimension": "TEXT", "score_pct": "DOUBLE",
                                   "defects": "BIGINT", "total": "BIGINT"}, kpis)
    db.write_table("gold_gate_results", {"gate_id": "TEXT", "file": "TEXT", "description": "TEXT", "severity": "TEXT",
                                         "failing_rows": "BIGINT", "status": "TEXT", "detail": "TEXT"}, gates)
    cols = {c: "TEXT" for c in ("issue_id", "domain", "bu", "source_row", "source_key", "defect_code", "severity", "status", "owner",
                                "description", "recommended_action", "detail", "ticket", "resolved_in_mock", "business_decision")}
    db.write_table("gold_issue_log", cols, [{k: ("" if v is None else str(v)) for k, v in r.items()} for r in issues])
    db.write_table("gold_readiness", {"criterion": "TEXT", "threshold": "TEXT", "actual": "TEXT", "status": "TEXT"}, readiness)
    led_cols = {"domain": "TEXT", "bu": "TEXT", "source_row": "BIGINT", "source_key": "TEXT", "disposition": "TEXT", "reason": "TEXT",
                "ent_key": "TEXT", "detail": "TEXT", "value_raw": "BIGINT", "value_adj": "BIGINT"}
    db.write_table("silver_row_ledger", led_cols, ctx.ledger)
    db.write_table("silver_party_review_queue", {"entity": "TEXT", "bu_a": "TEXT", "code_a": "TEXT", "name_a": "TEXT", "bu_b": "TEXT",
                                                 "code_b": "TEXT", "name_b": "TEXT", "name_score": "DOUBLE", "address_score": "DOUBLE",
                                                 "reason": "TEXT"}, ctx.review_pairs)
