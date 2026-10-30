"""Inpatient pharmacy planning (Capstone 1): the main DSS app, one st.navigation entry point.

    streamlit run app/capstone1_app.py

Decision first, pharmacist first. The sidebar holds the pages a pharmacist uses each month, in order: Decisions
(/decisions, the opening page), Reorder Planning (/reorder-planning), Waste and Expiry (/waste-and-expiry), Medicine
Detail (/medicine-detail) and Monthly Update (/monthly-update; uploads only locally, never in DEMO mode), then, after a
divider, Analysis (/analysis): ABC-VED, forecast accuracy, the pandemic period and data quality. Each page's name is the
same in the sidebar, its header and its address; the root and the earlier addresses (/overview, /reorder, /waste,
/medicine, /evidence, /update) open the matching page.

Every value shown is a value of the Capstone 1 data mart (database/staging/capstone1/capstone1.duckdb, or CAPSTONE1_DB),
read-only, formatted by app/c1_format.py, which also holds the one vocabulary of statuses and actions and the
definitions behind every "?". Two labels mark what rests on assumptions: "Planning estimate" (Limitation 6), while an
input it depends on is a proxy (config/capstone1_planning_inputs.csv, source), and "Limited planning estimate"
(Limitation 7) on each medicine forecast from simple averages only. The look is the existing app's visual system, in
light or dark mode (app/c1_ui.py, app/c1_theme.py). The pages place no orders and rank no option.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

import c1_format
import c1_ui
from c1_format import AT_ROP, BELOW_SS, DEFINITIONS, NEGATIVE, NO_DEMAND, REVIEW_STATUSES
from c1_ui import card, filter_bar, tiles

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = Path(os.environ.get("CAPSTONE1_DB", PROJECT_ROOT / "database" / "staging" / "capstone1" / "capstone1.duckdb"))
# DEMO mode (CAPSTONE1_DEMO=1): the mart is the synthetic one (src/capstone1/demo_data.py), every page says so, and
# nothing can be uploaded (the upload module is not even imported).
DEMO = os.environ.get("CAPSTONE1_DEMO") == "1"
# Uploads on Monthly Update: local only, never in DEMO mode.
SHOW_UPLOAD = not DEMO and os.environ.get("CAPSTONE1_UPDATE", "1") == "1"
DECISIONS, REORDER, WASTE, MEDICINE, UPDATE, ANALYSIS = ("Decisions", "Reorder Planning", "Waste and Expiry",
                                                         "Medicine Detail", "Monthly Update", "Analysis")
# Each page: its one line under the title.
PAGE_LINES = {DECISIONS: "What needs your decision this month.",
              REORDER: "What to order now, most critical first.",
              WASTE: "What to stop reordering, use first, or watch for expiry.",
              MEDICINE: "One medicine: stock, order, forecast and priority.",
              ANALYSIS: "How medicines are prioritised and how accurate the forecasts are.",
              UPDATE: "Upload this month's BizBox reports to refresh every page."}
# The earlier addresses of the pages, each opening its page.
REDIRECTS = {"overview": DECISIONS, "reorder": REORDER, "waste": WASTE, "medicine": MEDICINE, "evidence": ANALYSIS,
             "analysis-and-evidence": ANALYSIS, "update": UPDATE}
DEMO_NOTE = ("Demonstration data: synthetic medicines, demand, stock, costs and expiry lots, generated with a fixed "
             "seed. Not CDH data; no figure on this page describes Calamba Doctors Hospital.")
# The inputs a planning estimate rests on: while any of them is a proxy, the "Planning estimate" chip shows.
PLANNING_INPUTS = ("lead_time_days", "ordering_cost_php", "holding_rate_annual")     # Limitation 6
# Reorder Planning: the decision columns first; the full CSV keeps every column.
REORDER_COLUMNS = ["Brand_Name", "Suggested_Action", "Reorder_Status", "Planning_Stock", "Reorder_Point",
                   "Suggested_Order", "ABC_VED_Category", "Reliability", "Limited_Planning_Estimate",
                   "Months_Of_Cover_With_Order",
                   "Shelf_Life_Months", "Order_Basis", "EOQ", "Order_Multiple", "Unit", "Dosage_Form", "ABC_Planning",
                   "VED", "Service_Level", "Safety_Stock", "Forecast_Planning_Month"]
# The first eight columns fit the page at 1366px with the sidebar open (an 890px table): each at least its header's
# width, the long text wrapping in taller rows (pixels).
REORDER_WIDTHS = {"Brand_Name": 146, "Suggested_Action": 130, "Reorder_Status": 92, "Planning_Stock": 102,
                  "Reorder_Point": 100, "Suggested_Order": 116, "ABC_VED_Category": 76, "Reliability": 124}
# The suggested order list (Download): the order's own columns, in priority order.
ORDER_LIST_COLUMNS = {"Brand_Name": "Medicine", "Unit": "Unit", "Suggested_Order": "Suggested order",
                      "Unit_Cost": "Unit cost", "Amount": "Amount", "ABC_VED_Category": "ABC-VED",
                      "Reorder_Status": "Status", "Suggested_Action": "Action"}
FORECAST_COLUMNS = ["Brand_Name", "Suggested_Action", "Dosage_Form", "ABC_Planning", "Selected_Model", "Volume_Class",
                    "Test_MAE", "Test_RMSE", "Test_MAPE", "Test_MAPE_Excluded_Zero_Months", "Test_WAPE", "Test_MASE",
                    "Reliability", "Limited_Planning_Estimate", "Prospective_2026_MAE"]
ABC_COLUMNS = ["Brand_Name", "Dosage_Form", "ABC_2021", "ABC_2022", "ABC_2023", "ABC_2024", "ABC_2025",
               "ABC_2021_2025", "ABC_Planning", "VED", "VED_Category", "ABC_VED_Category", "Limited_Planning_Estimate"]
FLAGGED_COLUMNS = ["Brand_Name", "Unit", "Month", "Net_Demand", "Item_Average", "Rule"]
SENSITIVITY_COLUMNS = ["Scenario_Type", "Scenario", "Baseline_Safety_Stock", "Adjusted_Safety_Stock", "Baseline_ROP",
                       "Adjusted_ROP", "Change_ROP_Pct", "Baseline_EOQ", "Adjusted_EOQ", "Change_EOQ_Pct",
                       "Baseline_Suggested_Order", "Adjusted_Suggested_Order"]
GRID_COLUMNS = ["Lead_Time_Days", "Service_Level", "Holding_Rate", "Ordering_Cost", "Safety_Stock", "Reorder_Point",
                "EOQ", "Suggested_Order"]
EOQ_ONLY = "EOQ cost range"              # the scenarios of ordering cost and holding rate: they change EOQ, not ROP
# The What if? factors of the reorder point (the scenario types of the sensitivity table).
FACTORS = {"Lead time": "Lead time", "Service level": "Service level", "Demand (illustrative)": "Demand change",
           "Demand (historical)": "History-based demand"}
LOT_COLUMNS = ["Brand_Name", "Suggested_Action", "Expiration_Date", "Lot_No", "Near_Expiry_Capped_Quantity",
               "Near_Expiry_Capped_Value", "Unit", "Dosage_Form", "Limited_Planning_Estimate"]
PANDEMIC_HEADING = "Pandemic period (2021–2023; outlier rule tested on 2022–2023)"
PANDEMIC_LINE = "2021 is not tested because the rule needs 12 months of history."
FLAGGED_RULE = ("A month of 2022-2023 more than 100% above or 50% below the medicine's average of the 12 months before "
                "it; the forecast models learn from that average instead, and the month is listed for review.")
STABLE_RULE = ("Stable across periods: the post-pandemic mean monthly demand is 0.8 to 1.25 times the pandemic one "
               "and the coefficient of variation changed by 0.25 or less.")
COMPARISON_RULE = ("Pandemic (2021-2023) beside post-pandemic (2024-2025) net demand per medicine: mean monthly "
                   "demand, coefficient of variation (CV) and the ratio of means (post-pandemic / pandemic).")
SUDDEN_CHANGE = ("Forecasts follow the patterns in past use; sudden changes from emergency admissions, outbreaks, "
                 "formulary changes or prescribing may not be captured.")
GRID_HEADING = "Every combination of lead time, service level, holding rate and ordering cost"
# Reliability grades, from most to least reliable, with their status icon.
RELIABILITY_ICONS = {"Highly reliable": "check", "Acceptable for planning": "check",
                     "Planning use allowed only with reliability status": "warning", "Requires review": "cross",
                     "Requires pharmacy review (insufficient data)": "cross"}
# Reorder Planning's "Show" selector (the "view" query parameter, so a list can be bookmarked). The default is the
# order card's list.
VIEWS = {"Reorder now": "reorder-now", "Critical": "critical", "Do not reorder": "unused",
         "No order needed": "no-order", "No demand expected": "no-demand", "All": "all"}
VIEW_NOTES = {"reorder-now": "Below safety stock or at or below the reorder point: Category I and Vital first, then "
                             "the lowest stock as a share of the reorder point.",
              "critical": "Category I or Vital medicines below safety stock, the lowest stock first.",
              "unused": "No use in 2025 with stock held, or excess stock.",
              "no-order": "Above the reorder point, or no demand expected.",
              "no-demand": "No demand expected next month.", "all": "Every planned medicine, by name."}
# Waste and Expiry: the lot order (?sort=Soonest+expiry).
SORTS = {"Soonest expiry": (["Expiration_Date", "Near_Expiry_Capped_Value"], [True, False]),
         "Highest value": (["Near_Expiry_Capped_Value", "Expiration_Date"], [False, True])}
NO_CHANGE = "0%"                         # the What-if demand option for "demand as forecast"
TABLE_ROW_WRAP = 72                      # rows tall enough for long text to wrap (Streamlit wraps above 4rem)
VED_NAMES = {"V": "Vital", "E": "Essential", "D": "Desirable"}
# The planning rules of the pages (Planning settings): set in the mart's SQL, not in the inputs file.
# The What if? ranges: (setting, its inputs, how a value reads).
RANGES = [("Lead time range", "grid_lead_time_days", lambda v: f"{v:g}", " days"),
          ("Service level range", "grid_service_level", lambda v: f"{v * 100:g}", "%"),
          ("Holding rate range", "grid_holding_rate", lambda v: f"{v * 100:g}", "% a year"),
          ("Ordering cost range", "grid_ordering_cost", lambda v: f"₱{v:,.0f}", " per order")]
RULES = [("Slow-moving", "no use in the last 3 months, or more than 6 months of stock at the last 12 months' use"),
         ("Near-expiry", "lots expiring within 180 days, counted up to the stock on hand"),
         ("Stable across periods", "ratio of means 0.8 to 1.25 and a change in CV of 0.25 or less"),
         ("Excess stock", "stock above the reorder point plus one EOQ")]


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
    mart, is read afresh. A table the mart lacks reads as empty."""
    if name not in tables():
        return pd.DataFrame()
    return _load(str(DATABASE), DATABASE.stat().st_mtime_ns, f'SELECT * FROM "{name}"')


def present(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [c for c in columns if c in frame]


def rows_for(frame: pd.DataFrame, key: object, name: str) -> pd.DataFrame:
    """One medicine's rows: by Medicine_Key where the table has it, else by brand name."""
    if not len(frame.columns):
        return frame
    return frame[frame.Medicine_Key.eq(key)] if "Medicine_Key" in frame else frame[frame.Brand_Name.eq(name)]


def first(frame: pd.DataFrame, column: str) -> object:
    return frame[column].iloc[0] if column in frame and len(frame) and pd.notna(frame[column].iloc[0]) else None


def as_of_text() -> str | None:
    reorder = table("c1_tab_reorder")
    return c1_format.month(reorder.As_Of_Month.iloc[0]) if "As_Of_Month" in reorder and len(reorder) else None


def missing_expiry_months() -> list[str]:
    """The months whose expiry reports the next 180 days of near-expiry need and that are not loaded."""
    missing = table("c1_dq_expiry_missing")
    return sorted(missing.Month.astype(str)) if len(missing) and "Month" in missing else []


def month_span(months: list[str]) -> str:
    return (f"{c1_format.month(months[0])} – {c1_format.month(months[-1])}" if len(months) > 1
            else c1_format.month(months[0]) if months else "")


# ------------------------------------------------------------------ the two labels

def planning_estimate() -> tuple[str, str] | None:
    """The "Planning estimate" chip, while an input a planning estimate rests on is a proxy (source "proxy"; a mart
    without the source column counts as proxy). Its tooltip names the inputs in use."""
    inputs = table("c1_tab_assumptions")
    if not len(inputs) or "Input" not in inputs:
        return ("Planning estimate", DEFINITIONS["planning estimate"])
    used = inputs[inputs.Input.isin(PLANNING_INPUTS)]
    proxy = used.source.astype(str).str.lower().ne("cdh").any() if "source" in used else True
    if not proxy:
        return None
    values = dict(zip(inputs.Input, pd.to_numeric(inputs.Value, errors="coerce")))
    tip = (f"Uses lead time {values.get('lead_time_days', float('nan')):g} days, ordering cost "
           f"{c1_format.pesos_whole(values.get('ordering_cost_php'))} per order and holding cost "
           f"{c1_format.share(values.get('holding_rate_annual'))} a year. See Planning settings on Monthly Update.")
    return ("Planning estimate", tip)


def planning_chip() -> None:
    chip = planning_estimate()
    if chip:
        c1_ui.chips(chip)


def limited_chip_html() -> str:
    return c1_ui.chip_html(c1_format.LIMITED, DEFINITIONS["limited planning estimate"])


# ------------------------------------------------------------------ shared lists

def reorder_list() -> pd.DataFrame:
    """c1_tab_reorder with each medicine's ABC-VED category, its limited-planning-estimate flag and its action."""
    reorder = table("c1_tab_reorder")
    abc = table("c1_tab_abc_ved")
    forecast = table("c1_tab_forecast")
    for source, column in ((abc, "ABC_VED_Category"), (forecast, "Limited_Planning_Estimate")):
        on = next((c for c in ("Medicine_Key", "Brand_Name") if c in source and c in reorder), None)
        if column in source and column not in reorder and on:
            reorder = reorder.merge(source[[on, column]].drop_duplicates(on), on=on, how="left")
    return c1_format.with_action(reorder)


def priority(frame: pd.DataFrame) -> pd.DataFrame:
    """Category I or Vital first, then the lowest stock as a share of the reorder point, then the name."""
    vital = frame.get("VED", pd.Series(index=frame.index, dtype=object)).eq("V")
    first_ = frame.get("ABC_VED_Category", pd.Series(index=frame.index, dtype=object)).eq("I") | vital
    share = (frame.Planning_Stock / frame.Reorder_Point.where(frame.Reorder_Point > 0)).fillna(float("inf"))
    return (frame.assign(_first=(~first_).astype(int), _share=share)
            .sort_values(["_first", "_share", "Brand_Name"]).drop(columns=["_first", "_share"]))


def selections(reorder: pd.DataFrame) -> dict[str, pd.Series]:
    """The rows behind the decision cards and the Reorder Planning lists, from existing statuses only."""
    status, action = reorder.Reorder_Status, reorder.Suggested_Action
    category_one = reorder.get("ABC_VED_Category", pd.Series(index=reorder.index, dtype=object)).eq("I")
    vital = reorder.get("VED", pd.Series(index=reorder.index, dtype=object)).eq("V")
    unused = action.eq(c1_format.DO_NOT_REORDER)
    no_use = unused & reorder.ABC_Planning.eq(c1_format.NO_CONSUMPTION) & reorder.Planning_Stock.gt(0)
    excess = unused & reorder.get("Excess_Stock", pd.Series(False, index=reorder.index)).fillna(False).astype(bool)
    now = status.isin(REVIEW_STATUSES)
    return {"reorder-now": now, "critical": (category_one | vital) & status.eq(BELOW_SS),
            "no-use": no_use, "excess": excess, "unused": unused, "stock-record": status.eq(NEGATIVE),
            "no-order": action.eq(c1_format.NO_ORDER), "no-demand": status.eq(NO_DEMAND),
            "out-of-stock": now & reorder.Planning_Stock.eq(0), "all": pd.Series(True, index=reorder.index)}


def seed(key: str, options: list, parse=lambda text: text) -> None:
    """A bookmarked view: the URL's value (?view=Critical) presets its widget once; an unknown value is ignored.
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


def with_limited(frame: pd.DataFrame) -> pd.DataFrame:
    """The frame with each medicine's Limited_Planning_Estimate flag (Limitation 7), from the forecast table."""
    forecast = table("c1_tab_forecast")
    if "Limited_Planning_Estimate" in frame or "Limited_Planning_Estimate" not in forecast:
        return frame
    on = next((c for c in ("Medicine_Key", "Brand_Name") if c in frame and c in forecast), None)
    if not on:
        return frame
    return frame.merge(forecast[[on, "Limited_Planning_Estimate"]].drop_duplicates(on), on=on, how="left")


def show(frame: pd.DataFrame, key: str, **options) -> None:
    """A medicine list: clicking a medicine name opens Medicine Detail for it."""
    picked = c1_ui.show_table(frame, key=key, link=True, **options)
    if picked is not None:
        open_medicine(picked)


def download(frame: pd.DataFrame, name: str, key: str, label: str | None = None) -> None:
    st.download_button(label or f"Download the full table ({len(frame):,} rows, CSV)",
                       frame.to_csv(index=False).encode("utf-8"), file_name=name, mime="text/csv", key=key)


def go(page: str, presets: dict[str, object], params: dict[str, str]) -> None:
    """Open a page already filtered: the presets set its widgets, the query parameters make the view bookmarkable."""
    for name, value in presets.items():
        st.session_state[name] = value
    st.switch_page(PAGES[page], query_params=params)


def html_escape(text: object) -> str:
    import html
    return html.escape(str(text))


# ------------------------------------------------------------------ Decisions

def order_total(now: pd.DataFrame) -> tuple[float, int, int]:
    """The order card's pesos: suggested order x unit cost over the medicines to reorder, free goods left out; how
    many are priced and how many are free goods."""
    free = now.get("Free_Goods", pd.Series(False, index=now.index)).fillna(False).astype(bool)
    cost = (now.Suggested_Order * now.Unit_Cost)[~free] if {"Suggested_Order", "Unit_Cost"} <= set(now) \
        else pd.Series(dtype=float)
    return (cost.sum(min_count=1) if len(cost) else float("nan")), int(cost.notna().sum()), int(free.sum())


def decisions() -> None:
    reorder = reorder_list()
    chosen = selections(reorder)
    now = reorder[chosen["reorder-now"]]
    order_value, _, free = order_total(now)
    vital_now = int(now.VED.eq("V").sum()) if "VED" in now else 0
    critical = reorder[chosen["critical"]]
    no_use, excess = int(chosen["no-use"].sum()), int(chosen["excess"].sum())
    unused = int(chosen["unused"].sum())
    top = priority(now) if len(now) else priority(reorder)
    top_name = top.Brand_Name.iloc[0] if len(top) else None
    chip = planning_estimate()
    chip_html = f" {c1_ui.chip_html(*chip)}" if chip else ""

    first_row, second_row = c1_ui.question_row("top", 3), None
    with first_row[0]:
        free_line = (f"<br>{free:,} received as free goods: confirm the supplier (not priced)." if free else "")
        if c1_ui.question_card("order", "What do I order now, and how much?", f"{len(now):,} medicines",
                               f"<strong>{c1_format.pesos_whole(order_value)}</strong> · <strong>{vital_now:,}</strong> "
                               f"Vital{chip_html}{free_line}"):
            go(REORDER, {"view": "Reorder now"}, {"view": "Reorder now"})
    with first_row[1]:
        out = int((critical.Planning_Stock == 0).sum())
        if c1_ui.question_card("run-out", "Which critical medicines could run out?", f"{len(critical):,} medicines",
                               f"Category I or Vital below safety stock, <strong>{out:,}</strong> out of stock.",
                               attention=len(critical) > 0):
            go(REORDER, {"view": "Critical"}, {"view": "Critical"})
    with first_row[2]:
        expiry_card()
    second_row = c1_ui.question_row("bottom", 2)
    with second_row[0]:
        if c1_ui.question_card("unused", "What is sitting unused?", f"{unused:,} medicines",
                               f"Do not reorder (<strong>{excess:,}</strong> with excess stock, "
                               f"<strong>{unused - excess:,}</strong> more with no use in 2025)."):
            go(REORDER, {"view": "Do not reorder"}, {"view": "Do not reorder"})
    with second_row[1]:
        if c1_ui.question_card("what-if", "What if the supplier is late or demand rises?",
                               top_name if top_name else "no medicine",
                               "The top-priority medicine first: lead time 3/7/14 days, service level 90/95/99%, "
                               "demand -30% to +30%.", name_answer=True):
            presets = {"view": "Reorder now"}
            params = {"view": "Reorder now", "whatif": "1"}
            if top_name:
                presets["wi_medicine"] = top_name
                params["wi_medicine"] = top_name
            go(REORDER, presets, params)
    with card("stock-health", "Stock health"):
        action_bar(reorder)


def expiry_card() -> None:
    """The expiry card: while the next 180 days of expiry reports are missing, the upload they need; once loaded, the
    lots with stock on hand and their value."""
    months = missing_expiry_months()
    if months:
        if c1_ui.question_card("expiry", "What is expiring, and what do I do with it?", "Expiry reports needed",
                               f"Upload the expiry reports for {month_span(months)}.", button="Go to Monthly Update"):
            st.switch_page(PAGES[UPDATE])
        return
    lots, value = lots_with_stock(table("c1_tab_near_expiry"))
    if c1_ui.question_card("expiry", "What is expiring, and what do I do with it?", f"{lots:,} lots",
                           f"<strong>{c1_format.pesos_whole(value)}</strong> at stock on hand. Use the soonest first."):
        go(WASTE, {"sort": "Soonest expiry"}, {"sort": "Soonest expiry"})


def action_bar(reorder: pd.DataFrame) -> None:
    """The planned medicines by action, as one 100% stacked bar whose legend adds up to them."""
    counts = reorder.Suggested_Action.value_counts().reindex(c1_format.ACTIONS).fillna(0).astype(int)
    st.markdown(f"All {len(reorder):,} planned medicines by action.")
    c1_ui.stacked_share_bar(counts, c1_format.ACTION_TOKENS)


# ------------------------------------------------------------------ Reorder Planning

def order_list(reorder: pd.DataFrame, chosen: dict) -> pd.DataFrame:
    """The suggested order list: the medicines to reorder now, in priority order, with the amount (suggested order x
    unit cost; none for free goods)."""
    now = priority(reorder[chosen["reorder-now"]])
    free = now.get("Free_Goods", pd.Series(False, index=now.index)).fillna(False).astype(bool)
    now = now.assign(Amount=(now.Suggested_Order * now.Unit_Cost).where(~free) if "Unit_Cost" in now else float("nan"),
                     Reorder_Status=now.Reorder_Status.map(c1_format.status_term))
    return now[present(now, list(ORDER_LIST_COLUMNS))].rename(columns=ORDER_LIST_COLUMNS)


def reorder_planning() -> None:
    reorder = reorder_list()
    chosen = selections(reorder)
    in_review = chosen["reorder-now"]
    with card("reorder"):
        tiles("reorder", [
            ("Reorder now", int(in_review.sum()), "procurement",
             f"{int(reorder.Reorder_Status.eq(AT_ROP).sum()):,} at or below reorder point, "
             f"{int(reorder.Reorder_Status.eq(BELOW_SS).sum()):,} below safety stock"),
            ("Vital: reorder now", int((in_review & reorder.VED.eq("V")).sum()) if "VED" in reorder
             else "not available", "attention"),
            ("Out of stock", int(chosen["out-of-stock"].sum()), "cross", "to reorder, with no stock on hand", None,
             "red"),
            (c1_format.CHECK_RECORD, int(chosen["stock-record"].sum()), "attention", "negative stock record", None,
             "amber")])
        seed("view", list(VIEWS))
        view_label = st.selectbox("Show", list(VIEWS), key="view")
        keep_in_url("view", view_label, next(iter(VIEWS)))
        view_name = VIEWS[view_label]
        st.caption(VIEW_NOTES[view_name])
        listed = reorder[chosen[view_name]]
        listed = priority(listed) if view_name in ("reorder-now", "critical") else listed.sort_values("Brand_Name")
        view = filter_bar(listed, "reorder")
        planning_chip()
        show(view[present(view, ["Medicine_Key", *REORDER_COLUMNS])],
             key="reorder-table", widths=REORDER_WIDTHS, row_height=TABLE_ROW_WRAP)
        month = str(first(reorder, "Planning_Month") or "")
        prefix = "DEMO" if DEMO else "CDH"
        with st.container(horizontal=True, gap="small", key="c1-downloads"):      # side by side, on the left
            download(order_list(reorder, chosen), f"{prefix}_suggested_orders_{month}.csv", "order-list-csv",
                     label="Download suggested order list")
            download(view, "reorder_planning.csv", "reorder-csv")
    with c1_ui.collapsible("what-if", "What if?", expanded=st.query_params.get("whatif") == "1"):
        what_if(reorder)


def what_if(reorder: pd.DataFrame) -> None:
    """One medicine's adjusted values beside its baseline: lead time and service level from the sensitivity grid, or a
    demand change from the one-at-a-time scenarios. Both come from the mart; nothing is computed here."""
    sensitivity = table("c1_tab_sensitivity")
    assumptions = table("c1_tab_assumptions")
    grid = table("c1_tab_sensitivity_grid")
    names = sorted(sensitivity.Brand_Name.dropna().unique()) if len(sensitivity) else []
    if names and st.query_params.get("wi_medicine") in names and "wi_medicine" not in st.session_state:
        st.session_state["wi_medicine"] = st.query_params["wi_medicine"]
    if names and st.session_state.get("wi_medicine") not in names:
        ranked = priority(reorder[reorder.Brand_Name.isin(names)])
        st.session_state["wi_medicine"] = ranked.Brand_Name.iloc[0] if len(ranked) else names[0]
    picked = c1_ui.picker("Medicine", names, key="wi_medicine") if names else None
    if picked is not None and st.query_params.get("whatif") == "1":
        keep_in_url("wi_medicine", picked, None)
    view = sensitivity[sensitivity.Brand_Name.eq(picked)] if picked else sensitivity.iloc[0:0]
    own = grid[grid.Brand_Name.eq(picked)] if picked and len(grid) else grid.iloc[0:0]
    inputs = planning_inputs(assumptions)
    leads = sorted(grid.Lead_Time_Days.dropna().unique()) if "Lead_Time_Days" in grid else []
    levels = sorted(grid.Service_Level.dropna().unique()) if "Service_Level" in grid else []
    if not (len(view) and leads and levels):
        return
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
    st.markdown(f"**{lead:,.0f} days, {c1_format.share(service)} service level, demand {demand}**, against the baseline "
                f"of {base_lead:,.0f} days, the VED class's service level and demand as forecast.")
    planning_chip()
    if adjusted is None:
        st.info("Not available: the grid varies lead time and service level with demand as forecast, and the demand "
                "scenarios vary demand alone. Set the demand change to 0%, or lead time and service level to the "
                "baseline.")
    else:
        def tile(label, value, baseline, help_key):
            delta = (float(value) - float(baseline)) if pd.notna(value) and pd.notna(baseline) else float("nan")
            caption = (f"{delta:+,.0f} from baseline {c1_format.whole(baseline)}" if pd.notna(delta)
                       else f"baseline {c1_format.whole(baseline)}")
            return (label, c1_format.whole(value), "procurement", caption, DEFINITIONS.get(help_key))
        tiles("what-if", [tile("Reorder point", adjusted["rop"], base.Baseline_ROP, "reorder point"),
                          tile("EOQ", adjusted["eoq"], base.Baseline_EOQ, None),
                          tile("Suggested order", adjusted["order"], base.get("Baseline_Suggested_Order"),
                               "suggested order"),
                          tile("Safety stock", adjusted["ss"], base.Baseline_Safety_Stock, "safety stock")])
    st.subheader("What moves the reorder point most",
                 help="Each bar spans the change in the reorder point from the factor's lowest to its highest scenario.")
    factors = view[view.Scenario_Type.isin(list(FACTORS))].assign(Factor=lambda f: f.Scenario_Type.map(FACTORS))
    c1_ui.range_chart(factors.groupby("Factor").Change_ROP.agg(Low="min", High="max").reset_index(),
                      "Change in reorder point")
    costs = eoq_cost_table(view)
    if len(costs):
        st.subheader("EOQ by ordering cost and holding rate",
                     help="Ordering cost and holding rate change EOQ only; the reorder point stays the same.")
        c1_ui.static_table(costs, hide=())
    with st.expander(f"Every scenario for this medicine, baseline beside adjusted ({len(view):,})"):
        c1_ui.show_table(view[present(view, SENSITIVITY_COLUMNS)])
    with st.expander(f"{GRID_HEADING} ({len(own):,} combinations)"):
        c1_ui.show_table(own[present(own, GRID_COLUMNS)])
        download(own, "sensitivity_grid.csv", "grid-csv")


def eoq_cost_table(view: pd.DataFrame) -> pd.DataFrame:
    """The EOQ of each ordering cost (rows) and holding rate (columns) from the medicine's cost-range scenarios."""
    rows = view[view.Scenario_Type.astype(str).eq(EOQ_ONLY)]
    cells = []
    for name, eoq in zip(rows.Scenario.astype(str), rows.Adjusted_EOQ):
        match = re.match(r"ordering PHP ([\d,]+), holding (\d+)%", name)
        if match:
            cells.append({"Ordering cost": f"{c1_format.PESO}{match.group(1)} per order", "Order": float(
                match.group(1).replace(",", "")), "Holding": f"Holding {match.group(2)}%",
                "EOQ": c1_format.whole(eoq)})
    if not cells:
        return pd.DataFrame()
    frame = pd.DataFrame(cells).sort_values("Order")
    wide = frame.pivot_table(index=["Order", "Ordering cost"], columns="Holding", values="EOQ", aggfunc="first")
    return wide.reset_index().drop(columns=["Order"]).rename_axis(columns=None)


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
    reorder = reorder_list()
    review = c1_format.with_action(table("c1_tab_waste_review"), table("c1_tab_reorder"))
    near = table("c1_tab_near_expiry")
    months = missing_expiry_months()
    with card("waste"):
        unused = selections(reorder)["unused"]
        on = "Medicine_Key" if "Medicine_Key" in review and "Medicine_Key" in reorder else "Brand_Name"
        also = review[on].isin(set(reorder.loc[unused, on])) if len(review) else pd.Series(dtype=bool)
        slow, excess = ((review[c].fillna(False).astype(bool) if c in review else pd.Series(False, index=review.index))
                        for c in ("Slow_Moving", "Excess_Stock"))

        def overlap(flag: pd.Series) -> str:
            both = int((flag & also).sum())
            return "all of them are also Do not reorder" if both == int(flag.sum()) and both else \
                f"{both:,} of them are also Do not reorder"
        if months:
            near_tile = ("Near-expiry", "Upload needed", "expiry", f"expiry reports for {month_span(months)}",
                         DEFINITIONS["near-expiry"], "amber")
        else:
            lots, value = lots_with_stock(near)
            near_tile = ("Near-expiry", f"{lots:,} lots", "expiry", f"{c1_format.pesos_whole(value)} at stock on hand",
                         DEFINITIONS["near-expiry"])
        tiles("waste", [(c1_format.DO_NOT_REORDER, int(unused.sum()), "stop",
                         "no use in 2025 with stock held, or excess stock"),
                        ("Slow-moving", int(slow.sum()), "expiry", f"watch, use first; {overlap(slow)}",
                         DEFINITIONS["slow-moving"]),
                        ("Excess stock", int(excess.sum()), "expiry", overlap(excess), DEFINITIONS["excess stock"]),
                        near_tile])
        if months and st.button("Go to Monthly Update", key="waste-upload"):
            st.switch_page(PAGES[UPDATE])
    if not months:
        with card("near-expiry", "Lots expiring within 180 days"):
            lot_table("near", use_first=True)
    with card("expired", "Expired stock value by month"):
        timeline = table("c1_tab_expiry_timeline")
        if len(timeline):
            c1_ui.bar_chart(timeline.set_index("Month").Expired_Value_Capped.rename("Expired value (PHP)"),
                            value_title="PHP", value_format=",.2f")
            st.caption("Each lot expiring in the month, counted up to the medicine's stock at that month-end, at its "
                       "landed cost; lots of items not in the inventory report are left out.")
    if months and len(near):
        as_of = c1_format.month(first(near, "Near_Expiry_As_Of")) if first(near, "Near_Expiry_As_Of") else "March 2026"
        with c1_ui.collapsible("expiry-check", f"180-day check on {as_of} stock"):
            check = table("c1_tab_near_expiry_check")
            if len(check):
                st.markdown("Lots flagged as near-expiry beside what actually expired in the same 180 days.")
                c1_ui.show_table(check[present(check, ["Measure", "Lots", "Medicines", "Value_Capped_PHP"])],
                                 row_height=TABLE_ROW_WRAP)
            lot_table("check", use_first=False)


def lot_table(name: str, use_first: bool) -> None:
    """The near-expiry lots with stock left, one row per lot, or grouped by medicine; soonest expiry or highest value
    first. use_first: the lots are current, so their action is "Use first" (the check's lots are past)."""
    lots = with_limited(near_lots())
    if not len(lots):
        return
    left = lots.Near_Expiry_Capped_Quantity.fillna(0).gt(0)
    lots = lots[left]
    controls = st.columns([2, 1], vertical_alignment="bottom")
    seed("sort", list(SORTS))
    order = controls[0].selectbox("Sort lots by", list(SORTS), key="sort",
                                  help="Soonest expiry: then the highest value first. Highest value: then the soonest.")
    keep_in_url("sort", order, next(iter(SORTS)))
    grouped = controls[1].toggle("Group by medicine", key=f"{name}-group")
    keys, ascending = SORTS[order]
    lots = lots.sort_values([*keys, "Brand_Name"], ascending=[*ascending, True])
    if use_first:
        lots = lots.assign(Suggested_Action="Use first")
    if grouped:
        by = lots.groupby([c for c in ("Medicine_Key", "Brand_Name", "Unit", "Dosage_Form", "Limited_Planning_Estimate")
                           if c in lots], dropna=False, sort=False)
        medicines = by.agg(Near_Expiry_Lots=("Expiration_Date", "size"), First_Expiry=("Expiration_Date", "min"),
                           Last_Expiry=("Expiration_Date", "max"),
                           Near_Expiry_Quantity_Capped=("Near_Expiry_Capped_Quantity", "sum"),
                           Near_Expiry_Value_Capped=("Near_Expiry_Capped_Value", "sum")).reset_index()
        if use_first:
            medicines = medicines.assign(Suggested_Action="Use first")
        st.markdown(f"**{len(medicines):,}** medicines")
        show(medicines[present(medicines, ["Medicine_Key", "Brand_Name", "Suggested_Action", "Near_Expiry_Lots",
                                           "First_Expiry", "Last_Expiry", "Near_Expiry_Quantity_Capped",
                                           "Near_Expiry_Value_Capped", "Unit", "Dosage_Form",
                                           "Limited_Planning_Estimate"])],
             key=f"{name}-medicines-table")
    else:
        st.markdown(f"**{len(lots):,}** lots")
        show(lots[present(lots, ["Medicine_Key", *LOT_COLUMNS])], key=f"{name}-lots-table")


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


# ------------------------------------------------------------------ Medicine Detail

def medicine_detail() -> None:
    names = medicine_names()
    if not names:
        return
    wanted = st.query_params.get("medicine")             # a bookmark names the medicine by its brand name
    by_name = {n: k for k, n in names.items()}
    if wanted is not None and "medicine" not in st.session_state and (wanted in names or wanted in by_name):
        st.session_state["medicine"] = wanted if wanted in names else by_name[wanted]
    if st.session_state.get("medicine") not in names:
        ranked = priority(reorder_list())
        keys = ranked.Medicine_Key if "Medicine_Key" in ranked else ranked.Brand_Name.map(by_name)
        category_one = keys[ranked.get("ABC_VED_Category", pd.Series(index=ranked.index, dtype=object)).eq("I")
                            & keys.isin(list(names))]
        st.session_state["medicine"] = category_one.iloc[0] if len(category_one) else next(iter(names))
    key = c1_ui.picker("Medicine", list(names), key="medicine", format_func=names.get,
                       placeholder="Type to search a medicine")
    keep_in_url("medicine", names[key], None)
    name = names[key]
    reorder = rows_for(reorder_list(), key, name)
    abc = rows_for(table("c1_tab_abc_ved"), key, name)
    forecast = table("c1_tab_forecast")
    own_forecast = forecast[forecast.Medicine_Key.eq(key)]
    limited = bool(first(own_forecast, "Limited_Planning_Estimate"))
    with card("detail-stock", "Stock and order"):
        chips = [c for c in (planning_estimate(),) if c]
        if limited:
            chips.append((c1_format.LIMITED, DEFINITIONS["limited planning estimate"]))
        c1_ui.chips(*chips)
        months = first(reorder, "Shelf_Life_Months")
        action = first(reorder, "Suggested_Action") or "not planned"
        tone = c1_format.ACTION_TONES.get(action)
        tiles("detail-stock", [
            ("Stock on hand", c1_format.whole(first(reorder, "Planning_Stock")), "medicine"),
            ("Reorder point", c1_format.whole(first(reorder, "Reorder_Point")), "procurement", None,
             DEFINITIONS["reorder point"]),
            ("Safety stock", c1_format.whole(first(reorder, "Safety_Stock")), "governance", None,
             DEFINITIONS["safety stock"]),
            ("Suggested order", c1_format.whole(first(reorder, "Suggested_Order")), "procurement", None,
             DEFINITIONS["suggested order"]),
            ("Months of cover", c1_format.one_decimal(first(reorder, "Months_Of_Cover_With_Order"))
             if first(reorder, "Months_Of_Cover_With_Order") is not None else "not available", "forecast", None,
             DEFINITIONS["months of cover"]),
            ("Shelf life", f"{months:,.1f} months" if months is not None else "not recorded", "expiry", None,
             DEFINITIONS["shelf life"]),
            ("Action", action, "stop" if action == c1_format.DO_NOT_REORDER else "check", None, None, tone)], columns=4)
        planned = len(table("c1_tab_sensitivity")) and name in set(table("c1_tab_sensitivity").Brand_Name.dropna())
        if st.button("Open in What if?", key="open-what-if", disabled=not planned,
                     help=None if planned else "No scenarios: this medicine has no reorder plan."):
            go(REORDER, {"wi_medicine": name}, {"whatif": "1", "wi_medicine": name})
    with card("detail-forecast", "Demand and forecast"):
        series = table("c1_tab_forecast_series")
        own_series = series[series.Medicine_Key.eq(key)] if len(series) else series
        test = st.toggle("Show model test", key="detail-model-test", value=False, help=SUDDEN_CHANGE)
        names_map = {"Actual (net demand)": "Actual", "Planning forecast (frozen model refit to 2026-09)": "Forecast"}
        if test:
            names_map.update({"Test forecast (Jul-Dec 2025)": "Model test, Jul-Dec 2025",
                              "Frozen forecast (from Dec 2025)": "Model test, 2026"})
        shown = own_series[own_series.Series.isin(list(names_map))].assign(Series=lambda f: f.Series.map(names_map))
        if len(shown):
            c1_ui.line_chart(shown.pivot_table(index="Month", columns="Series", values="Value"), y_title="Units")
        model = first(own_forecast, "Selected_Model")
        parts = [c1_format.sentence(model) if model else "No model",
                 f"MAE {c1_format.number(first(own_forecast, 'Test_MAE'))}",
                 f"RMSE {c1_format.number(first(own_forecast, 'Test_RMSE'))}",
                 f"MAPE {c1_format.points(first(own_forecast, 'Test_MAPE'))}",
                 str(first(own_forecast, "Reliability") or "not graded")]
        st.markdown(" · ".join(html_escape(p) for p in parts) + (f" {limited_chip_html()}" if limited else "")
                    + c1_ui.help_icon(DEFINITIONS["forecast reliability"]), unsafe_allow_html=True)
    with card("detail-priority", "Priority"):
        ved = first(abc, "VED")
        tiles("detail-priority", [("ABC class", c1_format.sentence(first(abc, "ABC_Planning") or "not available"),
                                   "validation"),
                                  ("VED", VED_NAMES.get(ved, "not available"), "governance"),
                                  ("ABC-VED category", f"Category {first(abc, 'ABC_VED_Category')}"
                                   if first(abc, "ABC_VED_Category") else c1_format.NOT_CLASSED, "governance", None,
                                   DEFINITIONS["abc-ved category"])])
    with card("detail-pandemic", PANDEMIC_HEADING):
        flagged = rows_for(table("c1_tab_covid_flagged_months"), key, name)
        if len(flagged):
            st.markdown(f"**{len(flagged):,}** flagged months for review." + c1_ui.help_icon(FLAGGED_RULE),
                        unsafe_allow_html=True)
            c1_ui.show_table(flagged[present(flagged, ["Month", "Net_Demand", "Item_Average", "Rule"])])
        else:
            st.markdown("No flagged months for this medicine." + c1_ui.help_icon(FLAGGED_RULE),
                        unsafe_allow_html=True)


# ------------------------------------------------------------------ Analysis

ANALYSIS_TABS = ["ABC-VED", "Forecast accuracy", "Pandemic period", "Data quality"]


def analysis() -> None:
    for tab, render in zip(st.tabs(ANALYSIS_TABS), (abc_ved, forecast_accuracy, pandemic_period, data_quality)):
        with tab, card(f"analysis-{render.__name__}"):
            render()


def abc_ved() -> None:
    abc = with_limited(table("c1_tab_abc_ved"))
    summary = table("c1_tab_abc_summary")
    st.subheader("ABC-VED matrix", help=DEFINITIONS["abc-ved category"])
    matrix = table("c1_tab_abc_ved_matrix")
    if len(matrix):
        c1_ui.abc_ved_matrix(matrix)
        totals = matrix.groupby("Category").Medicines.sum()
        st.markdown(" · ".join(f"Category {c}: **{int(totals.get(c, 0)):,}**" for c in ("I", "II", "III"))
                    + f" (the {int(matrix.Medicines.sum()):,} medicines with a 2025 consumption value)")
    classes = abc.VED.value_counts() if "VED" in abc else pd.Series(dtype=int)
    st.markdown(f"All {len(abc):,} catalogue medicines: " + ", ".join(
        f"{VED_NAMES[v]} {int(classes.get(v, 0)):,}" for v in ("V", "E", "D")))
    st.subheader("Share of 2025 consumption value by class")
    year = summary[summary.Period.eq("2025") & summary.ABC_Class.isin(["A", "B", "C"])] if len(summary) else summary
    if len(year):
        c1_ui.bar_chart(year.set_index("ABC_Class").Value_Share.rename("Share of consumption value")
                        .rename_axis("ABC class"), value_title="Share of 2025 consumption value",
                        value_format=".0%", axis_format=".0%")
    view = filter_bar(abc, "abc", status="VED")
    show(view[present(view, ["Medicine_Key", *ABC_COLUMNS])].sort_values("Brand_Name"), key="abc-table")


def forecast_accuracy() -> None:
    forecast = c1_format.with_action(table("c1_tab_forecast"), table("c1_tab_reorder"))
    status = table("c1_tab_reorder")
    on = "Medicine_Key" if "Medicine_Key" in status and "Medicine_Key" in forecast else "Brand_Name"
    no_demand = set(status[on][status.Reorder_Status.eq(NO_DEMAND)]) if len(status) else set()
    graded = forecast[~forecast[on].isin(no_demand)]
    counts = graded.Reliability.value_counts()
    ordered = [label for label in RELIABILITY_ICONS if label in counts] + \
              [label for label in counts.index if label not in RELIABILITY_ICONS]
    st.subheader("Forecast reliability of the medicines with demand expected", help=DEFINITIONS["forecast reliability"])
    tiles("reliability", [(label, int(counts[label]), RELIABILITY_ICONS.get(label, "info")) for label in ordered],
          columns=min(len(ordered), 5) or None)
    st.markdown(f"{len(forecast) - len(graded):,} more medicines have no demand expected next month and are not graded.")
    view = filter_bar(forecast, "forecast", status="Reliability")
    show(view[present(view, ["Medicine_Key", *FORECAST_COLUMNS])].sort_values("Brand_Name"), key="forecast-table")


def pandemic_period() -> None:
    """Limitation 8: the three uses of the pandemic records, each labelled as such."""
    st.subheader(PANDEMIC_HEADING)
    st.caption(PANDEMIC_LINE)
    flagged = table("c1_tab_covid_flagged_months")
    comparison = table("c1_tab_covid_period_comparison")
    stable = table("c1_tab_covid_stable")
    tiles("pandemic", [("Flagged months for review", len(flagged), "attention", None, FLAGGED_RULE),
                       ("Medicines with a flagged month", int(flagged.Medicine_Key.nunique()) if len(flagged) else 0,
                        "medicine"),
                       ("Stable across periods", len(stable), "check", None, STABLE_RULE)])
    st.subheader("Flagged months for review", help=FLAGGED_RULE)
    view = filter_bar(flagged, "flagged", status="Rule", noun="months")
    c1_ui.show_table(view[present(view, FLAGGED_COLUMNS)])
    st.subheader("Pandemic beside post-pandemic demand", help=COMPARISON_RULE)
    view = filter_bar(with_limited(comparison), "pandemic-comparison", status="Stable_Across_Periods")
    show(view[present(view, ["Medicine_Key", "Brand_Name", "Unit", "Pandemic_Mean_Monthly_Demand", "Pandemic_CV",
                             "Post_Pandemic_Mean_Monthly_Demand", "Post_Pandemic_CV", "Ratio_Of_Means", "CV_Change",
                             "Stable_Across_Periods", "Limited_Planning_Estimate"])], key="pandemic-table")
    st.subheader("Stable across periods", help=STABLE_RULE)
    view = filter_bar(stable, "stable")
    c1_ui.show_table(view[present(view, ["Brand_Name", "Unit", "Ratio_Of_Means", "CV_Change"])])


def data_quality() -> None:
    dq = table("c1_dq_summary")
    st.subheader("Checks")
    if len(dq):
        c1_ui.show_table(dq[["Check", "Count"]].assign(Check=dq.Check.map(c1_format.words)))
    st.subheader("Records to fix")
    negative = table("c1_dq_negative_stock")
    if {"Year", "Month"} <= set(negative):                 # one month column: "Nov 2022"
        month = negative.Year.astype(int).astype(str) + "-" + negative.Month.astype(int).astype(str).str.zfill(2)
        negative = negative.drop(columns=["Year"]).assign(Month=month)
        negative = negative[["Brand_Name", "Month", *[c for c in negative if c not in ("Brand_Name", "Month")]]] \
            if "Brand_Name" in negative else negative
    st.markdown(f"**{len(negative):,}** negative stock records (month-ends)")
    c1_ui.show_table(negative)
    unmatched = table("c1_dq_expiry_unmatched_groups")
    st.markdown("Expiry lots of items not in the inventory report")
    c1_ui.show_table(unmatched)
    inactive = table("c1_dq_inactive")
    with st.expander(f"Inactive medicines (no stock, no demand): {len(inactive):,}"):
        view = filter_bar(inactive, "inactive", status="Status")
        c1_ui.show_table(view[present(view, ["Brand_Name", "Generic_Name", "Unit"])])
    with st.expander("Unmatched expiry items"):
        c1_ui.show_table(table("c1_dq_expiry_unmatched"))
    with st.expander("Expiry reports on disk"):
        exports = table("c1_dq_expiry_exports")
        c1_ui.show_table(exports.drop(columns=["Source_File"], errors="ignore"))


# ------------------------------------------------------------------ Monthly Update

def update_status() -> None:
    """What is loaded and what comes next, from the mart."""
    as_of = first(table("c1_tab_reorder"), "As_Of_Month")
    exports = table("c1_dq_expiry_exports")
    expiry = sorted(exports.Report_Month.astype(str))[-1] if len(exports) and "Report_Month" in exports else None
    months = missing_expiry_months()
    next_month = str(pd.Period(str(as_of), freq="M") + 1) if as_of else None
    tiles("update-status", [("Inventory reports loaded through", c1_format.month(as_of) if as_of else "none",
                             "medicine"),
                            ("Expiry reports loaded through", c1_format.month(expiry) if expiry else "none", "expiry"),
                            ("Next inventory report", c1_format.month(next_month) if next_month else "the first month",
                             "procurement"),
                            ("Expiry reports needed", month_span(months) if months else "none", "expiry", None, None,
                             "amber" if months else None)])


def planning_settings() -> None:
    """The planning inputs and rules, read-only, each with its source (Proxy, or CDH with the date it was confirmed)."""
    inputs = table("c1_tab_assumptions")
    rows = []
    if len(inputs):
        values = dict(zip(inputs.Input.astype(str), pd.to_numeric(inputs.Value, errors="coerce")))
        for r in inputs.itertuples():
            name = str(r.Input)
            if name.startswith(("ordering_cost_part", "grid_")):
                continue
            if name in PLANNING_INPUTS:                  # Limitation 6: a proxy until CDH confirms it
                source = str(getattr(r, "source", "proxy") or "proxy")
                confirmed = getattr(r, "confirmed_on", None)
                text = "CDH" if source.lower() == "cdh" else "Proxy"
                if text == "CDH" and isinstance(confirmed, str) and confirmed:
                    text += f", {confirmed}"
            else:
                text = "Rule"
            rows.append({"Setting": c1_format.input_label(r.Input),
                         "Value": setting_value(r.Input, r.Value, getattr(r, "Unit", "")), "Source": text})
        for setting, prefix, show_value, unit in RANGES:
            points = [values[k] for k in sorted(values) if k.startswith(prefix + "_") and pd.notna(values[k])]
            if points:
                rows.append({"Setting": setting, "Value": " / ".join(show_value(v) for v in points) + unit,
                             "Source": "Rule"})
    rows += [{"Setting": name, "Value": value, "Source": "Rule"} for name, value in RULES]
    c1_ui.static_table(pd.DataFrame(rows), hide=())
    st.caption("The DSS places no orders; purchasing and inventory decisions rest with authorized CDH personnel.")


def setting_value(name: str, value: object, unit: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if "service_level" in str(name) or "holding_rate" in str(name):
        return c1_format.share(number) + (" a year" if "holding" in str(name) else "")
    if "ordering_cost" in str(name):
        return f"{c1_format.pesos_whole(number)} per order"
    if "lead_time" in str(name):
        return f"{number:g} days"
    return f"{c1_format.number(number)} {unit}"


def monthly_update_page() -> None:
    with card("update-status"):
        update_status()
    if SHOW_UPLOAD:
        import c1_update_page
        c1_update_page.monthly_update()
    else:
        st.info("Uploading is not available in the demonstration.")
    with card("planning-settings", "Planning settings"):
        planning_settings()


# ------------------------------------------------------------------ Pages and navigation

# (title, URL path, render function, sidebar icon), in sidebar order; Analysis comes last, after a divider.
PAGE_LIST = [
    (DECISIONS, "decisions", decisions, "decisions"),
    (REORDER, "reorder-planning", reorder_planning, "cart"),
    (WASTE, "waste-and-expiry", waste_expiry, "calendar"),
    (MEDICINE, "medicine-detail", medicine_detail, "medicine"),
    (UPDATE, "monthly-update", monthly_update_page, "upload"),
    (ANALYSIS, "analysis", analysis, "shield"),
]


def url_paths() -> list[str]:
    return ["/", *[f"/{path}" for _, path, *_ in PAGE_LIST], *[f"/{path}" for path in REDIRECTS]]


def planning_page(title: str, render: Callable[[], None]) -> Callable[[], None]:
    def page() -> None:
        if not DATABASE.exists():
            c1_ui.page_header(title, PAGE_LINES[title])
            st.error(f"The planning data was not found at {DATABASE}. Run the Capstone 1 build first.")
            st.stop()
        month = as_of_text()
        c1_ui.topbar(f"Stock as of {month}" if month else None, url_paths())
        c1_ui.page_header(title, PAGE_LINES[title])
        if DEMO:
            st.warning(DEMO_NOTE)
        render()
    return page


def redirect(target: str) -> Callable[[], None]:
    """An earlier address: open the page now at target, keeping the query parameters."""
    def page() -> None:
        st.switch_page(PAGES[target], query_params=dict(st.query_params))
    return page


def sidebar(current: st.Page) -> None:
    """The page buttons, Analysis after a thin divider."""
    keys = {title: f"sidebar-nav-{c1_ui.slug(title)}" for title in PAGES}
    icons = {keys[title]: icon for title, _, _, icon in PAGE_LIST}
    with st.sidebar:
        c1_ui.install_styles(icons)
        c1_ui.sidebar_brand()
        for title, page in PAGES.items():
            if title == ANALYSIS:
                c1_ui.nav_divider()
            if c1_ui.nav_button(title, keys[title], page.url_path == current.url_path):
                # a page button opens the page's default list ("Show me" and bookmarks set theirs)
                st.session_state.update(view=next(iter(VIEWS)), sort=next(iter(SORTS)))
                st.switch_page(page)


# An integer opens the sidebar at that width (open on a wide screen, collapsed on a phone); it can then be dragged.
st.set_page_config(page_title="Inpatient Pharmacy Planning", layout="wide", initial_sidebar_state=c1_ui.SIDEBAR_WIDTH)
PAGES = {title: st.Page(planning_page(title, render), title=title, url_path=path)
         for title, path, render, _ in PAGE_LIST}
# The root address opens Decisions; the earlier addresses open their pages.
HOME = st.Page(redirect(DECISIONS), title="Inpatient Pharmacy Planning", url_path="home", default=True)
MOVED = [st.Page(redirect(target), title=f"{target} (earlier address)", url_path=path)
         for path, target in REDIRECTS.items() if target in PAGES]
current = st.navigation([HOME, *PAGES.values(), *MOVED], position="hidden")
if current is not HOME and current not in MOVED:
    sidebar(current)
current.run()
