"""End-to-end orchestrator: Bronze -> Profiling -> Silver -> IFS mock load + gates -> Reconciliation -> Gold.

    python -m ifs_migration.pipeline --mock 1        # first rehearsal (no business fixes)
    python -m ifs_migration.pipeline --all-mocks     # Mock 1, 2, 3 with defect burn-down
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import bronze, gates, gold, ifs_load, issue_log, profiling, report, silver_bom, silver_items, silver_parties, silver_txn
from . import reconcile
from .config import READINESS, Paths
from .context import new_context
from .db import connect
from .fuzzy import ENGINE
from .mapping import DOMAIN_LABEL, DOMAINS, IFS_FILES


def evaluate_readiness(ctx, recon, issues, gate_results) -> list[dict]:
    th = READINESS
    out = []

    def add(name, threshold, actual, ok):
        out.append({"criterion": name, "threshold": threshold, "actual": str(actual), "status": "PASS" if ok else "FAIL"})
    for c in recon["counts"]:
        rate = 0.0 if c["source_rows"] == 0 else 100.0 * (c["quarantined"]) / c["source_rows"]
        add(f"Quarantine rate - {DOMAIN_LABEL[c['domain']]}", f"<= {th['max_quarantine_rate_pct']}%", f"{rate:.2f}%", rate <= th["max_quarantine_rate_pct"])
    crit = sum(1 for i in issues if i["status"] == "OPEN" and i["severity"] == "CRITICAL")
    add("Open CRITICAL issues", f"<= {th['max_open_critical_issues']}", crit, crit <= th["max_open_critical_issues"])
    add("Unresolved steward-review pairs", f"<= {th['max_unresolved_review_pairs']}", len(ctx.review_pairs),
        len(ctx.review_pairs) <= th["max_unresolved_review_pairs"])
    mand_fail = sum(g["failing_rows"] for g in gate_results if g["gate_id"] == "G03_MANDATORY_POPULATED")
    add("Mandatory IFS fields populated in load files", f">= {th['min_mandatory_completeness_pct']}%", "100%" if mand_fail == 0 else "<100%", mand_fail == 0)
    return out


def run_mock(paths: Paths, mock: int, backend: str | None = None, verbose: bool = True, enforce_gates: bool = True) -> dict:
    t0 = time.time()
    say = (lambda m: print(m, flush=True)) if verbose else (lambda m: None)
    db = connect(paths, backend=backend, fresh=True)
    ctx = new_context(paths, db, mock)
    say(f"=== Mock load {mock} | engine: {db.backend} / matching: {ENGINE} ===")
    counts = bronze.ingest(db, paths)
    say(f"[bronze]  {sum(counts.values()):,} rows landed in {len(counts)} tables")
    prof = profiling.run(ctx)
    say(f"[profile] {len(prof['metrics'])} metrics; RED domains: {[r['domain'] + '/' + r['bu'] for r in prof['readiness'] if r['rag'] == 'RED']}")
    silver_items.build(ctx)
    silver_parties.build(ctx, "customer")
    silver_parties.build(ctx, "vendor")
    silver_bom.build(ctx)
    silver_txn.inventory(ctx)
    silver_txn.orders(ctx, "po")
    silver_txn.orders(ctx, "so")
    silver_txn.invoices(ctx, "ar")
    silver_txn.invoices(ctx, "ap")
    silver_txn.gl(ctx)
    ctx.ids.save()
    disp = Counter(l["disposition"] for l in ctx.ledger)
    say(f"[silver]  ledger: {dict(disp)}")
    ifs_rows = ifs_load.build_files(ctx)
    gate_results = gates.run_gates(paths.ifs_load(mock), set(ctx.uom_map.values()))
    nfail = sum(1 for g in gate_results if g["status"] == "FAIL")
    say(f"[gates]   {len(gate_results) - nfail}/{len(gate_results)} readiness gates passed")
    if enforce_gates:
        gates.enforce(gate_results)
    recon = reconcile.run(ctx)
    say(f"[recon]   {recon['status']} ({sum(1 for r in recon['results'] if r['status'] == 'PASS')}/{len(recon['results'])} checks)")
    issues = issue_log.build(ctx, recon)
    readiness = evaluate_readiness(ctx, recon, issues, gate_results)
    gold.build(ctx, recon, gate_results, issues, readiness)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logs = paths.mock_logs(mock)
    if logs.exists():
        shutil.rmtree(logs)
    logs.mkdir(parents=True)
    md = report.render(ctx, recon, gate_results, issues, readiness, {IFS_FILES[d]: n for d, n in ifs_rows.items()},
                       f"{db.backend} + {ENGINE}", ts)
    (logs / f"cutover_signoff_report_{ts}.md").write_text(md, encoding="utf-8")
    issue_log.write_csv(issues, logs / "data_issue_log.csv")
    _csv(logs / "reconciliation_results.csv", recon["results"])
    _csv(logs / "reconciliation_dollars.csv", recon["dollars"])
    _csv(logs / "readiness_gate_results.csv", gate_results)
    _csv(logs / "domain_readiness_scorecard.csv", prof["readiness"])
    _csv(logs / "party_review_queue.csv", ctx.review_pairs, ["entity", "bu_a", "code_a", "name_a", "bu_b", "code_b", "name_b", "name_score", "address_score", "reason"])
    _csv(logs / "quarantine_bom_defects.csv", db.query("SELECT * FROM quarantine_bom_defects"), ["bu", "source_row", "parent_code", "component_code", "defect_code", "severity", "owner", "detail", "recommended_action"])
    shutil.copy(logs / f"cutover_signoff_report_{ts}.md", paths.logs / "cutover_signoff_report_latest.md")
    _history(paths, mock, ctx, recon, issues, readiness)
    db.close()
    summary = {"mock": mock, "recon": recon["status"], "gates_failed": nfail, "ready": all(r["status"] == "PASS" for r in readiness),
               "open_issues": sum(1 for i in issues if i["status"] == "OPEN"), "seconds": round(time.time() - t0, 1)}
    say(f"[done]    {summary}")
    return summary


def _csv(path: Path, rows: list[dict], cols: list[str] | None = None) -> None:
    cols = cols or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def _history(paths: Paths, mock: int, ctx, recon, issues, readiness) -> None:
    """mock_history.csv drives the defect burn-down chart across rehearsals."""
    path = paths.logs / "mock_history.csv"
    rows = []
    if path.exists():
        with path.open(newline="") as fh:
            rows = [r for r in csv.DictReader(fh) if int(r["mock"]) != mock]
    open_ = [i for i in issues if i["status"] == "OPEN"]
    rows.append({"mock": mock, "run_at": ctx.started, "recon_status": recon["status"],
                 "open_issues": len(open_), "critical": sum(1 for i in open_ if i["severity"] == "CRITICAL"),
                 "high": sum(1 for i in open_ if i["severity"] == "HIGH"), "medium": sum(1 for i in open_ if i["severity"] == "MEDIUM"),
                 "low": sum(1 for i in open_ if i["severity"] == "LOW"), "quarantined_rows": sum(c["quarantined"] for c in recon["counts"]),
                 "review_pairs": len(ctx.review_pairs), "readiness": "READY" if all(r["status"] == "PASS" for r in readiness) else "NOT READY",
                 "golden_items": next(c["loaded"] for c in recon["counts"] if c["domain"] == "item")})
    rows.sort(key=lambda r: int(r["mock"]))
    _csv(path, rows)
    md = ["# Mock-load defect burn-down", "", "| Mock | Open issues | CRITICAL | HIGH | MEDIUM | LOW | Quarantined rows | Steward queue | Reconciliation | Readiness |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['mock']} | {r['open_issues']} | {r['critical']} | {r['high']} | {r['medium']} | {r['low']} | {r['quarantined_rows']} | "
           f"{r['review_pairs']} | {r['recon_status']} | {r['readiness']} |" for r in rows]
    (paths.logs / "mock_burndown.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mock", type=int, choices=(1, 2, 3), default=None, help="run a single rehearsal")
    ap.add_argument("--all-mocks", action="store_true", help="run Mock 1, 2 and 3 in sequence")
    ap.add_argument("--backend", choices=("duckdb", "sqlite"), default=None)
    ap.add_argument("--root", type=Path, default=None)
    args = ap.parse_args(argv)
    paths = Paths(args.root) if args.root else Paths()
    mocks = [1, 2, 3] if args.all_mocks or args.mock is None else [args.mock]
    try:
        for m in mocks:
            run_mock(paths, m, args.backend)
    except gates.CutoverBlocked as exc:
        print(f"\nCUTOVER BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
