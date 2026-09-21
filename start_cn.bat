@echo off
REM Start CN Tmall Shavers backend on port 8011 (v2)
set LOCAL_MODEL_PATH=CN_TMALL_SHAVERS.pkl
set COGS_CSV_PATH=
echo Starting CN (Tmall Shavers) backend on port 8011...
uvicorn app.main:app --host 127.0.0.1 --port 8011 --reload
