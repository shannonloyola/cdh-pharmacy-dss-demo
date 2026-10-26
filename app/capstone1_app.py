"""Inpatient pharmacy planning (Capstone 1): the main DSS app, one st.navigation entry point.

    streamlit run app/capstone1_app.py

Five pages, in order: Overview, Reorder Planning, Waste and Expiry, Medicine Detail, Analysis and Evidence. They hold
every output of the eight earlier planning pages (the six dashboard pages of Table 3.8.1.1, Data Quality and the KPIs),
moved, not changed. The existing DSS pages of app/main.py sit at the bottom of the sidebar under "Earlier annual
analysis", a collapsed group, their content unchanged. app/main.py still runs on its own (streamlit run app/main.py).

The look is the existing app's visual system (app/c1_ui.py). The planning pages read the Capstone 1 data mart
(database/staging/capstone1/capstone1.duckdb, or the path in CAPSTONE1_DB) read-only; the earlier pages read the
existing DSS database as app/main.py does. The pages show planning estimates for review by pharmacy and purchasing
personnel; they place no orders and rank no option.
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

import c1_ui
from c1_ui import card, filter_bar, show_table, tiles

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_APP = Path(__file__).resolve().parent / "main.py"
DATABASE = Path(os.environ.get("CAPSTONE1_DB", PROJECT_ROOT / "database" / "staging" / "capstone1" / "capstone1.duckdb"))
PLANNING_SECTION, EARLIER_GROUP = "Inpatient pharmacy planning", "Earlier annual analysis"
# Sidebar labels of earlier pages that differ from their page name (the page itself is unchanged).
EARLIER_LABELS = {"Overview": "Annual overview"}
# DEMO mode (CAPSTONE1_DEMO=1): the mart is the synthetic one (src/capstone1/demo_data.py), every page says so, and the
# earlier pages, which need the governed DSS database (CDH data), are left out.
DEMO = os.environ.get("CAPSTONE1_DEMO") == "1"
# The earlier pages need the existing DSS database; a deployment without it sets CAPSTONE1_SUPPLEMENTARY=0.
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
REORDER_COLUMNS = ["Brand_Name", "Unit", "Dosage_Form", "ABC_Planning", "VED", "Planning_Stock", "Stock_Status",
                   "Safety_Stock", "Reorder_Point", "EOQ", "Forecast_Planning_Month", "Reorder_Status", "Reliability",
                   "Planning_Label"]
FORECAST_COLUMNS = ["Brand_Name", "Dosage_Form", "ABC_Planning", "Selected_Model", "Volume_Class", "Test_MAE",
                    "Test_RMSE", "Test_MAPE", "Test_MAPE_Excluded_Zero_Months", "Test_WAPE", "Test_MASE", "Reliability",
                    "Prospective_2026_MAE", "Limited_Planning_Estimate"]
ABC_COLUMNS = ["Brand_Name", "Dosage_Form", "ABC_2021", "ABC_2022", "ABC_2023", "ABC_2024", "ABC_2025", "ABC_2021_2025",
               "ABC_Planning", "VED"]
FLAGGED_COLUMNS = ["Brand_Name", "Unit", "Month", "Net_Demand", "Item_Average", "Rule", "Period_Label"]
SENSITIVITY_COLUMNS = ["Scenario_Type", "Scenario", "Baseline_Safety_Stock", "Adjusted_Safety_Stock", "Baseline_ROP",
                       "Adjusted_ROP", "Change_ROP_Pct", "Baseline_EOQ", "Adjusted_EOQ", "Change_EOQ_Pct"]
GRID_COLUMNS = ["Lead_Time_Days", "Service_Level", "Holding_Rate", "Safety_Stock", "Reorder_Point", "EOQ"]
ABC_ORDER = {"A": 0, "B": 1, "C": 2}
FIRST_ROWS = 10
FLAGGED_CAPTION = ("Pandemic period: a month of 2022-2023 flagged by the outlier rule (more than 100% above or 50% below "
                   "the item average), replaced by that average in training only and listed here for review.")
GRID_CAPTION = ("Every combination of lead time 3/7/14 days, service level 90/95/99% and holding-cost rate 15/20/25%; "
                "the baseline is 7 days, 95% and 20%.")


@st.cache_data(show_spinner=False)
def _load(database: str, modified: int, name: str) -> pd.DataFrame:
    connection = duckdb.connect(database, read_only=True)
    try:
        return connection.execute(f'SELECT * FROM "{name}"').df()
    finally:
        connection.close()


def table(name: str) -> pd.DataFrame:
    """A mart table or view, read-only; cached per mart file and its modification time, so a rebuilt mart, or another
    mart, is read afresh."""
    return _load(str(DATABASE), DATABASE.stat().st_mtime_ns, name)


def present(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [c for c in columns if c in frame]


def as_of_line(frame: pd.DataFrame) -> None:
    if "As_Of_Month" in frame and len(frame):
        st.caption(f"Stock as of the month-end of {frame.As_Of_Month.iloc[0]} (latest PHARMACY export).")


def by_class_then(frame: pd.DataFrame, measure: pd.Series, ascending: bool) -> pd.DataFrame:
    """ABC class A, B, C, then the list's own measure, then the name: the order of the first rows on the Overview."""
    order = frame.assign(_class=frame.ABC_Planning.map(ABC_ORDER).fillna(len(ABC_ORDER)), _measure=measure)
    return order.sort_values(["_class", "_measure", "Brand_Name"], ascending=[True, ascending, True],
                             na_position="last").drop(columns=["_class", "_measure"])


def rows_for(frame: pd.DataFrame, key: object, name: str) -> pd.DataFrame:
    """One medicine's rows: by Medicine_Key where the table has it, else by brand name."""
    return frame[frame.Medicine_Key.eq(key)] if "Medicine_Key" in frame else frame[frame.Brand_Name.eq(name)]


def first_value(frame: pd.DataFrame, column: str) -> object:
    return frame[column].iloc[0] if column in frame and len(frame) and pd.notna(frame[column].iloc[0]) else "not available"


# ------------------------------------------------------------------ Overview

def action_list(title: str, frame: pd.DataFrame, columns: list[str], order: str, target: str, key: str) -> None:
    st.subheader(title)
    st.caption(f"First {min(FIRST_ROWS, len(frame))} of {len(frame)}, ordered by {order}.")
    if len(frame):
        c1_ui.first_rows_table(frame[present(frame, columns)], key=f"overview-{key}", rows=FIRST_ROWS)
    st.page_link(PAGES[target], label=f"Full list: {target}")


def overview() -> None:
    health = table("c1_tab_stock_health")
    reorder = table("c1_tab_reorder")
    review = table("c1_tab_waste_review")
    near = table("c1_tab_near_expiry")
    as_of_line(health)
    values = health.set_index("Metric").Value if len(health) else pd.Series(dtype=object)
    in_review = reorder.Reorder_Status.isin(REVIEW_STATUSES)
    below = reorder.Reorder_Status.eq("below safety stock")
    with card("action-counts"):
        tiles("actions", [("At or below ROP", int(in_review.sum()), "procurement"),
                          ("Below safety stock", int(below.sum()), "attention"),
                          ("Slow-moving", int(review.Slow_Moving.sum()), "expiry"),
                          ("Excess stock", int(review.Excess_Stock.sum()), "expiry"),
                          *[(m, values[m], "expiry") for m in ("Near-expiry count",) if m in values]])
    with card("action-lists"):
        action_list("At or below ROP", by_class_then(reorder[in_review], reorder.Planning_Stock - reorder.Reorder_Point,
                                                     True),
                    ["Brand_Name", "Unit", "ABC_Planning", "Planning_Stock", "Reorder_Point", "Reorder_Status"],
                    "ABC class, then planning stock minus ROP (lowest first)", "Reorder Planning", "at-or-below-rop")
        action_list("Below safety stock", by_class_then(reorder[below], reorder.Planning_Stock - reorder.Safety_Stock,
                                                        True),
                    ["Brand_Name", "Unit", "ABC_Planning", "Planning_Stock", "Safety_Stock", "Reorder_Status"],
                    "ABC class, then planning stock minus safety stock (lowest first)", "Reorder Planning",
                    "below-safety-stock")
        slow = review[review.Slow_Moving.fillna(False).astype(bool)]
        excess = review[review.Excess_Stock.fillna(False).astype(bool)]
        action_list("Slow-moving", by_class_then(slow, slow.Months_Of_Cover, False),
                    ["Brand_Name", "Unit", "ABC_Planning", "Planning_Stock", "Months_Of_Cover", "Review_Reason"],
                    "ABC class, then months of cover (highest first)", "Waste and Expiry", "slow-moving")
        action_list("Excess stock", by_class_then(excess, excess.Months_Of_Cover, False),
                    ["Brand_Name", "Unit", "ABC_Planning", "Planning_Stock", "Months_Of_Cover", "Review_Reason"],
                    "ABC class, then months of cover (highest first)", "Waste and Expiry", "excess-stock")
        if len(near):
            st.caption(near.Label.iloc[0])
        action_list("Near-expiry (180 days)", near.sort_values(["Near_Expiry_Value_Capped", "Brand_Name"],
                                                               ascending=[False, True]),
                    ["Brand_Name", "Unit", "Near_Expiry_Lots", "First_Expiry", "Near_Expiry_Value_Capped"],
                    "capped near-expiry value (highest first)", "Waste and Expiry", "near-expiry")
    with card("data-checks", "Data Quality"):
        data_check_status()
    with card("stock-health", "Stock Health Overview"):
        tiles("stock-health", [(m, values[m], icon) for m, icon in (
            ("Active medicines (demand in the last 12 months)", "medicine"), ("Class A medicines (2025)", "validation"),
            ("Reorder review count", "procurement"), ("Near-expiry count", "expiry")) if m in values])
        trend = table("c1_tab_stock_trend")
        st.subheader("Stock value at month-end (PHP)")
        c1_ui.line_chart(trend.set_index("Month").Stock_Value)
        show_table(health[["Metric", "Value", "Note"]])


def data_check_status() -> None:
    dq = table("c1_dq_summary")
    inactive = table("c1_dq_inactive")
    missing = table("c1_dq_expiry_missing")
    tiles("data-checks", [("Inactive (no stock, no demand)", len(inactive), "check"),
                          ("Negative stock records",
                           int(dq.set_index("Check").Count.get("Negative stock records (month-ends)", 0)), "attention")])
    if len(missing):
        st.warning(f"{len(missing)} expiry exports are needed for near-expiry and are not on disk.")
    st.page_link(PAGES["Analysis and Evidence"], label="Full checks: Analysis and Evidence")


# ------------------------------------------------------------------ Reorder Planning

def reorder_planning() -> None:
    reorder = table("c1_tab_reorder")
    as_of_line(reorder)
    in_review = reorder.Reorder_Status.isin(REVIEW_STATUSES)
    with card("reorder"):
        tiles("reorder", [("At or below ROP", int(in_review.sum()), "procurement"),
                          ("Vital below ROP", "pending pharmacist", "attention"),
                          ("Stock record negative", int(reorder.Reorder_Status.eq("stock record negative").sum()),
                           "attention")])
        st.subheader("Medicines by reorder status")
        c1_ui.bar_chart(reorder.Reorder_Status.value_counts())
        view = filter_bar(reorder, "reorder", status="Reorder_Status")
        show_table(view[present(view, REORDER_COLUMNS)].sort_values("Brand_Name"))
    with c1_ui.collapsible("what-if", "What if?"):
        what_if()


def what_if() -> None:
    """The sensitivity content: one medicine's baseline and adjusted levels side by side, its scenarios (lead time,
    service level, holding rate and demand), the sensitivity grid and the planning assumptions."""
    sensitivity = table("c1_tab_sensitivity")
    assumptions = table("c1_tab_assumptions")
    as_of_line(sensitivity)
    names = sorted(sensitivity.Brand_Name.dropna().unique())
    picked = c1_ui.picker("Medicine", names, key="sensitivity_medicine") if names else None
    view = sensitivity[sensitivity.Brand_Name.eq(picked)] if picked else sensitivity.iloc[0:0]
    if len(view):
        baseline, adjusted = st.columns(2)
        with baseline:
            st.markdown("**Baseline**")
            tiles("what-if-baseline", [("Baseline ROP", f"{view.Baseline_ROP.iloc[0]:,.1f}", "procurement"),
                                       ("Baseline EOQ", f"{view.Baseline_EOQ.iloc[0]:,.1f}", "procurement"),
                                       ("Baseline safety stock", f"{view.Baseline_Safety_Stock.iloc[0]:,.1f}",
                                        "governance")])
        with adjusted:
            st.markdown("**Adjusted**")
            labels = (view.Scenario_Type.astype(str) + ": " + view.Scenario.astype(str)).tolist()
            row = view.iloc[st.selectbox("Scenario", range(len(view)), format_func=labels.__getitem__,
                                         key=f"sensitivity_scenario-{picked}")]
            tiles("what-if-adjusted", [("Adjusted ROP", f"{row.Adjusted_ROP:,.1f}", "procurement"),
                                       ("Adjusted EOQ", f"{row.Adjusted_EOQ:,.1f}", "procurement"),
                                       ("Adjusted safety stock", f"{row.Adjusted_Safety_Stock:,.1f}", "governance")])
        c1_ui.bar_chart(view.set_index("Scenario").Change_ROP)
    show_table(view[present(view, SENSITIVITY_COLUMNS)])
    st.subheader("Sensitivity grid: lead time x service level x holding rate")
    st.caption(GRID_CAPTION)
    grid = table("c1_tab_sensitivity_grid")
    own = grid[grid.Brand_Name.eq(picked)] if picked else grid.iloc[0:0]
    show_table(own[GRID_COLUMNS])
    st.subheader("Planning assumptions")
    show_table(assumptions)


# ------------------------------------------------------------------ Waste and Expiry

def waste_expiry() -> None:
    review = table("c1_tab_waste_review")
    as_of_line(review)
    near = review.Near_Expiry_Status.iloc[0] if len(review) else "not available"
    with card("waste"):
        tiles("waste", [("Slow-moving", int(review.Slow_Moving.sum()), "expiry"),
                        ("Excess stock", int(review.Excess_Stock.sum()), "expiry"),
                        ("Near-expiry (180 days)", "not available" if near != "available" else "see table", "expiry")])
        if near != "available":
            st.warning(f"Near-expiry: {near}.")
            missing = table("c1_dq_expiry_missing")
            if len(missing):
                st.caption("Expiry exports needed for near-expiry: " + ", ".join(missing.Expected_File) + ".")
    with card("near-expiry"):
        near_expiry_section()
    with card("expired"):
        st.subheader("Expired value by month (PHP; upper bound, unmatched lots excluded)")
        timeline = table("c1_tab_expiry_timeline")
        c1_ui.bar_chart(timeline.set_index("Month").Expired_Value_Capped)
        st.caption("Expired value: the received quantity of each lot expiring in the month, capped at the medicine's "
                   "stock at that month-end, x land cost. An upper bound: the exports do not record what was left of "
                   "each lot. Lots not matched to a PHARMACY medicine are excluded (see Data Quality).")
    with card("waste-review"):
        st.caption("Review list: medicines with planning stock above 0. Medicines with no stock and no demand are "
                   "counted on the Data Quality page.")
        view = filter_bar(review, "waste-review", status="Review_Reason")
        show_table(view[present(view, ["Brand_Name", "Unit", "Dosage_Form", "ABC_Planning", "Planning_Stock",
                                       "Demand_Last_12_Months", "Months_Of_Cover", "Slow_Moving", "Excess_Stock",
                                       "Expired_Value_12m_Capped", "Expired_Value_Label",
                                       *(NEAR_COLUMNS if near == "available" else []), "Review_Reason"])]
                   .sort_values("Brand_Name"))


def near_expiry_section() -> None:
    """Near-expiry as of the latest month whose next 180 days the expiry exports cover: the current month once its
    exports are loaded, else a worked example on an earlier month, compared with what then actually expired."""
    near = table("c1_tab_near_expiry")
    st.subheader("Near-expiry (180 days; upper bound, capped at the as-of month-end stock)")
    if not len(near):
        return
    st.info(near.Label.iloc[0])
    tiles("near-expiry", [("Lots", int(near.Near_Expiry_Lots.sum()), "expiry"), ("Medicines", len(near), "medicine"),
                          ("Value capped (PHP)", f"{near.Near_Expiry_Value_Capped.sum():,.0f}", "procurement")])
    check = table("c1_tab_near_expiry_check")
    if len(check):
        st.caption("The worked example against what the same exports show actually expired in the months of its window.")
        show_table(check[["Measure", "Lots", "Medicines", "Value_Capped_PHP"]])
    view = filter_bar(near, "near-expiry")
    show_table(view[["Brand_Name", "Unit", "Dosage_Form", "Near_Expiry_Lots", "First_Expiry", "Last_Expiry",
                     "Stock_At_As_Of", "Near_Expiry_Quantity_Capped", "Near_Expiry_Value_Capped"]])


# ------------------------------------------------------------------ Medicine Detail

def medicine_detail() -> None:
    forecast = table("c1_tab_forecast")
    choices = forecast.sort_values("Brand_Name")
    names = dict(zip(choices.Medicine_Key, choices.Brand_Name))
    if not names:
        return
    key = c1_ui.picker("Medicine", list(names), key="detail_medicine", format_func=names.get)
    name = names[key]
    reorder = rows_for(table("c1_tab_reorder"), key, name)
    abc = rows_for(table("c1_tab_abc_ved"), key, name)
    own_forecast = forecast[forecast.Medicine_Key.eq(key)]
    with card("detail-class", "ABC-VED Priority Monitoring"):
        tiles("detail-class", [("ABC_Planning", first_value(abc, "ABC_Planning"), "validation"),
                               ("VED", first_value(abc, "VED"), "governance"),
                               ("Selected_Model", first_value(own_forecast, "Selected_Model"), "forecast"),
                               ("Reliability", first_value(own_forecast, "Reliability"), "check")])
        show_table(abc[present(abc, ABC_COLUMNS)])
    with card("detail-forecast", "Forecast Reliability and Demand Trends"):
        st.warning(SUDDEN_CHANGE_NOTE)
        series = table("c1_tab_forecast_series")
        own_series = series[series.Medicine_Key.eq(key)]
        c1_ui.line_chart(own_series.pivot_table(index="Month", columns="Series", values="Value"))
        show_table(own_forecast[present(own_forecast, FORECAST_COLUMNS)])
        st.subheader("Pandemic period (2021-2023)")
        st.caption(FLAGGED_CAPTION)
        flagged = rows_for(table("c1_tab_covid_flagged_months"), key, name)
        show_table(flagged[present(flagged, FLAGGED_COLUMNS)])
    with card("detail-stock", "Stockout Risk and Reorder Review"):
        as_of_line(reorder)
        show_table(reorder[present(reorder, REORDER_COLUMNS)])
    with card("detail-sensitivity", "Sensitivity and Planning Assumptions"):
        sensitivity = rows_for(table("c1_tab_sensitivity"), key, name)
        show_table(sensitivity[present(sensitivity, SENSITIVITY_COLUMNS)])
        st.subheader("Sensitivity grid: lead time x service level x holding rate")
        st.caption(GRID_CAPTION)
        grid = rows_for(table("c1_tab_sensitivity_grid"), key, name)
        show_table(grid[present(grid, GRID_COLUMNS)])


# ------------------------------------------------------------------ Analysis and Evidence

ANALYSIS_TABS = ["ABC-VED Priority Monitoring", "Forecast Reliability and Demand Trends", "Pandemic period (2021-2023)",
                 "Data Quality", "Key Performance Indicators"]


def analysis_evidence() -> None:
    for tab, render in zip(st.tabs(ANALYSIS_TABS), (abc_ved, forecast_evidence, covid_period, data_quality, kpis)):
        with tab, card(f"analysis-{render.__name__}"):
            render()


def abc_ved() -> None:
    abc = table("c1_tab_abc_ved")
    summary = table("c1_tab_abc_summary")
    planning = abc.ABC_Planning.value_counts()
    tiles("abc", [("Class A", int(planning.get("A", 0)), "validation"), ("Class B", int(planning.get("B", 0)), "validation"),
                  ("Class C", int(planning.get("C", 0)), "validation"), ("VED", "pending pharmacist", "governance")])
    st.info("VED classification is pending the chief pharmacist's validation. Until then this page shows ABC only; "
            "the ABC-VED matrix and Categories I, II and III appear once VED is validated.")
    st.subheader("Share of 2025 consumption value by class")
    year = summary[summary.Period.eq("2025") & summary.ABC_Class.isin(["A", "B", "C"])]
    c1_ui.bar_chart(year.set_index("ABC_Class").Value_Share)
    view = filter_bar(abc, "abc")
    show_table(view[present(view, ABC_COLUMNS)].sort_values("Brand_Name"))


def forecast_evidence() -> None:
    st.warning(SUDDEN_CHANGE_NOTE)
    forecast = table("c1_tab_forecast")
    counts = forecast.Reliability.value_counts()
    tiles("reliability", [(label, int(n), "check") for label, n in counts.items()][:4])
    view = filter_bar(forecast, "forecast", status="Reliability")
    show_table(view[present(view, FORECAST_COLUMNS)].sort_values("Brand_Name"))
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
        show_table(wide)


def covid_period() -> None:
    """Limitation 8: the pandemic-period outputs, each labelled as such."""
    st.subheader("Pandemic period (2021-2023)")
    flagged = table("c1_tab_covid_flagged_months")
    comparison = table("c1_tab_covid_period_comparison")
    stable = table("c1_tab_covid_stable")
    tiles("pandemic", [("Pandemic-period months flagged", len(flagged), "attention"),
                       ("Medicines with a flagged month", int(flagged.Medicine_Key.nunique()) if len(flagged) else 0,
                        "medicine"), ("Stable across periods", len(stable), "check")])
    st.caption(FLAGGED_CAPTION)
    with st.expander(f"Flagged months for review (pandemic period 2021-2023): {len(flagged)}"):
        view = filter_bar(flagged, "flagged", status="Rule")
        show_table(view[present(view, FLAGGED_COLUMNS)])
    st.caption("Pandemic (2021-2023) vs post-pandemic (2024-2025), net demand per medicine: mean monthly demand, "
               "coefficient of variation (CV), and the ratio of means (post-pandemic / pandemic).")
    view = filter_bar(comparison, "pandemic-comparison", status="Stable_Across_Periods")
    show_table(view[present(view, ["Brand_Name", "Unit", "Pandemic_Mean_Monthly_Demand", "Pandemic_CV",
                                   "Post_Pandemic_Mean_Monthly_Demand", "Post_Pandemic_CV", "Ratio_Of_Means",
                                   "CV_Change", "Stable_Across_Periods", "Period_Label"])])
    with st.expander(f"Stable across periods: {len(stable)} (ratio of means 0.8-1.25 and |CV change| <= 0.25; "
                     "a default pending the chief pharmacist)"):
        view = filter_bar(stable, "stable", status="Stable_Rule_Status")
        show_table(view[present(view, ["Brand_Name", "Unit", "Ratio_Of_Means", "CV_Change", "Period_Label",
                                       "Stable_Rule_Status"])])


def data_quality() -> None:
    dq = table("c1_dq_summary")
    as_of_line(dq)
    inactive = table("c1_dq_inactive")
    tiles("data-quality", [("Inactive (no stock, no demand)", len(inactive), "check"),
                           ("Negative stock records",
                            int(dq.set_index("Check").Count.get("Negative stock records (month-ends)", 0)), "attention")])
    show_table(dq[["Check", "Count"]])
    with st.expander(f"Inactive medicines (no stock, no demand): {len(inactive)}"):
        view = filter_bar(inactive, "inactive", status="Status")
        show_table(view[present(view, ["Brand_Name", "Generic_Name", "Unit"])])
    with st.expander("Negative stock records"):
        negative = table("c1_dq_negative_stock")
        show_table(filter_bar(negative, "negative-stock"))
    st.subheader("Expiry lots not matched to a PHARMACY medicine")
    show_table(table("c1_dq_expiry_unmatched_groups"))
    with st.expander("Unmatched expiry items"):
        show_table(table("c1_dq_expiry_unmatched"))
    st.subheader("Expiry exports on disk")
    st.caption("Each export lists the receipt lots expiring in one month (its printed expiration-date range); the "
               "exports carry no run date.")
    show_table(table("c1_dq_expiry_exports"))
    missing = table("c1_dq_expiry_missing")
    if len(missing):
        st.warning(f"{len(missing)} expiry exports are needed for near-expiry and are not on disk.")
        show_table(missing)


def kpis() -> None:
    """§1.3.3: each Key Performance Indicator of Table 1.3.3.1 against its target."""
    table_kpi = table("c1_tab_kpi")
    as_of_line(table_kpi)
    counts = table_kpi.Status.value_counts()
    tiles("kpi", [("Met", int(counts.get("met", 0)), "check"), ("Pending", int(counts.get("pending", 0)), "info"),
                  ("Not met", int(counts.get("not met", 0)), "attention")])
    st.caption("The KPIs measure whether the planning outputs are generated and interpretable; they do not claim "
               "operational improvement. Pending: the output exists but waits for a confirmation the target names.")
    show_table(table_kpi[["KPI", "Target", "Evidence", "Status", "Note"]])


# ------------------------------------------------------------------ Pages and navigation

# (title, URL path, render function, sidebar icon)
PLANNING_PAGES = [
    ("Overview", "overview", overview, "overview"),
    ("Reorder Planning", "reorder-planning", reorder_planning, "cart"),
    ("Waste and Expiry", "waste-and-expiry", waste_expiry, "calendar"),
    ("Medicine Detail", "medicine-detail", medicine_detail, "medicine"),
    ("Analysis and Evidence", "analysis-and-evidence", analysis_evidence, "shield"),
]


def stock_as_of() -> str | None:
    reorder = table("c1_tab_reorder")
    return f"Stock as of {reorder.As_Of_Month.iloc[0]}" if "As_Of_Month" in reorder and len(reorder) else None


def planning_page(title: str, render: Callable[[], None]) -> Callable[[], None]:
    def page() -> None:
        c1_ui.page_header(PLANNING_SECTION, title)
        if DEMO:
            st.warning(DEMO_NOTE)
        if not DATABASE.exists():
            st.error(f"The planning data mart was not found at {DATABASE}. Run the Capstone 1 build first.")
            st.stop()
        c1_ui.topbar(title, stock_as_of())
        st.info(PROXY_NOTE)
        st.caption(DECISION_NOTE)
        render()
        c1_ui.footer()
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
    return "supplementary-" + c1_ui.slug(name)


def sidebar(current: st.Page) -> None:
    """The page buttons: the five planning pages, then the earlier pages as one collapsed group at the bottom."""
    planning_keys = {title: f"sidebar-nav-{c1_ui.slug(title)}" for title, *_ in PLANNING_PAGES}
    earlier_keys = {name: f"sidebar-nav-earlier-{c1_ui.slug(name)}" for name in SUPPLEMENTARY}
    icons = {planning_keys[title]: icon for title, _, _, icon in PLANNING_PAGES} | dict.fromkeys(earlier_keys.values(),
                                                                                                "book")
    with st.sidebar:
        c1_ui.install_styles(icons)
        c1_ui.sidebar_brand()
        c1_ui.nav_group(PLANNING_SECTION)
        for title, page in PAGES.items():
            if c1_ui.nav_button(title, planning_keys[title], page.url_path == current.url_path):
                st.switch_page(page)
        if SUPPLEMENTARY:
            opened = current.url_path in {page.url_path for page in SUPPLEMENTARY.values()}
            with st.expander(EARLIER_GROUP, expanded=opened):
                for name, page in SUPPLEMENTARY.items():
                    if c1_ui.nav_button(EARLIER_LABELS.get(name, name), earlier_keys[name],
                                        page.url_path == current.url_path):
                        st.switch_page(page)


st.set_page_config(page_title="Inpatient Pharmacy Planning", layout="wide", initial_sidebar_state="expanded")
PAGES = {title: st.Page(planning_page(title, render), title=title, url_path=path, default=(n == 0))
         for n, (title, path, render, _) in enumerate(PLANNING_PAGES)}
# The earlier pages are built only when shown: in DEMO mode app/main.py (and the modules it imports) is never read, so
# a demo deployment can leave them out.
SUPPLEMENTARY = {name: st.Page(supplementary_page(name), title=name, url_path=url_path(name))
                 for name in existing_pages()} if SHOW_SUPPLEMENTARY else {}
current = st.navigation(list(PAGES.values()) + list(SUPPLEMENTARY.values()), position="hidden")
sidebar(current)
current.run()
