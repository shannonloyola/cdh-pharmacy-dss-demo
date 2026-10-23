"""Inpatient pharmacy planning (Capstone 1): the main DSS app, one st.navigation entry point.

    streamlit run app/capstone1_app.py

Pages, in order: the six dashboard pages of Table 3.8.1.1 and the data-quality page (section "Inpatient pharmacy
planning"), then the existing DSS pages of app/main.py under "Supplementary analysis", their content unchanged.
app/main.py still runs on its own (streamlit run app/main.py).

The Capstone 1 pages read the Capstone 1 data mart (database/staging/capstone1/capstone1.duckdb, or the path in
CAPSTONE1_DB) read-only; the supplementary pages read the existing DSS database as app/main.py does. The pages show
planning estimates for review by pharmacy and purchasing personnel; they place no orders and rank no option.
"""

from __future__ import annotations

import ast
import os
import runpy
from collections.abc import Callable
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_APP = Path(__file__).resolve().parent / "main.py"
DATABASE = Path(os.environ.get("CAPSTONE1_DB", PROJECT_ROOT / "database" / "staging" / "capstone1" / "capstone1.duckdb"))
PLANNING_SECTION, SUPPLEMENTARY_SECTION = "Inpatient pharmacy planning", "Supplementary analysis"
# DEMO mode (CAPSTONE1_DEMO=1): the mart is the synthetic one (src/capstone1/demo_data.py), every page says so, and the
# supplementary pages, which need the governed DSS database (CDH data), are left out.
DEMO = os.environ.get("CAPSTONE1_DEMO") == "1"
# The supplementary pages need the existing DSS database; a deployment without it sets CAPSTONE1_SUPPLEMENTARY=0.
SHOW_SUPPLEMENTARY = not DEMO and os.environ.get("CAPSTONE1_SUPPLEMENTARY", "1") == "1"
DEMO_NOTE = ("Demonstration data: synthetic medicines, demand, stock, costs and expiry lots, generated with a fixed "
             "seed. Not CDH data; no figure on this page describes Calamba Doctors Hospital.")
PROXY_NOTE = ("Planning estimates. Lead time, ordering cost, holding-cost rate and service levels are proxy values "
              "until CDH confirms them; VED classification is pending pharmacist validation.")
DECISION_NOTE = "Decision support only; final purchasing and inventory decisions rest with authorized CDH personnel."
SUDDEN_CHANGE_NOTE = ("Forecasts follow the patterns in the 2021-2025 records (and, for planning, January-September 2026). "
                      "Sudden changes from emergency admissions, outbreaks, formulary changes or physician prescribing "
                      "behavior may not be captured.")
REVIEW_STATUSES = ["below safety stock", "at or below ROP (reorder review)"]
NEAR_COLUMNS = ["Near_Expiry_Lots", "Near_Expiry_Quantity_Capped", "Near_Expiry_Value_Capped"]


FORM_FILTER_KEY = "dosage_form_filter"


@st.cache_data(show_spinner=False)
def _load(name: str) -> pd.DataFrame:
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        return connection.execute(f'SELECT * FROM "{name}"').df()
    finally:
        connection.close()


def table(name: str) -> pd.DataFrame:
    """A mart table or view; medicine-level ones (with a Dosage_Form column) are filtered by the sidebar's forms."""
    frame = _load(name)
    chosen = st.session_state.get(FORM_FILTER_KEY) or []
    if chosen and "Dosage_Form" in frame:
        frame = frame[frame.Dosage_Form.isin(chosen)]
    return frame


def form_filter() -> None:
    """The dosage-form filter, shared by every planning page (draft groups pending the pharmacist)."""
    forms = sorted(_load("c1_tab_reorder").get("Dosage_Form", pd.Series(dtype=str)).dropna().unique())
    if forms:
        st.sidebar.multiselect("Dosage form", forms, key=FORM_FILTER_KEY,
                               help="Draft groups from the unit and name, pending the chief pharmacist. Applies to "
                                    "the medicine tables and the charts drawn from them; the Stock Health totals and "
                                    "the stock-value trend cover every form.")


def as_of_line(frame: pd.DataFrame) -> None:
    if "As_Of_Month" in frame and len(frame):
        st.caption(f"Stock as of the month-end of {frame.As_Of_Month.iloc[0]} (latest PHARMACY export).")


def kpi_row(items: list[tuple[str, object]]) -> None:
    for column, (label, value) in zip(st.columns(len(items)), items):
        column.metric(label, value)


def stock_health() -> None:
    health = table("c1_tab_stock_health")
    as_of_line(health)
    values = health.set_index("Metric").Value
    kpi_row([(m, values[m]) for m in ("Active medicines (demand in the last 12 months)", "Class A medicines (2025)",
                                       "Reorder review count", "Near-expiry count") if m in values])
    trend = table("c1_tab_stock_trend")
    st.subheader("Stock value at month-end (PHP)")
    st.line_chart(trend.set_index("Month").Stock_Value)
    st.dataframe(health[["Metric", "Value", "Note"]], hide_index=True, width="stretch")


def stockout_reorder() -> None:
    reorder = table("c1_tab_reorder")
    as_of_line(reorder)
    in_review = reorder.Reorder_Status.isin(REVIEW_STATUSES)
    kpi_row([("At or below ROP", int(in_review.sum())), ("Vital below ROP", "pending pharmacist"),
             ("Stock record negative", int(reorder.Reorder_Status.eq("stock record negative").sum()))])
    st.subheader("Medicines by reorder status")
    st.bar_chart(reorder.Reorder_Status.value_counts())
    show_all = st.checkbox("Show every medicine", value=False, key="reorder_all")
    view = reorder if show_all else reorder[in_review | reorder.Reorder_Status.eq("stock record negative")]
    st.dataframe(view[["Brand_Name", "Unit", "Dosage_Form", "ABC_Planning", "VED", "Planning_Stock", "Stock_Status", "Safety_Stock",
                       "Reorder_Point", "EOQ", "Forecast_Planning_Month", "Reorder_Status", "Reliability",
                       "Planning_Label"]].sort_values("Brand_Name"), hide_index=True, width="stretch")


def waste_expiry() -> None:
    review = table("c1_tab_waste_review")
    as_of_line(review)
    near = review.Near_Expiry_Status.iloc[0] if len(review) else "not available"
    kpi_row([("Slow-moving", int(review.Slow_Moving.sum())), ("Excess stock", int(review.Excess_Stock.sum())),
             ("Near-expiry (180 days)", "not available" if near != "available" else "see table")])
    if near != "available":
        st.warning(f"Near-expiry: {near}.")
        missing = table("c1_dq_expiry_missing")
        if len(missing):
            st.caption("Expiry exports needed for near-expiry: " + ", ".join(missing.Expected_File) + ".")
    near_expiry_section()
    st.subheader("Expired value by month (PHP; upper bound, unmatched lots excluded)")
    timeline = table("c1_tab_expiry_timeline")
    st.bar_chart(timeline.set_index("Month").Expired_Value_Capped)
    st.caption("Expired value: the received quantity of each lot expiring in the month, capped at the medicine's "
               "stock at that month-end, x land cost. An upper bound: the exports do not record what was left of "
               "each lot. Lots not matched to a PHARMACY medicine are excluded (see Data Quality).")
    st.caption("Review list: medicines with planning stock above 0. Medicines with no stock and no demand are counted "
               "on the Data Quality page.")
    st.dataframe(review[["Brand_Name", "Unit", "Dosage_Form", "ABC_Planning", "Planning_Stock", "Demand_Last_12_Months",
                         "Months_Of_Cover", "Slow_Moving", "Excess_Stock", "Expired_Value_12m_Capped",
                         "Expired_Value_Label", *(NEAR_COLUMNS if near == "available" else []), "Review_Reason"]]
                 .sort_values("Brand_Name"), hide_index=True, width="stretch")


def near_expiry_section() -> None:
    """Near-expiry as of the latest month whose next 180 days the expiry exports cover: the current month once its
    exports are loaded, else a worked example on an earlier month, compared with what then actually expired."""
    near = table("c1_tab_near_expiry")
    st.subheader("Near-expiry (180 days; upper bound, capped at the as-of month-end stock)")
    if not len(near):
        return
    st.info(near.Label.iloc[0])
    kpi_row([("Lots", int(near.Near_Expiry_Lots.sum())), ("Medicines", len(near)),
             ("Value capped (PHP)", f"{near.Near_Expiry_Value_Capped.sum():,.0f}")])
    check = table("c1_tab_near_expiry_check")
    if len(check):
        st.caption("The worked example against what the same exports show actually expired in the months of its window.")
        st.dataframe(check[["Measure", "Lots", "Medicines", "Value_Capped_PHP"]], hide_index=True, width="stretch")
    st.dataframe(near[["Brand_Name", "Unit", "Dosage_Form", "Near_Expiry_Lots", "First_Expiry", "Last_Expiry",
                       "Stock_At_As_Of", "Near_Expiry_Quantity_Capped", "Near_Expiry_Value_Capped"]],
                 hide_index=True, width="stretch")


def forecast_reliability() -> None:
    st.warning(SUDDEN_CHANGE_NOTE)
    forecast = table("c1_tab_forecast")
    counts = forecast.Reliability.value_counts()
    kpi_row([(label, int(n)) for label, n in counts.items()][:4])
    choices = forecast.sort_values("Brand_Name")
    picked = st.selectbox("Medicine", choices.Brand_Name.tolist(), key="forecast_medicine")
    key = choices[choices.Brand_Name.eq(picked)].Medicine_Key.iloc[0] if len(choices) else None
    series = table("c1_tab_forecast_series")
    if key is not None:
        chart = series[series.Medicine_Key.eq(key)].pivot_table(index="Month", columns="Series", values="Value")
        st.line_chart(chart)
    columns = [c for c in ["Brand_Name", "Dosage_Form", "ABC_Planning", "Selected_Model", "Volume_Class", "Test_MAE", "Test_RMSE",
                           "Test_MAPE", "Test_MAPE_Excluded_Zero_Months", "Test_WAPE", "Test_MASE", "Reliability",
                           "Prospective_2026_MAE", "Limited_Planning_Estimate"] if c in forecast]
    st.dataframe(forecast[columns].sort_values("Brand_Name"), hide_index=True, width="stretch")
    st.subheader("COVID outlier rule: three variants")
    st.caption("The primary variant applies the paper's rule: a month of 2022-2023 more than 100% above or 50% below "
               "the item's 12-month average is flagged and, in training only, replaced by that average. Two "
               "corrections: an intermittent medicine is tested on its positive months only, against the average of "
               "the positive months before it (demand size), and a month is tested only 12 months after the "
               "medicine's first demand. The rule was defined after the January-September 2026 holdout was read, so "
               "its 2026 score is post-hoc, not a clean test; its clean test starts in October 2026. The other two "
               "variants were frozen before 2026 was read and remain the clean holdout evidence. Nothing was "
               "re-selected on 2026.")
    comparison = table("c1_tab_variant_comparison")
    if len(comparison):
        wide = comparison.pivot_table(index=["Measure_Group", "Measure"], columns="Variant", values="Value",
                                      aggfunc="first").reset_index()
        st.dataframe(wide, hide_index=True, width="stretch")
    covid_period()


def covid_period() -> None:
    """Limitation 8: the pandemic-period outputs, each labelled as such."""
    st.subheader("Pandemic period (2021-2023)")
    flagged = table("c1_tab_covid_flagged_months")
    comparison = table("c1_tab_covid_period_comparison")
    stable = table("c1_tab_covid_stable")
    kpi_row([("Pandemic-period months flagged", len(flagged)), ("Medicines with a flagged month",
             int(flagged.Medicine_Key.nunique()) if len(flagged) else 0), ("Stable across periods", len(stable))])
    st.caption("Pandemic period: a month of 2022-2023 flagged by the outlier rule (more than 100% above or 50% below "
               "the item average), replaced by that average in training only and listed here for review.")
    with st.expander(f"Flagged months for review (pandemic period 2021-2023): {len(flagged)}"):
        st.dataframe(flagged[["Brand_Name", "Unit", "Month", "Net_Demand", "Item_Average", "Rule", "Period_Label"]],
                     hide_index=True, width="stretch")
    st.caption("Pandemic (2021-2023) vs post-pandemic (2024-2025), net demand per medicine: mean monthly demand, "
               "coefficient of variation (CV), and the ratio of means (post-pandemic / pandemic).")
    st.dataframe(comparison[["Brand_Name", "Unit", "Pandemic_Mean_Monthly_Demand", "Pandemic_CV",
                             "Post_Pandemic_Mean_Monthly_Demand", "Post_Pandemic_CV", "Ratio_Of_Means", "CV_Change",
                             "Stable_Across_Periods", "Period_Label"]], hide_index=True, width="stretch")
    with st.expander(f"Stable across periods: {len(stable)} (ratio of means 0.8-1.25 and |CV change| <= 0.25; "
                     "a default pending the chief pharmacist)"):
        st.dataframe(stable[["Brand_Name", "Unit", "Ratio_Of_Means", "CV_Change", "Period_Label",
                             "Stable_Rule_Status"]], hide_index=True, width="stretch")


def abc_ved() -> None:
    abc = table("c1_tab_abc_ved")
    summary = table("c1_tab_abc_summary")
    planning = abc.ABC_Planning.value_counts()
    kpi_row([("Class A", int(planning.get("A", 0))), ("Class B", int(planning.get("B", 0))),
             ("Class C", int(planning.get("C", 0))), ("VED", "pending pharmacist")])
    st.info("VED classification is pending the chief pharmacist's validation. Until then this page shows ABC only; "
            "the ABC-VED matrix and Categories I, II and III appear once VED is validated.")
    st.subheader("Share of 2025 consumption value by class")
    year = summary[summary.Period.eq("2025") & summary.ABC_Class.isin(["A", "B", "C"])]
    st.bar_chart(year.set_index("ABC_Class").Value_Share)
    st.dataframe(abc[["Brand_Name", "Dosage_Form", "ABC_2021", "ABC_2022", "ABC_2023", "ABC_2024", "ABC_2025", "ABC_2021_2025",
                      "ABC_Planning", "VED"]].sort_values("Brand_Name"),
                 hide_index=True, width="stretch")


def sensitivity_assumptions() -> None:
    sensitivity = table("c1_tab_sensitivity")
    assumptions = table("c1_tab_assumptions")
    as_of_line(sensitivity)
    names = sorted(sensitivity.Brand_Name.dropna().unique())
    picked = st.selectbox("Medicine", names, key="sensitivity_medicine") if names else None
    view = sensitivity[sensitivity.Brand_Name.eq(picked)] if picked else sensitivity.iloc[0:0]
    if len(view):
        kpi_row([("Baseline ROP", f"{view.Baseline_ROP.iloc[0]:,.1f}"), ("Baseline EOQ", f"{view.Baseline_EOQ.iloc[0]:,.1f}"),
                 ("Baseline safety stock", f"{view.Baseline_Safety_Stock.iloc[0]:,.1f}")])
        st.bar_chart(view.set_index("Scenario").Change_ROP)
    st.dataframe(view[["Scenario_Type", "Scenario", "Baseline_Safety_Stock", "Adjusted_Safety_Stock", "Baseline_ROP",
                       "Adjusted_ROP", "Change_ROP_Pct", "Baseline_EOQ", "Adjusted_EOQ", "Change_EOQ_Pct"]],
                 hide_index=True, width="stretch")
    st.subheader("Sensitivity grid: lead time x service level x holding rate")
    st.caption("Every combination of lead time 3/7/14 days, service level 90/95/99% and holding-cost rate 15/20/25%; "
               "the baseline is 7 days, 95% and 20%.")
    grid = table("c1_tab_sensitivity_grid")
    own = grid[grid.Brand_Name.eq(picked)] if picked else grid.iloc[0:0]
    st.dataframe(own[["Lead_Time_Days", "Service_Level", "Holding_Rate", "Safety_Stock", "Reorder_Point", "EOQ"]],
                 hide_index=True, width="stretch")
    st.subheader("Planning assumptions")
    st.dataframe(assumptions, hide_index=True, width="stretch")


def data_quality() -> None:
    dq = table("c1_dq_summary")
    as_of_line(dq)
    inactive = table("c1_dq_inactive")
    kpi_row([("Inactive (no stock, no demand)", len(inactive)),
             ("Negative stock records", int(dq.set_index("Check").Count.get("Negative stock records (month-ends)", 0)))])
    st.dataframe(dq[["Check", "Count"]], hide_index=True, width="stretch")
    with st.expander(f"Inactive medicines (no stock, no demand): {len(inactive)}"):
        st.dataframe(inactive[["Brand_Name", "Generic_Name", "Unit"]], hide_index=True, width="stretch")
    with st.expander("Negative stock records"):
        st.dataframe(table("c1_dq_negative_stock"), hide_index=True, width="stretch")
    st.subheader("Expiry lots not matched to a PHARMACY medicine")
    st.dataframe(table("c1_dq_expiry_unmatched_groups"), hide_index=True, width="stretch")
    with st.expander("Unmatched expiry items"):
        st.dataframe(table("c1_dq_expiry_unmatched"), hide_index=True, width="stretch")
    st.subheader("Expiry exports on disk")
    st.caption("Each export lists the receipt lots expiring in one month (its printed expiration-date range); the "
               "exports carry no run date.")
    st.dataframe(table("c1_dq_expiry_exports"), hide_index=True, width="stretch")
    missing = table("c1_dq_expiry_missing")
    if len(missing):
        st.warning(f"{len(missing)} expiry exports are needed for near-expiry and are not on disk.")
        st.dataframe(missing, hide_index=True, width="stretch")


def kpis() -> None:
    """§1.3.3: each Key Performance Indicator of Table 1.3.3.1 against its target."""
    table_kpi = table("c1_tab_kpi")
    as_of_line(table_kpi)
    counts = table_kpi.Status.value_counts()
    kpi_row([("Met", int(counts.get("met", 0))), ("Pending", int(counts.get("pending", 0))),
             ("Not met", int(counts.get("not met", 0)))])
    st.caption("The KPIs measure whether the planning outputs are generated and interpretable; they do not claim "
               "operational improvement. Pending: the output exists but waits for a confirmation the target names.")
    st.dataframe(table_kpi[["KPI", "Target", "Evidence", "Status", "Note"]], hide_index=True, width="stretch")


# The order of Table 3.8.1.1, then the data-quality and KPI pages: (title, URL path, render function).
PLANNING_PAGES = [
    ("Stock Health Overview", "stock-health", stock_health),
    ("Stockout Risk and Reorder Review", "stockout-reorder", stockout_reorder),
    ("Waste and Expiry Risk", "waste-expiry", waste_expiry),
    ("Forecast Reliability and Demand Trends", "forecast-reliability", forecast_reliability),
    ("ABC-VED Priority Monitoring", "abc-ved", abc_ved),
    ("Sensitivity and Planning Assumptions", "sensitivity", sensitivity_assumptions),
    ("Data Quality", "data-quality", data_quality),
    ("Key Performance Indicators", "kpis", kpis),
]


def planning_page(title: str, render: Callable[[], None]) -> Callable[[], None]:
    def page() -> None:
        st.title(title)
        if DEMO:
            st.warning(DEMO_NOTE)
        if not DATABASE.exists():
            st.error(f"The planning data mart was not found at {DATABASE}. Run the Capstone 1 build first.")
            st.stop()
        st.info(PROXY_NOTE)
        st.caption(DECISION_NOTE)
        render()
    return page


def existing_pages() -> list[str]:
    """The existing app's pages in its own sidebar order: OPERATIONAL_PAGES, then EVIDENCE_PAGES, in app/main.py."""
    lists = {}
    for node in ast.parse(MAIN_APP.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("OPERATIONAL_PAGES", "EVIDENCE_PAGES"):
                    lists[target.id] = ast.literal_eval(node.value)
    return lists["OPERATIONAL_PAGES"] + lists["EVIDENCE_PAGES"]


def supplementary_page(name: str) -> Callable[[], None]:
    """Run app/main.py as one page: it renders the page named here, without its own page configuration and sidebar
    page buttons. A button that opens another existing page (for example a review list) switches to that page."""
    def page() -> None:
        state = st.session_state
        requested = state.get("active_page")
        if state.get("supplementary_page") == name and requested in SUPPLEMENTARY and requested != name:
            st.switch_page(SUPPLEMENTARY[requested])
        state["supplementary_page"] = state["active_page"] = name
        runpy.run_path(str(MAIN_APP), init_globals={"EMBEDDED_PAGE": name}, run_name="__main__")
    return page


def url_path(name: str) -> str:
    return "supplementary-" + name.lower().replace("&", "and").replace(" ", "-")


st.set_page_config(page_title="Inpatient Pharmacy Planning", layout="wide", initial_sidebar_state="expanded")
PLANNING = [st.Page(planning_page(title, render), title=title, url_path=path, default=(n == 0))
            for n, (title, path, render) in enumerate(PLANNING_PAGES)]
# The supplementary pages are built only when shown: in DEMO mode app/main.py (and the modules it imports) is never
# read, so a demo image can leave them out.
SUPPLEMENTARY = {name: st.Page(supplementary_page(name), title=name, url_path=url_path(name))
                 for name in existing_pages()} if SHOW_SUPPLEMENTARY else {}
sections = {PLANNING_SECTION: PLANNING}
if SHOW_SUPPLEMENTARY:
    sections[SUPPLEMENTARY_SECTION] = list(SUPPLEMENTARY.values())
current = st.navigation(sections)
if current.url_path in {page.url_path for page in PLANNING} and DATABASE.exists():
    form_filter()  # drawn here, outside the pages, so the choice survives a change of planning page
current.run()
