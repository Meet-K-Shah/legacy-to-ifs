"""Normalisation primitives shared by profiling, Silver standardisation and tests."""
from __future__ import annotations

import re
from datetime import datetime

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^A-Z0-9 ]")

# ----------------------------------------------------------------------------- codes / blanks


def is_blank(v) -> bool:
    return v is None or str(v).strip() == ""


def clean_code(v) -> str:
    """Legacy key standardisation: trim, collapse whitespace, upper-case. Blank -> ''."""
    if v is None:
        return ""
    return _WS.sub(" ", str(v).strip()).upper()


def clean_text(v) -> str:
    if v is None:
        return ""
    return _WS.sub(" ", str(v).strip())


# ----------------------------------------------------------------------------- dates

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y")


def parse_date(raw) -> str | None:
    """Return ISO date (YYYY-MM-DD) or None if blank/invalid."""
    s = clean_text(raw)
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if 2000 <= d.year <= 2100:
            return d.strftime("%Y-%m-%d")
    return None


# ----------------------------------------------------------------------------- company names

_SUFFIXES = {"LLC", "INC", "INCORPORATED", "CO", "COMPANY", "CORP", "CORPORATION", "LTD", "LP", "LLP", "LIMITED"}
_WORD_MAP = {
    "INTL": "INTERNATIONAL", "MFG": "MANUFACTURING", "SVC": "SERVICE", "SVCS": "SERVICES",
    "ASSOC": "ASSOCIATES", "SUPPLY": "SUPPLY", "SPLY": "SUPPLY", "EQUIP": "EQUIPMENT",
    "IND": "INDUSTRIAL", "INDS": "INDUSTRIES", "ENG": "ENGINEERING", "PROD": "PRODUCTS",
}


def normalize_company_name(name) -> str:
    s = clean_text(name).upper().replace("&", " AND ")
    s = _PUNCT.sub(" ", s)
    toks = [t for t in s.split() if t]
    if toks and toks[0] == "THE":
        toks = toks[1:]
    toks = [_WORD_MAP.get(t, t) for t in toks]
    while toks and toks[-1] in _SUFFIXES:
        toks.pop()
    toks = [t for t in toks if t != "AND"]
    return " ".join(toks)


# ----------------------------------------------------------------------------- addresses

_ADDR_MAP = {
    "STREET": "ST", "ROAD": "RD", "AVENUE": "AVE", "BOULEVARD": "BLVD", "DRIVE": "DR", "HIGHWAY": "HWY",
    "SUITE": "STE", "LANE": "LN", "PARKWAY": "PKWY", "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "COURT": "CT", "PLACE": "PL", "BUILDING": "BLDG", "FLOOR": "FL",
}


def normalize_address(*parts) -> str:
    s = " ".join(clean_text(p) for p in parts if not is_blank(p)).upper()
    s = _PUNCT.sub(" ", s)
    toks = [_ADDR_MAP.get(t, t) for t in s.split()]
    return " ".join(toks)


def normalize_taxid(v) -> str:
    digits = re.sub(r"\D", "", str(v or ""))
    return digits if len(digits) == 9 else ""


def normalize_zip(v) -> str:
    digits = re.sub(r"\D", "", str(v or ""))
    return digits[:5] if len(digits) >= 5 else ""


US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA",
    "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
