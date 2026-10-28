"""Light and dark mode for the Capstone 1 pages, in the existing app's look.

Light mode is the existing visual system unchanged. Dark mode is the same stylesheets with every colour passed through
one documented mapping (dark()): the hue is kept, the lightness is mirrored (L' = 0.11 + 0.80 (1 - L)), so white
cards become dark navy surfaces, navy text becomes light, and the teal accent becomes a lighter teal. Greys take the
navy hue of the ink so dark surfaces keep the DSS tint. The tokens (TOKENS) are the CSS variables of the new rules; the
contrast of each text and surface pair is checked in both modes (tests/test_c1_theme.py). .streamlit/config.toml holds
the same light and dark colours for Streamlit's own widgets, tables and charts.

The mode is the one Streamlit reports for the browser (st.context.theme.type): its settings menu, the operating system
or the top-bar toggle, which stores the choice the way the settings menu does and reloads the page.
"""

from __future__ import annotations

import colorsys
import re
from functools import lru_cache
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
NAVY_HUE = 0.61            # the ink's hue (#14264a), given to greys in dark mode
TOKENS = {                  # light values: the existing app's colours (app/ui_theme.py, app/ui_clone.css)
    "ink": "#14264a", "text": "#3d4f5f", "muted": "#5b6b7b", "line": "#e3e8eb", "canvas": "#f3f7f8",
    "surface": "#ffffff", "sidebar": "#eff4f5", "teal": "#1f6f78", "teal-strong": "#145e59", "teal-soft": "#eaf3f3",
    "header-fill": "#eaf3f3", "amber": "#8f5a12", "amber-soft": "#fbf2dd", "red": "#b42318", "red-soft": "#fdecea",
    "on-teal": "#ffffff", "amber-cell": "#d9a441", "on-amber": "#14264a",
}
# Text on a coloured fill stays dark in dark mode (the fill turns light): these tokens take their dark value here.
DARK_OVERRIDES = {"on-amber": "#151a23"}
# Text and surface pairs that must reach WCAG AA (4.5:1) in both modes.
TEXT_PAIRS = [("ink", "surface"), ("ink", "canvas"), ("text", "surface"), ("muted", "surface"), ("muted", "canvas"),
              ("teal", "surface"), ("teal", "teal-soft"), ("ink", "teal-soft"), ("on-teal", "teal"),
              ("amber", "surface"), ("ink", "amber-soft"), ("red", "surface"), ("ink", "red-soft"), ("ink", "sidebar"),
              ("muted", "sidebar"), ("on-amber", "amber-cell")]
HEX = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(,\s*[\d.]+\s*)?\)")
NAMED = re.compile(r"(?<![-\w#])(white|black)(?![-\w])")


def _dark_rgb(r: float, g: float, b: float) -> tuple[float, float, float]:
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.06:                                    # greys take the navy tint
        h, s = NAVY_HUE, 0.28
    return colorsys.hls_to_rgb(h, 0.11 + 0.80 * (1 - l), s * (0.85 if l > 0.5 else 1.0))


def dark(color: str) -> str:
    """The dark-mode counterpart of a #rgb, #rrggbb or #rrggbbaa colour."""
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    alpha = value[6:8]
    r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return "#" + "".join(f"{round(c * 255):02x}" for c in _dark_rgb(r, g, b)) + alpha


def token(name: str, mode: str = "light") -> str:
    if mode != "dark":
        return TOKENS[name]
    return DARK_OVERRIDES.get(name) or dark(TOKENS[name])


def color(value: str, mode: str) -> str:
    return dark(value) if mode == "dark" and value.startswith("#") else value


def css_for(css: str, mode: str) -> str:
    """A stylesheet in the given mode: unchanged for light; every colour mapped by dark() for dark."""
    if mode != "dark":
        return css
    css = HEX.sub(lambda m: dark(m.group(0)), css)

    def rgb(match: re.Match) -> str:
        r, g, b = (int(match.group(i)) / 255 for i in (1, 2, 3))
        red, green, blue = (round(c * 255) for c in _dark_rgb(r, g, b))
        alpha = match.group(4) or ""
        return f"rgba({red},{green},{blue}{alpha})" if alpha else f"rgb({red},{green},{blue})"
    css = RGB.sub(rgb, css)
    css = re.sub(r"color-scheme:\s*light", "color-scheme: dark", css)        # scrollbars and native controls
    return NAMED.sub(lambda m: dark("#ffffff" if m.group(1) == "white" else "#000000"), css)


def mode() -> str:
    """'dark' or 'light': the mode the browser shows (light when unknown, as in tests)."""
    try:
        kind = st.context.theme.type
    except Exception:  # noqa: BLE001 - no browser context
        kind = None
    return "dark" if kind == "dark" else "light"


def variables(mode_: str) -> str:
    return ":root{" + ";".join(f"--c1-{name}:{token(name, mode_)}" for name in TOKENS) + "}"


def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")[:6]
    channels = []
    for i in (0, 2, 4):
        c = int(value[i:i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(foreground: str, background: str) -> float:
    a, b = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def palette(mode_: str) -> list[str]:
    """The chart colours (ui_theme.style_figure's colorway) in the mode."""
    base = [TOKENS["teal"], "#d9a441", "#5b7b87", "#b8c2cc", "#294d7e", "#a66a1f"]
    return [color(c, mode_) for c in base]


# ------------------------------------------------------------------ the top-bar toggle

TOGGLE_JS = """
export default function ({ parentElement, data }) {
  const dark = data?.mode === 'dark';
  let button = parentElement.querySelector('button');
  if (!button) { button = document.createElement('button'); parentElement.appendChild(button); }
  button.type = 'button';
  button.className = 'c1-mode-toggle';
  button.setAttribute('aria-pressed', String(dark));
  button.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
  button.textContent = dark ? '\\u2600 Light mode' : '\\u263E Dark mode';
  button.onclick = () => {
    // Stored as Streamlit's settings menu stores the theme (per page path), then the page reloads in that mode.
    const value = JSON.stringify(dark ? 'Light' : 'Dark');
    // every page under the same base (on Community Cloud the app runs under /~/+/), so a reload of any page keeps it
    const here = window.location.pathname;
    const base = here.slice(0, here.lastIndexOf('/') + 1);
    const paths = new Set([here, ...(data?.paths || []).map(p => base + p.replace(/^\\//, ''))]);
    try { for (const path of paths) window.localStorage.setItem(`stActiveTheme-${path}-v2`, value); } catch (e) {}
    window.location.reload();
  };
}
"""
TOGGLE_CSS = """
.c1-mode-toggle{font:500 15px/1 Inter,sans-serif;color:var(--c1-ink);background:var(--c1-surface);
  border:1px solid var(--c1-line);border-radius:999px;padding:9px 16px;cursor:pointer;white-space:nowrap}
.c1-mode-toggle:hover{border-color:var(--c1-teal);color:var(--c1-teal)}
.c1-mode-toggle:focus-visible{outline:2px solid var(--c1-teal);outline-offset:2px}
"""


def _toggle():
    from streamlit.components.v2 import component
    return component("c1_mode_toggle", css=TOGGLE_CSS, js=TOGGLE_JS, isolate_styles=True)


def toggle(current: str, paths: list[str]) -> None:
    _toggle()(key="c1-mode-toggle", data={"mode": current, "paths": paths})


@lru_cache(maxsize=8)
def stylesheet(name: str, mode_: str) -> str:
    return css_for((APP_DIR / name).read_text(encoding="utf-8"), mode_)
