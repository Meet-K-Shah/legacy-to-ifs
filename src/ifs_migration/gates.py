"""Pre-load readiness gates (dbt-test / Great-Expectations style) executed against the IFS load FILES.

Any BLOCKER failure halts the cutover pipeline: load files must never contain null primary keys, unmapped UOMs,
negative on-hand inventory, orphaned references, circular BOMs, mis-extended values or an unbalanced trial balance.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from .mapping import IFS_FILES, IFS_MANDATORY, IFS_PK, IFS_PK_OPTIONAL
from .money import ext_cents, parse_decimal, to_cents


class CutoverBlocked(RuntimeError):
    def __init__(self, failures):
        self.failures = failures
        super().__init__("Readiness gate BLOCKER(s): " + "; ".join(f"{f['gate_id']} {f['file']} ({f['failing_rows']})" for f in failures))


def _read(folder: Path, fname: str) -> list[dict]:
    with (folder / fname).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _find_cycles(rows: list[dict]) -> int:
    """Iterative DFS over PARENT -> COMPONENT; returns the number of back-edges (cycles) found."""
    graph = defaultdict(list)
    for r in rows:
        graph[r["PARENT_PART_NO"]].append(r["COMPONENT_PART_NO"])
    color: dict[str, int] = {}
    back = 0
    for root in list(graph):
        if color.get(root):
            continue
        stack = [(root, iter(graph[root]))]
        color[root] = 1
        while stack:
            node, it = stack[-1]
            for nxt in it:
                c = color.get(nxt, 0)
                if c == 1:
                    back += 1
                elif c == 0:
                    color[nxt] = 1
                    stack.append((nxt, iter(graph.get(nxt, []))))
                    break
            else:
                color[node] = 2
                stack.pop()
    return back


def run_gates(folder: Path, canonical_uoms: set[str]) -> list[dict]:
    data = {f: _read(folder, f) for f in IFS_FILES.values()}
    res: list[dict] = []

    def add(gate, fname, desc, failing, detail=""):
        res.append({"gate_id": gate, "file": fname, "description": desc, "severity": "BLOCKER", "failing_rows": failing,
                    "status": "PASS" if failing == 0 else "FAIL", "detail": detail})

    for f, rows in data.items():
        pk = IFS_PK[f]
        opt = set(IFS_PK_OPTIONAL.get(f, []))
        add("G01_PK_NOT_NULL", f, "No null/blank primary-key columns", sum(1 for r in rows if any(not r[c].strip() for c in pk if c not in opt)))
        cnt = Counter(tuple(r[c] for c in pk) for r in rows)
        add("G02_PK_UNIQUE", f, "Primary key is unique", sum(v - 1 for v in cnt.values() if v > 1))
        mand = IFS_MANDATORY.get(f, [])
        add("G03_MANDATORY_POPULATED", f, "Mandatory IFS fields populated", sum(1 for r in rows if any(not r[c].strip() for c in mand)))
        if "UNIT_MEAS" in rows[0] if rows else False:
            add("G04_UOM_CANONICAL", f, "All UNIT_MEAS values are canonical (no unmapped UOMs)", sum(1 for r in rows if r["UNIT_MEAS"] not in canonical_uoms))
    inv = data["IFS_InventoryStock.csv"]
    add("G05_NO_NEGATIVE_ONHAND", "IFS_InventoryStock.csv", "No negative on-hand quantity",
        sum(1 for r in inv if (parse_decimal(r["QTY_ONHAND"]) or Decimal(0)) < 0))
    parts = {r["PART_NO"] for r in data["IFS_PartCatalog.csv"]}
    custs = {r["CUSTOMER_ID"] for r in data["IFS_CustomerInfo.csv"]}
    supps = {r["SUPPLIER_ID"] for r in data["IFS_SupplierInfo.csv"]}
    ri = [("IFS_ProductStructure.csv", "PARENT_PART_NO", parts), ("IFS_ProductStructure.csv", "COMPONENT_PART_NO", parts),
          ("IFS_InventoryStock.csv", "PART_NO", parts), ("IFS_OpenPurchaseOrders.csv", "PART_NO", parts),
          ("IFS_OpenCustomerOrders.csv", "PART_NO", parts), ("IFS_OpenPurchaseOrders.csv", "SUPPLIER_ID", supps),
          ("IFS_OpenCustomerOrders.csv", "CUSTOMER_ID", custs), ("IFS_OpenCustomerInvoices.csv", "CUSTOMER_ID", custs),
          ("IFS_OpenSupplierInvoices.csv", "SUPPLIER_ID", supps), ("IFS_CustomerAddress.csv", "CUSTOMER_ID", custs)]
    for f, col, ref in ri:
        add("G06_REFERENTIAL_INTEGRITY", f, f"{col} exists in its master file", sum(1 for r in data[f] if r[col] not in ref))
    add("G07_BOM_ACYCLIC", "IFS_ProductStructure.csv", "No circular or self-referencing structures", _find_cycles(data["IFS_ProductStructure.csv"]))
    for f, qc, pc in (("IFS_InventoryStock.csv", "QTY_ONHAND", "UNIT_COST"), ("IFS_OpenPurchaseOrders.csv", "QTY_OPEN", "UNIT_PRICE"),
                      ("IFS_OpenCustomerOrders.csv", "QTY_OPEN", "UNIT_PRICE")):
        bad = sum(1 for r in data[f] if ext_cents(parse_decimal(r[qc]), parse_decimal(r[pc])) != to_cents(parse_decimal(r["EXT_VALUE"])))
        add("G08_EXTENDED_VALUE", f, "EXT_VALUE = round_half_up(qty x price, 2)", bad)
    tb: dict[str, int] = defaultdict(int)
    for r in data["IFS_GLOpeningBalances.csv"]:
        tb[r["COMPANY"]] += to_cents(parse_decimal(r["BALANCE"]))
    add("G09_TRIAL_BALANCE_ZERO", "IFS_GLOpeningBalances.csv", "Trial balance sums to 0.00 per company",
        sum(1 for v in tb.values() if v != 0), detail=", ".join(f"{k}={v / 100:.2f}" for k, v in sorted(tb.items())))
    return res


def enforce(results: list[dict]) -> None:
    fails = [r for r in results if r["status"] == "FAIL" and r["severity"] == "BLOCKER"]
    if fails:
        raise CutoverBlocked(fails)
