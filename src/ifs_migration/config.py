"""Central configuration: paths, business units, thresholds."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BUS = ("BU1", "BU2")
BU_NAMES = {"BU1": "BU-1 (SYSPRO)", "BU2": "BU-2 (Syteline)"}
BU_SYSTEM = {"BU1": "SYSPRO", "BU2": "Infor Syteline"}
BU_FOLDER = {"BU1": "syspro", "BU2": "syteline"}

PART_PREFIX = "TT-FAB-"
CUSTOMER_PREFIX = "ENT-CUST-"
VENDOR_PREFIX = "ENT-VEND-"

# Fuzzy matching thresholds (0-100 scale, rapidfuzz token_sort_ratio semantics)
MATCH_AUTO_NAME = 92.0      # name score needed (with address support) to auto-merge
MATCH_REVIEW_NAME = 85.0    # name score that sends a pair to the steward review queue
MATCH_ADDR_SUPPORT = 70.0   # address similarity that counts as "supporting"
MATCH_ADDR_STRONG = 85.0

# Cutover readiness thresholds (go-live criteria)
READINESS = {
    "max_quarantine_rate_pct": 2.0,     # per domain, share of source rows quarantined
    "max_open_critical_issues": 0,      # CRITICAL severity must be zero
    "max_unresolved_review_pairs": 0,   # steward queue must be empty
    "min_mandatory_completeness_pct": 98.0,
}


@dataclass(frozen=True)
class Paths:
    root: Path = Path(__file__).resolve().parents[2]

    @property
    def data(self) -> Path:
        return self.root / "data"

    def raw(self, bu: str) -> Path:
        return self.data / "raw" / BU_FOLDER[bu]

    @property
    def reference(self) -> Path:
        return self.data / "reference"

    @property
    def ground_truth(self) -> Path:
        return self.data / "ground_truth"

    @property
    def remediation(self) -> Path:
        return self.data / "remediation"

    @property
    def warehouse(self) -> Path:
        return self.root / "warehouse"

    @property
    def logs(self) -> Path:
        return self.root / "reconciliation_logs"

    def ifs_load(self, mock: int) -> Path:
        return self.data / "ifs_load" / f"mock_{mock}"

    def mock_logs(self, mock: int) -> Path:
        return self.logs / f"mock_{mock}"

    @property
    def docs(self) -> Path:
        return self.root / "docs"
