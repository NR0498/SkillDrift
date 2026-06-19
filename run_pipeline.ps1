$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Create .venv and install requirements-dev.txt first."
}

& $python ingest.py
& $python simulate_history.py --days 6
& $python indexer.py
& $python trend_engine.py
