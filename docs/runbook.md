# Runbook

| Task | Command |
|---|---|
| Install | `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| Generate synthetic legacy data (deterministic) | `make data` (`--scale 1.0 --seed 42`) |
| One rehearsal | `PYTHONPATH=src python -m ifs_migration.pipeline --mock 1` |
| All rehearsals with burn-down | `make mocks` |
| Tests | `make test` |
| Governance app | `make app` |
| Regenerate docs | `make docs` |
| Force a specific engine | `IFS_MIG_BACKEND=duckdb` or `sqlite` |

## Outputs per mock (`reconciliation_logs/mock_N/`)
`cutover_signoff_report_<timestamp>.md`, `data_issue_log.csv`, `reconciliation_results.csv`, `reconciliation_dollars.csv`,
`readiness_gate_results.csv`, `domain_readiness_scorecard.csv`, `party_review_queue.csv`, `quarantine_bom_defects.csv`.
IFS load files: `data/ifs_load/mock_N/IFS_*.csv`.

## Troubleshooting
- **`CUTOVER BLOCKED`**: a readiness gate failed; see `readiness_gate_results.csv`. Fix the cause upstream - never edit load files by hand.
- **Reconciliation FAIL**: open `reconciliation_results.csv`, filter `status = FAIL`; `GL_TIEOUT` fails until Finance's adjusting journal is in the fixes file.
- **Enterprise IDs changed unexpectedly**: Mock 1 resets the ID registry on purpose; run Mock 2/3 against the same registry.
- **Slow matching on huge inputs**: install `rapidfuzz` (C++ implementation); the pure-Python fallback is ~20x slower.
