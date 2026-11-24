"""Silver: BOM validation. Circular structures are found with a recursive SQL CTE (sql/bom_cycles.sql);
defective lines go to quarantine_bom_defects with an actionable reason, clean lines are mapped to enterprise parts."""
from __future__ import annotations

from collections import defaultdict

from .config import BUS
from .context import RunContext
from .issues import info
from .mapping import FIELD_MAP
from .money import parse_decimal
from .textnorm import clean_code

LINE_COLS = {"parent_part_no": "TEXT", "component_part_no": "TEXT", "line_seq": "BIGINT", "qty": "TEXT", "scrap_pct": "TEXT",
             "source_bu": "TEXT", "source_row": "BIGINT"}
QUAR_COLS = {"bu": "TEXT", "source_row": "BIGINT", "parent_code": "TEXT", "component_code": "TEXT", "defect_code": "TEXT",
             "severity": "TEXT", "owner": "TEXT", "detail": "TEXT", "recommended_action": "TEXT"}
PRECEDENCE = ["BOM_DUPLICATE_LINE", "BOM_SELF_REFERENCE", "BOM_CIRCULAR", "BOM_ORPHAN_PARENT", "BOM_ORPHAN_COMPONENT",
              "BOM_INVALID_QTY", "BOM_ITEM_QUARANTINED"]


def build(ctx: RunContext) -> None:
    db = ctx.db
    lines: list[dict] = []
    item_codes = {bu: {c for (b, c) in ctx.item_map if b == bu} for bu in BUS}
    for bu in BUS:
        fm = FIELD_MAP[(bu, "bom")]
        seen: set[tuple] = set()
        for r in ctx.rows(bu, "bom"):
            p, c, seq = clean_code(r[fm["parent"]]), clean_code(r[fm["comp"]]), clean_code(r[fm["seq"]])
            if r["_excl"]:
                ctx.excluded("bom", bu, r, f"{p}>{c}")
                continue
            qty = parse_decimal(r[fm["qty"]])
            flags: dict[str, str] = {}
            key = (p, c, seq)
            if key in seen:
                flags["BOM_DUPLICATE_LINE"] = "same parent/component/sequence appears earlier"
            seen.add(key)
            if p == c and p:
                flags["BOM_SELF_REFERENCE"] = f"{p} lists itself"
            if p not in item_codes[bu]:
                flags["BOM_ORPHAN_PARENT"] = f"parent {p!r} not in {bu} item master"
            if c not in item_codes[bu]:
                flags["BOM_ORPHAN_COMPONENT"] = f"component {c!r} not in {bu} item master"
            if qty is None or qty <= 0:
                flags["BOM_INVALID_QTY"] = f"qty per = {r[fm['qty']]!r}"
            lines.append(dict(bu=bu, row=r["_row"], parent=p, comp=c, seq=seq, qty=qty, scrap=r[fm["scrap"]], flags=flags))

    edges = [{"bu": l["bu"], "source_row": l["row"], "parent_code": l["parent"], "comp_code": l["comp"]}
             for l in lines if "BOM_SELF_REFERENCE" not in l["flags"] and "BOM_ORPHAN_PARENT" not in l["flags"]
             and "BOM_ORPHAN_COMPONENT" not in l["flags"] and "BOM_DUPLICATE_LINE" not in l["flags"]]
    db.write_table("stg_bom_edges", {"bu": "TEXT", "source_row": "BIGINT", "parent_code": "TEXT", "comp_code": "TEXT"}, edges)
    cyc = db.query((ctx.paths.root / "sql" / "bom_cycles.sql").read_text())
    cyc_map = {(c["bu"], c["source_row"]): c["cycle_path"] for c in cyc}
    for l in lines:
        if (l["bu"], l["row"]) in cyc_map:
            path = cyc_map[(l["bu"], l["row"])].strip("|").replace("|", " > ")
            l["flags"]["BOM_CIRCULAR"] = f"loop: {l['parent']} > {l['comp']} ... {path}"

    good, quarantine = [], []
    for l in lines:
        bu = l["bu"]
        pi, ci = ctx.item_map.get((bu, l["parent"])), ctx.item_map.get((bu, l["comp"]))
        if not l["flags"]:
            for side, itm, code in (("parent", pi, l["parent"]), ("component", ci, l["comp"])):
                if itm and itm["status"] != "LOADED":
                    l["flags"]["BOM_ITEM_QUARANTINED"] = f"{side} item {code} is quarantined"
        code = next((c for c in PRECEDENCE if c in l["flags"]), None)
        key = f"{l['parent']}>{l['comp']}"
        if code:
            ctx.log("bom", bu, l["row"], key, "QUARANTINED", code, detail=l["flags"][code])
            quarantine.append({"bu": bu, "source_row": l["row"], "parent_code": l["parent"], "component_code": l["comp"],
                               "defect_code": code, "severity": info(code)["severity"], "owner": "Engineering",
                               "detail": l["flags"][code], "recommended_action": info(code)["action"]})
        else:
            good.append(l)

    # one BOM per enterprise parent: the surviving record's BU wins, other BU's structure is superseded
    surv_bu = {r["enterprise_part_no"]: r["bu"] for r in db.query("SELECT enterprise_part_no, bu FROM silver_item_xref WHERE is_survivor = 1")}
    by_parent: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for l in good:
        l["ent_parent"], l["ent_comp"] = ctx.item_map[(l["bu"], l["parent"])]["ent"], ctx.item_map[(l["bu"], l["comp"])]["ent"]
        by_parent[l["ent_parent"]][l["bu"]].append(l)
    out = []
    for parent, bus in sorted(by_parent.items()):
        chosen = surv_bu.get(parent) if surv_bu.get(parent) in bus else sorted(bus)[0]
        seq = 0
        for l in sorted(bus[chosen], key=lambda x: (x["seq"].zfill(6), x["row"])):
            seq += 10
            ctx.log("bom", l["bu"], l["row"], f"{l['parent']}>{l['comp']}", "LOADED", "", f"{parent}/{seq}")
            out.append({"parent_part_no": parent, "component_part_no": l["ent_comp"], "line_seq": seq,
                        "qty": format(l["qty"].normalize(), "f"), "scrap_pct": l["scrap"], "source_bu": chosen, "source_row": l["row"]})
        for other, ls in bus.items():
            if other != chosen:
                for l in ls:
                    ctx.log("bom", other, l["row"], f"{l['parent']}>{l['comp']}", "CONSOLIDATED", "BOM_SUPERSEDED_BY_SURVIVOR_BU",
                            parent, detail=f"BOM of {parent} taken from {chosen}")
    db.write_table("silver_bom_line", LINE_COLS, out)
    db.write_table("quarantine_bom_defects", QUAR_COLS, quarantine)
