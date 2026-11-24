"""Customer / vendor master generation: overlapping industrial entities with fuzzy name variants, address
noise, missing tax IDs, bill-to / ship-to hierarchies, within-BU duplicates and near-twin decoys that
must NOT be merged."""
from __future__ import annotations

from ..fuzzy import token_sort_ratio
from ..textnorm import normalize_company_name
from .common import Registry, Table, pick_indices

PREFIXES = ["Apex", "Summit", "Gulf Coast", "Lone Star", "Midwest", "Great Lakes", "Keystone", "Pioneer", "Titan",
            "Atlas", "Ironclad", "Bayou", "Prairie", "Cascade", "Heartland", "Frontier", "Liberty", "Patriot",
            "Sterling", "Cardinal", "Eagle", "Falcon", "Granite", "Harbor", "Meridian", "Northstar", "Oakridge",
            "Premier", "Redwood", "Silverline", "Triumph", "Union", "Vanguard", "Westfield", "Yellowstone",
            "Alamo", "Beacon", "Crescent", "Delta", "Evergreen", "Fortress", "Gateway", "Horizon", "Imperial",
            "Juniper", "Kingsley", "Landmark", "Monarch", "Nova", "Olympic", "Peninsula", "Quartz", "Ridgeway",
            "Stonebridge", "Tidewater", "Unity", "Valor", "Whitaker", "Zenith", "Bluewater", "Copperhead"]
CUST_MID = ["Piping", "Process", "Energy", "Chemical", "Petroleum", "Refining", "Pipeline", "Midstream", "Gas",
            "Power", "Industrial", "Terminals", "Fabrication", "Construction", "Engineering", "Marine"]
CUST_TAIL = ["Supply", "Systems", "Services", "Partners", "Group", "Holdings", "Solutions", "Technologies",
             "Operating", "Resources", "& Supply", "& Equipment", "& Service"]
VEND_MID = ["Steel", "Forge", "Flange", "Valve", "Pipe & Tube", "Alloy", "Metals", "Fasteners", "Fittings",
            "Castings", "Plate", "Gasket"]
VEND_TAIL = ["Supply", "Manufacturing", "Distributors", "Industries", "Works", "Mills", "Products", "& Supply",
             "& Equipment", "International", "Services"]
SUFFIXES = ["LLC", "Inc", "Corp", "Co", "Ltd", "LP"]
CITIES = [("Houston", "TX", "770"), ("Baton Rouge", "LA", "708"), ("Tulsa", "OK", "741"), ("Cleveland", "OH", "441"),
          ("Pittsburgh", "PA", "152"), ("Chicago", "IL", "606"), ("Denver", "CO", "802"), ("Lake Charles", "LA", "706"),
          ("Beaumont", "TX", "777"), ("Pasadena", "TX", "775"), ("Midland", "TX", "797"), ("Corpus Christi", "TX", "784"),
          ("Mobile", "AL", "366"), ("Louisville", "KY", "402"), ("Charleston", "WV", "253"), ("Wichita", "KS", "672"),
          ("Casper", "WY", "826"), ("Bakersfield", "CA", "933"), ("Long Beach", "CA", "908"), ("Newark", "NJ", "071"),
          ("Wilmington", "DE", "198"), ("Toledo", "OH", "436"), ("Akron", "OH", "443"), ("Canton", "OH", "447"),
          ("Detroit", "MI", "482"), ("Gary", "IN", "463"), ("Cincinnati", "OH", "452"), ("Columbus", "OH", "432"),
          ("Indianapolis", "IN", "462"), ("St. Louis", "MO", "631"), ("Kansas City", "MO", "641"), ("Omaha", "NE", "681"),
          ("Minneapolis", "MN", "554"), ("Salt Lake City", "UT", "841"), ("Phoenix", "AZ", "850"),
          ("Albuquerque", "NM", "871"), ("Lafayette", "LA", "705"), ("Shreveport", "LA", "711"), ("Jackson", "MS", "392"),
          ("Birmingham", "AL", "352"), ("Atlanta", "GA", "303"), ("Charlotte", "NC", "282"), ("Richmond", "VA", "232"),
          ("Baltimore", "MD", "212"), ("Buffalo", "NY", "142"), ("Erie", "PA", "165"), ("Allentown", "PA", "181"),
          ("Oklahoma City", "OK", "731"), ("Little Rock", "AR", "722"), ("Memphis", "TN", "381"),
          ("Nashville", "TN", "372"), ("Tampa", "FL", "336"), ("Jacksonville", "FL", "322"), ("Seattle", "WA", "981"),
          ("Portland", "OR", "972"), ("Billings", "MT", "591"), ("Fargo", "ND", "581"), ("Boise", "ID", "837")]
STREET_NAMES = ["Industrial", "Commerce", "Refinery", "Harbor", "Pipeline", "Main", "Market", "Gulf", "Railroad",
                "Energy", "Steel", "Foundry", "Oak", "Elm", "Enterprise", "Chemical"]
STREET_TYPES = ["Street", "Road", "Avenue", "Boulevard", "Drive", "Highway", "Parkway"]
STREET_ABBR = {"Street": "St", "Road": "Rd", "Avenue": "Ave", "Boulevard": "Blvd", "Drive": "Dr", "Highway": "Hwy",
               "Parkway": "Pkwy"}
FIRST = ["James", "Maria", "Robert", "Linda", "Michael", "Susan", "David", "Karen", "John", "Patricia", "Daniel", "Nancy"]
LAST = ["Garcia", "Miller", "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Clark"]
TERMS = ["NET30", "NET45", "NET60", "2/10N30", "COD"]
ABBR_OUT = {"Manufacturing": "Mfg", "International": "Intl", "Services": "Svcs", "Equipment": "Equip",
            "Engineering": "Eng", "Products": "Prod", "Supply": "Sply", "Industrial": "Ind"}

COLS = {
    ("BU1", "customer"): ["Customer", "Name", "ShortName", "Contact", "Telephone", "Addr1", "Addr2", "City", "State",
                          "PostalCode", "Country", "TaxNumber", "TermsCode", "LastActivityDate"],
    ("BU1", "vendor"): ["Supplier", "SupplierName", "ShortName", "Contact", "Telephone", "Addr1", "Addr2", "City", "State",
                        "PostalCode", "Country", "TaxNumber", "TermsCode", "LastActivityDate"],
    ("BU1", "shipto"): ["Customer", "ShipToCode", "ShipName", "Addr1", "City", "State", "PostalCode", "Country"],
    ("BU2", "customer"): ["cust_num", "cust_seq", "name", "contact", "phone", "addr_1", "addr_2", "city", "state", "zip",
                          "country", "tax_reg_num", "terms_code", "last_activity"],
    ("BU2", "vendor"): ["vend_num", "name", "contact", "phone", "addr_1", "addr_2", "city", "state", "zip", "country",
                        "tax_reg_num", "terms_code", "last_activity"],
}
FILES = {("BU1", "customer"): "ArCustomer.csv", ("BU1", "vendor"): "ApSupplier.csv", ("BU1", "shipto"): "ArShipToAddress.csv",
         ("BU2", "customer"): "custaddr_mst.csv", ("BU2", "vendor"): "vendaddr_mst.csv"}


# ---------------------------------------------------------------- entity + perturbation helpers


def _address(rng) -> tuple[str, str, str, str, str]:
    city, state, z3 = rng.choice(CITIES)
    line1 = f"{rng.randint(100, 9899)} {rng.choice(STREET_NAMES)} {rng.choice(STREET_TYPES)}"
    line2 = rng.choice(["", "", "", f"Suite {rng.randint(100, 900)}", f"Bldg {rng.randint(1, 9)}", f"Floor {rng.randint(2, 12)}"])
    return line1, line2, city, state, f"{z3}{rng.randint(0, 99):02d}"


def _taxid(rng) -> str:
    return f"{rng.randint(10, 99)}-{rng.randint(1000000, 9999999)}"


def make_entity(rng, kind: str, used: set[str]) -> dict:
    mids, tails = (CUST_MID, CUST_TAIL) if kind == "customer" else (VEND_MID, VEND_TAIL)
    for _ in range(200):
        name = f"{rng.choice(PREFIXES)} {rng.choice(mids)} {rng.choice(tails)} {rng.choice(SUFFIXES)}"
        norm = normalize_company_name(name)
        if norm not in used:
            used.add(norm)
            break
    a1, a2, city, state, zip5 = _address(rng)
    return {"name": name, "addr1": a1, "addr2": a2, "city": city, "state": state, "zip": zip5, "taxid": _taxid(rng),
            "contact": f"{rng.choice(FIRST)} {rng.choice(LAST)}", "phone": f"({rng.randint(200, 989)}) 555-{rng.randint(1000, 9999)}",
            "terms": rng.choice(TERMS)}


def make_decoy(rng, base: dict, used: set[str]) -> dict:
    """A different legal entity with an almost identical name (different city/state and tax ID)."""
    dec = dict(base)
    name = base["name"]
    if "&" in name:
        name = name.replace("& ", "")
    else:
        toks = name.split()
        suffixes = [s for s in SUFFIXES if s != toks[-1]]
        toks[-1] = rng.choice(suffixes)
        name = " ".join(toks)
    dec["name"] = name
    while True:
        a1, a2, city, state, zip5 = _address(rng)
        if state != base["state"]:
            break
    dec.update(addr1=a1, addr2=a2, city=city, state=state, zip=zip5, taxid=_taxid(rng),
               contact=f"{rng.choice(FIRST)} {rng.choice(LAST)}")
    used.add(normalize_company_name(name))
    return dec


def _swap_suffix(name, rng):
    toks = name.split()
    base = toks[-1].strip(".,")
    if base.upper() in {"LLC", "INC", "CORP", "CO", "LTD", "LP", "INCORPORATED", "COMPANY"}:
        options = [s for s in ["LLC", "Inc.", "Incorporated", "Co.", "Corp.", "Company", ""] if s.strip(".").lower() != base.lower()]
        toks[-1] = rng.choice(options)
        return " ".join(t for t in toks if t)
    return f"{name} {rng.choice(['LLC', 'Inc.', 'Co.'])}"


def _amp(name, rng):
    return name.replace("&", "and") if "&" in name else name.replace(" and ", " & ")


def _case(name, rng):
    return rng.choice([name.upper(), name.replace(" Inc", ", Inc").replace(" LLC", ", LLC"), name.title()])


def _abbr(name, rng):
    for full, short in ABBR_OUT.items():
        if full in name:
            return name.replace(full, short, 1)
    return name


def _the(name, rng):
    return f"The {name}"


def _typo(name, rng):
    toks = name.split(" ")
    idxs = [i for i, t in enumerate(toks) if len(t) >= 5 and t.isalpha()]
    if not idxs:
        return name
    i = rng.choice(idxs)
    t = toks[i]
    j = rng.randrange(1, len(t) - 1)
    toks[i] = t[:j] + t[j + 1:] if rng.random() < 0.6 else t[:j] + t[j + 1] + t[j] + t[j + 2:]
    return " ".join(toks)


def perturb_name(name: str, rng, heavy: bool = False) -> str:
    """Light: formatting/abbreviation noise only (identical after normalisation). Heavy: add typos until the
    normalised similarity falls into the steward-review band (85-91)."""
    ops = [_swap_suffix, _amp, _case, _abbr, _the]
    out = name
    for op in rng.sample(ops, rng.choice([1, 2, 2])):
        out = op(out, rng)
    if heavy:
        target = normalize_company_name(name)
        for _ in range(10):
            if token_sort_ratio(target, normalize_company_name(out)) <= 90:
                break
            out = _typo(out, rng)
    return out if out != name else _swap_suffix(name, rng)


def perturb_address(ent: dict, rng, strength: float):
    a1, a2 = ent["addr1"], ent["addr2"]
    if rng.random() < strength:
        for full, ab in STREET_ABBR.items():
            a1 = a1.replace(full, ab)
        a2 = a2.replace("Suite", "Ste").replace("Floor", "Fl")
    if rng.random() < strength * 0.4:
        a1 = a1.upper()
    if a2 and rng.random() < strength * 0.5:
        a2 = ""
    zip5 = ent["zip"]
    zipv = f"{zip5}-{rng.randint(1000, 9999)}" if rng.random() < strength * 0.4 else zip5
    return a1, a2, zipv


# ---------------------------------------------------------------- record writers


def _fmt_date(rng, bu):
    y, m, d = rng.choice([2023, 2024, 2025, 2026]), rng.randint(1, 12), rng.randint(1, 28)
    return f"{y}-{m:02d}-{d:02d}" if bu == "BU1" else f"{m:02d}/{d:02d}/{y}"


def _code(bu, kind, n):
    if bu == "BU1":
        return f"{'C' if kind == 'customer' else 'V'}{n:05d}"
    return f"{n:7d}"          # Syteline right-justifies keys with leading spaces


def _country(rng, bu):
    return rng.choice(["US", "US", "USA"]) if bu == "BU1" else rng.choice(["USA", "USA", "United States"])


def _party_row(bu, kind, code, ent, name, rng, strength, with_tax: bool):
    a1, a2, zipv = perturb_address(ent, rng, strength)
    if rng.random() < 0.03:
        zipv = ""                                     # completeness defect (profiling only)
    tax = ""
    if with_tax:
        t = ent["taxid"]
        tax = t if rng.random() < 0.5 else t.replace("-", "")
    country = _country(rng, bu)
    if bu == "BU1":
        row = {"ShortName": normalize_company_name(name)[:10], "Contact": ent["contact"], "Telephone": ent["phone"],
               "Addr1": a1, "Addr2": a2, "City": ent["city"], "State": ent["state"], "PostalCode": zipv,
               "Country": country, "TaxNumber": tax, "TermsCode": ent["terms"], "LastActivityDate": _fmt_date(rng, bu)}
        if kind == "customer":
            row.update(Customer=code, Name=name)
        else:
            row.update(Supplier=code, SupplierName=name)
    else:
        row = {"name": name, "contact": ent["contact"], "phone": ent["phone"], "addr_1": a1, "addr_2": a2,
               "city": ent["city"], "state": ent["state"], "zip": zipv, "country": country, "tax_reg_num": tax,
               "terms_code": ent["terms"], "last_activity": _fmt_date(rng, bu)}
        if kind == "customer":
            row.update(cust_num=code, cust_seq="0")
        else:
            row.update(vend_num=code)
    return row


def build_parties(reg: Registry, rng, kind: str, scale: float) -> dict[str, dict]:
    """Returns {bu: {'table': Table, 'shipto': Table|None, 'codes': [raw codes of valid bill-to records],
    'entities': {raw code: entity id}}} and registers ground truth + defects."""
    n_per_bu = max(40, round(1500 * scale))
    shared = round(0.20 * n_per_bu)
    wdup = round(0.03 * n_per_bu)
    junk = max(1, round(0.004 * n_per_bu))
    unique_own = n_per_bu - shared - wdup - junk
    ndecoy = max(2, round(0.04 * unique_own))
    used: set[str] = set()

    ents: dict[str, dict] = {}
    seq = [0]

    def new_ent(maker):
        seq[0] += 1
        eid = f"{kind[:4].upper()}{seq[0]:05d}"
        e = maker()
        e["eid"] = eid
        ents[eid] = e
        return eid

    shared_ids = [new_ent(lambda: make_entity(rng, kind, used)) for _ in range(shared)]
    own = {"BU1": [], "BU2": []}
    for bu in ("BU1", "BU2"):
        own[bu] = [new_ent(lambda: make_entity(rng, kind, used)) for _ in range(unique_own)]
    decoy_of: dict[str, str] = {}
    for bu, other in (("BU1", "BU2"), ("BU2", "BU1")):
        bases = shared_ids + own[other]
        for k in range(ndecoy):
            base_id = bases[rng.randrange(len(bases))]
            if base_id in decoy_of or base_id in decoy_of.values():
                continue
            eid = own[bu][k]
            ents[eid] = {**make_decoy(rng, ents[base_id], used), "eid": eid}
            decoy_of[eid] = base_id
            reg.decoys.append((kind, eid, base_id))

    heavy_pairs = set(rng.sample(shared_ids, max(1, round(0.08 * len(shared_ids)))))
    out: dict[str, dict] = {}
    for bu in ("BU1", "BU2"):
        table = Table(reg, kind, bu, FILES[(bu, kind)], COLS[(bu, kind)])
        ship = Table(reg, "customer_shipto", bu, FILES[(bu, "shipto")], COLS[(bu, "shipto")]) if (kind == "customer" and bu == "BU1") else None
        entity_ids = shared_ids + own[bu]
        order = list(range(len(entity_ids)))
        rng.shuffle(order)
        records = []          # (code_number, eid, name)
        for num, i in enumerate(order, start=1):
            eid = entity_ids[i]
            ent = ents[eid]
            heavy = eid in heavy_pairs and bu == "BU2"
            name = ent["name"] if (bu == "BU1" or rng.random() < 0.15) and not heavy else perturb_name(ent["name"], rng, heavy)
            records.append((num * 3 + rng.randint(0, 2), eid, name, heavy))
        # within-BU duplicates: a second record for an existing (non-decoy) entity
        dup_src = rng.sample([r for r in records if r[1] not in decoy_of], wdup)
        for k, r in enumerate(dup_src):
            records.append((len(order) * 3 + 10 + k * 2, r[1], perturb_name(ents[r[1]]["name"], rng), False))
        rows = []
        for num, eid, name, heavy in records:
            ent = ents[eid]
            code = _code(bu, kind, num)
            strength = 0.3 if bu == "BU1" else 0.7
            with_tax = (not heavy) and rng.random() < 0.75
            row = table.add(_party_row(bu, kind, code, ent, name, rng, strength, with_tax))
            rows.append((row, eid, code))
            reg.entity_truth.append({"domain": kind, "bu": bu, "source_key": code.strip(), "entity_id": eid})
        # junk rows (blank names) -> quarantine
        key = {"customer": "Name" if bu == "BU1" else "name", "vendor": "SupplierName" if bu == "BU1" else "name"}[kind]
        code_col = {("BU1", "customer"): "Customer", ("BU1", "vendor"): "Supplier", ("BU2", "customer"): "cust_num",
                    ("BU2", "vendor"): "vend_num"}[(bu, kind)]
        for k in range(junk):
            n = 90000 + k
            row = table.add({code_col: _code(bu, kind, n), key: "", "Country": "US" if bu == "BU1" else "USA"} if bu == "BU1"
                            else {code_col: _code(bu, kind, n), key: "", "country": "USA", **({"cust_seq": "0"} if kind == "customer" else {})})
            table.defect(row, f"{'CUST' if kind == 'customer' else 'VEND'}_NO_NAME", "QUARANTINE",
                         "Blank name on legacy record",
                         {"exclude": True, "reason": "Inactive/test record approved for deletion by data owner"})
        # ship-to hierarchy (customers only)
        shipto_rows: list[dict] = []
        if kind == "customer":
            sh_table = ship if ship is not None else table
            for row, eid, code in rows:
                if rng.random() < 0.35:
                    for s in range(1, rng.randint(1, 3) + 1):
                        a1, _a2, city, state, zip5 = _address(rng)
                        sname = f"{ents[eid]['name']} - Plant {s}"
                        if bu == "BU1":
                            srow = sh_table.add({"Customer": code, "ShipToCode": f"S{s:02d}", "ShipName": sname, "Addr1": a1,
                                                 "City": city, "State": state, "PostalCode": zip5, "Country": "US"})
                        else:
                            srow = sh_table.add({"cust_num": code, "cust_seq": str(s), "name": sname, "contact": ents[eid]["contact"],
                                                 "phone": ents[eid]["phone"], "addr_1": a1, "addr_2": "", "city": city, "state": state,
                                                 "zip": zip5, "country": "USA", "tax_reg_num": "", "terms_code": "", "last_activity": _fmt_date(rng, bu)})
                        shipto_rows.append(srow)
            # orphan ship-tos (customer code does not exist)
            for k in pick_indices(rng, len(shipto_rows), 0.01):
                srow = shipto_rows[k]
                key_col = "Customer" if bu == "BU1" else "cust_num"
                orig = srow[key_col]
                srow[key_col] = _code(bu, "customer", 95000 + k)
                sh_table.defect(srow, "SHIP_ORPHAN_CUSTOMER", "QUARANTINE", "Ship-to references a customer that does not exist",
                                {"field": key_col, "new_value": orig}, domain="customer_shipto")
        # sort like a real export: by code (and ship-to sequence)
        if bu == "BU1":
            code_col_sort = code_col
            table.sort(key=lambda r: (r.get(code_col_sort, "").strip(),))
            if ship is not None:
                ship.sort(key=lambda r: (r["Customer"].strip(), r["ShipToCode"]))
        else:
            table.rows.sort(key=lambda r: (r.get(code_col, "").strip().zfill(8), int(r.get("cust_seq", "0") or 0)))
            if ship is not None:
                ship.rows.sort(key=lambda r: (r["cust_num"].strip().zfill(8), int(r["cust_seq"])))
        out[bu] = {"table": table, "shipto": ship, "bill_rows": rows, "ents": ents}
    out["_decoys"] = {"decoy_of": decoy_of}
    return out
