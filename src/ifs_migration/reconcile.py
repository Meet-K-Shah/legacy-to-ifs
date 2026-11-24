"""Cutover reconciliation engine.

Proves, independently of the transformation code, that nothing was lost or invented:
  * every legacy source row has exactly one disposition (loaded / quarantined / consolidated / excluded)
  * Source rows == IFS rows loaded + quarantined + consolidated duplicates + business-approved exclusions
  * Dollar values reconcile to the penny: adjusted source == loaded + quarantined + excluded (variance $0.00)
  * GL control accounts tie to sub-ledgers; the trial balance is balanced
Sources of truth: raw bronze tables, the approved-fix register, and the IFS load FILES themselves (re-read from disk).
"""
from __future__ import annotations

import csv
from collections import defaultdict

from .config import BUS
from .context import RunContext, apply_fixes, read_bronze, value_cents
from .mapping import DOMAINS, FIELD_MAP, IFS_FILES, VALUE_DOMAINS, table_key
from .money import money, parse_decimal, to_cents
from .textnorm import clean_code


def _file(ctx: RunContext, domain: str) -> list[dict]:
    with (ctx.paths.ifs_load(ctx.mock) / IFS_FILES[domain]).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _source_rows(ctx: RunContext, bu: str, domain: str, adjusted: bool) -> list[dict]:
    """Source rows of a logical domain, straight from bronze (optionally with approved fixes applied)."""
    tkey = table_key(bu, domain)
    rows = read_bronze(ctx.db, bu, tkey)
    if domain in ("customer", "customer_shipto") and bu == "BU2":
        seq = FIELD_MAP[("BU2", "customer")]["seq"]
        want_ship = domain == "customer_shipto"
        rows = [r for r in rows if (int(clean_code(r[seq]) or 0) > 0) == want_ship]
    if domain == "customer_shipto" and bu == "BU2":
        pass
    return apply_fixes(rows, bu, tkey, ctx.fixes) if adjusted else [dict(r, _row=r["_row_num"]) for r in rows]


def run(ctx: RunContext) -> dict:
    res: list[dict] = []
    dollars: list[dict] = []

    def add(check, domain, bu, desc, expected, actual, unit="rows"):
        var = actual - expected
        res.append({"check_id": f"R{len(res) + 1:03d}", "check": check, "domain": domain, "bu": bu, "description": desc,
                    "expected": expected, "actual": actual, "variance": var, "unit": unit, "status": "PASS" if var == 0 else "FAIL"})

    led = defaultdict(list)
    for l in ctx.ledger:
        led[(l["domain"], l["bu"])].append(l)

    # ---- 1. ledger coverage: every source row has exactly one disposition
    for domain in DOMAINS:
        for bu in BUS:
            if domain == "customer_shipto" and False:
                continue
            src = _source_rows(ctx, bu, domain, False)
            rows = led.get((domain, bu), [])
            distinct = {l["source_row"] for l in rows}
            add("COVERAGE", domain, bu, "Source rows == ledger rows (each source row has one disposition)", len(src), len(rows))
            add("COVERAGE", domain, bu, "No source row has more than one disposition", len(rows), len(distinct))

    # ---- 2. row-count equation per domain: source = loaded (file) + quarantined + consolidated + excluded
    file_rows = {d: _file(ctx, d) for d in DOMAINS}
    loaded_file = {d: len(file_rows[d]) for d in DOMAINS}
    loaded_file["customer_shipto"] = sum(1 for r in file_rows["customer_shipto"] if r["ADDRESS_TYPE"] == "SHIP_TO")
    loaded_file["gl_balance"] = sum(1 for r in file_rows["gl_balance"] if r["ENTRY_TYPE"] == "OPENING")
    counts = []
    for domain in DOMAINS:
        src = sum(len(_source_rows(ctx, bu, domain, False)) for bu in BUS)
        by = {k: sum(1 for bu in BUS for l in led.get((domain, bu), []) if l["disposition"] == k)
              for k in ("QUARANTINED", "CONSOLIDATED", "EXCLUDED", "LOADED")}
        add("COUNT", domain, "ALL", "Source rows == IFS rows loaded + quarantined + consolidated duplicates + excluded",
            src, loaded_file[domain] + by["QUARANTINED"] + by["CONSOLIDATED"] + by["EXCLUDED"])
        add("COUNT", domain, "ALL", "Ledger LOADED rows == rows in IFS load file", by["LOADED"], loaded_file[domain])
        counts.append({"domain": domain, "source_rows": src, "loaded": loaded_file[domain], "quarantined": by["QUARANTINED"],
                       "consolidated": by["CONSOLIDATED"], "excluded": by["EXCLUDED"]})

    # ---- 3. dollar parity (value domains) per BU
    bu_col = {"inventory": "SOURCE_BU", "open_po": "SOURCE_BU", "open_so": "SOURCE_BU", "open_ar": "SOURCE_BU", "open_ap": "SOURCE_BU"}
    val_col = {"inventory": "EXT_VALUE", "open_po": "EXT_VALUE", "open_so": "EXT_VALUE", "open_ar": "OPEN_AMOUNT", "open_ap": "OPEN_AMOUNT"}
    loaded_by = defaultdict(int)
    for d in VALUE_DOMAINS:
        for r in file_rows[d]:
            if d == "gl_balance":
                if r["ENTRY_TYPE"] == "OPENING":
                    loaded_by[(d, r["COMPANY"])] += to_cents(parse_decimal(r["BALANCE"]))
            else:
                loaded_by[(d, r[bu_col[d]])] += to_cents(parse_decimal(r[val_col[d]]))
    for d in VALUE_DOMAINS:
        for bu in BUS:
            raw_rows = _source_rows(ctx, bu, d, False)
            adj_rows = _source_rows(ctx, bu, d, True)
            raw = sum(value_cents(d, bu, r) for r in raw_rows)
            adj = sum(value_cents(d, bu, r) for r in adj_rows)
            by_row = {r["_row"]: r for r in adj_rows}
            quar = sum(value_cents(d, bu, by_row[l["source_row"]]) for l in led.get((d, bu), []) if l["disposition"] == "QUARANTINED")
            excl = sum(value_cents(d, bu, by_row[l["source_row"]]) for l in led.get((d, bu), []) if l["disposition"] == "EXCLUDED")
            loaded = loaded_by[(d, bu)]
            var = adj - (loaded + quar + excl)
            dollars.append({"domain": d, "bu": bu, "raw_source_cents": raw, "corrections_cents": adj - raw, "adjusted_source_cents": adj,
                            "loaded_cents": loaded, "quarantined_cents": quar, "excluded_cents": excl, "variance_cents": var,
                            "status": "PASS" if var == 0 else "FAIL"})
            add("DOLLAR", d, bu, "Adjusted source $ == loaded $ + quarantined $ + excluded $ (variance must be $0.00)",
                adj, loaded + quar + excl, "cents")

    # ---- 4. GL: trial balance and sub-ledger tie-out
    ifs_role = {m["ifs_account"]: m["control_role"] for m in ctx.gl_map.values()}
    tbal = defaultdict(int)
    for r in file_rows["gl_balance"]:
        tbal[r["COMPANY"]] += to_cents(parse_decimal(r["BALANCE"]))
    for bu in BUS:
        add("GL_TB", "gl_balance", bu, "Loaded trial balance (opening + approved adjustments) sums to $0.00", 0, tbal[bu], "cents")
    ties = []
    sub_dom = {"AR": ("open_ar", 1), "AP": ("open_ap", -1), "INV": ("inventory", 1)}
    for bu in BUS:
        gl_raw_rows = _source_rows(ctx, bu, "gl_balance", False)
        gm = FIELD_MAP[(bu, "gl")]
        for role, (dom, sign) in sub_dom.items():
            gl_raw = sum(to_cents(parse_decimal(r[gm["balance"]])) for r in gl_raw_rows
                         if ctx.gl_map.get((bu, clean_code(r[gm["acct"]])), {}).get("control_role") == role)
            sub_raw = sign * sum(value_cents(dom, bu, r) for r in _source_rows(ctx, bu, dom, False))
            sub_adj = sign * sum(value_cents(dom, bu, r) for r in _source_rows(ctx, bu, dom, True))
            posted = sum(to_cents(parse_decimal(r["BALANCE"])) for r in file_rows["gl_balance"]
                         if r["COMPANY"] == bu and r["ENTRY_TYPE"] == "ADJUSTMENT" and ifs_role.get(r["ACCOUNT"]) == role)
            raw_var = gl_raw - sub_raw
            residual = raw_var + posted
            ties.append({"bu": bu, "control": role, "gl_control_raw_cents": gl_raw, "subledger_raw_cents": sub_raw,
                         "raw_break_cents": raw_var, "adjusting_je_cents": posted, "residual_break_cents": residual,
                         "pending_corrections_cents": sub_adj - sub_raw, "status": "PASS" if residual == 0 else "FAIL"})
            add("GL_TIEOUT", "gl_balance", bu, f"{role} control account ties to sub-ledger after approved adjusting journals", 0, residual, "cents")

    # ---- 5. XREF / golden-record integrity
    for dom, tbl, idc in (("item", "silver_item_xref", "enterprise_part_no"), ("customer", "silver_customer_xref", "enterprise_id"),
                          ("vendor", "silver_vendor_xref", "enterprise_id")):
        golden_t = {"item": "silver_item_golden", "customer": "silver_customer_golden", "vendor": "silver_vendor_golden"}[dom]
        gid = "part_no" if dom == "item" else "enterprise_id"
        n_xref_bad = ctx.db.scalar(f"SELECT COUNT(*) FROM {tbl} WHERE status IN ('LOADED','CONSOLIDATED') AND ({idc} IS NULL OR TRIM({idc}) = '')")
        add("XREF", dom, "ALL", "Every loaded/consolidated legacy record carries an enterprise ID", 0, int(n_xref_bad))
        n_orph = ctx.db.scalar(f"SELECT COUNT(*) FROM {tbl} x LEFT JOIN {golden_t} g ON x.{idc} = g.{gid} WHERE x.status IN ('LOADED','CONSOLIDATED') AND g.{gid} IS NULL")
        add("XREF", dom, "ALL", "Every XREF enterprise ID exists as a golden record", 0, int(n_orph))
        dup_g = ctx.db.scalar(f"SELECT COUNT(*) - COUNT(DISTINCT {gid}) FROM {golden_t}")
        add("XREF", dom, "ALL", "Golden IDs are unique", 0, int(dup_g))
        multi = ctx.db.scalar(f"SELECT COUNT(*) FROM (SELECT bu, legacy_code FROM {tbl} WHERE status IN ('LOADED','CONSOLIDATED') GROUP BY bu, legacy_code HAVING COUNT(DISTINCT {idc}) > 1) x")
        add("XREF", dom, "ALL", "Each legacy code maps to exactly one enterprise ID", 0, int(multi))

    status = "PASS" if all(r["status"] == "PASS" for r in res) else "FAIL"
    ctx.db.write_table("recon_results", {"check_id": "TEXT", "check": "TEXT", "domain": "TEXT", "bu": "TEXT", "description": "TEXT",
                                         "expected": "BIGINT", "actual": "BIGINT", "variance": "BIGINT", "unit": "TEXT", "status": "TEXT"}, res)
    ctx.db.write_table("recon_dollars", {k: ("TEXT" if k in ("domain", "bu", "status") else "BIGINT") for k in dollars[0]}, dollars)
    ctx.db.write_table("recon_counts", {k: ("TEXT" if k == "domain" else "BIGINT") for k in counts[0]}, counts)
    ctx.db.write_table("recon_gl_tieout", {k: ("TEXT" if k in ("bu", "control", "status") else "BIGINT") for k in ties[0]}, ties)
    return {"status": status, "results": res, "dollars": dollars, "counts": counts, "ties": ties}
