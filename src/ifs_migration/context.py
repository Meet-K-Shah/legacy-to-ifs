"""Run context shared by all pipeline stages: DB handle, reference lookups, approved fixes, the row ledger
(every source row ends in exactly one disposition) and the frozen enterprise-ID registry."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import BUS, Paths
from .db import Db
from .mapping import DOMAIN_TABLE, FIELD_MAP, bronze_table, table_key
from .money import ext_cents, parse_decimal, to_cents
from .textnorm import clean_code

LEDGER_COLS = {"domain": "TEXT", "bu": "TEXT", "source_row": "BIGINT", "source_key": "TEXT", "disposition": "TEXT",
               "reason": "TEXT", "ent_key": "TEXT", "detail": "TEXT", "value_raw": "BIGINT", "value_adj": "BIGINT"}


def load_reference(paths: Paths):
    def rd(name):
        with (paths.reference / name).open(newline="") as fh:
            return list(csv.DictReader(fh))
    uom = {r["legacy_code"].upper(): r["canonical_uom"] for r in rd("uom_map.csv")}
    cat = {(r["bu"], r["legacy_code"].upper()): r["category"] for r in rd("category_map.csv")}
    gl = {(r["bu"], r["legacy_account"].strip().upper()): r for r in rd("gl_account_map.csv")}
    return uom, cat, gl


def value_cents(domain: str, bu: str, row: dict) -> int:
    """Monetary value of a source row in cents (0 when the inputs are unparseable). One rule, used everywhere."""
    fm = FIELD_MAP[(bu, DOMAIN_TABLE[domain])]
    g = lambda k: parse_decimal(row.get(fm[k]))  # noqa: E731
    if domain in ("inventory", "open_po", "open_so"):
        q, p = g("qty"), g("cost" if domain == "inventory" else "price")
        return ext_cents(q, p) if q is not None and p is not None else 0
    if domain in ("open_ar", "open_ap"):
        a = g("amount")
        return to_cents(a) if a is not None else 0
    if domain == "gl_balance":
        a = g("balance")
        return to_cents(a) if a is not None else 0
    return 0


# --------------------------------------------------------------------------- approved fixes (simulated owner answers)
@dataclass
class Fixes:
    cells: dict = field(default_factory=lambda: defaultdict(dict))        # (bu, tkey, row) -> {field: new}
    excl: dict = field(default_factory=dict)                               # (bu, tkey, row) -> fix dict
    decisions: list = field(default_factory=list)
    gl_adjustments: list = field(default_factory=list)
    applied: list = field(default_factory=list)                            # every fix with its mock round


def load_fixes(paths: Paths, mock: int) -> Fixes:
    fx = Fixes()
    for n in range(2, mock + 1):
        p = paths.remediation / f"mock{n}_fixes.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text())
        for c in data.get("cell_fixes", []):
            key = (c["bu"], table_key(c["bu"], c["domain"]), c["row_num"])
            fx.cells[key][c["field"]] = c["new_value"]
            fx.applied.append({**c, "mock": n, "kind": "CELL_FIX"})
        for e in data.get("row_exclusions", []):
            fx.excl[(e["bu"], table_key(e["bu"], e["domain"]), e["row_num"])] = e
            fx.applied.append({**e, "mock": n, "kind": "EXCLUSION"})
        for d in data.get("party_decisions", []):
            fx.decisions.append({**d, "mock": n})
            fx.applied.append({**d, "mock": n, "kind": "PARTY_DECISION"})
        for g in data.get("gl_adjustments", []):
            fx.gl_adjustments.append({**g, "mock": n})
            fx.applied.append({**g, "mock": n, "kind": "GL_ADJUSTMENT"})
    return fx


def read_bronze(db: Db, bu: str, tkey: str) -> list[dict]:
    t = bronze_table(bu, tkey)
    return db.query(f"SELECT * FROM {t} ORDER BY _row_num") if db.table_exists(t) else []


def apply_fixes(rows: list[dict], bu: str, tkey: str, fx: Fixes) -> list[dict]:
    """Return rows with approved cell fixes applied; adds _row, _raw (original dict) and _excl."""
    out = []
    for r in rows:
        key = (bu, tkey, r["_row_num"])
        raw = dict(r)
        adj = dict(r)
        adj.update(fx.cells.get(key, {}))
        adj["_row"] = r["_row_num"]
        adj["_raw"] = raw
        adj["_excl"] = fx.excl.get(key)
        out.append(adj)
    return out


# --------------------------------------------------------------------------- enterprise ID registry
class IdRegistry:
    """Frozen enterprise IDs: once issued they never change between mock loads. When two previously separate
    members merge into one cluster the lowest ID survives (the other is retained as a retired alias)."""

    def __init__(self, path: Path, reset: bool = False):
        self.path = path
        self.data = {"members": {}, "next": {}, "retired": {}}
        if path.exists() and not reset:
            self.data = json.loads(path.read_text())

    def assign(self, domain: str, clusters: list[list[str]]) -> list[int]:
        members = self.data["members"].setdefault(domain, {})
        nxt = self.data["next"].setdefault(domain, 1)
        retired = self.data["retired"].setdefault(domain, {})
        ids = [None] * len(clusters)
        order = sorted(range(len(clusters)), key=lambda i: min(clusters[i]))
        for i in order:
            existing = sorted({members[m] for m in clusters[i] if m in members})
            if existing:
                ids[i] = existing[0]
                for other in existing[1:]:
                    retired[str(other)] = existing[0]
            else:
                ids[i] = nxt
                nxt += 1
            for m in clusters[i]:
                members[m] = ids[i]
        self.data["next"][domain] = nxt
        return ids

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data))


@dataclass
class RunContext:
    paths: Paths
    db: Db
    mock: int
    fixes: Fixes
    uom_map: dict
    cat_map: dict
    gl_map: dict
    ids: IdRegistry
    started: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    ledger: list = field(default_factory=list)
    item_map: dict = field(default_factory=dict)      # (bu, code) -> {"status","ent"}
    party_map: dict = field(default_factory=dict)     # (kind, bu, code) -> {"status","ent"}
    review_pairs: list = field(default_factory=list)
    notes: list = field(default_factory=list)         # informational pipeline notes

    def rows(self, bu: str, tkey: str) -> list[dict]:
        return apply_fixes(read_bronze(self.db, bu, tkey), bu, tkey, self.fixes)

    def log(self, domain, bu, row, key, disposition, reason="", ent="", detail="", raw=None, adj=None):
        self.ledger.append({"domain": domain, "bu": bu, "source_row": row, "source_key": key, "disposition": disposition,
                            "reason": reason, "ent_key": ent, "detail": detail, "value_raw": raw or 0, "value_adj": adj or 0})

    def log_row(self, domain, bu, r, key, disposition, reason="", ent="", detail=""):
        raw = value_cents(domain, bu, r["_raw"]) if domain in ("inventory", "open_po", "open_so", "open_ar", "open_ap", "gl_balance") else 0
        adj = value_cents(domain, bu, r) if domain in ("inventory", "open_po", "open_so", "open_ar", "open_ap", "gl_balance") else 0
        self.log(domain, bu, r["_row"], key, disposition, reason, ent, detail, raw, adj)

    def excluded(self, domain, bu, r, key):
        e = r["_excl"]
        self.log_row(domain, bu, r, key, "EXCLUDED", "BUSINESS_DECISION", detail=f"{e['ticket']}: {e['reason']}")


def new_context(paths: Paths, db: Db, mock: int) -> RunContext:
    uom, cat, gl = load_reference(paths)
    return RunContext(paths, db, mock, load_fixes(paths, mock), uom, cat, gl,
                      IdRegistry(paths.data / "id_registry" / "enterprise_ids.json", reset=(mock == 1)))
