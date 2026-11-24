# Master-Data Standards (enterprise)

## Item / Part
- **Part number:** non-significant sequence `TT-FAB-nnnnnn`, issued once and never reused (see decision DL-003). Meaning lives in attributes, not in the number.
- **Required attributes:** category, unit of measure, standard description, material spec (ASTM/ASME), size, pressure class or schedule where applicable, make/buy, drawing + revision for fabricated assemblies.
- **Description standard:** built from attributes - `CATEGORY, SUBTYPE, size, class/schedule, length, spec` e.g. `FLANGE, WN, 2 IN, CL150, A105`. Free-text descriptions are not accepted.
- **Identity rule:** two items are the same part only if category + subtype + size + rating + material spec (+ drawing/rev for assemblies) all match.
- **UOM:** canonical list in `data/reference/uom_map.csv`; one stocking UOM per part.

## Customer / Vendor
- **Legal entity** is the golden record; locations hang off it (bill-to = golden record, ship-tos are address children).
- **Required:** legal name, country, tax ID (US: EIN as `NN-NNNNNNN`), remit/bill address, payment terms.
- **Name standard:** legal name as registered, no punctuation tricks; suffix kept as registered (LLC, Inc.).
- **Duplicate rule:** same tax ID = same entity; same normalised name + same address/ZIP = same entity; near matches go to steward review; **different tax IDs are never merged automatically**.

## Lifecycle
Create -> approve (steward) -> active -> change (approval for key attributes) -> block -> retire (never delete). See `lifecycle_workflow.md`.

## Quality KPIs (published by domain and BU)
| KPI | Definition | Target |
|---|---|---|
| Completeness | mandatory fields populated / mandatory cells | >= 98% |
| Uniqueness | records that are not duplicate candidates | >= 99% |
| Validity | values in canonical lists (UOM, category) | >= 99% |
| Referential integrity | child rows whose parent exists (BOM components, order items, parties) | >= 99.5% |
| Migration yield | (loaded + consolidated) / source rows | >= 98% |
