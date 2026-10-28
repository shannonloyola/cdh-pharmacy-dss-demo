"""Shared visual theme: palette, safety-net CSS, Plotly styling, light tables, display-safe values.

The app is a light design. `.streamlit/config.toml` pins Streamlit's own theme to light so the
operating system's dark mode cannot recolour widgets, tables and charts, and everything in this
module sets its colours explicitly so nothing inherits a theme colour. No data or analytical
logic lives here.
"""

from __future__ import annotations

import math
import re

import pandas as pd
import streamlit as st

# Palette: the hex values already used by app/ui_clone.css and app/main.py.
INK = "#14264a"
TEXT = "#3d4f5f"
MUTED = "#5b6b7b"
LINE = "#e3e8eb"
CANVAS = "#f3f7f8"
SURFACE = "#ffffff"
TEAL = "#1f6f78"
TEAL_DARK = "#145e59"
TEAL_SOFT = "#eaf3f3"
HEADER_FILL = "#eaf3f3"
ZEBRA = "#f7fafb"
GRID = "#e3e8eb"
CONTROL_EDGE = "#6b7c8f"  # outlines of unselected controls: 3:1 or more on white and on the canvas
FONT_FAMILY = "Inter, 'Segoe UI', Arial, sans-serif"

NOT_AVAILABLE = "Not available"
NO_UNIT_COST = "Not available (no unit cost)"

# Tokens that must never be visible in a table or in text.
RAW_NULL_TOKENS = ("None", "nan", "NaN", "<NA>", "NaT")
_RAW_NULL_PATTERN = re.compile(r"(?<![A-Za-z0-9])(None|nan|NaN|<NA>|NaT)(?![A-Za-z0-9])")


# ------------------------------------------------------------
# CSS safety net (explicit colours for every widget type)
# ------------------------------------------------------------

THEME_CSS = f"""
:root {{ color-scheme: light; }}
html, body, .stApp, [data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
  color-scheme: light; color: {INK}; }}
[data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background-color: {CANVAS}; }}
[data-testid="stSidebar"] {{ background-color: #eff4f5; }}
.stApp p, .stApp li, .stApp span, .stApp label, .stApp div[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] strong, [data-testid="stMarkdownContainer"] em {{ color: {INK}; }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{ color: {INK}; }}
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p,
.stApp small, .stApp .stCaption {{ color: {MUTED} !important; opacity: 1 !important; }}
.stApp [data-testid="stWidgetLabel"], .stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stWidgetLabel"] label {{ color: {INK}; }}
.stApp [data-testid="stRadio"] label, .stApp [data-testid="stRadio"] label p,
.stApp [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stCheckbox"] label, .stApp [data-testid="stCheckbox"] label p,
.stApp [data-testid="stToggle"] label, .stApp [data-testid="stToggle"] label p {{ color: {INK}; }}
/* unselected radio ring: the default #e3e8eb on the canvas is about 1.1:1; controls need 3:1 */
.stApp [data-testid="stRadioOption"]:not([data-selected="true"]) > div > div > div:first-child {{ background-color: {CONTROL_EDGE} !important; }}
.stApp [data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child,
.stApp label[data-selected="true"] > div:first-child {{ background-color: {TEAL}; border-color: {TEAL}; }}
/* toggle off-state: grey track with a white knob (the default track is about 1.1:1 on the canvas) */
.stApp [data-testid="stCheckbox"] label:not([data-selected="true"]) > div:first-of-type {{ background-color: {CONTROL_EDGE} !important; }}
.stApp [data-testid="stCheckbox"] label > div:first-of-type > div {{ background-color: #ffffff !important; }}
/* text inputs, selects, multiselects */
.stApp input, .stApp textarea, .stApp [data-baseweb="input"], .stApp [data-baseweb="base-input"],
.stApp [data-baseweb="select"] > div, .stApp [data-baseweb="select"] input, .stApp [data-baseweb="select"] span,
.stApp [data-baseweb="textarea"] {{ background-color: #f7f9fa; color: {INK}; -webkit-text-fill-color: {INK};
  caret-color: {INK}; }}
.stApp input::placeholder, .stApp textarea::placeholder {{ color: {MUTED}; -webkit-text-fill-color: {MUTED}; opacity: 1; }}
.stApp [data-baseweb="select"] svg, .stApp [data-baseweb="input"] svg {{ fill: {INK}; color: {INK}; }}
/* dropdown / popover menus are rendered in a portal outside .stApp */
[data-baseweb="popover"], [data-baseweb="popover"] > div, [data-baseweb="menu"], [data-baseweb="menu"] ul,
[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] ul {{ background-color: {SURFACE}; color: {INK}; }}
[data-baseweb="popover"] li, [data-baseweb="popover"] [role="option"], [data-baseweb="menu"] li,
[data-baseweb="popover"] li span, [data-baseweb="popover"] [role="option"] span, [data-baseweb="popover"] div {{
  background-color: {SURFACE}; color: {INK}; }}
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [aria-selected="true"], [data-baseweb="menu"] li:hover {{ background-color: {TEAL_SOFT}; }}
/* tabs: teal when active, never the red default */
.stApp [data-baseweb="tab"], .stApp [data-baseweb="tab"] p, .stApp [role="tab"] p {{ color: {TEXT}; }}
.stApp [data-baseweb="tab"][aria-selected="true"], .stApp [data-baseweb="tab"][aria-selected="true"] p,
.stApp [role="tab"][aria-selected="true"], .stApp [role="tab"][aria-selected="true"] p {{ color: {TEAL} !important; }}
.stApp [data-baseweb="tab-highlight"] {{ background-color: {TEAL} !important; }}
.stApp [data-baseweb="tab-border"] {{ background-color: {LINE}; }}
/* expanders */
.stApp [data-testid="stExpander"] details, .stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary p, .stApp [data-testid="stExpander"] summary span {{ color: {INK}; }}
.stApp [data-testid="stExpander"] details {{ background-color: {SURFACE}; border-color: {LINE}; }}
/* buttons */
.stApp .stButton > button, .stApp [data-testid="stBaseButton-secondary"], .stApp .stDownloadButton > button,
.stApp [data-testid="stBaseButton-secondaryFormSubmit"] {{ background-color: {SURFACE}; color: {INK};
  border: 1px solid #c9d4dc; }}
.stApp .stButton > button p, .stApp .stDownloadButton > button p {{ color: {INK}; }}
.stApp .stButton > button:hover, .stApp .stDownloadButton > button:hover {{ border-color: {TEAL}; color: {TEAL}; }}
.stApp .stButton > button:hover p, .stApp .stDownloadButton > button:hover p {{ color: {TEAL}; }}
.stApp [data-testid="stBaseButton-primary"] {{ background-color: {TEAL}; border-color: {TEAL}; color: #ffffff; }}
.stApp [data-testid="stBaseButton-primary"] p {{ color: #ffffff; }}
/* slider */
.stApp [data-testid="stSlider"] label, .stApp [data-testid="stSlider"] p,
.stApp [data-testid="stSliderTickBar"] p, .stApp [data-testid="stSliderThumbValue"] p {{ color: {INK}; }}
/* the clone stylesheet hides the thumb value; show it so the chosen level is readable on the slider */
.stApp [data-testid="stSliderThumbValue"] {{ display: block !important; }}
.stApp [data-testid="stSliderThumbValue"] p {{ color: {INK} !important; font-weight: 600; }}
/* alerts keep their own tinted backgrounds, so give them readable text */
.stApp [data-testid="stAlert"] p, .stApp [data-testid="stAlert"] div {{ color: {INK}; }}
.stApp [data-testid="stAlertContainer"] {{ color: {INK}; }}
/* tables and dataframes */
.stApp [data-testid="stDataFrame"], .stApp [data-testid="stDataFrameResizable"] {{ background-color: {SURFACE};
  border: 1px solid {LINE}; border-radius: 12px; }}
.stApp [data-testid="stTable"] table, .stApp [data-testid="stTable"] td, .stApp [data-testid="stTable"] th {{
  background-color: {SURFACE}; color: {INK}; border-color: {LINE}; }}
.stApp [data-testid="stTable"] th {{ background-color: {HEADER_FILL}; }}
"""


# The earlier app (app/main.py) is a light design and hides Streamlit's menu, where a theme is chosen. Since
# .streamlit/config.toml defines a light and a dark theme (for app/capstone1_app.py), an operating system in dark mode
# would turn its widgets and tables dark under its light styles; this stores the light choice, as the settings menu
# does, and reloads once. A session flag keeps it from ever reloading twice.
_KEEP_LIGHT_JS = """
export default function () {
  try {
    if (window.sessionStorage.getItem('cdh-keep-light')) return;
    window.sessionStorage.setItem('cdh-keep-light', '1');
    const key = `stActiveTheme-${window.location.pathname}-v2`;
    window.localStorage.setItem(key, JSON.stringify('Light'));
    if (window.localStorage.getItem(key) === JSON.stringify('Light')) window.location.reload();
  } catch (e) {}
}
"""


def keep_light_mode() -> None:
    """Keep the earlier app light when the browser reports dark mode (see _KEEP_LIGHT_JS)."""
    try:
        dark = st.context.theme.type == "dark"
    except Exception:  # noqa: BLE001 - no browser context (tests)
        dark = False
    if dark:
        from streamlit.components.v2 import component
        component("cdh_keep_light", js=_KEEP_LIGHT_JS)(key="cdh-keep-light", data={})


def install_theme_css() -> None:
    """Inject the safety-net CSS. Safe to call once per run, after the page CSS."""
    st.html("<style>" + THEME_CSS + "</style>")


# ------------------------------------------------------------
# Plotly
# ------------------------------------------------------------

def style_figure(figure):
    """Light template with every text, axis, legend and colorbar colour set explicitly.

    Bar and scatter label colours are left to Plotly's contrast logic for text drawn inside a
    shape; text drawn outside a shape is set to ink.
    """
    figure.update_layout(
        template="plotly_white",
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": FONT_FAMILY, "color": INK, "size": 13},
        title_font={"color": INK},
        legend={"font": {"color": INK}, "title": {"font": {"color": INK}}, "bgcolor": "rgba(255,255,255,0)"},
        hoverlabel={"bgcolor": SURFACE, "font": {"color": INK, "family": FONT_FAMILY}, "bordercolor": LINE},
        colorway=[TEAL, "#d9a441", "#5b7b87", "#b8c2cc", "#294d7e", "#a66a1f"],
    )
    axis = {
        "tickfont": {"color": INK},
        "title": {"font": {"color": INK}},
        "gridcolor": GRID,
        "linecolor": "#c9d4dc",
        "zerolinecolor": "#c9d4dc",
    }
    figure.update_xaxes(**axis)
    figure.update_yaxes(**axis)
    figure.update_coloraxes(colorbar={"tickfont": {"color": INK}, "title": {"font": {"color": INK}}})
    for trace in figure.data:
        if hasattr(trace, "outsidetextfont"):
            try:
                trace.update(outsidetextfont={"color": INK})
            except Exception:
                pass
        if trace.type == "heatmap" and hasattr(trace, "colorbar"):
            trace.update(colorbar={"tickfont": {"color": INK}, "title": {"font": {"color": INK}}})
    for annotation in figure.layout.annotations or []:
        if annotation.font is None or annotation.font.color is None:
            annotation.update(font={"color": INK})
    return figure


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(hex_color: str) -> float:
    def channel(v: int) -> float:
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground_hex: str, background_hex: str) -> float:
    high, low = sorted((_luminance(foreground_hex), _luminance(background_hex)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def readable_text_color(background_hex: str) -> str:
    """Ink or white, whichever reads better on the given fill."""
    return INK if contrast_ratio(INK, background_hex) >= contrast_ratio("#ffffff", background_hex) else "#ffffff"


# Stepped teal scale for count heatmaps. A continuous scale puts mid-tones where neither white nor
# ink text reaches 4.5:1, so cells use fixed bands whose text colour is chosen for contrast.
HEATMAP_BANDS = [
    (0.10, "#eef5f6"),
    (0.25, "#cfe3e5"),
    (0.50, "#9cc5c9"),
    (0.75, "#1f6f78"),
    (1.01, "#145e59"),
]


def heatmap_band_color(fraction: float) -> str:
    for upper, color in HEATMAP_BANDS:
        if fraction < upper:
            return color
    return HEATMAP_BANDS[-1][1]


def show_chart(figure, **kwargs) -> None:
    """st.plotly_chart with our template; Streamlit's theme must not override it (theme=None)."""
    kwargs.setdefault("width", "stretch")
    st.plotly_chart(style_figure(figure), theme=None, **kwargs)


# ------------------------------------------------------------
# Tables
# ------------------------------------------------------------

def _is_missing(value) -> bool:
    if value is None or value is pd.NaT:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def display_frame(frame: pd.DataFrame, null_labels: dict[str, str] | None = None, default: str = NOT_AVAILABLE):
    """The frame, or a pandas Styler whose missing values read as a plain label.

    Without missing values the frame is returned unchanged. With them, the underlying data stay
    numeric (so sorting still works) and only the displayed text changes. `null_labels` sets the
    label per column, for example "Not available (no unit cost)".
    """
    labels = null_labels or {}
    with_nulls = [column for column in frame.columns if frame[column].isna().any()]
    if not with_nulls:
        return frame
    styler = frame.style
    for column in with_nulls:
        styler = styler.format(na_rep=labels.get(column, default), subset=[column])
    return styler


def show_table(frame: pd.DataFrame, *, null_labels: dict[str, str] | None = None, **kwargs) -> None:
    """The one place tables are drawn: missing values get a plain label.

    Colours come from the pinned light Streamlit theme (.streamlit/config.toml) and THEME_CSS.
    """
    kwargs.setdefault("hide_index", True)
    kwargs.setdefault("width", "stretch")
    data = display_frame(frame, null_labels=null_labels)
    st.dataframe(data, **kwargs)


def raw_null_tokens_in(value) -> list[str]:
    """Raw missing-value tokens (None, nan, NaN, <NA>, NaT) visible in a string."""
    return _RAW_NULL_PATTERN.findall(str(value))


# ------------------------------------------------------------
# CSV download (in memory: nothing is written to disk)
# ------------------------------------------------------------

DOWNLOAD_LABEL = "Download list (CSV)"
DOWNLOAD_CAPTION = "Contains CDH data; handle accordingly."
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def csv_bytes(frame: pd.DataFrame) -> bytes:
    """The table as UTF-8 CSV (with a byte-order mark so Excel reads it correctly).

    Text cells that a spreadsheet would read as a formula get a leading apostrophe.
    """
    safe = frame.copy()
    for column in safe.columns:
        if not pd.api.types.is_numeric_dtype(safe[column]) and not pd.api.types.is_bool_dtype(safe[column]):
            safe[column] = safe[column].map(
                lambda value: "'" + value if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES) else value
            )
    return safe.to_csv(index=False).encode("utf-8-sig")


def download_csv_button(frame: pd.DataFrame, file_name: str, key: str, label: str = DOWNLOAD_LABEL) -> None:
    st.download_button(
        label, data=csv_bytes(frame), file_name=file_name, mime="text/csv", key=key, on_click="ignore"
    )
    st.caption(DOWNLOAD_CAPTION)
