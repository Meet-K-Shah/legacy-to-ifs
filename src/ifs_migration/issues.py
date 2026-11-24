"""Defect catalogue: every defect code the pipeline can raise, with severity, owner and recommended action."""
from __future__ import annotations

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

OWNERS = {"item": "Supply Chain / Item Data Steward", "bom": "Engineering", "customer": "Sales Ops / AR",
          "customer_shipto": "Sales Ops / AR", "vendor": "Procurement / AP", "inventory": "Warehouse / Inventory Control",
          "open_po": "Procurement", "open_so": "Sales Operations", "open_ar": "Finance (AR)", "open_ap": "Finance (AP)",
          "gl_balance": "Controller"}

CATALOG: dict[str, dict] = {
    "ITEM_NULL_KEY": dict(domain="item", severity="HIGH", title="Item code is blank", action="Delete placeholder row or assign a code"),
    "ITEM_DUP_CODE": dict(domain="item", severity="MEDIUM", title="Item code already used in this BU", action="Confirm which row is valid; delete or renumber the other"),
    "ITEM_NO_DESC": dict(domain="item", severity="MEDIUM", title="Item has no description", action="Supply the description"),
    "ITEM_UNKNOWN_CATEGORY": dict(domain="item", severity="MEDIUM", title="Product class not mapped to a category", action="Assign the correct product class or extend the category map"),
    "ITEM_INVALID_UOM": dict(domain="item", severity="HIGH", title="Unit of measure not in canonical lookup", action="Provide the correct UOM or extend the UOM map"),
    "BOM_SELF_REFERENCE": dict(domain="bom", severity="HIGH", title="Assembly lists itself as a component", action="Remove the line"),
    "BOM_CIRCULAR": dict(domain="bom", severity="HIGH", title="Circular BOM: component is its own ancestor", action="Break the loop; Engineering to confirm correct structure"),
    "BOM_ORPHAN_PARENT": dict(domain="bom", severity="HIGH", title="BOM parent not in item master", action="Create the item or delete the structure"),
    "BOM_ORPHAN_COMPONENT": dict(domain="bom", severity="HIGH", title="BOM component not in item master", action="Correct the component code or create the item"),
    "BOM_INVALID_QTY": dict(domain="bom", severity="MEDIUM", title="Quantity per is zero, negative or blank", action="Supply the correct quantity"),
    "BOM_DUPLICATE_LINE": dict(domain="bom", severity="LOW", title="Same parent/component/sequence loaded twice", action="Delete the duplicate"),
    "BOM_ITEM_QUARANTINED": dict(domain="bom", severity="MEDIUM", title="Parent or component item is quarantined", action="Resolve the item defect; line reloads automatically"),
    "CUST_NO_NAME": dict(domain="customer", severity="HIGH", title="Customer has no name", action="Supply the name or delete the inactive record"),
    "VEND_NO_NAME": dict(domain="vendor", severity="HIGH", title="Vendor has no name", action="Supply the name or delete the inactive record"),
    "SHIP_ORPHAN_CUSTOMER": dict(domain="customer_shipto", severity="MEDIUM", title="Ship-to has no bill-to customer", action="Correct the customer code"),
    "SHIP_CUSTOMER_QUARANTINED": dict(domain="customer_shipto", severity="MEDIUM", title="Ship-to's customer is quarantined", action="Resolve the customer defect"),
    "SHIP_NO_ADDRESS": dict(domain="customer_shipto", severity="MEDIUM", title="Ship-to has no address", action="Supply the address"),
    "PARTY_REVIEW_PENDING": dict(domain="customer", severity="MEDIUM", title="Possible duplicate awaiting steward decision", action="Steward to approve MERGE or KEEP_SEPARATE"),
    "GL_UNMAPPED_ACCOUNT": dict(domain="gl_balance", severity="CRITICAL", title="GL account has no IFS mapping", action="Finance to map the account"),
    "RECON_GL_SUBLEDGER": dict(domain="gl_balance", severity="CRITICAL", title="GL control account does not equal sub-ledger in the legacy source",
                               action="Finance to post an adjusting journal before cutover"),
}
_TXN = {"INV": ("inventory", "HIGH"), "PO": ("open_po", "HIGH"), "SO": ("open_so", "HIGH"), "AR": ("open_ar", "HIGH"), "AP": ("open_ap", "HIGH")}
_TXN_SUFFIX = {
    "ORPHAN_ITEM": ("Item code does not exist in the item master", "Correct the item code or create the item", "HIGH"),
    "ITEM_QUARANTINED": ("Item is quarantined", "Resolve the item defect; line reloads automatically", "MEDIUM"),
    "ORPHAN_VENDOR": ("Vendor code does not exist", "Correct the vendor code", "HIGH"),
    "ORPHAN_CUSTOMER": ("Customer code does not exist", "Correct the customer code", "HIGH"),
    "PARTY_QUARANTINED": ("Customer/vendor is quarantined", "Resolve the party defect; line reloads automatically", "MEDIUM"),
    "INVALID_UOM": ("UOM not in canonical lookup", "Provide the correct UOM", "HIGH"),
    "INVALID_QTY": ("Quantity is zero, negative or blank", "Supply the correct quantity", "MEDIUM"),
    "INVALID_PRICE": ("Price/amount missing or invalid", "Supply the correct price", "MEDIUM"),
    "INVALID_AMOUNT": ("Balance missing or invalid", "Supply the correct balance", "MEDIUM"),
    "INVALID_DATE": ("Date missing or invalid", "Supply a valid date", "MEDIUM"),
    "MISSING_COST": ("Unit cost missing", "Supply the unit cost (affects valuation)", "HIGH"),
    "NEGATIVE_QTY": ("Negative on-hand quantity", "Cycle count and correct the quantity", "HIGH"),
    "DUPLICATE_KEY": ("Duplicate record key", "Delete the duplicate after confirming quantity", "MEDIUM"),
}
CATALOG["INV_DUPLICATE_AFTER_CONSOLIDATION"] = dict(
    domain="inventory", severity="MEDIUM", title="Two legacy item codes now share one enterprise part and one stock key",
    action="Inventory Control to combine the two stock records (same part, location, lot) after a count")
for _p, (_dom, _sev) in _TXN.items():
    for _s, (_t, _a, _sv) in _TXN_SUFFIX.items():
        CATALOG.setdefault(f"{_p}_{_s}", dict(domain=_dom, severity=_sv, title=_t, action=_a))


def info(code: str) -> dict:
    return CATALOG.get(code, dict(domain="", severity="MEDIUM", title=code, action="Review"))


def severity(code: str) -> str:
    return info(code)["severity"]
