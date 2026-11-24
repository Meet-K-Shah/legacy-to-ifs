"""Governance & Cutover App (Streamlit).  Run:  streamlit run app/streamlit_app.py

Tab 1  Cutover Reconciliation Gate    pass/fail sign-off metrics, $ parity, GL tie-out, defect-log downloads
Tab 2  MDM Golden Record Explorer     search a golden Item / Customer / Vendor and inspect its legacy lineage
Tab 3  Data Quality KPIs              completeness / uniqueness / integrity by domain, BU-1 vs BU-2
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_access as da  # noqa: E402
from ifs_migration.config import Paths  # noqa: E402
from ifs_migration.mapping import DOMAIN_LABEL  # noqa: E402

st.set_page_config(page_title="ERP Cutover & MDM Governance", layout="wide")
paths = Paths()
mocks = da.available_mocks(paths)
if not mocks:
    st.error("No mock loads found. Run `make mocks` first.")
    st.stop()


@st.cache_resource
def _db():
    return da.open_db(paths)


def usd(cents):
    return f"${int(cents) / 100:,.2f}"


st.title("Legacy-to-IFS Cloud: Cutover & Master-Data Governance")
st.caption("Synthetic SYSPRO (BU-1) + Infor Syteline (BU-2) migration rehearsal - Medallion lakehouse, Fabric / Power BI ready")
t1, t2, t3 = st.tabs(["Cutover Reconciliation Gate", "MDM Golden Record Explorer", "Data Quality KPIs by Domain & BU"])

with t1:
    mock = st.selectbox("Mock load", mocks, index=len(mocks) - 1, format_func=lambda m: f"Mock {m}")
    f = da.mock_files(paths, mock)
    recon_ok = all(r["status"] == "PASS" for r in f["recon"])
    gates_ok = all(g["status"] == "PASS" for g in f["gates"])
    open_issues = [i for i in f["issues"] if i["status"] == "OPEN"]
    crit = sum(1 for i in open_issues if i["severity"] == "CRITICAL")
    c = st.columns(4)
    c[0].metric("Reconciliation", "PASS" if recon_ok else "FAIL")
    c[1].metric("Readiness gates", f"{sum(g['status'] == 'PASS' for g in f['gates'])}/{len(f['gates'])}")
    c[2].metric("Open issues", len(open_issues), help="Quarantined rows + pending steward decisions")
    c[3].metric("CRITICAL open", crit)
    hist = pd.DataFrame(da.read_csv(paths.logs / "mock_history.csv"))
    if not hist.empty:
        st.subheader("Defect burn-down across mock loads")
        st.bar_chart(hist.set_index("mock")[["critical", "high", "medium", "low"]].astype(int))
    st.subheader("Dollar-value parity (variance must be $0.00)")
    dd = pd.DataFrame(f["dollars"])
    if not dd.empty:
        show = pd.DataFrame({"Domain": dd["domain"].map(DOMAIN_LABEL), "BU": dd["bu"],
                             "Adjusted source": dd["adjusted_source_cents"].map(usd), "Loaded": dd["loaded_cents"].map(usd),
                             "Quarantined": dd["quarantined_cents"].map(usd), "Excluded": dd["excluded_cents"].map(usd),
                             "Variance": dd["variance_cents"].map(usd), "Check": dd["status"]})
        st.dataframe(show, use_container_width=True, hide_index=True)
    st.subheader("Failed or all reconciliation checks")
    rr = pd.DataFrame(f["recon"])
    only_fail = st.checkbox("Show failures only", value=not recon_ok)
    st.dataframe(rr[rr["status"] == "FAIL"] if only_fail else rr, use_container_width=True, hide_index=True)
    st.subheader("Pre-load readiness gates")
    st.dataframe(pd.DataFrame(f["gates"]), use_container_width=True, hide_index=True)
    d1, d2 = st.columns(2)
    issue_csv = (paths.mock_logs(mock) / "data_issue_log.csv")
    if issue_csv.exists():
        d1.download_button("Download data_issue_log.csv", issue_csv.read_bytes(), "data_issue_log.csv", "text/csv")
    if f["report"]:
        d2.download_button("Download cutover sign-off report", Path(f["report"]).read_bytes(), Path(f["report"]).name, "text/markdown")
    with st.expander("Open issues for business owners"):
        st.dataframe(pd.DataFrame(open_issues), use_container_width=True, hide_index=True)

with t2:
    db = _db()
    dom = st.radio("Domain", list(da.DOMAIN_TABLES), horizontal=True)
    q = st.text_input("Search by enterprise ID, name/description, or legacy code (e.g. TT-FAB-000010, 'Apex Piping', 'FLG-00012')")
    if q:
        hits = da.search_golden(db, dom, q)
        st.write(f"{len(hits)} match(es)")
        if hits:
            idcol = "part_no" if dom == "Item" else "enterprise_id"
            labels = {h[idcol]: f"{h[idcol]} - {h.get('description') or h.get('name')}" for h in hits}
            pick = st.selectbox("Golden record", list(labels), format_func=labels.get)
            rec = next(h for h in hits if h[idcol] == pick)
            st.subheader("Golden record (IFS load values)")
            st.json({k: v for k, v in rec.items() if v not in ("", None)})
            st.subheader("Legacy lineage / cross-references")
            st.dataframe(pd.DataFrame(da.lineage(db, dom, pick)), use_container_width=True, hide_index=True)
    else:
        st.info("Enter a search term. Try a part number prefix `TT-FAB-`, a company name fragment, or a legacy code.")
    if db.table_exists("silver_party_review_queue"):
        with st.expander("Steward review queue (possible duplicates awaiting a decision)"):
            st.dataframe(pd.DataFrame(db.query("SELECT * FROM silver_party_review_queue")), use_container_width=True, hide_index=True)

with t3:
    k = da.kpis(_db())
    kp = pd.DataFrame(k["kpi"])
    rd = pd.DataFrame(k["readiness"])
    if not rd.empty:
        st.subheader("Domain readiness scorecard (source data, before cleansing)")
        st.dataframe(rd, use_container_width=True, hide_index=True)
    if not kp.empty:
        src = kp[kp["stage"] == "SOURCE"]
        for dim in sorted(src["dimension"].unique()):
            st.subheader(dim.replace("_", " ").title())
            piv = src[src["dimension"] == dim].pivot_table(index="domain", columns="bu", values="score_pct")
            st.bar_chart(piv)
        st.subheader("Migration yield after cleansing (loaded + consolidated duplicates / source rows)")
        st.dataframe(kp[kp["stage"] == "IFS_LOAD"][["domain", "score_pct", "defects", "total"]], use_container_width=True, hide_index=True)
