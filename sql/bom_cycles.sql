-- Detect BOM lines that sit on a circular structure (component is its own ancestor).
-- Portable recursive CTE: runs unchanged on DuckDB and SQLite.
-- reach(src, dst) = "dst is reachable from src"; the path string prevents revisiting a node, so loops terminate.
-- An edge (parent -> comp) is cyclic iff comp can reach parent again.
WITH RECURSIVE reach(bu, src, dst, path) AS (
    SELECT bu, parent_code, comp_code, '|' || parent_code || '|' || comp_code || '|'
    FROM stg_bom_edges
    UNION ALL
    SELECT r.bu, r.src, e.comp_code, r.path || e.comp_code || '|'
    FROM reach r
    JOIN stg_bom_edges e ON e.bu = r.bu AND e.parent_code = r.dst
    WHERE INSTR(r.path, '|' || e.comp_code || '|') = 0
)
SELECT e.bu, e.source_row, e.parent_code, e.comp_code, MIN(r.path) AS cycle_path
FROM stg_bom_edges e
JOIN reach r ON r.bu = e.bu AND r.src = e.comp_code AND r.dst = e.parent_code
GROUP BY e.bu, e.source_row, e.parent_code, e.comp_code
ORDER BY e.bu, e.source_row
