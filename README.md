# CDH Pharmacy DSS (Demo)

A demonstration of the planning pages of the pharmaceutical inventory decision support system built for CDH as a thesis
project.

**Synthetic demo data only.** Every medicine, supplier, demand, stock, cost and expiry value in this repository is
synthetic: 80 made-up medicines ("DEMO MEDICINE 001" to "DEMO MEDICINE 080") and one "DEMO SUPPLIER", generated from a
fixed random seed. Six of them carry a Vital generic term (for example "DEMO GENERIC 024 (OXYTOCIN)"), so the ABC-VED
matrix shows Vital medicines in classes A, B and C. None of it comes from CDH, and every page of the app says so. The
real DSS runs locally on CDH's machine, on CDH's own data, and is not published here.

## Files

- `app/capstone1_app.py`: the Streamlit app, run in DEMO mode (five pages: This month's decisions, Reorder Planning,
  Waste and Expiry, Medicine Detail, and Analysis and Evidence).
- `app/c1_ui.py`, `app/c1_format.py`, `app/c1_theme.py`, `app/ui_*.py`, `app/ui_*.css`, `app/ui_clone_table.js`: the
  app's visual system (styles in light and dark mode, labels and number formats, tiles, cards, filter bars, tables).
- `app/assets/`: the Inter font files and their licence (SIL Open Font License, `INTER-LICENSE.txt`).
- `.streamlit/config.toml`: the light and dark themes (the app's top-bar toggle switches between them).
- `demo/capstone1_demo.duckdb`: the synthetic data mart the app reads (read-only).
- `requirements.txt`: every package, locked for Python 3.14.

## Running it

On Streamlit Community Cloud: Python 3.14, main file `app/capstone1_app.py`, and these Secrets:

```toml
CAPSTONE1_DEMO = "1"
CAPSTONE1_SUPPLEMENTARY = "0"
CAPSTONE1_DB = "demo/capstone1_demo.duckdb"
```

Locally, from the repository root, on Python 3.14:

```sh
pip install -r requirements.txt
CAPSTONE1_DEMO=1 CAPSTONE1_SUPPLEMENTARY=0 CAPSTONE1_DB=demo/capstone1_demo.duckdb streamlit run app/capstone1_app.py
```
