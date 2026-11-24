# Decision Log

Decisions taken (or proposed for business-owner ratification) during the data workstream. Status: **Proposed** until the named owner signs.

| ID | Topic | Decision | Rationale | Owner | Status |
|---|---|---|---|---|---|
| DL-001 | Item identity | Duplicates are decided on attributes (category, subtype, size, rating, spec, drawing/rev), never on description text | SA-516 Gr 70 vs Gr 60 plate must stay distinct | Supply Chain | Proposed |
| DL-002 | UOM | One canonical UOM list; synonyms (EACH, PCS, PC) auto-map; unmapped codes are quarantined, never guessed | Wrong UOM silently corrupts valuation | Supply Chain / Finance | Proposed |
| DL-003 | Part numbering | Non-significant sequence `TT-FAB-nnnnnn`; classification lives in attributes | Smart numbers collide across BUs and break when specs change | Supply Chain | Proposed |
| DL-004 | Survivorship (items) | Most complete record survives; ties -> lowest BU, then earliest row | Deterministic, explainable | Item Steward | Proposed |
| DL-005 | Customer/vendor merge | Tax-ID match or name>=92 with address support auto-merges; name 85-92 with address support goes to steward queue; **different tax IDs never auto-merge** | Avoids merging distinct legal entities | Customer/Vendor Stewards | Proposed |
| DL-006 | Bill-to / ship-to | Golden record = bill-to legal entity; ship-tos are address children keyed `BU-code-shipcode` | Keeps site-level history without duplicating the entity | Sales Ops | Proposed |
| DL-007 | Duplicate BOMs | When both BUs have a BOM for the same enterprise assembly, the surviving record's BU structure loads; the other is reported as superseded | One structure per assembly in IFS | Engineering | Proposed |
| DL-008 | Negative on-hand | Quarantined until Inventory Control corrects after a count; never loaded | IFS rejects negative stock; hides valuation error | Inventory Control | Proposed |
| DL-009 | Stock-key collisions | If two legacy codes of one part share part/location/lot/serial, the second is quarantined for Inventory Control to combine | Silent summation would break exact value parity | Inventory Control | Proposed |
| DL-010 | Dollar parity | Adjusted source (legacy + approved corrections) must equal loaded + quarantined + excluded to $0.00; approved corrections are reported separately for Finance to post | Distinguishes migration errors from business corrections | Controller | Proposed |
| DL-011 | GL control accounts | AR/AP/Inventory control must tie to sub-ledgers; any legacy break needs a Finance adjusting journal before cutover | Prevents loading a known imbalance | Controller | Proposed |
| DL-012 | Readiness thresholds | Quarantine rate <= 2% per domain, zero CRITICAL issues, empty steward queue | Go-live criteria agreed up front | Program Mgmt | Proposed |
| DL-013 | Frozen IDs | Enterprise IDs never change between mock loads; merged IDs retained as aliases | Stable references for testing and reporting | Data & Analytics | Proposed |
