# CDH Pharmacy DSS (Demo)

A demonstration of the planning pages of the pharmaceutical inventory decision support system built for CDH as a thesis
project.

**Synthetic demo data only.** Every medicine, supplier, demand, stock, cost and expiry value in this repository is
synthetic: 80 made-up medicines ("DEMO MEDICINE 001" to "DEMO MEDICINE 080") and one "DEMO SUPPLIER", generated from a
fixed random seed. None of it comes from CDH, and every page of the app says so. The real DSS runs locally on CDH's
machine, on CDH's own data, and is not published here.

## Files

- `app/capstone1_app.py`: the Streamlit app, run in DEMO mode.
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
