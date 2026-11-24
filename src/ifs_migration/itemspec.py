"""Item attribute model for engineered liquid/gas fabrication, plus the regex parser that turns free-text
legacy descriptions into structured attributes. Item identity is decided on attributes (never on raw text):
SA-516 Gr 70 plate and SA-516 Gr 60 plate must never be merged because their descriptions look alike.
"""
from __future__ import annotations

import re
from fractions import Fraction

CATEGORIES = ("FLANGE", "VALVE", "PIPE", "FITTING", "PLATE", "BOLTING", "GASKET", "FABRICATION")

# canonical subtype -> accepted spellings (longest spelling is tried first)
SUBTYPES: dict[str, dict[str, list[str]]] = {
    "FLANGE": {"WN": ["WELD NECK", "WELDNECK", "WN"], "SO": ["SLIP-ON", "SLIP ON", "SO"], "BL": ["BLIND", "BL"],
               "SW": ["SOCKET WELD", "SW"]},
    "VALVE": {"GATE": ["GATE"], "GLOBE": ["GLOBE"], "CHECK": ["CHECK"], "BALL": ["BALL"],
              "BUTTERFLY": ["BUTTERFLY", "BFLY"]},
    "PIPE": {"SMLS": ["SEAMLESS", "SMLS"], "ERW": ["ERW"]},
    "FITTING": {"ELL90": ["90 DEG ELBOW", "90 ELBOW", "ELBOW 90"], "ELL45": ["45 DEG ELBOW", "45 ELBOW", "ELBOW 45"],
                "TEE": ["TEE"], "REDUCER": ["REDUCER", "RED"], "CAP": ["CAP"], "COUPLING": ["COUPLING", "CPLG"],
                "STUBEND": ["STUB END", "STUBEND"]},
    "PLATE": {},
    "BOLTING": {"STUD": ["STUD BOLT", "STUD"], "HEXBOLT": ["HEX HEAD BOLT", "HEX BOLT"], "NUT": ["HEAVY HEX NUT", "HEX NUT"]},
    "GASKET": {"SPIRAL": ["SPIRAL WOUND", "SPWD"], "RTJ": ["RING JOINT", "RTJ"], "SHEET": ["SHEET"]},
    "FABRICATION": {"SHELL": ["SHELL ASSEMBLY", "SHELL ASSY"], "HEAD": ["HEAD ASSEMBLY", "HEAD ASSY"],
                    "NOZZLE": ["NOZZLE ASSEMBLY", "NOZZLE ASSY"], "MANWAY": ["MANWAY ASSEMBLY", "MANWAY ASSY"],
                    "SKID": ["SKID FRAME", "SKID ASSY"], "SPOOL": ["PIPE SPOOL", "SPOOL"],
                    "SADDLE": ["SADDLE SUPPORT", "SADDLE"], "VESSEL": ["PRESSURE VESSEL", "VESSEL ASSY"],
                    "BUNDLE": ["TUBE BUNDLE", "BUNDLE"]},
}

# canonical material specs per category (ASTM/ASME)
SPECS: dict[str, list[str]] = {
    "FLANGE": ["A105", "A182-F316", "A182-F304", "A182-F316L", "A350-LF2", "A182-F51"],
    "VALVE": ["A216-WCB", "A351-CF8M", "A105", "A182-F316", "A352-LCC"],
    "PIPE": ["A106-B", "A53-B", "A312-TP304L", "A312-TP316L", "A333-6"],
    "FITTING": ["A234-WPB", "A403-WP316L", "A403-WP304L", "A420-WPL6"],
    "PLATE": ["A516-70", "A516-60", "A240-304L", "A240-316L", "A36", "A572-50", "A283-C"],
    "BOLTING": ["A193-B7", "A193-B8", "A194-2H", "A320-L7"],
    "GASKET": [],
    "FABRICATION": [],
}

KEY_FIELDS: dict[str, tuple[str, ...]] = {
    "FLANGE": ("subtype", "size", "cls", "spec"),
    "VALVE": ("subtype", "size", "cls", "spec"),
    "PIPE": ("subtype", "size", "sch", "length", "spec"),
    "FITTING": ("subtype", "size", "sch", "spec"),
    "PLATE": ("size", "dims", "spec"),
    "BOLTING": ("subtype", "size", "length", "spec"),
    "GASKET": ("subtype", "size", "cls"),
    "FABRICATION": ("subtype", "dwg", "rev"),
}

ATTR_FIELDS = ("subtype", "size", "cls", "sch", "length", "dims", "spec", "dwg", "rev")

_SIZE_RE = re.compile(r"(\d+/\d+|\d+(?:\.\d+)?)\s*-?\s*(?:IN(?:CH)?\b|\")")
_CLASS_RE = re.compile(r"\bCL(?:ASS)?\s*(\d{3,4})\b|(\d{3,4})\s*(?:#|LBS?\b)")
_SCH_RE = re.compile(r"\bSCH(?:EDULE)?[\s\-]*(\d+S?|STD|XXS|XS)\b")
_PIPE_LEN_RE = re.compile(r"(\d+)\s*(?:FT|FOOT|FEET)\b")
_BOLT_LEN_RE = re.compile(r"(\d+/\d+|\d+(?:\.\d+)?)\s*(?:IN\b|\")?\s*(?:LG|LONG)\b")
_DIMS_RE = re.compile(r"\b(\d+)\s*X\s*(\d+)\b")
_DWG_RE = re.compile(r"\bDWG[\s\-#]*(\d{5,6})\b")
_REV_RE = re.compile(r"\bREV\.?\s*([A-Z0-9])\b")
_SPEC_RE = re.compile(r"\b(?:ASTM\s*)?S?A[\s\-]?(\d{2,3})\b(?:[\s\-,\.]*(?:GR(?:ADE)?\.?[\s\-]*)?([A-Z0-9]+))?")


def canon_number(text: str) -> str:
    """'2.0' -> '2', '1/2' -> '0.5', '0.500' -> '0.5'."""
    val = float(Fraction(text)) if "/" in text else float(text)
    return f"{val:g}"


def spec_parts(spec_id: str) -> tuple[str, str]:
    base, _, grade = spec_id[1:].partition("-")
    return base, grade


def _subtype_lookup(category: str) -> list[tuple[str, str]]:
    pairs = [(syn, canon) for canon, syns in SUBTYPES.get(category, {}).items() for syn in syns]
    return sorted(pairs, key=lambda p: -len(p[0]))


def parse_item_description(category: str, description: str) -> dict[str, str]:
    """Extract structured attributes from a free-text description. Missing attributes are ''."""
    text = re.sub(r"\s+", " ", (description or "").upper()).strip()
    out = {f: "" for f in ATTR_FIELDS}
    out["category"] = category
    if not text:
        return out

    for syn, canon in _subtype_lookup(category):
        if re.search(rf"(?<![A-Z0-9]){re.escape(syn)}(?![A-Z0-9])", text):
            out["subtype"] = canon
            break

    if category != "FABRICATION":
        m = _SIZE_RE.search(text)
        if m:
            out["size"] = canon_number(m.group(1))
    m = _CLASS_RE.search(text)
    if m and category in ("FLANGE", "VALVE", "GASKET"):
        out["cls"] = m.group(1) or m.group(2)
    m = _SCH_RE.search(text)
    if m:
        out["sch"] = m.group(1)
    if category == "PIPE":
        m = _PIPE_LEN_RE.search(text)
        if m:
            out["length"] = str(int(m.group(1)))
    if category == "BOLTING":
        m = _BOLT_LEN_RE.search(text)
        if m:
            out["length"] = canon_number(m.group(1))
    if category == "PLATE":
        m = _DIMS_RE.search(text)
        if m:
            out["dims"] = f"{int(m.group(1))}X{int(m.group(2))}"
    if category == "FABRICATION":
        m = _DWG_RE.search(text)
        if m:
            out["dwg"] = m.group(1)
        m = _REV_RE.search(text)
        if m:
            out["rev"] = m.group(1)
    if SPECS.get(category):
        m = _SPEC_RE.search(text)
        if m:
            base, grade = m.group(1), (m.group(2) or "")
            out["spec"] = f"A{base}-{grade}" if grade else f"A{base}"
    return out


def key_complete(attrs: dict[str, str]) -> bool:
    return all(attrs.get(f) for f in KEY_FIELDS.get(attrs.get("category", ""), ()))


def item_key(attrs: dict[str, str]) -> str:
    """Attribute-based identity key used for duplicate detection across business units."""
    cat = attrs.get("category", "")
    return "|".join([cat] + [attrs.get(f, "") for f in KEY_FIELDS.get(cat, ())])


def standard_description(attrs: dict[str, str]) -> str:
    """Enterprise-standard description built from attributes (identical regardless of source BU style)."""
    cat = attrs["category"]
    parts = [cat if cat != "FABRICATION" else "FAB"]
    if attrs.get("subtype"):
        parts.append(attrs["subtype"])
    if attrs.get("dwg"):
        parts.append(f"DWG-{attrs['dwg']}")
    if attrs.get("rev"):
        parts.append(f"REV {attrs['rev']}")
    if attrs.get("size"):
        parts.append(f"{attrs['size']} IN")
    if attrs.get("dims"):
        parts.append(attrs["dims"])
    if attrs.get("cls"):
        parts.append(f"CL{attrs['cls']}")
    if attrs.get("sch"):
        parts.append(f"SCH {attrs['sch']}")
    if attrs.get("length"):
        parts.append(f"{attrs['length']} FT" if cat == "PIPE" else f"{attrs['length']} IN LG")
    if attrs.get("spec"):
        parts.append(attrs["spec"])
    return ", ".join(parts)
