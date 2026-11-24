"""Target mock load: converts Silver tables into IFS Cloud migration load files (CSV)."""
from __future__ import annotations

import csv
from pathlib import Path

from .context import RunContext
from .mapping import IFS_COLUMNS, IFS_FILES
from .money import cents_str


def _write(folder: Path, fname: str, rows: list[dict]) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    cols = IFS_COLUMNS[fname]
    with (folder / fname).open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") if r.get(c) is not None else "" for c in cols])
    return len(rows)


def build_files(ctx: RunContext) -> dict[str, int]:
    q, folder = ctx.db.query, ctx.paths.ifs_load(ctx.mock)
    n: dict[str, int] = {}
    up = lambda r, m: {k.upper(): v for k, v in r.items() if k.upper() in m}  # noqa: E731
    n["item"] = _write(folder, IFS_FILES["item"], [
        {"PART_NO": r["part_no"], "DESCRIPTION": r["description"], "UNIT_MEAS": r["uom"], "PART_CATEGORY": r["category"],
         "SUBTYPE": r["subtype"], "MATERIAL_SPEC": r["material_spec"], "SIZE_IN": r["size_in"], "CLASS_RATING": r["class_rating"],
         "SCHEDULE": r["schedule"], "DRAWING_NO": r["drawing_no"], "REVISION": r["revision"], "WEIGHT": r["weight"],
         "STD_UNIT_COST": r["std_unit_cost"], "MAKE_BUY": r["make_buy"], "LEGACY_SOURCES": r["legacy_sources"]}
        for r in q("SELECT * FROM silver_item_golden ORDER BY part_no")])
    n["bom"] = _write(folder, IFS_FILES["bom"], [
        {"PARENT_PART_NO": r["parent_part_no"], "LINE_SEQ": r["line_seq"], "COMPONENT_PART_NO": r["component_part_no"],
         "QTY_PER_ASSEMBLY": r["qty"], "SCRAP_PCT": r["scrap_pct"], "SOURCE_BU": r["source_bu"]}
        for r in q("SELECT * FROM silver_bom_line ORDER BY parent_part_no, line_seq")])
    for kind, dom, idc in (("customer", "customer", "CUSTOMER_ID"), ("vendor", "vendor", "SUPPLIER_ID")):
        n[dom] = _write(folder, IFS_FILES[dom], [
            {idc: r["enterprise_id"], "NAME": r["name"], "COUNTRY": r["country"], "TAX_ID": r["tax_id"], "ADDRESS1": r["address1"],
             "ADDRESS2": r["address2"], "CITY": r["city"], "STATE": r["state"], "ZIP": r["zip"], "PAYMENT_TERMS": r["payment_terms"],
             "CONTACT": r["contact"], "PHONE": r["phone"], "LEGACY_SOURCES": r["legacy_sources"]}
            for r in q(f"SELECT * FROM silver_{kind}_golden ORDER BY enterprise_id")])
    n["customer_shipto"] = _write(folder, IFS_FILES["customer_shipto"], [
        {"CUSTOMER_ID": r["customer_id"], "ADDRESS_ID": r["address_id"], "ADDRESS_TYPE": r["address_type"], "NAME": r["name"],
         "ADDRESS1": r["address1"], "CITY": r["city"], "STATE": r["state"], "ZIP": r["zip"], "COUNTRY": r["country"],
         "SOURCE_BU": r["source_bu"]} for r in q("SELECT * FROM silver_customer_address ORDER BY customer_id, address_id")])
    n["inventory"] = _write(folder, IFS_FILES["inventory"], [
        {"PART_NO": r["part_no"], "SITE": r["site"], "LOCATION_NO": r["location_no"], "LOT_BATCH_NO": r["lot_batch_no"],
         "SERIAL_NO": r["serial_no"], "QTY_ONHAND": r["qty"], "UNIT_MEAS": r["uom"], "UNIT_COST": r["unit_cost"],
         "EXT_VALUE": cents_str(r["ext_value_cents"]), "SOURCE_BU": r["source_bu"]}
        for r in q("SELECT * FROM silver_inventory ORDER BY part_no, site, location_no, lot_batch_no, serial_no")])
    for kind, dom, pc in (("po", "open_po", "SUPPLIER_ID"), ("so", "open_so", "CUSTOMER_ID")):
        n[dom] = _write(folder, IFS_FILES[dom], [
            {"ORDER_NO": r["order_no"], "LINE_NO": r["line_no"], pc: r["party_id"], "PART_NO": r["part_no"], "QTY_OPEN": r["qty"],
             "UNIT_MEAS": r["uom"], "UNIT_PRICE": r["unit_price"], "EXT_VALUE": cents_str(r["ext_value_cents"]),
             "WANTED_DATE": r["wanted_date"], "SOURCE_BU": r["source_bu"]}
            for r in q(f"SELECT * FROM silver_open_{kind} ORDER BY order_no, CAST(line_no AS INTEGER)")])
    for kind, dom, pc in (("ar", "open_ar", "CUSTOMER_ID"), ("ap", "open_ap", "SUPPLIER_ID")):
        n[dom] = _write(folder, IFS_FILES[dom], [
            {"INVOICE_NO": r["invoice_no"], pc: r["party_id"], "INVOICE_DATE": r["invoice_date"], "DUE_DATE": r["due_date"],
             "OPEN_AMOUNT": cents_str(r["open_amount_cents"]), "SOURCE_BU": r["source_bu"]}
            for r in q(f"SELECT * FROM silver_open_{kind} ORDER BY invoice_no")])
    n["gl_balance"] = _write(folder, IFS_FILES["gl_balance"], [
        {"COMPANY": r["company"], "ACCOUNT": r["account"], "ACCOUNT_NAME": r["account_name"], "BALANCE": cents_str(r["balance_cents"]),
         "ENTRY_TYPE": r["entry_type"], "MEMO": r["memo"]} for r in q("SELECT * FROM silver_gl_balance ORDER BY company, account, entry_type")])
    return n
