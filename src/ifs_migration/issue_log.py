"""Data issue log: open defects (from the row ledger), resolved/closed items (from approved fixes) and pending steward decisions."""
from __future__ import annotations

import csv
from pathlib import Path

from .context import RunContext
from .issues import OWNERS, SEVERITY_RANK, info

COLS = ["issue_id", "domain", "bu", "source_row", "source_key", "defect_code", "severity", "status", "owner", "description",
        "recommended_action", "detail", "ticket", "resolved_in_mock", "business_decision"]


def build(ctx: RunContext, recon: dict) -> list[dict]:
    rows: list[dict] = []
    for l in ctx.ledger:
        if l["disposition"] != "QUARANTINED":
            continue
        i = info(l["reason"])
        rows.append({"issue_id": f"ISS-{l['domain']}-{l['bu']}-{l['source_row']}", "domain": l["domain"], "bu": l["bu"],
                     "source_row": l["source_row"], "source_key": l["source_key"], "defect_code": l["reason"],
                     "severity": i["severity"], "status": "OPEN", "owner": OWNERS.get(l["domain"], ""), "description": i["title"],
                     "recommended_action": i["action"], "detail": l["detail"], "ticket": "", "resolved_in_mock": "", "business_decision": ""})
    for p in ctx.review_pairs:
        i = info("PARTY_REVIEW_PENDING")
        rows.append({"issue_id": f"ISS-{p['entity']}-REVIEW-{p['bu_a']}{p['code_a']}-{p['bu_b']}{p['code_b']}", "domain": p["entity"],
                     "bu": f"{p['bu_a']}/{p['bu_b']}", "source_row": "", "source_key": f"{p['code_a']} ~ {p['code_b']}",
                     "defect_code": "PARTY_REVIEW_PENDING", "severity": i["severity"], "status": "OPEN", "owner": OWNERS[p["entity"]],
                     "description": f"{p['name_a']} vs {p['name_b']} (name {p['name_score']}, address {p['address_score']})",
                     "recommended_action": i["action"], "detail": p["reason"], "ticket": "", "resolved_in_mock": "", "business_decision": ""})
    for t in recon["ties"]:
        if t["residual_break_cents"] != 0:
            i = info("RECON_GL_SUBLEDGER")
            rows.append({"issue_id": f"ISS-gl-{t['bu']}-{t['control']}", "domain": "gl_balance", "bu": t["bu"], "source_row": "",
                         "source_key": t["control"], "defect_code": "RECON_GL_SUBLEDGER", "severity": i["severity"], "status": "OPEN",
                         "owner": OWNERS["gl_balance"], "description": f"{t['control']} control differs from sub-ledger by ${t['residual_break_cents'] / 100:,.2f}",
                         "recommended_action": i["action"], "detail": "", "ticket": "", "resolved_in_mock": "", "business_decision": ""})
    for a in ctx.fixes.applied:                     # closed by an approved business decision
        if a["kind"] == "CELL_FIX":
            rows.append({"issue_id": f"ISS-{a['domain']}-{a['bu']}-{a['row_num']}", "domain": a["domain"], "bu": a["bu"], "source_row": a["row_num"],
                         "source_key": "", "defect_code": a["defect_code"], "severity": info(a["defect_code"])["severity"], "status": "RESOLVED",
                         "owner": a["owner"], "description": info(a["defect_code"])["title"], "recommended_action": info(a["defect_code"])["action"],
                         "detail": "", "ticket": a["ticket"], "resolved_in_mock": a["mock"],
                         "business_decision": f"Corrected {a['field']} -> {a['new_value']!r}"})
        elif a["kind"] == "EXCLUSION":
            rows.append({"issue_id": f"ISS-{a['domain']}-{a['bu']}-{a['row_num']}", "domain": a["domain"], "bu": a["bu"], "source_row": a["row_num"],
                         "source_key": "", "defect_code": a["defect_code"], "severity": info(a["defect_code"])["severity"], "status": "CLOSED_EXCLUDED",
                         "owner": a["owner"], "description": info(a["defect_code"])["title"], "recommended_action": info(a["defect_code"])["action"],
                         "detail": "", "ticket": a["ticket"], "resolved_in_mock": a["mock"], "business_decision": a["reason"]})
        elif a["kind"] == "PARTY_DECISION":
            rows.append({"issue_id": f"ISS-{a['entity']}-DECISION-{a['ticket']}", "domain": a["entity"], "bu": f"{a['a'][0]}/{a['b'][0]}",
                         "source_row": "", "source_key": f"{a['a'][1]} ~ {a['b'][1]}", "defect_code": "PARTY_REVIEW_PENDING", "severity": "MEDIUM",
                         "status": "RESOLVED", "owner": a["owner"], "description": "Possible duplicate reviewed by steward",
                         "recommended_action": "", "detail": "", "ticket": a["ticket"], "resolved_in_mock": a["mock"],
                         "business_decision": a["decision"]})
        elif a["kind"] == "GL_ADJUSTMENT":
            rows.append({"issue_id": f"ISS-gl-{a['bu']}-AP", "domain": "gl_balance", "bu": a["bu"], "source_row": "", "source_key": "AP",
                         "defect_code": "RECON_GL_SUBLEDGER", "severity": "CRITICAL", "status": "RESOLVED", "owner": a["owner"],
                         "description": info("RECON_GL_SUBLEDGER")["title"], "recommended_action": "", "detail": "", "ticket": a["ticket"],
                         "resolved_in_mock": a["mock"], "business_decision": f"{a['memo']} (${a['amount_cents'] / 100:,.2f})"})
    rows.sort(key=lambda r: (r["status"] != "OPEN", -SEVERITY_RANK[r["severity"]], r["domain"], str(r["bu"]), str(r["source_row"])))
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
