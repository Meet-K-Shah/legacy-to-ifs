"""Documentation-as-code: regenerates docs that must never drift from the implementation.

    python -m ifs_migration.docgen
writes docs/source_to_target_mapping.md, docs/data_dictionary.md and docs/defect_catalog.md
"""
from __future__ import annotations

from pathlib import Path

from . import issues, mapping
from .config import READINESS, Paths


def _tbl(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"] +
                     ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows])


def sttm() -> str:
    out = ["# Source-to-Target Mapping (STTM)", "",
           "> Generated from `src/ifs_migration/mapping.py` - do not edit by hand (`make docs`).", "",
           "IFS Cloud field names are **illustrative placeholders** aligned to the project brief; confirm them against the migration "
           "templates issued by the implementation partner. Legacy columns are simplified from the real SYSPRO / Syteline schemas.", ""]
    for dom in mapping.DOMAINS:
        rows = [r for r in mapping.STTM if r[0] == dom]
        if not rows:
            continue
        out += [f"## {mapping.DOMAIN_LABEL[dom]} -> `{mapping.IFS_FILES[dom]}`", "",
                _tbl(["IFS target field", "BU-1 SYSPRO source", "BU-2 Syteline source", "Transformation / validation rule", "Mandatory"],
                     [[f"`{r[2]}`", r[3], r[4], r[5], "Y" if r[6] else ""] for r in rows]), ""]
    out += ["## Reference lookups", "",
            "- `data/reference/uom_map.csv` - legacy UOM spellings -> canonical UOM (unmapped = quarantine)",
            "- `data/reference/category_map.csv` - SYSPRO `ProductClass` / Syteline `family_code` -> enterprise category",
            "- `data/reference/gl_account_map.csv` - legacy GL account -> IFS account + control role (AR / AP / INV)", ""]
    return "\n".join(out)


def data_dictionary() -> str:
    out = ["# Data Dictionary - IFS load files", "", "> Generated from `mapping.py`.", ""]
    for dom in mapping.DOMAINS:
        f = mapping.IFS_FILES[dom]
        out += [f"## `{f}` ({mapping.DOMAIN_LABEL[dom]})", "",
                _tbl(["Column", "Primary key", "Mandatory"],
                     [[c, "Y" if c in mapping.IFS_PK[f] else "", "Y" if c in mapping.IFS_MANDATORY.get(f, []) else ""] for c in mapping.IFS_COLUMNS[f]]), ""]
    return "\n".join(out)


def defect_catalog() -> str:
    rows = sorted(issues.CATALOG.items(), key=lambda kv: (kv[1]["domain"], -issues.SEVERITY_RANK[kv[1]["severity"]], kv[0]))
    return "\n".join(["# Defect Catalogue", "", "> Generated from `issues.py`. Every defect code the pipeline can raise.", "",
                      "Severity drives readiness: **CRITICAL** issues must be zero for go-live; the quarantine-rate threshold is "
                      f"{READINESS['max_quarantine_rate_pct']}% per domain.", "",
                      _tbl(["Code", "Domain", "Severity", "Meaning", "Required business action", "Owner"],
                           [[f"`{c}`", i["domain"], i["severity"], i["title"], i["action"], issues.OWNERS.get(i["domain"], "")] for c, i in rows]), ""])


def main() -> None:
    paths = Paths()
    paths.docs.mkdir(exist_ok=True)
    for name, text in (("source_to_target_mapping.md", sttm()), ("data_dictionary.md", data_dictionary()), ("defect_catalog.md", defect_catalog())):
        (paths.docs / name).write_text(text, encoding="utf-8")
        print("wrote", paths.docs / name)


if __name__ == "__main__":
    main()
