"""Silver: customer & vendor entity resolution (rapidfuzz token-sort + tax ID + address), steward review
queue, survivorship, golden IDs, XREF, and the bill-to / ship-to address hierarchy."""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from .config import (BUS, CUSTOMER_PREFIX, MATCH_ADDR_SUPPORT, MATCH_AUTO_NAME, MATCH_REVIEW_NAME, VENDOR_PREFIX)
from .context import RunContext
from .fuzzy import token_sort_ratio
from .mapping import FIELD_MAP
from .textnorm import (clean_code, clean_text, normalize_address, normalize_company_name, normalize_taxid, normalize_zip,
                       parse_date)

GOLDEN_COLS = {"enterprise_id": "TEXT", "name": "TEXT", "country": "TEXT", "tax_id": "TEXT", "address1": "TEXT",
               "address2": "TEXT", "city": "TEXT", "state": "TEXT", "zip": "TEXT", "payment_terms": "TEXT", "contact": "TEXT",
               "phone": "TEXT", "source_bus": "TEXT", "member_count": "BIGINT", "legacy_sources": "TEXT"}
XREF_COLS = {"enterprise_id": "TEXT", "bu": "TEXT", "legacy_code": "TEXT", "source_row": "BIGINT", "match_rule": "TEXT",
             "confidence": "DOUBLE", "is_survivor": "BIGINT", "status": "TEXT", "cluster_size": "BIGINT", "defect_code": "TEXT"}
REVIEW_COLS = {"entity": "TEXT", "bu_a": "TEXT", "code_a": "TEXT", "name_a": "TEXT", "bu_b": "TEXT", "code_b": "TEXT",
               "name_b": "TEXT", "name_score": "DOUBLE", "address_score": "DOUBLE", "reason": "TEXT"}
_COUNTRY = {"US": "US", "USA": "US", "UNITED STATES": "US", "UNITED STATES OF AMERICA": "US"}


def classify(a: dict, b: dict) -> tuple[str, str, float, float]:
    """Return (AUTO|REVIEW|NONE, rule, name_score, address_score) for a candidate pair."""
    name_s = token_sort_ratio(a["nname"], b["nname"])
    addr_s = token_sort_ratio(a["naddr"], b["naddr"])
    ta, tb = a["tax"], b["tax"]
    if ta and ta == tb and name_s >= 60:
        return "AUTO", "TAX_ID_MATCH", name_s, addr_s
    if ta and tb and ta != tb:                                        # hard negative: different legal entities
        if name_s >= 97 and addr_s >= 90:
            return "REVIEW", "TAX_ID_CONFLICT_SAME_NAME_ADDRESS", name_s, addr_s
        return "NONE", "", name_s, addr_s
    support = addr_s >= MATCH_ADDR_SUPPORT or (a["zip5"] and a["zip5"] == b["zip5"])
    if name_s >= MATCH_AUTO_NAME and support:
        return "AUTO", "NAME_ADDRESS", name_s, addr_s
    if name_s >= MATCH_REVIEW_NAME and support:
        return "REVIEW", "NAME_NEAR_MATCH", name_s, addr_s
    return "NONE", "", name_s, addr_s


def candidate_pairs(recs: list[dict]):
    """Blocking: pairs must share a tax ID, a name prefix, or a ZIP; avoids the full O(n^2) comparison."""
    blocks: dict[tuple, list[int]] = defaultdict(list)
    for i, r in enumerate(recs):
        if r["tax"]:
            blocks[("T", r["tax"])].append(i)
        blocks[("N", r["nname"][:5])].append(i)
        if r["zip5"]:
            blocks[("Z", r["zip5"])].append(i)
    pairs = set()
    for idx in blocks.values():
        if len(idx) > 600:
            continue
        for a, b in combinations(sorted(idx), 2):
            pairs.add((a, b))
    return sorted(pairs)


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def _fmt_tax(t: str) -> str:
    return f"{t[:2]}-{t[2:]}" if len(t) == 9 else ""


def build(ctx: RunContext, kind: str) -> None:
    prefix = CUSTOMER_PREFIX if kind == "customer" else VENDOR_PREFIX
    bad_code = "CUST_NO_NAME" if kind == "customer" else "VEND_NO_NAME"
    recs: list[dict] = []
    shipto_raw: list[tuple[str, dict]] = []
    for bu in BUS:
        fm = FIELD_MAP[(bu, kind)]
        g = lambda r, k: (r.get(fm[k]) if fm.get(k) else "") or ""  # noqa: E731
        for r in ctx.rows(bu, kind):
            code = clean_code(g(r, "code"))
            if kind == "customer" and bu == "BU2":
                try:
                    seq = int(clean_text(g(r, "seq")) or 0)
                except ValueError:
                    seq = 0
                if seq > 0:
                    shipto_raw.append((bu, r))
                    continue
            if r["_excl"]:
                ctx.excluded(kind, bu, r, code)
                continue
            name = clean_text(g(r, "name"))
            if not name:
                ctx.log(kind, bu, r["_row"], code, "QUARANTINED", bad_code, detail="blank name")
                ctx.party_map[(kind, bu, code)] = {"status": "QUARANTINED", "ent": ""}
                continue
            country = _COUNTRY.get(clean_code(g(r, "country")), clean_code(g(r, "country")))
            a1, a2 = clean_text(g(r, "addr1")), clean_text(g(r, "addr2"))
            city, state, zip5 = clean_text(g(r, "city")), clean_code(g(r, "state")), normalize_zip(g(r, "zip"))
            rec = dict(bu=bu, row=r["_row"], code=code, name=name, nname=normalize_company_name(name), country=country,
                       tax=normalize_taxid(g(r, "tax")), addr1=a1, addr2=a2, city=city, state=state, zip5=zip5,
                       zip=clean_text(g(r, "zip")), contact=clean_text(g(r, "contact")), phone=clean_text(g(r, "phone")),
                       terms=clean_text(g(r, "terms")), last=parse_date(g(r, "last_activity")) or "",
                       naddr=normalize_address(a1, a2, city, state, zip5))
            rec["score"] = sum(1 for k in ("name", "country", "tax", "addr1", "city", "state", "zip5", "contact", "phone", "terms") if rec[k])
            recs.append(rec)
    if kind == "customer":
        for bu, r in shipto_raw:
            pass  # handled below with the BU1 ship-to file

    uf = _UF(len(recs))
    review: list[tuple[int, int, str, float, float]] = []
    pos = {(r["bu"], r["code"]): i for i, r in enumerate(recs)}
    merged_by_decision = 0
    decided_same, decided_keys = set(), set()
    for d in ctx.fixes.decisions:
        if d["entity"] != kind:
            continue
        ka, kb = (d["a"][0], clean_code(d["a"][1])), (d["b"][0], clean_code(d["b"][1]))
        decided_keys.add(frozenset((ka, kb)))
        if d["decision"] == "MERGE" and ka in pos and kb in pos:
            uf.union(pos[ka], pos[kb])
            merged_by_decision += 1
    auto_rule: dict[tuple[int, int], tuple[str, float]] = {}
    for i, j in candidate_pairs(recs):
        cls, rule, ns, as_ = classify(recs[i], recs[j])
        if cls == "AUTO":
            uf.union(i, j)
            auto_rule[(i, j)] = (rule, ns)
        elif cls == "REVIEW":
            review.append((i, j, rule, ns, as_))
    review_rows = []
    for i, j, rule, ns, as_ in review:
        if uf.find(i) == uf.find(j):
            continue
        if frozenset(((recs[i]["bu"], recs[i]["code"]), (recs[j]["bu"], recs[j]["code"]))) in decided_keys:
            continue
        a, b = recs[i], recs[j]
        review_rows.append({"entity": kind, "bu_a": a["bu"], "code_a": a["code"], "name_a": a["name"], "bu_b": b["bu"],
                            "code_b": b["code"], "name_b": b["name"], "name_score": round(ns, 1), "address_score": round(as_, 1), "reason": rule})
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(recs)):
        groups[uf.find(i)].append(i)
    clusters = list(groups.values())
    member_keys = [[f"{recs[i]['bu']}|{recs[i]['code']}" for i in c] for c in clusters]
    ids = ctx.ids.assign(kind, member_keys)
    golden, xref = [], []
    for c, num in sorted(zip(clusters, ids), key=lambda t: t[1]):
        members = sorted((recs[i] for i in c), key=lambda m: (-m["score"], [-ord(ch) for ch in m["last"]], m["bu"], m["row"]))
        s = members[0]
        ent = f"{prefix}{num:04d}"

        def first(field, members=members):
            return next((m[field] for m in members if m[field]), "")
        golden.append({"enterprise_id": ent, "name": s["name"], "country": first("country") or "US", "tax_id": _fmt_tax(first("tax")),
                       "address1": first("addr1"), "address2": s["addr2"], "city": first("city"), "state": first("state"),
                       "zip": first("zip"), "payment_terms": first("terms"), "contact": first("contact"), "phone": first("phone"),
                       "source_bus": "|".join(sorted({m["bu"] for m in members})), "member_count": len(members),
                       "legacy_sources": "|".join(f"{m['bu']}:{m['code']}" for m in sorted(members, key=lambda m: (m["bu"], m["row"])))})
        for k, m in enumerate(members):
            surv = k == 0
            rule = "SURVIVOR" if surv else "TAX_ID_OR_NAME_ADDRESS_OR_STEWARD"
            xref.append({"enterprise_id": ent, "bu": m["bu"], "legacy_code": m["code"], "source_row": m["row"], "match_rule": rule,
                         "confidence": 100.0 if len(members) == 1 else 95.0, "is_survivor": int(surv),
                         "status": "LOADED" if surv else "CONSOLIDATED", "cluster_size": len(members), "defect_code": ""})
            ctx.log(kind, m["bu"], m["row"], m["code"], "LOADED" if surv else "CONSOLIDATED", "" if surv else "DUPLICATE_MERGED",
                    ent, detail=f"cluster of {len(members)}")
            ctx.party_map[(kind, m["bu"], m["code"])] = {"status": "LOADED", "ent": ent}
    ctx.db.write_table(f"silver_{kind}_golden", GOLDEN_COLS, golden)
    ctx.db.write_table(f"silver_{kind}_xref", XREF_COLS, xref)
    ctx.review_pairs.extend(review_rows)
    ctx.notes.append(f"{kind}: {len(recs)} valid records -> {len(golden)} golden; {len(review_rows)} pairs in steward queue; "
                     f"{merged_by_decision} steward MERGE decisions applied")
    if kind == "customer":
        _shipto(ctx, shipto_raw)


def _shipto(ctx: RunContext, bu2_rows: list[tuple[str, dict]]) -> None:
    golden = {r["enterprise_id"]: r for r in ctx.db.query("SELECT * FROM silver_customer_golden")}
    out = [{"customer_id": ent, "address_id": "BILL-TO", "address_type": "BILL_TO", "name": g["name"], "address1": g["address1"],
            "city": g["city"], "state": g["state"], "zip": g["zip"], "country": g["country"], "source_bu": g["source_bus"]}
           for ent, g in sorted(golden.items())]
    inputs = [("BU1", r) for r in ctx.rows("BU1", "shipto")] + bu2_rows
    for bu, r in inputs:
        tkey = "shipto" if bu == "BU1" else "customer"
        fm = FIELD_MAP[(bu, "shipto")] if bu == "BU1" else None
        if bu == "BU1":
            code, ship, name = clean_code(r[fm["code"]]), clean_code(r[fm["ship_code"]]), clean_text(r[fm["name"]])
            a1, city, st, zp, ctry = (clean_text(r[fm[k]]) for k in ("addr1", "city", "state", "zip", "country"))
        else:
            cm = FIELD_MAP[("BU2", "customer")]
            code, ship, name = clean_code(r[cm["code"]]), clean_code(r[cm["seq"]]), clean_text(r[cm["name"]])
            a1, city, st, zp, ctry = (clean_text(r[cm[k]]) for k in ("addr1", "city", "state", "zip", "country"))
        key = f"{code}/{ship}"
        if r["_excl"]:
            ctx.excluded("customer_shipto", bu, r, key)
            continue
        parent = ctx.party_map.get(("customer", bu, code))
        reason = None
        if parent is None:
            reason = "SHIP_ORPHAN_CUSTOMER"
        elif parent["status"] != "LOADED":
            reason = "SHIP_CUSTOMER_QUARANTINED"
        elif not a1 and not city:
            reason = "SHIP_NO_ADDRESS"
        if reason:
            ctx.log("customer_shipto", bu, r["_row"], key, "QUARANTINED", reason, detail=name)
            continue
        ent = parent["ent"]
        ctx.log("customer_shipto", bu, r["_row"], key, "LOADED", "", ent)
        out.append({"customer_id": ent, "address_id": f"{bu}-{code}-{ship}", "address_type": "SHIP_TO", "name": name, "address1": a1,
                    "city": city, "state": clean_code(st), "zip": zp, "country": _COUNTRY.get(clean_code(ctry), clean_code(ctry) or "US"),
                    "source_bu": bu})
    cols = {k: "TEXT" for k in ("customer_id", "address_id", "address_type", "name", "address1", "city", "state", "zip", "country", "source_bu")}
    ctx.db.write_table("silver_customer_address", cols, out)
