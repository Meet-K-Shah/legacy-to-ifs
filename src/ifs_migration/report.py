"""Business-owner sign-off pack: timestamped cutover_signoff_report.md (Finance & Operations review)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from .config import BU_NAMES
from .mapping import DOMAIN_LABEL, DOMAINS
from .money import money


def _tbl(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def render(ctx, recon, gates, issues, readiness, ifs_rows, engine_info, ts) -> str:
    ready = all(r["status"] == "PASS" for r in readiness)
    recon_ok = recon["status"] == "PASS"
    gates_ok = all(g["status"] == "PASS" for g in gates)
    open_issues = [i for i in issues if i["status"] == "OPEN"]
    sev = Counter(i["severity"] for i in open_issues)
    L = [f"# Cutover Sign-Off Report - Mock Load {ctx.mock}", "",
         f"*Generated {ts} UTC - engine: {engine_info}*", "",
         "## 1. Verdict", "",
         _tbl(["Control", "Result"], [
             ["Pre-load readiness gates (load-file integrity)", "PASS" if gates_ok else "FAIL"],
             ["Count & dollar reconciliation to legacy source", "PASS" if recon_ok else "FAIL"],
             ["Cutover readiness criteria (data quality)", "READY" if ready else "NOT READY"],
             ["Open issues", f"{len(open_issues)} (CRITICAL {sev['CRITICAL']}, HIGH {sev['HIGH']}, MEDIUM {sev['MEDIUM']}, LOW {sev['LOW']})"]]),
         "", "Reconciliation proves that nothing was lost or invented. Readiness says whether the *business* should accept the "
         "remaining quarantined data. They are separate decisions.", "",
         "## 2. Row-count reconciliation", "",
         "Rule: **source rows = IFS rows loaded + quarantined + consolidated duplicates + business-approved exclusions.**", "",
         _tbl(["Domain", "Source rows", "Loaded to IFS", "Quarantined", "Consolidated dups", "Excluded", "Check"],
              [[DOMAIN_LABEL[c["domain"]], f"{c['source_rows']:,}", f"{c['loaded']:,}", c["quarantined"], c["consolidated"], c["excluded"],
                "PASS" if c["source_rows"] == c["loaded"] + c["quarantined"] + c["consolidated"] + c["excluded"] else "FAIL"]
               for c in recon["counts"]]), "",
         "## 3. Dollar-value reconciliation (variance must be $0.00)", "",
         "*Adjusted source* = legacy extract plus approved data corrections from earlier mocks. "
         "Variance = adjusted source - (loaded + quarantined + excluded).", "",
         _tbl(["Domain", "BU", "Legacy source", "Approved corrections", "Adjusted source", "Loaded to IFS", "Quarantined", "Excluded", "Variance", "Check"],
              [[DOMAIN_LABEL[d["domain"]], d["bu"], money(d["raw_source_cents"]), money(d["corrections_cents"]), money(d["adjusted_source_cents"]),
                money(d["loaded_cents"]), money(d["quarantined_cents"]), money(d["excluded_cents"]), money(d["variance_cents"]), d["status"]]
               for d in recon["dollars"]]), "",
         "## 4. GL control-account tie-out", "",
         _tbl(["BU", "Control", "GL (legacy)", "Sub-ledger (legacy)", "Raw break", "Adjusting JE in load", "Residual break", "Corrections pending GL posting", "Check"],
              [[t["bu"], t["control"], money(t["gl_control_raw_cents"]), money(t["subledger_raw_cents"]), money(t["raw_break_cents"]),
                money(t["adjusting_je_cents"]), money(t["residual_break_cents"]), money(t["pending_corrections_cents"]), t["status"]]
               for t in recon["ties"]]), "",
         "*Residual break* must be $0.00. *Corrections pending GL posting* are approved data corrections that change a sub-ledger balance; "
         "Finance should confirm and post the matching journal in IFS.", "",
         "## 5. Pre-load readiness gates (executed on the load files)", "",
         _tbl(["Gate", "File", "Rule", "Failing rows", "Status"],
              [[g["gate_id"], g["file"].replace("IFS_", "").replace(".csv", ""), g["description"], g["failing_rows"], g["status"]] for g in gates]), "",
         "## 6. Cutover readiness criteria", "",
         _tbl(["Criterion", "Threshold", "Actual", "Status"], [[r["criterion"], r["threshold"], r["actual"], r["status"]] for r in readiness]), "",
         "## 7. Master-data harmonisation", ""]
    for dom, label in (("item", "Items"), ("customer", "Customers"), ("vendor", "Vendors")):
        c = next(x for x in recon["counts"] if x["domain"] == dom)
        L.append(f"- **{label}:** {c['source_rows']:,} legacy records -> {c['loaded']:,} golden records "
                 f"({c['consolidated']:,} duplicates consolidated, {c['quarantined']} quarantined, {c['excluded']} excluded).")
    L += [f"- **Steward review queue:** {len(ctx.review_pairs)} possible-duplicate pair(s) awaiting a MERGE / KEEP_SEPARATE decision.", "",
          "## 8. Open issues by domain", ""]
    by = Counter((i["domain"], i["severity"]) for i in open_issues)
    L.append(_tbl(["Domain", "CRITICAL", "HIGH", "MEDIUM", "LOW"], [[DOMAIN_LABEL.get(d, d)] + [by[(d, s)] for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW")] for d in DOMAINS]))
    L += ["", "Full detail: `data_issue_log.csv` (owner, severity, recommended action, ticket).", "",
          "## 9. Sign-off", "",
          "By signing, each owner confirms the reconciliation above, accepts the remaining quarantined records as a post-go-live "
          "backlog, and approves loading the files listed below into IFS Cloud.", "",
          _tbl(["Role", "Name", "Decision (Approve / Reject)", "Signature", "Date"],
               [["Finance (Controller)", "", "", "", ""], ["Operations / Supply Chain", "", "", "", ""],
                ["Sales Operations", "", "", "", ""], ["Procurement", "", "", "", ""], ["Data & Analytics (ERP data lead)", "", "", "", ""]]), "",
          "### Load files in this package", ""]
    L += [f"- `{f}` - {n:,} rows" for f, n in ifs_rows.items()]
    return "\n".join(L) + "\n"
