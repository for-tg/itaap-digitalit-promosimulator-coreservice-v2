# Local Testing — Quick Start

## Prerequisites

- Python 3.10+ (3.12 recommended)
- The pickle file: `cz_panel_2026_18May.pkl`
- Optional: `COGS_per_SKU.csv`

## Steps

### 1. Setup (one-time)

```cmd
cd itaap-digitalit-promosimulator-coreservice-main

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
pip install requests
```

### 2. Place data files

Copy the pickle and optional COGS file into this folder:

```cmd
copy ..\promo-simulator\cz_panel_2026_18May.pkl .
copy ..\promo-simulator\COGS_per_SKU.csv .
```

### 3. Start the server

```cmd
run_local.bat
```

This sets `PYTHONPATH` to include `local_stubs/` (which mocks the private `itaap-python-utils` package) and disables telemetry. The server starts at http://localhost:9000.

You should see a log line like:
```
Engine initialized: XX SKUs, panel shape (XXXX, XX)
```

### 4. Run the test script (in a separate terminal)

```cmd
venv\Scripts\activate
python test_local.py
```

This tests:
- Health check (model loaded?)
- SKU listing
- Retro simulation (unconstrained + constrained + turnover mode)
- Plan simulation

### 5. Manual testing with Swagger

Open http://localhost:9000/docs in your browser to use FastAPI's interactive Swagger UI.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: itaap_python_utils` | Use `run_local.bat` (not `python -m app.main` directly) |
| `FileNotFoundError: cz_panel_2026_18May.pkl` | Copy the pickle file into this folder |
| `econml` install fails | Try: `pip install econml --no-build-isolation` |
| Server starts but health returns `loading` | Pickle file found but may be corrupt — check logs |
| `ConnectionError` in test script | Server isn't running — start it first in another terminal |
