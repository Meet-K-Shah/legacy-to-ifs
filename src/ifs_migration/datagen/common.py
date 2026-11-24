"""Shared plumbing for the synthetic legacy-extract generator: tables, row tracking, defect registry."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Registry:
    """Collects every injected defect with the exact source row it landed on (ground truth)."""

    defects: list[dict] = field(default_factory=list)
    row_num: dict[int, int] = field(default_factory=dict)
    entity_truth: list[dict] = field(default_factory=list)
    decoys: list[tuple] = field(default_factory=list)      # (kind, decoy entity id, look-alike entity id)
    _next: int = 0

    def next_id(self) -> int:
        self._next += 1
        return self._next


class Table:
    def __init__(self, reg: Registry, domain: str, bu: str, filename: str, columns: list[str]):
        self.reg, self.domain, self.bu, self.filename, self.columns = reg, domain, bu, filename, columns
        self.rows: list[dict] = []

    def add(self, row: dict) -> dict:
        row["_id"] = self.reg.next_id()
        self.rows.append(row)
        return row

    def defect(self, row: dict, code: str, action: str, detail: str = "", fix: dict | None = None,
               domain: str | None = None) -> None:
        self.reg.defects.append({"domain": domain or self.domain, "bu": self.bu, "_id": row["_id"], "code": code,
                                 "action": action, "detail": detail, "fix": fix})

    def sort(self, key) -> None:
        self.rows.sort(key=key)

    def write(self, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / self.filename
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(self.columns)
            for pos, row in enumerate(self.rows, start=1):
                self.reg.row_num[row["_id"]] = pos
                w.writerow([row.get(c, "") for c in self.columns])
        return path


def pick_indices(rng, n: int, rate: float, minimum: int = 1, exclude: set[int] | None = None, pool: list[int] | None = None) -> list[int]:
    """Choose ~rate*n distinct indices (at least `minimum`) from pool/range, avoiding `exclude`."""
    candidates = [i for i in (pool if pool is not None else range(n)) if not exclude or i not in exclude]
    k = min(len(candidates), max(minimum, round(rate * n)))
    return rng.sample(candidates, k)
