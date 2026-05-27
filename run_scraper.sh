#!/bin/bash
# Flip Scraper — cron wrapper
# Invoked by cron at 6:00 AM every 4 days.
# Wrapper exists to safely handle the space in the project path.

PROJECT_DIR="/Users/williamparker/Downloads/flip_scraper 3/flip_scraper"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
LOG_FILE="$PROJECT_DIR/data/cron.log"

cd "$PROJECT_DIR" && "$PYTHON_BIN" main.py --hot-only >> "$LOG_FILE" 2>&1
