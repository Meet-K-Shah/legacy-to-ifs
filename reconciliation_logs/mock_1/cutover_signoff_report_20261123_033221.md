# Cutover Sign-Off Report - Mock Load 1

*Generated 20261123_033221 UTC - engine: duckdb + rapidfuzz*

## 1. Verdict

| Control | Result |
|---|---|
| Pre-load readiness gates (load-file integrity) | PASS |
| Count & dollar reconciliation to legacy source | FAIL |
| Cutover readiness criteria (data quality) | NOT READY |
| Open issues | 1042 (CRITICAL 1, HIGH 561, MEDIUM 452, LOW 28) |

Reconciliation proves that nothing was lost or invented. Readiness says whether the *business* should accept the remaining quarantined data. They are separate decisions.

## 2. Row-count reconciliation

Rule: **source rows = IFS rows loaded + quarantined + consolidated duplicates + business-approved exclusions.**

| Domain | Source rows | Loaded to IFS | Quarantined | Consolidated dups | Excluded | Check |
|---|---|---|---|---|---|---|
| Item / Part Master | 10,000 | 8,957 | 224 | 819 | 0 | PASS |
| Bill of Materials | 2,852 | 2,597 | 233 | 22 | 0 | PASS |
| Customer Master (bill-to) | 3,000 | 2,622 | 12 | 366 | 0 | PASS |
| Customer Ship-To Addresses | 2,196 | 2,174 | 22 | 0 | 0 | PASS |
| Vendor Master | 3,000 | 2,622 | 12 | 366 | 0 | PASS |
| Open Inventory | 4,012 | 3,787 | 225 | 0 | 0 | PASS |
| Open Purchase Orders | 2,000 | 1,880 | 120 | 0 | 0 | PASS |
| Open Sales Orders | 2,000 | 1,884 | 116 | 0 | 0 | PASS |
| Open AR Invoices | 1,200 | 1,182 | 18 | 0 | 0 | PASS |
| Open AP Invoices | 1,200 | 1,182 | 18 | 0 | 0 | PASS |
| GL Opening Balances (TB) | 40 | 40 | 0 | 0 | 0 | PASS |

## 3. Dollar-value reconciliation (variance must be $0.00)

*Adjusted source* = legacy extract plus approved data corrections from earlier mocks. Variance = adjusted source - (loaded + quarantined + excluded).

| Domain | BU | Legacy source | Approved corrections | Adjusted source | Loaded to IFS | Quarantined | Excluded | Variance | Check |
|---|---|---|---|---|---|---|---|---|---|
| Open Inventory | BU1 | $57,512,443.40 | $0.00 | $57,512,443.40 | $55,921,945.68 | $1,590,497.72 | $0.00 | $0.00 | PASS |
| Open Inventory | BU2 | $57,518,101.43 | $0.00 | $57,518,101.43 | $55,716,933.55 | $1,801,167.88 | $0.00 | $0.00 | PASS |
| Open Purchase Orders | BU1 | $29,441,118.04 | $0.00 | $29,441,118.04 | $28,370,128.12 | $1,070,989.92 | $0.00 | $0.00 | PASS |
| Open Purchase Orders | BU2 | $29,678,798.87 | $0.00 | $29,678,798.87 | $28,370,483.13 | $1,308,315.74 | $0.00 | $0.00 | PASS |
| Open Sales Orders | BU1 | $41,978,985.99 | $0.00 | $41,978,985.99 | $40,806,186.61 | $1,172,799.38 | $0.00 | $0.00 | PASS |
| Open Sales Orders | BU2 | $39,510,070.74 | $0.00 | $39,510,070.74 | $38,378,970.33 | $1,131,100.41 | $0.00 | $0.00 | PASS |
| Open AR Invoices | BU1 | $45,905,331.56 | $0.00 | $45,905,331.56 | $45,148,833.40 | $756,498.16 | $0.00 | $0.00 | PASS |
| Open AR Invoices | BU2 | $50,555,139.90 | $0.00 | $50,555,139.90 | $49,915,439.97 | $639,699.93 | $0.00 | $0.00 | PASS |
| Open AP Invoices | BU1 | $52,255,735.29 | $0.00 | $52,255,735.29 | $51,603,151.17 | $652,584.12 | $0.00 | $0.00 | PASS |
| Open AP Invoices | BU2 | $47,439,430.51 | $0.00 | $47,439,430.51 | $46,623,508.03 | $815,922.48 | $0.00 | $0.00 | PASS |
| GL Opening Balances (TB) | BU1 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |
| GL Opening Balances (TB) | BU2 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |

## 4. GL control-account tie-out

| BU | Control | GL (legacy) | Sub-ledger (legacy) | Raw break | Adjusting JE in load | Residual break | Corrections pending GL posting | Check |
|---|---|---|---|---|---|---|---|---|
| BU1 | AR | $45,905,331.56 | $45,905,331.56 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |
| BU1 | AP | -$52,255,735.29 | -$52,255,735.29 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |
| BU1 | INV | $57,512,443.40 | $57,512,443.40 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |
| BU2 | AR | $50,555,139.90 | $50,555,139.90 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |
| BU2 | AP | -$47,438,145.96 | -$47,439,430.51 | $1,284.55 | $0.00 | $1,284.55 | $0.00 | FAIL |
| BU2 | INV | $57,518,101.43 | $57,518,101.43 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |

*Residual break* must be $0.00. *Corrections pending GL posting* are approved data corrections that change a sub-ledger balance; Finance should confirm and post the matching journal in IFS.

## 5. Pre-load readiness gates (executed on the load files)

| Gate | File | Rule | Failing rows | Status |
|---|---|---|---|---|
| G01_PK_NOT_NULL | PartCatalog | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | PartCatalog | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | PartCatalog | Mandatory IFS fields populated | 0 | PASS |
| G04_UOM_CANONICAL | PartCatalog | All UNIT_MEAS values are canonical (no unmapped UOMs) | 0 | PASS |
| G01_PK_NOT_NULL | ProductStructure | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | ProductStructure | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | ProductStructure | Mandatory IFS fields populated | 0 | PASS |
| G01_PK_NOT_NULL | CustomerInfo | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | CustomerInfo | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | CustomerInfo | Mandatory IFS fields populated | 0 | PASS |
| G01_PK_NOT_NULL | CustomerAddress | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | CustomerAddress | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | CustomerAddress | Mandatory IFS fields populated | 0 | PASS |
| G01_PK_NOT_NULL | SupplierInfo | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | SupplierInfo | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | SupplierInfo | Mandatory IFS fields populated | 0 | PASS |
| G01_PK_NOT_NULL | InventoryStock | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | InventoryStock | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | InventoryStock | Mandatory IFS fields populated | 0 | PASS |
| G04_UOM_CANONICAL | InventoryStock | All UNIT_MEAS values are canonical (no unmapped UOMs) | 0 | PASS |
| G01_PK_NOT_NULL | OpenPurchaseOrders | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | OpenPurchaseOrders | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | OpenPurchaseOrders | Mandatory IFS fields populated | 0 | PASS |
| G04_UOM_CANONICAL | OpenPurchaseOrders | All UNIT_MEAS values are canonical (no unmapped UOMs) | 0 | PASS |
| G01_PK_NOT_NULL | OpenCustomerOrders | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | OpenCustomerOrders | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | OpenCustomerOrders | Mandatory IFS fields populated | 0 | PASS |
| G04_UOM_CANONICAL | OpenCustomerOrders | All UNIT_MEAS values are canonical (no unmapped UOMs) | 0 | PASS |
| G01_PK_NOT_NULL | OpenCustomerInvoices | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | OpenCustomerInvoices | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | OpenCustomerInvoices | Mandatory IFS fields populated | 0 | PASS |
| G01_PK_NOT_NULL | OpenSupplierInvoices | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | OpenSupplierInvoices | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | OpenSupplierInvoices | Mandatory IFS fields populated | 0 | PASS |
| G01_PK_NOT_NULL | GLOpeningBalances | No null/blank primary-key columns | 0 | PASS |
| G02_PK_UNIQUE | GLOpeningBalances | Primary key is unique | 0 | PASS |
| G03_MANDATORY_POPULATED | GLOpeningBalances | Mandatory IFS fields populated | 0 | PASS |
| G05_NO_NEGATIVE_ONHAND | InventoryStock | No negative on-hand quantity | 0 | PASS |
| G06_REFERENTIAL_INTEGRITY | ProductStructure | PARENT_PART_NO exists in its master file | 0 | PASS |
| G06_REFERENTIAL_INTEGRITY | ProductStructure | COMPONENT_PART_NO exists in its master file | 0 | PASS |
| G06_REFERENTIAL_INTEGRITY | InventoryStock | PART_NO exists in its master file | 0 | PASS |
| G06_REFERENTIAL_INTEGRITY | OpenPurchaseOrders | PART_NO exists in its master file | 0 | PASS |
| G06_REFERENTIAL_INTEGRITY | OpenCustomerOrders | PART_NO exists in its master file | 0 | PASS |
| G06_REFERENTIAL_INTEGRITY | OpenPurchaseOrders | SUPPLIER_ID exists in its master file | 0 | PASS |
| G06_REFERENTIAL_INTEGRITY | OpenCustomerOrders | CUSTOMER_ID exists in its master file | 0 | PASS |
| G06_REFERENTIAL_INTEGRITY | OpenCustomerInvoices | CUSTOMER_ID exists in its master file | 0 | PASS |
| G06_REFERENTIAL_INTEGRITY | OpenSupplierInvoices | SUPPLIER_ID exists in its master file | 0 | PASS |
| G06_REFERENTIAL_INTEGRITY | CustomerAddress | CUSTOMER_ID exists in its master file | 0 | PASS |
| G07_BOM_ACYCLIC | ProductStructure | No circular or self-referencing structures | 0 | PASS |
| G08_EXTENDED_VALUE | InventoryStock | EXT_VALUE = round_half_up(qty x price, 2) | 0 | PASS |
| G08_EXTENDED_VALUE | OpenPurchaseOrders | EXT_VALUE = round_half_up(qty x price, 2) | 0 | PASS |
| G08_EXTENDED_VALUE | OpenCustomerOrders | EXT_VALUE = round_half_up(qty x price, 2) | 0 | PASS |
| G09_TRIAL_BALANCE_ZERO | GLOpeningBalances | Trial balance sums to 0.00 per company | 0 | PASS |

## 6. Cutover readiness criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Quarantine rate - Item / Part Master | <= 2.0% | 2.24% | FAIL |
| Quarantine rate - Bill of Materials | <= 2.0% | 8.17% | FAIL |
| Quarantine rate - Customer Master (bill-to) | <= 2.0% | 0.40% | PASS |
| Quarantine rate - Customer Ship-To Addresses | <= 2.0% | 1.00% | PASS |
| Quarantine rate - Vendor Master | <= 2.0% | 0.40% | PASS |
| Quarantine rate - Open Inventory | <= 2.0% | 5.61% | FAIL |
| Quarantine rate - Open Purchase Orders | <= 2.0% | 6.00% | FAIL |
| Quarantine rate - Open Sales Orders | <= 2.0% | 5.80% | FAIL |
| Quarantine rate - Open AR Invoices | <= 2.0% | 1.50% | PASS |
| Quarantine rate - Open AP Invoices | <= 2.0% | 1.50% | PASS |
| Quarantine rate - GL Opening Balances (TB) | <= 2.0% | 0.00% | PASS |
| Open CRITICAL issues | <= 0 | 1 | FAIL |
| Unresolved steward-review pairs | <= 0 | 41 | FAIL |
| Mandatory IFS fields populated in load files | >= 98.0% | 100% | PASS |

## 7. Master-data harmonisation

- **Items:** 10,000 legacy records -> 8,957 golden records (819 duplicates consolidated, 224 quarantined, 0 excluded).
- **Customers:** 3,000 legacy records -> 2,622 golden records (366 duplicates consolidated, 12 quarantined, 0 excluded).
- **Vendors:** 3,000 legacy records -> 2,622 golden records (366 duplicates consolidated, 12 quarantined, 0 excluded).
- **Steward review queue:** 41 possible-duplicate pair(s) awaiting a MERGE / KEEP_SEPARATE decision.

## 8. Open issues by domain

| Domain | CRITICAL | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| Item / Part Master | 0 | 124 | 100 | 0 |
| Bill of Materials | 0 | 133 | 72 | 28 |
| Customer Master (bill-to) | 0 | 12 | 19 | 0 |
| Customer Ship-To Addresses | 0 | 0 | 22 | 0 |
| Vendor Master | 0 | 12 | 22 | 0 |
| Open Inventory | 0 | 136 | 89 | 0 |
| Open Purchase Orders | 0 | 60 | 60 | 0 |
| Open Sales Orders | 0 | 60 | 56 | 0 |
| Open AR Invoices | 0 | 12 | 6 | 0 |
| Open AP Invoices | 0 | 12 | 6 | 0 |
| GL Opening Balances (TB) | 1 | 0 | 0 | 0 |

Full detail: `data_issue_log.csv` (owner, severity, recommended action, ticket).

## 9. Sign-off

By signing, each owner confirms the reconciliation above, accepts the remaining quarantined records as a post-go-live backlog, and approves loading the files listed below into IFS Cloud.

| Role | Name | Decision (Approve / Reject) | Signature | Date |
|---|---|---|---|---|
| Finance (Controller) |  |  |  |  |
| Operations / Supply Chain |  |  |  |  |
| Sales Operations |  |  |  |  |
| Procurement |  |  |  |  |
| Data & Analytics (ERP data lead) |  |  |  |  |

### Load files in this package

- `IFS_PartCatalog.csv` - 8,957 rows
- `IFS_ProductStructure.csv` - 2,597 rows
- `IFS_CustomerInfo.csv` - 2,622 rows
- `IFS_SupplierInfo.csv` - 2,622 rows
- `IFS_CustomerAddress.csv` - 4,796 rows
- `IFS_InventoryStock.csv` - 3,787 rows
- `IFS_OpenPurchaseOrders.csv` - 1,880 rows
- `IFS_OpenCustomerOrders.csv` - 1,884 rows
- `IFS_OpenCustomerInvoices.csv` - 1,182 rows
- `IFS_OpenSupplierInvoices.csv` - 1,182 rows
- `IFS_GLOpeningBalances.csv` - 40 rows
