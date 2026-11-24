"""Canonical item universe (ASME/API fabrication materials) and BU-specific rendering of legacy descriptions."""
from __future__ import annotations

import itertools

from ..itemspec import ATTR_FIELDS, SPECS, SUBTYPES, spec_parts

SIZES = [0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8, 10, 12, 14, 16, 18, 20]
CLASSES = [150, 300, 600, 900]
SCHEDULES = ["STD", "40", "80", "160"]
PLATE_THICK = [0.25, 0.375, 0.5, 0.625, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 4]
PLATE_DIMS = ["48X96", "60X120", "72X144"]
BOLT_DIA = [0.5, 0.625, 0.75, 0.875, 1, 1.125, 1.25, 1.5, 1.75, 2]
BOLT_LEN = [2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 7, 8, 10]

CATEGORY_CODE = {
    "BU1": {"FLANGE": "FLG", "VALVE": "VLV", "PIPE": "PIP", "FITTING": "FIT", "PLATE": "PLT", "BOLTING": "BLT",
            "GASKET": "GSK", "FABRICATION": "FAB"},
    "BU2": {"FLANGE": "FLANGE", "VALVE": "VALVE", "PIPE": "PIPE", "FITTING": "FITTING", "PLATE": "PLATE",
            "BOLTING": "FASTENER", "GASKET": "GASKET", "FABRICATION": "FABASSY"},
}
BASE_UOM = {"FLANGE": "EA", "VALVE": "EA", "PIPE": "FT", "FITTING": "EA", "PLATE": "SHT", "BOLTING": "EA",
            "GASKET": "EA", "FABRICATION": "EA"}
UOM_SYNONYMS = {"EA": ["EACH", "PCS", "PC", "EAC"], "FT": ["FEET", "FOOT"], "SHT": ["SHEET", "SHEETS"]}
INVALID_UOMS = ["XX", "BX?", "UNK", "??", "N/A", ""]
BASE_COST = {"FLANGE": 22, "VALVE": 160, "PIPE": 4.5, "FITTING": 14, "PLATE": 320, "BOLTING": 3, "GASKET": 16,
             "FABRICATION": 4200}
NOUN = {"FLANGE": "FLANGE", "VALVE": "VALVE", "PIPE": "PIPE", "FITTING": "", "PLATE": "PLATE", "BOLTING": "",
        "GASKET": "GASKET", "FABRICATION": ""}
FRACTIONS = {0.25: "1/4", 0.375: "3/8", 0.5: "1/2", 0.625: "5/8", 0.75: "3/4", 0.875: "7/8"}


def _g(v) -> str:
    return f"{v:g}"


def _attrs(category: str, **kw) -> dict[str, str]:
    a = {f: "" for f in ATTR_FIELDS}
    a["category"] = category
    a.update({k: str(v) for k, v in kw.items()})
    return a


def non_fab_pool() -> list[dict[str, str]]:
    pool: list[dict[str, str]] = []
    for st, sz, cl, sp in itertools.product(SUBTYPES["FLANGE"], SIZES, CLASSES, SPECS["FLANGE"]):
        pool.append(_attrs("FLANGE", subtype=st, size=_g(sz), cls=cl, spec=sp))
    for st, sz, cl, sp in itertools.product(SUBTYPES["VALVE"], SIZES[:12], CLASSES, SPECS["VALVE"]):
        pool.append(_attrs("VALVE", subtype=st, size=_g(sz), cls=cl, spec=sp))
    for st, sz, sch, ln, sp in itertools.product(SUBTYPES["PIPE"], SIZES, SCHEDULES, (20, 40), SPECS["PIPE"]):
        pool.append(_attrs("PIPE", subtype=st, size=_g(sz), sch=sch, length=ln, spec=sp))
    for st, sz, sch, sp in itertools.product(SUBTYPES["FITTING"], SIZES, SCHEDULES, SPECS["FITTING"]):
        pool.append(_attrs("FITTING", subtype=st, size=_g(sz), sch=sch, spec=sp))
    for th, dm, sp in itertools.product(PLATE_THICK, PLATE_DIMS, SPECS["PLATE"]):
        pool.append(_attrs("PLATE", size=_g(th), dims=dm, spec=sp))
    for st, d, ln, sp in itertools.product(SUBTYPES["BOLTING"], BOLT_DIA, BOLT_LEN, SPECS["BOLTING"]):
        pool.append(_attrs("BOLTING", subtype=st, size=_g(d), length=_g(ln), spec=sp))
    for st, sz, cl in itertools.product(SUBTYPES["GASKET"], SIZES, CLASSES):
        pool.append(_attrs("GASKET", subtype=st, size=_g(sz), cls=cl))
    return pool


def fab_pool(rng, n: int) -> list[dict[str, str]]:
    dwgs = rng.sample(range(100000, 999999), n)
    subs = list(SUBTYPES["FABRICATION"])
    return [_attrs("FABRICATION", subtype=rng.choice(subs), dwg=d, rev=rng.choice("ABCD")) for d in dwgs]


def build_universe(rng, n_canon: int) -> list[dict[str, str]]:
    pool = non_fab_pool()
    rng.shuffle(pool)
    n_non = min(len(pool), round(n_canon * 0.6))
    items = pool[:n_non] + fab_pool(rng, n_canon - n_non)
    rng.shuffle(items)
    for i, it in enumerate(items):
        it["canon_id"] = f"I{i:06d}"
        base = BASE_COST[it["category"]]
        size = float(it["size"]) if it["size"] else 4.0
        factor = 1 + size / 4 if it["category"] != "FABRICATION" else rng.uniform(0.2, 14)
        it["base_cost"] = f"{base * factor * rng.uniform(0.8, 1.3):.4f}"
    return items


# ------------------------------------------------------------------ rendering


def _size_txt(v: str, rng, bu: str) -> str:
    f = float(v)
    r = rng.random()
    if f in FRACTIONS and r < 0.35:
        base = FRACTIONS[f]
        return rng.choice([f"{base}IN", f'{base}"', f"{base} IN"])
    one_dec = f"{f:.1f}" if abs(f * 10 - round(f * 10)) < 1e-9 else v   # never lose precision (1.25 stays 1.25)
    forms = [f"{v}IN", f'{v}"', f"{v} IN", f"{v}-INCH"] if bu == "BU1" else [f"{v} in", f'{v}"', f"{one_dec} in", f"{v} inch"]
    return rng.choice(forms)


def _class_txt(c: str, rng, bu: str) -> str:
    return rng.choice([f"{c}#", f"CL{c}", f"CLASS {c}", f"{c}LB"] if bu == "BU1" else [f"Cl {c}", f"Class {c}", f"{c}#", f"CL{c}"])


def _sch_txt(s: str, rng) -> str:
    return rng.choice([f"SCH {s}", f"SCH{s}", f"SCH-{s}", f"SCHEDULE {s}"])


def _spec_txt(spec: str, rng) -> str:
    base, grade = spec_parts(spec)
    if grade:
        return rng.choice([f"SA-{base} Gr {grade}", f"SA{base}-{grade}", f"A{base} GR.{grade}", f"ASTM A{base}-{grade}"])
    return rng.choice([f"SA-{base}", f"A{base}", f"ASTM A{base}"])


def _subtype_txt(category: str, subtype: str, rng, bu: str) -> str:
    syns = SUBTYPES[category].get(subtype, [subtype])
    return rng.choice(syns) if bu == "BU1" else max(syns, key=len)


def render_description(a: dict[str, str], bu: str, rng) -> str:
    """Render canonical attributes as a free-text legacy description in the BU's house style."""
    cat = a["category"]
    parts: list[str] = []
    if NOUN[cat]:
        parts.append(NOUN[cat])
    if a["subtype"]:
        parts.append(_subtype_txt(cat, a["subtype"], rng, bu))
    if cat == "FABRICATION":
        parts.append(rng.choice([f"DWG-{a['dwg']}", f"DWG {a['dwg']}", f"DWG#{a['dwg']}"]))
        parts.append(rng.choice([f"REV {a['rev']}", f"REV.{a['rev']}"]))
    if a["size"] and cat != "FABRICATION":
        parts.append(_size_txt(a["size"], rng, bu))
    if a["dims"]:
        parts.append(a["dims"] if rng.random() < 0.5 else a["dims"].replace("X", " X "))
    if a["sch"]:
        parts.append(_sch_txt(a["sch"], rng))
    if a["cls"]:
        parts.append(_class_txt(a["cls"], rng, bu))
    if a["length"]:
        if cat == "PIPE":
            parts.append(rng.choice([f"{a['length']}FT", f"{a['length']} FT"]))
        else:
            parts.append(rng.choice([f"{a['length']}LG", f"{a['length']} IN LG"]))
    if a["spec"]:
        parts.append(_spec_txt(a["spec"], rng))
    if bu == "BU1":
        return " ".join(parts).upper().replace("GR.", "GR.")
    text = ", ".join(parts)
    return text.title().replace('"', '"') if rng.random() < 0.5 else text
