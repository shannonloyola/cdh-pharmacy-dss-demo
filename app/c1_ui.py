"""Presentation helpers for the Capstone 1 pages (app/capstone1_app.py), built on the existing app's visual system.

The stylesheets are the existing ones, installed in the order app/main.py installs them: app/ui_main.css, app/ui_clone.css
(with the Inter fonts), app/ui_plan.css and ui_theme.THEME_CSS, each in the browser's light or dark mode (app/c1_theme.py).
The markup reuses their classes: the sidebar brand, group label and page buttons, the page header, the KPI tiles
(dss-workspace-metric), the white cards, the filter bar (clone-medicine-filters) and the matrix. C1_CSS adds the top bar,
the question cards and the page-button icons, on the colour tokens of c1_theme. Tables go through c1_format (labels and
formats); charts are Altair charts in the mode's colours. Markup only: no data or analytical logic.
"""

from __future__ import annotations

import html
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import altair as alt
import pandas as pd
import streamlit as st

import c1_format
import c1_theme
import ui_theme
from ui_clone import _stylesheet as clone_stylesheet, clone_footer
from ui_clone_table import clone_table

APP_DIR = Path(__file__).resolve().parent
ALL = "All"

# Tile icons: the paths of app/main.py's SVG_ICONS, with a cross and a warning sign for statuses.
SVG_ICONS = {
    "overview": '<circle cx="10" cy="10" r="7"/><path d="M10 6v4l3 2"/>',
    "medicine": '<rect x="3" y="4" width="14" height="12" rx="2"/><path d="M6 8h8M6 12h5"/>',
    "forecast": '<path d="M3 15l4-5 3 2 5-7"/><path d="M12 5h3v3"/>',
    "procurement": '<path d="M4 5h12l-1 9H5L4 5Z"/><path d="M7 5a3 3 0 0 1 6 0M7 17h.01M13 17h.01"/>',
    "expiry": '<rect x="3" y="4" width="14" height="13" rx="2"/><path d="M6 2v4M14 2v4M3 8h14M7 11h3M7 14h5"/>',
    "validation": '<path d="M10 2l2 3 3 .5-2 2.5.5 3.5-3.5-1.5L6.5 11 7 8.5 5 6l3-.5L10 2Z"/><path d="m8 15 2 2 4-4"/>',
    "governance": '<path d="M10 2 17 5v5c0 4-3 6.5-7 8-4-1.5-7-4-7-8V5l7-3Z"/><path d="m7 10 2 2 4-4"/>',
    "check": '<path d="m4 10 4 4 8-8"/>',
    "attention": '<path d="M10 3 18 17H2L10 3Z"/><path d="M10 8v4M10 14h.01"/>',
    "warning": '<path d="M10 3 18 17H2L10 3Z"/><path d="M10 8v4M10 14h.01"/>',
    "cross": '<circle cx="10" cy="10" r="7"/><path d="m7 7 6 6M13 7l-6 6"/>',
    "info": '<circle cx="10" cy="10" r="7"/><path d="M10 9v5M10 6h.01"/>',
}
# Status icons take the status colour; the others the teal of the existing tiles.
ICON_TOKENS = {"check": "teal", "warning": "amber", "cross": "red", "attention": "amber"}

# Page-button icons: the paths of app/ui_clone.py's sidebar icons.
NAV_ICONS = {
    "overview": '<rect x="2" y="2" width="6" height="6" rx="1"/><rect x="12" y="2" width="6" height="6" rx="1"/><rect x="2" y="12" width="6" height="6" rx="1"/><rect x="12" y="12" width="6" height="6" rx="1"/>',
    "cart": '<path d="M2 4h2l2.2 10h9.6l2-7H5"/><circle cx="8" cy="17" r="1"/><circle cx="15" cy="17" r="1"/>',
    "calendar": '<rect x="2.5" y="4" width="15" height="14" rx="2"/><path d="M6 2v4m8-4v4M3 8h14M6 12h8M6 15h5"/>',
    "medicine": '<path d="M7 2.5l9 5v9l-9 5-9-5v-9z" transform="translate(3 -2) scale(.85)"/>',
    "shield": '<path d="M10 2l7 3v5c0 4-3 6-7 8-4-2-7-4-7-8V5z"/><path d="M7 10l2 2 4-4"/>',
    "book": '<path d="M3 3h6c1.5 0 2.5.5 3 1.5C12.5 3.5 13.5 3 15 3h3v14h-3c-1.5 0-2.5.5-3 1.5C11.5 17.5 10.5 17 9 17H3zM12 4.5v14"/>',
    "upload": '<path d="M10 13V3M5.5 7.5 10 3l4.5 4.5"/><path d="M3 13v3.5h14V13"/>',
    "decisions": '<path d="M4 4h12v12H4z"/><path d="m7 10 2 2 4-4"/>',
}

# Existing rules from app/ui_clone.css, repeated for keys used more than once per page, then the new parts on tokens.
C1_CSS = """
[class*="st-key-clone-medicine-filters-"]{background:var(--c1-canvas);border:1px solid var(--c1-line);border-radius:12px;padding:14px 18px}
[class*="st-key-clone-medicine-filters-"] [data-testid="stVerticalBlock"]{gap:0}
[class*="st-key-c1-metric-grid-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{flex:1 1 0%!important;min-width:0!important}
[class*="st-key-c1-metric-grid-"] .dss-workspace-metric{min-height:150px}
.dss-workspace-metric-value.c1-text{white-space:normal;overflow-wrap:anywhere;font-size:20px;line-height:1.25}
.dss-workspace-metric-value.c1-long{font-size:17px}
.c1-tile-caption{font:400 14px/1.4 Inter,sans-serif;color:var(--c1-muted);margin-top:6px}
[class*="st-key-c1-card-"]{background:var(--c1-surface);border:1px solid var(--c1-line);border-radius:20px;box-shadow:0 3px 14px #14264a08;padding:30px;box-sizing:border-box}
[class*="st-key-c1-card-"] > [data-testid="stVerticalBlock"]{gap:24px}
.c1-card-title{font:600 26px/1.3 Inter,sans-serif;color:var(--c1-ink);letter-spacing:-.6px;border-bottom:1px solid var(--c1-line);margin:-8px -30px 0;padding:0 30px 20px}
@media(min-width:901px){:is([class*="st-key-c1-"],[class*="st-key-clone-medicine-filters-"],[class*="st-key-clone-section-"]) [data-testid="stHorizontalBlock"]{flex-wrap:nowrap}}
@media(max-width:1200px){[class*="st-key-c1-metric-grid-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{flex:1 1 calc(50% - 22px)!important}}
@media(max-width:600px){[class*="st-key-c1-metric-grid-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{flex:1 1 100%!important}[class*="st-key-c1-card-"]{padding:16px}.c1-card-title{font-size:22px;margin:-4px -16px 0;padding:0 16px 16px}}
/* the top bar: page title, stock badge, mode toggle; the badge and toggle never shrink, the title gives way */
.st-key-c1-topbar{position:fixed;z-index:990;left:348px;right:0;top:0;width:auto!important;height:93px;background:var(--c1-surface);border-bottom:1px solid var(--c1-line);padding:0 32px 0 40px;box-sizing:border-box;flex-wrap:nowrap!important;align-items:center;gap:16px}
.st-key-c1-topbar > div{flex:0 0 auto!important;width:auto!important;min-width:0}
.st-key-c1-topbar > div:first-child{flex:1 1 auto!important}
body:has([data-testid="stSidebar"][aria-expanded="false"]) .st-key-c1-topbar{left:0;padding-left:72px}
/* Streamlit's own header is a transparent strip above the top bar: clicks pass through it to the toggle, except on
   its sidebar button */
.stApp [data-testid="stHeader"]{pointer-events:none}
.stApp [data-testid="stHeader"] [data-testid="stExpandSidebarButton"],
.stApp [data-testid="stHeader"] [data-testid="stExpandSidebarButton"] *{pointer-events:auto}
.stApp [data-testid="stMarkdownContainer"] p.c1-topbar-title{font:600 22px/1.2 Inter,sans-serif;color:var(--c1-ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:0}
.c1-badge{display:inline-flex;align-items:center;gap:9px;white-space:nowrap;font:500 15px/1 Inter,sans-serif;color:var(--c1-ink);background:var(--c1-teal-soft);border:1px solid var(--c1-line);border-radius:999px;padding:9px 14px}
.c1-badge i{width:8px;height:8px;background:var(--c1-teal);border-radius:50%}
@media(max-width:900px){.st-key-c1-topbar{left:0;height:70px;padding:0 12px 0 56px;gap:8px}.stApp [data-testid="stMarkdownContainer"] p.c1-topbar-title{font-size:17px}}
@media(max-width:600px){.c1-badge{font-size:12px;padding:6px 9px}}
/* a compact page header: the title is also in the top bar */
.stApp .dss-workspace-page-header{height:auto!important;min-height:0!important;padding:22px 30px!important;margin-bottom:8px!important}
.stApp .dss-workspace-heading{font-size:32px}
/* the assumption line under the header */
.stApp [data-testid="stMarkdownContainer"] p.c1-assumption{font:400 15px/1.5 Inter,sans-serif;color:var(--c1-text);margin:0}
/* question cards: one height per row on wide screens, the button at the bottom */
[class*="st-key-c1-question-"]{background:var(--c1-surface);border:1px solid var(--c1-line);border-radius:18px;padding:22px 24px;box-sizing:border-box}
@media(min-width:1100px){[class*="st-key-c1-question-"]{min-height:292px}}
[class*="st-key-c1-question-"] > div:last-child{margin-top:auto}
.stApp [data-testid="stMarkdownContainer"] p.c1-question{font:600 18px/1.35 Inter,sans-serif;color:var(--c1-ink);margin:0 0 6px}
.stApp [data-testid="stMarkdownContainer"] p.c1-answer{font:700 32px/1.15 Inter,sans-serif;color:var(--c1-teal);letter-spacing:-.6px;margin:0 0 6px}
.stApp [data-testid="stMarkdownContainer"] p.c1-answer.attention{color:var(--c1-red)}
.stApp [data-testid="stMarkdownContainer"] p.c1-answer.c1-name{font-size:22px;line-height:1.3;letter-spacing:-.2px}
.stApp [data-testid="stMarkdownContainer"] p.c1-answer-detail{font:400 15px/1.45 Inter,sans-serif;color:var(--c1-text);margin:0}
.c1-answer-detail strong{color:var(--c1-ink)}
/* the ABC-VED matrix: the cell text keeps its contrast on the coloured fills (the markdown text rule would recolour it) */
.stApp .clone-matrix-cell.strong, .stApp .clone-matrix-cell.strong strong, .stApp .clone-matrix-cell.strong span{color:var(--c1-on-teal)}
.stApp .clone-matrix-cell.warm{background:var(--c1-amber-cell)}
.stApp .clone-matrix-cell.warm, .stApp .clone-matrix-cell.warm strong, .stApp .clone-matrix-cell.warm span{color:var(--c1-on-amber)}
/* the small sidebar label of the panel's page */
.dss-nav-group.c1-panel{font-size:11px;margin-top:22px;margin-bottom:6px}
"""


def slug(text: str) -> str:
    return text.lower().replace("&", "and").replace(" ", "-").replace("'", "")


def nav_icon_css(keys: dict[str, str]) -> str:
    """The icon of each page button, as app/ui_clone.py draws them: {button key: NAV_ICONS name}."""
    rules = []
    for key, name in keys.items():
        svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20' fill='none' stroke='black' "
               "stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'>" + NAV_ICONS[name] + "</svg>")
        rules.append(f'.st-key-{key} button::before' + '{--nav-icon:url("data:image/svg+xml,' + quote(svg, safe="") + '")}')
    return "\n".join(rules)


def install_styles(nav_keys: dict[str, str]) -> None:
    """The existing stylesheets, in app/main.py's order, in the browser's mode, then the tokens, C1_CSS and the
    page-button icons."""
    mode = c1_theme.mode()
    st.html("<style>" + c1_theme.stylesheet("ui_main.css", mode) + "</style>")
    st.html("<style>" + _clone_css(mode) + "</style>")
    st.html("<style>" + c1_theme.stylesheet("ui_plan.css", mode) + "</style>")
    st.html("<style>" + c1_theme.css_for(ui_theme.THEME_CSS, mode) + "</style>")
    st.html("<style>" + c1_theme.variables(mode) + C1_CSS + nav_icon_css(nav_keys) + "</style>")


def _clone_css(mode: str) -> str:
    return c1_theme.css_for(clone_stylesheet(), mode)


def sidebar_brand() -> None:
    st.markdown('<div class="dss-brand-row"><div class="dss-brand-mark">Rx</div><div>'
                '<div class="dss-sidebar-brand">CDH Inventory DSS</div><div class="dss-sidebar-product">'
                'Pharmaceutical decision<br>support</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="clone-sidebar-workspace">Hospital pharmacy workspace</div>', unsafe_allow_html=True)


def nav_group(label: str, small: bool = False) -> None:
    css = "dss-nav-group c1-panel" if small else "dss-nav-group"
    st.markdown(f'<div class="{css}">{html.escape(label)}</div>', unsafe_allow_html=True)


def nav_button(title: str, key: str, active: bool) -> bool:
    """One sidebar page button (app/main.py's sidebar_navigation_button); True when clicked."""
    return st.button(title, key=key, type="primary" if active else "secondary", width="stretch")


def topbar(title: str, badge: str | None, paths: list[str]) -> None:
    """The top bar: the page title, the stock badge ("Stock as of Sep 2026") and the light/dark toggle."""
    with st.container(key="c1-topbar", horizontal=True, vertical_alignment="center", gap="medium"):
        st.markdown(f'<p class="c1-topbar-title" role="heading" aria-level="1">{html.escape(title)}</p>',
                    unsafe_allow_html=True)
        if badge:
            st.markdown(f'<span class="c1-badge"><i></i>{html.escape(badge)}</span>', unsafe_allow_html=True)
        c1_theme.toggle(c1_theme.mode(), paths)


def page_header(eyebrow: str, title: str) -> None:
    st.markdown(f'<section class="dss-workspace-page-header"><div><div class="dss-workspace-eyebrow">'
                f'{html.escape(eyebrow)}</div><div class="dss-workspace-heading">{html.escape(title)}</div></div>'
                '</section>', unsafe_allow_html=True)


def footer() -> None:
    clone_footer()


def icon_svg(name: str, color: str | None = None, size: int = 20) -> str:
    stroke = color or c1_theme.token(ICON_TOKENS.get(name, "teal"), c1_theme.mode())
    return (f'<svg class="dss-svg-icon" width="{size}" height="{size}" viewBox="0 0 20 20" fill="none" '
            f'stroke="{stroke}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{SVG_ICONS.get(name, SVG_ICONS["info"])}</svg>')


def tile_html(label: str, value: object, icon: str = "info", caption: str | None = None) -> str:
    """One KPI tile (app/main.py's workspace_metric_card): icon, label, value as given, and an optional caption."""
    text = c1_format.count(value) if not isinstance(value, str) else value
    tone = ("teal c1-text" + (" c1-long" if len(text) > 24 else "")) if any(c.isalpha() for c in text) else ""
    note = f'<div class="c1-tile-caption">{html.escape(caption)}</div>' if caption else ""
    return (f'<section class="dss-workspace-metric"><div class="dss-workspace-metric-top">'
            f'<span class="dss-workspace-metric-icon">{icon_svg(icon)}</span></div>'
            f'<div class="dss-workspace-metric-label">{html.escape(label)}</div>'
            f'<div class="dss-workspace-metric-value {tone}">{html.escape(text)}</div>{note}</section>')


def tiles(name: str, items: list[tuple]) -> None:
    """A row of KPI tiles: (label, value), (label, value, icon) or (label, value, icon, caption)."""
    if not items:
        return
    with st.container(key=f"c1-metric-grid-{name}"):
        for column, item in zip(st.columns(len(items)), items):
            column.markdown(tile_html(*item), unsafe_allow_html=True)


@contextmanager
def card(name: str, title: str | None = None) -> Iterator[None]:
    """A white card (the look of app/ui_clone.py's clone_section, without the expander, so it can hold expanders)."""
    with st.container(key=f"c1-card-{name}"):
        if title:
            st.markdown(f'<div class="c1-card-title">{html.escape(title)}</div>', unsafe_allow_html=True)
        yield


@contextmanager
def collapsible(name: str, title: str, expanded: bool = False) -> Iterator[None]:
    """A collapsed card (app/ui_clone.py's clone_section, closed until opened)."""
    with st.container(key=f"clone-section-{name}"):
        with st.expander(title, expanded=expanded):
            yield


def question_card(name: str, question: str, answer: str, detail: str, button: str = "Show me",
                  attention: bool = False, name_answer: bool = False) -> bool:
    """A question card: the question, the answer up front, the detail (HTML) and a button; True when pressed."""
    tone = " attention" if attention else (" c1-name" if name_answer else "")
    with st.container(key=f"c1-question-{name}"):
        st.markdown(f'<p class="c1-question">{html.escape(question)}</p>'
                    f'<p class="c1-answer{tone}">{html.escape(answer)}</p>'
                    f'<p class="c1-answer-detail">{detail}</p>', unsafe_allow_html=True)
        return st.button(button, key=f"show-{name}", type="primary")


# ------------------------------------------------------------------ charts

def _axis(title: str | None = None, limit: int | None = None, angle: int | None = None,
          label_format: str | None = None) -> alt.Axis:
    options = {"title": title, "labelFontSize": 13, "titleFontSize": 13}
    if label_format:
        options["format"] = label_format
    if limit is not None:
        options["labelLimit"] = limit
    if angle is not None:
        options["labelAngle"] = angle
    return alt.Axis(**options)


def _styled(chart):
    """Axis and legend text in the mode's muted and ink colours (Streamlit's default grey is below 4.5:1 on the chart
    background), grid and axis lines in the line colour."""
    mode = c1_theme.mode()
    muted, ink, line = (c1_theme.token(name, mode) for name in ("muted", "ink", "line"))
    return (chart.configure_axis(labelColor=muted, titleColor=muted, gridColor=line, domainColor=line, tickColor=line)
            .configure_legend(labelColor=ink, titleColor=ink, labelFontSize=13))


def _long(data: pd.Series | pd.DataFrame, x: str) -> pd.DataFrame:
    frame = data.to_frame(data.name or "Value") if isinstance(data, pd.Series) else data
    frame = frame.reset_index()
    frame = frame.rename(columns={frame.columns[0]: x})
    return frame.melt(id_vars=x, var_name="Series", value_name="Value").dropna(subset=["Value"])


def line_chart(data: pd.Series | pd.DataFrame, x: str = "Month", y_title: str | None = None) -> None:
    """Lines over months, in the mode's palette, the legend below the chart."""
    if not len(data):
        return
    frame = _long(data, x)
    colors = c1_theme.palette(c1_theme.mode())
    series = list(dict.fromkeys(frame.Series))
    chart = alt.Chart(frame).mark_line(point=alt.OverlayMarkDef(size=18)).encode(
        x=alt.X(f"{x}:O", axis=_axis(None, angle=-45)),
        y=alt.Y("Value:Q", axis=_axis(y_title)),
        color=alt.Color("Series:N", scale=alt.Scale(domain=series, range=colors[:len(series)]),
                        legend=alt.Legend(orient="bottom", title=None, labelLimit=0, columns=2) if len(series) > 1
                        else None),
        tooltip=[x, "Series", alt.Tooltip("Value:Q", format=",.2f")])
    st.altair_chart(_styled(chart.properties(height=320)), width="stretch")


def bar_chart(data: pd.Series, horizontal: bool = False, value_title: str | None = None, order: list | None = None,
              value_format: str = ",.0f", axis_format: str | None = None) -> None:
    """Bars of one series: vertical by default; horizontal with the full category labels."""
    if not len(data):
        return
    category = data.index.name or "Category"
    frame = data.rename("Value").rename_axis(category).reset_index()
    frame[category] = frame[category].astype(str)
    color = c1_theme.token("teal", c1_theme.mode())
    sort = order if order is not None else None
    if horizontal:
        chart = alt.Chart(frame).mark_bar(color=color).encode(
            y=alt.Y(f"{category}:N", sort=sort, axis=_axis(None, limit=0)),
            x=alt.X("Value:Q", axis=_axis(value_title, label_format=axis_format)),
            tooltip=[category, alt.Tooltip("Value:Q", format=value_format)])
        # each value just past the end of its bar, outside it: right of a positive bar, left of a negative one
        ink = c1_theme.token("ink", c1_theme.mode())
        right = chart.mark_text(align="left", dx=4, fontSize=13, color=ink).encode(
            text=alt.Text("Value:Q", format=value_format)).transform_filter("datum.Value >= 0")
        left = chart.mark_text(align="right", dx=-4, fontSize=13, color=ink).encode(
            text=alt.Text("Value:Q", format=value_format)).transform_filter("datum.Value < 0")
        chart = (chart + right + left).properties(height=max(120, 42 * len(frame)))
    else:
        chart = alt.Chart(frame).mark_bar(color=color).encode(
            x=alt.X(f"{category}:N", sort=sort, axis=_axis(None, limit=0, angle=0)),
            y=alt.Y("Value:Q", axis=_axis(value_title, label_format=axis_format)),
            tooltip=[category, alt.Tooltip("Value:Q", format=value_format)]).properties(height=300)
    st.altair_chart(_styled(chart), width="stretch")


# ------------------------------------------------------------------ tables

def show_table(frame: pd.DataFrame, key: str | None = None, link: bool = False, row_height: int | None = None,
               hide: tuple[str, ...] = ("Medicine_Key",), height: int | None = None,
               widths: dict[str, int] | None = None) -> object:
    """A table with human labels and formatted values (c1_format.display). With link=True (and a key), clicking a
    medicine name returns that medicine's Medicine_Key. widths: {column: pixels} for long-text columns."""
    shown = [c for c in frame.columns if c not in hide]
    labels = [c1_format.label(c) for c in shown]
    options = {"hide_index": True, "column_order": list(dict.fromkeys(labels)), "width": "stretch",
               "placeholder": c1_format.NOT_AVAILABLE}
    if widths:
        options["column_config"] = {c1_format.label(c): st.column_config.Column(width=w) for c, w in widths.items()
                                    if c in frame}
    if row_height:
        options["row_height"] = row_height
    if height:
        options["height"] = height
    data = c1_format.display(frame)
    if not len(frame):
        st.dataframe(data, **options)
        return None
    if not (link and key and "Medicine_Key" in frame and "Brand_Name" in frame):
        st.dataframe(data, key=key, **options)
        return None
    event = st.dataframe(data, key=key, on_select="rerun", selection_mode="single-cell", **options)
    cells = getattr(getattr(event, "selection", None), "cells", None) or []
    for row, column in cells:
        if column == c1_format.label("Brand_Name") and 0 <= row < len(frame):
            return frame.Medicine_Key.iloc[row]
    return None


def first_rows_table(frame: pd.DataFrame, key: str, rows: int = 10) -> None:
    """A short sortable list in the clone-table style, with the display labels."""
    clone_table(frame.head(rows).reset_index(drop=True), key=key,
                labels={c: c1_format.label(c) for c in frame.columns}, page_size=rows)


def picker(label: str, options: list, key: str, **kwargs) -> object:
    """A medicine picker in the filter-bar panel."""
    with st.container(key=f"clone-medicine-filters-{key}"):
        return st.selectbox(label, options, key=key, **kwargs)


MATRIX_TONES = {"I": "strong", "II": "warm", "III": "light"}


def abc_ved_matrix(cells: pd.DataFrame) -> None:
    """The ABC-VED matrix in the existing clone-matrix styles: a row per ABC class, a column per VED class and the row
    total; each cell its medicines and its category (I teal, II amber, III light)."""
    def cell(count, category, tone):
        return (f'<div class="clone-matrix-cell {tone}"><strong>{count:,}</strong>'
                f'<span>{html.escape(category)}</span></div>')
    head = ('<div class="clone-matrix-row clone-matrix-head" role="row"><span></span><span>V (Vital)</span>'
            '<span>E (Essential)</span><span>D (Desirable)</span><span>All VED</span></div>')
    rows = []
    for abc in ("A", "B", "C"):
        part = cells[cells.ABC_Class.eq(abc)].set_index("VED")
        values = [cell(int(part.Medicines.get(v, 0)), f"Category {part.Category.get(v, '')}",
                       MATRIX_TONES.get(part.Category.get(v), "empty")) for v in ("V", "E", "D")]
        rows.append(f'<div class="clone-matrix-row" role="row"><span role="rowheader">Class {abc}</span>'
                    + "".join(values) + cell(int(part.Medicines.sum()), "", "empty") + "</div>")
    st.markdown(f'<div class="clone-matrix" role="table" aria-label="ABC-VED matrix">{head}{"".join(rows)}</div>',
                unsafe_allow_html=True)


def _options(frame: pd.DataFrame, column: str | None) -> list[str]:
    if not column or column not in frame:
        return [ALL]
    return [ALL] + sorted(frame[column].dropna().astype(str).unique())


def filter_bar(frame: pd.DataFrame, name: str, status: str | None = None) -> pd.DataFrame:
    """The filter bar above a medicine list: search, status, priority (ABC class) and dosage form, each "All" until
    chosen. A filter whose column the list does not have is shown disabled. Returns the rows that match."""
    with st.container(key=f"clone-medicine-filters-{name}"):
        search_col, status_col, priority_col, form_col = st.columns([2, 1.6, 1, 1.2])
        search = search_col.text_input("Search medicine", key=f"{name}-search", placeholder="Brand or generic name")
        choices = {}
        for column, label, field in ((status_col, "Status", status), (priority_col, "Priority", "ABC_Planning"),
                                     (form_col, "Dosage form", "Dosage_Form")):
            options = _options(frame, field)
            chosen = column.selectbox(label, options, key=f"{name}-{slug(label)}", disabled=len(options) == 1,
                                      format_func=lambda v: "(blank)" if v == "" else
                                      (v if v == ALL else str(c1_format.status_term(v))))
            if chosen != ALL:
                choices[field] = chosen
    view = frame
    for field, chosen in choices.items():
        view = view[view[field].astype(str).eq(chosen)]
    if search:
        names = [c for c in ("Brand_Name", "Generic_Name") if c in view]
        mask = pd.Series(False, index=view.index)
        for column in names:
            mask |= view[column].fillna("").astype(str).str.contains(search, case=False, regex=False)
        view = view[mask]
    st.markdown(f"**{len(view):,}** of {len(frame):,} rows shown. Filters change this table only.")
    return view
