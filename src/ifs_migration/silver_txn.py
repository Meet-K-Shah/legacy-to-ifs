"""Silver: transactional domains (inventory, open PO/SO, open AR/AP, GL opening balances).
Every source row receives exactly one disposition in the ledger; money is carried as integer cents."""
from __future__ import annotations

from decimal import Decimal

from .config import BUS
from .context import RunContext, value_cents
from .mapping import FIELD_MAP
from .money import ext_cents, parse_decimal, to_cents
from .textnorm import clean_code, clean_text, parse_date


def _item(ctx, bu, code):
    m = ctx.item_map.get((bu, code))
    if m is None:
        return None, "ORPHAN_ITEM"
    return (m["ent"], None) if m["status"] == "LOADED" else (None, "ITEM_QUARANTINED")


def _party(ctx, kind, bu, code, orphan_suffix):
    m = ctx.party_map.get((kind, bu, code))
    if m is None:
        return None, orphan_suffix
    return (m["ent"], None) if m["status"] == "LOADED" else (None, "PARTY_QUARANTINED")


def _qty(v):
    d = parse_decimal(v)
    return d


def inventory(ctx: RunContext) -> None:
    out = []
    loaded_keys: set[tuple] = set()      # enterprise stock keys already loaded (guards consolidation collisions)
    for bu in BUS:
        fm = FIELD_MAP[(bu, "inventory")]
        seen: set[tuple] = set()
        for r in ctx.rows(bu, "inventory"):
            code = clean_code(r[fm["item"]])
            wh, lot, ser = clean_code(r[fm["wh"]]), clean_code(r[fm["lot"]]), clean_code(r[fm["serial"]])
            key = f"{code}|{wh}|{lot}|{ser}"
            if r["_excl"]:
                ctx.excluded("inventory", bu, r, key)
                continue
            qty, cost = _qty(r[fm["qty"]]), parse_decimal(r[fm["cost"]])
            uom = ctx.uom_map.get(clean_code(r[fm["uom"]]))
            ent, why = _item(ctx, bu, code)
            reason = None
            if key in seen:
                reason = "INV_DUPLICATE_KEY"
            elif why == "ORPHAN_ITEM":
                reason = "INV_ORPHAN_ITEM"
            elif uom is None:
                reason = "INV_INVALID_UOM"
            elif cost is None:
                reason = "INV_MISSING_COST"
            elif qty is None or qty < 0:
                reason = "INV_NEGATIVE_QTY"
            elif why:
                reason = "INV_ITEM_QUARANTINED"
            elif (ent, bu, wh, lot, ser) in loaded_keys:
                reason = "INV_DUPLICATE_AFTER_CONSOLIDATION"     # two legacy codes of one part share a stock key
            seen.add(key)
            if reason:
                ctx.log_row("inventory", bu, r, key, "QUARANTINED", reason, detail=f"qty={r[fm['qty']]} cost={r[fm['cost']]!r}")
                continue
            loaded_keys.add((ent, bu, wh, lot, ser))
            val = ext_cents(qty, cost)
            ctx.log_row("inventory", bu, r, key, "LOADED", "", ent)
            out.append({"part_no": ent, "site": f"SITE-{bu}", "location_no": wh, "lot_batch_no": lot, "serial_no": ser,
                        "qty": format(qty.normalize(), "f") if qty != 0 else "0", "uom": uom, "unit_cost": f"{cost:.4f}",
                        "ext_value_cents": val, "source_bu": bu, "source_row": r["_row"]})
    ctx.db.write_table("silver_inventory", {"part_no": "TEXT", "site": "TEXT", "location_no": "TEXT", "lot_batch_no": "TEXT",
                                            "serial_no": "TEXT", "qty": "TEXT", "uom": "TEXT", "unit_cost": "TEXT",
                                            "ext_value_cents": "BIGINT", "source_bu": "TEXT", "source_row": "BIGINT"}, out)


def orders(ctx: RunContext, kind: str) -> None:
    """kind: 'po' (vendor) or 'so' (customer)."""
    dom = f"open_{kind}"
    P = kind.upper()
    pkind, orphan = ("vendor", "ORPHAN_VENDOR") if kind == "po" else ("customer", "ORPHAN_CUSTOMER")
    out = []
    for bu in BUS:
        fm = FIELD_MAP[(bu, kind)]
        seen: set[tuple] = set()
        for r in ctx.rows(bu, kind):
            order, line = clean_code(r[fm["order"]]), clean_code(r[fm["line"]])
            key = f"{order}/{line}"
            if r["_excl"]:
                ctx.excluded(dom, bu, r, key)
                continue
            item, party = clean_code(r[fm["item"]]), clean_code(r[fm["party"]])
            qty, price = _qty(r[fm["qty"]]), parse_decimal(r[fm["price"]])
            uom, dt = ctx.uom_map.get(clean_code(r[fm["uom"]])), parse_date(r[fm["date"]])
            ient, iwhy = _item(ctx, bu, item)
            pent, pwhy = _party(ctx, pkind, bu, party, orphan)
            reason = None
            if key in seen:
                reason = f"{P}_DUPLICATE_KEY"
            elif iwhy == "ORPHAN_ITEM":
                reason = f"{P}_ORPHAN_ITEM"
            elif pwhy == orphan:
                reason = f"{P}_{orphan}"
            elif uom is None:
                reason = f"{P}_INVALID_UOM"
            elif qty is None or qty <= 0:
                reason = f"{P}_INVALID_QTY"
            elif price is None:
                reason = f"{P}_INVALID_PRICE"
            elif dt is None:
                reason = f"{P}_INVALID_DATE"
            elif iwhy:
                reason = f"{P}_ITEM_QUARANTINED"
            elif pwhy:
                reason = f"{P}_PARTY_QUARANTINED"
            seen.add(key)
            if reason:
                ctx.log_row(dom, bu, r, key, "QUARANTINED", reason, detail=f"item={item} party={party}")
                continue
            ctx.log_row(dom, bu, r, key, "LOADED", "", f"{bu}-{order}/{line}")
            out.append({"order_no": f"{bu}-{order}", "line_no": line, "party_id": pent, "part_no": ient,
                        "qty": format(qty.normalize(), "f"), "uom": uom, "unit_price": f"{price:.4f}",
                        "ext_value_cents": ext_cents(qty, price), "wanted_date": dt, "source_bu": bu, "source_row": r["_row"]})
    ctx.db.write_table(f"silver_open_{kind}", {"order_no": "TEXT", "line_no": "TEXT", "party_id": "TEXT", "part_no": "TEXT",
                                               "qty": "TEXT", "uom": "TEXT", "unit_price": "TEXT", "ext_value_cents": "BIGINT",
                                               "wanted_date": "TEXT", "source_bu": "TEXT", "source_row": "BIGINT"}, out)


def invoices(ctx: RunContext, kind: str) -> None:
    """kind: 'ar' (customers) or 'ap' (vendors)."""
    dom = f"open_{kind}"
    P = kind.upper()
    pkind, orphan = ("customer", "ORPHAN_CUSTOMER") if kind == "ar" else ("vendor", "ORPHAN_VENDOR")
    out = []
    for bu in BUS:
        fm = FIELD_MAP[(bu, kind)]
        seen: set[str] = set()
        for r in ctx.rows(bu, kind):
            inv = clean_code(r[fm["inv"]])
            if r["_excl"]:
                ctx.excluded(dom, bu, r, inv)
                continue
            party = clean_code(r[fm["party"]])
            pent, pwhy = _party(ctx, pkind, bu, party, orphan)
            amt, due, idate = parse_decimal(r[fm["amount"]]), parse_date(r[fm["due_date"]]), parse_date(r[fm["inv_date"]])
            reason = None
            if inv in seen:
                reason = f"{P}_DUPLICATE_KEY"
            elif pwhy == orphan:
                reason = f"{P}_{orphan}"
            elif amt is None:
                reason = f"{P}_INVALID_AMOUNT"
            elif due is None or idate is None:
                reason = f"{P}_INVALID_DATE"
            elif pwhy:
                reason = f"{P}_PARTY_QUARANTINED"
            seen.add(inv)
            if reason:
                ctx.log_row(dom, bu, r, inv, "QUARANTINED", reason, detail=f"party={party}")
                continue
            ctx.log_row(dom, bu, r, inv, "LOADED", "", f"{bu}-{inv}")
            out.append({"invoice_no": f"{bu}-{inv}", "party_id": pent, "invoice_date": idate, "due_date": due,
                        "open_amount_cents": to_cents(amt), "source_bu": bu, "source_row": r["_row"]})
    ctx.db.write_table(f"silver_open_{kind}", {"invoice_no": "TEXT", "party_id": "TEXT", "invoice_date": "TEXT", "due_date": "TEXT",
                                               "open_amount_cents": "BIGINT", "source_bu": "TEXT", "source_row": "BIGINT"}, out)


def gl(ctx: RunContext) -> None:
    out = []
    for bu in BUS:
        fm = FIELD_MAP[(bu, "gl")]
        for r in ctx.rows(bu, "gl"):
            acct = clean_code(r[fm["acct"]])
            if r["_excl"]:
                ctx.excluded("gl_balance", bu, r, acct)
                continue
            m = ctx.gl_map.get((bu, acct))
            bal = parse_decimal(r[fm["balance"]])
            if m is None:
                ctx.log_row("gl_balance", bu, r, acct, "QUARANTINED", "GL_UNMAPPED_ACCOUNT", detail=clean_text(r[fm["desc"]]))
                continue
            if bal is None:
                ctx.log_row("gl_balance", bu, r, acct, "QUARANTINED", "GL_UNMAPPED_ACCOUNT", detail="balance not numeric")
                continue
            ctx.log_row("gl_balance", bu, r, acct, "LOADED", "", f"{bu}/{m['ifs_account']}")
            out.append({"company": bu, "account": m["ifs_account"], "account_name": m["ifs_account_name"], "balance_cents": to_cents(bal),
                        "entry_type": "OPENING", "memo": "", "control_role": m["control_role"], "source_row": r["_row"]})
    for adj in ctx.fixes.gl_adjustments:       # approved finance journals (not source rows)
        bu = adj["bu"]
        dr = ctx.gl_map[(bu, adj["debit_account"].strip().upper())]
        cr = ctx.gl_map[(bu, adj["credit_account"].strip().upper())]
        for m, sign in ((dr, 1), (cr, -1)):
            out.append({"company": bu, "account": m["ifs_account"], "account_name": m["ifs_account_name"],
                        "balance_cents": sign * adj["amount_cents"], "entry_type": "ADJUSTMENT", "memo": f"{adj['ticket']}: {adj['memo']}",
                        "control_role": m["control_role"], "source_row": None})
    ctx.db.write_table("silver_gl_balance", {"company": "TEXT", "account": "TEXT", "account_name": "TEXT", "balance_cents": "BIGINT",
                                             "entry_type": "TEXT", "memo": "TEXT", "control_role": "TEXT", "source_row": "BIGINT"}, out)
