"""String similarity with rapidfuzz when installed, and a pure-stdlib fallback with the same 0-100 scale."""
from __future__ import annotations

try:  # pragma: no cover - exercised only where rapidfuzz is installed
    from rapidfuzz import fuzz as _fuzz

    ENGINE = "rapidfuzz"

    def token_sort_ratio(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return float(_fuzz.token_sort_ratio(a, b))

except ImportError:  # stdlib fallback
    import difflib

    ENGINE = "difflib"

    def token_sort_ratio(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        sa = " ".join(sorted(a.split()))
        sb = " ".join(sorted(b.split()))
        return 100.0 * difflib.SequenceMatcher(None, sa, sb, autojunk=False).ratio()
