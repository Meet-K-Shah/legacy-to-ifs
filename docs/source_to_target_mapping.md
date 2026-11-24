# Source-to-Target Mapping (STTM)

> Generated from `src/ifs_migration/mapping.py` - do not edit by hand (`make docs`).

IFS Cloud field names are **illustrative placeholders** aligned to the project brief; confirm them against the migration templates issued by the implementation partner. Legacy columns are simplified from the real SYSPRO / Syteline schemas.

## Item / Part Master -> `IFS_PartCatalog.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `PART_NO` | InvMaster.StockCode | item_mst.item | Enterprise Golden ID `TT-FAB-nnnnnn` assigned per attribute-identity cluster; legacy codes kept in silver_item_xref | Y |
| `DESCRIPTION` | InvMaster.Description | item_mst.description | Regex-parsed into attributes, rebuilt as enterprise standard description (identical regardless of source style) | Y |
| `UNIT_MEAS` | InvMaster.StockUom | item_mst.u_m | Canonical lookup `reference/uom_map.csv` (EA/EACH/PCS/PC -> EA ...); unmapped -> quarantine ITEM_INVALID_UOM | Y |
| `PART_CATEGORY` | InvMaster.ProductClass | item_mst.family_code | Lookup `reference/category_map.csv` (FLG / FLANGE -> FLANGE ...); unmapped -> quarantine | Y |
| `MATERIAL_SPEC / SIZE_IN / CLASS_RATING / SCHEDULE` | parsed from Description | parsed from description | Extracted attributes (ASTM/ASME spec, size, pressure class, schedule); duplicates detected on these, never on raw text |  |
| `STD_UNIT_COST` | InvMaster.UnitCost | item_mst.unit_cost | Survivor record's cost (Decimal, 4 dp) |  |
| `LEGACY_SOURCES` | StockCode | item | `BU1:<code>\|BU2:<code>` for lineage |  |

## Bill of Materials -> `IFS_ProductStructure.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `PARENT_PART_NO / COMPONENT_PART_NO` | BomStructure.ParentPart / Component | bom_mst.parent_item / comp_item | Mapped through silver_item_xref; parents and components must be LOADED parts | Y |
| `QTY_PER_ASSEMBLY` | BomStructure.QtyPer | bom_mst.qty_per | Decimal > 0, else quarantine | Y |
| `LINE_SEQ` | SequenceNum | oper_num | Renumbered 10,20,30 per enterprise parent | Y |

## Customer Master (bill-to) -> `IFS_CustomerInfo.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `CUSTOMER_ID` | ArCustomer.Customer | custaddr_mst.cust_num (seq 0) | Golden ID `ENT-CUST-nnnn` from fuzzy + tax-ID entity resolution | Y |
| `NAME` | ArCustomer.Name | custaddr_mst.name | Survivor's name, whitespace-cleaned | Y |
| `COUNTRY` | ArCustomer.Country | custaddr_mst.country | US/USA/United States -> `US` | Y |
| `TAX_ID` | ArCustomer.TaxNumber | custaddr_mst.tax_reg_num | Digits normalised to `NN-NNNNNNN`; filled from any member of the cluster |  |

## Customer Ship-To Addresses -> `IFS_CustomerAddress.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `ADDRESS_ID / ADDRESS_TYPE` | ArShipToAddress.ShipToCode | custaddr_mst.cust_seq > 0 | Bill-to rows come from the golden record; ship-tos keep `BU-code` ids and hang off the golden customer | Y |

## Vendor Master -> `IFS_SupplierInfo.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `SUPPLIER_ID` | ApSupplier.Supplier | vendaddr_mst.vend_num | Golden ID `ENT-VEND-nnnn` | Y |
| `NAME / COUNTRY / TAX_ID` | ApSupplier.SupplierName / Country / TaxNumber | vendaddr_mst.name / country / tax_reg_num | Same rules as customers | Y |

## Open Inventory -> `IFS_InventoryStock.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `PART_NO` | InvWarehouse.StockCode | itemwhse_mst.item | Via silver_item_xref; orphan or quarantined item -> quarantine | Y |
| `SITE / LOCATION_NO` | (BU) / Warehouse | (BU) / whse | `SITE` = business unit; location = warehouse | Y |
| `LOT_BATCH_NO / SERIAL_NO` | LotNumber / SerialNumber | lot / serial_num | Heat/lot and serial numbers carried untouched (traceability) |  |
| `QTY_ONHAND` | QtyOnHand | qty_on_hand | Decimal; negative on-hand is quarantined | Y |
| `UNIT_COST / EXT_VALUE` | UnitCost | unit_cost | EXT_VALUE = round_half_up(qty x unit cost, 2); one rounding rule everywhere | Y |

## Open Purchase Orders -> `IFS_OpenPurchaseOrders.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `ORDER_NO / LINE_NO` | PurchaseOrder / Line | po_num / po_line | `<BU>-<legacy order no>` to avoid cross-BU collisions | Y |
| `SUPPLIER_ID / PART_NO` | Supplier / StockCode | vend_num / item | Through vendor and item XREFs | Y |
| `QTY_OPEN / UNIT_PRICE / EXT_VALUE` | QtyOutstanding / UnitPrice | qty_open / unit_cost | Decimal; qty must be > 0 | Y |

## Open Sales Orders -> `IFS_OpenCustomerOrders.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `ORDER_NO / CUSTOMER_ID / PART_NO` | SalesOrder / Customer / StockCode | co_num / cust_num / item | Through customer and item XREFs | Y |

## Open AR Invoices -> `IFS_OpenCustomerInvoices.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `INVOICE_NO / CUSTOMER_ID / OPEN_AMOUNT` | Invoice / Customer / InvoiceBalance | inv_num / cust_num / balance | Open balance in cents; credit memos stay negative | Y |

## Open AP Invoices -> `IFS_OpenSupplierInvoices.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `INVOICE_NO / SUPPLIER_ID / OPEN_AMOUNT` | Invoice / Supplier / InvoiceBalance | voucher / vend_num / balance | Open balance in cents | Y |

## GL Opening Balances (TB) -> `IFS_GLOpeningBalances.csv`

| IFS target field | BU-1 SYSPRO source | BU-2 Syteline source | Transformation / validation rule | Mandatory |
|---|---|---|---|---|
| `COMPANY / ACCOUNT / BALANCE` | GenMaster.GlCode / Balance | chart_mst.acct / balance | Legacy account mapped via `reference/gl_account_map.csv`; signed (debit +, credit -); trial balance must sum to 0.00 per company | Y |

## Reference lookups

- `data/reference/uom_map.csv` - legacy UOM spellings -> canonical UOM (unmapped = quarantine)
- `data/reference/category_map.csv` - SYSPRO `ProductClass` / Syteline `family_code` -> enterprise category
- `data/reference/gl_account_map.csv` - legacy GL account -> IFS account + control role (AR / AP / INV)
