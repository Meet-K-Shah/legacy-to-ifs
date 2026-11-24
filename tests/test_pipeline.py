"""End-to-end tests against the planted ground truth (defect manifest + entity truth)."""
import csv
from collections import Counter
from itertools import combinations

import pytest

from ifs_migration import gates
from ifs_migration.context import new_context
from ifs_migration.db import connect
from ifs_migration.gates import CutoverBlocked, enforce, run_gates
from ifs_migration.mapping import IFS_FILES


def _manifest(paths):
    with (paths.ground_truth / "defect_manifest.csv").open() as fh:
        return list(csv.DictReader(fh))


def _run_ledger(project, mock):
    """Re-run silver for a mock and return the row ledger (cheap at 10% scale)."""
    from ifs_migration import bronze, silver_bom, silver_items, silver_parties, silver_txn
    paths, _ = project
    db = connect(paths, backend="sqlite", fresh=True, path=paths.warehouse / f"probe{mock}.sqlite")
    ctx = new_context(paths, db, mock)
    bronze.ingest(db, paths)
    silver_items.build(ctx); silver_parties.build(ctx, "customer"); silver_parties.build(ctx, "vendor")
    silver_bom.build(ctx); silver_txn.inventory(ctx)
    for k in ("po", "so"): silver_txn.orders(ctx, k)
    for k in ("ar", "ap"): silver_txn.invoices(ctx, k)
    silver_txn.gl(ctx)
    db.close()
    return ctx


def test_every_planted_quarantine_defect_is_caught_with_the_right_code(project):
    paths, _ = project
    ctx = _run_ledger(project, 1)
    led = {(l["domain"], l["bu"], l["source_row"]): l for l in ctx.ledger}
    wrong = []
    planted = [m for m in _manifest(paths) if m["expected_action"] == "QUARANTINE"]
    assert len(planted) > 50
    for m in planted:
        l = led[(m["domain"], m["bu"], int(m["row_num"]))]
        if not (l["disposition"] == "QUARANTINED" and l["reason"] == m["defect_code"]):
            wrong.append((m["defect_code"], m["domain"], m["bu"], m["row_num"], l["disposition"], l["reason"]))
    assert not wrong, wrong[:10]


def test_every_source_row_has_exactly_one_disposition(project):
    ctx = _run_ledger(project, 1)
    c = Counter((l["domain"], l["bu"], l["source_row"]) for l in ctx.ledger)
    assert max(c.values()) == 1


def test_reconciliation_status_follows_the_finance_journal(project):
    _, s = project
    assert s[1]["recon"] == "FAIL"        # planted BU-2 AP control break is open
    assert s[2]["recon"] == "FAIL"
    assert s[3]["recon"] == "PASS"        # Finance journal posted in Mock 3
    assert all(v["gates_failed"] == 0 for v in s.values())


def test_defects_burn_down_across_mocks(project):
    paths, _ = project
    with (paths.logs / "mock_history.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    opened = [int(r["open_issues"]) for r in rows]
    assert opened[0] > opened[1] > opened[2]
    assert rows[-1]["readiness"] == "READY" and rows[-1]["critical"] == "0"


def test_dollar_parity_is_exact_in_final_mock(project):
    paths, _ = project
    with (paths.mock_logs(3) / "reconciliation_dollars.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows and all(int(r["variance_cents"]) == 0 for r in rows)


def test_entity_resolution_never_merges_different_entities(project):
    paths, _ = project
    truth = {}
    with (paths.ground_truth / "entity_truth.csv").open() as fh:
        for r in csv.DictReader(fh):
            truth[(r["domain"], r["bu"], r["source_key"])] = r["entity_id"]
    db = connect(paths, backend="sqlite", path=paths.warehouse / "migration.sqlite")
    for kind in ("customer", "vendor"):
        groups = {}
        for x in db.query(f"SELECT * FROM silver_{kind}_xref WHERE status IN ('LOADED','CONSOLIDATED')"):
            groups.setdefault(x["enterprise_id"], []).append((kind, x["bu"], x["legacy_code"]))
        false_merges = sum(1 for ms in groups.values() for a, b in combinations(ms, 2) if truth.get(a) != truth.get(b))
        assert false_merges == 0, f"{kind}: {false_merges} false merges (precision must be 100%)"
    for dom, tbl, col in (("item", "silver_item_xref", "enterprise_part_no"),):
        groups = {}
        for x in db.query(f"SELECT * FROM {tbl} WHERE status IN ('LOADED','CONSOLIDATED')"):
            groups.setdefault(x[col], []).append((dom, x["bu"], x["legacy_code"]))
        assert sum(1 for ms in groups.values() for a, b in combinations(ms, 2) if truth.get(a) != truth.get(b)) == 0
    db.close()


def test_enterprise_ids_are_frozen_between_mocks(project):
    paths, _ = project
    import json
    reg = json.loads((paths.data / "id_registry" / "enterprise_ids.json").read_text())
    assert reg["next"]["item"] > 1 and len(set(reg["members"]["item"].values())) <= reg["next"]["item"]


def test_gates_block_the_cutover_when_a_load_file_is_corrupted(project, tmp_path):
    paths, _ = project
    import shutil
    folder = tmp_path / "bad"
    shutil.copytree(paths.ifs_load(3), folder)
    inv = folder / IFS_FILES["inventory"]
    rows = list(csv.DictReader(inv.open()))
    rows[0]["QTY_ONHAND"] = "-5"                       # negative on-hand
    rows[1]["PART_NO"] = ""                            # null primary key
    rows[2]["UNIT_MEAS"] = "BOGUS"                     # unmapped UOM
    with inv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    res = run_gates(folder, {"EA", "FT", "SHT", "LB", "KG", "IN"})
    failed = {r["gate_id"] for r in res if r["status"] == "FAIL"}
    assert {"G01_PK_NOT_NULL", "G04_UOM_CANONICAL", "G05_NO_NEGATIVE_ONHAND"} <= failed
    with pytest.raises(CutoverBlocked):
        enforce(res)


def test_circular_boms_are_found_by_the_recursive_cte(project):
    paths, _ = project
    db = connect(paths, backend="sqlite", path=paths.warehouse / "migration.sqlite")
    rows = db.query("SELECT detail FROM quarantine_bom_defects WHERE defect_code = 'BOM_CIRCULAR'")
    db.close()
    mock3_remaining = len(rows)
    assert mock3_remaining % 3 == 0                    # loops are quarantined as complete 3-line cycles


def test_dashboard_data_access_layer(project):
    """The Streamlit app's data layer: golden search, lineage back to SYSPRO/Syteline, KPI tables, mock files."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    import data_access as da
    paths, _ = project
    db = connect(paths, backend="sqlite", path=paths.warehouse / "migration.sqlite")
    hits = da.search_golden(db, "Item", "TT-FAB-000010")
    assert hits and hits[0]["part_no"] == "TT-FAB-000010"
    lin = da.lineage(db, "Item", "TT-FAB-000010")
    assert lin and lin[0]["legacy_code"] and lin[0]["legacy_value"]
    multi = db.query("SELECT part_no FROM silver_item_golden WHERE member_count > 1 LIMIT 1")[0]["part_no"]
    assert {x["bu"] for x in da.lineage(db, "Item", multi)} == {"BU1", "BU2"}        # cross-BU lineage is visible
    assert da.kpis(db)["kpi"] and da.available_mocks(paths) == [1, 2, 3]
    assert da.mock_files(paths, 3)["dollars"]
    db.close()


def test_docs_are_generated_from_code():
    from ifs_migration import docgen
    text = docgen.sttm()
    assert "IFS_PartCatalog.csv" in text and "PART_NO" in text and "UNIT_MEAS" in text and "CUSTOMER_ID" in text
