"""Automated data profiling: Domain Readiness Scorecard on the Bronze layer.

Measures, per domain and business unit: completeness of mandatory IFS fields, validity of UOM codes,
referential integrity (orphans), key uniqueness, duplicate candidates and hygiene defects (spaces / case).
All counts come from SQL against the bronze tables (portable DuckDB/SQLite SQL) except the attribute-based
duplicate-candidate detection, which needs the item-description parser.
"""
from __future__ import annotations

from collections import Counter

from .config import BUS
from .context import RunContext
from .itemspec import item_key, key_complete, parse_item_description
from .mapping import FIELD_MAP, FK_CHECKS, MANDATORY, RECOMMENDED, UOM_CHECKS, bronze_table
from .textnorm import clean_code, clean_text, normalize_company_name, normalize_taxid, normalize_zip

PROFILE_TABLES = ["item", "bom", "customer", "vendor", "inventory", "po", "so", "ar", "ap", "gl"]
TABLE_DOMAIN = {"item": "item", "bom": "bom", "customer": "customer", "vendor": "vendor", "inventory": "inventory",
                "po": "open_po", "so": "open_so", "ar": "open_ar", "ap": "open_ap", "gl": "gl_balance"}
PASS_LINE = 98.0


def _metric(stage, domain, bu, dim, name, bad, total, higher_is_better=False):
    good = total - bad if not higher_is_better else bad
    pct = 100.0 if total == 0 else round(100.0 * good / total, 2)
    return {"stage": stage, "domain": domain, "bu": bu, "dimension": dim, "metric": name,
            "defects": bad if not higher_is_better else total - bad, "total": total, "score_pct": pct}


def _where(bu, tkey):
    return "WHERE TRIM(cust_seq) IN ('0','')" if (bu == "BU2" and tkey == "customer") else ""


def run(ctx: RunContext) -> dict:
    db = ctx.db
    metrics: list[dict] = []
    summary_rows = []
    for bu in BUS:
        for tkey in PROFILE_TABLES:
            fm = FIELD_MAP[(bu, tkey)]
            t = bronze_table(bu, tkey)
            dom = TABLE_DOMAIN[tkey]
            where = _where(bu, tkey)
            total = db.scalar(f"SELECT COUNT(*) FROM {t} {where}")
            summary_rows.append((dom, bu, total))
            # completeness of mandatory / recommended fields
            for label, fields in (("Mandatory", MANDATORY.get(tkey, [])), ("Recommended", RECOMMENDED.get(tkey, []))):
                cols = [(f, fm[f]) for f in fields if fm.get(f)]
                if not cols or total == 0:
                    continue
                sel = ", ".join(f"SUM(CASE WHEN TRIM(COALESCE({c},'')) <> '' THEN 1 ELSE 0 END) AS f_{f}" for f, c in cols)
                row = db.query(f"SELECT {sel} FROM {t} {where}")[0]
                filled = sum(int(row[f'f_{f}'] or 0) for f, _ in cols)
                metrics.append(_metric("SOURCE", dom, bu, "COMPLETENESS", f"{label} fields populated", filled, total * len(cols), True))
                for f, c in cols:
                    if label == "Mandatory":
                        metrics.append(_metric("SOURCE", dom, bu, "COMPLETENESS", f"{f} ({c}) populated", int(row[f'f_{f}'] or 0), total, True))
            # key uniqueness (exact duplicate keys after trim/upper)
            key_col = fm.get("code") or fm.get("acct") or fm.get("inv") or fm.get("order")
            if key_col and tkey not in ("bom",):
                extra = f"AND {where[6:]}" if where else ""
                dup = db.scalar(f"SELECT COALESCE(SUM(c-1),0) FROM (SELECT COUNT(*) c FROM {t} WHERE TRIM(COALESCE({key_col},''))<>'' {extra} "
                                f"GROUP BY UPPER(TRIM({key_col}))"
                                + (f", UPPER(TRIM({fm['line']}))" if fm.get("line") else "") + ") x WHERE c>1")
                metrics.append(_metric("SOURCE", dom, bu, "UNIQUENESS", "Duplicate primary keys", int(dup or 0), total))
                hyg = db.scalar(f"SELECT COUNT(*) FROM {t} {where} {'AND' if where else 'WHERE'} {key_col} IS NOT NULL AND "
                                f"({key_col} <> TRIM({key_col}) OR {key_col} <> UPPER({key_col})) AND TRIM({key_col}) <> ''") if tkey in ("item",) else 0
                if tkey == "item":
                    metrics.append(_metric("SOURCE", dom, bu, "VALIDITY", "Item codes with spaces/lower case (auto-fixable)", int(hyg or 0), total))
            if tkey == "bom":
                dup = db.scalar(f"SELECT COALESCE(SUM(c-1),0) FROM (SELECT COUNT(*) c FROM {t} GROUP BY UPPER(TRIM({fm['parent']})), UPPER(TRIM({fm['comp']})), TRIM({fm['seq']})) x WHERE c>1")
                metrics.append(_metric("SOURCE", dom, bu, "UNIQUENESS", "Duplicate BOM lines", int(dup or 0), total))
                neg = db.scalar(f"SELECT COUNT(*) FROM {t} WHERE CAST(NULLIF(TRIM({fm['qty']}),'') AS DOUBLE) IS NULL OR CAST(NULLIF(TRIM({fm['qty']}),'') AS DOUBLE) <= 0")
                metrics.append(_metric("SOURCE", dom, bu, "VALIDITY", "Quantity per > 0", int(neg or 0), total))
                self_ref = db.scalar(f"SELECT COUNT(*) FROM {t} WHERE UPPER(TRIM({fm['parent']})) = UPPER(TRIM({fm['comp']}))")
                metrics.append(_metric("SOURCE", dom, bu, "REFERENTIAL_INTEGRITY", "Self-referencing BOM lines", int(self_ref or 0), total))
        # UOM validity
        for tkey, f in UOM_CHECKS:
            t = bronze_table(bu, tkey)
            col = FIELD_MAP[(bu, tkey)][f]
            total = db.scalar(f"SELECT COUNT(*) FROM {t}")
            bad = db.scalar(f"SELECT COUNT(*) FROM {t} x LEFT JOIN ref_uom_map m ON UPPER(TRIM(COALESCE(x.{col},''))) = m.legacy_code WHERE m.legacy_code IS NULL")
            metrics.append(_metric("SOURCE", TABLE_DOMAIN[tkey], bu, "VALIDITY", "UOM code in canonical lookup", int(bad), total))
        # referential integrity (orphans)
        for child, ccol, parent, pcol, label in FK_CHECKS:
            ct, pt = bronze_table(bu, child), bronze_table(bu, parent)
            cc, pc = FIELD_MAP[(bu, child)][ccol], FIELD_MAP[(bu, parent)][pcol]
            total = db.scalar(f"SELECT COUNT(*) FROM {ct}")
            orphan = db.scalar(f"SELECT COUNT(*) FROM {ct} c LEFT JOIN (SELECT DISTINCT UPPER(TRIM({pc})) k FROM {pt}) p ON UPPER(TRIM(c.{cc})) = p.k WHERE p.k IS NULL")
            metrics.append(_metric("SOURCE", TABLE_DOMAIN[child], bu, "REFERENTIAL_INTEGRITY", label, int(orphan), total))
        # ship-to RI (BU1 separate file; BU2 ship-tos live in the customer file with cust_seq > 0)
        if bu == "BU1":
            tot = db.scalar("SELECT COUNT(*) FROM bronze_bu1_shipto")
            orph = db.scalar("SELECT COUNT(*) FROM bronze_bu1_shipto s LEFT JOIN (SELECT DISTINCT UPPER(TRIM(Customer)) k FROM bronze_bu1_customer) c ON UPPER(TRIM(s.Customer)) = c.k WHERE c.k IS NULL")
        else:
            tot = db.scalar("SELECT COUNT(*) FROM bronze_bu2_customer WHERE TRIM(cust_seq) NOT IN ('0','')")
            orph = db.scalar("SELECT COUNT(*) FROM bronze_bu2_customer s LEFT JOIN (SELECT DISTINCT UPPER(TRIM(cust_num)) k FROM bronze_bu2_customer WHERE TRIM(cust_seq) IN ('0','')) c ON UPPER(TRIM(s.cust_num)) = c.k WHERE TRIM(s.cust_seq) NOT IN ('0','') AND c.k IS NULL")
        metrics.append(_metric("SOURCE", "customer_shipto", bu, "REFERENTIAL_INTEGRITY", "Ship-to without bill-to customer", int(orph), int(tot)))
        summary_rows.append(("customer_shipto", bu, int(tot)))

    # duplicate candidates: attribute-identity for items, name+zip / tax ID for parties
    item_keys: dict[str, list[str]] = {}
    for bu in BUS:
        fm = FIELD_MAP[(bu, "item")]
        for r in ctx.db.query(f"SELECT * FROM {bronze_table(bu, 'item')}"):
            cat = ctx.cat_map.get((bu, clean_code(r[fm["cat"]])))
            if not cat or not clean_text(r[fm["desc"]]):
                continue
            a = parse_item_description(cat, r[fm["desc"]])
            if key_complete(a):
                item_keys.setdefault(item_key(a), []).append(bu)
    for bu in BUS:
        total = next(t for d, b, t in summary_rows if d == "item" and b == bu)
        in_dupe = sum(v.count(bu) for v in item_keys.values() if len(v) > 1)
        cross = sum(v.count(bu) for v in item_keys.values() if len(set(v)) > 1)
        metrics.append(_metric("SOURCE", "item", bu, "UNIQUENESS", "Rows that are duplicate candidates (attribute identity)", in_dupe, total))
        metrics.append(_metric("SOURCE", "item", bu, "UNIQUENESS", "Rows duplicated in the other BU (cross-BU)", cross, total))
    for kind in ("customer", "vendor"):
        seen: Counter = Counter()
        rows_by_bu: dict[str, list[tuple[str, str]]] = {}
        for bu in BUS:
            fm = FIELD_MAP[(bu, kind)]
            where = _where(bu, kind)
            lst = []
            for r in ctx.db.query(f"SELECT * FROM {bronze_table(bu, kind)} {where}"):
                nm = normalize_company_name(r[fm["name"]])
                if not nm:
                    continue
                keys = [("N", nm, normalize_zip(r[fm["zip"]]))]
                tax = normalize_taxid(r[fm["tax"]])
                if tax:
                    keys.append(("T", tax))
                lst.append(keys)
                for k in keys:
                    seen[k] += 1
            rows_by_bu[bu] = lst
        for bu in BUS:
            total = next(t for d, b, t in summary_rows if d == kind and b == bu)
            dup = sum(1 for keys in rows_by_bu[bu] if any(seen[k] > 1 for k in keys))
            metrics.append(_metric("SOURCE", kind, bu, "UNIQUENESS", "Rows that are duplicate candidates (exact name+zip or tax ID)", dup, total))

    # domain readiness = mean of dimension scores (excluding hygiene-only metrics), RAG against 98 / 95
    readiness = []
    for dom in sorted({m["domain"] for m in metrics}):
        for bu in BUS:
            ms = [m for m in metrics if m["domain"] == dom and m["bu"] == bu and not m["metric"].endswith("populated")
                  or (m["domain"] == dom and m["bu"] == bu and m["metric"] == "Mandatory fields populated")]
            ms = [m for m in ms if m["domain"] == dom and m["bu"] == bu and "cross-BU" not in m["metric"]
                  and "auto-fixable" not in m["metric"] and m["metric"] != "Recommended fields populated"]
            if not ms:
                continue
            score = round(sum(m["score_pct"] for m in ms) / len(ms), 2)
            rows = next((t for d, b, t in summary_rows if d == dom and b == bu), 0)
            readiness.append({"domain": dom, "bu": bu, "rows": rows, "readiness_pct": score,
                              "rag": "GREEN" if score >= 98 else "AMBER" if score >= 95 else "RED",
                              "defect_findings": sum(m["defects"] for m in ms if m["dimension"] != "COMPLETENESS")})
    db.write_table("profile_metrics", {"stage": "TEXT", "domain": "TEXT", "bu": "TEXT", "dimension": "TEXT", "metric": "TEXT",
                                       "defects": "BIGINT", "total": "BIGINT", "score_pct": "DOUBLE"}, metrics)
    db.write_table("profile_domain_readiness", {"domain": "TEXT", "bu": "TEXT", "rows": "BIGINT", "readiness_pct": "DOUBLE",
                                                "rag": "TEXT", "defect_findings": "BIGINT"}, readiness)
    return {"metrics": metrics, "readiness": readiness}
