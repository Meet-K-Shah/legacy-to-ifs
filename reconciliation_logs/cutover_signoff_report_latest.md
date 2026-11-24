# Cutover Sign-Off Report - Mock Load 3

*Generated 20261123_033225 UTC - engine: duckdb + rapidfuzz*

## 1. Verdict

| Control | Result |
|---|---|
| Pre-load readiness gates (load-file integrity) | PASS |
| Count & dollar reconciliation to legacy source | PASS |
| Cutover readiness criteria (data quality) | READY |
| Open issues | 164 (CRITICAL 0, HIGH 92, MEDIUM 67, LOW 5) |

Reconciliation proves that nothing was lost or invented. Readiness says whether the *business* should accept the remaining quarantined data. They are separate decisions.

## 2. Row-count reconciliation

Rule: **source rows = IFS rows loaded + quarantined + consolidated duplicates + business-approved exclusions.**

| Domain | Source rows | Loaded to IFS | Quarantined | Consolidated dups | Excluded | Check |
|---|---|---|---|---|---|---|
| Item / Part Master | 10,000 | 9,083 | 40 | 849 | 28 | PASS |
| Bill of Materials | 2,852 | 2,740 | 37 | 24 | 51 | PASS |
| Customer Master (bill-to) | 3,000 | 2,598 | 0 | 390 | 12 | PASS |
| Customer Ship-To Addresses | 2,196 | 2,194 | 2 | 0 | 0 | PASS |
| Vendor Master | 3,000 | 2,598 | 2 | 390 | 10 | PASS |
| Open Inventory | 4,012 | 3,969 | 35 | 0 | 8 | PASS |
| Open Purchase Orders | 2,000 | 1,973 | 27 | 0 | 0 | PASS |
| Open Sales Orders | 2,000 | 1,987 | 13 | 0 | 0 | PASS |
| Open AR Invoices | 1,200 | 1,196 | 4 | 0 | 0 | PASS |
| Open AP Invoices | 1,200 | 1,196 | 4 | 0 | 0 | PASS |
| GL Opening Balances (TB) | 40 | 40 | 0 | 0 | 0 | PASS |

## 3. Dollar-value reconciliation (variance must be $0.00)

*Adjusted source* = legacy extract plus approved data corrections from earlier mocks. Variance = adjusted source - (loaded + quarantined + excluded).

| Domain | BU | Legacy source | Approved corrections | Adjusted source | Loaded to IFS | Quarantined | Excluded | Variance | Check |
|---|---|---|---|---|---|---|---|---|---|
| Open Inventory | BU1 | $57,512,443.40 | $2,094,697.75 | $59,607,141.15 | $59,139,306.51 | $200,645.88 | $267,188.76 | $0.00 | PASS |
| Open Inventory | BU2 | $57,518,101.43 | $974,215.06 | $58,492,316.49 | $57,853,241.50 | $637,409.30 | $1,665.69 | $0.00 | PASS |
| Open Purchase Orders | BU1 | $29,441,118.04 | $235,036.26 | $29,676,154.30 | $29,374,705.74 | $301,448.56 | $0.00 | $0.00 | PASS |
| Open Purchase Orders | BU2 | $29,678,798.87 | $115,158.04 | $29,793,956.91 | $29,730,630.69 | $63,326.22 | $0.00 | $0.00 | PASS |
| Open Sales Orders | BU1 | $41,978,985.99 | $29,184.14 | $42,008,170.13 | $42,172,501.29 | -$164,331.16 | $0.00 | $0.00 | PASS |
| Open Sales Orders | BU2 | $39,510,070.74 | $193,240.11 | $39,703,310.85 | $39,650,858.25 | $52,452.60 | $0.00 | $0.00 | PASS |
| Open AR Invoices | BU1 | $45,905,331.56 | $0.00 | $45,905,331.56 | $45,610,124.83 | $295,206.73 | $0.00 | $0.00 | PASS |
| Open AR Invoices | BU2 | $50,555,139.90 | $0.00 | $50,555,139.90 | $50,483,031.62 | $72,108.28 | $0.00 | $0.00 | PASS |
| Open AP Invoices | BU1 | $52,255,735.29 | $0.00 | $52,255,735.29 | $52,161,732.12 | $94,003.17 | $0.00 | $0.00 | PASS |
| Open AP Invoices | BU2 | $47,439,430.51 | $0.00 | $47,439,430.51 | $47,125,008.31 | $314,422.20 | $0.00 | $0.00 | PASS |
| GL Opening Balances (TB) | BU1 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |
| GL Opening Balances (TB) | BU2 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |

## 4. GL control-account tie-out

| BU | Control | GL (legacy) | Sub-ledger (legacy) | Raw break | Adjusting JE in load | Residual break | Corrections pending GL posting | Check |
|---|---|---|---|---|---|---|---|---|
| BU1 | AR | $45,905,331.56 | $45,905,331.56 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |
| BU1 | AP | -$52,255,735.29 | -$52,255,735.29 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |
| BU1 | INV | $57,512,443.40 | $57,512,443.40 | $0.00 | $0.00 | $0.00 | $2,094,697.75 | PASS |
| BU2 | AR | $50,555,139.90 | $50,555,139.90 | $0.00 | $0.00 | $0.00 | $0.00 | PASS |
| BU2 | AP | -$47,438,145.96 | -$47,439,430.51 | $1,284.55 | -$1,284.55 | $0.00 | $0.00 | PASS |
| BU2 | INV | $57,518,101.43 | $57,518,101.43 | $0.00 | $0.00 | $0.00 | $974,215.06 | PASS |

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
| Quarantine rate - Item / Part Master | <= 2.0% | 0.40% | PASS |
| Quarantine rate - Bill of Materials | <= 2.0% | 1.30% | PASS |
| Quarantine rate - Customer Master (bill-to) | <= 2.0% | 0.00% | PASS |
| Quarantine rate - Customer Ship-To Addresses | <= 2.0% | 0.09% | PASS |
| Quarantine rate - Vendor Master | <= 2.0% | 0.07% | PASS |
| Quarantine rate - Open Inventory | <= 2.0% | 0.87% | PASS |
| Quarantine rate - Open Purchase Orders | <= 2.0% | 1.35% | PASS |
| Quarantine rate - Open Sales Orders | <= 2.0% | 0.65% | PASS |
| Quarantine rate - Open AR Invoices | <= 2.0% | 0.33% | PASS |
| Quarantine rate - Open AP Invoices | <= 2.0% | 0.33% | PASS |
| Quarantine rate - GL Opening Balances (TB) | <= 2.0% | 0.00% | PASS |
| Open CRITICAL issues | <= 0 | 0 | PASS |
| Unresolved steward-review pairs | <= 0 | 0 | PASS |
| Mandatory IFS fields populated in load files | >= 98.0% | 100% | PASS |

## 7. Master-data harmonisation

- **Items:** 10,000 legacy records -> 9,083 golden records (849 duplicates consolidated, 40 quarantined, 28 excluded).
- **Customers:** 3,000 legacy records -> 2,598 golden records (390 duplicates consolidated, 0 quarantined, 12 excluded).
- **Vendors:** 3,000 legacy records -> 2,598 golden records (390 duplicates consolidated, 2 quarantined, 10 excluded).
- **Steward review queue:** 0 possible-duplicate pair(s) awaiting a MERGE / KEEP_SEPARATE decision.

## 8. Open issues by domain

| Domain | CRITICAL | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| Item / Part Master | 0 | 21 | 19 | 0 |
| Bill of Materials | 0 | 22 | 10 | 5 |
| Customer Master (bill-to) | 0 | 0 | 0 | 0 |
| Customer Ship-To Addresses | 0 | 0 | 2 | 0 |
| Vendor Master | 0 | 2 | 0 | 0 |
| Open Inventory | 0 | 19 | 16 | 0 |
| Open Purchase Orders | 0 | 17 | 10 | 0 |
| Open Sales Orders | 0 | 6 | 7 | 0 |
| Open AR Invoices | 0 | 2 | 2 | 0 |
| Open AP Invoices | 0 | 3 | 1 | 0 |
| GL Opening Balances (TB) | 0 | 0 | 0 | 0 |

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

- `IFS_PartCatalog.csv` - 9,083 rows
- `IFS_ProductStructure.csv` - 2,740 rows
- `IFS_CustomerInfo.csv` - 2,598 rows
- `IFS_SupplierInfo.csv` - 2,598 rows
- `IFS_CustomerAddress.csv` - 4,792 rows
- `IFS_InventoryStock.csv` - 3,969 rows
- `IFS_OpenPurchaseOrders.csv` - 1,973 rows
- `IFS_OpenCustomerOrders.csv` - 1,987 rows
- `IFS_OpenCustomerInvoices.csv` - 1,196 rows
- `IFS_OpenSupplierInvoices.csv` - 1,196 rows
- `IFS_GLOpeningBalances.csv` - 42 rows
