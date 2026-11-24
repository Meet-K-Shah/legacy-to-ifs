"""Synthetic legacy-extract generator for two acquired fabrication business units.

BU-1 runs SYSPRO, BU-2 runs Infor Syteline. The generator is seeded and deterministic, plants defects with
known counts (ground truth), and also writes the simulated business-owner remediation responses that the
Mock 2 / Mock 3 cutover rehearsals consume.

Usage:  python -m ifs_migration.datagen.generate --scale 1.0 --seed 42
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from ..config import BUS, Paths
from ..itemspec import SPECS
from ..money import cents_str, ext_cents, parse_decimal, to_cents
from . import catalog
from .common import Registry, Table, pick_indices
from .parties import build_parties

OWNERS = {"item": "Supply Chain / Item Data Steward", "bom": "Engineering", "customer": "Sales Ops / AR",
          "customer_shipto": "Sales Ops / AR", "vendor": "Procurement / AP", "inventory": "Warehouse / Inventory Control",
          "open_po": "Procurement", "open_so": "Sales Operations", "open_ar": "Finance (AR)", "open_ap": "Finance (AP)",
          "gl_balance": "Controller"}

UOM_MAP_ROWS = [
    ("EA", "EA", "Each"), ("EACH", "EA", "Synonym"), ("EAC", "EA", "Synonym"), ("PC", "EA", "Synonym"),
    ("PCS", "EA", "Synonym"), ("PIECE", "EA", "Synonym"), ("PIECES", "EA", "Synonym"),
    ("FT", "FT", "Feet"), ("FEET", "FT", "Synonym"), ("FOOT", "FT", "Synonym"),
    ("SHT", "SHT", "Sheet"), ("SHEET", "SHT", "Synonym"), ("SHEETS", "SHT", "Synonym"),
    ("LB", "LB", "Pound"), ("LBS", "LB", "Synonym"), ("KG", "KG", "Kilogram"), ("IN", "IN", "Inch"),
]

GL_TEMPLATE = [  # role, ifs_acct, name, type, bu1 code, bu2 code
    ("CASH", "1000", "Cash and Equivalents", "A", "1000-00", "10000"),
    ("AR", "1200", "Accounts Receivable - Trade", "A", "1100-00", "11000"),
    ("INV", "1400", "Inventory - Raw Materials & WIP", "A", "1300-00", "13000"),
    ("", "1450", "Prepaid Expenses", "A", "1400-00", "14000"),
    ("", "1700", "Property, Plant & Equipment", "A", "1500-00", "15000"),
    ("", "1790", "Accumulated Depreciation", "A", "1590-00", "15900"),
    ("AP", "2100", "Accounts Payable - Trade", "L", "2000-00", "20000"),
    ("", "2200", "Accrued Liabilities", "L", "2100-00", "21000"),
    ("", "2400", "Customer Deposits", "L", "2200-00", "22000"),
    ("", "2700", "Long-Term Debt", "L", "2500-00", "25000"),
    ("", "3000", "Common Stock", "E", "3000-00", "30000"),
    ("", "3900", "Retained Earnings", "E", "3900-00", "39000"),
    ("", "4000", "Revenue - Fabrication", "R", "4000-00", "40000"),
    ("", "4100", "Revenue - Field Services", "R", "4100-00", "41000"),
    ("", "5000", "Cost of Goods Sold", "X", "5000-00", "50000"),
    ("", "5100", "Direct Labor", "X", "5100-00", "51000"),
    ("", "5200", "Manufacturing Overhead", "X", "5200-00", "52000"),
    ("", "6000", "Salaries & Wages", "X", "6000-00", "60000"),
    ("", "6100", "Rent & Utilities", "X", "6100-00", "61000"),
    ("", "6900", "AP Adjustments / Suspense", "X", "6900-00", "69000"),
]


def _dec(s: str) -> Decimal:
    return Decimal(s)


def _date(rng, y0=2026, m0=6, span_days=330) -> tuple[int, int, int]:
    from datetime import date, timedelta

    d = date(y0, m0, 1) + timedelta(days=rng.randint(0, span_days))
    return d.year, d.month, d.day


def _fmt_d(bu: str, y: int, m: int, d: int) -> str:
    return f"{y}-{m:02d}-{d:02d}" if bu == "BU1" else f"{m:02d}/{d:02d}/{y}"


def _fmt_amt(bu: str, value: Decimal, rng, places: int = 2, commas_p: float = 0.35) -> str:
    s = f"{value:.{places}f}"
    if bu == "BU2" and abs(value) >= 1000 and rng.random() < commas_p:
        s = f"{value:,.{places}f}"
    return s


def _fmt_qty(bu: str, q: Decimal) -> str:
    return f"{q:.3f}" if bu == "BU2" else format(q.normalize(), "f")


def inject(rng, table: Table, rows: list[dict], plan: list) -> None:
    """plan: (rate, minimum, code, action, detail, fn(row)->fix|None); indices are disjoint across plan entries."""
    used: set[int] = set()
    for rate, minimum, code, action, detail, fn in plan:
        for i in pick_indices(rng, len(rows), rate, minimum, exclude=used):
            used.add(i)
            fix = fn(rows[i])
            table.defect(rows[i], code, action, detail, fix)


# ===================================================================================== items


def build_items(reg: Registry, rng, scale: float, paths: Paths):
    n_per_bu = max(80, round(5000 * scale))
    shared = round(0.15 * n_per_bu)
    wdup = max(1, round(0.01 * n_per_bu))
    dupcode = max(1, round(0.003 * n_per_bu))
    nullkey = max(1, round(0.0004 * n_per_bu))
    unique_own = n_per_bu - shared - wdup - dupcode - nullkey
    universe = catalog.build_universe(rng, shared + 2 * unique_own)
    split = {"BU1": universe[:shared] + universe[shared:shared + unique_own],
             "BU2": universe[:shared] + universe[shared + unique_own:]}
    out = {}
    cols = {"BU1": ["StockCode", "Description", "LongDesc", "StockUom", "ProductClass", "PartCategory", "Mass",
                    "DrawingNumber", "Revision", "DateAdded", "UnitCost"],
            "BU2": ["item", "description", "u_m", "family_code", "matl_type", "unit_weight", "drawing_nbr", "revision",
                    "create_date", "unit_cost"]}
    files = {"BU1": "InvMaster.csv", "BU2": "item_mst.csv"}
    for bu in BUS:
        c = {k: v for k, v in zip(("code", "desc", "uom", "cls"), (
            ("StockCode", "Description", "StockUom", "ProductClass") if bu == "BU1" else ("item", "description", "u_m", "family_code")))}
        table = Table(reg, "item", bu, files[bu], cols[bu])
        recs: list[dict] = []
        counters: dict[str, int] = defaultdict(lambda: rng.randint(10, 200))
        gcount = [rng.randint(1000, 5000)]

        def new_code(cat: str) -> str:
            if bu == "BU1":
                counters[cat] += rng.randint(1, 3)
                return f"{catalog.CATEGORY_CODE['BU1'][cat]}-{counters[cat]:05d}"
            gcount[0] += rng.randint(1, 4)
            return f"{'F' if cat == 'FABRICATION' else ''}{gcount[0]:07d}"

        def make_row(attrs, code, dup_of=None):
            cat = attrs["category"]
            uom = catalog.BASE_UOM[cat]
            cost = _dec(attrs["base_cost"]) * Decimal(str(round(rng.uniform(0.95, 1.05), 3)))
            cost_s = f"{cost:.4f}" if rng.random() < 0.5 else f"{cost:.2f}"
            desc = catalog.render_description(attrs, bu, rng)
            weight = f"{rng.uniform(0.2, 900):.2f}"
            y, m, d = _date(rng, 2019, 1, 2400)
            if bu == "BU1":
                long = f"{desc}; ASME B16.5; MTR REQUIRED" if (rng.random() < 0.3 and cat != "FABRICATION") else ""
                row = {"StockCode": code, "Description": desc, "LongDesc": long, "StockUom": uom,
                       "ProductClass": catalog.CATEGORY_CODE["BU1"][cat], "PartCategory": "M" if cat == "FABRICATION" else "B",
                       "Mass": weight, "DrawingNumber": f"DWG-{attrs['dwg']}" if attrs["dwg"] else "",
                       "Revision": attrs["rev"], "DateAdded": _fmt_d(bu, y, m, d), "UnitCost": cost_s}
            else:
                row = {"item": code, "description": desc, "u_m": uom, "family_code": catalog.CATEGORY_CODE["BU2"][cat],
                       "matl_type": "M" if cat == "FABRICATION" else "P", "unit_weight": weight,
                       "drawing_nbr": attrs["dwg"], "revision": attrs["rev"], "create_date": _fmt_d(bu, y, m, d), "unit_cost": cost_s}
            return {"row": table.add(row), "code": code, "canon": attrs, "uom": uom, "cost": cost_s, "desc": desc,
                    "defective": False, "dup": False, "nullkey": False}

        for attrs in split[bu]:
            recs.append(make_row(attrs, new_code(attrs["category"])))
        for src in rng.sample(recs[:], wdup):                      # same item loaded twice under different codes
            r = make_row(src["canon"], new_code(src["canon"]["category"]))
            r["dup"] = True
            recs.append(r)
        for src in rng.sample(recs[:len(split[bu])], dupcode):     # same code reused for a *different* item
            other = rng.choice(split[bu])
            r = make_row(other, src["code"])
            r["dup"] = True
            r["defective"] = True
            recs.append(r)
            table.defect(r["row"], "ITEM_DUP_CODE", "QUARANTINE", "Legacy code already used by another item in this BU",
                         {"exclude": True, "reason": "Duplicate code row approved for deletion; surviving row is the original"})
        for k in range(nullkey):
            row = table.add({c["code"]: "", c["desc"]: "TEMP ITEM - DO NOT USE", c["uom"]: "EA", c["cls"]: catalog.CATEGORY_CODE[bu]["FLANGE"]})
            recs.append({"row": row, "code": "", "canon": None, "uom": "EA", "cost": "0", "desc": "", "defective": True,
                         "dup": False, "nullkey": True})
            table.defect(row, "ITEM_NULL_KEY", "QUARANTINE", "Blank item code",
                         {"exclude": True, "reason": "Placeholder row approved for deletion by data owner"})

        # sort like a real export (by code); duplicate-code rows come after the original (stable sort)
        recs.sort(key=lambda r: (r["code"], r["dup"]))
        table.rows = [r["row"] for r in recs]

        # defects on otherwise valid rows (disjoint index sets)
        eligible = [i for i, r in enumerate(recs) if not r["defective"] and not r["dup"]]
        used: set[int] = set()

        def take(rate, minimum=1, pool=None):
            idx = pick_indices(rng, len(recs), rate, minimum, exclude=used, pool=pool if pool is not None else eligible)
            used.update(idx)
            return idx

        for i in take(0.012):
            r = recs[i]; orig = r["row"][c["uom"]]
            r["row"][c["uom"]] = rng.choice(catalog.INVALID_UOMS); r["defective"] = True
            table.defect(r["row"], "ITEM_INVALID_UOM", "QUARANTINE", "Unit of measure not in canonical lookup",
                         {"field": c["uom"], "new_value": orig})
        for i in take(0.004):
            r = recs[i]; orig = r["row"][c["desc"]]
            r["row"][c["desc"]] = ""; r["defective"] = True
            table.defect(r["row"], "ITEM_NO_DESC", "QUARANTINE", "Blank description", {"field": c["desc"], "new_value": orig})
        for i in take(0.003):
            r = recs[i]; orig = r["row"][c["cls"]]
            r["row"][c["cls"]] = "ZZZ"; r["defective"] = True
            table.defect(r["row"], "ITEM_UNKNOWN_CATEGORY", "QUARANTINE", "Product class not mapped to a category",
                         {"field": c["cls"], "new_value": orig})
        for i in take(0.02, pool=eligible):
            r = recs[i]
            r["row"][c["code"]] = rng.choice([f" {r['code']}", f"{r['code']}  ", f"  {r['code']}"])
            table.defect(r["row"], "ITEM_WHITESPACE_CODE", "AUTO_FIX", "Leading/trailing spaces on item code")
        for i in take(0.015, pool=[j for j in eligible if j not in used]):
            r = recs[i]
            r["row"][c["code"]] = r["row"][c["code"]].lower()
            table.defect(r["row"], "ITEM_CASE_CODE", "AUTO_FIX", "Lower-case item code")
        for i in eligible:
            r = recs[i]
            syn = catalog.UOM_SYNONYMS.get(r["row"][c["uom"]])
            if syn and rng.random() < 0.25:
                r["row"][c["uom"]] = rng.choice(syn)
                table.defect(r["row"], "ITEM_UOM_SYNONYM", "AUTO_FIX", "Non-standard UOM spelling")
        for r in recs:                      # ground truth: which canonical item each legacy code really is
            if r["canon"] is not None and not r["nullkey"] and not (r["dup"] and r["defective"]):
                reg.entity_truth.append({"domain": "item", "bu": bu, "source_key": r["code"], "entity_id": r["canon"]["canon_id"]})
        out[bu] = {"table": table, "recs": recs, "cols": c}
    return out


# ===================================================================================== BOM


def build_bom(reg: Registry, rng, scale: float, items: dict):
    out = {}
    for bu in BUS:
        recs = [r for r in items[bu]["recs"] if r["canon"] is not None and not r["nullkey"] and not (r["dup"] and r["defective"])]
        by_code = {r["code"]: r for r in recs}
        fab_ok = [r for r in recs if r["canon"]["category"] == "FABRICATION" and not r["defective"] and not r["dup"]]
        buy = [r for r in recs if r["canon"]["category"] != "FABRICATION"]
        rng.shuffle(fab_ok)
        target = max(60, round(1500 * scale))
        ncycles = max(1, round(5 * scale))
        nself = max(1, round(3 * scale))
        reserved_n = ncycles * 3 + nself
        reserved, pool = fab_ok[:reserved_n], fab_ok[reserved_n:]
        n_parents = max(8, target // 7)
        l0_n = max(3, round(0.45 * n_parents))
        l0, l1 = pool[:l0_n], pool[l0_n:n_parents]
        cols = ["ParentPart", "Component", "SequenceNum", "QtyPer", "ScrapPct"] if bu == "BU1" else \
            ["parent_item", "comp_item", "oper_num", "qty_per", "scrap_factor"]
        cp, cc, cs, cq = cols[0], cols[1], cols[2], cols[3]
        table = Table(reg, "bom", bu, "BomStructure.csv" if bu == "BU1" else "bom_mst.csv", cols)
        lines: list[dict] = []

        def qty_for(r):
            cat = r["canon"]["category"]
            if cat == "PIPE":
                return Decimal(str(round(rng.uniform(5, 80), 1)))
            if cat == "PLATE":
                return Decimal(rng.randint(1, 4))
            return Decimal(rng.randint(1, 24))

        def add_line(parent_code, comp_code, seq, q, extra=None):
            row = table.add({cp: parent_code, cc: comp_code, cs: str(seq), cq: _fmt_qty(bu, q),
                             cols[4]: f"{rng.uniform(0, 5):.1f}"})
            row["_dup"] = False
            lines.append(row)
            return row

        for parent in l1 + l0:
            comps = rng.sample(buy, rng.randint(5, 8))
            if parent in l0 and l1:
                comps = comps[:-2] + rng.sample(l1, min(2, len(l1)))
            for k, comp in enumerate(comps, start=1):
                add_line(parent["code"], comp["code"], k * 10, qty_for(comp))
        base_lines = list(lines)
        all_codes = {r["code"] for r in recs}

        def ghost(prefix_ok: bool = True) -> str:
            return f"ZZ-{rng.randint(10000, 99999)}" if bu == "BU1" else f"{rng.randint(9000000, 9999999):07d}"

        plan = [
            (0.03, 1, "BOM_ORPHAN_COMPONENT", "QUARANTINE", "Component code does not exist in the item master",
             lambda r: (lambda o: (r.__setitem__(cc, ghost()), {"field": cc, "new_value": o})[1])(r[cc])),
            (0.005, 1, "BOM_ORPHAN_PARENT", "QUARANTINE", "Parent code does not exist in the item master",
             lambda r: (lambda o: (r.__setitem__(cp, ghost()), {"field": cp, "new_value": o})[1])(r[cp])),
            (0.01, 1, "BOM_INVALID_QTY", "QUARANTINE", "Quantity per is zero or negative",
             lambda r: (lambda o: (r.__setitem__(cq, rng.choice(["0", "-1", "-2.5"])), {"field": cq, "new_value": o})[1])(r[cq])),
            (0.02, 1, "BOM_WHITESPACE_CODE", "AUTO_FIX", "Component code has stray spaces",
             lambda r: (r.__setitem__(cc, f" {r[cc]} "), None)[1]),
        ]
        inject(rng, table, base_lines, plan)
        # duplicate lines (second occurrence quarantined)
        for src in rng.sample(base_lines, max(1, round(0.01 * len(base_lines)))):
            row = table.add({k: src[k] for k in cols})
            row["_dup"] = True
            lines.append(row)
            table.defect(row, "BOM_DUPLICATE_LINE", "QUARANTINE", "Same parent/component/sequence loaded twice",
                         {"exclude": True, "reason": "Duplicate BOM line approved for deletion"})
        # circular loops (A->B->C->A) built from reserved, otherwise-unused assemblies
        for k in range(ncycles):
            a, b, c3 = reserved[k * 3:k * 3 + 3]
            for p, q in ((a, b), (b, c3), (c3, a)):
                row = add_line(p["code"], q["code"], 10, Decimal(1))
                table.defect(row, "BOM_CIRCULAR", "QUARANTINE", "Assembly loop: component is its own ancestor",
                             {"exclude": True, "reason": "Loop broken: link is obsolete per Engineering"})
        for s in reserved[ncycles * 3:]:
            row = add_line(s["code"], s["code"], 10, Decimal(1))
            table.defect(row, "BOM_SELF_REFERENCE", "QUARANTINE", "Assembly lists itself as a component",
                         {"exclude": True, "reason": "Self-reference removed; Engineering confirmed it is an error"})
        table.rows = lines
        table.rows.sort(key=lambda r: (r[cp].strip(), int(r[cs]), r["_dup"]))
        out[bu] = {"table": table}
    return out


# ===================================================================================== transactional domains


def _qty_for_item(rng, r):
    """Realistic on-hand / order quantities: big-ticket items (fabricated assemblies, valves) are held in small counts."""
    cat = r["canon"]["category"]
    if cat == "PIPE":
        return Decimal(str(round(rng.uniform(20, 2000), 1)))
    if cat == "PLATE":
        return Decimal(rng.randint(1, 40))
    if cat == "FABRICATION":
        return Decimal(rng.randint(1, 3))
    if cat == "VALVE":
        return Decimal(rng.randint(1, 25))
    if cat in ("GASKET", "BOLTING"):
        return Decimal(rng.randint(10, 800))
    return Decimal(rng.randint(1, 200))


def build_inventory(reg, rng, scale, items):
    out = {}
    for bu in BUS:
        c = items[bu]["cols"]
        recs = [r for r in items[bu]["recs"] if r["canon"] is not None and not r["nullkey"] and not (r["dup"] and r["defective"])]
        cols = ["StockCode", "Warehouse", "LotNumber", "SerialNumber", "QtyOnHand", "StockUom", "UnitCost"] if bu == "BU1" else \
            ["item", "whse", "lot", "serial_num", "qty_on_hand", "u_m", "unit_cost"]
        ic, wc, lc, sc, qc, uc, cc_ = cols
        whs = ["MAIN", "YARD", "FAB1"] if bu == "BU1" else ["WH01", "WH02", "RAW"]
        table = Table(reg, "inventory", bu, "InvWarehouse.csv" if bu == "BU1" else "itemwhse_mst.csv", cols)
        seen: set[tuple] = set()
        rows: list[dict] = []
        n = max(60, round(2000 * scale))
        heat_pool = [f"H{rng.randint(100000, 999999)}" for _ in range(max(10, n // 6))]
        while len(rows) < n:
            r = rng.choice(recs)
            cat = r["canon"]["category"]
            lot = rng.choice(heat_pool) if cat in ("PIPE", "PLATE", "BOLTING", "FLANGE") else ""
            serial = f"SN{rng.randint(1000000, 9999999)}" if cat == "VALVE" and rng.random() < 0.3 else ""
            key = (r["code"], rng.choice(whs), lot, serial)
            if key in seen:
                continue
            seen.add(key)
            qty = _qty_for_item(rng, r)
            cost = _dec(r["cost"]) * Decimal(str(round(rng.uniform(0.9, 1.1), 3)))
            row = table.add({ic: r["code"], wc: key[1], lc: lot, sc: serial, qc: _fmt_qty(bu, qty), uc: r["uom"],
                             cc_: f"{cost:.4f}"})
            row["_item"] = r
            rows.append(row)
        ghost = (lambda: f"ZZ-{rng.randint(10000, 99999)}") if bu == "BU1" else (lambda: f"{rng.randint(9000000, 9999999):07d}")

        def mut(col, newval_fn):
            def f(row):
                o = row[col]
                row[col] = newval_fn(row)
                return {"field": col, "new_value": o}
            return f

        plan = [
            (0.006, 1, "INV_NEGATIVE_QTY", "QUARANTINE", "Negative on-hand quantity",
             mut(qc, lambda r: "-" + r[qc].lstrip("-"))),
            (0.010, 1, "INV_INVALID_UOM", "QUARANTINE", "Unit of measure not in canonical lookup",
             mut(uc, lambda r: rng.choice(catalog.INVALID_UOMS))),
            (0.010, 1, "INV_ORPHAN_ITEM", "QUARANTINE", "Item code does not exist in the item master",
             mut(ic, lambda r: ghost())),
            (0.008, 1, "INV_MISSING_COST", "QUARANTINE", "Unit cost missing", mut(cc_, lambda r: "")),
            (0.020, 1, "INV_WHITESPACE_CODE", "AUTO_FIX", "Stray spaces on item code",
             lambda r: (r.__setitem__(ic, f"{r[ic]} "), None)[1]),
        ]
        inject(rng, table, rows, plan)
        for row in rows:                                           # synonym spellings (auto-fixable)
            syn = catalog.UOM_SYNONYMS.get(row[uc])
            if syn and rng.random() < 0.2:
                row[uc] = rng.choice(syn)
        for src in rng.sample(rows[:], max(1, round(0.003 * len(rows)))):   # duplicate stock key
            row = table.add({k: src[k] for k in cols})
            row[qc] = _fmt_qty(bu, _dec(rng.choice(["3", "7", "12"])))
            row["_dup"] = True
            rows.append(row)
            table.defect(row, "INV_DUPLICATE_KEY", "QUARANTINE", "Duplicate item/warehouse/lot/serial key",
                         {"exclude": True, "reason": "Duplicate stock record approved for deletion after cycle count"})
        table.rows = rows
        table.sort(key=lambda r: (r[ic].strip().upper(), r[wc], r[lc], r[sc], r.get("_dup", False)))
        out[bu] = {"table": table, "cols": cols}
    return out


def _order_rows(reg, rng, scale, items, parties, bu, kind):
    """kind: 'po' (vendor, cost-based) or 'so' (customer, price-based)."""
    recs = [r for r in items[bu]["recs"] if r["canon"] is not None and not r["nullkey"] and not (r["dup"] and r["defective"])]
    if kind == "po":
        pc = [rw[2] for rw in parties["vendor"][bu]["bill_rows"]]
        cols = ["PurchaseOrder", "Line", "Supplier", "StockCode", "QtyOutstanding", "OrderUom", "UnitPrice", "DueDate"] if bu == "BU1" else \
            ["po_num", "po_line", "vend_num", "item", "qty_open", "u_m", "unit_cost", "due_date"]
        fname = "PorMasterDetail.csv" if bu == "BU1" else "poitem_mst.csv"
        domain, party_code_len = "open_po", "PO"
    else:
        pc = [rw[2] for rw in parties["customer"][bu]["bill_rows"]]
        cols = ["SalesOrder", "Line", "Customer", "StockCode", "QtyOutstanding", "OrderUom", "UnitPrice", "ShipDate"] if bu == "BU1" else \
            ["co_num", "co_line", "cust_num", "item", "qty_open", "u_m", "price", "due_date"]
        fname = "SorDetail.csv" if bu == "BU1" else "coitem_mst.csv"
        domain, party_code_len = "open_so", "SO"
    pre = "OPO" if kind == "po" else "OSO"
    ordc, linec, partyc, itemc, qtyc, uomc, pricec, datec = cols
    table = Table(reg, domain, bu, fname, cols)
    rows: list[dict] = []
    n = max(40, round(1000 * scale))
    num = rng.randint(1000, 9000)
    while len(rows) < n:
        num += rng.randint(1, 5)
        party = rng.choice(pc)
        for ln in range(1, rng.randint(1, 6) + 1):
            if len(rows) >= n:
                break
            r = rng.choice(recs)
            qty = _qty_for_item(rng, r)
            base = _dec(r["cost"]) * Decimal(str(round(rng.uniform(0.85, 1.15) if kind == "po" else rng.uniform(1.15, 1.6), 3)))
            y, m, d = _date(rng, 2026, 11, 300)
            row = table.add({ordc: f"{pre}{num:06d}" if bu == "BU1" else f"{num:7d}", linec: str(ln), partyc: party, itemc: r["code"],
                             qtyc: _fmt_qty(bu, qty), uomc: r["uom"], pricec: _fmt_amt(bu, base, rng, 4), datec: _fmt_d(bu, y, m, d)})
            rows.append(row)
    ghost_i = (lambda: f"ZZ-{rng.randint(10000, 99999)}") if bu == "BU1" else (lambda: f"{rng.randint(9000000, 9999999):07d}")
    ghost_p = (lambda: f"{'V' if kind == 'po' else 'C'}{rng.randint(80000, 89999)}") if bu == "BU1" else (lambda: f"{rng.randint(8000000, 8999999):7d}")
    P = "PO" if kind == "po" else "SO"

    def mut(col, fn):
        def f(row):
            o = row[col]
            row[col] = fn(row)
            return {"field": col, "new_value": o}
        return f

    plan = [
        (0.010, 1, f"{P}_ORPHAN_ITEM", "QUARANTINE", "Item code does not exist in the item master", mut(itemc, lambda r: ghost_i())),
        (0.010, 1, f"{P}_ORPHAN_{'VENDOR' if kind == 'po' else 'CUSTOMER'}", "QUARANTINE",
         f"{'Vendor' if kind == 'po' else 'Customer'} code does not exist", mut(partyc, lambda r: ghost_p())),
        (0.010, 1, f"{P}_INVALID_UOM", "QUARANTINE", "Order UOM not in canonical lookup", mut(uomc, lambda r: rng.choice(catalog.INVALID_UOMS))),
        (0.005, 1, f"{P}_INVALID_QTY", "QUARANTINE", "Open quantity is zero or negative", mut(qtyc, lambda r: rng.choice(["0", "-5"]))),
        (0.005, 1, f"{P}_INVALID_DATE", "QUARANTINE", "Due date missing or invalid", mut(datec, lambda r: rng.choice(["00/00/0000", "2026-13-45", ""]))),
        (0.020, 1, f"{P}_WHITESPACE_CODE", "AUTO_FIX", "Stray spaces on item code", lambda r: (r.__setitem__(itemc, f"{r[itemc]} "), None)[1]),
    ]
    inject(rng, table, rows, plan)
    table.rows = rows
    table.sort(key=lambda r: (r[ordc].strip(), int(r[linec])))
    return table, cols


def build_orders(reg, rng, scale, items, parties):
    out = {"po": {}, "so": {}}
    for kind in ("po", "so"):
        for bu in BUS:
            table, cols = _order_rows(reg, rng, scale, items, parties, bu, kind)
            out[kind][bu] = {"table": table, "cols": cols}
    return out


def build_invoices(reg, rng, scale, parties, kind):
    """kind: 'ar' (customers) or 'ap' (vendors)."""
    out = {}
    for bu in BUS:
        pk = "customer" if kind == "ar" else "vendor"
        pc = [rw[2] for rw in parties[pk][bu]["bill_rows"]]
        if kind == "ar":
            cols = ["Invoice", "Customer", "InvoiceDate", "DueDate", "InvoiceBalance"] if bu == "BU1" else \
                ["inv_num", "cust_num", "inv_date", "due_date", "balance"]
            fname = "ArInvoice.csv" if bu == "BU1" else "artran_mst.csv"
        else:
            cols = ["Invoice", "Supplier", "InvoiceDate", "DueDate", "InvoiceBalance"] if bu == "BU1" else \
                ["voucher", "vend_num", "inv_date", "due_date", "balance"]
            fname = "ApInvoice.csv" if bu == "BU1" else "aptrx_mst.csv"
        invc, partyc, dc, ddc, bc = cols
        domain = f"open_{kind}"
        table = Table(reg, domain, bu, fname, cols)
        rows = []
        n = max(40, round(600 * scale))
        num = rng.randint(10000, 50000)
        for _ in range(n):
            num += rng.randint(1, 7)
            y, m, d = _date(rng, 2026, 6, 150)
            from datetime import date, timedelta
            due = date(y, m, d) + timedelta(days=rng.choice([30, 45, 60]))
            amt = Decimal(str(round(rng.uniform(250, 180000), 2)))
            if rng.random() < 0.05:
                amt = -amt                                              # legitimate credit memo
            row = table.add({invc: f"{'INV' if kind == 'ar' else 'VCH'}{num}" if bu == "BU1" else f"{num:8d}", partyc: rng.choice(pc),
                             dc: _fmt_d(bu, y, m, d), ddc: _fmt_d(bu, due.year, due.month, due.day),
                             bc: _fmt_amt(bu, amt, rng)})
            rows.append(row)
        ghost = (lambda: f"{'C' if kind == 'ar' else 'V'}{rng.randint(80000, 89999)}") if bu == "BU1" else (lambda: f"{rng.randint(8000000, 8999999):7d}")
        P = kind.upper()

        def mut(col, fn):
            def f(row):
                o = row[col]
                row[col] = fn(row)
                return {"field": col, "new_value": o}
            return f

        plan = [
            (0.010, 1, f"{P}_ORPHAN_{'CUSTOMER' if kind == 'ar' else 'VENDOR'}", "QUARANTINE", "Party code does not exist",
             mut(partyc, lambda r: ghost())),
            (0.005, 1, f"{P}_INVALID_DATE", "QUARANTINE", "Due date missing or invalid",
             mut(ddc, lambda r: rng.choice(["00/00/0000", "2026-02-31", ""]))),
        ]
        inject(rng, table, rows, plan)
        table.rows = rows
        table.sort(key=lambda r: r[invc].strip())
        out[bu] = {"table": table, "cols": cols}
    return out


def build_gl(reg, rng, inventory, ar, ap, paths: Paths):
    """GL trial balance per BU. Control accounts equal their sub-ledgers except one planted BU-2 AP break."""
    out = {}
    map_rows = []
    for bu in BUS:
        def total(tbl, valfn):
            return sum(valfn(r) for r in tbl.rows)

        ic = inventory[bu]["cols"]
        inv_total = 0
        for r in inventory[bu]["table"].rows:
            q, u = parse_decimal(r[ic[4]]), parse_decimal(r[ic[6]])
            inv_total += ext_cents(q, u) if q is not None and u is not None else 0
        arc = ar[bu]["cols"][-1]
        apc = ap[bu]["cols"][-1]
        ar_total = sum(to_cents(parse_decimal(r[arc])) for r in ar[bu]["table"].rows)
        ap_total = sum(to_cents(parse_decimal(r[apc])) for r in ap[bu]["table"].rows)
        balances: dict[str, int] = {}
        for role, ifs, name, typ, c1, c2 in GL_TEMPLATE:
            code = c1 if bu == "BU1" else c2
            if role == "AR":
                balances[code] = ar_total
            elif role == "INV":
                balances[code] = inv_total
            elif role == "AP":
                balances[code] = -ap_total + (128455 if bu == "BU2" else 0)
            elif ifs == "3900":
                balances[code] = 0                                     # plug below
            else:
                sign = 1 if typ == "A" else -1 if typ in "LER" else 1
                balances[code] = sign * rng.randint(50_000_00, 4_000_000_00) * (-1 if ifs == "1790" else 1)
            map_rows.append((bu, code, ifs, name, role or "NONE"))
        plug = -sum(v for k, v in balances.items())
        re_code = GL_TEMPLATE[11][4] if bu == "BU1" else GL_TEMPLATE[11][5]
        balances[re_code] = plug
        cols = ["GlCode", "Description", "AccountType", "Balance"] if bu == "BU1" else ["acct", "acct_desc", "acct_type", "balance"]
        table = Table(reg, "gl_balance", bu, "GenMaster.csv" if bu == "BU1" else "chart_mst.csv", cols)
        for role, ifs, name, typ, c1, c2 in GL_TEMPLATE:
            code = c1 if bu == "BU1" else c2
            val = Decimal(balances[code]) / 100
            row = table.add({cols[0]: code, cols[1]: name if bu == "BU1" else name.upper(), cols[2]: typ,
                             cols[3]: _fmt_amt(bu, val, rng)})
            if role == "AP" and bu == "BU2":
                table.defect(row, "RECON_GL_SUBLEDGER", "RECON",
                             "AP control account differs from AP sub-ledger by $1,284.55 in the legacy source",
                             {"gl_adjustment": {"bu": bu, "debit_account": GL_TEMPLATE[19][5], "credit_account": code,
                                                "amount_cents": 128455,
                                                "memo": "Finance JE: correct AP control to sub-ledger before cutover"}})
        out[bu] = {"table": table, "cols": cols}
    return out, map_rows


# ===================================================================================== outputs


def write_reference(paths: Paths, items, gl_map):
    paths.reference.mkdir(parents=True, exist_ok=True)
    with (paths.reference / "uom_map.csv").open("w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["legacy_code", "canonical_uom", "note"]); w.writerows(UOM_MAP_ROWS)
    with (paths.reference / "category_map.csv").open("w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["bu", "legacy_code", "category"])
        for bu in BUS:
            for cat, code in catalog.CATEGORY_CODE[bu].items():
                w.writerow([bu, code, cat])
    with (paths.reference / "gl_account_map.csv").open("w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["bu", "legacy_account", "ifs_account", "ifs_account_name", "control_role"]); w.writerows(gl_map)


def write_ground_truth(paths: Paths, reg: Registry):
    paths.ground_truth.mkdir(parents=True, exist_ok=True)
    summary: dict[str, int] = defaultdict(int)
    with (paths.ground_truth / "defect_manifest.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["domain", "bu", "row_num", "defect_code", "expected_action", "detail"])
        for d in sorted(reg.defects, key=lambda d: (d["domain"], d["bu"], reg.row_num[d["_id"]])):
            w.writerow([d["domain"], d["bu"], reg.row_num[d["_id"]], d["code"], d["action"], d["detail"]])
            summary[f"{d['domain']}|{d['bu']}|{d['code']}"] += 1
    with (paths.ground_truth / "entity_truth.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["domain", "bu", "source_key", "entity_id"])
        for t in reg.entity_truth:
            w.writerow([t["domain"], t["bu"], t["source_key"], t["entity_id"]])
    (paths.ground_truth / "expected_summary.json").write_text(json.dumps(dict(sorted(summary.items())), indent=2))


def write_fixes(paths: Paths, reg: Registry, rng):
    """Simulate business owners answering the issue log: ~50% closed by Mock 2, ~35% by Mock 3, ~15% never."""
    paths.remediation.mkdir(parents=True, exist_ok=True)
    rounds = {2: {"cell_fixes": [], "row_exclusions": [], "party_decisions": [], "gl_adjustments": []},
              3: {"cell_fixes": [], "row_exclusions": [], "party_decisions": [], "gl_adjustments": []}}
    ticket = 0

    def pick_round(p2=0.5, p3=0.35):
        x = rng.random()
        return 2 if x < p2 else 3 if x < p2 + p3 else None

    for d in sorted(reg.defects, key=lambda d: d["_id"]):
        fix = d["fix"]
        if not fix:
            continue
        if "gl_adjustment" in fix:
            rounds[3]["gl_adjustments"].append({**fix["gl_adjustment"], "ticket": "DQ-GL-001", "owner": OWNERS["gl_balance"]})
            continue
        rnd = pick_round()
        if rnd is None:
            continue
        ticket += 1
        base = {"domain": d["domain"], "bu": d["bu"], "row_num": reg.row_num[d["_id"]], "ticket": f"DQ-{ticket:04d}",
                "owner": OWNERS[d["domain"]], "defect_code": d["code"]}
        if fix.get("exclude"):
            rounds[rnd]["row_exclusions"].append({**base, "reason": fix["reason"]})
        else:
            rounds[rnd]["cell_fixes"].append({**base, "field": fix["field"], "new_value": fix["new_value"]})
    groups: dict[tuple, list] = defaultdict(list)
    for t in reg.entity_truth:
        if t["domain"] in ("customer", "vendor"):
            groups[(t["domain"], t["entity_id"])].append((t["bu"], t["source_key"]))
    for (dom, _eid), members in sorted(groups.items()):
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                rnd = pick_round(0.55, 0.45)
                if rnd:
                    ticket += 1
                    rounds[rnd]["party_decisions"].append({"entity": dom, "a": list(members[i]), "b": list(members[j]),
                                                           "decision": "MERGE", "ticket": f"DQ-{ticket:04d}",
                                                           "owner": OWNERS[dom]})
    for kind, dec, base in reg.decoys:                 # near-twins that are NOT the same legal entity -> KEEP_SEPARATE
        for a in groups.get((kind, dec), []):
            for b in groups.get((kind, base), []):
                rnd = pick_round(0.55, 0.45)
                if rnd:
                    ticket += 1
                    rounds[rnd]["party_decisions"].append({"entity": kind, "a": list(a), "b": list(b), "decision": "KEEP_SEPARATE",
                                                           "ticket": f"DQ-{ticket:04d}", "owner": OWNERS[kind]})
    for mock, payload in rounds.items():
        (paths.remediation / f"mock{mock}_fixes.json").write_text(json.dumps({"mock": mock, **payload}, indent=1))


def generate(paths: Paths | None = None, scale: float = 1.0, seed: int = 42, verbose: bool = True) -> dict:
    paths = paths or Paths()
    rng = random.Random(seed)
    reg = Registry()
    items = build_items(reg, rng, scale, paths)
    parties = {"customer": build_parties(reg, rng, "customer", scale), "vendor": build_parties(reg, rng, "vendor", scale)}
    bom = build_bom(reg, rng, scale, items)
    inventory = build_inventory(reg, rng, scale, items)
    orders = build_orders(reg, rng, scale, items, parties)
    ar = build_invoices(reg, rng, scale, parties, "ar")
    ap = build_invoices(reg, rng, scale, parties, "ap")
    gl, gl_map = build_gl(reg, rng, inventory, ar, ap, paths)

    counts: dict[str, int] = {}
    for bu in BUS:
        folder = paths.raw(bu)
        tables = [items[bu]["table"], bom[bu]["table"], parties["customer"][bu]["table"], parties["vendor"][bu]["table"],
                  inventory[bu]["table"], orders["po"][bu]["table"], orders["so"][bu]["table"], ar[bu]["table"],
                  ap[bu]["table"], gl[bu]["table"]]
        if parties["customer"][bu]["shipto"] is not None:
            tables.append(parties["customer"][bu]["shipto"])
        for t in tables:
            t.write(folder)
            counts[f"{bu}:{t.filename}"] = len(t.rows)
    write_reference(paths, items, gl_map)
    write_ground_truth(paths, reg)
    write_fixes(paths, reg, rng)
    if verbose:
        for k, v in counts.items():
            print(f"  {k:36s} {v:>6,} rows")
        print(f"  planted defects (ground truth): {len(reg.defects):,}")
    return counts


def main() -> None:
    ap_ = argparse.ArgumentParser(description=__doc__)
    ap_.add_argument("--scale", type=float, default=1.0, help="1.0 = ~5,000 items per BU")
    ap_.add_argument("--seed", type=int, default=42)
    ap_.add_argument("--root", type=Path, default=None, help="project root (default: repo root)")
    args = ap_.parse_args()
    generate(Paths(args.root) if args.root else Paths(), args.scale, args.seed)


if __name__ == "__main__":
    main()
