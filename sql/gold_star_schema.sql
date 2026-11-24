-- Gold layer: Kimball star schema over the Silver golden records. Portable DuckDB/SQLite SQL.
-- Designed to be loaded to Power BI (Import or DirectQuery) as the semantic-layer source; no legacy ERP schema leaks through.

DROP TABLE IF EXISTS gold_dim_bu;
CREATE TABLE gold_dim_bu AS
SELECT 1 AS bu_key, 'BU1' AS bu, 'SYSPRO' AS legacy_system, 'BU-1 (SYSPRO)' AS bu_name
UNION ALL SELECT 2, 'BU2', 'Infor Syteline', 'BU-2 (Syteline)';

DROP TABLE IF EXISTS gold_dim_item;
CREATE TABLE gold_dim_item AS
SELECT ROW_NUMBER() OVER (ORDER BY part_no) AS item_key,
       part_no AS enterprise_part_no, description, category, subtype, size_in, material_spec, class_rating, schedule,
       uom, CAST(NULLIF(std_unit_cost, '') AS DOUBLE) AS std_unit_cost, make_buy, source_bus, member_count,
       CASE WHEN INSTR(source_bus, '|') > 0 THEN 1 ELSE 0 END AS is_cross_bu_item, legacy_sources
FROM silver_item_golden;

DROP TABLE IF EXISTS gold_dim_customer;
CREATE TABLE gold_dim_customer AS
SELECT ROW_NUMBER() OVER (ORDER BY enterprise_id) AS customer_key,
       enterprise_id AS enterprise_customer_id, name, country, city, state,
       CASE WHEN tax_id <> '' THEN 1 ELSE 0 END AS has_tax_id, source_bus, member_count, legacy_sources
FROM silver_customer_golden;

DROP TABLE IF EXISTS gold_dim_vendor;
CREATE TABLE gold_dim_vendor AS
SELECT ROW_NUMBER() OVER (ORDER BY enterprise_id) AS vendor_key,
       enterprise_id AS enterprise_vendor_id, name, country, city, state,
       CASE WHEN tax_id <> '' THEN 1 ELSE 0 END AS has_tax_id, source_bus, member_count, legacy_sources
FROM silver_vendor_golden;

DROP TABLE IF EXISTS gold_fact_inventory;
CREATE TABLE gold_fact_inventory AS
SELECT i.item_key, b.bu_key, s.site, s.location_no AS warehouse, s.lot_batch_no AS lot_no, s.serial_no,
       CAST(s.qty AS DOUBLE) AS qty_on_hand, CAST(s.unit_cost AS DOUBLE) AS unit_cost,
       s.ext_value_cents, s.ext_value_cents / 100.0 AS ext_value_usd
FROM silver_inventory s
JOIN gold_dim_item i ON i.enterprise_part_no = s.part_no
JOIN gold_dim_bu b ON b.bu = s.source_bu;

DROP TABLE IF EXISTS gold_fact_open_orders;
CREATE TABLE gold_fact_open_orders AS
SELECT 'PO' AS order_type, p.order_no, p.line_no, i.item_key, NULL AS customer_key, v.vendor_key, b.bu_key,
       CAST(p.qty AS DOUBLE) AS qty_open, CAST(p.unit_price AS DOUBLE) AS unit_price, p.ext_value_cents,
       p.ext_value_cents / 100.0 AS ext_value_usd, p.wanted_date
FROM silver_open_po p
JOIN gold_dim_item i ON i.enterprise_part_no = p.part_no
JOIN gold_dim_vendor v ON v.enterprise_vendor_id = p.party_id
JOIN gold_dim_bu b ON b.bu = p.source_bu
UNION ALL
SELECT 'SO', s.order_no, s.line_no, i.item_key, c.customer_key, NULL, b.bu_key,
       CAST(s.qty AS DOUBLE), CAST(s.unit_price AS DOUBLE), s.ext_value_cents, s.ext_value_cents / 100.0, s.wanted_date
FROM silver_open_so s
JOIN gold_dim_item i ON i.enterprise_part_no = s.part_no
JOIN gold_dim_customer c ON c.enterprise_customer_id = s.party_id
JOIN gold_dim_bu b ON b.bu = s.source_bu;

DROP VIEW IF EXISTS gold_v_inventory_by_category;
CREATE VIEW gold_v_inventory_by_category AS
SELECT d.category, b.bu, COUNT(*) AS stock_records, SUM(f.ext_value_usd) AS inventory_value_usd
FROM gold_fact_inventory f JOIN gold_dim_item d ON d.item_key = f.item_key JOIN gold_dim_bu b ON b.bu_key = f.bu_key
GROUP BY d.category, b.bu;

DROP VIEW IF EXISTS gold_v_open_orders_summary;
CREATE VIEW gold_v_open_orders_summary AS
SELECT f.order_type, b.bu, COUNT(*) AS open_lines, SUM(f.ext_value_usd) AS open_value_usd
FROM gold_fact_open_orders f JOIN gold_dim_bu b ON b.bu_key = f.bu_key
GROUP BY f.order_type, b.bu
