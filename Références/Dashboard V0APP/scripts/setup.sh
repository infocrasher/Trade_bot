#!/usr/bin/env bash
# Setup and run the AlgoTrader Flask dashboard
set -e
pip install -r requirements.txt --quiet
python app.py
