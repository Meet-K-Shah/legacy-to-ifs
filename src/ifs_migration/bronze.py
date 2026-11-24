"""Bronze layer: raw, untouched landing of every legacy extract (all columns as text) plus lineage columns."""
from __future__ import annotations

import csv
from datetime import datetime, timezone

from .config import BUS, Paths
from .db import Db
from .mapping import SOURCE_FILES, bronze_table


def ingest(db: Db, paths: Paths) -> dict[str, int]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts: dict[str, int] = {}
    for (bu, key), fname in SOURCE_FILES.items():
        path = paths.raw(bu) / fname
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            cols = list(reader.fieldnames or [])
            rows = []
            for n, row in enumerate(reader, start=1):
                row = {c: (row.get(c) if row.get(c) is not None else "") for c in cols}
                row.update(_row_num=n, _src_file=fname, _ingested_at=stamp)
                rows.append(row)
        schema = {c: "TEXT" for c in cols}
        schema.update({"_row_num": "BIGINT", "_src_file": "TEXT", "_ingested_at": "TEXT"})
        name = bronze_table(bu, key)
        db.write_table(name, schema, rows)
        counts[name] = len(rows)
    # reference lookups also live in the warehouse so profiling can use plain SQL joins
    import csv as _csv
    with (paths.reference / "uom_map.csv").open(newline="") as fh:
        uom = [{"legacy_code": r["legacy_code"].upper(), "canonical_uom": r["canonical_uom"]} for r in _csv.DictReader(fh)]
    db.write_table("ref_uom_map", {"legacy_code": "TEXT", "canonical_uom": "TEXT"}, uom)
    return counts
