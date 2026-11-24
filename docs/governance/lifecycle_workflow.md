# Create / Change / Retire Workflow

```mermaid
flowchart TD
  R[Request: create / change / retire] --> V{Automated checks<br/>duplicate search, mandatory fields,<br/>UOM / category lookup, tax-ID format}
  V -- fail --> RET[Return to requester with reasons]
  V -- pass --> D{Possible duplicate?}
  D -- yes --> ST[Steward review<br/>MERGE / KEEP_SEPARATE decision logged]
  D -- no --> AP{Key attribute change<br/>or new golden record?}
  ST --> AP
  AP -- yes --> OW[Data Owner approval<br/>SLA 2 business days]
  AP -- no --> POST[Post to IFS Cloud]
  OW --> POST
  POST --> PUB[Publish to Fabric Silver / Gold<br/>DQ KPIs refresh]
  PUB --> MON[Monthly stewardship review<br/>KPI trend, open defects, aged requests]
```

- **Retire** = block for new transactions, keep history; never hard-delete a part, customer or vendor.
- **Cross-BU changes** (shared items/parties) require both BU stewards.
- **Emergency creates** allowed for production-critical parts; steward ratifies within 1 business day.
