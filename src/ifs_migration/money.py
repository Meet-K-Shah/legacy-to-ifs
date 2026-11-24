"""Exact-decimal helpers. All money is carried as integer cents; floats are never used for values."""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_CLEAN = re.compile(r"[,$\s]")


def parse_decimal(raw) -> Decimal | None:
    """Parse messy legacy numerics ('1,234.50', ' $12.5 ', '(5.00)') into Decimal; None if invalid/blank."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = _CLEAN.sub("", s.strip("()"))
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    if not d.is_finite():
        return None
    return -d if neg else d


def to_cents(value: Decimal) -> int:
    return int((value * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def ext_cents(qty: Decimal, unit_price: Decimal) -> int:
    """Extended value in cents: qty * unit price, rounded half-up to the penny (one rule, used everywhere)."""
    return to_cents(qty * unit_price)


def cents_str(cents: int) -> str:
    """Plain machine format for load files: 1234.56"""
    sign = "-" if cents < 0 else ""
    c = abs(int(cents))
    return f"{sign}{c // 100}.{c % 100:02d}"


def money(cents: int) -> str:
    """Human format for reports: $1,234.56"""
    sign = "-" if cents < 0 else ""
    c = abs(int(cents))
    return f"{sign}${c // 100:,}.{c % 100:02d}"
