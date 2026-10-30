"""Presentation helpers for the Capstone 1 pages (app/capstone1_app.py), built on the existing app's visual system.

The stylesheets are the existing ones, installed in the order app/main.py installs them: app/ui_main.css, app/ui_clone.css
(with the Inter fonts), app/ui_plan.css and ui_theme.THEME_CSS, each in the browser's light or dark mode (app/c1_theme.py).
The markup reuses their classes: the sidebar brand, group label and page buttons, the page header, the KPI tiles
(dss-workspace-metric), the white cards, the filter bar (clone-medicine-filters) and the matrix. C1_CSS adds the top bar
(the stock badge and the mode toggle), the question cards, the sidebar's group label and the page-button icons, on the
colour tokens of c1_theme. The sidebar keeps Streamlit's own width, drag handle and collapse control: the shared
stylesheets' fixed sidebar width is left out here (_main_css, _clone_css). Tables go through c1_format (labels and
formats); charts are Altair charts in the mode's colours, months on a time axis ("Jan 2021"). Markup only: no data or
analytical logic.
"""

from __future__ import annotations

import html
import json
import math
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
from ui_clone import _stylesheet as clone_stylesheet
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
    "stop": '<circle cx="10" cy="10" r="7"/><path d="m7 7 6 6M13 7l-6 6"/>',
    "info": '<circle cx="10" cy="10" r="7"/><path d="M10 9v5M10 6h.01"/>',
}
# Status icons take the status colour; the others the teal of the existing tiles.
ICON_TOKENS = {"check": "teal", "warning": "amber", "cross": "red", "attention": "amber", "stop": "muted"}

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
/* one spacing scale on every page: 24px between sections, 16px between tiles both ways, 16px from a section heading to
   its content, 12px from tiles to the text below, 20px card padding; every tile row is one grid (tiles()), so the
   tiles of a row share one height */
.stApp .stMainBlockContainer > [data-testid="stVerticalBlock"]{gap:24px}
/* Streamlit pulls every markdown block up by 16px to absorb a paragraph's margin; the blocks drawn here hold no
   paragraph, so they keep their place and the scale holds */
.stApp [data-testid="stMarkdownContainer"]:has(> :is(.c1-tiles,.c1-chip-row,.c1-card-title,.c1-legend,.dss-workspace-page-header,.clone-matrix,.c1-nav-divider)){margin-bottom:0}
.c1-tiles{display:grid;grid-template-columns:repeat(var(--c1-cols),minmax(0,1fr));gap:16px;margin:0 0 -4px}
.c1-tiles .dss-workspace-metric{height:100%;min-height:0;margin:0;box-sizing:border-box;padding:18px 20px}
.dss-workspace-metric-value.c1-text{white-space:normal;overflow-wrap:anywhere;font-size:20px;line-height:1.25}
.dss-workspace-metric-value.c1-long{font-size:17px}
.dss-workspace-metric-value.c1-red{color:var(--c1-red)}
.dss-workspace-metric-value.c1-amber{color:var(--c1-amber)}
.c1-tile-caption{font:400 14px/1.4 Inter,sans-serif;color:var(--c1-muted);margin-top:6px}
[class*="st-key-c1-card-"]{background:var(--c1-surface);border:1px solid var(--c1-line);border-radius:20px;box-shadow:0 3px 14px #14264a08;padding:20px;box-sizing:border-box}
[class*="st-key-c1-card-"] > [data-testid="stVerticalBlock"]{gap:16px}
.c1-card-title{font:600 22px/1.3 Inter,sans-serif;color:var(--c1-ink);letter-spacing:-.4px;border-bottom:1px solid var(--c1-line);margin:-4px -20px 0;padding:0 20px 16px}
@media(min-width:901px){:is([class*="st-key-c1-"],[class*="st-key-clone-medicine-filters-"],[class*="st-key-clone-section-"]) [data-testid="stHorizontalBlock"]{flex-wrap:nowrap}}
@media(max-width:1200px){.c1-tiles{grid-template-columns:repeat(min(var(--c1-cols),2),minmax(0,1fr))}}
@media(max-width:600px){.c1-tiles{grid-template-columns:minmax(0,1fr)}[class*="st-key-c1-card-"]{padding:16px}.c1-card-title{font-size:20px;margin:-4px -16px 0;padding:0 16px 16px}}
/* the two labels: small neutral grey chips, no icon, the meaning in the tooltip */
.c1-chip{display:inline-block;font:500 12px/1.5 Inter,sans-serif;color:var(--c1-muted);background:var(--c1-canvas);border:1px solid var(--c1-line);border-radius:999px;padding:1px 10px;cursor:help;white-space:nowrap}
.c1-chip-row{display:flex;gap:8px;flex-wrap:wrap;margin:0}
/* a definition: "?" with the sentence as its tooltip */
.c1-help{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border:1px solid var(--c1-line);border-radius:50%;font:600 11px/1 Inter,sans-serif;color:var(--c1-muted);margin-left:6px;cursor:help;vertical-align:middle}
/* the header card: the title and one line */
.stApp .dss-workspace-page-header{height:auto!important;min-height:0!important;padding:26px 30px!important;margin:0!important}
.stApp .dss-workspace-page-header .dss-workspace-heading{margin:0}
.stApp .dss-workspace-page-header .dss-workspace-subtitle{margin-top:8px;font-size:18px;color:var(--c1-text)}
/* the 100% stacked bar's legend */
.c1-legend{display:flex;flex-wrap:wrap;gap:8px 20px;font:400 14px/1.4 Inter,sans-serif;color:var(--c1-text);margin:0}
.c1-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:baseline}
.c1-legend strong{color:var(--c1-ink)}
/* the top bar: the stock badge and the mode toggle, on the right. It spans the window under the sidebar (which is
   drawn above it), so it follows any sidebar width, collapsed or dragged, without moving */
.st-key-c1-topbar{position:fixed;z-index:990;left:0;right:0;top:0;width:auto!important;height:64px;background:var(--c1-surface);border-bottom:1px solid var(--c1-line);padding:0 32px;box-sizing:border-box;flex-wrap:nowrap!important;align-items:center;justify-content:flex-end;gap:16px}
.st-key-c1-topbar > div{flex:0 0 auto!important;width:auto!important;min-width:0}
.stApp .stMainBlockContainer.block-container{padding-top:88px}
/* Streamlit's own header is a transparent strip above the top bar: clicks pass through it to the toggle, except on
   its sidebar button */
.stApp [data-testid="stHeader"]{pointer-events:none}
.stApp [data-testid="stHeader"] [data-testid="stExpandSidebarButton"],
.stApp [data-testid="stHeader"] [data-testid="stExpandSidebarButton"] *{pointer-events:auto}
.c1-badge{display:inline-flex;align-items:center;gap:9px;white-space:nowrap;font:500 15px/1 Inter,sans-serif;color:var(--c1-ink);background:var(--c1-teal-soft);border:1px solid var(--c1-line);border-radius:999px;padding:9px 14px}
.c1-badge i{width:8px;height:8px;background:var(--c1-teal);border-radius:50%}
@media(max-width:900px){.st-key-c1-topbar{padding:0 12px 0 64px;gap:8px}}
@media(max-width:600px){.c1-badge{font-size:12px;padding:6px 9px}}
/* question cards: one height per row, the button at the bottom */
[class*="st-key-c1-question-"]{background:var(--c1-surface);border:1px solid var(--c1-line);border-radius:18px;padding:20px;box-sizing:border-box;height:100%}
[class*="st-key-c1-questions-"] [data-testid="stHorizontalBlock"]{gap:16px;align-items:stretch}
[class*="st-key-c1-questions-"] [data-testid="stColumn"] > [data-testid="stVerticalBlock"]{height:100%}
[class*="st-key-c1-questions-"] [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > *{flex:1 1 auto}
[class*="st-key-c1-question-"] > [data-testid="stVerticalBlock"]{height:100%}
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
/* the matrix fits its card: the row header and four equal columns share the width, All VED included */
.stApp .clone-matrix-row{grid-template-columns:96px repeat(4,minmax(0,1fr));gap:8px;min-width:0}
.stApp .clone-matrix-cell{min-height:88px}
.stApp .clone-matrix-cell strong{font-size:26px}
.stApp .clone-matrix-head{font-size:15px}
.stApp .clone-matrix-cell.warm, .stApp .clone-matrix-cell.warm strong, .stApp .clone-matrix-cell.warm span{color:var(--c1-on-amber)}
/* the sidebar: the page buttons 8px apart, a thin divider before Analysis */
.stApp [data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:8px}
.stApp .c1-nav-divider{border-top:1px solid var(--c1-line);margin:8px 18px}
/* the sidebar: Streamlit's own width (it opens at SIDEBAR_WIDTH, st.set_page_config), drag handle and collapse
   control, above the top bar. Expanded, it keeps a floor (SIDEBAR_MIN, install_styles) so no label breaks; collapsed,
   it takes no room and the page widens. The reopen button sits in Streamlit's toolbar, which the shared stylesheets
   hide: it alone is shown */
[data-testid="stSidebar"][aria-expanded="false"]{border-right-width:0}
.stApp [data-testid="stToolbar"]:has([data-testid="stExpandSidebarButton"]){display:flex!important;width:0!important;height:0!important;overflow:visible!important}
.stApp [data-testid="stToolbar"] *:not(:has([data-testid="stExpandSidebarButton"])):not([data-testid="stExpandSidebarButton"]):not([data-testid="stExpandSidebarButton"] *){display:none!important}
.stApp [data-testid="stExpandSidebarButton"]{display:flex!important;position:fixed!important;top:11px;left:12px;width:42px!important;height:42px!important;align-items:center;justify-content:center;background:var(--c1-surface)!important;border:1px solid var(--c1-line)!important;border-radius:9px!important;pointer-events:auto!important;z-index:1002!important}
/* a static table (every row, long text wrapped): the mode's text and line colours */
.stApp [data-testid="stTable"] :is(th,td){color:var(--c1-text);border-color:var(--c1-line);vertical-align:top}
.stApp [data-testid="stTable"] th{color:var(--c1-ink)}
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
    st.html("<style>" + _main_css(mode) + "</style>")
    st.html("<style>" + _clone_css(mode) + "</style>")
    st.html("<style>" + c1_theme.stylesheet("ui_plan.css", mode) + "</style>")
    st.html("<style>" + c1_theme.css_for(ui_theme.THEME_CSS, mode) + "</style>")
    st.html("<style>" + c1_theme.variables(mode) + C1_CSS + nav_icon_css(nav_keys)
            + f'[data-testid="stSidebar"][aria-expanded="true"]{{min-width:min({SIDEBAR_MIN}px,90vw)!important}}'
            + "</style>")


# The shared stylesheets' rules that fix the sidebar's width (348px in app/ui_clone.css, 350px in app/ui_main.css) or
# squeeze its header: with them Streamlit cannot resize the sidebar, and a collapsed one stays partly on screen (it
# slides by its own width, 300px, while the rule holds it at 348px). This app leaves them out; app/main.py keeps them.
MAIN_SIDEBAR_RULES = ("    min-width: 21.875rem !important;\n", "    width: 21.875rem !important;\n",
                      "    min-width: 21.875rem;\n",
                      '    [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child '
                      "{ min-width: 0 !important; width: auto !important; }\n")
CLONE_SIDEBAR_RULES = ("width:348px!important;min-width:348px!important;max-width:348px!important;",
                       '[data-testid="stSidebarHeader"]{height:20px;min-height:20px;padding:0 12px}\n',
                       '[data-testid="stSidebar"]{min-width:310px!important;max-width:310px!important;width:310px!important}')
# The opening width and the floor: the brand line ("CDH Inventory DSS", 20px) needs 349px to stay on one line, so the
# sidebar opens at 360px and can be dragged wider, not narrower (on a phone, at most 90% of the screen).
SIDEBAR_WIDTH = SIDEBAR_MIN = 360


def _without(css: str, rules: tuple[str, ...]) -> str:
    for rule in rules:
        if css.count(rule) != 1:
            raise ValueError(f"sidebar rule not found once in a shared stylesheet: {rule!r}")
        css = css.replace(rule, "")
    return css


def _main_css(mode: str) -> str:
    return c1_theme.css_for(_without((APP_DIR / "ui_main.css").read_text(encoding="utf-8"), MAIN_SIDEBAR_RULES), mode)


def _clone_css(mode: str) -> str:
    return c1_theme.css_for(_without(clone_stylesheet(), CLONE_SIDEBAR_RULES), mode)


def sidebar_brand() -> None:
    st.markdown('<div class="dss-brand-row"><div class="dss-brand-mark">Rx</div><div>'
                '<div class="dss-sidebar-brand">CDH Inventory DSS</div><div class="dss-sidebar-product">'
                'Pharmaceutical decision<br>support</div></div></div>', unsafe_allow_html=True)


def nav_divider() -> None:
    """The thin line before the Analysis page button."""
    st.markdown('<div class="c1-nav-divider" role="separator"></div>', unsafe_allow_html=True)


def nav_button(title: str, key: str, active: bool) -> bool:
    """One sidebar page button (app/main.py's sidebar_navigation_button); True when clicked."""
    return st.button(title, key=key, type="primary" if active else "secondary", width="stretch")


def topbar(badge: str | None, paths: list[str]) -> None:
    """The top bar: the stock badge ("Stock as of Sep 2026") and the light/dark toggle; the page title is in the
    header card."""
    with st.container(key="c1-topbar", horizontal=True, vertical_alignment="center", gap="medium"):
        if badge:
            st.markdown(f'<span class="c1-badge"><i></i>{html.escape(badge)}</span>', unsafe_allow_html=True)
        c1_theme.toggle(c1_theme.mode(), paths)


def page_header(title: str, line: str) -> None:
    """The header card: the page title and one line saying what the page is for."""
    st.markdown(f'<section class="dss-workspace-page-header"><div><div role="heading" aria-level="1" '
                f'class="dss-workspace-heading">{html.escape(title)}</div>'
                f'<div class="dss-workspace-subtitle">{html.escape(line)}</div></div></section>', unsafe_allow_html=True)


def help_icon(text: str) -> str:
    """A "?" whose tooltip is the definition."""
    return f'<span class="c1-help" title="{html.escape(text)}" aria-label="{html.escape(text)}">?</span>'


def chip_html(label: str, tooltip: str) -> str:
    return f'<span class="c1-chip" title="{html.escape(tooltip)}">{html.escape(label)}</span>'


def chips(*items: tuple[str, str]) -> None:
    """Small neutral chips (the planning-estimate labels) above a table or tile group."""
    if items:
        st.markdown('<div class="c1-chip-row">' + "".join(chip_html(*i) for i in items) + "</div>",
                    unsafe_allow_html=True)


def icon_svg(name: str, color: str | None = None, size: int = 20) -> str:
    stroke = color or c1_theme.token(ICON_TOKENS.get(name, "teal"), c1_theme.mode())
    return (f'<svg class="dss-svg-icon" width="{size}" height="{size}" viewBox="0 0 20 20" fill="none" '
            f'stroke="{stroke}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{SVG_ICONS.get(name, SVG_ICONS["info"])}</svg>')


def tile_html(label: str, value: object, icon: str = "info", caption: str | None = None, help: str | None = None,
              tone: str | None = None) -> str:
    """One KPI tile (app/main.py's workspace_metric_card): icon, label (with a "?" definition), value as given, an
    optional caption; tone "red" (act now) or "amber" (check) colours the value."""
    text = c1_format.count(value) if not isinstance(value, str) else value
    kind = ("teal c1-text" + (" c1-long" if len(text) > 24 else "")) if any(c.isalpha() for c in text) else ""
    kind += f" c1-{tone}" if tone in ("red", "amber") else ""
    note = f'<div class="c1-tile-caption">{html.escape(caption)}</div>' if caption else ""
    tip = help_icon(help) if help else ""
    return (f'<section class="dss-workspace-metric"><div class="dss-workspace-metric-top">'
            f'<span class="dss-workspace-metric-icon">{icon_svg(icon)}</span></div>'
            f'<div class="dss-workspace-metric-label">{html.escape(label)}{tip}</div>'
            f'<div class="dss-workspace-metric-value {kind}">{html.escape(text)}</div>{note}</section>')


def tiles(name: str, items: list[tuple], columns: int | None = None) -> None:
    """Every tile row of the pages: one grid, so the tiles of a row share one height and sit 16px apart both ways.
    Items: (label, value[, icon[, caption[, help[, tone]]]]); columns: per row (default all, at most 4)."""
    if not items:
        return
    cols = columns or min(len(items), 4)
    with st.container(key=f"c1-metric-grid-{name}"):
        st.markdown(f'<div class="c1-tiles" style="--c1-cols:{cols}">' + "".join(tile_html(*i) for i in items)
                    + "</div>", unsafe_allow_html=True)


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
    """A question card: the question, the answer up front, the detail (HTML) and a button; True when pressed. Red
    (attention) only where something must be acted on now."""
    tone = " attention" if attention else (" c1-name" if name_answer else "")
    with st.container(key=f"c1-question-{name}"):
        st.markdown(f'<p class="c1-question">{html.escape(question)}</p>'
                    f'<p class="c1-answer{tone}">{html.escape(answer)}</p>'
                    f'<p class="c1-answer-detail">{detail}</p>', unsafe_allow_html=True)
        return st.button(button, key=f"show-{name}", type="primary")


def question_row(name: str, count: int) -> list:
    """A row of question cards, side by side at one height (a second row of two spans the full width)."""
    with st.container(key=f"c1-questions-{name}"):
        return list(st.columns(count, gap=None))


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


MONTH_FORMAT = "%b %Y"                      # "Jan 2021", as c1_format.month


def _months(values: pd.Series) -> pd.Series | None:
    """Month labels ("2021-01", a month-end date) as the first day of each month, for a time axis; None when a value is
    not a month."""
    try:
        return pd.PeriodIndex(values.astype(str).str[:7], freq="M").to_timestamp().to_series(index=values.index)
    except (ValueError, TypeError):
        return None


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
    months = _months(frame[x])
    if months is not None:                     # a time axis: "Jan 2021", a label every few months
        frame[x] = months
        axis_x = alt.X(f"{x}:T", axis=_axis(None, angle=0, label_format=MONTH_FORMAT))
        tip_x = alt.Tooltip(f"{x}:T", format=MONTH_FORMAT)
    else:
        axis_x, tip_x = alt.X(f"{x}:O", axis=_axis(None, angle=-45)), x
    chart = alt.Chart(frame).mark_line(point=alt.OverlayMarkDef(size=18)).encode(
        x=axis_x,
        y=alt.Y("Value:Q", axis=_axis(y_title)),
        color=alt.Color("Series:N", scale=alt.Scale(domain=series, range=colors[:len(series)]),
                        legend=alt.Legend(orient="bottom", title=None, labelLimit=0, columns=2) if len(series) > 1
                        else None),
        tooltip=[tip_x, "Series", alt.Tooltip("Value:Q", format=",.2f")])
    st.altair_chart(_styled(chart.properties(height=320)), width="stretch")


def bar_chart(data: pd.Series, horizontal: bool = False, value_title: str | None = None, order: list | None = None,
              value_format: str = ",.0f", axis_format: str | None = None) -> None:
    """Bars of one series: vertical by default; horizontal with the full category labels."""
    if not len(data):
        return
    category = data.index.name or "Category"
    frame = data.rename("Value").rename_axis(category).reset_index()
    months = _months(frame[category]) if category == "Month" and not horizontal else None
    if months is not None:                     # bars over months: a time axis, "Jan 2021"
        frame[category] = months
        chart = alt.Chart(frame).mark_bar(color=c1_theme.token("teal", c1_theme.mode())).encode(
            x=alt.X(f"yearmonth({category}):T", axis=_axis(None, angle=0, label_format=MONTH_FORMAT)),
            y=alt.Y("Value:Q", axis=_axis(value_title, label_format=axis_format)),
            tooltip=[alt.Tooltip(f"yearmonth({category}):T", title=category, format=MONTH_FORMAT),
                     alt.Tooltip("Value:Q", format=value_format)]).properties(height=300)
        st.altair_chart(_styled(chart), width="stretch")
        return
    frame[category] = frame[category].astype(str)
    color = c1_theme.token("teal", c1_theme.mode())
    sort = order if order is not None else None
    if horizontal:
        # room past the longest bar for its value label, on each side that has bars
        low, high = min(0.0, float(frame.Value.min())), max(0.0, float(frame.Value.max()))
        room = (high - low) * 0.1 or 1.0
        domain = [low - room if low < 0 else 0.0, high + room if high > 0 else (0.0 if low < 0 else room)]
        chart = alt.Chart(frame).mark_bar(color=color).encode(
            y=alt.Y(f"{category}:N", sort=sort, axis=_axis(None, limit=0)),
            x=alt.X("Value:Q", axis=_axis(value_title, label_format=axis_format), scale=alt.Scale(domain=domain)),
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


def stacked_share_bar(counts: pd.Series, colors: dict[str, str]) -> None:
    """One 100% stacked horizontal bar of the medicines by category (counts in order), its legend below with each
    count; the legend sums to the total."""
    counts = counts[counts > 0]
    total = int(counts.sum())
    if not total:
        return
    mode = c1_theme.mode()
    frame = pd.DataFrame({"Action": counts.index, "Medicines": counts.to_numpy(),
                          "Order": range(len(counts))})
    frame["Share"] = frame.Medicines / total
    palette = [c1_theme.token(colors.get(a, "muted"), mode) for a in frame.Action]
    chart = alt.Chart(frame).mark_bar(height=36).encode(
        x=alt.X("Share:Q", stack="normalize", axis=None),
        color=alt.Color("Action:N", scale=alt.Scale(domain=list(frame.Action), range=palette), legend=None),
        order=alt.Order("Order:Q"),
        tooltip=["Action", alt.Tooltip("Medicines:Q", format=",.0f"), alt.Tooltip("Share:Q", format=".0%")]
    ).properties(height=44)
    st.altair_chart(_styled(chart), width="stretch")
    items = "".join(f'<span><i style="background:{c}"></i>{html.escape(a)} <strong>{n:,}</strong></span>'
                    for a, n, c in zip(frame.Action, frame.Medicines, palette))
    st.markdown(f'<div class="c1-legend">{items}<span>Total <strong>{total:,}</strong></span></div>',
                unsafe_allow_html=True)


def range_chart(frame: pd.DataFrame, value_title: str) -> None:
    """A tornado chart: one bar per factor from its lowest to its highest value (Factor, Low, High), the widest first,
    each end labelled."""
    if not len(frame):
        return
    mode = c1_theme.mode()
    data = frame.assign(Span=frame.High - frame.Low).sort_values("Span", ascending=False)
    order = data.Factor.tolist()
    low, high = min(0.0, float(data.Low.min())), max(0.0, float(data.High.max()))
    room = (high - low) * 0.12 or 1.0
    base = alt.Chart(data).encode(y=alt.Y("Factor:N", sort=order, axis=_axis(None, limit=0)))
    bars = base.mark_bar(color=c1_theme.token("teal", mode), height=22).encode(
        x=alt.X("Low:Q", axis=_axis(value_title), scale=alt.Scale(domain=[low - room, high + room])), x2="High:Q",
        tooltip=["Factor", alt.Tooltip("Low:Q", format=",.1f"), alt.Tooltip("High:Q", format=",.1f")])
    ink = c1_theme.token("ink", mode)
    left = base.mark_text(align="right", dx=-4, fontSize=13, color=ink).encode(
        x="Low:Q", text=alt.Text("Low:Q", format="+,.1f"))
    right = base.mark_text(align="left", dx=4, fontSize=13, color=ink).encode(
        x="High:Q", text=alt.Text("High:Q", format="+,.1f"))
    zero = alt.Chart(pd.DataFrame({"x": [0.0]})).mark_rule(color=c1_theme.token("muted", mode)).encode(x="x:Q")
    st.altair_chart(_styled((bars + left + right + zero).properties(height=max(120, 44 * len(data)))), width="stretch")


# ------------------------------------------------------------------ tables

# The grids' font (Inter at 14px; headers at weight 600): each character's width in pixels, as Chrome measures it. Each
# column is sized from all its text, not from glide's first 10 rows, so no cell or header is cut off.
_GRID_FONT = json.loads((Path(__file__).resolve().parent / "c1_grid_font.json").read_text(encoding="utf-8"))
GRID_NORMAL, GRID_BOLD = _GRID_FONT["normal"], _GRID_FONT["bold"]
GRID_PADDING = 22          # glide's 8px on each side, and a margin
GRID_MAX = 560             # a column with wider text wraps it (the longest medicine name fits)
GRID_WRAP_ROW = 72         # the row height that wraps text (Streamlit wraps above 4rem)
GRID_LINES = 2             # the lines a wrapped row shows in full


def text_width(text: str, bold: bool = False) -> float:
    table = GRID_BOLD if bold else GRID_NORMAL
    return sum(table.get(c, 10.0) for c in text)


def wrapped_lines(text: str, width: float) -> float:
    """The lines a text takes, wrapped at spaces in the width (infinite when one word is wider)."""
    lines, used, space = 1, 0.0, GRID_NORMAL[" "]
    for word in text.split(" "):
        size = text_width(word)
        if size > width:
            return math.inf
        if used and used + space + size > width:
            lines, used = lines + 1, size
        else:
            used += (space if used else 0) + size
    return lines


def fit_widths(texts: pd.DataFrame, widths: dict[str, int]) -> tuple[dict[str, int], bool]:
    """Each column's width in pixels (at least the one asked, and the header's) so that every text shows whole: on one
    line, or, past GRID_MAX, wrapped in GRID_LINES lines; and whether the rows must wrap."""
    out, wrap = {}, False
    for column in texts.columns:
        values = {v for v in texts[column] if v}
        longest = max((text_width(v) for v in values), default=0.0) + GRID_PADDING
        width = max(widths.get(column) or min(longest, GRID_MAX), text_width(str(column), bold=True) + GRID_PADDING)
        if longest > width:
            wrap = True
            long = [v for v in values if text_width(v) + GRID_PADDING > width]
            while any(wrapped_lines(v, width - GRID_PADDING) > GRID_LINES for v in long):
                width += 8
        out[column] = math.ceil(width)
    return out, wrap


def show_table(frame: pd.DataFrame, key: str | None = None, link: bool = False, row_height: int | None = None,
               hide: tuple[str, ...] = ("Medicine_Key",), height: int | None = None,
               widths: dict[str, int] | None = None) -> object:
    """A table with human labels and formatted values (c1_format.display). With link=True (and a key), clicking a
    medicine name returns that medicine's Medicine_Key. widths: {column: pixels} for long-text columns."""
    shown = [c for c in frame.columns if c not in hide]
    labels = [c1_format.label(c) for c in shown]
    options = {"hide_index": True, "column_order": list(dict.fromkeys(labels)), "width": "stretch",
               "placeholder": c1_format.NOT_AVAILABLE}
    asked = {c1_format.label(c): w for c, w in (widths or {}).items() if c in frame}
    fitted, wrap = fit_widths(c1_format.texts(frame[shown]), asked)
    options["column_config"] = {c: st.column_config.Column(width=w) for c, w in fitted.items()}
    if wrap:
        row_height = max(row_height or 0, GRID_WRAP_ROW)
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


def static_table(frame: pd.DataFrame, hide: tuple[str, ...] = ("Medicine_Key",)) -> None:
    """A short table drawn in full (st.table): every row, long text wrapped, the height of its content; the display
    labels and formats of c1_format."""
    shown = frame[[c for c in frame.columns if c not in hide]]
    st.table(c1_format.display(shown).hide(axis="index"), hide_index=True)


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
    """The ABC-VED matrix in the existing clone-matrix styles: a row per ABC class, a column per VED class, the row
    totals and a totals row; each cell its medicines and its category (I teal, II amber, III light)."""
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
    totals = [cell(int(cells[cells.VED.eq(v)].Medicines.sum()), "", "empty") for v in ("V", "E", "D")]
    rows.append('<div class="clone-matrix-row" role="row"><span role="rowheader">All ABC</span>' + "".join(totals)
                + cell(int(cells.Medicines.sum()), "", "empty") + "</div>")
    st.markdown(f'<div class="clone-matrix" role="table" aria-label="ABC-VED matrix">{head}{"".join(rows)}</div>',
                unsafe_allow_html=True)


def _options(frame: pd.DataFrame, column: str | None) -> list[str]:
    if not column or column not in frame:
        return [ALL]
    return [ALL] + sorted(frame[column].dropna().astype(str).unique())


def filter_bar(frame: pd.DataFrame, name: str, status: str | None = None, noun: str = "medicines") -> pd.DataFrame:
    """The filter bar above a medicine list: search, priority (ABC class), dosage form and, where asked, status, each
    "All" until chosen; then the count ("160 medicines", or "12 of 160 medicines" once filtered). A filter whose column
    the list does not have is shown disabled. Returns the rows that match."""
    with st.container(key=f"clone-medicine-filters-{name}"):
        if status:
            search_col, status_col, priority_col, form_col = st.columns([2, 1.6, 1, 1.2])
        else:
            (search_col, priority_col, form_col), status_col = st.columns([2, 1, 1.2]), None
        search = search_col.text_input("Search medicine", key=f"{name}-search", placeholder="Brand or generic name")
        choices = {}
        for column, label, field in ((status_col, "Status", status), (priority_col, "Priority", "ABC_Planning"),
                                     (form_col, "Dosage form", "Dosage_Form")):
            if column is None:
                continue
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
    shown = f"**{len(view):,}** {noun}" if len(view) == len(frame) else f"**{len(view):,}** of {len(frame):,} {noun}"
    st.markdown(shown)
    return view
