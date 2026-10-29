"""Inpatient pharmacy planning (Capstone 1): the main DSS app, one st.navigation entry point.

    streamlit run app/capstone1_app.py

Decision first. The sidebar holds the pages a pharmacist uses each month, in order: This month's decisions (/decisions,
the opening page), Reorder Planning (/reorder), Waste and Expiry (/waste), Medicine Detail (/medicine) and, locally (not
in DEMO mode), Monthly Update (/update, app/c1_update_page.py). Under a small "For the panel" label follows Analysis and
Evidence (/evidence): ABC-VED, forecast accuracy, the pandemic period, data quality and the KPIs, each tab with the
earlier annual analysis of the same objective where the DSS database is on disk (app/c1_annual.py; app/main.py still
runs on its own). The root URL and the earlier page addresses (/overview and the long slugs) open the matching page.

Every value shown is a value of the Capstone 1 data mart (database/staging/capstone1/capstone1.duckdb, or CAPSTONE1_DB),
read-only, formatted by app/c1_format.py; the suggested actions restate each medicine's reorder status, ABC class and
suggested order (n x EOQ, the (s, nQ) policy of the planning step). The look is the existing app's visual system, in
light or dark mode (app/c1_ui.py, app/c1_theme.py). The pages show planning estimates for review by pharmacy and
purchasing personnel; they place no orders and rank no option.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

import c1_format
import c1_ui
from c1_format import AT_ROP, BELOW_SS, NEGATIVE, REVIEW_STATUSES
from c1_ui import card, filter_bar, tiles

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = Path(os.environ.get("CAPSTONE1_DB", PROJECT_ROOT / "database" / "staging" / "capstone1" / "capstone1.duckdb"))
PLANNING_SECTION, PANEL_GROUP = "Inpatient pharmacy planning", "For the panel"
# DEMO mode (CAPSTONE1_DEMO=1): the mart is the synthetic one (src/capstone1/demo_data.py), every page says so, and the
# annual analysis, which needs the governed DSS database (CDH data), is left out.
DEMO = os.environ.get("CAPSTONE1_DEMO") == "1"
# The annual analysis needs the existing DSS database; a deployment without it sets CAPSTONE1_SUPPLEMENTARY=0.
SHOW_SUPPLEMENTARY = not DEMO and os.environ.get("CAPSTONE1_SUPPLEMENTARY", "1") == "1"
# The Monthly Update page: local only, never in DEMO mode (its module is not even imported there).
SHOW_UPDATE = not DEMO and os.environ.get("CAPSTONE1_UPDATE", "1") == "1"
DECISIONS, REORDER, WASTE, MEDICINE, EVIDENCE = ("This month's decisions", "Reorder Planning", "Waste and Expiry",
                                                 "Medicine Detail", "Analysis and Evidence")
UPDATE_PAGE = ("Monthly Update", "update", "upload")
# The earlier addresses of the pages, each opening its page.
REDIRECTS = {"overview": DECISIONS, "reorder-planning": REORDER, "waste-and-expiry": WASTE,
             "medicine-detail": MEDICINE, "analysis-and-evidence": EVIDENCE, "monthly-update": UPDATE_PAGE[0]}
DEMO_NOTE = ("Demonstration data: synthetic medicines, demand, stock, costs and expiry lots, generated with a fixed "
             "seed. Not CDH data; no figure on this page describes Calamba Doctors Hospital.")
ASSUMPTION_LINE = ("Planning estimates use assumptions set by the project team (see How these numbers are made). "
                   "The DSS suggests; the pharmacist decides.")
ORDER_RULE_NOTE = ("Suggested order: when a medicine's stock on hand is at or below its reorder point, n x EOQ, with n the "
                   "smallest whole number that brings stock on hand plus the order above the reorder point (the (s, nQ) "
                   "policy; Axsäter, Inventory Control, 3rd ed., 2015). Stock on hand stands in for the inventory "
                   "position (stock on hand plus stock on order): the PHARMACY exports record no quantity on order. EOQ, "
                   "the reorder point and safety stock are not changed by it. Months of cover: (stock on hand + suggested "
                   "order) / the planning month's forecast, blank when nothing is forecast.")
PROXY_NOTE = ("Planning estimates. Lead time (not recorded in CDH data), ordering cost, holding-cost rate and the "
              "service level of each VED class are proponent decisions and assumptions (P); VED classes are the "
              "proponents' assignment by documented clinical criteria, delegated by the chief pharmacist.")
DECISION_NOTE = "Decision support only; final purchasing and inventory decisions rest with authorized CDH personnel."
SUDDEN_CHANGE_NOTE = ("Forecasts follow the patterns in the 2021-2025 records (and, for planning, January-September 2026). "
                      "Sudden changes from emergency admissions, outbreaks, formulary changes or physician prescribing "
                      "behavior may not be captured.")
NEAR_COLUMNS = ["Near_Expiry_Lots", "Near_Expiry_Quantity_Capped", "Near_Expiry_Value_Capped"]
# Reorder Planning: the decision columns first; the CSV keeps every column.
REORDER_COLUMNS = ["Brand_Name", "Suggested_Action", "Reorder_Status", "Planning_Stock", "Reorder_Point",
                   "Suggested_Order", "ABC_VED_Category", "Reliability", "Months_Of_Cover_With_Order", "EOQ",
                   "Order_Multiple", "Unit", "Dosage_Form", "ABC_Planning", "VED", "Service_Level", "Safety_Stock",
                   "Forecast_Planning_Month", "Stock_Status", "Planning_Label"]
# The first eight columns fit the page at 1366px with the sidebar open (an 890px table): each at least its header's
# width, the long text wrapping in taller rows (pixels).
REORDER_WIDTHS = {"Brand_Name": 146, "Suggested_Action": 130, "Reorder_Status": 92, "Planning_Stock": 102,
                  "Reorder_Point": 100, "Suggested_Order": 116, "ABC_VED_Category": 76, "Reliability": 124}
FORECAST_COLUMNS = ["Brand_Name", "Suggested_Action", "Dosage_Form", "ABC_Planning", "Selected_Model", "Volume_Class",
                    "Test_MAE", "Test_RMSE", "Test_MAPE", "Test_MAPE_Excluded_Zero_Months", "Test_WAPE", "Test_MASE",
                    "Reliability", "Prospective_2026_MAE", "Limited_Planning_Estimate"]
ABC_COLUMNS = ["Brand_Name", "Suggested_Action", "Dosage_Form", "ABC_2021", "ABC_2022", "ABC_2023", "ABC_2024",
               "ABC_2025", "ABC_2021_2025", "ABC_Planning", "VED", "VED_Category", "ABC_VED_Category"]
FLAGGED_COLUMNS = ["Brand_Name", "Unit", "Month", "Net_Demand", "Item_Average", "Rule", "Period_Label"]
SENSITIVITY_COLUMNS = ["Scenario_Type", "Scenario", "Baseline_Safety_Stock", "Adjusted_Safety_Stock", "Baseline_ROP",
                       "Adjusted_ROP", "Change_ROP_Pct", "Baseline_EOQ", "Adjusted_EOQ", "Change_EOQ_Pct",
                       "Baseline_Suggested_Order", "Adjusted_Suggested_Order"]
GRID_COLUMNS = ["Lead_Time_Days", "Service_Level", "Holding_Rate", "Ordering_Cost", "Safety_Stock", "Reorder_Point",
                "EOQ", "Suggested_Order"]
EOQ_ONLY = "EOQ cost range"              # the scenarios of ordering cost and holding rate: they change EOQ, not ROP
LOT_COLUMNS = ["Brand_Name", "Suggested_Action", "Expiration_Date", "Lot_No", "Near_Expiry_Capped_Quantity",
               "Near_Expiry_Capped_Value", "Unit", "Dosage_Form"]
FLAGGED_CAPTION = ("Pandemic period: a month of 2022-2023 flagged by the outlier rule (more than 100% above or 50% below "
                   "the item average), replaced by that average in training only and listed here for review.")
GRID_HEADING = "Sensitivity grid: lead time x service level x holding rate x ordering cost"
GRID_CAPTION = ("Every combination of lead time 3/7/14 days, service level 90/95/99%, holding-cost rate 20/30/40% and "
                "ordering cost PHP 250/500/1,000; the baseline is 7 days, the service level of the medicine's VED class "
                "(V 99%, E 95%, D 90%), 30% and PHP 500.")
VED_CAPTION = ("VED by documented clinical criteria (Devnani et al. 2010), never by demand: Vital when the generic name "
               "is in a Vital category (emergency and resuscitation drugs, anaesthetics, neuromuscular blockers and "
               "reversal agents, vasopressors and inotropes, IV antiarrhythmics, anticoagulants and thrombolytics, "
               "insulin, IV fluids and electrolytes, parenteral anti-infectives, parenteral anticonvulsants, antidotes, "
               "oxytocics, blood products and albumin, rabies and tetanus immunoglobulins and vaccines), Essential when "
               "on the PNF and not Vital, Desirable when not on the PNF (config/capstone1_ved_rules.csv). A proponent "
               "assignment (P), delegated by the chief pharmacist. Categories (Gupta et al. 2007): I = AV, AE, AD, BV, "
               "CV; II = BE, BD, CE; III = CD. Medicines with no consumption value are outside the matrix.")
# Reliability labels, from most to least reliable, with their status icon.
RELIABILITY_ICONS = {"Highly reliable": "check", "Acceptable for planning": "check",
                     "Planning use allowed only with reliability status": "warning", "Requires review": "cross",
                     "Requires pharmacy review (insufficient data)": "cross"}
# Reorder Planning lists (the "view" query parameter). The default is the order card's list, so the page opens with
# the card's count. The option is what the URL holds (?view=Could+run+out), so a filtered list can be bookmarked.
VIEWS = {"Reorder now": ("reorder-now", "Below safety stock or at or below ROP: Category I and Vital first, then the "
                                        "lowest stock as a share of the reorder point."),
         "Could run out": ("critical", "Category I or Vital medicines below safety stock."),
         "Do not reorder": ("unused", "No consumption in 2025 with stock held, or excess stock (above ROP + EOQ)."),
         "Check the stock record": ("stock-record", "A negative stock record: no stock-based result until it is "
                                                    "checked.")}
# Waste and Expiry: the lot order (?sort=Soonest+expiry).
SORTS = {"Soonest expiry": (["Expiration_Date", "Near_Expiry_Capped_Value"], [True, False]),
         "Highest value": (["Near_Expiry_Capped_Value", "Expiration_Date"], [False, True])}
NO_CHANGE = "0%"                         # the What-if demand option for "demand as forecast"
TABLE_ROW_WRAP = 72                      # rows tall enough for long text to wrap (Streamlit wraps above 4rem)


@st.cache_data(show_spinner=False)
def _load(database: str, modified: int, query: str) -> pd.DataFrame:
    connection = duckdb.connect(database, read_only=True)
    try:
        return connection.execute(query).df()
    finally:
        connection.close()


def tables() -> frozenset:
    """The tables and views in the mart (a mart built before a view existed lacks it)."""
    return frozenset(_load(str(DATABASE), DATABASE.stat().st_mtime_ns,
                           "SELECT table_name FROM information_schema.tables").table_name)


def table(name: str) -> pd.DataFrame:
    """A mart table or view, read-only; cached per mart file and its modification time, so a rebuilt mart, or another
    mart, is read afresh."""
    return _load(str(DATABASE), DATABASE.stat().st_mtime_ns, f'SELECT * FROM "{name}"')


def present(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [c for c in columns if c in frame]


def rows_for(frame: pd.DataFrame, key: object, name: str) -> pd.DataFrame:
    """One medicine's rows: by Medicine_Key where the table has it, else by brand name."""
    return frame[frame.Medicine_Key.eq(key)] if "Medicine_Key" in frame else frame[frame.Brand_Name.eq(name)]


def first_value(frame: pd.DataFrame, column: str) -> object:
    if column in frame and len(frame) and pd.notna(frame[column].iloc[0]):
        return c1_format.sentence(frame[column].iloc[0])
    return "not available"


def as_of_text() -> str | None:
    reorder = table("c1_tab_reorder")
    return c1_format.month(reorder.As_Of_Month.iloc[0]) if "As_Of_Month" in reorder and len(reorder) else None


# ------------------------------------------------------------------ shared lists

def reorder_list() -> pd.DataFrame:
    """c1_tab_reorder with each medicine's ABC-VED category and its suggested action."""
    reorder = table("c1_tab_reorder")
    abc = table("c1_tab_abc_ved")
    on = next((c for c in ("Medicine_Key", "Brand_Name") if c in abc and c in reorder), None)
    if "ABC_VED_Category" in abc and "ABC_VED_Category" not in reorder and on:
        reorder = reorder.merge(abc[[on, "ABC_VED_Category"]].drop_duplicates(on), on=on, how="left")
    return c1_format.with_action(reorder)


def priority(frame: pd.DataFrame) -> pd.DataFrame:
    """Category I or Vital first, then the lowest stock as a share of the reorder point, then the name."""
    vital = frame.get("VED", pd.Series(index=frame.index, dtype=object)).eq("V")
    first = frame.get("ABC_VED_Category", pd.Series(index=frame.index, dtype=object)).eq("I") | vital
    share = (frame.Planning_Stock / frame.Reorder_Point.where(frame.Reorder_Point > 0)).fillna(float("inf"))
    return (frame.assign(_first=(~first).astype(int), _share=share)
            .sort_values(["_first", "_share", "Brand_Name"]).drop(columns=["_first", "_share"]))


def selections(reorder: pd.DataFrame) -> dict[str, pd.Series]:
    """The rows behind the decision cards and the Reorder Planning lists, from existing statuses only."""
    status = reorder.Reorder_Status
    category_one = reorder.get("ABC_VED_Category", pd.Series(index=reorder.index, dtype=object)).eq("I")
    vital = reorder.get("VED", pd.Series(index=reorder.index, dtype=object)).eq("V")
    unused = reorder.Suggested_Action.eq(c1_format.DO_NOT_REORDER)
    no_use = unused & reorder.ABC_Planning.eq(c1_format.NO_CONSUMPTION) & reorder.Planning_Stock.gt(0)
    excess = unused & reorder.get("Excess_Stock", pd.Series(False, index=reorder.index)).fillna(False).astype(bool)
    return {"reorder-now": status.isin(REVIEW_STATUSES), "critical": (category_one | vital) & status.eq(BELOW_SS),
            "no-use": no_use, "excess": excess, "unused": unused, "stock-record": status.eq(NEGATIVE)}


def seed(key: str, options: list, parse=lambda text: text) -> None:
    """A bookmarked view: the URL's value (?view=Could+run+out) presets its widget once; an unknown value is ignored.
    The widgets are not bound to the URL (st.switch_page cannot clear a bound parameter): seed and keep_in_url do it."""
    if key in st.session_state or key not in st.query_params:
        return
    value = parse(st.query_params[key])
    if value in options:
        st.session_state[key] = value


def keep_in_url(key: str, value: object, default: object, text=str) -> None:
    """The widget's value in the URL, so the view can be bookmarked; the default stays out of it."""
    if value is None or value == default:
        if key in st.query_params:
            del st.query_params[key]
    elif st.query_params.get(key) != text(value):
        st.query_params[key] = text(value)


def open_medicine(key: object) -> None:
    """Medicine Detail for one medicine; the URL names it (?medicine=<brand name>), as the picker does."""
    st.session_state["medicine"] = key
    names = medicine_names()
    st.switch_page(PAGES[MEDICINE], query_params={"medicine": str(names.get(key, key))})


def medicine_names() -> dict:
    """Medicine_Key -> brand name, in name order: the medicines of the forecast table (Medicine Detail's picker)."""
    forecast = table("c1_tab_forecast").sort_values("Brand_Name")
    return dict(zip(forecast.Medicine_Key, forecast.Brand_Name))


def show(frame: pd.DataFrame, key: str, **options) -> None:
    """A medicine list: clicking a medicine name opens Medicine Detail for it."""
    picked = c1_ui.show_table(frame, key=key, link=True, **options)
    if picked is not None:
        open_medicine(picked)


def download(frame: pd.DataFrame, name: str, key: str) -> None:
    st.download_button(f"Download CSV ({len(frame):,} rows, all columns)", frame.to_csv(index=False).encode("utf-8"),
                       file_name=name, mime="text/csv", key=key)


# ------------------------------------------------------------------ This month's decisions

def last_updated(reorder: pd.DataFrame) -> str | None:
    """"Data through <as-of month> · refreshed <date the mart file was written>" (the mart in use: an update or a
    rollback replaces the file)."""
    if "As_Of_Month" not in reorder or not len(reorder):
        return None
    month = pd.Period(reorder.As_Of_Month.iloc[0], freq="M")
    written = datetime.fromtimestamp(DATABASE.stat().st_mtime)
    return f"Data through {month.strftime('%b %Y')} · refreshed {written.day} {written.strftime('%b %Y')}"


def go(page: str, presets: dict[str, object], params: dict[str, str]) -> None:
    """Open a page already filtered: the presets set its widgets, the query parameters make the view bookmarkable."""
    for name, value in presets.items():
        st.session_state[name] = value
    st.switch_page(PAGES[page], query_params=params)


def decisions() -> None:
    reorder = reorder_list()
    if not DEMO and (updated := last_updated(table("c1_tab_reorder"))):
        st.caption(updated)
    chosen = selections(reorder)
    now = reorder[chosen["reorder-now"]]
    cost = now.Suggested_Order * now.Unit_Cost if {"Suggested_Order", "Unit_Cost"} <= set(now) \
        else pd.Series(dtype=float)
    order_value, priced = cost.sum(min_count=1) if len(cost) else float("nan"), int(cost.notna().sum())
    vital_now = int(now.VED.eq("V").sum()) if "VED" in now else 0
    critical = reorder[chosen["critical"]]
    no_use, excess = int(chosen["no-use"].sum()), int(chosen["excess"].sum())
    unused, both = int(chosen["unused"].sum()), int((chosen["no-use"] & chosen["excess"]).sum())
    near = table("c1_tab_near_expiry")
    review = table("c1_tab_waste_review")
    near_status = review.Near_Expiry_Status.iloc[0] if len(review) and "Near_Expiry_Status" in review else ""
    top = priority(now) if len(now) else priority(reorder)
    top_name = top.Brand_Name.iloc[0] if len(top) else None

    first, second, third = st.columns(3)
    with first:
        if c1_ui.question_card("order", "What do I order now, and how much?", f"{len(now):,} medicines",
                               f"<strong>{vital_now:,}</strong> Vital. Suggested orders "
                               f"<strong>{c1_format.pesos(order_value)}</strong> (suggested order x unit cost, "
                               f"{priced:,} priced)."):
            go(REORDER, {"view": "Reorder now", "all": False}, {"view": "Reorder now"})
    with second:
        if c1_ui.question_card("run-out", "Which critical medicines could run out?", f"{len(critical):,} medicines",
                               "Category I or Vital, below safety stock.", attention=len(critical) > 0):
            go(REORDER, {"view": "Could run out", "all": False}, {"view": "Could run out"})
    with third:
        lots, value = lots_with_stock(near)
        if c1_ui.question_card("expiry", "What is expiring, and what do I do with it?", f"{lots:,} lots",
                               f"{html_escape(expiry_note(near, near_status))} <strong>{c1_format.pesos(value)}"
                               "</strong>, capped at stock on hand. Use the soonest first."):
            go(WASTE, {"sort": "Soonest expiry"}, {"sort": "Soonest expiry"})
    fourth, fifth, _ = st.columns(3)
    with fourth:
        if c1_ui.question_card("unused", "What is sitting unused?", f"{unused:,} medicines",
                               f"Do not reorder: <strong>{no_use:,}</strong> with no consumption in 2025 and stock "
                               f"held, <strong>{excess:,}</strong> with excess stock (above ROP + EOQ)"
                               + (f"; {both:,} counted in both." if both else ".")):
            go(REORDER, {"view": "Do not reorder", "all": False}, {"view": "Do not reorder"})
    with fifth:
        if c1_ui.question_card("what-if", "What if the supplier is late or demand rises?",
                               top_name if top_name else "no medicine",
                               "The top-priority medicine first: lead time 3/7/14 days, service level 90/95/99%, "
                               "demand -30% to +30%.", name_answer=True):
            presets = {"view": "Reorder now", "all": False}
            params = {"view": "Reorder now", "whatif": "1"}
            if top_name:
                presets["wi_medicine"] = top_name
                params["wi_medicine"] = top_name
            go(REORDER, presets, params)

    with card("stock-health", "Stock health"):
        action_tiles(reorder, "stock-health-actions")
        action_chart(reorder)
        with st.expander("Stock value, data checks and the stock-health table"):
            stock_health_details()


def action_tiles(reorder: pd.DataFrame, name: str) -> None:
    """The medicines by suggested action, one tile per action (they add up to the planned medicines), in the terms of
    the Suggested action column and the action chart."""
    status, action = reorder.Reorder_Status, reorder.Suggested_Action
    chosen = selections(reorder)
    no_use, excess = int(chosen["no-use"].sum()), int(chosen["excess"].sum())
    both = int((chosen["no-use"] & chosen["excess"]).sum())
    tiles(name, [
        ("Reorder now", int(chosen["reorder-now"].sum()), "procurement",
         f"{int(status.eq(AT_ROP).sum()):,} at or below ROP, {int(status.eq(BELOW_SS).sum()):,} below safety stock"),
        (c1_format.NO_ORDER, int(action.eq(c1_format.NO_ORDER).sum()), "check", "above ROP"),
        (c1_format.NO_DEMAND_ACTION, int(action.eq(c1_format.NO_DEMAND_ACTION).sum()), "info",
         "ROP 0 or next-month forecast below 0.5 units"),
        (c1_format.DO_NOT_REORDER, int(chosen["unused"].sum()), "cross",
         f"{no_use:,} no consumption in 2025 with stock held, {excess:,} excess stock"
         + (f" ({both:,} both)" if both else "")),
        (c1_format.CHECK_RECORD, int(action.eq(c1_format.CHECK_RECORD).sum()), "attention", "negative stock record")])


ACTION_CHART_ORDER = ["Reorder now: below safety stock", "Reorder now: at or below ROP", c1_format.CHECK_RECORD,
                      c1_format.DO_NOT_REORDER, c1_format.NO_ORDER, c1_format.NO_DEMAND_ACTION]


def action_chart(reorder: pd.DataFrame) -> None:
    """The medicines by suggested action as horizontal bars, in the terms of the tiles (Reorder now split by status)."""
    st.subheader("Medicines by suggested action")
    status = reorder.Reorder_Status
    terms = reorder.Suggested_Action.where(~status.isin(REVIEW_STATUSES),
                                           "Reorder now: " + status.map(c1_format.status_term).str.lower()
                                           .str.replace("rop", "ROP", regex=False))
    counts = terms.value_counts()
    order = [t for t in ACTION_CHART_ORDER if t in counts] + [t for t in counts.index if t not in ACTION_CHART_ORDER]
    c1_ui.bar_chart(counts.reindex(order).rename("Medicines").rename_axis("Suggested action"), horizontal=True,
                    value_title="Medicines", order=order)


def html_escape(text: object) -> str:
    import html
    return html.escape(str(text))


def stock_health_details() -> None:
    health = table("c1_tab_stock_health")
    values = health.set_index("Metric").Value if len(health) else pd.Series(dtype=object)
    review = table("c1_tab_waste_review")
    tiles("stock-health", [(m, values[m], icon) for m, icon in (
        ("Active medicines (demand in the last 12 months)", "medicine"), ("Class A medicines (2025)", "validation"),
        ("Reorder review count", "procurement"), ("Near-expiry count", "expiry")) if m in values])
    unused_tiles(review, "review-counts")
    st.subheader("Stock value at month-end (PHP)")
    trend = table("c1_tab_stock_trend")
    c1_ui.line_chart(trend.set_index("Month").Stock_Value.rename("Stock value (PHP)").map(float), y_title="PHP")
    c1_ui.show_table(health[["Metric", "Value", "Note"]], row_height=TABLE_ROW_WRAP)
    data_check_status()


def unused_tiles(review: pd.DataFrame, name: str) -> None:
    """Do not reorder first (the count of "What is sitting unused?"), then the slow-moving and excess-stock medicines of
    the review list, each with how many of them are also Do not reorder. Slow-moving (no use in the last 3 months, or
    more than 6 months of stock at the last 12 months' use) is a watch list, not a reorder rule."""
    reorder = reorder_list()
    unused = selections(reorder)["unused"]
    on = "Medicine_Key" if "Medicine_Key" in review and "Medicine_Key" in reorder else "Brand_Name"
    also = review[on].isin(set(reorder.loc[unused, on]))
    slow, excess = (review[c].fillna(False).astype(bool) for c in ("Slow_Moving", "Excess_Stock"))

    def overlap(flag: pd.Series) -> str:
        both = int((flag & also).sum())
        return "all of them are also Do not reorder" if both == int(flag.sum()) and both else \
            f"{both:,} of them are also Do not reorder"
    tiles(name, [(c1_format.DO_NOT_REORDER, int(unused.sum()), "cross",
                  "no consumption in 2025 with stock held, or excess stock (above ROP + EOQ)"),
                 ("Slow-moving", int(slow.sum()), "expiry", f"watch, use first; {overlap(slow)}"),
                 ("Excess stock", int(excess.sum()), "expiry", overlap(excess))])


def data_check_status() -> None:
    dq = table("c1_dq_summary")
    inactive = table("c1_dq_inactive")
    missing = table("c1_dq_expiry_missing")
    tiles("data-checks", [("Inactive (no stock, no demand)", len(inactive), "check"),
                          ("Negative stock records",
                           int(dq.set_index("Check").Count.get("Negative stock records (month-ends)", 0)), "attention")])
    if len(missing):
        st.caption(f"{len(missing):,} expiry exports are needed for near-expiry and are not on disk.")
    st.page_link(PAGES[EVIDENCE], label="Full checks: Analysis and Evidence")


# ------------------------------------------------------------------ Reorder Planning

def reorder_planning() -> None:
    reorder = reorder_list()
    chosen = selections(reorder)
    in_review = chosen["reorder-now"]
    with card("reorder"):
        tiles("reorder", [("Reorder now", int(in_review.sum()), "procurement",
                           f"{int(reorder.Reorder_Status.eq(AT_ROP).sum()):,} at or below ROP, "
                           f"{int(reorder.Reorder_Status.eq(BELOW_SS).sum()):,} below safety stock"),
                          ("Vital: reorder now", int((in_review & reorder.VED.eq("V")).sum()) if "VED" in reorder
                           else "not available", "attention"),
                          (c1_format.CHECK_RECORD, int(reorder.Reorder_Status.eq(NEGATIVE).sum()), "attention")])
        action_chart(reorder)
        left, right = st.columns([3, 1], vertical_alignment="bottom")
        seed("view", list(VIEWS))
        seed("all", [True], parse=lambda text: text.lower() == "true")
        view_label = left.selectbox("List", list(VIEWS), key="view")
        show_all = right.toggle(f"Show all {len(reorder):,}", key="all")
        keep_in_url("view", view_label, next(iter(VIEWS)))
        keep_in_url("all", show_all, False, text=lambda value: "true")
        view_name, view_note = VIEWS[view_label]
        st.caption(f"All {len(reorder):,} planned medicines, by name." if show_all else view_note)
        listed = reorder if show_all else reorder[chosen[view_name]]
        listed = priority(listed) if not show_all and view_name in ("reorder-now", "critical") \
            else listed.sort_values("Brand_Name")
        view = filter_bar(listed, "reorder", status="Reorder_Status")
        show(view[present(view, ["Medicine_Key", *REORDER_COLUMNS])], key="reorder-table", widths=REORDER_WIDTHS,
             row_height=TABLE_ROW_WRAP)
        download(view, "reorder_planning.csv", "reorder-csv")
    with c1_ui.collapsible("what-if", "What if?", expanded=st.query_params.get("whatif") == "1"):
        what_if(reorder)


def what_if(reorder: pd.DataFrame) -> None:
    """One medicine's baseline beside an adjusted case: lead time and service level from the sensitivity grid, or a
    demand change from the one-at-a-time scenarios. Both come from the mart; nothing is computed here."""
    sensitivity = table("c1_tab_sensitivity")
    assumptions = table("c1_tab_assumptions")
    grid = table("c1_tab_sensitivity_grid")
    names = sorted(sensitivity.Brand_Name.dropna().unique())
    if names and st.query_params.get("wi_medicine") in names and "wi_medicine" not in st.session_state:
        st.session_state["wi_medicine"] = st.query_params["wi_medicine"]
    if names and st.session_state.get("wi_medicine") not in names:
        ranked = priority(reorder[reorder.Brand_Name.isin(names)])
        st.session_state["wi_medicine"] = ranked.Brand_Name.iloc[0] if len(ranked) else names[0]
    picked = c1_ui.picker("Medicine", names, key="wi_medicine") if names else None
    if picked is not None and st.query_params.get("whatif") == "1":
        keep_in_url("wi_medicine", picked, None)
    view = sensitivity[sensitivity.Brand_Name.eq(picked)] if picked else sensitivity.iloc[0:0]
    own = grid[grid.Brand_Name.eq(picked)] if picked else grid.iloc[0:0]
    inputs = planning_inputs(assumptions)
    leads = sorted(grid.Lead_Time_Days.dropna().unique()) if "Lead_Time_Days" in grid else []
    levels = sorted(grid.Service_Level.dropna().unique()) if "Service_Level" in grid else []
    if len(view) and leads and levels:
        base = view.iloc[0]
        level = reorder.loc[reorder.Brand_Name.eq(picked), "Service_Level"] if "Service_Level" in reorder else []
        base_lead = inputs.get("lead_time_days", leads[len(leads) // 2])
        base_level = float(level.iloc[0]) if len(level) and pd.notna(level.iloc[0]) else levels[len(levels) // 2]
        demands = demand_options(view)
        lead_col, level_col, demand_col = st.columns(3)
        lead = lead_col.selectbox("Lead time", leads, index=leads.index(base_lead) if base_lead in leads else 0,
                                  format_func=lambda d: f"{d:,.0f} days", key="wi_lead")
        service = level_col.selectbox("Service level", levels, index=levels.index(base_level)
                                      if base_level in levels else 0, format_func=c1_format.share, key="wi_service")
        demand = demand_col.selectbox("Demand change", demands, index=demands.index(NO_CHANGE), key="wi_demand")
        adjusted = adjusted_case(view, own, inputs, lead, service, base_lead, base_level, demand)
        # baseline, then adjusted, each a full row: four tiles in half a page would break their labels
        st.markdown(f"**Baseline** ({base_lead:,.0f} days, the VED class's service level, demand as forecast)")
        tiles("what-if-baseline", [("Baseline ROP", c1_format.whole(base.Baseline_ROP), "procurement"),
                                   ("Baseline EOQ", c1_format.whole(base.Baseline_EOQ), "procurement"),
                                   ("Baseline suggested order",
                                    c1_format.whole(base.get("Baseline_Suggested_Order")), "procurement"),
                                   ("Baseline safety stock", c1_format.whole(base.Baseline_Safety_Stock),
                                    "governance")])
        st.markdown(f"**Adjusted** ({lead:,.0f} days, {c1_format.share(service)}, demand {demand})")
        if adjusted is None:
            st.info("Not in the mart: the grid varies lead time and service level with demand as forecast, and "
                    "the demand scenarios vary demand alone. Set the demand change to 0%, or lead time and service "
                    "level to the baseline.")
        else:
            tiles("what-if-adjusted", [("Adjusted ROP", c1_format.whole(adjusted["rop"]), "procurement"),
                                       ("Adjusted EOQ", c1_format.whole(adjusted["eoq"]), "procurement"),
                                       ("Adjusted suggested order", c1_format.whole(adjusted["order"]),
                                        "procurement"),
                                       ("Adjusted safety stock", c1_format.whole(adjusted["ss"]), "governance")])
        moves_rop = ~view.Scenario_Type.astype(str).eq(EOQ_ONLY)
        st.subheader("Change in the reorder point by scenario")
        rop = view[moves_rop]
        labels = rop.Scenario_Type.astype(str) + ": " + rop.Scenario.astype(str)
        c1_ui.bar_chart(pd.Series(rop.Change_ROP.to_numpy(), index=pd.Index(labels, name="Scenario"),
                                  name="Change in ROP"), horizontal=True, value_title="Change in reorder point",
                        order=labels.tolist(), value_format=",.1f")
        costs = view[~moves_rop]
        if len(costs) and "Change_EOQ_Pct" in costs:
            st.subheader("Change in EOQ by ordering cost and holding rate (%)")
            st.caption("Ordering cost and holding rate change EOQ only; the reorder point stays the same.")
            names = costs.Scenario.astype(str)
            c1_ui.bar_chart(pd.Series(costs.Change_EOQ_Pct.to_numpy(), index=pd.Index(names, name="Scenario"),
                                      name="Change in EOQ (%)"), horizontal=True, value_title="Change in EOQ (%)",
                            order=names.tolist(), value_format=",.1f")
    with st.expander(f"Every scenario for this medicine, baseline beside adjusted ({len(view):,})"):
        c1_ui.show_table(view[present(view, SENSITIVITY_COLUMNS)])
    with st.expander(f"{GRID_HEADING} ({len(own):,} combinations)"):
        st.subheader(GRID_HEADING)
        st.caption(GRID_CAPTION)
        c1_ui.show_table(own[present(own, GRID_COLUMNS)])
        download(own, "sensitivity_grid.csv", "grid-csv")


def planning_inputs(assumptions: pd.DataFrame) -> dict[str, float]:
    """The planning inputs of the mart (c1_tab_assumptions): input name -> value."""
    if not {"Input", "Value"} <= set(assumptions):
        return {}
    values = pd.to_numeric(assumptions.Value, errors="coerce")
    return {name: float(value) for name, value in zip(assumptions.Input, values) if pd.notna(value)}


def demand_options(view: pd.DataFrame) -> list[str]:
    """The demand changes of the one-at-a-time scenarios ("-30%" ... "+30%") and "0%", in order."""
    named = view[view.Scenario_Type.astype(str).str.startswith("Demand (illustrative)")].Scenario.astype(str).tolist()
    return sorted(dict.fromkeys([*named, NO_CHANGE]), key=_percent)


def _percent(text: str) -> float:
    try:
        return float(text.rstrip("%"))
    except ValueError:
        return 0.0


def adjusted_case(view: pd.DataFrame, grid: pd.DataFrame, inputs: dict[str, float], lead: float, service: float,
                  base_lead: float, base_level: float, demand: str) -> dict | None:
    """The adjusted case from the mart: a grid row (lead time and service level at the baseline costs) when demand is
    as forecast, else the demand scenario at the baseline lead time and service level; None for any other mix."""
    if demand == NO_CHANGE:
        rows = grid[grid.Lead_Time_Days.eq(lead) & (grid.Service_Level - service).abs().lt(1e-9)]
        for column, name in (("Holding_Rate", "holding_rate_annual"), ("Ordering_Cost", "ordering_cost_php")):
            baseline = inputs.get(name)
            if baseline is not None and column in rows and (rows[column] - baseline).abs().lt(1e-9).any():
                rows = rows[(rows[column] - baseline).abs().lt(1e-9)]
        if not len(rows):
            return None
        r = rows.iloc[0]
        return {"rop": r.Reorder_Point, "eoq": r.EOQ, "ss": r.Safety_Stock, "order": r.get("Suggested_Order")}
    if lead != base_lead or abs(service - base_level) > 1e-9:
        return None
    rows = view[view.Scenario_Type.astype(str).str.startswith("Demand (illustrative)") & view.Scenario.eq(demand)]
    if not len(rows):
        return None
    r = rows.iloc[0]
    return {"rop": r.Adjusted_ROP, "eoq": r.Adjusted_EOQ, "ss": r.Adjusted_Safety_Stock,
            "order": r.get("Adjusted_Suggested_Order")}


# ------------------------------------------------------------------ Waste and Expiry

def waste_expiry() -> None:
    review = c1_format.with_action(table("c1_tab_waste_review"), table("c1_tab_reorder"))
    near_status = review.Near_Expiry_Status.iloc[0] if len(review) else "not available"
    with card("waste"):
        unused_tiles(review, "waste")
        if near_status != "available":
            missing = table("c1_dq_expiry_missing")
            months = sorted(missing.Month) if len(missing) and "Month" in missing else []
            span = (f" ({len(months)} monthly exports, {c1_format.month(months[0])} to {c1_format.month(months[-1])}; "
                    "listed under Analysis and Evidence, Data quality)") if months else ""
            st.markdown(f"**Near-expiry as of {as_of_text() or 'the as-of month'} is not available yet:** the expiry "
                        f"exports for the next 180 days are not loaded{span}. Until they are, the worked example below "
                        "shows the same calculation on an earlier month.")
    with card("near-expiry"):
        near_expiry_section()
    with card("expired"):
        st.subheader("Expired value by month (PHP; upper bound, unmatched lots excluded)")
        timeline = table("c1_tab_expiry_timeline")
        c1_ui.bar_chart(timeline.set_index("Month").Expired_Value_Capped.rename("Expired value (PHP)"),
                        value_title="PHP", value_format=",.2f")
        st.caption("Expired value: the received quantity of each lot expiring in the month, capped at the medicine's "
                   "stock at that month-end, x land cost. An upper bound: the exports do not record what was left of "
                   "each lot. Lots not matched to a PHARMACY medicine are excluded (see Data Quality).")
    with card("waste-review"):
        st.caption("Review list: medicines with planning stock above 0. Medicines with no stock and no demand are "
                   "counted on the Data Quality page.")
        view = filter_bar(review, "waste-review", status="Review_Reason")
        show(view[present(view, ["Medicine_Key", "Brand_Name", "Suggested_Action", "Unit", "Dosage_Form",
                                 "ABC_Planning", "Planning_Stock", "Demand_Last_12_Months", "Months_Of_Cover",
                                 "Slow_Moving", "Excess_Stock", "Expired_Value_12m_Capped", "Expired_Value_Label",
                                 *(NEAR_COLUMNS if near_status == "available" else []), "Review_Reason"])]
             .sort_values("Brand_Name"), key="waste-review-table")


def near_lots() -> pd.DataFrame:
    """The lots in the near-expiry window, one row per lot, from the expiry fact table."""
    if "Fact_Expiry_Monitoring" not in tables():
        return pd.DataFrame()
    return _load(str(DATABASE), DATABASE.stat().st_mtime_ns, """
        SELECT x.Medicine_Key, m.Brand_Name, m.Unit, m.Dosage_Form, x.Expiration_Date, x.Lot_No,
               x.Near_Expiry_Capped_Quantity, x.Near_Expiry_Capped_Value
        FROM Fact_Expiry_Monitoring x JOIN Dim_Medicine m USING (Medicine_Key)
        WHERE x.Matched AND x.Near_Expiry_Window""")


def lots_with_stock(near: pd.DataFrame) -> tuple[int, float]:
    """The near-expiry lots that still hold stock at the as-of month-end (capped quantity above 0) and their value
    capped at that stock; without the lot table, the near-expiry table's lots and value."""
    lots = near_lots()
    if len(lots):
        held = lots[lots.Near_Expiry_Capped_Quantity.fillna(0).gt(0)]
        return len(held), held.Near_Expiry_Capped_Value.sum()
    return (int(near.Near_Expiry_Lots.sum()), near.Near_Expiry_Value_Capped.sum()) if len(near) else (0, float("nan"))


def expiry_note(near: pd.DataFrame, near_status: str) -> str:
    """"Worked example as of 31 Mar 2026: no export after Sep 2026 is loaded yet." while the next 180 days' exports are
    missing; else the as-of date."""
    if not len(near) or "Near_Expiry_As_Of" not in near:
        return ""
    when = c1_format.day(near.Near_Expiry_As_Of.iloc[0])
    if near_status == "available":
        return f"As of {when}."
    return f"Worked example as of {when}: no export after {as_of_text() or 'the latest month'} is loaded yet."


def near_expiry_section() -> None:
    """Near-expiry as of the latest month whose next 180 days the expiry exports cover: the current month once its
    exports are loaded, else a worked example on an earlier month, compared with what then actually expired."""
    near = table("c1_tab_near_expiry")
    st.subheader("Near-expiry (180 days; upper bound, capped at the as-of month-end stock)")
    if not len(near):
        return
    st.markdown(near.Label.iloc[0] + ".")
    held, _ = lots_with_stock(near)
    tiles("near-expiry", [("Lots", int(near.Near_Expiry_Lots.sum()), "expiry", f"{held:,} with stock on hand"),
                          ("Medicines", len(near), "medicine"),
                          ("Value capped (PHP)", c1_format.pesos(near.Near_Expiry_Value_Capped.sum()), "procurement")])
    check = table("c1_tab_near_expiry_check")
    if len(check):
        st.caption("The worked example against what the same exports show actually expired in the months of its window.")
        c1_ui.show_table(check[["Measure", "Lots", "Medicines", "Value_Capped_PHP"]], row_height=TABLE_ROW_WRAP)
    lots = near_lots()
    if len(lots):
        seed("sort", list(SORTS))
        order = st.selectbox("Sort lots by", list(SORTS), key="sort",
                             help="Soonest expiry: then the highest value first. Highest value: then the soonest.")
        keep_in_url("sort", order, next(iter(SORTS)))
        keys, ascending = SORTS[order]
        lots = lots.sort_values([*keys, "Brand_Name"], ascending=[*ascending, True]).assign(Suggested_Action="Use first")
        left = lots.Near_Expiry_Capped_Quantity.fillna(0).gt(0)
        st.caption(f"{int(left.sum()):,} lots with stock left at the as-of month-end, one row per lot. "
                   f"{int((~left).sum()):,} more lots in the window had no stock left (capped quantity 0) and are "
                   "not listed.")
        lots = lots[left]
        show(lots[present(lots, ["Medicine_Key", *LOT_COLUMNS])], key="near-lots-table")
    view = filter_bar(near.assign(Suggested_Action="Use first")
                      .sort_values(["First_Expiry", "Near_Expiry_Value_Capped", "Brand_Name"],
                                   ascending=[True, False, True]), "near-expiry")
    show(view[present(view, ["Medicine_Key", "Brand_Name", "Suggested_Action", "Unit", "Dosage_Form",
                             "Near_Expiry_Lots", "First_Expiry", "Last_Expiry", "Stock_At_As_Of",
                             "Near_Expiry_Quantity_Capped", "Near_Expiry_Value_Capped"])], key="near-expiry-table")


# ------------------------------------------------------------------ Medicine Detail

def medicine_detail() -> None:
    forecast = table("c1_tab_forecast")
    choices = forecast.sort_values("Brand_Name")
    names = dict(zip(choices.Medicine_Key, choices.Brand_Name))
    if not names:
        return
    wanted = st.query_params.get("medicine")             # a bookmark names the medicine by its brand name
    by_name = {n: k for k, n in names.items()}
    if wanted is not None and "medicine" not in st.session_state and (wanted in names or wanted in by_name):
        st.session_state["medicine"] = wanted if wanted in names else by_name[wanted]
    if st.session_state.get("medicine") not in names:
        ranked = priority(reorder_list())
        keys = ranked.Medicine_Key if "Medicine_Key" in ranked else ranked.Brand_Name.map({n: k for k, n in names.items()})
        category_one = keys[ranked.get("ABC_VED_Category", pd.Series(index=ranked.index, dtype=object)).eq("I")
                            & keys.isin(list(names))]
        st.session_state["medicine"] = category_one.iloc[0] if len(category_one) else next(iter(names))
    search = st.text_input("Search medicine", key="detail-search", placeholder="Brand or generic name")
    options = [k for k, n in names.items() if not search or search.lower() in str(n).lower()] or list(names)
    if st.session_state["medicine"] not in options:
        options = [st.session_state["medicine"], *options]
    key = c1_ui.picker("Medicine", options, key="medicine", format_func=names.get)
    keep_in_url("medicine", names[key], None)
    name = names[key]
    reorder = rows_for(reorder_list(), key, name)
    abc = rows_for(table("c1_tab_abc_ved"), key, name)
    own_forecast = forecast[forecast.Medicine_Key.eq(key)]
    with card("detail-class", "Classification"):
        tiles("detail-class", [("ABC class", first_value(abc, "ABC_Planning"), "validation"),
                               ("VED", first_value(abc, "VED"), "governance"),
                               ("ABC-VED category", first_value(abc, "ABC_VED_Category"), "governance"),
                               ("Forecast model", first_value(own_forecast, "Selected_Model"), "forecast"),
                               ("Reliability", first_value(own_forecast, "Reliability"),
                                RELIABILITY_ICONS.get(own_forecast.Reliability.iloc[0] if len(own_forecast) else "",
                                                      "check"))])
        c1_ui.show_table(abc[present(abc, [c for c in ABC_COLUMNS if c != "Suggested_Action"])])
        if "VED_Basis" in abc and len(abc) and pd.notna(abc.VED_Basis.iloc[0]):
            st.caption(f"VED basis: {abc.VED_Basis.iloc[0]}")
    with card("detail-forecast", "Demand and forecast"):
        st.caption(SUDDEN_CHANGE_NOTE)
        series = table("c1_tab_forecast_series")
        own_series = series[series.Medicine_Key.eq(key)]
        c1_ui.line_chart(own_series.pivot_table(index="Month", columns="Series", values="Value"), y_title="Units")
        c1_ui.show_table(own_forecast[present(own_forecast, [c for c in FORECAST_COLUMNS if c != "Suggested_Action"])])
        st.subheader("Pandemic period (2021-2023)")
        st.caption(FLAGGED_CAPTION)
        flagged = rows_for(table("c1_tab_covid_flagged_months"), key, name)
        if len(flagged):
            c1_ui.show_table(flagged[present(flagged, FLAGGED_COLUMNS)])
        else:
            st.markdown("No flagged months for this medicine.")
    with card("detail-stock", "Stock and reorder"):
        c1_ui.show_table(reorder[present(reorder, REORDER_COLUMNS)])
    with card("detail-sensitivity", "What if"):
        planned = name in set(table("c1_tab_sensitivity").Brand_Name.dropna())
        st.markdown("This medicine's lead time, service level and demand scenarios, baseline beside adjusted, are in "
                    "What if? on Reorder Planning." if planned else
                    "No scenarios for this medicine: it has no reorder plan (no forecast).")
        if st.button("Open in What if?", key="open-what-if", type="primary", disabled=not planned):
            go(REORDER, {"wi_medicine": name}, {"whatif": "1", "wi_medicine": name})


# ------------------------------------------------------------------ Analysis and Evidence

ANALYSIS_TABS = ["ABC-VED", "Forecast accuracy", "Pandemic period", "Data quality", "KPIs"]


def annual(section: str) -> None:
    if SHOW_SUPPLEMENTARY:
        import c1_annual
        if c1_annual.available():
            getattr(c1_annual, section)()


def analysis_evidence() -> None:
    for tab, render in zip(st.tabs(ANALYSIS_TABS), (abc_ved, forecast_evidence, covid_period, data_quality, kpis)):
        with tab, card(f"analysis-{render.__name__}"):
            render()


def abc_ved() -> None:
    abc = c1_format.with_action(table("c1_tab_abc_ved"), table("c1_tab_reorder"))
    summary = table("c1_tab_abc_summary")
    planning = abc.ABC_Planning.value_counts()
    tiles("abc", [("Class A", int(planning.get("A", 0)), "validation"), ("Class B", int(planning.get("B", 0)), "validation"),
                  ("Class C", int(planning.get("C", 0)), "validation")])
    classes = abc.VED.value_counts() if "VED" in abc else pd.Series(dtype=int)
    categories = abc.ABC_VED_Category.value_counts() if "ABC_VED_Category" in abc else pd.Series(dtype=int)
    tiles("ved", [("Vital", int(classes.get("V", 0)), "governance"), ("Essential", int(classes.get("E", 0)), "governance"),
                  ("Desirable", int(classes.get("D", 0)), "governance")])
    tiles("categories", [("Category I", int(categories.get("I", 0)), "attention"),
                         ("Category II", int(categories.get("II", 0)), "check"),
                         ("Category III", int(categories.get("III", 0)), "info")])
    st.subheader("ABC-VED matrix (planning class x VED)")
    st.caption(VED_CAPTION)
    matrix = table("c1_tab_abc_ved_matrix") if "c1_tab_abc_ved_matrix" in tables() else pd.DataFrame()
    if len(matrix):
        c1_ui.abc_ved_matrix(matrix)
    st.subheader("Share of 2025 consumption value by class")
    year = summary[summary.Period.eq("2025") & summary.ABC_Class.isin(["A", "B", "C"])]
    c1_ui.bar_chart(year.set_index("ABC_Class").Value_Share.rename("Share of consumption value").rename_axis("ABC class"),
                    value_title="Share of 2025 consumption value", value_format=".0%", axis_format=".0%")
    view = filter_bar(abc, "abc", status="VED")
    show(view[present(view, ["Medicine_Key", *ABC_COLUMNS])].sort_values("Brand_Name"), key="abc-table")
    annual("abc_section")


def forecast_evidence() -> None:
    st.caption(SUDDEN_CHANGE_NOTE)
    forecast = c1_format.with_action(table("c1_tab_forecast"), table("c1_tab_reorder"))
    counts = forecast.Reliability.value_counts()
    ordered = [label for label in RELIABILITY_ICONS if label in counts] + \
              [label for label in counts.index if label not in RELIABILITY_ICONS]
    tiles("reliability", [(label, int(counts[label]), RELIABILITY_ICONS.get(label, "info")) for label in ordered])
    st.caption("From most to least reliable: a tick for planning use, a warning for use with the reliability status "
               "shown, a cross where the pharmacy reviews the medicine first.")
    view = filter_bar(forecast, "forecast", status="Reliability")
    show(view[present(view, ["Medicine_Key", *FORECAST_COLUMNS])].sort_values("Brand_Name"), key="forecast-table")
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
        c1_ui.show_table(wide, widths={"Measure_Group": 270, "Measure": 210})
    annual("forecast_section")


def covid_period() -> None:
    """Limitation 8: the pandemic-period outputs, each labelled as such. The outlier rule tests 2022-2023 only: a month
    is tested once 12 months of history precede it."""
    st.subheader("Pandemic period (2021–2023; outlier rule tested on 2022–2023)")
    st.caption("2021 is not tested because the rule needs 12 months of history.")
    flagged = table("c1_tab_covid_flagged_months")
    comparison = c1_format.with_action(table("c1_tab_covid_period_comparison"), table("c1_tab_reorder"))
    stable = table("c1_tab_covid_stable")
    tiles("pandemic", [("Pandemic-period months flagged", len(flagged), "attention"),
                       ("Medicines with a flagged month", int(flagged.Medicine_Key.nunique()) if len(flagged) else 0,
                        "medicine"), ("Stable across periods", len(stable), "check")])
    st.caption(FLAGGED_CAPTION)
    with st.expander(f"Flagged months for review (pandemic period 2021-2023): {len(flagged):,}"):
        view = filter_bar(flagged, "flagged", status="Rule")
        c1_ui.show_table(view[present(view, FLAGGED_COLUMNS)])
    st.caption("Pandemic (2021-2023) vs post-pandemic (2024-2025), net demand per medicine: mean monthly demand, "
               "coefficient of variation (CV), and the ratio of means (post-pandemic / pandemic).")
    view = filter_bar(comparison, "pandemic-comparison", status="Stable_Across_Periods")
    show(view[present(view, ["Medicine_Key", "Brand_Name", "Suggested_Action", "Unit", "Pandemic_Mean_Monthly_Demand",
                             "Pandemic_CV", "Post_Pandemic_Mean_Monthly_Demand", "Post_Pandemic_CV", "Ratio_Of_Means",
                             "CV_Change", "Stable_Across_Periods", "Period_Label"])], key="pandemic-table")
    with st.expander(f"Stable across periods: {len(stable):,} (ratio of means 0.8-1.25 and |CV change| <= 0.25; "
                     "a default pending the chief pharmacist)"):
        view = filter_bar(stable, "stable", status="Stable_Rule_Status")
        c1_ui.show_table(view[present(view, ["Brand_Name", "Unit", "Ratio_Of_Means", "CV_Change", "Period_Label",
                                             "Stable_Rule_Status"])])


def data_quality() -> None:
    dq = table("c1_dq_summary")
    inactive = table("c1_dq_inactive")
    tiles("data-quality", [("Inactive (no stock, no demand)", len(inactive), "check"),
                           ("Negative stock records",
                            int(dq.set_index("Check").Count.get("Negative stock records (month-ends)", 0)), "attention")])
    c1_ui.show_table(dq[["Check", "Count"]])
    with st.expander(f"Inactive medicines (no stock, no demand): {len(inactive):,}"):
        view = filter_bar(inactive, "inactive", status="Status")
        c1_ui.show_table(view[present(view, ["Brand_Name", "Generic_Name", "Unit"])])
    with st.expander("Negative stock records"):
        negative = table("c1_dq_negative_stock")
        c1_ui.show_table(filter_bar(negative, "negative-stock"))
    st.subheader("Expiry lots not matched to a PHARMACY medicine")
    c1_ui.show_table(table("c1_dq_expiry_unmatched_groups"))
    with st.expander("Unmatched expiry items"):
        c1_ui.show_table(table("c1_dq_expiry_unmatched"))
    st.subheader("Expiry exports on disk")
    st.caption("Each export lists the receipt lots expiring in one month (its printed expiration-date range); the "
               "exports carry no run date.")
    c1_ui.show_table(table("c1_dq_expiry_exports"))
    missing = table("c1_dq_expiry_missing")
    if len(missing):
        st.warning(f"{len(missing):,} expiry exports are needed for near-expiry and are not on disk.")
        c1_ui.show_table(missing)
    annual("data_quality_section")


def kpis() -> None:
    """§1.3.3: each Key Performance Indicator of Table 1.3.3.1 against its target."""
    table_kpi = table("c1_tab_kpi")
    counts = table_kpi.Status.value_counts()
    tiles("kpi", [("Met", int(counts.get("met", 0)), "check"), ("Pending", int(counts.get("pending", 0)), "warning"),
                  ("Not met", int(counts.get("not met", 0)), "cross")])
    st.caption("The KPIs measure whether the planning outputs are generated and interpretable; they do not claim "
               "operational improvement. Pending: the output exists but waits for a confirmation the target names.")
    c1_ui.static_table(table_kpi[["KPI", "Target", "Evidence", "Status", "Note"]])


# ------------------------------------------------------------------ Pages and navigation

# (title, URL path, render function, sidebar icon); Analysis and Evidence sits apart, under "For the panel".
PLANNING_PAGES = [
    (DECISIONS, "decisions", decisions, "decisions"),
    (REORDER, "reorder", reorder_planning, "cart"),
    (WASTE, "waste", waste_expiry, "calendar"),
    (MEDICINE, "medicine", medicine_detail, "medicine"),
]
PANEL_PAGE = (EVIDENCE, "evidence", analysis_evidence, "shield")


def how_numbers_are_made() -> None:
    """The assumptions: one short line, the details in an expander (once per page): the planning inputs, the order
    rule and the planning-assumptions table, each input by its name."""
    st.caption(ASSUMPTION_LINE)
    with st.expander("How these numbers are made"):
        st.markdown(PROXY_NOTE)
        st.markdown(DECISION_NOTE)
        if (month := as_of_text()) is not None:
            st.markdown(f"Stock is as of the month-end of {month} (the latest PHARMACY export loaded). Lists, counts and "
                        "pesos are values of the Capstone 1 data mart; a suggested action restates a medicine's reorder "
                        "status, ABC class and suggested order.")
        st.markdown(ORDER_RULE_NOTE)
        assumptions = table("c1_tab_assumptions")
        if len(assumptions):
            st.markdown("**Planning assumptions**")
            named = assumptions.assign(Input=assumptions.Input.map(c1_format.input_label)) \
                if "Input" in assumptions else assumptions
            c1_ui.static_table(named)


def url_paths() -> list[str]:
    return ["/", *[f"/{path}" for _, path, *_ in [*PLANNING_PAGES, PANEL_PAGE]], f"/{UPDATE_PAGE[1]}",
            *[f"/{path}" for path in REDIRECTS]]


def planning_page(title: str, render: Callable[[], None]) -> Callable[[], None]:
    def page() -> None:
        if not DATABASE.exists():
            c1_ui.page_header(PLANNING_SECTION, title)
            st.error(f"The planning data mart was not found at {DATABASE}. Run the Capstone 1 build first.")
            st.stop()
        month = as_of_text()
        c1_ui.topbar(f"Stock as of {month}" if month else None, url_paths())
        c1_ui.page_header(PLANNING_SECTION, title)
        if DEMO:
            st.warning(DEMO_NOTE)
        how_numbers_are_made()
        render()
        c1_ui.footer()
    return page


def update_page() -> None:
    """The Monthly Update page, imported only when shown (and never in DEMO mode)."""
    import c1_update_page
    month = as_of_text() if DATABASE.exists() else None
    c1_ui.topbar(f"Stock as of {month}" if month else None, url_paths())
    c1_ui.page_header(PLANNING_SECTION, UPDATE_PAGE[0])
    c1_update_page.monthly_update()
    c1_ui.footer()


def redirect(target: str) -> Callable[[], None]:
    """An earlier address: open the page now at target, keeping the query parameters."""
    def page() -> None:
        st.switch_page(PAGES[target], query_params=dict(st.query_params))
    return page


def sidebar(current: st.Page) -> None:
    """The page buttons: the monthly pages (and, locally, Monthly Update), then Analysis and Evidence under the
    "For the panel" label (the same label style as the first group's)."""
    keys = {title: f"sidebar-nav-{c1_ui.slug(title)}" for title in PAGES}
    icons = {keys[title]: icon for title, _, _, icon in [*PLANNING_PAGES, PANEL_PAGE]}
    if SHOW_UPDATE:
        icons[keys[UPDATE_PAGE[0]]] = UPDATE_PAGE[2]
    with st.sidebar:
        c1_ui.install_styles(icons)
        c1_ui.sidebar_brand()
        c1_ui.nav_group(PLANNING_SECTION)
        for title, page in PAGES.items():
            if title == EVIDENCE:
                c1_ui.nav_group(PANEL_GROUP)
            if c1_ui.nav_button(title, keys[title], page.url_path == current.url_path):
                # a page button opens the page's default list ("Show me" and bookmarks set theirs)
                st.session_state.update(view=next(iter(VIEWS)), all=False, sort=next(iter(SORTS)))
                st.switch_page(page)


# An integer opens the sidebar at that width (open on a wide screen, collapsed on a phone); it can then be dragged.
st.set_page_config(page_title="Inpatient Pharmacy Planning", layout="wide", initial_sidebar_state=c1_ui.SIDEBAR_WIDTH)
PAGES = {title: st.Page(planning_page(title, render), title=title, url_path=path)
         for title, path, render, _ in PLANNING_PAGES}
if SHOW_UPDATE:
    PAGES[UPDATE_PAGE[0]] = st.Page(update_page, title=UPDATE_PAGE[0], url_path=UPDATE_PAGE[1])
PAGES[EVIDENCE] = st.Page(planning_page(EVIDENCE, analysis_evidence), title=EVIDENCE, url_path=PANEL_PAGE[1])
# The root address opens This month's decisions; the earlier addresses open their pages.
HOME = st.Page(redirect(DECISIONS), title="Inpatient Pharmacy Planning", url_path="home", default=True)
MOVED = [st.Page(redirect(target), title=f"{target} (earlier address)", url_path=path)
         for path, target in REDIRECTS.items() if target in PAGES]
current = st.navigation([HOME, *PAGES.values(), *MOVED], position="hidden")
if current is not HOME and current not in MOVED:
    sidebar(current)
current.run()
