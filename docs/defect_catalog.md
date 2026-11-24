# Defect Catalogue

> Generated from `issues.py`. Every defect code the pipeline can raise.

Severity drives readiness: **CRITICAL** issues must be zero for go-live; the quarantine-rate threshold is 2.0% per domain.

| Code | Domain | Severity | Meaning | Required business action | Owner |
|---|---|---|---|---|---|
| `BOM_CIRCULAR` | bom | HIGH | Circular BOM: component is its own ancestor | Break the loop; Engineering to confirm correct structure | Engineering |
| `BOM_ORPHAN_COMPONENT` | bom | HIGH | BOM component not in item master | Correct the component code or create the item | Engineering |
| `BOM_ORPHAN_PARENT` | bom | HIGH | BOM parent not in item master | Create the item or delete the structure | Engineering |
| `BOM_SELF_REFERENCE` | bom | HIGH | Assembly lists itself as a component | Remove the line | Engineering |
| `BOM_INVALID_QTY` | bom | MEDIUM | Quantity per is zero, negative or blank | Supply the correct quantity | Engineering |
| `BOM_ITEM_QUARANTINED` | bom | MEDIUM | Parent or component item is quarantined | Resolve the item defect; line reloads automatically | Engineering |
| `BOM_DUPLICATE_LINE` | bom | LOW | Same parent/component/sequence loaded twice | Delete the duplicate | Engineering |
| `CUST_NO_NAME` | customer | HIGH | Customer has no name | Supply the name or delete the inactive record | Sales Ops / AR |
| `PARTY_REVIEW_PENDING` | customer | MEDIUM | Possible duplicate awaiting steward decision | Steward to approve MERGE or KEEP_SEPARATE | Sales Ops / AR |
| `SHIP_CUSTOMER_QUARANTINED` | customer_shipto | MEDIUM | Ship-to's customer is quarantined | Resolve the customer defect | Sales Ops / AR |
| `SHIP_NO_ADDRESS` | customer_shipto | MEDIUM | Ship-to has no address | Supply the address | Sales Ops / AR |
| `SHIP_ORPHAN_CUSTOMER` | customer_shipto | MEDIUM | Ship-to has no bill-to customer | Correct the customer code | Sales Ops / AR |
| `GL_UNMAPPED_ACCOUNT` | gl_balance | CRITICAL | GL account has no IFS mapping | Finance to map the account | Controller |
| `RECON_GL_SUBLEDGER` | gl_balance | CRITICAL | GL control account does not equal sub-ledger in the legacy source | Finance to post an adjusting journal before cutover | Controller |
| `INV_INVALID_UOM` | inventory | HIGH | UOM not in canonical lookup | Provide the correct UOM | Warehouse / Inventory Control |
| `INV_MISSING_COST` | inventory | HIGH | Unit cost missing | Supply the unit cost (affects valuation) | Warehouse / Inventory Control |
| `INV_NEGATIVE_QTY` | inventory | HIGH | Negative on-hand quantity | Cycle count and correct the quantity | Warehouse / Inventory Control |
| `INV_ORPHAN_CUSTOMER` | inventory | HIGH | Customer code does not exist | Correct the customer code | Warehouse / Inventory Control |
| `INV_ORPHAN_ITEM` | inventory | HIGH | Item code does not exist in the item master | Correct the item code or create the item | Warehouse / Inventory Control |
| `INV_ORPHAN_VENDOR` | inventory | HIGH | Vendor code does not exist | Correct the vendor code | Warehouse / Inventory Control |
| `INV_DUPLICATE_AFTER_CONSOLIDATION` | inventory | MEDIUM | Two legacy item codes now share one enterprise part and one stock key | Inventory Control to combine the two stock records (same part, location, lot) after a count | Warehouse / Inventory Control |
| `INV_DUPLICATE_KEY` | inventory | MEDIUM | Duplicate record key | Delete the duplicate after confirming quantity | Warehouse / Inventory Control |
| `INV_INVALID_AMOUNT` | inventory | MEDIUM | Balance missing or invalid | Supply the correct balance | Warehouse / Inventory Control |
| `INV_INVALID_DATE` | inventory | MEDIUM | Date missing or invalid | Supply a valid date | Warehouse / Inventory Control |
| `INV_INVALID_PRICE` | inventory | MEDIUM | Price/amount missing or invalid | Supply the correct price | Warehouse / Inventory Control |
| `INV_INVALID_QTY` | inventory | MEDIUM | Quantity is zero, negative or blank | Supply the correct quantity | Warehouse / Inventory Control |
| `INV_ITEM_QUARANTINED` | inventory | MEDIUM | Item is quarantined | Resolve the item defect; line reloads automatically | Warehouse / Inventory Control |
| `INV_PARTY_QUARANTINED` | inventory | MEDIUM | Customer/vendor is quarantined | Resolve the party defect; line reloads automatically | Warehouse / Inventory Control |
| `ITEM_INVALID_UOM` | item | HIGH | Unit of measure not in canonical lookup | Provide the correct UOM or extend the UOM map | Supply Chain / Item Data Steward |
| `ITEM_NULL_KEY` | item | HIGH | Item code is blank | Delete placeholder row or assign a code | Supply Chain / Item Data Steward |
| `ITEM_DUP_CODE` | item | MEDIUM | Item code already used in this BU | Confirm which row is valid; delete or renumber the other | Supply Chain / Item Data Steward |
| `ITEM_NO_DESC` | item | MEDIUM | Item has no description | Supply the description | Supply Chain / Item Data Steward |
| `ITEM_UNKNOWN_CATEGORY` | item | MEDIUM | Product class not mapped to a category | Assign the correct product class or extend the category map | Supply Chain / Item Data Steward |
| `AP_INVALID_UOM` | open_ap | HIGH | UOM not in canonical lookup | Provide the correct UOM | Finance (AP) |
| `AP_MISSING_COST` | open_ap | HIGH | Unit cost missing | Supply the unit cost (affects valuation) | Finance (AP) |
| `AP_NEGATIVE_QTY` | open_ap | HIGH | Negative on-hand quantity | Cycle count and correct the quantity | Finance (AP) |
| `AP_ORPHAN_CUSTOMER` | open_ap | HIGH | Customer code does not exist | Correct the customer code | Finance (AP) |
| `AP_ORPHAN_ITEM` | open_ap | HIGH | Item code does not exist in the item master | Correct the item code or create the item | Finance (AP) |
| `AP_ORPHAN_VENDOR` | open_ap | HIGH | Vendor code does not exist | Correct the vendor code | Finance (AP) |
| `AP_DUPLICATE_KEY` | open_ap | MEDIUM | Duplicate record key | Delete the duplicate after confirming quantity | Finance (AP) |
| `AP_INVALID_AMOUNT` | open_ap | MEDIUM | Balance missing or invalid | Supply the correct balance | Finance (AP) |
| `AP_INVALID_DATE` | open_ap | MEDIUM | Date missing or invalid | Supply a valid date | Finance (AP) |
| `AP_INVALID_PRICE` | open_ap | MEDIUM | Price/amount missing or invalid | Supply the correct price | Finance (AP) |
| `AP_INVALID_QTY` | open_ap | MEDIUM | Quantity is zero, negative or blank | Supply the correct quantity | Finance (AP) |
| `AP_ITEM_QUARANTINED` | open_ap | MEDIUM | Item is quarantined | Resolve the item defect; line reloads automatically | Finance (AP) |
| `AP_PARTY_QUARANTINED` | open_ap | MEDIUM | Customer/vendor is quarantined | Resolve the party defect; line reloads automatically | Finance (AP) |
| `AR_INVALID_UOM` | open_ar | HIGH | UOM not in canonical lookup | Provide the correct UOM | Finance (AR) |
| `AR_MISSING_COST` | open_ar | HIGH | Unit cost missing | Supply the unit cost (affects valuation) | Finance (AR) |
| `AR_NEGATIVE_QTY` | open_ar | HIGH | Negative on-hand quantity | Cycle count and correct the quantity | Finance (AR) |
| `AR_ORPHAN_CUSTOMER` | open_ar | HIGH | Customer code does not exist | Correct the customer code | Finance (AR) |
| `AR_ORPHAN_ITEM` | open_ar | HIGH | Item code does not exist in the item master | Correct the item code or create the item | Finance (AR) |
| `AR_ORPHAN_VENDOR` | open_ar | HIGH | Vendor code does not exist | Correct the vendor code | Finance (AR) |
| `AR_DUPLICATE_KEY` | open_ar | MEDIUM | Duplicate record key | Delete the duplicate after confirming quantity | Finance (AR) |
| `AR_INVALID_AMOUNT` | open_ar | MEDIUM | Balance missing or invalid | Supply the correct balance | Finance (AR) |
| `AR_INVALID_DATE` | open_ar | MEDIUM | Date missing or invalid | Supply a valid date | Finance (AR) |
| `AR_INVALID_PRICE` | open_ar | MEDIUM | Price/amount missing or invalid | Supply the correct price | Finance (AR) |
| `AR_INVALID_QTY` | open_ar | MEDIUM | Quantity is zero, negative or blank | Supply the correct quantity | Finance (AR) |
| `AR_ITEM_QUARANTINED` | open_ar | MEDIUM | Item is quarantined | Resolve the item defect; line reloads automatically | Finance (AR) |
| `AR_PARTY_QUARANTINED` | open_ar | MEDIUM | Customer/vendor is quarantined | Resolve the party defect; line reloads automatically | Finance (AR) |
| `PO_INVALID_UOM` | open_po | HIGH | UOM not in canonical lookup | Provide the correct UOM | Procurement |
| `PO_MISSING_COST` | open_po | HIGH | Unit cost missing | Supply the unit cost (affects valuation) | Procurement |
| `PO_NEGATIVE_QTY` | open_po | HIGH | Negative on-hand quantity | Cycle count and correct the quantity | Procurement |
| `PO_ORPHAN_CUSTOMER` | open_po | HIGH | Customer code does not exist | Correct the customer code | Procurement |
| `PO_ORPHAN_ITEM` | open_po | HIGH | Item code does not exist in the item master | Correct the item code or create the item | Procurement |
| `PO_ORPHAN_VENDOR` | open_po | HIGH | Vendor code does not exist | Correct the vendor code | Procurement |
| `PO_DUPLICATE_KEY` | open_po | MEDIUM | Duplicate record key | Delete the duplicate after confirming quantity | Procurement |
| `PO_INVALID_AMOUNT` | open_po | MEDIUM | Balance missing or invalid | Supply the correct balance | Procurement |
| `PO_INVALID_DATE` | open_po | MEDIUM | Date missing or invalid | Supply a valid date | Procurement |
| `PO_INVALID_PRICE` | open_po | MEDIUM | Price/amount missing or invalid | Supply the correct price | Procurement |
| `PO_INVALID_QTY` | open_po | MEDIUM | Quantity is zero, negative or blank | Supply the correct quantity | Procurement |
| `PO_ITEM_QUARANTINED` | open_po | MEDIUM | Item is quarantined | Resolve the item defect; line reloads automatically | Procurement |
| `PO_PARTY_QUARANTINED` | open_po | MEDIUM | Customer/vendor is quarantined | Resolve the party defect; line reloads automatically | Procurement |
| `SO_INVALID_UOM` | open_so | HIGH | UOM not in canonical lookup | Provide the correct UOM | Sales Operations |
| `SO_MISSING_COST` | open_so | HIGH | Unit cost missing | Supply the unit cost (affects valuation) | Sales Operations |
| `SO_NEGATIVE_QTY` | open_so | HIGH | Negative on-hand quantity | Cycle count and correct the quantity | Sales Operations |
| `SO_ORPHAN_CUSTOMER` | open_so | HIGH | Customer code does not exist | Correct the customer code | Sales Operations |
| `SO_ORPHAN_ITEM` | open_so | HIGH | Item code does not exist in the item master | Correct the item code or create the item | Sales Operations |
| `SO_ORPHAN_VENDOR` | open_so | HIGH | Vendor code does not exist | Correct the vendor code | Sales Operations |
| `SO_DUPLICATE_KEY` | open_so | MEDIUM | Duplicate record key | Delete the duplicate after confirming quantity | Sales Operations |
| `SO_INVALID_AMOUNT` | open_so | MEDIUM | Balance missing or invalid | Supply the correct balance | Sales Operations |
| `SO_INVALID_DATE` | open_so | MEDIUM | Date missing or invalid | Supply a valid date | Sales Operations |
| `SO_INVALID_PRICE` | open_so | MEDIUM | Price/amount missing or invalid | Supply the correct price | Sales Operations |
| `SO_INVALID_QTY` | open_so | MEDIUM | Quantity is zero, negative or blank | Supply the correct quantity | Sales Operations |
| `SO_ITEM_QUARANTINED` | open_so | MEDIUM | Item is quarantined | Resolve the item defect; line reloads automatically | Sales Operations |
| `SO_PARTY_QUARANTINED` | open_so | MEDIUM | Customer/vendor is quarantined | Resolve the party defect; line reloads automatically | Sales Operations |
| `VEND_NO_NAME` | vendor | HIGH | Vendor has no name | Supply the name or delete the inactive record | Procurement / AP |
