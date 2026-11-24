"""Source-to-target mapping (STTM) as code: single source of truth for field mappings, mandatory fields,
profiling specs and the IFS load-file layouts. `docgen.py` renders docs/source_to_target_mapping.md from this
module, so the documentation can never drift from the implementation.

NOTE: IFS Cloud field names below are illustrative placeholders aligned to the project brief (PART_NO,
UNIT_MEAS, CUSTOMER_ID, SUPPLIER_ID ...). Confirm them against the IFS Cloud migration templates issued by the
implementation partner before any real use.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- source files (per BU)
SOURCE_FILES = {
    ("BU1", "item"): "InvMaster.csv", ("BU2", "item"): "item_mst.csv",
    ("BU1", "bom"): "BomStructure.csv", ("BU2", "bom"): "bom_mst.csv",
    ("BU1", "customer"): "ArCustomer.csv", ("BU2", "customer"): "custaddr_mst.csv",
    ("BU1", "shipto"): "ArShipToAddress.csv",
    ("BU1", "vendor"): "ApSupplier.csv", ("BU2", "vendor"): "vendaddr_mst.csv",
    ("BU1", "inventory"): "InvWarehouse.csv", ("BU2", "inventory"): "itemwhse_mst.csv",
    ("BU1", "po"): "PorMasterDetail.csv", ("BU2", "po"): "poitem_mst.csv",
    ("BU1", "so"): "SorDetail.csv", ("BU2", "so"): "coitem_mst.csv",
    ("BU1", "ar"): "ArInvoice.csv", ("BU2", "ar"): "artran_mst.csv",
    ("BU1", "ap"): "ApInvoice.csv", ("BU2", "ap"): "aptrx_mst.csv",
    ("BU1", "gl"): "GenMaster.csv", ("BU2", "gl"): "chart_mst.csv",
}

# logical domain (used by fixes, ledger, recon) -> source table key
DOMAIN_TABLE = {
    "item": "item", "bom": "bom", "customer": "customer", "vendor": "vendor", "inventory": "inventory",
    "open_po": "po", "open_so": "so", "open_ar": "ar", "open_ap": "ap", "gl_balance": "gl",
}
DOMAINS = ["item", "bom", "customer", "customer_shipto", "vendor", "inventory", "open_po", "open_so", "open_ar",
           "open_ap", "gl_balance"]
DOMAIN_LABEL = {
    "item": "Item / Part Master", "bom": "Bill of Materials", "customer": "Customer Master (bill-to)",
    "customer_shipto": "Customer Ship-To Addresses", "vendor": "Vendor Master", "inventory": "Open Inventory",
    "open_po": "Open Purchase Orders", "open_so": "Open Sales Orders", "open_ar": "Open AR Invoices",
    "open_ap": "Open AP Invoices", "gl_balance": "GL Opening Balances (TB)",
}
VALUE_DOMAINS = ["inventory", "open_po", "open_so", "open_ar", "open_ap", "gl_balance"]


def table_key(bu: str, domain: str) -> str:
    """Which bronze source table holds rows of a logical domain."""
    if domain == "customer_shipto":
        return "shipto" if bu == "BU1" else "customer"
    return DOMAIN_TABLE[domain]


def bronze_table(bu: str, key: str) -> str:
    return f"bronze_{bu.lower()}_{key}"


# --------------------------------------------------------------------------- canonical -> legacy column
FIELD_MAP: dict[tuple[str, str], dict[str, str | None]] = {
    ("BU1", "item"): {"code": "StockCode", "desc": "Description", "long_desc": "LongDesc", "uom": "StockUom",
                      "cat": "ProductClass", "weight": "Mass", "drawing": "DrawingNumber", "rev": "Revision",
                      "cost": "UnitCost", "make_buy": "PartCategory"},
    ("BU2", "item"): {"code": "item", "desc": "description", "long_desc": None, "uom": "u_m", "cat": "family_code",
                      "weight": "unit_weight", "drawing": "drawing_nbr", "rev": "revision", "cost": "unit_cost",
                      "make_buy": "matl_type"},
    ("BU1", "bom"): {"parent": "ParentPart", "comp": "Component", "seq": "SequenceNum", "qty": "QtyPer", "scrap": "ScrapPct"},
    ("BU2", "bom"): {"parent": "parent_item", "comp": "comp_item", "seq": "oper_num", "qty": "qty_per", "scrap": "scrap_factor"},
    ("BU1", "customer"): {"code": "Customer", "name": "Name", "contact": "Contact", "phone": "Telephone", "addr1": "Addr1",
                          "addr2": "Addr2", "city": "City", "state": "State", "zip": "PostalCode", "country": "Country",
                          "tax": "TaxNumber", "terms": "TermsCode", "last_activity": "LastActivityDate", "seq": None},
    ("BU2", "customer"): {"code": "cust_num", "name": "name", "contact": "contact", "phone": "phone", "addr1": "addr_1",
                          "addr2": "addr_2", "city": "city", "state": "state", "zip": "zip", "country": "country",
                          "tax": "tax_reg_num", "terms": "terms_code", "last_activity": "last_activity", "seq": "cust_seq"},
    ("BU1", "shipto"): {"code": "Customer", "ship_code": "ShipToCode", "name": "ShipName", "addr1": "Addr1", "city": "City",
                        "state": "State", "zip": "PostalCode", "country": "Country"},
    ("BU1", "vendor"): {"code": "Supplier", "name": "SupplierName", "contact": "Contact", "phone": "Telephone",
                        "addr1": "Addr1", "addr2": "Addr2", "city": "City", "state": "State", "zip": "PostalCode",
                        "country": "Country", "tax": "TaxNumber", "terms": "TermsCode", "last_activity": "LastActivityDate"},
    ("BU2", "vendor"): {"code": "vend_num", "name": "name", "contact": "contact", "phone": "phone", "addr1": "addr_1",
                        "addr2": "addr_2", "city": "city", "state": "state", "zip": "zip", "country": "country",
                        "tax": "tax_reg_num", "terms": "terms_code", "last_activity": "last_activity"},
    ("BU1", "inventory"): {"item": "StockCode", "wh": "Warehouse", "lot": "LotNumber", "serial": "SerialNumber",
                           "qty": "QtyOnHand", "uom": "StockUom", "cost": "UnitCost"},
    ("BU2", "inventory"): {"item": "item", "wh": "whse", "lot": "lot", "serial": "serial_num", "qty": "qty_on_hand",
                           "uom": "u_m", "cost": "unit_cost"},
    ("BU1", "po"): {"order": "PurchaseOrder", "line": "Line", "party": "Supplier", "item": "StockCode",
                    "qty": "QtyOutstanding", "uom": "OrderUom", "price": "UnitPrice", "date": "DueDate"},
    ("BU2", "po"): {"order": "po_num", "line": "po_line", "party": "vend_num", "item": "item", "qty": "qty_open",
                    "uom": "u_m", "price": "unit_cost", "date": "due_date"},
    ("BU1", "so"): {"order": "SalesOrder", "line": "Line", "party": "Customer", "item": "StockCode",
                    "qty": "QtyOutstanding", "uom": "OrderUom", "price": "UnitPrice", "date": "ShipDate"},
    ("BU2", "so"): {"order": "co_num", "line": "co_line", "party": "cust_num", "item": "item", "qty": "qty_open",
                    "uom": "u_m", "price": "price", "date": "due_date"},
    ("BU1", "ar"): {"inv": "Invoice", "party": "Customer", "inv_date": "InvoiceDate", "due_date": "DueDate", "amount": "InvoiceBalance"},
    ("BU2", "ar"): {"inv": "inv_num", "party": "cust_num", "inv_date": "inv_date", "due_date": "due_date", "amount": "balance"},
    ("BU1", "ap"): {"inv": "Invoice", "party": "Supplier", "inv_date": "InvoiceDate", "due_date": "DueDate", "amount": "InvoiceBalance"},
    ("BU2", "ap"): {"inv": "voucher", "party": "vend_num", "inv_date": "inv_date", "due_date": "due_date", "amount": "balance"},
    ("BU1", "gl"): {"acct": "GlCode", "desc": "Description", "type": "AccountType", "balance": "Balance"},
    ("BU2", "gl"): {"acct": "acct", "desc": "acct_desc", "type": "acct_type", "balance": "balance"},
}

# mandatory canonical fields per source table (used by profiling completeness)
MANDATORY = {
    "item": ["code", "desc", "uom", "cat"],
    "bom": ["parent", "comp", "qty"],
    "customer": ["code", "name", "country"], "vendor": ["code", "name", "country"],
    "shipto": ["code", "ship_code", "addr1", "city"],
    "inventory": ["item", "wh", "qty", "uom", "cost"],
    "po": ["order", "line", "party", "item", "qty", "uom", "price", "date"],
    "so": ["order", "line", "party", "item", "qty", "uom", "price", "date"],
    "ar": ["inv", "party", "due_date", "amount"], "ap": ["inv", "party", "due_date", "amount"],
    "gl": ["acct", "balance"],
}
RECOMMENDED = {"customer": ["addr1", "city", "state", "zip", "tax"], "vendor": ["addr1", "city", "state", "zip", "tax"],
               "item": ["weight", "cost"]}

# referential-integrity checks: (child table, child canonical col, parent table, parent canonical col, label)
FK_CHECKS = [
    ("bom", "parent", "item", "code", "BOM parent not in item master"),
    ("bom", "comp", "item", "code", "BOM component not in item master"),
    ("inventory", "item", "item", "code", "Inventory item not in item master"),
    ("po", "item", "item", "code", "PO line item not in item master"),
    ("so", "item", "item", "code", "SO line item not in item master"),
    ("po", "party", "vendor", "code", "PO vendor not in vendor master"),
    ("so", "party", "customer", "code", "SO customer not in customer master"),
    ("ar", "party", "customer", "code", "AR customer not in customer master"),
    ("ap", "party", "vendor", "code", "AP vendor not in vendor master"),
]
UOM_CHECKS = [("item", "uom"), ("inventory", "uom"), ("po", "uom"), ("so", "uom")]

# --------------------------------------------------------------------------- IFS load files
IFS_FILES = {
    "item": "IFS_PartCatalog.csv", "bom": "IFS_ProductStructure.csv", "customer": "IFS_CustomerInfo.csv",
    "customer_shipto": "IFS_CustomerAddress.csv", "vendor": "IFS_SupplierInfo.csv", "inventory": "IFS_InventoryStock.csv",
    "open_po": "IFS_OpenPurchaseOrders.csv", "open_so": "IFS_OpenCustomerOrders.csv",
    "open_ar": "IFS_OpenCustomerInvoices.csv", "open_ap": "IFS_OpenSupplierInvoices.csv",
    "gl_balance": "IFS_GLOpeningBalances.csv",
}
IFS_COLUMNS = {
    "IFS_PartCatalog.csv": ["PART_NO", "DESCRIPTION", "UNIT_MEAS", "PART_CATEGORY", "SUBTYPE", "MATERIAL_SPEC", "SIZE_IN",
                            "CLASS_RATING", "SCHEDULE", "DRAWING_NO", "REVISION", "WEIGHT", "STD_UNIT_COST", "MAKE_BUY",
                            "LEGACY_SOURCES"],
    "IFS_ProductStructure.csv": ["PARENT_PART_NO", "LINE_SEQ", "COMPONENT_PART_NO", "QTY_PER_ASSEMBLY", "SCRAP_PCT", "SOURCE_BU"],
    "IFS_CustomerInfo.csv": ["CUSTOMER_ID", "NAME", "COUNTRY", "TAX_ID", "ADDRESS1", "ADDRESS2", "CITY", "STATE", "ZIP",
                             "PAYMENT_TERMS", "CONTACT", "PHONE", "LEGACY_SOURCES"],
    "IFS_CustomerAddress.csv": ["CUSTOMER_ID", "ADDRESS_ID", "ADDRESS_TYPE", "NAME", "ADDRESS1", "CITY", "STATE", "ZIP",
                                "COUNTRY", "SOURCE_BU"],
    "IFS_SupplierInfo.csv": ["SUPPLIER_ID", "NAME", "COUNTRY", "TAX_ID", "ADDRESS1", "ADDRESS2", "CITY", "STATE", "ZIP",
                             "PAYMENT_TERMS", "CONTACT", "PHONE", "LEGACY_SOURCES"],
    "IFS_InventoryStock.csv": ["PART_NO", "SITE", "LOCATION_NO", "LOT_BATCH_NO", "SERIAL_NO", "QTY_ONHAND", "UNIT_MEAS",
                               "UNIT_COST", "EXT_VALUE", "SOURCE_BU"],
    "IFS_OpenPurchaseOrders.csv": ["ORDER_NO", "LINE_NO", "SUPPLIER_ID", "PART_NO", "QTY_OPEN", "UNIT_MEAS", "UNIT_PRICE",
                                   "EXT_VALUE", "WANTED_DATE", "SOURCE_BU"],
    "IFS_OpenCustomerOrders.csv": ["ORDER_NO", "LINE_NO", "CUSTOMER_ID", "PART_NO", "QTY_OPEN", "UNIT_MEAS", "UNIT_PRICE",
                                   "EXT_VALUE", "WANTED_DATE", "SOURCE_BU"],
    "IFS_OpenCustomerInvoices.csv": ["INVOICE_NO", "CUSTOMER_ID", "INVOICE_DATE", "DUE_DATE", "OPEN_AMOUNT", "SOURCE_BU"],
    "IFS_OpenSupplierInvoices.csv": ["INVOICE_NO", "SUPPLIER_ID", "INVOICE_DATE", "DUE_DATE", "OPEN_AMOUNT", "SOURCE_BU"],
    "IFS_GLOpeningBalances.csv": ["COMPANY", "ACCOUNT", "ACCOUNT_NAME", "BALANCE", "ENTRY_TYPE", "MEMO"],
}
IFS_PK = {
    "IFS_PartCatalog.csv": ["PART_NO"], "IFS_ProductStructure.csv": ["PARENT_PART_NO", "LINE_SEQ"],
    "IFS_CustomerInfo.csv": ["CUSTOMER_ID"], "IFS_CustomerAddress.csv": ["CUSTOMER_ID", "ADDRESS_ID"],
    "IFS_SupplierInfo.csv": ["SUPPLIER_ID"],
    "IFS_InventoryStock.csv": ["PART_NO", "SITE", "LOCATION_NO", "LOT_BATCH_NO", "SERIAL_NO"],
    "IFS_OpenPurchaseOrders.csv": ["ORDER_NO", "LINE_NO"], "IFS_OpenCustomerOrders.csv": ["ORDER_NO", "LINE_NO"],
    "IFS_OpenCustomerInvoices.csv": ["INVOICE_NO"], "IFS_OpenSupplierInvoices.csv": ["INVOICE_NO"],
    "IFS_GLOpeningBalances.csv": ["COMPANY", "ACCOUNT", "ENTRY_TYPE", "MEMO"],
}
# columns that may legitimately be blank in the PK (lot/serial are optional stock-key parts, memo only on adjustments)
IFS_PK_OPTIONAL = {"IFS_InventoryStock.csv": ["LOT_BATCH_NO", "SERIAL_NO"], "IFS_GLOpeningBalances.csv": ["MEMO"]}
IFS_MANDATORY = {
    "IFS_PartCatalog.csv": ["PART_NO", "DESCRIPTION", "UNIT_MEAS", "PART_CATEGORY"],
    "IFS_CustomerInfo.csv": ["CUSTOMER_ID", "NAME", "COUNTRY"], "IFS_SupplierInfo.csv": ["SUPPLIER_ID", "NAME", "COUNTRY"],
    "IFS_ProductStructure.csv": ["PARENT_PART_NO", "COMPONENT_PART_NO", "QTY_PER_ASSEMBLY"],
    "IFS_InventoryStock.csv": ["PART_NO", "SITE", "QTY_ONHAND", "UNIT_MEAS", "UNIT_COST"],
    "IFS_OpenPurchaseOrders.csv": ["ORDER_NO", "LINE_NO", "SUPPLIER_ID", "PART_NO", "QTY_OPEN", "WANTED_DATE"],
    "IFS_OpenCustomerOrders.csv": ["ORDER_NO", "LINE_NO", "CUSTOMER_ID", "PART_NO", "QTY_OPEN", "WANTED_DATE"],
    "IFS_OpenCustomerInvoices.csv": ["INVOICE_NO", "CUSTOMER_ID", "DUE_DATE", "OPEN_AMOUNT"],
    "IFS_OpenSupplierInvoices.csv": ["INVOICE_NO", "SUPPLIER_ID", "DUE_DATE", "OPEN_AMOUNT"],
    "IFS_GLOpeningBalances.csv": ["COMPANY", "ACCOUNT", "BALANCE"],
}

# --------------------------------------------------------------------------- STTM rows (rendered to markdown)
# (domain, ifs_file, ifs_field, bu1_source, bu2_source, rule, mandatory)
STTM: list[tuple[str, str, str, str, str, str, bool]] = [
    ("item", "IFS_PartCatalog.csv", "PART_NO", "InvMaster.StockCode", "item_mst.item",
     "Enterprise Golden ID `TT-FAB-nnnnnn` assigned per attribute-identity cluster; legacy codes kept in silver_item_xref", True),
    ("item", "IFS_PartCatalog.csv", "DESCRIPTION", "InvMaster.Description", "item_mst.description",
     "Regex-parsed into attributes, rebuilt as enterprise standard description (identical regardless of source style)", True),
    ("item", "IFS_PartCatalog.csv", "UNIT_MEAS", "InvMaster.StockUom", "item_mst.u_m",
     "Canonical lookup `reference/uom_map.csv` (EA/EACH/PCS/PC -> EA ...); unmapped -> quarantine ITEM_INVALID_UOM", True),
    ("item", "IFS_PartCatalog.csv", "PART_CATEGORY", "InvMaster.ProductClass", "item_mst.family_code",
     "Lookup `reference/category_map.csv` (FLG / FLANGE -> FLANGE ...); unmapped -> quarantine", True),
    ("item", "IFS_PartCatalog.csv", "MATERIAL_SPEC / SIZE_IN / CLASS_RATING / SCHEDULE", "parsed from Description",
     "parsed from description", "Extracted attributes (ASTM/ASME spec, size, pressure class, schedule); duplicates detected on these, never on raw text", False),
    ("item", "IFS_PartCatalog.csv", "STD_UNIT_COST", "InvMaster.UnitCost", "item_mst.unit_cost", "Survivor record's cost (Decimal, 4 dp)", False),
    ("item", "IFS_PartCatalog.csv", "LEGACY_SOURCES", "StockCode", "item", "`BU1:<code>|BU2:<code>` for lineage", False),
    ("bom", "IFS_ProductStructure.csv", "PARENT_PART_NO / COMPONENT_PART_NO", "BomStructure.ParentPart / Component",
     "bom_mst.parent_item / comp_item", "Mapped through silver_item_xref; parents and components must be LOADED parts", True),
    ("bom", "IFS_ProductStructure.csv", "QTY_PER_ASSEMBLY", "BomStructure.QtyPer", "bom_mst.qty_per", "Decimal > 0, else quarantine", True),
    ("bom", "IFS_ProductStructure.csv", "LINE_SEQ", "SequenceNum", "oper_num", "Renumbered 10,20,30 per enterprise parent", True),
    ("customer", "IFS_CustomerInfo.csv", "CUSTOMER_ID", "ArCustomer.Customer", "custaddr_mst.cust_num (seq 0)",
     "Golden ID `ENT-CUST-nnnn` from fuzzy + tax-ID entity resolution", True),
    ("customer", "IFS_CustomerInfo.csv", "NAME", "ArCustomer.Name", "custaddr_mst.name", "Survivor's name, whitespace-cleaned", True),
    ("customer", "IFS_CustomerInfo.csv", "COUNTRY", "ArCustomer.Country", "custaddr_mst.country", "US/USA/United States -> `US`", True),
    ("customer", "IFS_CustomerInfo.csv", "TAX_ID", "ArCustomer.TaxNumber", "custaddr_mst.tax_reg_num", "Digits normalised to `NN-NNNNNNN`; filled from any member of the cluster", False),
    ("customer_shipto", "IFS_CustomerAddress.csv", "ADDRESS_ID / ADDRESS_TYPE", "ArShipToAddress.ShipToCode",
     "custaddr_mst.cust_seq > 0", "Bill-to rows come from the golden record; ship-tos keep `BU-code` ids and hang off the golden customer", True),
    ("vendor", "IFS_SupplierInfo.csv", "SUPPLIER_ID", "ApSupplier.Supplier", "vendaddr_mst.vend_num",
     "Golden ID `ENT-VEND-nnnn`", True),
    ("vendor", "IFS_SupplierInfo.csv", "NAME / COUNTRY / TAX_ID", "ApSupplier.SupplierName / Country / TaxNumber",
     "vendaddr_mst.name / country / tax_reg_num", "Same rules as customers", True),
    ("inventory", "IFS_InventoryStock.csv", "PART_NO", "InvWarehouse.StockCode", "itemwhse_mst.item", "Via silver_item_xref; orphan or quarantined item -> quarantine", True),
    ("inventory", "IFS_InventoryStock.csv", "SITE / LOCATION_NO", "(BU) / Warehouse", "(BU) / whse", "`SITE` = business unit; location = warehouse", True),
    ("inventory", "IFS_InventoryStock.csv", "LOT_BATCH_NO / SERIAL_NO", "LotNumber / SerialNumber", "lot / serial_num", "Heat/lot and serial numbers carried untouched (traceability)", False),
    ("inventory", "IFS_InventoryStock.csv", "QTY_ONHAND", "QtyOnHand", "qty_on_hand", "Decimal; negative on-hand is quarantined", True),
    ("inventory", "IFS_InventoryStock.csv", "UNIT_COST / EXT_VALUE", "UnitCost", "unit_cost", "EXT_VALUE = round_half_up(qty x unit cost, 2); one rounding rule everywhere", True),
    ("open_po", "IFS_OpenPurchaseOrders.csv", "ORDER_NO / LINE_NO", "PurchaseOrder / Line", "po_num / po_line", "`<BU>-<legacy order no>` to avoid cross-BU collisions", True),
    ("open_po", "IFS_OpenPurchaseOrders.csv", "SUPPLIER_ID / PART_NO", "Supplier / StockCode", "vend_num / item", "Through vendor and item XREFs", True),
    ("open_po", "IFS_OpenPurchaseOrders.csv", "QTY_OPEN / UNIT_PRICE / EXT_VALUE", "QtyOutstanding / UnitPrice", "qty_open / unit_cost", "Decimal; qty must be > 0", True),
    ("open_so", "IFS_OpenCustomerOrders.csv", "ORDER_NO / CUSTOMER_ID / PART_NO", "SalesOrder / Customer / StockCode", "co_num / cust_num / item", "Through customer and item XREFs", True),
    ("open_ar", "IFS_OpenCustomerInvoices.csv", "INVOICE_NO / CUSTOMER_ID / OPEN_AMOUNT", "Invoice / Customer / InvoiceBalance", "inv_num / cust_num / balance", "Open balance in cents; credit memos stay negative", True),
    ("open_ap", "IFS_OpenSupplierInvoices.csv", "INVOICE_NO / SUPPLIER_ID / OPEN_AMOUNT", "Invoice / Supplier / InvoiceBalance", "voucher / vend_num / balance", "Open balance in cents", True),
    ("gl_balance", "IFS_GLOpeningBalances.csv", "COMPANY / ACCOUNT / BALANCE", "GenMaster.GlCode / Balance", "chart_mst.acct / balance",
     "Legacy account mapped via `reference/gl_account_map.csv`; signed (debit +, credit -); trial balance must sum to 0.00 per company", True),
]
