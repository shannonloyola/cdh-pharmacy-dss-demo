"""Display formatting for the Capstone 1 pages: one place for column labels, number, peso, percent and date formats,
plain status terms and the suggested action of a medicine. Presentation only: every value shown is a mart value or a
plain restatement of one; nothing here computes a planning quantity.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pandas as pd

PESO = "₱"
REVIEW_STATUSES = ("below safety stock", "at or below ROP (reorder review)")
BELOW_SS, AT_ROP = REVIEW_STATUSES
ABOVE_ROP = "above ROP"
NEGATIVE = "stock record negative"
NO_CONSUMPTION = "NO_CONSUMPTION"
NO_DEMAND = "no demand expected (ROP 0 or next-month forecast below 0.5 units)"
# The reorder statuses of build_planning.stock_status in plain words. The suggested actions group them: "Reorder now" is
# below safety stock or at or below ROP; the other statuses need no order, except that a medicine with no 2025
# consumption reads "Do not reorder" and a negative stock record "Check the stock record".
STATUS_TERMS = {
    BELOW_SS: "Below safety stock",
    AT_ROP: "At or below ROP",
    ABOVE_ROP: "Above ROP",
    NO_DEMAND: "No demand expected (ROP 0 or next-month forecast below 0.5 units)",
    NEGATIVE: "Stock record negative",
    "no reorder point (input missing)": "No reorder point (input missing)",
}
STATUS_ORDER = list(STATUS_TERMS.values())

# Column labels. Columns not listed get their name with spaces and sentence case.
LABELS = {
    "Brand_Name": "Medicine", "Generic_Name": "Generic name", "Unit": "Unit", "Dosage_Form": "Dosage form",
    "ABC_Planning": "ABC class", "VED": "VED", "VED_Category": "VED category", "ABC_VED_Category": "ABC-VED",
    "Reorder_Status": "Status", "Stock_Status": "Stock record", "Planning_Stock": "Stock on hand",
    "Reorder_Point": "Reorder point", "Safety_Stock": "Safety stock", "EOQ": "EOQ", "Suggested_Order": "Suggested order",
    "Order_Multiple": "EOQ batches (n)", "Months_Of_Cover_With_Order": "Months of cover",
    "Baseline_Suggested_Order": "Baseline suggested order", "Adjusted_Suggested_Order": "Adjusted suggested order",
    "Service_Level": "Service level", "Selected_Model": "Forecast model", "Reliability": "Reliability",
    "Test_MAE": "Test MAE", "Test_RMSE": "Test RMSE", "Test_MAPE": "Test MAPE",
    "Test_MAPE_Excluded_Zero_Months": "Test MAPE (zero months excluded)", "Test_WAPE": "Test WAPE",
    "Test_MASE": "Test MASE", "Prospective_2026_MAE": "2026 MAE (Jan-Sep)", "Volume_Class": "Volume class",
    "Limited_Planning_Estimate": "Limited planning estimate", "Forecast_Planning_Month": "Forecast, planning month",
    "Planning_Label": "Label", "Suggested_Action": "Suggested action", "Medicine_Key": "Medicine key",
    "ABC_2021": "ABC 2021", "ABC_2022": "ABC 2022", "ABC_2023": "ABC 2023", "ABC_2024": "ABC 2024",
    "ABC_2025": "ABC 2025", "ABC_2021_2025": "ABC 2021-2025", "Demand_Last_12_Months": "Demand, last 12 months",
    "Months_Of_Cover": "Months of stock at last 12 months' use", "Slow_Moving": "Slow-moving",
    "Excess_Stock": "Excess stock",
    "Expired_Value_12m_Capped": "Expired value, last 12 months (upper bound)", "Expired_Value_Label": "Expired value note",
    "Review_Reason": "Review reason", "Near_Expiry_Lots": "Near-expiry lots",
    "Near_Expiry_Quantity_Capped": "Near-expiry quantity (capped)", "Near_Expiry_Value_Capped": "Near-expiry value (capped)",
    "First_Expiry": "First expiry", "Last_Expiry": "Last expiry", "Stock_At_As_Of": "Stock at the as-of date",
    "Expiration_Date": "Expiry date", "Lot_No": "Lot", "Quantity": "Quantity received",
    "Near_Expiry_Capped_Quantity": "Quantity (capped)", "Near_Expiry_Capped_Value": "Value (capped)",
    "Supplier_Name": "Supplier", "Scenario_Type": "Scenario type", "Baseline_Safety_Stock": "Baseline safety stock",
    "Adjusted_Safety_Stock": "Adjusted safety stock", "Baseline_ROP": "Baseline reorder point",
    "Adjusted_ROP": "Adjusted reorder point", "Change_ROP": "Change in reorder point",
    "Change_ROP_Pct": "Change in reorder point (%)", "Baseline_EOQ": "Baseline EOQ", "Adjusted_EOQ": "Adjusted EOQ",
    "Change_EOQ_Pct": "Change in EOQ (%)", "Lead_Time_Days": "Lead time (days)", "Holding_Rate": "Holding rate",
    "Ordering_Cost": "Ordering cost", "Net_Demand": "Net demand", "Item_Average": "Item average",
    "Period_Label": "Period", "Pandemic_Mean_Monthly_Demand": "Pandemic mean monthly demand",
    "Pandemic_CV": "Pandemic CV", "Post_Pandemic_Mean_Monthly_Demand": "Post-pandemic mean monthly demand",
    "Post_Pandemic_CV": "Post-pandemic CV", "Ratio_Of_Means": "Ratio of means", "CV_Change": "CV change",
    "Stable_Across_Periods": "Stable across periods", "Stable_Rule_Status": "Stable rule status",
    "Value_Capped_PHP": "Value (capped)", "Unit_Cost": "Unit cost", "Value": "Value", "Note": "Note",
    "Expected_File": "Expected file", "Needed_For": "Needed for", "Report_Month": "Report month",
    "Expiry_From": "Expiry from", "Expiry_To": "Expiry to", "Min_Expiry": "Earliest expiry",
    "Max_Expiry": "Latest expiry", "Latest_Document_Date": "Latest document date", "Source_File": "Source file",
    "Item_ID": "Item ID", "Item_Description": "Item description", "Ending_Balance": "Ending balance",
    "Measure_Group": "Measure group", "Order_Value": "Order value (suggested order x unit cost)", "KPI": "KPI",
    "Input": "Assumption", "Replace_With": "Form item",
    "ABC_Class": "ABC class", "Medicine_Count": "Medicines", "Known_ACV": "Spending value",
    "Known_ACV_Share": "Share of spending value", "NON_MOVING": "Non-moving", "PERSISTENT_STABLE": "Persistent, stable",
    "PERSISTENT_VARIABLE": "Persistent, variable", "SPARSE": "Sparse", "Segment_Type": "Segment type",
    "Positive_Targets": "Medicines with use", "Actual_Total": "Actual total", "Forecast_Total": "Forecast total",
    "WAPE_Pct": "WAPE", "Forecast_Bias_Pct": "Forecast bias", "Quantile_Label": "Buffer",
    "Empirical_Coverage_Pct": "Coverage, all medicines", "Positive_Target_Coverage_Pct": "Coverage, medicines with use",
    "Rows": "Medicines", "ABC_AsOf": "ABC class", "Needs_Current_Stock_Override": "Needs a stock check",
    "Needs_Planning_Cost_Override": "Needs a cost check", "Mapping_Status": "Mapping status",
    "Source_Row_Count": "Source rows", "Earliest_Document_Date": "Earliest document date",
    "Latest_Expiration_Date": "Latest expiry", "Earliest_Expiration_Date": "Earliest expiry",
    "Behavior_Segment": "Use pattern", "Latest_Annual_Issuance": "Units issued, 2025",
    "Latest_ACV": "Spending value, 2025", "Years_With_Use": "Years with use",
}
# Whole numbers with commas: stock, reorder point, safety stock, EOQ and the quantities beside them.
WHOLE = {"Planning_Stock", "Reorder_Point", "Safety_Stock", "EOQ", "Baseline_Safety_Stock", "Adjusted_Safety_Stock",
         "Baseline_ROP", "Adjusted_ROP", "Change_ROP", "Baseline_EOQ", "Adjusted_EOQ", "Stock_At_As_Of",
         "Near_Expiry_Quantity_Capped", "Near_Expiry_Capped_Quantity", "Quantity", "Ending_Balance", "Lots",
         "Near_Expiry_Lots", "Medicines", "Count", "Items", "Lead_Time_Days", "Latest_Annual_Issuance",
         "Suggested_Order", "Baseline_Suggested_Order", "Adjusted_Suggested_Order", "Order_Multiple"}
ONE_DECIMAL = {"Months_Of_Cover_With_Order"}
PESOS = {"Near_Expiry_Value_Capped", "Expired_Value_12m_Capped", "Expired_Value_Capped", "Value_Capped_PHP",
         "Near_Expiry_Capped_Value", "Unit_Cost", "Ordering_Cost", "Stock_Value", "Consumption_Value", "Average_Cost",
         "Lot_Value", "Order_Value", "Known_ACV", "Latest_ACV"}
SHARES = {"Service_Level", "Holding_Rate", "Value_Share", "Known_ACV_Share"}          # 0.95 -> 95%
PERCENT_POINTS = {"Change_ROP_Pct", "Change_EOQ_Pct", "Test_MAPE", "Test_MAPE_Excluded_Zero_Months", "Test_WAPE",
                  "WAPE_Pct", "Forecast_Bias_Pct", "Empirical_Coverage_Pct", "Positive_Target_Coverage_Pct"}
MONTHS = {"As_Of_Month", "Month", "Date_Key", "Report_Month", "Forecast_Origin", "Planning_Month", "Unit_Cost_Month"}
DATES = {"First_Expiry", "Last_Expiry", "Expiration_Date", "Expiry_From", "Expiry_To", "Min_Expiry", "Max_Expiry",
         "Latest_Document_Date", "Near_Expiry_As_Of", "Earliest_Document_Date", "Earliest_Expiration_Date",
         "Latest_Expiration_Date"}
# Codes shown as words; acronyms stay as they are.
VALUE_WORDS = {"NO_CONSUMPTION": "No consumption", "class NO_CONSUMPTION": "No consumption", "NAIVE": "Naive",
               "SEASONAL_NAIVE": "Seasonal naive",
               "PROPHET": "Prophet", "HIGH": "High", "MODERATE": "Moderate", "LOW": "Low",
               "INTERMITTENT": "Intermittent", "PROXY": "Proxy", "PROPONENT": "Proponent",
               "UNCLASSIFIED_COST": "Unclassified (no cost)", "ELIGIBLE": "Eligible", "NON_MOVING": "Non-moving",
               "PERSISTENT_STABLE": "Persistent, stable", "PERSISTENT_VARIABLE": "Persistent, variable",
               "SPARSE": "Sparse"}
ENUMS = {"Reorder_Status", "Stock_Status", "ABC_Planning", "Selected_Model", "Volume_Class", "Reliability", "Rule",
         "Review_Reason", "Status", "Stable_Rule_Status", "Period_Label", "Planning_Label", "Expired_Value_Label",
         "Scenario_Type", "Suggested_Action", "Segment", "Behavior_Segment", "ABC_Class", "ABC_Eligibility"}
NOT_AVAILABLE = "not available"
NOT_CLASSED = "Not classed"                   # no 2025 consumption value: outside the ABC-VED matrix
# The planning inputs (config/capstone1_planning_inputs.csv) by name; a grid point reads "Sensitivity grid: <input>
# (<n> of 3)".
INPUT_LABELS = {"lead_time_days": "Lead time", "ordering_cost_php": "Ordering cost",
                "ordering_cost_part_order_preparation": "Ordering cost: order preparation",
                "ordering_cost_part_supplier_follow_up": "Ordering cost: supplier follow-up",
                "ordering_cost_part_receiving": "Ordering cost: receiving",
                "ordering_cost_part_payment": "Ordering cost: payment",
                "ordering_cost_part_office_supplies": "Ordering cost: office supplies",
                "holding_rate_annual": "Holding rate", "service_level_V": "Service level, Vital",
                "service_level_E": "Service level, Essential", "service_level_D": "Service level, Desirable"}
GRID_INPUTS = {"grid_lead_time_days": "lead time", "grid_service_level": "service level",
               "grid_holding_rate": "holding rate", "grid_ordering_cost": "ordering cost"}


def input_label(name: object) -> object:
    """A planning input's name in words ("holding_rate_annual" -> "Holding rate")."""
    text = str(name)
    if text in INPUT_LABELS:
        return INPUT_LABELS[text]
    for prefix, words_ in GRID_INPUTS.items():
        if text.startswith(prefix + "_"):
            return f"Sensitivity grid: {words_} ({text.rsplit('_', 1)[-1]} of 3)"
    return name


def label(column: str) -> str:
    if column in LABELS:
        return LABELS[column]
    text = str(column).replace("_", " ").strip()
    return text[:1].upper() + text[1:].lower() if text.isupper() or "_" in str(column) else text


def sentence(value: object) -> object:
    """A code or status in sentence case: the first letter capitalised, acronyms (ROP, EOQ, ABC) kept."""
    if not isinstance(value, str) or not value:
        return value
    if value in VALUE_WORDS:
        return VALUE_WORDS[value]
    return value[0].upper() + value[1:]


def _missing(value: object) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or value is pd.NA or value is pd.NaT


def whole(value: object) -> str:
    """Whole numbers with commas; a quantity under 1 keeps one decimal (0.4, not 0)."""
    if _missing(value):
        return NOT_AVAILABLE
    number = float(value)
    if 0 < abs(number) < 1:
        return f"{number:.1f}" if abs(number) >= 0.05 else ("<0.1" if number > 0 else ">-0.1")
    return f"{number:,.0f}"


def one_decimal(value: object) -> str:
    """One decimal; an infinite value (no cover: nothing is forecast) is a blank cell."""
    if _missing(value):
        return NOT_AVAILABLE
    return "" if math.isinf(float(value)) else f"{float(value):,.1f}"


def pesos(value: object) -> str:
    return NOT_AVAILABLE if _missing(value) else f"{PESO}{float(value):,.2f}"


def share(value: object) -> str:
    if _missing(value):
        return NOT_AVAILABLE
    number = float(value) * 100
    return f"{number:,.0f}%" if abs(number - round(number)) < 1e-9 else f"{number:,.1f}%"


def points(value: object) -> str:
    return NOT_AVAILABLE if _missing(value) else f"{float(value):,.1f}%"


def count(value: object) -> str:
    """A tile value: whole numbers with commas, anything else as given."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or _missing(value):
        return str(value)
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"


def number(value: object) -> str:
    if _missing(value):
        return NOT_AVAILABLE
    number = float(value)
    return f"{number:,.0f}" if abs(number - round(number)) < 1e-9 else f"{number:,.2f}"


def month(value: object) -> str:
    """'2026-09' -> 'Sep 2026'."""
    if _missing(value) or value == "":
        return NOT_AVAILABLE if _missing(value) else ""
    try:
        return pd.Period(str(value)[:7], freq="M").strftime("%b %Y")
    except (ValueError, TypeError):
        return str(value)


def day(value: object) -> str:
    """A date as '3 Apr 2026' (a lot's expiry needs the day)."""
    if _missing(value) or value == "":
        return NOT_AVAILABLE if _missing(value) else ""
    try:
        stamp = pd.Timestamp(value)
    except (ValueError, TypeError):
        return str(value)
    return f"{stamp.day} {stamp.strftime('%b %Y')}"


def yes_no(value: object) -> str:
    return NOT_AVAILABLE if _missing(value) else ("Yes" if bool(value) else "No")


def formatter(column: str, dtype) -> Callable[[object], object] | None:
    if column in WHOLE:
        return whole
    if column in ONE_DECIMAL:
        return one_decimal
    if column in PESOS:
        return pesos
    if column in SHARES:
        return share
    if column in PERCENT_POINTS:
        return points
    if column in MONTHS:
        return month
    if column in DATES:
        return day
    if pd.api.types.is_bool_dtype(dtype):
        return yes_no
    if column == "Reorder_Status":
        return lambda v: NOT_AVAILABLE if _missing(v) else status_term(v)
    if column == "ABC_VED_Category":            # a medicine with no 2025 consumption value is outside the matrix
        return lambda v: NOT_CLASSED if _missing(v) else v
    if column in ENUMS:
        return lambda v: NOT_AVAILABLE if _missing(v) else sentence(v)
    if pd.api.types.is_numeric_dtype(dtype):
        return number
    return lambda v: NOT_AVAILABLE if _missing(v) else (words(v) if isinstance(v, str) else v)


def words(text: str) -> str:
    """A code as a word, also inside a sentence ("class NO_CONSUMPTION" -> "class no consumption")."""
    if text in VALUE_WORDS:
        return VALUE_WORDS[text]
    return text.replace("NO_CONSUMPTION", "no consumption")


def display(frame: pd.DataFrame):
    """The frame for st.dataframe: human column labels and formatted values, as a pandas Styler, so sorting a column
    still sorts by its value. Missing values read "not available" (st.dataframe's placeholder; Streamlit draws missing
    cells itself), except that a medicine outside the ABC-VED matrix reads "Not classed", a lot number of 0 or blank
    "not recorded", and the months of cover of a medicine with nothing forecast is blank."""
    if "ABC_VED_Category" in frame and frame.ABC_VED_Category.isna().any():
        frame = frame.assign(ABC_VED_Category=frame.ABC_VED_Category.astype(object).where(
            frame.ABC_VED_Category.notna(), NOT_CLASSED))
    if "Months_Of_Cover_With_Order" in frame and "Forecast_Planning_Month" in frame:
        # nothing forecast: no months of cover, a blank cell (a value, so the column still sorts as numbers)
        zero = frame.Months_Of_Cover_With_Order.isna() & frame.Forecast_Planning_Month.le(0)
        frame = frame.assign(Months_Of_Cover_With_Order=frame.Months_Of_Cover_With_Order.mask(zero, math.inf))
    if "Lot_No" in frame:                       # a lot number of 0 or blank was not recorded in the export
        lot = frame.Lot_No.astype(object)
        blank = lot.isna() | lot.astype(str).str.strip().isin(["", "0", "0.0"])
        frame = frame.assign(Lot_No=lot.where(~blank, "not recorded"))
    renamed = frame.rename(columns={c: label(c) for c in frame.columns})
    renamed = renamed.loc[:, ~renamed.columns.duplicated()]
    formats = {label(c): formatter(c, frame[c].dtype) for c in frame.columns}
    return renamed.style.format({k: f for k, f in formats.items() if f is not None and k in renamed}, na_rep=NOT_AVAILABLE)


# ------------------------------------------------------------------ suggested action

DO_NOT_REORDER, NO_DEMAND_ACTION, NO_ORDER, CHECK_RECORD = ("Do not reorder", "No demand expected", "No order needed",
                                                          "Check the stock record")


def suggested_action(status: object, abc: object = None, quantity: object = None, stock: object = None,
                     excess: object = None) -> str:
    """The plain action of a medicine, restated from its existing reorder status, ABC class, suggested order (n x EOQ,
    the (s, nQ) policy of the planning step), stock and excess-stock flag; the first that applies:
    no plan row (not forecast) -> "Not planned (no forecast)"; below safety stock -> "Order urgently <suggested order>";
    at or below ROP -> "Order <suggested order>"; a negative stock record -> "Check the stock record"; no 2025
    consumption with stock held, or
    excess stock (above ROP + EOQ) -> "Do not reorder"; no demand expected (ROP 0 or a next-month forecast below 0.5
    units) -> "No demand expected"; above ROP -> "No order needed".
    """
    if _missing(status):
        return "Not planned (no forecast)"
    amount = "" if _missing(quantity) else f" {float(quantity):,.0f}"
    if status == BELOW_SS:
        return f"Order urgently{amount}" if amount else "Order urgently (order quantity not available)"
    if status == AT_ROP:
        return f"Order{amount}" if amount else "Order (order quantity not available)"
    if status == NEGATIVE:
        return CHECK_RECORD
    held = not _missing(stock) and float(stock) > 0
    if (abc == NO_CONSUMPTION and held) or (not _missing(excess) and bool(excess)):
        return DO_NOT_REORDER
    if status == NO_DEMAND:
        return NO_DEMAND_ACTION
    if status == "no reorder point (input missing)":
        return "Check the inputs"
    return NO_ORDER


def with_action(frame: pd.DataFrame, reorder: pd.DataFrame | None = None) -> pd.DataFrame:
    """The frame with a Suggested_Action column as its second column. Status, EOQ, stock and the excess-stock flag come
    from the frame itself or, when it lacks them, from the reorder table (by Medicine_Key)."""
    if not len(frame.columns):
        return frame
    source = frame
    on = next((c for c in ("Medicine_Key", "Brand_Name") if reorder is not None and c in frame and c in reorder), None)
    extra = [c for c in ("Reorder_Status", "Suggested_Order", "Planning_Stock", "Excess_Stock")
             if on and c not in frame and c in reorder]
    if extra:
        lookup = reorder.drop_duplicates(on).set_index(on)[extra]
        source = frame.join(lookup, on=on)
    actions = [suggested_action(s, a, q, h, x) for s, a, q, h, x in zip(
        source.get("Reorder_Status", pd.Series(index=source.index, dtype=object)),
        source.get("ABC_Planning", pd.Series(index=source.index, dtype=object)),
        source.get("Suggested_Order", pd.Series(index=source.index, dtype=float)),
        source.get("Planning_Stock", pd.Series(index=source.index, dtype=float)),
        source.get("Excess_Stock", pd.Series(index=source.index, dtype=object)))]
    out = frame.copy()
    out.insert(1 if len(out.columns) else 0, "Suggested_Action", actions)
    return out


def status_term(status: object) -> object:
    return STATUS_TERMS.get(status, sentence(status))
