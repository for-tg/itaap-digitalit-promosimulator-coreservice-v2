@echo off
REM Start DE Amazon RTB backend on port 8010 (v2)
set LOCAL_MODEL_PATH=DE_Amazon_RTB.pkl
set COGS_CSV_PATH=COGS_per_SKU.csv
echo Starting DE (Amazon RTB) backend on port 8010...
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
