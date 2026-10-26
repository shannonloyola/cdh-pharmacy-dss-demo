"""Presentation helpers for the Capstone 1 pages (app/capstone1_app.py), built on the existing app's visual system.

The stylesheets are the existing ones, installed in the order app/main.py installs them: app/ui_main.css, app/ui_clone.css
(with the Inter fonts), app/ui_plan.css and ui_theme.THEME_CSS. The markup reuses their classes: the sidebar brand,
group label and page buttons, the top bar, the page header, the KPI tiles (dss-workspace-metric), the white cards, the
filter bar (clone-medicine-filters), the light tables (ui_theme.show_table) and the sortable clone tables
(ui_clone_table). C1_CSS only repeats existing rules for keys that occur more than once on a page (several cards, tile
grids and filter bars) and adds the page-button icons. Markup only: no data or analytical logic.
"""

from __future__ import annotations

import html
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

import ui_theme
from ui_clone import clone_footer, install_clone_style
from ui_clone_table import clone_table

APP_DIR = Path(__file__).resolve().parent
ALL = "All"

# Tile icons: the paths of app/main.py's SVG_ICONS.
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
    "info": '<circle cx="10" cy="10" r="7"/><path d="M10 9v5M10 6h.01"/>',
}

# Page-button icons: the paths of app/ui_clone.py's sidebar icons.
NAV_ICONS = {
    "overview": '<rect x="2" y="2" width="6" height="6" rx="1"/><rect x="12" y="2" width="6" height="6" rx="1"/><rect x="2" y="12" width="6" height="6" rx="1"/><rect x="12" y="12" width="6" height="6" rx="1"/>',
    "cart": '<path d="M2 4h2l2.2 10h9.6l2-7H5"/><circle cx="8" cy="17" r="1"/><circle cx="15" cy="17" r="1"/>',
    "calendar": '<rect x="2.5" y="4" width="15" height="14" rx="2"/><path d="M6 2v4m8-4v4M3 8h14M6 12h8M6 15h5"/>',
    "medicine": '<path d="M7 2.5l9 5v9l-9 5-9-5v-9z" transform="translate(3 -2) scale(.85)"/>',
    "shield": '<path d="M10 2l7 3v5c0 4-3 6-7 8-4-2-7-4-7-8V5z"/><path d="M7 10l2 2 4-4"/>',
    "book": '<path d="M3 3h6c1.5 0 2.5.5 3 1.5C12.5 3.5 13.5 3 15 3h3v14h-3c-1.5 0-2.5.5-3 1.5C11.5 17.5 10.5 17 9 17H3zM12 4.5v14"/>',
}

# Existing rules from app/ui_clone.css, repeated for keys used more than once per page.
C1_CSS = """
[class*="st-key-clone-medicine-filters-"]{background:#f7f9fa;border:1px solid #e3e8eb;border-radius:12px;padding:14px 18px}
[class*="st-key-clone-medicine-filters-"] [data-testid="stVerticalBlock"]{gap:0}
[class*="st-key-c1-metric-grid-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{flex:1 1 0%!important;min-width:0!important}
[class*="st-key-c1-metric-grid-"] .dss-workspace-metric{min-height:190px}
.dss-workspace-metric-value.c1-text{white-space:normal}
[class*="st-key-c1-card-"]{background:#fff;border:1px solid #e3e8eb;border-radius:20px;box-shadow:0 3px 14px #14264a03;padding:30px;box-sizing:border-box}
[class*="st-key-c1-card-"] > [data-testid="stVerticalBlock"]{gap:24px}
.c1-card-title{font:600 28px/1.3 Inter,sans-serif;color:#14264a;letter-spacing:-.7px;border-bottom:1px solid #e3e8eb;margin:-8px -30px 0;padding:0 30px 22px}
@media(min-width:901px){:is([class*="st-key-c1-"],[class*="st-key-clone-medicine-filters-"],[class*="st-key-clone-section-"]) [data-testid="stHorizontalBlock"]{flex-wrap:nowrap}}
@media(max-width:1200px){[class*="st-key-c1-metric-grid-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{flex:1 1 calc(50% - 22px)!important}}
@media(max-width:600px){[class*="st-key-c1-metric-grid-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{flex:1 1 100%!important}[class*="st-key-c1-card-"]{padding:16px}.c1-card-title{font-size:23px;margin:-4px -16px 0;padding:0 16px 16px}}
"""


def slug(text: str) -> str:
    return text.lower().replace("&", "and").replace(" ", "-")


def nav_icon_css(keys: dict[str, str]) -> str:
    """The icon of each page button, as app/ui_clone.py draws them: {button key: NAV_ICONS name}."""
    rules = []
    for key, name in keys.items():
        svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20' fill='none' stroke='black' "
               "stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'>" + NAV_ICONS[name] + "</svg>")
        rules.append(f'.st-key-{key} button::before' + '{--nav-icon:url("data:image/svg+xml,' + quote(svg, safe="") + '")}')
    return "\n".join(rules)


def install_styles(nav_keys: dict[str, str]) -> None:
    """The existing stylesheets, in app/main.py's order, then C1_CSS and the page-button icons."""
    st.html("<style>" + (APP_DIR / "ui_main.css").read_text(encoding="utf-8") + "</style>")
    install_clone_style()
    st.html("<style>" + (APP_DIR / "ui_plan.css").read_text(encoding="utf-8") + "</style>")
    ui_theme.install_theme_css()
    st.html("<style>" + C1_CSS + nav_icon_css(nav_keys) + "</style>")


def sidebar_brand() -> None:
    st.markdown('<div class="dss-brand-row"><div class="dss-brand-mark">Rx</div><div>'
                '<div class="dss-sidebar-brand">CDH Inventory DSS</div><div class="dss-sidebar-product">'
                'Pharmaceutical decision<br>support</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="clone-sidebar-workspace">Hospital pharmacy workspace</div>', unsafe_allow_html=True)


def nav_group(label: str) -> None:
    st.markdown(f'<div class="dss-nav-group">{html.escape(label)}</div>', unsafe_allow_html=True)


def nav_button(title: str, key: str, active: bool) -> bool:
    """One sidebar page button (app/main.py's sidebar_navigation_button); True when clicked."""
    return st.button(title, key=key, type="primary" if active else "secondary", width="stretch")


def topbar(page: str, status: str | None) -> None:
    """The existing top bar (app/ui_clone.py's clone_topbar): breadcrumb and data status."""
    state = f'<span class="clone-data-status"><i></i>{html.escape(status)}</span>' if status else ""
    st.markdown(
        '<header id="planning-workspace" class="clone-topbar"><div class="clone-breadcrumb">'
        '<span class="clone-grid-icon" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 20 20" fill="none" '
        'stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="6" height="6" rx="1"/><rect x="12" y="2" '
        'width="6" height="6" rx="1"/><rect x="2" y="12" width="6" height="6" rx="1"/><rect x="12" y="12" width="6" '
        'height="6" rx="1"/></svg></span><span>Workspace</span><span aria-hidden="true">›</span>'
        f'<strong>{html.escape(page)}</strong></div><div class="clone-topbar-tools">{state}</div></header>',
        unsafe_allow_html=True)


def page_header(eyebrow: str, title: str) -> None:
    st.markdown(f'<section class="dss-workspace-page-header"><div><div class="dss-workspace-eyebrow">'
                f'{html.escape(eyebrow)}</div><div class="dss-workspace-heading">{html.escape(title)}</div></div>'
                '</section>', unsafe_allow_html=True)


def footer() -> None:
    clone_footer()


def icon_svg(name: str, color: str = "#147783", size: int = 20) -> str:
    return (f'<svg class="dss-svg-icon" width="{size}" height="{size}" viewBox="0 0 20 20" fill="none" '
            f'stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{SVG_ICONS.get(name, SVG_ICONS["info"])}</svg>')


def tile_html(label: str, value: object, icon: str = "info") -> str:
    """One KPI tile (app/main.py's workspace_metric_card): icon, label and value, as given."""
    text = str(value)
    tone = "teal c1-text" if any(c.isalpha() for c in text) else ""
    return (f'<section class="dss-workspace-metric"><div class="dss-workspace-metric-top">'
            f'<span class="dss-workspace-metric-icon">{icon_svg(icon)}</span></div>'
            f'<div class="dss-workspace-metric-label">{html.escape(label)}</div>'
            f'<div class="dss-workspace-metric-value {tone}">{html.escape(text)}</div></section>')


def tiles(name: str, items: list[tuple]) -> None:
    """A row of KPI tiles: (label, value) or (label, value, icon)."""
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
def collapsible(name: str, title: str) -> Iterator[None]:
    """A collapsed card (app/ui_clone.py's clone_section, closed until opened)."""
    with st.container(key=f"clone-section-{name}"):
        with st.expander(title, expanded=False):
            yield


def chart_colors(frame: pd.Series | pd.DataFrame) -> str | list[str]:
    """The existing chart palette (ui_theme.style_figure's colorway), one colour per series."""
    palette = [ui_theme.TEAL, "#d9a441", "#5b7b87", "#b8c2cc", "#294d7e", "#a66a1f"]
    count = frame.shape[1] if isinstance(frame, pd.DataFrame) else 1
    return palette[0] if count == 1 else [palette[n % len(palette)] for n in range(count)]


def line_chart(data: pd.Series | pd.DataFrame) -> None:
    st.line_chart(data, color=chart_colors(data))


def bar_chart(data: pd.Series | pd.DataFrame) -> None:
    st.bar_chart(data, color=chart_colors(data))


def show_table(frame: pd.DataFrame) -> None:
    ui_theme.show_table(frame)


def first_rows_table(frame: pd.DataFrame, key: str, rows: int = 10) -> None:
    """A short sortable list in the clone-table style; the column names are shown as they are."""
    clone_table(frame.head(rows).reset_index(drop=True), key=key, labels={c: c for c in frame.columns}, page_size=rows)


def picker(label: str, options: list, key: str, **kwargs) -> object:
    """A medicine picker in the filter-bar panel."""
    with st.container(key=f"clone-medicine-filters-{key}"):
        return st.selectbox(label, options, key=key, **kwargs)


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
                                      format_func=lambda v: v if v != "" else "(blank)")
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
