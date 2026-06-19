#!/usr/bin/env sh
set -eu

python ingest.py
python simulate_history.py --days 6
python indexer.py
python trend_engine.py

