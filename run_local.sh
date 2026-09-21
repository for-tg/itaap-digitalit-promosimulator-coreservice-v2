#!/bin/bash
# Run the Promo Simulator Core Service locally using stubs for itaap-python-utils.
# Prerequisites: pip install -r requirements.txt

export PYTHONPATH="$(dirname "$0")/local_stubs:${PYTHONPATH}"
export SEND_TELEMETRY_DATA=false

echo "Starting Promo Simulator Core Service (local mode)..."
echo "Make sure cz_panel_2026_18May.pkl is in this folder."
echo ""

python -m app.main
