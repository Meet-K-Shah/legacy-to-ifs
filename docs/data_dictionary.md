# Data Dictionary - IFS load files

> Generated from `mapping.py`.

## `IFS_PartCatalog.csv` (Item / Part Master)

| Column | Primary key | Mandatory |
|---|---|---|
| PART_NO | Y | Y |
| DESCRIPTION |  | Y |
| UNIT_MEAS |  | Y |
| PART_CATEGORY |  | Y |
| SUBTYPE |  |  |
| MATERIAL_SPEC |  |  |
| SIZE_IN |  |  |
| CLASS_RATING |  |  |
| SCHEDULE |  |  |
| DRAWING_NO |  |  |
| REVISION |  |  |
| WEIGHT |  |  |
| STD_UNIT_COST |  |  |
| MAKE_BUY |  |  |
| LEGACY_SOURCES |  |  |

## `IFS_ProductStructure.csv` (Bill of Materials)

| Column | Primary key | Mandatory |
|---|---|---|
| PARENT_PART_NO | Y | Y |
| LINE_SEQ | Y |  |
| COMPONENT_PART_NO |  | Y |
| QTY_PER_ASSEMBLY |  | Y |
| SCRAP_PCT |  |  |
| SOURCE_BU |  |  |

## `IFS_CustomerInfo.csv` (Customer Master (bill-to))

| Column | Primary key | Mandatory |
|---|---|---|
| CUSTOMER_ID | Y | Y |
| NAME |  | Y |
| COUNTRY |  | Y |
| TAX_ID |  |  |
| ADDRESS1 |  |  |
| ADDRESS2 |  |  |
| CITY |  |  |
| STATE |  |  |
| ZIP |  |  |
| PAYMENT_TERMS |  |  |
| CONTACT |  |  |
| PHONE |  |  |
| LEGACY_SOURCES |  |  |

## `IFS_CustomerAddress.csv` (Customer Ship-To Addresses)

| Column | Primary key | Mandatory |
|---|---|---|
| CUSTOMER_ID | Y |  |
| ADDRESS_ID | Y |  |
| ADDRESS_TYPE |  |  |
| NAME |  |  |
| ADDRESS1 |  |  |
| CITY |  |  |
| STATE |  |  |
| ZIP |  |  |
| COUNTRY |  |  |
| SOURCE_BU |  |  |

## `IFS_SupplierInfo.csv` (Vendor Master)

| Column | Primary key | Mandatory |
|---|---|---|
| SUPPLIER_ID | Y | Y |
| NAME |  | Y |
| COUNTRY |  | Y |
| TAX_ID |  |  |
| ADDRESS1 |  |  |
| ADDRESS2 |  |  |
| CITY |  |  |
| STATE |  |  |
| ZIP |  |  |
| PAYMENT_TERMS |  |  |
| CONTACT |  |  |
| PHONE |  |  |
| LEGACY_SOURCES |  |  |

## `IFS_InventoryStock.csv` (Open Inventory)

| Column | Primary key | Mandatory |
|---|---|---|
| PART_NO | Y | Y |
| SITE | Y | Y |
| LOCATION_NO | Y |  |
| LOT_BATCH_NO | Y |  |
| SERIAL_NO | Y |  |
| QTY_ONHAND |  | Y |
| UNIT_MEAS |  | Y |
| UNIT_COST |  | Y |
| EXT_VALUE |  |  |
| SOURCE_BU |  |  |

## `IFS_OpenPurchaseOrders.csv` (Open Purchase Orders)

| Column | Primary key | Mandatory |
|---|---|---|
| ORDER_NO | Y | Y |
| LINE_NO | Y | Y |
| SUPPLIER_ID |  | Y |
| PART_NO |  | Y |
| QTY_OPEN |  | Y |
| UNIT_MEAS |  |  |
| UNIT_PRICE |  |  |
| EXT_VALUE |  |  |
| WANTED_DATE |  | Y |
| SOURCE_BU |  |  |

## `IFS_OpenCustomerOrders.csv` (Open Sales Orders)

| Column | Primary key | Mandatory |
|---|---|---|
| ORDER_NO | Y | Y |
| LINE_NO | Y | Y |
| CUSTOMER_ID |  | Y |
| PART_NO |  | Y |
| QTY_OPEN |  | Y |
| UNIT_MEAS |  |  |
| UNIT_PRICE |  |  |
| EXT_VALUE |  |  |
| WANTED_DATE |  | Y |
| SOURCE_BU |  |  |

## `IFS_OpenCustomerInvoices.csv` (Open AR Invoices)

| Column | Primary key | Mandatory |
|---|---|---|
| INVOICE_NO | Y | Y |
| CUSTOMER_ID |  | Y |
| INVOICE_DATE |  |  |
| DUE_DATE |  | Y |
| OPEN_AMOUNT |  | Y |
| SOURCE_BU |  |  |

## `IFS_OpenSupplierInvoices.csv` (Open AP Invoices)

| Column | Primary key | Mandatory |
|---|---|---|
| INVOICE_NO | Y | Y |
| SUPPLIER_ID |  | Y |
| INVOICE_DATE |  |  |
| DUE_DATE |  | Y |
| OPEN_AMOUNT |  | Y |
| SOURCE_BU |  |  |

## `IFS_GLOpeningBalances.csv` (GL Opening Balances (TB))

| Column | Primary key | Mandatory |
|---|---|---|
| COMPANY | Y | Y |
| ACCOUNT | Y | Y |
| ACCOUNT_NAME |  |  |
| BALANCE |  | Y |
| ENTRY_TYPE | Y |  |
| MEMO | Y |  |
