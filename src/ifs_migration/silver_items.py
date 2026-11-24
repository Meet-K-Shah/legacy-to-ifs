"""Silver: item standardisation, attribute-based duplicate detection, enterprise part numbers and XREF."""
from __future__ import annotations

from collections import defaultdict

from .config import BUS, PART_PREFIX
from .context import RunContext
from .itemspec import item_key, key_complete, parse_item_description, standard_description
from .mapping import FIELD_MAP
from .money import parse_decimal
from .textnorm import clean_code, clean_text

GOLDEN_COLS = {"part_no": "TEXT", "description": "TEXT", "uom": "TEXT", "category": "TEXT", "subtype": "TEXT",
               "size_in": "TEXT", "material_spec": "TEXT", "class_rating": "TEXT", "schedule": "TEXT", "drawing_no": "TEXT",
               "revision": "TEXT", "weight": "TEXT", "std_unit_cost": "TEXT", "make_buy": "TEXT", "source_bus": "TEXT",
               "member_count": "BIGINT", "legacy_sources": "TEXT", "attr_key": "TEXT"}
XREF_COLS = {"enterprise_part_no": "TEXT", "bu": "TEXT", "legacy_code": "TEXT", "legacy_code_raw": "TEXT", "source_row": "BIGINT",
             "match_rule": "TEXT", "is_survivor": "BIGINT", "status": "TEXT", "cluster_size": "BIGINT", "defect_code": "TEXT"}


def _score(rec) -> int:
    return sum(1 for k in ("desc", "long_desc", "weight", "cost", "drawing", "rev") if rec[k])


def build(ctx: RunContext) -> None:
    valid, xref, quarantined = [], [], []
    for bu in BUS:
        fm = FIELD_MAP[(bu, "item")]
        g = lambda r, k: (r.get(fm[k]) if fm.get(k) else "") or ""  # noqa: E731
        seen: set[str] = set()
        for r in ctx.rows(bu, "item"):
            code, raw_code = clean_code(g(r, "code")), g(r, "code")
            if r["_excl"]:
                ctx.excluded("item", bu, r, code)
                xref.append(dict(enterprise_part_no="", bu=bu, legacy_code=code, legacy_code_raw=raw_code, source_row=r["_row"],
                                 match_rule="", is_survivor=0, status="EXCLUDED", cluster_size=0, defect_code="BUSINESS_DECISION"))
                continue
            desc, cat = clean_text(g(r, "desc")), ctx.cat_map.get((bu, clean_code(g(r, "cat"))))
            uom = ctx.uom_map.get(clean_code(g(r, "uom")))
            reason = None
            if not code:
                reason = "ITEM_NULL_KEY"
            elif code in seen:
                reason = "ITEM_DUP_CODE"
            elif not desc:
                reason = "ITEM_NO_DESC"
            elif cat is None:
                reason = "ITEM_UNKNOWN_CATEGORY"
            elif uom is None:
                reason = "ITEM_INVALID_UOM"
            if code:
                seen.add(code)
            if reason:
                ctx.log("item", bu, r["_row"], code, "QUARANTINED", reason, detail=f"{raw_code!r} / {desc[:60]}")
                xref.append(dict(enterprise_part_no="", bu=bu, legacy_code=code, legacy_code_raw=raw_code, source_row=r["_row"],
                                 match_rule="", is_survivor=0, status="QUARANTINED", cluster_size=0, defect_code=reason))
                ctx.item_map[(bu, code)] = ctx.item_map.get((bu, code)) or {"status": "QUARANTINED", "ent": ""}
                continue
            attrs = parse_item_description(cat, desc)
            cost = parse_decimal(g(r, "cost"))
            weight = parse_decimal(g(r, "weight"))
            rec = dict(bu=bu, row=r["_row"], code=code, raw_code=raw_code, desc=desc, long_desc=clean_text(g(r, "long_desc")),
                       uom=uom, cat=cat, attrs=attrs, drawing=clean_text(g(r, "drawing")), rev=clean_text(g(r, "rev")),
                       cost=f"{cost:.4f}" if cost is not None else "", weight=f"{weight:.2f}" if weight is not None else "",
                       make_buy={"M": "MAKE", "P": "BUY", "B": "BUY"}.get(clean_code(g(r, "make_buy")), ""))
            rec["key"] = item_key(attrs) if key_complete(attrs) else f"{bu}|{code}"
            rec["by_attrs"] = key_complete(attrs)
            valid.append(rec)

    clusters: dict[str, list[dict]] = defaultdict(list)
    for rec in valid:
        clusters[rec["key"]].append(rec)
    keys = sorted(clusters)
    ids = ctx.ids.assign("item", [[k] for k in keys])
    golden = []
    for key, num in zip(keys, ids):
        members = sorted(clusters[key], key=lambda m: (-_score(m), m["bu"], m["row"]))
        s = members[0]
        part_no = f"{PART_PREFIX}{num:06d}"
        a = s["attrs"]
        uoms = {m["uom"] for m in members}
        if len(uoms) > 1:
            ctx.notes.append(f"UOM conflict across duplicates of {part_no}: {sorted(uoms)} (survivor's UOM used)")
        golden.append({"part_no": part_no, "description": standard_description(a) if s["by_attrs"] else s["desc"],
                       "uom": s["uom"], "category": s["cat"], "subtype": a["subtype"], "size_in": a["size"],
                       "material_spec": a["spec"], "class_rating": a["cls"], "schedule": a["sch"],
                       "drawing_no": a["dwg"] or s["drawing"].replace("DWG-", ""), "revision": a["rev"] or s["rev"],
                       "weight": s["weight"], "std_unit_cost": s["cost"], "make_buy": s["make_buy"],
                       "source_bus": "|".join(sorted({m["bu"] for m in members})), "member_count": len(members),
                       "legacy_sources": "|".join(f"{m['bu']}:{m['code']}" for m in sorted(members, key=lambda m: (m["bu"], m["row"]))),
                       "attr_key": key if s["by_attrs"] else ""})
        for i, m in enumerate(members):
            surv = i == 0
            xref.append(dict(enterprise_part_no=part_no, bu=m["bu"], legacy_code=m["code"], legacy_code_raw=m["raw_code"],
                             source_row=m["row"], match_rule="ATTRIBUTE_KEY" if m["by_attrs"] else "UNIQUE", is_survivor=int(surv),
                             status="LOADED" if surv else "CONSOLIDATED", cluster_size=len(members), defect_code=""))
            ctx.log("item", m["bu"], m["row"], m["code"], "LOADED" if surv else "CONSOLIDATED",
                    "" if surv else "DUPLICATE_MERGED", part_no, detail=f"cluster of {len(members)}")
            ctx.item_map[(m["bu"], m["code"])] = {"status": "LOADED", "ent": part_no}
    ctx.db.write_table("silver_item_golden", GOLDEN_COLS, golden)
    ctx.db.write_table("silver_item_xref", XREF_COLS, xref)
